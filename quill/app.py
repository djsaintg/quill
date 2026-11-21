"""Quill: Claude Code as a little desk robot with a speech bubble.

The app is put together from a few parts, one file each:
  reply.py       the reply in the bubble, step by step     face.py      the robot's face
  asking.py      permission questions and multiple choice  commands.py  /help, /theme, /new, ...
  characters.py  Quill or Plume, colours, your name        projects.py  the project picker
  remote.py      desktop pop-ups and Remote Control         sudo_ui.py   sudo questions
This file starts Claude Code, reads what it says, and wires the parts together.
"""
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
from textual.widgets import Button, Input, Markdown, Static

from . import settings, sudo, themes
from .asking import AskMixin
from .characters import CharacterMixin, persona_note
from .commands import CommandsMixin
from .engine import Engine, describe_tool, resume_request, strip_resume
from .face import FaceMixin
from .projects import ProjectsMixin
from .remote import RemoteMixin
from .reply import ReplyMixin
from .sprites import CHARACTERS
from .style import CSS
from .sudo_ui import SudoMixin
from .texts import GREETING
from .widgets import BG, ChatBox, Chooser, History

__version__ = "0.4.0"

CLOSE_AFTER = 30  # seconds the wrap-up summary stays up before the window closes


def write_tty(seq):
    """Send an escape sequence straight to the terminal, past Textual."""
    try:
        fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
    except OSError:
        return False
    try:
        os.write(fd, seq.encode())
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


class QuillApp(FaceMixin, ReplyMixin, AskMixin, CommandsMixin, CharacterMixin, RemoteMixin,
               ProjectsMixin, SudoMixin, App):
    TITLE = "Quill"
    CSS = CSS
    BINDINGS = [
        Binding("escape", "stop", "Stop", show=False),
        Binding("f2", "history", "History", show=False),
        Binding("f3", "copy_reply", "Copy reply", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self, claude_args):
        super().__init__()
        # `quill -r` / `--resume` without a chat id: show the list of earlier chats
        self.claude_args, self.resume_search = resume_request(claude_args)
        self.session_id = None
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
        self.flash_face, self.flash_until = None, 0.0  # a quick reaction, even mid-work
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
        self.chatted = False  # said anything in this chat? (nothing to wrap up if not)
        self.stopping = False  # Esc pressed: the turn ending early isn't a failure
        self.wrapping = None  # {"code": exit code} while wrapping up before closing
        self.closing_at = None  # when the window closes after the wrap-up
        self.shown_title = None
        self.quit_armed = -100.0
        cfg = sudo.load_config()
        self.who = cfg.get("character") if cfg.get("character") in CHARACTERS else None
        self.first_run = self.who is None
        self.user_name = (cfg.get("user_name") or "").strip()
        typed = os.environ.get("QUILL_AS")  # the launcher says `quill` or `plume` was typed
        self.typed_as = typed if typed in CHARACTERS else None
        self.who = (self.typed_as if not self.first_run else None) or self.who or "quill"
        self.told_who = self.who
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
        write_tty("\x1b[22;0t")  # save the terminal's own title, to put back when Quill closes
        self.set_title()
        self.set_interval(0.15, self.animate)
        self.set_interval(0.1, self.flush)
        self.set_interval(1, self.tick_status)
        self.set_interval(3, self.keep_window_title)
        self.query_one("#input").focus()
        self.start_engine()
        if self.first_run:
            self.push_screen(Chooser(self.typed_as), self.chose)  # who would you like? (once)
        elif self.resume_search is not None:
            self.offer_chats(self.resume_search)
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
        self.window_title(self.char_name)

    def window_title(self, text):
        """Name the terminal window (title bar + task bar) after whoever's at the desk."""
        self.shown_title = text
        write_tty(f"\x1b]0;{text}\x07")  # OSC 0 = window title + icon name

    def keep_window_title(self):
        """Put the title back every few seconds, in case something else in the terminal
        (a program Claude ran, the terminal itself) changed it in the meantime."""
        if self.shown_title:
            write_tty(f"\x1b]0;{self.shown_title}\x07")

    def status(self, text):
        """What Quill is doing. While busy, a timer adds how long it's been going."""
        if text != self.activity:
            self.activity, self.activity_t0 = text, time.monotonic()
        self.query_one("#status", Static).update(text)

    def tick_status(self):
        now = time.monotonic()
        if self.closing_at is not None:
            left = int(self.closing_at - now + 0.99)
            if left <= 0:
                self.run_worker(self.leave(self.wrap_code), group="quit")
            else:
                self.query_one("#status", Static).update(
                    f"Closing in {left} s · Close now, or Stay open (or just type)")
            return
        if not self.busy or self.pending or self.dialog:
            return
        spent, quiet = now - self.activity_t0, now - self.last_event

        def clock(sec):
            return f"{int(sec // 60)}:{int(sec % 60):02d}"
        text = self.activity
        if not self.tool_active and quiet > 120:
            text = (f"No reply from Claude's servers for {clock(quiet)}. It may be stuck: "
                    "Esc stops it, then ask again.")
        elif spent >= 5:
            text += f" · {clock(spent)}" + (" · Esc to stop" if spent > 120 else "")
        if self.wrapping:
            text = "Wrapping up · " + text
        self.query_one("#status", Static).update(text)

    def show(self, md, top=False):
        """Put something other than the live reply in the bubble."""
        self.override = md
        self.show_top = top
        self.jump = True  # something new to read: show it
        self.dirty = True

    def show_reply(self):
        self.override = None
        self.dirty = True

    # ---------- talking to Claude ----------
    def system_note(self):
        note = "\n\n".join([persona_note(self.who), sudo.SYSTEM_NOTE, settings.system_note()])
        if self.user_name:
            note += f"\n\nThe user's name is {self.user_name}."
        return note

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
            self.told_who = self.who
            self.engine = Engine(args + ["--append-system-prompt", self.system_note()],
                                 env=sudo.child_env(self.sudo_server.path))
            await self.engine.start()
        except Exception as e:  # noqa: BLE001
            self.show(f"**I couldn't start Claude Code.**\n\n`{e}`")
            self.feel("oops", 5)
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
        self.wrapping = None
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
            self.session_id = ev.get("session_id") or self.session_id
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
            self.chatted = True
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
                        if b.get("is_error") and not self.stopping:
                            self.flash("oops")  # a step failed: X eyes, just for a moment
                if not self.pending:
                    self.status("Thinking…")

        elif t == "control_request":
            req = ev.get("request", {})
            if req.get("subtype") == "can_use_tool":
                await self.ask(ev["request_id"], req)

        elif t == "result":
            self.busy = False
            self.tool_active = False
            stopped, self.stopping = self.stopping, False
            for p in self.parts:
                if p["kind"] == "step" and p["state"] == "run":
                    p["state"] = "stopped"  # never got an answer (stopped with Esc)
            ok = not ev.get("is_error") and ev.get("subtype", "success") == "success"
            if stopped:
                self.status("Stopped")
            elif not ok:
                err = ev.get("result") or ev.get("subtype", "error")
                if not self.turn_text:
                    self.add_text(f"Something went wrong:\n\n`{err}`", new_block=True)
                self.feel("oops", 4)
                self.status("Stopped")
            else:
                self.feel("happy", 1.5)
                self.status("Done")
                if time.monotonic() - self.turn_t0 > 30 and not self.wrapping:
                    first = next((l for l in self.turn_text.splitlines() if l.strip()), "")
                    self.pop_up(f"{self.char_name} is done", first)
            if self.turn_text:
                self.log_items.append(("quill", self.turn_text))
            self.show_reply()
            if self.wrapping:
                self.wrapped(ok and not stopped)

    # ---------- buttons ----------
    @on(Button.Pressed)
    async def pressed(self, event):
        bid = event.button.name or ""
        if bid in ("nm-yes", "nm-skip"):
            d = self.dialog or {}
            self.name_done(d.get("guess") if bid == "nm-yes" else None)
        elif bid.startswith("ch-"):
            self.chat_choice(bid)
        elif bid.startswith("pk-"):
            self.pick(bid)
        elif bid.startswith("pj-"):
            self.project_choice(bid)
        elif bid.startswith("sm-"):
            self.sudo_setup(bid)
        elif bid in ("sudo-run", "sudo-no"):
            self.sudo_answer(bid == "sudo-run")
        elif bid == "wr-close":
            await self.leave(self.wrap_code)
        elif bid == "wr-stay":
            self.stay_open()
        elif self.pending:
            await self.pending_button(bid, event.button)

    @on(Input.Submitted, ".sudo-pw")
    def sudo_pw_entered(self, event):
        self.sudo_answer(True)

    # ---------- your input ----------
    @on(ChatBox.Submitted)
    async def submitted(self, event):
        text = event.text.strip()
        event.box.clear()
        if not text:
            return
        if self.closing_at is not None:
            self.stay_open()  # typing after the wrap-up = you're not done yet
        if self.dialog and self.dialog["kind"] == "name":
            self.name_done(text)  # whatever you type is what I'll call you
            return
        if self.dialog and self.dialog["kind"] in ("picker", "chats") and self.typed_in_list(text):
            return  # a number from the list
        if self.dialog and self.dialog["kind"] == "chats" and not text.startswith(("/", "-")):
            self.offer_chats(text)  # a word: search the chats for it
            return
        if self.dialog and self.dialog["kind"] in ("picker", "chats"):
            self.close_picker()  # typing instead of picking = something new, here
        elif self.dialog and self.dialog["kind"] == "project":
            self.enter_project(self.dialog["project"], resume=False, prefill=False)  # typing = fresh chat there
        elif self.dialog:
            event.box.load_text(text)
            self.notify(f"Answer {self.char_name}'s question above first (or press Esc).", timeout=2)
            return
        cmd = text.lower()
        word = cmd.split(" ", 1)[0]
        if word in ("/resume", "--resume", "-r", "--r", "/continue", "--continue", "-c", "--c",
                    "/projects"):
            # like Claude Code: -c continues the last chat here, --resume lists them all
            if self.busy or self.pending:
                self.notify(f"Wait until I've finished, then {word}.", timeout=2)
            elif word == "/projects":
                self.offer_picker()
            elif word in ("/continue", "--continue", "-c", "--c"):
                self.continue_here()
            else:
                self.offer_chats(text.partition(" ")[2].strip() or None)
            return
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
        if await self.run_command(text):
            return
        await self.send(text)

    async def send(self, text, shown=None):
        """Pass a message to Claude. `shown` is what appears as yours (None = the text itself)."""
        try:  # a project may still be starting up
            await asyncio.wait_for(self.engine_ready.wait(), 30)
        except asyncio.TimeoutError:
            pass
        if not self.engine or not self.engine.proc or self.engine.proc.returncode is not None:
            self.show("I'm not connected to Claude Code. Type `/new` to start again.")
            return False
        shown = text if shown is None else shown
        self.chatted = True
        self.log_items.append(("you", shown))
        self.query_one("#you", Static).update(Text("you: " + shown, overflow="ellipsis"))
        if not self.busy:
            self.new_turn()
            self.turn_t0 = time.monotonic()
            self.show("…")
        else:
            self.notify("Got it. I'll read that as soon as I finish this step.", timeout=3)
        self.busy = True
        self.status("Thinking…")
        if self.told_who != self.who:
            # switched with /character mid-chat: the system prompt still names the old one
            self.told_who = self.who
            text = f"[Quill note: the user switched characters. {persona_note(self.who)}]\n\n{text}"
        await self.engine.say(text)
        return True

    async def action_stop(self):
        if self.dialog:
            if self.dialog["kind"] == "name":
                self.name_done(None)
            elif self.dialog["kind"] in ("picker", "project", "chats"):
                self.close_picker()
                self.show("Something new it is. What are we working on?")
            elif self.dialog["kind"] == "sudo":
                self.sudo_answer(False)
            else:
                self.sudo_setup("sm-cancel")
            return
        if self.closing_at is not None:
            self.stay_open()
            return
        if self.busy and self.engine:
            if self.wrapping:
                self.wrapping = None
                self.notify("Wrap-up stopped. I'll stay open.", timeout=3)
            queued, self.ask_queue = self.ask_queue, []
            for rid, _ in queued:
                await self.engine.answer(rid, {"behavior": "deny", "message": "The user stopped you."})
            if self.pending:
                await self.finish_pending({"behavior": "deny", "message": "The user stopped you."})
            self.stopping = True
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

    # ---------- leaving (with a wrap-up first) ----------
    async def action_quit(self):
        await self.close_after_wrap_up(code=77)  # 77 = the launcher closes the terminal window too

    async def close_after_wrap_up(self, code):
        """/exit, /terminal and Ctrl+Q: tidy up the docs (and commit, where wanted) first.
        Asking again while that runs closes straight away."""
        now = time.monotonic()
        if self.wrapping or self.closing_at is not None or now - self.quit_armed < 10:
            await self.leave(code)
            return
        on, words = settings.rule(settings.WRAP_UP)
        alive = self.engine and self.engine.proc and self.engine.proc.returncode is None
        if not (on and words and self.chatted and alive):
            await self.leave(code)
            return
        if self.pending or self.dialog:
            self.notify("Answer the question above first, or press Ctrl+Q again to close now.",
                        timeout=4)
            self.quit_armed = now  # a second Ctrl+Q in the next few seconds closes
            return
        self.wrapping = {"code": code}
        note = (f"[Quill note: the user is closing Quill now, so wrap up. "
                f"{' '.join(words.split())}]")
        if await self.send(note, shown="(closing: wrap up)"):
            self.show("**Wrapping up before I close.** I'm bringing the notes up to date and "
                      "committing where that's wanted.\n\n"
                      "*Esc stops the wrap-up · Ctrl+Q again closes right now*")
        else:
            await self.leave(code)

    @property
    def wrap_code(self):
        return (self.wrapping or {}).get("code", 77)

    def wrapped(self, ok):
        """The wrap-up turn ended. Done: show what I did, then close. Not done: stay open."""
        if not ok:
            self.wrapping = None
            self.show_reply()
            self.notify("The wrap-up didn't finish, so I'm staying open.", timeout=4)
            return
        self.closing_at = time.monotonic() + CLOSE_AFTER
        self.set_choices([Button("Close now", name="wr-close", variant="primary"),
                          Button("Stay open", name="wr-stay")], focus=False)
        self.tick_status()

    def stay_open(self):
        self.closing_at, self.wrapping = None, None
        self.clear_choices()
        self.status("Staying open")

    async def leave(self, code):
        self.closing_at = None
        if self.engine:
            await self.engine.stop()
        write_tty("\x1b[23;0t")  # give the terminal its own title back
        self.exit(return_code=code)

    def on_unmount(self):
        if self.sudo_server:
            self.sudo_server.close()
        proc = self.engine and self.engine.proc
        if proc and proc.returncode is None:
            proc.kill()  # closed some other way than /exit: don't leave Claude Code running


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
