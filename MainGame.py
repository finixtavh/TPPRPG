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
from sshkeyboard import listen_keyboard, stop_listening, keyboard_listener_scope
from rich.live import Live

# Modules/ 
from Modules.Loader import Write, Read
from Modules.ModLoader import get_mod_loader, get_mod_api
from Modules.ItemManager import get_item_manager, load_item_by_id
from Modules.ShopManager import get_shop_manager, display_shop
from Modules.GatheringMasterySystem import cTool, cMaterial, Gathering_init
from Modules.EnchantmentSystem import open_enchantment_menu
from Modules.MasterySystem import ensure_mastery, MASTERY_MAX_LEVEL
from Modules.input_utils import wait_for_enter, interactive_menu_select
from Modules.InventoryMenu import open_inventory_menu
from Modules.SaveSystem import save_load_menu
from Modules.ZoneManager import get_all_zones, get_zones_for_selector
from Modules.BuffManager import get_buff_manager
from Modules.CraftingSystem import open_crafting_menu
from Modules.BaseSystem import BaseManager, open_base_menu
from Modules.CompanionSystem import (
    cCompanion,
    companion_management_menu,
    COMPANION_REVIVAL_GOLD_COST,)
from Modules.debug import (
    setup_logging,
    attach_console_logging,
    install_exception_hooks,
    log_imported_modules,
    dump_debug_snapshot,)
from Modules.setup import (
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

        # PASO 5: Seleccionar enemigo aleatorio
        enemy_random = random.choice(enemy_list)
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

    zone_text = chosen_area if chosen_area is not None else "Ninguna"
    left = Text.from_markup(
        f"[bold]Nombre:[/bold] {player.name} [dim](Nivel {player.Level})[/dim]"
    )
    right = Text.from_markup(
        f"[bold yellow]Oro:[/bold yellow] {player.Gold}   [bold]Zona:[/bold] {zone_text}"
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


player = setup_player()


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
    header = Text.from_markup(f"[bold]Combate - Ronda {combat_round}[/]")

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
        (5, "Mirar Stats"),
        (6, "Acciones de Zona"),
        (7, "Gestión de Mods"),
        (8, "Ver Items Disponibles"),
        (9, "Guardar"),
        (10, "Compañeros"),
        (11, "Árbol de Habilidades"),
        (12, "Mesa de Encantamientos"),
        (13, "Yunque de Crafteo"),
        (14, "Base"),
    ]
    if CONFIG["DEBUG"]["ENABLED"]:
        options.append((15, "DEBUG"))
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
            kwargs={"on_press": _on_press, "sequential": False, "delay_second_char": 0.0},
            daemon=True,
        )
        kb.start()
        try:
            with Live(_render(), console=console, refresh_per_second=30, transient=True) as live:
                while not state["done"]:
                    if state["dirty"]:
                        state["dirty"] = False
                        live.update(_render())
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
        # Usar el ItemManager para instanciar el material correctamente, o hacerlo manual
        mat_id = selected_data.get("MATERIAL_ID", selected_data.get("STATIC_ID"))
        material_obj = item_manager_inst.create_item_object(
            item_id=mat_id, cMaterial=cMaterial
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

        _TAB_NAMES = ["Stats Principales", "Mastery Armas/Armadura", "Mastery Recoleccion"]
        _st = {"tab": 0, "done": False}

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

        def _build_panel():
            tab = _st["tab"]
            hdr = _tab_header(tab)
            content = [_tab_stats, _tab_mastery, _tab_gathering][tab]()
            return Panel(Group(hdr, Text(""), content),
                         title=f"[bold yellow]{_TAB_NAMES[tab]}[/]", border_style="yellow", padding=(1, 2))

        def _on_key(key):
            if _st["done"]: return
            if key == "left":
                _st["tab"] = (_st["tab"] - 1) % len(_TAB_NAMES)
            elif key == "right":
                _st["tab"] = (_st["tab"] + 1) % len(_TAB_NAMES)
            elif key in ("enter", "q", "escape"):
                _st["done"] = True
                try: stop_listening()
                except Exception: pass

        _kb = None
        with keyboard_listener_scope():
            _kb = threading.Thread(target=listen_keyboard, kwargs={"on_press": _on_key, "sequential": False, "delay_second_char": 0.0}, daemon=True)
            _kb.start()
            try:
                with Live(_build_panel(), console=console, refresh_per_second=20, transient=True) as live:
                    while not _st["done"]:
                        live.update(_build_panel())
                        sp.sleep(0.05)
            finally:
                _st["done"] = True
                try: stop_listening()
                except Exception: pass
                if _kb and _kb.is_alive(): _kb.join(timeout=3.0)

    elif main_input == 6: # Zones
        if chosen_area is None:
            console.print(
                "[danger]No has escogido ningún lugar. Debes ir a una zona primero.[/danger]"
            )
            console.print(
                "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
            )
            wait_for_enter()
        else:
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
                        return

                combat_round = 1
                combat_active = True

                # ── Regenerar barrera al inicio del combate ──
                # Los buffs/habilidades definen player.Barrier; aquí se
                # restaura al valor que tengan otorgado.
                # La barrera la setean los buffs/skills antes del combate.

                while combat_active:
                    render_combat_menu(player, enemy, combat_round)
                    player_debuffs = apply_debuffs(player)
                    if player_debuffs:
                        debuff_text = ", ".join(
                            [f"{attr}: {val}" for attr, val in player_debuffs.items()]
                        )
                        console.print(f"[warning]Debuffs activos: {debuff_text}[/warning]")

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
                        sp.sleep(2.5)
                        damage_dealt = player.attack(enemy)
                        if damage_dealt is not None:
                            console.print(
                                f"[success]¡Has atacado a {enemy.NAME} por {damage_dealt} puntos de daño![/success]"
                            )
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
                                console.print(f"\n[cyan]>> Turno de {comp.name} (Clase: {getattr(comp, 'c_class', 'Daño')}) <<[/cyan]")
                                sp.sleep(0.5)
                                c_opts = [(1, "Atacar")]
                                c_class = getattr(comp, 'c_class', 'Daño')
                                
                                if c_class == "Curandero":
                                    c_opts.extend([(2, "Curar al jugador (+20% MAX HP)"), (3, "Curar a todo el equipo (+15% MAX HP)")])
                                elif c_class == "Soporte":
                                    c_opts.append((2, f"Debilitar a {enemy.NAME} (Debuff/Defesa -10%)"))
                                
                                c_action = interactive_menu_select(
                                    title=f"Acción de {comp.name}",
                                    subtitle="Selecciona habilidad:",
                                    options=c_opts,
                                    prompt="Acción: ",
                                    default_value=1,
                                    border_style="cyan"
                                )
                                
                                if c_action == 1:
                                    comp.attack(enemy)
                                    
                                elif c_action == 2 and c_class == "Curandero":
                                    cura = player.Health_max * 0.20
                                    player.Health = min(player.Health_max, player.Health + cura)
                                    console.print(f"[success]{comp.name} usó magia sagrada curando a {player.name} por {cura:.1f} HP![/success]")
                                    
                                elif c_action == 3 and c_class == "Curandero":
                                    cura_p = player.Health_max * 0.15
                                    player.Health = min(player.Health_max, player.Health + cura_p)
                                    for c in player.companion:
                                        if c.is_alive:
                                            c.Health = min(c.Health_max, c.Health + c.Health_max * 0.15)
                                    console.print(f"[success]{comp.name} emanó un aura sanadora, curando a todo el equipo.[/success]")
                                    
                                elif c_action == 2 and c_class == "Soporte":
                                    
                                    bm = get_buff_manager()
                                    # Intentar aplicar debuff 5_debuff u otro
                                    debuff = bm.create_buff("5_debuff", "companion_skill")
                                    if not debuff:
                                        # Generic fallback
                                        enemy.DEF = [max(0, d * 0.9) for d in enemy.DEF]
                                        console.print(f"[warning]{comp.name} lanzó una maldición, bajando un 10% las defensas de {enemy.NAME}.[/warning]")
                                    else:
                                        if not hasattr(enemy, 'active_buffs'): enemy.active_buffs = []
                                        enemy.active_buffs.append(debuff)
                                        console.print(f"[warning]{comp.name} aplicó {debuff.name} a {enemy.NAME}![/warning]")

                        # ── ¿Murió el enemigo? ────────────────────────────────
                        if enemy.HP <= 0:
                            console.print(f"[success]¡Has derrotado a {enemy.NAME}![/success]")
                            exp_gain = enemy.EXP_TO_PLAYER
                            gold_gain = enemy.GOLD
                            player.EXP += exp_gain
                            player.Gold += gold_gain
                            console.print(
                                f"[success]Ganaste {exp_gain} puntos de experiencia y {gold_gain} de oro.[/success]"
                            )
                            if random.random() < 0.3:
                                loot_table = {
                                    1: [1, 10, 20, 30, 40, 50],
                                    2: [2, 11, 21, 31, 41, 51],
                                    3: [3, 12, 22, 32, 42, 52],
                                }
                                enemy_level = min(3, max(1, player.Level // 3))
                                possible_loot = loot_table.get(enemy_level, [1])
                                loot_id = random.choice(possible_loot)
                                loot_item = load_item_by_id(
                                    loot_id, cWeapon, cEquippableItems, cObject, cTool
                                )
                                if loot_item:
                                    console.print(
                                        f"[success]¡El enemigo dejó caer: {getattr(loot_item, 'Name', getattr(loot_item, 'name', 'Objeto'))}![/success]"
                                    )
                                    vInventory.addObject(loot_item)
                            if player.EXP >= player.EXP_M:
                                while player.EXP >= player.EXP_M:
                                    player.Level += 1
                                    player.EXP -= player.EXP_M
                                    player.EXP_M = int(player.EXP_M * 1.5)
                                    player.Health_max += 20
                                    player.Mana_max += 10
                                    player.Health = player.Health_max
                                    player.Mana = player.Mana_max
                                    console.print(
                                        f"[success]¡Subiste al nivel {player.Level}![/success]"
                                    )
                            input_done = input("Seguir?:: ")
                            if input_done:
                                enemy = zone_loader(chosen_area)
                            combat_active = False
                            break

                        # ── Turno del enemigo: elige objetivo aleatorio ────────
                        console.print("\n[bold]¡Turno del enemigo![/bold]")
                        sp.sleep(2.5)

                        alive_companions = [c for c in player.companion if c.is_alive]
                        possible_targets = [player] + alive_companions
                        attack_target = random.choice(possible_targets)

                        damage_taken = enemy.attack(attack_target)

                        if attack_target is player:
                            if damage_taken is not None:
                                console.print(
                                    f"[danger]{enemy.NAME} te ataca a ti por {damage_taken:.1f} puntos de daño![/danger]"
                                )
                                # Registrar daño recibido en mastery de armadura
                                try:
                                    mm = ensure_mastery(player)
                                    lvlup_msg = mm.register_damage_received(player, float(damage_taken))
                                    if lvlup_msg:
                                        console.print(f"[bold cyan]{lvlup_msg}[/bold cyan]")
                                except Exception:
                                    pass
                            if player.Health <= 0:
                                console.print(
                                    f"[danger]¡Has sido derrotado por {enemy.NAME}![/danger]"
                                )
                                console.print("[danger]Game Over[/danger]")
                                player.Health = max(1, int(player.Health_max * 0.1))
                                player.Gold = max(1, (player.Gold - (player.Health * 0.6)))
                                combat_active = False
                                break
                        else:
                            # El enemigo atacó a un compañero
                            console.print(
                                f"[danger]{enemy.NAME} ataca a {attack_target.name} por {damage_taken:.1f} puntos de daño![/danger]"
                            )
                            if not attack_target.is_alive:
                                console.print(
                                    f"[bold red]💀 {attack_target.name} ha caído en combate! "
                                    f"Puedes revivirlo con {COMPANION_REVIVAL_GOLD_COST} oro o un ítem de resurrección.[/bold red]"
                                )

                    elif combat_action == 2:
                        open_inventory_menu(vInventory, player)
                        console.print("[info]Has revisado tu inventario.[/info]")
                        # In this rewrite we don't automatically make the enemy attack after viewing inventory so the player can actually equip or check items safely.

                    elif combat_action == 3:
                        flee_chance = CONFIG["COMBAT"]["CHANCE_TO_FLEE"]
                        player_agi = getattr(player, "AGI", 0) or 0
                        enemy_agi = getattr(enemy, "AGI", 0) or 0
                        flee_chance = flee_chance + (player_agi - enemy_agi) / 100
                        flee_chance = max(0.05, min(0.95, flee_chance))
                        if random.random() < flee_chance:
                            console.print("[success]¡Has logrado escapar del combate![/success]")
                            combat_active = False
                            break
                        console.print("[danger]¡No pudiste escapar![/danger]")
                        console.print(
                            "\n[bold]¡El enemigo te ataca mientras intentas huir![/bold]"
                        )
                        sp.sleep(1)
                        damage_taken = enemy.attack(player)
                        bonus_damage = damage_taken * 0.2
                        player.Health = max(0, player.Health - bonus_damage)
                        damage_taken = damage_taken + bonus_damage
                        console.print(
                            f"[danger]{enemy.NAME} te ha atacado por {damage_taken:.1f} puntos de daño![/danger]"
                        )
                        if player.Health <= 0:
                            console.print(
                                f"[danger]¡Has sido derrotado por {enemy.NAME}![/danger]"
                            )
                            console.print("[danger]Game Over[/danger]")
                            player.Health = max(1, int(player.Health_max * 0.1))
                            combat_active = False
                            break

                    print("\n")
                    if player.Barrier > 0:
                        player_hp_bar, player_hp_percent = create_hp_barrier_bar(
                            player.Health, player.Health_max, player.Barrier
                        )
                        barrier_tag = f" [bright_cyan]+{int(player.Barrier)}🛡️[/bright_cyan]"
                    else:
                        player_hp_bar, player_hp_percent = create_status_bar(
                            player.Health, player.Health_max, "green", True
                        )
                        barrier_tag = ""
                    player_mp_bar, player_mp_percent = create_status_bar(
                        player.Mana, player.Mana_max, "blue", True
                    )
                    enemy_hp_bar, enemy_hp_percent = create_status_bar(
                        enemy.HP, enemy.HP_M, "red", True
                    )
                    enemy_mp_bar, enemy_mp_percent = create_status_bar(
                        enemy.MP, enemy.MP_M, "blue", True
                    )
                    status_table = Table(show_header=False, box=None)
                    status_table.add_column("Entity", style="bright_white")
                    status_table.add_column("HP", style="bright_white")
                    status_table.add_column("MP", style="bright_white")
                    status_table.add_row(
                        f"[bold]{player.name}[/bold]",
                        f"{player_hp_bar} {player_hp_percent}%{barrier_tag}",
                        f"{player_mp_bar} {player_mp_percent}%",
                    )
                    status_table.add_row(
                        f"[bold red]{enemy.NAME}[/bold red]",
                        f"{enemy_hp_bar} {enemy_hp_percent}%",
                        f"{enemy_mp_bar} {enemy_mp_percent}%",
                    )
                    console.print(status_table)
                    combat_round += 1
                    sp.sleep(CONFIG["COMBAT"]["DELAY_BETWEEN_ROUNDS"])

                console.print(
                    "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
                )
                wait_for_enter()

            elif zone_input == 2:
                if not shop_manager:
                    console.print("[warning]El sistema de tiendas no esta inicializado.[/warning]")
                else:
                    zone_shop = get_zone_shop_name(chosen_area)
                    shop_items = shop_manager.get_shop_items(zone_shop)
                    if shop_items:
                        display_shop(zone_shop, player, item_manager)
                    else:
                        console.print("[warning]Esta zona no tiene tienda disponible.[/warning]")
                wait_for_enter()

            elif zone_input == 3:
                run_zone_gathering(chosen_area)
                console.print(
                    "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
                )
                wait_for_enter()

            elif zone_input == 4:
                console.print("[info]Regresando al menu principal...[/info]")
         

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

    elif main_input == 15 and CONFIG["DEBUG"]["ENABLED"]:
        debug_input = int(
            input("""DEBUG: 
                  [1] ARMAS
                  [2] GOLD Y EXP
                  [3] Mastery & Gathering
                  [4] LOOK Variables
                  [5] AÑADIR COMPAÑERO DE PRUEBA
                  > """)
        )
        if debug_input == 1:
            vInventory.addObject(load_item_by_id(3, cWeapon, cEquippableItems, cObject, cTool))
            vInventory.addObject(load_item_by_id(100, cWeapon, cEquippableItems, cObject, cTool))

        elif debug_input == 2:
            player.Gold += 9999999
            player.EXP += 9999999
        elif debug_input == 3:
            for skill in Gathering_init.gathering.values():
                skill.current_level += 10
                print("Done")
            for skill in Gathering_init.weapons.values():
                skill.current_level += 10
                print("Done")
        elif debug_input == 4:
            debug_text = dump_debug_snapshot(
                player=player,
                inventory=vInventory,
                mod_loader=get_mod_loader(),
                mod_api=None,
                current_state=None,
                chosen_area=chosen_area,
            )
            console.print(Panel(debug_text, title="Debug Variables", border_style="magenta"))
            app_logger.debug("Debug snapshot requested from in-game debug menu.")
            wait_for_enter()
        elif debug_input == 5:
            # Añadir compañero de prueba
            test_comp = cCompanion(
                companion_id="lyra",
                name="Lyra",
                health_max=75,
                mana_max=50,
            )
            # Darle un arma básica si hay en el inventario
            for slot in vInventory.slots:
                if isinstance(slot.item, cWeapon):
                    test_comp.equip_weapon(slot.item)
                    break
            player.companion.append(test_comp)
            console.print(f"[success]Compañero de prueba '{test_comp.name}' añadido.[/success]")
            wait_for_enter()


# Add a save game function
def save_game() -> bool:
    """
    Save the current game state to a file.

    Returns:
        True if save was successful, False otherwise
    """
    try:
        # Create save data structure
        save_data = {
            "player": {
                "name": player.name,
                "level": player.Level,
                "health": player.Health,
                "health_max": player.Health_max,
                "mana": player.Mana,
                "mana_max": player.Mana_max,
                "exp": player.EXP,
                "exp_max": player.EXP_M,
                "gold": player.Gold,
            },
            "game_state": {"area": chosen_area, "tick": tick},
            "timestamp": str(sp.time()),
        }

        # Write save data to file (full overwrite; Loader.Write expects key/content for merge)
        save_path = os.path.normpath("./Data/SaveGame.json")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=4)
        console.print("[success]Juego guardado correctamente.[/success]")
        return True
    except Exception as e:
        console.print(f"[danger]Error al guardar el juego: {str(e)}[/danger]")
        return False


# Add a load game function
def load_game() -> bool:
    """
    Load a saved game from file.

    Returns:
        True if load was successful, False otherwise
    """
    global player, chosen_area, tick

    try:
        # Check if save file exists
        if not os.path.exists("./Data/SaveGame.json"):
            console.print("[warning]No hay partidas guardadas.[/warning]")
            return False

        # Load save data
        save_data = Read("./Data/SaveGame.json", None, None)

        if not save_data:
            console.print("[warning]Archivo de guardado vacío o corrupto.[/warning]")
            return False

        # Restore player state
        player_data = save_data.get("player", {})
        game_state = save_data.get("game_state", {})

        # Restore basic player attributes
        player.name = player_data.get("name", player.name)
        player.Level = player_data.get("level", player.Level)
        player.Health = player_data.get("health", player.Health)
        player.Health_max = player_data.get("health_max", player.Health_max)
        player.Mana = player_data.get("mana", player.Mana)
        player.Mana_max = player_data.get("mana_max", player.Mana_max)
        player.EXP = player_data.get("exp", player.EXP)
        player.EXP_M = player_data.get("exp_max", player.EXP_M)
        player.Gold = player_data.get("gold", player.Gold)

        # Restore game state
        chosen_area = game_state.get("area", None)
        tick = game_state.get("tick", 0)

        console.print("[success]Partida cargada correctamente.[/success]")
        return True
    except Exception as e:
        console.print(f"[danger]Error al cargar la partida: {str(e)}[/danger]")
        return False


def init_game():
    global item_manager, shop_manager
    
    item_manager = get_item_manager()
    shop_manager = get_shop_manager()
    mod_loader_instance = get_mod_loader()
    mod_loader_instance.load_all_mods()

    if os.path.exists("./Data/SaveGame.json"):
        console.print("[info]Se ha encontrado una partida guardada.[/info]")
        console.print("¿Deseas cargar la partida guardada? (s/n)")
        response = input().lower()

        if response == "s" or response == "si":
            load_game()
            
    resultados = []

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

