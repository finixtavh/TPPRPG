"""
GuildMenu.py — UI principal del sistema de Guilds. Opción 16.

Regla de renderizado: cada función interactiva tiene su propio
    with console.screen():
        with keyboard_listener_scope():
            with Live(..., transient=True):
                ...
    console.clear()

NO se anidan screens. open_guild_menu es solo un loop de navegación.
"""

import os
import time
import threading
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

from Modules.GuildSystem import Guild, GuildManager, get_guild_manager, reset_guild_manager, SIMULATION_INTERVAL
from Modules.GuildSkillTree import open_guild_skill_tree, BRANCH_ICONS
from Modules.GuildMissions import open_guild_missions_menu
from Modules.input_utils import keyboard_listener_scope

console = Console()

RARITY_COLORS = {
    "Common":    "white",
    "Uncommon":  "green",
    "Rare":      "bright_cyan",
    "Legendary": "bright_yellow",
}


# ── Helpers de renderizado (sin estado, solo devuelven renderizables) ──────────

def _render_summary(guild: Guild, player, gm: GuildManager):
    t = Table(show_header=False, box=None, expand=True)
    t.add_column("K", style="cyan",  width=22)
    t.add_column("V", style="white", ratio=1)

    moral_bar = "█" * (guild.moral // 10) + "░" * (10 - guild.moral // 10)
    ml_bar    = "█" * (guild.military_power // 10) + "░" * (10 - guild.military_power // 10)
    rep       = gm.get_player_reputation(player, guild.guild_id)
    rank_name, rank_color = gm.get_reputation_rank(rep)

    t.add_row("Tipo",          f"{guild.icon} {guild.guild_type}")
    t.add_row("Poder Militar", f"[bold red]{ml_bar}[/] {guild.military_power}")
    t.add_row("Moral",         f"[yellow]{moral_bar}[/] {guild.moral}/100")
    t.add_row("Población",     str(guild.population))
    t.add_row("Influencia",    str(guild.influence))
    t.add_row("Territorios",   str(len(guild.territories)))
    t.add_row("Skill Points",  f"[bold green]{guild.skill_points}[/]")
    t.add_row("Tu Reputación", f"[{rank_color}]{rank_name} ({rep:+d})[/]")

    log_text = Text()
    log_text.append("\n  Eventos recientes:\n", style="bold dim")
    for ev in guild.event_log[-5:]:
        log_text.append(f"  • {ev}\n", style="dim")

    return Panel(Group(t, Rule(style="dim"), log_text),
                 title=f"[bold]{guild.icon} {guild.name}[/]", border_style="bright_magenta")


def _render_territories(guild: Guild, gm: GuildManager):
    map_rows = gm.get_territory_map_rows()
    map_text = Text()
    map_text.append("  ★ = Tuyo  · = Neutral  🔸 = Otro\n\n", style="dim")
    for row in map_rows:
        map_text.append("  " + row + "\n")

    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("Territorio")
    t.add_column("Recursos generados", ratio=1)
    if not guild.territories:
        t.add_row("[dim]Sin territorios[/]", "[dim]—[/]")
    else:
        for tid in guild.territories:
            terr = gm.territories.get(tid)
            if terr:
                res_str = "  ".join(
                    f"{gm.resource_defs.get(rid, {}).get('icon','?')} {amt}/tick"
                    for rid, amt in terr.resource_output.items()
                )
                t.add_row(f"{terr.icon} {terr.name}", res_str)

    return Panel(Group(map_text, Rule(style="dim"), t),
                 title="[bold]🗺 TERRITORIOS[/]", border_style="green")


def _render_resources(guild: Guild, gm: GuildManager):
    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("", width=3)
    t.add_column("Recurso",  ratio=2)
    t.add_column("Cantidad", width=10)
    t.add_column("Rareza",   width=12)

    for rid, defn in gm.resource_defs.items():
        amount = guild.get_resource(rid)
        rarity = defn.get("rarity", "Common")
        color  = RARITY_COLORS.get(rarity, "white")
        icon   = defn.get("icon", "?")
        bar    = "█" * min(20, amount // 5)
        t.add_row(icon, defn.get("name", rid), f"[{color}]{amount:,}[/] {bar}", f"[{color}]{rarity}[/]")

    food_needed = max(1, guild.population // 10)
    food_have   = guild.get_resource("comida")
    ticks_left  = food_have // food_needed if food_needed > 0 else 9999
    footer = Text(f"\n🍞 Consumo: {food_needed}/tick | Stock: {food_have} ({ticks_left} ticks)\n", style="dim")

    return Panel(Group(t, footer), title="[bold]💰 RECURSOS DE GUILD[/]", border_style="yellow")


def _render_world(gm: GuildManager, player):
    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("#",       width=3)
    t.add_column("Guild",   ratio=2)
    t.add_column("Tipo",    width=12)
    t.add_column("Poder",   width=8)
    t.add_column("Moral",   width=8)
    t.add_column("Terr.",   width=6)
    t.add_column("Tu Rep.", width=12)

    for i, guild in enumerate(gm.get_sorted_guilds_by_power(), 1):
        rep       = gm.get_player_reputation(player, guild.guild_id)
        rank, col = gm.get_reputation_rank(rep)
        is_player = guild.guild_id == gm.player_guild_id
        prefix    = "★ " if is_player else f"{i}. "
        row_style = "bold bright_cyan" if is_player else "white"
        t.add_row(prefix, f"{guild.icon} {guild.name}", guild.guild_type,
                  str(guild.military_power), str(guild.moral),
                  str(len(guild.territories)), f"[{col}]{rank}[/]", style=row_style)

    ev_text = Text("\n")
    ev_text.append("  Últimos eventos del mundo:\n", style="bold dim")
    for ev in gm.world_events[-8:]:
        ev_text.append(f"  • {ev}\n", style="dim")

    return Panel(Group(t, Rule(style="dim"), ev_text),
                 title="[bold]🌍 ESTADO DEL MUNDO[/]", border_style="blue")


def _render_diplomacy(guild: Guild, gm: GuildManager, player):
    t = Table(show_header=True, box=box.SIMPLE, expand=True)
    t.add_column("Guild",    ratio=2)
    t.add_column("Relación", width=10)
    t.add_column("Tu Rep.",  width=12)
    t.add_column("Alianza",  width=8)

    for gid, g in gm.guilds.items():
        if gid == guild.guild_id:
            continue
        relation  = guild.relations.get(gid, 0)
        rep       = gm.get_player_reputation(player, gid)
        rank, col = gm.get_reputation_rank(rep)
        rel_color = "green" if relation >= 30 else ("red" if relation < -20 else "dim white")
        is_ally   = gid in guild.alliances
        ally_str  = "[bold green]✓[/]" if is_ally else "[dim]—[/]"
        t.add_row(f"{g.icon} {g.name}", f"[{rel_color}]{relation:+d}[/]",
                  f"[{col}]{rank}[/]", ally_str)

    hint = Text("\n  [F] Formar alianza  |  [S] Sabotear (requiere Espionaje)\n", style="dim")
    return Panel(Group(t, hint), title="[bold]🕊 DIPLOMACIA[/]", border_style="bright_magenta")


# ── Función auxiliar de loop de Live ─────────────────────────────────────────

def _run_live_loop(render_fn, on_press_fn, exit_key="esc", con=None):
    """
    Patrón estándar: console.screen + keyboard_listener + Live.
    Maneja limpieza correctamente y evita pantallas anidadas.
    """
    if con is None:
        con = console
    state_exit = {"v": False}
    orig_on_press = on_press_fn

    def _wrapped_on_press(key):
        orig_on_press(key)

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _wrapped_on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=con, refresh_per_second=20, transient=True) as live:
                    while True:
                        live.update(render_fn())
                        time.sleep(0.05)
                        # Check exit from outside (state dict passed via closure)
                        if _check_exit():
                            break
            finally:
                stop_listening()
                if kb_thread.is_alive():
                    kb_thread.join(timeout=0.2)
        con.clear()

# We won't use the helper above — simpler to inline the pattern directly.
# Each function below follows the exact same pattern as CraftingSystem.py


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
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=con, refresh_per_second=20, transient=True) as live:
                    while not state["exit"]:
                        live.update(_render())
                        time.sleep(0.05)
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
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=con, refresh_per_second=20, transient=True) as live:
                    while not state["done"]:
                        live.update(_render())
                        time.sleep(0.05)
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
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=con, refresh_per_second=20, transient=True) as live:
                    while not state["done"]:
                        live.update(_render())
                        time.sleep(0.05)
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
    Menú con 7 pestañas para la guild del jugador.
    Retorna: 'exit' | 'skill_tree' | 'missions'
    """
    tabs  = ["Resumen", "Territorios", "Recursos", "Mundo", "Misiones", "Habilidades", "Diplomacia"]
    state = {
        "tab_idx":        0,
        "exit":           False,
        "inner_action":   "exit",
        "open_sub":       None,   # 'skill_tree' | 'missions' | None
        "message":        f"{player_guild.icon} {player_guild.name}  |  Skill pts: {player_guild.skill_points}",
        "msg_style":      "dim",
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
        if tab == "Resumen":
            content = _render_summary(player_guild, player, gm)
        elif tab == "Territorios":
            content = _render_territories(player_guild, gm)
        elif tab == "Recursos":
            content = _render_resources(player_guild, gm)
        elif tab == "Mundo":
            content = _render_world(gm, player)
        elif tab == "Habilidades":
            content = Panel(
                Text("\n  Pulsa [ENTER] para abrir el árbol de habilidades.\n", style="dim"),
                border_style="cyan",
            )
        elif tab == "Misiones":
            content = Panel(
                Text("\n  Pulsa [ENTER] para abrir el gestor de misiones.\n", style="dim"),
                border_style="yellow",
            )
        elif tab == "Diplomacia":
            content = _render_diplomacy(player_guild, gm, player)
        else:
            content = Panel(Text("Próximamente.", style="dim"))

        footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
        hint   = Text("← →: Pestañas | [ENTER]: Acción | [ESC]: Salir", style="dim")
        return Panel(
            Group(h, Rule(style="cyan"), content, hint, footer),
            title=f"[bold cyan]⚔ GUILDS — {player_guild.icon} {player_guild.name}[/]",
            border_style="cyan",
        )

    def _on_press(key):
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
        elif key == "esc":
            state["open_sub"] = None
            state["exit"]     = True

    with con.screen():
        with keyboard_listener_scope():
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=con, refresh_per_second=20, transient=True) as live:
                    while not state["exit"]:
                        live.update(_render())
                        time.sleep(0.05)
            finally:
                stop_listening()
                if kb_thread.is_alive():
                    kb_thread.join(timeout=0.2)
        con.clear()

    return state["open_sub"] or "exit"


# ── Punto de entrada principal ────────────────────────────────────────────────

def open_guild_menu(player, console=None):
    """Opción 16 del menú principal. Sin console.screen() propio — cada sub-función tiene el suyo."""
    if console is None:
        console = Console()

    gm = get_guild_manager()
    if not gm.guilds:
        gm.generate_random_guilds()

    while True:
        player_guild = gm.get_player_guild()

        if not player_guild:
            action = _no_guild_menu(player, gm, console)
            if action == "create":
                guild = _create_guild_flow(player, gm, console)
                if guild:
                    # Breve confirmación en pantalla limpia
                    console.print(f"\n[bold green]✨ Guild '{guild.name}' ({guild.guild_type}) creada con éxito![/bold green]")
                    time.sleep(1.5)
                continue
            elif action == "join":
                guild = _join_guild_flow(player, gm, console)
                if guild:
                    console.print(f"\n[bold green]✓ Te has unido a {guild.icon} {guild.name}![/bold green]")
                    time.sleep(1.5)
                continue
            else:
                break  # "back" → volver al menú principal

        # Jugador tiene guild — mostrar menú con pestañas
        sub_action = _main_guild_tabs(player_guild, player, gm, console)

        if sub_action == "exit":
            break
        elif sub_action == "skill_tree":
            open_guild_skill_tree(player_guild, console)
        elif sub_action == "missions":
            open_guild_missions_menu(player_guild, player, gm, console)
