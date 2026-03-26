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


    GATHERING_SKILLS = ["mining", "lumberjack", "fishing", "herbs", "hunting", "astrology"]

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

        skill_key = material.SkillName.lower()
        if skill_key not in self.gathering:
            raise ValueError(f"Skill desconocida: {skill_key}")

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

        # Escucha en hilo aparte
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
        stop_listening()

        # ── XP ────────────────────────────────
        self.gathering[skill_key].exp_total += material.Hardness / 13

        console.print(f"\n[bold green]✓ Recolección completada.[/bold green] "
                      f"XP acumulada: {self.gathering[skill_key].exp_total:.2f}\n")
        return True
                
class cMaterial:
    def __init__(self, MATERIAL_ID, TypeStr, Name, Hardness, SkillName):
        self.MATERIAL_ID = MATERIAL_ID
        self.Material_Type: str = "TYPE_M:" + TypeStr
        self.Name = Name
        self.Hardness = Hardness
        self.SkillName = SkillName

class cTool:
    def __init__(self, ID, TypeStr, Name, Desc, Efficiency, Gold_Cost, MaxStack, Enchantments: List):
        self.ID = ID
        self.ToolTypeStr: str = "TYPE_M:" + TypeStr # Needs support for multiple materials
        self.Name = Name
        self.Desc = Desc
        self.Efficiency = Efficiency
        self.Gold_Cost = Gold_Cost
        self.MaxStack = MaxStack
        self.Enchantments = Enchantments


def Gathering(cFarmv, cMaterialv, cToolv, cPlayerv, vInventory):
    if cFarmv.gather(cMaterialv, cToolv, cPlayerv): 
        vInventory.addObject(cMaterialv)

Gathering_init = cFarm()