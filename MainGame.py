from rich.console import Console, Group
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from typing import List, Dict, Optional, Tuple, Any, Union
from Modules.Loader import Write, Read
from Modules.setup import (
    cEnemy,
    cWeapon,
    cEquippableItems,
    cObject,
    setup_player,
    vInventory,
    enemy_loader,
)


# Modules/ 
from Modules.ModLoader import get_mod_loader, get_mod_api
from Modules.ItemManager import get_item_manager, load_item_by_id, load_items_by_type
from Modules.ShopManager import get_shop_manager, display_shop
from Modules.EquipmentSystem import EquipmentManager, equip_menu
from Modules.GatheringMasterySystem import cTool, cMaterial, Gathering_init
from Modules.debug import (
    setup_logging,
    attach_console_logging,
    install_exception_hooks,
    log_imported_modules,
    dump_debug_snapshot,
)
from Modules.input_utils import wait_for_enter, interactive_menu_select
from Modules.InventoryMenu import open_inventory_menu

# ---   ---
import json
import random
import time as sp
import os
import sys
from enum import Enum, auto

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
        import traceback

        traceback.print_exc()
        return None


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

    # Barras HP / MP
    health_bar, health_percent = create_status_bar(
        player.Health, player.Health_max, "red"
    )
    mana_bar, mana_percent = create_status_bar(player.Mana, player.Mana_max, "blue")

    bars = Table.grid(padding=(0, 1))
    bars.add_column()
    bars.add_row(
        Text.from_markup(
            f"[bold red]HP:[/bold red] {health_bar} [dim]{health_percent}%[/]"
        )
    )
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


def render_combat_menu(player, enemy, combat_round: int) -> None:
    """UI de combate: jugador vs enemigo + acciones (inspirado en Interfaces/03_combat_ui.py)."""
    # Cabecera de ronda
    header = Text.from_markup(f"[bold]Combate - Ronda {combat_round}[/]")

    # Barras de vida/mana
    p_hp_bar, p_hp_pct = create_status_bar(player.Health, player.Health_max, "green")
    p_mp_bar, p_mp_pct = create_status_bar(player.Mana, player.Mana_max, "blue")
    e_hp_bar, e_hp_pct = create_status_bar(enemy.HP, enemy.HP_M, "red")
    e_mp_bar, e_mp_pct = create_status_bar(enemy.MP, enemy.MP_M, "blue")

    player_block = Panel(
        f"[bold]{player.name}[/]\n"
        f"[red]HP:[/red] {p_hp_bar} [dim]{p_hp_pct}%[/]\n"
        f"[blue]MP:[/blue] {p_mp_bar} [dim]{p_mp_pct}%[/]",
        border_style="success",
        padding=(0, 1),
    )
    enemy_block = Panel(
        f"[bold red]{enemy.NAME}[/bold red]\n"
        f"[red]HP:[/red] {e_hp_bar} [dim]{e_hp_pct}%[/]\n"
        f"[blue]MP:[/blue] {e_mp_bar} [dim]{e_mp_pct}%[/]",
        border_style="danger",
        padding=(0, 1),
    )

    top = Columns([player_block, enemy_block], equal=True, expand=True)

    actions = Table(show_header=False, box=None, padding=(0, 2))
    actions.add_column("Opción", style="bright_white")
    actions.add_column("Acción", style="bright_white")
    actions.add_row("[1]", "Atacar")
    actions.add_row("[2]", "Usar objeto")
    actions.add_row("[3]", "Intentar huir")

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


def display_main_menu() -> int:
    options = [
        (1, "Inspeccionar las zonas"),
        (2, "Ir a una zona"),
        (3, "Tienda"),
        (4, "Inventario"),
        (5, "Usar objetos consumibles"),
        (6, "Gestión de Equipamiento"),
        (7, "Acciones de Zona"),
        (8, "Mirar Stats"),
        (9, "Gestión de Mods"),
        (10, "Ver Items Disponibles"),
        (11, "Guardar"),
        (12, "DEBUG"),
        (0, "Salir del juego"),
    ]
    return interactive_menu_select(
        title="RPG Game Menu",
        subtitle="Selecciona una opción",
        options=options,
        prompt="Selecciona una opción: ",
        default_value=7,
        border_style="menu_title",
    )


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

        all_items = Read(os.path.join("Data", "DataItems.json"), None, None)
        materials_table = all_items.get("TYPE:Materials", {}) if isinstance(all_items, dict) else {}

        candidates = []
        for material_data in materials_table.values():
            if material_data.get("MATERIAL_ID") in material_ids:
                candidates.append(material_data)

        if not candidates:
            console.print("[warning]No se encontraron materiales configurados para esta zona.[/warning]")
            return False

        selected_data = random.choice(candidates)
        material_obj = cMaterial(
            MATERIAL_ID=selected_data.get("MATERIAL_ID"),
            TypeStr=selected_data.get("Material_Type", "Unknown"),
            Name=selected_data.get("Name", "Material"),
            Hardness=selected_data.get("Hardness", 10),
            SkillName=selected_data.get("SkillName", "mining"),
        )
        material_obj.ID = material_obj.MATERIAL_ID
        material_obj.MaxStack = selected_data.get("MaxStack", 99)
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
    global chosen_area, tick, enemy, player, current_state, item_manager, shop_manager

    # Apply automatic regeneration and check inventory
    player.Check(vInventory)
    player.Mana = min(player.Mana + player.ManaRegen, player.Mana_max)
    amd = int(input("asdasd::"))
    if amd == 1:
        open_inventory_menu(vInventory, player)
    
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

    elif main_input == 1:
        # Set current state
        """Inspeccionar las zonas - VERSIÓN DINÁMICA"""
        try:
            from Modules.ZoneManager import get_all_zones

            # Obtener TODAS las zonas (JSON + Mods)
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
            import traceback

            traceback.print_exc()

        wait_for_enter()

        console.print("\n[info]Presiona Enter para continuar... ↵ [/info]")
        wait_for_enter()

    elif main_input == 2:
        """Ir a una zona - VERSIÓN DINÁMICA"""
        # Set current state

        try:
            from Modules.ZoneManager import get_zones_for_selector

            # Obtener lista de TODAS las zonas disponibles
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
                    from Modules.ModLoader import get_mod_api

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
            import traceback

            traceback.print_exc()

        wait_for_enter()

        # Pause to read message
        console.print("\n[info]Presiona Enter para continuar... ↵ [/info]")
        wait_for_enter()

    elif main_input == 3:
        # ===== TIENDA CON SISTEMA JSON =====
        
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
         
    # ===================================

    elif main_input == 4:
        # Set current state
        
        console.print(Panel("Inventario", style="menu_title"))

        try:
            player.Check(vInventory)
            vInventory.PrintObjects()
        except Exception as e:
            console.print(f"[danger]Error al mostrar el inventario: {str(e)}[/danger]")

        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()
         

    elif main_input == 5:
        # Usar objetos consumibles
        
        console.print(Panel("Usar Objetos Consumibles", style="menu_title"))

        try:
            # Mostrar solo objetos consumibles/usables
            usable_items = []

            for i, item in enumerate(vInventory.Objects):
                if isinstance(item, cObject) or (
                    hasattr(item, "isUsable") and item.isUsable
                ):
                    usable_items.append((i, item))

            if not usable_items:
                console.print(
                    "[warning]No tienes objetos consumibles en el inventario.[/warning]"
                )
            else:
                options = [(0, "Cancelar")]
                for idx, (_, item) in enumerate(usable_items, 1):
                    item_name = item.Name if hasattr(item, "Name") else item.name
                    options.append((idx, item_name))
                choice = interactive_menu_select(
                    title="Objetos Consumibles",
                    subtitle="Selecciona un objeto para usar",
                    options=options,
                    prompt="Objeto: ",
                    default_value=1 if len(options) > 1 else 0,
                    border_style="yellow",
                )

                if choice > 0:
                    selected_item = usable_items[choice - 1][1]

                    # Usar el objeto
                    if hasattr(selected_item, "use"):
                        selected_item.use(player)
                        console.print(
                            f"[success]Has usado {selected_item.Name if hasattr(selected_item, 'Name') else selected_item.name}[/success]"
                        )
                    elif hasattr(selected_item, "HealthRestore"):
                        player.Health = min(
                            player.Health + selected_item.HealthRestore,
                            player.Health_max,
                        )
                        console.print(
                            f"[success]Restauraste {selected_item.HealthRestore} HP![/success]"
                        )
                    if (
                        hasattr(selected_item, "ManaRestore")
                        and selected_item.ManaRestore > 0
                    ):
                        player.Mana = min(
                            player.Mana + selected_item.ManaRestore, player.Mana_max
                        )
                        console.print(
                            f"[success]Restauraste {selected_item.ManaRestore} MP![/success]"
                        )

                    # Remover del inventario (1 unidad)
                    vInventory.remove_item(selected_item, 1)
                else:
                    console.print("[info]Cancelado.[/info]")

        except Exception as e:
            console.print(f"[danger]Error al usar objeto: {str(e)}[/danger]")

        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()

    # ===== NUEVA OPCIÓN: GESTIÓN DE EQUIPAMIENTO =====
    elif main_input == 6:
        console.clear()

        try:
            equip_menu(player, vInventory)
        except Exception as e:
            console.print(
                f"[danger]Error en gestión de equipamiento: {str(e)}[/danger]"
            )

         
    # ===============================================

    elif main_input == 7:
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
                            (2, "Usar objeto"),
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

                        console.print("\n[bold]¡Turno del enemigo![/bold]")
                        sp.sleep(2.5)
                        damage_taken = enemy.attack(player)
                        if damage_taken is not None:
                            console.print(
                                f"[danger]{enemy.NAME} te ha atacado por {damage_taken} puntos de daño![/danger]"
                            )
                        if player.Health <= 0:
                            console.print(
                                f"[danger]¡Has sido derrotado por {enemy.NAME}![/danger]"
                            )
                            console.print("[danger]Game Over[/danger]")
                            player.Health = max(1, int(player.Health_max * 0.1))
                            player.Gold = max(1, (player.Gold - (player.Health * 0.6)))
                            combat_active = False
                            break

                    elif combat_action == 2:
                        console.print("[info]Inventario:[/info]")
                        usable_items = []
                        for i, item in enumerate(vInventory.Objects):
                            if hasattr(item, "isUsable") and item.isUsable:
                                usable_items.append(item)
                                console.print(f"[{i + 1}] {item.Name}")
                        if not usable_items:
                            console.print("[warning]No tienes objetos utilizables.[/warning]")
                            sp.sleep(2)
                            continue
                        valid_items = list(range(1, len(usable_items) + 1))
                        item_options = [(0, "Cancelar")]
                        for i, it in enumerate(usable_items, 1):
                            item_options.append((i, getattr(it, "Name", getattr(it, "name", "Objeto"))))
                        item_choice = interactive_menu_select(
                            title="Usar objeto",
                            subtitle="Selecciona un consumible",
                            options=item_options,
                            prompt="Objeto: ",
                            default_value=1 if len(item_options) > 1 else 0,
                            border_style="yellow",
                        )
                        if item_choice == 0:
                            console.print("[info]Cancelando uso de objeto...[/info]")
                            continue
                        selected_item = usable_items[item_choice - 1]
                        if hasattr(selected_item, "use"):
                            selected_item.use(player)
                        elif hasattr(selected_item, "HealthRestore"):
                            player.Health = min(
                                player.Health + getattr(selected_item, "HealthRestore", 0),
                                player.Health_max,
                            )
                        if (
                            hasattr(selected_item, "ManaRestore")
                            and getattr(selected_item, "ManaRestore", 0) > 0
                        ):
                            player.Mana = min(
                                player.Mana + selected_item.ManaRestore, player.Mana_max
                            )
                        vInventory.remove_item(selected_item, 1)
                        console.print(
                            f"[success]Has usado {getattr(selected_item, 'Name', getattr(selected_item, 'name', 'objeto'))}[/success]"
                        )
                        console.print("\n[bold]¡Turno del enemigo![/bold]")
                        sp.sleep(1)
                        damage_taken = enemy.attack(player)
                        console.print(
                            f"[danger]{enemy.NAME} te ha atacado por {damage_taken} puntos de daño![/danger]"
                        )
                        if player.Health <= 0:
                            console.print(
                                f"[danger]¡Has sido derrotado por {enemy.NAME}![/danger]"
                            )
                            console.print("[danger]Game Over[/danger]")
                            player.Health = max(1, int(player.Health_max * 0.1))
                            combat_active = False
                            break

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
                    player_hp_bar, player_hp_percent = create_status_bar(
                        player.Health, player.Health_max, "green", True
                    )
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
                        f"{player_hp_bar} {player_hp_percent}%",
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

    elif main_input == 8:
        # Set current state
         

        # ===== STATS CON EQUIPAMIENTO =====
        if CONFIG["DISPLAY"]["SHOW_FULL_STATS"]:
            stats_lines = [
                f"[bold]Nombre:[/bold] {player.name} - [bold]Nivel:[/bold] {player.Level}",
                "",
                f"[bold red]Vida:[/bold red] [red]{player.Health}/{player.Health_max}[/red]",
                f"[bold blue]Mana:[/bold blue] [blue]{player.Mana}/{player.Mana_max}[/blue] ([cyan]Regen: {player.ManaRegen}[/cyan])",
                "",
                f"[bold]Defensa:[/bold] {player.DEF[0]} puntos // [gray]Porcentaje de defensa: {player.DefensePercentage}%[/gray]",
                f"[bold]Agilidad:[/bold] {player.AGI}",
                f"[bold]Prob. ContraAtaque:[/bold] {player.CounterAttack}%",
                f"[bold]Prob. Evasion:[/bold] {player.Evasion}%",
                "",
                f"[bold yellow]Oro:[/bold yellow] {player.Gold}",
                f"[bold cyan]Experiencia:[/bold cyan] {player.EXP}/{player.EXP_M}",
            ]
        else:
            stats_lines = [
                f"[bold]Nombre:[/bold] {player.name} - [bold]Nivel:[/bold] {player.Level}",
                "",
                f"[bold red]Vida:[/bold red] [red]{player.Health}/{player.Health_max}[/red]",
                f"[bold blue]Mana:[/bold blue] [blue]{player.Mana}/{player.Mana_max}[/blue] ([cyan]Regen: {player.ManaRegen}[/cyan])",
                "",
                f"[bold]Defensa:[/bold] {player.DEF} puntos // [gray]Porcentaje de defensa: {player.DefensePercentage}%[/gray]",
                f"[bold]Agilidad:[/bold] {player.AGI}",
                f"[bold]Prob. ContraAtaque:[/bold] {player.CounterAttack}%",
                f"[bold]Prob. Evasion:[/bold] {player.Evasion}%",
                "",
                f"[bold yellow]Oro:[/bold yellow] {player.Gold}",
                f"[bold cyan]Experiencia:[/bold cyan] {player.EXP}/{player.EXP_M}",
            ]

        # Add status bars
        health_bar, health_percent = create_status_bar(
            player.Health, player.Health_max, "red", True
        )
        mana_bar, mana_percent = create_status_bar(
            player.Mana, player.Mana_max, "blue", True
        )
        exp_bar, exp_percent = create_status_bar(
            player.EXP, player.EXP_M, "green", True
        )

        stats_lines.append("")
        stats_lines.append(f"Salud: {health_bar} {health_percent}%")
        stats_lines.append(f"Mana:  {mana_bar} {mana_percent}%")
        stats_lines.append(f"EXP:   {exp_bar} {exp_percent}%")

        # ===== MOSTRAR EQUIPAMIENTO =====
        stats_lines.append("")
        stats_lines.append("[bold underline]Equipo actual:[/bold underline]")

        equipment_slots = [
            ("weapon", "Arma"),
            ("helmet", "Casco"),
            ("armor", "Armadura"),
            ("boots", "Botas"),
            ("ring", "Anillo 1"),
            ("ring2", "Anillo 2"),
            ("ring3", "Anillo 3"),
        ]

        for slot, display_name in equipment_slots:
            item = getattr(player, slot, None)
            if item:
                item_name = item.Name if hasattr(item, "Name") else item.name
                stats_lines.append(f"[bold]{display_name}:[/bold] {item_name}")
            else:
                stats_lines.append(f"[bold]{display_name}:[/bold] [dim]Vacío[/dim]")


        # Create and display the panel
        stats_panel = Panel(
            "\n".join(stats_lines), title="Estadísticas", border_style="cyan"
        )
        console.print(stats_panel)

        # Wait for user input to continue
        console.print(
            "\n[info]Presiona Enter para volver al menú principal... ↵ [/info]"
        )
        wait_for_enter()
         

    elif main_input == 9:
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


    # ===== NUEVA OPCIÓN: VER ITEMS DISPONIBLES =====
    elif main_input == 10:
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
         
    # ==============================================

    elif main_input == 11:
        console.print("\n[warning]¿Deseas guardar antes de salir? (s/n)[/warning]")
        save_response = input().lower()
        if save_response == "s" or save_response == "si":
            save_game()

    elif main_input == 12:
        debug_input = int(
            input("""DEBUG: 
                  [1] ARMAS
                  [2] GOLD Y EXP
                  [3] Mastery & Gathering
                  [4] LOOK Variables""")
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
                current_state=current_state,
                chosen_area=chosen_area,
            )
            console.print(Panel(debug_text, title="Debug Variables", border_style="magenta"))
            app_logger.debug("Debug snapshot requested from in-game debug menu.")
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


# Game initialization function
def init_game():
    global item_manager, shop_manager

    console.print(Panel("Bienvenido al Juego RPG", style="success"))
    console.print("[info]Iniciando juego...[/info]")

    # ===== INICIALIZAR SISTEMA DE ITEMS JSON =====
    try:
        console.print("[info]Cargando sistema de items desde JSON...[/info]")
        item_manager = get_item_manager()
        console.print("[success]Sistema de items cargado correctamente.[/success]")
    except Exception as e:
        console.print(f"[warning]Error al cargar sistema de items: {str(e)}[/warning]")
        console.print(
            "[warning]El juego continuará sin el sistema de items JSON[/warning]"
        )
    print("\n")
    # Inicializar sistema de tiendas
    try:
        console.print("[info]Cargando sistema de tiendas desde JSON...[/info]")
        shop_manager = get_shop_manager()
        console.print("[success]Sistema de tiendas cargado correctamente.[/success]")
    except Exception as e:
        console.print(
            f"[warning]Error al cargar sistema de tiendas: {str(e)}[/warning]"
        )
        console.print(
            "[warning]El juego continuará sin el sistema de tiendas JSON[/warning]"
        )
    print("\n")
    try:
        console.print("[info]Inicializando sistema de mods...[/info]")
        mod_loader_instance = get_mod_loader()
        mod_loader_instance.load_all_mods()
    except Exception as e:
        console.print(f"[warning]Error al cargar mods: {str(e)}[/warning]")

    # Check for saved games
    if os.path.exists("./Data/SaveGame.json"):
        console.print("[info]Se ha encontrado una partida guardada.[/info]")
        console.print("¿Deseas cargar la partida guardada? (s/n)")
        response = input().lower()

        if response == "s" or response == "si":
            load_game()
    wait_for_enter()


# Main Execution
if __name__ == "__main__":
    try:
        # Initialize game
        init_game()

        # Main game loop
        while True:
            try:
                main()
            except Exception as e:
                console.print(f"[danger]Error en el bucle principal: {str(e)}[/danger]")
                console.print("[info]El juego intentará continuar...[/info]")
                sp.sleep(2)
    except Exception as e:
        console.print(f"[danger]Error: {str(e)}[/danger]")

        sys.exit(1)

