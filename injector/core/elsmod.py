""".elsmod file operations — pack, unpack, validate"""
import json
import os
import shutil
import tempfile
import zipfile
from typing import Optional

REQUIRED_FIELDS = ["name", "version", "author", "description", "gameVersion"]
EXPECTED_ROOT = "www"

def _find_plugin_json(extract_dir: str) -> Optional[str]:
    """Find plugin.json inside extracted elsmod. Returns path relative to extract_dir."""
    for root, dirs, files in os.walk(extract_dir):
        if "plugin.json" in files:
            return os.path.relpath(os.path.join(root, "plugin.json"), extract_dir)
    return None

def _validate_structure(extract_dir: str) -> list[str]:
    """Validate elsmod internal structure. Returns list of error messages."""
    errors = []

    # Must have www/ at root
    www_dir = os.path.join(extract_dir, EXPECTED_ROOT)
    if not os.path.isdir(www_dir):
        errors.append(f"缺少 '{EXPECTED_ROOT}/' 根目录")
        return errors

    # Must have www/js/plugins/
    plugins_dir = os.path.join(www_dir, "js", "plugins")
    if not os.path.isdir(plugins_dir):
        errors.append(f"缺少 '{EXPECTED_ROOT}/js/plugins/' 目录")
        return errors

    # Must have plugin.json inside data/<Name>_<Author>/
    json_path = _find_plugin_json(extract_dir)
    if not json_path:
        errors.append("缺少 plugin.json（必须在 data/<插件名称>_<作者>/ 下）")
        return errors

    # plugin.json must be under data/<Name>_<Author>/
    parts = json_path.replace("\\", "/").split("/")
    # Expected: .../data/<Name>_<Author>/plugin.json
    # parts[-2] is the <Name>_<Author> dir, parts[-3] must be "data"
    if len(parts) < 3 or parts[-3] != "data":
        errors.append(f"plugin.json 必须在 data/<插件名称>_<作者>/ 下，当前路径：{json_path}")

    # At least one .js file in plugins/
    js_files = [f for f in os.listdir(plugins_dir) if f.endswith(".js")]
    if not js_files:
        errors.append(f"'{EXPECTED_ROOT}/js/plugins/' 下缺少 .js 插件文件")

    return errors

def read_metadata(elsmod_path: str) -> dict:
    """Read plugin.json from an elsmod file. Raises on invalid."""
    with zipfile.ZipFile(elsmod_path, "r") as zf:
        json_path = None
        for name in zf.namelist():
            if name.endswith("plugin.json") and "/data/" in name:
                json_path = name
                break
        if not json_path:
            raise ValueError("elsmod 内缺少 plugin.json")
        data = json.loads(zf.read(json_path).decode("utf-8"))

    missing = [f for f in REQUIRED_FIELDS if f not in data or not data[f]]
    if missing:
        raise ValueError(f"plugin.json 缺少必填字段：{', '.join(missing)}")

    return data

def unpack(elsmod_path: str, output_dir: str) -> None:
    """Unpack elsmod to output_dir. Raises on error."""
    if not zipfile.is_zipfile(elsmod_path):
        raise ValueError("不是有效的 elsmod 文件（zip）")

    # Validate structure
    with zipfile.ZipFile(elsmod_path, "r") as zf:
        # Validate internally
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            errors = _validate_structure(tmp)
            if errors:
                raise ValueError("elsmod 格式错误：\n" + "\n".join(f"  - {e}" for e in errors))
            # Read metadata — normalize path to zip-internal forward slashes
            json_path = _find_plugin_json(tmp).replace("\\", "/")
            metadata = json.loads(zf.read(json_path).decode("utf-8"))

        # Extract to output
        os.makedirs(output_dir, exist_ok=True)
        zf.extractall(output_dir)

def pack(source_dir: str, output_path: str) -> None:
    """Pack source_dir into an elsmod file. Raises on error."""
    errors = _validate_structure(source_dir)
    if errors:
        raise ValueError("项目格式错误：\n" + "\n".join(f"  - {e}" for e in errors))

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        www_dir = os.path.join(source_dir, EXPECTED_ROOT)
        for root, dirs, files in os.walk(www_dir):
            for fn in files:
                full = os.path.join(root, fn)
                arcname = os.path.relpath(full, source_dir).replace("\\", "/")
                zf.write(full, arcname)

def list_files(elsmod_path: str, relative_root: str = "www/js/plugins/") -> list[str]:
    """List files inside elsmod relative to www/js/plugins/."""
    files = []
    with zipfile.ZipFile(elsmod_path, "r") as zf:
        for name in zf.namelist():
            if name.startswith(relative_root) and not name.endswith("/"):
                rel = name[len(relative_root):]
                files.append(rel)
    return files

def read_file(elsmod_path: str, internal_path: str) -> bytes:
    """Read a single file from inside an elsmod."""
    with zipfile.ZipFile(elsmod_path, "r") as zf:
        return zf.read(internal_path)
