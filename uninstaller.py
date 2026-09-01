"""UninstallElusha.exe — Standalone uninstaller for Elusha Injector.

Cleanup strategy (three-layer):
  1. PRIMARY:   install_manifest.json — complete file list from build, covers everything
  2. FALLBACK:  dynamic Nuitka pattern scan — when manifest is missing
  3. RESIDUAL:  batch file — deletes process-locked files after exit
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# Pre-load ctypes + winreg at module level — these must be in memory BEFORE
# Layer 1 deletes their .pyd/.dll files from disk.  Late imports inside
# _cleanup_elsmod_registry() would crash the process because the .pyd file
# is already gone by the time the function runs.
import ctypes
import winreg

GAME_DIR = os.path.dirname(os.path.abspath(sys.executable
                           if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(GAME_DIR, "elsmod_data", "registry.json")
PLUGINS_DIR = os.path.join(GAME_DIR, "www", "js", "plugins")
MANIFEST_PATH = os.path.join(GAME_DIR, "elsmod_data", "install_manifest.json")


# ── Diagnostic logging ──
_LOG_DIR = r"D:\log"
_LOG_LOCK = __import__('threading').Lock()
def _ulog(msg: str):
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        ts = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}][PID={os.getpid()}] {msg}\n"
        with _LOG_LOCK:
            with open(os.path.join(_LOG_DIR, "uninstaller.log"), "a", encoding="utf-8") as lf:
                lf.write(line)
                lf.flush()
                os.fsync(lf.fileno())
    except Exception:
        pass
_ulog(f"=== START === GAME_DIR={GAME_DIR} frozen={getattr(sys, 'frozen', False)} argv={sys.argv} cwd={os.getcwd()} ===")


# ═══════════════════════════════════════════════════════════════
#  Layer 1: Manifest-driven cleanup (primary)
# ═══════════════════════════════════════════════════════════════

def _cleanup_from_manifest():
    """Delete every file/directory listed in install_manifest.json.

    Returns:
        list of absolute paths that could NOT be deleted (locked by this process).
        Empty list = everything was deleted, or manifest was missing.
    """
    locked = []
    _ulog(f"_cleanup_from_manifest: checking {MANIFEST_PATH}")
    if not os.path.isfile(MANIFEST_PATH):
        _ulog("_cleanup_from_manifest: manifest NOT FOUND")
        return locked

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        _ulog(f"_cleanup_from_manifest: failed to read manifest: {e}")
        return locked

    items = manifest.get("items", [])
    _ulog(f"_cleanup_from_manifest: {len(items)} items in manifest")
    if not items:
        return locked

    # Classify each item
    file_items = []
    dir_items = []
    for item in items:
        path = os.path.join(GAME_DIR, item)
        if os.path.isdir(path):
            dir_items.append(item)
        elif os.path.isfile(path):
            file_items.append(item)
        # else: already deleted, or never existed — skip

    _ulog(f"_cleanup_from_manifest: {len(file_items)} files + {len(dir_items)} dirs to delete")
    # Phase A: delete individual files first
    for item in file_items:
        path = os.path.join(GAME_DIR, item)
        try:
            os.remove(path)
        except OSError as e:
            _ulog(f"_cleanup_from_manifest: LOCKED file: {path}  err={e}")
            locked.append(path)
    _ulog(f"_cleanup_from_manifest: Phase A done, {len(locked)} files locked")

    # Phase B: delete directories (deepest first so children go before parents)
    dir_items.sort(key=lambda d: d.replace("\\", "/").count("/"), reverse=True)
    for item in dir_items:
        path = os.path.join(GAME_DIR, item)
        try:
            shutil.rmtree(path, ignore_errors=True)
        except OSError:
            locked.append(path)

    # Phase C: retry directories — Phase A may have emptied them
    for item in dir_items:
        path = os.path.join(GAME_DIR, item)
        if os.path.isdir(path) and path not in locked:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError:
                if path not in locked:
                    locked.append(path)

    return locked


# ═══════════════════════════════════════════════════════════════
#  Layer 2: Dynamic Nuitka pattern scan (fallback)
# ═══════════════════════════════════════════════════════════════

def _is_nuitka_installation():
    """Return True if the game directory looks like it has a Nuitka injector."""
    return os.path.isfile(os.path.join(GAME_DIR, "python310.dll"))


def _cleanup_dynamic_fallback():
    """Pattern-based cleanup used when install_manifest.json is missing.

    Scans for known Nuitka / PyInstaller file patterns and deletes them.
    Returns list of locked paths that couldn't be deleted.
    """
    locked = []

    # ── PyInstaller onedir runtime ──
    internal = os.path.join(GAME_DIR, "_internal")
    if os.path.isdir(internal):
        try:
            shutil.rmtree(internal, ignore_errors=True)
        except OSError:
            locked.append(internal)

    if not _is_nuitka_installation():
        # Not Nuitka; still try to delete known EXEs
        for exe in ["ElushaInjector.exe", "UninstallElusha.exe",
                     "ElushaInstaller.exe"]:
            ep = os.path.join(GAME_DIR, exe)
            if os.path.isfile(ep):
                try:
                    os.remove(ep)
                except OSError:
                    locked.append(ep)
        return locked

    # ── Nuitka known directories ──
    for d in ["injector", "PySide6", "shiboken6", "tcl", "tk", "tcl8"]:
        dp = os.path.join(GAME_DIR, d)
        if os.path.isdir(dp):
            try:
                shutil.rmtree(dp, ignore_errors=True)
            except OSError:
                locked.append(dp)

    # ── Nuitka known file patterns ──
    _delete_patterns(locked,
        "*.pyd",
        "python3.dll", "python310.dll",
        "qt6*.dll", "pyside6*.dll", "shiboken6*.dll",
        "libcrypto-*.dll", "libffi-*.dll", "libssl-*.dll",
        "msvcp140*.dll", "msvcp140_codecvt*.dll",
        "vcruntime140*.dll",
        "tcl86t.dll", "tk86t.dll",
        "select.pyd", "unicodedata.pyd",
    )

    # ── Known EXEs ──
    for exe in ["ElushaInjector.exe", "UninstallElusha.exe",
                 "ElushaInstaller.exe"]:
        ep = os.path.join(GAME_DIR, exe)
        if os.path.isfile(ep):
            try:
                os.remove(ep)
            except OSError:
                locked.append(ep)

    return locked


def _delete_patterns(locked, *patterns):
    """Delete all files in GAME_DIR matching the given glob patterns."""
    for pattern in patterns:
        for fp in glob.glob(os.path.join(GAME_DIR, pattern)):
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    if fp not in locked:
                        locked.append(fp)


# ═══════════════════════════════════════════════════════════════
#  Layer 3: Batch file residual cleanup
# ═══════════════════════════════════════════════════════════════

def _collect_residual_patterns():
    """Walk GAME_DIR and collect remaining injector-looking paths for batch cleanup.

    Only activates when Nuitka/PyInstaller markers are present, to avoid
    touching non-injector directories.
    """
    paths = []

    is_injected = (
        _is_nuitka_installation()
        or os.path.isfile(os.path.join(GAME_DIR, "ElushaInjector.exe"))
        or os.path.isfile(os.path.join(GAME_DIR, "UninstallElusha.exe"))
        or os.path.isdir(os.path.join(GAME_DIR, "_internal"))
    )
    _ulog(f"_collect_residual_patterns: is_injected={is_injected} "
          f"(nuitka={_is_nuitka_installation()} injector_exe={os.path.isfile(os.path.join(GAME_DIR, 'ElushaInjector.exe'))} "
          f"uninstaller_exe={os.path.isfile(os.path.join(GAME_DIR, 'UninstallElusha.exe'))} "
          f"internal_dir={os.path.isdir(os.path.join(GAME_DIR, '_internal'))})")
    if not is_injected:
        _ulog("_collect_residual_patterns: not injected, returning empty")
        return paths

    # Scan for injector patterns (broader than fallback — catches everything)
    for pattern in [
        "*.pyd", "python3.dll", "python310.dll",
        "qt6*.dll", "pyside6*.dll", "shiboken6*.dll",
        "libcrypto-*.dll", "libffi-*.dll", "libssl-*.dll",
        "msvcp140*.dll", "msvcp140_codecvt*.dll",
        "vcruntime140*.dll",
        "tcl86t.dll", "tk86t.dll",
        "select.pyd", "unicodedata.pyd",
    ]:
        for fp in glob.glob(os.path.join(GAME_DIR, pattern)):
            if os.path.isfile(fp) and fp not in paths:
                paths.append(fp)

    # Directories
    for d in ["injector", "PySide6", "shiboken6", "_internal",
              "tcl", "tk", "tcl8"]:
        dp = os.path.join(GAME_DIR, d)
        if os.path.isdir(dp) and dp not in paths:
            paths.append(dp)

    # EXEs
    for exe in ["ElushaInjector.exe", "UninstallElusha.exe",
                 "ElushaInstaller.exe"]:
        ep = os.path.join(GAME_DIR, exe)
        if os.path.isfile(ep) and ep not in paths:
            paths.append(ep)

    return paths


def _schedule_residual_cleanup(paths):
    """Write and launch a batch file that deletes *paths* after this process exits.

    The batch loops until every file/directory is gone, then self-destructs.
    Uses TEMP so it won't be blocked by game-directory file locks.
    """
    _ulog(f"_schedule_residual_cleanup: {len(paths)} paths to clean")
    for p in paths:
        _ulog(f"  batch_target: {p}")
    if not paths:
        _ulog("_schedule_residual_cleanup: empty, skipping")
        return

    bat_path = os.path.join(os.environ.get("TEMP", "."), "_elu_cleanup.bat")
    _ulog(f"_schedule_residual_cleanup: writing batch to {bat_path}")
    with open(bat_path, "w") as f:
        f.write("@echo off\r\n"
                "setlocal enabledelayedexpansion\r\n"
                ":retry\r\n"
                "timeout /t 2 /nobreak >nul\r\n")
        for p in paths:
            if os.path.isdir(p):
                f.write(f'rmdir /s /q "{p}" 2>nul\r\n')
            else:
                f.write(f'del /f /q "{p}" 2>nul\r\n')
        f.write("set \"any_left=0\"\r\n")
        for p in paths:
            f.write(f'if exist "{p}" set "any_left=1"\r\n')
        f.write('if "!any_left!"=="1" goto retry\r\n'
                'del /f /q "%~f0"\r\n')

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )


# ═══════════════════════════════════════════════════════════════
#  Main uninstall logic
# ═══════════════════════════════════════════════════════════════

def _cleanup_elsmod_registry():
    """Remove .elsmod ProgID association registered by the injector (HKCU Classes only).

    Failure is non-critical — the caller wraps this in try/except to ensure
    registry issues never block file cleanup.
    """
    _ulog("_cleanup_elsmod_registry: start")
    ELSMOD_PROGID = "ElushaPlugin.elsmod"

    # .elsmod → ProgID
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.elsmod")
        _ulog("_cleanup_elsmod_registry: deleted .elsmod key")
    except OSError as e:
        _ulog(f"_cleanup_elsmod_registry: .elsmod key skip ({e})")

    # ProgID tree (DefaultIcon, shell/open/command, shell/open, shell)
    for sub in [
        rf"Software\Classes\{ELSMOD_PROGID}\shell\open\command",
        rf"Software\Classes\{ELSMOD_PROGID}\shell\open",
        rf"Software\Classes\{ELSMOD_PROGID}\shell",
        rf"Software\Classes\{ELSMOD_PROGID}\DefaultIcon",
        rf"Software\Classes\{ELSMOD_PROGID}",
    ]:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            _ulog(f"_cleanup_elsmod_registry: deleted {sub}")
        except OSError as e:
            _ulog(f"_cleanup_elsmod_registry: skip {sub} ({e})")

    _ulog("_cleanup_elsmod_registry: calling SHChangeNotify")
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        _ulog("_cleanup_elsmod_registry: SHChangeNotify done")
    except Exception as e:
        _ulog(f"_cleanup_elsmod_registry: SHChangeNotify error ({e})")

    _ulog("_cleanup_elsmod_registry: end")


def _restore_plugins_js():
    """Restore original plugins.js from backup and strip any mod plugin entries.

    Restores the backup (unpacked mode), then strips every entry whose
    ``"name"`` matches a mod plugin in the registry.  This is belt-and-
    suspenders: even if the backup was created *after* mod plugins were
    injected (corrupted backup), the result will be clean.
    """
    target = os.path.join(GAME_DIR, "www", "js", "plugins.js")

    # Phase 1 — Restore from backup (if available)
    backup = os.path.join(GAME_DIR, "elsmod_data", "originals",
                          "www", "js", "plugins.js")
    if os.path.isfile(backup):
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(backup, target)
            _ulog("_restore_plugins_js: restored original plugins.js from backup")
        except OSError as e:
            _ulog(f"_restore_plugins_js: FAILED — {e}")
            return

    # Phase 2 — Strip mod plugin entries
    if not os.path.isfile(target):
        return

    # Collect mod plugin names from registry
    mod_names = set()
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            reg = json.load(f)
        for rec in reg.get("records", []):
            mod_names.add(rec["name"])
    except Exception:
        pass

    if not mod_names:
        return

    with open(target, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        # Each plugin entry is a single-line JSON object
        if stripped.startswith("{") and '"name"' in stripped:
            m = re.search(r'"name"\s*:\s*"([^"]+)"', stripped)
            if m and m.group(1) in mod_names:
                removed += 1
                continue
        new_lines.append(line)

    if removed:
        with open(target, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        _ulog(f"_restore_plugins_js: stripped {removed} mod plugin entries")


def uninstall(keep_elsmod_data: bool, keep_plugins: bool):
    """Three-layer cleanup. Returns list of locked paths for batch cleanup."""
    _ulog(f"uninstall: keep_elsmod_data={keep_elsmod_data} keep_plugins={keep_plugins}")

    # ── Delete plugin files ──
    if not keep_plugins:
        # From registry
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                reg = json.load(f)
            for rec in reg.get("records", []):
                for fn in rec.get("files", []):
                    fp = os.path.join(PLUGINS_DIR, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
        except Exception:
            pass

        # Bootstrap JS files
        if os.path.isdir(PLUGINS_DIR):
            for fn in os.listdir(PLUGINS_DIR):
                if fn.endswith("_bootstrap.js"):
                    fp = os.path.join(PLUGINS_DIR, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except OSError:
                            pass

    # ── Delete winhttp.dll (current injector payload) ──
    # The deploy step sets the hook DLL read-only, so clear that bit before removing.
    for _dll_name in ("winhttp.dll", "version.dll"):  # version.dll = legacy installs
        _dll = os.path.join(GAME_DIR, _dll_name)
        if os.path.isfile(_dll):
            try:
                import stat
                os.chmod(_dll, os.stat(_dll).st_mode | stat.S_IWRITE)
                os.remove(_dll)
            except OSError:
                pass

    # ── Restore original plugins.js for unpacked mode ──
    _restore_plugins_js()

    # ── Layer 1: Manifest-driven (covers 99% of files) ──
    _ulog("uninstall: Layer 1 — manifest cleanup")
    manifest_locked = _cleanup_from_manifest()
    _ulog(f"uninstall: Layer 1 done — {len(manifest_locked)} locked: {[os.path.basename(p) for p in manifest_locked]}")

    # ── Layer 2: Dynamic fallback (only when manifest missing) ──
    if not manifest_locked and not os.path.isfile(MANIFEST_PATH):
        _ulog("uninstall: Layer 2 — dynamic fallback (manifest missing, nothing locked)")
        _cleanup_dynamic_fallback()
    else:
        _ulog(f"uninstall: Layer 2 — skipped (manifest_locked={len(manifest_locked)}, manifest_exists={os.path.isfile(MANIFEST_PATH)})")

    # ── ElushaInstaller.exe (PyInstaller, not in Nuitka manifest) ──
    _ulog("uninstall: deleting ElushaInstaller.exe if present")
    installer = os.path.join(GAME_DIR, "ElushaInstaller.exe")
    if os.path.isfile(installer):
        try:
            os.remove(installer)
            _ulog("uninstall: ElushaInstaller.exe deleted")
        except OSError:
            manifest_locked.append(installer)
            _ulog(f"uninstall: ElushaInstaller.exe LOCKED")

    # ── Clean up elsmod_data ──
    _ulog(f"uninstall: elsmod_data cleanup — keep_elsmod_data={keep_elsmod_data}")
    if not keep_elsmod_data:
        elsmod_dir = os.path.join(GAME_DIR, "elsmod_data")
        _ulog(f"uninstall: elsmod_dir={elsmod_dir} isdir={os.path.isdir(elsmod_dir)}")
        if os.path.isdir(elsmod_dir):
            try:
                shutil.rmtree(elsmod_dir, ignore_errors=True)
                _ulog("uninstall: elsmod_data rmtree done")
            except Exception as _e:
                _ulog(f"uninstall: elsmod_data rmtree ERROR: {type(_e).__name__}: {_e}")

    # ── Clean up .elsmod registry association (non-critical) ──
    _ulog("uninstall: cleaning up .elsmod registry")
    try:
        _cleanup_elsmod_registry()
        _ulog("uninstall: registry cleanup done")
    except Exception as _e:
        _ulog(f"uninstall: registry cleanup ERROR: {type(_e).__name__}: {_e}")

    # ── Clean up empty directories left behind ──
    _ulog("uninstall: cleaning up empty directories")
    for d in [PLUGINS_DIR, os.path.join(GAME_DIR, "www", "js"),
              os.path.join(GAME_DIR, "www")]:
        if os.path.isdir(d):
            try:
                if not os.listdir(d):
                    os.rmdir(d)
                    _ulog(f"uninstall: removed empty dir {d}")
            except OSError as _e:
                _ulog(f"uninstall: empty dir cleanup skipping {d}: {_e}")

    _ulog(f"uninstall: RETURNING manifest_locked={[os.path.basename(p) for p in manifest_locked]}")
    return manifest_locked


# ═══════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.title("卸载艾露莎注入器")
    root.geometry("420x240")
    root.resizable(False, False)

    # Window icon
    try:
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "injector", "Uninstall_logo.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)
    except Exception:
        pass

    ttk.Label(root, text="卸载艾露莎注入器",
              font=("", 14, "bold")).pack(pady=(16, 8))
    ttk.Label(root, text="将卸载注入器和所有已安装 + 已下载的插件",
              font=("", 9)).pack()

    keep_elsmod = tk.BooleanVar(value=False)
    keep_plugins = tk.BooleanVar(value=False)

    ttk.Checkbutton(root, text="保留已下载的插件（保留 elsmod_data/）",
                    variable=keep_elsmod).pack(anchor=tk.W, padx=40, pady=(16, 4))
    ttk.Checkbutton(root, text="保留已加载的插件（保留 www/js/plugins/）",
                    variable=keep_plugins).pack(anchor=tk.W, padx=40)

    btn_f = ttk.Frame(root)
    btn_f.pack(pady=20)

    def _do_uninstall():
        _ulog("_do_uninstall: button clicked")
        try:
            locked = uninstall(keep_elsmod.get(), keep_plugins.get())
        except Exception as e:
            _ulog(f"_do_uninstall: ERROR: {e}")
            messagebox.showerror("错误", str(e))
            return
        messagebox.showinfo("完成", "艾露莎注入器已卸载。")

        # Collect remaining injector-looking files (locked by this process)
        # and schedule batch cleanup after exit.
        # Each step wrapped individually — batch cleanup MUST run regardless.
        locked = locked if isinstance(locked, list) else []
        _ulog(f"_do_uninstall: manifest_locked={len(locked)} paths")
        residual = []
        try:
            residual = _collect_residual_patterns()
            _ulog(f"_do_uninstall: residual_patterns={len(residual)} paths")
        except Exception as _e2:
            _ulog(f"_do_uninstall: _collect_residual_patterns CRASHED: {type(_e2).__name__}: {_e2}")
        all_locked = locked + [p for p in residual if p not in locked]
        _ulog(f"_do_uninstall: combined={len(all_locked)} paths for batch cleanup")
        try:
            _schedule_residual_cleanup(all_locked)
            _ulog("_do_uninstall: batch cleanup SCHEDULED")
        except Exception as _e3:
            _ulog(f"_do_uninstall: _schedule_residual_cleanup CRASHED: {type(_e3).__name__}: {_e3}")
        try:
            root.destroy()
        except Exception:
            pass

    ttk.Button(btn_f, text="确认卸载", command=_do_uninstall).pack(
        side=tk.LEFT, padx=8)
    ttk.Button(btn_f, text="取消", command=root.destroy).pack(
        side=tk.LEFT, padx=8)

    root.mainloop()


if __name__ == "__main__":
    main()
