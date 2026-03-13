#!/usr/bin/env python3

import os
import platform
import sys
from pathlib import Path


# ==============================
# Project paths
# ==============================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LOG_PATH = PROJECT_ROOT / "logs" / "logs.txt"


# ==============================
# Privilege utilities
# ==============================

def is_admin() -> bool:
    """Check if the script is running with administrator/root privileges."""
    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        return os.geteuid() == 0


def request_admin() -> None:
    """Restart the script with elevated privileges."""
    system = platform.system()

    if system == "Windows":
        try:
            import ctypes

            if not ctypes.windll.shell32.IsUserAnAdmin():
                print("Requesting administrator privileges...")

                # Absolute path of the current script
                script_path = str(Path(sys.argv[0]).resolve())

                # Build parameters string safely
                params = " ".join(f'"{arg}"' for arg in sys.argv[1:])

                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    sys.executable,
                    f'"{script_path}" {params}',
                    None,
                    1
                )

                sys.exit()

        except Exception as e:
            print(f"Failed to request admin privileges: {e}")
            sys.exit(1)

    else:
        if os.geteuid() != 0:
            print("Requesting root privileges...")
            try:
                os.execvp("sudo", ["sudo", sys.executable] + sys.argv)
            except Exception as e:
                print(f"Failed to request root privileges: {e}")
                sys.exit(1)


# ==============================
# Main logic
# ==============================

def main_c():
    """Main execution entry point."""

    if not is_admin():
        request_admin()
        return  # In Windows case; Linux replaces process

    print("Running with administrator/root privileges.")

    # Clear screen (cross-platform)
    os.system("cls" if platform.system() == "Windows" else "clear")

    print("Privileges confirmed.")
    input("Press Enter to continue...")


