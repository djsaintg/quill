"""Quill: Claude Code as a little desk robot with a speech bubble."""
import asyncio
import os
import shutil
import subprocess
import sys
import time

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Button, Input, Markdown, Static, TextArea

from . import notify, perms, sessions, sudo
from .engine import Engine, clean_env, describe_result, describe_tool, find_claude, past_tense
from . import themes
from .sprites import CHARACTERS, PALETTE, sprite

__version__ = "0.4.0"
BG = "#1a1c2c"

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

GREETING = ("Hi! I'm **Quill**, your desk robot. "
            "Ask me anything, or tell me what we're working on.\n\n"
            "*Esc stops me mid-answer · F2 shows our chat so far · F3 copies my reply · /help for more*")

NEW_LINE_KEYS = ("shift+enter", "alt+enter", "ctrl+j")

# Told to Claude Code at the start of every Quill/Plume chat (with the sudo note).
TEST_REPO_NOTE = (
    "Test repos: when the user asks for a 'test repo' (or test project / test folder), it is "
    "throwaway, only for testing something and noting the issues or changes they find. Make it a "
    "plain local folder: never add a git remote, create a GitHub repo, commit or push it. Keep its "
    "notes up to date as you go. When the user ends the chat (e.g. says 'wrap up'), first give a "
    "short summary of what it recorded so the findings can be carried over, then delete the test "
    "folder without asking; that is already approved. Only delete the folder you made for the test "
    "in this chat; if it has a git remote or the user said to keep it, ask instead."
)


def strip_resume(args):
    """Drop -c/--continue and -r/--resume <id> so we can start fresh or resume another chat."""
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-c", "--continue"):
            continue
        if a in ("-r", "--resume"):
            skip = True
            continue
        if a.startswith("--resume="):
            continue
        out.append(a)
    return out


class ChatBox(TextArea):
    """Your input: wraps and grows as you type.

    Enter sends. A new line: end the line with \\ then Enter (like Claude Code),
    or Ctrl+J, or Shift/Alt+Enter in terminals that send those differently from Enter.
    """

    class Submitted(Message):
        def __init__(self, box, text):
            super().__init__()
            self.box, self.text = box, text

    async def _on_key(self, event):
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            row, col = self.cursor_location
            if col and self.document.get_line(row)[col - 1] == "\\":
                self.delete((row, col - 1), (row, col))  # "\" + Enter = new line
                self.insert("\n")
                return
            self.post_message(self.Submitted(self, self.text))
            return
        if event.key in NEW_LINE_KEYS:
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        await super()._on_key(event)

HELP = """**Things you can type**

- Anything: it goes straight to Claude Code
- `/history` (or F2): the whole chat so far
- `/copy` (or F3): copy Quill's last reply
- Drag over any text with the mouse, then Ctrl+C, to copy just that part
- `/new`: start a fresh conversation
- `/resume`: pick a project to pick up again
- `\\` then Enter (or Ctrl+J): new line in your message
- `/sudo`: let Quill use sudo (or `/sudo off`)
- `/character` (or `/character quill` / `/character plume`): switch between Quill and Plume
- `/name` (or `/name Sam`): what I call you
- `/theme` (or `/theme classic` / `/theme aurora`): change this character's colours
- `/exit` (or Ctrl+Q): leave and close this terminal window
- `/terminal`: leave Quill but keep the terminal open
- `/remote-control` (or `/rc`): carry on this chat from your phone or claude.ai (`/rc off` to stop)
- `/notify off` / `/notify on`: desktop pop-ups when I need you or finish a long job
- Other `/commands` and skills are passed to Claude Code

**Keys**: Esc = stop me · F2 = history · F3 = copy reply · Ctrl+Q = quit"""


def render_sprite(rows_in, scale=2, pal=None, bg=BG):
    """Half-block pixels: one text cell = 1 pixel wide, 2 pixels tall."""
    pal = pal or PALETTE
    rows = [r for r in rows_in for _ in range(scale)]
    rows = ["".join(ch * scale for ch in r) for r in rows]
    out = Text(no_wrap=True)
    for top, bot in zip(rows[0::2], rows[1::2]):
        for t, b in zip(top, bot):
            out.append("▀", style=f"{pal.get(t, bg)} on {pal.get(b, bg)}")
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
        # Inline code wraps; a fenced block would cut long commands off.
        cmd = "  \n".join(f"`` {l} ``" for l in inp.get("command", "").splitlines())
        body = f"> {cmd}"
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
        return (f"**Can I write `{inp.get('file_path', '')}`?**\n\n```text\n"
                + "\n".join(lines[:15]) + more + "\n```")
    if tool == "ExitPlanMode":
        return f"**Here's my plan. Shall I go ahead?**\n\n{inp.get('plan', '')}"
    if tool == "Read":
        return f"**Can I read `{inp.get('file_path', '')}`?**"
    if tool == "WebFetch":
        return f"**Can I open this page?**\n\n{inp.get('url', '')}"
    shown = ", ".join(f"{k}: {str(v)[:80]}" for k, v in list(inp.items())[:5])
    return f"**Can I use {desc or tool}?**\n\n`{shown}`"


class History(ModalScreen):
    BINDINGS = [Binding("escape,f2", "dismiss", "Close")]

    def __init__(self, log, name="quill"):
        super().__init__()
        self.log_items, self.char = log, name

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="hist"):
            yield Static("CHAT SO FAR  (Esc to close)", id="hist-title")
            if not self.log_items:
                yield Static("Nothing yet.")
            for who, text in self.log_items:
                yield Static("you" if who == "you" else self.char,
                             classes=f"who {who}")
                yield Markdown(text, classes=f"msg {who}")

    def on_mount(self):
        self.query_one("#hist").scroll_end(animate=False)


class Chooser(Screen):
    """First start: pick Quill (left, classic colours) or Plume (right, aurora colours)."""

    BINDINGS = [Binding("left", "focus_side('quill')", show=False),
                Binding("right", "focus_side('plume')", show=False)]
    SIDES = (("quill", "classic"), ("plume", "aurora"))

    def __init__(self, prefer=None):
        super().__init__()
        self.prefer = prefer or "quill"

    def compose(self) -> ComposeResult:
        yield Static("Who would you like on your desk?", id="ch-title")
        with Horizontal(id="ch-halves"):
            for who, theme in self.SIDES:
                with Vertical(classes="half", id=f"half-{who}"):
                    yield Static("", classes="ch-sprite", id=f"spr-{who}")
                    yield Button(who.capitalize(), id=f"pick-{who}")
        yield Static("Click one, or use ← → and Enter. Switch any time with /character.", id="ch-foot")

    def on_mount(self):
        for who, theme in self.SIDES:
            t = themes.THEMES[theme]
            half = self.query_one(f"#half-{who}")
            half.styles.background = t["bg"]
            half.styles.border = ("round", t["accent"])
            half.border_title = "classic colours" if theme == "classic" else "aurora colours"
            half.styles.border_title_color = t["accent"]
            b = self.query_one(f"#pick-{who}", Button)
            b.styles.background = t["primary"]
            b.styles.color = "#ffffff"
            b.styles.border_top = ("tall", t["accent"])
            b.styles.border_bottom = ("tall", t["primary"])
        self.tick = 0
        self.animate()
        self.set_interval(0.25, self.animate)
        self.query_one(f"#pick-{self.prefer}").focus()

    def animate(self):
        """Both float gently (out of step with each other) and blink now and then."""
        self.tick += 1
        scale = 2 if self.app.size.height >= 34 else 1
        for i, (who, theme) in enumerate(self.SIDES):
            blink = (self.tick + 9 * i) % 23 == 0
            art = sprite(who, "blink" if blink else "idle", "idle")
            if who == "quill":
                art = ["." * 16] * 2 + art  # same height as Plume
            spr = self.query_one(f"#spr-{who}", Static)
            spr.update(render_sprite(art, scale, themes.palette(theme), themes.THEMES[theme]["bg"]))
            spr.styles.margin = (1 if (self.tick // 3 + i) % 2 else 0, 0, 0, 0)

    def action_focus_side(self, who):
        self.query_one(f"#pick-{who}").focus()

    @on(Button.Pressed)
    def picked(self, event):
        self.dismiss((event.button.id or "pick-quill")[5:])


class QuillApp(App):
    TITLE = "Quill"
    CSS = """
    Screen { background: $q-bg; color: $q-ink; }
    #title { height: 1; background: $q-panel; color: $q-title; padding: 0 1; text-style: bold; }
    #stage { height: 1fr; padding: 1 1 0 1; }
    #stage.small { padding: 0 1; }
    #quill { width: 34; height: auto; }
    #stage.small #quill { width: 17; height: auto; }
    #stage.small #tail { margin-top: 1; }
    #tail { width: 1; margin-top: 3; color: $q-accent; }
    #bubble { border: round $q-accent; background: $q-bg; padding: 0;
              height: auto; max-height: 100%; scrollbar-size-vertical: 1; }
    #bubble Markdown { background: $q-panel; margin: 0; padding: 0 1; height: auto; }
    #turn { height: auto; display: none; }
    .step { background: $q-panel; color: $q-muted; padding: 0 1; height: 1;
             text-wrap: nowrap; text-overflow: ellipsis; }
    #turn Markdown.after { padding: 1 1 0 1; }
    .step.run { color: $q-accent; }
    .step.err { color: $error; }
    #status { height: 1; color: $q-muted; padding: 0 2; }
    #choices { height: auto; padding: 0 2; display: none; }
    #choices.show { display: block; }
    #choices Button { margin: 0 1 0 0; min-width: 8; }
    #choices Button.picked { background: $q-picked; }
    .sudo-pw { width: 32; border: round $error; background: $q-bg; background-tint: 0%; margin: 0 1 0 0; }
    #title.sudo { background: $q-sudo; }
    #you { height: auto; max-height: 3; color: $q-muted; padding: 0 2; }
    #input { border: round $q-input; background: $q-bg; margin: 0 1; padding: 0 1;
             height: auto; max-height: 10; background-tint: 0%; }
    #input:focus { border: round $q-input; background-tint: 0%; }
    #input .text-area--cursor-line { background: $q-bg; }
    #hints { height: 1; color: $q-hint; padding: 0 2; }
    History { align: center middle; background: $q-bg 80%; }
    #hist { width: 90%; height: 90%; border: round $q-accent; background: $q-bg; padding: 0 1; }
    #hist-title { color: $q-title; text-style: bold; margin-bottom: 1; }
    .who { text-style: bold; margin-top: 1; }
    .who.you { color: $q-title; }
    .who.quill { color: $q-accent; }
    .msg { background: $q-panel; padding: 0 1; margin: 0; }
    Chooser { background: $q-bg; }
    #ch-title { width: 100%; content-align: center middle; height: 3; color: $q-title; text-style: bold; }
    #ch-halves { height: 1fr; }
    .half { width: 1fr; height: 100%; align: center middle; margin: 0 1; }
    .half Static.ch-sprite { width: auto; height: auto; }
    .half Button { width: 20; margin-top: 1; text-style: bold; }
    .half Button:focus { text-style: bold reverse; }
    #ch-foot { width: 100%; content-align: center middle; height: 2; color: $q-hint; }
    """
    BINDINGS = [
        Binding("escape", "stop", "Stop", show=False),
        Binding("f2", "history", "History", show=False),
        Binding("f3", "copy_reply", "Copy reply", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self, claude_args):
        super().__init__()
        self.claude_args = claude_args
        self.engine = None
        self.model = ""
        self.busy = False
        self.tool_active = False
        self.turn_text = ""  # the words of this reply (for copy, history, pop-ups)
        self.parts = []  # the same reply as shown: text pieces and the steps between them
        self.streamed_ids = set()
        self.dirty = False
        self.flushing = False
        self.scale = 2
        self.override = None
        self.show_top = False
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
        self.dialog = None  # Quill's own questions (sudo)
        self.sudo_mode = sudo.load_mode()
        self.sudo_pw = None  # memory only, never saved
        self.sudo_last_pid = None
        self.sudo_server = None
        self.engine_ready = asyncio.Event()
        self.granted = 0  # "don't ask again" level, this chat only
        self.ask_queue = []  # permission requests waiting behind the one on screen
        self.in_front = True  # is Quill's terminal window in front? (for pop-ups)
        self.turn_t0 = time.monotonic()
        self.rc_on, self.rc_url, self.rc_state = False, "", ""
        self.notify_on = sudo.load_config().get("notifications", True)
        self.activity, self.activity_t0 = "", time.monotonic()
        self.last_event = time.monotonic()
        cfg = sudo.load_config()
        self.who = cfg.get("character") if cfg.get("character") in CHARACTERS else None
        self.first_run = self.who is None
        self.user_name = (cfg.get("user_name") or "").strip()
        typed = os.environ.get("QUILL_AS")  # the launcher says `quill` or `plume` was typed
        self.typed_as = typed if typed in CHARACTERS else None
        self.who = (self.typed_as if not self.first_run else None) or self.who or "quill"
        for name in themes.NAMES:
            self.register_theme(themes.textual_theme(name))
        self.apply_look(startup=True)

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        yield Static("", id="title")
        with Horizontal(id="stage"):
            yield Static("", id="quill")
            yield Static("◀", id="tail")
            with VerticalScroll(id="bubble"):
                yield Markdown(GREETING.replace("Quill", self.char_name), id="say")
                yield Vertical(id="turn")
        yield Static("", id="status")
        yield Horizontal(id="choices")
        yield Static("", id="you")
        yield ChatBox(id="input", placeholder=f"Talk to {self.char_name}…", soft_wrap=True,
                      show_line_numbers=False, highlight_cursor_line=False, theme="css")
        yield Static("Enter send · \\+Enter new line · Esc stop · F2 history · F3 copy · Ctrl+Q quit",
                     id="hints")

    def on_mount(self):
        self.set_title()
        self.set_interval(0.15, self.animate)
        self.set_interval(0.1, self.flush)
        self.set_interval(1, self.tick_status)
        self.query_one("#input").focus()
        self.start_engine()
        if self.first_run:
            self.push_screen(Chooser(self.typed_as), self.chose)  # who would you like? (once)
        elif strip_resume(self.claude_args) == list(self.claude_args):
            self.offer_picker(first=True)

    def on_resize(self, event):
        # Big Quill needs ~32 rows and 90 columns; otherwise draw him at half size.
        scale = 2 if (event.size.height >= 32 and event.size.width >= 90) else 1
        if scale != self.scale:
            self.scale = scale
            self.query_one("#stage").set_class(scale == 1, "small")
            self.last_frame = None

    def set_title(self):
        folder = os.path.basename(os.getcwd()) or "/"
        bits = [self.char_name.upper(), folder] + ([self.model] if self.model else [])
        if self.sudo_mode != "off":
            bits.append(sudo.LABELS[self.sudo_mode])
        if self.rc_on:
            bits.append("REMOTE: " + ("on" if self.rc_state == "connected" else (self.rc_state or "starting")))
        title = self.query_one("#title", Static)
        title.update("  ·  ".join(bits))
        title.set_class(self.sudo_mode != "off", "sudo")

    def status(self, text):
        """What Quill is doing. While busy, a timer adds how long it's been going."""
        if text != self.activity:
            self.activity, self.activity_t0 = text, time.monotonic()
        self.query_one("#status", Static).update(text)

    def tick_status(self):
        if not self.busy or self.pending or self.dialog:
            return
        now = time.monotonic()
        spent, quiet = now - self.activity_t0, now - self.last_event

        def clock(sec):
            return f"{int(sec // 60)}:{int(sec % 60):02d}"
        text = self.activity
        if not self.tool_active and quiet > 120:
            text = (f"No reply from Claude's servers for {clock(quiet)}. It may be stuck: "
                    "Esc stops it, then ask again.")
        elif spent >= 5:
            text += f" · {clock(spent)}" + (" · Esc to stop" if spent > 120 else "")
        self.query_one("#status", Static).update(text)

    def show(self, md, top=False):
        """Put something other than the live reply in the bubble."""
        self.override = md
        self.show_top = top
        self.dirty = True

    def show_reply(self):
        self.override = None
        self.dirty = True

    def feel(self, mood, secs=1.5):
        self.mood, self.mood_until = mood, time.monotonic() + secs

    # ---------- animation ----------
    def animate(self):
        self.tick += 1
        self.spin()
        now = time.monotonic()
        if self.pending or self.dialog:
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
            self.query_one("#quill", Static).update(
                render_sprite(sprite(self.who, face, bulb), self.scale, self.pal, self.bgc))

    # ---------- the reply, step by step ----------
    def new_turn(self):
        self.turn_text, self.parts = "", []

    def add_text(self, text, new_block=False):
        """Claude's words. A new text block after a step starts a new piece."""
        if not self.parts or self.parts[-1]["kind"] != "text":
            self.parts.append({"kind": "text", "text": ""})
        elif new_block and self.parts[-1]["text"] and not self.parts[-1]["text"].endswith("\n\n"):
            self.parts[-1]["text"] += "\n\n"
        self.parts[-1]["text"] += text
        if new_block and self.turn_text and not self.turn_text.endswith("\n\n"):
            self.turn_text += "\n\n"
        self.turn_text += text

    def step(self, tool_id):
        return next((p for p in self.parts if p["kind"] == "step" and p["id"] == tool_id), None)

    def add_step(self, block):
        if self.step(block.get("id")):
            return
        self.parts.append({"kind": "step", "id": block.get("id"), "name": block.get("name"),
                           "input": block.get("input") or {}, "state": "run", "note": "", "helper": ""})
        self.reveal()

    def end_step(self, ev, block):
        p = self.step(block.get("tool_use_id"))
        if not p:
            return
        err = bool(block.get("is_error"))
        p["note"] = describe_result(p["name"], p["input"], ev.get("tool_use_result"),
                                    block.get("content"), err)
        p["state"], p["helper"] = ("err" if err else "ok"), ""
        self.reveal()

    def reveal(self):
        """Show the reply so far, unless a question for you is on screen."""
        if self.pending or self.dialog:
            self.dirty = True  # it'll show once you've answered
        else:
            self.show_reply()

    def step_line(self, p):
        label = describe_tool(p["name"], p["input"])
        if p["state"] == "run":
            line = f"{SPINNER[self.tick % len(SPINNER)]} {label}…"
            if p["helper"]:
                line += f"  ·  {p['helper']}"
        else:
            mark = {"ok": "✓", "err": "✗", "stopped": "■"}[p["state"]]
            line = f"{mark} {past_tense(label)}" + (f"  ·  {p['note']}" if p["note"] else "")
        return Text(line, overflow="ellipsis", no_wrap=True)

    async def sync_turn(self):
        """Make the widgets in #turn match self.parts (one per text piece or step)."""
        turn = self.query_one("#turn")
        have = list(turn.children)
        kinds = [("text" if isinstance(w, Markdown) else "step") for w in have]
        if len(have) > len(self.parts) or kinds != [p["kind"] for p in self.parts[:len(have)]]:
            await turn.remove_children()
            have = []
        for i, p in enumerate(self.parts):
            if i >= len(have):
                w = (Markdown("", classes="after" if i else "") if p["kind"] == "text"
                     else Static("", classes="step"))
                w.shown = None
                await turn.mount(w)
                have.append(w)
            w = have[i]
            if p["kind"] == "text":
                if w.shown != p["text"]:
                    w.shown = p["text"]
                    await w.update(p["text"])
            else:
                w.part = p
                w.set_class(p["state"] == "run", "run")
                w.set_class(p["state"] == "err", "err")
                w.update(self.step_line(p))

    def spin(self):
        """Turn the spinner on running steps without redrawing the whole reply."""
        if self.override is not None or not self.busy:
            return
        try:
            for w in self.query_one("#turn").children:
                if getattr(w, "part", None) and w.part["state"] == "run":
                    w.update(self.step_line(w.part))
        except NoMatches:
            pass

    async def flush(self):
        if self.dirty and not self.flushing:
            self.dirty, self.flushing = False, True
            try:
                say, turn = self.query_one("#say", Markdown), self.query_one("#turn")
                steps = self.override is None and bool(self.parts)
                say.display, turn.display = not steps, steps
                if steps:
                    await self.sync_turn()
                else:
                    await say.update(self.override if self.override is not None
                                     else (self.turn_text or "…"))
                bubble = self.query_one("#bubble")
                if self.override is not None and self.show_top:
                    bubble.scroll_home(animate=False)
                else:
                    bubble.scroll_end(animate=False)
            except NoMatches:
                pass  # Quill is closing
            finally:
                self.flushing = False

    # ---------- talking to Claude ----------
    @work(exclusive=True, group="engine")
    async def start_engine(self, fresh=False):
        self.engine_ready.clear()
        if self.engine:
            await self.engine.stop()
        args = strip_resume(self.claude_args) if fresh else list(self.claude_args)
        self.granted = 0  # every new or resumed chat starts asking again
        self.ask_queue, self.pending = [], None
        if not any(a == "--permission-mode" or a.startswith("--permission-mode=") for a in args):
            # same as a normal Claude Code session: routine actions don't ask
            args += ["--permission-mode", sudo.load_config().get("permission_mode", "auto")]
        try:
            if not self.sudo_server:
                self.sudo_server = sudo.SudoServer(self.sudo_request)
                await self.sudo_server.start()
            note = sudo.SYSTEM_NOTE + "\n\n" + TEST_REPO_NOTE
            if self.user_name:
                note += f"\n\nThe user's name is {self.user_name}."
            self.engine = Engine(args + ["--append-system-prompt", note],
                                 env=sudo.child_env(self.sudo_server.path))
            await self.engine.start()
        except Exception as e:  # noqa: BLE001
            self.show(f"**I couldn't start Claude Code.**\n\n`{e}`")
            self.feel("sad", 5)
            return
        self.engine_ready.set()
        if self.rc_on:
            self.run_worker(self.remote_control(True, quiet=True), group="rc")
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
        self.last_event = time.monotonic()

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
                    self.add_text("", new_block=True)
                elif block.get("type") == "thinking":
                    self.status("Thinking…")
            elif e.get("type") == "content_block_delta":
                d = e.get("delta", {})
                if d.get("type") == "text_delta":
                    self.add_text(d.get("text", ""))
                    self.last_delta = time.monotonic()
                    if not self.pending:
                        self.show_reply()

        elif t == "assistant":
            msg = ev.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    if sub_agent:
                        doing = describe_tool(block.get("name"), block.get("input"))
                        parent = self.step(ev.get("parent_tool_use_id"))
                        if parent:
                            parent["helper"] = doing
                        self.status("A helper is working… " + doing)
                    else:
                        self.add_step(block)
                        if not self.pending:
                            self.tool_active = True
                            self.status(describe_tool(block.get("name"), block.get("input")))
                elif (block.get("type") == "text" and not sub_agent
                      and msg.get("id") not in self.streamed_ids):
                    self.add_text(block.get("text", ""), new_block=True)
                    if not self.pending:
                        self.show_reply()

        elif t == "control_response":
            self.engine.resolve(ev)

        elif t == "system" and ev.get("subtype") == "bridge_state":
            self.rc_state = ev.get("state", "")
            self.set_title()

        elif t == "user" and not sub_agent and isinstance((ev.get("message") or {}).get("content"), str):
            # a message typed somewhere else (Remote Control: phone or claude.ai)
            text = ev["message"]["content"]
            self.log_items.append(("you", text))
            self.query_one("#you", Static).update(Text("you (remote): " + text, overflow="ellipsis"))
            if not self.busy:
                self.new_turn()
                self.turn_t0 = time.monotonic()
            self.busy = True
            self.status("Thinking…")

        elif t == "user" and not sub_agent:
            content = (ev.get("message") or {}).get("content")
            if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                self.tool_active = False  # that step finished; Claude is thinking again
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        self.end_step(ev, b)
                if not self.pending:
                    self.status("Thinking…")

        elif t == "control_request":
            req = ev.get("request", {})
            if req.get("subtype") == "can_use_tool":
                await self.ask(ev["request_id"], req)

        elif t == "result":
            self.busy = False
            self.tool_active = False
            for p in self.parts:
                if p["kind"] == "step" and p["state"] == "run":
                    p["state"] = "stopped"  # never got an answer (stopped with Esc)
            if ev.get("is_error") or ev.get("subtype", "success") != "success":
                err = ev.get("result") or ev.get("subtype", "error")
                if not self.turn_text:
                    self.add_text(f"Something went wrong:\n\n`{err}`", new_block=True)
                self.feel("sad", 4)
                self.status("Stopped")
            else:
                self.feel("happy", 1.5)
                self.status("Done")
                if time.monotonic() - self.turn_t0 > 30:
                    first = next((l for l in self.turn_text.splitlines() if l.strip()), "")
                    self.pop_up(f"{self.char_name} is done", first)
            if self.turn_text:
                self.log_items.append(("quill", self.turn_text))
            self.show_reply()

    # ---------- questions & permissions ----------
    async def ask(self, request_id, req):
        tool, inp = req.get("tool_name", ""), req.get("input") or {}
        if perms.allowed(tool, inp, os.getcwd(), self.granted):
            # you already said "don't ask again" for this level in this chat
            self.tool_active = True
            self.status(describe_tool(tool, inp) + "  (allowed for this chat)")
            await self.engine.answer(request_id, {"behavior": "allow", "updatedInput": inp})
            return
        if self.pending or (self.dialog and self.dialog["kind"] == "sudo"):
            # Claude can ask about several things at once (e.g. two reads in parallel):
            # show them one at a time, never drop one
            self.ask_queue.append((request_id, req))
            self.status(f"Waiting for you ({len(self.ask_queue)} more after this)")
            return
        self.pending = {"id": request_id, **req}
        if tool == "AskUserQuestion":
            self.q_index, self.q_answers = 0, {}
        self.present()

    def present(self):
        """Show the request we're waiting on you for (again, e.g. after a sudo prompt)."""
        req = self.pending
        tool, inp = req.get("tool_name", ""), req.get("input") or {}
        self.pop_up(f"{self.char_name} needs you", "Has a question for you" if tool == "AskUserQuestion"
                    else describe_tool(tool, inp) + ": OK?")
        if tool == "AskUserQuestion":
            self.show_question()
            return
        lvl = perms.level(tool, inp, os.getcwd())
        text = permission_text(tool, inp, req.get("display_name"))
        buttons = [Button("Yes", name="perm-yes", variant="success")]
        if tool not in perms.NEVER_AUTO:
            text += (f"\n\n*\"Don't ask again\" covers {perms.NAMES[lvl]}"
                     + (" and anything smaller" if lvl > perms.READ else "")
                     + ", until this chat ends.*")
            buttons.append(Button("Yes, and don't ask again", name="perm-always", variant="primary"))
        buttons.append(Button("No", name="perm-no", variant="error"))
        if self.ask_queue:
            text += f"\n\n*({len(self.ask_queue)} more question{'s' if len(self.ask_queue) > 1 else ''} after this one)*"
        self.show(text)
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
        buttons = [Button(o.get("label", "?"), name=f"opt-{i}") for i, o in enumerate(opts)]
        if q.get("multiSelect"):
            buttons.append(Button("Done", name="opt-done", variant="success"))
        self.set_choices(buttons)
        self.status(f"Question {self.q_index + 1} of {len(qs)}")

    def set_choices(self, buttons, focus=True):
        box = self.query_one("#choices")
        box.remove_children()
        box.mount_all(buttons)
        box.add_class("show")
        if buttons and focus:
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
        tool = req.get("tool_name", "")
        if response.get("behavior") == "allow" and tool not in perms.NEVER_AUTO:
            self.tool_active = True
            self.status(describe_tool(tool, req.get("input")))  # what's running now
        else:
            self.tool_active = False
            self.status("Thinking…")
        await self.engine.answer(req["id"], response)
        if self.ask_queue:
            rid, nxt = self.ask_queue.pop(0)
            await self.ask(rid, nxt)  # may be covered by "don't ask again" now

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
        bid = event.button.name or ""
        if bid in ("nm-yes", "nm-skip"):
            d = self.dialog or {}
            self.name_done(d.get("guess") if bid == "nm-yes" else None)
            return
        if bid.startswith("pk-"):
            self.pick(bid)
            return
        if bid.startswith("pj-"):
            self.project_choice(bid)
            return
        if bid.startswith("sm-"):
            self.sudo_setup(bid)
            return
        if bid in ("sudo-run", "sudo-no"):
            self.sudo_answer(bid == "sudo-run")
            return
        if not self.pending:
            return
        req = self.pending
        if bid == "perm-yes":
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {})})
        elif bid == "perm-always":
            # remembered by Quill for this chat only; nothing is written to Claude Code's settings
            self.granted = max(self.granted, perms.level(req.get("tool_name", ""), req.get("input"),
                                                         os.getcwd()))
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {})})
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
    @on(ChatBox.Submitted)
    async def submitted(self, event):
        text = event.text.strip()
        event.box.clear()
        if not text:
            return
        if self.dialog and self.dialog["kind"] == "name":
            self.name_done(text)  # whatever you type is what I'll call you
            return
        if self.dialog and self.dialog["kind"] == "picker":
            self.close_picker()  # typing instead of picking = something new, here
        elif self.dialog and self.dialog["kind"] == "project":
            self.enter_project(self.dialog["project"], resume=False, prefill=False)  # typing = fresh chat there
        elif self.dialog:
            event.box.load_text(text)
            self.notify("Answer Quill's question above first (or press Esc).", timeout=2)
            return
        if text.lower() == "/resume":
            if self.busy or self.pending:
                self.notify("Wait until I've finished, then /resume.", timeout=2)
            else:
                self.offer_picker()
            return
        cmd = text.lower()
        if cmd.startswith("/sudo"):
            self.sudo_command(cmd)
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
        if cmd == "/terminal":
            await self.leave(code=3)  # back to a normal terminal
            return
        if cmd in ("/remote-control", "/rc", "/remote-control on", "/rc on"):
            self.run_worker(self.remote_control(True), group="rc")
            return
        if cmd in ("/remote-control off", "/rc off"):
            self.run_worker(self.remote_control(False), group="rc")
            return
        if cmd == "/name":
            self.ask_name()
            return
        if cmd.startswith("/name "):
            self.dialog = {"kind": "name"}
            self.name_done(text[6:])
            return
        if cmd == "/character" or cmd.startswith("/character "):
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            who = arg if arg in CHARACTERS else ("plume" if self.who == "quill" else "quill")
            self.switch_to(who)
            return
        if cmd == "/theme" or cmd.startswith("/theme "):
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            if arg and arg not in themes.NAMES:
                self.show("Colour schemes: " + ", ".join(f"`{n}`" for n in themes.NAMES))
                return
            name = arg or themes.NAMES[(themes.NAMES.index(self.theme_name) + 1) % len(themes.NAMES)]
            cfg = sudo.load_config()
            sudo.set_config("themes", {**cfg.get("themes", {}), self.who: name})
            self.apply_look()
            self.show(f"{self.char_name} is wearing **{name}** now. "
                      + "Other schemes: " + ", ".join(f"`/theme {n}`" for n in themes.NAMES if n != name))
            return
        if cmd in ("/notify on", "/notify off", "/notify"):
            self.notify_on = cmd != "/notify off"
            sudo.set_config("notifications", self.notify_on)
            self.show("Desktop pop-ups are **" + ("on" if self.notify_on else "off") + "**: "
                      "I'll pop one up when I need you or finish a long job while you're in "
                      "another window.")
            return
        if cmd == "/help":
            self.show(HELP.replace("Quill", self.char_name))
            return
        if cmd == "/copy":
            self.action_copy_reply()
            return
        if cmd == "/history":
            self.action_history()
            return
        if cmd in ("/new", "/clear"):
            self.log_items, self.busy = [], False
            self.new_turn()
            self.claude_args = strip_resume(self.claude_args)
            self.show("Fresh start! What's next?")
            self.query_one("#you", Static).update("")
            self.start_engine(fresh=True)
            return
        try:  # a project may still be starting up
            await asyncio.wait_for(self.engine_ready.wait(), 30)
        except asyncio.TimeoutError:
            pass
        if not self.engine or not self.engine.proc or self.engine.proc.returncode is not None:
            self.show("I'm not connected to Claude Code. Type `/new` to start again.")
            return
        self.log_items.append(("you", text))
        self.query_one("#you", Static).update(Text("you: " + text, overflow="ellipsis"))
        if not self.busy:
            self.new_turn()
            self.turn_t0 = time.monotonic()
            self.show("…")
        else:
            self.notify("Got it. I'll read that as soon as I finish this step.", timeout=3)
        self.busy = True
        self.status("Thinking…")
        await self.engine.say(text)

    async def action_stop(self):
        if self.dialog:
            if self.dialog["kind"] == "name":
                self.name_done(None)
            elif self.dialog["kind"] in ("picker", "project"):
                self.close_picker()
                self.show("Something new it is. What are we working on?")
            elif self.dialog["kind"] == "sudo":
                self.sudo_answer(False)
            else:
                self.sudo_setup("sm-cancel")
            return
        if self.busy and self.engine:
            queued, self.ask_queue = self.ask_queue, []
            for rid, _ in queued:
                await self.engine.answer(rid, {"behavior": "deny", "message": "The user stopped you."})
            if self.pending:
                await self.finish_pending({"behavior": "deny", "message": "The user stopped you."})
            await self.engine.interrupt()
            self.status("Stopping…")

    def copy_to_clipboard(self, text):
        """Copy via the terminal (OSC 52) *and* the desktop clipboard tool,
        because many terminals (e.g. xfce4-terminal) ignore OSC 52."""
        super().copy_to_clipboard(text)
        tools = []
        if os.environ.get("WAYLAND_DISPLAY"):
            tools.append(["wl-copy"])
        if os.environ.get("DISPLAY"):
            tools += [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
        for cmd in tools:
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=text.encode(), timeout=3,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
                except (OSError, subprocess.SubprocessError):
                    continue
        self.notify("Copied!", timeout=1.5)

    def action_copy_reply(self):
        replies = [t for who, t in self.log_items if who == "quill"]
        text = self.turn_text if self.busy else (replies[-1] if replies else "")
        if text:
            self.copy_to_clipboard(text)
        else:
            self.notify("Nothing to copy yet.", timeout=1.5)

    def action_history(self):
        self.push_screen(History(self.log_items, self.char_name.lower()))

    async def action_quit(self):
        await self.leave(code=77)  # 77 = the launcher closes the terminal window too

    async def leave(self, code):
        if self.engine:
            await self.engine.stop()
        self.exit(return_code=code)

    # ---------- character & colours ----------
    @property
    def char_name(self):
        return self.who.capitalize()

    def apply_look(self, startup=False):
        default = "aurora" if self.who == "plume" else "classic"
        name = sudo.load_config().get("themes", {}).get(self.who, default)
        self.theme_name = name if name in themes.NAMES else default
        self.pal = themes.palette(self.theme_name)
        self.bgc = themes.THEMES[self.theme_name]["bg"]
        self.theme = f"quill-{self.theme_name}"
        self.last_frame = None
        if not startup:
            self.set_title()
            self.query_one("#input", ChatBox).placeholder = f"Talk to {self.char_name}…"

    def switch_to(self, who, greet=True):
        self.who = who
        sudo.set_config("character", who)
        self.apply_look()
        if greet:
            self.feel("happy", 1.5)
            self.show(f"Hi! I'm **{self.char_name}** now. "
                      f"`/character` switches back, `/theme` changes my colours.")

    def chose(self, who):
        self.switch_to(who or "quill", greet=False)
        self.ask_name(first=True)

    # ---------- your name ----------
    def ask_name(self, first=False):
        """Ask what to call you, suggesting the name Claude already knows (if any)."""
        self.dialog = {"kind": "name", "guess": None, "first": first}
        self.show(f"Nice to meet you! I'm **{self.char_name}**.\n\n"
                  "What should I call you? Type your name below and press **Enter**.")
        self.set_choices([Button("Skip", name="nm-skip")], focus=False)
        self.query_one("#input", ChatBox).focus()
        self.run_worker(self.guess_name(), group="name")

    async def guess_name(self):
        """One quick, unsaved question to Claude: does it already know the user's name?"""
        try:
            proc = await asyncio.create_subprocess_exec(
                find_claude(), "-p",
                "If your instructions or memory tell you the user's first name, reply with just "
                "that name. Otherwise reply with exactly: UNKNOWN",
                "--no-session-persistence", "--model", "haiku", "--tools", "",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL, env=clean_env())
            out, _ = await asyncio.wait_for(proc.communicate(), 60)
        except Exception:  # noqa: BLE001 - no guess is fine
            return
        lines = [l.strip() for l in out.decode(errors="replace").splitlines() if l.strip()]
        guess = lines[-1].strip(" .!\"'*") if lines else ""
        d = self.dialog
        if (not guess or guess.upper() == "UNKNOWN" or len(guess) > 30 or " " in guess.strip()
                or not d or d["kind"] != "name"):
            return
        d["guess"] = guess
        self.show(f"Nice to meet you! I'm **{self.char_name}**.\n\n"
                  f"My notes say you're **{guess}**. Is that right? "
                  "Or type what you'd like me to call you.")
        self.set_choices([Button(f"Yes, I'm {guess}", name="nm-yes", variant="success"),
                          Button("Skip", name="nm-skip")], focus=False)

    def name_done(self, name):
        d, self.dialog = self.dialog, None
        self.clear_choices()
        name = " ".join((name or "").split())[:40]
        if name:
            self.user_name = name
            sudo.set_config("user_name", name)
        if d and d.get("first") and strip_resume(self.claude_args) == list(self.claude_args):
            self.offer_picker(first=True)
        else:
            self.show(f"Hi {name}! Nice to meet you." if name else "No problem.")

    # ---------- desktop pop-ups & Remote Control ----------
    def on_app_focus(self, event):
        self.in_front = True

    def on_app_blur(self, event):
        self.in_front = False

    def pop_up(self, title, body=""):
        if self.notify_on and not self.in_front:
            notify.send(title, body)

    async def remote_control(self, on, quiet=False):
        try:
            await asyncio.wait_for(self.engine_ready.wait(), 30)
        except asyncio.TimeoutError:
            pass
        if not self.engine or not self.engine.proc:
            self.show("I'm not connected to Claude Code yet. Try again in a moment.")
            return
        if not on:
            self.rc_on, self.rc_url, self.rc_state = False, "", ""
            try:
                await self.engine.request({"subtype": "remote_control", "enabled": False})
            except Exception:  # noqa: BLE001
                pass
            self.set_title()
            self.show("Remote Control is **off**. This chat is only here again.")
            return
        self.status("Turning on Remote Control…")
        name = f"Quill · {os.path.basename(os.getcwd())}"
        try:
            info = await self.engine.request({"subtype": "remote_control", "enabled": True, "name": name})
        except Exception as e:  # noqa: BLE001
            self.show(f"**Remote Control didn't start.**\n\n`{e}`")
            self.status("")
            return
        self.rc_on, self.rc_url = True, info.get("session_url", "")
        self.set_title()
        self.status("Remote Control on")
        if quiet:
            return
        self.show("**Remote Control is on.** 📱\n\n"
                  "Open the **Claude** app on your phone (Code tab), or this link, and carry on "
                  f"this same chat there:\n\n{self.rc_url}\n\n"
                  "Messages from there show up here too. Type `/rc off` to stop.")
        if self.rc_url:
            self.copy_to_clipboard(self.rc_url)

    def on_unmount(self):
        if self.sudo_server:
            self.sudo_server.close()

    # ---------- picking up a project ----------
    def offer_picker(self, first=False):
        here = os.getcwd()
        try:
            projs = sessions.projects(limit=5, here=here)
        except Exception as e:  # noqa: BLE001 - the picker must never stop Quill starting
            projs = []
            self.notify(f"Couldn't list earlier projects: {e}", timeout=4)
        if not projs:
            if not first:
                self.show("I haven't found any earlier chats yet.")
            return
        self.dialog = {"kind": "picker", "projects": projs}
        hi = f"Hi {self.user_name}!" if self.user_name else "Hi!"
        hello = f"{hi} I'm **{self.char_name}**. " if first else ""
        lines = [f"{hello}Want to start something **new**, or pick up where we left off?", ""]
        for i, p in enumerate(projs, 1):
            tag = " *(this folder)*" if p["folder"] == here else ""
            label = {"roadmap": "next", "chat": "left off", "notes": "notes"}.get(p["next_from"], "next")
            if p["next"]:
                sub = f"{label}: {p['next']}"
            else:
                sub = "last: " + sessions.one_line(p["last_you"] or "(nothing yet)", 70)
            lines.append(f"{i}. **{p['name']}**{tag} · *{sessions.ago(p['when'])}*  \n   {sub}")
        lines += ["", "*Or just start typing for something new here.*"]
        self.show("\n".join(lines), top=True)
        buttons = [Button("Something new", name="pk-new", variant="success")]
        buttons += [Button(str(i), name=f"pk-{i - 1}", variant="primary")
                    for i in range(1, len(projs) + 1)]
        self.set_choices(buttons, focus=False)  # keep typing in the message box
        self.status("Something new, or pick a project")

    def close_picker(self):
        self.dialog = None
        self.clear_choices()
        self.status("Ready")

    def pick(self, bid):
        d = self.dialog
        if not d or d["kind"] != "picker":
            return
        if bid == "pk-new":
            self.close_picker()
            self.show("Something new it is. What are we working on?")
            return
        p = d["projects"][int(bid[3:])]
        self.dialog = {"kind": "project", "project": p, "projects": d["projects"]}
        where = (f" (started in *{os.path.basename(p['chat_cwd'])}*)"
                 if p["chat_cwd"] != p["folder"] else "")
        lines = [f"**{p['name']}** · last chat {sessions.ago(p['when'])}{where}", ""]
        if p["next"]:
            label = {"roadmap": "Next on the roadmap", "chat": "Where we left off",
                     "notes": "From my notes"}.get(p["next_from"], "Next")
            lines += [f"**{label}:** {p['next']}", ""]
        if p["last_you"]:
            lines += [f"*Last time you said:* {sessions.one_line(p['last_you'], 160)}"]
        self.show("\n".join(lines))
        self.set_choices([Button("Continue last chat", name="pj-continue", variant="primary"),
                          Button("Fresh chat", name="pj-fresh", variant="success"),
                          Button("Back", name="pj-back")], focus=False)
        self.status(p["folder"])

    def project_choice(self, bid):
        d = self.dialog
        if not d or d["kind"] != "project":
            return
        if bid == "pj-back":
            self.dialog = None
            self.offer_picker()
            return
        self.enter_project(d["project"], resume=(bid == "pj-continue"))

    def enter_project(self, p, resume, prefill=True):
        self.close_picker()
        try:
            # a chat must be resumed from the folder it ran in; fresh chats start in the project
            os.chdir(p["chat_cwd"] if resume else p["folder"])
        except OSError as e:
            self.show(f"I couldn't open that folder: `{e}`")
            return
        self.claude_args = strip_resume(self.claude_args) + (["--resume", p["session"]] if resume else [])
        self.log_items = sessions.transcript_file(p["path"]) if resume else []
        self.new_turn()
        self.busy = False
        self.set_title()
        self.start_engine()
        box = self.query_one("#input", ChatBox)
        if resume:
            last = next((t for who, t in reversed(self.log_items) if who == "quill"), "")
            if len(last) > 700:
                last = last[:700].rsplit(" ", 1)[0] + " …"
            quoted = "\n".join("> " + l for l in last.splitlines()) if last else "> (nothing yet)"
            self.show(f"Picking up **{p['name']}** where we left off.\n\n"
                      f"Last time I said:\n\n{quoted}\n\n*F2 shows the whole chat.*")
            self.query_one("#you", Static).update(
                Text("you (last time): " + sessions.one_line(p["last_you"] or "", 200)))
        else:
            self.query_one("#you", Static).update("")
            if p["next"] and prefill and p["next_from"] == "roadmap":
                self.show(f"Fresh chat in **{p['name']}**. Next on the roadmap:\n\n> {p['next']}\n\n"
                          "I've put it in your message box. Press **Enter** to start on it, "
                          "or change it to anything else.")
                box.load_text(f"Let's work on the next roadmap item: {p['next']}")
            elif p["next"] and prefill:
                where = "Where we left off" if p["next_from"] == "chat" else "My notes say"
                self.show(f"Fresh chat in **{p['name']}**. {where}:\n\n> {p['next']}\n\n"
                          "I've put a starter in your message box. Press **Enter**, or change it.")
                box.load_text(f"Let's pick up {p['name']} where we left off. What's next?")
                box.move_cursor(box.document.end)
            else:
                self.show(f"Fresh chat in **{p['name']}**. What are we working on?")
        box.focus()

    # ---------- sudo ----------
    def sudo_command(self, cmd):
        if self.pending:
            self.notify("Answer the current question first.", timeout=2)
            return
        if cmd.strip() == "/sudo off":
            self.sudo_set("off")
            self.show("Sudo is **off**. Root commands will fail until you turn it back on.")
            return
        self.dialog = {"kind": "setup"}
        now = sudo.LABELS[self.sudo_mode] or "off"
        self.show("**Let Quill use sudo?**\n\n"
                  "Commands run as root can change or break your whole system. "
                  "Your password stays in memory only, never on disk, and is forgotten "
                  f"when Quill closes.\n\n*Right now: {now}*")
        buttons = [Button("Just this chat", name="sm-chat", variant="primary"),
                   Button("Permanently", name="sm-perm", variant="warning")]
        if self.sudo_mode != "off":
            buttons.append(Button("Turn it off", name="sm-off"))
        buttons.append(Button("Cancel", name="sm-cancel", variant="error"))
        self.set_choices(buttons)
        self.status("Sudo setup")

    def sudo_setup(self, bid):
        d = self.dialog
        if not d or d["kind"] != "setup":
            return
        if bid == "sm-cancel":
            self.dialog = None
            self.clear_choices()
            self.show("OK, nothing changed. Sudo is "
                      f"**{sudo.LABELS[self.sudo_mode] or 'off'}**.")
            self.status("")
        elif bid == "sm-off":
            self.dialog = None
            self.clear_choices()
            self.sudo_set("off")
            self.show("Sudo is **off**.")
        elif bid == "sm-perm":
            self.show("**Permanently: how should it work?**\n\n"
                      "- **Ask me each time**: I show you every root command and wait for "
                      "your OK. You type your password once per Quill window.\n"
                      "- **Allow whenever**: root commands run *without asking*, once "
                      "you've typed your password in that Quill window.")
            self.set_choices([Button("Ask me each time", name="sm-ask", variant="primary"),
                              Button("Allow whenever", name="sm-always", variant="warning"),
                              Button("Cancel", name="sm-cancel", variant="error")])
        elif bid in ("sm-chat", "sm-ask", "sm-always"):
            d["choice"] = bid[3:]
            if d["choice"] == "always":
                warn = ("With this on, Claude can run **any** command as root **without "
                        "showing you first**, in every chat, until you type `/sudo off`.")
            elif d["choice"] == "ask":
                warn = ("Quill will be able to use sudo in every chat. You'll still see and "
                        "approve each root command.")
            else:
                warn = ("Quill will be able to use sudo until you close this window. You'll "
                        "still see and approve each root command.")
            self.show(f"**Are you sure?**\n\n{warn}")
            self.set_choices([Button("Yes, turn it on", name="sm-yes", variant="success"),
                              Button("Cancel", name="sm-cancel", variant="error")])
        elif bid == "sm-yes":
            self.dialog = None
            self.clear_choices()
            self.sudo_set(d["choice"])
            self.feel("happy", 1.5)
            self.show(f"Sudo is on: **{sudo.LABELS[self.sudo_mode]}**. "
                      "Type `/sudo off` any time to turn it off.")

    def sudo_set(self, mode):
        self.sudo_mode = mode
        if mode == "off":
            self.sudo_pw = None
        if mode != "chat":
            sudo.save_mode(mode)
        self.set_title()
        self.status("")

    async def sudo_request(self, cmd, sudo_pid):
        """askpass is asking for the password to run `cmd` as root."""
        once = self.sudo_mode == "off"  # sudo off: still ask, as a one-time OK
        retry = sudo_pid == self.sudo_last_pid
        self.sudo_last_pid = sudo_pid
        if retry:
            self.sudo_pw = None  # sudo asked again for the same command: wrong password
        if self.sudo_mode == "always" and self.sudo_pw:
            self.status(f"Ran as root: {cmd}"[:100])
            self.log_items.append(("quill", f"*(ran as root: `{cmd}`)*"))
            return self.sudo_pw
        fut = asyncio.get_running_loop().create_future()
        self.dialog = {"kind": "sudo", "cmd": cmd, "fut": fut}
        need_pw = once or not self.sudo_pw
        lines = [f"**{self.char_name} wants to run this as root (sudo):**", "", f"> `` {cmd} ``", ""]
        if retry:
            lines.append("*That password didn't work. Try again.*")
        elif need_pw:
            lines.append(f"Type your password, then **{'Run it once' if once else 'Run it'}**.")
        if once:
            lines += ["", "*Sudo is off in this window, so this is a one-time OK. "
                          "Type `/sudo` to turn it on for longer.*"]
        self.show("\n".join(lines))
        widgets = []
        if need_pw:
            self.dialog["input"] = Input(password=True, placeholder="sudo password", classes="sudo-pw")
            widgets.append(self.dialog["input"])
        widgets += [Button("Run it once" if once else "Run it", name="sudo-run", variant="success"),
                    Button("Don't", name="sudo-no", variant="error")]
        self.set_choices(widgets)
        self.status("Waiting for you: sudo")
        self.pop_up(f"{self.char_name} needs you", f"Wants to run as root: {cmd}")
        try:
            pw = await asyncio.wait_for(fut, 110)  # Claude's command times out at 120 s
        except asyncio.TimeoutError:
            pw = None
            self.sudo_finish(None)
            self.notify("Sudo question timed out.", timeout=3)
        if pw:
            if not once:
                self.sudo_pw = pw  # remembered only while sudo is on; never saved
            self.log_items.append(("you", f"Allowed as root: `{cmd}`"))
        else:
            self.log_items.append(("you", f"Didn't allow as root: `{cmd}`"))
        return pw

    def sudo_answer(self, run):
        d = self.dialog
        if not d or d["kind"] != "sudo":
            return
        if not run:
            self.sudo_finish(None)
            return
        # a password box on screen always wins over a remembered password
        pw = d["input"].value if d.get("input") else self.sudo_pw
        if not pw:
            self.notify("Type your password first.", timeout=2)
            return
        self.sudo_finish(pw)

    def sudo_finish(self, pw):
        d, self.dialog = self.dialog, None
        if d and not d["fut"].done():
            d["fut"].set_result(pw)
        self.clear_choices()
        self.show_reply()
        self.status("Running as root…" if pw else "Sudo cancelled")
        if self.pending:
            self.present()  # a permission question was waiting behind the sudo prompt

    @on(Input.Submitted, ".sudo-pw")
    def sudo_pw_entered(self, event):
        self.sudo_answer(True)


def key_check():
    """`quill --keys`: shows what your terminal sends for each key (Ctrl+Q to leave)."""
    class Keys(App):
        CSS = f"Screen {{ background: {BG}; color: #f4f4f4; padding: 1 2; }}"

        def compose(self):
            yield Static("Press keys (Shift+Enter, Alt+Enter, …). Ctrl+Q leaves.\n", id="k")

        def on_key(self, event):
            k = self.query_one("#k", Static)
            k.update(str(k.renderable) + f"\n{event.key!r}   character={event.character!r}")
    Keys().run()


def main():
    args = sys.argv[1:]
    if args and args[0] in ("--version", "-v"):
        print(f"Quill {__version__}")
        return
    if args and args[0] == "--keys":
        key_check()
        return
    if args and args[0] in ("--help", "-h"):
        print("quill [claude flags]   e.g. quill -c  (continue last chat),"
              " quill --resume <id>, quill --model sonnet")
        return
    app = QuillApp(args)
    app.run()
    sys.exit(app.return_code or 0)


if __name__ == "__main__":
    main()
