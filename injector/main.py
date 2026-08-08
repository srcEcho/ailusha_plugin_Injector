"""Elusha Injector v1.0 — Main entry point.

Three modes:
  ElushaInjector.exe              → Normal user GUI
  ElushaInjector.exe --dev        → Developer GUI
  ElushaInjector.exe <cmd> ...    → CLI (uses argparse subcommands)
"""
import os
import sys

# ── Diagnostic logging (writes to elsmod_data/logs/ under game directory) ──
def _get_log_dir():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    return os.path.join(os.path.dirname(os.path.abspath(exe_path)), "elsmod_data", "logs")

_LOG_LOCK = __import__('threading').Lock()
def _ilog(msg: str):
    try:
        d = _get_log_dir()
        os.makedirs(d, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}][PID={os.getpid()}] {msg}\n"
        with _LOG_LOCK:
            with open(os.path.join(d, "injector.log"), "a", encoding="utf-8") as lf:
                lf.write(line)
    except Exception:
        pass
_ilog(f"=== START === argv={sys.argv} cwd={os.getcwd()} frozen={getattr(sys, 'frozen', False)} executable={sys.executable} ===")


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
        _ilog(f".elsmod double-click detected: {sys.argv[1]}")
        from injector.core import cli_engine
        try:
            _ilog("calling cmd_install...")
            cli_engine.cmd_install(sys.argv[1])
            _ilog("cmd_install succeeded")
        except BaseException as e:
            _ilog(f"cmd_install FAILED: {type(e).__name__}: {e}")
            import tkinter.messagebox as mb
            mb.showerror("导入失败", str(e))
            # If game dir detection failed, still launch GUI so user sees the error
            from injector.gui.main_window_pyside6 import run as gui_run
            _ilog("launching GUI after install failure")
            gui_run()
            return
        # Fall through to GUI (install succeeded, show the updated plugin list)
        _ilog("launching GUI after successful install")
        from injector.gui.main_window_pyside6 import run as gui_run
        gui_run()
        return

    # CLI mode: subcommand present
    if _is_cli_mode():
        from injector.cli import main as cli_main
        cli_main()
        return

    # --dev flag
    dev_mode = "--dev" in sys.argv

    # GUI mode
    _ilog(f"GUI mode (manual launch) dev_mode={dev_mode}")
    from injector.gui.main_window_pyside6 import run as gui_run
    gui_run(dev_mode=dev_mode)


if __name__ == "__main__":
    main()
