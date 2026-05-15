"""
ItemModifierSystem.py
=====================
Sistema de Modificadores de Objetos (prefijos tipo Terraria).

Cada objeto de tipo cWeapon, cEquippableItems o cTool puede recibir
UN modificador al ser creado (loot o crafteo). El modificador cambia
atributos del objeto in-place y queda guardado en item.modifier.

Separación de tipos:
  - cWeapon          → WEAPON_MODIFIERS
  - cEquippableItems → ARMOR_MODIFIERS
  - cTool            → TOOL_MODIFIERS  (exclusivos de herramientas)

Uso principal:
  from Modules.ModulesManager.ItemModifierSystem import roll_and_apply_modifier
  roll_and_apply_modifier(item, quality_pos=1.0, quality_neg=1.0)
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field


# ── Clase base de modificador ─────────────────────────────────────────────────

@dataclass
class ItemModifier:
    """Define un modificador de objeto."""
    name:        str
    icon:        str
    is_negative: bool
    weight:      int           # peso relativo para random.choices()
    effects:     Dict[str, float] = field(default_factory=dict)
    # Claves de effects soportadas:
    #   dmg_pct, dmg_min_flat, agi_pct, counter_pct, mana_flat   (cWeapon)
    #   def_flat, def_all_flat, def_pct, hp_flat                  (cEquippableItems)
    #   efficiency_pct                                             (cTool)

    def display(self) -> str:
        """Texto coloreado para mostrar en UI."""
        color = "red" if self.is_negative else "green"
        return f"[{color}]{self.icon} {self.name}[/{color}]"


# ── Tablas de modificadores ───────────────────────────────────────────────────

WEAPON_MODIFIERS: List[ItemModifier] = [
    # --- Positivos: Daño ---
    ItemModifier("Afilado",    "⚔",  False, 35, {"dmg_pct": 0.02}),
    ItemModifier("Forjado",    "🔨", False, 25, {"dmg_pct": 0.04}),
    ItemModifier("Brutal",     "💥", False, 18, {"dmg_pct": 0.06}),
    ItemModifier("Implacable", "🩸", False,  9, {"dmg_pct": 0.08, "dmg_min_flat": 1}),
    # --- Positivos: Velocidad / Agilidad ---
    ItemModifier("Veloz",      "💨", False, 28, {"agi_pct": 0.03}),
    ItemModifier("Ágil",       "🌬", False, 18, {"agi_pct": 0.05}),
    # --- Positivos: Crítico ---
    ItemModifier("Preciso",    "🎯", False, 20, {"counter_pct": 0.03}),
    ItemModifier("Letal",      "☠",  False,  9, {"counter_pct": 0.05}),
    # --- Positivos: Mana ---
    ItemModifier("Arcano",     "🔮", False, 15, {"mana_flat": 25.0}),
    # --- Negativos ---
    ItemModifier("Oxidado",    "🦠", True,  30, {"dmg_pct": -0.03}),
    ItemModifier("Mellado",    "🪨", True,  25, {"dmg_pct": -0.02, "dmg_min_flat": -1}),
    ItemModifier("Frágil",     "💔", True,  15, {"dmg_pct": -0.05}),
]

ARMOR_MODIFIERS: List[ItemModifier] = [
    # --- Positivos: Defensa física ---
    ItemModifier("Reforzado",    "🛡",  False, 35, {"def_flat": 2.0}),
    ItemModifier("Blindado",     "⚙",  False, 22, {"def_flat": 4.0}),
    ItemModifier("Inexpugnable", "🏰", False,  9, {"def_flat": 3.0, "def_all_flat": 1.0}),
    # --- Positivos: Defensa porcentual ---
    ItemModifier("Resistente",   "💪", False, 18, {"def_pct": 0.02}),
    # --- Positivos: HP ---
    ItemModifier("Vital",        "❤",  False, 30, {"hp_flat": 15.0}),
    ItemModifier("Robusto",      "🫀", False, 18, {"hp_flat": 30.0}),
    # --- Negativos ---
    ItemModifier("Deteriorado",  "🪨", True,  30, {"def_flat": -2.0}),
    ItemModifier("Desgastado",   "💔", True,  20, {"def_flat": -1.0, "hp_flat": -5.0}),
]

TOOL_MODIFIERS: List[ItemModifier] = [
    # --- Positivos ---
    ItemModifier("Eficiente",  "⚒",  False, 40, {"efficiency_pct": 0.10}),
    ItemModifier("Maestro",    "🏅", False, 25, {"efficiency_pct": 0.20}),
    ItemModifier("Experto",    "🌟", False, 12, {"efficiency_pct": 0.30}),
    ItemModifier("Diligente",  "🔆", False,  8, {"efficiency_pct": 0.15, "gather_xp_pct": 0.05}),
    # --- Negativos ---
    ItemModifier("Torpe",      "🐢", True,  30, {"efficiency_pct": -0.10}),
    ItemModifier("Roto",       "💔", True,  20, {"efficiency_pct": -0.15}),
]

# Chance base de que un objeto reciba un modificador
BASE_MODIFIER_CHANCE = 0.60


# ── Función de roll ───────────────────────────────────────────────────────────

def _get_table(item) -> Optional[List[ItemModifier]]:
    """Devuelve la tabla de modificadores según el tipo del objeto."""
    cls_name = type(item).__name__
    if cls_name == "cWeapon":
        return WEAPON_MODIFIERS
    if cls_name == "cEquippableItems":
        return ARMOR_MODIFIERS
    if cls_name == "cTool":
        return TOOL_MODIFIERS
    return None


def roll_modifier(
    item,
    quality_pos: float = 1.0,
    quality_neg: float = 1.0,
) -> Optional[ItemModifier]:
    """
    Decide si el objeto recibe un modificador y cuál.

    quality_pos: multiplicador de peso para positivos  (1.0 = normal, 1.5 = +50% más probable)
    quality_neg: multiplicador de peso para negativos  (1.0 = normal, 1.5 = +50% más probable)

    Retorna la instancia ItemModifier elegida, o None si no se asigna.
    """
    table = _get_table(item)
    if not table:
        return None

    if random.random() > BASE_MODIFIER_CHANCE:
        return None  # Este objeto no tendrá modificador

    weighted = []
    weights  = []
    for mod in table:
        multiplier = quality_neg if mod.is_negative else quality_pos
        w = max(1, int(mod.weight * multiplier))
        weighted.append(mod)
        weights.append(w)

    return random.choices(weighted, weights=weights, k=1)[0]


# ── Aplicación del modificador ────────────────────────────────────────────────

def apply_modifier_to_item(item, modifier: ItemModifier) -> None:
    """
    Aplica el modificador al objeto in-place.
    Guarda la referencia en item.modifier para UI.
    """
    e = modifier.effects

    # cWeapon
    if hasattr(item, "DMG") and hasattr(item, "DMG_min"):
        if "dmg_pct" in e:
            pct = e["dmg_pct"]
            item.DMG = [max(0.0, v * (1 + pct)) for v in item.DMG]
            # DMG_min no puede superar DMG
            item.DMG_min = [max(0.0, min(v * (1 + pct), item.DMG[i]))
                            for i, v in enumerate(item.DMG_min)]
        if "dmg_min_flat" in e:
            flat = e["dmg_min_flat"]
            item.DMG_min = [max(0.0, v + flat) for v in item.DMG_min]
        if "agi_pct" in e:
            current = getattr(item, "StatsBoosts", {}).get("AGI", 0)
            item.StatsBoosts = getattr(item, "StatsBoosts", {})
            item.StatsBoosts["AGI"] = current + e["agi_pct"] * 100  # guardamos como flat bonus
        if "counter_pct" in e:
            cb = getattr(item, "StatsBoosts", {})
            cb["CounterAttack"] = cb.get("CounterAttack", 0) + e["counter_pct"] * 100
            item.StatsBoosts = cb
        if "mana_flat" in e:
            cb = getattr(item, "StatsBoosts", {})
            cb["Mana_max"] = cb.get("Mana_max", 0) + e["mana_flat"]
            item.StatsBoosts = cb

    # cEquippableItems
    elif hasattr(item, "Defense") and hasattr(item, "HealthBoost"):
        if "def_flat" in e:
            item.Defense = [max(0.0, v + e["def_flat"]) for v in item.Defense]
        if "def_all_flat" in e:
            item.Defense = [max(0.0, v + e["def_all_flat"]) for v in item.Defense]
        if "def_pct" in e:
            item.Defense = [max(0.0, v * (1 + e["def_pct"])) for v in item.Defense]
        if "hp_flat" in e:
            item.HealthBoost = getattr(item, "HealthBoost", 0) + e["hp_flat"]

    # cTool
    elif hasattr(item, "Efficiency"):
        if "efficiency_pct" in e:
            item.Efficiency = max(0.01, item.Efficiency * (1 + e["efficiency_pct"]))
        if "gather_xp_pct" in e:
            item.gather_xp_bonus = getattr(item, "gather_xp_bonus", 0.0) + e["gather_xp_pct"]

    # Guardar referencia para UI
    item.modifier = modifier


def roll_and_apply_modifier(
    item,
    quality_pos: float = 1.0,
    quality_neg: float = 1.0,
) -> Optional[ItemModifier]:
    """Atajo que hace roll + apply en un solo call. Devuelve el modificador o None."""
    mod = roll_modifier(item, quality_pos, quality_neg)
    if mod is not None:
        apply_modifier_to_item(item, mod)
    return mod


# ── Helpers de display ────────────────────────────────────────────────────────

def get_modifier_display(item) -> str:
    """
    Retorna el texto coloreado del modificador del objeto, o cadena vacía.
    Ejemplo: "[green]⚔ Afilado[/green]"
    """
    mod = getattr(item, "modifier", None)
    if mod is None:
        return ""
    return mod.display()


def get_item_display_name(item) -> str:
    """
    Nombre del item con el prefijo del modificador.
    Ejemplo: "Espada Afilada"  →  "⚔ Afilado — Espada"
    """
    base_name = getattr(item, "name", getattr(item, "Name", "?"))
    mod = getattr(item, "modifier", None)
    if mod is None:
        return base_name
    prefix_color = "red" if mod.is_negative else "green"
    return f"[{prefix_color}]{mod.icon} {mod.name}[/{prefix_color}] — {base_name}"
