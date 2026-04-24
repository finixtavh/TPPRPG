import os
import time
import threading
from typing import List, Dict, Optional, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.box import ROUNDED
from rich.rule import Rule
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

from Modules.input_utils import keyboard_listener_scope
from Modules.ItemManager import get_item_manager
from Modules.setup import cWeapon, cEquippableItems, cObject
from Modules.GatheringMasterySystem import cMaterial, cTool  

console = Console()

# Constantes visuales
_TYPE_ICON = {
    "cWeapon":          "⚔",
    "cEquippableItems": "🛡",
    "cObject":          "🧪",
    "cTool":            "⛏",
    "cMaterial":        "🪨"
}

_TYPE_LABEL = {
    "cWeapon":          "Arma",
    "cEquippableItems": "Equipamiento",
    "cObject":          "Objeto",
    "cTool":            "Herramienta",
    "cMaterial":        "Material"
}

_TYPE_COLOR = {
    "cWeapon":          "bold red",
    "cEquippableItems": "bold cyan",
    "cObject":          "bold yellow",
    "cTool":            "bold dark_orange3",
    "cMaterial":        "bold blue"
}

class ItemBrowser:
    def __init__(self, item_manager):
        self.item_manager = item_manager
        self.all_items = []
        self._load_all_items()

    def _load_all_items(self):
        for category, items in self.item_manager.items_data.items():
            is_mat = (category == "TYPE:Materials")
            for item_key, item_data in items.items():
                item_id = item_data.get("MATERIAL_ID") if is_mat else item_data.get("STATIC_ID")
                if item_id is not None:
                    try:
                        obj = self.item_manager.create_item_object(item_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial, material_lookup=is_mat)
                        if obj: self.all_items.append(obj)
                    except Exception: pass
        self.all_items.sort(key=lambda x: getattr(x, "ID", getattr(x, "STATIC_ID", getattr(x, "MATERIAL_ID", 0))))

def _is_discovered(item, player) -> bool:
    if player is None: return True
    item_id = getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", None)))
    return item_id in getattr(player, "discovered_items", set())

def _obscure(text: str) -> str:
    return "".join("█" if not c.isspace() else c for c in text)

def open_item_browser(player, item_manager):
    browser = ItemBrowser(item_manager)
    state = {
        "idx": 0, "scroll": 0, "search_query": "", "input_mode": "normal",
        "message": "↑↓: Navegar | [F]: Favorito | [S]: Buscar | [ESC]: Salir",
        "msg_style": "dim", "exit": False
    }
    MAX_VISIBLE = 15

    def _get_filtered_items():
        q = state["search_query"].lower()
        items = browser.all_items
        if q: items = [item for item in items if q in getattr(item, "Name", getattr(item, "name", "")).lower()]
        favs = [item for item in items if getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", -1))) in getattr(player, "favorite_items", [])]
        others = [item for item in items if getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", -1))) not in getattr(player, "favorite_items", [])]
        return favs + others

    def _render_list(items, selected_idx, scroll_offset):
        t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t.add_column("Fav", width=3); t.add_column("Icon", width=2); t.add_column("Nombre", ratio=1)
        if not items:
            t.add_row("", "", "[dim]No se encontraron ítems[/]")
            return Panel(t, title="[bold yellow] LISTA DE ITEMS [/]", border_style="yellow")
        visible = items[scroll_offset : scroll_offset + MAX_VISIBLE]
        for i, item in enumerate(visible):
            abs_idx = scroll_offset + i
            is_selected = abs_idx == selected_idx
            item_id = getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", -1)))
            is_fav = item_id in getattr(player, "favorite_items", [])
            discovered = _is_discovered(item, player)
            name = getattr(item, "Name", getattr(item, "name", "???"))
            if not discovered: name = _obscure(name)
            itype = type(item).__name__
            icon = _TYPE_ICON.get(itype, "?")
            tcolor = _TYPE_COLOR.get(itype, "white").replace("bold ", "")
            fav_icon = "[yellow]★[/]" if is_fav else "[dim]☆[/]"
            name_text = Text(name)
            if is_selected:
                name_text.stylize("bold reverse")
                row_style = f"bold {tcolor}"
            else: row_style = tcolor
            t.add_row(fav_icon, icon, name_text, style=row_style)
        return Panel(t, title="[bold yellow] ÍTEMS [/]", border_style="yellow")

    def _render_detail(item):
        if not item: return Panel(Text("\n\nSelecciona un ítem", justify="center", style="dim"), title="[bold] DETALLE [/]")
        discovered = _is_discovered(item, player)
        itype = type(item).__name__
        tcolor = _TYPE_COLOR.get(itype, "white")
        name = getattr(item, "Name", getattr(item, "name", "???"))
        desc = getattr(item, "Description", getattr(item, "description", getattr(item, "Desc", "Sin descripción.")))
        if not discovered: name = _obscure(name); desc = _obscure(desc)
        lines = [Text(f" {_TYPE_ICON.get(itype, '?')}  {name}", style=f"bold {tcolor}"), Rule(style="dim"), Text(f" Tipo: {_TYPE_LABEL.get(itype, itype)}", style="dim"), Text(""), Text(f" {desc}", style="italic"), Text("")]
        if discovered:
            if itype == "cWeapon": lines.append(Text(f" Daño: {getattr(item, 'DMG', [0]*5)}", style="bold red"))
            elif itype == "cEquippableItems":
                df = getattr(item, "Defense", [0]*5)
                lines.append(Text(f" Defensa: {df}", style="bold cyan"))
                if getattr(item, "HealthBoost", 0): lines.append(Text(f" HP+: {item.HealthBoost}", style="bold green"))
            lines.append(Text(f"\n Valor: {getattr(item, 'Gold_Cost', 0)}g", style="yellow"))
        else: lines.append(Text(" [?] Descubre este ítem para ver sus estadísticas", style="bold red"))
        return Panel(Group(*lines), title="[bold cyan] INFORMACIÓN [/]", border_style="cyan")

    def _on_press(key):
        items = _get_filtered_items()
        if state["input_mode"] == "search":
            if key == "enter" or key == "esc": state["input_mode"] = "normal"
            elif key == "backspace": state["search_query"] = state["search_query"][:-1]; state["idx"] = 0; state["scroll"] = 0
            elif len(key) == 1: state["search_query"] += key; state["idx"] = 0; state["scroll"] = 0
            return
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
            if state["idx"] < state["scroll"]: state["scroll"] = state["idx"]
        elif key == "down":
            state["idx"] = min(len(items) - 1, state["idx"] + 1)
            if state["idx"] >= state["scroll"] + MAX_VISIBLE: state["scroll"] = state["idx"] - MAX_VISIBLE + 1
        elif key == "esc": state["exit"] = True
        elif key == "f" and items:
            item = items[state["idx"]]
            item_id = getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", -1)))
            if not hasattr(player, "favorite_items"): player.favorite_items = []
            if item_id in player.favorite_items: player.favorite_items.remove(item_id)
            else: player.favorite_items.append(item_id)
        elif key == "s": state["input_mode"] = "search"; state["search_query"] = ""

    with console.screen():
        with keyboard_listener_scope():
            kb_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_press, "sequential": False, "until": None}, daemon=True)
            kb_thread.start()
            try:
                with Live(console=console, refresh_per_second=20, transient=True) as live:
                    while not state["exit"]:
                        items = _get_filtered_items()
                        if state["idx"] >= len(items) and len(items) > 0: state["idx"] = len(items) - 1
                        selected_item = items[state["idx"]] if items else None
                        search_info = f" [bold yellow]BUSCANDO:[/] {state['search_query']}_" if state["input_mode"] == "search" else ""
                        footer = Panel(Text(state["message"], style=state["msg_style"]).append(search_info, style="white"), border_style="dim")
                        grid = Table.grid(expand=True); grid.add_column(ratio=2); grid.add_column(ratio=3); grid.add_row(_render_list(items, state["idx"], state["scroll"]), _render_detail(selected_item))
                        live.update(Panel(Group(grid, footer), title="[bold white]📖 ENCICLOPEDIA DE ÍTEMS 📖[/]", border_style="bright_black", padding=(0,1)))
                        time.sleep(0.05)
            finally:
                stop_listening()
                if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
        console.clear()
