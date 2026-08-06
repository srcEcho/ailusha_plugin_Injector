"""Plugin installation/uninstallation logic"""
import os
import shutil
from typing import Optional

from . import registry
from . import elsmod
from . import dependency

PLUGINS_DIR = "www/js/plugins"
ELSMOD_DATA = "elsmod_data"
TMP_DIR = "elsmod_data/tmp"


def _game_path(game_dir: str, rel: str) -> str:
    return os.path.join(game_dir, rel)


def install(game_dir: str, elsmod_path: str) -> dict:
    """
    Install a plugin from an .elsmod file.
    Returns the created registry record.
    Raises ValueError on validation failure, FileExistsError on duplicate.
    """
    # Phase 1: read metadata
    try:
        meta = elsmod.read_metadata(elsmod_path)
    except Exception:
        raise

    name = meta["name"]
    author = meta["author"]
    version = meta["version"]
    source_name = f"{name}-{version}.elsmod"
    source_path = _game_path(game_dir, f"{ELSMOD_DATA}/{source_name}")

    # Phase 2: check duplicates
    if os.path.exists(source_path):
        raise FileExistsError(f"插件 {name} v{version} 已存在")

    # Check name conflict (different author)
    other_author_count = registry.count_same_name_different_author(
        registry.load(game_dir), name)
    if other_author_count > 0:
        reg = registry.load(game_dir)
        existing_authors = set()
        for r in reg["records"]:
            if r["name"] == name:
                existing_authors.add(r.get("author", ""))
        if author not in existing_authors:
            raise ValueError(
                f"名称冲突：插件 '{name}' 已由其他作者注册({', '.join(existing_authors)})。"
                f"建议联系插件作者在名称中标注作者后缀。")

    # Phase 3: transactional extraction
    tmp_dir = _game_path(game_dir, TMP_DIR)
    plugins_dir = _game_path(game_dir, PLUGINS_DIR)
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(plugins_dir, exist_ok=True)

    try:
        # Extract to temp
        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)
        elsmod.unpack(elsmod_path, tmp_dir)

        # Validate structure
        from .elsmod import _validate_structure
        errors = _validate_structure(tmp_dir)
        if errors:
            raise ValueError("elsmod 格式错误：\n" + "\n".join(f"  - {e}" for e in errors))

        # Check file conflicts for reinstall/upgrade
        reg = registry.load(game_dir)
        existing = registry.find_record(reg, name, author)
        existing_files = set(existing["files"]) if existing else set()

        www_tmp = os.path.join(tmp_dir, "www", "js", "plugins")
        new_files = []
        for root, dirs, files in os.walk(www_tmp):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, www_tmp)
                new_files.append(rel)

                target = os.path.join(plugins_dir, rel)
                if os.path.exists(target) and rel not in existing_files:
                    # Cleanup before raising
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    raise ValueError(
                        f"文件冲突：'{rel}' 已存在且不是插件原始文件。\n"
                        f"请联系插件作者解决。")

        # If existing plugin, delete old files
        if existing:
            for old_file in existing["files"]:
                old_path = os.path.join(plugins_dir, old_file)
                if os.path.isfile(old_path):
                    os.remove(old_path)

        # Move from temp to final
        for root, dirs, files in os.walk(www_tmp):
            for fn in files:
                src = os.path.join(root, fn)
                rel = os.path.relpath(src, www_tmp)
                dst = os.path.join(plugins_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Phase 4: copy elsmod to data dir
    elsmod_data_dir = _game_path(game_dir, ELSMOD_DATA)
    os.makedirs(elsmod_data_dir, exist_ok=True)
    shutil.copy2(elsmod_path, source_path)

    # Phase 5: update registry
    reg = registry.load(game_dir)
    if existing:
        registry.update_source(reg, name, source_name, version, new_files,
                               author=author)
    else:
        registry.add_record(reg, name, author, version, source_name, new_files,
                            enabled=True)

    # Phase 6: topological sort
    try:
        reg["loadOrder"] = dependency.resolve(reg)
    except ValueError:
        pass  # keep existing loadOrder if cycle

    registry.save(game_dir, reg)

    return registry.find_record(reg, name, author)


def uninstall(game_dir: str, name: str, author: Optional[str] = None) -> Optional[dict]:
    """
    Uninstall a plugin. Only deletes files listed in registry record.
    Returns the removed record or None.
    """
    reg = registry.load(game_dir)
    rec = registry.find_record(reg, name, author)
    if not rec:
        return None

    # Delete only files in the record
    plugins_dir = _game_path(game_dir, PLUGINS_DIR)
    for f in rec.get("files", []):
        fp = os.path.join(plugins_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)

    # Remove source elsmod
    source = rec.get("source", "")
    source_path = _game_path(game_dir, source)
    if os.path.isfile(source_path):
        os.remove(source_path)

    # Update registry
    registry.remove_record(reg, name, author)
    try:
        reg["loadOrder"] = dependency.resolve(reg)
    except ValueError:
        if name in reg.get("loadOrder", []):
            reg["loadOrder"].remove(name)
    registry.save(game_dir, reg)

    return rec


def repair(game_dir: str, name: str, author: Optional[str] = None) -> dict:
    """Repair a broken plugin by re-extracting from elsmod_data."""
    reg = registry.load(game_dir)
    rec = registry.find_record(reg, name, author)
    if not rec:
        raise ValueError(f"插件 '{name}' 未找到")

    source = rec.get("source", "")
    source_path = _game_path(game_dir, source)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"源文件 {source} 不存在，无法修复")

    plugins_dir = _game_path(game_dir, PLUGINS_DIR)

    # Extract directly from elsmod
    with __import__("zipfile").ZipFile(source_path, "r") as zf:
        www_prefix = "www/js/plugins/"
        for f in zf.namelist():
            if f.startswith(www_prefix) and not f.endswith("/"):
                rel = f[len(www_prefix):]
                dst = os.path.join(plugins_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with zf.open(f) as src:
                    with open(dst, "wb") as out:
                        out.write(src.read())

    return rec


def check_integrity(game_dir: str) -> list[dict]:
    """Check integrity of all installed plugins. Returns list of broken records."""
    reg = registry.load(game_dir)
    plugins_dir = _game_path(game_dir, PLUGINS_DIR)
    broken = []
    for rec in reg["records"]:
        for f in rec.get("files", []):
            if not os.path.isfile(os.path.join(plugins_dir, f)):
                broken.append(rec)
                break
    return broken


def recover_orphans(game_dir: str) -> int:
    """Scan elsmod_data/ for elsmod files not in registry. Add them. Returns count added."""
    reg = registry.load(game_dir)
    elsmod_dir = _game_path(game_dir, ELSMOD_DATA)
    if not os.path.isdir(elsmod_dir):
        return 0

    count = 0
    for fn in os.listdir(elsmod_dir):
        if not fn.endswith(".elsmod"):
            continue
        fp = os.path.join(elsmod_dir, fn)
        if not __import__("zipfile").is_zipfile(fp):
            continue
        try:
            meta = elsmod.read_metadata(fp)
        except Exception:
            continue
        name = meta["name"]
        author = meta["author"]
        version = meta["version"]

        existing = registry.find_record(reg, name, author)
        if existing:
            continue  # already registered

        files = elsmod.list_files(fp)
        registry.add_record(reg, name, author, version, fn, files, enabled=True)
        count += 1

    if count > 0:
        try:
            reg["loadOrder"] = dependency.resolve(reg)
        except ValueError:
            pass
        registry.save(game_dir, reg)

    return count
