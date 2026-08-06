"""Main GUI window — plugin list, toggle switches, buttons"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

# Try ttkbootstrap, fallback to plain ttk
try:
    import ttkbootstrap as tb
    HAS_BOOTSTRAP = True
except ImportError:
    tb = None
    HAS_BOOTSTRAP = False

from ..core import cli_engine, deploy


class ElushaInjectorGUI:
    def __init__(self, dev_mode: bool = False):
        self.dev_mode = dev_mode
        self._game_dir = os.getcwd()

        # Validate game directory
        if not deploy.is_game_directory(self._game_dir):
            messagebox.showerror(
                "错误", "当前目录不包含 Game.exe。\n请将本程序放到游戏目录下运行。")
            sys.exit(1)

        # Setup environment
        self._setup_result = deploy.setup(self._game_dir)

        # Build UI — use TkinterDnD.Tk for drag-drop, apply ttkbootstrap theme on top
        try:
            from tkinterdnd2 import TkinterDnD
            self.root = TkinterDnD.Tk()
            if HAS_BOOTSTRAP:
                tb.Style("darkly")  # apply theme to existing Tk
            self._has_dnd = True
        except ImportError:
            if HAS_BOOTSTRAP:
                self.root = tb.Window(themename="darkly")
            else:
                self.root = tk.Tk()
            self._has_dnd = False

        self.root.title("艾露莎注入器 v1.0 — 世間知らずの猫エルーシャ 插件管理")
        self.root.geometry("520x500")
        self.root.minsize(420, 380)

        # Window icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "Injector_logo.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # Enable drag-drop targets
        if self._has_dnd:
            self.root.drop_target_register("*")
            self.root.dnd_bind("<<Drop>>", self._on_drop)

        self._build_header()
        self._build_plugin_list()
        self._build_buttons()
        self._refresh()

    # ---- header ----
    def _build_header(self):
        f = ttk.Frame(self.root)
        f.pack(fill=tk.X, padx=16, pady=(16, 8))
        ttk.Label(f, text="艾露莎注入器 v1.0",
                  font=("", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(f, text="世間知らずの猫エルーシャ 插件管理 · 支持游戏版本 1.051",
                  font=("", 8)).pack(anchor=tk.W)
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16)

    # ---- plugin list ----
    def _build_plugin_list(self):
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Canvas + scrollbar for scrollable list
        self._canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self._canvas.yview)
        self._list_frame = ttk.Frame(self._canvas)

        self._list_frame.bind("<Configure>",
                              lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._list_frame, anchor=tk.NW)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all("<MouseWheel>",
                          lambda ev: self._canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

    # ---- buttons ----
    def _build_buttons(self):
        f = ttk.Frame(self.root)
        f.pack(fill=tk.X, padx=16, pady=(0, 12))

        bootstyle = {"bootstyle": "secondary"} if HAS_BOOTSTRAP else {}
        success_style = {"bootstyle": "success"} if HAS_BOOTSTRAP else {}

        ttk.Button(f, text="关闭", command=self._on_close, **bootstyle).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(f, text="导入", command=self._on_import, **bootstyle).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="启动游戏", command=self._on_launch, **success_style).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="设置", command=self._on_settings, **bootstyle).pack(side=tk.LEFT, padx=4)
        ttk.Button(f, text="更多", command=self._on_more, **bootstyle).pack(side=tk.LEFT, padx=4)

        if self.dev_mode:
            ttk.Button(f, text="开发者", command=self._on_dev_panel,
                       **({"bootstyle": "warning"} if HAS_BOOTSTRAP else {})).pack(side=tk.RIGHT, padx=4)

    # ---- refresh ----
    def _refresh(self):
        """Rebuild the plugin list from registry and sync enabled_plugins.txt."""
        for w in self._list_frame.winfo_children():
            w.destroy()

        # Sync enabled_plugins.txt for DLL
        try:
            from ..core.cli_engine import _sync_enabled_plugins
            _sync_enabled_plugins(self._game_dir)
        except Exception:
            pass

        try:
            plugins = cli_engine.cmd_list()
            broken = cli_engine.cmd_check_broken()
        except Exception:
            plugins = []
            broken = []

        broken_names = {b["name"] for b in broken}

        if not plugins:
            lbl = ttk.Label(self._list_frame,
                            text="暂无插件\n\n拖放 .elsmod 文件或点击「导入」安装插件",
                            font=("", 10), foreground="gray")
            lbl.pack(pady=40)
            return

        for i, p in enumerate(plugins):
            self._add_plugin_row(p, i, p["name"] in broken_names)

    def _add_plugin_row(self, plugin: dict, index: int, is_broken: bool):
        f = ttk.Frame(self._list_frame)
        f.pack(fill=tk.X, pady=2)

        # Broken indicator
        if is_broken:
            ttk.Label(f, text="⚠", foreground="red", font=("", 10)).pack(side=tk.LEFT, padx=(4, 0))

        # ↑↓ buttons
        btn_f = ttk.Frame(f)
        btn_f.pack(side=tk.LEFT, padx=(4, 8))
        ttk.Button(btn_f, text="↑", width=2,
                   command=lambda n=plugin["name"]: self._move_up(n)).pack()
        ttk.Button(btn_f, text="↓", width=2,
                   command=lambda n=plugin["name"]: self._move_down(n)).pack()

        # Name + version + description
        info_f = ttk.Frame(f)
        info_f.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(info_f, text=f"{plugin['name']}",
                  font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(info_f, text=f"v{plugin.get('version', '?')} — {plugin.get('description', '')}",
                  font=("", 8), foreground="gray").pack(anchor=tk.W)

        if is_broken:
            ttk.Label(info_f, text="破损 — 文件缺失", foreground="red",
                      font=("", 8)).pack(anchor=tk.W)

        # Toggle switch
        enabled = plugin.get("enabled", False)
        var = tk.BooleanVar(value=enabled)
        state = tk.DISABLED if is_broken else tk.NORMAL
        cb = ttk.Checkbutton(f, variable=var, text="",
                             command=lambda n=plugin["name"], v=var: self._on_toggle(n, v.get()))
        cb.configure(state=state)
        cb.pack(side=tk.RIGHT, padx=8)

        # Repair button for broken plugins
        if is_broken:
            ttk.Button(f, text="修复", width=4,
                       command=lambda n=plugin["name"]: self._on_repair(n)).pack(side=tk.RIGHT, padx=4)

        # Double-click → detail
        def _on_dbl(e, n=plugin["name"]):
            self._on_detail(n)
        for child in [f, info_f] + list(info_f.winfo_children()):
            child.bind("<Double-Button-1>", _on_dbl)

    # ---- actions ----
    def _on_toggle(self, name: str, enable: bool):
        if self._check_game_running():
            return
        try:
            if enable:
                result = cli_engine.cmd_enable(name)
                cascade = result.get("cascadeEnabled", [])
                if cascade:
                    messagebox.showinfo("依赖启用",
                                        f"以下依赖插件已同时启用：{', '.join(cascade)}")
            else:
                from ..core import registry as _reg, dependency as _dep
                reg = _reg.load(self._game_dir)
                deps = _dep.find_dependents(reg, name)
                if deps:
                    if not messagebox.askyesno("依赖禁用",
                                               f"以下插件依赖 {name}，将一起禁用：\n{', '.join(deps)}\n\n确认？"):
                        self._refresh()
                        return
                result = cli_engine.cmd_disable(name)
            self._refresh()
        except Exception as e:
            messagebox.showerror("操作失败", str(e))
            self._refresh()

    def _move_up(self, name: str):
        if self._check_game_running():
            return
        gd = self._game_dir
        from ..core import registry
        reg = registry.load(gd)
        lo = reg.get("loadOrder", [])
        if name not in lo:
            return
        i = lo.index(name)
        if i > 0:
            lo[i], lo[i - 1] = lo[i - 1], lo[i]
            reg["loadOrder"] = lo
            registry.save(gd, reg)
            self._refresh()

    def _move_down(self, name: str):
        if self._check_game_running():
            return
        gd = self._game_dir
        from ..core import registry
        reg = registry.load(gd)
        lo = reg.get("loadOrder", [])
        if name not in lo:
            return
        i = lo.index(name)
        if i < len(lo) - 1:
            lo[i], lo[i + 1] = lo[i + 1], lo[i]
            reg["loadOrder"] = lo
            registry.save(gd, reg)
            self._refresh()

    def _on_import(self):
        if self._check_game_running():
            return
        fp = filedialog.askopenfilename(
            title="选择 .elsmod 文件",
            filetypes=[("Elusha Mod", "*.elsmod"), ("所有文件", "*.*")])
        if not fp:
            return
        try:
            result = cli_engine.cmd_install(fp)
            messagebox.showinfo("导入成功",
                                f"{result['installed']} v{result['version']}")
            self._refresh()
        except FileExistsError as e:
            messagebox.showwarning("已存在", str(e))
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _on_launch(self):
        try:
            cli_engine.cmd_launch()
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def _on_detail(self, name: str):
        try:
            info = cli_engine.cmd_info(name)
            DetailDialog(self.root, info, self._game_dir, self._refresh)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _on_repair(self, name: str):
        if self._check_game_running():
            return
        try:
            cli_engine.cmd_repair(name)
            messagebox.showinfo("修复", f"{name} 已修复")
            self._refresh()
        except Exception as e:
            messagebox.showerror("修复失败", str(e))

    def _on_settings(self):
        SettingsDialog(self.root, self._game_dir)

    def _on_more(self):
        webbrowser.open("https://github.com/example/elusha-injector")

    def _on_dev_panel(self):
        DevPanel(self.root, self._game_dir, self._refresh)

    def _on_drop(self, event):
        if not self._has_dnd or self._check_game_running():
            return
        files = self.root.tk.splitlist(event.data)
        for fp in files:
            if fp.endswith(".elsmod"):
                try:
                    cli_engine.cmd_install(fp)
                except FileExistsError:
                    pass  # already exists, skip silently
                except Exception as e:
                    messagebox.showerror("导入失败", f"{os.path.basename(fp)}: {e}")
        self._refresh()

    def _on_close(self):
        self.root.destroy()

    def _check_game_running(self) -> bool:
        if cli_engine.is_game_running():
            messagebox.showwarning("游戏运行中", "请先关闭游戏再执行此操作。")
            return True
        return False

    def run(self):
        self.root.mainloop()


# ---- Detail Dialog ----
class DetailDialog(tk.Toplevel):
    def __init__(self, parent, info: dict, game_dir: str, refresh_cb):
        super().__init__(parent)
        self.title(f"{info['name']} — 插件详情")
        self.geometry("460x480")
        self._info = info
        self._game_dir = game_dir
        self._refresh_cb = refresh_cb

        # Back button
        ttk.Button(self, text="← 返回", command=self.destroy).pack(anchor=tk.W, padx=12, pady=(12, 8))

        # Info fields
        fields = [
            ("插件名称", info.get("name", "")),
            ("插件作者", info.get("author", "")),
            ("插件版本", info.get("version", "")),
            ("插件介绍", info.get("description", "")),
            ("支持游戏版本", info.get("gameVersion", "")),
        ]
        for label, value in fields:
            f = ttk.Frame(self)
            f.pack(fill=tk.X, padx=16, pady=4)
            ttk.Label(f, text=f"{label}：", font=("", 9, "bold")).pack(anchor=tk.W)
            ttk.Label(f, text=value or "—", font=("", 9)).pack(anchor=tk.W, padx=(16, 0))

        # Dependencies
        deps = info.get("dependencies", [])
        ttk.Label(self, text=f"依赖：{_fmt_deps(deps)}", font=("", 9)).pack(anchor=tk.W, padx=16, pady=4)

        # Conflicts
        conflicts = info.get("conflicts", [])
        ttk.Label(self, text=f"冲突：{_fmt_deps(conflicts)}", font=("", 9)).pack(anchor=tk.W, padx=16, pady=4)

        # File list
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=8)
        ttk.Label(self, text="文件列表：", font=("", 9, "bold")).pack(anchor=tk.W, padx=16)

        files = info.get("files", {})
        for fn, sz in sorted(files.items()):
            f = ttk.Frame(self)
            f.pack(fill=tk.X, padx=16)
            ttk.Label(f, text=fn, font=("", 8)).pack(side=tk.LEFT)
            ttk.Label(f, text=_fmt_size(sz), font=("", 8),
                      foreground="gray").pack(side=tk.RIGHT)

        # Size total
        total = info.get("totalSize", 0)
        ttk.Label(self, text=f"总大小：{_fmt_size(total)}",
                  font=("", 9)).pack(anchor=tk.W, padx=16, pady=8)

        # Uninstall button
        ttk.Button(self, text="卸载插件", command=self._uninstall).pack(pady=12)

    def _uninstall(self):
        if cli_engine.is_game_running():
            messagebox.showwarning("游戏运行中", "请先关闭游戏。")
            return
        name = self._info["name"]
        if not messagebox.askyesno("确认卸载", f"确定要卸载 {name} 吗？"):
            return
        try:
            cli_engine.cmd_uninstall(name)
            self._refresh_cb()
            self.destroy()
        except Exception as e:
            messagebox.showerror("卸载失败", str(e))


# ---- Settings Dialog ----
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, game_dir: str):
        super().__init__(parent)
        self.title("设置")
        self.geometry("360x220")
        self._game_dir = game_dir

        ttk.Button(self, text="← 返回", command=self.destroy).pack(anchor=tk.W, padx=12, pady=12)

        ttk.Label(self, text="环境检测",
                  font=("", 10)).pack(anchor=tk.W, padx=16, pady=(8, 4))
        ttk.Label(self, text="重新检测游戏目录，创建必要文件",
                  font=("", 8), foreground="gray").pack(anchor=tk.W, padx=32)
        ttk.Button(self, text="执行环境检测", command=self._env_check).pack(anchor=tk.W, padx=32, pady=(4, 12))

        ttk.Label(self, text="查看注册表",
                  font=("", 10)).pack(anchor=tk.W, padx=16, pady=(8, 4))
        ttk.Label(self, text="打开 elsmod_data/ 所在目录",
                  font=("", 8), foreground="gray").pack(anchor=tk.W, padx=32)
        ttk.Button(self, text="打开目录", command=self._open_elsmod_dir).pack(anchor=tk.W, padx=32, pady=(4, 12))

        ttk.Label(self, text=".elsmod 文件关联",
                  font=("", 10)).pack(anchor=tk.W, padx=16, pady=(8, 4))
        btn_f = ttk.Frame(self)
        btn_f.pack(anchor=tk.W, padx=32, pady=4)
        ttk.Button(btn_f, text="注册", command=self._register).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_f, text="取消注册", command=self._unregister).pack(side=tk.LEFT, padx=2)

    def _env_check(self):
        result = deploy.setup(self._game_dir)
        msg = f"已创建 {len(result['dirs_created'])} 个目录\n已解出 {len(result['files_extracted'])} 个文件"
        messagebox.showinfo("环境检测", msg)

    def _open_elsmod_dir(self):
        d = os.path.join(self._game_dir, "elsmod_data")
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    def _register(self):
        from ..core import elsmod_register
        elsmod_register.register()
        messagebox.showinfo("文件关联", ".elsmod 已关联")

    def _unregister(self):
        from ..core import elsmod_register
        elsmod_register.unregister()
        messagebox.showinfo("文件关联", ".elsmod 关联已取消")


# ---- Developer Panel ----
class DevPanel(tk.Toplevel):
    def __init__(self, parent, game_dir: str, refresh_cb):
        super().__init__(parent)
        self.title("开发者面板")
        self.geometry("560x520")
        self._game_dir = game_dir
        self._refresh_cb = refresh_cb

        ttk.Label(self, text="开发者面板 — 艾露莎注入器 v1.0",
                  font=("", 12, "bold")).pack(pady=12)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # Actions tab
        actions = ttk.Frame(nb)
        nb.add(actions, text="操作")
        self._build_actions_tab(actions)

        # Terminal tab
        terminal = ttk.Frame(nb)
        nb.add(terminal, text="终端")
        self._terminal_text = tk.Text(terminal, height=10, bg="#1a1a1a", fg="#00ff00",
                                       insertbackground="#00ff00", font=("Consolas", 9))
        self._terminal_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Tools tab
        tools = ttk.Frame(nb)
        nb.add(tools, text="工具")
        self._build_tools_tab(tools)

    def _build_actions_tab(self, parent):
        ttk.Button(parent, text="打包 elsmod", command=self._pack).pack(fill=tk.X, padx=16, pady=4)
        ttk.Button(parent, text="解包 elsmod", command=self._unpack).pack(fill=tk.X, padx=16, pady=4)
        ttk.Button(parent, text="生成项目模板", command=self._template).pack(fill=tk.X, padx=16, pady=4)

    def _build_tools_tab(self, parent):
        tools = cli_engine.cmd_tools_list()
        for t in tools:
            f = ttk.Frame(parent)
            f.pack(fill=tk.X, padx=16, pady=4)
            ttk.Label(f, text=t["name"], font=("", 9, "bold")).pack(anchor=tk.W)
            ttk.Label(f, text=t["description"], font=("", 8), foreground="gray").pack(anchor=tk.W)
            ttk.Button(f, text="打开", command=lambda url=t["url"]: webbrowser.open(url)).pack(anchor=tk.E)

    def _log(self, msg: str):
        self._terminal_text.insert(tk.END, msg + "\n")
        self._terminal_text.see(tk.END)

    def _pack(self):
        d = filedialog.askdirectory(title="选择项目目录")
        if not d:
            return
        out = filedialog.asksaveasfilename(defaultextension=".elsmod",
                                           filetypes=[("Elusha Mod", "*.elsmod")])
        if not out:
            return
        try:
            result = cli_engine.cmd_pack(d, out)
            self._log(f"打包完成：{result['packed']}")
            messagebox.showinfo("打包", "打包完成")
        except Exception as e:
            self._log(f"错误：{e}")
            messagebox.showerror("打包失败", str(e))

    def _unpack(self):
        fp = filedialog.askopenfilename(filetypes=[("Elusha Mod", "*.elsmod")])
        if not fp:
            return
        d = filedialog.askdirectory(title="选择输出目录")
        if not d:
            return
        try:
            result = cli_engine.cmd_unpack(fp, d)
            self._log(f"解包完成：{result['unpacked']}")
            messagebox.showinfo("解包", "解包完成")
        except Exception as e:
            self._log(f"错误：{e}")
            messagebox.showerror("解包失败", str(e))

    def _template(self):
        dialog = tk.Toplevel(self)
        dialog.title("生成模板")
        dialog.geometry("360x200")
        ttk.Label(dialog, text="插件名称：").pack(anchor=tk.W, padx=16, pady=(16, 0))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).pack(fill=tk.X, padx=16)
        ttk.Label(dialog, text="插件作者：").pack(anchor=tk.W, padx=16, pady=(8, 0))
        author_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=author_var).pack(fill=tk.X, padx=16)
        ttk.Label(dialog, text="输出目录：").pack(anchor=tk.W, padx=16, pady=(8, 0))
        dir_var = tk.StringVar()
        dir_f = ttk.Frame(dialog)
        dir_f.pack(fill=tk.X, padx=16)
        ttk.Entry(dir_f, textvariable=dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_f, text="...", width=3,
                   command=lambda: dir_var.set(filedialog.askdirectory())).pack(side=tk.RIGHT)

        def _do():
            try:
                result = cli_engine.cmd_template(name_var.get(), author_var.get(), dir_var.get())
                self._log(f"模板生成：{result['templateCreated']}")
                messagebox.showinfo("模板", "模板已生成")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("失败", str(e))
        ttk.Button(dialog, text="生成", command=_do).pack(pady=16)


# ---- helpers ----
def _fmt_size(size: int) -> str:
    if size >= 1048576:
        return f"{size / 1048576:.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _fmt_deps(deps: list) -> str:
    if not deps:
        return "无"
    parts = []
    for d in deps:
        name = d.get("name", "?")
        ver = d.get("version", "")
        parts.append(f"{name} {ver}" if ver else name)
    return ", ".join(parts)


# ---- entry point ----
def run(dev_mode: bool = False):
    app = ElushaInjectorGUI(dev_mode=dev_mode)
    app.run()
