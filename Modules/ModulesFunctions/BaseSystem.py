"""
BaseSystem.py
=============
Sistema de construcción y mejora de edificios de la base del jugador.

Mecánica:
    - El jugador puede construir y mejorar 5 edificios.
    - Cada edificio tiene un nivel máximo definido en DataBuildings.json.
    - Los materiales provienen del sistema de Gathering existente.
    - Dos tipos de edificios: Pasivos y con Minijuego.
    - Los edificios con minijuego otorgan EXP de Mastery al completarlos.

Minijuegos:
    1. Timing (Campo de Entrenamiento): presiona Enter en el momento exacto.
    2. Endurance (Arena de Resistencia): sobrevive oleadas de daño reducido.

Efectos pasivos:
    - Almacén:    +5 slots de inventario por nivel.
    - Salón:      +2.5% EXP global por nivel (aplicado al ganar EXP en combate).
    - Tesorería:  +3% oro ganado en batallas por nivel.
"""

import os
import json
import time
import random
from typing import Dict, Optional, List

from Modules.ModulesUtils.Loader import Read
from Modules.ModulesUtils.input_utils import get_menu_refresh_rate


_BUILDINGS_JSON = os.path.join("Data", "DataBuildings.json")
_BASE_SAVE_KEY = "player_base"


# ── Clase de estado de un edificio ────────────────────────────────────────────

class Building:
    """Estado de un edificio en la base del jugador."""

    def __init__(self, building_id: str, data: dict):
        self.building_id   = building_id
        self.name          = data["Name"]
        self.icon          = data.get("Icon", "🏠")
        self.description   = data.get("Description", "")
        self.max_level     = data.get("MaxLevel", 10)
        self.passive_effect = data.get("PassiveEffect")
        self.passive_value_per_level = data.get("PassiveValuePerLevel", 0)
        self.has_minigame  = data.get("HasMinigame", False)
        self.minigame_type = data.get("MinigameType")
        self.minigame_desc = data.get("MinigameDescription", "")
        self.level_data    = data.get("Levels", {})

        # Estado mutable
        self.current_level: int = 0   # 0 = sin construir

    @property
    def is_built(self) -> bool:
        return self.current_level > 0

    @property
    def is_max(self) -> bool:
        return self.current_level >= self.max_level

    @property
    def passive_total(self) -> float:
        """Valor pasivo total al nivel actual."""
        return self.passive_value_per_level * self.current_level

    def next_level_data(self) -> Optional[dict]:
        """Datos del siguiente nivel (o None si está al máximo)."""
        next_lvl = self.current_level + 1
        if next_lvl > self.max_level:
            return None
        return self.level_data.get(str(next_lvl))

    def current_level_mastery_exp(self) -> float:
        """EXP de mastery otorgada por este edificio en su nivel actual."""
        lvl_data = self.level_data.get(str(self.current_level), {})
        return float(lvl_data.get("MasteryExpGain", 0))

    def to_dict(self) -> dict:
        return {"building_id": self.building_id, "current_level": self.current_level}

    def load_state(self, state: dict):
        self.current_level = state.get("current_level", 0)


# ── Gestor principal ───────────────────────────────────────────────────────────

class BaseManager:
    """Gestor de la base del jugador. Carga desde DataBuildings.json."""

    def __init__(self):
        self.buildings: Dict[str, Building] = {}
        self._load_definitions()

    def _load_definitions(self):
        try:
            raw = Read(_BUILDINGS_JSON, "BUILDINGS", None)
            if not raw:
                # Fallback: leer directamente
                with open(_BUILDINGS_JSON, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("BUILDINGS", {})
            for bid, bdata in raw.items():
                self.buildings[bid] = Building(bid, bdata)
        except Exception as e:
            print(f"[BaseSystem] Error cargando edificios: {e}")

    # ── Guardar / Cargar estado ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {bid: b.to_dict() for bid, b in self.buildings.items()}

    def load_from_dict(self, data: dict):
        for bid, state in data.items():
            if bid in self.buildings:
                self.buildings[bid].load_state(state)

    # ── Efectos pasivos ───────────────────────────────────────────────────────

    def get_inventory_bonus_slots(self) -> int:
        b = self.buildings.get("storage")
        return int(b.passive_total) if b else 0

    def get_exp_bonus_multiplier(self) -> float:
        """Retorna 1 + bonus_percent/100. Ej: nivel 4 → 1.10"""
        b = self.buildings.get("experience_hall")
        if not b:
            return 1.0
        return 1.0 + b.passive_total / 100.0

    def get_gold_bonus_multiplier(self) -> float:
        """Retorna 1 + bonus_percent/100. Ej: nivel 3 → 1.09"""
        b = self.buildings.get("gold_vault")
        if not b:
            return 1.0
        return 1.0 + b.passive_total / 100.0

    # ── Construcción / Mejora ─────────────────────────────────────────────────

    def can_build_or_upgrade(self, building_id: str, player, inventory) -> tuple:
        """
        Verifica si el jugador puede construir/mejorar un edificio.
        Retorna (bool, str) donde str es el motivo si es False.
        """
        b = self.buildings.get(building_id)
        if not b:
            return False, "Edificio no encontrado."
        if b.is_max:
            return False, "Ya está al nivel máximo."

        next_data = b.next_level_data()
        if not next_data:
            return False, "No hay datos para el siguiente nivel."

        # Verificar oro
        gold_cost = next_data.get("GoldCost", 0)
        if player.Gold < gold_cost:
            return False, f"Necesitas {gold_cost} oro (tienes {int(player.Gold)})."

        # Verificar materiales
        materials = next_data.get("Materials", {})
        for req_key, amount in materials.items():
            count = _count_material(inventory, req_key)
            if count < amount:
                needed = amount - count
                return False, f"Faltan {needed}x {_format_requirement(req_key, amount).split('x ', 1)[-1]}."

        return True, "OK"

    def build_or_upgrade(self, building_id: str, player, inventory) -> bool:
        """Ejecuta la construcción/mejora. Retorna True si tuvo éxito."""
        ok, reason = self.can_build_or_upgrade(building_id, player, inventory)
        if not ok:
            return False

        b = self.buildings[building_id]
        next_data = b.next_level_data()
        if not next_data:
            return False

        # Descontar oro
        player.Gold -= next_data.get("GoldCost", 0)

        # Consumir materiales
        for req_key, amount in next_data.get("Materials", {}).items():
            _consume_material(inventory, req_key, amount)

        # Subir nivel
        b.current_level += 1
        return True


# ── Minijuego: Timing ─────────────────────────────────────────────────────────

def minigame_timing(console, building: Building) -> bool:
    """
    Minijuego de timing para el Campo de Entrenamiento.
    Muestra una barra en movimiento. El jugador debe presionar Enter
    cuando el cursor esté en la zona objetivo (marcada con ★).
    Retorna True si acertó, False si falló.
    """
    from Modules.ModulesUtils.input_utils import keyboard_listener_scope
    from sshkeyboard import listen_keyboard, stop_listening
    import threading

    console.print(
        f"\n[bold yellow]━━━ {building.icon} {building.name} — Entrenamiento ━━━[/]"
    )
    console.print(f"[dim]{building.minigame_desc}[/dim]\n")
    console.print("Pulsa [bold]Enter[/bold] cuando el cursor '●' llegue a la zona [bold green]★★★[/bold green].\n")
    time.sleep(get_menu_refresh_rate())

    BAR_LEN = 30
    TARGET_START = 12
    TARGET_END = 18

    state = {"pressed": False, "done": False, "position": 0}

    def on_press(key):
        if key == "enter" and not state["done"]:
            state["pressed"] = True
            state["done"] = True
            stop_listening()

    def _run_bar():
        pos = 0
        direction = 1
        while not state["done"]:
            state["position"] = pos
            bar = list("─" * BAR_LEN)
            for i in range(TARGET_START, TARGET_END):
                bar[i] = "★"
            bar[pos] = "●"
            in_zone = TARGET_START <= pos < TARGET_END
            color = "green" if in_zone else "white"
            rendered = "".join(bar)
            print(f"\r[{rendered}]", end="", flush=True)
            time.sleep(0.07)
            pos += direction
            if pos >= BAR_LEN - 1 or pos <= 0:
                direction *= -1

    bar_thread = threading.Thread(target=_run_bar, daemon=True)
    bar_thread.start()

    with keyboard_listener_scope():
        listen_keyboard(on_press=on_press, sequential=True)

    state["done"] = True
    bar_thread.join(timeout=1)
    print()

    pos = state["position"]
    hit = TARGET_START <= pos < TARGET_END
    if hit:
        console.print("[bold green]¡Impacto perfecto! Entrenamiento exitoso.[/bold green]")
    else:
        console.print("[bold red]¡Fallaste! El golpe fue demasiado temprano o tarde.[/bold red]")
    return hit


# ── Minijuego: Endurance ──────────────────────────────────────────────────────

def minigame_endurance(console, building: Building, player) -> bool:
    """
    Minijuego de resistencia para la Arena de Armaduras.
    El jugador recibe 3 oleadas de daño (10% de su HP máximo cada una).
    Debe sobrevivir las 3 oleadas. No causa daño real; solo simula.
    Retorna True si sobrevivió todas las oleadas.
    """
    console.print(
        f"\n[bold cyan]━━━ {building.icon} {building.name} — Arena de Resistencia ━━━[/]"
    )
    console.print(f"[dim]{building.minigame_desc}[/dim]\n")
    console.print("Recibirás 3 oleadas de golpes de entrenamiento.")
    console.print("Tu salud no baja de verdad, pero debes \"aguantar\" las 3 oleadas.\n")
    time.sleep(get_menu_refresh_rate())

    WAVES = 3
    survived = True

    for wave in range(1, WAVES + 1):
        base_damage = player.Health_max * 0.10
        # Reducir por DEF del jugador
        actual_dmg = max(1.0, base_damage - player.DEF[0] / 2)
        console.print(f"[yellow]Oleada {wave}/{WAVES}:[/yellow] Impacto de entrenamiento — {actual_dmg:.1f} daño simulado.")

        # Animación de "aguante"
        for i in range(5):
            print("\r  Aguantando" + "." * (i + 1) + " " * (5 - i), end="", flush=True)
            time.sleep(0.3)
        print()

        # Probabilidad de fallo: si HP_max es muy bajo y daño es alto, puede "rendirse"
        if player.Health_max < 20 and actual_dmg > player.Health_max * 0.5:
            survived = False
            console.print("[bold red]El personaje no pudo aguantar el entrenamiento.[/bold red]")
            break

        console.print(f"  [green]✓ Oleada {wave} superada.[/green]")
        time.sleep(0.4)

    if survived:
        console.print("\n[bold green]¡Resistencia total! Entrenamiento de armadura exitoso.[/bold green]")
    return survived


# ── Menú de Base ──────────────────────────────────────────────────────────────

def open_base_menu(player, inventory, console, menu_fn, pause_fn):
    """Menú principal de la base del jugador."""
    from rich.panel import Panel
    from rich.table import Table

    base_mgr = _get_base_manager(player)

    while True:
        os.system("cls" if os.name == "nt" else "clear")

        # Resumen de efectos pasivos
        inv_slots = base_mgr.get_inventory_bonus_slots()
        exp_bonus = (base_mgr.get_exp_bonus_multiplier() - 1) * 100
        gold_bonus = (base_mgr.get_gold_bonus_multiplier() - 1) * 100

        summary = (
            f"[green]📦 Slots extra: +{inv_slots}[/green]  |  "
            f"[cyan]⭐ EXP bonus: +{exp_bonus:.1f}%[/cyan]  |  "
            f"[yellow]💰 Oro bonus: +{gold_bonus:.1f}%[/yellow]"
        )
        console.print(Panel(summary, title="🏰 Tu Base", border_style="bright_white"))

        options = [(0, "Volver al menú principal")]
        ordered = list(base_mgr.buildings.items())
        for i, (bid, b) in enumerate(ordered, 1):
            lvl_str = f"Nv.{b.current_level}/{b.max_level}" if b.is_built else "Sin construir"
            badge = "✓" if b.is_built else "·"
            options.append((i, f"{b.icon} {b.name}  [{badge}] {lvl_str}"))

        choice = menu_fn(
            title="🏰 Base — Edificios",
            subtitle=f"Oro: {int(player.Gold)}",
            options=options,
            prompt="Edificio: ",
            default_value=0,
            border_style="yellow",
        )

        if choice == 0:
            break

        bid, b = ordered[choice - 1]
        _building_submenu(b, bid, base_mgr, player, inventory, console, menu_fn, pause_fn)


def _building_submenu(building, bid, base_mgr, player, inventory, console, menu_fn, pause_fn):
    """Submenú de un edificio específico."""
    from rich.panel import Panel

    while True:
        next_data = building.next_level_data()
        next_lvl = building.current_level + 1

        sub = [(0, "Volver")]

        can_build, reason = base_mgr.can_build_or_upgrade(bid, player, inventory)
        action_label = f"Construir (Nv.1)" if not building.is_built else f"Mejorar a Nv.{next_lvl}"
        if building.is_max:
            sub.append((1, f"[dim]Al nivel máximo[/dim]"))
        else:
            cost_str = f"{next_data.get('GoldCost', 0)} oro" if next_data else "?"
            mats_str = ", ".join(
                _format_requirement(k, v)
                for k, v in next_data.get("Materials", {}).items()
            ) if next_data else "?"
            can_str = "[green]✓[/green]" if can_build else f"[red]✗ {reason}[/red]"
            sub.append((1, f"{action_label}  ({cost_str} | {mats_str}) {can_str}"))

        if building.is_built and building.has_minigame:
            sub.append((2, f"🎮 Entrenar (Minijuego) — +{building.current_level_mastery_exp():.0f} EXP Mastery"))

        sub.append((3, "📋 Ver detalles del edificio"))

        choice = menu_fn(
            title=f"{building.icon} {building.name}",
            subtitle=building.description,
            options=sub,
            prompt="Acción: ",
            default_value=0,
            border_style="yellow",
        )

        if choice == 0:
            break

        elif choice == 1 and not building.is_max:
            if can_build:
                if base_mgr.build_or_upgrade(bid, player, inventory):
                    console.print(
                        f"[success]✅ {building.icon} {building.name} mejorado a Nv.{building.current_level}![/success]"
                    )
                else:
                    console.print("[danger]Error al construir el edificio.[/danger]")
            else:
                console.print(f"[warning]{reason}[/warning]")
            pause_fn()

        elif choice == 2 and building.has_minigame:
            _run_training(building, player, console, pause_fn)

        elif choice == 3:
            _show_building_details(building, console, pause_fn)


def _run_training(building, player, console, pause_fn):
    """Ejecuta el minijuego del edificio y otorga EXP de Mastery."""
    from Modules.ModulesFunctions.MasterySystem import ensure_mastery

    mgr = ensure_mastery(player)
    exp_gain = building.current_level_mastery_exp()

    success = False

    if building.minigame_type == "timing":
        success = minigame_timing(console, building)
    elif building.minigame_type == "endurance":
        success = minigame_endurance(console, building, player)

    if success and exp_gain > 0:
        # Dar EXP a todos los masteries del tipo correspondiente
        if building.building_id == "weapon_training":
            from Modules.ModulesFunctions.MasterySystem import WEAPON_TYPES
            for wt in WEAPON_TYPES:
                skill = mgr.weapon_masteries.get(wt)
                if skill:
                    levels = skill.add_exp(exp_gain)
                    if levels > 0:
                        console.print(
                            f"[green]⚔️  Mastery de {skill.name} subió a Nv.{skill.current_level}![/green]"
                        )
        elif building.building_id == "armor_training":
            from Modules.ModulesFunctions.MasterySystem import ARMOR_TYPES
            for at in ARMOR_TYPES:
                skill = mgr.armor_masteries.get(at)
                if skill:
                    levels = skill.add_exp(exp_gain)
                    if levels > 0:
                        console.print(
                            f"[cyan]🛡️  Mastery de {skill.name} subió a Nv.{skill.current_level}![/cyan]"
                        )

        console.print(f"[dim]EXP de Mastery ganada: +{exp_gain:.0f}[/dim]")

    pause_fn()


def _show_building_details(building: Building, console, pause_fn):
    """Muestra detalles y tabla de niveles de un edificio."""
    from rich.table import Table
    from rich.panel import Panel

    t = Table(title=f"{building.icon} {building.name} — Niveles", show_header=True)
    t.add_column("Nivel", justify="center", style="yellow")
    t.add_column("Costo Oro", justify="right")
    t.add_column("Materiales")
    t.add_column("Bonus", style="green")

    for lvl_str, lvl_data in building.level_data.items():
        lvl = int(lvl_str)
        current = building.current_level
        style = "bold green" if lvl == current else ("dim" if lvl < current else "")
        mats = ", ".join(
            _format_requirement(k, v)
            for k, v in lvl_data.get("Materials", {}).items()
        )
        t.add_row(
            f"{'✓ ' if lvl == current else ''}{lvl}",
            str(lvl_data.get("GoldCost", 0)),
            mats,
            lvl_data.get("Bonus", ""),
            style=style,
        )

    console.print(Panel(t, border_style="yellow"))
    pause_fn()


# ── Helpers de materiales ─────────────────────────────────────────────────────
#
# Los requisitos en DataBuildings.json pueden ser de DOS tipos:
#
#   A) Tipo de material (OR):  "Wood": 5
#      Cualquier combinación de items cuyo Material_Type == "Wood" suma para
#      alcanzar la cantidad requerida.
#      Ej: 2x Madera de Roble + 3x Madera de Pino = 5  ✓
#
#   B) Item exacto (nombre):   "Madera de Roble": 3
#      Solo ese item específico cuenta.
#
# El sistema detecta automáticamente cuál es el caso:
#   - Si el requisito coincide con algún Material_Type conocido → modo OR.
#   - Si no → búsqueda por nombre exacto (compatibilidad hacia atrás).
#

# Tipos conocidos (deben coincidir con Material_Type en DataItems.json)
_KNOWN_MATERIAL_TYPES = {"Wood", "Rock", "Ore", "Herbs", "Leather", "Crystal",
                          "Fiber", "Bone", "Essence", "Gem"}

# Cache de mapeo Material_Type → lista de nombres de item
# Se llena la primera vez que se necesita desde el ItemManager.
_mat_type_cache: Dict[str, List[str]] = {}


def _build_mat_type_cache():
    """Llena _mat_type_cache leyendo DataItems.json vía ItemManager."""
    global _mat_type_cache
    if _mat_type_cache:
        return
    try:
        from Modules.ModulesManager.ItemManager import get_item_manager
        im = get_item_manager()
        mats = im.items_data.get("TYPE:Materials", {})
        for key, data in mats.items():
            mat_type = data.get("Material_Type", "")
            name = data.get("Name", "")
            if mat_type and name:
                _mat_type_cache.setdefault(mat_type, []).append(name)
    except Exception as e:
        print(f"[BaseSystem] No se pudo cargar caché de materiales: {e}")


def _is_type_requirement(req_key: str) -> bool:
    """True si req_key es un Material_Type (modo OR)."""
    _build_mat_type_cache()
    return req_key in _mat_type_cache or req_key in _KNOWN_MATERIAL_TYPES


def _names_for_type(mat_type: str) -> List[str]:
    """Devuelve todos los nombres de items que corresponden a ese Material_Type."""
    _build_mat_type_cache()
    return _mat_type_cache.get(mat_type, [])


def _count_material(inventory, req_key: str) -> int:
    """
    Cuenta cuántas unidades del requisito tiene el jugador.
    Si req_key es un Material_Type, suma todos los items de ese tipo (OR).
    Si no, busca por nombre exacto.
    """
    total = 0
    if _is_type_requirement(req_key):
        valid_names = {n.lower() for n in _names_for_type(req_key)}
        for slot in inventory.slots:
            name = getattr(slot.item, "Name", getattr(slot.item, "name", ""))
            if name.lower() in valid_names:
                total += slot.quantity
    else:
        for slot in inventory.slots:
            name = getattr(slot.item, "Name", getattr(slot.item, "name", ""))
            if name.lower() == req_key.lower():
                total += slot.quantity
    return total


def _consume_material(inventory, req_key: str, amount: int):
    """
    Consume `amount` unidades del requisito del inventario.
    Si es tipo OR, consume de cualquier item válido (primero los que aparecen antes).
    """
    remaining = amount
    if _is_type_requirement(req_key):
        valid_names = {n.lower() for n in _names_for_type(req_key)}
        match_fn = lambda name: name.lower() in valid_names
    else:
        match_fn = lambda name: name.lower() == req_key.lower()

    for slot in list(inventory.slots):
        if remaining <= 0:
            break
        name = getattr(slot.item, "Name", getattr(slot.item, "name", ""))
        if match_fn(name):
            removed = slot.remove(remaining)
            remaining -= removed

    # Limpiar slots vacíos
    inventory.slots = [s for s in inventory.slots if not s.is_empty()]


def _format_requirement(req_key: str, amount: int) -> str:
    """
    Genera un texto legible para un requisito de material.
    Ej:  "Wood: 5"  →  "5x Madera (Roble/Pino/Abedul/Arce/Ébano)"
         "Madera de Roble: 3" → "3x Madera de Roble"
    """
    if _is_type_requirement(req_key):
        names = _names_for_type(req_key)
        if names:
            short = [n.split(" de ")[-1] if " de " in n else n for n in names]
            return f"{amount}x {req_key} ({'/'.join(short)})"
        return f"{amount}x {req_key}"
    return f"{amount}x {req_key}"


# ── Singleton por jugador ─────────────────────────────────────────────────────

def _get_base_manager(player) -> BaseManager:
    """Obtiene (o crea) el BaseManager asociado al jugador."""
    if not hasattr(player, "base_manager") or player.base_manager is None:
        player.base_manager = BaseManager()
    return player.base_manager
