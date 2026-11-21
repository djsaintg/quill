"""Talks to the installed `claude` CLI in headless stream-json mode.

Claude Code runs as a child process with its own screen switched off.
We write JSON lines to its stdin (your messages, permission answers) and
read JSON lines from its stdout (streamed text, tool calls, questions).
"""
import asyncio
import json
import os
import shutil
import re
import uuid

BASE_ARGS = [
    "-p",
    "--input-format", "stream-json",
    "--output-format", "stream-json",
    "--verbose",
    "--include-partial-messages",
    "--permission-prompt-tool", "stdio",
]


SESSION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Settings a parent Claude Code session leaves in the environment. If Quill is started
# from inside Claude Code (e.g. a `!` command), passing these on would make the child
# reuse that session's ID and messaging socket.
INHERITED = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_PID",
             "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
             "CLAUDE_CODE_CHILD_NOTES_DIR", "CLAUDE_CODE_SESSION_ATTENDED",
             "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH", "CLAUDE_EFFORT", "AI_AGENT")


def clean_env(env=None):
    env = dict(os.environ if env is None else env)
    for k in INHERITED:
        env.pop(k, None)
    env["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"] = "1"  # the window title is Quill's to set
    return env


def find_claude():
    """The real claude binary, never a `claude` alias/wrapper pointing back at Quill."""
    override = os.environ.get("QUILL_CLAUDE_BIN")
    if override:
        return override
    for cand in (os.path.expanduser("~/.local/bin/claude"), shutil.which("claude")):
        if cand and os.path.exists(cand) and "quill" not in os.path.realpath(cand):
            return cand
    raise FileNotFoundError("Couldn't find the claude command. Is Claude Code installed?")


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


def resume_request(args):
    """Read Claude Code's resume flags the way `claude` does, for `quill` and `plume`.

    `-c` / `--continue` (and `--c`) and `--resume <session id>` go on to Claude Code as they
    are. `-r` / `--resume` (and `--r`) on their own, or with a search word or chat name instead
    of an id, open Quill's list of earlier chats. Returns (args for Claude Code, search):
    search is None when there's no list to show, "" for every chat, or the word to look for.
    """
    out, search, i = [], None, 0
    args = ["-c" if a == "--c" else "-r" if a == "--r" else a for a in args]
    while i < len(args):
        a = args[i]
        if a in ("-r", "--resume") or a.startswith("--resume="):
            if "=" in a:
                value = a.split("=", 1)[1]
            elif i + 1 < len(args) and not args[i + 1].startswith("-"):
                value, i = args[i + 1], i + 1
            else:
                value = ""
            if SESSION_ID.match(value):
                out += ["--resume", value]
            else:
                search = value
        else:
            out.append(a)
        i += 1
    return out, search


class Engine:
    def __init__(self, extra_args=None, cwd=None, env=None):
        self.extra_args = list(extra_args or [])
        self.env = env
        self.cwd = cwd or os.getcwd()
        self.proc = None
        self.stderr_tail = []
        self.waiting = {}  # request_id -> future, for control requests that need a reply

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            find_claude(), *BASE_ARGS, *self.extra_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=clean_env(self.env),
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
        rid = f"quill-{uuid.uuid4().hex[:12]}"
        await self._send({"type": "control_request", "request_id": rid, "request": request})
        return rid

    async def request(self, request, timeout=45):
        """Send a control request and wait for Claude Code's reply to it."""
        rid = f"quill-{uuid.uuid4().hex[:12]}"
        fut = asyncio.get_running_loop().create_future()
        self.waiting[rid] = fut
        await self._send({"type": "control_request", "request_id": rid, "request": request})
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.waiting.pop(rid, None)

    def resolve(self, ev):
        """Hand a control_response to whoever is waiting for it."""
        resp = ev.get("response") or {}
        fut = self.waiting.get(resp.get("request_id"))
        if fut and not fut.done():
            if resp.get("subtype") == "error":
                fut.set_exception(RuntimeError(resp.get("error") or "Claude Code said no"))
            else:
                fut.set_result(resp.get("response") or {})

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


# describe_tool() says what's happening ("Reading app.py"); once a step is finished
# its line in the bubble switches to the past tense ("Read app.py").
PAST = [("Reading a web page", "Read a web page"), ("Reading ", "Read "), ("Editing ", "Edited "),
        ("Writing ", "Wrote "), ("Running: ", "Ran: "), ("Searching ", "Searched "),
        ("Sending a helper: ", "Helper: "), ("Updating ", "Updated "), ("Loading ", "Loaded "),
        ("Using ", "Used ")]


def past_tense(label):
    for now, then in PAST:
        if label.startswith(now):
            return then + label[len(now):]
    return label


def _short(text, n=60):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def describe_result(name, inp, result, content, is_error):
    """A few words on how a finished step went, e.g. "130 lines" or "exit code 2".

    `result` is Claude Code's structured tool_use_result (its shape differs per tool and
    between versions, so everything here is best effort); `content` is the plain text
    the model saw.
    """
    if isinstance(content, list):  # [{"type": "text", "text": ...}, ...]
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    content = str(content or "")
    try:
        if is_error:
            low = content.lower()
            if "user said no" in low or "doesn't want to proceed" in low or "rejected" in low:
                return "you said no"
            if "user stopped" in low or "interrupted" in low:
                return "stopped"
            lines = [l for l in content.splitlines() if l.strip()]
            if lines and lines[0].lower().startswith("exit code"):
                return _short(lines[0].lower() + (" · " + lines[1] if len(lines) > 1 else ""))
            return _short(lines[0] if lines else "failed")
        r = result if isinstance(result, dict) else {}
        if name == "Read":
            n = (r.get("file") or {}).get("numLines")
            return _plural(n, "line") if isinstance(n, int) else ""
        if name == "Bash":
            out = (r.get("stdout") or "").strip() if r else content.strip()
            if r.get("backgroundTaskId"):
                return "running in the background"
            if not out:
                return "done"
            lines = out.splitlines()
            return _short(lines[0], 50) if len(lines) == 1 else _plural(len(lines), "line") + " of output"
        if name in ("Edit", "MultiEdit"):
            added = removed = 0
            for hunk in r.get("structuredPatch") or []:
                for l in hunk.get("lines", []):
                    added += l.startswith("+")
                    removed += l.startswith("-")
            return f"+{added} −{removed}" if added or removed else "saved"
        if name == "Write":
            return "new file" if r.get("type") == "create" else "saved"
        if name == "Grep":
            if r.get("mode") == "content" and isinstance(r.get("numLines"), int):
                return _plural(r["numLines"], "matching line")
            if isinstance(r.get("numFiles"), int):
                return "no matches" if r["numFiles"] == 0 else _plural(r["numFiles"], "file")
        if name == "Glob" and isinstance(r.get("numFiles"), int):
            return _plural(r["numFiles"], "file")
        if name == "WebSearch":
            hits = sum(len(x.get("content") or []) for x in r.get("results") or [] if isinstance(x, dict))
            return _plural(hits, "result") if hits else ""
    except (AttributeError, TypeError, ValueError):
        pass
    return ""
