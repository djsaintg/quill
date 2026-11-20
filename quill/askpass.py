#!/usr/bin/env python3
"""SUDO_ASKPASS helper: sudo runs this when it needs a password.

It asks the Quill window that started Claude Code (over a private socket),
shows you the exact command, and prints the password only if you approve.
Exit code 1 = no password (sudo then fails safely).
"""
import json
import os
import socket
import sys


def sudo_command():
    try:
        with open(f"/proc/{os.getppid()}/cmdline", "rb") as f:
            args = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return "(unknown command)"
    args = args[1:]  # drop "sudo"
    while args and args[0].startswith("-") and args[0] != "--":
        args = args[1:]
    if args and args[0] == "--":
        args = args[1:]
    return " ".join(args) or "(sudo with no command)"


def main():
    path = os.environ.get("QUILL_SUDO_SOCK")
    if not path:
        return 1
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(path)
        s.sendall((json.dumps({"cmd": sudo_command(), "prompt": " ".join(sys.argv[1:])}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        reply = json.loads(data or b"{}")
    except (OSError, ValueError):
        return 1
    if "password" in reply:
        sys.stdout.write(reply["password"] + "\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
