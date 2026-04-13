from contextlib import contextmanager
from sshkeyboard import listen_keyboard, stop_listening
from typing import List, Optional, Tuple, Any, Dict
import threading
import time

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.theme import Theme
from rich.live import Live

_MENU_THEME = Theme(
    {
        "info": "dim cyan",
        "warning": "magenta",
        "danger": "bold red",
        "success": "bold green",
        "menu_title": "bold yellow",
        "menu_option": "bright_white",
    }
)

_MENU_LISTENER_LOCK = threading.Lock()


def _stop_keyboard_listener_and_wait() -> None:
    """sshkeyboard solo permite un listener; hay que esperar a que termine el hilo."""
    try:
        stop_listening()
    except Exception:
        pass
    time.sleep(0.08)


@contextmanager
def keyboard_listener_scope():
    """
    Serializa cualquier uso de listen_keyboard (menús, wait_for_enter, minijuegos).
    Evita: AssertionError: Only one listener allowed at a time
    """
    with _MENU_LISTENER_LOCK:
        _stop_keyboard_listener_and_wait()
        try:
            yield
        finally:
            _stop_keyboard_listener_and_wait()


def select_option_with_arrows(prompt: str, valid_options: List[int], default_option=None) -> int:
    """Select option using up/down arrows or numeric input (rápido y continuo)."""
    if not valid_options:
        raise ValueError("valid_options no puede estar vacio")

    ordered_options = sorted(set(valid_options))
    if default_option in ordered_options:
        current_index = ordered_options.index(default_option)
    else:
        current_index = 0

    number_buffer = {"value": ""}
    selected = {"value": None}

    def _render_prompt() -> None:
        current = ordered_options[current_index]
        if number_buffer["value"]:
            print(
                f"\r{prompt}[↑/↓ + Enter] o numero: {number_buffer['value']} (actual: {current})",
                end="",
                flush=True,
            )
        else:
            print(
                f"\r{prompt}[↑/↓ + Enter] (actual: {current})",
                end="",
                flush=True,
            )

    def _on_press(key: str) -> None:
        nonlocal current_index
        if key == "up":
            current_index = (current_index - 1) % len(ordered_options)
            _render_prompt()
        elif key == "down":
            current_index = (current_index + 1) % len(ordered_options)
            _render_prompt()
        elif key == "backspace":
            number_buffer["value"] = number_buffer["value"][:-1]
            _render_prompt()
        elif key == "enter":
            if number_buffer["value"]:
                typed = int(number_buffer["value"])
                if typed in ordered_options:
                    selected["value"] = typed
                    stop_listening()
                    return
                number_buffer["value"] = ""
                _render_prompt()
                return
            selected["value"] = ordered_options[current_index]
            stop_listening()
        elif key.isdigit():
            number_buffer["value"] += key
            _render_prompt()

    _render_prompt()
    with keyboard_listener_scope():
        # sequential=False permite que múltiples pulsaciones rápidas se procesen mejor
        listen_keyboard(on_press=_on_press, sequential=False)
    print()

    if selected["value"] is None:
        return ordered_options[current_index]
    return selected["value"]


def interactive_menu_select(
    title: str,
    options: List[Tuple[int, str]],
    prompt: str = "Selecciona una opción: ",
    subtitle: Optional[str] = None,
    default_value: Optional[int] = None,
    allow_zero_shortcut: bool = True,
    border_style: str = "menu_title",
) -> int:
    """
    Menú interactivo (Rich) con selección invertida como `abc.py`:
    - Flechas ↑/↓ para mover selección
    - Enter para confirmar
    - Input numérico opcional (buffer) para seleccionar por número
    """
    if not options:
        raise ValueError("options no puede estar vacio")

    console = Console(theme=_MENU_THEME)
    values = [v for v, _ in options]
    index_by_value = {v: i for i, (v, _) in enumerate(options)}

    current_index = 0
    if default_value is not None and default_value in index_by_value:
        current_index = index_by_value[default_value]

    state: Dict[str, Any] = {
        "idx": current_index,
        "buf": "",
        "done": False,
        "selected": None,
        "dirty": True,
    }

    def _render() -> Panel:
        header = Text.from_markup(f"[bold]{title}[/bold]")
        if subtitle:
            header = Group(header, Text.from_markup(f"[dim]{subtitle}[/dim]"))

        t = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        t.add_column("Opción", style="bright_white", width=6)
        t.add_column("Acción", style="bright_white")

        for i, (val, label) in enumerate(options):
            selected = i == state["idx"]
            if selected:
                opt = f"[black on white]> {val} <[/black on white]"
                lab = f"[black on white] {label} [/black on white]"
            else:
                opt = f"[{val}]"
                lab = label
            t.add_row(opt, lab)

        footer = Text.from_markup(
            f"[dim]{prompt}[/dim]"
            + (f"[dim][↑/↓ + Enter] o número: {state['buf']}[/dim]" if state["buf"] else "[dim][↑/↓ + Enter] o número[/dim]")
        )
        return Panel(Group(header, "", t, "", footer), border_style=border_style)

    def _on_press(key: str) -> None:
        if state["done"]:
            return
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
                if allow_zero_shortcut and typed == 0 and 0 in index_by_value:
                    state["selected"] = 0
                    state["done"] = True
                    stop_listening()
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
            with Live(
                _render(),
                console=console,
                refresh_per_second=30,
                transient=True,
            ) as live:
                while not state["done"]:
                    if state["dirty"]:
                        state["dirty"] = False
                        live.update(_render())
                    time.sleep(0.01)
        finally:
            state["done"] = True
            try:
                stop_listening()
            except Exception:
                pass
            if kb_thread is not None and kb_thread.is_alive():
                kb_thread.join(timeout=3.0)
            time.sleep(0.05)

    if state["selected"] is None:
        return options[state["idx"]][0]
    return int(state["selected"])


def wait_for_enter(Message: Optional[str] = None) -> None:
    done = {"pressed": False}
    if Message:
        print(Message)

    def _on_press(key: str) -> None:
        if key == "enter":
            done["pressed"] = True
            stop_listening()

    with keyboard_listener_scope():
        listen_keyboard(on_press=_on_press, sequential=True)
