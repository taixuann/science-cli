"""Crossbar device data models, YAML I/O, validation, and sync.

Models the hierarchy:
    Device (1) -> MatrixPoint (N) -> TechniqueGroup (0-4) -> FileEntry (1+)

devices.yaml lives at protocol/<proto>/devices.yaml with a steps:
mapping that connects techniques to step subdirectories.
"""

import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from science_cli.core.protocol import (
    has_device_section,
    migrate_from_devices_yaml,
)

# ── Sweep segment metadata ─────────────────────────────────


@dataclass
class SweepSegment:
    direction: str = "forward"
    sweep_rate_v_s: float = 0.0
    voltage_range: float = 0.0
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "sweep_rate_v_s": self.sweep_rate_v_s,
            "voltage_range": self.voltage_range,
            "duration_s": self.duration_s,
        }


# ── Leaf: single data file ─────────────────────────────────


@dataclass
class FileEntry:
    file: str
    sweep_order: Optional[int] = None
    sweep_type: Optional[str] = None
    sweep: list[dict] = field(default_factory=list)
    temperature: Optional[float] = None
    extra: dict = field(default_factory=dict)

    @property
    def is_sweep_detected(self) -> bool:
        return len(self.sweep) > 0

    def to_dict(self) -> dict:
        d: dict = {"file": self.file}
        if self.sweep_order is not None:
            d["sweep_order"] = self.sweep_order
        if self.sweep_type is not None:
            d["sweep_type"] = self.sweep_type
        if self.sweep:
            d["sweep"] = self.sweep
        if self.temperature is not None:
            d["temperature"] = self.temperature
        if self.extra:
            d.update(self.extra)
        return d


# ── Technique group ─────────────────────────────────────────


@dataclass
class TechniqueGroup:
    technique: str
    files: list[FileEntry] = field(default_factory=list)

    @property
    def primary_file(self) -> Optional[FileEntry]:
        return self.files[0] if self.files else None

    @property
    def file_count(self) -> int:
        return len(self.files)

    def sorted_files(self) -> list[FileEntry]:
        return sorted(
            self.files,
            key=lambda f: (f.sweep_order is None, f.sweep_order or 0),
        )


# ── Matrix point ────────────────────────────────────────────


@dataclass
class MatrixPoint:
    row: int
    col: int
    techniques: dict[str, TechniqueGroup] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @property
    def position(self) -> tuple[int, int]:
        return (self.row, self.col)

    def _resolve_tech_key(self, tech: str) -> str:
        """Map standard short tech names to database/protocol technique names."""
        if tech == "iv" and "iv" not in self.techniques and "iv-sweep" in self.techniques:
            return "iv-sweep"
        if tech == "endurance" and "endurance" not in self.techniques and "mem-endurance" in self.techniques:
            return "mem-endurance"
        if tech == "retention" and "retention" not in self.techniques and "mem-retention" in self.techniques:
            return "mem-retention"
        if tech == "iv-sweep" and "iv-sweep" not in self.techniques and "iv" in self.techniques:
            return "iv"
        if tech == "mem-endurance" and "mem-endurance" not in self.techniques and "endurance" in self.techniques:
            return "endurance"
        if tech == "mem-retention" and "mem-retention" not in self.techniques and "retention" in self.techniques:
            return "retention"
        return tech

    def has_technique(self, tech: str) -> bool:
        resolved = self._resolve_tech_key(tech)
        return resolved in self.techniques and len(self.techniques[resolved].files) > 0

    def get_files(self, tech: str) -> list[FileEntry]:
        resolved = self._resolve_tech_key(tech)
        tg = self.techniques.get(resolved)
        return tg.files if tg else []

    def get_primary_file(self, tech: str) -> Optional[FileEntry]:
        resolved = self._resolve_tech_key(tech)
        tg = self.techniques.get(resolved)
        return tg.primary_file if tg else None


    @property
    def technique_names(self) -> list[str]:
        return [t for t, tg in self.techniques.items() if tg.files]

    @property
    def total_files(self) -> int:
        return sum(tg.file_count for tg in self.techniques.values())

    @property
    def is_measured(self) -> bool:
        return self.total_files > 0


# ── Crossbar device ─────────────────────────────────────────


@dataclass
class DeviceGeometry:
    id: str
    label: str
    rows: int
    cols: int
    description: str = ""
    cell_area_um2: Optional[float] = None
    row_labels: list[str] = field(default_factory=list)
    col_labels: list[str] = field(default_factory=list)

    @property
    def total_cells(self) -> int:
        return self.rows * self.cols

    def cell_label(self, row: int, col: int) -> str:
        if (
            self.row_labels
            and self.col_labels
            and row < len(self.row_labels)
            and col < len(self.col_labels)
        ):
            return f"{self.row_labels[row]}/{self.col_labels[col]}"
        return f"r{row}c{col}"


# ── Device configuration (aggregate) ────────────────────────


@dataclass
class DeviceConfig:
    device: DeviceGeometry
    points: list[MatrixPoint]
    steps: dict[str, str] = field(default_factory=dict)
    step_name: str = ""
    protocol_name: str = ""
    _meta: dict = field(default_factory=dict)

    def resolve_file_path(self, protocol_dir: Path, technique: str, filename: str) -> Path:
        """Resolve a data file to its physical path via the steps mapping."""
        tech_resolved = technique
        if technique == "iv" and "iv" not in self.steps and "iv-sweep" in self.steps:
            tech_resolved = "iv-sweep"
        elif technique == "endurance" and "endurance" not in self.steps and "mem-endurance" in self.steps:
            tech_resolved = "mem-endurance"
        elif technique == "retention" and "retention" not in self.steps and "mem-retention" in self.steps:
            tech_resolved = "mem-retention"

        step = self.steps.get(tech_resolved)
        if step:
            return protocol_dir / step / filename
        return protocol_dir / filename


    def get_point(self, row: int, col: int) -> Optional[MatrixPoint]:
        for p in self.points:
            if p.row == row and p.col == col:
                return p
        return None

    def get_row(self, row: int) -> list[MatrixPoint]:
        return sorted([p for p in self.points if p.row == row], key=lambda p: p.col)

    def get_col(self, col: int) -> list[MatrixPoint]:
        return sorted([p for p in self.points if p.col == col], key=lambda p: p.row)

    def get_points_with_technique(self, tech: str) -> list[MatrixPoint]:
        return [p for p in self.points if p.has_technique(tech)]

    def get_all_files(
        self, tech: str
    ) -> list[tuple[MatrixPoint, FileEntry]]:
        results: list[tuple[MatrixPoint, FileEntry]] = []
        for p in self.points:
            for fe in p.get_files(tech):
                results.append((p, fe))
        return results

    @property
    def measured_cells(self) -> int:
        return len(self.points)

    @property
    def missing_cells(self) -> list[tuple[int, int]]:
        measured = {(p.row, p.col) for p in self.points}
        return [
            (r, c)
            for r in range(self.device.rows)
            for c in range(self.device.cols)
            if (r, c) not in measured
        ]

    @property
    def technique_coverage(self) -> dict[str, int]:
        coverage: dict[str, int] = {}
        for p in self.points:
            for tech in p.technique_names:
                coverage[tech] = coverage.get(tech, 0) + 1
        return coverage

    @property
    def total_files(self) -> int:
        return sum(p.total_files for p in self.points)

    @property
    def file_map(self) -> dict[str, tuple[int, int, str]]:
        fm: dict[str, tuple[int, int, str]] = {}
        for p in self.points:
            for tech, tg in p.techniques.items():
                for fe in tg.files:
                    fm[fe.file] = (p.row, p.col, tech)
        return fm

    def get_points_by_material(self) -> dict[str, list[MatrixPoint]]:
        """Group points by material+batch key.

        Primary grouping uses tags prefixed with ``"material:"``.
        Falls back to scanning filenames if a point has no material tags
        (supports legacy data without re-sync).

        A single point may appear in multiple groups if it has files
        from different materials.

        Returns:
            Dict keyed by material key like ``"Ta-PDA-ITO(1)"``,
            values are lists of MatrixPoints.
        """
        groups: dict[str, list[MatrixPoint]] = {}

        for pt in self.points:
            # Prefer tags
            materials_from_tags: list[str] = [
                tag.split(":", 1)[1]
                for tag in pt.tags
                if tag.startswith(MATERIAL_TAG_PREFIX)
            ]

            if materials_from_tags:
                for mat in materials_from_tags:
                    if mat not in groups:
                        groups[mat] = []
                    groups[mat].append(pt)
            else:
                # Fallback: scan filenames for legacy data
                seen: set[str] = set()
                for tg in pt.techniques.values():
                    for fe in tg.files:
                        result = extract_material_batch(fe.file)
                        if result:
                            material, batch = result
                            key = f"{material}({batch})" if batch else material
                            if key not in seen:
                                seen.add(key)
                                if key not in groups:
                                    groups[key] = []
                                groups[key].append(pt)

        return groups


# ── Constants ────────────────────────────────────────────────

KNOWN_TECHNIQUES = {"iv", "endurance", "retention", "switching"}
STANDARD_FILE_KEYS = {"file", "sweep_order", "sweep_type", "sweep", "temperature"}
DATA_SUFFIXES = {".txt", ".csv", ".dat", ".tsv", ".log"}
YAML_EXCLUDE = {"devices.yaml", "devices.yml", "results"}

# ── Material / batch extraction ──────────────────────────────

MATERIAL_TAG_PREFIX = "material:"

_MATERIAL_BATCH_RE = re.compile(
    r'^\d{4,6}_'                      # DDMM or DDMMYY date prefix
    r'([A-Za-z0-9/\-]+?)'            # Material name (lazy, allows /)
    r'(?:\(([A-Za-z0-9]+)\))?'       # Optional batch (alphanumeric)
    r'_(?:iv-sweep|b\d+-t\d+)_'      # technique or b#-t# position markers
)


def extract_material_batch(filename: str, project_root=None) -> tuple[str, str] | None:
    """Extract (material_name, batch_number) from a canonical memristor filename.

    Tries grammar-based parsing first if project_root is provided,
    falls back to hardcoded regex.

    Args:
        filename: e.g. ``"0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv"``
        project_root: Optional project root path for grammar-based config lookup.

    Returns:
        ``("Ta-PDA-ITO", "1")`` or ``None`` if not parseable.
        If no batch number is present, returns ``("MaterialName", "")``.

    Examples:
        >>> extract_material_batch("0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv")
        ('Ta-PDA-ITO', '1')
        >>> extract_material_batch("0605_Ta-PDAc-ITO(2)_b1-t1_IV-DC_f_01.csv")
        ('Ta-PDAc-ITO', '2')
        >>> extract_material_batch("0505_Ta-PDA-ITO_b1-t1_IV-DC_uc_01.csv")
        ('Ta-PDA-ITO', '')
    """
    # Try grammar-based parsing first if project_root is provided
    if project_root is not None:
        try:
            from science_cli.core.technique import parse_filename_grammar
            grammar_result = parse_filename_grammar(filename, project_root)
            if "parse_error" not in grammar_result and "material" in grammar_result:
                material = grammar_result["material"]
                batch = grammar_result.get("batch", "") or ""
                return (material, batch)
        except ImportError:
            pass

    # Fall back to hardcoded regex
    m = _MATERIAL_BATCH_RE.match(filename)
    if not m:
        return None
    material = m.group(1)
    batch = m.group(2) or ""
    return (material, batch)


# ── YAML I/O ────────────────────────────────────────────────


def read_devices(dir_path: Path | str) -> Optional[DeviceConfig]:
    """Load crossbar device configuration from a protocol directory.

    Resolution order:
    1. Try protocol YAML ``device:`` section (new)
    2. Fall back to legacy ``devices.yaml``

    Returns None if neither source has device info.
    """
    path = Path(dir_path)

    # ── Try protocol YAML first ──
    protocol_yaml = path / f"{path.name}.yaml"
    if protocol_yaml.exists() and has_device_section(protocol_yaml):
        config = _read_from_protocol_yaml(path, protocol_yaml)
        if config is not None:
            return config

    # ── Fall back to legacy devices.yaml ──
    devices_yaml = path / "devices.yaml"
    if not devices_yaml.exists():
        return None

    with open(devices_yaml) as f:
        data = yaml.safe_load(f) or {}

    dev_data = data.get("device", {})
    device = DeviceGeometry(
        id=dev_data.get("id", ""),
        label=dev_data.get("label", ""),
        rows=dev_data.get("rows", 1),
        cols=dev_data.get("cols", 1),
        description=dev_data.get("description", ""),
        cell_area_um2=dev_data.get("cell_area_um2"),
        row_labels=dev_data.get("row_labels", []),
        col_labels=dev_data.get("col_labels", []),
    )

    steps: dict[str, str] = data.get("steps", {}) or {}

    points: list[MatrixPoint] = []
    for p_data in data.get("points", []):
        techniques: dict[str, TechniqueGroup] = {}
        for tech_name, file_list in (p_data.get("techniques") or {}).items():
            files = []
            for f_data in file_list:
                extra = {
                    k: v
                    for k, v in f_data.items()
                    if k not in STANDARD_FILE_KEYS
                }
                files.append(
                    FileEntry(
                        file=f_data.get("file", ""),
                        sweep_order=f_data.get("sweep_order"),
                        sweep_type=f_data.get("sweep_type"),
                        sweep=f_data.get("sweep", []),
                        temperature=f_data.get("temperature"),
                        extra=extra,
                    )
                )
            techniques[tech_name] = TechniqueGroup(
                technique=tech_name, files=files
            )
        points.append(
            MatrixPoint(
                row=p_data.get("row", 0),
                col=p_data.get("col", 0),
                techniques=techniques,
                tags=p_data.get("tags", []),
            )
        )

    return DeviceConfig(
        device=device,
        points=points,
        steps=steps,
        _meta=data.get("_meta", {}),
    )


def _read_from_protocol_yaml(
    protocol_dir: Path, yaml_path: Path
) -> Optional[DeviceConfig]:
    """Read DeviceConfig from protocol YAML device section + steps.

    Also attempts to load per-cell MatrixPoints from SQLite if available.

    Args:
        protocol_dir: The protocol subdirectory (e.g., ``protocol/1_pda/``).
        yaml_path: Path to the protocol YAML file.

    Returns:
        DeviceConfig or None if no device section found.
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        return None

    dev_data = data.get("device", {})
    if not dev_data:
        return None

    device = DeviceGeometry(
        id=dev_data.get("id", f"crossbar-{dev_data.get('rows',1)}x{dev_data.get('cols',1)}"),
        label=dev_data.get("label", f"{dev_data.get('rows',1)}x{dev_data.get('cols',1)} Crossbar"),
        rows=dev_data.get("rows", 1),
        cols=dev_data.get("cols", 1),
        description=dev_data.get("description", ""),
        cell_area_um2=dev_data.get("cell_area_um2"),
        row_labels=dev_data.get("row_labels", []),
        col_labels=dev_data.get("col_labels", []),
    )

    # Build steps mapping: technique → step_name (reverse of protocol YAML)
    steps: dict[str, str] = {}
    for step in data.get("steps", []) or []:
        if isinstance(step, dict) and step.get("name") and step.get("technique"):
            steps[step["technique"]] = step["name"]

    # Try to read points from SQLite if available
    points: list[MatrixPoint] = []
    try:
        from science_cli.core.project import get_current_project_path
        from science_cli.library.memristor.db import close_db, open_db, query_files

        proj = get_current_project_path()
        if proj:
            conn = open_db(proj)
            try:
                files_data = query_files(conn, protocol=protocol_dir.name)
                # Group by (row, col)
                point_map: dict[tuple[int, int], MatrixPoint] = {}
                for fd in files_data:
                    r = fd.get("row")
                    c = fd.get("col")
                    if r is None or c is None:
                        continue
                    key = (r, c)
                    if key not in point_map:
                        point_map[key] = MatrixPoint(row=r, col=c)
                    pt = point_map[key]
                    tech = fd.get("technique_id") or "iv"
                    if tech not in pt.techniques:
                        pt.techniques[tech] = TechniqueGroup(technique=tech)
                    fe = FileEntry(
                        file=fd.get("filename", ""),
                        sweep_order=fd.get("sweep_order"),
                        sweep_type=fd.get("sweep_type"),
                        temperature=fd.get("temperature"),
                    )
                    pt.techniques[tech].files.append(fe)
                points = list(point_map.values())
            finally:
                close_db(conn)
    except Exception:
        pass  # SQLite not available; return empty points

    return DeviceConfig(
        device=device,
        points=points,
        steps=steps,
        _meta=data.get("_meta", {}),
    )


def write_devices(dir_path: Path | str, config: DeviceConfig) -> bool:
    """Save a DeviceConfig to devices.yaml.

    Writes the protocol-level format with a ``steps:`` mapping if
    the config has steps defined.

    .. deprecated::
        Use protocol YAML write functions instead
        (``memristor init --matrix``).
    """
    warnings.warn(
        "write_devices() is deprecated. "
        "Use protocol YAML write functions instead (memristor init --matrix).",
        DeprecationWarning,
        stacklevel=2,
    )

    data: dict = {
        "device": {
            "id": config.device.id,
            "label": config.device.label,
            "rows": config.device.rows,
            "cols": config.device.cols,
        },
        "points": [],
        "_meta": {
            "generated_by": "memristor sync",
            "generated_at": datetime.now().isoformat(),
            "total_cells": config.device.total_cells,
            "measured_cells": config.measured_cells,
            "missing_cells": [list(c) for c in config.missing_cells],
            "technique_coverage": config.technique_coverage,
        },
    }
    if config.device.description:
        data["device"]["description"] = config.device.description
    if config.device.cell_area_um2 is not None:
        data["device"]["cell_area_um2"] = config.device.cell_area_um2
    if config.device.row_labels:
        data["device"]["row_labels"] = config.device.row_labels
    if config.device.col_labels:
        data["device"]["col_labels"] = config.device.col_labels
    if config.steps:
        data["steps"] = dict(config.steps)

    for pt in sorted(config.points, key=lambda p: (p.row, p.col)):
        pt_data: dict = {"row": pt.row, "col": pt.col, "techniques": {}}
        for tech_name, tg in pt.techniques.items():
            if tg.files:
                pt_data["techniques"][tech_name] = [
                    fe.to_dict() for fe in tg.sorted_files()
                ]
        if pt.tags:
            pt_data["tags"] = pt.tags
        if pt_data["techniques"]:
            data["points"].append(pt_data)

    path = Path(dir_path) / "devices.yaml"
    with open(path, "w") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
        )
    return True


# ── Validation ──────────────────────────────────────────────


def validate(config: DeviceConfig, protocol_dir: Path | None = None) -> list[str]:
    """Validate a DeviceConfig and return list of issues (empty = valid)."""
    issues: list[str] = []

    if not config.device.id:
        issues.append("device.id is empty")
    if not config.device.label:
        issues.append("device.label is empty")
    if config.device.rows < 1:
        issues.append(f"device.rows must be >= 1, got {config.device.rows}")
    if config.device.cols < 1:
        issues.append(f"device.cols must be >= 1, got {config.device.cols}")

    for pt in config.points:
        if pt.row >= config.device.rows or pt.row < 0:
            issues.append(
                f"point r{pt.row}c{pt.col}: row out of bounds "
                f"(0-{config.device.rows - 1})"
            )
        if pt.col >= config.device.cols or pt.col < 0:
            issues.append(
                f"point r{pt.row}c{pt.col}: col out of bounds "
                f"(0-{config.device.cols - 1})"
            )
        if not pt.techniques:
            issues.append(f"point r{pt.row}c{pt.col}: has no techniques (empty)")
        for tech_name, tg in pt.techniques.items():
            if not tg.files:
                issues.append(
                    f"point r{pt.row}c{pt.col}/{tech_name}: "
                    "technique has no files"
                )
            for fe in tg.files:
                if not fe.file:
                    issues.append(
                        f"point r{pt.row}c{pt.col}/{tech_name}: "
                        "file entry has empty filename"
                    )
                if protocol_dir:
                    fpath = config.resolve_file_path(protocol_dir, tech_name, fe.file)
                    if not fpath.exists():
                        issues.append(
                            f"point r{pt.row}c{pt.col}/{tech_name}: "
                            f"file not found: {fe.file}"
                        )

    positions: dict[tuple[int, int], int] = {}
    for i, pt in enumerate(config.points):
        key = (pt.row, pt.col)
        if key in positions:
            issues.append(
                f"Duplicate position r{pt.row}c{pt.col}: "
                f"entries at index {positions[key]} and {i}"
            )
        positions[key] = i

    for pt in config.points:
        for tech_name, tg in pt.techniques.items():
            orders_seen: dict[int, str] = {}
            for fe in tg.files:
                if fe.sweep_order is not None:
                    if fe.sweep_order in orders_seen:
                        issues.append(
                            f"point r{pt.row}c{pt.col}/{tech_name}: "
                            f"duplicate sweep_order #{fe.sweep_order}: "
                            f"'{orders_seen[fe.sweep_order]}' and '{fe.file}'"
                        )
                    orders_seen[fe.sweep_order] = fe.file

    for pt in config.points:
        for tech_name in pt.techniques:
            if tech_name not in KNOWN_TECHNIQUES:
                issues.append(
                    f"point r{pt.row}c{pt.col}: unknown technique "
                    f"'{tech_name}' (known: "
                    f"{', '.join(sorted(KNOWN_TECHNIQUES))}) - "
                    "will be stored but analysis may not recognize it"
                )

    if protocol_dir and config.steps:
        for tech, step_dir_name in config.steps.items():
            step_path = protocol_dir / step_dir_name
            if not step_path.exists():
                issues.append(
                    f"steps: '{tech}' references "
                    f"non-existent step directory: {step_dir_name}"
                )

    return issues


# ── Sweep type validation ─────────────────────────────────

SWEEP_TYPE_MAP = {
    "f": {"segments": (2, 3), "desc": "full bipolar (0->+V->-V->0 or 0->-V->+V->0)"},
    "sp": {"segments": (1, 2), "desc": "sweep positive (0->+V->0)"},
    "sn": {"segments": (1, 2), "desc": "sweep negative (0->-V->0)"},
    "uc": {"segments": None, "desc": "uncategorized"},
}


def validate_sweep_type(
    filename: str,
    segments: list[dict],
    sweep_type_code: str,
) -> str | None:
    """Validate that the sweep type code matches actual data segments.

    Returns an error string if mismatch, None if valid.
    """
    if sweep_type_code == "uc":
        return None

    spec = SWEEP_TYPE_MAP.get(sweep_type_code)
    if not spec:
        return f"Unknown type code '{sweep_type_code}'"

    n = len(segments)
    expected = spec["segments"]

    if sweep_type_code == "f":
        # Full bipolar: need 2 or 3 segments
        if n < 2:
            return (
                f"Type 'f' (full bipolar) expects 2-3 segments, "
                f"but data has {n} segment(s)"
            )
    elif expected and n not in expected:
        return (
            f"Type '{sweep_type_code}' ({spec['desc']}) expects "
            f"{expected} segment(s), but data has {n}"
        )

    # Check voltage sign on first segment
    if segments:
        direction = segments[0].get("direction", "")
        try:
            # Parse "X.XXV -> Y.YYV" format
            parts = direction.split("->")
            if len(parts) == 2:
                v_end = float(parts[1].strip().rstrip("V"))
                if sweep_type_code == "sp" and v_end <= 0:
                    return (
                        f"Type 'sp' (positive sweep) but first segment "
                        f"end voltage is {v_end:.2f}V (expected positive)"
                    )
                if sweep_type_code == "sn" and v_end >= 0:
                    return (
                        f"Type 'sn' (negative sweep) but first segment "
                        f"end voltage is {v_end:.2f}V (expected negative)"
                    )
        except (ValueError, IndexError):
            pass  # can't parse direction string; skip sign check

    return None


# ── Sync ────────────────────────────────────────────────────


def sync_devices(protocol_dir: Path | str) -> dict:
    """Scan data files and update sweep metadata in devices.yaml.

    Uses the steps mapping to resolve file paths per technique.
    For each IV FileEntry, runs extract_sweep_from_file() and stores
    results in the entry's sweep field.

    Returns a report dict: {synced, missing, unreadable, total}.
    """
    from science_cli.core.sweep_metadata import extract_sweep_from_file

    path = Path(protocol_dir)
    config = read_devices(path)
    if config is None:
        return {"synced": 0, "missing": 0, "unreadable": 0, "total": 0, "type_mismatches": 0}

    synced = 0
    missing = 0
    unreadable = 0
    total = 0
    type_mismatches = 0

    for pt in config.points:
        for tech_name, tg in pt.techniques.items():
            if tech_name != "iv":
                continue
            for fe in tg.files:
                total += 1
                filepath = config.resolve_file_path(path, tech_name, fe.file)
                segments = extract_sweep_from_file(str(filepath))
                if segments is None:
                    unreadable += 1
                elif len(segments) == 0:
                    missing += 1
                else:
                    fe.sweep = segments
                    synced += 1

                # Validate sweep type against actual data segments
                if fe.sweep_type and segments:
                    mismatch = validate_sweep_type(
                        fe.file, segments, fe.sweep_type
                    )
                    if mismatch:
                        fe.extra["sweep_type_mismatch"] = mismatch
                        type_mismatches += 1
                    elif "sweep_type_mismatch" in fe.extra:
                        del fe.extra["sweep_type_mismatch"]

    if synced > 0:
        write_devices(path, config)

    return {
        "synced": synced,
        "missing": missing,
        "unreadable": unreadable,
        "total": total,
        "type_mismatches": type_mismatches,
    }


def sync_sweep_to_protocol_yaml(
    protocol_dir: Path, conn
) -> dict:
    """Sync sweep metadata from SQLite back to protocol YAML file entries.

    Steps:
        1. Read protocol YAML
        2. For each step, query sweep metadata from SQLite
        3. Update protocol YAML file entries with sweep data
        4. Save protocol YAML

    Args:
        protocol_dir: Path to the protocol subdirectory
            (e.g. ``protocol/1_pda/``).
        conn: Open SQLite connection.

    Returns:
        Report dict: ``{steps_updated: int, files_updated: int,
        errors: list[str]}``.
    """
    import sqlite3

    from science_cli.library.memristor.db import query_sweep_metadata

    proto_path = Path(protocol_dir)
    yaml_path = proto_path / f"{proto_path.name}.yaml"

    result: dict = {
        "steps_updated": 0,
        "files_updated": 0,
        "errors": [],
    }

    if not yaml_path.exists():
        result["errors"].append(f"Protocol YAML not found: {yaml_path}")
        return result

    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        result["errors"].append(f"Failed to read protocol YAML: {e}")
        return result

    if not isinstance(data, dict):
        result["errors"].append("Protocol YAML is not a dict")
        return result

    for step in data.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        step_name = step.get("name", "")
        if not step_name:
            continue

        try:
            sweep_data = query_sweep_metadata(
                conn, protocol=proto_path.name, step=step_name
            )
        except (sqlite3.OperationalError, sqlite3.ProgrammingError) as e:
            result["errors"].append(f"SQLite error for step '{step_name}': {e}")
            continue

        if not sweep_data:
            continue

        # Normalize existing files
        existing_files = _normalize_step_files(
            step.get("files", []) or []
        )

        # Build index of existing files by filename
        existing_by_name: dict[str, int] = {}
        for i, fe in enumerate(existing_files):
            fname = fe.get("file", "")
            if fname:
                existing_by_name[fname] = i

        step_updated = False
        for sd in sweep_data:
            fname = sd.get("filename", "")
            if not fname:
                continue

            entry: dict = {"file": fname}

            if sd.get("sweep_order") is not None:
                entry["sweep_order"] = sd["sweep_order"]
            if sd.get("sweep_type"):
                entry["sweep_type"] = sd["sweep_type"]
            if sd.get("temperature") is not None:
                entry["temperature"] = sd["temperature"]

            # Parse sweep_segments JSON if present
            sweep_segments_raw = sd.get("sweep_segments")
            if sweep_segments_raw:
                try:
                    import json
                    entry["sweep"] = json.loads(sweep_segments_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

            if fname in existing_by_name:
                # Merge with existing entry (preserve extra keys)
                idx = existing_by_name[fname]
                old_entry = existing_files[idx]
                for k, v in old_entry.items():
                    if k not in entry and k != "file":
                        entry[k] = v
                existing_files[idx] = entry
            else:
                existing_files.append(entry)

            result["files_updated"] += 1
            step_updated = True

        if step_updated:
            step["files"] = _denormalize_step_files(existing_files)
            result["steps_updated"] += 1

    if result["steps_updated"] > 0:
        try:
            with open(yaml_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False,
                          sort_keys=False, allow_unicode=True, indent=2)
        except Exception as e:
            result["errors"].append(f"Failed to write protocol YAML: {e}")

    return result


def _normalize_step_files(step_files: list) -> list[dict]:
    """Normalize a step's files list to list of dicts with 'file' key."""
    normalized: list[dict] = []
    for entry in step_files:
        if isinstance(entry, str):
            normalized.append({"file": entry})
        elif isinstance(entry, dict) and "file" in entry:
            normalized.append(entry)
    return normalized


def _denormalize_step_files(entries: list[dict]) -> list:
    """Convert normalized entries back: plain string if no extras, dict otherwise."""
    ENRICHED_KEYS = {"sweep_order", "sweep_type", "sweep", "temperature"}
    result: list = []
    for entry in entries:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        extra_keys = set(entry.keys()) - {"file"}
        if extra_keys & ENRICHED_KEYS or len(extra_keys) > 0:
            result.append(entry)
        else:
            result.append(entry.get("file", ""))
    return result


def _migrate_devices_yaml(protocol_dir: str | Path) -> dict:
    """Migrate legacy devices.yaml to protocol YAML.

    Calls ``migrate_from_devices_yaml()`` with the correct paths
    for the given protocol directory.

    Args:
        protocol_dir: Path to the protocol subdirectory
            (e.g. ``protocol/1_pda/``).

    Returns:
        Report dict from ``migrate_from_devices_yaml()``.
    """
    pd = Path(protocol_dir)
    devices_yaml_path = pd / "devices.yaml"
    protocol_yaml_path = pd / f"{pd.name}.yaml"

    return migrate_from_devices_yaml(devices_yaml_path, protocol_yaml_path)


# ── Grid display ────────────────────────────────────────────

TECH_LETTERS = {
    "iv": "I",
    "endurance": "E",
    "retention": "R",
    "switching": "S",
}
TECH_ORDER = ("iv", "endurance", "retention", "switching")


def generate_device_grid(
    config: DeviceConfig,
    occupied: set[tuple[int, int]] | None = None,
    technique: str = "",
    title: str = "",
    cell_counts: dict[tuple[int, int], int] | None = None,
) -> str:
    """Generate ASCII grid showing file count or technique coverage per cell.

    Conventions:
      R=row (1-indexed, R1 at top), C=col (1-indexed, C1 left, increases right)

    Args:
        occupied: If provided, only these positions are shown as occupied.
        technique: If provided, only check this technique (e.g., ``"iv"``).
        title: Optional title line above the grid.
        cell_counts: Optional dict of (row,col) → file count. If given, shows count.
    """
    rows, cols = config.device.rows, config.device.cols
    grid: dict[tuple[int, int], str] = {}

    for pt in config.points:
        if occupied is not None and (pt.row, pt.col) not in occupied:
            continue
        if cell_counts is not None:
            n = cell_counts.get((pt.row, pt.col), 0)
            grid[(pt.row, pt.col)] = str(n)
        elif technique:
            letters = (
                TECH_LETTERS.get(technique, "?")
                if pt.has_technique(technique)
                else "-"
            )
            grid[(pt.row, pt.col)] = letters
        else:
            letters = ""
            for tech in TECH_ORDER:
                letters += (
                    TECH_LETTERS.get(tech, "?")
                    if pt.has_technique(tech)
                    else "-"
                )
            grid[(pt.row, pt.col)] = letters

    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")

    col_header = "     " + "  ".join(f"C{j + 1}".ljust(5) for j in range(cols))
    lines.append(col_header)

    for i in range(rows):
        row_parts: list[str] = []
        for j in range(cols):
            cell = grid.get((i, j), "----")
            row_parts.append(cell.ljust(5))
        lines.append(f"R{i + 1}   " + "  ".join(row_parts))

    lines.append("")
    if cell_counts is not None:
        lines.append("File count per cell. '----' = no data")
    elif technique:
        lines.append(
            f"Legend: {TECH_LETTERS.get(technique, '?')}={technique.upper()}, "
            "-=not measured"
        )
    else:
        lines.append(
            "Legend: I=IV, E=Endurance, R=Retention, "
            "S=Switching, -=not measured"
        )
    lines.append("R=row, C=col, 1-indexed")
    return "\n".join(lines)


def generate_rich_grid(
    config: DeviceConfig,
    occupied: set[tuple[int, int]] | None = None,
    technique: str = "",
    title: str = "Device Matrix",
    cell_counts: dict[tuple[int, int], int] | None = None,
):
    """Generate a Rich Table showing file count or technique coverage per cell.

    Conventions:
      R=row (1-indexed, R1 at top), C=col (1-indexed, C1 left, increases right)

    Args:
        occupied: If provided, only these positions are shown as occupied.
        technique: If provided, only check this technique (e.g., ``"iv"``).
        title: Custom table title.
        cell_counts: Optional dict of (row,col) → file count. If given, shows count.
    """
    from rich.table import Table

    rows, cols = config.device.rows, config.device.cols
    grid: dict[tuple[int, int], str] = {}

    def _count_style(n_str: str) -> str:
        try:
            n = int(n_str)
            if n > 0:
                return f"[cyan]{n_str}[/cyan]"
            else:
                return f"[bright_black]{n_str}[/bright_black]"
        except ValueError:
            return f"[bright_black]{n_str}[/bright_black]"

    for pt in config.points:
        if occupied is not None and (pt.row, pt.col) not in occupied:
            continue
        if cell_counts is not None:
            n = cell_counts.get((pt.row, pt.col), 0)
            grid[(pt.row, pt.col)] = str(n)
        elif technique:
            letters = (
                TECH_LETTERS.get(technique, "?")
                if pt.has_technique(technique)
                else "-"
            )
            grid[(pt.row, pt.col)] = letters
        else:
            letters = ""
            for tech in TECH_ORDER:
                letters += (
                    TECH_LETTERS.get(tech, "?")
                    if pt.has_technique(tech)
                    else "-"
                )
            grid[(pt.row, pt.col)] = letters

    table = Table(title=title, show_header=True, border_style="bright_black")

    col_header = ["C" + str(j + 1) for j in range(cols)]
    table.add_column("", style="bold", width=4)
    for j, h in enumerate(col_header):
        table.add_column(h, justify="center", width=6)

    for i in range(rows):
        cells = [f"R{i + 1}"]
        for j in range(cols):
            val = grid.get((i, j), "----")
            if cell_counts is not None:
                cells.append(_count_style(val))
            else:
                styled = ""
                for ch in val:
                    color = TECH_STYLES.get(ch, "white")
                    styled += f"[{color}]{ch}[/{color}]"
                cells.append(styled)
        table.add_row(*cells)

    return table


# ── Orphan detection ────────────────────────────────


def find_orphaned_files(protocol_dir: Path) -> list[str]:
    """Find data files in protocol directory not tracked in devices.yaml.

    Scans all subdirectories recursively. Returns sorted list of
    relative paths from protocol_dir.
    """
    config = read_devices(protocol_dir)
    assigned = set(config.file_map.keys()) if config else set()

    orphans: list[str] = []
    for f in Path(protocol_dir).rglob("*"):
        if not f.is_file():
            continue
        if f.name in YAML_EXCLUDE or f.parent.name == "results":
            continue
        if f.suffix not in DATA_SUFFIXES:
            continue
        rel = f.relative_to(protocol_dir)
        if f.name not in assigned:
            orphans.append(str(rel))

    return sorted(orphans)


__all__ = [
    "SweepSegment",
    "FileEntry",
    "TechniqueGroup",
    "MatrixPoint",
    "DeviceGeometry",
    "DeviceConfig",
    "read_devices",
    "write_devices",
    "validate",
    "sync_devices",
    "sync_sweep_to_protocol_yaml",
    "_migrate_devices_yaml",
    "generate_device_grid",
    "generate_rich_grid",
    "find_orphaned_files",
    "extract_material_batch",
    "MATERIAL_TAG_PREFIX",
    "KNOWN_TECHNIQUES",
    "STANDARD_FILE_KEYS",
    "DATA_SUFFIXES",
    "YAML_EXCLUDE",
]
