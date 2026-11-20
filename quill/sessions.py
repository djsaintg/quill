"""Read Claude Code's saved chats and project roadmaps (for the "pick up where we left off" picker).

Claude Code keeps one JSONL transcript per chat in
~/.claude/projects/<folder path with non-alphanumerics as '-'>/<session id>.jsonl
"""
import glob
import json
import os
import re
import time


def project_dir(cwd=None):
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(base, "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd or os.getcwd()))


def _user_text(o):
    if o.get("isMeta") or o.get("isSidechain"):
        return None
    content = (o.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = "\n".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    content = content.strip()
    if not content or content.startswith("<"):  # command wrappers, reminders
        return None
    return content


def _lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def transcript(session_id, cwd=None):
    """[(who, text)] for the chat, oldest first; who is 'you' or 'quill'."""
    return transcript_file(os.path.join(project_dir(cwd), f"{session_id}.jsonl"))


def transcript_file(path):
    items = []
    for o in _lines(path):
        t = o.get("type")
        if t == "user":
            text = _user_text(o)
            if text:
                items.append(("you", text))
        elif t == "assistant" and not o.get("isSidechain"):
            msg = o.get("message") or {}
            text = "\n\n".join(b.get("text", "") for b in msg.get("content") or []
                               if isinstance(b, dict) and b.get("type") == "text").strip()
            if not text:
                continue
            if items and items[-1][0] == "quill":  # one turn can span several messages
                items[-1] = ("quill", items[-1][1] + "\n\n" + text)
            else:
                items.append(("quill", text))
    return items


ROADMAPS = ["ROADMAP.md", "roadmap.md", "docs/roadmap.md", "docs/ROADMAP.md",
            "HANDOFF.md", "docs/HANDOFF.md", "TODO.md"]


def _clean(text, n=90):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # [link](url) -> link
    text = re.sub(r"[*_`#>]+", "", text)                         # markdown marks
    text = re.sub(r"^\s*([-*+]|\d+\.)\s*(\[[ xX]\]\s*)?", "", text)  # bullets, numbers, boxes
    text = text.strip(" :-")
    m = re.match(r"(.{25,}?[.!?])\s", text)   # first sentence is enough
    if m:
        text = m.group(1)
    return one_line(text[:1].upper() + text[1:], n)


def _done(line):
    """Finished, historical or optional: not a sensible 'next' item."""
    if re.search(r"~~|\bdone\b|✅|\[[xX]\]|\b20\d\d-\d\d-\d\d\b", line, re.I):
        return True  # crossed out, ticked, or dated (roadmaps date things that happened)
    line = re.sub(r"^\s*([-*+]|\d+\.)\s*(\[[ xX]\]\s*)?", "", line)  # drop "7." / "- [ ]"
    return bool(re.match(r"^\W*(optional|maybe|later|someday|idea|nice to have)\b", line, re.I))


def _next_sentence(line):
    m = re.search(r'(?<!["“])\bnext (?:step|up) is\s+(.+)', line, re.I)
    return _clean(m.group(1)) if m else None


BULLET = re.compile(r"^\s{0,3}([-*+]|\d+\.)\s")


def roadmap_next(folder):
    """Best guess at the next item on a project's roadmap/handoff, or None."""
    return roadmap_next_info(folder)[0]


def _last_quill(path, mention=None):
    """The gist of Claude's last message in a chat (preferring one that names the project)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - 3_000_000))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    texts = []
    for line in reversed(tail):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("type") != "assistant" or o.get("isSidechain"):
            continue
        text = "\n".join(b.get("text", "") for b in (o.get("message") or {}).get("content") or []
                         if isinstance(b, dict) and b.get("type") == "text").strip()
        if text:
            texts.append(text)
        if len(texts) >= 30:
            break
    if not texts:
        return None
    pick = texts[0]
    if mention:
        pick = next((t for t in texts if mention.lower() in t.lower()), pick)
    paras = [p for p in re.split(r"\n\s*\n", pick)
             if p.strip() and not p.lstrip().startswith(("```", "|", "#"))]
    return _clean(paras[-1] if paras else pick) or None


def roadmap_next_info(folder):
    """(next item, roadmap file it came from), or (None, None)."""
    for name in ROADMAPS:
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        # 1. a "Next" / "Next steps" section
        for i, line in enumerate(lines):
            if not re.match(r"^#{1,4}\s.*\bnext\b", line, re.I):
                continue
            body = []
            for b in lines[i + 1:]:
                if b.startswith("#"):
                    break
                body.append(b)
            for b in body:                       # "Next up is step 7 ..."
                if _next_sentence(b):
                    return _next_sentence(b), path
            for b in body:                       # first open bullet / checkbox
                if BULLET.match(b) and not _done(b) and not b.rstrip().endswith(":"):
                    return _clean(b), path
            for b in body:                       # first plain line
                if b.strip() and not b[0].isspace() and not _done(b) and not b.rstrip().endswith(":"):
                    return _clean(b), path
        # 2. the first unticked checkbox anywhere
        for line in lines:
            if re.match(r"^\s*[-*]\s*\[ \]", line) and not _done(re.sub(r"\[ \]", "", line)):
                return _clean(line), path
        # 3. a "Next step is ..." sentence anywhere
        for line in lines:
            if _next_sentence(line):
                return _next_sentence(line), path
        # 4. the first top-level numbered step that isn't done
        for line in lines:
            if re.match(r"^\d+\.\s", line) and not _done(line):
                return _clean(line), path
    return None, None


def _session_cwd(path):
    for i, o in enumerate(_lines(path)):
        if o.get("cwd"):
            return o["cwd"]
        if i > 60:
            break
    return None


def _last_you(path):
    """Your last message in a chat, reading only the end of big files."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - 2_000_000))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("type") == "user":
            text = _user_text(o)
            if text:
                return text
    return None


def is_container(folder):
    """A folder of projects (like 'GitHub Projects') rather than a project itself."""
    if os.path.isdir(os.path.join(folder, ".git")):
        return False
    if any(os.path.exists(os.path.join(folder, r)) for r in ROADMAPS):
        return False
    try:
        subdirs = [e for e in os.scandir(folder) if e.is_dir() and not e.name.startswith(".")]
    except OSError:
        return False
    return len(subdirs) >= 2


CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                     "quill", "attribution.json")


def _load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w") as f:
            json.dump(cache, f)
    except OSError:
        pass


def touched_project(path, container):
    """Which sub-folder of `container` a chat mostly worked in (or None).

    Counts the folder Claude was in for each step, plus paths in its tool calls
    (files read/edited, commands run). Tool *results* are ignored, so a long
    `ls` of every project doesn't count.
    """
    prefix = container.rstrip("/") + "/"
    pat = re.compile(re.escape(prefix) + r"([^/\"\\\n]+)")
    counts = {}

    def add(name, n=1):
        name = name.strip()
        if name and os.path.isdir(prefix + name):
            counts[name] = counts.get(name, 0) + n

    for o in _lines(path):
        cwd = o.get("cwd") or ""
        if cwd.startswith(prefix):
            add(cwd[len(prefix):].split("/")[0])
        if o.get("type") == "assistant":
            for b in (o.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    for m in pat.finditer(json.dumps(b.get("input"), ensure_ascii=False)):
                        add(m.group(1), 2)
    if not counts:
        return None
    best = max(counts, key=counts.get)
    return prefix + best if counts[best] >= 3 else None


def projects(limit=6, here=None):
    """Projects you've recently chatted with Claude Code in, newest first.

    Each: name, folder (the project), chat_cwd (where the chat itself ran, needed to
    resume it), session, path, when, next (roadmap/notes item), next_from, last_you.
    Chats started in a container folder like 'GitHub Projects' are filed under the
    project they actually worked on. The folder Quill was started in comes first.
    """
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"),
                        "projects")
    home = os.path.expanduser("~")
    cache, cache_dirty = _load_cache(), False
    found = {}

    def offer(folder, chat_cwd, path, when):
        if folder not in found or when > found[folder]["when"]:
            found[folder] = {"name": os.path.basename(folder.rstrip("/")) or folder,
                             "folder": folder, "chat_cwd": chat_cwd, "when": when,
                             "session": os.path.basename(path)[:-6], "path": path}

    try:
        dirs = [d.path for d in os.scandir(base) if d.is_dir()]
    except OSError:
        return []
    for d in dirs:
        chats = sorted(glob.glob(os.path.join(d, "*.jsonl")), key=os.path.getmtime, reverse=True)
        if not chats:
            continue
        cwd = _session_cwd(chats[0])
        if (not cwd or cwd == home or not os.path.isdir(cwd)
                or cwd.startswith(("/tmp/", "/var/tmp/"))):
            continue
        if not is_container(cwd):
            offer(cwd, cwd, chats[0], os.path.getmtime(chats[0]))
            continue
        for path in chats[:25]:  # a container's recent chats, each filed under its project
            st = os.stat(path)
            key = f"{st.st_mtime}:{st.st_size}"
            hit = cache.get(path)
            if hit and hit[0] == key:
                folder = hit[1]
            else:
                folder = touched_project(path, cwd)
                cache[path], cache_dirty = [key, folder], True
            if folder and _session_cwd(path) == cwd:
                offer(folder, cwd, path, st.st_mtime)
            elif folder is None:
                offer(cwd, cwd, path, st.st_mtime)
    if cache_dirty:
        _save_cache(cache)

    ordered = sorted(found.values(), key=lambda p: p["when"], reverse=True)
    # a container with only tool-only chats has nothing to show
    ordered = [p for p in ordered if p["folder"] != p["chat_cwd"] or not is_container(p["folder"])
               or _last_you(p["path"])]
    if here and here in found and found[here] in ordered:
        ordered.remove(found[here])
        ordered.insert(0, found[here])
    out = ordered[:limit]
    for p in out:
        p["last_you"] = _last_you(p["path"])
        item, file = roadmap_next_info(p["folder"])
        fresh = file and os.path.getmtime(file) >= p["when"] - 7 * 86400
        said = _last_quill(p["path"], p["name"] if p["chat_cwd"] != p["folder"] else None)
        if item and fresh:
            p["next"], p["next_from"] = item, "roadmap"
        elif said:  # no roadmap item that makes sense: where Claude left off
            p["next"], p["next_from"] = said, "chat"
        elif item:
            p["next"], p["next_from"] = item, "roadmap"
        else:
            p["next"], p["next_from"] = notes_next(p["folder"]), "notes"
    return out


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def notes_next(folder):
    """What Claude Code's memory notes say is next for this project (or None).

    Looks in the memory of the project folder and of its parent (e.g. 'GitHub Projects'),
    finds the note named after the project, and pulls the "next ..." part of its summary.
    """
    name = _norm(os.path.basename(folder.rstrip("/")))
    if not name:
        return None
    parent = os.path.dirname(folder.rstrip("/"))
    best = None
    for mem in (os.path.join(project_dir(folder), "memory"), os.path.join(project_dir(parent), "memory")):
        try:
            with open(os.path.join(mem, "MEMORY.md"), encoding="utf-8") as f:
                index = f.read().splitlines()
        except OSError:
            continue
        for line in index:
            m = re.match(r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)\s*[—-]+\s*(.+)$", line)
            if not m:
                continue
            title, file, hook = m.groups()
            stem = _norm(os.path.splitext(file)[0].replace("-project", ""))
            if stem == name or _norm(title.replace("project", "")) == name:
                score = 2
            elif stem.startswith(name) or name in _norm(title):
                score = 1
            else:
                continue
            if not best or score > best[0]:
                best = (score, hook, os.path.join(mem, file))
    if not best:
        return None
    hook = best[1]
    for pat in (r"\bnext(?: step)?(?: is|:)\s*([^;]+)", r"\bresume (?:at|with|here)\s*([^;]+)",
                r"([^;,—]{6,}?)\s+(?:is\s+)?next\b"):
        m = re.search(pat, hook, re.I)
        if m:
            return _clean(m.group(1))
    try:
        with open(best[2], encoding="utf-8") as f:
            for line in f:
                if _next_sentence(line):
                    return _next_sentence(line)
    except OSError:
        pass
    return _clean(hook)  # no "next" wording: the note's summary of where things stand


def ago(ts):
    s = max(0, time.time() - ts)
    if s < 90:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < 86400:
        h = int(s // 3600)
        return f"{h} hour{'s' if h > 1 else ''} ago"
    d = int(s // 86400)
    return "yesterday" if d == 1 else f"{d} days ago"


def one_line(text, n=70):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"
