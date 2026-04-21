import time
import threading
from typing import List, Tuple, Optional, Dict, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.live import Live
from rich.align import Align

from Modules.input_utils import keyboard_listener_scope, listen_keyboard, stop_listening

console = Console()

def test_menu_theme(
    theme_name: str,
    title_ascii: str,
    options: List[Tuple[int, str]],
    style_config: dict
) -> int:
    """
    Función de menú adaptada para probar distintos estilos visuales.
    """
    values = [v for v, _ in options]
    index_by_value = {v: i for i, (v, _) in enumerate(options)}
    current_index = 0

    state: Dict[str, Any] = {
        "idx": current_index,
        "buf": "",
        "done": False,
        "selected": None,
        "dirty": True,
    }

    def _render() -> Panel:
        # Header (ASCII Art)
        header = Text.from_markup(f"[{style_config['title_color']}]{title_ascii}[/]")
        if style_config.get('center_title'):
            header = Align.center(header)

        # Table Layout
        t = Table(show_header=False, box=style_config['box_style'], padding=(0, style_config.get('padding', 1)))
        
        # Add columns
        t.add_column("Opción", style=style_config['col_number_style'], justify="right")
        if style_config.get('separator'):
            t.add_column("Sep", style=style_config['col_number_style'])
        t.add_column("Acción", style=style_config['col_text_style'])

        for i, (val, label) in enumerate(options):
            selected = i == state["idx"]
            
            if selected:
                # Estilo de hover/selección
                if style_config.get('cursor_char'):
                    cursor = style_config['cursor_char']
                    opt_str = f"[{style_config['selected_color']}]{cursor} {val}[/]"
                    lab_str = f"[{style_config['selected_color']}]{label}[/]"
                else:
                    opt_str = f"[{style_config['selected_bg']}][{style_config['selected_fg']}]{val}[/][/]"
                    lab_str = f"[{style_config['selected_bg']}][{style_config['selected_fg']}] {label} [/][/]"
            else:
                opt_str = f" {val} "
                lab_str = label

            if style_config.get('separator'):
                sep = style_config['separator'] if not selected else f"[{style_config.get('selected_color', 'white')}]{style_config['separator']}[/]"
                t.add_row(opt_str, sep, lab_str)
            else:
                t.add_row(opt_str, lab_str)

        # Footer
        footer_text = f"[dim]↑/↓ para mover | Enter para seleccionar[/dim]"
        if state["buf"]:
            footer_text += f"\n[dim]Ingresando número: {state['buf']}[/dim]"
            
        footer = Text.from_markup(footer_text)
        if style_config.get('center_title'):
            footer = Align.center(footer)

        return Panel(
            Group(header, "", Align.center(t) if style_config.get('center_menu') else t, "", footer),
            border_style=style_config['border_color'],
            title=f"[{style_config['border_color']}]{theme_name}[/]",
            padding=(1, 2)
        )

    def _on_press(key: str) -> None:
        if state["done"]: return
        if key == "up":
            state["idx"] = (state["idx"] - 1) % len(options)
            state["dirty"] = True
        elif key == "down":
            state["idx"] = (state["idx"] + 1) % len(options)
            state["dirty"] = True
        elif key == "backspace":
            state["buf"] = state["buf"][:-1]
            state["dirty"] = True
        elif key == "enter":
            if state["buf"]:
                try:
                    typed = int(state["buf"])
                except ValueError:
                    state["buf"] = ""
                    state["dirty"] = True
                    return
                if typed in index_by_value:
                    state["selected"] = typed
                    state["done"] = True
                    stop_listening()
                    return
                state["buf"] = ""
                state["dirty"] = True
                return
            state["selected"] = options[state["idx"]][0]
            state["done"] = True
            stop_listening()
        elif key.isdigit():
            state["buf"] += key
            state["dirty"] = True

    kb_thread: Optional[threading.Thread] = None

    with keyboard_listener_scope():
        kb_thread = threading.Thread(
            target=listen_keyboard,
            kwargs={"on_press": _on_press, "sequential": False, "delay_second_char": 0.0},
            daemon=True,
        )
        kb_thread.start()

        try:
            with Live(_render(), console=console, refresh_per_second=30, transient=True) as live:
                while not state["done"]:
                    if state["dirty"]:
                        state["dirty"] = False
                        live.update(_render())
                    time.sleep(0.01)
        finally:
            state["done"] = True
            try: stop_listening()
            except Exception: pass
            if kb_thread and kb_thread.is_alive():
                kb_thread.join(timeout=3.0)
            time.sleep(0.05)

    return state["selected"]

# ==========================================
# DEFINICIÓN DE ESTILOS
# ==========================================

options_mock = [
    (1, "Inspeccionar las zonas"),
    (2, "Ir a una zona"),
    (3, "Tienda"),
    (4, "Inventario"),
    (5, "Mesa de Encantamientos"),
    (6, "Base"),
    (7, "Tablón de Misiones"),
    (0, "Salir del juego")
]

# TEMA 1: Fantasía Clásica (Elegante)
ASCII_FANTASY = '''
  ___  ___  ___ 
 | _ \| _ \/ __|
 |   /|  _/ (_ |
 |_|_\|_|  \___|
'''
STYLE_FANTASY = {
    'title_color': 'bold yellow',
    'border_color': 'yellow',
    'box_style': box.ROUNDED,
    'col_number_style': 'bright_yellow',
    'col_text_style': 'bright_white',
    'selected_color': 'bold bright_yellow',
    'cursor_char': '►',
    'center_title': True,
    'center_menu': True,
    'separator': '·'
}

# TEMA 2: Terminal / Cyberpunk
ASCII_CYBER = '''
████████╗██████╗ ██████╗ ██████╗ ██████╗  ██████╗
╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝
   ██║   ██████╔╝██████╔╝██████╔╝██████╔╝██║  ███╗
   ██║   ██╔═══╝ ██╔═══╝ ██╔══██╗██╔═══╝ ██║   ██║
   ██║   ██║     ██║     ██║  ██║██║     ╚██████╔╝
   ╚═╝   ╚═╝     ╚═╝     ╚═╝  ╚═╝╚═╝      ╚═════╝
'''
STYLE_CYBER = {
    'title_color': 'bold bright_green',
    'border_color': 'cyan',
    'box_style': box.HEAVY,
    'col_number_style': 'green',
    'col_text_style': 'bright_white',
    'selected_bg': 'on bright_cyan',
    'selected_fg': 'black',
    'center_title': False,
    'center_menu': False,
    'separator': '::'
}

# TEMA 3: Minimalista
ASCII_MINIMAL = " T P P R P G "
STYLE_MINIMAL = {
    'title_color': 'bold white',
    'border_color': 'white',
    'box_style': box.SIMPLE,
    'col_number_style': 'dim white',
    'col_text_style': 'white',
    'selected_color': 'bold bright_white',
    'cursor_char': '>',
    'center_title': False,
    'center_menu': False,
    'separator': '|'
}

if __name__ == "__main__":
    console.clear()
    
    # Probar Tema 1
    console.print("\n[info]Iniciando Tema 1: Fantasía Clásica...[/info]")
    time.sleep(1)
    res = test_menu_theme("Tema 1: Fantasía Clásica", ASCII_FANTASY, options_mock, STYLE_FANTASY)
    console.print(f"Seleccionaste la opción: {res}")
    time.sleep(2)
    
    console.clear()
    
    # Probar Tema 2
    console.print("\n[info]Iniciando Tema 2: Cyberpunk / Terminal...[/info]")
    time.sleep(1)
    res = test_menu_theme("Tema 2: Cyberpunk", ASCII_CYBER, options_mock, STYLE_CYBER)
    console.print(f"Seleccionaste la opción: {res}")
    time.sleep(2)
    
    console.clear()
    
    # Probar Tema 3
    console.print("\n[info]Iniciando Tema 3: Minimalista...[/info]")
    time.sleep(1)
    res = test_menu_theme("Tema 3: Minimalista", ASCII_MINIMAL, options_mock, STYLE_MINIMAL)
    console.print(f"Seleccionaste la opción: {res}")
    time.sleep(1)
    
    console.print("\n[bold green]¡Fin de las pruebas![/bold green] Puedes revisar el código de test.py para ver cómo está construido cada estilo.")
