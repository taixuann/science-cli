"""Crossbar device data models, YAML I/O, validation, and sync.

Models the hierarchy:
    Device (1) -> MatrixPoint (N) -> TechniqueGroup (0-4) -> FileEntry (1+)

devices.yaml lives at protocol/<proto>/devices.yaml with a steps:
mapping that connects techniques to step subdirectories.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Optional

import yaml


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

    def has_technique(self, tech: str) -> bool:
        return tech in self.techniques and len(self.techniques[tech].files) > 0

    def get_files(self, tech: str) -> list[FileEntry]:
        tg = self.techniques.get(tech)
        return tg.files if tg else []

    def get_primary_file(self, tech: str) -> Optional[FileEntry]:
        tg = self.techniques.get(tech)
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
        step = self.steps.get(technique)
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
    r'^\d{4}_'                        # DDMM date prefix
    r'([A-Za-z0-9\-]+?)'              # Material name (lazy)
    r'(?:\((\d+)\))?'                 # Optional batch number in parens
    r'_b\d+-t\d+_'                    # b#-t# position markers
)


def extract_material_batch(filename: str) -> tuple[str, str] | None:
    """Extract (material_name, batch_number) from a canonical memristor filename.

    Parses the ``DDMM_MaterialName(Batch)_b#-t#_...`` naming convention.

    Args:
        filename: e.g. ``"0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv"``

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
    m = _MATERIAL_BATCH_RE.match(filename)
    if not m:
        return None
    material = m.group(1)
    batch = m.group(2) or ""
    return (material, batch)


# ── YAML I/O ────────────────────────────────────────────────


def read_devices(dir_path: Path | str) -> Optional[DeviceConfig]:
    """Load devices.yaml from a directory.

    Supports two formats:
    - Protocol-level (new): has ``steps:`` mapping key
    - Step-level (legacy): no ``steps:`` key, files relative to dir

    Returns None if the file doesn't exist.
    """
    path = Path(dir_path) / "devices.yaml"
    if not path.exists():
        return None

    with open(path) as f:
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


def write_devices(dir_path: Path | str, config: DeviceConfig) -> bool:
    """Save a DeviceConfig to devices.yaml.

    Writes the protocol-level format with a ``steps:`` mapping if
    the config has steps defined.
    """
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
) -> str:
    """Generate ASCII grid showing technique coverage per cell.

    Conventions:
      T=top electrode (1-indexed, T1 at bottom, increases upward)
      B=bottom electrode (1-indexed, B1 left, increases right)

    Args:
        occupied: If provided, only these positions are shown as occupied.
        technique: If provided, only check this technique (e.g., ``"iv"``).
        title: Optional title line above the grid.
    """
    rows, cols = config.device.rows, config.device.cols
    grid: dict[tuple[int, int], str] = {}

    for pt in config.points:
        if occupied is not None and (pt.row, pt.col) not in occupied:
            continue
        if technique:
            letters = (
                TECH_LETTERS.get(technique, "?")
                if pt.has_technique(technique)
                else "-"
            )
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
    for i in reversed(range(rows)):
        row_parts: list[str] = []
        for j in range(cols):
            cell = grid.get((i, j), "----")
            row_parts.append(cell.ljust(5))
        lines.append(f"T{i + 1}   " + "  ".join(row_parts))

    bottom = "     " + "  ".join(f"B{j + 1}".ljust(5) for j in range(cols))
    lines.append(bottom)

    lines.append("")
    if technique:
        lines.append(
            f"Legend: {TECH_LETTERS.get(technique, '?')}={technique.upper()}, "
            "-=not measured"
        )
    else:
        lines.append(
            "Legend: I=IV, E=Endurance, R=Retention, "
            "S=Switching, -=not measured"
        )
    lines.append("T=top electrode row, B=bottom electrode col, 1-indexed")
    return "\n".join(lines)


def generate_rich_grid(
    config: DeviceConfig,
    occupied: set[tuple[int, int]] | None = None,
    technique: str = "",
    title: str = "Device Matrix",
):
    """Generate a Rich Table showing technique coverage per cell with colors.

    Conventions:
      T=top electrode (1-indexed, T1 at bottom, increases upward)
      B=bottom electrode (1-indexed, B1 left, increases right)

    Args:
        occupied: If provided, only these positions are shown as occupied.
        technique: If provided, only check this technique (e.g., ``"iv"``).
        title: Custom table title.
    """
    from rich.table import Table

    rows, cols = config.device.rows, config.device.cols
    grid: dict[tuple[int, int], str] = {}
    for pt in config.points:
        if occupied is not None and (pt.row, pt.col) not in occupied:
            continue
        if technique:
            letters = (
                TECH_LETTERS.get(technique, "?")
                if pt.has_technique(technique)
                else "-"
            )
        else:
            letters = ""
            for tech in TECH_ORDER:
                letters += (
                    TECH_LETTERS.get(tech, "?")
                    if pt.has_technique(tech)
                    else "-"
                )
        grid[(pt.row, pt.col)] = letters

    TECH_STYLES = {
        "I": "cyan",
        "E": "yellow",
        "R": "magenta",
        "S": "green",
        "-": "bright_black",
    }

    table = Table(title=title, show_header=False, border_style="bright_black")
    table.add_column("", style="bold", width=4)
    for j in range(cols):
        table.add_column("", justify="center", width=6)

    for i in reversed(range(rows)):
        cells = [f"T{i + 1}"]
        for j in range(cols):
            letters = grid.get((i, j), "----")
            styled = ""
            for ch in letters:
                color = TECH_STYLES.get(ch, "white")
                styled += f"[{color}]{ch}[/{color}]"
            cells.append(styled)
        table.add_row(*cells)

    footer = ["B" + str(j + 1) for j in range(cols)]
    table.add_row("", *footer, style="bold")

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
