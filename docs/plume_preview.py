"""Terminal preview of the Plume mock-ups next to Quill:  .venv/bin/python docs/plume_preview.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from preview import render
from quill.sprites import ROBOT

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plume_options.py")).read())
items = [("Quill", ["." * 16] * 2 + ROBOT)] + [(f"{k}: {n}", sp) for k, (n, sp) in OPTIONS.items()]
grid = Table.grid(padding=(0, 2))
grid.add_row(*(render(sp) for _, sp in items))
grid.add_row(*(Text(n, style="bold #ffcd75", justify="center") for n, _ in items))
Console().print(Panel(grid, title="Plume — pick a look", border_style="#566c86", style="on #1a1c2c"))
