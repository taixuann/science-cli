"""Project path resolution and management."""

from pathlib import Path
from science_cli.core.session import load_session


def _get_projects_root() -> Path:
    """Return the configured projects root directory.

    Checks the config system first; falls back to hardcoded path.
    """
    try:
        from science_cli.core.config import get_projects_root
        return get_projects_root()
    except (ImportError, Exception):
        return Path.home() / "workspace" / "projects" / "active_projects"


def get_current_project_path() -> Path | None:
    session = load_session()
    name = session.get("last_project", "")
    if not name:
        return None
    root = _get_projects_root()
    candidate = root / name
    if candidate.exists():
        return candidate
    return None


def list_projects():
    root = _get_projects_root()
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())


def open_project(name: str) -> Path | None:
    root = _get_projects_root()
    proj = root / name
    if proj.exists():
        return proj
    return None


def project_status() -> dict:
    proj = get_current_project_path()
    if not proj:
        return {"error": "no project open"}
    raw_dir = proj / "data" / "raw"
    proto_dir = proj / "protocol"
    info = {
        "name": proj.name,
        "path": str(proj),
        "raw_files": len(list(raw_dir.iterdir())) if raw_dir.exists() else 0,
        "protocols": _count_protocol_yamls(proto_dir),
    }
    return info


def _count_protocol_yamls(proto_dir) -> int:
    """Count protocol YAMLs in both new and legacy locations, without duplicates.

    Inlined from ProjectPaths.list_protocol_yamls() to avoid circular imports.
    """
    if not proto_dir.exists():
        return 0
    found: set[str] = set()
    # New format: protocol/<name>/<name>.yaml
    for sub in proto_dir.iterdir():
        if sub.is_dir():
            yaml_candidate = sub / f"{sub.name}.yaml"
            if yaml_candidate.exists():
                found.add(sub.name)
    # Legacy format: protocol/<name>.yaml (only if no new-format entry)
    for y in proto_dir.glob("*.yaml"):
        if y.stem not in found:
            found.add(y.stem)
    return len(found)
