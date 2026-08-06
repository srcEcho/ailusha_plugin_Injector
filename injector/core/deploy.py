"""Environment deployment — directory creation, file extraction"""
import os
import shutil
import sys

REQUIRED_DIRS = [
    "www/js/plugins",
    "www/js/plugins/data",
    "elsmod_data",
    "elsmod_data/tmp",
]

EMBEDDED_FILES = [
    "version.dll",
    "UninstallElusha.exe",
]


def is_game_directory(path: str) -> bool:
    """Check if path contains Game.exe."""
    return os.path.isfile(os.path.join(path, "Game.exe"))


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
    """Extract embedded files (version.dll, UninstallElusha.exe) from resource dir.
    resource_dir is where PyInstaller stores bundled files (sys._MEIPASS or __file__ dir)."""
    extracted = []
    for fn in EMBEDDED_FILES:
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
    Works both in PyInstaller bundle and from source."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        # Running from source — resources are in the project root
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup(game_dir: str) -> dict:
    """Full environment setup. Returns summary dict."""
    result = {
        "is_game_dir": False,
        "dirs_created": [],
        "files_extracted": [],
        "orphans_recovered": 0,
        "broken_plugins": [],
        "errors": [],
    }

    if not is_game_directory(game_dir):
        result["errors"].append("当前目录不包含 Game.exe")
        return result

    result["is_game_dir"] = True

    # Create directories
    result["dirs_created"] = ensure_directories(game_dir)

    # Extract embedded files
    try:
        resource_dir = get_resource_dir()
        result["files_extracted"] = extract_embedded_files(game_dir, resource_dir)
    except Exception as e:
        result["errors"].append(f"解出嵌入文件失败：{e}")

    # Recover orphans, check integrity
    try:
        from . import installer
        result["orphans_recovered"] = installer.recover_orphans(game_dir)
        result["broken_plugins"] = installer.check_integrity(game_dir)
    except Exception as e:
        result["errors"].append(f"注册表扫描失败：{e}")

    return result
