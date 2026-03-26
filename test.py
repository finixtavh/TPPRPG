"""
Prueba de concepto: Minijuego de recolección con barra de zona verde.
Presiona ESPACIO cuando el marcador esté en la zona verde para reducir el tiempo.

Dependencias:
    pip install rich sshkeyboard

Uso:
    python gathering.py
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List

from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box
from sshkeyboard import listen_keyboard, stop_listening


# ──────────────────────────────────────────────
# Modelos de datos
# ──────────────────────────────────────────────

@dataclass
class cSkill:
    current_level: int = 1
    exp_total: float = 0.0


@dataclass
class cMaterial:
    Name: str
    SkillName: str       # "mining", "lumberjack", etc.
    Hardness: float = 100.0


@dataclass
class cTool:
    Name: str
    Efficiency: float = 1.0


# ──────────────────────────────────────────────
# Config del minijuego
# ──────────────────────────────────────────────

ZONE_BONUS: float = 0.20          # % de reducción al acertar (configurable)
TICK_INTERVAL: float = 0.05       # segundos por frame de la animación
MARKER_SPEED: float = 0.035       # cuánto se mueve el marcador por tick (0-1)
ZONE_WIDTH_MIN: float = 0.12      # ancho mínimo de la zona verde (fracción)
ZONE_WIDTH_MAX: float = 0.22      # ancho máximo
ZONE_RESPAWN_TICKS: int = 60      # ticks antes de reposicionar la zona


# ──────────────────────────────────────────────
# Clase principal
# ──────────────────────────────────────────────

class cFarm:
    GATHERING_SKILLS = ["mining", "lumberjack", "fishing", "herbs", "hunting", "astrology"]
    WEAPON_SKILLS = [
        "swords", "electric_wands", "thermal_wands", "earth_wands",
        "void_staffs", "shields", "blessed_ornament", "ornament", "cursed_ornament",
    ]

    def __init__(self):
        self.gathering: Dict[str, cSkill] = {s: cSkill() for s in self.GATHERING_SKILLS}
        self.weapons: Dict[str, cSkill]   = {s: cSkill() for s in self.WEAPON_SKILLS}

    # ── helpers internos ──────────────────────

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
        """Construye el panel que se refresca en cada tick."""

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
        table.add_row(Text(f"Poder: {power:.2f}  |  Bonus zona: {ZONE_BONUS*100:.0f}%", style="dim"))
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

    # ── método principal ──────────────────────

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
            "zone_width": random.uniform(ZONE_WIDTH_MIN, ZONE_WIDTH_MAX),
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

        with Live(console=console, refresh_per_second=int(1 / TICK_INTERVAL)) as live:
            while state["elapsed"] < total_time:
                # ── mover marcador ────────────
                state["marker"] += state["marker_dir"] * MARKER_SPEED
                if state["marker"] >= 1.0:
                    state["marker"] = 1.0
                    state["marker_dir"] = -1
                elif state["marker"] <= 0.0:
                    state["marker"] = 0.0
                    state["marker_dir"] = 1

                # ── reposicionar zona ─────────
                state["zone_ticks"] += 1
                if state["zone_ticks"] >= ZONE_RESPAWN_TICKS:
                    state["zone_ticks"] = 0
                    state["zone_width"] = random.uniform(ZONE_WIDTH_MIN, ZONE_WIDTH_MAX)
                    state["zone_start"] = random.uniform(0.05, 0.90 - state["zone_width"])

                # ── detectar ESPACIO ──────────
                if state["space_pressed"]:
                    state["space_pressed"] = False
                    m = state["marker"]
                    zs = state["zone_start"]
                    zw = state["zone_width"]
                    in_zone = zs <= m <= zs + zw
                    if in_zone:
                        reduction = (total_time - state["elapsed"]) * ZONE_BONUS
                        state["elapsed"] += reduction
                        state["last_msg"] = f"✓ ¡Acierto! -{ZONE_BONUS*100:.0f}% de tiempo restante"
                        state["msg_color"] = "bold green"
                        # Respawnear zona inmediatamente
                        state["zone_ticks"] = ZONE_RESPAWN_TICKS
                    else:
                        state["last_msg"] = "✗ Fallaste — el marcador estaba fuera de la zona"
                        state["msg_color"] = "bold red"

                # ── avanzar tiempo ────────────
                state["elapsed"] += TICK_INTERVAL
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
                time.sleep(TICK_INTERVAL)

        state["done"] = True
        stop_listening()

        # ── XP ────────────────────────────────
        self.gathering[skill_key].exp_total += material.Hardness / 13

        console.print(f"\n[bold green]✓ Recolección completada.[/bold green] "
                      f"XP acumulada: {self.gathering[skill_key].exp_total:.2f}\n")
        return True


# ──────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────

if __name__ == "__main__":
    farm = cFarm()
    farm.gathering["mining"].current_level = 3

    iron_ore = cMaterial(Name="Iron Ore", SkillName="mining", Hardness=80.0)
    pickaxe = cTool(Name="Iron Pickaxe", Efficiency=1.5)

    farm.gather(iron_ore, pickaxe, buffs=[1.2])

