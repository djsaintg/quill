"""Quill's face: which expression to show, a few times a second."""
import time

from textual.css.query import NoMatches
from textual.widgets import Static

from .sprites import sprite
from .widgets import render_sprite


class FaceMixin:
    def feel(self, mood, secs=1.5):
        """An expression that lasts a little while once I'm not busy (happy, oops, sad)."""
        self.mood, self.mood_until = mood, time.monotonic() + secs

    def flash(self, face, secs=1.2):
        """A quick reaction that shows even in the middle of work (a step just failed)."""
        self.flash_face, self.flash_until = face, time.monotonic() + secs

    # ---------- animation ----------
    def animate(self):
        self.tick += 1
        self.spin()
        now = time.monotonic()
        if self.pending or self.dialog:
            face, bulb = "ask", ("ask" if self.tick % 4 < 2 else "off")
        elif self.flash_face and now < self.flash_until:
            face, bulb = self.flash_face, self.flash_face
        elif now - self.last_delta < 0.4:
            face, bulb = ("talk1" if self.tick % 2 else "talk2"), "think"
        elif self.busy and self.tool_active:
            face, bulb = ("workL" if (self.tick // 4) % 2 else "workR"), "work"
        elif self.busy:
            face, bulb = f"load{self.tick % 4}{(self.tick // 4) % 3 + 1}", "think"
        elif self.mood and now < self.mood_until:
            face, bulb = self.mood, {"happy": "happy", "oops": "oops"}.get(self.mood, "ask")
        else:
            face, bulb = ("blink" if self.tick % 28 == 0 else "idle"), "idle"
        if (face, bulb) != self.last_frame:
            self.last_frame = (face, bulb)
            try:
                self.query_one("#quill", Static).update(
                    render_sprite(sprite(self.who, face, bulb), self.scale, self.pal, self.bgc))
            except NoMatches:
                pass  # closing
