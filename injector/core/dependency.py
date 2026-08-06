"""Plugin dependency resolution — topological sort + cycle detection"""
from collections import deque
from typing import Optional


def _version_satisfies(actual: str, constraint: str) -> bool:
    """Check if actual version satisfies constraint like '>=0.6.0'.
    Simplified: only supports '>=' prefix. No constraint = always satisfied."""
    if not constraint:
        return True
    if constraint.startswith(">="):
        return actual >= constraint[2:]
    if constraint.startswith("=") or constraint[0].isdigit():
        target = constraint.lstrip("=")
        return actual == target
    if constraint.startswith("<="):
        return actual <= constraint[2:]
    return actual == constraint  # default: exact match


def resolve(registry: dict) -> list[str]:
    """
    Topological sort of enabled plugins by dependency graph.
    Returns ordered list of plugin names.
    Uses Kahn's algorithm. Detects cycles.
    """
    records = {r["name"]: r for r in registry["records"] if r.get("enabled", False)}
    if not records:
        # fallback: existing loadOrder filtered to enabled
        return [n for n in registry.get("loadOrder", []) if n in records]

    # Build graph
    in_degree: dict[str, int] = {n: 0 for n in records}
    adj: dict[str, list[str]] = {n: [] for n in records}

    for name, rec in records.items():
        for dep in rec.get("dependencies", []):
            dep_name = dep.get("name", "")
            dep_author = dep.get("author")
            dep_version = dep.get("version", "")

            # Find matching dependency in enabled records
            matched = None
            for other_name, other_rec in records.items():
                if other_name != dep_name:
                    continue
                if dep_author and other_rec.get("author") != dep_author:
                    continue
                if dep_version and not _version_satisfies(other_rec.get("version", "0"), dep_version):
                    continue
                matched = other_name
                break

            if matched and matched != name:
                adj[matched].append(name)
                in_degree[name] += 1

    # Kahn topological sort
    queue = deque([n for n, d in in_degree.items() if d == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(records):
        # Cycle detected — find cycle nodes
        remaining = set(records.keys()) - set(result)
        raise ValueError(f"检测到循环依赖，涉及插件：{', '.join(sorted(remaining))}")

    # Append any remaining enabled plugins without dependencies (shouldn't happen but safe)
    for name in records:
        if name not in result:
            result.append(name)

    return result


def check_dependencies_satisfied(registry: dict, name: str,
                                  author: Optional[str] = None) -> list[str]:
    """Check if a plugin's dependencies are all installed (enabled or not).
    Returns list of missing dependency names."""
    rec = None
    for r in registry["records"]:
        if r["name"] == name:
            if author is None or r.get("author") == author:
                rec = r
                break
    if not rec:
        return []

    missing = []
    for dep in rec.get("dependencies", []):
        dep_name = dep.get("name", "")
        dep_author = dep.get("author")
        found = False
        for other in registry["records"]:
            if other["name"] != dep_name:
                continue
            if dep_author and other.get("author") != dep_author:
                continue
            found = True
            break
        if not found:
            missing.append(dep_name)
    return missing


def find_dependents(registry: dict, name: str) -> list[str]:
    """Find all enabled plugins that depend on the named plugin."""
    dependents = []
    for rec in registry["records"]:
        if not rec.get("enabled", False):
            continue
        for dep in rec.get("dependencies", []):
            if dep.get("name") == name:
                dependents.append(rec["name"])
                break
    return dependents
