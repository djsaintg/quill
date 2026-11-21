"""Quill's sudo questions: turning sudo on or off, and the password box."""
import asyncio

from textual.widgets import Button, Input

from . import sudo


class SudoMixin:
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
