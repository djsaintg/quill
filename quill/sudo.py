"""Sudo for Quill: settings, the private socket askpass talks to, and safety checks.

Modes
  off     sudo always fails (default)
  chat    on for this Quill window only; asks before every root command
  ask     on in every chat; asks before every root command
  always  on in every chat; root commands run without asking

The password is never written to disk. It's kept in memory for the open
Quill window only, and forgotten when Quill closes or sudo is turned off.
"""
import asyncio
import json
import os
import shutil
import socket
import struct
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHIMS = os.path.join(HERE, "shims")
ASKPASS = os.path.join(HERE, "askpass.py")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                      "quill", "config.json")

LABELS = {
    "off": "",
    "chat": "SUDO: this chat",
    "ask": "SUDO: asks each time",
    "always": "SUDO: ALWAYS ALLOWED",
}

SYSTEM_NOTE = (
    "You are running inside Quill, a chat window for Claude Code. `sudo` works here: "
    "Quill shows the user each root command and asks for their password, unless they've "
    "allowed sudo without asking. If sudo fails with 'no password was provided' or "
    "similar, the user declined or sudo is off in Quill (they can type /sudo to turn it "
    "on). Never try to get around that."
)


def load_mode():
    try:
        with open(CONFIG) as f:
            mode = json.load(f).get("sudo", "off")
        return mode if mode in ("ask", "always") else "off"
    except (OSError, ValueError):
        return "off"


def save_mode(mode):
    """Only the permanent modes are saved; 'chat' and 'off' clear the file setting."""
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    if mode in ("ask", "always"):
        cfg["sudo"] = mode
    else:
        cfg.pop("sudo", None)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)


def socket_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(base, f"quill-{os.getpid()}.sock")


def child_env(sock):
    """Environment for the claude process so its `sudo` goes through Quill."""
    real = shutil.which("sudo") or "/usr/bin/sudo"
    env = dict(os.environ)
    env["PATH"] = SHIMS + os.pathsep + env.get("PATH", "")
    env["SUDO_ASKPASS"] = ASKPASS
    env["QUILL_SUDO_SOCK"] = sock
    env["QUILL_REAL_SUDO"] = real
    return env


def _status(pid):
    out = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            k, _, v = line.partition(":")
            out[k] = v.split()
    return out


def peer_is_sudo(conn):
    """Only answer askpass helpers that a real, running sudo started.

    The helper's parent must be a process called sudo running as root
    (only the setuid sudo binary can be that), owned by our own user.
    """
    try:
        creds = conn.get_extra_info("socket").getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, _ = struct.unpack("3i", creds)
        if uid != os.getuid():
            return None
        parent = int(_status(pid)["PPid"][0])
        st = _status(parent)
        if st.get("Name", [""])[0] != "sudo" or st["Uid"][1] != "0" or st["Uid"][0] != str(os.getuid()):
            return None
        return parent
    except (OSError, KeyError, IndexError, ValueError, struct.error, AttributeError):
        return None


class SudoServer:
    """Listens for askpass. `on_request(cmd, sudo_pid)` returns a password or None."""

    def __init__(self, on_request):
        self.on_request = on_request
        self.path = socket_path()
        self.server = None
        self.lock = asyncio.Lock()

    async def start(self):
        if os.path.exists(self.path):
            os.unlink(self.path)
        old = os.umask(0o177)  # socket is created 0600: only you can connect
        try:
            self.server = await asyncio.start_unix_server(self._handle, path=self.path)
        finally:
            os.umask(old)

    async def _handle(self, reader, writer):
        reply = {"cancel": True}
        try:
            line = await asyncio.wait_for(reader.readline(), 5)
            req = json.loads(line or b"{}")
            sudo_pid = peer_is_sudo(writer)
            if sudo_pid:
                async with self.lock:  # one question at a time
                    pw = await self.on_request(req.get("cmd", "?"), sudo_pid)
                if pw is not None:
                    reply = {"password": pw}
        except (asyncio.TimeoutError, ValueError, OSError):
            pass
        try:
            writer.write((json.dumps(reply) + "\n").encode())
            await writer.drain()
            writer.close()
        except OSError:
            pass

    def close(self):
        if self.server:
            self.server.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass
