"""The "pick up where we left off" project picker."""
import os

from rich.text import Text
from textual.widgets import Button, Static

from . import sessions
from .engine import strip_resume
from .widgets import ChatBox


class ProjectsMixin:
    # ---------- picking up a project ----------
    def offer_picker(self, first=False):
        here = os.getcwd()
        try:
            projs = sessions.projects(limit=5, here=here)
        except Exception as e:  # noqa: BLE001 - the picker must never stop Quill starting
            projs = []
            self.notify(f"Couldn't list earlier projects: {e}", timeout=4)
        if not projs:
            if not first:
                self.show("I haven't found any earlier chats yet.")
            return
        self.dialog = {"kind": "picker", "projects": projs}
        hi = f"Hi {self.user_name}!" if self.user_name else "Hi!"
        hello = f"{hi} I'm **{self.char_name}**. " if first else ""
        lines = [f"{hello}Want to start something **new**, or pick up where we left off?", ""]
        for i, p in enumerate(projs, 1):
            tag = " *(this folder)*" if p["folder"] == here else ""
            label = {"roadmap": "next", "chat": "left off", "notes": "notes"}.get(p["next_from"], "next")
            if p["next"]:
                sub = f"{label}: {p['next']}"
            else:
                sub = "last: " + sessions.one_line(p["last_you"] or "(nothing yet)", 70)
            lines.append(f"{i}. **{p['name']}**{tag} · *{sessions.ago(p['when'])}*  \n   {sub}")
        lines += ["", "*Or just start typing for something new here.*"]
        self.show("\n".join(lines), top=True)
        buttons = [Button("Something new", name="pk-new", variant="success")]
        buttons += [Button(str(i), name=f"pk-{i - 1}", variant="primary")
                    for i in range(1, len(projs) + 1)]
        self.set_choices(buttons, focus=False)  # keep typing in the message box
        self.status("Something new, or pick a project")

    def close_picker(self):
        self.dialog = None
        self.clear_choices()
        self.status("Ready")

    def pick(self, bid):
        d = self.dialog
        if not d or d["kind"] != "picker":
            return
        if bid == "pk-new":
            self.close_picker()
            self.show("Something new it is. What are we working on?")
            return
        p = d["projects"][int(bid[3:])]
        self.dialog = {"kind": "project", "project": p, "projects": d["projects"]}
        where = (f" (started in *{os.path.basename(p['chat_cwd'])}*)"
                 if p["chat_cwd"] != p["folder"] else "")
        lines = [f"**{p['name']}** · last chat {sessions.ago(p['when'])}{where}", ""]
        if p["next"]:
            label = {"roadmap": "Next on the roadmap", "chat": "Where we left off",
                     "notes": "From my notes"}.get(p["next_from"], "Next")
            lines += [f"**{label}:** {p['next']}", ""]
        if p["last_you"]:
            lines += [f"*Last time you said:* {sessions.one_line(p['last_you'], 160)}"]
        self.show("\n".join(lines))
        self.set_choices([Button("Continue last chat", name="pj-continue", variant="primary"),
                          Button("Fresh chat", name="pj-fresh", variant="success"),
                          Button("Back", name="pj-back")], focus=False)
        self.status(p["folder"])

    def project_choice(self, bid):
        d = self.dialog
        if not d or d["kind"] != "project":
            return
        if bid == "pj-back":
            self.dialog = None
            self.offer_picker()
            return
        self.enter_project(d["project"], resume=(bid == "pj-continue"))

    def enter_project(self, p, resume, prefill=True):
        self.close_picker()
        try:
            # a chat must be resumed from the folder it ran in; fresh chats start in the project
            os.chdir(p["chat_cwd"] if resume else p["folder"])
        except OSError as e:
            self.show(f"I couldn't open that folder: `{e}`")
            return
        self.claude_args = strip_resume(self.claude_args) + (["--resume", p["session"]] if resume else [])
        self.log_items = sessions.transcript_file(p["path"]) if resume else []
        self.new_turn()
        self.busy = False
        self.set_title()
        self.start_engine()
        box = self.query_one("#input", ChatBox)
        if resume:
            last = next((t for who, t in reversed(self.log_items) if who == "quill"), "")
            if len(last) > 700:
                last = last[:700].rsplit(" ", 1)[0] + " …"
            quoted = "\n".join("> " + l for l in last.splitlines()) if last else "> (nothing yet)"
            self.show(f"Picking up **{p['name']}** where we left off.\n\n"
                      f"Last time I said:\n\n{quoted}\n\n*F2 shows the whole chat.*")
            self.query_one("#you", Static).update(
                Text("you (last time): " + sessions.one_line(p["last_you"] or "", 200)))
        else:
            self.query_one("#you", Static).update("")
            if p["next"] and prefill and p["next_from"] == "roadmap":
                self.show(f"Fresh chat in **{p['name']}**. Next on the roadmap:\n\n> {p['next']}\n\n"
                          "I've put it in your message box. Press **Enter** to start on it, "
                          "or change it to anything else.")
                box.load_text(f"Let's work on the next roadmap item: {p['next']}")
            elif p["next"] and prefill:
                where = "Where we left off" if p["next_from"] == "chat" else "My notes say"
                self.show(f"Fresh chat in **{p['name']}**. {where}:\n\n> {p['next']}\n\n"
                          "I've put a starter in your message box. Press **Enter**, or change it.")
                box.load_text(f"Let's pick up {p['name']} where we left off. What's next?")
                box.move_cursor(box.document.end)
            else:
                self.show(f"Fresh chat in **{p['name']}**. What are we working on?")
        box.focus()

    # ---------- every chat (/resume, `quill --resume`) ----------
    PAGE = 8

    def offer_chats(self, search=None, page=0):
        """Every earlier chat, newest first, like Claude Code's --resume list."""
        try:
            found = sessions.chats(search or None)
        except Exception as e:  # noqa: BLE001
            self.show(f"I couldn't read the earlier chats: `{e}`")
            return
        found = [c for c in found if c["session"] != getattr(self, "session_id", None)]
        if not found:
            self.dialog = None
            self.clear_choices()
            self.show(f"No earlier chats mention **{search}**." if search
                      else "I haven't found any earlier chats yet.")
            return
        pages = (len(found) - 1) // self.PAGE + 1
        page = max(0, min(page, pages - 1))
        shown = found[page * self.PAGE:(page + 1) * self.PAGE]
        self.dialog = {"kind": "chats", "chats": shown, "search": search, "page": page}
        here = os.getcwd()
        head = f"**Chats mentioning “{search}”**" if search else "**Pick up an earlier chat**"
        lines = [f"{head} · page {page + 1} of {pages} ({len(found)} chats)", ""]
        for i, c in enumerate(shown, 1):
            tag = " *(this folder)*" if c["folder"] == here else ""
            lines.append(f"{i}. **{sessions.chat_label(c)}**  \n"
                         f"   {c['name']}{tag} · *{sessions.ago(c['when'])}*")
        lines += ["", "*Type a number to open one, or a word to search. Esc closes this.*"]
        self.show("\n".join(lines), top=True)
        buttons = [Button(str(i), name=f"ch-{i - 1}", variant="primary") for i in range(1, len(shown) + 1)]
        if page > 0:
            buttons.append(Button("Newer", name="ch-newer"))
        if page < pages - 1:
            buttons.append(Button("Older", name="ch-older"))
        if search:
            buttons.append(Button("All chats", name="ch-all"))
        self.set_choices(buttons, focus=False)
        self.status("Pick a chat to pick up")

    def chat_choice(self, bid):
        d = self.dialog
        if not d or d["kind"] != "chats":
            return
        if bid in ("ch-newer", "ch-older"):
            self.offer_chats(d["search"], d["page"] + (1 if bid == "ch-older" else -1))
        elif bid == "ch-all":
            self.offer_chats()
        else:
            self.open_chat(d["chats"][int(bid[3:])])

    def open_chat(self, c):
        if self.busy or self.pending:
            self.notify("Wait until I've finished, then pick a chat.", timeout=2)
            return
        self.enter_project(c, resume=True)

    def typed_in_list(self, text):
        """You typed while a list is up: a number picks that row. True = handled."""
        d = self.dialog
        if not text.isdigit():
            return False
        i = int(text) - 1
        if d["kind"] == "chats" and 0 <= i < len(d["chats"]):
            self.open_chat(d["chats"][i])
            return True
        if d["kind"] == "picker" and 0 <= i < len(d["projects"]):
            self.pick(f"pk-{i}")
            return True
        return False

    def continue_here(self):
        """`-c` / `/continue`: the newest earlier chat in this folder, like `claude -c`."""
        here = os.getcwd()
        mine = getattr(self, "session_id", None)
        c = next((c for c in sessions.chats() if c["chat_cwd"] == here and c["session"] != mine), None)
        if not c:
            self.show("There's no earlier chat in this folder to continue. `/resume` lists them all.")
            return
        self.open_chat(c)
