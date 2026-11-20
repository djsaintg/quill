"""Talks to the installed `claude` CLI in headless stream-json mode.

Claude Code runs as a child process with its own screen switched off.
We write JSON lines to its stdin (your messages, permission answers) and
read JSON lines from its stdout (streamed text, tool calls, questions).
"""
import asyncio
import json
import os
import shutil
import uuid

BASE_ARGS = [
    "-p",
    "--input-format", "stream-json",
    "--output-format", "stream-json",
    "--verbose",
    "--include-partial-messages",
    "--permission-prompt-tool", "stdio",
]


def find_claude():
    """The real claude binary, never a `claude` alias/wrapper pointing back at Quill."""
    override = os.environ.get("QUILL_CLAUDE_BIN")
    if override:
        return override
    for cand in (os.path.expanduser("~/.local/bin/claude"), shutil.which("claude")):
        if cand and os.path.exists(cand) and "quill" not in os.path.realpath(cand):
            return cand
    raise FileNotFoundError("Couldn't find the claude command. Is Claude Code installed?")


class Engine:
    def __init__(self, extra_args=None, cwd=None):
        self.extra_args = list(extra_args or [])
        self.cwd = cwd or os.getcwd()
        self.proc = None
        self.stderr_tail = []

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            find_claude(), *BASE_ARGS, *self.extra_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            limit=64 * 1024 * 1024,  # a single line can carry a whole file
        )
        asyncio.create_task(self._drain_stderr())
        await self.control({"subtype": "initialize"})

    async def _drain_stderr(self):
        async for line in self.proc.stderr:
            self.stderr_tail = (self.stderr_tail + [line.decode(errors="replace").rstrip()])[-20:]

    async def _send(self, obj):
        if not self.proc or self.proc.stdin.is_closing():
            raise RuntimeError("Claude isn't running")
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        await self.proc.stdin.drain()

    async def control(self, request):
        await self._send({"type": "control_request",
                          "request_id": f"quill-{uuid.uuid4().hex[:12]}",
                          "request": request})

    async def say(self, text):
        await self._send({"type": "user",
                          "message": {"role": "user", "content": text}})

    async def interrupt(self):
        await self.control({"subtype": "interrupt"})

    async def answer(self, request_id, response):
        await self._send({"type": "control_response",
                          "response": {"subtype": "success",
                                       "request_id": request_id,
                                       "response": response}})

    async def events(self):
        """Yield every JSON message Claude prints, until it exits."""
        async for raw in self.proc.stdout:
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                continue

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.stdin.close()
                await asyncio.wait_for(self.proc.wait(), 3)
            except (asyncio.TimeoutError, Exception):
                self.proc.kill()


def describe_tool(name, inp):
    """A short human line for the status bar: what Quill is up to."""
    inp = inp or {}
    path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or ""
    short = os.path.basename(path) if path else ""
    if name == "Read":
        return f"Reading {short}"
    if name in ("Edit", "MultiEdit", "NotebookEdit"):
        return f"Editing {short}"
    if name == "Write":
        return f"Writing {short}"
    if name == "Bash":
        return "Running: " + (inp.get("description") or inp.get("command", ""))[:70]
    if name in ("Grep", "Glob"):
        return f"Searching for {inp.get('pattern', '')[:50]}"
    if name == "WebSearch":
        return f"Searching the web: {inp.get('query', '')[:50]}"
    if name == "WebFetch":
        return f"Reading a web page"
    if name in ("Task", "Agent"):
        return "Sending a helper: " + inp.get("description", "")[:50]
    if name == "TodoWrite":
        return "Updating my to-do list"
    if name == "Skill":
        return f"Loading skill {inp.get('skill', '')}"
    return f"Using {name}"
