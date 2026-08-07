"""UninstallElusha.exe — Standalone uninstaller for Elusha Injector."""
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

GAME_DIR = os.path.dirname(os.path.abspath(sys.executable)
                           if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(GAME_DIR, "elsmod_data", "registry.json")
PLUGINS_DIR = os.path.join(GAME_DIR, "www", "js", "plugins")
MANIFEST_PATH = os.path.join(GAME_DIR, "elsmod_data", "install_manifest.json")


def load_registry():
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _collect_injector_paths():
    """Return a list of all known injector file/directory paths that still exist.
    Used as a comprehensive safety net for residual cleanup via batch file.
    Covers Nuitka standalone, PyInstaller, Tcl/Tk runtime, and injector EXEs."""
    paths = []

    # EXEs
    for exe in ["ElushaInjector.exe", "UninstallElusha.exe", "ElushaInstaller.exe"]:
        p = os.path.join(GAME_DIR, exe)
        if os.path.isfile(p):
            paths.append(p)

    # DLLs — Nuitka + Tcl/Tk runtime
    for dll in ["python3.dll", "python310.dll",
                 "libcrypto-1_1.dll", "libffi-7.dll",
                 "pyside6.abi3.dll", "shiboken6.abi3.dll",
                 "qt6core.dll", "qt6gui.dll", "qt6network.dll",
                 "qt6pdf.dll", "qt6svg.dll", "qt6widgets.dll",
                 "tcl86t.dll", "tk86t.dll"]:
        p = os.path.join(GAME_DIR, dll)
        if os.path.isfile(p):
            paths.append(p)

    # .pyd files
    for pyd in ["_bz2.pyd", "_ctypes.pyd", "_decimal.pyd",
                 "_hashlib.pyd", "_lzma.pyd", "_socket.pyd",
                 "_tkinter.pyd", "select.pyd", "unicodedata.pyd"]:
        p = os.path.join(GAME_DIR, pyd)
        if os.path.isfile(p):
            paths.append(p)

    # VC++ runtime
    for vc in ["msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
                "vcruntime140.dll", "vcruntime140_1.dll"]:
        p = os.path.join(GAME_DIR, vc)
        if os.path.isfile(p):
            paths.append(p)

    # version.dll (injector payload)
    vdll = os.path.join(GAME_DIR, "version.dll")
    if os.path.isfile(vdll):
        paths.append(vdll)

    # Directories
    for d in ["injector", "PySide6", "shiboken6", "_internal",
              "tcl", "tk", "tcl8"]:
        dp = os.path.join(GAME_DIR, d)
        if os.path.isdir(dp):
            paths.append(dp)

    return paths


def _schedule_residual_cleanup(paths):
    """Write a batch file that deletes all *paths* after this process exits.
    Loops until every path is gone, then self-destructs."""
    if not paths:
        return
    bat_path = os.path.join(os.environ.get("TEMP", "."), "_elu_cleanup.bat")
    with open(bat_path, "w") as f:
        f.write("@echo off\r\n"
                "setlocal enabledelayedexpansion\r\n"
                ":retry\r\n"
                "timeout /t 1 /nobreak >nul\r\n")
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
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=0x08000000)  # CREATE_NO_WINDOW


def _cleanup_from_manifest() -> bool:
    """Delete files listed in install manifest. Returns True if manifest was found/used."""
    if not os.path.isfile(MANIFEST_PATH):
        return False
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for item in manifest.get("items", []):
            path = os.path.join(GAME_DIR, item)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                elif os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass  # file in use (e.g. self), skip
        return True
    except Exception:
        return False


def _cleanup_legacy_fallback():
    """Fallback cleanup when no manifest exists, or as safety net after manifest.
    Handles both PyInstaller (_internal/) and Nuitka (flat) layouts.
    Includes Tcl/Tk runtime files from tk-inter plugin."""
    # PyInstaller onedir runtime
    internal = os.path.join(GAME_DIR, "_internal")
    if os.path.isdir(internal):
        shutil.rmtree(internal, ignore_errors=True)

    # PyInstaller / Nuitka injector EXE
    injector = os.path.join(GAME_DIR, "ElushaInjector.exe")
    if os.path.isfile(injector):
        try:
            os.remove(injector)
        except OSError:
            pass

    # Nuitka: detect by presence of python310.dll or qt6core.dll in game root
    nuitka_marker = os.path.join(GAME_DIR, "python310.dll")
    is_nuitka = os.path.isfile(nuitka_marker)

    if is_nuitka:
        # Nuitka runtime directories (including Tcl/Tk from tk-inter plugin)
        for d in ["injector", "PySide6", "shiboken6",
                  "tcl", "tk", "tcl8"]:
            dp = os.path.join(GAME_DIR, d)
            if os.path.isdir(dp):
                shutil.rmtree(dp, ignore_errors=True)

        # Nuitka runtime DLLs (including Tcl/Tk)
        for dll in ["python3.dll", "python310.dll", "libcrypto-1_1.dll",
                     "libffi-7.dll", "pyside6.abi3.dll", "shiboken6.abi3.dll",
                     "qt6core.dll", "qt6gui.dll", "qt6network.dll",
                     "qt6pdf.dll", "qt6svg.dll", "qt6widgets.dll",
                     "tcl86t.dll", "tk86t.dll"]:
            dp = os.path.join(GAME_DIR, dll)
            if os.path.isfile(dp):
                try:
                    os.remove(dp)
                except OSError:
                    pass

        # Nuitka .pyd files
        for pyd in ["_bz2.pyd", "_ctypes.pyd", "_decimal.pyd",
                     "_hashlib.pyd", "_lzma.pyd", "_socket.pyd",
                     "_tkinter.pyd", "select.pyd", "unicodedata.pyd"]:
            pp = os.path.join(GAME_DIR, pyd)
            if os.path.isfile(pp):
                try:
                    os.remove(pp)
                except OSError:
                    pass

        # VC++ runtime
        for vc in ["msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
                    "vcruntime140.dll", "vcruntime140_1.dll"]:
            vp = os.path.join(GAME_DIR, vc)
            if os.path.isfile(vp):
                try:
                    os.remove(vp)
                except OSError:
                    pass


def uninstall(keep_elsmod_data: bool, keep_plugins: bool):
    reg = load_registry()

    # Delete plugin files
    if not keep_plugins and reg:
        for rec in reg.get("records", []):
            for f in rec.get("files", []):
                fp = os.path.join(PLUGINS_DIR, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass

    # Delete version.dll
    dll = os.path.join(GAME_DIR, "version.dll")
    if os.path.isfile(dll):
        try:
            os.remove(dll)
        except OSError:
            pass

    # Delete injector runtime files — always run BOTH manifest and fallback.
    # Manifest handles explicitly tracked items; fallback catches anything
    # the manifest missed (e.g. Tcl/Tk files merged into ElushaInjector/).
    # Files locked by the running process will be caught by residual batch.
    _cleanup_from_manifest()
    _cleanup_legacy_fallback()

    # ElushaInstaller.exe may or may not be present
    installer = os.path.join(GAME_DIR, "ElushaInstaller.exe")
    if os.path.isfile(installer):
        try:
            os.remove(installer)
        except OSError:
            pass

    # Delete bootstrap JS files left by deploy
    if os.path.isdir(PLUGINS_DIR):
        for fn in os.listdir(PLUGINS_DIR):
            if fn.endswith("_bootstrap.js"):
                fp = os.path.join(PLUGINS_DIR, fn)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass

    # Delete elsmod_data if not keeping
    if not keep_elsmod_data:
        elsmod_dir = os.path.join(GAME_DIR, "elsmod_data")
        if os.path.isdir(elsmod_dir):
            shutil.rmtree(elsmod_dir, ignore_errors=True)

    # Delete registry
    if os.path.isfile(REGISTRY_PATH):
        try:
            os.remove(REGISTRY_PATH)
        except OSError:
            pass


def main():
    root = tk.Tk()
    root.title("卸载艾露莎注入器")
    root.geometry("420x240")
    root.resizable(False, False)

    # Window icon
    try:
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "injector", "Uninstall_logo.ico")
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
        # Collect residual files that couldn't be deleted (locked by this process)
        # and schedule a batch file to clean them up after we exit.
        residual = _collect_injector_paths()
        root.destroy()
        _schedule_residual_cleanup(residual)

    ttk.Button(btn_f, text="确认卸载", command=_do_uninstall).pack(side=tk.LEFT, padx=8)
    ttk.Button(btn_f, text="取消", command=root.destroy).pack(side=tk.LEFT, padx=8)

    root.mainloop()


if __name__ == "__main__":
    main()
