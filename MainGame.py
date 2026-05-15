from rich.console import Console, Group
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn # IDK HOW TO USE TS
from rich.align import Align 
from typing import List, Dict, Optional, Tuple, Any, Union
from rich import box
import sys
import time
import traceback
from rich.live import Live
from sshkeyboard import listen_keyboard, stop_listening


_original_stdout_write = sys.stdout.write

def _safe_stdout_write(text):
    while True:
        try:
            return _original_stdout_write(text)
        except BlockingIOError:
            time.sleep(0.001)  # Esperar a que el buffer se drene

sys.stdout.write = _safe_stdout_write
# -----------------------------------------------------------------------------
# Modules/

from Modules.ModulesManager.ItemManager import get_item_manager, load_item_by_id
from Modules.ModulesManager.ShopManager import get_shop_manager, display_shop
from Modules.ModulesManager.ZoneManager import get_all_zones, get_zones_for_selector
from Modules.ModulesManager.BuffManager import get_buff_manager

from Modules.ModulesMenu.InventoryMenu import open_inventory_menu
from Modules.ModulesMenu.GuildMenu import open_guild_menu

from Modules.ModulesFunctions.GatheringMasterySystem import cTool, cMaterial, Gathering_init
from Modules.ModulesFunctions.EnchantmentSystem import open_enchantment_menu
from Modules.ModulesFunctions.MasterySystem import ensure_mastery, MASTERY_MAX_LEVEL
from Modules.ModulesFunctions.SaveSystem import save_load_menu, get_slot_info
from Modules.ModulesFunctions.CraftingSystem import open_crafting_menu
from Modules.ModulesFunctions.GuildSystem import get_guild_manager, SIMULATION_INTERVAL
from Modules.ModulesFunctions.QuestSystem import quest_manager
from Modules.ModulesFunctions.BaseSystem import BaseManager, open_base_menu
from Modules.ModulesFunctions.CompanionSystem import (
    cCompanion,
    companion_management_menu,
    COMPANION_REVIVAL_GOLD_COST,)

from Modules.ModulesUtils.Loader import Write, Read
from Modules.ModulesUtils.ModLoader import get_mod_loader, get_mod_api
from Modules.ModulesUtils.input_utils import wait_for_enter, interactive_menu_select, keyboard_listener_scope
from Modules.ModulesUtils.debug import (
    setup_logging,
    attach_console_logging,
    install_exception_hooks,
    log_imported_modules,
    dump_debug_snapshot,)
from Modules.ModulesUtils.setup import (
    cPlayer,
    cEnemy,
    cWeapon,
    cEquippableItems,
    cObject,
    setup_player,
    vInventory,
    enemy_loader,)

# ---   ---
import json
import random
import time as sp
import os
import sys
import traceback
import threading

# Game configuration
CONFIG = Read("config.json", None)

data_path = os.path.join("Data", "DataStats.json")

# Initialize console with custom theme
custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "magenta",
        "danger": "bold red",
        "success": "bold green",
        "menu_title": "bold yellow",
        "menu_option": "bright_white",
    }
)

console = Console(theme=custom_theme)

app_logger = setup_logging(CONFIG["DEBUG"]["ENABLED"])
attach_console_logging(console, app_logger)
install_exception_hooks(app_logger)

def _display_combat_details(attacker_name, defender_name, res, is_counter=False):
    """Muestra una tabla detallada del resultado del ataque."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    
    title = f"[bold yellow]⚔️ CONTRAATAQUE[/]" if is_counter else f"[bold cyan]⚔️ ATAQUE: {attacker_name} → {defender_name}[/]"
    
    if res.get("is_evaded"):
        console.print(Panel(Text(f"¡{defender_name} ha ESQUIVADO el ataque! 💨", style="bold cyan"), border_style="cyan"))
        return

    # --- NUEVA INTERFAZ V4 (BLOQUES MODERNOS) ---
    from rich.console import Group
    icons = ["⚔️", "🔥", "🪨", "⚡", "🔮"]
    colors = ["white", "orange3", "yellow4", "bright_blue", "purple"]
    types_display = ["Físico", "Térmico", "Tierra", "Eléctrico", "Profundo"]
    
    content = Text()
    dmg_per_type = res.get("damage_per_type", [0]*5)
    
    for i in range(5):
        val = dmg_per_type[i]
        if val > 0 or (i == 0 and sum(dmg_per_type) == 0):
            # Barra visual proporcional
            bar_size = int(min(10, val / 5 + 1)) if val > 0 else 1
            bar = "▉" * bar_size
            content.append(f"{bar}", style=colors[i])
            content.append(f" {icons[i]} {val:.1f} {types_display[i]}", style="bold " + colors[i])
            
            # Construir explicación detallada (Parentesis)
            parts = []
            
            # Defensa Fija
            def_fixed = res.get("blocked_by_def", [0]*5)[i]
            if def_fixed > 0:
                parts.append(f"-{def_fixed:.1f} Def")
            
            # Porcentaje
            def_pct_amt = res.get("blocked_by_pct", [0]*5)[i]
            if def_pct_amt > 0:
                pct_val = res.get("def_pct_val", [0]*5)[i]
                parts.append(f"-{def_pct_amt:.1f} %Def ({pct_val}%)")
            
            # Encantamientos
            enc_def = res.get("enchant_def", [0]*5)[i]
            if enc_def > 0:
                enc_names = ", ".join(res.get("enchant_names", ["Mágico"]))
                parts.append(f"-{enc_def:.1f} Encant: {enc_names}")
                
            # Clima
            w_def = res.get("weather_def", [0]*5)[i]
            if w_def != 0:
                w_name = res.get("weather_name", "Clima")
                sign = "-" if w_def > 0 else "+"
                parts.append(f"{sign}{abs(w_def):.1f} Clima: {w_name}")
                
            if parts:
                expl = " (" + " | ".join(parts) + ")"
                # Envolver detalle si es muy largo
                expl_wrapped = expl.replace(" | ", "\n      | ")
                content.append(f"\n     {expl_wrapped}\n", style="dim italic")
            else:
                content.append("\n")

    # Footer
    footer = Text()
    if res.get("barrier_absorbed", 0) > 0:
        footer.append(f"🛡️ Barrera: -{res['barrier_absorbed']:.1f} ", style="bold blue")
    
    footer.append(f"💥 TOTAL: {res['total_damage']:.1f}", style="bold yellow")
    if res.get("is_counter"):
        footer.append(f"\n⚡ ¡{defender_name} se prepara para CONTRAATACAR!", style="bold magenta")
    
    panel = Panel(
        content,
        title=title,
        subtitle=footer,
        subtitle_align="right",
        border_style="yellow" if is_counter else "cyan",
        box=box.ROUNDED,
        expand=False
    )
    console.print(panel)

def _perform_attack(attacker, defender, console):
    """Ejecuta un ataque y maneja el posible contraataque en cadena."""
    res = attacker.attack(defender)
    _display_combat_details(getattr(attacker, "name", getattr(attacker, "NAME", "???")), 
                           getattr(defender, "name", getattr(defender, "NAME", "???")), res)
    
    total_dmg = res.get("total_damage", 0)
    
    if res.get("is_counter") and getattr(defender, "Health", getattr(defender, "HP", 0)) > 0:
        sp.sleep(0.5)
        counter_res = defender.attack(attacker)
        _display_combat_details(getattr(defender, "name", getattr(defender, "NAME", "???")), 
                               getattr(attacker, "name", getattr(attacker, "NAME", "???")), counter_res, is_counter=True)
    return total_dmg
if CONFIG["DEBUG"]["ENABLED"]:
    log_imported_modules(app_logger)

# Game state variables
enemies: List[Any] = []
enemy: Optional[cEnemy] = None
chosen_area: Optional[str] = None
shop_objects: List[Any] = []
zone_name: str = ""
tick: int = 0
chars: List[Any] = []

item_manager = None
shop_manager = None

def zone_loader(player_zone: str) -> cEnemy:
    """
    Carga enemigos de la zona especificada (DataStats.json O mods)

    Args:
        player_zone: Nombre de la zona a cargar

    Returns:
        Un enemigo aleatorio de la zona especificada
    """
    try:
        data_npcs = None
        try:
            mod_api = get_mod_api()

            if player_zone in mod_api.stats_injections:
                data_npcs = mod_api.stats_injections[player_zone]
                console.print(f"[dim]Cargando zona de mod: {player_zone}[/dim]")
        except:
            pass

        if not data_npcs:
            data_path = os.path.join("Data", "DataStats.json")
            data_npcs = Read(data_path, player_zone, None)

            if data_npcs:
                console.print(f"[dim]Cargando zona del juego base: {player_zone}[/dim]")

        if not data_npcs:
            console.print(
                f"[danger]No se encontraron datos para la zona: {player_zone}[/danger]"
            )
            return None

        enemy_list = enemy_loader(data_npcs)

        if not enemy_list:
            console.print(
                f"[danger]No se encontraron enemigos en la zona: {player_zone}[/danger]"
            )
            return None

        # PASO 5: Filtrar jefes por SPAWN_CHANCE y seleccionar aleatoriamente
        valid_enemies = []
        for e in enemy_list:
            if getattr(e, 'IS_BOSS', False):
                if random.random() <= getattr(e, 'SPAWN_CHANCE', 1.0):
                    valid_enemies.append(e)
            else:
                valid_enemies.append(e)
                
        if not valid_enemies:
            valid_enemies = enemy_list
            
        enemy_random = random.choice(valid_enemies)
        
        if getattr(enemy_random, 'IS_BOSS', False):
            console.print(f"[blink bold red]¡ADVERTENCIA! ¡Has encontrado a un JEFE: {enemy_random.NAME}![/blink bold red]")
        else:
            console.print(f"[success]Enemigo seleccionado: {enemy_random.NAME}[/success]")
        return enemy_random

    except Exception as e:
        console.print(
            f"[danger]Error al cargar la zona {player_zone}: {str(e)}[/danger]"
        )
        

        traceback.print_exc()
        return None


def zone_loader_group(player_zone: str, max_enemies: int = 5) -> List[cEnemy]:
    """
    Carga un grupo de hasta `max_enemies` enemigos de la zona indicada.

    Returns:
        Lista de enemigos (puede ser vacía si falla la carga).
    """
    try:
        data_npcs = None
        try:
            mod_api = get_mod_api()
            if player_zone in mod_api.stats_injections:
                data_npcs = mod_api.stats_injections[player_zone]
        except Exception:
            pass

        if not data_npcs:
            data_path_local = os.path.join("Data", "DataStats.json")
            data_npcs = Read(data_path_local, player_zone, None)

        if not data_npcs:
            console.print(f"[danger]No se encontraron datos para la zona: {player_zone}[/danger]")
            return []

        enemy_list = enemy_loader(data_npcs)
        if not enemy_list:
            return []

        # Elegir entre 1 y max_enemies enemigos aleatoriamente
        count = random.randint(1, min(max_enemies, len(enemy_list)))
        group = [random.choice(enemy_list) for _ in range(count)]
        console.print(f"[success]Grupo de {count} enemigo(s) encontrado en {player_zone}.[/success]")
        return group

    except Exception as e:
        console.print(f"[danger]Error al cargar grupo de zona {player_zone}: {e}[/danger]")
        return []


def load_test_items():
    """Carga algunos items de prueba desde JSON para testing"""
    global item_manager

    try:
        # Cargar Espada Grande (ID: 3)
        great_sword = load_item_by_id(3, cWeapon, cEquippableItems, cObject, cTool)

        # Cargar Bastón Mágico (ID: 4 o 5)
        magic_staff = load_item_by_id(4, cWeapon, cEquippableItems, cObject, cTool)

        # Cargar algunos anillos
        ring_1 = load_item_by_id(40, cWeapon, cEquippableItems, cObject, cTool)
        ring_2 = load_item_by_id(41, cWeapon, cEquippableItems, cObject, cTool)

        # Cargar pociones
        health_potion = load_item_by_id(52, cWeapon, cEquippableItems, cObject, cTool)

        # Agregar al inventario para pruebas (opcional)
        if great_sword:
            vInventory.addObject(great_sword)
            console.print(
                f"[info]Item de prueba cargado: {getattr(great_sword, 'Name', great_sword.name)}[/info]"
            )

    except Exception as e:
        console.print(f"[warning]No se pudieron cargar items de prueba: {e}[/warning]")


def display_player_status() -> None:
    """Estado del jugador con barras y zona actual (inspirado en Interfaces/01_dashboard.py)."""
    # Cabecera: nombre, nivel, zona, oro
    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")

    try:
        from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
        w = get_weather_manager().get_current_weather()
        weather_text = f"   [bold]Clima:[/bold] {w.icon} {w.name}"
    except ImportError:
        weather_text = ""

    zone_text = chosen_area if chosen_area is not None else "Ninguna"
    left = Text.from_markup(
        f"[bold]Nombre:[/bold] {player.name} [dim](Nivel {player.Level})[/dim]"
    )
    right = Text.from_markup(
        f"[bold yellow]Oro:[/bold yellow] {player.Gold}   [bold]Zona:[/bold] {zone_text}{weather_text}"
    )
    header.add_row(left, right)

    # Barras HP (con barrera) / MP
    if player.Barrier >= 0:
        health_bar, health_percent = create_hp_barrier_bar(
            player.Health, player.Health_max, player.Barrier
        )
    else:
        health_bar, health_percent = create_status_bar(
            player.Health, player.Health_max, "red"
        )
    mana_bar, mana_percent = create_status_bar(player.Mana, player.Mana_max, "blue")

    bars = Table.grid(padding=(0, 1))
    bars.add_column()
    
    hp_label = f"[bold red]HP:[/bold red] {health_bar} [dim]{health_percent}%[/]"
    if player.Barrier > 0:
        hp_label += f" [bright_cyan]+{int(player.Barrier)} 🛡️[/bright_cyan]"    
    bars.add_row(Text.from_markup(hp_label))
    bars.add_row(
        Text.from_markup(
            f"[bold blue]MP:[/bold blue] {mana_bar} [dim]{mana_percent}%[/]"
        )
    )

    content = Group(header, "", bars)
    panel = Panel(
        content, title="Estado del Jugador", border_style="bright_white", padding=(0, 1)
    )
    console.print(panel)


player = None


def create_status_bar(
    current: float, maximum: float, color: str, return_values: bool = True) -> Union[None, Tuple[str, int]]:
    """
    Create a visual status bar representation for health, mana, etc.

    Args:
        current: Current value of the status
        maximum: Maximum possible value
        color: Color to use for the filled portion of the bar
        return_values: Whether to return the bar or print it directly

    Returns:
        If return_values is True, returns a tuple with (bar_string, percentage)
        Otherwise, prints the bar and returns None
    """

    current = min(current, maximum)

    if maximum <= 0:
        maximum = 1

    bar_length = CONFIG["DISPLAY"]["BAR_LENGTH"]
    filled_length = int(bar_length * current / maximum)

    # Create the bar string
    bar = (
        "["
        + f"[{color}]#[/{color}]" * filled_length
        + "-" * (bar_length - filled_length)
        + "]"
    )
    percentage = int((current / maximum) * 100)

    if not return_values:
        console.print(f"Vida: {bar} {percentage}%")
        return None

    return bar, percentage


def create_hp_barrier_bar(
    health: float, health_max: float, barrier: float, _unused=None
) -> Tuple[str, int]:
    """
    Create an HP bar with a bright_cyan barrier overlay (like League of Legends shields).

    Visual: [CYAN_barrier | GREEN_hp | EMPTY]
    The barrier overlays from the LEFT of the bar, covering HP.
    Barrier is proportional to health_max.

    Returns:
        Tuple of (bar_string, health_percentage)
    """
    health = min(health, health_max)
    if health_max <= 0:
        health_max = 1
    barrier = max(0, barrier)

    bar_length = CONFIG["DISPLAY"]["BAR_LENGTH"]

    health_pct = health / health_max
    barrier_pct = barrier / health_max

    health_cells = int(bar_length * health_pct)
    barrier_cells = int(bar_length * barrier_pct)

    # Total filled = health + barrier (barrier extends beyond current HP)
    total_filled = min(health_cells + barrier_cells, bar_length)

    # Barrier overlays FROM THE LEFT, on top of HP
    barrier_shown = min(barrier_cells, total_filled)
    health_shown = total_filled - barrier_shown
    empty = bar_length - total_filled

    bar = (
        "["
        + f"[bright_cyan]#[/bright_cyan]" * barrier_shown
        + f"[green]#[/green]" * health_shown
        + "-" * empty
        + "]"
    )
    percentage = int(health_pct * 100)
    return bar, percentage


def render_combat_menu(player, enemy, combat_round: int) -> None:
    """UI de combate con soporte de compañeros: [comp…] [jugador] vs [enemigo]."""
    try:
        from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
        w = get_weather_manager().get_current_weather()
        
        # Mostrar modificadores del clima de forma compacta
        mods = []
        for k, v in w.combat_mods.items():
            if v != 1.0:
                sign = "+" if v > 1.0 else ""
                pct = int((v - 1.0) * 100)
                mods.append(f"{k.upper()}: {sign}{pct}%")
        
        mod_str = f" ({', '.join(mods)})" if mods else ""
        weather_text = f"  |  Clima: {w.icon} {w.name}{mod_str}"
    except ImportError:
        weather_text = ""
        
    header = Text.from_markup(f"[bold]Combate - Ronda {combat_round}[/]{weather_text}")

    # ── Bloques de aliados (compañeros primero, jugador al final) ────────────
    ally_blocks = []

    # Solo mostrar hasta 4 compañeros activos; el resto se gestiona desde companion_bank
    active_companions = [c for c in player.companion if c.is_alive or not c.is_alive][:4]

    for comp in active_companions:
        if comp.is_alive:
            comp_barrier = getattr(comp, "Barrier", 0)
            if comp_barrier > 0:
                c_hp_bar, c_hp_pct = create_hp_barrier_bar(comp.Health, comp.Health_max, comp_barrier)
                barrier_line = f"\n[bright_cyan]🛡️ Barrera: {int(comp_barrier)}[/bright_cyan]"
            else:
                c_hp_bar, c_hp_pct = create_status_bar(comp.Health, comp.Health_max, "green")
                barrier_line = ""
            c_mp_bar, c_mp_pct = create_status_bar(comp.Mana, comp.Mana_max, "blue")
            weapon_tag = f" [{comp.weapon.name}]" if comp.weapon else ""
            comp_block = Panel(
                f"[bold cyan]{comp.name}[/bold cyan]{weapon_tag}\n"
                f"[red]HP:[/red] {c_hp_bar} [dim]{c_hp_pct}%[/]{barrier_line}\n"
                f"[blue]MP:[/blue] {c_mp_bar} [dim]{c_mp_pct}%[/]",
                border_style="cyan",
                padding=(0, 1),
            )
        else:
            comp_block = Panel(
                f"[dim]{comp.name}[/dim]\n"
                f"[bold red]💀 KO[/bold red]\n"
                f"[dim]Necesita ser revivido[/dim]",
                border_style="dim",
                padding=(0, 1),
            )
        ally_blocks.append(comp_block)

    # ── Bloque del jugador ───────────────────────────────────────────────────
    if player.Barrier > 0:
        p_hp_bar, p_hp_pct = create_hp_barrier_bar(
            player.Health, player.Health_max, player.Barrier
        )
        barrier_text = f"\n[bright_cyan]🛡️ Barrera: {int(player.Barrier)}[/bright_cyan]"
    else:
        p_hp_bar, p_hp_pct = create_status_bar(player.Health, player.Health_max, "green")
        barrier_text = ""
    p_mp_bar, p_mp_pct = create_status_bar(player.Mana, player.Mana_max, "blue")
    player_block = Panel(
        f"[bold]{player.name}[/]\n"
        f"[red]HP:[/red] {p_hp_bar} [dim]{p_hp_pct}%[/]{barrier_text}\n"
        f"[blue]MP:[/blue] {p_mp_bar} [dim]{p_mp_pct}%[/]",
        border_style="success",
        padding=(0, 1),
    )
    ally_blocks.append(player_block)

    # ── Bloque del enemigo ───────────────────────────────────────────────────
    e_hp_bar, e_hp_pct = create_status_bar(enemy.HP, enemy.HP_M, "red")
    e_mp_bar, e_mp_pct = create_status_bar(enemy.MP, enemy.MP_M, "blue")
    enemy_block = Panel(
        f"[bold red]{enemy.NAME}[/bold red]\n"
        f"[red]HP:[/red] {e_hp_bar} [dim]{e_hp_pct}%[/]\n"
        f"[blue]MP:[/blue] {e_mp_bar} [dim]{e_mp_pct}%[/]",
        border_style="danger",
        padding=(0, 1),
    )

    separator_text = Text("│\n│\n│\n│", style="dim")
    sep_panel = Panel(separator_text, border_style="dim", padding=(0, 0))
    top = Columns(ally_blocks + [sep_panel, enemy_block], equal=False, expand=True)

    actions = Table.grid(padding=(0, 2))
    actions.add_column(style="bold yellow")
    actions.add_column(style="bright_white")
    actions.add_column(style="dim")
    actions.add_column(style="bold yellow")
    actions.add_column(style="bright_white")
    actions.add_row("[1]", "Atacar", "  │  ", "[2]", "Inventario")
    actions.add_row("[3]", "Huir",   "  │  ", "",    "")

    bottom = Panel(
        actions, title="[bold yellow]Acciones[/]", border_style="yellow", padding=(0, 1)
    )
    content = Group(header, "", top, "", bottom)
    console.print(Panel(content, border_style="danger", padding=(1, 2)))


def apply_debuffs(player: Any) -> Dict[str, Any]:
    """
    Apply all active debuffs to the player and return a summary of applied effects.

    Args:
        player: The player object to apply debuffs to

    Returns:
        A dictionary summarizing all applied debuff effects
    """
    applied_effects = {}

    if not hasattr(player, "applieddebuffs") or not player.applieddebuffs:
        return applied_effects

    for debuff in player.applieddebuffs:
        # Get all non-callable, non-dunder attributes
        debuff_attributes = [
            attr
            for attr in dir(debuff)
            if not callable(getattr(debuff, attr)) and not attr.startswith("__")
        ]

        for debuff_attr in debuff_attributes:
            debuff_value = getattr(debuff, debuff_attr, None)
            if debuff_value is not None:
                # Apply the debuff effect
                debuff.Apply(debuff_attr, player)
                # Record the applied effect
                applied_effects[debuff_attr] = debuff_value

    return applied_effects


def display_zone_enemies(
    zone_name: str, enemies_data: List, strings_data: Dict
) -> None:
    """
    Display enemy information for a zone with physical and magical damage.

    Args:
        zone_name: Name of the zone to display
        enemies_data: JSON data containing enemy information
        strings_data: String data containing zone description
    """
    # Nombre y estilo de la zona desde el JSON (Strings.name)
    # Obtener título y color de la zona desde JSON
    zone_title = strings_data.get("name", zone_name)
    zone_style = strings_data.get("color", "white")  # Color desde JSON, default "white"

    zone_table = Table(title=zone_title, title_style=zone_style)
    zone_table.add_column("Enemigo", style=zone_style)
    zone_table.add_column("Vida", justify="right")
    zone_table.add_column("Daño Físico", justify="right", style="red")
    zone_table.add_column("Daño Mágico", justify="right", style="blue")
    zone_table.add_column("Defensa", justify="right")

    console.print(
        f"\n[bold {zone_style}]{zone_title}[/bold {zone_style}]: {strings_data.get('desc', 'No hay descripción disponible')}"
    )

    for enemy in enemy_loader(enemies_data, False):
        # Formatear daño multi-tipo
        # DMG es [Físico, Térmico, Tierra, Eléctrico, Profundo]
        physical_dmg = f"{enemy.DMG_min[0]}-{enemy.DMG[0]}" if enemy.DMG[0] > 0 else "0"

        # Sumar todos los daños mágicos (Térmico, Tierra, Eléctrico, Profundo)
        magical_total_min = sum(enemy.DMG_min[1:4])
        magical_total_max = sum(enemy.DMG[1:4])
        if enemy.DMG[4] > 0:  # Profundo siempre máximo
            magical_total_max += enemy.DMG[4]
            magical_total_min += enemy.DMG[4]

        magical_dmg = (
            f"{magical_total_min}-{magical_total_max}" if magical_total_max > 0 else "0"
        )

        # Formatear defensa - mostrar la física principalmente
        if isinstance(enemy.DEF, (list, tuple)):
            defense = f"{enemy.DEF[0]}"  # Mostrar defensa física
        else:
            defense = f"{enemy.DEF}"

        zone_table.add_row(
            enemy.NAME, str(enemy.HP_M), physical_dmg, magical_dmg, defense
        )

    console.print(zone_table)


############################## Main Menu Functions ##############################


_MAIN_MENU_ASCII = '''
  ___  ___  ___ 
 | _ \\| _ \\/ __|
 |   /|  _/ (_ |
 |_|_\\|_|  \\___|
'''

def display_main_menu() -> int:


    options = [
        (1, "Inspeccionar las zonas"),
        (2, "Ir a una zona"),
        (3, "Tienda"),
        (4, "Inventario"),
        (5, "Mirar Stats / Maestrias"),
        (6, "Acciones de Zona"),
        (7, "Gestión de Mods"),
        (8, "Ver Items Disponibles"),
        (9, "Guardar / Cargar (3 Slots)"),
        (10, "Compañeros"),
        (11, "Árbol de Habilidades"),
        (12, "Mesa de Encantamientos"),
        (13, "Yunque de Crafteo"),
        (14, "Base"),
        (15, "Tablón de Misiones"),
        (16, "⚔ Guilds"),
    ]
    if CONFIG["DEBUG"]["ENABLED"]:
        options.append((17, "DEBUG"))
    options.append((0, "Salir del juego"))

    index_by_value = {v: i for i, (v, _) in enumerate(options)}
    state = {"idx": index_by_value.get(6, 0), "buf": "", "done": False, "selected": None, "dirty": True}

    def _render():
        # ASCII header
        header = Text.from_markup(f"[bold yellow]{_MAIN_MENU_ASCII}[/bold yellow]")
        header = Align.center(header)

        # Table
        t = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
        t.add_column("Opción", style="bright_yellow", justify="right")
        t.add_column("Sep", style="bright_yellow")
        t.add_column("Acción", style="bright_white")

        for i, (val, label) in enumerate(options):
            selected = i == state["idx"]
            if selected:
                opt = f"[bold bright_yellow]► {val}[/]"
                lab = f"[bold bright_yellow]{label}[/]"
                sep = f"[bold bright_yellow]·[/]"
            else:
                opt = f"  {val}"
                lab = label
                sep = "·"
            t.add_row(opt, sep, lab)

        footer_str = "Selecciona una opción: "
        if state["buf"]:
            footer_str += f"[dim]↑/↓ + Enter | número: {state['buf']}[/dim]"
        else:
            footer_str += "[dim]↑/↓ + Enter | número[/dim]"
        footer = Align.center(Text.from_markup(footer_str))

        return Panel(
            Group(header, "", Align.center(t), "", footer),
            border_style="yellow",
            title=f"[bold yellow]RPG[/bold yellow]",
            padding=(1, 2),
        )

    def _on_press(key):
        if state["done"]: return
        if key == "esc": return  # ESC no hace nada en el menú principal
        if key == "up":
            state["idx"] = (state["idx"] - 1) % len(options)
            state["dirty"] = True
        elif key == "down":
            state["idx"] = (state["idx"] + 1) % len(options)
            state["dirty"] = True
        elif key == "backspace":
            state["buf"] = state["buf"][:-1]
            state["dirty"] = True
        elif key == "enter":
            if state["buf"]:
                try:
                    typed = int(state["buf"])
                except ValueError:
                    state["buf"] = ""; state["dirty"] = True; return
                if typed in index_by_value:
                    state["selected"] = typed
                    state["done"] = True
                    try: stop_listening()
                    except Exception: pass
                    return
                state["buf"] = ""; state["dirty"] = True; return
            state["selected"] = options[state["idx"]][0]
            state["done"] = True
            try: stop_listening()
            except Exception: pass
        elif key.isdigit():
            state["buf"] += key
            state["dirty"] = True

    
    kb = None
    with keyboard_listener_scope():
        kb = threading.Thread(
            target=listen_keyboard,
            kwargs={"on_press": _on_press, "sequential": False, "delay_second_char": 0.0, "until": None},
            daemon=True,
        )
        kb.start()
        try:
            with Live(_render(), console=console, screen=True, auto_refresh=False) as live:
                while not state["done"]:
                    if state["dirty"]:
                        state["dirty"] = False
                        live.update(_render(), refresh=True)
                    sp.sleep(0.01)
        finally:
            state["done"] = True
            try: stop_listening()
            except Exception: pass
            if kb and kb.is_alive(): kb.join(timeout=3.0)
            sp.sleep(0.05)

    return int(state["selected"]) if state["selected"] is not None else options[state["idx"]][0]


def get_validated_input(prompt: str, valid_options: List[int]) -> int:
    """
    Get and validate numeric input from the user.
    Ignores entradas vacías (p. ej. Enter residual tras pause) para evitar
    mostrar "Por favor ingresa un número válido" al volver al menú.
    """
    # Fallback numérico simple: se usa cuando no hay menú Rich asociado.
    while True:
        try:
            user_input = input(prompt).strip()
            if user_input == "":
                continue
            value = int(user_input)
            if value in valid_options:
                return value
            console.print(
                f"[warning]Por favor ingresa una opción válida ({', '.join(map(str, valid_options))})[/warning]"
            )
        except ValueError:
            console.print("[warning]Por favor ingresa un número válido[/warning]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[info]Saliendo del juego...[/info]")
            sys.exit(0)


def get_zone_shop_name(zone_key: str) -> str:
    return f"{zone_key}Shop"


def run_zone_gathering(zone_key: str) -> bool:
    """Run gathering minigame using zone material IDs from DataStats."""
    try:
        zone_data = Read(os.path.join("Data", "DataStats.json"), zone_key, None)
        if not zone_data or not isinstance(zone_data, list):
            console.print("[warning]No se encontraron datos de recolección para esta zona.[/warning]")
            return False

        gathering_data = zone_data[0].get("Gathering", {})
        materials_raw = gathering_data.get("Materials", [])
        if not materials_raw:
            console.print("[warning]Esta zona no tiene materiales para recolectar.[/warning]")
            return False

        material_ids = []
        for token in materials_raw:
            try:
                material_ids.append(int(str(token).split("_")[0]))
            except (ValueError, IndexError):
                continue

        if not material_ids:
            console.print("[warning]No hay IDs de materiales validos en esta zona.[/warning]")
            return False

        
        item_manager_inst = get_item_manager()
        materials_table = item_manager_inst.items_data.get("TYPE:Materials", {})

        candidates = []
        for material_data in materials_table.values():
            # Algunos mods podrían inyectar items con STATIC_ID, otros con MATERIAL_ID
            mat_id = material_data.get("MATERIAL_ID", material_data.get("STATIC_ID"))
            if mat_id in material_ids:
                candidates.append(material_data)

        if not candidates:
            console.print("[warning]No se encontraron materiales configurados para esta zona.[/warning]")
            return False

        selected_data = random.choice(candidates)
        # Usar el ItemManager para instanciar el material correctamente
        mat_id = selected_data.get("MATERIAL_ID", selected_data.get("STATIC_ID"))
        material_obj = item_manager_inst.create_item_object(
            item_id=mat_id, 
            cMaterial=cMaterial,
            material_lookup=True
        )
        if not material_obj:
            console.print("[danger]Error instanciando el material.[/danger]")
            return False
            
        material_obj.ID = material_obj.MATERIAL_ID
        material_obj.name = material_obj.Name

        console.print(f"[info]Iniciando recolección de [bold]{material_obj.Name}[/bold]...[/info]")
        ok = Gathering_init.gather(material_obj, getattr(player, 'tool', None), [])
        if ok:
            vInventory.addObject(material_obj)
            console.print(f"[success]Material obtenido: {material_obj.Name}[/success]")
            return True
        return False
    except Exception as e:
        console.print(f"[danger]Error en recolección: {e}[/danger]")
        return False


############################## Main Game Loop ##############################


def main():
    """Main game loop function that handles player actions and game state"""
    global chosen_area, tick, enemy, player, item_manager, shop_manager

    # Apply automatic regeneration and check inventory
    player.Check(vInventory)

    
    # Clear the screen for better UI
    os.system("cls" if os.name == "nt" else "clear")

    # Display player status
    display_player_status()

    # Display main menu
    main_input = display_main_menu()

    # Process player choice
    if main_input == 0:
        # Exit game option
        console.print("[info]¿Estás seguro de que quieres salir? (s/n)[/info]")
        confirm = input().lower()
        if confirm == "s" or confirm == "si":
            console.print("[info]¡Gracias por jugar! Hasta pronto.[/info]")
            sys.exit(0)

    elif main_input == 1: # Inspect
        
        try:
            all_zones = get_all_zones()

            if not all_zones:
                console.print("[warning]No hay zonas disponibles[/warning]")
                wait_for_enter()

            console.print(Panel("Información de Zonas", style="menu_title"))

            # Iterar dinámicamente sobre TODAS las zonas
            for zone_key, zone_info in all_zones.items():
                zone_name = zone_info["name"]
                zone_desc = zone_info["desc"]
                zone_color = zone_info["color"]
                enemies = zone_info["enemies"]

                # Crear tabla para esta zona
                zone_table = Table(title=zone_name, title_style=zone_color)
                zone_table.add_column("Enemigo", style=zone_color)
                zone_table.add_column("Vida", justify="right")
                zone_table.add_column("Daño Físico", justify="right")
                zone_table.add_column("Daño Mágico", justify="right")

                console.print(
                    f"\n[bold {zone_color}]{zone_name}[/bold {zone_color}]: {zone_desc}"
                )

                # Mostrar enemigos de esta zona
                for enemy_data in enemies:
                    # Formatear daño multi-tipo
                    # DMG es [Físico, Térmico, Tierra, Eléctrico, Profundo]
                    dmg = enemy_data.get("DMG", [0, 0, 0, 0, 0])
                    dmg_min = enemy_data.get("DMG_min", [0, 0, 0, 0])

                    physical_dmg = f"{dmg_min[0]}-{dmg[0]}" if dmg[0] > 0 else "0"

                    # Sumar todos los daños mágicos (Térmico, Tierra, Eléctrico, Profundo)
                    magical_total_min = sum(dmg_min[1:4]) if len(dmg_min) > 3 else 0
                    magical_total_max = sum(dmg[1:4]) if len(dmg) > 3 else 0

                    # Agregar daño profundo (siempre máximo)
                    if len(dmg) > 4 and dmg[4] > 0:
                        magical_total_max += dmg[4]
                        magical_total_min += dmg[4]

                    magical_dmg = (
                        f"{magical_total_min}-{magical_total_max}"
                        if magical_total_max > 0
                        else "0"
                    )

                    zone_table.add_row(
                        enemy_data.get("NAME", "???"),
                        str(enemy_data.get("HP_M", 0)),
                        physical_dmg,
                        magical_dmg,
                    )

                console.print(zone_table)

                # Mostrar si es de un mod
                if zone_info.get("source") == "mod":
                    console.print(f"[dim]  📦 Zona agregada por mod[/dim]")

        except Exception as e:
            console.print(
                f"[danger]Error al cargar la información de zonas: {str(e)}[/danger]"
            )

            traceback.print_exc()

        wait_for_enter()

        console.print("\n[info]Presiona Enter para continuar... ↵ [/info]")
        wait_for_enter()

    elif main_input == 2: # Go to a Zone
        try:
            
            # Get all zones
            zones_list = get_zones_for_selector()

            if not zones_list:
                console.print("[warning]No hay zonas disponibles[/warning]")
                wait_for_enter()

            zone_options = []
            for idx, (zone_key, zone_name, zone_color) in enumerate(zones_list, 1):
                zone_options.append((idx, f"[{zone_color}]{zone_name}[/{zone_color}]"))
            zone_options.append((len(zones_list) + 1, "Salir de la zona actual"))

            zone_input = interactive_menu_select(
                title="Selección de Zona",
                subtitle="Usa ↑/↓ + Enter o escribe el número",
                options=zone_options,
                prompt="Zona: ",
                default_value=1,
                border_style="yellow",
            )

            # Opción de salir
            if zone_input == len(zones_list) + 1:
                if chosen_area is not None:
                    console.print("[info]Saliendo de la zona actual...[/info]")
                    chosen_area = None
                    enemy = None
                else:
                    console.print(
                        "[danger]No puedes irte sin haber escogido una zona antes...[/danger]"
                    )
                wait_for_enter()

            # Selección de zona
            zone_key, zone_name, zone_color = zones_list[zone_input - 1]
            chosen_area = zone_key

            console.print(f"[info]Cargando zona de {zone_name}...[/info]")
            enemy = zone_loader(chosen_area)

            if enemy:
                console.print(
                    f"[success]Has entrado a {zone_name}. Ten cuidado con {enemy.NAME}![/success]"
                )

                # Disparar evento de entrada a zona (para mods)
                try:
                    mod_api = get_mod_api()
                    mod_api.fire_event("zone_entered", player, chosen_area)
                except:
                    pass

                # La tienda de zona ahora se abre desde la opción 7 (submenú de zona).
                if shop_manager:
                    shop_items = shop_manager.get_shop_items(get_zone_shop_name(zone_key))
                    if shop_items:
                        console.print(f"[dim]La zona {zone_name} tiene tienda disponible.[/dim]")
                    else:
                        console.print(f"[dim]No hay tiendas disponibles en {zone_name}[/dim]")
            else:
                console.print(
                    f"[warning]No se pudo cargar un enemigo de {zone_name}.[/warning]"
                )

        except Exception as e:
            console.print(f"[danger]Error al cargar zonas: {str(e)}[/danger]")

            traceback.print_exc()

        wait_for_enter()

        # Pause to read message
        console.print("\n[info]Presiona Enter para continuar... ↵ [/info]")
        wait_for_enter()

    elif main_input == 3: # Shops
        
        console.print("[info]Entrando a la tienda...[/info]")

        try:
            shop_choice = interactive_menu_select(
                title="Tiendas",
                subtitle="Selecciona una tienda",
                options=[
                    (1, "Tienda General"),
                    (2, "Armería"),
                    (3, "Tienda de Armaduras"),
                    (4, "Tienda Mágica"),
                    (0, "Cancelar"),
                ],
                prompt="Tienda: ",
                default_value=1,
                border_style="yellow",
            )

            if shop_choice == 1:
                display_shop("GeneralStore", player, item_manager)
            elif shop_choice == 2:
                display_shop("WeaponShop", player, item_manager)
            elif shop_choice == 3:
                display_shop("ArmorShop", player, item_manager)
            elif shop_choice == 4:
                display_shop("MagicShop", player, item_manager)
            elif shop_choice == 0:
                console.print("[info]Cancelando...[/info]")

        except Exception as e:
            console.print(f"[danger]Error en la tienda: {str(e)}[/danger]")

        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()
         

    elif main_input == 4: # Inventory
        
        try:
            open_inventory_menu(vInventory, player)
        except Exception as e:
            console.print(f"[danger]Error al mostrar el inventario: {str(e)}[/danger]")

        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()
            
    elif main_input == 5: # Stats (3 pestañas con flechas izquierda/derecha)
        
        os.system("cls" if os.name == "nt" else "clear")

        _TAB_NAMES = ["Stats Principales", "Mastery Armas/Armadura", "Mastery Recoleccion", "Estado del Jugador"]
        _st = {"tab": 0, "done": False, "dirty": True}

        def _tab_header(active):
            h = Text()
            for i, name in enumerate(_TAB_NAMES):
                if i == active:
                    h.append(f" {name} ", style="bold black on bright_yellow")
                else:
                    h.append(f" {name} ", style="dim")
                if i < len(_TAB_NAMES) - 1:
                    h.append("  ")
            h.append("\n")
            h.append("<- -> para cambiar pestana  |  Enter/Q para cerrar", style="dim")
            return h

        def _tab_stats():
            dn = ["Fisica", "Termica", "Tierra", "Electrica", "Profunda"]
            ds = " | ".join([f"{n}: {player.DEF[i]}" for i, n in enumerate(dn) if player.DEF[i] > 0]) or "Ninguna"
            bp = [f"{n}: {player.DefensePercentage[i]:.1f}%" for i, n in enumerate(dn)
                  if (player.DefensePercentage[i] if isinstance(player.DefensePercentage, list) else 0) > 0]
            bs = " | ".join(bp) or "0%"
            wn = getattr(player.weapon, "name", getattr(player.weapon, "Name", "???")) if player.weapon else "Punos (sin arma)"
            ep = (player.EXP / player.EXP_M * 100) if player.EXP_M > 0 else 0
            eb = "█" * min(int(ep / 100 * 20), 20) + "░" * max(0, 20 - min(int(ep / 100 * 20), 20))
            ar = []
            for sn, sl in [("helmet","Casco"),("armor","Armadura"),("boots","Botas"),
                           ("ring","Anillo 1"),("ring2","Anillo 2"),("ring3","Anillo 3")]:
                eq = getattr(player, sn, None)
                if eq: ar.append(f"  {sl}: [bright_white]{getattr(eq,'name',getattr(eq,'Name','???'))}[/]")
            a_s = "\n".join(ar) or "  [dim]Nada equipado[/]"
            cr = []
            for c in getattr(player, "companion", []):
                st = "vivo" if getattr(c, "is_alive", True) else "caido"
                cr.append(f"  [{st}] {getattr(c,'name','?')} ({getattr(c,'companion_class','?')}) HP:{getattr(c,'Health',0):.0f}/{getattr(c,'Health_max',0):.0f}")
            c_s = "\n".join(cr) or "  [dim]Ninguno[/]"
            bf = [f"  + [green]{getattr(b,'Name',getattr(b,'name','?'))}[/]" for b in getattr(player,"appliedbuffs",[])]
            bf += [f"  - [red]{getattr(d,'Name',getattr(d,'name','?'))}[/]" for d in getattr(player,"applieddebuffs",[])]
            b_s = "\n".join(bf) or "  [dim]Ninguno[/]"
            g = Table.grid(padding=(0,0))
            g.add_column()
            g.add_row(Text.from_markup(
                f"[bold yellow]Atributos Principales[/]\n"
                f"[bold red]HP:[/] {player.Health:.0f}/{player.Health_max:.0f}\n"
                f"[bold blue]MP:[/] {player.Mana:.0f}/{player.Mana_max:.0f}  [dim](Regen: +{player.ManaRegen:.1f}/turno)[/]\n"
                f"[bold yellow]Nivel:[/] {player.Level}   [dim]Puntos: {player.lvlPoints}[/]\n"
                f"[green]EXP:[/] {eb}  {int(player.EXP)}/{int(player.EXP_M)} ({ep:.1f}%)\n"
                f"[gold1]Oro:[/] {int(player.Gold):,}\n"
                f"\n[bold cyan]Combate[/]\n"
                f"Arma: {wn}\n"
                f"Defensa Plana: {ds}\n"
                f"Bloqueo %: {bs}\n"
                f"Barrera: {int(player.Barrier)}\n"
                f"Evasion: {player.Evasion}%\n"
                f"Contra-ataque: {player.CounterAttack}%\n"
                f"\n[bold bright_magenta]Equipamiento[/]\n{a_s}\n"
                f"\n[bold bright_green]Companeros[/]\n{c_s}\n"
                f"\n[bold bright_yellow]Efectos Activos[/]\n{b_s}"))
            return g

        def _tab_mastery():
            mgr = ensure_mastery(player)
            t = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
            t.add_column("Tipo", style="bold", min_width=10)
            t.add_column("Skill", style="cyan", min_width=14)
            t.add_column("Nivel", justify="center", style="yellow", min_width=7)
            t.add_column("EXP", justify="left", min_width=20)
            t.add_column("Atributo", justify="left")
            for sk in mgr.weapon_masteries.values():
                fl = int(15 * sk.exp_current / max(sk.exp_to_next, 1))
                bar = "[bright_yellow]" + "█" * fl + "[/bright_yellow][dim]" + "░" * (15 - fl) + "[/dim]"
                t.add_row("Arma", sk.name, f"{sk.current_level}/{MASTERY_MAX_LEVEL}",
                          Text.from_markup(f"{bar} {sk.exp_current:.0f}/{sk.exp_to_next:.0f}"),
                          Text.from_markup(sk.bonus_description))
            for sk in mgr.armor_masteries.values():
                fl = int(15 * sk.exp_current / max(sk.exp_to_next, 1))
                bar = "[bright_yellow]" + "█" * fl + "[/bright_yellow][dim]" + "░" * (15 - fl) + "[/dim]"
                t.add_row("Armadura", sk.name, f"{sk.current_level}/{MASTERY_MAX_LEVEL}",
                          Text.from_markup(f"{bar} {sk.exp_current:.0f}/{sk.exp_to_next:.0f}"),
                          Text.from_markup(sk.bonus_description))
            return t

        def _tab_gathering():
            t = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
            t.add_column("Skill", style="cyan", min_width=14)
            t.add_column("Nivel", justify="center", style="yellow", min_width=7)
            t.add_column("EXP", justify="left", min_width=20)
            t.add_column("Eficiencia", justify="left", style="bright_green")
            t.add_column("Bonus XP", justify="left", style="bright_cyan")
            for sk_key, sk in Gathering_init.gathering.items():
                fl = int(15 * sk.exp_total / max(sk.exp_to_next_lvl, 1))
                bar = "[bright_yellow]" + "█" * fl + "[/bright_yellow][dim]" + "░" * (15 - fl) + "[/dim]"
                t.add_row(sk_key.capitalize(), f"{sk.current_level}/{sk.MAX_LEVEL}",
                          Text.from_markup(f"{bar} {sk.exp_total:.1f}/{sk.exp_to_next_lvl:.0f}"),
                          f"+{sk.efficiency_pct:.0f}% velocidad", f"+{sk.xp_pct:.0f}% XP")
            return t

        def _tab_player_state():
            from Modules.ModulesFunctions.WeatherSystem import get_weather_manager
            g = Table.grid(padding=(0, 0))
            g.add_column()

            # ── Clima ──────────────────────────────────────────────────────
            wm = get_weather_manager()
            w = wm.get_current_weather()
            weather_lines = [f"[bold cyan]🌦 Clima actual:[/] {w.icon} [bold]{w.name}[/]"]
            weather_lines.append(f"[dim]{w.description}[/dim]")
            weather_lines.append("")
            _mod_labels = {
                "attack": "Ataque", "defense": "Defensa", "magic_def": "Def. Mágica",
                "agi": "Agilidad", "counter": "Contraataque", "evasion": "Evasión"
            }
            for k, v in w.combat_mods.items():
                if v == 1.0:
                    continue
                label = _mod_labels.get(k, k)
                pct = (v - 1.0) * 100
                color = "green" if pct > 0 else "red"
                sign = "+" if pct > 0 else ""
                weather_lines.append(f"  [{color}]{label}: {sign}{pct:.0f}%[/{color}]")
            if all(v == 1.0 for v in w.combat_mods.values()):
                weather_lines.append("  [dim]Sin modificadores de combate.[/dim]")

            # ── Buffs activos ───────────────────────────────────────────────
            buff_lines = [""]
            buff_lines.append("[bold green]✨ Buffs activos:[/]")
            raw_buffs = getattr(player, "appliedbuffs", [])
            if raw_buffs:
                for b in raw_buffs:
                    name = getattr(b, "Name", getattr(b, "name", "Buff desconocido"))
                    desc = getattr(b, "description", getattr(b, "Description", ""))
                    buff_lines.append(f"  [green]+ {name}[/green]" + (f" [dim]— {desc}[/dim]" if desc else ""))
            else:
                buff_lines.append("  [dim]Ningún buff activo.[/dim]")

            # ── Debuffs activos ─────────────────────────────────────────────
            buff_lines.append("")
            buff_lines.append("[bold red]💀 Debuffs activos:[/]")
            raw_debuffs = getattr(player, "applieddebuffs", [])
            if raw_debuffs:
                for d in raw_debuffs:
                    name = getattr(d, "Name", getattr(d, "name", "Debuff desconocido"))
                    desc = getattr(d, "description", getattr(d, "Description", ""))
                    buff_lines.append(f"  [red]- {name}[/red]" + (f" [dim]— {desc}[/dim]" if desc else ""))
            else:
                buff_lines.append("  [dim]Ningún debuff activo.[/dim]")

            # ── Tax debuffs (Guild) ─────────────────────────────────────────
            gm = get_guild_manager()
            pg = gm.get_player_guild()
            buff_lines.append("")
            buff_lines.append("[bold yellow]💰 Impuestos de Guild:[/]")
            if pg:
                tax = getattr(pg, "tax_rate", 5)
                buff_lines.append(f"  Tasa actual: [bold]{tax}%[/bold]")
                tax_debuffs = pg.get_tax_debuffs() if hasattr(pg, "get_tax_debuffs") else {}
                if tax_debuffs:
                    for attr, val in tax_debuffs.items():
                        pct = (val - 1.0) * 100
                        sign = "+" if pct > 0 else ""
                        color = "red" if pct < 0 else "green"
                        buff_lines.append(f"  [{color}]{attr.capitalize()}: {sign}{pct:.0f}%[/{color}]")
                elif tax <= 10:
                    buff_lines.append("  [dim]Sin penalizaciones (tasa ≤ 10%).[/dim]")
            else:
                buff_lines.append("  [dim]No perteneces a ningún gremio.[/dim]")

            g.add_row(Text.from_markup("\n".join(weather_lines + buff_lines)))
            return g

        def _build_panel():
            tab = _st["tab"]
            hdr = _tab_header(tab)
            content = [_tab_stats, _tab_mastery, _tab_gathering, _tab_player_state][tab]()
            return Panel(Group(hdr, Text(""), content),
                         title=f"[bold yellow]{_TAB_NAMES[tab]}[/]", border_style="yellow", padding=(1, 2))

        def _on_key(key):
            if _st["done"]: return
            if key == "left":
                _st["tab"] = (_st["tab"] - 1) % len(_TAB_NAMES)
                _st["dirty"] = True
            elif key == "right":
                _st["tab"] = (_st["tab"] + 1) % len(_TAB_NAMES)
                _st["dirty"] = True
            elif key in ("enter", "q", "esc"):
                _st["done"] = True
                try: stop_listening()
                except Exception: pass

        _kb = None
        with keyboard_listener_scope():
            _kb = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_key, "sequential": False, "delay_second_char": 0.0, "until": None}, daemon=True)
            _kb.start()
            try:
                with Live(_build_panel(), console=console, screen=True, auto_refresh=False) as live:
                    while not _st["done"]:
                        if _st["dirty"]:
                            _st["dirty"] = False
                            live.update(_build_panel(), refresh=True)
                        sp.sleep(0.05)
            finally:
                _st["done"] = True
                try: stop_listening()
                except Exception: pass
                if _kb and _kb.is_alive(): _kb.join(timeout=3.0)

    elif main_input == 6: # Zones
        if chosen_area is None:
            console.print("[danger]No has escogido ningún lugar. Debes ir a una zona primero.[/danger]")
            console.print("\n[info]Presiona Enter para volver al menú principal... ↵ [/info]")
            wait_for_enter()
        else:
            while True:
                zone_input = interactive_menu_select(
                    title=f"Zona actual: {chosen_area}",
                    subtitle="¿Qué quieres hacer?",
                    options=[
                        (1, "Luchar"),
                        (2, "Tienda actual de la zona"),
                        (3, "Recolectar"),
                        (4, "Devolverse al menú principal"),
                    ],
                    prompt="Acción: ",
                    default_value=1,
                    border_style="yellow",
                )

                if zone_input == 1:
                    if enemy is None:
                        enemy = zone_loader(chosen_area)
                        if enemy is None:
                            console.print("[danger]No hay enemigo disponible en esta zona.[/danger]")
                            wait_for_enter()
                            continue

                    combat_round = 1
                    combat_active = True

                    while combat_active:
                        render_combat_menu(player, enemy, combat_round)
                        player_debuffs = apply_debuffs(player)
                        
                        # Apply Tax debuffs if player in guild
                        gm = get_guild_manager()
                        pg = gm.get_player_guild()
                        if pg:
                            tax_debuffs = pg.get_tax_debuffs()
                            if tax_debuffs:
                                for attr, val in tax_debuffs.items():
                                    if attr not in player_debuffs:
                                        player_debuffs[attr] = val
                                    else:
                                        player_debuffs[attr] *= val # Cumulative
                        
                        if player_debuffs:
                            debuff_text = ", ".join([f"{attr}: {val}" for attr, val in player_debuffs.items()])
                            console.print(f"[warning]Debuffs activos (incl. Taxes): {debuff_text}[/warning]")

                        combat_action = interactive_menu_select(
                            title="Acciones de Combate",
                            subtitle="Selecciona tu acción",
                            options=[
                                (1, "Atacar"),
                                (2, "Abrir Inventario"),
                                (3, "Intentar huir"),
                            ],
                            prompt="Acción: ",
                            default_value=1,
                            border_style="danger",
                        )
                        os.system("cls" if os.name == "nt" else "clear")

                        if combat_action == 1:
                            console.print("\n[bold]¡Tu turno![/bold]")
                            sp.sleep(1.0)
                            damage_dealt = _perform_attack(player, enemy, console)
                            
                            # Registrar daño en mastery de arma
                            try:
                                mm = ensure_mastery(player)
                                lvlup_msg = mm.register_damage_dealt(player, float(damage_dealt))
                                if lvlup_msg:
                                    console.print(f"[bold green]{lvlup_msg}[/bold green]")
                            except Exception:
                                pass

                            # ── Acción de los Compañeros ────────────────────────────
                            for comp in player.companion:
                                if comp.is_alive and enemy.HP > 0:
                                    console.print(f"\n[cyan]>> Turno de {comp.name} <<[/cyan]")
                                    sp.sleep(0.5)
                                    c_opts = [(1, "Atacar")]
                                    c_class = getattr(comp, 'c_class', 'Daño')
                                    
                                    if c_class == "Curandero":
                                        c_opts.extend([(2, "Curar al jugador"), (3, "Curar a todo el equipo")])
                                    elif c_class == "Soporte":
                                        c_opts.append((2, f"Debilitar a {enemy.NAME}"))
                                    
                                    c_action = interactive_menu_select(
                                        title=f"Acción de {comp.name}",
                                        subtitle="Selecciona habilidad:",
                                        options=c_opts,
                                        prompt="Acción: ",
                                        default_value=1,
                                        border_style="cyan"
                                    )
                                    
                                    if c_action == 1:
                                        _perform_attack(comp, enemy, console)
                                    elif c_action == 2 and c_class == "Curandero":
                                        cura = player.Health_max * 0.20
                                        player.Health = min(player.Health_max, player.Health + cura)
                                        console.print(f"[success]{comp.name} curó a {player.name} por {cura:.1f} HP![/success]")
                                    elif c_action == 3 and c_class == "Curandero":
                                        cura_p = player.Health_max * 0.15
                                        player.Health = min(player.Health_max, player.Health + cura_p)
                                        for c in player.companion:
                                            if c.is_alive: c.Health = min(c.Health_max, c.Health + c.Health_max * 0.15)
                                        console.print(f"[success]{comp.name} curó a todo el equipo.[/success]")
                                    elif c_action == 2 and c_class == "Soporte":
                                        bm = get_buff_manager()
                                        debuff = bm.create_buff("5_debuff", "companion_skill")
                                        if debuff:
                                            if not hasattr(enemy, 'active_buffs'): enemy.active_buffs = []
                                            enemy.active_buffs.append(debuff)
                                            console.print(f"[warning]{comp.name} aplicó {debuff.name} a {enemy.NAME}![/warning]")

                            # ── ¿Murió el enemigo? ────────────────────────────────
                            if enemy.HP <= 0:
                                console.print(f"[success]¡Has derrotado a {enemy.NAME}![/success]")

                                # ── Modificadores globales de EXP y Oro ──────────
                                _world_cfg   = CONFIG.get("WORLD", {})
                                _exp_mod     = float(_world_cfg.get("GLOBAL_EXP_MODIFIER",  1))
                                _gold_mod    = float(_world_cfg.get("GLOBAL_GOLD_MODIFIER", 1))
                                _loot_mod    = float(_world_cfg.get("GLOBAL_LOOT_MODIFIER", 1))
                                _lq_pos      = float(_world_cfg.get("GLOBAL_LOOT_QUALITY_MODIFIER_POSITIVE", 1))
                                _lq_neg      = float(_world_cfg.get("GLOBAL_LOOT_QUALITY_MODIFIER_NEGATIVE", 1))

                                exp_gain  = int(enemy.EXP_TO_PLAYER * _exp_mod)
                                gold_gain = int(enemy.GOLD          * _gold_mod)
                                player.EXP  += exp_gain
                                player.Gold += gold_gain
                                console.print(f"[success]Ganaste {exp_gain} EXP y {gold_gain} oro.[/success]")

                                # ── Drop de loot ─────────────────────────────────
                                _base_loot_chance = 0.30
                                _loot_chance = min(1.0, _base_loot_chance * _loot_mod)
                                if random.random() < _loot_chance:
                                    # Intentar usar loot table del enemigo o zona
                                    _loot_pool = getattr(enemy, "LOOT_TABLE", None)
                                    if not _loot_pool:
                                        _loot_pool = getattr(enemy, "loot_ids", None)
                                    # Fallback a lista de IDs genérica
                                    _fallback_ids = [1, 10, 21, 32, 43, 54]
                                    if _loot_pool and isinstance(_loot_pool, (list, tuple)) and len(_loot_pool) > 0:
                                        loot_id = random.choice(_loot_pool)
                                    else:
                                        loot_id = random.choice(_fallback_ids)

                                    loot_item = load_item_by_id(loot_id, cWeapon, cEquippableItems, cObject, cTool)
                                    if loot_item:
                                        # Aplicar modificador de objeto al loot
                                        try:
                                            from Modules.ModulesManager.ItemModifierSystem import roll_and_apply_modifier, get_item_display_name
                                            mod = roll_and_apply_modifier(loot_item, _lq_pos, _lq_neg)
                                            display_name = get_item_display_name(loot_item)
                                            mod_txt = f" [{('red' if mod.is_negative else 'green')}]{mod.icon} {mod.name}[/]" if mod else ""
                                        except Exception:
                                            display_name = getattr(loot_item, 'name', getattr(loot_item, 'Name', 'Objeto'))
                                            mod_txt = ""
                                        console.print(f"[success]¡Soltó: {display_name}{mod_txt}![/success]")
                                        vInventory.addObject(loot_item)

                                quest_manager.update_kill_quest(enemy.NAME, player)
                                player.level_up()

                                # ── V4: Guild Taxes Trigger ──────────────────────────
                                gm = get_guild_manager()
                                pg = gm.get_player_guild()
                                if pg:
                                    pg.fight_count += 1
                                    if pg.fight_count >= 5:
                                        tax_msg = pg.apply_taxes()
                                        console.print(f"\n[bold yellow]💰 {tax_msg}[/bold yellow]")
                                        pg.fight_count = 0
                                
                                if input("¿Seguir en esta zona? (s/n): ").lower() == 's':
                                    enemy = zone_loader(chosen_area)
                                else:
                                    enemy = None
                                combat_active = False
                                break

                            # ── Turno del enemigo ──
                            console.print("\n[bold]¡Turno del enemigo![/bold]")
                            sp.sleep(1.0)
                            alive_companions = [c for c in player.companion if c.is_alive]
                            possible_targets = [player] + alive_companions
                            attack_target = random.choice(possible_targets)

                            damage_taken = _perform_attack(enemy, attack_target, console)

                            if attack_target is player:
                                try:
                                    mm = ensure_mastery(player)
                                    lvlup_msg = mm.register_damage_received(player, float(damage_taken))
                                    if lvlup_msg: console.print(f"[bold cyan]{lvlup_msg}[/bold cyan]")
                                except Exception: pass
                                
                                if player.Health <= 0:
                                    console.print("[danger]¡Has sido derrotado![/danger]")
                                    player.Health = max(1, int(player.Health_max * 0.1))
                                    player.Gold = max(0, player.Gold * 0.5)
                                    combat_active = False
                                    enemy = None
                                    break
                            else:
                                if not attack_target.is_alive:
                                    console.print(f"[bold red]💀 {attack_target.name} ha caído![/bold red]")

                        elif combat_action == 2:
                            open_inventory_menu(vInventory, player)
                            continue

                        elif combat_action == 3:
                            if random.random() < 0.5:
                                console.print("[success]¡Escapaste![/success]")
                                combat_active = False
                                enemy = None
                                break
                            else:
                                console.print("[danger]¡No pudiste escapar![/danger]")
                                _perform_attack(enemy, player, console)
                                if player.Health <= 0:
                                    combat_active = False
                                    enemy = None
                                    break

                        # Mostrar estados al final de ronda
                        status_table = Table(show_header=False, box=None)
                        p_hp_bar, p_hp_pct = create_status_bar(player.Health, player.Health_max, "green", True)
                        e_hp_bar, e_hp_pct = create_status_bar(enemy.HP, enemy.HP_M, "red", True)
                        status_table.add_row(f"[bold]{player.name}[/bold]", f"{p_hp_bar} {p_hp_pct}%")
                        status_table.add_row(f"[bold red]{enemy.NAME}[/bold red]", f"{e_hp_bar} {e_hp_pct}%")
                        console.print(status_table)
                        combat_round += 1
                        sp.sleep(0.5)

                elif zone_input == 2:
                    try:
                        sm = get_shop_manager()
                        z_shop = get_zone_shop_name(chosen_area)
                        display_shop(z_shop, player, get_item_manager())
                    except Exception as e:
                        console.print(f"[warning]Tienda no disponible: {e}[/warning]")
                    wait_for_enter()

                elif zone_input == 3:
                    try:
                        run_zone_gathering(chosen_area)
                    except Exception as e:
                        console.print(f"[danger]Error en recolección: {e}[/danger]")
                    wait_for_enter()

                elif zone_input == 4:
                    break
         

    elif main_input == 7:
        # Gestión de Mods
        console.print(Panel(" Gestión de Mods", style="cyan"))

        mod_loader_instance = get_mod_loader()
        mod_api_instance = get_mod_api()

        while True:
            console.print("\n1.  Mostrar mods cargados")
            console.print("2.  Cargar/Recargar todos los mods")
            console.print("3.  Estado del sistema de mods")
            console.print("0.  Volver al menú principal")

            mod_choice = get_validated_input("Selecciona una opción: ", [0, 1, 2, 3])

            if mod_choice == 0:
                break
            elif mod_choice == 1:
                mod_loader_instance.display_mods_info()

                # Mostrar comandos personalizados si existen
                if mod_api_instance.custom_commands:
                    console.print("\n[bold]Comandos personalizados disponibles:[/bold]")
                    for cmd_name, cmd_info in mod_api_instance.custom_commands.items():
                        console.print(
                            f"• {cmd_name}: {cmd_info.get('description', 'Sin descripción')}"
                        )

            elif mod_choice == 2:
                console.print("[info]Cargando mods...[/info]")
                mod_loader_instance.load_all_mods()
                console.print("[success]Proceso de carga completado.[/success]")

            elif mod_choice == 3:
                console.print(Panel(" Estado del Sistema de Mods", style="green"))

                loaded_count = len(mod_loader_instance.loaded_mods)
                console.print(f"Mods cargados: {loaded_count}")

                # Estadísticas de la API
                console.print(
                    f"Items registrados: {len(mod_api_instance.registered_items)}"
                )
                console.print(
                    f"Enemigos registrados: {len(mod_api_instance.registered_enemies)}"
                )
                console.print(
                    f"Zonas registradas: {len(mod_api_instance.registered_zones)}"
                )
                console.print(
                    f"Comandos personalizados: {len(mod_api_instance.custom_commands)}"
                )
                console.print(
                    f"Manejadores de eventos: {sum(len(handlers) for handlers in mod_api_instance.event_handlers.values())}"
                )

            console.print("\n[info]Presiona Enter para continuar...[/info]")
            wait_for_enter()



    elif main_input == 8:
        console.clear()
        console.print(Panel("Items Disponibles en el Juego", style="menu_title"))

        try:
            if item_manager:
                item_manager.list_all_items(detailed=True)
            else:
                console.print("[warning]Sistema de items no inicializado[/warning]")
        except Exception as e:
            console.print(f"[danger]Error al listar items: {str(e)}[/danger]")

        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()
         


    elif main_input == 9:
        game_state = save_load_menu(
            player, vInventory, chosen_area, item_manager,
            console, interactive_menu_select, wait_for_enter
        )
        if game_state is not None:
            # Se cargó una partida: restaurar zona
            chosen_area = game_state.get("chosen_area", chosen_area)
            enemy = None  # Resetear enemigo; se recargará al entrar a la zona

    elif main_input == 10:

        try:
            companion_management_menu(
                player, vInventory, console,
                interactive_menu_select, wait_for_enter
            )
        except Exception as e:
            console.print(f"[danger]Error en gestión de compañeros: {e}[/danger]")

    elif main_input == 11:
        player.Points()

    elif main_input == 12:
        
        open_enchantment_menu(player, vInventory)

    elif main_input == 13:
        
        open_crafting_menu(player, vInventory)

    elif main_input == 14:
        try:
            
            if not hasattr(player, "base_manager") or player.base_manager is None:
                player.base_manager = BaseManager()
            # Inyectar edificios de mods
            try:
                mod_api_inst = get_mod_api()
                injected = mod_api_inst.integrate_with_base_manager(player.base_manager)
                if injected:
                    console.print(f"[dim]{injected} edificio(s) de mods cargado(s).[/dim]")
            except Exception:
                pass
            ensure_mastery(player)
            open_base_menu(player, vInventory, console, interactive_menu_select, wait_for_enter)
        except Exception as e:
            console.print(f"[danger]Error al abrir la Base: {e}[/danger]")
            traceback.print_exc()
            wait_for_enter()

    elif main_input == 15:
        quest_manager.open_quest_board(player, vInventory)

    elif main_input == 16:
        try:
            open_guild_menu(player, console)
        except Exception as e:
            console.print(f"[danger]Error en el menú de Guilds: {e}[/danger]")
            import traceback; traceback.print_exc()
            sp.sleep(2)

    elif main_input == 17 and CONFIG["DEBUG"]["ENABLED"]:
        try:
            from Modules.ModulesMenu.DebugMenu import open_enhanced_debug_menu
            open_enhanced_debug_menu(
                player=player, 
                inventory=vInventory, 
                gathering_init=Gathering_init, 
                mod_loader=get_mod_loader(), 
                mod_api=get_mod_api(), 
                chosen_area=chosen_area
            )
        except Exception as e:
            console.print(f"[danger]Error en el menú debug: {e}[/danger]")
            sp.sleep(2)


# Save functions handled by Modules.ModulesFunctions.SaveSystem


def init_game():
    global player, item_manager, shop_manager, chosen_area
    
    item_manager = get_item_manager()
    shop_manager = get_shop_manager()
    mod_loader_instance = get_mod_loader()
    mod_loader_instance.load_all_mods()

    get_mod_api().integrate_with_quest_manager(quest_manager)

    has_saves = False
    for s in [1, 2, 3]:
        info = get_slot_info(s)
        if info["exists"]:
            has_saves = True
            break
            
    if has_saves:
        console.print("[info]Se han encontrado partidas guardadas.[/info]")
        response = interactive_menu_select(
            title="Partidas Encontradas",
            options=[(1, "Cargar Partida"), (2, "Nueva Partida")],
            prompt="Selecciona: ",
            default_value=1,
            border_style="yellow"
        )
        if response == 1:
            # Crear player temporal para cargar encima
            player = cPlayer("Cargando...", None)
            game_state = save_load_menu(
                player, vInventory, chosen_area, item_manager,
                console, interactive_menu_select, wait_for_enter
            )
            if game_state is not None:
                chosen_area = game_state.get("chosen_area", chosen_area)
            else:
                # Si canceló carga, iniciar nueva partida
                player = setup_player()
        else:
            player = setup_player()
    else:
        player = setup_player()

# Execution
if __name__ == "__main__":
    try:
        # Init TODO: Looks like shii
        init_game()

        # Main game loop
        while True:
            try:
                main()
            except Exception as e:
                console.print(f"[danger]Error en el bucle principal: {str(e)}[/danger]")
                sp.sleep(2)
    except Exception as e:
        console.print(f"[danger]Error: {str(e)}[/danger]")
        sys.exit(1) # 67