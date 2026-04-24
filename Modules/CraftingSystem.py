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

from Modules.Loader import Read
from Modules.input_utils import keyboard_listener_scope
from Modules.ItemManager import get_item_manager
from Modules.setup import cWeapon, cEquippableItems, cObject
from Modules.GatheringMasterySystem import cMaterial, cTool  
from Modules.ModLoader import get_mod_api

console = Console()

class CraftingSystem:
    def __init__(self, player, inventory):
        self.player = player
        self.inventory = inventory
        self.recipes = []
        self._load_recipes()

    def _load_recipes(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        data = Read(config_path, "CRAFTING_RECIPES")
        if data:
            for r_id, r_data in data.items():
                r_data["id"] = r_id
                self.recipes.append(r_data)
        try:
            
            mod_api = get_mod_api()
            if hasattr(mod_api, "recipe_injections"):
                for r_id, r_data in mod_api.recipe_injections.items():
                    r_data["id"] = r_id; self.recipes.append(r_data)
        except ImportError: pass

def open_crafting_menu(player, inventory):
    system = CraftingSystem(player, inventory)
    item_manager = get_item_manager()
    state = {
        "idx": 0, "scroll": 0, "search_query": "", "input_mode": "normal", "qty_buffer": "",
        "message": "↑↓: Navegar | [S]: Buscar | [F]: Favorito | [ENTER]: Craftear | [Q]: Cantidad | [ESC]: Salir",
        "msg_style": "dim", "exit": False
    }
    MAX_VISIBLE = 12

    def _get_filtered_recipes():
        q = state["search_query"].lower()
        recipes = system.recipes
        if q: recipes = [r for r in recipes if q in r.get("result_name", "").lower()]
        favs = [r for r in recipes if r["id"] in getattr(player, "favorite_recipes", [])]
        others = [r for r in recipes if r["id"] not in getattr(player, "favorite_recipes", [])]
        return favs + others

    def _has_materials(recipe, multiplier=1):
        for mat_id, req_qty in recipe["materials"].items():
            if inventory.get_item_quantity(mat_id) < (req_qty * multiplier): return False
        return True

    def _render_recipe_list(recipes, selected_idx, scroll_offset):
        t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t.add_column("Fav", width=3); t.add_column("Nombre", ratio=1); t.add_column("Status", width=10)
        if not recipes:
            t.add_row("", "[dim]No hay recetas disponibles[/]", "")
            return Panel(t, title="[bold white] RECETAS [/]", border_style="grey50")
        visible = recipes[scroll_offset : scroll_offset + MAX_VISIBLE]
        for i, recipe in enumerate(visible):
            abs_idx = scroll_offset + i; is_selected = abs_idx == selected_idx; is_fav = recipe["id"] in getattr(player, "favorite_recipes", [])
            can_craft = _has_materials(recipe); fav_icon = "[yellow]★[/]" if is_fav else "[dim]☆[/]"
            name = recipe.get("result_name", "Desconocido")
            status = "[bold green]LISTO[/]" if can_craft else "[bold red]FALTAN[/]"
            name_text = Text(name)
            if is_selected: name_text.stylize("bold reverse"); row_style = "bold white"
            else: row_style = "white" if can_craft else "grey50"
            t.add_row(fav_icon, name_text, status, style=row_style)
        return Panel(t, title="[bold white] RECETAS [/]", border_style="grey50")

    def _render_recipe_detail(recipe):
        if not recipe: return Panel(Text("\n\nSelecciona una receta", justify="center", style="dim"), title="[bold] DETALLE [/]")
        lines = [Text(f" {recipe.get('result_name')}", style="bold cyan"), Rule(style="dim"), Text(" Materiales requeridos:", style="bold white")]
        for mat_id, req_qty in recipe["materials"].items():
            owned = inventory.get_item_quantity(mat_id); mat_name = item_manager.get_item_name(mat_id)
            color = "green" if owned >= req_qty else ("yellow" if owned > 0 else "red")
            lines.append(Text(f" • {mat_name}: {owned}/{req_qty}", style=color))
        lines.append(Text("")); lines.append(Text(f" Resultado: {recipe.get('result_qty', 1)}x {recipe.get('result_name')}", style="dim italic"))
        return Panel(Group(*lines), title="[bold cyan] INFORMACIÓN DE CRAFTEO [/]", border_style="cyan")

    def _craft(recipe, qty=1):
        if _has_materials(recipe, qty):
            for mat_id, req_qty in recipe["materials"].items(): inventory.remove_item(mat_id, req_qty * qty)
            res_id = recipe.get("result_id"); res_qty = recipe.get("result_qty", 1) * qty
            obj = item_manager.create_item_object(res_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)
            if obj:
                inventory.addItem(obj, res_qty); state["message"] = f"✓ ¡Has creado {res_qty}x {recipe['result_name']}!"; state["msg_style"] = "bold green"
                if not hasattr(player, "discovered_items"): player.discovered_items = set()
                player.discovered_items.add(res_id)
        else: state["message"] = "✗ No tienes materiales suficientes"; state["msg_style"] = "bold red"

    def _on_press(key):
        recipes = _get_filtered_recipes()
        if state["input_mode"] == "search":
            if key == "enter" or key == "esc": state["input_mode"] = "normal"
            elif key == "backspace": state["search_query"] = state["search_query"][:-1]; state["idx"] = 0; state["scroll"] = 0
            elif len(key) == 1: state["search_query"] += key; state["idx"] = 0; state["scroll"] = 0
            return
        if state["input_mode"] == "quantity":
            if key == "enter":
                if state["qty_buffer"].isdigit():
                    qty = int(state["qty_buffer"])
                    if qty > 0 and recipes: _craft(recipes[state["idx"]], qty)
                state["input_mode"] = "normal"
            elif key == "esc": state["input_mode"] = "normal"
            elif key == "backspace": state["qty_buffer"] = state["qty_buffer"][:-1]
            elif key.isdigit(): state["qty_buffer"] += key
            return
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
            if state["idx"] < state["scroll"]: state["scroll"] = state["idx"]
        elif key == "down":
            state["idx"] = min(len(recipes) - 1, state["idx"] + 1)
            if state["idx"] >= state["scroll"] + MAX_VISIBLE: state["scroll"] = state["idx"] - MAX_VISIBLE + 1
        elif key == "esc": state["exit"] = True
        elif key == "s": state["input_mode"] = "search"; state["search_query"] = ""
        elif key == "f" and recipes:
            r_id = recipes[state["idx"]]["id"]
            if not hasattr(player, "favorite_recipes"): player.favorite_recipes = []
            if r_id in player.favorite_recipes: player.favorite_recipes.remove(r_id)
            else: player.favorite_recipes.append(r_id)
        elif key == "enter" and recipes: _craft(recipes[state["idx"]], 1)
        elif key == "q": state["input_mode"] = "quantity"; state["qty_buffer"] = ""

    with console.screen():
        with keyboard_listener_scope():
            kb_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_press, "sequential": False, "until": None}, daemon=True)
            kb_thread.start()
            try:
                with Live(console=console, refresh_per_second=20, transient=True) as live:
                    while not state["exit"]:
                        recipes = _get_filtered_recipes()
                        if state["idx"] >= len(recipes) and len(recipes) > 0: state["idx"] = len(recipes) - 1
                        left_panel = _render_recipe_list(recipes, state["idx"], state["scroll"]); right_panel = _render_recipe_detail(recipes[state["idx"]] if recipes else None)
                        mode_info = f" [bold yellow]BUSCANDO:[/] {state['search_query']}_" if state["input_mode"] == "search" else (f" [bold magenta]CANTIDAD:[/] {state['qty_buffer']}_" if state["input_mode"] == "quantity" else "")
                        footer = Panel(Text(state["message"], style=state["msg_style"]).append(mode_info, style="white"), border_style="dim")
                        grid = Table.grid(expand=True); grid.add_column(ratio=2); grid.add_column(ratio=3); grid.add_row(left_panel, right_panel)
                        live.update(Panel(Group(grid, footer), title="[bold white]⚒ MESA DE CRAFTEO ⚒[/]", subtitle="[ESC] Salir", border_style="bright_black", padding=(0,1)))
                        time.sleep(0.05)
            finally:
                stop_listening()
                if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
        console.clear()
