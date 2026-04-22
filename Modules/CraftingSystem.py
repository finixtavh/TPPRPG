import json
import os
import time
import threading
import random
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

console = Console()

class cRecipe:
    def __init__(self, data: dict):
        self.recipe_id = data.get("recipe_id")
        self.name = data.get("name")
        self.result_item_id = data.get("result_item_id")
        self.result_item_type = data.get("result_item_type")  # e.g., Weapon, Tool, Object
        self.materials_required = data.get("materials_required", {})
        self.description = data.get("description", "")
        self.gold_cost = data.get("gold_cost", 0)
        self.category = data.get("category", "General")

class CraftingSystem:
    def __init__(self):
        self.recipes: List[cRecipe] = []
        self.load_recipes()

    def load_recipes(self):
        path = os.path.join("Data", "DataRecipes.json")
        if not os.path.exists(path): return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.recipes = [cRecipe(r) for r in data.get("recipes", [])]
            
            # Inyectar recetas de mods
            try:
                from Modules.ModLoader import get_mod_api
                mod_api = get_mod_api()
                mod_api.integrate_with_crafting_system(self)
            except Exception:
                pass
        except Exception:
            pass

    def get_material_count(self, inventory, material_name: str) -> int:
        count = 0
        for slot in inventory.slots:
            name = getattr(slot.item, "Name", getattr(slot.item, "name", ""))
            if name.lower() == material_name.lower():
                count += slot.quantity
        return count

    def can_craft(self, recipe: cRecipe, inventory, player_gold: float, quantity: int = 1) -> bool:
        if quantity <= 0: return False
        if player_gold < recipe.gold_cost * quantity:
            return False
        for mat_name, amount in recipe.materials_required.items():
            if self.get_material_count(inventory, mat_name) < amount * quantity:
                return False
        return True

    def get_max_craftable(self, recipe: cRecipe, inventory, player_gold: float) -> int:
        max_by_gold = int(player_gold // recipe.gold_cost) if recipe.gold_cost > 0 else 999
        max_by_mats = 999
        for mat_name, amount in recipe.materials_required.items():
            in_inv = self.get_material_count(inventory, mat_name)
            max_by_mats = min(max_by_mats, in_inv // amount) if amount > 0 else max_by_mats
        return min(max_by_gold, max_by_mats)

    def consume_materials(self, inventory, material_name: str, amount: int):
        item_to_remove = None
        for slot in inventory.slots:
            name = getattr(slot.item, "Name", getattr(slot.item, "name", ""))
            if name.lower() == material_name.lower():
                item_to_remove = slot.item
                break
        
        if item_to_remove:
            inventory.remove_item(item_to_remove, amount)

def open_crafting_menu(player, inventory):
    system = CraftingSystem()
    item_manager = get_item_manager()
    
    state = {
        "idx": 0,
        "scroll": 0,
        "search_query": "",
        "input_mode": "normal", # normal, search, quantity
        "qty_buffer": "",
        "message": "Usa ↑↓ para navegar, [F] Favorito, [S] Buscar, [ENTER] Craftear 1, [M] Máx, [Q] Cantidad",
        "msg_style": "dim",
        "exit": False,
        "last_key_time": 0
    }

    MAX_VISIBLE = 10

    def _get_filtered_recipes():
        q = state["search_query"].lower()
        filtered = [r for r in system.recipes if q in r.name.lower() or any(q in m.lower() for m in r.materials_required.keys())]
        
        favs = [r for r in filtered if r.recipe_id in player.favorite_recipes]
        others = [r for r in filtered if r.recipe_id not in player.favorite_recipes]
        return favs + others

    def _render_recipe_list(recipes, selected_idx, scroll_offset):
        t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t.add_column("Fav", width=3)
        t.add_column("Nombre", ratio=1)
        t.add_column("Estado", width=10)

        if not recipes:
            t.add_row("", "[dim]No se encontraron recetas[/]", "")
            return Panel(t, title="[bold yellow] RECETAS [/]", border_style="yellow")

        visible = recipes[scroll_offset : scroll_offset + MAX_VISIBLE]
        for i, recipe in enumerate(visible):
            abs_idx = scroll_offset + i
            is_selected = abs_idx == selected_idx
            is_fav = recipe.recipe_id in player.favorite_recipes
            
            can_c = system.can_craft(recipe, inventory, player.Gold)
            status = "[green]LISTO[/]" if can_c else "[red]FALTAN[/]"
            
            fav_icon = "[yellow]★[/]" if is_fav else "[dim]☆[/]"
            name_text = Text(recipe.name)
            if is_selected:
                name_text.stylize("bold reverse")
                row_style = "bold cyan"
            else:
                row_style = "white"

            t.add_row(fav_icon, name_text, status, style=row_style)
        
        return Panel(t, title="[bold yellow] RECETAS [/]", border_style="yellow")

    def _render_recipe_detail(recipe: Optional[cRecipe]):
        if not recipe:
            return Panel(Text("\n\nSelecciona una receta", justify="center", style="dim"), title="[bold] DETALLE [/]")

        lines = []
        lines.append(Text(f" {recipe.name}", style="bold cyan"))
        lines.append(Rule(style="dim"))
        lines.append(Text(f" {recipe.description}", style="italic dim"))
        lines.append(Text(""))
        
        gold_color = "green" if player.Gold >= recipe.gold_cost else "red"
        lines.append(Text(f" Costo: ", style="bold").append(f"{recipe.gold_cost}g", style=gold_color).append(f" (Tienes: {int(player.Gold)}g)", style="dim"))
        lines.append(Text(""))
        
        lines.append(Text(" Materiales Requeridos:", style="bold underline"))
        m_table = Table(show_header=True, box=box.SIMPLE_HEAD, header_style="bold", padding=(0,1), expand=True)
        m_table.add_column("Material")
        m_table.add_column("Tengo", justify="right")
        m_table.add_column("Necesito", justify="right")
        
        for mat_name, req_amt in recipe.materials_required.items():
            have_amt = system.get_material_count(inventory, mat_name)
            color = "green" if have_amt >= req_amt else "red"
            if have_amt > 0 and have_amt < req_amt: color = "yellow"
            m_table.add_row(mat_name, Text(str(have_amt), style=color), str(req_amt))
        
        lines.append(m_table)
        
        max_c = system.get_max_craftable(recipe, inventory, player.Gold)
        lines.append(Text(f"\n Máximo posible: [bold]{max_c}[/]", style="dim"))

        return Panel(Group(*lines), title="[bold cyan] INFORMACIÓN [/]", border_style="cyan")

    def _on_press(key):
        recipes = _get_filtered_recipes()
        num_recipes = len(recipes)

        if state["input_mode"] == "search":
            if key == "enter" or key == "esc":
                state["input_mode"] = "normal"
            elif key == "backspace":
                state["search_query"] = state["search_query"][:-1]
                state["idx"] = 0
                state["scroll"] = 0
            elif len(key) == 1:
                state["search_query"] += key
                state["idx"] = 0
                state["scroll"] = 0
            return

        if state["input_mode"] == "quantity":
            if key == "enter":
                qty = 0
                try: qty = int(state["qty_buffer"])
                except: pass
                state["input_mode"] = "normal"
                _do_craft(recipes, qty)
            elif key == "esc":
                state["input_mode"] = "normal"
            elif key == "backspace":
                state["qty_buffer"] = state["qty_buffer"][:-1]
            elif key.isdigit():
                state["qty_buffer"] += key
            return

        # Normal mode
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
            if state["idx"] < state["scroll"]:
                state["scroll"] = state["idx"]
        elif key == "down":
            state["idx"] = min(num_recipes - 1, state["idx"] + 1)
            if state["idx"] >= state["scroll"] + MAX_VISIBLE:
                state["scroll"] = state["idx"] - MAX_VISIBLE + 1
        elif key == "esc":
            state["exit"] = True
        elif key == "f":
            if num_recipes > 0:
                rid = recipes[state["idx"]].recipe_id
                if rid in player.favorite_recipes:
                    player.favorite_recipes.remove(rid)
                else:
                    player.favorite_recipes.append(rid)
        elif key == "s":
            state["input_mode"] = "search"
            state["search_query"] = ""
        elif key == "m":
            if num_recipes > 0:
                max_q = system.get_max_craftable(recipes[state["idx"]], inventory, player.Gold)
                _do_craft(recipes, max_q)
        elif key == "q":
            if num_recipes > 0:
                state["input_mode"] = "quantity"
                state["qty_buffer"] = ""
        elif key == "enter":
            _do_craft(recipes, 1)

    def _do_craft(recipes, qty):
        if not recipes or qty <= 0: return
        recipe = recipes[state["idx"]]
        
        if system.can_craft(recipe, inventory, player.Gold, qty):
            player.Gold -= recipe.gold_cost * qty
            for mat_name, amt in recipe.materials_required.items():
                system.consume_materials(inventory, mat_name, amt * qty)
            
            for _ in range(qty):
                new_item = item_manager.create_item_object(recipe.result_item_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)
                if new_item:
                    inventory.addObject(new_item)
            
            state["message"] = f"¡Éxito! Has fabricado {qty}x {recipe.name}"
            state["msg_style"] = "bold green"
        else:
            state["message"] = f"Recursos insuficientes para {qty}x {recipe.name}"
            state["msg_style"] = "bold red"

    with keyboard_listener_scope():
        kb_thread = threading.Thread(
            target=listen_keyboard, 
            kwargs={"on_press": _on_press, "sequential": True}, 
            daemon=True
        )
        kb_thread.start()

        try:
            with Live(console=console, refresh_per_second=20, transient=False, screen=True) as live:
                while not state["exit"]:
                    recipes = _get_filtered_recipes()
                    if state["idx"] >= len(recipes) and len(recipes) > 0:
                        state["idx"] = len(recipes) - 1
                    
                    selected_recipe = recipes[state["idx"]] if recipes else None
                    
                    left_panel = _render_recipe_list(recipes, state["idx"], state["scroll"])
                    right_panel = _render_recipe_detail(selected_recipe)
                    
                    mode_info = ""
                    if state["input_mode"] == "search":
                        mode_info = f" [bold yellow]BUSCANDO:[/] {state['search_query']}_"
                    elif state["input_mode"] == "quantity":
                        mode_info = f" [bold magenta]CANTIDAD:[/] {state['qty_buffer']}_"
                    
                    footer = Panel(Text(state["message"], style=state["msg_style"]).append(mode_info, style="white"), border_style="dim")
                    
                    grid = Table.grid(expand=True)
                    grid.add_column(ratio=2)
                    grid.add_column(ratio=3)
                    grid.add_row(left_panel, right_panel)
                    
                    main_group = Group(grid, footer)
                    live.update(Panel(main_group, title="[bold white]⚒ MESA DE CRAFTEO ⚒[/]", subtitle="[ESC] Salir", border_style="bright_black", padding=(0,1)))
                    time.sleep(0.05)
        finally:
            stop_listening()
            if kb_thread.is_alive():
                kb_thread.join(timeout=1.0)
            time.sleep(0.05)
