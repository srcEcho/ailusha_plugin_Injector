"""PySide6 GUI — 18 themes, i18n, drag-drop, auto-register"""
import os, sys, webbrowser

# ── inline logger (no external deps) ──
def _get_log_dir():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    return os.path.join(os.path.dirname(os.path.abspath(exe_path)), "elsmod_data", "logs")

def _glog(msg: str):
    try:
        d = _get_log_dir()
        os.makedirs(d, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(d, "gui.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}][PID={os.getpid()}] {msg}\n")
    except Exception:
        pass
_glog(f"=== START === exe={sys.executable} argv={sys.argv} cwd={os.getcwd()} frozen={getattr(sys, 'frozen', False)} ===")

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QCheckBox, QFileDialog,
    QMessageBox, QDialog, QFormLayout, QTabWidget, QTextEdit, QLineEdit, QInputDialog,
    QComboBox, QSpinBox, QStyleFactory, QFrame, QAbstractButton)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRectF, Property
from PySide6.QtGui import QFont, QIcon, QDragEnterEvent, QDropEvent, QPainter, QColor, QBrush, QPen

from ..core import cli_engine, deploy
from ..core.i18n import tr, load_config, save_config
from ..core.themes import THEMES

# Global CLI log sink — DevPanel subscribes to this
_cli_sinks = []

def _cli_log(msg: str):
    for sink in _cli_sinks:
        try: sink(msg)
        except Exception: pass

class ToggleSwitch(QAbstractButton):
    """Animated sliding toggle switch."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(44, 24)
        self._offset = 2  # knob position (2=off, 22=on)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)

    def _get_offset(self): return self._offset
    def _set_offset(self, v): self._offset = v; self.update()
    offset = Property(float, _get_offset, _set_offset)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2
        # Track
        if self.isChecked():
            p.setBrush(QBrush(QColor("#4caf50")))
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(QBrush(QColor("#555555")))
            p.setPen(QPen(QColor("#666666"), 1))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)
        # Knob
        knob_r = r - 3
        knob_x = w - h + 3 if self.isChecked() else 3
        p.setBrush(QBrush(QColor("#e0e0e0")))
        p.drawEllipse(QRectF(knob_x, 3, knob_r * 2, knob_r * 2))
        p.end()

    def nextCheckState(self):
        if self.isChecked():
            self._anim.setStartValue(22)
            self._anim.setEndValue(2)
        else:
            self._anim.setStartValue(2)
            self._anim.setEndValue(22)
        self._anim.start()
        super().nextCheckState()


def _fmt_size(size: int) -> str:
    if size >= 1048576: return f"{size/1048576:.1f} MB"
    elif size >= 1024: return f"{size/1024:.1f} KB"
    return f"{size} B"


class MainWindow(QMainWindow):
    def __init__(self, dev_mode: bool = False):
        super().__init__()
        self._dev_mode = dev_mode
        # Use centralized game-dir detection — same as CLI engine.
        # Avoids subtle divergence when launched via file association
        # (where os.getcwd() can differ from the EXE directory).
        from ..core.cli_engine import _game_dir as _detect_game_dir
        try:
            self._game_dir = _detect_game_dir()
        except SystemExit:
            self._game_dir = os.getcwd()
        _glog(f"MainWindow.__init__: _game_dir={self._game_dir} is_game_dir={deploy.is_game_directory(self._game_dir)} cwd={os.getcwd()}")
        self._settings_dlg = None

        if not deploy.is_game_directory(self._game_dir):
            _glog("MainWindow.__init__: NOT a game directory — aborting")
            QMessageBox.critical(None, "Error",
                                 "当前目录不包含 Game.exe 或 nw.exe。\n请将本程序放到游戏目录下运行。")
            sys.exit(1)

        self._mode = deploy.game_mode(self._game_dir)
        _glog(f"MainWindow.__init__: game mode={self._mode}  calling deploy.setup()")
        deploy.setup(self._game_dir)
        _glog("MainWindow.__init__: deploy.setup() done")
        self._cfg = load_config(self._game_dir)
        self._lang = self._cfg.get("lang", "zh")
        self._theme = self._cfg.get("theme", "slate_gray")
        self._font_size = self._cfg.get("font_size", 13)

        mode_label = {"packed": "打包版", "unpacked": "解包版"}.get(self._mode, "未知")
        self._mode_str = mode_label

        # Auto-register .elsmod (frozen/compiled EXE only)
        import sys as _sys
        if getattr(_sys, 'frozen', False):
            try:
                from ..core import elsmod_register
                elsmod_register.register()
            except Exception:
                pass

        self._t = lambda key: tr(self._lang, key)
        self.setWindowTitle(self._t("app.title"))
        self.setMinimumSize(520, 500)
        self.resize(540, 560)
        self.setAcceptDrops(True)

        try:
            ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Injector_logo.ico")
            if os.path.exists(ico): self.setWindowIcon(QIcon(ico))
        except Exception: pass

        self._apply_theme()
        self._apply_font()
        self._build_ui()
        self._refresh()

        self._game_check_timer = QTimer(self)
        self._game_check_timer.timeout.connect(self._check_game_running)
        self._game_check_timer.start(2000)

    def _apply_theme(self):
        t = THEMES.get(self._theme, THEMES["slate_gray"])
        self.setStyleSheet(t["qss"] if isinstance(t, dict) else "")

    def _apply_font(self):
        f = QFont()
        f.setPointSize(self._font_size)
        QApplication.setFont(f)

    def _build_ui(self):
        t = self._t
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(t("app.title"))
        title.setFont(QFont("", self._font_size + 3, QFont.Bold))
        root.addWidget(title)
        root.addWidget(QLabel(t("app.subtitle")))

        self._running_lbl = QLabel("")
        self._running_lbl.setStyleSheet("color:#c06010;")
        self._running_lbl.setVisible(False)
        root.addWidget(self._running_lbl)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.setDefaultDropAction(Qt.MoveAction)
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item:selected{background:rgba(100,150,255,30);color:inherit;border:none;}"
            "QListWidget::item:hover{background:rgba(255,255,255,8);}"
        )
        self._list.doubleClicked.connect(lambda idx: self._on_detail(self._list.item(idx.row()).data(Qt.UserRole)))
        self._list.model().rowsMoved.connect(self._on_order_changed)
        root.addWidget(self._list, 1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        for key in ["import","launch","settings","advanced"]:
            if key == "launch":
                launch_btn = QPushButton(t("btn.launch"))
                launch_btn.clicked.connect(self._on_launch)
                btn_row.addWidget(launch_btn)
                # game exe selector — users may rename their game exe
                self._exe_combo = QComboBox()
                self._exe_combo.setMinimumWidth(160)
                self._exe_combo.setToolTip("选择要启动的游戏程序")
                self._refresh_exe_combo()
                btn_row.addWidget(self._exe_combo)
            else:
                btn = QPushButton(t(f"btn.{key}"))
                btn.clicked.connect(getattr(self, f"_on_{key}"))
                btn_row.addWidget(btn)
        if self._dev_mode:
            dev_btn = QPushButton(t("btn.dev"))
            dev_btn.clicked.connect(self._on_dev_panel)
            btn_row.addWidget(dev_btn)
        root.addLayout(btn_row)

    def _refresh(self):
        t = self._t
        self._list.clear()
        try:
            plugins = cli_engine.cmd_list()
            broken = cli_engine.cmd_check_broken()
        except Exception:
            plugins, broken = [], []
        broken_names = {b["name"] for b in broken}

        for p in plugins:
            name = p["name"]; enabled = p.get("enabled", False); is_broken = name in broken_names
            item = QListWidgetItem()
            item.setData(Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled)
            self._list.addItem(item)

            card = QWidget(); card.setObjectName("pluginCard")
            # red border only — let app theme handle background
            if is_broken:
                card.setStyleSheet("#pluginCard{border:2px solid #cc5555;border-radius:6px;}#pluginCard:hover{border-color:#ff5555;}")
            layout = QHBoxLayout(card); layout.setContentsMargins(8, 6, 8, 6)
            info = QVBoxLayout(); info.setSpacing(1)
            nl = QLabel(name)
            nl.setFont(QFont("", max(11, self._font_size - 2), QFont.Bold))
            if is_broken: nl.setStyleSheet("color:#e06060;")
            info.addWidget(nl)
            sub = f"v{p.get('version','?')}"
            if p.get("description"): sub += f" — {p.get('description')}"
            if is_broken: sub += f"  ·  {t('detail.broken')}"
            sl = QLabel(sub)
            if is_broken: sl.setStyleSheet("color:#cc7777;")
            info.addWidget(sl)
            layout.addLayout(info, 1)

            # right side: repair button (if broken) + toggle switch
            right = QHBoxLayout(); right.setSpacing(6)
            if is_broken:
                rb = QPushButton(t("btn.repair"))
                rb.setFixedHeight(26)
                rb.clicked.connect(lambda c, n=name: self._on_repair(n))
                right.addWidget(rb)
            sw = ToggleSwitch()
            sw.setChecked(enabled); sw.setEnabled(not is_broken)
            sw.toggled.connect(lambda checked, n=name: self._on_toggle(n, checked))
            sw.setToolTip("启用" if self._lang == "zh" else ("Enable" if self._lang == "en" else "有効"))
            right.addWidget(sw)
            layout.addLayout(right)

            card.setLayout(layout)
            item.setSizeHint(card.sizeHint())
            self._list.setItemWidget(item, card)

        try:
            from ..core.cli_engine import _sync_enabled_plugins
            _sync_enabled_plugins(self._game_dir)
        except Exception: pass

    def _get_current_order(self):
        return [self._list.item(i).data(Qt.UserRole) for i in range(self._list.count())]

    def _on_order_changed(self):
        cli_engine.cmd_reorder(self._get_current_order())

    def _check_game_running(self):
        running = cli_engine.is_game_running()
        self._running_lbl.setVisible(running)
        if running: self._running_lbl.setText(self._t("game.running"))
        return running

    def _guard(self):
        if self._check_game_running():
            QMessageBox.warning(self, self._t("game.running.title"), self._t("game.running.msg"))
            return True
        return False

    def _on_toggle(self, name, enabled):
        if self._guard(): self._refresh(); return
        _cli_log(f"> ElushaInjector.exe --cli {'enable' if enabled else 'disable'} \"{name}\"")
        try:
            if enabled:
                r = cli_engine.cmd_enable(name)
                if r.get("cascadeEnabled"): QMessageBox.information(self, "", f"{self._t('dep.enable')}{', '.join(r['cascadeEnabled'])}")
            else:
                from ..core import registry as _r, dependency as _d
                reg = _r.load(self._game_dir)
                deps = _d.find_dependents(reg, name)
                if deps:
                    if QMessageBox.question(self, "", f"{self._t('dep.disable')} {name} {self._t('dep.disable.msg')}{', '.join(deps)}\n\n{self._t('dep.confirm')}") != QMessageBox.Yes:
                        self._refresh(); return
                cli_engine.cmd_disable(name)
            self._refresh()
        except Exception as e: QMessageBox.critical(self, "Error", str(e)); self._refresh()

    def _on_import(self):
        if self._guard(): return
        fp, _ = QFileDialog.getOpenFileName(self, "Import", "", "Elusha Mod (*.elsmod);;All (*.*)")
        if not fp: return
        _cli_log(f"> ElushaInjector.exe --cli install \"{fp}\"")
        try:
            r = cli_engine.cmd_install(fp)
            self._refresh()
        except FileExistsError as e: QMessageBox.warning(self, self._t("import.exists"), str(e))
        except Exception as e: QMessageBox.critical(self, self._t("import.failed"), str(e))

    # exe names to hide from the game selector
    _OWN_EXES = {"ElushaInjector.exe", "UninstallElusha.exe", "ElushaInstaller.exe"}

    def _scan_exes(self):
        """Return sorted list of .exe files in game dir, excluding injector's own."""
        exes = []
        try:
            for f in os.listdir(self._game_dir):
                if f.lower().endswith(".exe") and f not in self._OWN_EXES:
                    exes.append(f)
        except Exception:
            pass
        return sorted(exes)

    def _refresh_exe_combo(self):
        """Repopulate the game exe dropdown and restore saved selection."""
        self._exe_combo.clear()
        exes = self._scan_exes()
        self._exe_combo.addItems(exes)
        saved = self._cfg.get("game_exe", "")
        if saved and saved in exes:
            self._exe_combo.setCurrentText(saved)
        elif "Game.exe" in exes:
            self._exe_combo.setCurrentText("Game.exe")
        elif "nw.exe" in exes:
            self._exe_combo.setCurrentText("nw.exe")
        elif exes:
            self._exe_combo.setCurrentIndex(0)

    def _on_launch(self):
        exe_name = self._exe_combo.currentText()
        _glog(f"_on_launch: exe_name={exe_name} game_dir={self._game_dir}")
        if not exe_name:
            QMessageBox.warning(self, "", "未找到可执行文件，请检查游戏目录")
            return
        # remember choice
        self._cfg["game_exe"] = exe_name
        save_config(self._game_dir, self._cfg)

        # Ensure plugin config is synced before launching (belt-and-suspenders:
        # _refresh() already synced at startup, but state can drift).
        from ..core.cli_engine import _sync_enabled_plugins
        _glog("_on_launch: calling _sync_enabled_plugins before launch")
        _sync_enabled_plugins(self._game_dir)
        _glog("_on_launch: _sync_enabled_plugins done")

        _cli_log(f"> launch \"{exe_name}\" (cwd={self._game_dir})")
        try:
            cli_engine.cmd_launch(exe_name=exe_name)
            _glog("_on_launch: cmd_launch succeeded")
            self._check_game_running()
        except Exception as e:
            _glog(f"_on_launch: cmd_launch FAILED: {type(e).__name__}: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _on_detail(self, name):
        try:
            DetailDialog(self, cli_engine.cmd_info(name), self._game_dir, self._lang, self._font_size).exec()
            self._refresh()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _on_repair(self, name):
        if self._guard(): return
        try: cli_engine.cmd_repair(name); QMessageBox.information(self, "", f"{name} {self._t('repair.done')}"); self._refresh()
        except Exception as e: QMessageBox.critical(self, self._t("repair.failed"), str(e))

    def _on_close(self): self.close()
    def _on_advanced(self):
        self._adv_panel = AdvancedPanel(self, self._game_dir, self._lang, self._font_size)
        self._adv_panel.setAttribute(Qt.WA_DeleteOnClose)
        self._adv_panel.show()
    def _on_dev_panel(self):
        if hasattr(self, '_dev_panel') and self._dev_panel.isVisible():
            self._dev_panel.raise_()
            return
        self._dev_panel = DevPanel(self, self._game_dir, self._lang)
        self._dev_panel.setAttribute(Qt.WA_DeleteOnClose)
        self._dev_panel.destroyed.connect(lambda: delattr(self, '_dev_panel'))
        self._dev_panel.show()

    def _on_settings(self):
        if self._settings_dlg: self._settings_dlg.close()
        self._settings_dlg = SettingsDialog(self, self._game_dir, self)
        self._settings_dlg.exec()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            for u in e.mimeData().urls():
                if u.toLocalFile().endswith(".elsmod"): e.acceptProposedAction(); return
        e.ignore()

    def dropEvent(self, e: QDropEvent):
        if self._guard(): return
        for u in e.mimeData().urls():
            fp = u.toLocalFile()
            if fp.endswith(".elsmod"):
                try: cli_engine.cmd_install(fp)
                except FileExistsError: pass
                except Exception as ex: QMessageBox.critical(self, self._t("import.failed"), f"{os.path.basename(fp)}: {ex}")
        self._refresh()

    def closeEvent(self, e): self._game_check_timer.stop(); e.accept()

    def _change_lang(self, lang):
        self._lang = lang; self._cfg["lang"] = lang; save_config(self._game_dir, self._cfg)
        self._t = lambda key: tr(lang, key)
        self.setWindowTitle(self._t("app.title"))
        self._rebuild_all()
        # Reopen settings dialog with new language
        if self._settings_dlg and self._settings_dlg.isVisible():
            self._settings_dlg.close()
            self._on_settings()

    def _change_theme(self, theme):
        self._theme = theme; self._cfg["theme"] = theme; save_config(self._game_dir, self._cfg)
        self._apply_theme()

    def _change_font(self, size):
        self._font_size = size; self._cfg["font_size"] = size; save_config(self._game_dir, self._cfg)
        self._apply_font()
        QMessageBox.information(self, "", "字体大小将在重新启动程序后完全生效。\nFont size will fully apply after restart.")

    def _rebuild_all(self):
        geom = self.geometry()
        central = self.centralWidget()
        if central: central.deleteLater()
        self._build_ui(); self._refresh()
        self.setGeometry(geom)


class AdvancedPanel(QDialog):
    """Non-modal advanced settings — hook library + injection method."""

    def __init__(self, parent, game_dir, lang, font_size):
        super().__init__(parent)
        t = lambda k: tr(lang, k)
        self._gd, self._lang, self._t = game_dir, lang, t
        self.setWindowTitle(t("advanced.title"))
        self.setMinimumSize(420, 280)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        lyt = QVBoxLayout(self)
        lyt.setSpacing(12)
        lyt.addWidget(QLabel(t("advanced.subtitle")))

        # Build 5 dropdown rows
        self._combos = {}
        dimensions = ["entry_point", "hook_library", "injection_entry",
                      "file_passthrough", "injection_mode"]
        from ..core import injector_config

        for dim in dimensions:
            row = QHBoxLayout()
            row.addWidget(QLabel(t(f"advanced.{dim}")))
            combo = QComboBox()
            for opt in injector_config.OPTIONS[dim]:
                label = opt.get(f"label_{lang}", opt.get("label_zh", opt["value"]))
                combo.addItem(label, opt["value"])
            row.addWidget(combo, 1)
            lyt.addLayout(row)
            self._combos[dim] = combo

        # Load current config
        cfg = injector_config.load(game_dir)
        for dim, combo in self._combos.items():
            val = cfg.get(dim)
            for i in range(combo.count()):
                if combo.itemData(i) == val:
                    combo.setCurrentIndex(i); break

        lyt.addStretch()

        # Save button
        save_btn = QPushButton(t("advanced.save"))
        save_btn.clicked.connect(self._on_save)
        lyt.addWidget(save_btn)

        # Apply font size
        self.setStyleSheet(f"font-size:{font_size}px;")

    def _on_save(self):
        from ..core import injector_config
        cfg = {dim: combo.currentData() for dim, combo in self._combos.items()}
        injector_config.save(self._gd, cfg)
        t = self._t
        QMessageBox.information(self, t("advanced.saved.title"), t("advanced.saved.text"))
        self.accept()


class DetailDialog(QDialog):
    def __init__(self, parent, info, game_dir, lang, font_size):
        super().__init__(parent)
        t = lambda k: tr(lang, k)
        self.setWindowTitle(info['name'] + t("detail.title")); self.setMinimumSize(440, 420)
        self._info, self._game_dir, self._t = info, game_dir, t
        lyt = QVBoxLayout(self)
        lyt.addWidget(QPushButton(t("btn.back"), clicked=self.accept), alignment=Qt.AlignLeft)
        fm = QFormLayout()
        for k in ["name","author","version","desc","gamever"]: fm.addRow(t(f"detail.{k}"), QLabel(str(info.get(k,""))))
        fm.addRow(t("detail.deps"), QLabel(_fd(info.get("dependencies",[]), lang)))
        fm.addRow(t("detail.conflicts"), QLabel(_fd(info.get("conflicts",[]), lang)))
        lyt.addLayout(fm)
        lyt.addWidget(QLabel(t("detail.files")))
        for fn, sz in sorted(info.get("files",{}).items()):
            r = QHBoxLayout(); r.addWidget(QLabel(fn))
            sl = QLabel(_fmt_size(sz)); sl.setAlignment(Qt.AlignRight); r.addWidget(sl)
            lyt.addLayout(r)
        lyt.addWidget(QLabel(f"{t('detail.total')}{_fmt_size(info.get('totalSize',0))}"))
        ub = QPushButton(t("btn.uninstall")); ub.clicked.connect(self._uninstall)
        lyt.addWidget(ub, alignment=Qt.AlignCenter)

    def _uninstall(self):
        t = self._t
        if cli_engine.is_game_running(): QMessageBox.warning(self, t("game.running.title"), t("game.running.msg")); return
        if QMessageBox.question(self, "", f"{t('confirm.uninstall')} {self._info['name']}？") != QMessageBox.Yes: return
        try: cli_engine.cmd_uninstall(self._info['name']); self.accept()
        except Exception as e: QMessageBox.critical(self, "Error", str(e))


class SettingsDialog(QDialog):
    def __init__(self, parent, game_dir, main_window):
        super().__init__(parent)
        t = main_window._t
        self.setWindowTitle(t("settings.title")); self.setMinimumSize(420, 440)
        self._gd, self._mw = game_dir, main_window
        lyt = QVBoxLayout(self)
        lyt.addWidget(QPushButton(t("btn.back"), clicked=self.accept), alignment=Qt.AlignLeft)

        lyt.addWidget(QLabel(t("settings.lang")))
        lang_cb = QComboBox()
        lang_cb.addItems(["中文","English","日本語"])
        lang_cb.setCurrentIndex({"zh":0,"en":1,"ja":2}.get(main_window._lang, 0))
        lang_cb.currentIndexChanged.connect(lambda i: main_window._change_lang({0:"zh",1:"en",2:"ja"}[i]))
        lyt.addWidget(lang_cb)

        lyt.addWidget(QLabel(t("settings.font_size")))
        fs = QSpinBox(); fs.setRange(9,24); fs.setValue(main_window._font_size)
        fs.valueChanged.connect(main_window._change_font)
        lyt.addWidget(fs)

        lyt.addWidget(QLabel(t("settings.theme")))
        theme_cb = QComboBox()
        theme_keys = list(THEMES.keys())
        theme_cb.addItems([THEMES[k]["name"] for k in theme_keys])
        cur_idx = theme_keys.index(main_window._theme) if main_window._theme in theme_keys else 0
        theme_cb.setCurrentIndex(cur_idx)
        theme_cb.currentIndexChanged.connect(lambda i: main_window._change_theme(theme_keys[i]))
        lyt.addWidget(theme_cb)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        lyt.addWidget(sep)

        lyt.addWidget(QLabel(t("settings.env")))
        lyt.addWidget(QLabel(t("settings.env.desc")))
        lyt.addWidget(QPushButton(t("btn.env_check"), clicked=self._env))
        lyt.addWidget(QLabel(t("settings.registry")))
        lyt.addWidget(QLabel(t("settings.registry.desc")))
        lyt.addWidget(QPushButton(t("btn.open_dir"), clicked=self._open))
        lyt.addWidget(QLabel(t("settings.assoc")))
        ar = QHBoxLayout()
        ar.addWidget(QPushButton(t("btn.register"), clicked=self._reg))
        ar.addWidget(QPushButton(t("btn.unregister"), clicked=self._unreg))
        lyt.addLayout(ar)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setFrameShadow(QFrame.Sunken)
        lyt.addWidget(sep2)
        lyt.addWidget(QLabel(t("settings.dev_info")))
        dev_lbl = QLabel(t("settings.dev_info.text")); dev_lbl.setWordWrap(True)
        lyt.addWidget(dev_lbl)

    def _env(self):
        r = deploy.setup(self._gd)
        QMessageBox.information(self, "", f"{r['dirs_created']} dirs, {r['files_extracted']} files")
    def _open(self):
        d = os.path.join(self._gd, "elsmod_data"); os.makedirs(d, exist_ok=True); os.startfile(d)
    def _reg(self):
        from ..core import elsmod_register; elsmod_register.register()
        QMessageBox.information(self, "", self._mw._t("assoc.registered"))
    def _unreg(self):
        from ..core import elsmod_register; elsmod_register.unregister()
        QMessageBox.information(self, "", self._mw._t("assoc.unregistered"))


class DevPanel(QDialog):
    def __init__(self, parent, game_dir, lang):
        super().__init__(parent)
        t = lambda k: tr(lang, k)
        self.setWindowTitle(t("dev.title")); self.setMinimumSize(560, 480)
        self._gd, self._t, self._lang = game_dir, t, lang
        lyt = QVBoxLayout(self)
        lyt.addWidget(QLabel(t("dev.subtitle")))
        tabs = QTabWidget(); lyt.addWidget(tabs)
        # Dev tools tab
        dev_tab = QWidget(); dtl = QVBoxLayout(dev_tab)
        dtl.addWidget(QLabel("— 项目管理 —"))
        for k in ["pack","unpack","template"]:
            dtl.addWidget(QPushButton(t(f"btn.{k}"), clicked=getattr(self, f"_{k}")))
        dtl.addWidget(QLabel("— 开发工具 —"))
        dtl.addWidget(QPushButton("验证 elsmod", clicked=self._validate_elsmod))
        dtl.addWidget(QPushButton("查看 plugin.json", clicked=self._view_json))
        dtl.addWidget(QPushButton("孤立启动", clicked=self._isolated_launch))
        dtl.addStretch(); tabs.addTab(dev_tab, "开发工具")
        # CLI tab
        tw = QWidget(); tl = QVBoxLayout(tw)
        self._cli = QTextEdit(); self._cli.setReadOnly(True)
        self._cli.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        tl.addWidget(self._cli)
        tabs.addTab(tw, t("dev.tab.cli"))
        _cli_sinks.append(self._log)
        # Links tab
        tww = QWidget(); twl = QVBoxLayout(tww)
        for tool in cli_engine.cmd_tools_list():
            r = QHBoxLayout()
            r.addWidget(QLabel(f"{tool['name']} — {tool['description']}"))
            r.addWidget(QPushButton("Open", clicked=lambda _, u=tool["url"]: webbrowser.open(u)))
            twl.addLayout(r)
        twl.addStretch(); tabs.addTab(tww, t("dev.tab.tools"))

    def _log(self, m): self._cli.append(m)
    def _pack(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择插件 JS 文件", self._gd, "JavaScript (*.js)")
        if not fp: return
        self._log(f"> pack \"{fp}\"")
        try:
            r = cli_engine.cmd_pack(fp)
            self._log(f"  OK: {r['packed']}")
            QMessageBox.information(self, "打包完成", f"{r['name']} v{r['version']}\n→ {r['packed']}")
        except Exception as e:
            self._log(f"  ERROR: {e}")
            QMessageBox.critical(self, "打包失败", str(e))
    def _unpack(self):
        f, _ = QFileDialog.getOpenFileName(self, "", "", "*.elsmod")
        if not f: return
        d = QFileDialog.getExistingDirectory(self)
        if not d: return
        self._log(f"> ElushaInjector.exe --cli unpack \"{f}\" -o \"{d}\"")
        try: self._log(f"  OK: {cli_engine.cmd_unpack(f, d)['unpacked']}")
        except Exception as e: self._log(f"  ERROR: {e}"); QMessageBox.critical(self, "Error", str(e))
    def _template(self):
        t = self._t
        dlg = QDialog(self); dlg.setWindowTitle("Template"); dlg.setMinimumSize(360, 200)
        l = QVBoxLayout(dlg)
        l.addWidget(QLabel(t("template.name"))); ne = QLineEdit(); l.addWidget(ne)
        l.addWidget(QLabel(t("template.author"))); ae = QLineEdit(); l.addWidget(ae)
        l.addWidget(QLabel(t("template.dir"))); dr = QHBoxLayout()
        de = QLineEdit(); dr.addWidget(de)
        dr.addWidget(QPushButton(t("btn.browse"), clicked=lambda: de.setText(QFileDialog.getExistingDirectory(dlg)))); l.addLayout(dr)
        def _do():
            n, a, d = ne.text(), ae.text(), de.text()
            self._log(f"> ElushaInjector.exe --cli template --name \"{n}\" --author \"{a}\" --dir \"{d}\"")
            try: r = cli_engine.cmd_template(n, a, d); self._log(f"  OK: {r['templateCreated']}"); dlg.accept()
            except Exception as e: self._log(f"  ERROR: {e}"); QMessageBox.critical(dlg, "Error", str(e))
        l.addWidget(QPushButton(t("btn.generate"), clicked=_do))
        dlg.exec()


    def _validate_elsmod(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择 elsmod", "", "*.elsmod")
        if not fp: return
        self._log(f"> validate \"{fp}\"")
        try:
            r = cli_engine.cmd_validate(fp)
            msg = f"✓ 验证通过\n\n名称: {r['name']}\n版本: {r['version']}\n作者: {r['author']}\n文件数: {r['files']}"
            self._log(msg.replace("\n", "  "))
            QMessageBox.information(self, "验证结果", msg)
        except Exception as e:
            self._log(f"  ✗ {e}")
            QMessageBox.warning(self, "验证结果", f"✗ 验证失败\n\n{e}")

    def _view_json(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择 elsmod 文件", "", "*.elsmod")
        if not fp: return
        self._log(f"> view-json \"{fp}\"")
        try:
            import json, zipfile
            with zipfile.ZipFile(fp, "r") as zf:
                json_path = None
                for name in zf.namelist():
                    if name.endswith("plugin.json") and "/data/" in name:
                        json_path = name; break
                if not json_path:
                    raise ValueError("elsmod 内未找到 plugin.json")
                data = json.loads(zf.read(json_path).decode("utf-8"))
            text = json.dumps(data, ensure_ascii=False, indent=2)
            self._log(text[:200] + "..." if len(text) > 200 else text)
            dlg = QDialog(self)
            dlg.setWindowTitle(f"plugin.json — {data.get('name', '?')}")
            dlg.setMinimumSize(500, 400)
            l = QVBoxLayout(dlg)
            te = QTextEdit(); te.setReadOnly(True); te.setPlainText(text)
            l.addWidget(te)
            l.addWidget(QPushButton("关闭", clicked=dlg.accept))
            dlg.exec()
        except Exception as e:
            self._log(f"  ERROR: {e}")
            QMessageBox.warning(self, "错误", str(e))

    def _isolated_launch(self):
        if cli_engine.is_game_running():
            QMessageBox.warning(self, "", "请先关闭游戏")
            return
        fp, _ = QFileDialog.getOpenFileName(self, "选择 elsmod", "", "*.elsmod")
        if not fp: return
        self._log(f"> isolated-launch \"{fp}\"")
        try:
            from ..core import registry, installer
            # Save current state
            reg = registry.load(self._gd)
            saved = [(r["name"], r.get("enabled", False)) for r in reg["records"]]
            # Install the plugin
            rec = installer.install(self._gd, fp)
            # Disable all except this one
            reg = registry.load(self._gd)
            for r in reg["records"]:
                r["enabled"] = (r["name"] == rec["name"])
            registry.save(self._gd, reg)
            from ..core.cli_engine import _sync_enabled_plugins
            _sync_enabled_plugins(self._gd)
            # Launch
            cli_engine.cmd_launch()
            self._log(f"  已启动，仅启用 {rec['name']}，游戏关闭后自动恢复")
            # Restore after game closes
            def _restore():
                import time
                while cli_engine.is_game_running(): time.sleep(2)
                time.sleep(3)
                # Uninstall the temp plugin
                try: installer.uninstall(self._gd, rec["name"])
                except Exception: pass
                reg2 = registry.load(self._gd)
                for r in reg2["records"]:
                    for sn, se in saved:
                        if r["name"] == sn: r["enabled"] = se; break
                registry.save(self._gd, reg2)
                _sync_enabled_plugins(self._gd)
            import threading
            threading.Thread(target=_restore, daemon=True).start()
        except Exception as e:
            self._log(f"  ERROR: {e}")
            QMessageBox.critical(self, "错误", str(e))



def _fd(deps, lang):
    if not deps: return tr(lang, "detail.none")
    return ", ".join(f"{d.get('name','?')} {d.get('version','')}" for d in deps)


def run(dev_mode=False):
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    # Suppress MS Sans Serif fallback warnings
    f = QFont("Segoe UI", 10)
    app.setFont(f)
    try:
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Injector_logo.ico")
        if os.path.exists(ico): app.setWindowIcon(QIcon(ico))
    except Exception: pass
    w = MainWindow(dev_mode=dev_mode)
    w.show()
    sys.exit(app.exec())
