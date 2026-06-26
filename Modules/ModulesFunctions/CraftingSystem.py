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
from sshkeyboard import stop_listening

from Modules.ModulesUtils.Loader import Read
from Modules.ModulesUtils.input_utils import keyboard_listener_scope, start_key_listener
from Modules.ModulesManager.ItemManager import get_item_manager
from Modules.ModulesUtils.setup import cWeapon, cEquippableItems, cObject
from Modules.ModulesFunctions.GatheringMasterySystem import cMaterial, cTool  
from Modules.ModulesUtils.ModLoader import get_mod_api
from Modules.ModulesManager.ItemModifierSystem import roll_and_apply_modifier, get_item_display_name

console = Console()

class CraftingSystem:
    def __init__(self, player, inventory):
        self.player = player
        self.inventory = inventory
        self.recipes = []
        self._load_recipes()

    def _load_recipes(self):
        data_path = os.path.join(os.path.dirname(__file__), "..", "..", "Data", "DataRecipes.json")
        try:
            import json
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # DataRecipes.json has {"recipes": [...]}
            for r in data.get("recipes", []):
                # Normalise field names to what the UI expects
                self.recipes.append({
                    "id":          r.get("recipe_id", "???"),
                    "result_name": r.get("name", "???"),
                    "result_id":   r.get("result_item_id"),
                    "result_qty":  r.get("result_qty", 1),
                    "materials":   r.get("materials_required", {}),
                    "description": r.get("description", ""),
                    "gold_cost":   r.get("gold_cost", 0),
                })
        except Exception as e:
            pass  # No recipes — menu will show empty state gracefully

        try:
            mod_api = get_mod_api()
            if hasattr(mod_api, "recipe_injections"):
                for r_id, r_data in mod_api.recipe_injections.items():
                    r_data["id"] = r_id
                    self.recipes.append(r_data)
        except Exception:
            pass

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

    def _get_actual_item_id(mat_id_or_name):
        try:
            return int(mat_id_or_name)
        except ValueError:
            pass
        item_data = item_manager.get_item_by_name(mat_id_or_name)
        if item_data:
            return item_data.get("STATIC_ID", item_data.get("MATERIAL_ID", mat_id_or_name))
        return mat_id_or_name

    def _get_actual_item_name(mat_id_or_name):
        try:
            item_id = int(mat_id_or_name)
            item_data = item_manager.get_item_by_id(item_id) or item_manager.get_item_by_id(item_id, material=True)
            if item_data:
                return item_data.get("Name", str(item_id))
        except ValueError:
            return str(mat_id_or_name)
        return str(mat_id_or_name)

    def _has_materials(recipe, multiplier=1):
        for mat_id, req_qty in recipe["materials"].items():
            actual_id = _get_actual_item_id(mat_id)
            if inventory.get_item_count(actual_id) < (req_qty * multiplier): return False
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
            actual_id = _get_actual_item_id(mat_id)
            owned = inventory.get_item_count(actual_id)
            mat_name = _get_actual_item_name(mat_id)
            color = "green" if owned >= req_qty else ("yellow" if owned > 0 else "red")
            lines.append(Text(f" • {mat_name}: {owned}/{req_qty}", style=color))
        lines.append(Text("")); lines.append(Text(f" Resultado: {recipe.get('result_qty', 1)}x {recipe.get('result_name')}", style="dim italic"))
        return Panel(Group(*lines), title="[bold cyan] INFORMACIÓN DE CRAFTEO [/]", border_style="cyan")

    def _craft(recipe, qty=1):
        if _has_materials(recipe, qty):
            for mat_id, req_qty in recipe["materials"].items():
                actual_id = _get_actual_item_id(mat_id)
                inventory.remove_item(actual_id, req_qty * qty)
            res_id = recipe.get("result_id"); res_qty = recipe.get("result_qty", 1) * qty
            obj = item_manager.create_item_object(res_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)
            if obj:
                # Aplicar modificador de crafteo
                try:
                    from pathlib import Path
                    import json as _json
                    _cfgp = Path(__file__).parent.parent.parent / "config.json"
                    _cfg  = _json.loads(_cfgp.read_text("utf-8"))
                    _cqp  = float(_cfg.get("WORLD", {}).get("GLOBAL_CRAFTING_QUALITY_MODIFIER_POSITIVE", 1))
                    _cqn  = float(_cfg.get("WORLD", {}).get("GLOBAL_CRAFTING_QUALITY_MODIFIER_NEGATIVE", 1))
                    _mod = roll_and_apply_modifier(obj, _cqp, _cqn)
                    _dname = get_item_display_name(obj)
                    _mod_txt = f" [{('red' if _mod.is_negative else 'green')}]{_mod.icon} {_mod.name}[/]" if _mod else ""
                except Exception:
                    _dname  = recipe['result_name']
                    _mod_txt = ""
                inventory.addObject(obj, res_qty)
                state["message"] = f"✓ ¡Creado: {_dname}{_mod_txt} x{res_qty}!"
                state["msg_style"] = "bold green"
                if not hasattr(player, "discovered_items"): player.discovered_items = set()
                player.discovered_items.add(res_id)
        else: state["message"] = "✗ No tienes materiales suficientes"; state["msg_style"] = "bold red"

    # ── Modo Reforjar ─────────────────────────────────────────────────────────────

    REFORGE_COST = 500  # oro

    reforge_state = {
        "idx":   0,
        "scroll": 0,
    }

    def _get_forgeable_slots():
        """Items reforjables: cWeapon, cEquippableItems, cTool."""
        forgeable = []
        for slot in getattr(inventory, "slots", []):
            item = slot.item
            if type(item).__name__ in ("cWeapon", "cEquippableItems", "cTool"):
                forgeable.append(slot)
        return forgeable

    def _render_reforge():
        slots = _get_forgeable_slots()
        t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t.add_column("▶", width=3)
        t.add_column("Nombre", ratio=1)
        t.add_column("Tipo", width=16)
        t.add_column("Mod actual", width=20)
        if not slots:
            t.add_row("", "[dim]No tienes objetos reforjables[/]", "", "")
        else:
            for i, slot in enumerate(slots):
                item     = slot.item
                selected = i == reforge_state["idx"]
                iname    = getattr(item, "name", getattr(item, "Name", "?"))
                itype    = type(item).__name__
                cur_mod  = getattr(item, "modifier", None)
                mod_str  = (f"[{'red' if cur_mod.is_negative else 'green'}]{cur_mod.icon} {cur_mod.name}[/]"
                            if cur_mod else "[dim]Sin modificador[/]")
                t.add_row(
                    "[bold bright_cyan]▶[/]" if selected else " ",
                    f"[bold bright_cyan]{iname}[/]" if selected else iname,
                    f"[dim]{itype}[/]",
                    mod_str,
                    style="bold bright_cyan" if selected else "white",
                )
        gold = getattr(player, "Gold", 0)
        can_afford = gold >= REFORGE_COST
        gold_color = "green" if can_afford else "red"
        hint = (f"↑↓: Seleccionar | [ENTER]: Reforjar ({REFORGE_COST}g)  "
                f"Tu oro: [{gold_color}]{gold}g[/{gold_color}]  | [ESC]: Volver al crafteo")
        footer = Panel(
            Group(
                Text.from_markup(f"  💰 Costo de reforje: [yellow]{REFORGE_COST} oro[/yellow]  —  "
                                 f"Tu oro: [{gold_color}]{gold}[/{gold_color}]"),
                Text(state["message"], style=state["msg_style"]),
            ),
            border_style="yellow",
        )
        return Panel(
            Group(Text.from_markup(f" [dim]{hint}[/dim]"), Rule(style="yellow"), t, footer),
            title="[bold yellow]🔨 YUNQUE — REFORJAR OBJETO[/]",
            border_style="yellow",
            padding=(0, 1),
        )

    def _do_reforge():
        slots = _get_forgeable_slots()
        if not slots:
            state["message"] = "✗ No hay objetos para reforjar."
            state["msg_style"] = "bold red"
            return
        idx = min(reforge_state["idx"], len(slots) - 1)
        item = slots[idx].item

        if getattr(player, "Gold", 0) < REFORGE_COST:
            state["message"] = f"✗ Necesitas {REFORGE_COST} oro para reforjar."
            state["msg_style"] = "bold red"
            return

        # Cobrar
        player.Gold -= REFORGE_COST

        # Leer modificadores de calidad de crafteo
        try:
            from pathlib import Path
            import json as _json
            _cfgp = Path(__file__).parent.parent.parent / "config.json"
            _cfg  = _json.loads(_cfgp.read_text("utf-8"))
            _cqp  = float(_cfg.get("WORLD", {}).get("GLOBAL_CRAFTING_QUALITY_MODIFIER_POSITIVE", 1))
            _cqn  = float(_cfg.get("WORLD", {}).get("GLOBAL_CRAFTING_QUALITY_MODIFIER_NEGATIVE", 1))
        except Exception:
            _cqp, _cqn = 1.0, 1.0

        # Quitar modificador anterior si lo había
        if hasattr(item, "modifier") and item.modifier is not None:
            item.modifier = None  # El modify ya fue aplicado al objeto en la última vez

        mod = roll_and_apply_modifier(item, _cqp, _cqn)
        dname = get_item_display_name(item)
        if mod:
            color = "red" if mod.is_negative else "green"
            state["message"] = f"✓ [{color}]{mod.icon} {mod.name}[/] aplicado a {dname}!"
        else:
            state["message"] = f"✓ {dname} reforjado sin modificador especial."
        state["msg_style"] = "bold cyan"

    def _on_press(key):
        if state.get("mode") == "reforge":
            slots = _get_forgeable_slots()
            if key == "up":
                reforge_state["idx"] = max(0, reforge_state["idx"] - 1)
            elif key == "down":
                reforge_state["idx"] = min(max(0, len(slots) - 1), reforge_state["idx"] + 1)
            elif key == "enter":
                _do_reforge()
            elif key in ("esc", "r"):
                state["mode"] = "craft"
                state["message"] = "↑↓: Navegar | [S]: Buscar | [F]: Favorito | [ENTER]: Craftear | [R]: Reforjar | [ESC]: Salir"
                state["msg_style"] = "dim"
            state["dirty"] = True
            return

        # Modo crafteo normal
        recipes = _get_filtered_recipes()
        if state["input_mode"] == "search":
            if key == "enter" or key == "esc": state["input_mode"] = "normal"
            elif key == "backspace": state["search_query"] = state["search_query"][:-1]; state["idx"] = 0; state["scroll"] = 0
            elif len(key) == 1: state["search_query"] += key; state["idx"] = 0; state["scroll"] = 0
            state["dirty"] = True
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
            state["dirty"] = True
            return
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
            if state["idx"] < state["scroll"]: state["scroll"] = state["idx"]
        elif key == "down":
            state["idx"] = min(len(recipes) - 1, state["idx"] + 1)
            if state["idx"] >= state["scroll"] + MAX_VISIBLE: state["scroll"] = state["idx"] - MAX_VISIBLE + 1
        elif key == "esc": state["exit"] = True; stop_listening()
        elif key == "r":
            state["mode"] = "reforge"
            state["message"] = "Selecciona un objeto y presiona ENTER para reforjar."
            state["msg_style"] = "bold yellow"
        elif key == "s": state["input_mode"] = "search"; state["search_query"] = ""
        elif key == "f" and recipes:
            r_id = recipes[state["idx"]]["id"]
            if not hasattr(player, "favorite_recipes"): player.favorite_recipes = []
            if r_id in player.favorite_recipes: player.favorite_recipes.remove(r_id)
            else: player.favorite_recipes.append(r_id)
        elif key == "enter" and recipes: _craft(recipes[state["idx"]], 1)
        elif key == "q": state["input_mode"] = "quantity"; state["qty_buffer"] = ""
        state["dirty"] = True

    state["mode"] = "craft"
    state["message"] = "↑↓: Navegar | [S]: Buscar | [F]: Favorito | [ENTER]: Craftear | [R]: Reforjar | [ESC]: Salir"
    state["dirty"] = True
    with console.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            try:
                with Live(console=console, screen=True, auto_refresh=False) as live:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            state["dirty"] = False
                            if state.get("mode") == "reforge":
                                live.update(_render_reforge(), refresh=True)
                            else:
                                recipes = _get_filtered_recipes()
                                if state["idx"] >= len(recipes) and len(recipes) > 0: state["idx"] = len(recipes) - 1
                                left_panel = _render_recipe_list(recipes, state["idx"], state["scroll"]); right_panel = _render_recipe_detail(recipes[state["idx"]] if recipes else None)
                                mode_info = f" [bold yellow]BUSCANDO:[/] {state['search_query']}_" if state["input_mode"] == "search" else (f" [bold magenta]CANTIDAD:[/] {state['qty_buffer']}_" if state["input_mode"] == "quantity" else "")
                                footer = Panel(Text(state["message"], style=state["msg_style"]).append(mode_info, style="white"), border_style="dim")
                                grid = Table.grid(expand=True); grid.add_column(ratio=2); grid.add_column(ratio=3); grid.add_row(left_panel, right_panel)
                                live.update(Panel(Group(grid, footer), title="[bold white]⚒ MESA DE CRAFTEO ⚒[/]", subtitle="[R] Reforjar | [ESC] Salir", border_style="bright_black", padding=(0,1)), refresh=True)
                        time.sleep(0.005)
            finally:
                stop_listening()
                if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
        console.clear()
