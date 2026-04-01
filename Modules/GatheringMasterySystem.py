import time
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from pathlib import Path

from Modules.Loader import Read

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

from Modules.input_utils import keyboard_listener_scope

class cSkill:
    exp_total: float = 0.0
    exp_to_next_lvl: float = 100.0
    current_level: int = 1

class cFarm:
    ruta = Path(__file__).parent.parent / "config.json"

    ZONE_BONUS = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("ZONE_BONUS")
    TICK_INTERVAL = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("TICK_INTERVAL")
    MARKER_SPEED = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("MARKER_SPEED")
    ZONE_WIDTH_MIN = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("ZONE_WIDTH_MIN")
    ZONE_WIDTH_MAX = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("ZONE_WIDTH_MAX")
    ZONE_RESPAWN_TICKS = Read(ruta, "GATHERING_MINIGAME_PARAMS").get("ZONE_RESPAWN_TICKS")


    GATHERING_SKILLS = ["mining", "woodcutting", "fishing", "herbalism", "skinning", "astrology"]

    WEAPON_SKILLS = ["swords", "electric_wands", "thermal_wands", "earth_wands", 
                     "void_staffs", "shields", "blessed_ornament", "ornament", "cursed_ornament"]

    def __init__(self):
        self.gathering: Dict[str, cSkill] = {skill: cSkill() for skill in self.GATHERING_SKILLS}
        self.weapons: Dict[str, cSkill] = {skill: cSkill() for skill in self.WEAPON_SKILLS}
    def _build_display(
        self,
        progress: float,       # 0.0 – 1.0
        marker: float,         # 0.0 – 1.0
        zone_start: float,     # 0.0 – 1.0
        zone_width: float,
        remaining: float,
        total_time: float,
        last_msg: str,
        msg_color: str,
        material_name: str,
        power: float,
    ) -> Panel:

        BAR_WIDTH = 50  # caracteres de ancho de la barra

        # ── barra de progreso ──────────────────
        filled = int(progress * BAR_WIDTH)
        prog_bar = Text()
        prog_bar.append("█" * filled, style="bold blue")
        prog_bar.append("░" * (BAR_WIDTH - filled), style="dim")

        # ── barra del minijuego (zona + marcador) ──
        zone_l = int(zone_start * BAR_WIDTH)
        zone_r = int((zone_start + zone_width) * BAR_WIDTH)
        marker_pos = int(marker * BAR_WIDTH)
        marker_pos = max(0, min(BAR_WIDTH - 1, marker_pos))

        mini_chars: list[str] = []
        mini_styles: list[str] = []
        for i in range(BAR_WIDTH):
            in_zone = zone_l <= i <= zone_r
            is_marker = (i == marker_pos)

            if is_marker:
                mini_chars.append("▼")
                mini_styles.append("bold white on green" if in_zone else "bold white on dark_orange3")
            elif in_zone:
                mini_chars.append("░")
                mini_styles.append("bold green")
            else:
                mini_chars.append("─")
                mini_styles.append("dim")

        mini_bar = Text()
        for ch, st in zip(mini_chars, mini_styles):
            mini_bar.append(ch, style=st)

        # ── tiempo restante ────────────────────
        elapsed = total_time - remaining
        pct = (elapsed / total_time * 100) if total_time > 0 else 100
        time_line = Text()
        time_line.append(f"⏱  {remaining:.1f}s restantes", style="bold")
        time_line.append(f"  ({pct:.0f}% completado)", style="dim")

        # ── mensaje de feedback ────────────────
        fb = Text(last_msg, style=msg_color)

        # ── tabla contenedora ─────────────────
        table = Table.grid(padding=(0, 0, 0, 0))
        table.add_column(no_wrap=True)

        table.add_row(Text(f"Recolectando: {material_name}", style="bold cyan"))
        table.add_row(Text(f"Poder: {power:.2f}  |  Bonus zona: {self.ZONE_BONUS*100:.0f}%", style="dim"))
        table.add_row(Text(""))
        table.add_row(Text("Progreso:", style="dim"))
        table.add_row(prog_bar)
        table.add_row(Text(""))
        table.add_row(Text("Zona verde  (pulsa ESPACIO cuando el marcador ▼ esté en verde):", style="dim"))
        table.add_row(mini_bar)
        table.add_row(Text(""))
        table.add_row(time_line)
        table.add_row(fb)

        return Panel(table, title="[bold]Minijuego de recolección[/bold]", box=box.ROUNDED)

    def gather(
        self,
        material: cMaterial,
        tool: Optional[cTool],
        buffs: Optional[List[float]] = None,
    ) -> bool:
        if buffs is None:
            buffs = []

        # cMaterial ya normaliza y valida SkillName en su constructor,
        # por lo que skill_key siempre está en forma canónica.
        skill_key = material.SkillName
        if skill_key not in self.gathering:
            raise ValueError(f"Skill desconocida: {skill_key!r}")

        # ── Verificar nivel mínimo requerido (integración cMaterial ↔ cSkill) ──
        if not material.can_be_gathered_by(self, skill_key):
            current_lvl = self.gathering[skill_key].current_level
            raise PermissionError(
                f"Nivel insuficiente para recolectar '{material.Name}'. "
                f"Requiere nivel {material.Level_Req} en {skill_key} "
                f"(nivel actual: {current_lvl})."
            )

        Gathering_Skill_Bonus = 1 + (self.gathering[skill_key].current_level * 0.05)
        total_modifier = 1.0
        for b in buffs:
            total_modifier *= b

        tool_eff = tool.Efficiency if tool else 1.0
        power = tool_eff * Gathering_Skill_Bonus * total_modifier

        # Tiempo total basado en Hardness / power (segundos)
        # Cada "tick" equivale a TICK_INTERVAL seg; avanzamos `power` por tick
        # escalado para que Hardness/power ~ segundos reales.
        total_time: float = material.Hardness / power   # segundos reales

        # ── estado del minijuego ──────────────
        state = {
            "elapsed": 0.0,
            "marker": 0.0,
            "marker_dir": 1,
            "zone_start": random.uniform(0.05, 0.60),
            "zone_width": random.uniform(self.ZONE_WIDTH_MIN, self.ZONE_WIDTH_MAX),
            "zone_ticks": 0,
            "last_msg": "Pulsa ESPACIO cuando el marcador esté en verde",
            "msg_color": "dim",
            "space_pressed": False,
            "done": False,
        }

        console = Console()

        def on_press(key: str):
            if key == "space" and not state["done"]:
                state["space_pressed"] = True

        kb_thread = None
        with keyboard_listener_scope():
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": on_press, "sequential": True, "delay_second_char": 0.05},
                daemon=True,
            )
            kb_thread.start()

            with Live(console=console, refresh_per_second=int(1 / self.TICK_INTERVAL)) as live:
                while state["elapsed"] < total_time:
                    # ── mover marcador ────────────
                    state["marker"] += state["marker_dir"] * self.MARKER_SPEED
                    if state["marker"] >= 1.0:
                        state["marker"] = 1.0
                        state["marker_dir"] = -1
                    elif state["marker"] <= 0.0:
                        state["marker"] = 0.0
                        state["marker_dir"] = 1

                    # ── reposicionar zona ─────────
                    state["zone_ticks"] += 1
                    if state["zone_ticks"] >= self.ZONE_RESPAWN_TICKS:
                        state["zone_ticks"] = 0
                        state["zone_width"] = random.uniform(self.ZONE_WIDTH_MIN, self.ZONE_WIDTH_MAX)
                        state["zone_start"] = random.uniform(0.05, 0.90 - state["zone_width"])

                    # ── detectar ESPACIO ──────────
                    if state["space_pressed"]:
                        state["space_pressed"] = False
                        m = state["marker"]
                        zs = state["zone_start"]
                        zw = state["zone_width"]
                        in_zone = zs <= m <= zs + zw
                        if in_zone:
                            reduction = (total_time - state["elapsed"]) * self.ZONE_BONUS
                            state["elapsed"] += reduction
                            state["last_msg"] = f"✓ ¡Acierto! -{self.ZONE_BONUS*100:.0f}% de tiempo restante"
                            state["msg_color"] = "bold green"
                            # Respawnear zona inmediatamente
                            state["zone_ticks"] = self.ZONE_RESPAWN_TICKS
                        else:
                            state["last_msg"] = "✗ Fallaste — el marcador estaba fuera de la zona"
                            state["msg_color"] = "bold red"

                    # ── avanzar tiempo ────────────
                    state["elapsed"] += self.TICK_INTERVAL
                    remaining = max(0.0, total_time - state["elapsed"])
                    progress_frac = min(1.0, state["elapsed"] / total_time)

                    live.update(
                        self._build_display(
                            progress=progress_frac,
                            marker=state["marker"],
                            zone_start=state["zone_start"],
                            zone_width=state["zone_width"],
                            remaining=remaining,
                            total_time=total_time,
                            last_msg=state["last_msg"],
                            msg_color=state["msg_color"],
                            material_name=material.Name,
                            power=power,
                        )
                    )
                    time.sleep(self.TICK_INTERVAL)

            state["done"] = True
            try:
                stop_listening()
            except Exception:
                pass
            if kb_thread is not None and kb_thread.is_alive():
                kb_thread.join(timeout=3.0)

        # ── XP ────────────────────────────────
        self.gathering[skill_key].exp_total += material.Hardness / 13

        console.print(f"\n[bold green]✓ Recolección completada.[/bold green] "
                      f"XP acumulada: {self.gathering[skill_key].exp_total:.2f}\n")
        return True
                
class cMaterial:
    VALID_RARITIES   = ("Common", "Uncommon", "Rare", "Epic", "Legendary")

    # Tipos válidos de material (mismo prefijo que cTool usa internamente)
    VALID_TYPES      = (
        "ore", "wood", "fish", "herb", "hide",
        "fiber", "gem", "bone", "essence", "star_dust",
    )

    # Nivel mínimo de skill requerido por rareza (integración con cFarm/cSkill)
    RARITY_LEVEL_REQ = {
        "Common":    1,
        "Uncommon":  10,
        "Rare":      25,
        "Epic":      50,
        "Legendary": 75,
    }

    # Aliases de SkillName aceptados (mismos que usa cFarm.gather)
    SKILL_ALIASES = {
        "woodcutting": "woodcutting",
        "lumberjack":  "woodcutting",
        "herbs":       "herbalism",
        "herbalism":   "herbalism",
        "mining":      "mining",
        "skinning":    "skinning",
        "fishing":     "fishing",
        "astrology":   "astrology",
    }

    def __init__(
        self,
        MATERIAL_ID:  int,
        TypeStr,                        # str  o  List[str]
        Name:         str,
        Hardness:     float,
        SkillName:    str,
        Description:  str   = "Sin descripción.",
        Gold_Cost:    int   = 0,
        MaxStack:     int   = 99,
        Rarity:       str   = "Common",
        Level_Req:    Optional[int] = None,   # None → se deriva de Rarity
    ):
        # ── MATERIAL_ID ───────────────────────────────────────────────────
        if not isinstance(MATERIAL_ID, int) or MATERIAL_ID < 0:
            raise ValueError(f"MATERIAL_ID debe ser un entero >= 0, recibido: {MATERIAL_ID!r}")
        self.MATERIAL_ID: int = MATERIAL_ID

        # ── TypeStr → Material_Types (con validación) ─────────────────────
        raw_types: List[str] = [TypeStr] if isinstance(TypeStr, str) else list(TypeStr)
        if not raw_types:
            raise ValueError("TypeStr no puede estar vacío.")
        invalid = [t for t in raw_types.lower() if t not in self.VALID_TYPES]
        if invalid:
            raise ValueError(
                f"Tipo(s) de material desconocido(s): {invalid}. "
                f"Válidos: {list(self.VALID_TYPES)}"
            )
        self.Material_Types: List[str] = ["TYPE_M:" + t for t in raw_types]
        # Alias de compatibilidad con código anterior
        self.Material_Type:  str       = self.Material_Types[0]

        # ── Name ──────────────────────────────────────────────────────────
        if not isinstance(Name, str) or not Name.strip():
            raise ValueError("Name debe ser una cadena no vacía.")
        self.Name: str = Name.strip()

        # ── Hardness ──────────────────────────────────────────────────────
        hardness_f = float(Hardness)
        if hardness_f <= 0:
            raise ValueError(f"Hardness debe ser > 0, recibido: {Hardness!r}")
        self.Hardness: float = hardness_f

        # ── SkillName (integración con cFarm.GATHERING_SKILLS) ────────────
        normalized_skill = self.SKILL_ALIASES.get(SkillName.lower())
        if normalized_skill is None:
            raise ValueError(
                f"SkillName desconocida: {SkillName!r}. "
                f"Aliases válidos: {list(self.SKILL_ALIASES.keys())}"
            )
        self.SkillName: str = normalized_skill   # siempre guardado en forma canónica

        # ── Rarity ────────────────────────────────────────────────────────
        if Rarity not in self.VALID_RARITIES:
            raise ValueError(
                f"Rarity inválida: {Rarity!r}. Válidas: {list(self.VALID_RARITIES)}"
            )
        self.Rarity: str = Rarity

        # ── Level_Req (integración con cSkill.current_level) ─────────────
        if Level_Req is not None:
            if not isinstance(Level_Req, int) or Level_Req < 1:
                raise ValueError(f"Level_Req debe ser un entero >= 1, recibido: {Level_Req!r}")
            self.Level_Req: int = Level_Req
        else:
            # Derivar automáticamente del nivel mínimo asociado a la rareza
            self.Level_Req = self.RARITY_LEVEL_REQ[Rarity]

        # ── Description ───────────────────────────────────────────────────
        self.Description: str = str(Description) if Description else "Sin descripción."

        # ── Gold_Cost ─────────────────────────────────────────────────────
        if not isinstance(Gold_Cost, int) or Gold_Cost < 0:
            raise ValueError(f"Gold_Cost debe ser un entero >= 0, recibido: {Gold_Cost!r}")
        self.Gold_Cost: int = Gold_Cost

        # ── MaxStack ──────────────────────────────────────────────────────
        if not isinstance(MaxStack, int) or MaxStack < 1:
            raise ValueError(f"MaxStack debe ser un entero >= 1, recibido: {MaxStack!r}")
        self.MaxStack: int = MaxStack

    # ── helpers ────────────────────────────────────────────────────────────

    def has_type(self, type_str: str) -> bool:
        """Comprueba si este material pertenece a un tipo dado (con o sin prefijo TYPE_M:)."""
        normalized = type_str if type_str.startswith("TYPE_M:") else "TYPE_M:" + type_str
        return normalized in self.Material_Types

    def compatible_with_tool(self, tool: "cTool") -> bool:
        """Devuelve True si la herramienta puede procesar alguno de los tipos de este material."""
        tool_types = tool.ToolTypeStr if isinstance(tool.ToolTypeStr, list) else [tool.ToolTypeStr]
        return any(t in tool_types for t in self.Material_Types)

    def can_be_gathered_by(self, farm: "cFarm", skill_key: Optional[str] = None) -> bool:
        """
        Devuelve True si el cFarm dado tiene el nivel suficiente para recolectar
        este material. Usa self.SkillName por defecto; acepta skill_key para override.
        """
        key = skill_key or self.SkillName
        skill = farm.gathering.get(key)
        if skill is None:
            return False
        return skill.current_level >= self.Level_Req

    def __repr__(self) -> str:
        types = ", ".join(t.replace("TYPE_M:", "") for t in self.Material_Types)
        return (
            f"cMaterial(id={self.MATERIAL_ID!r}, name={self.Name!r}, "
            f"types=[{types}], hardness={self.Hardness}, "
            f"skill={self.SkillName!r}, rarity={self.Rarity!r}, lvl_req={self.Level_Req})"
        )

class cTool:
    def __init__(self, ID, TypeStr, Name, Desc, Efficiency, Gold_Cost, MaxStack, Enchantments: List):
        self.ID = ID

        # ── soporte a múltiples tipos de material ──────────────────────────
        if isinstance(TypeStr, str):
            raw_types = [TypeStr]
        else:
            raw_types = list(TypeStr)
        self.ToolTypeStr: List[str] = ["TYPE_M:" + t for t in raw_types]

        self.Name = Name
        self.Desc = Desc
        self.Efficiency = Efficiency
        self.Gold_Cost = Gold_Cost
        self.MaxStack = MaxStack
        self.Enchantments = Enchantments

    def can_gather(self, material: "cMaterial") -> bool:
        """Devuelve True si esta herramienta es compatible con el material dado."""
        return material.compatible_with_tool(self)


def Gathering(cFarmv, cMaterialv, cToolv, cPlayerv, vInventory):
    if cFarmv.gather(cMaterialv, cToolv, cPlayerv): 
        vInventory.addObject(cMaterialv)

Gathering_init = cFarm()