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


def load_registry():
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _self_delete():
    """Schedule self-deletion after process exits. Runs after GUI is destroyed.
    Uses a batch file that loops until the exe is deletable, then cleans up."""
    exe = sys.executable if getattr(sys, 'frozen', False) else __file__
    if not os.path.isfile(exe):
        return
    bat_path = os.path.join(os.environ.get("TEMP", "."), "_elu_del.bat")
    with open(bat_path, "w") as f:
        f.write(f'@echo off\n'
                f':retry\n'
                f'timeout /t 1 /nobreak >nul\n'
                f'del /f /q "{exe}" 2>nul\n'
                f'if exist "{exe}" goto retry\n'
                f'del /f /q "%~f0"\n')
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=0x08000000)  # CREATE_NO_WINDOW


def uninstall(keep_elsmod_data: bool, keep_plugins: bool):
    reg = load_registry()

    # Delete plugin files
    if not keep_plugins and reg:
        for rec in reg.get("records", []):
            for f in rec.get("files", []):
                fp = os.path.join(PLUGINS_DIR, f)
                if os.path.isfile(fp):
                    os.remove(fp)

    # Delete version.dll
    dll = os.path.join(GAME_DIR, "version.dll")
    if os.path.isfile(dll):
        os.remove(dll)

    # Delete ElushaInjector.exe
    injector = os.path.join(GAME_DIR, "ElushaInjector.exe")
    if os.path.isfile(injector):
        os.remove(injector)

    # Delete elsmod_data if not keeping
    if not keep_elsmod_data:
        elsmod_dir = os.path.join(GAME_DIR, "elsmod_data")
        if os.path.isdir(elsmod_dir):
            shutil.rmtree(elsmod_dir, ignore_errors=True)

    # Delete registry
    if os.path.isfile(REGISTRY_PATH):
        os.remove(REGISTRY_PATH)


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
        root.destroy()
        # Self-delete AFTER GUI is completely destroyed
        _self_delete()

    ttk.Button(btn_f, text="确认卸载", command=_do_uninstall).pack(side=tk.LEFT, padx=8)
    ttk.Button(btn_f, text="取消", command=root.destroy).pack(side=tk.LEFT, padx=8)

    root.mainloop()


if __name__ == "__main__":
    main()
