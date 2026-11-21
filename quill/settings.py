"""Rules for Claude that you can switch on and off, in a plain Markdown file.

~/.config/quill/config.md is a checklist: `- [x]` is on, `- [ ]` is off. You can edit it by
hand, change the wording of any rule, add rules of your own in the same shape, or ask Quill
or Plume to do it for you. The rules that are on are told to Claude when a chat starts.

Quill's other settings (character, theme, sudo, ...) stay in config.json next to it.
"""
import os
import re

from .sudo import CONFIG as JSON_CONFIG

PATH = os.path.join(os.path.dirname(JSON_CONFIG), "config.md")

WRAP_UP = "Wrap up"
TEST_REPOS = "Test repos"

# Built-in rules: (name, on by default?, the words Claude is given)
BUILT_IN = [
    (WRAP_UP, True,
     "When the user says 'wrap up', or Quill says the user is closing the window, do the "
     "housekeeping before the chat ends. For every project or repo this chat changed, bring its "
     "documentation up to date with what was actually done (README, CHANGELOG, ROADMAP, a "
     "HANDOFF.md or any other notes it keeps, and your memory), so the next chat finds nothing "
     "undocumented. Then commit and push where that is the user's or the repo's usual way and the "
     "user's own instructions allow it. If they want to test or approve first, or it's a test "
     "repo, leave it uncommitted and say so. Never commit secrets. Finish with a short summary: "
     "what was updated, what was committed and pushed, and anything left undone."),
    (TEST_REPOS, False,
     "When the user asks for a 'test repo' (or test project / test folder), it is throwaway, only "
     "for testing something and noting the issues or changes they find. Make it a plain local "
     "folder: never add a git remote, create a GitHub repo, commit or push it. Keep its notes up "
     "to date as you go. When the user ends the chat (e.g. says 'wrap up'), first give a short "
     "summary of what it recorded so the findings can be carried over, then delete the test "
     "folder without asking; that is already approved. Only delete the folder you made for the "
     "test in this chat; if it has a git remote or the user said to keep it, ask instead."),
]

HEADER = """# Quill settings

Rules for Claude in every Quill and Plume chat. `[x]` = on, `[ ]` = off.
Change them here, or ask Quill or Plume to change them for you; they apply from the next chat.
You can reword any rule, or add your own at the end of the list in the same shape.
To turn a built-in rule off, untick it: if you delete it, it comes back.

## Rules
"""

RULE = re.compile(r"^- \[( |x|X)\] \*\*(.+?)\*\*:?\s*(.*)$")


def parse(text):
    """[(name, on, words)] in file order. A rule's words may carry on over indented lines."""
    rules = []
    for line in text.splitlines():
        m = RULE.match(line)
        if m:
            rules.append([m.group(2).strip(), m.group(1) != " ", m.group(3).strip()])
        elif rules and line.startswith((" ", "\t")) and line.strip():
            rules[-1][2] = (rules[-1][2] + " " + line.strip()).strip()
    return [tuple(r) for r in rules]


def render(rules):
    return HEADER + "\n" + "\n".join(
        f"- [{'x' if on else ' '}] **{name}**: {words}" for name, on, words in rules) + "\n"


def load(path=None):
    """The rules, creating the file (or adding new built-in rules to it) if needed."""
    path = path or PATH
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = None
    rules = parse(text) if text is not None else []
    have = {name.lower() for name, _, _ in rules}
    missing = [r for r in BUILT_IN if r[0].lower() not in have]
    if missing or text is None:
        rules += missing
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if text is None:
                new = render(rules)
            else:  # keep everything you wrote; just add the new rules at the end
                new = text.rstrip("\n") + "\n" + render(missing).split("## Rules\n", 1)[1].lstrip("\n")
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
        except OSError:
            pass  # read-only config: the defaults still apply
    return rules


def rule(name, path=None):
    """(on, words) for one rule, by name (any case)."""
    for n, on, words in load(path):
        if n.lower() == name.lower():
            return on, words
    return False, ""


def system_note(path=None):
    """What Claude is told about these rules when a chat starts."""
    path = path or PATH
    on = [f"{name}: {' '.join(words.split())}" for name, enabled, words in load(path)
          if enabled and words]
    shown = path.replace(os.path.expanduser("~"), "~", 1)
    note = (f"Quill's rules live in {shown}, a Markdown checklist (`- [x]` on, `- [ ]` off). If "
            "the user asks you to turn one on or off, change its box there; reword or add rules "
            "only when asked. Changes apply from the next chat.")
    return "\n\n".join(on + [note])
