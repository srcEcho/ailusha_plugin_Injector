"""Environment deployment — directory creation, file extraction, bootstrap generation"""
import os
import shutil
import sys
from . import injector_config, registry

# ── inline logger (no external deps) ──
def _get_log_dir():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    return os.path.join(os.path.dirname(os.path.abspath(exe_path)), "elsmod_data", "logs")

def _dlog(msg: str):
    try:
        d = _get_log_dir()
        os.makedirs(d, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(d, "deploy.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}][PID={os.getpid()}] {msg}\n")
    except Exception:
        pass
_dlog(f"=== START === exe={sys.executable} argv={sys.argv} cwd={os.getcwd()} frozen={getattr(sys, 'frozen', False)} ===")

REQUIRED_DIRS = [
    "www/js/plugins",
    "www/js/plugins/data",
    "elsmod_data",
    "elsmod_data/tmp",
    "elsmod_data/logs",
    "elsmod_data/originals/www/js/plugins",
    "elsmod_data/bootstraps",
]

BOOTSTRAP_TEMPLATE = """(function(){{var f=require('fs'),p=require('path'),b=process.cwd();
try{{eval(f.readFileSync(p.join(b,'elsmod_data/originals/www/js/plugins/{original}'),'utf8'));}}catch(e){{}}
{loaders}
}})();"""

PLUGIN_LOADER = "try{{eval(f.readFileSync(p.join(b,'{path}'),'utf8'));}}catch(e){{}}\n"

EMBEDDED_FILES_PACKED = ["UninstallElusha.exe"]
EMBEDDED_FILES_UNPACKED = ["UninstallElusha.exe"]


def _extract_dll(game_dir: str) -> bool:
    """Extract version.dll from embedded base64 data.
    Respects injector_config.json for hook_library selection.
    Returns True on success."""
    dll_path = os.path.join(game_dir, "version.dll")

    # Read config to determine which DLL variant to deploy
    try:
        from . import injector_config
        cfg = injector_config.load(game_dir)
        hook_lib = cfg.get("hook_library", "minhook")
    except Exception:
        hook_lib = "minhook"

    # Build a version marker to detect config changes
    marker_path = os.path.join(game_dir, "elsmod_data", ".dll_version")
    current_marker = f"v={hook_lib}"
    if os.path.exists(dll_path) and os.path.exists(marker_path):
        try:
            with open(marker_path, "r") as f:
                if f.read().strip() == current_marker:
                    return True  # Already present with correct variant
        except Exception:
            pass

    # Extract the correct DLL variant
    try:
        import base64
        from . import _dll_data
        if hook_lib == "p5u5":
            data = base64.b64decode("".join(_dll_data.VERSION_DLL_V46_B64))
        else:
            data = base64.b64decode("".join(_dll_data.VERSION_DLL_B64))
        with open(dll_path, "wb") as f:
            f.write(data)
        with open(marker_path, "w") as f:
            f.write(current_marker)
        return True
    except Exception:
        return False


def _has_unpacked_layout(path: str) -> bool:
    """Check for NW.js unpacked layout: www/ with index.html + package.json + runtime DLLs."""
    return (os.path.isdir(os.path.join(path, "www")) and
            os.path.isfile(os.path.join(path, "www", "index.html")) and
            os.path.isfile(os.path.join(path, "package.json")) and
            any(os.path.isfile(os.path.join(path, d)) for d in ["nw.dll", "nw_elf.dll", "node.dll", "ffmpeg.dll"]))


def is_game_directory(path: str) -> bool:
    """Check if path is a valid game directory (packed or unpacked)."""
    if os.path.isfile(os.path.join(path, "Game.exe")):
        return True
    if _has_unpacked_layout(path):
        return True
    return False


def game_mode(path: str) -> str:
    """Return 'packed' or 'unpacked' based on directory layout.
    Unpacked: has www/index.html + package.json + NW.js runtime DLLs.
    Packed: has Game.exe (Enigma-packed, 1.4GB) but no NW.js layout."""
    if _has_unpacked_layout(path):
        return "unpacked"
    if os.path.isfile(os.path.join(path, "Game.exe")):
        return "packed"
    return "unknown"


def ensure_directories(game_dir: str) -> list[str]:
    """Create required directories. Returns list of created paths."""
    created = []
    for d in REQUIRED_DIRS:
        full = os.path.join(game_dir, d)
        if not os.path.isdir(full):
            os.makedirs(full, exist_ok=True)
            created.append(full)
    return created


def extract_embedded_files(game_dir: str, resource_dir: str) -> list[str]:
    """Extract embedded files from resource dir, based on game mode."""
    extracted = []
    mode = game_mode(game_dir)
    files = EMBEDDED_FILES_PACKED if mode == "packed" else EMBEDDED_FILES_UNPACKED
    for fn in files:
        dest = os.path.join(game_dir, fn)
        if os.path.exists(dest):
            continue
        src = os.path.join(resource_dir, fn)
        if os.path.isfile(src):
            shutil.copy2(src, dest)
            extracted.append(dest)
    return extracted


def get_resource_dir() -> str:
    """Get the directory containing bundled resources.
    Supports PyInstaller (_MEIPASS) and Nuitka (exe directory)."""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS  # PyInstaller
        return os.path.dirname(sys.executable)  # Nuitka standalone
    # Running from source — resources are in the exe directory
    try:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ensure_originals(game_dir: str, config: dict) -> list[str]:
    """Copy original game files to originals/ backup for bootstrap.
    Sources, in order: unpacked game www/, sibling 解包/ dir, project root www/,
    then the packed Game.exe's own VFS (EnigmaVB, raw files only).
    Returns list of copied paths."""
    _dlog(f"_ensure_originals: game_dir={game_dir} redirects={config.get('redirects', [])}")
    copied = []
    redirects = config.get("redirects", [])
    if not redirects:
        _dlog("_ensure_originals: no redirects, returning empty")
        return copied

    originals_dir = os.path.join(game_dir, "elsmod_data", "originals", "www", "js", "plugins")

    # Collect all needed filenames first (a single VFS pass covers them all)
    needed = []
    for rule in redirects:
        target_name = rule.get("target", "")
        filename = target_name.replace("\\", "/").split("/")[-1]
        if filename:
            needed.append(filename)

    missing = []
    for filename in needed:
        dest = os.path.join(originals_dir, filename)
        if os.path.isfile(dest):
            continue  # Already copied
        missing.append(filename)

    # Try to find originals on disk:
    # 1. From unpacked game www/ in the same directory
    # 2. From a sibling 解包/ directory
    # 3. From project root www/ (for development)
    still_missing = []
    for filename in missing:
        sources = [
            os.path.join(game_dir, "www", "js", "plugins", filename),
            os.path.join(os.path.dirname(game_dir), "解包", "www", "js", "plugins", filename),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "www", "js", "plugins", filename),  # project root www/
        ]
        done = False
        for src in sources:
            if os.path.isfile(src):
                os.makedirs(originals_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(originals_dir, filename))
                copied.append(os.path.join(originals_dir, filename))
                done = True
                break
        if not done:
            still_missing.append(filename)

    # 4. Extract from the packed game exe's own VFS (EnigmaVB).
    #    Covers fresh packed installs where no unpacked copy exists on disk —
    #    the original is read straight out of Game.exe, never pre-prepared.
    if still_missing:
        exe_path = os.path.join(game_dir, "Game.exe")
        if os.path.isfile(exe_path):
            try:
                from . import evb_vfs
                _dlog(f"_ensure_originals: extracting {still_missing} from packed exe VFS")
                results = evb_vfs.extract_files(exe_path, set(still_missing), originals_dir)
                for filename, ok in results.items():
                    if ok:
                        copied.append(os.path.join(originals_dir, filename))
                    else:
                        _dlog(f"_ensure_originals: VFS extract FAILED for {filename} "
                              f"(missing in VFS or compressed — bootstrap try/catch will skip the original)")
            except Exception as e:
                _dlog(f"_ensure_originals: VFS extraction error: {type(e).__name__}: {e}")

    return copied


def _generate_bootstraps(game_dir: str, config: dict, plugin_files: dict[str, str]) -> list[str]:
    """Generate bootstrap JS files from redirect config.
    plugin_files: {plugin_name: relative_path_to_js_file, ...}
    Returns list of bootstrap paths created."""
    created = []
    redirects = config.get("redirects", [])
    plugins = config.get("plugins", [])
    _dlog(f"_generate_bootstraps: redirects={redirects} plugins={plugins} plugin_files={list(plugin_files.keys())}")
    if not redirects:
        _dlog("_generate_bootstraps: no redirects, returning empty")
        return created

    for rule in redirects:
        target_name = rule.get("target", "")
        source_name = rule.get("source", "")
        if not target_name or not source_name:
            continue

        # Extract original filename (e.g., "EventInformation.js")
        original = target_name.replace("\\", "/").split("/")[-1]

        # Build plugin loaders
        loaders = ""
        for pname in plugins:
            path = plugin_files.get(pname, f"www/js/plugins/{pname}.js")
            loaders += PLUGIN_LOADER.format(path=path)

        bootstrap_js = BOOTSTRAP_TEMPLATE.format(original=original, loaders=loaders)

        dest = os.path.join(game_dir, "www/js/plugins", source_name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(bootstrap_js)
        created.append(dest)

    return created


def setup(game_dir: str) -> dict:
    """Full environment setup. Returns summary dict."""
    _dlog(f"setup: game_dir={game_dir}")
    result = {
        "is_game_dir": False,
        "dirs_created": [],
        "files_extracted": [],
        "orphans_recovered": 0,
        "broken_plugins": [],
        "errors": [],
    }

    if not is_game_directory(game_dir):
        _dlog(f"setup: NOT a game directory (no Game.exe or unpacked layout) — aborting")
        result["errors"].append("当前目录不包含 Game.exe")
        return result

    result["is_game_dir"] = True
    mode = game_mode(game_dir)
    _dlog(f"setup: mode={mode}")

    # Create directories
    result["dirs_created"] = ensure_directories(game_dir)

    # Extract version.dll from embedded base64 (packed mode only)
    if mode == "packed":
        _dlog("setup: packed mode — extracting version.dll")
        if _extract_dll(game_dir):
            _dlog("setup: version.dll extracted OK")
            result["files_extracted"].append(os.path.join(game_dir, "version.dll"))
        else:
            _dlog("setup: version.dll extraction FAILED")
            result["errors"].append("无法解出版本 DLL")

        # Generate bootstrap files for bootstrap mode
        _dlog("setup: generating bootstraps...")
        try:
            cfg = injector_config.load(game_dir)
            _dlog(f"setup: config loaded — injection_mode={cfg.get('injection_mode')} redirects={cfg.get('redirects')}")
            if cfg.get("injection_mode") == "bootstrap" and cfg.get("redirects"):
                # Collect plugin file paths from registry
                plugin_files = {}
                try:
                    reg = registry.load(game_dir)
                    for rec in reg.get("records", []):
                        if rec.get("enabled", False):
                            name = rec["name"]
                            plugin_files[name] = f"www/js/plugins/{name}.js"
                except Exception as e:
                    _dlog(f"setup: registry read for bootstraps failed: {e}")
                    pass
                _dlog(f"setup: calling _generate_bootstraps with plugin_files={list(plugin_files.keys())}")
                bootstraps = _generate_bootstraps(game_dir, cfg, plugin_files)
                _dlog(f"setup: bootstraps generated: {len(bootstraps)} files: {[os.path.basename(b) for b in bootstraps]}")
                result["files_extracted"].extend(bootstraps)
            else:
                _dlog(f"setup: skipping bootstrap generation (mode={cfg.get('injection_mode')} redirects={cfg.get('redirects')})")
        except Exception as e:
            _dlog(f"setup: bootstrap generation ERROR: {type(e).__name__}: {e}")
            result["errors"].append(f"Bootstrap 生成失败：{e}")

    # Extract embedded files
    try:
        resource_dir = get_resource_dir()
        _dlog(f"setup: extracting embedded files from resource_dir={resource_dir}")
        result["files_extracted"] = extract_embedded_files(game_dir, resource_dir)
    except Exception as e:
        _dlog(f"setup: embedded extraction failed: {e}")
        result["errors"].append(f"解出嵌入文件失败：{e}")

    # Recover orphans, check integrity
    try:
        from . import installer
        result["orphans_recovered"] = installer.recover_orphans(game_dir)
        result["broken_plugins"] = installer.check_integrity(game_dir)
    except Exception as e:
        _dlog(f"setup: orphan/integrity scan failed: {e}")
        result["errors"].append(f"注册表扫描失败：{e}")

    _dlog(f"setup: DONE — errors={result['errors']} files={len(result['files_extracted'])} bootstraps={len([f for f in result['files_extracted'] if '_bootstrap' in f])}")
    return result
