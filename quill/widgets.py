"""Quill's pieces of screen: the message box, the history view and the first-start chooser."""
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Markdown, Static, TextArea

from . import themes
from .sprites import PALETTE, sprite

BG = "#1a1c2c"
NEW_LINE_KEYS = ("shift+enter", "alt+enter", "ctrl+j")


def render_sprite(rows_in, scale=2, pal=None, bg=BG):
    """Half-block pixels: one text cell = 1 pixel wide, 2 pixels tall."""
    pal = pal or PALETTE
    rows = [r for r in rows_in for _ in range(scale)]
    rows = ["".join(ch * scale for ch in r) for r in rows]
    out = Text(no_wrap=True)
    for top, bot in zip(rows[0::2], rows[1::2]):
        for t, b in zip(top, bot):
            out.append("▀", style=f"{pal.get(t, bg)} on {pal.get(b, bg)}")
        out.append("\n")
    return out


class ChatBox(TextArea):
    """Your input: wraps and grows as you type.

    Enter sends. A new line: end the line with \\ then Enter (like Claude Code),
    or Ctrl+J, or Shift/Alt+Enter in terminals that send those differently from Enter.
    """

    class Submitted(Message):
        def __init__(self, box, text):
            super().__init__()
            self.box, self.text = box, text

    async def _on_key(self, event):
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            row, col = self.cursor_location
            if col and self.document.get_line(row)[col - 1] == "\\":
                self.delete((row, col - 1), (row, col))  # "\" + Enter = new line
                self.insert("\n")
                return
            self.post_message(self.Submitted(self, self.text))
            return
        if event.key in NEW_LINE_KEYS:
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        await super()._on_key(event)


class History(ModalScreen):
    BINDINGS = [Binding("escape,f2", "dismiss", "Close")]

    def __init__(self, log, name="quill"):
        super().__init__()
        self.log_items, self.char = log, name

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="hist"):
            yield Static("CHAT SO FAR  (Esc to close)", id="hist-title")
            if not self.log_items:
                yield Static("Nothing yet.")
            for who, text in self.log_items:
                yield Static("you" if who == "you" else self.char,
                             classes=f"who {who}")
                yield Markdown(text, classes=f"msg {who}")

    def on_mount(self):
        self.query_one("#hist").scroll_end(animate=False)


class Chooser(Screen):
    """First start: pick Quill (left, classic colours) or Plume (right, aurora colours)."""

    BINDINGS = [Binding("left", "focus_side('quill')", show=False),
                Binding("right", "focus_side('plume')", show=False)]
    SIDES = (("quill", "classic"), ("plume", "aurora"))

    def __init__(self, prefer=None):
        super().__init__()
        self.prefer = prefer or "quill"

    def compose(self) -> ComposeResult:
        yield Static("Who would you like on your desk?", id="ch-title")
        with Horizontal(id="ch-halves"):
            for who, theme in self.SIDES:
                with Vertical(classes="half", id=f"half-{who}"):
                    yield Static("", classes="ch-sprite", id=f"spr-{who}")
                    yield Button(who.capitalize(), id=f"pick-{who}")
        yield Static("Click one, or use ← → and Enter. Switch any time with /character.", id="ch-foot")

    def on_mount(self):
        for who, theme in self.SIDES:
            t = themes.THEMES[theme]
            half = self.query_one(f"#half-{who}")
            half.styles.background = t["bg"]
            half.styles.border = ("round", t["accent"])
            half.border_title = "classic colours" if theme == "classic" else "aurora colours"
            half.styles.border_title_color = t["accent"]
            b = self.query_one(f"#pick-{who}", Button)
            b.styles.background = t["primary"]
            b.styles.color = "#ffffff"
            b.styles.border_top = ("tall", t["accent"])
            b.styles.border_bottom = ("tall", t["primary"])
        self.tick = 0
        self.animate()
        self.set_interval(0.25, self.animate)
        self.query_one(f"#pick-{self.prefer}").focus()

    def animate(self):
        """Both float gently (out of step with each other) and blink now and then."""
        self.tick += 1
        scale = 2 if self.app.size.height >= 34 else 1
        for i, (who, theme) in enumerate(self.SIDES):
            blink = (self.tick + 9 * i) % 23 == 0
            art = sprite(who, "blink" if blink else "idle", "idle")
            if who == "quill":
                art = ["." * 16] * 2 + art  # same height as Plume
            spr = self.query_one(f"#spr-{who}", Static)
            spr.update(render_sprite(art, scale, themes.palette(theme), themes.THEMES[theme]["bg"]))
            spr.styles.margin = (1 if (self.tick // 3 + i) % 2 else 0, 0, 0, 0)

    def action_focus_side(self, who):
        self.query_one(f"#pick-{who}").focus()

    @on(Button.Pressed)
    def picked(self, event):
        self.dismiss((event.button.id or "pick-quill")[5:])
