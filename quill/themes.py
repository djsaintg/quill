"""Colour schemes. Each has screen colours (Textual theme variables) and sprite colours.

classic: the Sweetie 16 palette (Quill's default)
aurora:  Tokyo Night style, every blue turned purple (Plume's default)
"""
from textual.theme import Theme

from .sprites import PALETTE

THEMES = {
    "classic": {
        "bg": "#1a1c2c", "panel": "#333c57", "ink": "#f4f4f4", "accent": "#41a6f6",
        "title": "#ffcd75", "muted": "#94b0c2", "hint": "#566c86", "input": "#ffcd75",
        "sudo": "#5d275d", "picked": "#38b764",
        "primary": "#3b5dc9", "success": "#38b764", "warning": "#ef7d57", "error": "#b13e53",
        "sprite": {},  # the plain Sweetie 16 palette
    },
    "aurora": {
        "bg": "#1a1b26", "panel": "#2f2a47", "ink": "#c0caf5", "accent": "#bb9af7",
        "title": "#e0af68", "muted": "#a9b1d6", "hint": "#565f89", "input": "#bb9af7",
        "sudo": "#7a2e5c", "picked": "#9ece6a",
        "primary": "#9d7cd8", "success": "#9ece6a", "warning": "#ff9e64", "error": "#f7768e",
        "sprite": {
            "k": "#15161e",  # outline
            "s": "#a9a1d6",  # frame: lavender grey
            "d": "#3b3561",  # body
            "m": "#565f89",
            "t": "#3d2c6e",  # screen: deep purple
            "a": "#d4bfff",  # eyes: lavender glow
            "r": "#f7768e",  # cheeks, smile
            "y": "#e0af68", "o": "#ff9e64", "l": "#9ece6a", "g": "#73daca",
            "w": "#e6e1ff", "p": "#9d7cd8",
            "b": "#9d7cd8", "c": "#bb9af7", "n": "#7a5cb8",  # the blues, now purples
        },
    },
}
NAMES = list(THEMES)


def palette(name):
    return {**PALETTE, **THEMES.get(name, THEMES["classic"])["sprite"]}


def textual_theme(name):
    t = THEMES[name]
    return Theme(
        name=f"quill-{name}", primary=t["primary"], secondary=t["accent"], accent=t["accent"],
        foreground=t["ink"], background=t["bg"], surface=t["bg"], panel=t["panel"],
        success=t["success"], warning=t["warning"], error=t["error"], dark=True,
        variables={f"q-{k}": v for k, v in t.items() if isinstance(v, str)},
    )
