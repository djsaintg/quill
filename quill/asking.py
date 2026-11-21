"""Claude asking you things: permission to use a tool, or a multiple-choice question."""
import os

from textual.widgets import Button

from . import perms
from .engine import describe_tool
from .texts import permission_text


class AskMixin:
    # ---------- questions & permissions ----------
    async def ask(self, request_id, req):
        tool, inp = req.get("tool_name", ""), req.get("input") or {}
        if perms.allowed(tool, inp, os.getcwd(), self.granted):
            # you already said "don't ask again" for this level in this chat
            self.tool_active = True
            self.status(describe_tool(tool, inp) + "  (allowed for this chat)")
            await self.engine.answer(request_id, {"behavior": "allow", "updatedInput": inp})
            return
        if self.pending or (self.dialog and self.dialog["kind"] == "sudo"):
            # Claude can ask about several things at once (e.g. two reads in parallel):
            # show them one at a time, never drop one
            self.ask_queue.append((request_id, req))
            self.status(f"Waiting for you ({len(self.ask_queue)} more after this)")
            return
        self.pending = {"id": request_id, **req}
        if tool == "AskUserQuestion":
            self.q_index, self.q_answers = 0, {}
        self.present()

    def present(self):
        """Show the request we're waiting on you for (again, e.g. after a sudo prompt)."""
        req = self.pending
        tool, inp = req.get("tool_name", ""), req.get("input") or {}
        self.pop_up(f"{self.char_name} needs you", "Has a question for you" if tool == "AskUserQuestion"
                    else describe_tool(tool, inp) + ": OK?")
        if tool == "AskUserQuestion":
            self.show_question()
            return
        lvl = perms.level(tool, inp, os.getcwd())
        text = permission_text(tool, inp, req.get("display_name"))
        buttons = [Button("Yes", name="perm-yes", variant="success")]
        if tool not in perms.NEVER_AUTO:
            text += (f"\n\n*\"Don't ask again\" covers {perms.NAMES[lvl]}"
                     + (" and anything smaller" if lvl > perms.READ else "")
                     + ", until this chat ends.*")
            buttons.append(Button("Yes, and don't ask again", name="perm-always", variant="primary"))
        buttons.append(Button("No", name="perm-no", variant="error"))
        if self.ask_queue:
            text += f"\n\n*({len(self.ask_queue)} more question{'s' if len(self.ask_queue) > 1 else ''} after this one)*"
        self.show(text)
        self.set_choices(buttons)
        self.status("Waiting for you: Yes / No, or type what to do instead")

    def show_question(self):
        qs = self.pending["input"].get("questions", [])
        q = qs[self.q_index]
        self.q_picked = set()
        opts = q.get("options", [])
        lines = [f"**{q.get('question', '')}**", ""]
        for o in opts:
            lines.append(f"- **{o.get('label')}**: {o.get('description', '')}")
        lines += ["", "*Pick one, or type your own answer below.*"]
        self.show("\n".join(lines))
        buttons = [Button(o.get("label", "?"), name=f"opt-{i}") for i, o in enumerate(opts)]
        if q.get("multiSelect"):
            buttons.append(Button("Done", name="opt-done", variant="success"))
        self.set_choices(buttons)
        self.status(f"Question {self.q_index + 1} of {len(qs)}")

    def set_choices(self, buttons, focus=True):
        box = self.query_one("#choices")
        box.remove_children()
        box.mount_all(buttons)
        box.add_class("show")
        if buttons and focus:
            self.call_after_refresh(buttons[0].focus)

    def clear_choices(self):
        box = self.query_one("#choices")
        box.remove_children()
        box.remove_class("show")
        self.query_one("#input").focus()

    async def finish_pending(self, response):
        req = self.pending
        self.pending = None
        self.clear_choices()
        self.show_reply()
        tool = req.get("tool_name", "")
        if response.get("behavior") == "allow" and tool not in perms.NEVER_AUTO:
            self.tool_active = True
            self.status(describe_tool(tool, req.get("input")))  # what's running now
        else:
            self.tool_active = False
            self.status("Thinking…")
        await self.engine.answer(req["id"], response)
        if self.ask_queue:
            rid, nxt = self.ask_queue.pop(0)
            await self.ask(rid, nxt)  # may be covered by "don't ask again" now

    async def answer_question(self, answer):
        q = self.pending["input"]["questions"][self.q_index]
        self.q_answers[q.get("question", "")] = answer
        self.log_items.append(("you", f"{q.get('question')}: **{answer}**"))
        self.q_index += 1
        if self.q_index < len(self.pending["input"]["questions"]):
            self.show_question()
        else:
            inp = dict(self.pending["input"], answers=self.q_answers)
            await self.finish_pending({"behavior": "allow", "updatedInput": inp})

    async def pending_button(self, bid, button):
        """A button for the question Claude is waiting on: Yes / No / an option."""
        req = self.pending
        if bid == "perm-yes":
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {})})
        elif bid == "perm-always":
            # remembered by Quill for this chat only; nothing is written to Claude Code's settings
            self.granted = max(self.granted, perms.level(req.get("tool_name", ""), req.get("input"),
                                                         os.getcwd()))
            await self.finish_pending({"behavior": "allow", "updatedInput": req.get("input", {})})
        elif bid == "perm-no":
            await self.finish_pending({"behavior": "deny", "message": "The user said no."})
        elif bid.startswith("opt-"):
            q = req["input"]["questions"][self.q_index]
            if bid == "opt-done":
                await self.answer_question(", ".join(sorted(self.q_picked)) or "(none)")
                return
            label = q["options"][int(bid[4:])].get("label", "")
            if q.get("multiSelect"):
                self.q_picked ^= {label}
                button.set_class(label in self.q_picked, "picked")
            else:
                await self.answer_question(label)
