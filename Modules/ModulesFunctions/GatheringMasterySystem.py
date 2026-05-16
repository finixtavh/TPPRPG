import time
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from pathlib import Path

from Modules.ModulesUtils.Loader import Read

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box
from sshkeyboard import listen_keyboard, stop_listening

from Modules.ModulesUtils.input_utils import keyboard_listener_scope

class cSkill:
    BONUS_EFFICIENCY: float = 0.05   # +5% de eficiencia de recolección por nivel
    BONUS_XP_FACTOR:  float = 0.10   # +10% de XP obtenida al recolectar por nivel
    MAX_LEVEL: int = 50
    EXP_BASE: float = 100.0
    EXP_GROWTH: float = 1.5

    def __init__(self):
        self.exp_total: float = 0.0
        self.exp_to_next_lvl: float = self.EXP_BASE
        self.current_level: int = 1

    def _recalc_exp_to_next(self) -> None:
        self.exp_to_next_lvl = self.EXP_BASE * (self.EXP_GROWTH ** (self.current_level - 1))

    def level_up(self) -> None:
        """Incrementa nivel y actualiza la EXP requerida para el siguiente."""
        if self.current_level >= self.MAX_LEVEL:
            return
        self.current_level += 1
        self._recalc_exp_to_next()

    def add_exp(self, amount: float) -> int:
        """Añade EXP y sube de nivel si corresponde. Devuelve niveles ganados."""
        if self.current_level >= self.MAX_LEVEL:
            return 0
        self.exp_total += amount
        levels_gained = 0
        while self.exp_total >= self.exp_to_next_lvl and self.current_level < self.MAX_LEVEL:
            self.exp_total -= self.exp_to_next_lvl
            self.level_up()
            levels_gained += 1
        if self.current_level >= self.MAX_LEVEL:
            self.exp_total = 0.0
        return levels_gained

    @property
    def efficiency_bonus(self) -> float:
        """Multiplicador de eficiencia (velocidad de recolección). 1.0 = sin bonus."""
        return 1.0 + (self.current_level - 1) * self.BONUS_EFFICIENCY

    @property
    def xp_bonus_factor(self) -> float:
        """Multiplicador de XP ganada al recolectar. 1.0 = sin bonus."""
        return 1.0 + (self.current_level - 1) * self.BONUS_XP_FACTOR

    @property
    def efficiency_pct(self) -> float:
        """Bonus de eficiencia en porcentaje (para mostrar en UI)."""
        return (self.current_level - 1) * self.BONUS_EFFICIENCY * 100

    @property
    def xp_pct(self) -> float:
        """Bonus de XP en porcentaje (para mostrar en UI)."""
        return (self.current_level - 1) * self.BONUS_XP_FACTOR * 100

class cFarm:
    ruta = Path(__file__).parent.parent.parent / "config.json"

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
        skill_info: Optional[tuple] = None, # (lvl, efficiency_pct, xp_pct)
    ) -> Panel:
        BAR_WIDTH = 50
        
        # ── barra de progreso principal ───────
        prog_r = int(progress * BAR_WIDTH)
        prog_bar = Text()
        prog_bar.append("█" * prog_r, style="bright_green")
        prog_bar.append("░" * (BAR_WIDTH - prog_r), style="dim")

        # ── minijuego (zona y marcador) ───────
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
        time_line = Text(f"Tiempo: {elapsed:.1f}/{total_time:.1f}s ({pct:.0f}%)", style="yellow")

        # ── mensaje de feedback ────────────────
        fb = Text(last_msg, style=msg_color)

        # ── tabla contenedora ─────────────────
        table = Table.grid(padding=(0, 0, 0, 0))
        table.add_column(no_wrap=True)

        table.add_row(Text(f"Recolectando: {material_name}", style="bold cyan"))
        table.add_row(Text(f"Poder: {power:.2f}  |  Bonus zona: {self.ZONE_BONUS*100:.0f}%", style="dim"))
        # ── indicadores de bonus de skill ─────
        if skill_info:
            lvl, eff_pct, xp_pct = skill_info
            bonus_text = Text()
            bonus_text.append(f"Nivel de skill: {lvl}", style="bold bright_yellow")
            bonus_text.append("  |  ", style="dim")
            bonus_text.append(f"+{eff_pct:.0f}% eficiencia", style="bright_green")
            bonus_text.append("  ", style="dim")
            bonus_text.append(f"+{xp_pct:.0f}% XP", style="bright_cyan")
            table.add_row(bonus_text)
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
        material: "cMaterial",
        tool: Optional["cTool"],
        buffs: Optional[List[float]] = None,
    ) -> int: # Retorna la cantidad obtenida (0 si falla/cancela)
        if buffs is None:
            buffs = []

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

        skill_obj = self.gathering[skill_key]
        Gathering_Skill_Bonus = skill_obj.efficiency_bonus
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
                            skill_info=(
                                skill_obj.current_level,
                                skill_obj.efficiency_pct,
                                skill_obj.xp_pct,
                            ),
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
        xp_base = material.Hardness / 13
        
        global_xp_mod = 1.0
        try:
            cfg_world = Read(self.ruta, "WORLD")
            if cfg_world and "GLOBAL_RESOURCE_EXP_MASTERY_MODIFIER" in cfg_world:
                global_xp_mod = float(cfg_world["GLOBAL_RESOURCE_EXP_MASTERY_MODIFIER"])
        except Exception:
            pass
            
        xp_gained = xp_base * skill_obj.xp_bonus_factor * global_xp_mod
        levels_up = skill_obj.add_exp(xp_gained)

        level_msg = ""
        if levels_up > 0:
            level_msg = (
                f"  [bold bright_yellow]¡Subiste a nivel {skill_obj.current_level} en {skill_key}![/bold bright_yellow]\n"
                f"  [bright_green]  +{skill_obj.efficiency_pct:.0f}% eficiencia de recoleccion[/bright_green]\n"
                f"  [bright_cyan]  +{skill_obj.xp_pct:.0f}% XP ganada[/bright_cyan]"
            )

        # ── Cálculo de Cantidad (1x, 2x, 3x) ──
        # Probabilidades base: 1x=80%, 2x=15%, 3x=5%
        # El power (herramienta + skill + buffs) aumenta la probabilidad de 2x y 3x
        
        bonus_roll = (power - 1.0) * 0.15 # Cada punto de power extra da 15% de bonus a los rolls raros
        
        p3 = 0.05 + bonus_roll * 0.2
        p2 = 0.15 + bonus_roll * 0.5
        
        roll = random.random()
        if roll < p3:
            quantity = 3
        elif roll < (p3 + p2):
            quantity = 2
        else:
            quantity = 1

        console.print(
            f"\n[bold green]Recolección completada.[/bold green] "
            f"¡Has obtenido [bold yellow]{quantity}x[/bold yellow] {material.Name}!"
        )
        
        console.print(
            f"[bright_cyan]+{xp_gained:.1f} XP[/bright_cyan] "
            f"(Lv.{skill_obj.current_level} | hasta siguiente: {skill_obj.exp_to_next_lvl:.0f})"
        )
        if level_msg:
            console.print(level_msg)
            
        return quantity
                
class cMaterial:
    VALID_RARITIES   = ("Common", "Uncommon", "Rare", "Epic", "Legendary")

    # Tipos válidos de material (mismo prefijo que cTool usa internamente)
    VALID_TYPES      = (
        "ore", "wood", "fish", "herb", "hide",
        "fiber", "gem", "bone", "essence", "star_dust",
        "rock", "herbs", "leather", "fabric", "potion", "scroll", "special", "food", "seed"
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

        if not isinstance(MATERIAL_ID, int) or MATERIAL_ID < 0:
            raise ValueError(f"MATERIAL_ID debe ser un entero >= 0, recibido: {MATERIAL_ID!r}")
        self.MATERIAL_ID: int = MATERIAL_ID

        raw_types: List[str] = [TypeStr.lower()] if isinstance(TypeStr, str) else [t.lower() for t in TypeStr]
        if not raw_types:
            raise ValueError("TypeStr no puede estar vacío.")
        invalid = [t for t in raw_types if t not in self.VALID_TYPES]
        if invalid:
            raise ValueError(
                f"Tipo(s) de material desconocido(s): {invalid}. "
                f"Válidos: {list(self.VALID_TYPES)}"
            )
        self.Material_Types: List[str] = ["TYPE_M:" + t for t in raw_types]

        if not isinstance(Name, str) or not Name.strip():
            raise ValueError("Name debe ser una cadena no vacía.")
        self.Name: str = Name.strip()

        hardness_f = float(Hardness)
        if hardness_f <= 0:
            raise ValueError(f"Hardness debe ser > 0, recibido: {Hardness!r}")
        self.Hardness: float = hardness_f

        normalized_skill = self.SKILL_ALIASES.get(SkillName.lower())
        if normalized_skill is None:
            raise ValueError(
                f"SkillName desconocida: {SkillName!r}. "
                f"Aliases válidos: {list(self.SKILL_ALIASES.keys())}"
            )
        self.SkillName: str = normalized_skill   

        if Rarity not in self.VALID_RARITIES:
            raise ValueError(
                f"Rarity inválida: {Rarity!r}. Válidas: {list(self.VALID_RARITIES)}"
            )
        self.Rarity: str = Rarity

        if Level_Req is not None:
            if not isinstance(Level_Req, int) or Level_Req < 1:
                raise ValueError(f"Level_Req debe ser un entero >= 1, recibido: {Level_Req!r}")
            self.Level_Req: int = Level_Req
        else:
            self.Level_Req = self.RARITY_LEVEL_REQ[Rarity]

        self.Description: str = str(Description) if Description else "Sin descripción."

        if not isinstance(Gold_Cost, int) or Gold_Cost < 0:
            raise ValueError(f"Gold_Cost debe ser un entero >= 0, recibido: {Gold_Cost!r}")
        self.Gold_Cost: int = Gold_Cost

        if not isinstance(MaxStack, int) or MaxStack < 1:
            raise ValueError(f"MaxStack debe ser un entero >= 1, recibido: {MaxStack!r}")
        self.MaxStack: int = MaxStack

    @property
    def ID(self):
        return self.MATERIAL_ID


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
        Devuelve True si el nivel en la skill requerida es suficiente.
        """
        if skill_key is None:
            skill_key = self.SkillName
        if skill_key not in farm.gathering:
            return False
        return farm.gathering[skill_key].current_level >= self.Level_Req

class cTool:
    def __init__(self, ID, Name, TypeStr=None, Efficiency=1.0, Gold_Cost=0, Description="Sin descripción", ToolTypeStr=None, Desc=None, MaxStack=1, Enchantments=None):
        self.ID = ID
        self.Name = Name
        
        # Soporte para ambos nombres de argumento (TypeStr de ItemManager, ToolTypeStr de GatheringSystem)
        raw_type = TypeStr or ToolTypeStr or "Unknown"
        self.ToolTypeStr = ["TYPE_M:" + t.lower() for t in (raw_type if isinstance(raw_type, list) else [raw_type])]
        
        self.Efficiency = Efficiency
        self.Gold_Cost = Gold_Cost
        self.Description = Desc or Description
        self.MaxStack = MaxStack
        self.Enchantments = Enchantments or []

Gathering_init = cFarm()