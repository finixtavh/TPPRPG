"""
GuildSkillTree.py
=================
Árbol de habilidades de Guild. Completamente independiente del árbol del jugador.
Moneda: guild_skill_points (por guild, no por jugador).

Ramas:
  Militar   (⚔)  — Combat power, mission slots, assault bonuses
  Economía  (🌾)  — Resource production, food efficiency, trade
  Diplomacia(🏛)  — Reputation gain, alliances, espionage
"""

from typing import Dict, List, Optional, Tuple

# ── Definiciones del árbol ────────────────────────────────────────────────────

GUILD_SKILL_TREE: Dict[str, dict] = {

    # ── RAMA MILITAR ──────────────────────────────────────────────────────────
    "mil_tactics": {
        "id":          "mil_tactics",
        "name":        "Tácticas Básicas",
        "branch":      "Militar",
        "icon":        "📜",
        "description": "Mejora la planificación de ataques. +10% en resolución de guerra.",
        "cost":        1,
        "requires":    [],
        "effect":      {"war_bonus": 0.10},
    },
    "mil_vanguard": {
        "id":          "mil_vanguard",
        "name":        "Vanguardia",
        "branch":      "Militar",
        "icon":        "🛡",
        "description": "Desbloquea 1 slot extra de misión autónoma para compañeros.",
        "cost":        2,
        "requires":    ["mil_tactics"],
        "effect":      {"mission_slots": 1},
    },
    "mil_assault": {
        "id":          "mil_assault",
        "name":        "Maestría de Asalto",
        "branch":      "Militar",
        "icon":        "⚔",
        "description": "+25% efectividad en misiones de tipo Asalto.",
        "cost":        3,
        "requires":    ["mil_vanguard"],
        "effect":      {"assault_bonus": 0.25},
    },
    "mil_professional": {
        "id":          "mil_professional",
        "name":        "Ejército Profesional",
        "branch":      "Militar",
        "icon":        "🎖",
        "description": "+40% poder militar base de la guild. La tropa élite llega.",
        "cost":        5,
        "requires":    ["mil_assault"],
        "effect":      {"military_power_bonus": 0.40},
    },
    "mil_logistics": {
        "id":          "mil_logistics",
        "name":        "Reclutamiento Eficiente",
        "branch":      "Militar",
        "icon":        "⛺",
        "description": "El ejército puede reclutar hasta un +5% de la población total.",
        "cost":        3,
        "requires":    ["mil_vanguard"],
        "effect":      {"recruit_pct_bonus": 0.05},
    },
    "mil_fortress": {
        "id":          "mil_fortress",
        "name":        "Fortaleza Permanente",
        "branch":      "Militar",
        "icon":        "🏰",
        "description": "+50 Defensa en todos tus territorios.",
        "cost":        4,
        "requires":    ["mil_assault"],
        "effect":      {"territory_defense_bonus": 50},
    },

    # ── RAMA ECONOMÍA ────────────────────────────────────────────────────────
    "eco_logistics": {
        "id":          "eco_logistics",
        "name":        "Logística",
        "branch":      "Economía",
        "icon":        "📦",
        "description": "+20% producción de todos los recursos por tick.",
        "cost":        1,
        "requires":    [],
        "effect":      {"resource_production": 0.20},
    },
    "eco_granaries": {
        "id":          "eco_granaries",
        "name":        "Graneros",
        "branch":      "Economía",
        "icon":        "🏚",
        "description": "La Comida alimenta el doble de población antes de agotarse.",
        "cost":        2,
        "requires":    ["eco_logistics"],
        "effect":      {"food_efficiency": 2.0},
    },
    "eco_trade": {
        "id":          "eco_trade",
        "name":        "Red Comercial",
        "branch":      "Economía",
        "icon":        "🪙",
        "description": "Desbloquea el comercio de recursos con otras guilds.",
        "cost":        3,
        "requires":    ["eco_granaries"],
        "effect":      {"trade_unlocked": True},
    },
    "eco_hegemony": {
        "id":          "eco_hegemony",
        "name":        "Hegemonía Económica",
        "branch":      "Economía",
        "icon":        "👑",
        "description": "Controlar un territorio produce +50% recursos adicionales.",
        "cost":        5,
        "requires":    ["eco_trade"],
        "effect":      {"territory_production_bonus": 0.50},
    },
    "eco_storage": {
        "id":          "eco_storage",
        "name":        "Almacenes Ampliados",
        "branch":      "Economía",
        "icon":        "🗃",
        "description": "Aumenta la capacidad de almacenamiento (+100 Común, +50 Poco Común).",
        "cost":        2,
        "requires":    ["eco_logistics"],
        "effect":      {"storage_bonus": {"Common": 100, "Uncommon": 50}},
    },
    "eco_population": {
        "id":          "eco_population",
        "name":        "Colonos",
        "branch":      "Economía",
        "icon":        "👨‍👩‍👧‍👦",
        "description": "+1% a la tasa de crecimiento poblacional por tick.",
        "cost":        3,
        "requires":    ["eco_granaries"],
        "effect":      {"population_growth_bonus": 0.01},
    },

    # ── RAMA DIPLOMACIA ───────────────────────────────────────────────────────
    "dip_ambassador": {
        "id":          "dip_ambassador",
        "name":        "Embajador",
        "branch":      "Diplomacia",
        "icon":        "🕊",
        "description": "+15% ganancia de reputación con todas las guilds.",
        "cost":        1,
        "requires":    [],
        "effect":      {"reputation_gain_bonus": 0.15},
    },
    "dip_alliances": {
        "id":          "dip_alliances",
        "name":        "Alianzas",
        "branch":      "Diplomacia",
        "icon":        "🤝",
        "description": "Permite formar alianzas formales con otras guilds.",
        "cost":        2,
        "requires":    ["dip_ambassador"],
        "effect":      {"alliances_unlocked": True},
    },
    "dip_espionage": {
        "id":          "dip_espionage",
        "name":        "Espionaje",
        "branch":      "Diplomacia",
        "icon":        "🕵",
        "description": "Permite ver las stats internas de guilds enemigas.",
        "cost":        3,
        "requires":    ["dip_alliances"],
        "effect":      {"espionage_unlocked": True},
    },
    "dip_hegemony": {
        "id":          "dip_hegemony",
        "name":        "Hegemonía Política",
        "branch":      "Diplomacia",
        "icon":        "🏛",
        "description": "Permite forzar acuerdos de paz con guilds rivales.",
        "cost":        5,
        "requires":    ["dip_espionage"],
        "effect":      {"peace_treaty_unlocked": True},
    },
}

BRANCH_ORDER = {
    "Militar":    ["mil_tactics", "mil_vanguard", "mil_logistics", "mil_assault", "mil_fortress", "mil_professional"],
    "Economía":   ["eco_logistics", "eco_storage", "eco_granaries", "eco_population", "eco_trade", "eco_hegemony"],
    "Diplomacia": ["dip_ambassador", "dip_alliances", "dip_espionage", "dip_hegemony"],
}

BRANCH_ICONS = {
    "Militar":    "⚔",
    "Economía":   "🌾",
    "Diplomacia": "🏛",
}


# ── Lógica de desbloqueo ──────────────────────────────────────────────────────

def can_unlock(skill_id: str, guild) -> Tuple[bool, str]:
    """
    Verifica si una guild puede desbloquear el nodo.
    Retorna (can, reason_string).
    """
    skill = GUILD_SKILL_TREE.get(skill_id)
    if not skill:
        return False, "Habilidad no encontrada."
    if skill_id in guild.unlocked_skills:
        return False, "Ya está desbloqueada."
    for req in skill["requires"]:
        if req not in guild.unlocked_skills:
            req_name = GUILD_SKILL_TREE.get(req, {}).get("name", req)
            return False, f"Requiere: {req_name}"
    if guild.skill_points < skill["cost"]:
        return False, f"Necesitas {skill['cost']} puntos (tienes {guild.skill_points})."
    return True, "OK"


def unlock_skill(skill_id: str, guild) -> Tuple[bool, str]:
    """Intenta desbloquear una habilidad. Retorna (success, message)."""
    ok, reason = can_unlock(skill_id, guild)
    if not ok:
        return False, reason
    skill = GUILD_SKILL_TREE[skill_id]
    guild.skill_points -= skill["cost"]
    guild.unlocked_skills.append(skill_id)
    return True, f"✓ '{skill['name']}' desbloqueada."


def get_effective_mission_slots(guild) -> int:
    """Calcula el número de slots de misión disponibles."""
    base = 1
    if "mil_vanguard" in guild.unlocked_skills:
        base += 1
    return base


def get_war_bonus(guild) -> float:
    """Calcula el bonus total de guerra del árbol."""
    bonus = 0.0
    if "mil_tactics" in guild.unlocked_skills:
        bonus += 0.10
    if "mil_professional" in guild.unlocked_skills:
        bonus += 0.40
    return bonus


def get_resource_bonus(guild) -> float:
    """Calcula el multiplicador total de producción de recursos."""
    mult = 1.0
    if "eco_logistics" in guild.unlocked_skills:
        mult += 0.20
    if "eco_hegemony" in guild.unlocked_skills:
        mult += 0.50
    return mult


def get_food_efficiency(guild) -> float:
    """Multiplicador de eficiencia de comida."""
    if "eco_granaries" in guild.unlocked_skills:
        return 2.0
    return 1.0


# ── UI de árbol de habilidades ────────────────────────────────────────────────

import os
import time
import threading
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

console_gs = Console()


def open_guild_skill_tree(guild, console=None):
    """UI completa del árbol de habilidades de guild con pestañas por rama."""
    if console is None:
        console = console_gs

    from Modules.input_utils import keyboard_listener_scope

    branches = list(BRANCH_ORDER.keys())
    state = {
        "branch_idx": 0,
        "skill_idx":  0,
        "exit":       False,
        "message":    f"Puntos disponibles: {guild.skill_points}",
        "msg_style":  "bold yellow",
    }

    def _current_skills():
        branch = branches[state["branch_idx"]]
        return BRANCH_ORDER[branch]

    def _render():
        branch_name = branches[state["branch_idx"]]
        branch_icon = BRANCH_ICONS[branch_name]
        skills      = _current_skills()

        # Pestañas
        tabs = Text()
        for i, br in enumerate(branches):
            bicon = BRANCH_ICONS[br]
            if i == state["branch_idx"]:
                tabs.append(f" {bicon} {br} ", style="bold black on bright_cyan")
            else:
                tabs.append(f" {bicon} {br} ", style="dim")
            if i < len(branches) - 1:
                tabs.append("  ")

        # Tabla de habilidades
        t = Table(show_header=False, box=box.SIMPLE, expand=True)
        t.add_column("Status", width=3)
        t.add_column("Icon",   width=3)
        t.add_column("Nombre", ratio=2)
        t.add_column("Costo",  width=8)
        t.add_column("Estado", ratio=1)

        for i, sid in enumerate(skills):
            skill    = GUILD_SKILL_TREE[sid]
            unlocked = sid in guild.unlocked_skills
            ok, reason = can_unlock(sid, guild)
            selected   = i == state["skill_idx"]

            status_icon = "✓" if unlocked else ("▶" if selected else " ")
            cost_str    = f"{skill['cost']}pt"

            if unlocked:
                row_style = "bold green"
                state_str = "[green]ACTIVA[/green]"
            elif selected:
                row_style = "bold bright_cyan"
                state_str = "[bold bright_cyan]← SELECCIONADA[/]"
            elif ok:
                row_style = "white"
                state_str = "[dim]Disponible[/]"
            else:
                row_style = "dim"
                state_str = f"[dim red]{reason}[/]"

            name_text = Text(skill["name"])
            if selected:
                name_text.stylize("bold reverse")

            t.add_row(status_icon, skill["icon"], name_text, cost_str, state_str, style=row_style)

        # Detalle de la habilidad seleccionada
        skills_list = _current_skills()
        if skills_list:
            sel_skill = GUILD_SKILL_TREE[skills_list[state["skill_idx"]]]
            unlocked  = skills_list[state["skill_idx"]] in guild.unlocked_skills
            ok, reason = can_unlock(skills_list[state["skill_idx"]], guild)
            detail = Text()
            detail.append(f"\n {sel_skill['icon']}  {sel_skill['name']}\n", style="bold cyan")
            detail.append(f" {sel_skill['description']}\n", style="italic")
            if unlocked:
                detail.append(" Estado: ACTIVA\n", style="bold green")
            elif ok:
                detail.append(f" [ENTER] para desbloquear por {sel_skill['cost']} puntos\n", style="bold yellow")
            else:
                detail.append(f" {reason}\n", style="red")
        else:
            detail = Text("Sin habilidades en esta rama.", style="dim")

        footer = Panel(
            Text(state["message"], style=state["msg_style"]),
            border_style="dim",
        )
        footer_hint = Text(
            "← →: Cambiar rama | ↑↓: Navegar | [ENTER]: Desbloquear | [ESC]: Volver",
            style="dim",
        )

        return Panel(
            Group(tabs, Rule(style="cyan"), t, Rule(style="dim"), detail, footer_hint, footer),
            title=f"[bold cyan]🌳 ÁRBOL DE HABILIDADES — {guild.name}[/]",
            subtitle=f"Puntos: {guild.skill_points}",
            border_style="cyan",
        )

    def _on_press(key):
        skills = _current_skills()
        if key == "left":
            state["branch_idx"] = (state["branch_idx"] - 1) % len(branches)
            state["skill_idx"]  = 0
        elif key == "right":
            state["branch_idx"] = (state["branch_idx"] + 1) % len(branches)
            state["skill_idx"]  = 0
        elif key == "up":
            state["skill_idx"] = max(0, state["skill_idx"] - 1)
        elif key == "down":
            state["skill_idx"] = min(len(skills) - 1, state["skill_idx"] + 1)
        elif key == "enter":
            if skills:
                sid = skills[state["skill_idx"]]
                success, msg = unlock_skill(sid, guild)
                state["message"]   = msg
                state["msg_style"] = "bold green" if success else "bold red"
        elif key == "esc":
            state["exit"] = True

    with console.screen():
        from Modules.input_utils import keyboard_listener_scope
        with keyboard_listener_scope():
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": False, "until": None},
                daemon=True,
            )
            kb_thread.start()
            try:
                with Live(console=console, refresh_per_second=20) as live:
                    while not state["exit"]:
                        live.update(_render())
                        time.sleep(0.05)
            finally:
                stop_listening()
                if kb_thread.is_alive():
                    kb_thread.join(timeout=0.2)
        console.clear()
