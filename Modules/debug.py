import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict


LOGGER_NAME = "TPPRPG"


def _strip_rich_markup(text: str) -> str:
    return re.sub(r"\[/?[^\]]+\]", "", text)


def setup_logging(debug_enabled: bool = False) -> logging.Logger:
    """Configure project-wide logging into logs/ directory."""
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    date_suffix = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(
        os.path.join("logs", f"tpprpg_{date_suffix}.log"),
        mode="a",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(file_handler)

    if debug_enabled:
        logger.info("Debug mode enabled.")
    else:
        logger.info("Logging initialized.")

    return logger


def attach_console_logging(console: Any, logger: logging.Logger) -> None:
    """Patch console.print so info/warning/error-like output is logged too."""
    original_print = console.print

    def logged_print(*args, **kwargs):
        message = " ".join(str(arg) for arg in args)
        plain_message = _strip_rich_markup(message).strip()
        lower_message = plain_message.lower()

        if "[danger]" in message or "[red]" in message or "error" in lower_message:
            logger.error("Console error message: %s", plain_message)
        elif "[warning]" in message or "warning" in lower_message:
            logger.warning("Console warning message: %s", plain_message)
        elif "[success]" in message or "[green]" in message:
            logger.info("Console success message: %s", plain_message)
        elif "[info]" in message:
            logger.info("Console info message: %s", plain_message)

        return original_print(*args, **kwargs)

    console.print = logged_print


def install_exception_hooks(logger: logging.Logger) -> None:
    """Capture unhandled exceptions."""

    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return sys.__excepthook__(exc_type, exc_value, exc_traceback)
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _handle_exception


def log_imported_modules(logger: logging.Logger) -> None:
    """Log currently imported modules for debug mode."""
    module_names = sorted(name for name in sys.modules.keys() if name and not name.startswith("_"))
    logger.debug("Imported modules count: %d", len(module_names))
    for module_name in module_names:
        logger.debug("Imported module: %s", module_name)


def _safe_attrs(obj: Any, max_items: int = 40) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    count = 0
    for attr in dir(obj):
        if attr.startswith("__"):
            continue
        try:
            value = getattr(obj, attr)
        except Exception:
            continue
        if callable(value):
            continue
        data[attr] = value
        count += 1
        if count >= max_items:
            break
    return data


def dump_debug_snapshot(
    *,
    player: Any,
    inventory: Any,
    mod_loader: Any,
    mod_api: Any,
    current_state: Any,
    chosen_area: Any,
) -> str:
    """Build a compact runtime snapshot for debug menu option."""
    loaded_mods = list(getattr(mod_loader, "loaded_mods", {}).keys())
    custom_commands = list(getattr(mod_api, "custom_commands", {}).keys())
    player_data = _safe_attrs(player)
    inventory_size = len(getattr(inventory, "Objects", []))

    lines = [
        "=== DEBUG SNAPSHOT ===",
        f"State: {current_state}",
        f"Chosen area: {chosen_area}",
        f"Loaded mods ({len(loaded_mods)}): {loaded_mods}",
        f"Custom mod commands ({len(custom_commands)}): {custom_commands}",
        f"Inventory objects: {inventory_size}",
        "Player variables:",
    ]

    for key, value in player_data.items():
        lines.append(f"  - {key}: {value}")

    return "\n".join(lines)
