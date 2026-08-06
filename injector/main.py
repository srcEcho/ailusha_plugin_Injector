"""Elusha Injector v1.0 — Main entry point.

Three modes:
  ElushaInjector.exe              → Normal user GUI
  ElushaInjector.exe --dev        → Developer GUI
  ElushaInjector.exe <cmd> ...    → CLI (uses argparse subcommands)
"""
import os
import sys


def _is_cli_mode() -> bool:
    """Check if any CLI subcommand is present in args."""
    cli_commands = {"list", "info", "enable", "disable", "install", "uninstall",
                    "repair", "imported", "pack", "unpack", "template",
                    "deploy", "launch", "config", "tools", "register",
                    "unregister", "version"}
    for arg in sys.argv[1:]:
        if arg in cli_commands:
            return True
    return False


def main():
    # Check for double-click on .elsmod file
    if len(sys.argv) == 2 and sys.argv[1].endswith(".elsmod"):
        from .core import cli_engine
        try:
            cli_engine.cmd_install(sys.argv[1])
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("导入失败", str(e))
        # Fall through to GUI
        from .gui.main_window_pyside6 import run as gui_run
        gui_run()
        return

    # CLI mode: subcommand present
    if _is_cli_mode():
        from .cli import main as cli_main
        cli_main()
        return

    # --dev flag
    dev_mode = "--dev" in sys.argv

    # GUI mode
    from .gui.main_window_pyside6 import run as gui_run
    gui_run(dev_mode=dev_mode)


if __name__ == "__main__":
    main()
