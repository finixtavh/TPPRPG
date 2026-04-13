
import os
import json
import time
from typing import Optional, Dict, Any

from Modules.Loader import Read
from Modules.GatheringMasterySystem import cTool, cMaterial
from Modules.setup import cObject
from Modules.setup import cWeapon, cEquippableItems
from Modules.CompanionSystem import load_companion_by_id
from Modules.MasterySystem import MasteryManager
from Modules.BaseSystem import BaseManager

_SAVE_DIR = os.path.join("Data", "Saves")
_SLOT_PATHS = {
    1: os.path.join(_SAVE_DIR, "Slot1.json"),
    2: os.path.join(_SAVE_DIR, "Slot2.json"),
    3: os.path.join(_SAVE_DIR, "Slot3.json"),
}




def _serialize_item(item) -> Optional[dict]:
    """Convierte un objeto de item a dict serializable."""
    if item is None:
        return None
    item_id = getattr(item, "ID", getattr(item, "STATIC_ID", None))
    item_name = getattr(item, "Name", getattr(item, "name", "???"))
    category = getattr(item, "item_category", getattr(item, "objectcheck", None))
    # Encantamientos si existen
    enchantments = []
    if hasattr(item, "enchantments"):
        for ench in item.enchantments:
            enchantments.append({
                "id": getattr(ench, "ENCHANT_ID", None),
                "level": getattr(ench, "current_level", 1),
            })
    return {
        "id": item_id,
        "name": item_name,
        "category": category,
        "enchantments": enchantments,
    }


def _serialize_companion(comp) -> dict:
    """Serializa un compañero."""
    return {
        "companion_id": getattr(comp, "companion_id", "unknown"),
        "name": comp.name,
        "Health": comp.Health,
        "Health_max": comp.Health_max,
        "Mana": comp.Mana,
        "Mana_max": comp.Mana_max,
        "is_alive": comp.is_alive,
        "Level": comp.Level,
        "weapon": _serialize_item(getattr(comp, "weapon", None)),
        "armor": _serialize_item(getattr(comp, "armor", None)),
    }


def _serialize_inventory(inventory) -> list:
    """Serializa el inventario completo."""
    result = []
    for slot in inventory.slots:
        item_data = _serialize_item(slot.item)
        if item_data:
            result.append({
                "item": item_data,
                "quantity": slot.quantity,
            })
    return result


def _serialize_mastery(player) -> dict:
    """Serializa los masteries del jugador."""
    if not hasattr(player, "mastery_manager") or player.mastery_manager is None:
        return {}
    return player.mastery_manager.to_dict()


def _serialize_base(player) -> dict:
    """Serializa el estado de la base."""
    if not hasattr(player, "base_manager") or player.base_manager is None:
        return {}
    return player.base_manager.to_dict()


def build_save_data(player, inventory, chosen_area, active_enemies_ids=None) -> dict:
    """Construye el dict completo de guardado."""
    # Equipamiento del jugador (todos los slots)
    equipment = {}
    for slot_name in ["weapon", "helmet", "armor", "boots", "ring", "ring2", "ring3", "tool", "SecHand"]:
        equipment[slot_name] = _serialize_item(getattr(player, slot_name, None))

    return {
        "version": "1.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player": {
            "name": player.name,
            "Level": player.Level,
            "lvlPoints": player.lvlPoints,
            "Health": player.Health,
            "Health_max": player.Health_max,
            "Mana": player.Mana,
            "Mana_max": player.Mana_max,
            "EXP": player.EXP,
            "EXP_M": player.EXP_M,
            "Gold": player.Gold,
            "DEF": list(player.DEF),
            "AGI": player.AGI,
            "DefensePercentage": list(player.DefensePercentage),
            "CounterAttack": player.CounterAttack,
            "Evasion": player.Evasion,
            "ManaRegen": player.ManaRegen,
            "RAC": getattr(player, "RAC", 0),
            "Control": getattr(player, "Control", 0),
            "Barrier": getattr(player, "Barrier", 0),
        },
        "equipment": equipment,
        "inventory": _serialize_inventory(inventory),
        "companions": [_serialize_companion(c) for c in player.companion],
        "companion_bank": [_serialize_companion(c) for c in getattr(player, "companion_bank", [])],
        "skills_purchased": player.skills_purchased if isinstance(player.skills_purchased, dict) else {},
        "mastery": _serialize_mastery(player),
        "base": _serialize_base(player),
        "game_state": {
            "chosen_area": chosen_area,
        },
    }


# ── Guardar ───────────────────────────────────────────────────────────────────

def save_to_slot(slot: int, player, inventory, chosen_area) -> bool:
    """
    Guarda la partida en el slot indicado (1, 2 o 3).
    Retorna True si tuvo éxito.
    """
    if slot not in _SLOT_PATHS:
        return False

    os.makedirs(_SAVE_DIR, exist_ok=True)
    path = _SLOT_PATHS[slot]

    try:
        data = build_save_data(player, inventory, chosen_area)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[SaveSystem] Error guardando slot {slot}: {e}")
        return False


# ── Cargar ────────────────────────────────────────────────────────────────────

def load_from_slot(slot: int, player, inventory, item_manager) -> Optional[dict]:
    """
    Carga la partida del slot indicado.
    Restaura el estado del jugador y del inventario.
    Retorna el dict de game_state (chosen_area etc.) o None si falla.
    """
    if slot not in _SLOT_PATHS:
        return None

    path = _SLOT_PATHS[slot]
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[SaveSystem] Error leyendo slot {slot}: {e}")
        return None

    try:
        _restore_player(player, data.get("player", {}))
        _restore_equipment(player, data.get("equipment", {}), item_manager)
        _restore_inventory(inventory, data.get("inventory", []), item_manager)
        _restore_companions(player, data.get("companions", []), data.get("companion_bank", []), item_manager)
        _restore_skills(player, data.get("skills_purchased", {}))
        _restore_mastery(player, data.get("mastery", {}))
        _restore_base(player, data.get("base", {}))
        return data.get("game_state", {})
    except Exception as e:
        print(f"[SaveSystem] Error restaurando estado del slot {slot}: {e}")
        import traceback; traceback.print_exc()
        return None


def _restore_player(player, pdata: dict):
    """Restaura los stats básicos del jugador."""
    for attr in ["name", "Level", "lvlPoints", "Health", "Health_max",
                 "Mana", "Mana_max", "EXP", "EXP_M", "Gold",
                 "AGI", "CounterAttack", "Evasion", "ManaRegen",
                 "RAC", "Control", "Barrier"]:
        if attr in pdata:
            setattr(player, attr, pdata[attr])
    if "DEF" in pdata:
        player.DEF = list(pdata["DEF"])
    if "DefensePercentage" in pdata:
        player.DefensePercentage = list(pdata["DefensePercentage"])


def _restore_equipment(player, equip_data: dict, item_manager):
    """Restaura el equipamiento del jugador por ID."""
    from Modules.setup import cWeapon, cEquippableItems
    try:
        from Modules.GatheringMasterySystem import cTool
        from Modules.setup import cObject
    except ImportError:
        cTool = None
        cObject = None

    for slot_name, item_info in equip_data.items():
        if item_info is None:
            setattr(player, slot_name, None)
            continue
        item_id = item_info.get("id")
        if item_id is None:
            continue
        try:
            item_obj = item_manager.create_item_object(
                item_id, cWeapon, cEquippableItems, cObject, cTool
            )
            if item_obj == True and not isinstance(item_obj, cWeapon):
                # Re-aplicar encantamientos si existen (simplificado)
                setattr(player, slot_name, item_obj)
                if hasattr(item_obj, "AppliedStats"):
                    item_obj.AppliedStats = False
        except Exception:
            pass


def _restore_inventory(inventory, inv_data: list, item_manager):
    """Restaura el inventario."""

    inventory.slots.clear()

    for entry in inv_data:
        item_info = entry.get("item", {})
        quantity = entry.get("quantity", 1)
        item_id = item_info.get("id")
        if item_id is None:
            continue
        try:
            item_obj = item_manager.create_item_object(
                item_id, cWeapon, cEquippableItems, cObject, cTool, cMaterial
            )
            if item_obj:
                inventory.addObject(item_obj, quantity)
        except Exception:
            pass


def _restore_companions(player, companions_data: list, bank_data: list, item_manager):
    """Restaura los compañeros activos e inactivos."""

    player.companion = []
    if not hasattr(player, "companion_bank"):
        player.companion_bank = []
    player.companion_bank = []

    def _load_comp_list(cdata_list, target_list):
        for cdata in cdata_list:
            cid = cdata.get("companion_id", "")
            comp = load_companion_by_id(cid)
            if comp is None:
                continue
            # Restaurar estado
            comp.Health = float(cdata.get("Health", comp.Health_max))
            comp.Health_max = float(cdata.get("Health_max", comp.Health_max))
            comp.Mana = float(cdata.get("Mana", comp.Mana_max))
            comp.Mana_max = float(cdata.get("Mana_max", comp.Mana_max))
            comp.is_alive = cdata.get("is_alive", True)
            comp.Level = cdata.get("Level", 1)
            target_list.append(comp)

    _load_comp_list(companions_data, player.companion)
    _load_comp_list(bank_data, player.companion_bank)


def _restore_skills(player, skills_data: dict):
    """Restaura el árbol de habilidades."""
    player.skills_purchased = skills_data if isinstance(skills_data, dict) else {}


def _restore_mastery(player, mastery_data: dict):
    """Restaura los masteries."""
    if not mastery_data:
        return  
    player.mastery_manager = MasteryManager.from_dict(mastery_data)

def _restore_base(player, base_data: dict):
    """Restaura el estado de la base."""
    if not base_data:
        return
    try:
        mgr = BaseManager()
        mgr.load_from_dict(base_data)
        player.base_manager = mgr
    except Exception as e:
        print(f"[SaveSystem] Error restaurando base: {e}")

def get_slot_info(slot: int) -> dict:
    """
    Retorna metadatos de un slot.
    {'exists': bool, 'player_name': str, 'level': int, 'timestamp': str, 'area': str}
    """
    path = _SLOT_PATHS.get(slot)
    if not path or not os.path.exists(path):
        return {"exists": False}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pdata = data.get("player", {})
        gs = data.get("game_state", {})
        return {
            "exists": True,
            "player_name": pdata.get("name", "???"),
            "level": pdata.get("Level", 1),
            "timestamp": data.get("timestamp", "???"),
            "area": gs.get("chosen_area", "Ninguna"),
        }
    except Exception:
        return {"exists": False}

def save_load_menu(player, inventory, chosen_area, item_manager, console, menu_fn, pause_fn) -> Optional[dict]:
    """
    Menú completo de guardar / cargar con 3 slots.
    Retorna dict de game_state si se cargó, None si solo se guardó o canceló.
    """
    from rich.panel import Panel

    while True:
        action = menu_fn(
            title="💾 Guardar / Cargar Partida",
            subtitle="Selecciona una acción",
            options=[
                (1, "Guardar partida"),
                (2, "Cargar partida"),
                (0, "Cancelar"),
            ],
            prompt="Acción: ",
            default_value=1,
            border_style="yellow",
        )

        if action == 0:
            return None

        # Mostrar info de slots
        slot_options = [(0, "Cancelar")]
        for s in [1, 2, 3]:
            info = get_slot_info(s)
            if info["exists"]:
                label = (
                    f"Slot {s}: {info['player_name']}  Nv.{info['level']}  "
                    f"[{info['area']}]  {info['timestamp']}"
                )
            else:
                label = f"Slot {s}: [dim]Vacío[/dim]"
            slot_options.append((s, label))

        chosen_slot = menu_fn(
            title="Selecciona un Slot",
            options=slot_options,
            prompt="Slot: ",
            default_value=1,
            border_style="cyan",
        )

        if chosen_slot == 0:
            continue

        if action == 1:
            # Guardar
            if save_to_slot(chosen_slot, player, inventory, chosen_area):
                console.print(f"[success]Partida guardada en Slot {chosen_slot}.[/success]")
            else:
                console.print(f"[danger]Error al guardar en Slot {chosen_slot}.[/danger]")
            pause_fn()
            return None

        elif action == 2:
            # Cargar
            info = get_slot_info(chosen_slot)
            if not info["exists"]:
                console.print(f"[warning]El Slot {chosen_slot} está vacío.[/warning]")
                pause_fn()
                continue

            confirm = menu_fn(
                title=f"¿Cargar Slot {chosen_slot}?",
                subtitle=f"{info['player_name']} Nv.{info['level']} — {info['timestamp']}",
                options=[(1, "Sí, cargar"), (0, "Cancelar")],
                prompt="Confirmar: ",
                default_value=0,
                border_style="yellow",
            )
            if confirm == 1:
                game_state = load_from_slot(chosen_slot, player, inventory, item_manager)
                if game_state is not None:
                    console.print(f"[success]Partida del Slot {chosen_slot} cargada.[/success]")
                    pause_fn()
                    return game_state
                else:
                    console.print(f"[danger]Error al cargar el Slot {chosen_slot}.[/danger]")
                    pause_fn()
