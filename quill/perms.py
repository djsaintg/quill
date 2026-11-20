"""Quill's permission ladder for "Yes, and don't ask again".

Saying that to a request grants its level, and everything below it, for the
rest of this chat only. Nothing is saved: a new chat, /new, /resume or picking
a project starts from zero again. Higher levels still ask.

Routine actions (reading, searching, Monitor and the like) normally never reach
Quill at all, because Claude Code runs in the same auto mode as a normal session.
"""
import os
import re

READ, EDIT_HERE, EDIT_ELSEWHERE, COMMANDS, SUDO = 1, 2, 3, 4, 5

NAMES = {
    READ: "reading and searching",
    EDIT_HERE: "creating and editing files in this folder",
    EDIT_ELSEWHERE: "creating and editing files anywhere",
    COMMANDS: "running commands",
    SUDO: "running commands as root (sudo)",
}

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead", "WebSearch", "WebFetch",
              "TodoWrite", "ListMcpResourcesTool", "ReadMcpResourceTool"}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
NEVER_AUTO = {"AskUserQuestion", "ExitPlanMode"}  # questions and plans always need you
SUDO_RE = re.compile(r"(^|[;&|(`]\s*|\s)sudo(\s|$)")


def inside(path, folder):
    try:
        p, f = os.path.realpath(path), os.path.realpath(folder)
    except (TypeError, ValueError):
        return False
    return p == f or p.startswith(f.rstrip("/") + "/")


def level(tool, inp, cwd):
    inp = inp or {}
    if tool in READ_TOOLS:
        return READ
    if tool in EDIT_TOOLS:
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        if path and not os.path.isabs(path):
            path = os.path.join(cwd, path)
        return EDIT_HERE if path and inside(path, cwd) else EDIT_ELSEWHERE
    if tool == "Bash":
        return SUDO if SUDO_RE.search(inp.get("command", "")) else COMMANDS
    return COMMANDS  # anything else (MCP tools, etc.) counts as running something


def allowed(tool, inp, cwd, granted):
    return tool not in NEVER_AUTO and granted and level(tool, inp, cwd) <= granted
