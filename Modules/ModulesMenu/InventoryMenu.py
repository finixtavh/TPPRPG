"""
InventoryMenu.py
================
Menú de inventario interactivo con selección visual por flechas.
Compatible con cWeapon, cEquippableItems, cObject y cTool.

Acciones disponibles según tipo:
  cWeapon / cEquippableItems / cTool  →  [E] Equipar   [I] Información
  cObject                             →  [U] Usar       [I] Información

Nota: equipar un Anillo muestra un menú para elegir en qué slot (ring/ring2/ring3).
"""

import threading
import time
from typing import List, Optional, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import box
from rich.live import Live
from rich.rule import Rule
from sshkeyboard import listen_keyboard, stop_listening

from Modules.ModulesUtils.input_utils import keyboard_listener_scope
from Modules.ModulesUtils.UIStyle import (
    herald_panel, herald_bar, herald_table, ICONS, 
    COLOR_PRIMARY, COLOR_SECONDARY, COLOR_DIM
)

# ──────────────────────────────────────────────
#  Paleta / constantes visuales
# ──────────────────────────────────────────────
_RARITY_COLOR = {
    "Common":    "white",
    "Uncommon":  "bright_green",
    "Rare":      "bright_blue",
    "Epic":      "medium_purple1",
    "Legendary": "gold1",
}

_TYPE_ICON = {
    "cWeapon":          "⚔",
    "cEquippableItems": "🛡",
    "cObject":          "🧪",
    "cTool":            "⛏",
    "cMaterial":        "🪨"
}

_TYPE_LABEL = {
    "cWeapon":          "Arma",
    "cEquippableItems": "Equipamiento",
    "cObject":          "Objeto",
    "cTool":            "Herramienta",
    "cMaterial":        "Material"
}

_TYPE_COLOR = {
    "cWeapon":          "bold red",
    "cEquippableItems": "bold cyan",
    "cObject":          "bold yellow",
    "cTool":            "bold dark_orange3",
    "cMaterial":        "bold blue"
}

_DMG_NAMES  = ["Fís", "Tér", "Tier", "Eléc", "Prof"]
_DEF_NAMES  = ["Fís", "Tér", "Tier", "Eléc", "Prof"]


# ──────────────────────────────────────────────
#  Helpers de tipo
# ──────────────────────────────────────────────
def _item_type(item) -> str:
    return type(item).__name__


def _item_name(item) -> str:
    return getattr(item, "Name", getattr(item, "name", "???"))


def _item_desc(item) -> str:
    return getattr(item, "Description", getattr(item, "description", getattr(item, "Desc", getattr(item, "desc", "Sin descripción."))))


def _item_cost(item) -> int:
    return getattr(item, "Gold_Cost", 0)


def _is_discovered(item, player) -> bool:
    """Comprueba si el item ha sido descubierto por el jugador."""
    if player is None:
        return True
    # Algunos items usan ID, otros STATIC_ID o MATERIAL_ID
    item_id = getattr(item, "ID", getattr(item, "STATIC_ID", getattr(item, "MATERIAL_ID", None)))
    if item_id is None:
        return True
    return item_id in getattr(player, "discovered_items", set())


def _obscure(text: str) -> str:
    """Reemplaza caracteres por bloques para ocultar información."""
    # Preservar espacios para mantener estructura visual básica
    return "".join("█" if not c.isspace() else c for c in text)


# ──────────────────────────────────────────────
#  Panel: lista de inventario (lado izquierdo)
# ──────────────────────────────────────────────
def _render_item_list(slots, selected_idx: int, scroll_offset: int, max_visible: int, player=None) -> Panel:
    t = herald_table(expand=True)
    t.add_column("Idx",   width=3)
    t.add_column("Icon",  width=3)
    t.add_column("Nombre", ratio=1)
    t.add_column("Cant",  width=4)

    visible = slots[scroll_offset : scroll_offset + max_visible]

    for rel_idx, slot in enumerate(visible):
        abs_idx = scroll_offset + rel_idx
        selected = abs_idx == selected_idx
        itype    = _item_type(slot.item)
        icon     = _TYPE_ICON.get(itype, "?")
        
        discovered = _is_discovered(slot.item, player)
        name     = _item_name(slot.item) if discovered else _obscure(_item_name(slot.item))
        qty      = str(slot.quantity) if slot.quantity > 1 else ""

        if selected:
            row_style = f"bold {COLOR_PRIMARY}"
            idx_text  = Text(f"{ICONS['arrow']}{abs_idx + 1:2d}", style=row_style)
            icon_text = Text(icon, style=row_style)
            name_text = Text(name, style=row_style)
            qty_text  = Text(qty,  style=row_style)
        else:
            idx_text  = Text(f"  {abs_idx + 1:2d}", style=COLOR_DIM)
            icon_text = Text(icon, style=COLOR_SECONDARY)
            name_text = Text(name, style="bright_white")
            qty_text  = Text(qty,  style=COLOR_DIM)

        t.add_row(idx_text, icon_text, name_text, qty_text)

    return herald_panel(t, title="Inventario", border_style=COLOR_PRIMARY, expand=True)


# ──────────────────────────────────────────────
#  Panel: detalle del item (lado derecho)
# ──────────────────────────────────────────────
def _render_item_detail(slot, player=None) -> Panel:
    if slot is None:
        return Panel(
            Text("\n  Selecciona un ítem\n  para ver sus detalles.", style="dim italic"),
            title="[dim]DETALLE[/dim]",
            border_style="grey35",
        )

    item  = slot.item
    itype = _item_type(item)
    discovered = _is_discovered(item, player)
    
    name  = _item_name(item) if discovered else _obscure(_item_name(item))
    desc  = _item_desc(item) if discovered else _obscure(_item_desc(item))
    cost  = _item_cost(item)
    icon  = _TYPE_ICON.get(itype, "?")
    tcolor = _TYPE_COLOR.get(itype, "white")

    lines: List[Any] = []

    # ── Cabecera ──
    header = Text()
    header.append(f"{icon}  ", style=tcolor)
    header.append(name, style=f"bold {tcolor}")
    lines.append(header)
    lines.append(Rule(style="grey35"))

    # ── Tipo ──
    type_line = Text()
    type_line.append("Tipo: ", style="dim")
    type_line.append(_TYPE_LABEL.get(itype, itype), style=tcolor)
    if itype == "cEquippableItems":
        slot_label = getattr(item, "objectcheck", "?")
        type_line.append(f"  ({slot_label})", style="dim")
    lines.append(type_line)

    if not discovered:
        lines.append(Text(""))
        lines.append(Text(desc, style="italic dim"))
        lines.append(Text(""))
        lines.append(Rule(style="grey35"))
        lines.append(Text("  [?] Ítem no descubierto", style="bold red"))
        return Panel(
            Group(*lines),
            title=f"[bold {tcolor}]  DETALLE  [/bold {tcolor}]",
            border_style=tcolor.replace("bold ", ""),
            padding=(0, 1),
        )

    # ── Descripción ──
    lines.append(Text(""))
    lines.append(Text(desc, style="italic dim"))
    lines.append(Text(""))
    lines.append(Rule(style="grey35"))

    # ── Stats específicos por tipo ──
    if itype == "cWeapon":
        dmg     = getattr(item, "DMG",     [0]*5)
        dmg_min = getattr(item, "DMG_min", [0]*4)

        has_dmg = any(v > 0 for v in dmg)
        if has_dmg:
            lines.append(Text("  Daño:", style=f"bold {COLOR_PRIMARY}"))
            max_val = max(dmg) or 1
            for i, (mn, mx) in enumerate(zip(dmg_min + [dmg[4]], dmg)):
                if mx > 0:
                    lines.append(Text(f"    {_DMG_NAMES[i]:<4} {herald_bar(mx, max_val, 12)} {mn}-{mx}", style="dim"))

    elif itype == "cEquippableItems":
        defense     = getattr(item, "Defense",     [0]*5)
        health_b    = getattr(item, "HealthBoost", 0)
        health_st   = getattr(item, "HealthSteal", 0)
        dmg_boost   = getattr(item, "DmgBoost",    0)

        has_def = any(v > 0 for v in defense)
        if has_def:
            lines.append(Text("  Defensa:", style=f"bold {COLOR_PRIMARY}"))
            max_def = max(defense) or 1
            for i, v in enumerate(defense):
                if v > 0:
                    lines.append(Text(f"    {_DEF_NAMES[i]:<4} {herald_bar(v, max_def, 12)} +{v}", style="dim"))

        if health_b > 0:
            lines.append(Text(f"  ❤  HP Máximo:     +{health_b}", style="green"))
        if health_st > 0:
            lines.append(Text(f"  🩸 Robo de vida:  +{health_st}", style="red"))
        if dmg_boost > 0:
            lines.append(Text(f"  ⚔  Daño extra:    +{dmg_boost}", style="yellow"))

    elif itype == "cObject":
        hp_r  = getattr(item, "HealthRestore", 0)
        mp_r  = getattr(item, "ManaRestore",   0)

        if hp_r > 0:
            lines.append(Text(f"  ❤  Restaura HP:  +{hp_r}", style="bold green"))
        if mp_r > 0:
            lines.append(Text(f"  💧 Restaura MP:  +{mp_r}", style="bold blue"))

    elif itype == "cTool":
        efficiency = getattr(item, "Efficiency", 1.0)
        tool_types_raw = getattr(item, "ToolTypeStr", [])
        if isinstance(tool_types_raw, str):
            tool_types_raw = [tool_types_raw]
        tool_types = [t.replace("TYPE_M:", "") for t in tool_types_raw if t]
        enchants   = getattr(item, "Enchantments", []) or []

        bar_len = min(int(efficiency / 8.0 * 12), 12)
        bar     = "█" * bar_len + "░" * (12 - bar_len)
        lines.append(Text(f"  ⚡ Eficiencia:  {bar}  {efficiency:.1f}x", style="bold yellow"))
        if tool_types:
            lines.append(Text(f"  🪵 Tipo matl.:  {', '.join(tool_types)}", style="dim"))
        if enchants:
            lines.append(Text(f"  ✨ Encants.:    {', '.join(enchants)}", style="bright_magenta"))

    elif itype == "cMaterial":
        hardness      = getattr(item, "Hardness",       1.0)
        skill_name    = getattr(item, "SkillName",       "?")
        rarity        = getattr(item, "Rarity",          "Common")
        mat_types_raw = getattr(item, "Material_Types",  [])
        if isinstance(mat_types_raw, str):
            mat_types_raw = [mat_types_raw]
        mat_types = [t.replace("TYPE_M:", "") for t in mat_types_raw if t]

        rarity_color = _RARITY_COLOR.get(rarity, "white")
        rar_line = Text(f"  ✦  Rareza:      ", style="dim")
        rar_line.append(rarity, style=f"bold {rarity_color}")
        lines.append(rar_line)

        bar_len = min(int(hardness / 20.0 * 12), 12)
        bar     = "█" * bar_len + "░" * (12 - bar_len)
        lines.append(Text(f"  🪨 Dureza:      {bar}  {hardness:.1f}", style="bold blue"))
        lines.append(Text(f"  ⛏  Skill:       {skill_name.capitalize()}", style="dim"))
        if mat_types:
            lines.append(Text(f"  📦 Tipo(s):     {', '.join(mat_types)}", style="dim"))

    # ── Modificador de Objeto ────────────────────────────────────────────────
    if itype in ("cWeapon", "cEquippableItems", "cTool"):
        mod = getattr(item, "modifier", None)
        lines.append(Text(""))
        lines.append(Rule(style="grey35"))
        if mod is not None:
            m_color = "red" if mod.is_negative else "green"
            mod_line = Text()
            mod_line.append(f"  {mod.icon} Modificador:  ", style="dim")
            mod_line.append(f"{mod.name}", style=f"bold {m_color}")
            # Mostrar efectos
            eff_parts = []
            for k, v in mod.effects.items():
                sign = "+" if v > 0 else ""
                if "pct" in k:
                    eff_parts.append(f"{sign}{v*100:.0f}%")
                else:
                    eff_parts.append(f"{sign}{v:.0f}")
            if eff_parts:
                mod_line.append(f"  ({', '.join(eff_parts)})", style=f"dim {m_color}")
            lines.append(mod_line)
        else:
            lines.append(Text("  Sin modificador", style="dim italic"))

    # ── Encantamientos (para Armas, Equipo y Herramientas) ──
    if itype in ("cWeapon", "cEquippableItems", "cTool"):
        try:
            from Modules.ModulesFunctions.EnchantmentSystem import (
                get_item_enchants, format_enchant_display,
                ENCHANTMENTS_CATALOG, MAX_ENCHANT_SLOTS
            )
            enchant_entries = get_item_enchants(item)
            if enchant_entries:
                lines.append(Text(""))
                lines.append(Rule(style="grey35"))
                n_fam = len({e["family_id"] for e in enchant_entries})
                lines.append(Text(f"  ✨ Encantamientos ({n_fam}/{MAX_ENCHANT_SLOTS}):", style="bold bright_magenta"))
                for entry in enchant_entries:
                    display = format_enchant_display(entry, ENCHANTMENTS_CATALOG)
                    # Color by family rarity
                    fam_id = entry["family_id"]
                    color = "bright_magenta"
                    for ench in ENCHANTMENTS_CATALOG.values():
                        if ench.family_id == fam_id:
                            color = ench.get_rarity_color()
                            break
                    lines.append(Text(f"    ✦ {display}", style=f"bold {color}"))
        except Exception:
            pass

    lines.append(Text(""))

    # ── Precio ──
    if cost > 0:
        lines.append(Text(f"  💰 Precio: {cost} oro", style="dim gold1"))

    # ── Cantidad ──
    if slot.quantity > 1:
        lines.append(Text(f"  📦 Cantidad: x{slot.quantity}", style="dim"))

    # ── Equipado actualmente ──
    if player is not None:
        if itype in ("cWeapon", "cEquippableItems"):
            equipped_slots = ["weapon", "helmet", "armor", "boots", "ring", "ring2", "ring3"]
            for eq_slot in equipped_slots:
                eq = getattr(player, eq_slot, None)
                if eq is not None and eq is item:
                    lines.append(Text(""))
                    lines.append(Text("  ✓ ACTUALMENTE EQUIPADO", style="bold bright_green"))
                    break
        elif itype == "cTool":
            eq = getattr(player, "tool", None)
            if eq is not None and eq is item:
                lines.append(Text(""))
                lines.append(Text("  ✓ ACTUALMENTE EQUIPADO", style="bold bright_green"))

    return herald_panel(
        Group(*lines),
        title="Detalle",
        border_style=COLOR_PRIMARY,
        expand=True
    )


# ──────────────────────────────────────────────
#  Panel: barra de acciones (abajo)
# ──────────────────────────────────────────────
def _render_actions(slot, message: str, message_style: str) -> Panel:
    if slot is None:
        return Panel(
            Text("Sin ítem seleccionado.", style="dim"),
            border_style="grey35",
            height=3,
        )

    itype = _item_type(slot.item)

    parts = []

    if itype in ("cWeapon", "cEquippableItems", "cTool"):
        parts.append(("[E] Equipar",    "bold bright_green"))
    else:
        parts.append(("[U] Usar",       "bold bright_yellow"))

    parts.append(("[I] Información", "bold bright_cyan"))
    parts.append(("[Q] Cerrar",      "dim"))

    action_text = Text()
    for i, (label, style) in enumerate(parts):
        if i > 0:
            action_text.append("   ", style="dim")
        action_text.append(label, style=style)

    msg_text = Text(message, style=message_style) if message else Text("")

    return Panel(
        Group(action_text, msg_text),
        border_style="grey50",
        padding=(0, 1),
    )


# ──────────────────────────────────────────────
#  Pantalla de información detallada
# ──────────────────────────────────────────────
def _show_item_info_screen(item, console: Console, player=None):
    """Muestra pantalla completa de información y espera Enter."""
    itype  = _item_type(item)
    discovered = _is_discovered(item, player)
    name   = _item_name(item) if discovered else _obscure(_item_name(item))
    tcolor = _TYPE_COLOR.get(itype, "white")

    lines: List[Any] = []
    lines.append(Text(f"  {_TYPE_ICON.get(itype, '?')}  {name}", style=f"bold {tcolor}"))
    lines.append(Rule(style="grey35"))
    lines.append(Text(f"  Tipo: {_TYPE_LABEL.get(itype, itype)}", style="dim"))
    lines.append(Text(""))
    
    if not discovered:
        lines.append(Text(f"  {_obscure(_item_desc(item))}", style="italic"))
        lines.append(Text(""))
        lines.append(Text("  [!] Debes descubrir este ítem para ver sus detalles.", style="bold red"))
    else:
        lines.append(Text(f"  {_item_desc(item)}", style="italic"))
        lines.append(Text(""))

    if discovered and itype == "cWeapon":
        dmg     = getattr(item, "DMG",     [0]*5)
        dmg_min = getattr(item, "DMG_min", [0]*4)
        lines.append(Text("  ─── Estadísticas de Daño ───", style="bold"))
        for i, (name_d, mn, mx) in enumerate(zip(_DMG_NAMES, dmg_min + [dmg[4]], dmg)):
            if mx > 0:
                if i == 4:
                    lines.append(Text(f"    {name_d:<12} {mx} (siempre fijo)", style="dim"))
                else:
                    lines.append(Text(f"    {name_d:<12} {mn} – {mx}", style="dim"))

    elif itype == "cEquippableItems":
        defense   = getattr(item, "Defense",     [0]*5)
        health_b  = getattr(item, "HealthBoost", 0)
        health_st = getattr(item, "HealthSteal", 0)
        dmg_boost = getattr(item, "DmgBoost",    0)
        slot_label = getattr(item, "objectcheck", "?")

        lines.append(Text(f"  Slot: {slot_label}", style="dim"))
        lines.append(Text(""))
        lines.append(Text("  ─── Defensa ───", style="bold"))
        for i, v in enumerate(defense):
            if v > 0:
                lines.append(Text(f"    {_DEF_NAMES[i]:<12} +{v}", style="dim"))
        if health_b:  lines.append(Text(f"\n  ❤  HP Máximo:     +{health_b}", style="green"))
        if health_st: lines.append(Text(f"  🩸 Robo de vida:  +{health_st}", style="red"))
        if dmg_boost: lines.append(Text(f"  ⚔  Daño extra:    +{dmg_boost}", style="yellow"))

    elif itype == "cObject":
        hp_r = getattr(item, "HealthRestore", 0)
        mp_r = getattr(item, "ManaRestore",   0)
        lines.append(Text("  ─── Efectos al usar ───", style="bold"))
        if hp_r: lines.append(Text(f"    ❤  Restaura HP:  +{hp_r}", style="green"))
        if mp_r: lines.append(Text(f"    💧 Restaura MP:  +{mp_r}", style="blue"))

    elif itype == "cTool":
        efficiency = getattr(item, "Efficiency", 1.0)
        tool_type  = getattr(item, "ToolTypeStr", "").replace("TYPE_M:", "")
        lines.append(Text("  ─── Estadísticas de Herramienta ───", style="bold"))
        lines.append(Text(f"    ⚡ Eficiencia:   {efficiency:.1f}x", style="dim"))
        if tool_type:
            lines.append(Text(f"    🪵 Tipo matl.:  {tool_type}", style="dim"))

    # ── Encantamientos (universal para armas, equipo y herramientas) ──
    if itype in ("cWeapon", "cEquippableItems", "cTool"):
        try:
            from Modules.ModulesFunctions.EnchantmentSystem import (
                get_item_enchants, format_enchant_display,
                ENCHANTMENTS_CATALOG, MAX_ENCHANT_SLOTS
            )
            enchant_entries = get_item_enchants(item)
            if enchant_entries:
                n_fam = len({e["family_id"] for e in enchant_entries})
                lines.append(Text(""))
                lines.append(Text(f"  ✨ Encantamientos ({n_fam}/{MAX_ENCHANT_SLOTS}):", style="bold bright_magenta"))
                for entry in enchant_entries:
                    display = format_enchant_display(entry, ENCHANTMENTS_CATALOG)
                    lines.append(Text(f"    ✦ {display}", style="bright_magenta"))
        except Exception:
            pass

    cost = _item_cost(item)
    if cost:
        lines.append(Text(""))
        lines.append(Text(f"  💰 Precio: {cost} oro", style="dim gold1"))

    lines.append(Text(""))
    lines.append(Rule(style="grey35"))
    lines.append(Text("  Presiona cualquier tecla para volver...", style="dim italic"))

    console.clear()
    console.print(Panel(
        Group(*lines),
        title=f"[bold {tcolor}]  INFORMACIÓN COMPLETA  [/bold {tcolor}]",
        border_style=tcolor.replace("bold ", ""),
        width=70,
    ))

    # Esperar tecla
    done = {"v": False}
    def _on_press(key: str):
        done["v"] = True
        stop_listening()

    with keyboard_listener_scope():
        listen_keyboard(on_press=_on_press, sequential=True)


# ──────────────────────────────────────────────
#  Menú principal de inventario
# ──────────────────────────────────────────────
def open_inventory_menu(
    inventory,
    player=None,
    *,
    on_equip=None,    # Callable(player, item, inventory) → bool
    on_use=None,      # Callable(player, item, inventory) → bool
) -> None:
    """
    Abre el menú de inventario interactivo.

    Args:
        inventory : cInventory  – inventario del jugador
        player    : cPlayer     – objeto del jugador (opcional, para mostrar equipado)
        on_equip  : función callback para equipar (None = usa EquipmentManager por defecto)
        on_use    : función callback para usar objeto consumible
    """

    # ── fallback equip ──
    if on_equip is None:
        try:
            from Modules.ModulesFunctions.EquipmentSystem import EquipmentManager
            on_equip = lambda p, i, inv: EquipmentManager.equip_item(p, i, inv)
        except ImportError:
            on_equip = lambda p, i, inv: False

    console = Console()
    MAX_VISIBLE = 14
    PANEL_WIDTH = 80   # detalle

    state = {
        "idx":      0,
        "scroll":   0,
        "message":  "",
        "msg_style":"dim",
        "action":   None,   # "equip" | "use" | "info" | "quit"
        "done":     False,
        "dirty":    True,
    }

    def _slots():
        return getattr(inventory, "slots", [])

    def _current_slot():
        s = _slots()
        if not s:
            return None
        return s[state["idx"]] if 0 <= state["idx"] < len(s) else None

    def _clamp():
        s = _slots()
        n = len(s)
        if n == 0:
            state["idx"] = 0
            state["scroll"] = 0
            return
        state["idx"] = max(0, min(state["idx"], n - 1))
        # scroll follow
        if state["idx"] < state["scroll"]:
            state["scroll"] = state["idx"]
        elif state["idx"] >= state["scroll"] + MAX_VISIBLE:
            state["scroll"] = state["idx"] - MAX_VISIBLE + 1

    def _on_press(key: str):
        if state["done"]:
            return

        k = key.lower()

        if k == "up":
            state["idx"] -= 1
            _clamp()
            state["message"]   = ""
            state["dirty"]     = True

        elif k == "down":
            state["idx"] += 1
            _clamp()
            state["message"]   = ""
            state["dirty"]     = True

        elif k in ("e",):
            slot = _current_slot()
            if slot and _item_type(slot.item) in ("cWeapon", "cEquippableItems", "cTool"):
                state["action"] = "equip"
                state["done"]   = True
                stop_listening()
            else:
                state["message"]   = "  ✗  Este ítem no se puede equipar."
                state["msg_style"] = "bold red"
                state["dirty"]     = True

        elif k == "u":
            slot = _current_slot()
            if slot and _item_type(slot.item) == "cObject":
                state["action"] = "use"
                state["done"]   = True
                stop_listening()
            else:
                state["message"]   = "  ✗  Este ítem no se puede usar directamente."
                state["msg_style"] = "bold red"
                state["dirty"]     = True

        elif k == "i":
            state["action"] = "info"
            state["done"]   = True
            stop_listening()

        elif k in ("q", "esc"):
            state["action"] = "quit"
            state["done"]   = True
            stop_listening()

    # ── render completo ──
    def _full_render() -> Panel:
        slots = _slots()
        slot  = _current_slot()
        
        left  = _render_item_list(slots, state["idx"], state["scroll"], MAX_VISIBLE, player)
        right = _render_item_detail(slot, player)
        bottom = _render_actions(slot, state["message"], state["msg_style"])

        # Columnas izquierda / derecha
        cols = Columns([left, right], expand=True)

        title = Text("  GESTIÓN DE INVENTARIO  ", style="bold bright_white on grey23")
        hint  = Text(
            "  ↑ ↓  Navegar   [E] Equipar   [U] Usar   [I] Info   [Q] Cerrar  ",
            style="dim",
            justify="center",
        )

        return Panel(
            Group(hint, Text(""), cols, bottom),
            title=title,
            border_style="grey50",
        )

    # ── bucle principal ──
    while True:
        state.update({"done": False, "action": None, "dirty": True})
        kb_thread: Optional[threading.Thread] = None

        with keyboard_listener_scope():
            kb_thread = threading.Thread(
                target=listen_keyboard,
                kwargs={"on_press": _on_press, "sequential": True, "delay_second_char": 0.0},
                daemon=True,
            )
            kb_thread.start()

            try:
                with Live(
                    _full_render(),
                    console=console,
                    auto_refresh=False,
                    screen=True,
                ) as live:
                    while not state["done"]:
                        if state["dirty"]:
                            state["dirty"] = False
                            live.update(_full_render(), refresh=True)
                        time.sleep(0.005)
            finally:
                state["done"] = True
                try:
                    stop_listening()
                except Exception:
                    pass
                if kb_thread is not None and kb_thread.is_alive():
                    kb_thread.join(timeout=1.0)
                time.sleep(0.05)

        action = state["action"]

        # ── procesar acciones ──
        if action == "quit":
            console.clear()
            break

        elif action == "info":
            slot = _current_slot()
            if slot:
                _show_item_info_screen(slot.item, console, player)
            # vuelve al loop

        elif action == "equip":
            slot = _current_slot()
            if slot and player is not None:
                item = slot.item
                itype = _item_type(item)
                if itype in ("cWeapon", "cEquippableItems", "cTool"):
                    success = on_equip(player, item, inventory)
                    if success:
                        inventory.remove_item(item, 1)
                        state["message"]   = f"  \u2713  {_item_name(item)} equipado correctamente."
                        state["msg_style"] = "bold bright_green"
                    else:
                        state["message"]   = "  \u2717  No se pudo equipar (o cancelado)."
                        state["msg_style"] = "bold red"
                    _clamp()
            # vuelve al loop

        elif action == "use":
            slot = _current_slot()
            if slot and player is not None:
                item = slot.item
                if _item_type(item) == "cObject":
                    if on_use is not None:
                        result = on_use(player, item, inventory)
                        if result:
                            inventory.remove_item(item, 1)
                            state["message"]   = f"  ✓  Usaste {_item_name(item)}."
                            state["msg_style"] = "bold bright_green"
                        else:
                            state["message"]   = "  ✗  No se pudo usar el ítem."
                            state["msg_style"] = "bold red"
                    else:
                        # Default: aplicar efectos directamente
                        hp_r = getattr(item, "HealthRestore", 0)
                        mp_r = getattr(item, "ManaRestore",   0)
                        healed, restored = 0, 0
                        if hp_r and hasattr(player, "Health") and hasattr(player, "Health_max"):
                            prev = player.Health
                            player.Health = min(player.Health + hp_r, player.Health_max)
                            healed = player.Health - prev
                        if mp_r and hasattr(player, "Mana") and hasattr(player, "Mana_max"):
                            prev = player.Mana
                            player.Mana = min(player.Mana + mp_r, player.Mana_max)
                            restored = player.Mana - prev
                        inventory.remove_item(item, 1)
                        parts = []
                        if healed:   parts.append(f"❤ +{healed} HP")
                        if restored: parts.append(f"💧 +{restored} MP")
                        msg = "  ✓  Usaste " + _item_name(item)
                        if parts: msg += ": " + "  ".join(parts)
                        state["message"]   = msg
                        state["msg_style"] = "bold bright_green"
                    _clamp()
            # vuelve al loop