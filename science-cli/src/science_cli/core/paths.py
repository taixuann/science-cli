"""Central file path config for science-cli projects.

All directory structure logic lives here. To change the project layout,
modify this single file instead of hunting across the codebase.
"""

from pathlib import Path
from typing import Optional


def sanitize_name(name: str, extra_chars: str = "") -> str:
    """Sanitize a name for use as a directory/filename.

    Keeps alphanumeric, ``-``, ``_``, and any extra_chars.
    Other characters are replaced with ``_``.
    """
    base = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    allowed = set(base + extra_chars)
    return "".join(c if c in allowed else "_" for c in name)


def sanitize_protocol_name(name: str) -> str:
    """Sanitize a protocol name — allows alphanumeric, ``-``, ``_``, ``.``, ``(``, ``)``."""
    return sanitize_name(name, "._()")


def sanitize_project_name(name: str) -> str:
    """Sanitize a project name — alphanumeric, ``-``, ``_``, ``.`` only."""
    return sanitize_name(name, ".")


def sanitize_name_legacy(name: str) -> str:
    """Old sanitization (no dot/paren support) — used for backward-compat lookups."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def resolve_protocol_yaml(protocol_dir: Path, name: str) -> Path | None:
    """Find a protocol YAML by name, trying exact and legacy sanitized forms."""
    candidates = [
        protocol_dir / name / f"{name}.yaml",           # exact, new format
        protocol_dir / f"{name}.yaml",                   # exact, old flat format
    ]
    legacy = sanitize_name_legacy(name)
    if legacy != name:
        candidates += [
            protocol_dir / legacy / f"{legacy}.yaml",    # legacy, new format
            protocol_dir / f"{legacy}.yaml",              # legacy, old flat format
        ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # return the first candidate even if it doesn't exist


class ProjectPaths:
    """Path resolution for a science-cli project.

    Directory structure:
        <project_root>/
            protocol/
                <protocol_name>/          ← new: protocol subdirectory
                    <protocol_name>.yaml  ← new: protocol descriptor inside folder
                    devices.yaml          ← memristor crossbar mapping
                    <step_name>/
                        results/
                            ...
            data/
                raw/
                    ...
            results/
                ...

    LEGACY format (still supported for reads):
        <project_root>/
            protocol/
                <protocol_name>.yaml      ← old: flat protocol descriptor
                <protocol_name>/          ← protocol subdirectory exists
                    ...
    """

    def __init__(self, project_root: Path):
        self.root = project_root.resolve()

    # ── Protocol descriptors ────────────────────────────────

    @property
    def protocol_dir(self) -> Path:
        return self.root / "protocol"

    def protocol_yaml(self, name: str) -> Path:
        """Protocol descriptor YAML path.

        Resolves name (supports ``.`` and ``()`` in names) with
        backward-compatible fallback to old sanitization.
        """
        result = resolve_protocol_yaml(self.protocol_dir, name)
        return result

    def protocol_yaml_new(self, name: str) -> Path:
        """New protocol YAML location (inside protocol folder).

        Use this for CREATE operations. Existing protocols at the
        old flat location are NOT moved — this is opt-in for new ones.
        """
        return self.protocol_dir / name / f"{name}.yaml"

    def list_protocol_yamls(self) -> list[Path]:
        """Find all protocol YAMLs in both new and legacy locations."""
        found: dict[str, Path] = {}
        if self.protocol_dir.exists():
            # New format: protocol/<name>/<name>.yaml
            for sub in sorted(self.protocol_dir.iterdir()):
                if sub.is_dir():
                    yaml_candidate = sub / f"{sub.name}.yaml"
                    if yaml_candidate.exists():
                        found[sub.name] = yaml_candidate
            # Legacy format: protocol/<name>.yaml (only if no new-format entry)
            for y in sorted(self.protocol_dir.glob("*.yaml")):
                if y.stem not in found:
                    found[y.stem] = y
        return sorted(found.values(), key=lambda p: p.stem)

    def protocol_names(self) -> list[str]:
        return sorted(p.stem for p in self.list_protocol_yamls())

    def protocol_subdir(self, name: str) -> Path:
        """Protocol subdirectory holding step dirs and devices.yaml."""
        return self.protocol_dir / name

    # ── Device / step paths ─────────────────────────────────

    def devices_yaml(self, protocol: str) -> Path:
        return self.protocol_dir / protocol / "devices.yaml"

    def step_dir(self, protocol: str, step: str) -> Path:
        return self.protocol_dir / protocol / step

    def step_results_dir(self, protocol: str, step: str) -> Path:
        return self.step_dir(protocol, step) / "results"

    # ── Data / results ──────────────────────────────────────

    def flat_yamls(self) -> list[Path]:
        """Find protocol YAMLs still at the legacy flat location.

        Returns paths like ``protocol/<name>.yaml`` where the
        corresponding ``protocol/<name>/<name>.yaml`` does NOT exist.
        """
        found: list[Path] = []
        for y in sorted(self.protocol_dir.glob("*.yaml")):
            nested = self.protocol_dir / y.stem / f"{y.stem}.yaml"
            if not nested.exists():
                found.append(y)
        return found

    def migrate_protocol_yamls(self) -> dict:
        """Migrate flat protocol YAMLs to nested format.

        Validates YAML syntax before moving. Skips if target exists.
        Returns dict: {migrated: int, skipped: int, errors: list[str]}.
        """
        import shutil
        import yaml

        result: dict = {"migrated": 0, "skipped": 0, "errors": []}
        for yaml_path in self.flat_yamls():
            name = yaml_path.stem
            target = self.protocol_yaml_new(name)

            if target.exists():
                result["skipped"] += 1
                continue

            try:
                with open(yaml_path) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                result["errors"].append(f"{yaml_path.name}: YAML error: {e}")
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(yaml_path), str(target))
                result["migrated"] += 1
            except OSError as e:
                result["errors"].append(f"{yaml_path.name}: move failed: {e}")

        return result

    @property
    def data_raw_dir(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"


def get_techniques_config_dir() -> Path:
    """Return the directory for per-technique YAML config files."""
    return Path.home() / ".config" / "science-cli" / "techniques"


def get_project_paths() -> Optional[ProjectPaths]:
    """Get ProjectPaths for the currently open project."""
    from science_cli.core.project import get_current_project_path

    proj = get_current_project_path()
    return ProjectPaths(proj) if proj else None
