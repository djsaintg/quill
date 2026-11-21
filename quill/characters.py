"""Who's at the desk (Quill or Plume), their colours, and what they call you."""
import asyncio

from textual.widgets import Button

from . import sudo, themes
from .engine import clean_env, find_claude, strip_resume
from .widgets import ChatBox

# Who's at the desk. Only the voice changes: the work, care and honesty are the same.
PERSONAS = {
    "quill": (
        "Quill", "he/him",
        "a cheerful little desk robot with an antenna and a lightbulb that lights up when he has "
        "an idea. Upbeat, quick and practical, a tinkerer who likes getting things working and "
        "says so plainly. Short sentences, a bit of friendly enthusiasm."),
    "plume": (
        "Plume", "she/her",
        "a calm desk robot with a quill feather instead of an antenna and purple aurora colours. "
        "Thoughtful and warm, a writer at heart: she notices details, explains the why, and "
        "words things gently and clearly. Unhurried, never flowery."),
}


def persona_note(who):
    name, pronouns, about = PERSONAS[who]
    other = next(n for k, (n, _, _) in PERSONAS.items() if k != who)
    return (f"Character: in this window you are {name} ({pronouns}), {about} Speak as {name} "
            f"in the first person, and if anyone refers to you, it's as {name} ({pronouns}). "
            f"You are not {other}; {other} is the other character the user can switch to with "
            "/character. The app itself is still called Quill. Keep the personality to tone and "
            "word choice: it never changes how carefully you work, what you check, or how plainly "
            "you report results.")


class CharacterMixin:
    # ---------- character & colours ----------
    @property
    def char_name(self):
        return self.who.capitalize()

    def apply_look(self, startup=False):
        default = "aurora" if self.who == "plume" else "classic"
        name = sudo.load_config().get("themes", {}).get(self.who, default)
        self.theme_name = name if name in themes.NAMES else default
        self.pal = themes.palette(self.theme_name)
        self.bgc = themes.THEMES[self.theme_name]["bg"]
        self.theme = f"quill-{self.theme_name}"
        self.last_frame = None
        if not startup:
            self.set_title()
            self.query_one("#input", ChatBox).placeholder = f"Talk to {self.char_name}…"

    def switch_to(self, who, greet=True):
        self.who = who
        sudo.set_config("character", who)
        self.apply_look()
        if greet:
            self.feel("happy", 1.5)
            self.show(f"Hi! I'm **{self.char_name}** now. "
                      f"`/character` switches back, `/theme` changes my colours.")

    def chose(self, who):
        self.switch_to(who or "quill", greet=False)
        self.ask_name(first=True)

    # ---------- your name ----------
    def ask_name(self, first=False):
        """Ask what to call you, suggesting the name Claude already knows (if any)."""
        self.dialog = {"kind": "name", "guess": None, "first": first}
        self.show(f"Nice to meet you! I'm **{self.char_name}**.\n\n"
                  "What should I call you? Type your name below and press **Enter**.")
        self.set_choices([Button("Skip", name="nm-skip")], focus=False)
        self.query_one("#input", ChatBox).focus()
        self.run_worker(self.guess_name(), group="name")

    async def guess_name(self):
        """One quick, unsaved question to Claude: does it already know the user's name?"""
        try:
            proc = await asyncio.create_subprocess_exec(
                find_claude(), "-p",
                "If your instructions or memory tell you the user's first name, reply with just "
                "that name. Otherwise reply with exactly: UNKNOWN",
                "--no-session-persistence", "--model", "haiku", "--tools", "",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                stdin=asyncio.subprocess.DEVNULL, env=clean_env())
            out, _ = await asyncio.wait_for(proc.communicate(), 60)
        except Exception:  # noqa: BLE001 - no guess is fine
            return
        lines = [l.strip() for l in out.decode(errors="replace").splitlines() if l.strip()]
        guess = lines[-1].strip(" .!\"'*") if lines else ""
        d = self.dialog
        if (not guess or guess.upper() == "UNKNOWN" or len(guess) > 30 or " " in guess.strip()
                or not d or d["kind"] != "name"):
            return
        d["guess"] = guess
        self.show(f"Nice to meet you! I'm **{self.char_name}**.\n\n"
                  f"My notes say you're **{guess}**. Is that right? "
                  "Or type what you'd like me to call you.")
        self.set_choices([Button(f"Yes, I'm {guess}", name="nm-yes", variant="success"),
                          Button("Skip", name="nm-skip")], focus=False)

    def name_done(self, name):
        d, self.dialog = self.dialog, None
        self.clear_choices()
        name = " ".join((name or "").split())[:40]
        if name:
            self.user_name = name
            sudo.set_config("user_name", name)
        if d and d.get("first") and strip_resume(self.claude_args) == list(self.claude_args):
            self.offer_picker(first=True)
        else:
            self.show(f"Hi {name}! Nice to meet you." if name else "No problem.")
