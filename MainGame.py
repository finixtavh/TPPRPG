from rich.console import Console, Group
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from typing import List, Dict, Optional, Tuple, Any
from rich import box
import sys
import time
import traceback
from rich.live import Live
from Modules.ModulesUtils.UIStyle import (
    herald_bar, herald_panel, herald_table, ICONS, 
    COLOR_PRIMARY, COLOR_SECONDARY, COLOR_DIM
)
from sshkeyboard import stop_listening

# -----------------------------------------------------------------------------
# Modules/

from Modules.ModulesManager.ItemManager import get_item_manager, load_item_by_id
from Modules.ModulesManager.ShopManager import get_shop_manager, display_shop
from Modules.ModulesManager.ZoneManager import get_all_zones, get_zones_for_selector
from Modules.ModulesManager.BuffManager import get_buff_manager

from Modules.ModulesMenu.InventoryMenu import open_inventory_menu
from Modules.ModulesMenu.GuildMenu import open_guild_menu
from Modules.ModulesMenu.DebugMenu import open_enhanced_debug_menu

from Modules.ModulesFunctions.GatheringMasterySystem import cTool, cMaterial, Gathering_init
from Modules.ModulesFunctions.EnchantmentSystem import open_enchantment_menu
from Modules.ModulesFunctions.MasterySystem import ensure_mastery, MASTERY_MAX_LEVEL
from Modules.ModulesFunctions.SaveSystem import save_load_menu, get_slot_info
from Modules.ModulesFunctions.CraftingSystem import open_crafting_menu
from Modules.ModulesFunctions.GuildSystem import get_guild_manager, SIMULATION_INTERVAL
from Modules.ModulesFunctions.QuestSystem import quest_manager
from Modules.ModulesFunctions.BaseSystem import BaseManager, open_base_menu
from Modules.ModulesFunctions.WeatherSystem import get_weather_manager, apply_weather_combat_mods
from Modules.ModulesManager.ItemModifierSystem import roll_and_apply_modifier, get_item_display_name
from Modules.ModulesFunctions.CompanionSystem import (
    cCompanion,
    companion_management_menu,
    COMPANION_REVIVAL_GOLD_COST,)

from Modules.ModulesUtils.Loader import Write, Read
from Modules.ModulesUtils.ModLoader import get_mod_loader, get_mod_api, GAME_VERSION
from Modules.ModulesUtils.input_utils import wait_for_enter, interactive_menu_select, keyboard_listener_scope, start_key_listener
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
    enemy_loader,
    roll_group_size,)

# ---   ---
import random
import time as sp
import os
import copy
import threading

# Game configuration
CONFIG = Read("config.json", None)

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

_original_stdout_write = sys.stdout.write

def _safe_stdout_write(text):
    while True:
        try:
            return _original_stdout_write(text)
        except BlockingIOError:
            time.sleep(0.001)  # Esperar a que el buffer se drene

sys.stdout.write = _safe_stdout_write

app_logger = setup_logging(CONFIG["DEBUG"]["ENABLED"])
attach_console_logging(console, app_logger)
install_exception_hooks(app_logger)

def _display_combat_details(attacker_name, defender_name, res, is_counter=False):
    """Muestra una tabla detallada del resultado del ataque."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    
    title = f"[bold yellow]CONTRAATAQUE[/]" if is_counter else f"[bold cyan]ATAQUE: {attacker_name} → {defender_name}[/]"
    
    if res.get("is_evaded"):
        return Panel(Text(f"¡{defender_name} ha ESQUIVADO el ataque!", style="bold cyan"), border_style="cyan")

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

            # Afinidad elemental: marcar debilidad / resistencia
            aff = res.get("affinity_mult", [1.0]*5)[i]
            if aff > 1.0:
                content.append(f"  ¡DÉBIL! x{aff:.2g}", style="bold bright_green")
            elif aff < 1.0:
                content.append(f"  Resiste x{aff:.2g}", style="bold bright_red")

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
        footer.append(f"Barrera: -{res['barrier_absorbed']:.1f} ", style="bold blue")
    
    footer.append(f"TOTAL: {res['total_damage']:.1f}", style="bold yellow")
    if res.get("is_counter"):
        footer.append(f"\n¡{defender_name} se prepara para CONTRAATACAR!", style="bold magenta")
    
    panel = Panel(
        content,
        title=title,
        subtitle=footer,
        subtitle_align="right",
        border_style="yellow" if is_counter else "cyan",
        box=box.ROUNDED,
        expand=False
    )
    return panel

def _perform_attack(attacker, defender, console, redraw_callback=None, combat_logs=None):
    """Ejecuta un ataque y maneja el posible contraataque en cadena."""
    res = attacker.attack(defender)
    panel = _display_combat_details(attacker.name, defender.name, res)

    if panel is not None:
        if combat_logs is not None:
            combat_logs.append(panel)
            if redraw_callback:
                redraw_callback(combat_logs)
        else:
            console.print(panel)

    total_dmg = res.get("total_damage", 0)

    if res.get("is_counter") and defender.Health > 0:
        _combat_delay(0.5)
        counter_res = defender.attack(attacker)
        c_panel = _display_combat_details(defender.name, attacker.name, counter_res, is_counter=True)

        if c_panel is not None:
            if combat_logs is not None:
                combat_logs.append(c_panel)
                if redraw_callback:
                    redraw_callback(combat_logs)
            else:
                console.print(c_panel)

    # Pausa para leer el resultado del ataque
    _combat_delay()
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

def _load_zone_enemy_list(player_zone: str) -> Optional[List[cEnemy]]:
    """Carga la lista de enemigos (instancias distintas) de una zona (base o mod).

    Returns:
        Lista de enemigos, o None si no hay datos/enemigos.
    """
    data_npcs = None
    try:
        mod_api = get_mod_api()
        if player_zone in mod_api.stats_injections:
            data_npcs = mod_api.stats_injections[player_zone]
            console.print(f"[dim]Cargando zona de mod: {player_zone}[/dim]")
    except Exception:
        pass

    if not data_npcs:
        data_npcs = Read(os.path.join("Data", "DataStats.json"), player_zone, None)

    if not data_npcs:
        console.print(f"[danger]No se encontraron datos para la zona: {player_zone}[/danger]")
        return None

    enemy_list = enemy_loader(data_npcs)
    if not enemy_list:
        console.print(f"[danger]No se encontraron enemigos en la zona: {player_zone}[/danger]")
        return None
    return enemy_list


def _spawnable_enemies(enemy_list: List[cEnemy]) -> List[cEnemy]:
    """Filtra jefes según su SPAWN_CHANCE; nunca devuelve lista vacía."""
    valid = []
    for e in enemy_list:
        if getattr(e, 'IS_BOSS', False):
            if random.random() <= getattr(e, 'SPAWN_CHANCE', 1.0):
                valid.append(e)
        else:
            valid.append(e)
    return valid or enemy_list


def zone_loader(player_zone: str) -> Optional[cEnemy]:
    """Carga un enemigo aleatorio de la zona indicada."""
    try:
        enemy_list = _load_zone_enemy_list(player_zone)
        if not enemy_list:
            return None

        enemy_random = random.choice(_spawnable_enemies(enemy_list))

        if getattr(enemy_random, 'IS_BOSS', False):
            console.print(f"[blink bold red]¡ADVERTENCIA! ¡Has encontrado a un JEFE: {enemy_random.NAME}![/blink bold red]")
        else:
            console.print(f"[success]Enemigo seleccionado: {enemy_random.NAME}[/success]")
        return enemy_random

    except Exception as e:
        console.print(f"[danger]Error al cargar la zona {player_zone}: {str(e)}[/danger]")
        traceback.print_exc()
        return None


def zone_loader_group(player_zone: str, max_enemies: int = 5) -> List[cEnemy]:
    """Carga un grupo de enemigos de la zona.

    El tamaño del grupo lo decide el dict `group_spawn` del enemigo líder
    (probabilidades 1..5). Los jefes siempre aparecen en solitario.
    Devuelve instancias independientes (deepcopy) para que el HP no se comparta.
    """
    try:
        enemy_list = _load_zone_enemy_list(player_zone)
        if not enemy_list:
            return []

        pool = _spawnable_enemies(enemy_list)
        lead = random.choice(pool)

        # Los jefes son encuentros en solitario
        if getattr(lead, 'IS_BOSS', False):
            console.print(f"[blink bold red]¡ADVERTENCIA! ¡Has encontrado a un JEFE: {lead.NAME}![/blink bold red]")
            return [lead]

        size = roll_group_size(getattr(lead, 'GROUP_SPAWN', None))
        size = max(1, min(size, max_enemies))

        # El relleno excluye jefes
        fillers = [e for e in pool if not getattr(e, 'IS_BOSS', False)] or pool
        group = [lead]
        for _ in range(size - 1):
            group.append(copy.deepcopy(random.choice(fillers)))

        if len(group) > 1:
            console.print(f"[success]¡Grupo de {len(group)} enemigos! Liderado por {lead.NAME}.[/success]")
        else:
            console.print(f"[success]Enemigo seleccionado: {lead.NAME}[/success]")
        return group

    except Exception as e:
        console.print(f"[danger]Error al cargar grupo de zona {player_zone}: {e}[/danger]")
        traceback.print_exc()
        return []


player = None


def create_status_bar(current: float, maximum: float, color: str = "green") -> Tuple[str, int]:
    """Crea una barra de estado estilo Heraldo."""
    bar = herald_bar(current, maximum, width=CONFIG["DISPLAY"]["BAR_LENGTH"], color=color)
    percentage = int((current / maximum) * 100) if maximum > 0 else 0
    return bar, percentage


def create_hp_barrier_bar(
    health: float, health_max: float, barrier: float, _unused=None
) -> Tuple[str, int]:
    health = min(health, health_max)
    if health_max <= 0:
        health_max = 1
    barrier = max(0, barrier)
    bar_length = CONFIG["DISPLAY"]["BAR_LENGTH"]
    health_pct = health / health_max
    barrier_pct = barrier / health_max
    health_cells = int(bar_length * health_pct)
    barrier_cells = int(bar_length * barrier_pct)
    total_filled = min(health_cells + barrier_cells, bar_length)
    barrier_shown = min(barrier_cells, total_filled)
    health_shown = total_filled - barrier_shown
    empty = bar_length - total_filled
    bar = (
        f"[bright_cyan]{'◆' * barrier_shown}[/]" +
        f"[green]{'◆' * health_shown}[/]" +
        f"[dim]{'◇' * empty}[/]"
    )
    percentage = int((health / health_max) * 100)
    return bar, percentage


def render_combat_menu(player, enemies, combat_round: int) -> None:
    """UI de combate Heraldo: [aliados] vs [grupo de enemigos].

    `enemies` puede ser un solo enemigo o una lista de enemigos.
    """
    if not isinstance(enemies, (list, tuple)):
        enemies = [enemies]

    try:
        w = get_weather_manager().get_current_weather()
        weather_text = f"  |  {ICONS['weather']} {w.name}"
    except Exception:
        weather_text = ""

    console.print(Align.center(Text.from_markup(f"[bold gold3]RONDA {combat_round}[/]{weather_text}")))

    # Aliados
    ally_blocks = []
    active_comps = player.companion[:4]

    for comp in active_comps:
        if comp.is_alive:
            barrier = getattr(comp, "Barrier", 0)
            hp_bar, hp_pct = create_hp_barrier_bar(comp.Health, comp.Health_max, barrier) if barrier > 0 else create_status_bar(comp.Health, comp.Health_max, "green")
            mp_bar, mp_pct = create_status_bar(comp.Mana, comp.Mana_max, "blue")
            
            content = Table.grid()
            content.add_row(f"[bold cyan]{comp.name}[/]")
            content.add_row(f"{ICONS['hp']}{hp_bar} [dim]{hp_pct}%[/]")
            content.add_row(f"{ICONS['mp']}{mp_bar} [dim]{mp_pct}%[/]")
            if barrier > 0: content.add_row(f"[bright_cyan]{ICONS['def']}Barrera: {int(barrier)}[/]")
            
            ally_blocks.append(herald_panel(content, border_style="cyan"))
        else:
            ally_blocks.append(herald_panel(f"[dim]{comp.name}[/]\n[bold red]💀 KO[/]", border_style="dim"))

    # Jugador
    p_barrier = getattr(player, "Barrier", 0)
    p_hp_bar, p_hp_pct = create_hp_barrier_bar(player.Health, player.Health_max, p_barrier) if p_barrier > 0 else create_status_bar(player.Health, player.Health_max, "green")
    p_mp_bar, p_mp_pct = create_status_bar(player.Mana, player.Mana_max, "blue")
    
    p_content = Table.grid()
    p_content.add_row(f"[bold]{player.name}[/]")
    p_content.add_row(f"{ICONS['hp']}{p_hp_bar} [dim]{p_hp_pct}%[/]")
    p_content.add_row(f"{ICONS['mp']}{p_mp_bar} [dim]{p_mp_pct}%[/]")
    if p_barrier > 0: p_content.add_row(f"[bright_cyan]{ICONS['def']}Barrera: {int(p_barrier)}[/]")
    
    ally_blocks.append(herald_panel(p_content, border_style="green"))

    # Enemigos (grupo): cada uno con su índice de objetivo [1], [2], ...
    enemy_blocks = []
    for idx, en in enumerate(enemies, 1):
        if getattr(en, "HP", 0) > 0:
            e_hp_bar, e_hp_pct = create_status_bar(en.HP, en.HP_M, "red")
            e_content = Table.grid()
            e_content.add_row(f"[bold red][{idx}] {en.NAME}[/]")
            e_content.add_row(f"{ICONS['hp']}{e_hp_bar} [dim]{e_hp_pct}%[/]")
            e_content.add_row(f"[dim]{int(en.HP)}/{en.HP_M}[/]")
            enemy_blocks.append(herald_panel(e_content, border_style="red"))
        else:
            enemy_blocks.append(herald_panel(f"[dim][{idx}] {en.NAME}[/]\n[bold red]💀 Muerto[/]", border_style="dim"))

    enemy_panel = Columns(enemy_blocks, padding=(0, 1), equal=True)

    # Layout de Combate
    main_grid = herald_table()
    main_grid.add_column(ratio=2) # Aliados
    main_grid.add_column(ratio=2) # Enemigos
    main_grid.add_row(Columns(ally_blocks, padding=(0, 1), equal=True), enemy_panel)

    console.print(main_grid)

    actions = Table.grid(padding=(0, 2))
    actions.add_column(style="bold yellow")
    actions.add_column(style="bright_white")
    actions.add_column(style="dim")
    actions.add_column(style="bold yellow")
    actions.add_column(style="bright_white")
    actions.add_row("[1]", "Atacar", "  │  ", "[2]", "Inventario")
    actions.add_row("[3]", "Huir",   "  │  ", "",    "")

    bottom = herald_panel(
        actions, title="Acciones", border_style=COLOR_PRIMARY
    )
    console.print(bottom)


def apply_debuffs(player: Any) -> Dict[str, Any]:
    """Aplica todos los debuffs activos al jugador usando el BuffManager."""
    manager = get_buff_manager()
    
    debuffs = getattr(player, "applieddebuffs", [])
    if not debuffs:
        return {}
        
    # Identificar qué buffs no han sido aplicados para procesar sus efectos una sola vez
    to_process = [b for b in debuffs if not b.applied]
    
    # El manager calcula los multiplicadores y marca como applied
    total_modifiers = manager.apply_buffs_to_entity(player, debuffs)
    
    # Aplicar efectos a los atributos reales del jugador
    # Nota: Los cambios en stats bases (como ATK) se gestionan sumando el total_modifiers 
    # en el momento del cálculo, pero efectos como veneno (HP Regen) deben aplicarse aquí.
    for b in to_process:
        for effect_name, val in b.effects.items():
            # Ejemplo: HealthRegenFlat resta vida cada turno
            if effect_name == "HealthRegenFlat" and val < 0:
                player.Health = max(0, player.Health + val)
            elif effect_name == "ManaRegenFlat" and val < 0:
                player.Mana = max(0, player.Mana + val)
            # Otros efectos se procesan dinámicamente en el combate
                
    return total_modifiers


############################## Main Menu Functions ##############################


_MAIN_MENU_ASCII = '''
  _______ _____  _____  _____   _____   ____
 |__   __|  __ \\|  __ \\|  __ \\ |  __ \\ / ____|
    | |  | |__) | |__) | |__)  | |__)|| |  ___ 
    | |  |  ___/|  ___/|  _  / |  ___/| | |_ |
    | |  | |    | |    | | \\ \\ | |    | |__| |
    |_|  |_|    |_|    |_|  \\_\\|_|    |______|
'''



def _bar(current: float, maximum: float, width: int = 10, color: str = "green") -> str:
    if maximum <= 0: return "░" * width
    filled = int((current / maximum) * width)
    filled = max(0, min(width, filled))
    return f"[{color}]" + "█" * filled + f"[/][bright_black]" + "░" * (width - filled) + "[/]"

def _create_player_panel(player):
    table = herald_table(expand=True)
    table.add_column(style=f"bold {COLOR_PRIMARY}", width=12)
    table.add_column(justify="right")
    
    table.add_row(f" {ICONS['hp']}Vida", herald_bar(player.Health, player.Health_max))
    table.add_row("", f"[dim]{int(player.Health)}/{player.Health_max}[/dim]")
    table.add_row(f" {ICONS['mp']}Maná", herald_bar(player.Mana, player.Mana_max, color="blue"))
    table.add_row("", f"[dim]{int(player.Mana)}/{player.Mana_max}[/dim]")
    
    table.add_row("", "") # Espaciador

    atk_f = apply_weather_combat_mods(getattr(player, "ATK", 0), "attack")
    def_f = apply_weather_combat_mods(player.DEF[0] if hasattr(player, "DEF") else 0, "defense")
    
    def format_stat(base, final, is_pct=False):
        res = f"{final:.1f}{'%' if is_pct else ''}"
        if abs(final - base) > 0.01:
            diff = final - base
            color = "green" if diff > 0 else "red"
            res += f"[{color}]({'+' if diff > 0 else ''}{diff:.1f})[/{color}]"
        return res

    table.add_row(f" {ICONS['atk']}ATK", format_stat(getattr(player, "ATK", 0), atk_f))
    table.add_row(f" {ICONS['def']}DEF", format_stat(player.DEF[0] if hasattr(player, "DEF") else 0, def_f))
    table.add_row(f" {ICONS['agi']}AGI", format_stat(player.AGI, apply_weather_combat_mods(player.AGI, "agi")))
    
    table.add_row("", "") # Espaciador
    
    slots = [(" Arma", player.weapon), (" SecH", getattr(player, "SecHand", None)), (" Pecho", player.armor)]
    for label, item in slots:
        if item:
            name = getattr(item, "Name", getattr(item, "name", "Equipado"))
            table.add_row(f"{ICONS['item']}{label}", f"[{COLOR_SECONDARY}]{name[:10]}[/]")
        else:
            table.add_row(f"{ICONS['item']}{label}", "[dim red]---[/]")
            
    return herald_panel(table, title="Estado", border_style=COLOR_PRIMARY, expand=True)

def _create_buffs_panel(player):
    all_buffs = getattr(player, "appliedbuffs", []) + getattr(player, "applieddebuffs", [])
    if not all_buffs: return None
        
    _MAP = {
        "PhysicalDamageFlat": "DMG-F", "ThermalDamageFlat": "DMG-T", "EarthDamageFlat": "DMG-E", "ElectricDamageFlat": "DMG-EL", "DeepDamageFlat": "DMG-P",
        "PhysicalDamagePercent": "%DMG-F", "ThermalDamagePercent": "%DMG-T", "EarthDamagePercent": "%DMG-E", "ElectricDamagePercent": "%DMG-EL", "DeepDamagePercent": "%DMG-P",
        "DefenseFlat": "DEF-F", "ThermalDefenseFlat": "DEF-T", "EarthDefenseFlat": "DEF-E", "ElectricDefenseFlat": "DEF-EL", "DeepDefenseFlat": "DEF-P",
        "DefensePercent": "%DEF-F", "MagicDefenseFlat": "DEF-M", "MagicDefensePercent": "%DEF-M",
        "AgilityFlat": "AGI", "AgilityPercent": "%AGI", "EvasionPercent": "EVA", "CounterAttackPercent": "CTK",
        "HealthMaxFlat": "HPX", "HealthMaxPercent": "%HPX", "ManaMaxFlat": "MPX", "ManaMaxPercent": "%MPX",
        "ManaRegenFlat": "MPR", "HealthRegenFlat": "HPR", "Barrier": "BR", "MagicalDamageFlat": "DMG-M", "MagicalDamagePercent": "%DMG-M"
    }

    table = herald_table(expand=True)
    table.add_column("Estado")
    table.add_column("Efectos", ratio=1)

    for b in all_buffs:
        icon = ICONS['debuff'] if b.is_debuff else ICONS['buff']
        color = "red" if b.is_debuff else "green"
        duration = f"{b.duration_current}T" if not b.permanent else "∞"
        
        # Resumen de efectos
        fx_list = []
        for key, val in b.effects.items():
            short = _MAP.get(key, key[:5])
            sign = "+" if val > 0 else ""
            suffix = "%" if "Percent" in key else ""
            fx_list.append(f"{short}{sign}{val}{suffix}")
        
        fx_str = " ".join(fx_list)
        table.add_row(
            f"{icon} [bold {color}]{b.name[:12]}[/] [dim]({duration})[/]",
            f"[dim]{fx_str}[/]"
        )

    return herald_panel(table, title="Estados", border_style="green", expand=True)

def _create_guild_panel(player):
    gm = get_guild_manager()
    guild = gm.get_player_guild()
    if not guild: return None
    
    table = herald_table(expand=True)
    table.add_column(width=4)
    table.add_column()
    table.add_row(ICONS['guild'], f"[bold {COLOR_PRIMARY}]{guild.name[:18]}[/]")
    table.add_row(ICONS['atk'], f"Ataque Lv.{guild.attack_rating}")
    
    return herald_panel(table, title="Guild", border_style=COLOR_PRIMARY, expand=True)

def _create_weather_panel():
    wm = get_weather_manager()
    w = wm.get_current_weather()
    
    table = herald_table(expand=True)
    table.add_row(f"{ICONS['weather']} [bold magenta]{w.name}[/]")
    
    mods = []
    for stat, mod in w.combat_mods.items():
        if mod != 1.0:
            color = "green" if mod > 1.0 else "red"
            pct = int((mod - 1.0) * 100)
            mods.append(f"[{color}]{stat[:3].upper()}{'+' if pct > 0 else ''}{pct}%[/{color}]")
    
    if mods: table.add_row(" ".join(mods[:2]))
    
    return herald_panel(table, title="Clima", border_style="magenta", expand=True)


def display_main_menu() -> int:
    global player, item_manager, vInventory


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
        (16, "Guilds"),
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

        # Table de Opciones
        t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        t.add_column("Opción", style="bright_yellow", justify="right", width=4)
        t.add_column("Sep", style="bright_yellow", width=1)
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

        # Dashboard Lateral (Derecha)
        dash_group = []
        dash_group.append(_create_weather_panel())
        
        buffs_p = _create_buffs_panel(player)
        if buffs_p: dash_group.append(buffs_p)
            
        guild_p = _create_guild_panel(player)
        if guild_p: dash_group.append(guild_p)

        # Panel exclusivo para el menú de opciones
        footer_str = "Selecciona: "
        if state["buf"]:
            footer_str += f"[dim]{state['buf']}[/dim]"
        else:
            footer_str += "[dim]↑/↓ + Enter[/dim]"
        
        menu_content = herald_panel(
            Group(Align.center(t), "", Align.center(Text.from_markup(footer_str))),
            title="Menú",
            border_style=COLOR_PRIMARY,
            padding=(1, 2)
        )

        # Tabla contenedora sin borde exterior
        main_layout = herald_table(expand=True)
        main_layout.add_column(ratio=0.9, vertical="top")
        main_layout.add_column(ratio=1.4, vertical="top")
        main_layout.add_column(ratio=1.2, vertical="top")
        
        main_layout.add_row(
            _create_player_panel(player),
            menu_content,
            Group(*dash_group)
        )

        return Group(header, "", main_layout)

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
        kb = start_key_listener(_on_press)
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


############################## Combat Helpers ##############################


def _combat_delay(factor: float = 1.0) -> None:
    """Pausa de animación de combate (configurable, desacoplada del refresh de menús)."""
    sp.sleep(CONFIG.get("COMBAT", {}).get("ANIM_DELAY", 0.4) * factor)


def _alive_enemies(enemies: List[cEnemy]) -> List[cEnemy]:
    return [e for e in enemies if getattr(e, "HP", 0) > 0]


def _choose_target(enemies: List[cEnemy]) -> Optional[cEnemy]:
    """Elige un enemigo objetivo. Auto si solo queda uno vivo."""
    alive = [(i + 1, e) for i, e in enumerate(enemies) if getattr(e, "HP", 0) > 0]
    if not alive:
        return None
    if len(alive) == 1:
        return alive[0][1]
    options = [(idx, f"[{idx}] {e.NAME} — HP {int(e.HP)}/{e.HP_M}") for idx, e in alive]
    sel = interactive_menu_select(
        title="¿A quién atacas?",
        subtitle="Elige tu objetivo",
        options=options,
        prompt="Objetivo: ",
        default_value=alive[0][0],
        border_style="red",
        use_screen=False,
    )
    for idx, e in alive:
        if idx == sel:
            return e
    return alive[0][1]


def _process_enemy_loot(enemy: cEnemy) -> List[str]:
    """Genera el loot de un enemigo derrotado y lo agrega al inventario.

    Returns:
        Lista de nombres (con markup) de los items soltados.
    """
    _world_cfg = CONFIG.get("WORLD", {})
    _loot_mod = float(_world_cfg.get("GLOBAL_LOOT_MODIFIER", 1))
    _lq_pos = float(_world_cfg.get("GLOBAL_LOOT_QUALITY_MODIFIER_POSITIVE", 1))
    _lq_neg = float(_world_cfg.get("GLOBAL_LOOT_QUALITY_MODIFIER_NEGATIVE", 1))
    _combat_cfg = CONFIG.get("COMBAT", {})
    base_chance = float(_combat_cfg.get("LOOT_CHANCE", 0.40))
    fallback_ids = _combat_cfg.get("LOOT_FALLBACK_IDS", [1, 10, 21, 32, 43, 54])

    dropped: List[str] = []
    if random.random() >= min(1.0, base_chance * _loot_mod):
        return dropped

    items_to_drop = random.choices([1, 2, 3, 4, 5], weights=[0.4, 0.5, 0.3, 0.2, 0.08], k=1)[0]
    loot_pool = getattr(enemy, "loot_tables", None)

    for _ in range(items_to_drop):
        if loot_pool and isinstance(loot_pool, dict) and len(loot_pool) > 0:
            ids = list(loot_pool.keys())
            weights = list(loot_pool.values())
            loot_id = int(random.choices(ids, weights=weights, k=1)[0])
        else:
            loot_id = random.choice(fallback_ids)

        loot_item = load_item_by_id(loot_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial)
        if not loot_item:
            continue
        try:
            mod = roll_and_apply_modifier(loot_item, _lq_pos, _lq_neg)
            display_name = get_item_display_name(loot_item)
            mod_txt = f" [{('red' if mod.is_negative else 'green')}]{mod.icon} {mod.name}[/]" if mod else ""
        except Exception:
            display_name = getattr(loot_item, "name", getattr(loot_item, "Name", "Objeto"))
            mod_txt = ""
        dropped.append(f"{display_name}{mod_txt}")
        vInventory.addObject(loot_item)
        try:
            get_mod_api().fire_event("item_looted", player, loot_item, enemy)
        except Exception:
            pass
    return dropped


def _grant_group_victory(enemies: List[cEnemy], add_log) -> None:
    """Otorga EXP, oro, loot y dispara quests/impuestos al derrotar al grupo."""
    _world_cfg = CONFIG.get("WORLD", {})
    _exp_mod = float(_world_cfg.get("GLOBAL_EXP_MODIFIER", 1))
    _gold_mod = float(_world_cfg.get("GLOBAL_GOLD_MODIFIER", 1))

    total_exp = sum(int(getattr(e, "EXP_TO_PLAYER", 0) * _exp_mod) for e in enemies)
    total_gold = sum(int(getattr(e, "GOLD", 0) * _gold_mod) for e in enemies)
    player.EXP += total_exp
    player.Gold += total_gold
    add_log(f"[success]Ganaste {total_exp} EXP y {total_gold} oro.[/success]")

    all_drops: List[str] = []
    for e in enemies:
        all_drops.extend(_process_enemy_loot(e))
        quest_manager.update_kill_quest(e.NAME, player)
        try:
            get_mod_api().fire_event("enemy_killed", player, e, chosen_area)
        except Exception:
            pass

    if all_drops:
        add_log("\n[success]¡El grupo soltó los siguientes objetos![/success]")
        for d in all_drops:
            add_log(f"  [yellow]- {d}[/yellow]")

    player.level_up()

    gm = get_guild_manager()
    pg = gm.get_player_guild()
    if pg:
        pg.fight_count += 1
        if pg.fight_count >= 5:
            tax_msg = pg.apply_taxes()
            add_log(f"\n[bold yellow]💰 {tax_msg}[/bold yellow]")
            pg.fight_count = 0

    # ── Avanzar la simulación viva de guilds cada SIMULATION_INTERVAL combates ──
    player.combat_counter = getattr(player, "combat_counter", 0) + 1
    if gm.guilds and player.combat_counter % SIMULATION_INTERVAL == 0:
        try:
            events = gm.tick(gm.resource_defs, gm.guild_type_defs)
            try:
                get_mod_api().fire_guild_tick_handlers(gm)
            except Exception:
                pass
            if events:
                add_log("\n[bold magenta]🌍 El mundo de las guilds avanza:[/]")
                for e in events[:5]:
                    add_log(f"  [dim]{e}[/dim]")
        except Exception as e:
            add_log(f"[dim]Error en simulación de guilds: {e}[/dim]")


############################## Mod Manager UI ##############################


def open_mod_manager() -> None:
    """Gestor de mods: activar/desactivar, recargar, ajustes y comandos."""
    mod_loader_instance = get_mod_loader()
    api = get_mod_api()

    while True:
        console.clear()
        mod_loader_instance.display_mods_info()

        choice = interactive_menu_select(
            title="Gestión de Mods",
            subtitle=f"Versión del juego: {GAME_VERSION}",
            options=[
                (1, "Activar / Desactivar un mod"),
                (2, "Recargar un mod"),
                (3, "Recargar TODOS los mods"),
                (4, "Ajustes de un mod"),
                (5, "Ejecutar comando de mod"),
                (6, "Estado del sistema"),
                (0, "Volver"),
            ],
            prompt="Opción: ",
            default_value=0,
            border_style="cyan",
            use_screen=False,
        )

        if choice == 0:
            break

        all_mods = mod_loader_instance.discover_mods()

        if choice == 1:  # toggle enable/disable
            if not all_mods:
                console.print("[warning]No hay mods.[/warning]"); wait_for_enter(); continue
            opts = []
            keys = list(all_mods.keys())
            for i, name in enumerate(keys, 1):
                state = "ON" if mod_loader_instance.is_enabled(name) else "OFF"
                opts.append((i, f"[{state}] {all_mods[name].display_name}"))
            opts.append((0, "Cancelar"))
            sel = interactive_menu_select(title="Activar/Desactivar", options=opts,
                                          prompt="Mod: ", default_value=0, border_style="yellow", use_screen=False)
            if sel and sel != 0:
                name = keys[sel - 1]
                if mod_loader_instance.is_enabled(name):
                    mod_loader_instance.disable_mod(name)
                    console.print(f"[yellow]'{name}' desactivado. Recargando...[/yellow]")
                else:
                    mod_loader_instance.enable_mod(name)
                    console.print(f"[green]'{name}' activado. Recargando...[/green]")
                mod_loader_instance.load_all_mods()
                api.integrate_all()
                api.integrate_with_quest_manager(quest_manager)
                api.apply_player_attributes(player)
            wait_for_enter()

        elif choice == 2:  # reload one
            loaded = list(mod_loader_instance.loaded_mods.keys())
            if not loaded:
                console.print("[warning]No hay mods cargados.[/warning]"); wait_for_enter(); continue
            opts = [(i, n) for i, n in enumerate(loaded, 1)] + [(0, "Cancelar")]
            sel = interactive_menu_select(title="Recargar mod", options=opts, prompt="Mod: ",
                                          default_value=0, border_style="yellow", use_screen=False)
            if sel and sel != 0:
                name = loaded[sel - 1]
                if mod_loader_instance.reload_mod(name):
                    api.integrate_all()
                    console.print(f"[success]'{name}' recargado.[/success]")
                else:
                    console.print(f"[danger]No se pudo recargar '{name}'.[/danger]")
            wait_for_enter()

        elif choice == 3:  # reload all
            mod_loader_instance.load_all_mods()
            api.integrate_all()
            api.integrate_with_quest_manager(quest_manager)
            api.apply_player_attributes(player)
            console.print("[success]Todos los mods recargados.[/success]")
            wait_for_enter()

        elif choice == 4:  # settings
            mods_with_settings = [n for n in all_mods if api.mod_settings_schema.get(n)]
            if not mods_with_settings:
                console.print("[warning]Ningún mod expone ajustes.[/warning]"); wait_for_enter(); continue
            opts = [(i, all_mods[n].display_name) for i, n in enumerate(mods_with_settings, 1)] + [(0, "Cancelar")]
            sel = interactive_menu_select(title="Ajustes de Mod", options=opts, prompt="Mod: ",
                                          default_value=0, border_style="yellow", use_screen=False)
            if sel and sel != 0:
                _edit_mod_settings(mods_with_settings[sel - 1], api, mod_loader_instance)

        elif choice == 5:  # run command
            cmds = list(api.custom_commands.items())
            if not cmds:
                console.print("[warning]No hay comandos de mod registrados.[/warning]"); wait_for_enter(); continue
            opts = [(i, f"{n} — {info.get('description', '')}") for i, (n, info) in enumerate(cmds, 1)] + [(0, "Cancelar")]
            sel = interactive_menu_select(title="Comandos de Mod", options=opts, prompt="Comando: ",
                                          default_value=0, border_style="yellow", use_screen=False)
            if sel and sel != 0:
                cmd_name = cmds[sel - 1][0]
                console.print(f"[info]Ejecutando '{cmd_name}'...[/info]")
                api.run_command(cmd_name, player)
            wait_for_enter()

        elif choice == 6:  # system status
            console.print(Panel(" Estado del Sistema de Mods", style="green"))
            console.print(f"Mods cargados: {len(mod_loader_instance.loaded_mods)}")
            console.print(f"Items inyectados (tipos): {len(api.item_injections)}")
            console.print(f"Zonas inyectadas: {len(api.stats_injections)}")
            console.print(f"Tiendas inyectadas: {len(api.shop_injections)}")
            console.print(f"Recetas: {len(api.recipe_injections)} | Quests: {len(api.quest_injections)}")
            console.print(f"Climas: {len(api.weather_injections)} | Afinidades: {len(api.affinity_injections)}")
            console.print(f"Compañeros: {len(api.companion_injections)} | Buffs: {len(api.buff_injections)}")
            console.print(f"Comandos: {len(api.custom_commands)}")
            console.print(f"Event handlers: {sum(len(h) for h in api.event_handlers.values())}")
            console.print(f"Atributos de jugador: {len(api.player_attributes)}")
            wait_for_enter()


def _edit_mod_settings(mod_name, api, mod_loader_instance) -> None:
    schema = api.mod_settings_schema.get(mod_name, {})
    while True:
        keys = list(schema.keys())
        opts = []
        for i, k in enumerate(keys, 1):
            val = api.get_setting(mod_name, k)
            opts.append((i, f"{k} = {val}  [dim]({schema[k].get('description', '')})[/dim]"))
        opts.append((0, "Volver"))
        sel = interactive_menu_select(title=f"Ajustes: {mod_name}", options=opts, prompt="Ajuste: ",
                                      default_value=0, border_style="cyan", use_screen=False)
        if not sel or sel == 0:
            mod_loader_instance._save_config()
            break
        key = keys[sel - 1]
        meta = schema[key]
        console.print(f"[info]{key} ({meta.get('type', 'str')}) — actual: {api.get_setting(mod_name, key)}[/info]")
        raw = input("Nuevo valor: ").strip()
        if raw == "":
            continue
        api.set_setting(mod_name, key, _coerce_setting(raw, meta.get("type", "str")))
        console.print("[success]Guardado.[/success]")


def _coerce_setting(raw: str, typ: str):
    try:
        if typ in ("int", "integer"):
            return int(raw)
        if typ in ("float", "number"):
            return float(raw)
        if typ in ("bool", "boolean"):
            return raw.lower() in ("1", "true", "sí", "si", "yes", "y")
    except ValueError:
        pass
    return raw


############################## Main Game Loop ##############################


def main():
    """Main game loop function that handles player actions and game state"""
    global chosen_area, tick, enemy, player, item_manager, shop_manager

    # Apply automatic regeneration and check inventory
    player.Check(vInventory)

    
    # Clear the screen for better UI
    os.system("cls" if os.name == "nt" else "clear")

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
            else:
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
                f"\n[bold bright_green]Compañeros[/]\n{c_s}\n"
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
            buff_lines.append("[bold red]Debuffs activos:[/]")
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
            buff_lines.append("[bold yellow]Impuestos de Guild:[/]")
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
            _kb = start_key_listener(_on_key)
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
                    # Generar un grupo de enemigos (tamaño según group_spawn del líder)
                    enemies = zone_loader_group(chosen_area)
                    if not enemies:
                        console.print("[danger]No hay enemigos disponibles en esta zona.[/danger]")
                        wait_for_enter()
                        continue
                    enemy = enemies[0]  # mantener global por compatibilidad

                    try:
                        get_mod_api().fire_event("combat_start", player, enemies, chosen_area)
                    except Exception:
                        pass

                    combat_round = 1
                    combat_active = True

                    combat_logs = []
                    def redraw_combat_screen(logs=None):
                        if logs is None: logs = combat_logs
                        os.system("cls" if os.name == "nt" else "clear")
                        render_combat_menu(player, enemies, combat_round)
                        for log in logs:
                            console.print(log)

                    def add_log(markup):
                        combat_logs.append(Text.from_markup(markup))
                        redraw_combat_screen()

                    while combat_active:
                        os.system("cls" if os.name == "nt" else "clear")
                        render_combat_menu(player, enemies, combat_round)
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
                            use_screen=False,
                            bottom_content=Group(*combat_logs) if combat_logs else None
                        )

                        combat_logs.clear()
                        redraw_combat_screen()

                        if combat_action == 1:
                            add_log("\n[bold]¡Tu turno![/bold]")
                            _combat_delay(0.5)
                            target = _choose_target(enemies)
                            if target is not None:
                                damage_dealt = _perform_attack(player, target, console, redraw_combat_screen, combat_logs)

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
                                if comp.is_alive and _alive_enemies(enemies):
                                    c_target = _alive_enemies(enemies)[0]
                                    add_log(f"\n[cyan]>> Turno de {comp.name} <<[/cyan]")
                                    _combat_delay(0.3)
                                    c_opts = [(1, "Atacar")]
                                    c_class = getattr(comp, 'c_class', 'Daño')

                                    if c_class == "Curandero":
                                        c_opts.extend([(2, "Curar al jugador"), (3, "Curar a todo el equipo")])
                                    elif c_class == "Soporte":
                                        c_opts.append((2, f"Debilitar a {c_target.NAME}"))

                                    c_action = interactive_menu_select(
                                        title=f"Acción de {comp.name}",
                                        subtitle="Selecciona habilidad:",
                                        options=c_opts,
                                        prompt="Acción: ",
                                        default_value=1,
                                        border_style="cyan"
                                    )

                                    if c_action == 1:
                                        _perform_attack(comp, c_target, console, redraw_combat_screen, combat_logs)
                                    elif c_action == 2 and c_class == "Curandero":
                                        cura = player.Health_max * 0.20
                                        player.Health = min(player.Health_max, player.Health + cura)
                                        add_log(f"[success]{comp.name} curó a {player.name} por {cura:.1f} HP![/success]")
                                    elif c_action == 3 and c_class == "Curandero":
                                        cura_p = player.Health_max * 0.15
                                        player.Health = min(player.Health_max, player.Health + cura_p)
                                        for c in player.companion:
                                            if c.is_alive: c.Health = min(c.Health_max, c.Health + c.Health_max * 0.15)
                                        add_log(f"[success]{comp.name} curó a todo el equipo.[/success]")
                                    elif c_action == 2 and c_class == "Soporte":
                                        bm = get_buff_manager()
                                        debuff = bm.create_buff("5_debuff", "companion_skill")
                                        if debuff:
                                            if not hasattr(c_target, 'active_buffs'): c_target.active_buffs = []
                                            c_target.active_buffs.append(debuff)
                                            add_log(f"[warning]{comp.name} aplicó {debuff.name} a {c_target.NAME}![/warning]")

                            # ── ¿Murió todo el grupo? ─────────────────────────────
                            if not _alive_enemies(enemies):
                                if len(enemies) > 1:
                                    add_log("[success]¡Has derrotado a todo el grupo![/success]")
                                else:
                                    add_log(f"[success]¡Has derrotado a {enemies[0].NAME}![/success]")

                                _grant_group_victory(enemies, add_log)

                                stay_choice = interactive_menu_select(
                                    title="¡Grupo derrotado!",
                                    subtitle="¿Qué quieres hacer?",
                                    options=[(1, "Seguir en esta zona"), (2, "Volver al menú")],
                                    prompt="Acción: ",
                                    default_value=1,
                                    border_style="green",
                                    use_screen=False,
                                )
                                # En ambos casos volvemos al submenú de zona; un nuevo
                                # grupo se generará al elegir "Luchar" otra vez.
                                enemy = None
                                combat_active = False
                                break

                            # ── Turno de los enemigos (cada uno vivo ataca) ──
                            add_log("\n[bold]¡Turno de los enemigos![/bold]")
                            _combat_delay()
                            for en in _alive_enemies(enemies):
                                alive_companions = [c for c in player.companion if c.is_alive]
                                possible_targets = [player] + alive_companions
                                attack_target = random.choice(possible_targets)

                                damage_taken = _perform_attack(en, attack_target, console, redraw_combat_screen, combat_logs)

                                if attack_target is player:
                                    try:
                                        mm = ensure_mastery(player)
                                        lvlup_msg = mm.register_damage_received(player, float(damage_taken))
                                        if lvlup_msg: console.print(f"[bold cyan]{lvlup_msg}[/bold cyan]")
                                    except Exception: pass

                                    if player.Health <= 0:
                                        add_log("[danger]¡Has sido derrotado![/danger]")
                                        player.Health = max(1, int(player.Health_max * 0.1))
                                        player.Gold = max(0, int(player.Gold * 0.5))
                                        combat_active = False
                                        enemy = None
                                        break
                                else:
                                    if not attack_target.is_alive:
                                        add_log(f"[bold red]💀 {attack_target.name} ha caído![/bold red]")

                            if not combat_active:
                                break

                            combat_round += 1

                        elif combat_action == 2:
                            open_inventory_menu(vInventory, player)
                            os.system("cls" if os.name == "nt" else "clear")
                            render_combat_menu(player, enemies, combat_round)
                            continue

                        elif combat_action == 3:
                            # Escape vs grupo: usa la AGI más alta entre enemigos vivos
                            base_escape_chance = random.uniform(0.3, 0.6)
                            player_eva = getattr(player, "Evasion", 0) / 100.0
                            alive = _alive_enemies(enemies)
                            enemy_agi = (max(getattr(e, "AGI", 0) for e in alive) / 100.0) if alive else 0.0
                            escape_chance = base_escape_chance + player_eva - enemy_agi

                            if random.random() < escape_chance:
                                add_log(f"\n[success]¡Escapaste con éxito! (Probabilidad: {escape_chance*100:.1f}%)[/success]")
                                _combat_delay()
                                combat_active = False
                                enemy = None
                                break
                            else:
                                add_log(f"\n[danger]¡No pudiste escapar! (Probabilidad: {escape_chance*100:.1f}%)[/danger]")
                                _combat_delay(0.5)
                                # Todos los enemigos vivos aprovechan para golpear
                                for en in _alive_enemies(enemies):
                                    _perform_attack(en, player, console, redraw_combat_screen, combat_logs)
                                    if player.Health <= 0:
                                        player.Health = max(1, int(player.Health_max * 0.1))
                                        player.Gold = max(0, int(player.Gold * 0.5))
                                        combat_active = False
                                        enemy = None
                                        break

                                if not combat_active:
                                    break

                                combat_round += 1

                    try:
                        get_mod_api().fire_event("combat_end", player, enemies, chosen_area)
                    except Exception:
                        pass

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
        open_mod_manager()



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
            sp.sleep(CONFIG["DISPLAY"].get("MENU_REFRESH_RATE", 1.0))

    elif main_input == 17 and CONFIG["DEBUG"]["ENABLED"]:
        try:
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
            sp.sleep(CONFIG["DISPLAY"].get("MENU_REFRESH_RATE", 1.0))


# Save functions handled by Modules.ModulesFunctions.SaveSystem


def init_game():
    global player, item_manager, shop_manager, chosen_area
    
    item_manager = get_item_manager()
    shop_manager = get_shop_manager()
    mod_loader_instance = get_mod_loader()
    mod_loader_instance.load_all_mods()

    # Integrar contenido de mods en los managers reales (items, tiendas, encantamientos, buffs)
    mod_api = get_mod_api()
    mod_api.integrate_all()
    mod_api.integrate_with_quest_manager(quest_manager)

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

    # Aplicar atributos de mod al jugador y disparar evento de creación
    try:
        mod_api.apply_player_attributes(player)
        mod_api.fire_event("player_created", player)
    except Exception as e:
        console.print(f"[warning]Error aplicando atributos de mod: {e}[/warning]")

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
                sp.sleep(CONFIG["DISPLAY"].get("MENU_REFRESH_RATE", 1.0))
    except Exception as e:
        console.print(f"[danger]Error: {str(e)}[/danger]")
        sys.exit(1) # 67