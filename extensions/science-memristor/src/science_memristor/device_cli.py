#!/usr/bin/env python3
"""Standalone CLI for crossbar device management.

devices.yaml lives at protocol/<proto>/devices.yaml with a steps:
mapping that connects techniques to step subdirectories.

Usage:
    mem-device init --size 4x4 [--steps step-4,step-5 | iv:4_iv,endurance:5_end]
    mem-device ls [--matrix] [--technique iv] [--material ...]
    mem-device add --fzf [--filter ddmm,tech,purpose] [--matrix r0c0]
    mem-device add --pattern r'(\\d+)c(\\d+)' [--dry-run]
    mem-device rm --matrix r0c0 [--confirm]
    mem-device sync
    mem-device check [--list]
    mem-device plot [--all] [--fzf] [--filter ...] [--material ...] [--row R --col C] [--overwrite] [--dpi 150] [--multi-cycle]
    mem-device dashboard [--output path] [--open]

In the sci REPL, use 'memristor' instead of 'mem-device'.
"""

import argparse
import logging
import re
import shlex
import sys
from pathlib import Path

from rich import print as rprint
from rich.console import Console

from science_memristor.device import (
    DeviceGeometry,
    DeviceConfig,
    MatrixPoint,
    TechniqueGroup,
    FileEntry,
    read_devices,
    write_devices,
    validate as validate_config,
    sync_devices,
    generate_device_grid,
    generate_rich_grid,
    find_orphaned_files,
    extract_material_batch,
    KNOWN_TECHNIQUES,
)
from science_cli.core.session import (
    load_session,
    set_last_step,
)

logger = logging.getLogger(__name__)


# ── Protocol directory resolution ───────────────────────────


def _resolve_protocol_dir(args) -> Path:
    """Resolve protocol directory: --step-dir -> session -> cwd()."""
    if getattr(args, "step_dir", None):
        return Path(args.step_dir).resolve()

    sess = load_session()
    last_proj = sess.get("last_project", "")
    last_proto = sess.get("last_protocol", "")

    if last_proj and last_proto:
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if proj:
            pdir = proj / "protocol" / last_proto
            if pdir.exists():
                return pdir.resolve()

    return Path.cwd()


def _validate_protocol_dir(pdir: Path) -> bool:
    """Validate protocol dir. Returns False and prints error if invalid."""
    if not pdir.exists():
        print(f"Directory does not exist: {pdir}")
        print("Use 'open -m protocol -n <name>' or navigate to a protocol directory.")
        return False
    yaml_path = pdir / "devices.yaml"
    if not yaml_path.exists():
        print(f"No devices.yaml in {pdir}")
        print("Run 'memristor init' first.")
        return False
    return True


def _resolve_step_context(proto_dir: Path) -> tuple:
    """Resolve (protocol_name, technique) from a protocol directory."""
    name = proto_dir.name
    protocol_dir = proto_dir.parent
    if protocol_dir.name == "protocol":
        from science_cli.core.paths import ProjectPaths
        # proto_dir.parent.parent is the project root
        proj_root = protocol_dir.parent
        paths = ProjectPaths(proj_root)
        proto_yaml = paths.protocol_yaml(name)
        if proto_yaml.exists():
            import yaml
            with open(proto_yaml) as f:
                data = yaml.safe_load(f) or {}
            return name, ""
    return name, ""


# ── Argument parsing helpers ────────────────────────────────

_MATRIX_RE = re.compile(r'^r(\d+)c(\d+)$', re.IGNORECASE)


def _parse_matrix_arg(s: str) -> tuple[int, int]:
    """Parse 'r0c0' format into (row, col)."""
    m = _MATRIX_RE.match(s.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"Invalid matrix position '{s}'. Expected format: r0c0"
        )
    return int(m.group(1)), int(m.group(2))


def _parse_size_arg(s: str) -> tuple[int, int]:
    """Parse '4x4' format into (rows, cols)."""
    parts = s.strip().split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"Invalid size '{s}'. Expected format: 4x4"
        )
    try:
        rows = int(parts[0])
        cols = int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid size '{s}'. Expected format: 4x4"
        )
    if rows < 1 or cols < 1:
        raise argparse.ArgumentTypeError(
            f"Size must be positive: got {rows}x{cols}"
        )
    return rows, cols


# ── Technique inference ─────────────────────────────────────


def _infer_technique(filename: str) -> str:
    """Infer technique from filename alone."""
    from science_cli.core.technique import detect_technique

    ft = detect_technique(filename)
    TECH_MAP = {
        "iv-sweep": "iv",
        "iv-breakdown": "iv",
        "iv-leakage": "iv",
        "mem-endurance": "endurance",
        "mem-retention": "retention",
        "mem-switching": "switching",
    }
    return TECH_MAP.get(ft, "")


# ── Filename parsing ────────────────────────────────────────

CANONICAL_RE = re.compile(
    r'^'
    r'(?P<date>\d{4})'                         # DDMM
    r'_'
    r'(?P<material>[A-Za-z0-9\-\(\)]+?)'       # Material (lazy)
    r'_'
    r'r(?P<row>\d+)'                           # Row (0-indexed)
    r'c(?P<col>\d+)'                           # Column (0-indexed)
    r'_'
    r'(?P<technique>[A-Za-z0-9\-]+?)'          # Technique: iv, endurance, retention, switching
    r'(?:'                                      # Optional suffix (set, reset, forming, ...)
    r'_(?P<sweep_type>[A-Za-z0-9]+)'
    r')?'
    r'(?:'                                      # Optional attempt index (-1, -2, ...)
    r'-(?P<index>\d+)'
    r')?'
    r'\.'
    r'(?P<ext>csv|txt|dat|tsv|log)'            # Extension
    r'$'
)


def parse_canonical_filename(filename: str) -> dict | None:
    """Parse a canonical crossbar filename.

    Format: DDMM_Material_r#c#_Technique[_Suffix][-Index].ext

    Returns dict or None if not matching.
    """
    m = CANONICAL_RE.search(filename)
    if not m:
        return None
    return {
        "date": m.group("date"),
        "material": m.group("material"),
        "row": int(m.group("row")),
        "col": int(m.group("col")),
        "technique": m.group("technique"),
        "sweep_type": m.group("sweep_type"),  # e.g. set, reset, forming
        "index": int(m.group("index")) if m.group("index") else None,
        "ext": m.group("ext"),
        "technique_mapped": "",               # filled by infer_technique
    }


def _parse_filename_metadata(filename: str) -> dict:
    """Parse row, col, technique, sweep_type from filename convention."""
    meta = {
        "row": None,
        "col": None,
        "technique": "",
        "sweep_type": None,
        "sweep_order": None,
    }
    m = re.search(r'r(\d+)c(\d+)', filename, re.IGNORECASE)
    if m:
        meta["row"] = int(m.group(1))
        meta["col"] = int(m.group(2))

    tech_patterns = [
        (r'_(iv|IV)_(set|SET)\b', "iv", "SET"),
        (r'_(iv|IV)_(reset|RESET)\b', "iv", "RESET"),
        (r'_(iv|IV)_(forming|FORMING)\b', "iv", "FORMING"),
        (r'_(iv|IV)_(read|READ)\b', "iv", "READ"),
        (r'_(endurance|ENDURANCE)\b', "endurance", None),
        (r'_(retention|RETENTION)\b', "retention", None),
        (r'_(switching|SWITCHING)\b', "switching", None),
        (r'_iv[^a-z]', "iv", None),
        (r'[._]iv$', "iv", None),
    ]
    for pattern, tech, stype in tech_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            meta["technique"] = tech
            meta["sweep_type"] = stype
            break
    return meta


# ── Material tag helpers ─────────────────────────────────────


def _add_material_tag(pt: MatrixPoint, filename: str) -> None:
    """Extract material+batch from a canonical filename and add to point tags.

    Adds a tag like ``"material:Ta-PDA-ITO(1)"`` if the filename
    matches the canonical format.  Duplicates are silently skipped.
    """
    result = extract_material_batch(filename)
    if result:
        material, batch = result
        material_key = f"{material}({batch})" if batch else material
        tag = f"material:{material_key}"
        if tag not in pt.tags:
            pt.tags.append(tag)


def _format_material_display(material_key: str) -> str:
    """Format ``"Ta-PDA-ITO(1)"`` → ``"Ta-PDA-ITO (batch 1)"`` for display."""
    m = re.match(r"^(.+)\((\d+)\)$", material_key)
    if m:
        return f"{m.group(1)} (batch {m.group(2)})"
    return material_key


# ── Data file helpers ───────────────────────────────────────


def _device_data_files_recursive(proto_dir: Path) -> list[tuple[str, str, Path]]:
    """List data files recursively across step subdirs.

    Returns list of (rel_path, step_dir_name, Path) tuples.
    """
    from science_memristor.device import DATA_SUFFIXES, YAML_EXCLUDE

    results: list[tuple[str, str, Path]] = []
    for f in proto_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.name in YAML_EXCLUDE or f.parent.name == "results":
            continue
        if f.suffix not in DATA_SUFFIXES:
            continue
        rel = f.relative_to(proto_dir)
        step_dir_name = str(f.parent.name) if f.parent != proto_dir else ""
        results.append((str(rel), step_dir_name, f))
    return sorted(results, key=lambda x: x[0])


# ── Command: init ───────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    yaml_path = pdir / "devices.yaml"
    if yaml_path.exists():
        print(f"devices.yaml already exists at {yaml_path}")
        sys.exit(1)

    from science_cli.core.technique import detect_technique
    TECH_MAP = {
        "iv-sweep": "iv", "iv-breakdown": "iv", "iv-leakage": "iv",
        "mem-endurance": "endurance", "mem-retention": "retention",
        "mem-switching": "switching",
    }

    steps: dict[str, str] = {}
    raw = getattr(args, "steps", "") or ""
    if raw:
        for raw_part in raw.split(","):
            part = raw_part.strip()
            if not part:
                continue
            if ":" in part:
                tech, step_dir_name = part.split(":", 1)
                steps[tech.strip()] = step_dir_name.strip()
            else:
                ft = detect_technique(part)
                tech = TECH_MAP.get(ft, "")
                if tech:
                    steps[tech] = part
                else:
                    # Look up step technique from protocol YAML
                    import yaml
                    proto_yaml = pdir / f"{pdir.name}.yaml"
                    if proto_yaml.exists():
                        with open(proto_yaml) as f:
                            proto = yaml.safe_load(f)
                        for s in (proto or {}).get("steps", []):
                            if s.get("name") == part:
                                st = s.get("technique", "")
                                if st in ("ec-cv", "ec-ca", "ec-eis"):
                                    pass  # Skip electrochem steps
                                elif st:
                                    steps[st] = part
                                break

    rows, cols = args.size
    config = DeviceConfig(
        device=DeviceGeometry(
            id=f"crossbar-{rows}x{cols}",
            label="",
            rows=rows,
            cols=cols,
        ),
        points=[],
        steps=steps,
    )
    write_devices(pdir, config)
    print(f"Initialized {yaml_path}")
    print(f"  Device: {config.device.id} ({config.device.rows}x{config.device.cols})")
    print(f"  Cells: {config.device.total_cells}")
    if steps:
        print(f"  Steps mapping: {steps}")
    print(f"  Use 'memristor ls --matrix' to view the grid.")
    if not steps:
        print(f"  Tip: add --steps step_dir_name or --steps iv:4_iv,endurance:5_end")
    set_last_step(pdir.name)


# ── Command: ls ─────────────────────────────────────────────


def cmd_ls(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    material_filter = getattr(args, "material", "") or ""
    technique = args.technique or ""

    if args.matrix:
        from rich.console import Console

        console = Console()
        material_groups = config.get_points_by_material()

        if material_filter:
            # Single-material view (filtered)
            points = material_groups.get(material_filter, [])
            occupied: set[tuple[int, int]] = {(p.row, p.col) for p in points}
            if technique and points:
                occupied = {
                    (p.row, p.col)
                    for p in points
                    if p.has_technique(technique)
                }
            title = (
                f"Material: {_format_material_display(material_filter)} "
                f"— {len(occupied)} cell(s)"
            )
            console.print(
                generate_rich_grid(
                    config, occupied=occupied, technique=technique, title=title
                )
            )
        elif not material_groups:
            # No material data — single grid (backward-compatible)
            console.print(generate_rich_grid(config, technique=technique))
        else:
            # All materials — one table per material+batch
            first = True
            for mat_key in sorted(material_groups.keys()):
                points = material_groups[mat_key]
                occupied = {(p.row, p.col) for p in points}
                if technique:
                    occupied = {
                        (p.row, p.col)
                        for p in points
                        if p.has_technique(technique)
                    }
                if not occupied:
                    continue
                if not first:
                    console.print()  # blank line between tables
                first = False
                display_name = _format_material_display(mat_key)
                title = (
                    f"Material: {display_name} "
                    f"— {len(occupied)} cell(s)"
                )
                console.print(
                    generate_rich_grid(
                        config,
                        occupied=occupied,
                        technique=technique,
                        title=title,
                    )
                )
        return

    # ── Plain (non-matrix) listing ────────────────────────────

    print(f"Device: {config.device.label} ({config.device.id})")
    print(f"  Geometry: {config.device.rows} rows x {config.device.cols} cols")
    print(f"  Measured: {config.measured_cells}/{config.device.total_cells} cells")
    print(f"  Files: {config.total_files}")
    print(f"  Techniques: {', '.join(sorted(config.technique_coverage.keys()))}")
    if config.steps:
        print(f"  Steps mapping: {dict(config.steps)}")

    if args.technique:
        tech = args.technique
        pts = config.get_points_with_technique(tech)
        if material_filter:
            material_groups = config.get_points_by_material()
            mat_positions: set[tuple[int, int]] = set()
            for p in material_groups.get(material_filter, []):
                mat_positions.add((p.row, p.col))
            pts = [p for p in pts if (p.row, p.col) in mat_positions]
        print(f"\nPoints with {tech}: {len(pts)}")
        for pt in sorted(pts, key=lambda p: (p.row, p.col)):
            files = pt.get_files(tech)
            flist = ", ".join(fe.file for fe in files)
            print(f"  r{pt.row}c{pt.col}: {flist}")

    set_last_step(pdir.name)


# ── Command: add ────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> None:
    """Add files to the crossbar device config.

    Supports two modes:
      --fzf        Interactive fzf file picker (scans all step subdirs)
      --pattern    Batch regex assignment
    """
    if args.fzf:
        cmd_add_fzf(args)
        return
    if args.pattern:
        cmd_add_pattern(args)
        return

    # No mode selected — show usage guidance
    print("No assignment mode selected.")
    print("Use one of:")
    print("  memristor add --fzf            Interactive file picker")
    print("  memristor add --fzf --filter FILTER   Pre-filtered picker")
    print("  memristor add --pattern REGEX   Batch regex assignment")
    sys.exit(1)


def cmd_add_pattern(args: argparse.Namespace) -> None:
    """Batch-assign files matching a regex pattern, recursive scan."""
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    try:
        pattern = re.compile(args.pattern)
    except re.error as e:
        print(f"Invalid regex pattern: {e}")
        sys.exit(1)

    assigned = set(config.file_map.keys())
    all_files = _device_data_files_recursive(pdir)
    unassigned = [(r, s, p) for r, s, p in all_files if p.name not in assigned]
    matches: list[tuple[Path, int, int]] = []

    for rel_path, step_name, fpath in unassigned:
        m = pattern.search(fpath.name)
        if m:
            try:
                row = int(m.group(1))
                col = int(m.group(2))
            except (IndexError, ValueError):
                continue
            if row >= config.device.rows or col >= config.device.cols:
                print(f"  Skipping {rel_path}: position r{row}c{col} out of bounds")
                continue
            matches.append((fpath, row, col))

    if not matches:
        print("No files match pattern.")
        return

    tech = _infer_technique(matches[0][0].name) or "iv"

    print(f"\nPattern: {args.pattern}")
    print(f"Technique: {tech}")
    print(f"Matches: {len(matches)} file(s)")
    print(f"  {'File':40s} {'Row':4s} {'Col':4s}")
    print("  " + "-" * 55)
    for f, r, c in matches:
        print(f"  {f.name:40s} {r:4d} {c:4d}")

    if args.dry_run:
        print("\n[Dry run] No changes written.")
        return

    for f, r, c in matches:
        pt = config.get_point(r, c)
        if pt is None:
            pt = MatrixPoint(row=r, col=c)
            config.points.append(pt)
        if tech not in pt.techniques:
            pt.techniques[tech] = TechniqueGroup(technique=tech)
        fe = FileEntry(file=f.name)
        pt.techniques[tech].files.append(fe)
        _add_material_tag(pt, f.name)

    write_devices(pdir, config)
    print(f"Added {len(matches)} file(s) via pattern.")
    set_last_step(pdir.name)


def cmd_add_fzf(args: argparse.Namespace) -> None:
    """Interactive fzf file picker — scans all step subdirs recursively."""
    from science_cli.core.fzf_utils import (
        fzf_select,
        parse_filter_string,
        filter_files_by_metadata,
    )

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    assigned = set(config.file_map.keys())
    all_files = _device_data_files_recursive(pdir)
    unassigned = [(r, s, p) for r, s, p in all_files if p.name not in assigned]

    if not unassigned:
        print("No unassigned data files found.")
        return

    display_names = [rel for rel, _, _ in unassigned]

    filter_str = getattr(args, "filter", "") or ""
    if filter_str:
        fd = parse_filter_string(filter_str)
        display_names = filter_files_by_metadata(display_names, fd)

    if not display_names:
        print("No files match filter.")
        return

    selected = fzf_select(
        items=display_names,
        prompt="Select data files to assign >",
        multi=True,
        preview="head -30 {}",
        preview_window="right:50%:border-sharp",
        query=filter_str.split(",")[0] if filter_str else "",
    )
    if not selected:
        print("No files selected.")
        return

    # Build a lookup from display name → (rel_path, step, path)
    lookup = {rel: (rel, step, path) for rel, step, path in unassigned}

    # Parse --matrix override if provided
    matrix_override = getattr(args, "matrix", None)
    override_row = None
    override_col = None
    if matrix_override:
        override_row, override_col = _parse_matrix_arg(matrix_override)

    assignments = []
    for display in selected:
        rel_path, step_name, fpath = lookup[display]
        # Try canonical parser first, fall back to legacy parser
        canonical = parse_canonical_filename(fpath.name)
        if canonical:
            tech = canonical["technique_mapped"] or _infer_technique(fpath.name) or "iv"
            row = override_row if override_row is not None else canonical["row"]
            col = override_col if override_col is not None else canonical["col"]
            sweep_type = canonical["sweep_type"]
        else:
            meta = _parse_filename_metadata(fpath.name)
            tech = meta["technique"] or _infer_technique(fpath.name) or "iv"
            row = override_row if override_row is not None else (meta["row"] or 0)
            col = override_col if override_col is not None else (meta["col"] or 0)
            sweep_type = meta["sweep_type"]
        assignments.append({
            "file": fpath.name,
            "row": row,
            "col": col,
            "technique": tech,
            "sweep_type": sweep_type,
            "step_name": step_name,
            "fpath": fpath,
        })

    print("\nAssignments:")
    print(f"  {'File':30s} {'Row':4s} {'Col':4s} {'Technique':12s} {'Type'}")
    print("  " + "-" * 65)
    for a in assignments:
        st = a["sweep_type"] or "-"
        print(f"  {a['file']:30s} {a['row']:4d} {a['col']:4d} {a['technique']:12s} {st}")

    try:
        ok = input("\nApply these assignments? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ok = ""
    if ok != "y":
        print("Cancelled.")
        return

    for a in assignments:
        pt = config.get_point(a["row"], a["col"])
        if pt is None:
            pt = MatrixPoint(row=a["row"], col=a["col"])
            config.points.append(pt)
        if a["technique"] not in pt.techniques:
            pt.techniques[a["technique"]] = TechniqueGroup(technique=a["technique"])
        fe = FileEntry(file=a["file"], sweep_type=a["sweep_type"])
        pt.techniques[a["technique"]].files.append(fe)
        _add_material_tag(pt, a["file"])

    write_devices(pdir, config)
    print(f"Added {len(assignments)} file(s).")

    # Always auto-sync sweep metadata after assignment
    from science_cli.core.sweep_metadata import extract_sweep_from_file

    synced_count = 0
    for a in assignments:
        pt = config.get_point(a["row"], a["col"])
        if pt is None:
            continue
        tg = pt.techniques.get(a["technique"])
        if tg is None:
            continue
        # Find the FileEntry we just added (match by filename)
        for fe in tg.files:
            if fe.file == a["file"]:
                fpath = config.resolve_file_path(
                    pdir, a["technique"], a["file"]
                )
                segments = extract_sweep_from_file(str(fpath))
                if segments:
                    fe.sweep = segments
                    synced_count += 1
                break

    if synced_count > 0:
        write_devices(pdir, config)
        print(f"Auto-synced sweep metadata for {synced_count} file(s).")

    set_last_step(pdir.name)


# ── Command: rm ─────────────────────────────────────────────


def cmd_rm(args: argparse.Namespace) -> None:
    """Remove an entire matrix point from the device config."""
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    row, col = _parse_matrix_arg(args.matrix)

    pt = config.get_point(row, col)
    if pt is None:
        print(f"No point at r{row}c{col}")
        sys.exit(1)

    if not args.confirm:
        print(f"Use --confirm to remove entire point r{row}c{col}")
        print(f"  This point has {pt.total_files} file(s) across "
              f"{len(pt.techniques)} technique(s).")
        sys.exit(1)

    config.points = [
        p for p in config.points
        if not (p.row == row and p.col == col)
    ]

    write_devices(pdir, config)
    print(f"Removed point r{row}c{col}")
    set_last_step(pdir.name)


# ── Command: sync ───────────────────────────────────────────


def cmd_sync(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    report = sync_devices(pdir)
    print(
        f"Sync complete: {report['synced']} synced, "
        f"{report['missing']} missing data, "
        f"{report['unreadable']} unreadable, "
        f"{report['type_mismatches']} type mismatches, "
        f"{report['total']} total IV files"
    )


# ── Command: check ──────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> None:
    """Find data files not tracked in devices.yaml (recursive scan)."""
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    config = read_devices(pdir)
    step_filter = list(config.steps.values()) if config and config.steps else None
    orphans = find_orphaned_files(pdir, step_filter=step_filter)
    if not orphans:
        print("All files are assigned in devices.yaml.")
        return

    if args.list:
        print(f"Unassigned files ({len(orphans)}):")
        for fn in orphans:
            print(f"  {fn}")
    else:
        print(f"Found {len(orphans)} unassigned file(s).")
        print("Use 'memristor check --list' to see them.")
        print("Use 'memristor add --fzf' to assign interactively.")
        print("Use 'memristor add --pattern <regex>' for batch assignment.")

    sys.exit(1)


def _parse_column_overrides(user_input: str) -> dict:
    """Parse interactive column override input using shlex.

    Input format: ``--x COL_NAME --y COL_NAME [--y2 COL_NAME] [--group COL_NAME]``
    Returns dict mapping logical roles (``"voltage"``, ``"current"``, etc.)
    to column header names.

    Args:
        user_input: Raw input string from the user.

    Returns:
        Dict suitable for use as ``column_map``. Empty dict if no overrides.
    """
    if not user_input.strip():
        return {}

    try:
        parts = shlex.split(user_input)
    except ValueError:
        return {}

    column_map: dict = {}
    i = 0
    while i < len(parts):
        flag = parts[i]
        if flag in ("--x",) and i + 1 < len(parts):
            column_map["voltage"] = parts[i + 1]
            i += 2
        elif flag in ("--y",) and i + 1 < len(parts):
            column_map["current"] = parts[i + 1]
            i += 2
        elif flag in ("--y2",) and i + 1 < len(parts):
            column_map["y2"] = parts[i + 1]
            i += 2
        elif flag in ("--group",) and i + 1 < len(parts):
            column_map["group"] = parts[i + 1]
            i += 2
        else:
            i += 1
    return column_map


# ── Command: plot ───────────────────────────────────────────


def cmd_plot(args: argparse.Namespace) -> None:
    """Batch-generate IV curve SVGs from devices.yaml."""
    from science_memristor.plotting import (
        read_iv_csv,
        build_plot_filename,
        build_plot_title,
        generate_iv_svg,
        collect_iv_files,
        build_fzf_line,
        detect_csv_columns,
    )

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    # ── Issue 1: Auto-sync if no sweep metadata found ──
    total_sweep = sum(1 for _, fe in config.get_all_files("iv") if fe.sweep)
    if total_sweep == 0:
        print("No sweep metadata found. Running sync first...")
        sync_devices(pdir)
        config = read_devices(pdir)
        if config is None:
            print("Failed to re-read devices.yaml after sync.")
            sys.exit(1)

    # Collect all IV files
    row_filter = args.row if getattr(args, "row", None) is not None else None
    col_filter = args.col if getattr(args, "col", None) is not None else None
    material_filter = getattr(args, "material", "") or ""

    targets = collect_iv_files(config, material=material_filter, row=row_filter, col=col_filter)

    if not targets:
        print("No IV files found in devices.yaml.")
        return

    # Apply fzf filter if requested
    if args.fzf:
        from science_cli.core.fzf_utils import fzf_select, parse_filter_string, filter_files_by_metadata

        # Build display lines
        display_map: dict[str, dict] = {}
        display_lines: list[str] = []
        for t in targets:
            line = build_fzf_line(t)
            display_lines.append(line)
            display_map[line] = t

        filter_str = getattr(args, "filter", "") or ""
        if filter_str:
            fd = parse_filter_string(filter_str)
            # Re-filter using the parsed filter
            if filter_str:
                filtered_lines = filter_files_by_metadata(display_lines, fd)
                if not filtered_lines:
                    print("No files match filter.")
                    return
                display_lines = filtered_lines

        selected_lines = fzf_select(
            items=display_lines,
            prompt="Select IV files to plot >",
            multi=True,
            preview="echo {}",
            preview_window="",
            query=filter_str.split(",")[0] if filter_str else "",
        )
        if not selected_lines:
            print("No files selected.")
            return

        # Map back to targets
        targets = [display_map[line] for line in selected_lines if line in display_map]

    # ── Build column_map from CLI flags ──
    column_map: dict = {}
    if getattr(args, "x", None):
        column_map["voltage"] = args.x
    if getattr(args, "y", None):
        column_map["current"] = args.y
    if getattr(args, "y2", None):
        column_map["y2"] = args.y2
    if getattr(args, "group", None):
        column_map["group"] = args.group

    # ── Column preview + interactive override ──
    if targets:
        first_target = targets[0]
        first_fe = first_target["file_entry"]
        first_filepath = config.resolve_file_path(pdir, "iv", first_fe.file)

        try:
            detected = detect_csv_columns(str(first_filepath))
        except Exception as exc:
            print(f"  Warning: could not detect columns from {first_fe.file}: {exc}")
            detected = {"time": None, "voltage": None, "current": None}

        print(f"\nColumn detection (from first file: {first_fe.file}):")
        time_name = detected.get("time") or "—"
        volt_name = column_map.get("voltage") or detected.get("voltage") or "—"
        curr_name = column_map.get("current") or detected.get("current") or "—"
        rprint(f"  time    : [bold cyan]{time_name}[/bold cyan]")
        override_mark = "  [bright_black][override][/bright_black]" if column_map.get("voltage") else ""
        rprint(f"  x (V)   : [bold green]{volt_name}[/bold green]{override_mark}")
        override_mark = "  [bright_black][override][/bright_black]" if column_map.get("current") else ""
        rprint(f"  y (A)   : [bold yellow]{curr_name}[/bold yellow]{override_mark}")

        # Interactive override prompt (only if no CLI flags given)
        has_cli_overrides = bool(column_map.get("voltage") or column_map.get("current"))
        if not has_cli_overrides:
            try:
                override_input = Console().input(
                    "\n[bold]Override columns?[/bold] (--x COL --y COL) [Enter for defaults]: "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                override_input = ""
            if override_input:
                overrides = _parse_column_overrides(override_input)
                column_map.update(overrides)
                if overrides:
                    print("  Using overrides:", ", ".join(
                        f"{k}={v}" for k, v in overrides.items()
                    ))

        # Confirmation
        try:
            proceed = Console().input("\n[bold]Proceed with plot?[/bold] [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            proceed = ""
        if proceed and proceed != "y":
            print("Cancelled.")
            return

    # Store column_map in targets (update in-place for interactive overrides)
    if column_map:
        for t in targets:
            t["column_map"] = column_map

    # Resolve results directory
    step_dir_name = config.steps.get("iv", "4_iv-characterization")
    results_dir = pdir / step_dir_name / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    overwrite = getattr(args, "overwrite", False)
    dpi = 600

    # ── Issue 4: Compute per-cell file index for line style cycling ──
    position_files: dict[tuple[int, int], list[dict]] = {}
    for t in targets:
        pos = (t["row"], t["col"])
        position_files.setdefault(pos, []).append(t)
    for pos, files in position_files.items():
        files.sort(key=lambda x: x["order"])
        for i, f in enumerate(files):
            f["file_index"] = i

    plotted = 0
    skipped = 0
    errors = 0

    for t in targets:
        fe = t["file_entry"]
        plot_filename = fe.extra.get("plot", "")

        # Skip if already plotted and not overwriting
        if plot_filename and not overwrite:
            existing = results_dir / plot_filename
            if existing.exists():
                skipped += 1
                continue

        # Read CSV data
        filepath = config.resolve_file_path(pdir, "iv", fe.file)
        try:
            voltage, current, info = read_iv_csv(
                str(filepath),
                column_map=column_map if column_map else None,
            )
        except Exception as exc:
            print(f"  Error reading {fe.file}: {exc}")
            errors += 1
            continue

        # Build plot metadata
        plot_filename = build_plot_filename(
            row=t["row"],
            col=t["col"],
            material_key=t["material_key"],
            sweep_type=t["sweep_type"],
            order=t["order"],
        )
        title = build_plot_title(
            order=t["order"],
            sweep=fe.sweep,
            sweep_type=t["sweep_type"],
        )

        metadata = {
            "title": title,
            "sweep": fe.sweep,
            "sweep_type": fe.sweep_type,
            "row": t["row"],
            "col": t["col"],
            "order": t["order"],
            "file_index": t.get("file_index", 0),
            "time": info.get("time"),  # for auto-detection fallback in generate_iv_svg
        }

        # Generate SVG
        output_path = results_dir / plot_filename
        try:
            multi_cycle = getattr(args, "multi_cycle", False)
            generate_iv_svg(
                voltage, current, metadata, str(output_path),
                dpi=dpi,
                multi_cycle=multi_cycle,
                column_map=column_map if column_map else None,
            )
        except Exception as exc:
            print(f"  Error plotting {fe.file}: {exc}")
            errors += 1
            continue

        # Store plot filename in devices.yaml
        fe.extra["plot"] = plot_filename
        plotted += 1
        print(f"  ✓ {plot_filename}")

    # Write updated devices.yaml
    if plotted > 0:
        write_devices(pdir, config)
        print(f"\nPlotted: {plotted} | Skipped (exists): {skipped} | Errors: {errors}")
        print(f"Results: {results_dir}/")
    else:
        print(f"\nNo new plots generated. {skipped} already exist. Use --overwrite to regenerate.")

    set_last_step(pdir.name)


# ── Command: dashboard ──────────────────────────────────────


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Generate an HTML dashboard for plotted IV SVGs."""
    from science_memristor.dashboard import generate_dashboard

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    # Resolve results directory
    step_dir_name = config.steps.get("iv", "4_iv-characterization")
    results_dir = pdir / step_dir_name / "results"

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        print("Run 'memristor plot --all' first.")
        sys.exit(1)

    # Determine output path
    output_path = results_dir / (args.name or "dashboard.html")

    try:
        out = generate_dashboard(config, results_dir, output_path)
        print(f"Dashboard generated: {out}")

        if getattr(args, "open", False):
            import subprocess
            subprocess.run(["open", str(out)], check=False)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error generating dashboard: {exc}")
        sys.exit(1)

    set_last_step(pdir.name)


# ── CLI entry point ─────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crossbar device manager for memristor characterization"
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # ── init ──
    p_init = sub.add_parser("init", help="Scaffold a devices.yaml")
    p_init.add_argument(
        "--size", type=_parse_size_arg, required=True,
        help="Crossbar dimensions in {rows}x{cols} format (e.g. 4x4)",
    )
    p_init.add_argument(
        "--steps", default="",
        help="Step dirs: step-4,step-5 or iv:4_iv,endurance:5_end",
    )
    p_init.set_defaults(func=cmd_init)

    # ── ls ──
    p_ls = sub.add_parser("ls", help="List devices or matrix map")
    p_ls.add_argument("--step-dir", default="")
    p_ls.add_argument("--matrix", action="store_true", help="Grid view (per-material when data tagged)")
    p_ls.add_argument("--technique", default="", help="Filter by technique (e.g., iv)")
    p_ls.add_argument("--material", default="", help="Filter by material+batch (e.g., Ta-PDAc-ITO(1))")
    p_ls.set_defaults(func=cmd_ls)

    # ── add ──
    p_add = sub.add_parser("add", help="Add file(s) to device config")
    p_add.add_argument("--fzf", action="store_true", help="Interactive fzf picker (scans all step dirs)")
    p_add.add_argument("--filter", default="", help="Pre-filter for fzf: {ddmm},{technique},{purpose}")
    p_add.add_argument(
        "--matrix", default=None,
        help="Override cell position as r0c0 (used with --fzf)",
    )
    p_add.add_argument(
        "--pattern", default="",
        help="Regex for batch: r(\\d+)c(\\d+) captures row/col",
    )
    p_add.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_add.add_argument("--step-dir", default="")
    p_add.set_defaults(func=cmd_add)

    # ── rm ──
    p_rm = sub.add_parser("rm", help="Remove a matrix point from the device config")
    p_rm.add_argument(
        "--matrix", required=True,
        help="Cell position as r0c0",
    )
    p_rm.add_argument("--confirm", action="store_true", help="Confirm point removal")
    p_rm.add_argument("--step-dir", default="")
    p_rm.set_defaults(func=cmd_rm)

    # ── sync ──
    p_sync = sub.add_parser("sync", help="Sync sweep metadata from data files")
    p_sync.add_argument("--step-dir", default="")
    p_sync.set_defaults(func=cmd_sync)

    # ── check ──
    p_check = sub.add_parser("check", help="Find unassigned data files (recursive)")
    p_check.add_argument("--list", action="store_true", help="List unassigned files")
    p_check.add_argument("--step-dir", default="")
    p_check.set_defaults(func=cmd_check)

    # ── plot ──
    p_plot = sub.add_parser("plot", help="Generate IV curve SVGs from devices.yaml")
    p_plot.add_argument("--step-dir", default="")
    p_plot.add_argument("--all", action="store_true", help="Plot all IV files (default if no filter)")
    p_plot.add_argument("--fzf", action="store_true", help="Interactive fzf multi-select picker")
    p_plot.add_argument("--filter", default="", help="Pre-filter for fzf: {material},{sweep_type},{ddmm}")
    p_plot.add_argument("--material", default="", help="Plot files for a specific material+batch")
    p_plot.add_argument("--row", type=int, default=None, help="Filter by matrix row")
    p_plot.add_argument("--col", type=int, default=None, help="Filter by matrix column")
    p_plot.add_argument("--overwrite", action="store_true", help="Re-plot even if SVG already exists")
    p_plot.add_argument("--multi-cycle", action="store_true", help="Plot all sweep cycles (default: first cycle only)")
    p_plot.add_argument("--x", default=None, help="Override x-axis (voltage) column name")
    p_plot.add_argument("--y", default=None, help="Override y-axis (current) column name")
    p_plot.add_argument("--y2", default=None, help="Override secondary y-axis column name")
    p_plot.add_argument("--group", default=None, help="Override grouping column name")
    p_plot.set_defaults(func=cmd_plot)

    # ── dashboard ──
    p_dash = sub.add_parser("dashboard", help="Generate HTML viewer for plotted IV SVGs")
    p_dash.add_argument("-n", "--name", default="dashboard.html", help="Output filename (default: dashboard.html)")
    p_dash.add_argument("--open", action="store_true", help="Open in browser")
    p_dash.set_defaults(func=cmd_dashboard)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
