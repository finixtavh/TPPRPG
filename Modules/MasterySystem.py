"""
MasterySystem.py
================
Sistema de Mastery para Armas y Armaduras.

Mecánica:
    - Mastery de Armas: sube cuando el jugador hace daño.
      EXP ganada = daño_hecho / 35
    - Mastery de Armaduras: sube cuando el jugador recibe daño.
      EXP ganada = daño_recibido / 35

    Cada tipo tiene su propio pool de EXP y nivel (1-20).

Tipos de Mastery de Armas (según categoría en DataItems.json):
    "Swords", "Staffs", "Hammers", "Spears", "Daggers", "Bows"

Tipos de Mastery de Armaduras (según objectcheck del item):
    "Helmet", "Armor", "Boots", "Ring"

Bonus por nivel:
    - Armas:   +0.5% de daño por nivel (acumulativo).
    - Armaduras: +0.25% de reducción de daño por nivel (acumulativo).

EXP para siguiente nivel: 100 * (1.5 ^ (nivel_actual - 1))
Nivel máximo: 20
"""

import math
from typing import Dict, Optional


# ── Constantes ────────────────────────────────────────────────────────────────

MASTERY_MAX_LEVEL: int = 20
MASTERY_EXP_BASE: float = 100.0
MASTERY_EXP_GROWTH: float = 1.5      # multiplicador por nivel

WEAPON_BONUS_PER_LEVEL: float = 0.5  # % de daño extra por nivel
ARMOR_BONUS_PER_LEVEL: float = 0.25  # % de reducción de daño por nivel

# Tipos de arma reconocidos (equivalentes a las keys TYPE: de DataItems.json sin el "TYPE:" prefijo)
WEAPON_TYPES = ["Swords", "Staffs", "Hammers", "Spears", "Daggers", "Bows", "Generic"]

# Tipos de armadura (objectcheck en cEquippableItems)
ARMOR_TYPES = ["Helmet", "Armor", "Boots", "Ring"]


# ── Clase de Skill ─────────────────────────────────────────────────────────────

class MasterySkill:
    """Representa un nivel de mastery para un tipo de arma o armadura."""

    def __init__(self, name: str, skill_type: str):
        self.name = name          # nombre legible (ej: "Espadas", "Armadura")
        self.skill_type = skill_type  # "weapon" o "armor"
        self.current_level: int = 1
        self.exp_current: float = 0.0
        self.exp_to_next: float = MASTERY_EXP_BASE

    def add_exp(self, amount: float) -> int:
        """
        Agrega EXP al mastery. Retorna cuántos niveles subió (0 si ninguno).
        No sube más allá de MASTERY_MAX_LEVEL.
        """
        if self.current_level >= MASTERY_MAX_LEVEL:
            return 0

        self.exp_current += amount
        levels_gained = 0

        while self.exp_current >= self.exp_to_next and self.current_level < MASTERY_MAX_LEVEL:
            self.exp_current -= self.exp_to_next
            self.current_level += 1
            levels_gained += 1
            self.exp_to_next = MASTERY_EXP_BASE * (MASTERY_EXP_GROWTH ** (self.current_level - 1))

        if self.current_level >= MASTERY_MAX_LEVEL:
            self.exp_current = 0.0

        return levels_gained

    @property
    def bonus_percent(self) -> float:
        """Retorna el bonus total en porcentaje según el nivel actual."""
        if self.skill_type == "weapon":
            return (self.current_level - 1) * WEAPON_BONUS_PER_LEVEL
        else:
            return (self.current_level - 1) * ARMOR_BONUS_PER_LEVEL

    @property
    def bonus_multiplier(self) -> float:
        """Retorna el multiplicador de daño/reducción (1.0 = sin bonus)."""
        return 1.0 + self.bonus_percent / 100.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "skill_type": self.skill_type,
            "current_level": self.current_level,
            "exp_current": self.exp_current,
            "exp_to_next": self.exp_to_next,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MasterySkill":
        skill = cls(data["name"], data["skill_type"])
        skill.current_level = data.get("current_level", 1)
        skill.exp_current = data.get("exp_current", 0.0)
        skill.exp_to_next = data.get("exp_to_next", MASTERY_EXP_BASE)
        return skill

    def __repr__(self):
        return (
            f"<MasterySkill '{self.name}' Nv{self.current_level}/{MASTERY_MAX_LEVEL} "
            f"EXP:{self.exp_current:.1f}/{self.exp_to_next:.1f} (+{self.bonus_percent:.1f}%)>"
        )


# ── Gestor principal ───────────────────────────────────────────────────────────

class MasteryManager:
    """
    Gestiona todos los masteries de un jugador.
    Se instancia una vez y se guarda en player.mastery_manager.
    """

    # Nombres legibles para mostrar en UI
    WEAPON_NAMES = {
        "Swords":  "Espadas",
        "Staffs":  "Bastones",
        "Hammers": "Martillos",
        "Spears":  "Lanzas",
        "Daggers": "Dagas",
        "Bows":    "Arcos",
        "Generic": "Armas Genéricas",
    }
    ARMOR_NAMES = {
        "Helmet": "Cascos",
        "Armor":  "Armaduras",
        "Boots":  "Botas",
        "Ring":   "Anillos",
    }

    def __init__(self):
        # Weapon masteries
        self.weapon_masteries: Dict[str, MasterySkill] = {
            wt: MasterySkill(self.WEAPON_NAMES[wt], "weapon")
            for wt in WEAPON_TYPES
        }
        # Armor masteries
        self.armor_masteries: Dict[str, MasterySkill] = {
            at: MasterySkill(self.ARMOR_NAMES[at], "armor")
            for at in ARMOR_TYPES
        }

    # ── Obtener tipo de arma ──────────────────────────────────────────────────

    @staticmethod
    def get_weapon_type(weapon) -> str:
        """
        Determina el tipo de mastery de un arma.
        Busca en el atributo 'item_category' (inyectado por ItemManager),
        o cae a 'Generic'.
        """
        if weapon is None:
            return "Generic"

        # ItemManager inyecta 'item_category' = "TYPE:Swords", etc.
        raw = getattr(weapon, "item_category", "") or getattr(weapon, "category", "")
        if raw:
            # Quitar el prefijo "TYPE:"
            raw = raw.replace("TYPE:", "")
            if raw in WEAPON_TYPES:
                return raw

        # Intentar inferir del nombre del arma
        name_lower = (getattr(weapon, "name", "") or getattr(weapon, "Name", "")).lower()
        if any(k in name_lower for k in ["spada", "espada", "sword", "sable"]):
            return "Swords"
        if any(k in name_lower for k in ["bastón", "baston", "staff", "vara", "cetro"]):
            return "Staffs"
        if any(k in name_lower for k in ["martillo", "hammer", "mazo"]):
            return "Hammers"
        if any(k in name_lower for k in ["lanza", "spear", "pica"]):
            return "Spears"
        if any(k in name_lower for k in ["daga", "dagger", "cuchillo"]):
            return "Daggers"
        if any(k in name_lower for k in ["arco", "bow"]):
            return "Bows"

        return "Generic"

    # ── Registrar daño hecho (arma) ───────────────────────────────────────────

    def register_damage_dealt(self, player, damage_total: float) -> Optional[str]:
        """
        Llama cuando el jugador hace daño. Agrega EXP al mastery del arma equipada.
        Retorna un mensaje de level-up si subió, None si no.
        """
        if damage_total <= 0:
            return None

        weapon_type = self.get_weapon_type(getattr(player, "weapon", None))
        skill = self.weapon_masteries.get(weapon_type)
        if skill is None:
            return None

        exp_gain = damage_total / 35.0
        levels_up = skill.add_exp(exp_gain)

        if levels_up > 0:
            return (
                f"⚔️  Mastery de {skill.name} subió a Nv.{skill.current_level}! "
                f"(+{skill.bonus_percent:.1f}% daño)"
            )
        return None

    # ── Registrar daño recibido (armadura) ────────────────────────────────────

    def register_damage_received(self, player, damage_total: float) -> Optional[str]:
        """
        Llama cuando el jugador recibe daño. Agrega EXP a TODOS los masteries
        de armadura que tenga equipados.
        Retorna mensajes de level-up concatenados, o None.
        """
        if damage_total <= 0:
            return None

        exp_gain = damage_total / 35.0
        messages = []

        armor_slot_map = {
            "helmet": "Helmet",
            "armor":  "Armor",
            "boots":  "Boots",
            "ring":   "Ring",
            "ring2":  "Ring",
            "ring3":  "Ring",
        }

        seen = set()
        for slot, armor_type in armor_slot_map.items():
            item = getattr(player, slot, None)
            if item is not None and armor_type not in seen:
                seen.add(armor_type)
                skill = self.armor_masteries.get(armor_type)
                if skill:
                    levels_up = skill.add_exp(exp_gain)
                    if levels_up > 0:
                        messages.append(
                            f"🛡️  Mastery de {skill.name} subió a Nv.{skill.current_level}! "
                            f"(+{skill.bonus_percent:.1f}% reducción)"
                        )

        return "\n".join(messages) if messages else None

    # ── Bonus de daño del jugador ─────────────────────────────────────────────

    def get_weapon_damage_multiplier(self, player) -> float:
        """
        Retorna el multiplicador de daño basado en el mastery del arma equipada.
        1.0 = sin bonus.
        """
        weapon_type = self.get_weapon_type(getattr(player, "weapon", None))
        skill = self.weapon_masteries.get(weapon_type)
        return skill.bonus_multiplier if skill else 1.0

    # ── Bonus de reducción de armadura ────────────────────────────────────────

    def get_armor_damage_reduction_bonus(self, player, slot: str) -> float:
        """
        Retorna % extra de reducción para una slot de armadura específica.
        Valor 0.0 a 1.0 (ya en decimales, listo para multiplicar).
        """
        armor_slot_map = {
            "helmet": "Helmet",
            "armor":  "Armor",
            "boots":  "Boots",
            "ring":   "Ring",
            "ring2":  "Ring",
            "ring3":  "Ring",
        }
        armor_type = armor_slot_map.get(slot)
        if not armor_type:
            return 0.0
        skill = self.armor_masteries.get(armor_type)
        if not skill:
            return 0.0
        return skill.bonus_percent / 100.0

    def get_total_armor_reduction_bonus(self, player) -> float:
        """Retorna el promedio de bonus de todas las armaduras equipadas (0.0-1.0)."""
        slots = ["helmet", "armor", "boots", "ring", "ring2", "ring3"]
        bonuses = []
        seen_types = set()
        armor_slot_map = {"helmet": "Helmet", "armor": "Armor",
                          "boots": "Boots", "ring": "Ring",
                          "ring2": "Ring", "ring3": "Ring"}
        for slot in slots:
            item = getattr(player, slot, None)
            armor_type = armor_slot_map.get(slot)
            if item is not None and armor_type not in seen_types:
                seen_types.add(armor_type)
                bonuses.append(self.get_armor_damage_reduction_bonus(player, slot))
        return sum(bonuses) / len(bonuses) if bonuses else 0.0

    # ── Serialización ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "weapon_masteries": {k: v.to_dict() for k, v in self.weapon_masteries.items()},
            "armor_masteries":  {k: v.to_dict() for k, v in self.armor_masteries.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MasteryManager":
        mgr = cls()
        for k, v in data.get("weapon_masteries", {}).items():
            if k in mgr.weapon_masteries:
                mgr.weapon_masteries[k] = MasterySkill.from_dict(v)
        for k, v in data.get("armor_masteries", {}).items():
            if k in mgr.armor_masteries:
                mgr.armor_masteries[k] = MasterySkill.from_dict(v)
        return mgr

    # ── UI ────────────────────────────────────────────────────────────────────

    def display_masteries(self, console) -> None:
        """Muestra todos los masteries en consola con Rich."""
        from rich.table import Table
        from rich.panel import Panel

        t = Table(title="Sistema de Mastery", show_header=True)
        t.add_column("Tipo", style="bold")
        t.add_column("Categoría", style="cyan")
        t.add_column("Nivel", justify="center", style="yellow")
        t.add_column("EXP", justify="right")
        t.add_column("Bonus", justify="right", style="green")

        for wt, skill in self.weapon_masteries.items():
            bar_len = 15
            filled = int(bar_len * skill.exp_current / max(skill.exp_to_next, 1))
            bar = "█" * filled + "░" * (bar_len - filled)
            t.add_row(
                "⚔️ Arma",
                skill.name,
                f"{skill.current_level}/{MASTERY_MAX_LEVEL}",
                f"{bar} {skill.exp_current:.1f}/{skill.exp_to_next:.1f}",
                f"+{skill.bonus_percent:.1f}%",
            )

        for at, skill in self.armor_masteries.items():
            bar_len = 15
            filled = int(bar_len * skill.exp_current / max(skill.exp_to_next, 1))
            bar = "█" * filled + "░" * (bar_len - filled)
            t.add_row(
                "🛡️ Armadura",
                skill.name,
                f"{skill.current_level}/{MASTERY_MAX_LEVEL}",
                f"{bar} {skill.exp_current:.1f}/{skill.exp_to_next:.1f}",
                f"+{skill.bonus_percent:.1f}%",
            )

        console.print(Panel(t, border_style="cyan"))


# ── Helper para inicializar en player ─────────────────────────────────────────

def ensure_mastery(player) -> MasteryManager:
    """
    Garantiza que player.mastery_manager exista.
    Llama esta función antes de usar el mastery.
    """
    if not hasattr(player, "mastery_manager") or player.mastery_manager is None:
        player.mastery_manager = MasteryManager()
    return player.mastery_manager
