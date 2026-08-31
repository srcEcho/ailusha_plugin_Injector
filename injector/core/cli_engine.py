"""CLI engine — all injector functionality. Returns dicts (JSON-serializable).
GUI is a thin wrapper that calls these functions and displays results."""
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

from . import registry, elsmod, installer, deploy, dependency

# ── inline logger (no external deps) ──
def _get_log_dir():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    return os.path.join(os.path.dirname(os.path.abspath(exe_path)), "elsmod_data", "logs")

def _clog(msg: str):
    try:
        d = _get_log_dir()
        os.makedirs(d, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(d, "cli_engine.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}][PID={os.getpid()}] {msg}\n")
    except Exception:
        pass
_clog(f"=== START === exe={sys.executable} argv={sys.argv} cwd={os.getcwd()} frozen={getattr(sys, 'frozen', False)} ===")


def _game_dir() -> str:
    """Detect game directory. Tries: argv[0] path, executable dir, then CWD."""
    # First try: directory of the running executable
    # PyInstaller onefile: sys.executable is in TEMP, use sys.argv[0]
    # Nuitka standalone: sys.executable IS the actual EXE — always reliable
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            d = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            d = os.path.dirname(os.path.abspath(sys.executable))
    else:
        d = os.path.dirname(os.path.abspath(sys.argv[0]))

    # Fallbacks: CWD, then parent of executable dir
    for candidate in [d, os.getcwd(),
                      os.path.dirname(os.path.abspath(sys.argv[0]))]:
        _clog(f"_game_dir: trying candidate={candidate}  is_game_dir={deploy.is_game_directory(candidate)}")
        if deploy.is_game_directory(candidate):
            _clog(f"_game_dir: MATCH → {candidate}")
            return candidate

    _clog("_game_dir: NO MATCH — raising SystemExit")
    raise SystemExit("错误：当前目录不包含 Game.exe。请将程序放到游戏目录下运行。")


def cmd_setup(game_dir: Optional[str] = None) -> dict:
    """Run environment setup. Called automatically on startup."""
    gd = game_dir or os.getcwd()
    result = deploy.setup(gd)
    if not result["is_game_dir"]:
        raise SystemExit("错误：当前目录不包含 Game.exe。请将程序放到游戏目录下运行。")
    return result


def cmd_list(enabled_only: bool = False, disabled_only: bool = False) -> list[dict]:
    """List installed plugins."""
    gd = _game_dir()
    reg = registry.load(gd)
    records = reg["records"]

    if enabled_only:
        records = [r for r in records if r.get("enabled", False)]
    elif disabled_only:
        records = [r for r in records if not r.get("enabled", False)]

    # Add load order position
    load_order = reg.get("loadOrder", [])
    result = []
    for rec in records:
        entry = dict(rec)
        try:
            entry["order"] = load_order.index(rec["name"])
        except ValueError:
            entry["order"] = -1
        result.append(entry)

    # Sort by loadOrder
    result.sort(key=lambda r: r["order"] if r["order"] >= 0 else 999)
    return result


def cmd_info(name: str, author: Optional[str] = None) -> dict:
    """Get detailed info for a plugin."""
    gd = _game_dir()
    reg = registry.load(gd)
    rec = registry.find_record(reg, name, author)
    if not rec:
        raise ValueError(f"插件 '{name}' 未找到")

    # Get file sizes
    plugins_dir = os.path.join(gd, "www/js/plugins")
    files_with_size = {}
    total_size = 0
    for f in rec.get("files", []):
        fp = os.path.join(plugins_dir, f)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            files_with_size[f] = sz
            total_size += sz

    # Read metadata from plugin.json
    meta = {}
    json_path = None
    for f in rec.get("files", []):
        if f.endswith("plugin.json") and "/data/" in f:
            json_path = os.path.join(plugins_dir, f)
            break
    if json_path and os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception:
            pass

    return {
        "name": rec["name"],
        "author": rec.get("author", ""),
        "version": rec.get("version", ""),
        "description": meta.get("description", ""),
        "gameVersion": meta.get("gameVersion", ""),
        "enabled": rec.get("enabled", False),
        "source": rec.get("source", ""),
        "installedAt": rec.get("installedAt", ""),
        "totalSize": total_size,
        "dependencies": meta.get("dependencies", []),
        "conflicts": meta.get("conflicts", []),
        "files": files_with_size,
    }


def cmd_enable(name: str, author: Optional[str] = None) -> dict:
    """Enable a plugin. Checks dependencies. Does NOT reorder."""
    gd = _game_dir()
    reg = registry.load(gd)
    rec = registry.find_record(reg, name, author)
    if not rec:
        raise ValueError(f"插件 '{name}' 未找到")

    deps = dependency.check_dependencies_satisfied(reg, name, author)
    if deps:
        raise ValueError(f"缺少依赖：{', '.join(deps)}")

    cascade = []
    for dep_rec in reg["records"]:
        dep_name = dep_rec["name"]
        if dep_name == name:
            continue
        if dep_name in [d.get("name") for d in rec.get("dependencies", [])]:
            if not dep_rec.get("enabled", False):
                cascade.append(dep_name)

    if cascade:
        for cn in cascade:
            registry.set_enabled(reg, cn, True)

    registry.set_enabled(reg, name, True)
    registry.save(gd, reg)
    return {"enabled": True, "cascadeEnabled": cascade}


def cmd_disable(name: str, author: Optional[str] = None) -> dict:
    """Disable a plugin. Checks dependents."""
    gd = _game_dir()
    reg = registry.load(gd)

    # Find dependents
    dependents = dependency.find_dependents(reg, name)
    cascade = []
    for dn in dependents:
        if dn == name:
            continue
        cascade.append(dn)
        registry.set_enabled(reg, dn, False)

    registry.set_enabled(reg, name, False)
    registry.save(gd, reg)
    return {"disabled": True, "cascadeDisabled": cascade}


def cmd_install(elsmod_path: str) -> dict:
    """Install a plugin from elsmod."""
    _clog(f"cmd_install: elsmod_path={elsmod_path}")
    gd = _game_dir()
    _clog(f"cmd_install: game_dir={gd}")
    if not os.path.isfile(elsmod_path):
        raise FileNotFoundError(f"文件不存在：{elsmod_path}")
    rec = installer.install(gd, elsmod_path)
    _clog(f"cmd_install: installed {rec['name']} v{rec['version']}")
    return {"installed": rec["name"], "version": rec["version"], "author": rec.get("author", "")}


def cmd_uninstall(name: str, author: Optional[str] = None) -> dict:
    """Uninstall a plugin."""
    gd = _game_dir()
    reg = registry.load(gd)

    # Check dependents
    dependents = dependency.find_dependents(reg, name)
    dependents = [d for d in dependents if d != name]
    cascade = []
    for dn in dependents:
        cascade.append(dn)
        installer.uninstall(gd, dn)

    rec = installer.uninstall(gd, name, author)
    if not rec:
        raise ValueError(f"插件 '{name}' 未找到")
    return {"uninstalled": name, "cascadeUninstalled": cascade}


def cmd_repair(name: str, author: Optional[str] = None) -> dict:
    """Repair a broken plugin."""
    gd = _game_dir()
    installer.repair(gd, name, author)
    return {"repaired": name}


def cmd_check_broken() -> list[dict]:
    """Check for broken plugins (files missing)."""
    gd = _game_dir()
    return installer.check_integrity(gd)


def cmd_imported() -> list[str]:
    """List imported elsmod files."""
    gd = _game_dir()
    elsmod_dir = os.path.join(gd, "elsmod_data")
    if not os.path.isdir(elsmod_dir):
        return []
    return sorted([f for f in os.listdir(elsmod_dir) if f.endswith(".elsmod")])


def cmd_pack(js_path: str, output_path: str = None) -> dict:
    """Pack a plugin JS file (and its data dir) into an elsmod.
    Auto-discovers data/<name>_<author>/ directory alongside the JS file."""
    if not os.path.isfile(js_path):
        raise FileNotFoundError(f"JS 文件不存在：{js_path}")
    if not js_path.endswith(".js"):
        raise ValueError("请选择 .js 插件文件")

    plugins_dir = os.path.dirname(os.path.abspath(js_path))
    js_name = os.path.splitext(os.path.basename(js_path))[0]
    data_dir = os.path.join(plugins_dir, "data")

    # Find matching data directory: data/<js_name>_<author>/
    if not os.path.isdir(data_dir):
        raise ValueError(f"data 目录不存在：{data_dir}")

    candidates = []
    for entry in os.listdir(data_dir):
        full = os.path.join(data_dir, entry)
        if os.path.isdir(full) and entry.startswith(js_name + "_"):
            plugin_json = os.path.join(full, "plugin.json")
            if os.path.isfile(plugin_json):
                candidates.append((entry, full, plugin_json))

    if not candidates:
        raise ValueError(f"未找到匹配的 data 目录（data/{js_name}_<作者>/）")
    if len(candidates) > 1:
        names = [c[0] for c in candidates]
        raise ValueError(f"找到多个匹配的 data 目录，请手动选择：{', '.join(names)}")

    data_name, data_path, json_path = candidates[0]

    # Validate plugin.json name matches
    import json
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("name") != js_name:
        raise ValueError(f"plugin.json 中 name='{meta.get('name')}' 与 JS 文件名 '{js_name}.js' 不一致")

    # Build temp structure and pack
    import tempfile, shutil
    tmp = tempfile.mkdtemp()
    try:
        www_plugins = os.path.join(tmp, "www", "js", "plugins")
        os.makedirs(www_plugins, exist_ok=True)
        shutil.copy2(js_path, os.path.join(www_plugins, os.path.basename(js_path)))
        dst_data = os.path.join(www_plugins, "data", data_name)
        shutil.copytree(data_path, dst_data)

        if not output_path:
            ver = meta.get("version", "0.1.0")
            output_path = os.path.join(os.path.dirname(js_path), f"{js_name}-{ver}.elsmod")
        elsmod.pack(tmp, output_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {"packed": output_path, "name": js_name, "version": meta.get("version", "?")}


def cmd_unpack(elsmod_path: str, output_dir: str) -> dict:
    """Unpack an elsmod to a directory."""
    if not os.path.isfile(elsmod_path):
        raise FileNotFoundError(f"文件不存在：{elsmod_path}")
    elsmod.unpack(elsmod_path, output_dir)
    return {"unpacked": output_dir}


def cmd_template(name: str, author: str, target_dir: str) -> dict:
    """Generate standard plugin project template."""
    plugins_dir = os.path.join(target_dir, "www", "js", "plugins")
    data_dir = os.path.join(plugins_dir, "data", f"{name}_{author}")
    os.makedirs(data_dir, exist_ok=True)

    # Create empty .js file
    js_path = os.path.join(plugins_dir, f"{name}.js")
    if not os.path.exists(js_path):
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(f"// {name}.js\n// TODO: plugin code\n")

    # Create plugin.json
    json_path = os.path.join(data_dir, "plugin.json")
    meta = {
        "name": name,
        "version": "0.1.0",
        "author": author,
        "description": "TODO: plugin description",
        "gameVersion": "1.06",
        "dependencies": [],
        "conflicts": [],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"templateCreated": target_dir,
            "pluginJson": json_path, "pluginJs": js_path}


def cmd_move_up(name: str) -> dict:
    """Move plugin up one position in loadOrder."""
    gd = _game_dir()
    reg = registry.load(gd)
    lo = reg.get("loadOrder", [])
    if name not in lo:
        raise ValueError(f"插件 '{name}' 不在排序列表中")
    i = lo.index(name)
    if i > 0:
        lo[i], lo[i - 1] = lo[i - 1], lo[i]
        reg["loadOrder"] = lo
        registry.save(gd, reg)
    return {"name": name, "position": max(0, i - 1)}


def cmd_move_down(name: str) -> dict:
    """Move plugin down one position in loadOrder."""
    gd = _game_dir()
    reg = registry.load(gd)
    lo = reg.get("loadOrder", [])
    if name not in lo:
        raise ValueError(f"插件 '{name}' 不在排序列表中")
    i = lo.index(name)
    if i < len(lo) - 1:
        lo[i], lo[i + 1] = lo[i + 1], lo[i]
        reg["loadOrder"] = lo
        registry.save(gd, reg)
    return {"name": name, "position": min(len(lo) - 1, i + 1)}


def cmd_reorder(order: list[str]) -> dict:
    """Set the entire loadOrder (from drag-drop)."""
    gd = _game_dir()
    reg = registry.load(gd)
    reg["loadOrder"] = order
    registry.save(gd, reg)
    return {"loadOrder": order}


def cmd_launch(skip_plugins: bool = False, exe_name: str = None) -> dict:
    """Launch game. If exe_name is given, use it directly. Otherwise detect Game.exe/nw.exe."""
    gd = _game_dir()
    _clog(f"cmd_launch: game_dir={gd} exe_name={exe_name} skip_plugins={skip_plugins}")
    # Sync before launch — same as the GUI (_on_launch). Without this, CLI-only
    # users never get injector_config.json/bootstraps/originals, the DLL finds
    # no redirects and injects nothing.
    try:
        _sync_enabled_plugins(gd)
    except Exception as e:
        _clog(f"cmd_launch: sync failed, continuing: {type(e).__name__}: {e}")
    if exe_name:
        exe = os.path.join(gd, exe_name)
        if not os.path.isfile(exe):
            raise FileNotFoundError(f"{exe_name} 不存在")
        mode = "custom"
    else:
        mode = deploy.game_mode(gd)
        if mode == "packed":
            exe = os.path.join(gd, "Game.exe")
            if not os.path.isfile(exe):
                raise FileNotFoundError("Game.exe 不存在")
        elif mode == "unpacked":
            exe = os.path.join(gd, "nw.exe")
            if not os.path.isfile(exe):
                raise FileNotFoundError("nw.exe 不存在")
        else:
            raise FileNotFoundError("未找到可执行文件 (Game.exe 或 nw.exe)")

    # Launch via ShellExecuteW with explicit working directory.
    # os.startfile() passes NULL lpDirectory → new process inherits
    # calling process CWD. When injector was launched via .elsmod file
    # association, CWD is the .elsmod file's directory (NOT the game dir).
    # The bootstrap template uses process.cwd() for ALL file paths, so the
    # game MUST start with the game directory as its CWD.
    import ctypes
    _clog(f"cmd_launch: ShellExecuteW(open, {os.path.basename(exe)}, lpDirectory={gd})")
    ctypes.windll.shell32.ShellExecuteW(None, "open", exe, None, gd, 1)
    _clog("cmd_launch: game launched")
    return {"launched": True, "mode": mode, "skipPlugins": skip_plugins}


def cmd_config() -> dict:
    """Show current configuration."""
    gd = _game_dir()
    return {
        "gameDir": gd,
        "hasGameExe": os.path.isfile(os.path.join(gd, "Game.exe")),
        "hasVersionDll": os.path.isfile(os.path.join(gd, "version.dll")),
        "hasElsmodDir": os.path.isdir(os.path.join(gd, "elsmod_data")),
    }


def cmd_tools_list() -> list[dict]:
    """List recommended developer tools."""
    return [
        {"name": "MinHook", "url": "https://github.com/TsudaKageyu/minhook",
         "description": "Windows API Hook 库"},
        {"name": "Ghidra", "url": "https://github.com/NationalSecurityAgency/ghidra",
         "description": "逆向工程工具"},
        {"name": "evbunpack", "url": "https://github.com/mos9527/evbunpack",
         "description": "EnigmaVB 解包工具"},
        {"name": "ElushaInjector", "url": "https://github.com/srcEcho/ailusha_plugin_Injector",
         "description": "艾露莎注入器源码"},
    ]


def _sync_enabled_plugins(game_dir: str):
    """Sync plugins to game: write injector_config.json (packed) or edit plugins.js (unpacked)."""
    from . import registry, injector_config
    _clog(f"_sync_enabled_plugins: game_dir={game_dir}")
    mode = deploy.game_mode(game_dir)
    reg = registry.load(game_dir)
    load_order = reg.get("loadOrder", [])
    enabled = set()
    for rec in reg.get("records", []):
        if rec.get("enabled", False):
            enabled.add(rec["name"])
    _clog(f"_sync_enabled_plugins: mode={mode} enabled={list(enabled)} load_order={load_order}")

    if mode == "packed":
        cfg = injector_config.load(game_dir)
        _clog(f"_sync_enabled_plugins: loaded config — injection_mode={cfg.get('injection_mode')} redirects={cfg.get('redirects')} plugins_before={cfg.get('plugins')}")
        # Update plugins list
        cfg["plugins"] = [n for n in load_order if n in enabled]

        # If bootstrap mode and no redirects exist, add a default one
        if cfg.get("injection_mode") == "bootstrap" and not cfg.get("redirects"):
            _clog("_sync_enabled_plugins: adding default redirect (EventInformation.js → EventInformation_bootstrap.js)")
            cfg["redirects"] = [
                {"target": "EventInformation.js",
                 "source": "EventInformation_bootstrap.js"}
            ]

        injector_config.save(game_dir, cfg)
        _clog(f"_sync_enabled_plugins: config saved — plugins={cfg['plugins']} redirects={cfg.get('redirects')}")

        # Generate bootstrap files + copy originals
        plugin_files = {}
        for rec in reg.get("records", []):
            if rec.get("enabled", False):
                name = rec["name"]
                plugin_files[name] = f"www/js/plugins/{name}.js"
        _clog(f"_sync_enabled_plugins: generating bootstraps for {list(plugin_files.keys())}")
        # Try to copy originals from unpacked game or existing originals
        originals = deploy._ensure_originals(game_dir, cfg)
        _clog(f"_sync_enabled_plugins: _ensure_originals → {len(originals)} files")
        bootstraps = deploy._generate_bootstraps(game_dir, cfg, plugin_files)
        _clog(f"_sync_enabled_plugins: _generate_bootstraps → {len(bootstraps)} files: {[os.path.basename(b) for b in bootstraps]}")

        # Also write enabled_plugins.txt for backward compatibility
        path = os.path.join(game_dir, "elsmod_data", "enabled_plugins.txt")
        with open(path, "w", encoding="utf-8") as f:
            for name in load_order:
                if name in enabled:
                    f.write(name + "\n")
    elif mode == "unpacked":
        _sync_unpacked_plugins(game_dir, [n for n in load_order if n in enabled])


def _parse_js_array_entries(text: str) -> list[str]:
    """Parse JS array text into individual top-level object entries.

    Handles nested braces inside string values (e.g. JSON in ``parameters``).
    Returns a list of raw entry strings (including outer braces)."""
    entries = []
    i = 0
    n = len(text)

    while i < n:
        c = text[i]
        # Skip whitespace and commas between entries
        if c in " \t\r\n,":
            i += 1
            continue
        if c == "{":
            depth = 0
            start = i
            in_string = False
            escape = False
            while i < n:
                ch = text[i]
                if escape:
                    escape = False
                    i += 1
                    continue
                if ch == "\\":
                    escape = True
                    i += 1
                    continue
                if ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            entries.append(text[start:i + 1])
                            i += 1
                            break
                i += 1
        else:
            i += 1

    return entries


def _find_array_end(content: str, bracket_start: int) -> int:
    """Find the matching ``]`` for the ``[`` at bracket_start.

    String‑aware: ignores ``[`` / ``]`` inside double‑quoted strings (including
    escape sequences like ``\\"``).  Returns -1 if no match is found."""
    depth = 0
    in_string = False
    escape = False
    for i in range(bracket_start, len(content)):
        ch = content[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _sync_unpacked_plugins(game_dir: str, enabled_plugins: list[str]):
    """Sync mod plugins into www/js/plugins.js for unpacked (non-Enigma) games.

    Strategy:
      1. On first use: backup original plugins.js → elsmod_data/originals/
      2. APPEND mod plugins to the existing $plugins array (preserving built-ins)
      3. When all mods are disabled: restore original from backup
      4. Corruption detection: if the file is broken, auto-restore from backup
    """
    path = os.path.join(game_dir, "www", "js", "plugins.js")
    originals_dir = os.path.join(game_dir, "elsmod_data", "originals", "www", "js")
    backup_path = os.path.join(originals_dir, "plugins.js")
    _clog(f"_sync_unpacked_plugins: path={path} enabled={enabled_plugins}")

    # ── Check source file exists ──
    if not os.path.isfile(path):
        _clog(f"_sync_unpacked_plugins: plugins.js MISSING at {path}")

    # ── Empty mod list → restore from backup ──
    if not enabled_plugins:
        if os.path.isfile(backup_path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(backup_path, path)
            _clog("_sync_unpacked_plugins: all mods disabled — restored from backup")
        return

    # ── Ensure source file exists (try restore from backup) ──
    if not os.path.isfile(path):
        if os.path.isfile(backup_path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(backup_path, path)
            _clog("_sync_unpacked_plugins: restored missing plugins.js from backup")
        else:
            _clog("_sync_unpacked_plugins: no source and no backup — aborting")
            return

    # ── Read current file ──
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # ── Locate & validate $plugins array ──
    var_pos = content.find("var $plugins")
    if var_pos < 0:
        _clog("_sync_unpacked_plugins: CORRUPTED — 'var $plugins' not found, restoring backup")
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            var_pos = content.find("var $plugins")
        if var_pos < 0:
            _clog("_sync_unpacked_plugins: backup also broken — aborting")
            return

    bracket_start = content.find("[", var_pos)
    if bracket_start < 0:
        _clog("_sync_unpacked_plugins: CORRUPTED — no opening bracket after $plugins, restoring backup")
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            var_pos = content.find("var $plugins")
            bracket_start = content.find("[", var_pos) if var_pos >= 0 else -1
        if bracket_start < 0:
            _clog("_sync_unpacked_plugins: backup also broken — aborting")
            return

    # Find matching ] — string‑aware to avoid false matches inside strings
    bracket_end = _find_array_end(content, bracket_start)
    if bracket_end < 0:
        _clog("_sync_unpacked_plugins: CORRUPTED — unclosed bracket, restoring backup")
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            var_pos = content.find("var $plugins")
            bracket_start = content.find("[", var_pos) if var_pos >= 0 else -1
            if bracket_start >= 0:
                bracket_end = _find_array_end(content, bracket_start)
        if bracket_end < 0:
            _clog("_sync_unpacked_plugins: backup also broken — aborting")
            return

    # ── Parse existing entries ──
    array_text = content[bracket_start + 1:bracket_end]
    existing_entries = _parse_js_array_entries(array_text)
    _clog(f"_sync_unpacked_plugins: parsed {len(existing_entries)} existing entries")

    # ── Collect mod plugin names from registry ──
    mod_names = set()
    try:
        reg = registry.load(game_dir)
        for rec in reg.get("records", []):
            mod_names.add(rec["name"])
    except Exception:
        pass
    _clog(f"_sync_unpacked_plugins: {len(mod_names)} mod names in registry")

    # ── Filter: keep built-in plugins, remove previously-injected mod plugins ──
    kept_entries = []
    removed = []
    for entry_str in existing_entries:
        m = re.search(r'"name"\s*:\s*"([^"]+)"', entry_str)
        if m and m.group(1) in mod_names:
            removed.append(m.group(1))
            continue
        kept_entries.append(entry_str)
    if removed:
        _clog(f"_sync_unpacked_plugins: removed previously-injected mod entries: {removed}")

    # ── Append currently-enabled mod plugins ──
    # Verify the physical .js file exists before injecting — prevents
    # "Failed to load: js/plugins/X.js" at game startup after the file
    # was deleted (e.g. by uninstaller or manual cleanup).
    plugins_js_dir = os.path.join(game_dir, "www", "js", "plugins")
    skipped_missing = []
    for name in enabled_plugins:
        if not os.path.isfile(os.path.join(plugins_js_dir, f"{name}.js")):
            skipped_missing.append(name)
            _clog(f"_sync_unpacked_plugins: SKIPPING '{name}' — {name}.js not found in www/js/plugins/")
            continue
        kept_entries.append(
            json.dumps({"name": name, "status": True, "description": "", "parameters": {}},
                       ensure_ascii=False)
        )
    actual_count = len(enabled_plugins) - len(skipped_missing)
    _clog(f"_sync_unpacked_plugins: final array → {actual_count} mod + {len(kept_entries) - actual_count} built-in entries" +
          (f" (skipped {len(skipped_missing)}: {skipped_missing})" if skipped_missing else ""))

    # ── Rebuild array ──
    indent = "  "
    lines = ["["]
    for i, entry_str in enumerate(kept_entries):
        comma = "," if (i < len(kept_entries) - 1) else ""
        lines.append(indent + entry_str.strip() + comma)
    lines.append("]")
    new_array = "\r\n".join(lines)

    new_content = content[:bracket_start] + new_array + content[bracket_end + 1:]
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        _clog(f"_sync_unpacked_plugins: plugins.js written ({len(new_content)} bytes)")
    else:
        _clog("_sync_unpacked_plugins: no change needed")


def cmd_validate(elsmod_path: str) -> dict:
    """Validate an elsmod file without installing."""
    gd = _game_dir()
    if not os.path.isfile(elsmod_path):
        raise FileNotFoundError(f"文件不存在：{elsmod_path}")
    meta = elsmod.read_metadata(elsmod_path)
    files = elsmod.list_files(elsmod_path)
    return {"valid": True, "name": meta["name"], "version": meta["version"],
            "author": meta.get("author", ""), "files": len(files)}


def cmd_view_json(name: str) -> dict:
    """Return full plugin.json content for a plugin."""
    gd = _game_dir()
    reg = registry.load(gd)
    rec = registry.find_record(reg, name)
    if not rec:
        raise ValueError(f"插件 '{name}' 未找到")
    plugins_dir = os.path.join(gd, "www/js/plugins")
    for f in rec.get("files", []):
        if f.endswith("plugin.json"):
            fp = os.path.join(plugins_dir, f)
            if os.path.isfile(fp):
                with open(fp, "r", encoding="utf-8") as fh:
                    return {"name": name, "pluginJson": json.loads(fh.read())}
    raise ValueError(f"插件 '{name}' 的 plugin.json 未找到")


def cmd_isolated_launch(name: str) -> dict:
    """Launch game with only the named plugin enabled. State is saved and restored."""
    gd = _game_dir()
    reg = registry.load(gd)
    # Save current state
    saved = [(r["name"], r.get("enabled", False)) for r in reg["records"]]
    # Disable all, enable only target
    for r in reg["records"]:
        r["enabled"] = (r["name"] == name)
    registry.save(gd, reg)
    _sync_enabled_plugins(gd)
    # Launch
    cmd_launch()
    # Restore state in background after game closes
    def _restore():
        import time
        while is_game_running():
            time.sleep(2)
        time.sleep(3)
        reg2 = registry.load(gd)
        for r in reg2["records"]:
            for sn, se in saved:
                if r["name"] == sn:
                    r["enabled"] = se
                    break
        registry.save(gd, reg2)
        _sync_enabled_plugins(gd)
    import threading
    threading.Thread(target=_restore, daemon=True).start()
    return {"isolatedLaunch": name, "savedCount": len(saved)}


def cmd_clean_orphans() -> dict:
    """Remove files in www/js/plugins/ not tracked by registry."""
    gd = _game_dir()
    reg = registry.load(gd)
    plugins_dir = os.path.join(gd, "www/js/plugins")
    # Build set of all tracked files
    tracked = set()
    for rec in reg.get("records", []):
        for f in rec.get("files", []):
            tracked.add(f.replace("\\", "/"))
    # Scan for orphans
    orphan_files = []
    orphan_dirs = []
    for root, dirs, files in os.walk(plugins_dir, topdown=False):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, plugins_dir).replace("\\", "/")
            if rel not in tracked and rel != "plugin.registry.json":
                orphan_files.append(full)
        # Remove empty dirs after files
        for d in dirs:
            full_d = os.path.join(root, d)
            try:
                if not os.listdir(full_d):
                    orphan_dirs.append(full_d)
            except Exception:
                pass
    return {"orphanFiles": len(orphan_files), "orphanDirs": len(orphan_dirs),
            "files": orphan_files, "dirs": orphan_dirs}


def cmd_clean_orphans_execute() -> dict:
    """Execute orphan cleanup."""
    result = cmd_clean_orphans()
    for f in result["files"]:
        try: os.remove(f)
        except Exception: pass
    for d in result["dirs"]:
        try: os.rmdir(d)
        except Exception: pass
    return {"cleaned": len(result["files"]) + len(result["dirs"])}


def cmd_dep_tree() -> str:
    """Generate text dependency tree of all enabled plugins."""
    gd = _game_dir()
    reg = registry.load(gd)
    records = {r["name"]: r for r in reg["records"]}

    def _tree(name: str, indent: str = "", visited: set = None) -> list[str]:
        if visited is None:
            visited = set()
        if name in visited:
            return [f"{indent}{name} (循环依赖!)"]
        visited.add(name)
        lines = [f"{indent}{name}"]
        rec = records.get(name, {})
        deps = rec.get("dependencies", [])
        for i, d in enumerate(deps):
            dn = d.get("name", "?")
            is_last = (i == len(deps) - 1)
            prefix = indent + ("  " if is_last else "│ ")
            child_lines = _tree(dn, prefix, visited.copy())
            for cl in child_lines:
                lines.append(cl)
        return lines

    # Find root plugins (not depended on by any other enabled plugin)
    enabled = {r["name"] for r in reg["records"] if r.get("enabled")}
    depended_on = set()
    for r in reg["records"]:
        if not r.get("enabled"): continue
        for d in r.get("dependencies", []):
            if d.get("name"): depended_on.add(d["name"])

    roots = [n for n in enabled if n not in depended_on]
    if not roots:
        roots = list(enabled)  # All interdependent

    lines = []
    for root in sorted(roots):
        lines.extend(_tree(root))
    return "\n".join(lines)


def _send_to_trash(filepath: str) -> bool:
    """Move a file to the Windows Recycle Bin. Returns True on success."""
    import ctypes
    from ctypes import wintypes
    flags = 0x0004 | 0x0040 | 0x0100  # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    buf = ctypes.create_unicode_buffer(filepath + "\0\0", len(filepath) + 2)
    shf = ctypes.windll.shell32.SHFileOperationW
    shf.restype = ctypes.c_int
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]
    op = SHFILEOPSTRUCTW()
    op.hwnd = 0; op.wFunc = 3  # FO_DELETE
    op.pFrom = buf; op.pTo = None; op.fFlags = flags
    return shf(ctypes.byref(op)) == 0


def cmd_version() -> dict:
    return {"name": "艾露莎注入器", "version": "1.0"}


def is_game_running() -> bool:
    """Check if Game.exe is currently running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Game.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000)
        return "Game.exe" in result.stdout
    except Exception:
        return False
