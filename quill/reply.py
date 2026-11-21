"""The reply in the speech bubble, built up step by step while Claude works."""
from rich.text import Text
from textual.css.query import NoMatches
from textual.widget import MountError
from textual.widgets import Markdown, Static

from .engine import describe_result, describe_tool, past_tense

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ReplyMixin:
    # ---------- the reply, step by step ----------
    def new_turn(self):
        self.turn_text, self.parts = "", []
        self.jump = True  # a new answer starts at the bottom

    def add_text(self, text, new_block=False):
        """Claude's words. A new text block after a step starts a new piece."""
        if not self.parts or self.parts[-1]["kind"] != "text":
            self.parts.append({"kind": "text", "text": ""})
        elif new_block and self.parts[-1]["text"] and not self.parts[-1]["text"].endswith("\n\n"):
            self.parts[-1]["text"] += "\n\n"
        self.parts[-1]["text"] += text
        if new_block and self.turn_text and not self.turn_text.endswith("\n\n"):
            self.turn_text += "\n\n"
        self.turn_text += text

    def step(self, tool_id):
        return next((p for p in self.parts if p["kind"] == "step" and p["id"] == tool_id), None)

    def add_step(self, block):
        if self.step(block.get("id")):
            return
        self.parts.append({"kind": "step", "id": block.get("id"), "name": block.get("name"),
                           "input": block.get("input") or {}, "state": "run", "note": "", "helper": ""})
        self.reveal()

    def end_step(self, ev, block):
        p = self.step(block.get("tool_use_id"))
        if not p:
            return
        err = bool(block.get("is_error"))
        p["note"] = describe_result(p["name"], p["input"], ev.get("tool_use_result"),
                                    block.get("content"), err)
        p["state"], p["helper"] = ("err" if err else "ok"), ""
        self.reveal()

    def reveal(self):
        """Show the reply so far, unless a question for you is on screen."""
        if self.pending or self.dialog:
            self.dirty = True  # it'll show once you've answered
        else:
            self.show_reply()

    def step_line(self, p):
        label = describe_tool(p["name"], p["input"])
        if p["state"] == "run":
            line = f"{SPINNER[self.tick % len(SPINNER)]} {label}…"
            if p["helper"]:
                line += f"  ·  {p['helper']}"
        else:
            mark = {"ok": "✓", "err": "✗", "stopped": "■"}[p["state"]]
            line = f"{mark} {past_tense(label)}" + (f"  ·  {p['note']}" if p["note"] else "")
        return Text(line, overflow="ellipsis", no_wrap=True)

    async def sync_turn(self):
        """Make the widgets in #turn match self.parts (one per text piece or step)."""
        turn = self.query_one("#turn")
        have = list(turn.children)
        kinds = [("text" if isinstance(w, Markdown) else "step") for w in have]
        if len(have) > len(self.parts) or kinds != [p["kind"] for p in self.parts[:len(have)]]:
            await turn.remove_children()
            have = []
        for i, p in enumerate(self.parts):
            if i >= len(have):
                w = (Markdown("", classes="after" if i else "") if p["kind"] == "text"
                     else Static("", classes="step"))
                w.shown = None
                await turn.mount(w)
                have.append(w)
            w = have[i]
            if p["kind"] == "text":
                if w.shown != p["text"]:
                    w.shown = p["text"]
                    await w.update(p["text"])
            else:
                w.part = p
                w.set_class(p["state"] == "run", "run")
                w.set_class(p["state"] == "err", "err")
                w.update(self.step_line(p))

    def spin(self):
        """Turn the spinner on running steps without redrawing the whole reply."""
        if self.override is not None or not self.busy:
            return
        try:
            for w in self.query_one("#turn").children:
                if getattr(w, "part", None) and w.part["state"] == "run":
                    w.update(self.step_line(w.part))
        except NoMatches:
            pass

    async def flush(self):
        if self.dirty and not self.flushing:
            self.dirty, self.flushing = False, True
            try:
                say, turn = self.query_one("#say", Markdown), self.query_one("#turn")
                bubble = self.query_one("#bubble")
                # Follow the reply only if you're already at the bottom. Scrolled up to read?
                # It keeps updating quietly and leaves you where you are. Something new on
                # screen (a question, a fresh answer) still brings you down to it.
                was_override = getattr(self, "flushed_override", False)
                follow = (bubble.max_scroll_y - bubble.scroll_y <= 1 or getattr(self, "jump", True)
                          or was_override != (self.override is not None))
                self.jump, self.flushed_override = False, self.override is not None
                steps = self.override is None and bool(self.parts)
                say.display, turn.display = not steps, steps
                if steps:
                    await self.sync_turn()
                else:
                    await say.update(self.override if self.override is not None
                                     else (self.turn_text or "…"))
                if self.override is not None and self.show_top:
                    if follow:
                        bubble.scroll_home(animate=False)
                elif follow:
                    bubble.scroll_end(animate=False)
            except (NoMatches, MountError):
                pass  # Quill is closing
            finally:
                self.flushing = False
