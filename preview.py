"""Show the four Quill character options in the terminal.

Run:  .venv/bin/python preview.py        (all four, side by side)
      .venv/bin/python preview.py B      (one option in a mock chat layout)
"""
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from quill.sprites import OPTIONS, PALETTE, check

BG = "#1a1c2c"


def render(sprite, scale=2):
    """Half-block render: each text cell = one pixel wide, two pixels tall."""
    check(sprite)
    rows = [r for r in sprite for _ in range(scale)]
    rows = ["".join(ch * scale for ch in r) for r in rows]
    if len(rows) % 2:
        rows.append("." * len(rows[0]))
    out = Text()
    for top, bot in zip(rows[0::2], rows[1::2]):
        for t, b in zip(top, bot):
            tc = PALETTE.get(t, BG)
            bc = PALETTE.get(b, BG)
            out.append("▀", style=f"{tc} on {bc}")
        out.append("\n")
    return out


def main():
    con = Console()
    pick = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if pick in OPTIONS:
        name, sprite = OPTIONS[pick]
        bubble = Panel(
            "Hi! I'm Quill. What are we working on today?",
            border_style="#41a6f6", style=f"#f4f4f4 on #333c57", width=44,
        )
        grid = Table.grid(padding=(0, 2))
        grid.add_row(render(sprite), bubble)
        con.print(Panel(grid, title=f"Quill — option {pick}: {name}",
                        border_style="#566c86", style=f"on {BG}"))
        con.print(Panel("[#94b0c2]type here…[/]", border_style="#ffcd75",
                        style=f"on {BG}", title="you"))
        return
    grid = Table.grid(padding=(0, 3))
    grid.add_row(*(render(sp) for _, sp in OPTIONS.values()))
    grid.add_row(*(Text(f"{k}: {n}", style="bold #ffcd75", justify="center")
                   for k, (n, _) in OPTIONS.items()))
    con.print(Panel(grid, title="Quill — pick a look", border_style="#566c86",
                    style=f"on {BG}"))


if __name__ == "__main__":
    main()
