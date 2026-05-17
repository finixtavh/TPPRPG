from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align
from rich.text import Text

# Paleta de colores Heraldo
COLOR_PRIMARY = "gold3"
COLOR_SECONDARY = "tan"
COLOR_DIM = "grey50"
COLOR_SUCCESS = "green3"
COLOR_DANGER = "red3"

# Iconos Heraldo
ICONS = {
    "hp": "❣ ",
    "mp": "🝓 ",
    "atk": "⚔ ",
    "def": "🛡 ",
    "agi": "𐓷 ",
    "eva": "💨 ",
    "cnt": "↺ ",
    "guild": "🏰 ",
    "weather": "🌤 ",
    "buff": "✧ ",
    "debuff": "☠ ",
    "item": "◈ ",
    "arrow": "► ",
    "sep": "·"
}

def herald_bar(current, maximum, width=15, color=COLOR_PRIMARY):
    """Crea una barra de progreso estilo Heraldo (◆◇)."""
    if maximum <= 0: return " " * width
    pct = max(0, min(1, current / maximum))
    filled = int(pct * width)
    bar = f"[{color}]" + "◆" * filled + f"[/][dim]" + "◇" * (width - filled) + "[/]"
    return bar

def herald_panel(content, title=None, border_style=COLOR_PRIMARY, padding=(1, 2), expand=False):
    """Crea un panel con bordes horizontales estilo Heraldo."""
    return Panel(
        content,
        title=f"[bold {border_style}]{title.upper()}[/]" if title else None,
        border_style=border_style,
        box=box.HORIZONTALS,
        padding=padding,
        expand=expand
    )

def herald_table(expand=True, padding=(0, 1)):
    """Crea una tabla grid base para layouts estilo Heraldo."""
    return Table.grid(expand=expand, padding=padding)
