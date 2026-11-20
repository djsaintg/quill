"""Quill: Claude Code as a little desk robot with a speech bubble."""
import os
import sys
import time

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Markdown, Static

from .engine import Engine, describe_tool
from .sprites import PALETTE, frame

__version__ = "0.1.0"
BG = "#1a1c2c"

GREETING = ("Hi! I'm **Quill**, your desk robot. "
            "Ask me anything, or tell me what we're working on.\n\n"
            "*Esc stops me mid-answer · F2 shows our chat so far · /help for more*")

HELP = """**Things you can type**

- Anything: it goes straight to Claude Code
- `/history` (or F2): the whole chat so far
- `/new`: start a fresh conversation
- `/quit`: leave (Ctrl+Q works too)
- Other `/commands` and skills are passed to Claude Code

**Keys**: Esc = stop me · F2 = history · Ctrl+Q = quit"""


def render_sprite(sprite, scale=2):
    """Half-block pixels: one text cell = 1 pixel wide, 2 pixels tall."""
    rows = [r for r in sprite for _ in range(scale)]
    rows = ["".join(ch * scale for ch in r) for r in rows]
    out = Text(no_wrap=True)
    for top, bot in zip(rows[0::2], rows[1::2]):
        for t, b in zip(top, bot):
            out.append("▀", style=f"{PALETTE.get(t, BG)} on {PALETTE.get(b, BG)}")
        out.append("\n")
    return out


def nice_path(path):
    if not path:
        return ""
    rel = os.path.relpath(path)
    return rel if not rel.startswith("..") else path.replace(os.path.expanduser("~"), "~", 1)


def permission_text(tool, inp, desc):
    inp = dict(inp or {})
    if inp.get("file_path"):
        inp["file_path"] = nice_path(inp["file_path"])
    if tool == "Bash":
        body = f"```bash\n{inp.get('command', '')}\n```"
        if inp.get("description"):
            body = f"{inp['description']}\n\n" + body
        return f"**Can I run this command?**\n\n{body}"
    if tool in ("Edit", "MultiEdit"):
        old = (inp.get("old_string") or "").splitlines()[:12]
        new = (inp.get("new_string") or "").splitlines()[:12]
        diff = "\n".join([f"- {l}" for l in old] + [f"+ {l}" for l in new])
        return f"**Can I edit `{inp.get('file_path', '')}`?**\n\n```diff\n{diff}\n```"
    if tool == "Write":
        lines = (inp.get("content") or "").splitlines()
        more = f"\n… (+{len(lines) - 15} more lines)" if len(lines) > 15 else ""
        return (f"**Can I write `{inp.get('file_path', '')}`?**\n\n```\n"
                + "\n".join(lines[:15]) + more + "\n```")
    if tool == "ExitPlanMode":
        return f"**Here's my plan. Shall I go ahead?**\n\n{inp.get('plan', '')}"
    if tool == "WebFetch":
        return f"**Can I open this page?**\n\n{inp.get('url', '')}"
    shown = ", ".join(f"{k}: {str(v)[:80]}" for k, v in list(inp.items())[:5])
    return f"**Can I use {desc or tool}?**\n\n`{shown}`"


class History(ModalScreen):
    BINDINGS = [Binding("escape,f2", "dismiss", "Close")]

    def __init__(self, log):
        super().__init__()
        self.log_items = log

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="hist"):
            yield Static("CHAT SO FAR  (Esc to close)", id="hist-title")
            if not self.log_items:
                yield Static("Nothing yet.")
            for who, text in self.log_items:
                yield Static("you" if who == "you" else "quill",
                             classes=f"who {who}")
                yield Markdown(text, classes=f"msg {who}")

    def on_mount(self):
        self.query_one("#hist").scroll_end(animate=False)


class QuillApp(App):
    TITLE = "Quill"
    CSS = f"""
    Screen {{ background: {BG}; color: #f4f4f4; }}
    #title {{ height: 1; background: #333c57; color: #ffcd75; padding: 0 1; text-style: bold; }}
    #stage {{ height: 1fr; min-height: 19; padding: 1 1 0 1; }}
    #quill {{ width: 34; height: 18; }}
    #tail {{ width: 1; margin-top: 2; color: #41a6f6; }}
    #bubble {{ border: round #41a6f6; background: {BG}; padding: 0;
               height: auto; max-height: 100%; scrollbar-size-vertical: 1; }}
    #bubble Markdown {{ background: #333c57; margin: 0; padding: 0 1; height: auto; }}
    #status {{ height: 1; color: #94b0c2; padding: 0 2; }}
    #choices {{ height: auto; padding: 0 2; display: none; }}
    #choices.show {{ display: block; }}
    #choices Button {{ margin: 0 1 0 0; min-width: 8; }}
    #choices Button.picked {{ background: #38b764; }}
    #you {{ height: auto; max-height: 3; color: #94b0c2; padding: 0 2; }}
    #input {{ border: round #ffcd75; background: {BG}; margin: 0 1; background-tint: 0%; }}
    #input:focus {{ border: round #ffcd75; background-tint: 0%; }}
    #hints {{ height: 1; color: #566c86; padding: 0 2; }}
    History {{ align: center middle; background: {BG} 80%; }}
    #hist {{ width: 90%; height: 90%; border: round #41a6f6; background: {BG}; padding: 0 1; }}
    #hist-title {{ color: #ffcd75; text-style: bold; margin-bottom: 1; }}
    .who {{ text-style: bold; margin-top: 1; }}
    .who.you {{ color: #ffcd75; }}
    .who.quill {{ color: #73eff7; }}
    .msg {{ background: #333c57; padding: 0 1; margin: 0; }}
    """
    BINDINGS = [
        Binding("escape", "stop", "Stop", show=False),
        Binding("f2", "history", "History", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self, claude_args):
        super().__init__()
        self.claude_args = claude_args
        self.engine = None
        self.model = ""
        self.busy = False
        self.tool_active = False
        self.turn_text = ""
        self.streamed_ids = set()
        self.dirty = False
        self.flushing = False
        self.override = None
        self.last_delta = 0.0
        self.mood = None
        self.mood_until = 0.0
        self.tick = 0
        self.last_frame = None
        self.pending = None  # the control_request we're waiting on you for
        self.q_index = 0
        self.q_answers = {}
        self.q_picked = set()
        self.log_items = []

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        yield Static("", id="title")
        with Horizontal(id="stage"):
            yield Static("", id="quill")
            yield Static("◀", id="tail")
            with VerticalScroll(id="bubble"):
                yield Markdown(GREETING, id="say")
        yield Static("", id="status")
        yield Horizontal(id="choices")
        yield Static("", id="you")
        yield Input(placeholder="Talk to Quill…", id="input")
        yield Static("Enter send · Esc stop · F2 history · Ctrl+Q quit", id="hints")

    def on_mount(self):
        self.set_title()
        self.set_interval(0.15, self.animate)
        self.set_interval(0.1, self.flush)
        self.query_one("#input").focus()
        self.start_engine()

    def set_title(self):
        folder = os.path.basename(os.getcwd()) or "/"
        bits = ["QUILL", folder] + ([self.model] if self.model else [])
        self.query_one("#title", Static).update("  ·  ".join(bits))

    def status(self, text):
        self.query_one("#status", Static).update(text)

    def show(self, md):
        """Put something other than the live reply in the bubble."""
        self.override = md
        self.dirty = True

    def show_reply(self):
        self.override = None
        self.dirty = True

    def feel(self, mood, secs=1.5):
        self.mood, self.mood_until = mood, time.monotonic() + secs

    # ---------- animation ----------
    def animate(self):
        self.tick += 1
        now = time.monotonic()
        if self.pending:
            face, bulb = "ask", ("ask" if self.tick % 4 < 2 else "off")
        elif now - self.last_delta < 0.4:
            face, bulb = ("talk1" if self.tick % 2 else "talk2"), "think"
        elif self.busy and self.tool_active:
            face, bulb = ("workL" if (self.tick // 4) % 2 else "workR"), "work"
        elif self.busy:
            face, bulb = f"think{(self.tick // 3) % 3 + 1}", "think"
        elif self.mood and now < self.mood_until:
            face, bulb = self.mood, ("happy" if self.mood == "happy" else "ask")
        else:
            face, bulb = ("blink" if self.tick % 28 == 0 else "idle"), "idle"
        if (face, bulb) != self.last_frame:
            self.last_frame = (face, bulb)
            self.query_one("#quill", Static).update(render_sprite(frame(face, bulb)))

    async def flush(self):
        if self.dirty and not self.flushing:
            self.dirty, self.flushing = False, True
            text = self.override if self.override is not None else (self.turn_text or "…")
            try:
                await self.query_one("#say", Markdown).update(text)
                self.query_one("#bubble").scroll_end(animate=False)
            finally:
                self.flushing = False

    # ---------- talking to Claude ----------
    @work(exclusive=True, group="engine")
    async def start_engine(self, fresh=False):
        if self.engine:
            await self.engine.stop()
        args = [a for a in self.claude_args if not fresh or a not in ("-c", "--continue")]
        self.engine = Engine(args)
        try:
            await self.engine.start()
        except Exception as e:  # noqa: BLE001
            self.show(f"**I couldn't start Claude Code.**\n\n`{e}`")
            self.feel("sad", 5)
            return
        self.status("Ready")
        async for ev in self.engine.events():
            try:
                await self.handle(ev)
            except Exception as e:  # noqa: BLE001 - one bad message shouldn't kill the session
                self.status(f"(skipped a message I didn't understand: {e})")
        # Claude exited
        self.busy = False
        tail = "\n".join(self.engine.stderr_tail[-6:])
        self.show("**Claude Code stopped.**\n\n"
                  + (f"```\n{tail}\n```\n\n" if tail else "")
                  + "Type `/new` to start again.")
        self.feel("sad", 8)
        self.status("Not connected")

    async def handle(self, ev):
        t = ev.get("type")
        sub_agent = ev.get("parent_tool_use_id") is not None

        if t == "system" and ev.get("subtype") == "init":
            self.model = ev.get("model", "")
            self.set_title()

        elif t == "stream_event" and not sub_agent:
            e = ev.get("event", {})
            if e.get("type") == "message_start":
                self.streamed_ids.add(e.get("message", {}).get("id"))
            elif e.get("type") == "content_block_start":
                block = e.get("content_block", {})
                if block.get("type") == "text":
                    self.tool_active = False
                    if self.turn_text and not self.turn_text.endswith("\n\n"):
                        self.turn_text += "\n\n"
                elif block.get("type") == "thinking":
                    self.status("Thinking…")
            elif e.get("type") == "content_block_delta":
                d = e.get("delta", {})
                if d.get("type") == "text_delta":
                    self.turn_text += d.get("text", "")
                    self.last_delta = time.monotonic()
                    if not self.pending:
                        self.show_reply()

        elif t == "assistant":
            msg = ev.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    if sub_agent:
                        self.status("A helper is working…")
                    else:
                        self.tool_active = True
                        self.status(describe_tool(block.get("name"), block.get("input")))
                elif (block.get("type") == "text" and not sub_agent
                      and msg.get("id") not in self.streamed_ids):
                    self.turn_text += ("\n\n" if self.turn_text else "") + block.get("text", "")
                    if not self.pending:
                        self.show_reply()

        elif t == "control_request":
            req = ev.get("request", {})
            if req.get("subtype") == "can_use_tool":
                self.ask(ev["request_id"], req)

        elif t == "result":
            self.busy = False
            self.tool_active = False
            if ev.get("is_error") or ev.get("subtype", "success") != "success":
                err = ev.get("result") or ev.get("subtype", "error")
                if not self.turn_text:
                    self.turn_text = f"Something went wrong:\n\n`{err}`"
                self.feel("sad", 4)
                self.status("Stopped")
            else:
                self.feel("happy", 1.5)
                self.status("Done")
            if self.turn_text:
                self.log_items.append(("quill", self.turn_text))
            self.show_reply()

    # ---------- questions & permissions ----------
    def ask(self, request_id, req):
        self.pending = {"id": request_id, **req}
        if req.get("tool_name") == "AskUserQuestion":
            self.q_index, self.q_answers = 0, {}
            self.show_question()
            return
        tool = req.get("tool_name", "")
        self.show(permission_text(tool, req.get("input"), req.get("display_name")))
        buttons = [Button("Yes", id="perm-yes", variant="success")]
        if req.get("permission_suggestions"):
            buttons.append(Button("Yes, and don't ask again", id="perm-always", variant="primary"))
        buttons.append(Button("No", id="perm-no", variant="error"))
        self.set_choices(buttons)
        self.status("Waiting for you: Yes / No, or type what to do instead")

    def show_question(self):
        qs = self.pending["input"].get("questions", [])
        q = qs[self.q_index]
        self.q_picked = set()
        opts = q.get("options", [])
        lines = [f"**{q.get('question', '')}**", ""]
        for o in opts:
            lines.append(f"- **{o.get('label')}**: {o.get('description', '')}")
        lines += ["", "*Pick one, or type your own answer below.*"]
        self.show("\n".join(lines))
        buttons = [Button(o.get("label", "?"), id=f"opt-{i}") for i, o in enumerate(opts)]
        if q.get("multiSelect"):
            buttons.append(Button("Done", id="opt-done", variant="success"))
        self.set_choices(buttons)
        self.status(f"Question {self.q_index + 1} of {len(qs)}")

    def set_choices(self, buttons):
        box = self.query_one("#choices")
        box.remove_children()
        box.mount_all(buttons)
        box.add_class("show")
        if buttons:
            self.call_after_refresh(buttons[0].focus)

    def clear_choices(self):
        box = self.query_one("#choices")
        box.remove_children()
        box.remove_class("show")
        self.query_one("#input").focus()

    async def finish_pending(self, response):
        req = self.pending
        self.pending = None
        self.clear_choices()
        self.show_reply()
        self.status("Thanks! Carrying on…")
        await self.engine.answer(req["id"], response)

    async def answer_question(self, answer):
        q = self.pending["input"]["questions"][self.q_index]
        self.q_answers[q.get("question", "")] = answer
        self.log_items.append(("you", f"{q.get('question')}: **{answer}**"))
        self.q_index += 1
        if self.q_index < len(self.pending["input"]["questions"]):
            self.show_question()
        else:
            inp = dict(self.pending["input"], answers=self.q_answers)
            await self.finish_pending({"behavior": "allow", "updatedInput": inp})

    @on(Button.Pressed)
    async def pressed(self, event):
        if not self.pending:
            return
        bid = event.button.id or ""
        req = self.pending
        if bid == "perm-yes":
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {})})
        elif bid == "perm-always":
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {}),
                                       "updatedPermissions": req.get("permission_suggestions", [])})
        elif bid == "perm-no":
            await self.finish_pending({"behavior": "deny", "message": "The user said no."})
        elif bid.startswith("opt-"):
            q = req["input"]["questions"][self.q_index]
            if bid == "opt-done":
                await self.answer_question(", ".join(sorted(self.q_picked)) or "(none)")
                return
            label = q["options"][int(bid[4:])].get("label", "")
            if q.get("multiSelect"):
                self.q_picked ^= {label}
                event.button.set_class(label in self.q_picked, "picked")
            else:
                await self.answer_question(label)

    # ---------- your input ----------
    @on(Input.Submitted, "#input")
    async def submitted(self, event):
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if self.pending:
            if self.pending.get("tool_name") == "AskUserQuestion":
                await self.answer_question(text)
            else:
                self.log_items.append(("you", text))
                await self.finish_pending({"behavior": "deny",
                                           "message": f"The user said no, and instead: {text}"})
            return
        cmd = text.lower()
        if cmd in ("/quit", "/exit"):
            await self.action_quit()
            return
        if cmd == "/help":
            self.show(HELP)
            return
        if cmd == "/history":
            self.action_history()
            return
        if cmd in ("/new", "/clear"):
            self.log_items, self.turn_text, self.busy = [], "", False
            self.show("Fresh start! What's next?")
            self.query_one("#you", Static).update("")
            self.start_engine(fresh=True)
            return
        if not self.engine or not self.engine.proc or self.engine.proc.returncode is not None:
            self.show("I'm not connected to Claude Code. Type `/new` to start again.")
            return
        self.log_items.append(("you", text))
        self.query_one("#you", Static).update(Text("you: " + text, overflow="ellipsis"))
        if not self.busy:
            self.turn_text = ""
            self.show("…")
        self.busy = True
        self.status("Thinking…")
        await self.engine.say(text)

    async def action_stop(self):
        if self.busy and self.engine:
            if self.pending:
                await self.finish_pending({"behavior": "deny", "message": "The user stopped you."})
            await self.engine.interrupt()
            self.status("Stopping…")

    def action_history(self):
        self.push_screen(History(self.log_items))

    async def action_quit(self):
        if self.engine:
            await self.engine.stop()
        self.exit()


def main():
    args = sys.argv[1:]
    if args and args[0] in ("--version", "-v"):
        print(f"Quill {__version__}")
        return
    if args and args[0] in ("--help", "-h"):
        print("quill [claude flags]   e.g. quill -c  (continue last chat),"
              " quill --resume <id>, quill --model sonnet")
        return
    QuillApp(args).run()


if __name__ == "__main__":
    main()
