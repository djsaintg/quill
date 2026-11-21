"""Quill's own /commands. Anything else typed with a / goes on to Claude Code."""
import os

from textual.widgets import Static

from . import settings, sudo, themes
from .engine import strip_resume
from .sprites import CHARACTERS
from .texts import HELP


class CommandsMixin:
    async def run_command(self, text):
        """Handle `text` if it's one of Quill's commands. True = handled, don't send it on."""
        cmd = text.lower()
        if cmd in ("/exit now", "/quit now"):
            await self.leave(code=77)  # no wrap-up
            return True
        if cmd in ("/quit", "/exit"):
            await self.close_after_wrap_up(code=77)
            return True
        if cmd == "/terminal":
            await self.close_after_wrap_up(code=3)  # back to a normal terminal
            return True
        if cmd in ("/remote-control", "/rc", "/remote-control on", "/rc on"):
            self.run_worker(self.remote_control(True), group="rc")
            return True
        if cmd in ("/remote-control off", "/rc off"):
            self.run_worker(self.remote_control(False), group="rc")
            return True
        if cmd == "/name":
            self.ask_name()
            return True
        if cmd.startswith("/name "):
            self.dialog = {"kind": "name"}
            self.name_done(text[6:])
            return True
        if cmd == "/character" or cmd.startswith("/character "):
            arg = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
            who = arg if arg in CHARACTERS else ("plume" if self.who == "quill" else "quill")
            self.switch_to(who)
            return True
        if cmd == "/theme" or cmd.startswith("/theme "):
            self.theme_command(cmd)
            return True
        if cmd in ("/notify on", "/notify off", "/notify"):
            self.notify_on = cmd != "/notify off"
            sudo.set_config("notifications", self.notify_on)
            self.show("Desktop pop-ups are **" + ("on" if self.notify_on else "off") + "**: "
                      "I'll pop one up when I need you or finish a long job while you're in "
                      "another window.")
            return True
        if cmd == "/rules":
            self.show_rules()
            return True
        if cmd == "/help":
            self.show(HELP.replace("Quill", self.char_name))
            return True
        if cmd == "/copy":
            self.action_copy_reply()
            return True
        if cmd == "/history":
            self.action_history()
            return True
        if cmd in ("/new", "/clear"):
            self.log_items, self.busy, self.chatted = [], False, False
            self.new_turn()
            self.claude_args = strip_resume(self.claude_args)
            self.show("Fresh start! What's next?")
            self.query_one("#you", Static).update("")
            self.start_engine(fresh=True)
            return True
        return False

    def theme_command(self, cmd):
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

    def show_rules(self):
        rules = settings.load()
        shown = settings.PATH.replace(os.path.expanduser("~"), "~", 1)
        lines = ["**Rules I follow in every chat**", ""]
        for name, on, words in rules:
            lines.append(f"- {'☑' if on else '☐'} **{name}**: {words[:110]}{'…' if len(words) > 110 else ''}")
        lines += ["", f"*They live in `{shown}`. Edit that file, or ask me to turn one on or off "
                      "(it applies from the next chat).*"]
        self.show("\n".join(lines), top=True)

