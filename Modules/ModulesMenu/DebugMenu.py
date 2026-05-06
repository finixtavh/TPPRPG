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

from Modules.ModulesUtils.input_utils import keyboard_listener_scope
from Modules.ModulesManager.ItemManager import load_item_by_id
from Modules.ModulesUtils.setup import cWeapon, cEquippableItems, cObject
from Modules.ModulesFunctions.GatheringMasterySystem import cTool
from Modules.ModulesFunctions.CompanionSystem import cCompanion

console = Console()

def open_enhanced_debug_menu(player, inventory, gathering_init, mod_loader, mod_api, chosen_area):
    state = {
        "idx": 0,
        "exit": False,
        "message": "Navega con ↑↓ y Enter para seleccionar",
        "msg_style": "dim"
    }

    options = [
        ("Añadir Armas de Prueba", "add_weapons"),
        ("Añadir Oro y EXP (Max)", "max_resources"),
        ("Añadir +20 niveles a todo Mastery", "boost_mastery"),
        ("Dar +20 SP de Guild (Todas)", "guild_sp"),
        ("Ver Variables (Avanzado)", "look_variables"),
        ("Añadir Compañero de Prueba", "add_companion"),
        ("Provocar Desastre Aleatorio", "trigger_disaster"),
        ("Añadir Buff Aleatorio", "add_buff"),
        ("Añadir Debuff Aleatorio", "add_debuff"),
        ("Volver", "exit")
    ]

    def _trigger_disaster():
        try:
            from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
            from Modules.ModulesFunctions.GuildSystem import get_guild_manager
            wm = get_weather_manager()
            disaster_weathers = [w for w in wm.weathers.values() if w.disaster_effect]
            if disaster_weathers:
                chosen = random.choice(disaster_weathers)
                wm.current_weather = chosen
                gm = get_guild_manager()
                gm.tick()
                state["message"] = f"✓ Desastre provocado: {chosen.name}"
                state["msg_style"] = "bold red"
            else:
                state["message"] = "✗ No se encontraron desastres."
                state["msg_style"] = "bold yellow"
        except Exception as e:
            state["message"] = f"✗ Error: {e}"
            state["msg_style"] = "bold red"

    def _add_buff():
        try:
            from Modules.ModulesManager.BuffManager import get_buff_manager, apply_buff_to_player
            bm = get_buff_manager()
            buff_ids = list(bm.buffs_data.keys())
            if buff_ids:
                bid = random.choice(buff_ids)
                apply_buff_to_player(player, bid)
                state["message"] = f"✓ Buff aplicado: {bid}"
                state["msg_style"] = "bold green"
            else:
                state["message"] = "✗ No hay buffs disponibles."
                state["msg_style"] = "bold yellow"
        except Exception as e:
            state["message"] = f"✗ Error: {e}"
            state["msg_style"] = "bold red"

    def _add_debuff():
        try:
            from Modules.ModulesManager.BuffManager import get_buff_manager, apply_buff_to_player
            bm = get_buff_manager()
            debuff_ids = list(bm.debuffs_data.keys())
            if debuff_ids:
                did = random.choice(debuff_ids)
                apply_buff_to_player(player, did)
                state["message"] = f"✓ Debuff aplicado: {did}"
                state["msg_style"] = "bold red"
            else:
                state["message"] = "✗ No hay debuffs disponibles."
                state["msg_style"] = "bold yellow"
        except Exception as e:
            state["message"] = f"✗ Error: {e}"
            state["msg_style"] = "bold red"

    def _boost_mastery():
        for skill in gathering_init.gathering.values():
            skill.current_level += 20
        for skill in gathering_init.weapons.values():
            skill.current_level += 20
        state["message"] = "✓ +20 niveles añadidos a todas las maestrías"
        state["msg_style"] = "bold green"

    def _max_resources():
        player.Gold += 9999999
        player.EXP += 9999999
        state["message"] = "✓ Oro y EXP aumentados al máximo"
        state["msg_style"] = "bold yellow"

    def _add_weapons():


        try:
            w1 = load_item_by_id(3, cWeapon, cEquippableItems, cObject, cTool)
            w2 = load_item_by_id(100, cWeapon, cEquippableItems, cObject, cTool)
            if w1: inventory.addObject(w1)
            if w2: inventory.addObject(w2)
            state["message"] = "✓ Armas de prueba añadidas al inventario"
            state["msg_style"] = "bold cyan"
        except Exception as e:
            state["message"] = f"✗ Error: {e}"
            state["msg_style"] = "bold red"

    def _add_companion():

        test_comp = cCompanion(
            companion_id="lyra_debug",
            name="Lyra (Debug)",
            health_max=100,
            mana_max=100,
        )
        player.companion.append(test_comp)
        state["message"] = f"✓ Compañero '{test_comp.name}' añadido"
        state["msg_style"] = "bold green"

    def _add_guild_sp():
        try:
            from Modules.ModulesFunctions.GuildSystem import get_guild_manager
            gm = get_guild_manager()
            if not gm.guilds:
                gm.generate_random_guilds()
            for gid, g in gm.guilds.items():
                g.skill_points += 20
            state["message"] = "✓ +20 SP de Guild añadidos a todas las guilds"
            state["msg_style"] = "bold green"
        except Exception as e:
            state["message"] = f"✗ Error: {e}"
            state["msg_style"] = "bold red"

    def _on_press(key):
        if key == "up":
            state["idx"] = (state["idx"] - 1) % len(options)
        elif key == "down":
            state["idx"] = (state["idx"] + 1) % len(options)
        elif key == "enter":
            action = options[state["idx"]][1]
            if action == "exit":
                state["exit"] = True
                stop_listening()
            elif action == "add_weapons":
                _add_weapons()
            elif action == "max_resources":
                _max_resources()
            elif action == "boost_mastery":
                _boost_mastery()
            elif action == "guild_sp":
                _add_guild_sp()
            elif action == "add_companion":
                _add_companion()
            elif action == "trigger_disaster":
                _trigger_disaster()
            elif action == "look_variables":
                state["exit_for_variables"] = True
                stop_listening()
        elif key == "esc":
            state["exit"] = True
            stop_listening()

    # Usamos console.screen() para evitar el bug de "títulos repetidos" y asegurar limpieza total
    with console.screen() as screen:
        while not state["exit"]:
            state["exit_for_variables"] = False
            with keyboard_listener_scope():
                kb_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_press, "sequential": False, "until": None}, daemon=True)
                kb_thread.start()

                try:
                    with Live(console=console, refresh_per_second=15) as live:
                        while not state["exit"] and not state.get("exit_for_variables", False):
                            t = Table(show_header=False, box=None, expand=True)
                            for i, (label, _) in enumerate(options):
                                if i == state["idx"]:
                                    t.add_row(f"[bold bright_magenta]▶ {label}[/]")
                                else:
                                    t.add_row(f"  {label}")
                            
                            footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
                            live.update(Panel(Group(t, "", footer), title="[bold magenta]⚙ MENÚ DEBUG ⚙[/]", border_style="magenta", padding=(1, 2)))
                            time.sleep(0.06)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
            
            if state.get("exit_for_variables", False):
                open_variable_viewer(player, inventory, gathering_init, mod_loader, mod_api, chosen_area)
                # Al volver del visor, seguimos en el bucle principal del menú debug

def open_variable_viewer(player, inventory, gathering_init, mod_loader, mod_api, chosen_area):
    tabs = ["Jugador", "Stats", "Mastery", "Mundo", "Sistema"]
    cur_tab = 0
    exit_viewer = False

    def _get_player_data():
        p = player
        data = {
            "Nombre": p.name,
            "Nivel": p.Level,
            "Oro": f"{p.Gold:,}",
            "EXP": f"{p.EXP:,.1f} / {p.EXP_M:,.1f}",
            "Puntos LVL": p.lvlPoints,
            "Descubiertos": f"{len(getattr(p, 'discovered_items', set()))} ítems",
            "Favoritos (R)": f"{len(getattr(p, 'favorite_recipes', []))} recetas",
            "Favoritos (I)": f"{len(getattr(p, 'favorite_items', []))} ítems",
        }
        return data

    def _get_stats_data():
        p = player
        data = {
            "HP": f"{p.Health:.1f} / {p.Health_max:.1f}",
            "Mana": f"{p.Mana:.1f} / {p.Mana_max:.1f}",
            "Regen Mana": p.ManaRegen,
            "AGI": p.AGI,
            "Defensas": list(p.DEF),
            "Def %": list(p.DefensePercentage),
            "Evasión": p.Evasion,
            "Counter": p.CounterAttack,
            "Barrera": p.Barrier,
        }
        return data

    def _get_mastery_data():
        g = gathering_init
        data = {}
        for k, v in g.gathering.items():
            data[f"Rec: {k}"] = f"Lv.{v.current_level} ({v.exp_total:,.0f} XP)"
        for k, v in g.weapons.items():
            data[f"Wep: {k}"] = f"Lv.{v.current_level} ({v.exp_total:,.0f} XP)"
        return data

    def _get_world_data():
        data = {
            "Zona Actual": chosen_area,
            "Compañeros": len(getattr(player, "companion", [])),
            "Misiones": "Ver Tablón",
            "Base": "Nivel " + str(getattr(player, "BaseLevel", 1) if hasattr(player, "BaseLevel") else "?"),
        }
        return data

    def _get_system_data():
        data = {
            "Mods Cargados": len(getattr(mod_loader, "loaded_mods", {})),
            "Comandos Mod": len(getattr(mod_api, "custom_commands", {})) if mod_api else 0,
            "Items Mod": len(getattr(mod_api, "registered_items", {})) if mod_api else 0,
            "Recetas Mod": len(getattr(mod_api, "recipe_injections", {})) if mod_api else 0,
        }
        return data

    def _render_viewer(tab_idx):
        h = Text()
        for i, name in enumerate(tabs):
            if i == tab_idx:
                h.append(f" {name} ", style="bold black on magenta")
            else:
                h.append(f" {name} ", style="dim")
            if i < len(tabs) - 1: h.append("  ")
        
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("Variable", style="cyan")
        t.add_column("Valor", style="white")

        if tab_idx == 0: d = _get_player_data()
        elif tab_idx == 1: d = _get_stats_data()
        elif tab_idx == 2: d = _get_mastery_data()
        elif tab_idx == 3: d = _get_world_data()
        else: d = _get_system_data()

        for k, v in d.items():
            t.add_row(k, str(v))

        return Panel(Group(h, Rule(style="magenta"), t), title="[bold magenta] VISOR DE VARIABLES DEBUG [/]", subtitle="<- -> para pestañas | ESC para volver", border_style="magenta")

    def _on_press_viewer(key):
        nonlocal cur_tab, exit_viewer
        if key == "left":
            cur_tab = (cur_tab - 1) % len(tabs)
        elif key == "right":
            cur_tab = (cur_tab + 1) % len(tabs)
        elif key == "esc" or key == "enter":
            exit_viewer = True
            stop_listening()

    # No usamos console.screen() aquí porque ya estamos dentro de uno en open_enhanced_debug_menu
    with keyboard_listener_scope():
        kb_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_press_viewer, "sequential": False, "until": None}, daemon=True)
        kb_thread.start()
        try:
            with Live(console=console, refresh_per_second=15) as live:
                while not exit_viewer:
                    live.update(_render_viewer(cur_tab))
                    time.sleep(0.06)
        finally:
            stop_listening()
            if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
    
    console.clear()
