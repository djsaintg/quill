"""Words Quill shows you: the greeting, /help, and how permission questions read."""
import os

GREETING = ("Hi! I'm **Quill**, your desk robot. "
            "Ask me anything, or tell me what we're working on.\n\n"
            "*Esc stops me mid-answer · F2 shows our chat so far · F3 copies my reply · /help for more*")

HELP = """**Things you can type**

- Anything: it goes straight to Claude Code
- `/history` (or F2): the whole chat so far
- `/copy` (or F3): copy Quill's last reply
- Drag over any text with the mouse, then Ctrl+C, to copy just that part
- `/new`: start a fresh conversation
- `/resume` (or `--resume`, `-r`): every earlier chat, newest first; `/resume <word>` searches them
- `/continue` (or `-c`): pick up the last chat in this folder
- `/projects`: your recent projects and what's next in each
- `\\` then Enter (or Ctrl+J): new line in your message
- `/sudo`: let Quill use sudo (or `/sudo off`)
- `/character` (or `/character quill` / `/character plume`): switch between Quill and Plume
- `/name` (or `/name Sam`): what I call you
- `/theme` (or `/theme classic` / `/theme aurora`): change this character's colours
- `/exit` (or Ctrl+Q): wrap up (notes, commits where wanted), then close this terminal window
- `/exit now` (or Ctrl+Q twice): close straight away, no wrap-up
- `/terminal`: wrap up, then leave Quill but keep the terminal open
- `/rules`: the rules I follow in every chat (switch them on or off in `config.md`)
- `/remote-control` (or `/rc`): carry on this chat from your phone or claude.ai (`/rc off` to stop)
- `/notify off` / `/notify on`: desktop pop-ups when I need you or finish a long job
- Other `/commands` and skills are passed to Claude Code

**Keys**: Esc = stop me · F2 = history · F3 = copy reply · Ctrl+Q = quit"""


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
