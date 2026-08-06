"""CLI engine — all injector functionality. Returns dicts (JSON-serializable).
GUI is a thin wrapper that calls these functions and displays results."""
import json
import os
import subprocess
import sys
from typing import Optional

from . import registry, elsmod, installer, deploy, dependency


def _game_dir() -> str:
    """Detect game directory. Raises SystemExit if not in game dir."""
    d = os.getcwd()
    if not deploy.is_game_directory(d):
        raise SystemExit("错误：当前目录不包含 Game.exe。请将程序放到游戏目录下运行。")
    return d


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
    gd = _game_dir()
    if not os.path.isfile(elsmod_path):
        raise FileNotFoundError(f"文件不存在：{elsmod_path}")
    rec = installer.install(gd, elsmod_path)
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


def cmd_pack(source_dir: str, output_path: str) -> dict:
    """Pack a directory into an elsmod."""
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"目录不存在：{source_dir}")
    elsmod.pack(source_dir, output_path)
    return {"packed": output_path}


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
        "gameVersion": "1.051",
        "dependencies": [],
        "conflicts": [],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"templateCreated": target_dir,
            "pluginJson": json_path, "pluginJs": js_path}


def cmd_launch(skip_plugins: bool = False) -> dict:
    """Launch Game.exe."""
    gd = _game_dir()
    exe = os.path.join(gd, "Game.exe")
    if not os.path.isfile(exe):
        raise FileNotFoundError("Game.exe 不存在")
    subprocess.Popen([exe], cwd=gd, creationflags=0x08000000)
    return {"launched": True, "skipPlugins": skip_plugins}


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
        {"name": "ElushaInjector", "url": "https://github.com/example/elusha-injector",
         "description": "艾露莎注入器源码"},
    ]


def _sync_enabled_plugins(game_dir: str):
    """Write elsmod_data/enabled_plugins.txt for DLL consumption."""
    from . import registry
    reg = registry.load(game_dir)
    load_order = reg.get("loadOrder", [])
    enabled = set()
    for rec in reg.get("records", []):
        if rec.get("enabled", False):
            enabled.add(rec["name"])

    path = os.path.join(game_dir, "elsmod_data", "enabled_plugins.txt")
    with open(path, "w", encoding="utf-8") as f:
        for name in load_order:
            if name in enabled:
                f.write(name + "\n")


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
