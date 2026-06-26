"""
GuildMenu.py — UI principal del sistema de Guilds. Opción 16.

Regla de renderizado: cada función interactiva tiene su propio
    with console.screen():
        with keyboard_listener_scope():
            with Live(console=..., refresh_per_second=20):  # SIN transient=True
                ...
    console.clear()

NO se anidan screens. open_guild_menu es solo un loop de navegación.
"""

# ── Edificios de Guild ────────────────────────────────────────────────────────
from Modules.ModulesFunctions.GuildSystem import GUILD_BUILDINGS


import os
import time
import threading
import json
from pathlib import Path
from typing import Optional

def _get_guild_config():
    cfg_path = Path(__file__).parent.parent.parent / "config.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f).get("GUILDS_PARAMS", {})
    except:
        return {}

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich import box
from sshkeyboard import stop_listening

from Modules.ModulesFunctions.GuildSystem import Guild, GuildManager, get_guild_manager, reset_guild_manager, SIMULATION_INTERVAL, TIER_ROMAN, ROMAN_TIER, MAX_TERRITORY_LEVEL
from Modules.ModulesUtils.setup import vInventory
from Modules.ModulesUtils.Loader import Read
from Modules.ModulesFunctions.GuildSkillTree import open_guild_skill_tree, BRANCH_ICONS
from Modules.ModulesFunctions.GuildMissions import open_guild_missions_menu
from Modules.ModulesUtils.input_utils import keyboard_listener_scope, start_key_listener
from Modules.ModulesUtils.UIStyle import (
    herald_panel, herald_bar, herald_table, ICONS, 
    COLOR_PRIMARY, COLOR_SECONDARY, COLOR_DIM
)

console = Console()

RARITY_COLORS = {
    "Common":    "white",
    "Uncommon":  "green",
    "Rare":      "bright_cyan",
    "Legendary": "bright_yellow",
}

def _render_summary(guild: Guild, player, gm: GuildManager):
    t = herald_table(expand=True)
    t.add_column("K", style=COLOR_PRIMARY, width=22)
    t.add_column("V", style="white", ratio=1)

    rep = gm.get_player_reputation(player, guild.guild_id)
    rank_name, rank_color = gm.get_reputation_rank(rep)

    t.add_row("Tipo",          f"{guild.icon} {guild.guild_type}")
    t.add_row(f"{ICONS['atk']}Poder Militar", f"{herald_bar(guild.military_power, 100)} {guild.military_power}")
    t.add_row(f"{ICONS['hp']}Moral",         f"{herald_bar(guild.moral, 100, color='yellow')} {guild.moral}/100")
    t.add_row("Población",     str(guild.population))
    t.add_row("Tu Reputación", f"[{rank_color}]{rank_name} ({rep:+d})[/]")

    log_text = Text()
    log_text.append("\n  Eventos recientes:\n", style="bold dim")
    for ev in guild.event_log[-3:]:
        log_text.append(f"  • {ev}\n", style="dim")

    return herald_panel(Group(t, Rule(style="dim"), log_text),
                  title=f"{guild.icon} {guild.name}", border_style=COLOR_PRIMARY)


def _render_territories(guild: Guild, gm: GuildManager, page: int = 0):
    map_rows = gm.get_territory_map_rows()
    map_text = Text()
    map_text.append("  ★ = Tuyo  · = Neutral  🔸 = Otro\n\n", style="dim")
    for row in map_rows:
        map_text.append("  " + row + "\n")

    PAGE_SIZE = 6
    total_pages = max(1, (len(guild.territories) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("Territorio")
    t.add_column("Recursos generados", ratio=1)
    if not guild.territories:
        t.add_row("[dim]Sin territorios[/]", "[dim]—[/]")
    else:
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        for tid in guild.territories[start:end]:
            terr = gm.territories.get(tid)
            if terr:
                res_str = f"Nv.{terr.level} → mat. Tier {TIER_ROMAN.get(terr.level, 'I')}/tick"
                t.add_row(f"{terr.icon} {terr.name}", res_str)

    footer = Text()
    if total_pages > 1:
        footer.append(f"\n  Página {page+1}/{total_pages} (↑↓ para cambiar)\n", style="bold yellow")

    return Panel(Group(map_text, Rule(style="dim"), t, footer),
                 title="[bold]🗺 TERRITORIOS[/]", border_style="green"), total_pages


def _render_resources(guild: Guild, gm: GuildManager):
    t = herald_table(expand=True)
    t.add_column("",       width=3)
    t.add_column("Recurso", ratio=3)
    t.add_column("Cant/Max", width=14)
    t.add_column("",       ratio=2)

    for rid, defn in gm.resource_defs.items():
        amount = guild.get_resource(rid)
        cap    = guild.get_resource_cap(rid, gm.resource_defs, gm.guild_type_defs)
        icon   = defn.get("icon", "?")
        t.add_row(
            icon, defn.get("name", rid),
            f"[white]{amount:,}/{cap}[/]",
            herald_bar(amount, cap, width=20)
        )

    return herald_panel(t, title="Recursos", border_style=COLOR_PRIMARY)


def _render_world(gm: GuildManager, player, page: int = 0):
    guilds = gm.get_sorted_guilds_by_power()
    PAGE_SIZE = 10
    total_pages = max(1, (len(guilds) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("#",       width=3)
    t.add_column("Guild",   ratio=2)
    t.add_column("Tipo",    width=12)
    t.add_column("Poder",   width=8)
    t.add_column("Moral",   width=8)
    t.add_column("Población", width=10)
    t.add_column("Tu Rep.", width=12)

    has_espionage = gm.get_player_guild() and "dip_espionage" in gm.get_player_guild().unlocked_skills

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    for i, guild in enumerate(guilds[start:end], start + 1):
        rep       = gm.get_player_reputation(player, guild.guild_id)
        rank, col = gm.get_reputation_rank(rep)
        is_player = guild.guild_id == gm.player_guild_id
        
        # Ocultar stats si no hay espionaje y no es la propia
        power_str = str(guild.military_power) if (is_player or has_espionage) else "???"
        moral_str = str(guild.moral) if (is_player or has_espionage) else "???"
        pop_str   = str(guild.population) if (is_player or has_espionage) else "???"

        prefix    = "★ " if is_player else f"{i}. "
        row_style = "bold bright_cyan" if is_player else "white"
        t.add_row(prefix, f"{guild.icon} {guild.name}", guild.guild_type,
                  power_str, moral_str, pop_str, f"[{col}]{rank}[/]", style=row_style)

    tension_bar = "█" * int(gm.world_tension // 4) + "░" * (25 - int(gm.world_tension // 4))
    tension_text = Text(f"\n  Tensión Mundial: [[ {tension_bar} ]] {gm.world_tension:.1f}%\n", style="bold red")

    ev_text = Text("\n")
    if total_pages > 1:
        ev_text.append(f"  Página {page+1}/{total_pages} (↑↓ para cambiar)\n", style="bold yellow")
    ev_text.append("  Últimos eventos del mundo:\n", style="bold dim")
    for ev in gm.world_events[-6:]:
        ev_text.append(f"  • {ev}\n", style="dim")

    return Panel(Group(tension_text, t, Rule(style="dim"), ev_text),
                 title="[bold]🌍 ESTADO DEL MUNDO[/]", border_style="blue"), total_pages


def _render_diplomacy(guild: Guild, gm: GuildManager, player, page: int = 0):
    items_per_page = 8
    all_guilds = [g for gid, g in gm.guilds.items() if gid != guild.guild_id]
    total_pages = max(1, (len(all_guilds) + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_items = all_guilds[start_idx:end_idx]

    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("Guild",    ratio=2)
    t.add_column("Relación", width=10)
    t.add_column("Tu Rep.",  width=12)
    t.add_column("Alianza",  width=8)

    for g in page_items:
        gid = g.guild_id
        relation  = guild.relations.get(gid, 0)
        rep       = gm.get_player_reputation(player, gid)
        rank, col = gm.get_reputation_rank(rep)
        rel_color = "green" if relation >= 30 else ("red" if relation < -20 else "dim white")
        is_ally   = gid in guild.alliances
        ally_str  = "[bold green]✓[/]" if is_ally else "[dim]—[/]"
        t.add_row(f"{g.icon} {g.name}", f"[{rel_color}]{relation:+d}[/]",
                  f"[{col}]{rank}[/]", ally_str)

    hint = Text(f"\n  Página {page+1}/{total_pages} | [F] Formar alianza  |  [S] Sabotear (requiere Espionaje)\n", style="dim")
    return Panel(Group(t, hint), title="[bold]🕊 DIPLOMACIA[/]", border_style="bright_magenta"), total_pages


def _diplomacy_action_menu(player_guild: Guild, player, gm: GuildManager, con):
    all_guilds = [g for gid, g in gm.guilds.items() if gid != player_guild.guild_id]
    state = {
        "idx": 0,
        "exit": False,
        "dirty": True,
        "message": "↑↓: Navegar | [F]: Alianza | [W]: Guerra | [S]: Sabotear | [T]: Comercio | [ESC]: Volver",
        "msg_style": "dim"
    }

    if not all_guilds:
        con.print("\n[bold dim]No hay otras guilds en el mundo.[/]")
        time.sleep(get_menu_refresh_rate())
        return

    def _render():
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("", width=3)
        t.add_column("Guild",    ratio=2)
        t.add_column("Relación", width=10)
        t.add_column("Tu Rep.",  width=12)
        t.add_column("Estado",  width=12)

        for i, g in enumerate(all_guilds):
            sel = (i == state["idx"])
            gid = g.guild_id
            relation  = player_guild.relations.get(gid, 0)
            rep       = gm.get_player_reputation(player, gid)
            rank, col = gm.get_reputation_rank(rep)
            rel_color = "green" if relation >= 30 else ("red" if relation < -20 else "dim white")
            
            is_ally   = gid in player_guild.alliances
            is_war    = gid in getattr(player_guild, "at_war_with", [])
            
            if is_ally:
                status = "[bold cyan]Alianza[/]"
            elif is_war:
                status = "[bold red]En Guerra[/]"
            elif rep <= -5:
                status = "[bold yellow]Enemiga[/]"
            elif rep >= 20:
                status = "[bold blue]Aliada[/]"
            else:
                status = "[white]Neutral[/]"

            prefix = "▶" if sel else " "
            nm = Text(f"{g.icon} {g.name}")
            if sel: nm.stylize("bold reverse")
            
            t.add_row(prefix, nm, f"[{rel_color}]{relation:+d}[/]", f"[{col}]{rank}[/]", status)

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(Group(t, footer), 
                     title=f"[bold magenta]🕊 DIPLOMACIA — {player_guild.icon} {player_guild.name}[/]", 
                     border_style="magenta")

    def _on_press(key):
        state["dirty"] = True
        if key == "esc":
            state["exit"] = True
        elif key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(all_guilds) - 1, state["idx"] + 1)
        elif key == "f":
            g = all_guilds[state["idx"]]
            if g.guild_id in player_guild.alliances:
                state["message"] = "Ya estás en alianza."
                state["msg_style"] = "bold yellow"
            elif g.guild_id in getattr(player_guild, "at_war_with", []):
                state["message"] = "No puedes aliarte con un enemigo en guerra."
                state["msg_style"] = "bold red"
            else:
                rep = gm.get_player_reputation(player, g.guild_id)
                if rep >= 20 and player_guild.relations.get(g.guild_id, 0) >= 30:
                    player_guild.alliances.append(g.guild_id)
                    g.alliances.append(player_guild.guild_id)
                    state["message"] = f"¡Alianza formada con {g.name}!"
                    state["msg_style"] = "bold green"
                    gm.world_events.append(f"🕊 {player_guild.name} y {g.name} han formado una alianza formal.")
                else:
                    state["message"] = "Requiere +20 de Reputación y +30 de Relación de Guild."
                    state["msg_style"] = "bold red"
        elif key == "w":
            g = all_guilds[state["idx"]]
            if g.guild_id in player_guild.alliances:
                state["message"] = "Debes romper la alianza primero."
                state["msg_style"] = "bold yellow"
            elif g.guild_id in getattr(player_guild, "at_war_with", []):
                state["message"] = "Ya estás en guerra."
                state["msg_style"] = "bold yellow"
            else:
                cfg = _get_guild_config()
                formal_penalty = cfg.get("FORMAL_WAR_PENALTY", 0)
                
                player_guild.at_war_with.append(g.guild_id)
                g.at_war_with.append(player_guild.guild_id)
                
                if formal_penalty > 0:
                    if g.guild_id in player_guild.relations:
                        player_guild.relations[g.guild_id] = max(-100, player_guild.relations[g.guild_id] - formal_penalty)
                    else:
                        player_guild.relations[g.guild_id] = -formal_penalty
                        
                state["message"] = f"Has declarado Guerra Formal a {g.name}."
                state["msg_style"] = "bold red"
                gm.world_events.append(f"⚔ ¡GUERRA FORMAL! {player_guild.name} le ha declarado la guerra a {g.name}.")
                gm.world_tension = min(100.0, gm.world_tension + 5.0)
        elif key == "s":
            # Sabotaje
            g = all_guilds[state["idx"]]
            if "dip_espionage" not in player_guild.unlocked_skills:
                state["message"] = "Requiere la habilidad 'Espionaje'."
                state["msg_style"] = "bold red"
            elif g.guild_id in player_guild.alliances:
                state["message"] = "No puedes sabotear a un aliado."
                state["msg_style"] = "bold yellow"
            else:
                # Éxito basado en moral y habilidad shadows
                chance = 0.4 + (0.2 if "dip_shadows" in player_guild.unlocked_skills else 0.0)
                if random.random() < chance:
                    damage = random.randint(5, 15)
                    g.change_moral(-damage)
                    # Robar algo de recursos
                    stolen = random.randint(10, 30)
                    g.consume_resource("oro", stolen)
                    player_guild.add_resource("oro", stolen, gm.resource_defs)
                    state["message"] = f"¡Éxito! Sabotaje a {g.name}: -{damage} Moral y robar {stolen} Oro."
                    state["msg_style"] = "bold green"
                    gm.change_player_reputation(player, g.guild_id, -10)
                else:
                    state["message"] = f"Fracaso. Tu espía en {g.name} fue capturado."
                    state["msg_style"] = "bold red"
                    gm.change_player_reputation(player, g.guild_id, -25)
                    player_guild.change_moral(-5)
        elif key == "t":
            g = all_guilds[state["idx"]]
            _custom_trade_menu(player_guild, g, player, gm, con)
            state["dirty"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()


# ── Función auxiliar de loop de Live ─────────────────────────────────────────
# (cada función interna usa el patrón directamente, sin helper compartido)


# ── Pantallas interactivas de acción ──────────────────────────────────────────

import random
from Modules.ModulesUtils.input_utils import get_menu_refresh_rate


def _territories_action_menu(player_guild: Guild, player, gm: GuildManager, con):
    """Pantalla interactiva para conquistar o ver territorios."""
    
    def get_terr_status_and_priority(terr):
        is_own = terr.owner == player_guild.guild_id
        if is_own:
            return 0, "[bold green]★ Tuyo[/]", "green", f"[bold green]{player_guild.icon} {player_guild.name}[/]"
        elif terr.owner == "neutral":
            return 5, "[dim]Libre[/]", "white", "[dim]Neutral[/]"
        else:
            og = gm.guilds.get(terr.owner)
            owner_str = f"{og.icon} {og.name}" if og else "??"
            if terr.owner in player_guild.alliances:
                return 1, "[bold cyan]Alianza[/]", "cyan", owner_str
            elif terr.owner in getattr(player_guild, "at_war_with", []):
                return 6, "[bold red]En Guerra[/]", "red", owner_str
            else:
                rep = gm.get_player_reputation(player, terr.owner)
                if rep >= 20:
                    return 2, "[bold blue]Aliada[/]", "blue", owner_str
                elif rep <= -5:
                    return 4, "[bold yellow]Enemiga[/]", "yellow", owner_str
                else:
                    return 3, "[white]Neutral[/]", "white", owner_str

    all_territories = sorted(gm.territories.values(), key=lambda t: (get_terr_status_and_priority(t)[0], t.name))
    
    state = {
        "idx":       0,
        "exit":      False,
        "confirm_war": None,
        "page":      0,
        "message":   "↑↓←→: Navegar | [ENTER]: Atacar | [U]: Mejorar (tuyo) | [ESC]: Volver",
        "msg_style": "dim",
    }

    def _render():
        # Calcula cuántas filas caben en la terminal (max 10)
        try:
            term_h = os.get_terminal_size().lines
        except OSError:
            term_h = 40
        # ~11 líneas de overhead (título, header tabla, detalle, footer, bordes)
        overhead = 11
        items_per_page = max(3, min(10, term_h - overhead))

        total = len(all_territories)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)

        # La página se sincroniza automáticamente al índice seleccionado
        page = state["idx"] // items_per_page
        start = page * items_per_page
        end   = min(start + items_per_page, total)
        visible = all_territories[start:end]

        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("",            width=3)
        t.add_column("Territorio",  ratio=2)
        t.add_column("Dueño",       ratio=2)
        t.add_column("Producción",  ratio=3)
        t.add_column("Dif",         width=5)
        t.add_column("Estado",      width=12)

        for terr in visible:
            real_i = all_territories.index(terr)
            sel    = real_i == state["idx"]
            prio, status, s_color, owner_str = get_terr_status_and_priority(terr)
            res_str = f"Nv.{terr.level} → mat. Tier {TIER_ROMAN.get(terr.level, 'I')}"
            nm = Text(f"{terr.icon} {terr.name}")
            if sel:
                nm.stylize("bold reverse")
            t.add_row(
                "▶" if sel else " ",
                nm, owner_str, res_str,
                str(terr.difficulty), status,
                style="bold bright_cyan" if sel else s_color,
            )

        # Detalle del seleccionado
        if all_territories:
            terr   = all_territories[state["idx"]]
            is_own = terr.owner == player_guild.guild_id
            detail = Text()
            detail.append(f"\n  {terr.icon} {terr.name} — {terr.description}\n", style="bold cyan")
            if not is_own:
                cost_t1 = terr.difficulty * 8
                cost_t2 = terr.difficulty * 5
                detail.append(f"  Coste de ataque: {cost_t1} mat. Tier I + {cost_t2} mat. Tier II\n", style="yellow")
                detail.append(f"  Poder militar tu guild: {player_guild.military_power}  |  Defensa: {terr.defense_value}\n", style="dim")
                detail.append("  [ENTER] Atacar\n", style="bold bright_cyan")
            else:
                detail.append(f"  Nivel {terr.level}/{MAX_TERRITORY_LEVEL} — produce materiales Tier {TIER_ROMAN.get(terr.level,'I')}\n", style="green")
                if terr.level < MAX_TERRITORY_LEVEL:
                    cost = terr.upgrade_cost()
                    (tk, amt), = cost.items()
                    tr = tk.split("_", 1)[1]
                    detail.append(f"  Mejora a Nv.{terr.level+1}: {amt} materiales Tier {tr} (de tu inventario)\n", style="yellow")
                    detail.append("  [U] Mejorar territorio (recolecta los materiales a mano)\n", style="bold bright_green")
                else:
                    detail.append("  Nivel máximo alcanzado.\n", style="dim")
        else:
            detail = Text("Sin territorios disponibles.", style="dim")

        page_hint = Text(f"  Pág. {page+1}/{total_pages} — {total} territorios totales", style="dim")
        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(
            Group(t, Rule(style="dim"), detail, page_hint, footer),
            title="[bold green]🗺 TERRITORIOS — ATACAR / DEFENDER[/]",
            border_style="green",
        )

    def _on_press(key):
        state["dirty"] = True
        if key != "enter":
            state["confirm_war"] = None
            
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(all_territories) - 1, state["idx"] + 1)
        elif key == "left" or key == "right":
            # Calcular items_per_page para el salto de página
            try:
                term_h = os.get_terminal_size().lines
            except OSError:
                term_h = 40
            overhead = 11
            items_per_page = max(3, min(10, term_h - overhead))
            
            if key == "left":
                new_idx = state["idx"] - items_per_page
                if new_idx < 0:
                    state["idx"] = len(all_territories) - 1
                else:
                    state["idx"] = new_idx
            else:
                new_idx = state["idx"] + items_per_page
                if new_idx >= len(all_territories):
                    state["idx"] = 0
                else:
                    state["idx"] = new_idx
        elif key == "u" and all_territories:
            # Mejorar territorio propio (consume materiales del inventario del jugador)
            terr = all_territories[state["idx"]]
            ok, msg = gm.upgrade_territory(terr, player, vInventory)
            state["message"]   = msg
            state["msg_style"] = "bold green" if ok else "bold red"
        elif key == "enter" and all_territories:
            terr  = all_territories[state["idx"]]
            is_own = terr.owner == player_guild.guild_id
            if is_own:
                state["message"]   = "✗ Ya controlas este territorio."
                state["msg_style"] = "bold yellow"
                return
            
            if terr.owner in player_guild.alliances:
                state["message"]   = "✗ ¡No puedes atacar a un aliado! Rompe la alianza primero."
                state["msg_style"] = "bold red"
                return
                
            is_war = terr.owner in getattr(player_guild, "at_war_with", [])
            is_neutral_zone = terr.owner == "neutral"
            
            cfg = _get_guild_config()
            surprise_penalty = cfg.get("SURPRISE_WAR_PENALTY", 20)
            
            if not is_neutral_zone and not is_war:
                if state.get("confirm_war") != terr.id:
                    state["confirm_war"] = terr.id
                    gname = gm.guilds[terr.owner].name if terr.owner in gm.guilds else "Desconocido"
                    state["message"] = f"¿Declarar GUERRA SORPRESA a {gname}? (-{surprise_penalty} Reputación Global) [ENTER] para confirmar."
                    state["msg_style"] = "bold red on yellow"
                    return
                else:
                    state["confirm_war"] = None
                    player_guild.at_war_with.append(terr.owner)
                    if terr.owner in gm.guilds:
                        gm.guilds[terr.owner].at_war_with.append(player_guild.guild_id)
                    for gid in gm.guilds:
                        if gid == player_guild.guild_id: continue
                        if gid in player_guild.relations:
                            player_guild.relations[gid] = max(-100, player_guild.relations[gid] - surprise_penalty)
                        else:
                            player_guild.relations[gid] = -surprise_penalty
                    gm.world_events.append(f"💥 ¡{player_guild.name} ha declarado una GUERRA SORPRESA! El mundo los desprecia.")
            # Atacar cuesta materiales: Tier I (suministros) + Tier II (armamento)
            cost_t1 = terr.difficulty * 8
            cost_t2 = terr.difficulty * 5
            attack_cost = {"tier_I": cost_t1, "tier_II": cost_t2}
            if not player_guild.can_afford_tier_cost(attack_cost):
                state["message"]   = f"✗ Necesitas {cost_t1} mat. Tier I y {cost_t2} mat. Tier II para atacar."
                state["msg_style"] = "bold red"
                return
            player_guild.pay_tier_cost(attack_cost)
            # Resolver ataque
            msg = gm._attack_territory(player_guild, gm.guilds.get(terr.owner) if terr.owner not in ("neutral","") else None, terr)
            state["message"]   = msg
            state["msg_style"] = "bold green" if player_guild.guild_id == terr.owner else "bold red"
        elif key == "esc":
            state["exit"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()


def _buildings_menu(player_guild: Guild, gm: GuildManager, con):
    """Menú de construcciones de Guild. Los edificios usan materiales de Guild."""
    if not hasattr(player_guild, "buildings"):
        player_guild.buildings = []

    building_ids = list(GUILD_BUILDINGS.keys())
    state = {
        "idx":       0,
        "exit":      False,
        "message":   "↑↓: Navegar | [ENTER]: Construir | [ESC]: Volver",
        "msg_style": "dim",
    }

    def _can_build(bid):
        b = GUILD_BUILDINGS[bid]
        if b.get("unique") and bid in player_guild.buildings:
            return False, "Ya construido"
        for rid, qty in b["cost"].items():
            if player_guild.get_resource(rid) < qty:
                rname = gm.resource_defs.get(rid, {}).get("name", rid)
                return False, f"Faltan {rname}"
        return True, "Disponible"

    def _render():
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("",            width=3)
        t.add_column("Edificio",    ratio=2)
        t.add_column("Descripción", ratio=3)
        t.add_column("Coste",       ratio=2)
        t.add_column("Estado",      width=14)

        for i, bid in enumerate(building_ids):
            b   = GUILD_BUILDINGS[bid]
            sel = i == state["idx"]
            ok, reason = _can_build(bid)
            built = bid in player_guild.buildings

            cost_str = "  ".join(
                f"{gm.resource_defs.get(r,{}).get('icon','?')} {q} {gm.resource_defs.get(r,{}).get('name',r)}"
                for r, q in b["cost"].items()
            )

            if built:
                s_col  = "bold green"
                s_text = "[bold green]✓ CONSTRUIDO[/]"
            elif ok:
                s_col  = "white"
                s_text = "[dim]Disponible[/]"
            else:
                s_col  = "dim"
                s_text = f"[dim red]{reason}[/]"

            nm = Text(f"{b['icon']} {b['name']}")
            if sel:
                nm.stylize("bold reverse")
            t.add_row(
                "▶" if sel else " ",
                nm, b["description"], cost_str, s_text,
                style="bold bright_cyan" if sel else s_col,
            )

        # Log de edificios activos
        active = Text("\n  Edificios activos: ")
        if player_guild.buildings:
            for bid in player_guild.buildings:
                b = GUILD_BUILDINGS.get(bid, {})
                active.append(f"{b.get('icon','?')} {b.get('name','?')}  ", style="green")
        else:
            active.append("Ninguno aún.", style="dim")

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(
            Group(t, active, footer),
            title="[bold]🏗 CONSTRUCCIONES DE GUILD[/]",
            border_style="bright_yellow",
        )

    def _on_press(key):
        state["dirty"] = True
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(building_ids) - 1, state["idx"] + 1)
        elif key == "enter":
            bid = building_ids[state["idx"]]
            ok, reason = _can_build(bid)
            if not ok:
                state["message"]   = f"✗ No se puede construir: {reason}"
                state["msg_style"] = "bold red"
                return
            b = GUILD_BUILDINGS[bid]
            for rid, qty in b["cost"].items():
                player_guild.consume_resource(rid, qty)
            player_guild.buildings.append(bid)
            # Aplicar efectos inmediatos
            for eff_key, eff_val in b["effect"].items():
                if eff_key == "military_power" and isinstance(eff_val, int):
                    player_guild.military_power += eff_val
            player_guild.log_event(f"🏗 Construido: {b['icon']} {b['name']}")
            state["message"]   = f"✓ {b['icon']} {b['name']} construido."
            state["msg_style"] = "bold green"
        elif key == "esc":
            state["exit"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()


# ── Menú sin guild ────────────────────────────────────────────────────────────

def _no_guild_menu(player, gm: GuildManager, con) -> str:
    """Pantalla cuando el jugador no tiene guild. Retorna: 'create'|'join'|'back'."""
    options = ["Crear mi propia Guild", "Unirme a una Guild existente", "Volver"]
    state   = {"idx": 0, "exit": False, "action": "back"}

    def _render():
        t = Table(show_header=False, box=None, expand=True, padding=(0, 2))
        for i, opt in enumerate(options):
            if i == state["idx"]:
                t.add_row(f"[bold bright_cyan]▶ {opt}[/]")
            else:
                t.add_row(f"  [dim]{opt}[/]")
        intro = Text(
            "\n  No perteneces a ninguna guild.\n"
            "  Puedes crear la tuya o unirte a una existente.\n",
            style="dim",
        )
        hint = Text("\n  ↑↓: Navegar | [ENTER]: Confirmar | [ESC]: Volver\n", style="dim")
        return Panel(Group(intro, t, hint),
                     title="[bold cyan]⚔ SISTEMA DE GUILDS[/]",
                     border_style="cyan", padding=(1, 2))

    def _on_press(key):
        state["dirty"] = True
        if key == "up":
            state["idx"] = (state["idx"] - 1) % len(options)
        elif key == "down":
            state["idx"] = (state["idx"] + 1) % len(options)
        elif key == "enter":
            if state["idx"] == 0:
                state["action"] = "create"
            elif state["idx"] == 1:
                state["action"] = "join"
            else:
                state["action"] = "back"
            state["exit"] = True
        elif key == "esc":
            state["action"] = "back"
            state["exit"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()

    return state["action"]


# ── Crear guild ───────────────────────────────────────────────────────────────

def _create_guild_flow(player, gm: GuildManager, con) -> Optional[Guild]:
    guild_types = list(gm.guild_type_defs.keys())
    state = {"type_idx": 0, "name": "", "mode": "type", "done": False, "action": None}

    def _render():
        if state["mode"] == "type":
            t = Table(show_header=False, box=None, expand=True, padding=(0, 2))
            for i, gt in enumerate(guild_types):
                defn = gm.guild_type_defs[gt]
                icon = defn.get("icon", "?")
                desc = defn.get("description", "")
                if i == state["type_idx"]:
                    t.add_row(f"[bold bright_cyan]▶ {icon} {gt}[/]", f"[dim]{desc}[/]")
                else:
                    t.add_row(f"  [dim]{icon} {gt}[/]", f"[dim]{desc}[/]")
            hint = Text("\n  ↑↓: Navegar | [ENTER]: Elegir | [ESC]: Cancelar\n", style="dim")
            return Panel(Group(Text("\n Elige el tipo de tu guild:\n", style="bold"), t, hint),
                         title="[bold cyan]✨ CREAR GUILD[/]", border_style="cyan", padding=(1, 2))
        else:
            name_display = state["name"] + "█"
            hint = Text("\n  Escribe y [ENTER] para confirmar | [ESC] para volver\n", style="dim")
            return Panel(
                Group(Text(f"\n  Nombre: {name_display}\n", style="white bold"), hint),
                title="[bold cyan]✨ NOMBRE DE TU GUILD[/]",
                border_style="cyan", padding=(1, 2),
            )

    def _on_press(key):
        state["dirty"] = True
        if state["mode"] == "type":
            if key == "up":
                state["type_idx"] = (state["type_idx"] - 1) % len(guild_types)
            elif key == "down":
                state["type_idx"] = (state["type_idx"] + 1) % len(guild_types)
            elif key == "enter":
                state["mode"] = "name"
            elif key == "esc":
                state["action"] = "cancel"
                state["done"]   = True
        else:
            if key == "esc":
                state["mode"] = "type"
            elif key == "enter" and state["name"].strip():
                state["action"] = "confirm"
                state["done"]   = True
            elif key == "backspace":
                state["name"] = state["name"][:-1]
            elif len(key) == 1 and len(state["name"]) < 30:
                state["name"] += key

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["done"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()

    if state["action"] == "confirm":
        guild_type = guild_types[state["type_idx"]]
        return gm.create_player_guild(state["name"].strip(), guild_type, player)
    return None


# ── Unirse a guild ────────────────────────────────────────────────────────────

def _join_guild_flow(player, gm: GuildManager, con) -> Optional[Guild]:
    guilds = [g for g in gm.guilds.values() if not g.is_player_guild]
    if not guilds:
        return None

    state = {"idx": 0, "done": False, "action": None}

    def _render():
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("",      width=3)
        t.add_column("Guild", ratio=2)
        t.add_column("Tipo",  width=12)
        t.add_column("Poder", width=8)
        t.add_column("Terr.", width=6)
        for i, g in enumerate(guilds):
            sel  = i == state["idx"]
            nm   = Text(f"{g.icon} {g.name}")
            if sel:
                nm.stylize("bold reverse")
            t.add_row("▶" if sel else " ", nm, g.guild_type,
                      str(g.military_power), str(len(g.territories)),
                      style="bold bright_cyan" if sel else "white")
        hint = Text("\n  ↑↓: Navegar | [ENTER]: Unirse | [ESC]: Cancelar\n", style="dim")
        return Panel(Group(t, hint), title="[bold cyan]🤝 UNIRSE A UNA GUILD[/]", border_style="cyan")

    def _on_press(key):
        state["dirty"] = True
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(guilds) - 1, state["idx"] + 1)
        elif key == "enter":
            state["action"] = "join"
            state["done"]   = True
        elif key == "esc":
            state["action"] = "cancel"
            state["done"]   = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["done"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()

    if state["action"] == "join":
        chosen = guilds[state["idx"]]
        gm.join_guild(chosen.guild_id, player)
        return chosen
    return None


# ── Menú principal con pestañas ───────────────────────────────────────────────

def _main_guild_tabs(player_guild: Guild, player, gm: GuildManager, con) -> str:
    """
    Menú con pestañas para la guild del jugador.
    Retorna acción seleccionada.
    """
    tabs  = ["Resumen", "Territorios", "Recursos", "Mundo", "Mercado y Trueques", "Comercio", "Misiones", "Militar", "Habilidades", "Diplomacia", "Construcciones"]
    state = {
        "tab_idx":        0,
        "exit":           False,
        "inner_action":   "exit",
        "open_sub":       None,
        "message":        f"{player_guild.icon} {player_guild.name}  |  Skill pts: {player_guild.skill_points}  |  Eventos: {len(player_guild.pending_events)}",
        "msg_style":      "bold bright_cyan" if player_guild.pending_events else "dim",
        "page":           0,
        "total_pages":    1,
        "dirty":          True,
    }

    def _render():
        # Pestañas
        h = Text()
        for i, tab in enumerate(tabs):
            if i == state["tab_idx"]:
                h.append(f" {tab} ", style="bold black on bright_cyan")
            else:
                h.append(f" {tab} ", style="dim")
            if i < len(tabs) - 1:
                h.append("  ")

        tab = tabs[state["tab_idx"]]
        state["total_pages"] = 1
        if tab == "Resumen":
            content = _render_summary(player_guild, player, gm)
        elif tab == "Territorios":
            content, state["total_pages"] = _render_territories(player_guild, gm, state["page"])
        elif tab == "Recursos":
            content = _render_resources(player_guild, gm)
        elif tab == "Mundo":
            content, state["total_pages"] = _render_world(gm, player, state["page"])
        elif tab == "Habilidades":
            content = Panel(
                Text("\n  Pulsa [ENTER] para abrir el árbol de habilidades.\n", style="dim"),
                border_style="cyan",
            )
        elif tab == "Comercio":
            content = Panel(
                Text("\n  Pulsa [ENTER] para vender excedentes a otras Guilds.\n", style="dim"),
                border_style="yellow",
            )
        elif tab == "Militar":
            content = Panel(
                Text("\n  Pulsa [ENTER] para gestionar tu ejército.\n", style="dim"),
                border_style="red",
            )
        elif tab == "Misiones":
            content = Panel(
                Text("\n  Pulsa [ENTER] para abrir el gestor de misiones.\n", style="dim"),
                border_style="yellow",
            )
        elif tab == "Diplomacia":
            content = Panel(
                Text("\n  Pulsa [ENTER] para gestionar Diplomacia y Tradeos personalizados.\n", style="dim"),
                border_style="magenta",
            )
        elif tab == "Mercado":
            content = _render_market_preview(player_guild, gm)
        else:
            content = Panel(Text("Próximamente.", style="dim"))

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        hint   = Text("← →: Pestañas | [ENTER]: Acción | [O]: Config. Taxes | [M]: Eventos | [ESC]: Salir", style="dim")
        return Panel(
            Group(h, Rule(style="cyan"), content, hint, footer),
            title=f"[bold cyan]⚔ GUILDS — {player_guild.icon} {player_guild.name}[/]",
            border_style="cyan",
        )

    def _on_press(key):
        state["dirty"] = True
        if key == "left":
            state["tab_idx"] = (state["tab_idx"] - 1) % len(tabs)
        elif key == "right":
            state["tab_idx"] = (state["tab_idx"] + 1) % len(tabs)
        elif key == "enter":
            tab = tabs[state["tab_idx"]]
            if tab == "Habilidades":
                state["open_sub"] = "skill_tree"
                state["exit"]     = True
            elif tab == "Misiones":
                state["open_sub"] = "missions"
                state["exit"]     = True
            elif tab == "Territorios":
                state["open_sub"] = "territories"
                state["exit"]     = True
            elif tab == "Comercio":
                state["open_sub"] = "commerce"
                state["exit"]     = True
            elif tab == "Construcciones":
                state["open_sub"] = "buildings"
                state["exit"]     = True
            elif tab == "Militar":
                state["open_sub"] = "military"
                state["exit"]     = True
            elif tab == "Diplomacia":
                state["open_sub"] = "diplomacy"
                state["exit"]     = True
            elif tab == "Mercado y Trueques":
                state["open_sub"] = "market"
                state["exit"]     = True
        elif key == "m":
            state["open_sub"] = "events"
            state["exit"]     = True
        elif key == "o":
            state["open_sub"] = "taxes"
            state["exit"]     = True
        elif key == "esc":
            state["open_sub"] = None
            state["exit"]     = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive():
                        kb_thread.join(timeout=0.2)
            con.clear()

    return state["open_sub"] or "exit"


def _commerce_menu(player_guild: Guild, player, gm: GuildManager, con):
    """Menú para vender excedentes de recursos a otras Guilds."""
    resources = list(player_guild.resources.values())
    # Filtrar recursos con cantidad > 0 y que no sean Oro
    resources = [r for r in resources if r.amount > 0 and r.resource_id != "oro"]
    
    state = {
        "idx":       0,
        "exit":      False,
        "message":   "↑↓: Elegir Recurso | [Z]: Vender 10 | [X]: Vender 50 | [C]: Vender 200 | [ESC]: Volver",
        "msg_style": "dim"
    }

    def _render():
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("", width=3)
        t.add_column("Recurso", ratio=2)
        t.add_column("Cantidad", ratio=1)
        t.add_column("Precio/u", ratio=1)
        t.add_column("Total Potencial", ratio=2)

        prices = {"Common": 2, "Uncommon": 5, "Rare": 15, "Legendary": 50}

        for i, res in enumerate(resources):
            sel = (i == state["idx"])
            rarity = res.rarity
            price = prices.get(rarity, 2)
            
            nm = Text(f"{res.icon} {res.name}")
            if sel: nm.stylize("bold reverse")
            
            t.add_row(
                "▶" if sel else " ",
                nm,
                str(res.amount),
                f"💰{price}",
                f"💰{res.amount * price}",
                style="bold yellow" if sel else "white"
            )

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(Group(t, footer), title="[bold yellow]⚖ COMERCIO EXTERNO[/]", border_style="yellow")

    def _on_press(key):
        state["dirty"] = True
        if key == "esc":
            state["exit"] = True
        elif key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(resources) - 1, state["idx"] + 1)
        elif key in ["z", "x", "c"] and resources:
            res = resources[state["idx"]]
            amt = 10 if key == "z" else (50 if key == "x" else 200)
            
            ok, msg = gm.sell_surplus_resources(player_guild, res.resource_id, amt, player)
            state["message"] = msg
            state["msg_style"] = "bold green" if ok else "bold red"

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
            con.clear()


# ── Pestaña Eventos ──────────────────────────────────────────────────────────

def _events_menu(player_guild: Guild, player, gm: GuildManager, con):
    state = {
        "idx":       0,
        "exit":      False,
        "message":   "↑↓: Navegar | [ENTER]: Seleccionar opción | [ESC]: Volver",
        "msg_style": "dim",
        "opt_idx":   0,
        "mode":      "list",  # "list" o "detail"
    }

    def _render():
        if state["mode"] == "list":
            if not player_guild.pending_events:
                return Panel(Text("\n  No hay eventos pendientes.\n", style="dim"),
                             title="[bold bright_cyan]📬 EVENTOS PENDIENTES[/]", border_style="cyan")
            t = Table(show_header=False, box=None, expand=True)
            for i, ev in enumerate(player_guild.pending_events):
                sel = i == state["idx"]
                nm = Text(f"✉ {ev['title']}")
                if sel: nm.stylize("bold reverse")
                t.add_row("▶" if sel else " ", nm, style="bold bright_cyan" if sel else "white")
            hint = Text("\n  [ENTER] Ver detalles | [ESC] Volver\n", style="dim")
            return Panel(Group(t, hint), title="[bold bright_cyan]📬 EVENTOS PENDIENTES[/]", border_style="cyan")
        else:
            ev = player_guild.pending_events[state["idx"]]
            t = Table(show_header=False, box=None, expand=True, padding=(0, 2))
            for i, opt in enumerate(ev["options"]):
                sel = i == state["opt_idx"]
                nm = Text(f"{i+1}. {opt['text']}")
                if sel: nm.stylize("bold reverse")
                t.add_row("▶" if sel else " ", nm, style="bold bright_cyan" if sel else "dim")
            
            desc = Text(f"\n  {ev['description']}\n\n", style="white")
            hint = Text("  ↑↓: Elegir opción | [ENTER]: Confirmar | [ESC]: Volver a lista\n", style="dim")
            return Panel(Group(desc, t, hint), title=f"[bold cyan]📬 {ev['title']}[/]", border_style="cyan")

    def _on_press(key):
        state["dirty"] = True
        if key == "esc":
            if state["mode"] == "detail":
                state["mode"] = "list"
            else:
                state["exit"] = True
        elif state["mode"] == "list" and player_guild.pending_events:
            if key == "up":
                state["idx"] = max(0, state["idx"] - 1)
            elif key == "down":
                state["idx"] = min(len(player_guild.pending_events) - 1, state["idx"] + 1)
            elif key == "enter":
                state["mode"] = "detail"
                state["opt_idx"] = 0
        elif state["mode"] == "detail":
            ev = player_guild.pending_events[state["idx"]]
            if key == "up":
                state["opt_idx"] = max(0, state["opt_idx"] - 1)
            elif key == "down":
                state["opt_idx"] = min(len(ev["options"]) - 1, state["opt_idx"] + 1)
            elif key == "enter":
                # Aplicar efectos
                opt = ev["options"][state["opt_idx"]]
                eff = opt.get("effects", {})
                for k, v in eff.items():
                    if k == "soldiers" or k == "military_power": player_guild.military_power = max(0, player_guild.military_power + v)
                    elif k == "population":   player_guild.population = max(10, player_guild.population + v)
                    elif k == "moral":        player_guild.change_moral(v)
                    elif k == "rel_src":
                        if ev["source_guild_id"]:
                            player_guild.relations[ev["source_guild_id"]] = max(-100, min(100, player_guild.relations.get(ev["source_guild_id"], 0) + v))
                            if ev["source_guild_id"] in gm.guilds:
                                gm.guilds[ev["source_guild_id"]].relations[player_guild.guild_id] = player_guild.relations[ev["source_guild_id"]]
                    elif k == "rel_all":
                        for gid in gm.guilds:
                            player_guild.relations[gid] = max(-100, min(100, player_guild.relations.get(gid, 0) + v))
                    elif k == "trade_accept":
                        offer_rid = eff.get("offer_rid")
                        offer_amt = eff.get("offer_amt")
                        req_rid   = eff.get("req_rid")
                        req_amt   = eff.get("req_amt")
                        if offer_rid and req_rid:
                            if player_guild.get_resource(req_rid) >= req_amt:
                                player_guild.consume_resource(req_rid, req_amt)
                                player_guild.add_resource(offer_rid, offer_amt, gm.resource_defs)
                                player_guild.log_event(f"🤝 Trade completado con éxito.")
                                if ev["source_guild_id"] in gm.guilds:
                                    g = gm.guilds[ev["source_guild_id"]]
                                    g.consume_resource(offer_rid, offer_amt)
                                    g.add_resource(req_rid, req_amt, gm.resource_defs)
                            else:
                                player_guild.log_event(f"✗ Trade fallido: no tienes suficientes recursos.")
                    elif k in ("src_id", "offer_rid", "offer_amt", "req_rid", "req_amt"):
                        pass  # Ignorar claves de metadatos usadas por otros efectos
                    elif isinstance(k, str) and k.startswith("tier_"):
                        # Efecto en materiales por tier (ej. "tier_I": 30)
                        tier_n = ROMAN_TIER.get(k.split("_", 1)[1], 1)
                        if v > 0:
                            pool = gm.tier_materials.get(tier_n, [])
                            if pool:
                                player_guild.add_resource(pool[0], int(v), gm.resource_defs)
                        else:
                            player_guild.consume_tier(tier_n, abs(int(v)))
                    else:
                        # Asumir que es un id de material (recurso)
                        if isinstance(v, (int, float)):
                            if v > 0: player_guild.add_resource(k, v, gm.resource_defs)
                            else:     player_guild.consume_resource(k, abs(v))
                player_guild.pending_events.pop(state["idx"])
                state["idx"] = max(0, state["idx"] - 1)
                state["mode"] = "list"

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
                    con.clear()

# ── Pestaña Militar ──────────────────────────────────────────────────────────

def _military_management_menu(player_guild: Guild, player, gm: GuildManager, con):
    sections = [
        "Reclutar Infantería", "Reclutar Arqueros", "Reclutar Caballería", "Reclutar Asedio",
        "Gestionar Guarniciones",
        "Mejorar Ataque", "Mejorar Defensa", "Mejorar Armadura"
    ]
    state = {
        "idx":       0,
        "exit":      False,
        "dirty":     True,
        "message":   "↑↓: Navegar | [ENTER]: Confirmar | [ESC]: Volver",
        "msg_style": "dim",
        "rec_amt":   5,
        "action":    None
    }

    def _render():
        t = Table(show_header=False, box=None, expand=True)
        max_sol = player_guild.get_max_soldiers(gm.guild_type_defs)
        
        inf = player_guild.soldiers.get("infantry", 0)
        arc = player_guild.soldiers.get("archers", 0)
        cav = player_guild.soldiers.get("cavalry", 0)
        sie = player_guild.soldiers.get("siege", 0)
        
        info = Text(f"  Poder Militar: {player_guild.military_power}  |  Soldados Totales: {player_guild.get_total_soldiers()} / {max_sol}\n"
                    f"  Infantería: {inf}  |  Arqueros: {arc}  |  Caballería: {cav}  |  Asedio: {sie}\n"
                    f"  Ataque Lv.{player_guild.attack_rating}  |  Defensa Lv.{player_guild.defense_rating}  |  Armadura Lv.{player_guild.armor_rating}\n", style="bold cyan")
        
        for i, sec in enumerate(sections):
            sel = i == state["idx"]
            nm  = Text(sec)
            desc = ""
            if sec.startswith("Reclutar"):
                n = state['rec_amt']
                desc = f" (Coste: {n} mat. Tier I, {max(1, n//2)} mat. Tier II) [+ {n}]"
            elif sec == "Gestionar Guarniciones":
                desc = " (Asignar tropas a territorios controlados)"
            elif sec == "Mejorar Ataque":
                desc = f" (Coste: {5 * player_guild.attack_rating} mat. Tier II)"
            elif sec == "Mejorar Defensa":
                desc = f" (Coste: {5 * player_guild.defense_rating} mat. Tier II)"
            elif sec == "Mejorar Armadura":
                desc = f" (Coste: {4 * player_guild.armor_rating} mat. Tier III)"
            
            if sel: nm.stylize("bold reverse")
            t.add_row("▶" if sel else " ", nm, Text(desc, style="dim"), style="bold bright_cyan" if sel else "white")
        
        hint = Text("\n  ← →: Ajustar cantidad (Reclutar) | [ENTER]: Aplicar | [ESC]: Volver\n", style="dim")
        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(Group(info, t, hint, footer), title="[bold red]⚔ ADMINISTRACIÓN MILITAR V3[/]", border_style="red")

    def _on_press(key):
        state["dirty"] = True
        if key == "esc":
            state["exit"] = True
        elif key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(sections) - 1, state["idx"] + 1)
        elif key == "left":
            sec = sections[state["idx"]]
            if sec.startswith("Reclutar"):
                state["rec_amt"] = max(1, state["rec_amt"] - 1)
        elif key == "right":
            sec = sections[state["idx"]]
            if sec.startswith("Reclutar"):
                state["rec_amt"] = min(50, state["rec_amt"] + 1)
        elif key == "enter":
            sec = sections[state["idx"]]
            if sec.startswith("Reclutar"):
                troop_map = {"Reclutar Infantería": "infantry", "Reclutar Arqueros": "archers", "Reclutar Caballería": "cavalry", "Reclutar Asedio": "siege"}
                n, msg = player_guild.recruit_soldiers(troop_map[sec], state["rec_amt"], gm.resource_defs, gm.guild_type_defs)
                state["message"] = msg
                state["msg_style"] = "bold green" if n > 0 else "bold red"
            elif sec == "Gestionar Guarniciones":
                state["exit"] = True
                state["action"] = "garrison"
            elif sec == "Mejorar Ataque":
                ok, msg = player_guild.upgrade_army_stat("attack", gm.resource_defs)
                state["message"] = msg
                state["msg_style"] = "bold green" if ok else "bold red"
            elif sec == "Mejorar Defensa":
                ok, msg = player_guild.upgrade_army_stat("defense", gm.resource_defs)
                state["message"] = msg
                state["msg_style"] = "bold green" if ok else "bold red"
            elif sec == "Mejorar Armadura":
                ok, msg = player_guild.upgrade_army_stat("armor", gm.resource_defs)
                state["message"] = msg
                state["msg_style"] = "bold green" if ok else "bold red"

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
                    con.clear()

    if state.get("action") == "garrison":
        _garrison_management_menu(player_guild, player, gm, con)

def _garrison_management_menu(player_guild: Guild, player, gm: GuildManager, con):
    if not player_guild.territories:
        con.print("\n[bold red]No controlas ningún territorio para gestionar guarniciones.[/bold red]")
        time.sleep(get_menu_refresh_rate())
        return
        
    state = {
        "idx": 0,
        "exit": False,
        "dirty": True,
        "message": "↑↓: Territorio | ← →: Cambiar Tropa | (z/x): Guarnecer | (c/v): Retirar",
        "troop_idx": 0
    }
    
    troop_types = ["infantry", "archers", "cavalry", "siege"]
    troop_names = ["Infantería", "Arqueros", "Caballería", "Asedio"]

    def _render():
        t = Table(title="[bold green]🛡️ GUARNICIONES[/]", box=None, expand=True)
        t.add_column("Territorio")
        t.add_column("Tropa Activa")
        t.add_column("En Guarnición", justify="right")
        t.add_column("En Capital", justify="right")
        t.add_column("Gobernador")
        
        ttype = troop_types[state["troop_idx"]]
        tname = troop_names[state["troop_idx"]]
        
        for i, tid in enumerate(player_guild.territories):
            terr = gm.territories.get(tid)
            if not terr: continue
            
            sel = (i == state["idx"])
            name_txt = Text(f"▶ {terr.name}" if sel else f"  {terr.name}", style="bold cyan" if sel else "white")
            
            garrison_qty = terr.garrison.get(ttype, 0)
            capital_qty  = player_guild.soldiers.get(ttype, 0)
            gov_name     = terr.governor_id if terr.governor_id else "Ninguno"
            
            t.add_row(name_txt, Text(tname, style="yellow"), str(garrison_qty), str(capital_qty), f"[bold magenta]{gov_name}[/]")
            
        info = Text(f"\n  [z] Mover 1 tropa a Guarnición  |  [x] Mover 10 tropas a Guarnición\n"
                    f"  [c] Retirar 1 tropa a Capital   |  [v] Retirar 10 tropas a Capital\n"
                    f"  [g] Asignar Gobernador (Cíclico)\n", style="dim")
        footer = Panel(Text(state["message"], style="yellow"), border_style="dim")
        return Panel(Group(t, info, footer), border_style="green")

    def _on_press(key):
        state["dirty"] = True
        if key == "esc":
            state["exit"] = True
        elif key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(player_guild.territories) - 1, state["idx"] + 1)
        elif key == "left":
            state["troop_idx"] = (state["troop_idx"] - 1) % 4
        elif key == "right":
            state["troop_idx"] = (state["troop_idx"] + 1) % 4
        elif key in ["+", "z", "x"]:
            tid = player_guild.territories[state["idx"]]
            terr = gm.territories.get(tid)
            ttype = troop_types[state["troop_idx"]]
            amt = 10 if str(key) == "x" else 1
            if player_guild.soldiers.get(ttype, 0) >= amt:
                player_guild.soldiers[ttype] -= amt
                terr.garrison[ttype] = terr.garrison.get(ttype, 0) + amt
                state["message"] = f"Se movieron {amt} {troop_names[state['troop_idx']]} a la guarnición."
            else:
                state["message"] = "No tienes suficientes tropas en la capital."
        elif key in ["-", "c", "v"]:
            tid = player_guild.territories[state["idx"]]
            terr = gm.territories.get(tid)
            ttype = troop_types[state["troop_idx"]]
            amt = 10 if str(key) == "v" else 1
            if terr.garrison.get(ttype, 0) >= amt:
                terr.garrison[ttype] -= amt
                player_guild.soldiers[ttype] = player_guild.soldiers.get(ttype, 0) + amt
                state["message"] = f"Se devolvieron {amt} {troop_names[state['troop_idx']]} a la capital."
            else:
                state["message"] = "No hay suficientes tropas en la guarnición."
        elif key == "g":
            tid = player_guild.territories[state["idx"]]
            terr = gm.territories.get(tid)
            # Fetch companions from MainGame implicitly by importing it if needed, or accessing player.companion
            companions = getattr(player, "companion", [])
            if not companions:
                state["message"] = "No tienes compañeros para asignar como gobernadores."
            else:
                current_gov = terr.governor_id
                if current_gov is None:
                    terr.governor_id = getattr(companions[0], "name", "Compañero 1")
                else:
                    idx = next((i for i, c in enumerate(companions) if getattr(c, "name", "") == current_gov), -1)
                    if idx == len(companions) - 1 or idx == -1:
                        terr.governor_id = None
                    else:
                        terr.governor_id = getattr(companions[idx+1], "name", f"Compañero {idx+2}")
                
                if terr.governor_id:
                    state["message"] = f"Gobernador asignado: {terr.governor_id} (+20% Prod, +25 Def)"
                else:
                    state["message"] = "Gobernador retirado."

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
                    con.clear()

# ── Punto de entrada principal ────────────────────────────────────────────────

def open_guild_menu(player, console=None):
    """Opción 16 del menú principal."""
    if console is None:
        console = Console()

    gm = get_guild_manager()
    if not gm.guilds:
        gm.generate_random_guilds()
        try:
            _cfg = Read("config.json", None)
            world_cfg = _cfg.get("WORLD", {}) if _cfg else {}
        except Exception:
            world_cfg = {}
        gm.initialize_world_state(world_cfg)

    while True:
        player_guild = gm.get_player_guild()

        if not player_guild:
            action = _no_guild_menu(player, gm, console)
            if action == "create":
                guild = _create_guild_flow(player, gm, console)
                if guild:
                    gm.generate_initial_player_events()
                    console.print(f"\n[bold green]✨ Guild '{guild.name}' ({guild.guild_type}) creada con éxito![/bold green]")
                    time.sleep(get_menu_refresh_rate())
                continue
            elif action == "join":
                guild = _join_guild_flow(player, gm, console)
                if guild:
                    gm.generate_initial_player_events()
                    console.print(f"\n[bold green]✓ Te has unido a {guild.icon} {guild.name}![/bold green]")
                    time.sleep(get_menu_refresh_rate())
                continue
            else:
                break

        sub_action = _main_guild_tabs(player_guild, player, gm, console)

        if sub_action == "exit":
            break
        elif sub_action == "skill_tree":
            open_guild_skill_tree(player_guild, console)
        elif sub_action == "missions":
            open_guild_missions_menu(player_guild, player, gm, console)
        elif sub_action == "territories":
            _territories_action_menu(player_guild, player, gm, console)
        elif sub_action == "buildings":
            _buildings_menu(player_guild, gm, console)
        elif sub_action == "military":
            _military_management_menu(player_guild, player, gm, console)
        elif sub_action == "diplomacy":
            _diplomacy_action_menu(player_guild, player, gm, console)
        elif sub_action == "market":
            _market_and_barter_menu(player_guild, player, gm, console)
        elif sub_action == "commerce":
            _commerce_menu(player_guild, player, gm, console)
        elif sub_action == "events":
            _events_menu(player_guild, player, gm, console)
        elif sub_action == "taxes":
            _tax_settings_menu(player_guild, player, gm, console)

def _render_market_preview(guild: Guild, gm: GuildManager):
    pending = guild.pending_events
    if not pending:
        return Panel(Text("\n  No hay propuestas comerciales pendientes.\n", style="dim"), border_style="yellow")
    
    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("Propuesta", ratio=1)
    t.add_column("De", ratio=1)
    
    for ev in pending[:5]:
        src = gm.guilds.get(ev.get("source_guild_id", ""))
        src_name = f"{src.icon} {src.name}" if src else "Desconocido"
        t.add_row(ev["title"], src_name)
        
    return Panel(Group(Text("  [ENTER] para abrir el Mercado de Trueques\n", style="bold yellow"), t), title="[bold yellow]🤝 Mercado y Trueques[/]", border_style="yellow")

def _tax_settings_menu(player_guild: Guild, player, gm: GuildManager, con):
    state = {"exit": False, "dirty": True}
    def _render():
        rate = player_guild.tax_rate * 100
        msg = ""
        color = "green"
        if rate > 40:
            msg = "💀 TIRANÍA ABSOLUTA: Gran pérdida de Moral y severos debuffs."
            color = "red"
        elif rate > 25:
            msg = "⚠️ PRESIÓN FISCAL EXTREMA: Descontento masivo."
            color = "bright_red"
        elif rate > 10:
            msg = "⚠️ ALTA PRESIÓN FISCAL: -Moral y Debuffs en combate."
            color = "yellow"
        elif rate > 5:
            msg = "⚡ Impuestos moderados."
            color = "bright_green"
        else:
            msg = "🕊️ Impuestos bajos. Población feliz."
            color = "cyan"
        
        # Slider visual
        slider_len = 25
        pos = int((player_guild.tax_rate - 0.01) / (0.50 - 0.01) * (slider_len - 1))
        slider = "[" + "─" * pos + "●" + "─" * (slider_len - 1 - pos) + "]"
        
        t = Table(show_header=False, box=None, expand=True)
        # Escapamos los corchetes para evitar errores de Rich ANSI
        t.add_row(f"[bold]Tasa de Impuestos Actual: [[ [bold {color}]{rate:.0f}%[/] ]][/]")
        t.add_row(f"[bold {color}]{slider}[/]")
        t.add_row(f"[{color}]{msg}[/]")
        t.add_row("")
        t.add_row("↑/↓: Cambiar Tasa (1% - 50%)")
        t.add_row("💰 Oro acumulado por recaudar: " + str(player_guild.tax_gold_pool))
        t.add_row("")
        t.add_row("[R]: Recaudar oro acumulado")
        t.add_row("[ESC]: Guardar y Salir")
        
        return Panel(t, title=f"[bold yellow]⚖ TAXES — {player_guild.icon} {player_guild.name}[/]", border_style="yellow")

    def _on_press(key):
        if key == "up":
            player_guild.tax_rate = min(0.50, player_guild.tax_rate + 0.01)
        elif key == "down":
            player_guild.tax_rate = max(0.01, player_guild.tax_rate - 0.01)
        elif key == "r":
            if player_guild.tax_gold_pool > 0:
                player.Gold += player_guild.tax_gold_pool
                player_guild.tax_gold_pool = 0
        elif key == "esc":
            state["exit"] = True
        state["dirty"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
            con.clear()

def _market_and_barter_menu(player_guild: Guild, player, gm: GuildManager, con):
    state = {"idx": 0, "opt_idx": 0, "exit": False, "dirty": True, "msg": "", "mode": "list"}
    
    def _render():
        pending = player_guild.pending_events
        if not pending:
            return Panel(Text("\n  No hay propuestas comerciales en este momento.\n  Vuelve más tarde o mejora tu reputación.\n", style="dim"), 
                         title="[bold yellow]🤝 Mercado de Trueques[/]", border_style="yellow")
        
        if state["mode"] == "list":
            t = Table(show_header=True, box=box.SIMPLE, expand=True)
            t.add_column("", width=3)
            t.add_column("Propuesta", ratio=1)
            t.add_column("Origen", ratio=1)
            
            for i, ev in enumerate(pending):
                sel = (i == state["idx"])
                src = gm.guilds.get(ev.get("source_guild_id", ""))
                src_name = f"{src.icon} {src.name}" if src else "Desconocido"
                t.add_row("▶" if sel else " ", ev["title"], src_name, style="bold yellow" if sel else "white")
            
            hint = Text("\n ↑↓: Seleccionar | [ENTER]: Ver Detalle | [ESC]: Volver", style="dim")
            return Panel(Group(t, hint), title="[bold yellow]🤝 Mercado de Trueques[/]", border_style="yellow")
        
        else: # mode == "detail"
            ev = pending[state["idx"]]
            src = gm.guilds.get(ev.get("source_guild_id", ""))
            src_name = f"{src.icon} {src.name}" if src else "Desconocido"
            
            detail = Table(show_header=False, box=None, expand=True)
            detail.add_row(f"[bold cyan]De:[/] {src_name}")
            detail.add_row(f"[bold cyan]Asunto:[/] {ev['title']}")
            detail.add_row("")
            detail.add_row(ev["desc_tmpl"])
            detail.add_row("")
            
            opts = Table(show_header=False, box=None, expand=True)
            for j, opt in enumerate(ev["options"]):
                sel_opt = (j == state["opt_idx"])
                opts.add_row(f"{'▶' if sel_opt else ' '} {opt['text']}", style="bold yellow" if sel_opt else "dim")
            
            hint = Text("\n ↑↓: Elegir opción | [ENTER]: Confirmar | [ESC]: Atrás", style="dim")
            return Panel(Group(detail, Rule(), opts, hint), title=f"[bold yellow]🤝 Detalle de Propuesta[/]", border_style="yellow")

    def _on_press(key):
        pending = player_guild.pending_events
        state["dirty"] = True
        
        if state["mode"] == "list":
            if key == "up":
                state["idx"] = max(0, state["idx"] - 1)
            elif key == "down":
                state["idx"] = min(len(pending) - 1, state["idx"] + 1)
            elif key == "enter" and pending:
                state["mode"] = "detail"
                state["opt_idx"] = 0
            elif key == "esc":
                state["exit"] = True
        else: # detail
            ev = pending[state["idx"]]
            if key == "up":
                state["opt_idx"] = max(0, state["opt_idx"] - 1)
            elif key == "down":
                state["opt_idx"] = min(len(ev["options"]) - 1, state["opt_idx"] + 1)
            elif key == "esc":
                state["mode"] = "list"
            elif key == "enter":
                opt = ev["options"][state["opt_idx"]]
                effects = opt.get("effects", {})
                
                # Procesar efectos del trade
                if effects.get("trade_accept"):
                    rid_offer = effects["offer_rid"]
                    amt_offer = effects["offer_amt"]
                    rid_req   = effects["req_rid"]
                    amt_req   = effects["req_amt"]
                    src_id    = effects["src_id"]
                    
                    if player_guild.get_resource(rid_req) >= amt_req:
                        player_guild.consume_resource(rid_req, amt_req)
                        player_guild.add_resource(rid_offer, amt_offer, gm.resource_defs)
                        gm.change_player_reputation(player, src_id, 5)
                        player_guild.log_event(f"🤝 Trade aceptado con {src_id}.")
                        pending.pop(state["idx"])
                        state["mode"] = "list"
                        state["idx"] = 0
                    else:
                        state["msg"] = "✗ No tienes suficientes recursos."
                else:
                    # Otros efectos (rechazar, etc)
                    if "rel_src" in effects:
                        gm.change_player_reputation(player, effects["src_id"], effects["rel_src"])
                    pending.pop(state["idx"])
                    state["mode"] = "list"
                    state["idx"] = 0

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
            con.clear()

def _custom_trade_menu(player_guild: Guild, target_guild: Guild, player, gm: GuildManager, con):
    """Menú para proponer un trade personalizado a un NPC."""
    resources = list(gm.resource_defs.keys())
    state = {
        "offer":    {rid: 0 for rid in resources},
        "request":  {rid: 0 for rid in resources},
        "idx":      0,
        "mode":     "offer", # "offer" or "request"
        "exit":     False,
        "dirty":    True,
        "message":  "↑↓: Elegir Recurso | ←→: + / - Cantidad | [TAB]: Cambiar Oferta/Pedido | [ENTER]: Proponer | [ESC]: Cancelar",
        "msg_style": "dim"
    }

    def _render():
        t_off = Table(title="Tu Oferta", show_header=True, box=box.SIMPLE, expand=True)
        t_off.add_column("Recurso", ratio=1)
        t_off.add_column("Cantidad", ratio=1)
        
        t_req = Table(title=f"Pedido a {target_guild.name}", show_header=True, box=box.SIMPLE, expand=True)
        t_req.add_column("Recurso", ratio=1)
        t_req.add_column("Cantidad", ratio=1)

        for i, rid in enumerate(resources):
            r_def = gm.resource_defs[rid]
            name = f"{r_def.get('icon','')} {r_def.get('name', rid)}"
            
            # Render Offer
            sel_off = (state["mode"] == "offer" and i == state["idx"])
            off_qty = state["offer"][rid]
            t_off.add_row(name, str(off_qty), style="bold yellow" if sel_off else ("white" if off_qty > 0 else "dim"))
            
            # Render Request
            sel_req = (state["mode"] == "request" and i == state["idx"])
            req_qty = state["request"][rid]
            t_req.add_row(name, str(req_qty), style="bold cyan" if sel_req else ("white" if req_qty > 0 else "dim"))

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        return Panel(Group(Group(t_off, t_req), Rule(), footer), 
                     title=f"[bold yellow]⚖ Propuesta Comercial con {target_guild.name}[/]", border_style="yellow")

    def _on_press(key):
        state["dirty"] = True
        rid = resources[state["idx"]]
        
        if key == "up":
            state["idx"] = (state["idx"] - 1) % len(resources)
        elif key == "down":
            state["idx"] = (state["idx"] + 1) % len(resources)
        elif key == "right":
            if state["mode"] == "offer":
                if player_guild.get_resource(rid) > state["offer"][rid]:
                    state["offer"][rid] += 5
            else:
                if target_guild.get_resource(rid) > state["request"][rid]:
                    state["request"][rid] += 5
        elif key == "left":
            if state["mode"] == "offer":
                state["offer"][rid] = max(0, state["offer"][rid] - 5)
            else:
                state["request"][rid] = max(0, state["request"][rid] - 5)
        elif key == "tab":
            state["mode"] = "request" if state["mode"] == "offer" else "offer"
        elif key == "enter":
            # Evaluar trade
            player_offer = {rid: qty for rid, qty in state["offer"].items() if qty > 0}
            player_req   = {rid: qty for rid, qty in state["request"].items() if qty > 0}
            
            if not player_offer and not player_req:
                state["message"] = "No puedes proponer un trato vacío."
                state["msg_style"] = "bold red"
                return

            rep = gm.get_player_reputation(player, target_guild.guild_id)
            accepted, msg = gm.evaluate_trade_proposal(target_guild, player_offer, player_req, rep)
            
            if accepted:
                # Ejecutar trade
                for r, q in player_offer.items():
                    player_guild.consume_resource(r, q)
                    target_guild.add_resource(r, q, gm.resource_defs)
                for r, q in player_req.items():
                    target_guild.consume_resource(r, q)
                    player_guild.add_resource(r, q, gm.resource_defs)
                
                gm.change_player_reputation(player, target_guild.guild_id, 2)
                state["message"] = f"✅ {target_guild.name}: {msg}"
                state["msg_style"] = "bold green"
                # Limpiar oferta
                state["offer"] = {rid: 0 for rid in resources}
                state["request"] = {rid: 0 for rid in resources}
            else:
                state["message"] = f"❌ {target_guild.name}: {msg}"
                state["msg_style"] = "bold red"
                gm.change_player_reputation(player, target_guild.guild_id, -1)
                
        elif key == "esc":
            state["exit"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                try:
                    while not state["exit"]:
                        if state.get("dirty", True):
                            live.update(_render(), refresh=True)
                            state["dirty"] = False
                        time.sleep(0.01)
                finally:
                    stop_listening()
                    if kb_thread.is_alive(): kb_thread.join(timeout=0.2)
            con.clear()

def _custom_trade_menu(player_guild: Guild, target_guild: Guild, player, gm: GuildManager, con):
    state = {
        "exit": False, "dirty": True, "msg": "",
        "offer": {}, "request": {},
        "res_idx": 0, "col": 0 # 0: Offer, 1: Request
    }
    all_res = list(gm.resource_defs.keys())

    def _render():
        t = Table(show_header=True, box=box.SIMPLE, expand=True)
        t.add_column("Recurso", ratio=2)
        t.add_column("Tú Ofreces", ratio=1)
        t.add_column("Tú Pides", ratio=1)
        t.add_column("Stock NPC", ratio=1)

        for i, rid in enumerate(all_res):
            sel = (i == state["res_idx"])
            r_def = gm.resource_defs[rid]
            name = f"{r_def.get('icon','')} {r_def.get('name',rid)}"
            
            off = state["offer"].get(rid, 0)
            req = state["request"].get(rid, 0)
            stock = target_guild.get_resource(rid)
            
            style_off = "bold green" if sel and state["col"] == 0 else "white"
            style_req = "bold yellow" if sel and state["col"] == 1 else "white"
            
            t.add_row(name, 
                      Text(str(off), style=style_off), 
                      Text(str(req), style=style_req), 
                      str(stock))

        hint = Text("\n← →: Cambiar columna | ↑ ↓: Seleccionar recurso | +/- : Ofrecer | [/] : Pedir\n[ENTER]: Enviar propuesta | [ESC]: Cancelar", style="dim")
        return Panel(Group(t, Rule(), hint), title=f"[bold cyan]🤝 Tradeando con {target_guild.name}[/]", subtitle=state["msg"])

    def _on_press(key):
        rid = all_res[state["res_idx"]]
        if key == "up": state["res_idx"] = (state["res_idx"] - 1) % len(all_res)
        elif key == "down": state["res_idx"] = (state["res_idx"] + 1) % len(all_res)
        elif key == "left": state["col"] = 0
        elif key == "right": state["col"] = 1
        elif key == "+":
            if player_guild.get_resource(rid) > state["offer"].get(rid, 0):
                state["offer"][rid] = state["offer"].get(rid, 0) + 1
        elif key == "-":
            state["offer"][rid] = max(0, state["offer"].get(rid, 0) - 1)
        elif key == "[": # Usar [ para menos pedido y ] para más pedido
            state["request"][rid] = max(0, state["request"].get(rid, 0) - 1)
        elif key == "]":
            state["request"][rid] = state["request"].get(rid, 0) + 1
        elif key == "enter":
            # Evaluar trade
            rep = gm.get_player_reputation(player, target_guild.guild_id)
            ok, msg = gm.evaluate_trade_proposal(target_guild, state["offer"], state["request"], rep)
            if ok:
                # Ejecutar
                for r, a in state["offer"].items():
                    player_guild.consume_resource(r, a)
                    target_guild.add_resource(r, a, gm.resource_defs)
                for r, a in state["request"].items():
                    target_guild.consume_resource(r, a)
                    player_guild.add_resource(r, a, gm.resource_defs)
                state["msg"] = "[bold green]¡Aceptado![/] " + msg
                time.sleep(get_menu_refresh_rate())
                state["exit"] = True
            else:
                state["msg"] = "[bold red]Rechazado:[/] " + msg
        elif key == "esc":
            state["exit"] = True
        state["dirty"] = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = start_key_listener(_on_press)
            with Live(console=con, screen=True, auto_refresh=False) as live:
                while not state["exit"]:
                    if state["dirty"]:
                        live.update(_render(), refresh=True)
                        state["dirty"] = False
                    time.sleep(0.01)
            stop_listening()
