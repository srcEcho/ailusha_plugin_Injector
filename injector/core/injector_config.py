"""Injector configuration — 5 dimensions of injection strategy."""
import os, json

CONFIG_DIR = "elsmod_data"
CONFIG_FILENAME = "injector_config.json"

DEFAULTS = {
    "entry_point": "winhttp_dll",
    "hook_library": "minhook",
    "injection_entry": "readfile",
    "file_passthrough": "createfile_redirect",
    "injection_mode": "bootstrap",
    "plugins": [],
    "redirects": [],
}

OPTIONS = {
    "entry_point": [
        {"value": "winhttp_dll", "label_zh": "winhttp.dll 侧载", "label_en": "winhttp.dll side-load", "label_ja": "winhttp.dll サイドロード"},
    ],
    "hook_library": [
        {"value": "minhook", "label_zh": "MinHook", "label_en": "MinHook", "label_ja": "MinHook"},
        {"value": "p5u5", "label_zh": "P5/U5", "label_en": "P5/U5", "label_ja": "P5/U5"},
    ],
    "injection_entry": [
        {"value": "readfile", "label_zh": "ReadFile", "label_en": "ReadFile", "label_ja": "ReadFile"},
    ],
    "file_passthrough": [
        {"value": "vfs_fallback", "label_zh": "VFS Fallback 穿透", "label_en": "VFS Fallback", "label_ja": "VFS Fallback 透過"},
        {"value": "createfile_redirect", "label_zh": "CreateFileW 路径重定向", "label_en": "CreateFileW Redirect", "label_ja": "CreateFileW リダイレクト"},
    ],
    "injection_mode": [
        {"value": "bootstrap", "label_zh": "Bootstrap 替换", "label_en": "Bootstrap", "label_ja": "Bootstrap 置換"},
        {"value": "mainjs_push", "label_zh": "main.js 插入", "label_en": "main.js push", "label_ja": "main.js 挿入"},
    ],
}


def load(game_dir: str) -> dict:
    """Load injector config, merging with defaults."""
    path = os.path.join(game_dir, CONFIG_DIR, CONFIG_FILENAME)
    if not os.path.isfile(path):
        return dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    # Migrate legacy entry_point value (version.dll → winhttp.dll side-load)
    if merged.get("entry_point") == "version_dll":
        merged["entry_point"] = "winhttp_dll"
    return merged


def save(game_dir: str, config: dict) -> str:
    """Save injector config. Returns the config file path."""
    config_dir = os.path.join(game_dir, CONFIG_DIR)
    os.makedirs(config_dir, exist_ok=True)
    path = os.path.join(config_dir, CONFIG_FILENAME)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in config.items() if k in DEFAULTS})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return path
