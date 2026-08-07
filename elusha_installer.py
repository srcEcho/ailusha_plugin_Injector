"""ElushaInstaller — multi-page wizard with 3-language support."""
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ═══════════════════════════════════════════════════════════════
#  Language strings — zh / en / ja
# ═══════════════════════════════════════════════════════════════

INSTALLER_STRINGS = {
    "zh": {
        "wizard.title": "艾露莎注入器 安装向导",
        "welcome.title": "欢迎使用艾露莎注入器",
        "welcome.subtitle": (
            "本向导将引导您完成注入器的安装。\n\n"
            "艾露莎注入器用于管理《世間知らずの猫エルーシャ》的插件。\n"
            "安装后即可通过图形界面导入、启用和管理游戏 MOD。"
        ),
        "welcome.start": "开始安装",
        "welcome.exit": "退出",
        "lang.label": "语言",
        "select.title": "选择游戏程序",
        "select.prompt": "请选择游戏目录下的主程序 (.exe)：",
        "select.no_file": "尚未选择文件",
        "select.target_dir": "安装目录：",
        "select.browse": "浏览...",
        "select.next": "继续",
        "select.back": "上一步",
        "select.error.not_exe": "请选择一个 .exe 文件。",
        "confirm.title": "确认安装",
        "confirm.summary": "安装摘要",
        "confirm.game_exe": "游戏程序：",
        "confirm.install_dir": "安装目录：",
        "confirm.will_install": "将安装以下文件：",
        "confirm.item_exe": "ElushaInjector.exe — 注入器主程序",
        "confirm.item_internal": "_internal/ — 运行库及依赖",
        "confirm.warning_exists": "⚠ 目标目录已存在 ElushaInjector.exe，将被覆盖。",
        "confirm.install": "安装",
        "confirm.cancel": "取消",
        "confirm.back": "上一步",
        "progress.title": "正在安装...",
        "progress.copying": "正在复制文件...",
        "progress.please_wait": "请勿关闭此窗口。",
        "done.success_title": "✅ 安装完成！",
        "done.success_msg": (
            "艾露莎注入器已成功安装到游戏目录。\n\n"
            "运行 ElushaInjector.exe 来管理插件。"
        ),
        "done.delete_self": "删除此安装程序（推荐保留备用）",
        "done.finish": "完成",
        "done.open_dir": "打开安装目录",
        "done.error_title": "❌ 安装失败",
        "error.payload_missing": "未找到注入器文件。\n期望路径：",
        "error.copy_failed": "文件复制失败：",
        "error.not_writable": "目标目录不可写，请以管理员身份运行。",
        "lang.zh": "中文",
        "lang.en": "English",
        "lang.ja": "日本語",
    },
    "en": {
        "wizard.title": "Elusha Injector Setup Wizard",
        "welcome.title": "Welcome to Elusha Injector",
        "welcome.subtitle": (
            "This wizard will guide you through installing the injector.\n\n"
            "Elusha Injector manages plugins for the game.\n"
            "After installation, you can import, enable, and manage game MODs through the GUI."
        ),
        "welcome.start": "Start Install",
        "welcome.exit": "Exit",
        "lang.label": "Language",
        "select.title": "Select Game Executable",
        "select.prompt": "Please select the game's main executable (.exe):",
        "select.no_file": "No file selected",
        "select.target_dir": "Install Directory: ",
        "select.browse": "Browse...",
        "select.next": "Next",
        "select.back": "Back",
        "select.error.not_exe": "Please select a .exe file.",
        "confirm.title": "Confirm Installation",
        "confirm.summary": "Installation Summary",
        "confirm.game_exe": "Game Executable: ",
        "confirm.install_dir": "Install Directory: ",
        "confirm.will_install": "The following will be installed:",
        "confirm.item_exe": "ElushaInjector.exe — Injector main program",
        "confirm.item_internal": "_internal/ — Runtime and dependencies",
        "confirm.warning_exists": "⚠ ElushaInjector.exe already exists and will be overwritten.",
        "confirm.install": "Install",
        "confirm.cancel": "Cancel",
        "confirm.back": "Back",
        "progress.title": "Installing...",
        "progress.copying": "Copying files...",
        "progress.please_wait": "Please do not close this window.",
        "done.success_title": "✅ Installation Complete!",
        "done.success_msg": (
            "Elusha Injector has been installed to the game directory.\n\n"
            "Run ElushaInjector.exe to manage your plugins."
        ),
        "done.delete_self": "Delete this installer (keep for later)",
        "done.finish": "Finish",
        "done.open_dir": "Open Install Folder",
        "done.error_title": "❌ Installation Failed",
        "error.payload_missing": "Injector files not found.\nExpected path: ",
        "error.copy_failed": "File copy failed: ",
        "error.not_writable": "Target directory is not writable. Try running as administrator.",
        "lang.zh": "中文",
        "lang.en": "English",
        "lang.ja": "日本語",
    },
    "ja": {
        "wizard.title": "エルーシャインジェクター セットアップ",
        "welcome.title": "エルーシャインジェクターへようこそ",
        "welcome.subtitle": (
            "このウィザードがインジェクターのインストールを案内します。\n\n"
            "エルーシャインジェクターはゲームのプラグインを管理します。\n"
            "インストール後、GUIでプラグインのインポート、有効化、管理ができます。"
        ),
        "welcome.start": "インストール開始",
        "welcome.exit": "終了",
        "lang.label": "言語",
        "select.title": "ゲームの実行ファイルを選択",
        "select.prompt": "ゲームのメイン実行ファイル (.exe) を選択してください：",
        "select.no_file": "ファイルが選択されていません",
        "select.target_dir": "インストール先：",
        "select.browse": "参照...",
        "select.next": "次へ",
        "select.back": "戻る",
        "select.error.not_exe": ".exeファイルを選択してください。",
        "confirm.title": "インストールの確認",
        "confirm.summary": "インストール概要",
        "confirm.game_exe": "ゲームの実行ファイル：",
        "confirm.install_dir": "インストール先：",
        "confirm.will_install": "以下をインストールします：",
        "confirm.item_exe": "ElushaInjector.exe — インジェクター本体",
        "confirm.item_internal": "_internal/ — ランタイムと依存関係",
        "confirm.warning_exists": "⚠ ElushaInjector.exe は既に存在し、上書きされます。",
        "confirm.install": "インストール",
        "confirm.cancel": "キャンセル",
        "confirm.back": "戻る",
        "progress.title": "インストール中...",
        "progress.copying": "ファイルをコピーしています...",
        "progress.please_wait": "このウィンドウを閉じないでください。",
        "done.success_title": "✅ インストール完了！",
        "done.success_msg": (
            "エルーシャインジェクターがゲームディレクトリに\n"
            "インストールされました。\n\n"
            "ElushaInjector.exe を実行してプラグインを管理してください。"
        ),
        "done.delete_self": "このインストーラーを削除する（保管する場合はオフ）",
        "done.finish": "完了",
        "done.open_dir": "インストール先を開く",
        "done.error_title": "❌ インストール失敗",
        "error.payload_missing": "インジェクターファイルが見つかりません。\n想定パス：",
        "error.copy_failed": "ファイルコピーに失敗しました：",
        "error.not_writable": "インストール先に書き込めません。管理者として実行してください。",
        "lang.zh": "中文",
        "lang.en": "English",
        "lang.ja": "日本語",
    },
}


def tr(lang: str, key: str) -> str:
    """Return the string for *key* in *lang*, falling back to zh then key itself."""
    return INSTALLER_STRINGS.get(lang, INSTALLER_STRINGS["zh"]).get(
        key, INSTALLER_STRINGS["zh"].get(key, key)
    )


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _get_frozen_base() -> str:
    """Base directory for frozen apps. Supports PyInstaller and Nuitka."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS  # PyInstaller
    return os.path.dirname(sys.executable)  # Nuitka


def _get_icon_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(_get_frozen_base(), "injector", "Injector_logo.ico")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "injector", "Injector_logo.ico")


def _get_payload_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(_get_frozen_base(), "ElushaInjector")
    # Dev mode: check both Nuitka (.dist) and PyInstaller naming
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
    for name in ["ElushaInjector", "ElushaInjector.dist"]:
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    return os.path.join(base, "ElushaInjector")


def _count_files(directory: str) -> int:
    total = 0
    for root, dirs, files in os.walk(directory):
        total += len(files)
    return total


def _schedule_self_delete(target: str) -> None:
    """Delete *target* after this process exits."""
    if not os.path.isfile(target):
        return
    bat = os.path.join(os.path.dirname(target), "_del_installer.bat")
    with open(bat, "w") as f:
        f.write(
            "@echo off\r\n"
            ":retry\r\n"
            "timeout /t 1 /nobreak >nul\r\n"
            f'del /f /q "{target}" 2>nul\r\n'
            f'if exist "{target}" goto retry\r\n'
            f'del /f /q "%~f0"\r\n'
        )
    os.startfile(bat)


# ═══════════════════════════════════════════════════════════════
#  Base page
# ═══════════════════════════════════════════════════════════════

class WizardPage(ttk.Frame):
    """Base class for all wizard pages."""

    def __init__(self, wizard):
        super().__init__(wizard._page_container, padding=28)
        self.wizard = wizard

    @property
    def lang(self) -> str:
        return self.wizard.state["lang"]

    @property
    def s(self) -> dict:
        return self.wizard.state

    def tr(self, key: str) -> str:
        return tr(self.lang, key)

    def translate(self, new_lang: str) -> None:
        """Override: rebuild widget text for *new_lang*."""
        pass

    def on_enter(self) -> None:
        """Called when this page becomes visible."""
        pass

    def on_leave(self) -> None:
        """Called when this page is about to be hidden."""
        pass


# ═══════════════════════════════════════════════════════════════
#  WelcomePage
# ═══════════════════════════════════════════════════════════════

class WelcomePage(WizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._title = ttk.Label(self, style="Title.TLabel")
        self._title.grid(row=1, column=0, pady=(0, 16))

        self._subtitle = ttk.Label(self, style="Body.TLabel",
                                   wraplength=460, justify=tk.CENTER)
        self._subtitle.grid(row=2, column=0, pady=(0, 32))

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=3, column=0)
        self._start_btn = ttk.Button(btn_frame, style="Accent.TButton",
                                     command=self._on_start)
        self._start_btn.pack(side=tk.LEFT, padx=8)
        self._exit_btn = ttk.Button(btn_frame, style="Secondary.TButton",
                                    command=self._on_exit)
        self._exit_btn.pack(side=tk.LEFT, padx=8)

        self._refresh_text()

    def _refresh_text(self):
        self._title.configure(text=self.tr("welcome.title"))
        self._subtitle.configure(text=self.tr("welcome.subtitle"))
        self._start_btn.configure(text=self.tr("welcome.start"))
        self._exit_btn.configure(text=self.tr("welcome.exit"))

    def translate(self, new_lang):
        self._refresh_text()

    def _on_start(self):
        self.wizard.show_page("select")

    def _on_exit(self):
        self.wizard.destroy()


# ═══════════════════════════════════════════════════════════════
#  SelectExePage
# ═══════════════════════════════════════════════════════════════

class SelectExePage(WizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self._built = False
        self._build()

    def _build(self):
        if self._built:
            for w in self.winfo_children():
                w.destroy()
        self._built = True

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._title = ttk.Label(self, style="Heading.TLabel")
        self._title.grid(row=0, column=0, pady=(0, 12), sticky="n")

        self._prompt = ttk.Label(self, style="Body.TLabel",
                                 wraplength=460)
        self._prompt.grid(row=1, column=0, pady=(0, 16), sticky="n")

        # File row
        file_frame = ttk.Frame(self)
        file_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        file_frame.grid_columnconfigure(0, weight=1)

        self._path_var = tk.StringVar()
        self._path_entry = ttk.Entry(file_frame, textvariable=self._path_var,
                                     state="readonly")
        self._path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._browse_btn = ttk.Button(file_frame, style="Secondary.TButton",
                                      command=self._on_browse)
        self._browse_btn.grid(row=0, column=1)

        # Target dir row
        dir_frame = ttk.Frame(self)
        dir_frame.grid(row=3, column=0, sticky="ew", pady=(0, 24))
        dir_frame.grid_columnconfigure(1, weight=1)

        self._dir_label = ttk.Label(dir_frame, style="Body.TLabel")
        self._dir_label.grid(row=0, column=0, sticky="w")
        self._dir_value = ttk.Label(dir_frame, style="Body.TLabel",
                                    foreground="#5599cc", wraplength=400)
        self._dir_value.grid(row=0, column=1, sticky="w", padx=(4, 0))

        # Nav buttons
        nav_frame = ttk.Frame(self)
        nav_frame.grid(row=4, column=0, sticky="n")
        self._back_btn = ttk.Button(nav_frame, style="Secondary.TButton",
                                    command=lambda: self.wizard.show_page("welcome"))
        self._back_btn.pack(side=tk.LEFT, padx=8)
        self._next_btn = ttk.Button(nav_frame, style="Accent.TButton",
                                    command=self._on_next)
        self._next_btn.pack(side=tk.LEFT, padx=8)

        self._refresh_text()
        self._update_state()

    def _refresh_text(self):
        self._title.configure(text=self.tr("select.title"))
        self._prompt.configure(text=self.tr("select.prompt"))
        self._dir_label.configure(text=self.tr("select.target_dir"))
        self._browse_btn.configure(text=self.tr("select.browse"))
        self._back_btn.configure(text=self.tr("select.back"))
        self._next_btn.configure(text=self.tr("select.next"))

    def translate(self, new_lang):
        self._build()

    def _on_browse(self):
        fp = filedialog.askopenfilename(
            parent=self.wizard,
            title=self.tr("select.title"),
            filetypes=[("可执行文件 (*.exe)", "*.exe")],
        )
        if fp:
            self.s["exe_path"] = os.path.abspath(fp)
            self.s["game_dir"] = os.path.dirname(self.s["exe_path"])
            self._update_state()

    def _update_state(self):
        if self.s.get("exe_path"):
            self._path_var.set(self.s["exe_path"])
            self._dir_value.configure(text=self.s["game_dir"])
            self._next_btn.configure(state=tk.NORMAL)
        else:
            self._path_var.set(self.tr("select.no_file"))
            self._dir_value.configure(text="—")
            self._next_btn.configure(state=tk.DISABLED)

    def on_enter(self):
        self._update_state()

    def _on_next(self):
        if not self.s.get("exe_path"):
            messagebox.showwarning(self.tr("wizard.title"),
                                   self.tr("select.error.not_exe"),
                                   parent=self.wizard)
            return
        self.wizard.show_page("confirm")


# ═══════════════════════════════════════════════════════════════
#  ConfirmPage
# ═══════════════════════════════════════════════════════════════

class ConfirmPage(WizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self._built = False
        self._build()

    def _build(self):
        if self._built:
            for w in self.winfo_children():
                w.destroy()
        self._built = True

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(7, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._title = ttk.Label(self, style="Heading.TLabel")
        self._title.grid(row=0, column=0, pady=(0, 4), sticky="n")

        self._summary = ttk.Label(self, style="Body.TLabel",
                                  foreground="gray")
        self._summary.grid(row=1, column=0, pady=(0, 12), sticky="n")

        sep = ttk.Separator(self, orient="horizontal")
        sep.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        # Info rows
        self._rows = []
        for _ in range(5):
            frame = ttk.Frame(self)
            frame.grid(sticky="ew", pady=2)
            frame.grid_columnconfigure(1, weight=1)
            lbl = ttk.Label(frame, style="Body.TLabel")
            lbl.grid(row=0, column=0, sticky="w")
            val = ttk.Label(frame, style="Body.TLabel",
                            foreground="#aaaaaa", wraplength=440)
            val.grid(row=0, column=1, sticky="w", padx=(8, 0))
            self._rows.append((lbl, val, frame))

        self._warning = ttk.Label(self, style="Warning.TLabel",
                                  wraplength=460)
        self._warning.grid(row=4, column=0, sticky="n", pady=(12, 0))

        nav_frame = ttk.Frame(self)
        nav_frame.grid(row=6, column=0, sticky="n", pady=(24, 0))
        self._back_btn = ttk.Button(nav_frame, style="Secondary.TButton",
                                    command=lambda: self.wizard.show_page("select"))
        self._back_btn.pack(side=tk.LEFT, padx=8)
        self._cancel_btn = ttk.Button(nav_frame, style="Secondary.TButton",
                                      command=self.wizard.destroy)
        self._cancel_btn.pack(side=tk.LEFT, padx=8)
        self._install_btn = ttk.Button(nav_frame, style="Accent.TButton",
                                       command=self.wizard.start_install)
        self._install_btn.pack(side=tk.LEFT, padx=8)

        self._refresh_text()

    def _refresh_text(self):
        self._title.configure(text=self.tr("confirm.title"))
        self._summary.configure(text=self.tr("confirm.summary"))
        self._back_btn.configure(text=self.tr("confirm.back"))
        self._cancel_btn.configure(text=self.tr("confirm.cancel"))
        self._install_btn.configure(text=self.tr("confirm.install"))

    def translate(self, new_lang):
        self._build()

    def on_enter(self):
        # Rebuild rows with current data
        game_dir = self.s.get("game_dir", "")
        exe_path = self.s.get("exe_path", "")

        rows_data = [
            (self.tr("confirm.game_exe"), exe_path),
            (self.tr("confirm.install_dir"), game_dir),
            ("", ""),
            (self.tr("confirm.will_install"), ""),
            ("", f"  • {self.tr('confirm.item_exe')}\n  • {self.tr('confirm.item_internal')}"),
        ]
        for (lbl, val), (label_w, value_w, _) in zip(rows_data, self._rows):
            label_w.configure(text=lbl)
            value_w.configure(text=val)

        # Existing-install warning
        existing = os.path.join(game_dir, "ElushaInjector.exe") if game_dir else ""
        if os.path.isfile(existing):
            self._warning.configure(text=self.tr("confirm.warning_exists"))
            self._warning.grid()
        else:
            self._warning.grid_remove()


# ═══════════════════════════════════════════════════════════════
#  ProgressPage
# ═══════════════════════════════════════════════════════════════

class ProgressPage(WizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self._built = False
        self._build()

    def _build(self):
        if self._built:
            for w in self.winfo_children():
                w.destroy()
        self._built = True
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._title = ttk.Label(self, style="Heading.TLabel")
        self._title.grid(row=1, column=0, pady=(0, 20))

        self._bar = ttk.Progressbar(self, mode="determinate", length=440)
        self._bar.grid(row=2, column=0, pady=(0, 12))

        self._status = ttk.Label(self, style="Body.TLabel",
                                 wraplength=440)
        self._status.grid(row=3, column=0)

        self._please = ttk.Label(self, style="Subtitle.TLabel",
                                 wraplength=440)
        self._please.grid(row=4, column=0, pady=(4, 0))

        self._refresh_text()

    def _refresh_text(self):
        self._title.configure(text=self.tr("progress.title"))
        self._status.configure(text=self.tr("progress.copying"))
        self._please.configure(text=self.tr("progress.please_wait"))

    def translate(self, new_lang):
        # Progress page text is minimal; just refresh
        self._refresh_text()

    def on_enter(self):
        self._bar["value"] = 0
        self._status.configure(text=self.tr("progress.copying"))

    def set_progress(self, current: int, total: int, filename: str = ""):
        self._bar["maximum"] = total
        self._bar["value"] = current
        if filename:
            display = os.path.basename(filename)
            if len(display) > 50:
                display = display[:47] + "..."
            self._status.configure(text=f"{self.tr('progress.copying')}\n{display}")


# ═══════════════════════════════════════════════════════════════
#  DonePage
# ═══════════════════════════════════════════════════════════════

class DonePage(WizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self._built = False
        self._build()

    def _build(self):
        if self._built:
            for w in self.winfo_children():
                w.destroy()
        self._built = True

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._title_lbl = ttk.Label(self, style="Heading.TLabel")
        self._title_lbl.grid(row=1, column=0, pady=(0, 16))

        self._msg_lbl = ttk.Label(self, style="Body.TLabel",
                                  wraplength=440, justify=tk.CENTER)
        self._msg_lbl.grid(row=2, column=0, pady=(0, 24))

        self._del_var = tk.BooleanVar(value=False)
        self._del_cb = ttk.Checkbutton(self, variable=self._del_var)
        self._del_cb.grid(row=3, column=0, pady=(0, 16))

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        self._open_btn = ttk.Button(btn_frame, style="Secondary.TButton",
                                    command=self._on_open_dir)
        self._open_btn.grid(row=0, column=0, padx=8, sticky="e")
        self._finish_btn = ttk.Button(btn_frame, style="Accent.TButton",
                                      command=self._on_finish)
        self._finish_btn.grid(row=0, column=1, padx=8, sticky="w")

    def translate(self, new_lang):
        self._build()

    def on_enter(self):
        error = self.s.get("error", "")
        if error:
            self._title_lbl.configure(text=self.tr("done.error_title"))
            self._msg_lbl.configure(text=error)
            self._del_cb.grid_remove()
            self._open_btn.grid_remove()
        else:
            self._title_lbl.configure(text=self.tr("done.success_title"))
            self._msg_lbl.configure(text=self.tr("done.success_msg"))
            self._del_cb.configure(text=self.tr("done.delete_self"))
            self._del_cb.grid()
            self._open_btn.configure(text=self.tr("done.open_dir"))
            self._open_btn.grid()
        self._finish_btn.configure(text=self.tr("done.finish"))

    def _on_open_dir(self):
        game_dir = self.s.get("game_dir", "")
        if game_dir and os.path.isdir(game_dir):
            os.startfile(game_dir)

    def _on_finish(self):
        if not self.s.get("error") and self._del_var.get():
            if getattr(sys, "frozen", False):
                _schedule_self_delete(sys.argv[0])
        self.wizard.destroy()


# ═══════════════════════════════════════════════════════════════
#  InstallerWizard — main controller
# ═══════════════════════════════════════════════════════════════

class InstallerWizard(tk.Tk):
    """Single-window multi-page installer wizard."""

    def __init__(self):
        super().__init__()

        # Shared state
        self.state = {
            "lang": "zh",
            "exe_path": "",
            "game_dir": "",
            "installed": [],
            "error": "",
            "delete_self": False,
        }

        # Window config
        self.title(tr(self.state["lang"], "wizard.title"))
        self.minsize(540, 460)
        self.geometry("540x500")
        self.resizable(True, True)

        # Icon
        try:
            ico = _get_icon_path()
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception:
            pass

        # Theme
        self._configure_style()

        # Build chrome
        self._build_lang_bar()
        self._page_container = ttk.Frame(self)
        self._page_container.pack(fill=tk.BOTH, expand=True)

        # Create pages
        self._pages = {
            "welcome": WelcomePage(self),
            "select": SelectExePage(self),
            "confirm": ConfirmPage(self),
            "progress": ProgressPage(self),
            "done": DonePage(self),
        }

        self._current_page = None
        self.show_page("welcome")

        # Install progress
        self._progress_queue = None

    # ---- Style ----

    def _configure_style(self):
        style = ttk.Style(self)
        available = style.theme_names()
        if "clam" in available:
            style.theme_use("clam")
        elif "alt" in available:
            style.theme_use("alt")

        default_font = ("Segoe UI", 10) if sys.platform == "win32" else ("", 10)

        style.configure("TFrame", background="#2b2b2b")
        style.configure("TLabel", background="#2b2b2b", foreground="#e0e0e0",
                        font=default_font)
        style.configure("TButton", font=default_font, padding=(16, 6))
        style.map("TButton",
                  foreground=[("active", "#e0e0e0"), ("pressed", "#e0e0e0")],
                  background=[("active", "#444444"), ("pressed", "#333333")])
        style.configure("TCheckbutton", background="#2b2b2b",
                        foreground="#e0e0e0", font=default_font)
        style.map("TCheckbutton",
                  foreground=[("active", "#e0e0e0"), ("hover", "#e0e0e0"),
                              ("pressed", "#e0e0e0"), ("selected", "#e0e0e0")],
                  background=[("active", "#2b2b2b"), ("hover", "#383838"),
                              ("pressed", "#2b2b2b"), ("selected", "#2b2b2b")])
        style.configure("TEntry", fieldbackground="#3c3c3c",
                        foreground="#e0e0e0")
        style.map("TEntry",
                  fieldbackground=[("readonly", "#333333"), ("disabled", "#2a2a2a")],
                  foreground=[("readonly", "#aaaaaa"), ("disabled", "#666666")])
        style.configure("TProgressbar", thickness=18,
                        troughcolor="#333333", background="#4caf50")

        style.configure("Title.TLabel", font=(default_font[0], 18, "bold"),
                        foreground="#ffffff")
        style.configure("Heading.TLabel", font=(default_font[0], 14, "bold"),
                        foreground="#ffffff")
        style.configure("Body.TLabel", font=default_font,
                        foreground="#cccccc")
        style.configure("Subtitle.TLabel", font=(default_font[0], 9),
                        foreground="#888888")
        style.configure("Warning.TLabel", font=default_font,
                        foreground="#cc8800")

        style.configure("Accent.TButton", font=(default_font[0], 10, "bold"))
        style.configure("Secondary.TButton", font=default_font)
        style.configure("Lang.TButton", font=(default_font[0], 8),
                        padding=(10, 3))

    # ---- Language bar ----

    def _build_lang_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=12, pady=(8, 0))

        self._lang_label = ttk.Label(bar, style="Subtitle.TLabel")
        self._lang_label.pack(side=tk.LEFT, padx=(0, 4))

        self._lang_btns = {}
        for code in ["zh", "en", "ja"]:
            name = tr(self.state["lang"], f"lang.{code}")
            btn = ttk.Button(bar, text=name, style="Lang.TButton",
                             command=lambda c=code: self._on_lang_change(c))
            btn.pack(side=tk.LEFT, padx=2)
            self._lang_btns[code] = btn

        self._refresh_lang_bar()

    def _refresh_lang_bar(self):
        lang = self.state["lang"]
        self._lang_label.configure(text=tr(lang, "lang.label") + ":")
        for code, btn in self._lang_btns.items():
            btn.configure(text=tr(lang, f"lang.{code}"))

    def _on_lang_change(self, new_lang):
        self.state["lang"] = new_lang
        self._refresh_lang_bar()
        if self._current_page:
            self._current_page.translate(new_lang)
            self._current_page.on_enter()

    # ---- Page navigation ----

    def show_page(self, page_name: str):
        if self._current_page:
            self._current_page.on_leave()
            self._current_page.pack_forget()

        page = self._pages[page_name]
        page.translate(self.state["lang"])
        page.pack(fill=tk.BOTH, expand=True)
        page.on_enter()

        self._current_page = page

    # ---- Install ----

    def start_install(self):
        payload = _get_payload_dir()

        # Validate payload
        if not os.path.isdir(payload):
            self.state["error"] = tr(self.state["lang"], "error.payload_missing") + payload
            self.show_page("done")
            return

        # Validate target is writable
        game_dir = self.state.get("game_dir", "")
        if game_dir and os.path.isdir(game_dir):
            try:
                test = os.path.join(game_dir, "._write_test")
                with open(test, "w") as f:
                    f.write("")
                os.remove(test)
            except Exception:
                self.state["error"] = tr(self.state["lang"], "error.not_writable")
                self.show_page("done")
                return

        self._progress_queue = queue.Queue()
        self.show_page("progress")

        # Disable close during install
        self._orig_close = self.protocol("WM_DELETE_WINDOW")
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        threading.Thread(
            target=self._install_thread,
            args=(payload, game_dir, self._progress_queue),
            daemon=True,
        ).start()
        self._poll_progress()

    def _install_thread(self, payload_dir, game_dir, q):
        try:
            import json as _json

            # Pre-scan: walk the entire payload to build the manifest BEFORE copying.
            # This way the uninstaller knows about every single file and directory.
            installed = []
            for root, dirs, files in os.walk(payload_dir):
                for d in dirs:
                    rel = os.path.relpath(os.path.join(root, d),
                                          payload_dir).replace("\\", "/")
                    installed.append(rel)
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f),
                                          payload_dir).replace("\\", "/")
                    installed.append(rel)

            total = _count_files(payload_dir)
            cur = [0]

            def _copy_with_progress(src, dst, *, follow_symlinks=True):
                shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
                cur[0] += 1
                q.put(("progress", cur[0], total, os.path.basename(src)))

            for item in os.listdir(payload_dir):
                src = os.path.join(payload_dir, item)
                dst = os.path.join(game_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst, copy_function=_copy_with_progress)
                else:
                    _copy_with_progress(src, dst)

            # Write install manifest — single source of truth for uninstaller
            try:
                manifest_dir = os.path.join(game_dir, "elsmod_data")
                os.makedirs(manifest_dir, exist_ok=True)
                manifest_path = os.path.join(manifest_dir,
                                             "install_manifest.json")
                with open(manifest_path, "w", encoding="utf-8") as f:
                    _json.dump({"items": sorted(installed)}, f,
                              ensure_ascii=False, indent=2)
            except Exception:
                pass  # non-critical

            # Register .elsmod file association to the installed injector
            try:
                import ctypes
                import winreg
                ELSMOD_PROGID = "ElushaPlugin.elsmod"
                exe_path = os.path.join(game_dir, "ElushaInjector.exe")
                if os.path.isfile(exe_path):
                    # Remove UserChoice hash (Windows 8+) that blocks the
                    # association when user previously set a default app.
                    try:
                        uc_key = winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.elsmod",
                            0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
                        try:
                            winreg.DeleteValue(uc_key, "UserChoice")
                        except FileNotFoundError:
                            pass
                        winreg.CloseKey(uc_key)
                    except FileNotFoundError:
                        pass
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                          r"Software\Classes\.elsmod") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, ELSMOD_PROGID)
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                          rf"Software\Classes\{ELSMOD_PROGID}\DefaultIcon") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, f'"{exe_path}",0')
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                          rf"Software\Classes\{ELSMOD_PROGID}\shell\open\command") as k:
                        winreg.SetValue(k, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
                    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
            except Exception:
                pass  # non-critical, injector will auto-register on startup

            q.put(("done", installed))
        except Exception as exc:
            q.put(("error", str(exc)))

    def _poll_progress(self):
        try:
            while True:
                msg = self._progress_queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, cur, total, fname = msg
                    self._pages["progress"].set_progress(cur, total, fname)
                elif kind == "done":
                    self.state["installed"] = msg[1]
                    self.state["error"] = ""
                    self.protocol("WM_DELETE_WINDOW", self.destroy)
                    self.show_page("done")
                    return
                elif kind == "error":
                    self.state["error"] = msg[1]
                    self.protocol("WM_DELETE_WINDOW", self.destroy)
                    self.show_page("done")
                    return
        except queue.Empty:
            pass
        self.after(50, self._poll_progress)


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

def main():
    wizard = InstallerWizard()
    wizard.mainloop()


if __name__ == "__main__":
    main()
