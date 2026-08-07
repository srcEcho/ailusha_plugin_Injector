"""UninstallElusha.exe — Standalone uninstaller for Elusha Injector.

Cleanup strategy (three-layer):
  1. PRIMARY:   install_manifest.json — complete file list from build, covers everything
  2. FALLBACK:  dynamic Nuitka pattern scan — when manifest is missing
  3. RESIDUAL:  batch file — deletes process-locked files after exit
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

GAME_DIR = os.path.dirname(os.path.abspath(sys.executable
                           if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(GAME_DIR, "elsmod_data", "registry.json")
PLUGINS_DIR = os.path.join(GAME_DIR, "www", "js", "plugins")
MANIFEST_PATH = os.path.join(GAME_DIR, "elsmod_data", "install_manifest.json")


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
    if not os.path.isfile(MANIFEST_PATH):
        return locked

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return locked

    items = manifest.get("items", [])
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

    # Phase A: delete individual files first
    for item in file_items:
        path = os.path.join(GAME_DIR, item)
        try:
            os.remove(path)
        except OSError:
            locked.append(path)

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
        or os.path.isdir(os.path.join(GAME_DIR, "_internal"))
    )
    if not is_injected:
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
    if not paths:
        return

    bat_path = os.path.join(os.environ.get("TEMP", "."), "_elu_cleanup.bat")
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

def uninstall(keep_elsmod_data: bool, keep_plugins: bool):
    """Three-layer cleanup:
    1. Manifest-driven deletion (comprehensive, from build)
    2. Dynamic fallback (pattern scan, if manifest missing)
    3. Residual: collected later by _collect_residual_patterns + batch
    """

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

    # ── Delete version.dll (injector payload) ──
    dll = os.path.join(GAME_DIR, "version.dll")
    if os.path.isfile(dll):
        try:
            os.remove(dll)
        except OSError:
            pass

    # ── Layer 1: Manifest-driven (covers 99% of files) ──
    manifest_locked = _cleanup_from_manifest()

    # ── Layer 2: Dynamic fallback (only when manifest missing) ──
    if not manifest_locked and not os.path.isfile(MANIFEST_PATH):
        _cleanup_dynamic_fallback()
    # Note: when manifest IS present, locked files from it are already
    # in manifest_locked — they'll be handled by batch cleanup.

    # ── ElushaInstaller.exe (PyInstaller, not in Nuitka manifest) ──
    installer = os.path.join(GAME_DIR, "ElushaInstaller.exe")
    if os.path.isfile(installer):
        try:
            os.remove(installer)
        except OSError:
            pass

    # ── Clean up elsmod_data ──
    if not keep_elsmod_data:
        elsmod_dir = os.path.join(GAME_DIR, "elsmod_data")
        if os.path.isdir(elsmod_dir):
            shutil.rmtree(elsmod_dir, ignore_errors=True)

    # ── Clean up empty directories left behind ──
    for d in [PLUGINS_DIR, os.path.join(GAME_DIR, "www", "js"),
              os.path.join(GAME_DIR, "www")]:
        if os.path.isdir(d):
            try:
                if not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass


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
        try:
            uninstall(keep_elsmod.get(), keep_plugins.get())
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return
        messagebox.showinfo("完成", "艾露莎注入器已卸载。")

        # Collect remaining injector-looking files (locked by this process)
        # and schedule batch cleanup after exit.
        residual = _collect_residual_patterns()
        root.destroy()
        _schedule_residual_cleanup(residual)

    ttk.Button(btn_f, text="确认卸载", command=_do_uninstall).pack(
        side=tk.LEFT, padx=8)
    ttk.Button(btn_f, text="取消", command=root.destroy).pack(
        side=tk.LEFT, padx=8)

    root.mainloop()


if __name__ == "__main__":
    main()
