"""Desktop pop-ups and Remote Control (carry the chat on in the Claude app)."""
import asyncio
import os

from . import notify


class RemoteMixin:
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
