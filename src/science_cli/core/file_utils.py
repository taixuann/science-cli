"""File operations: symlink management, path resolution, flag parsing helpers."""

from pathlib import Path


def is_flag(s: str) -> bool:
    """True if s looks like a flag (--name or -x), not a negative value."""
    if not s.startswith("-"):
        return False
    if s.startswith("--"):
        return True
    if len(s) > 1 and s[1].isdigit():
        return False
    return True


def resolve_data_file(name: str, project_path: Path | None = None) -> str:
    path = Path(name)
    if path.exists():
        return str(path.resolve())
    if project_path:
        raw_dir = project_path / "data" / "raw"
        full = raw_dir / name
        if full.exists():
            return str(full.resolve())
        for f in raw_dir.iterdir():
            if name.lower() in f.name.lower():
                return str(f.resolve())
    return ""


def get_results_dir(filepath: str, project_path: Path | None = None, protocol: str = "") -> Path:
    fp = Path(filepath)
    if protocol and project_path:
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(project_path)
        yaml_path = paths.protocol_yaml(protocol)
        if yaml_path.exists():
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            fname = fp.name
            for s in data.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    results_dir = paths.step_results_dir(protocol, s["name"])
                    results_dir.mkdir(parents=True, exist_ok=True)
                    return results_dir
    if project_path:
        out = project_path / "results"
    else:
        out = fp.parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def create_symlink(target: Path, link_path: Path):
    if link_path.exists():
        link_path.unlink()
    link_path.symlink_to(target)
