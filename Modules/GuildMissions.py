"""
GuildMissions.py
================
Sistema de misiones de Guild.

Tipos:
  Asalto      — Combate contra escuadrón enemigo por un territorio
  Defensa     — Defender territorio propio de un ataque
  Sabotaje    — Reducir stats de una guild enemiga
  Recolección — Obtener recursos específicos

Resolución autónoma:
  éxito_score = suma de (health_max * 0.5 + companion_class_bonus) vs difficulty * 15
  Si los compañeros regresan, pasan a estado "inactive" (fuera del grupo).
"""

import os
import random
import time
import threading
from typing import List, Optional, Dict, Tuple

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

from Modules.GuildSystem import Guild, GuildManager, get_guild_manager
from Modules.GuildSkillTree import get_effective_mission_slots

console_gm = Console()

# ── Clase de Misión ───────────────────────────────────────────────────────────

MISSION_TYPES = {
    "asalto": {
        "name":        "Asalto",
        "icon":        "⚔",
        "color":       "bold red",
        "description": "Ataca una posición enemiga. Alto riesgo, alta recompensa.",
        "base_diff":   50,
    },
    "defensa": {
        "name":        "Defensa",
        "icon":        "🛡",
        "color":       "bold cyan",
        "description": "Defiende un territorio propio de un ataque inminente.",
        "base_diff":   35,
    },
    "sabotaje": {
        "name":        "Sabotaje",
        "icon":        "🗡",
        "color":       "bold magenta",
        "description": "Reduce el poder militar de una guild rival.",
        "base_diff":   45,
    },
    "recoleccion": {
        "name":        "Recolección",
        "icon":        "📦",
        "color":       "bold yellow",
        "description": "Consigue recursos estratégicos para la guild.",
        "base_diff":   20,
    },
}

# Bonus de clase para misiones
CLASS_MISSION_BONUS = {
    "Daño":       {"asalto": 0.3,  "defensa": 0.0,  "sabotaje": 0.1,  "recoleccion": 0.0},
    "Tanque":     {"asalto": 0.1,  "defensa": 0.4,  "sabotaje": 0.0,  "recoleccion": 0.0},
    "Soporte":    {"asalto": 0.0,  "defensa": 0.2,  "sabotaje": 0.0,  "recoleccion": 0.2},
    "Explorador": {"asalto": 0.1,  "defensa": 0.1,  "sabotaje": 0.3,  "recoleccion": 0.4},
    "Mago":       {"asalto": 0.2,  "defensa": 0.1,  "sabotaje": 0.2,  "recoleccion": 0.1},
}


class GuildMission:
    def __init__(
        self,
        mission_id:   str,
        mission_type: str,
        name:         str,
        description:  str,
        difficulty:   int,         # 1–10
        duration_combats: int,     # Cuántos combates del jugador hasta que acaba
        reward_resources: Dict[str, int],
        reward_skill_pts: int     = 0,
        target_guild_id:  str     = "",
        target_territory: str     = "",
    ):
        self.mission_id          = mission_id
        self.mission_type        = mission_type
        self.name                = name
        self.description         = description
        self.difficulty          = difficulty
        self.duration_combats    = duration_combats
        self.reward_resources    = reward_resources
        self.reward_skill_pts    = reward_skill_pts
        self.target_guild_id     = target_guild_id
        self.target_territory    = target_territory

        # Estado de ejecución
        self.assigned_companions: List[str] = []  # companion_ids
        self.started_at_combat:   int = 0          # nº de combate al que empezó
        self.is_active:           bool = False
        self.result:              Optional[str] = None  # "success" | "failure"
        self.result_message:      str = ""

    def to_dict(self) -> dict:
        return {
            "mission_id":          self.mission_id,
            "mission_type":        self.mission_type,
            "name":                self.name,
            "description":         self.description,
            "difficulty":          self.difficulty,
            "duration_combats":    self.duration_combats,
            "reward_resources":    self.reward_resources,
            "reward_skill_pts":    self.reward_skill_pts,
            "target_guild_id":     self.target_guild_id,
            "target_territory":    self.target_territory,
            "assigned_companions": list(self.assigned_companions),
            "started_at_combat":   self.started_at_combat,
            "is_active":           self.is_active,
            "result":              self.result,
            "result_message":      self.result_message,
        }

    @staticmethod
    def from_dict(data: dict) -> "GuildMission":
        m = GuildMission(
            mission_id        = data["mission_id"],
            mission_type      = data["mission_type"],
            name              = data["name"],
            description       = data["description"],
            difficulty        = data["difficulty"],
            duration_combats  = data["duration_combats"],
            reward_resources  = data.get("reward_resources", {}),
            reward_skill_pts  = data.get("reward_skill_pts", 0),
            target_guild_id   = data.get("target_guild_id", ""),
            target_territory  = data.get("target_territory", ""),
        )
        m.assigned_companions = data.get("assigned_companions", [])
        m.started_at_combat   = data.get("started_at_combat", 0)
        m.is_active           = data.get("is_active", False)
        m.result              = data.get("result")
        m.result_message      = data.get("result_message", "")
        return m


# ── Generación de misiones ────────────────────────────────────────────────────

def generate_missions_for_guild(guild: Guild, guild_manager: GuildManager) -> List[GuildMission]:
    """Genera 4 misiones aleatorias disponibles para la guild."""
    missions = []
    gm       = guild_manager
    res_defs = gm.resource_defs

    # Misión de recolección
    resource_ids = list(res_defs.keys())
    target_rid   = random.choice(resource_ids)
    amount       = random.randint(10, 50)
    missions.append(GuildMission(
        mission_id        = "m_recoleccion",
        mission_type      = "recoleccion",
        name              = f"Expedición de Recursos",
        description       = f"Consigue {amount}x {res_defs[target_rid]['name']} para las reservas de la guild.",
        difficulty        = random.randint(1, 4),
        duration_combats  = random.randint(3, 6),
        reward_resources  = {target_rid: amount},
        reward_skill_pts  = 1,
    ))

    # Misión de asalto (si hay territorios neutrales o enemigos)
    neutral = [t for t in gm.territories.values() if t.owner != guild.guild_id]
    if neutral:
        target = random.choice(neutral)
        missions.append(GuildMission(
            mission_id        = "m_asalto",
            mission_type      = "asalto",
            name              = f"Asalto a {target.name}",
            description       = f"Toma el control de {target.icon} {target.name} por la fuerza.",
            difficulty        = target.difficulty,
            duration_combats  = random.randint(4, 8),
            reward_resources  = dict(list(target.resource_output.items())[:2]),
            reward_skill_pts  = 2,
            target_territory  = target.id,
        ))

    # Misión de defensa (si la guild tiene territorios)
    if guild.territories:
        tid       = random.choice(guild.territories)
        territory = gm.territories.get(tid)
        if territory:
            missions.append(GuildMission(
                mission_id        = "m_defensa",
                mission_type      = "defensa",
                name              = f"Defender {territory.name}",
                description       = f"Mantén el control de {territory.icon} {territory.name} ante el ataque enemigo.",
                difficulty        = random.randint(2, 6),
                duration_combats  = random.randint(2, 5),
                reward_resources  = {"lingote_xar": random.randint(5, 15)},
                reward_skill_pts  = 1,
                target_territory  = tid,
            ))

    # Misión de sabotaje
    enemy_guilds = [
        g for gid, g in gm.guilds.items()
        if gid != guild.guild_id and guild.relations.get(gid, 0) < 20
    ]
    if enemy_guilds:
        target_g = random.choice(enemy_guilds)
        missions.append(GuildMission(
            mission_id        = "m_sabotaje",
            mission_type      = "sabotaje",
            name              = f"Sabotaje a {target_g.name}",
            description       = f"Infiltra agentes en {target_g.icon} {target_g.name} y reduce su capacidad militar.",
            difficulty        = random.randint(4, 7),
            duration_combats  = random.randint(5, 9),
            reward_resources  = {"cuero_endurecido": random.randint(8, 20)},
            reward_skill_pts  = 2,
            target_guild_id   = target_g.guild_id,
        ))

    return missions


# ── Resolución autónoma ───────────────────────────────────────────────────────

def resolve_autonomous_mission(
    mission:     GuildMission,
    companions:  list,
    guild:       Guild,
) -> Tuple[bool, str, Dict[str, int]]:
    """
    Calcula el resultado de una misión sin el jugador.
    Devuelve (success, narrative_message, rewards_dict).
    """
    if not companions:
        return False, "La misión falló: no había compañeros asignados.", {}

    # Calcular poder del squad
    squad_power = 0.0
    for comp in companions:
        base     = getattr(comp, "Health_max", 80) * 0.5
        c_class  = getattr(comp, "c_class", "Daño")
        m_type   = mission.mission_type
        bonus    = CLASS_MISSION_BONUS.get(c_class, {}).get(m_type, 0.0)
        squad_power += base * (1.0 + bonus)

    # Bonus del árbol de habilidades
    if mission.mission_type == "asalto" and "mil_assault" in guild.unlocked_skills:
        squad_power *= 1.25

    # Dificultad de la misión
    difficulty_threshold = mission.difficulty * 12 + random.randint(-10, 20)

    success = squad_power >= difficulty_threshold

    if success:
        rewards    = dict(mission.reward_resources)
        skill_pts  = mission.reward_skill_pts
        guild.skill_points += skill_pts
        comp_names = ", ".join(
            getattr(c, "generated_name", None) or getattr(c, "name", "?")
            for c in companions
        )
        msg = (
            f"✓ [{mission.mission_type.upper()}] '{mission.name}' completada. "
            f"Squad: {comp_names}. +{skill_pts} pt."
        )
        guild.log_event(msg)
        guild.change_moral(5)
    else:
        rewards = {}
        comp_names = ", ".join(
            getattr(c, "generated_name", None) or getattr(c, "name", "?")
            for c in companions
        )
        msg = (
            f"✗ [{mission.mission_type.upper()}] '{mission.name}' falló. "
            f"Squad: {comp_names}."
        )
        guild.log_event(msg)
        guild.change_moral(-5)
        
        # Pérdida de soldados en misiones de asalto o sabotaje fallidas
        if mission.mission_type in ["asalto", "sabotaje"]:
            import random
            soldier_loss = random.randint(1, max(1, mission.difficulty // 2))
            guild.soldiers = max(0, getattr(guild, 'soldiers', 0) - soldier_loss)
            guild.population = max(10, getattr(guild, 'population', 10) - soldier_loss)
            guild.log_event(f"✗ Perdimos {soldier_loss} soldados en la misión.")

    return success, msg, rewards


def check_mission_completion(
    mission:        GuildMission,
    current_combat: int,
    companions:     list,
    guild:          Guild,
    guild_manager:  GuildManager,
) -> Optional[Tuple[bool, str, Dict[str, int]]]:
    """
    Verifica si una misión activa ha completado su duración.
    Si sí, resuelve y devuelve (success, msg, rewards). Si no, devuelve None.
    """
    if not mission.is_active:
        return None
    if current_combat < mission.started_at_combat + mission.duration_combats:
        return None

    result = resolve_autonomous_mission(mission, companions, guild)
    mission.is_active = False
    mission.result    = "success" if result[0] else "failure"
    mission.result_message = result[1]

    # Asignar recursos de recompensa
    success, msg, rewards = result
    if success:
        for rid, amt in rewards.items():
            guild.add_resource(rid, amt, guild_manager.resource_defs)

    # Poner compañeros en estado "inactive"
    for comp in companions:
        comp.mission_status = "inactive"

    return result


# ── UI de Misiones ────────────────────────────────────────────────────────────

def open_guild_missions_menu(guild: Guild, player, guild_manager: GuildManager, console=None):
    """Menú de misiones de guild con navegación de teclado."""
    if console is None:
        console = console_gm

    from Modules.input_utils import keyboard_listener_scope

    # Generar misiones disponibles
    available_missions = generate_missions_for_guild(guild, guild_manager)
    max_slots = get_effective_mission_slots(guild)

    # Misiones activas del jugador (guardadas en guild)
    if not hasattr(guild, "active_missions"):
        guild.active_missions = []

    state = {
        "idx":     0,
        "mode":    "list",   # list | assign
        "exit":    False,
        "message": f"Slots de misión: {len(guild.active_missions)}/{max_slots}",
        "msg_style": "dim",
    }

    # Compañeros disponibles (no en misión)
    available_companions = [
        c for c in player.companion
        if getattr(c, "mission_status", "available") == "available"
    ]

    def _render():
        if state["mode"] == "list":
            t = Table(show_header=True, box=box.SIMPLE, expand=True)
            t.add_column("",         width=3)   # selector
            t.add_column("",         width=3)   # icono de tipo
            t.add_column("Tipo",     width=14)  # nombre del tipo (sin icono → cabe)
            t.add_column("Nombre",   ratio=2)
            t.add_column("Dif",      width=4)
            t.add_column("Duración", width=12)

            for i, m in enumerate(available_missions):
                mtype    = MISSION_TYPES.get(m.mission_type, {})
                selected = i == state["idx"]
                icon     = mtype.get("icon", "?")
                mname    = Text(m.name)
                if selected:
                    mname.stylize("bold reverse")
                t.add_row(
                    "▶" if selected else " ",
                    icon,
                    mtype.get("name", m.mission_type),
                    mname,
                    str(m.difficulty),
                    f"{m.duration_combats} combates",
                    style=mtype.get("color", "white") if selected else "white",
                )

            # Detalle de la misión seleccionada
            sel = available_missions[state["idx"]] if available_missions else None
            if sel:
                mtype  = MISSION_TYPES.get(sel.mission_type, {})
                detail = Text()
                detail.append(f"\n {mtype.get('icon','?')}  {sel.name}\n", style="bold cyan")
                detail.append(f" {sel.description}\n", style="italic")
                detail.append(f"\n Recompensas: ", style="bold white")
                for rid, amt in sel.reward_resources.items():
                    rdef = guild_manager.resource_defs.get(rid, {})
                    detail.append(f"{rdef.get('icon','?')} {rdef.get('name', rid)}: {amt}  ", style="yellow")
                detail.append(f"\n Puntos de Guild: +{sel.reward_skill_pts}\n", style="green")
                detail.append(f"\n Compañeros disponibles: {len(available_companions)}\n", style="dim")
                detail.append(f" [ENTER] Asignar compañeros | [ESC] Volver\n", style="dim")
            else:
                detail = Text("No hay misiones disponibles.", style="dim")

            footer = Panel(Text(state["message"], style=state["msg_style"]), border_style="dim")
            return Panel(
                Group(t, Rule(style="dim"), detail, footer),
                title="[bold yellow]📋 MISIONES DE GUILD[/]",
                subtitle=f"[{guild.icon} {guild.name}] — {len(guild.active_missions)}/{max_slots} slots activos",
                border_style="yellow",
            )
        return Panel(Text("...", style="dim"))

    def _on_press(key):
        if key == "up":
            state["idx"] = max(0, state["idx"] - 1)
        elif key == "down":
            state["idx"] = min(len(available_missions) - 1, state["idx"] + 1)
        elif key == "enter" and available_missions:
            mission = available_missions[state["idx"]]
            if len(guild.active_missions) >= max_slots:
                state["message"]   = "✗ No hay slots de misión disponibles."
                state["msg_style"] = "bold red"
                return
            if not available_companions:
                state["message"]   = "✗ No hay compañeros disponibles para enviar."
                state["msg_style"] = "bold red"
                return
            # Asignar el primer compañero disponible
            comp = available_companions.pop(0)
            comp.mission_status = "on_mission"
            comp.mission_return_combat = getattr(player, "combat_counter", 0) + mission.duration_combats
            mission.assigned_companions = [comp.companion_id]
            mission.started_at_combat   = getattr(player, "combat_counter", 0)
            mission.is_active           = True
            guild.active_missions.append(mission.to_dict())
            available_missions.pop(state["idx"])
            state["idx"]     = max(0, state["idx"] - 1)
            state["message"] = f"✓ '{mission.name}' iniciada. {getattr(comp, 'generated_name', comp.name)} ha partido."
            state["msg_style"] = "bold green"
        elif key == "esc":
            state["exit"] = True

    with console.screen():
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
