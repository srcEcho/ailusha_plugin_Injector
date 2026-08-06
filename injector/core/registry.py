"""Registry management — elsmod_data/registry.json"""
import json
import os
from datetime import datetime
from typing import Optional

REGISTRY_FILENAME = "registry.json"

def _default_registry() -> dict:
    return {"version": 1, "loadOrder": [], "records": []}

def load(game_dir: str) -> dict:
    """Load registry.json from game_dir/elsmod_data/. Returns default if missing."""
    path = os.path.join(game_dir, "elsmod_data", REGISTRY_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = _default_registry()
    # ensure keys exist
    if "loadOrder" not in data:
        data["loadOrder"] = []
    if "records" not in data:
        data["records"] = []
    return data

def save(game_dir: str, registry: dict) -> None:
    """Save registry.json."""
    path = os.path.join(game_dir, "elsmod_data", REGISTRY_FILENAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

def find_record(registry: dict, name: str, author: Optional[str] = None) -> Optional[dict]:
    """Find a record by name, optionally filtered by author."""
    for rec in registry["records"]:
        if rec["name"] != name:
            continue
        if author and rec.get("author") != author:
            continue
        return rec
    return None

def add_record(registry: dict, name: str, author: str, version: str,
               source: str, files: list[str], enabled: bool = True) -> dict:
    """Add a new record. Returns the created record."""
    rec = {
        "name": name,
        "author": author,
        "version": version,
        "enabled": enabled,
        "source": source,
        "installedAt": datetime.now().isoformat(),
        "files": files,
    }
    registry["records"].append(rec)
    if name not in registry["loadOrder"]:
        registry["loadOrder"].append(name)
    return rec

def remove_record(registry: dict, name: str, author: Optional[str] = None) -> Optional[dict]:
    """Remove a record. Returns removed record or None."""
    rec = find_record(registry, name, author)
    if rec:
        registry["records"].remove(rec)
        if name in registry["loadOrder"]:
            registry["loadOrder"].remove(name)
    return rec

def set_enabled(registry: dict, name: str, enabled: bool,
                author: Optional[str] = None) -> bool:
    """Set enabled state. Returns True if record found."""
    rec = find_record(registry, name, author)
    if rec:
        rec["enabled"] = enabled
        return True
    return False

def update_source(registry: dict, name: str, new_source: str, new_version: str,
                  new_files: list[str], author: Optional[str] = None) -> Optional[dict]:
    """Update record after upgrade. Returns record or None."""
    rec = find_record(registry, name, author)
    if rec:
        rec["source"] = new_source
        rec["version"] = new_version
        rec["files"] = new_files
        rec["installedAt"] = datetime.now().isoformat()
    return rec

def find_versions(registry: dict, name: str, author: str) -> list[dict]:
    """Find all version records for a plugin by same author."""
    return [r for r in registry["records"]
            if r["name"] == name and r.get("author") == author]

def count_same_name_different_author(registry: dict, name: str) -> int:
    """Count how many different authors have a plugin with this name."""
    authors = set()
    for r in registry["records"]:
        if r["name"] == name:
            authors.add(r.get("author", ""))
    return len(authors)
