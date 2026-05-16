#!/usr/bin/env python3
"""Standalone CLI for crossbar device management.

devices.yaml lives at protocol/<proto>/devices.yaml with a steps:
mapping that connects techniques to step subdirectories.

Usage:
    mem-device init --rows 4 --cols 4 --label "My Device" [--steps iv:4_iv,endurance:5_end]
    mem-device ls [--matrix] [--technique iv]
    mem-device info --row 0 --col 0
    mem-device add --row 0 --col 0 --file data.txt [--technique iv]
    mem-device add --fzf

    # Plot all:
    mem-device plot --all [--material ...] [--row R --col C] [--overwrite] [--dpi 150]

    # Interactive:
    mem-device plot [--all] [--fzf] [--material ...] [--row R --col C] [--overwrite] [--dpi 150]
    mem-device dashboard [--output path] [--open]
    
In the sci REPL, use 'memristor' instead of 'mem-device'.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from science_cli.memristor.device import (
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
    """Validate protocol dir. Returns False only if directory does not exist.
    
    devices.yaml is optional — sync and analyze use grammar-based workflows
    that don't require it. Older commands that need devices.yaml will fail
    when they call read_devices().
    """
    if not pdir.exists():
        print(f"Directory does not exist: {pdir}")
        print("Use 'open -m protocol -n <name>' or navigate to a protocol directory.")
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


# ── Technique inference ─────────────────────────────────────


def _build_tech_map(project_root=None) -> dict[str, str]:
    """Build technique name → short name mapping from config.

    Reads from config ``techniques.<name>.short_name`` first.
    Falls back to hardcoded TECH_MAP if config doesn't define a mapping.
    """
    HARDCODED_TECH_MAP = {
        "iv-sweep": "iv",
        "iv-breakdown": "iv",
        "iv-leakage": "iv",
        "mem-endurance": "endurance",
        "mem-retention": "retention",
        "mem-switching": "switching",
    }
    try:
        from science_cli.core.config import get_technique_config
        result: dict[str, str] = {}
        for tech, fallback in HARDCODED_TECH_MAP.items():
            tconfig = get_technique_config(tech, project_root)
            if tconfig and "short_name" in tconfig:
                result[tech] = tconfig["short_name"]
            else:
                result[tech] = fallback
        return result
    except ImportError:
        return dict(HARDCODED_TECH_MAP)


def _infer_technique(filename: str) -> str:
    """Infer technique from filename alone."""
    from science_cli.core.technique import detect_technique

    ft = detect_technique(filename)
    tech_map = _build_tech_map()
    return tech_map.get(ft, "")


# ── Filename parsing ────────────────────────────────────────

CANONICAL_RE = re.compile(
    r'^'
    r'(?P<date>\d{4})'                         # DDMM
    r'_'
    r'(?P<material>[A-Za-z0-9\-\(\)]+?)'       # Material (lazy)
    r'_'
    r'b(?P<bottom>\d+)'                        # Bottom electrode # (1-indexed)
    r'-'
    r't(?P<top>\d+)'                           # Top electrode # (1-indexed)
    r'_'
    r'(?P<technique>[A-Za-z0-9\-]+?)'          # Technique (e.g., IV-DC)
    r'_'
    r'(?P<sweep_type>f|sp|sn|uc|p|n)'           # Sweep type code
    r'_'
    r'(?P<order>\d{1,3})'                      # Sequence number
    r'\.'
    r'(?P<ext>csv|txt|dat|tsv|log)'            # Extension
    r'$'
)


def parse_canonical_filename(filename: str) -> dict | None:
    """Parse a canonical crossbar filename.

    Format: DDMM_Material_b#-t#_Technique_Type_#.ext

    Returns dict or None if not matching.
    """
    m = CANONICAL_RE.search(filename)
    if not m:
        return None
    return {
        "date": m.group("date"),
        "material": m.group("material"),
        "row": int(m.group("top")) - 1,      # T → 0-indexed row
        "col": int(m.group("bottom")) - 1,    # B → 0-indexed col
        "technique": m.group("technique"),
        "sweep_type": m.group("sweep_type"),  # f, sp, sn, uc
        "order": int(m.group("order")),
        "ext": m.group("ext"),
        "technique_mapped": "",               # filled by infer_technique
    }


def _parse_filename_metadata(filename: str) -> dict:
    """Parse row, col, technique, sweep_type from filename convention.

    Tries grammar-based parsing first, falls back to hardcoded patterns.
    """
    meta = {
        "row": None,
        "col": None,
        "technique": "",
        "sweep_type": None,
        "sweep_order": None,
    }

    # Try grammar-based parsing first
    try:
        from science_cli.core.technique import parse_filename_grammar
        grammar_result = parse_filename_grammar(filename)
        if "parse_error" not in grammar_result:
            # Extract row/col from grammar result if available
            if "row" in grammar_result:
                try:
                    meta["row"] = int(grammar_result["row"])
                except (ValueError, TypeError):
                    pass
            if "col" in grammar_result:
                try:
                    meta["col"] = int(grammar_result["col"])
                except (ValueError, TypeError):
                    pass
            if "technique" in grammar_result:
                meta["technique"] = grammar_result["technique"]
            if "sweep_type" in grammar_result:
                meta["sweep_type"] = grammar_result["sweep_type"]
            if meta["row"] is not None or meta["col"] is not None or meta["technique"]:
                return meta
    except ImportError:
        pass

    # Fall back to hardcoded patterns
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
    from science_cli.memristor.device import DATA_SUFFIXES, YAML_EXCLUDE

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
    import re

    # Resolve rows/cols from --matrix shorthand or explicit --rows/--cols
    rows, cols = getattr(args, "rows", None), getattr(args, "cols", None)
    matrix_str = getattr(args, "matrix", "") or ""
    if matrix_str:
        m = re.match(r"r(\d+)[-.]c(\d+)", matrix_str)
        if m:
            rows, cols = int(m.group(1)), int(m.group(2))
        else:
            print(f"  Error: --matrix format should be rN-cN (e.g. r6-c6), got '{matrix_str}'")
            sys.exit(1)
    elif rows is None or cols is None:
        print("  Error: provide --matrix rN-cN or --rows N --cols N")
        sys.exit(1)

    label = getattr(args, "label", "") or ""
    if not label:
        label = f"{rows}x{cols} crossbar"

    pdir = _resolve_protocol_dir(args)
    yaml_path = pdir / "devices.yaml"
    if yaml_path.exists():
        print(f"devices.yaml already exists at {yaml_path}")
        sys.exit(1)

    from science_cli.core.technique import detect_technique
    tech_map = _build_tech_map()

    # Read protocol YAML to auto-resolve step → technique/device
    import yaml
    proto_yaml = pdir / f"{pdir.name}.yaml"
    proto_data = yaml.safe_load(open(proto_yaml)) if proto_yaml.exists() else {}
    step_meta = {s["name"]: s for s in proto_data.get("steps", [])}

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
                # Try protocol YAML metadata first
                meta = step_meta.get(part)
                if meta and meta.get("technique"):
                    steps[meta["technique"]] = part
                else:
                    ft = detect_technique(part)
                    tech = tech_map.get(ft, "")
                    if tech:
                        steps[tech] = part
                    else:
                        print(f"  Warning: could not infer technique from '{part}', skipping")

    config = DeviceConfig(
        device=DeviceGeometry(
            id=f"crossbar-{rows}x{cols}",
            label=label,
            rows=rows,
            cols=cols,
        ),
        points=[],
        steps=steps,
    )
    write_devices(pdir, config)
    print(f"Initialized {yaml_path}")
    print(f"  Device: {config.device.label} ({config.device.rows}x{config.device.cols})")
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


# ── Command: info ───────────────────────────────────────────


def cmd_info(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    pt = config.get_point(args.row, args.col)
    if pt is None:
        print(f"No data for r{args.row}c{args.col}")
        sys.exit(1)

    label = config.device.cell_label(args.row, args.col)
    tag_str = f" - tags: {', '.join(pt.tags)}" if pt.tags else ""
    print(f"Point r{args.row}c{args.col} ({label}){tag_str}")
    for tech_name, tg in pt.techniques.items():
        step_info = ""
        if config.steps.get(tech_name):
            step_info = f" [in {config.steps[tech_name]}/]"
        print(f"  {tech_name}:{step_info}")
        for i, fe in enumerate(tg.sorted_files()):
            parts = [f"[{i + 1}]"]
            if fe.sweep_type:
                parts.append(fe.sweep_type)
            parts.append(fe.file)
            if fe.sweep:
                s = fe.sweep[0]
                parts.append(
                    f"({s.get('direction', '?')}, "
                    f"{s.get('sweep_rate_v_s', '?')} V/s, "
                    f"{s.get('voltage_range', '?')} V)"
                )
            if fe.temperature is not None:
                parts.append(f"({fe.temperature} K)")
            print("    " + " ".join(parts))


# ── Command: add ────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)

    if args.fzf:
        cmd_add_fzf(args)
        return
    if args.pattern:
        cmd_add_pattern(args)
        return
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    technique = args.technique or _infer_technique(args.file)
    if not technique:
        print(
            "Cannot determine technique. "
            "Use --technique <name> to specify."
        )
        sys.exit(1)

    pt = config.get_point(args.row, args.col)
    if pt is None:
        pt = MatrixPoint(row=args.row, col=args.col)
        config.points.append(pt)
    if technique not in pt.techniques:
        pt.techniques[technique] = TechniqueGroup(technique=technique)
    fe = FileEntry(
        file=args.file,
        sweep_order=args.sweep_order,
        sweep_type=args.sweep_type,
        temperature=getattr(args, "temperature", None),
    )
    pt.techniques[technique].files.append(fe)
    _add_material_tag(pt, args.file)
    write_devices(pdir, config)
    print(f"Added {args.file} -> r{args.row}c{args.col}/{technique}")
    set_last_step(pdir.name)


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

    technique = args.technique or ""
    sweep_type = args.sweep_type or None
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

    tech = technique or _infer_technique(matches[0][0].name) or "iv"

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

    if not args.yes:
        try:
            ok = input("\nApply these assignments? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ok = ""
        if ok != "y":
            print("Cancelled.")
            return

    for f, r, c in matches:
        pt = config.get_point(r, c)
        if pt is None:
            pt = MatrixPoint(row=r, col=c)
            config.points.append(pt)
        if tech not in pt.techniques:
            pt.techniques[tech] = TechniqueGroup(technique=tech)
        fe = FileEntry(file=f.name, sweep_type=sweep_type)
        pt.techniques[tech].files.append(fe)
        _add_material_tag(pt, f.name)

    write_devices(pdir, config)
    print(f"Added {len(matches)} file(s) via pattern.")
    set_last_step(pdir.name)


def cmd_add_fzf(args: argparse.Namespace) -> None:
    """Interactive fzf file picker — scans all step subdirs recursively."""
    from science_cli.core.fzf_utils import fzf_select

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

    selected = fzf_select(
        items=display_names,
        prompt="Select data files to assign >",
        multi=True,
        preview="head -30 {}",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        print("No files selected.")
        return

    # Build a lookup from display name → (rel_path, step, path)
    lookup = {rel: (rel, step, path) for rel, step, path in unassigned}

    assignments = []
    for display in selected:
        rel_path, step_name, fpath = lookup[display]
        # Try canonical parser first, fall back to legacy parser
        canonical = parse_canonical_filename(fpath.name)
        if canonical:
            tech = canonical["technique_mapped"] or _infer_technique(fpath.name) or "iv"
            row = args.row if args.row is not None else canonical["row"]
            col = args.col if args.col is not None else canonical["col"]
            sweep_type = canonical["sweep_type"]
        else:
            meta = _parse_filename_metadata(fpath.name)
            tech = meta["technique"] or _infer_technique(fpath.name) or "iv"
            row = args.row if args.row is not None else (meta["row"] or 0)
            col = args.col if args.col is not None else (meta["col"] or 0)
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

    # Auto-sync sweep metadata if --sync flag was passed
    if getattr(args, "sync", False):
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
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    pt = config.get_point(args.row, args.col)
    if pt is None:
        print(f"No point at r{args.row}c{args.col}")
        sys.exit(1)

    technique = args.technique or (
        _infer_technique(args.file) if args.file else ""
    )

    if args.file:
        if not technique or technique not in pt.techniques:
            print(f"No technique '{technique}' at r{args.row}c{args.col}")
            sys.exit(1)
        tg = pt.techniques[technique]
        before = len(tg.files)
        tg.files = [f for f in tg.files if f.file != args.file]
        removed = before - len(tg.files)
        if removed == 0:
            print(f"File '{args.file}' not found in r{args.row}c{args.col}/{technique}")
            sys.exit(1)
        if not tg.files:
            del pt.techniques[technique]
    elif technique:
        if technique not in pt.techniques:
            print(f"No technique '{technique}' at r{args.row}c{args.col}")
            sys.exit(1)
        del pt.techniques[technique]
    else:
        if not args.confirm:
            print(f"Use --confirm to remove entire point r{args.row}c{args.col}")
            sys.exit(1)
        config.points = [
            p for p in config.points
            if not (p.row == args.row and p.col == args.col)
        ]

    write_devices(pdir, config)
    print(f"Removed from r{args.row}c{args.col}")
    set_last_step(pdir.name)


# ── Command: sync ───────────────────────────────────────────


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync: pure filename parsing — scan step dirs, parse filenames via grammar, populate SQLite.

    Does NOT read CSV content. Does NOT compute Vset/Vreset.
    Use 'memristor analyze' for CSV-based computation.
    """
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    from science_cli.core.project import get_current_project_path
    from science_cli.memristor.db import open_db, populate_protocol_from_step_dirs, close_db, rebuild_cells

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    protocol_name = pdir.name
    conn = open_db(proj)
    try:
        report = populate_protocol_from_step_dirs(
            conn,
            protocol=protocol_name,
            project_root=proj,
        )
        rebuild_cells(conn)
        conn.commit()

        print(f"Sync complete for protocol '{protocol_name}':")
        print(f"  Step dirs found: {report['steps_found']}")
        print(f"  Files found: {report['total_files']}")
        print(f"  Files matched (grammar): {report['total_matched']}")
        print(f"  Files inserted: {report['total_inserted']}")
        if report['errors']:
            print(f"  Errors ({len(report['errors'])}):")
            for err in report['errors'][:10]:  # Show first 10
                print(f"    - {err}")
            if len(report['errors']) > 10:
                print(f"    ... and {len(report['errors']) - 10} more")
        print(f"  SQLite cache updated: {proj.name}.db")
    except Exception as e:
        conn.rollback()
        print(f"  Sync failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        close_db(conn)

    set_last_step(pdir.name)


# ── SQLite sync helpers ─────────────────────────────────────


def _sqlite_sync_from_yaml(pdir: Path) -> None:
    """Write current devices.yaml contents into the SQLite cache."""
    from science_cli.core.project import get_current_project_path
    from science_cli.memristor.db import (
        open_db, insert_file, upsert_cells, upsert_protocol, close_db, rebuild_cells,
    )
    from science_cli.memristor.device import read_devices, extract_material_batch

    proj = get_current_project_path()
    if not proj:
        return

    config = read_devices(pdir)
    if not config:
        return

    conn = open_db(proj)
    protocol_name = pdir.name
    try:
        # Upsert protocol info
        upsert_protocol(
            conn, protocol_name,
            label=config.device.label,
            rows=config.device.rows,
            cols=config.device.cols,
            materials=json.dumps(
                sorted(set(
                    extract_material_batch(fe.file)[0] if extract_material_batch(fe.file) else "unknown"
                    for pt in config.points
                    for tg in pt.techniques.values()
                    for fe in tg.files
                ))
            ),
        )

        # For each point+file, insert into files table
        for pt in config.points:
            for tech_name, tg in pt.techniques.items():
                step_name = config.steps.get(tech_name, "")
                for fe in tg.files:
                    # Parse material from filename
                    mb = extract_material_batch(fe.file)
                    material = mb[0] if mb else "unknown"

                    # Extract row/col from point
                    row = pt.row
                    col = pt.col

                    # Extract plot filename from extra
                    plot_figure_path = fe.extra.get("plot", None)

                    # Determine mtime from filesystem
                    try:
                        fpath = config.resolve_file_path(pdir, tech_name, fe.file)
                        mtime_str = (
                            datetime.fromtimestamp(
                                fpath.stat().st_mtime, tz=timezone.utc
                            ).isoformat()
                        )
                        file_size = fpath.stat().st_size
                    except OSError:
                        mtime_str = ""
                        file_size = 0

                    insert_file(
                        conn,
                        protocol=protocol_name,
                        step=step_name,
                        filename=fe.file,
                        technique=tech_name,
                        material=material,
                        row=row,
                        col=col,
                        cycle_index=fe.sweep_order,
                        file_size=file_size,
                        mtime=mtime_str,
                        plot_figure_path=plot_figure_path,
                    )

        # Rebuild cells from files
        rebuild_cells(conn)
        conn.commit()
        print(f"  SQLite cache updated: {proj.name}.db")
    except Exception as e:
        conn.rollback()
        print(f"  SQLite cache write failed: {e}", file=sys.stderr)
    finally:
        close_db(conn)


def _sqlite_reindex(pdir: Path) -> None:
    """Reindex SQLite from YAML only (no CSV re-read).

    Reads devices.yaml and repopulates the SQLite database.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.memristor.db import (
        open_db, insert_file, upsert_cells, upsert_protocol, close_db, rebuild_cells,
    )
    from science_cli.memristor.device import read_devices, extract_material_batch

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    config = read_devices(pdir)
    if not config:
        print(f"No devices.yaml found in {pdir}")
        sys.exit(1)

    conn = open_db(proj)
    protocol_name = pdir.name
    try:
        # Upsert protocol info
        upsert_protocol(
            conn, protocol_name,
            label=config.device.label,
            rows=config.device.rows,
            cols=config.device.cols,
            materials=json.dumps(
                sorted(set(
                    extract_material_batch(fe.file)[0] if extract_material_batch(fe.file) else "unknown"
                    for pt in config.points
                    for tg in pt.techniques.values()
                    for fe in tg.files
                ))
            ),
        )

        # For each point+file, insert into files table
        for pt in config.points:
            for tech_name, tg in pt.techniques.items():
                step_name = config.steps.get(tech_name, "")
                for fe in tg.files:
                    mb = extract_material_batch(fe.file)
                    material = mb[0] if mb else "unknown"

                    plot_figure_path = fe.extra.get("plot", None)

                    try:
                        fpath = config.resolve_file_path(pdir, tech_name, fe.file)
                        mtime_str = (
                            datetime.fromtimestamp(
                                fpath.stat().st_mtime, tz=timezone.utc
                            ).isoformat()
                        )
                        file_size = fpath.stat().st_size
                    except OSError:
                        mtime_str = ""
                        file_size = 0

                    insert_file(
                        conn,
                        protocol=protocol_name,
                        step=step_name,
                        filename=fe.file,
                        technique=tech_name,
                        material=material,
                        row=pt.row,
                        col=pt.col,
                        cycle_index=fe.sweep_order,
                        file_size=file_size,
                        mtime=mtime_str,
                        plot_figure_path=plot_figure_path,
                    )

        rebuild_cells(conn)
        conn.commit()
        print(f"SQLite reindex complete: {proj.name}.db")
    except Exception as e:
        conn.rollback()
        print(f"SQLite reindex failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        close_db(conn)


# ── Command: analyze ────────────────────────────────────────


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze: read CSVs, compute Vset/Vreset/ratio/compliance, update SQLite.

    Depends on 'memristor sync' having populated the metadata.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.memristor.db import open_db, query_files, update_file_analysis, close_db
    from science_cli.memristor.plotting import read_iv_csv
    from science_cli.memristor.switching import extract_iv_parameters

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    protocol_name = pdir.name
    conn = open_db(proj)

    try:
        files = query_files(conn, protocol=protocol_name)

        # Filter to files with no parse_error
        target_files = [
            f for f in files
            if not f.get("parse_error")
        ]

        if not target_files:
            print("No parseable files found. Run 'memristor sync' first.")
            close_db(conn)
            return

        force = getattr(args, "force", False)
        single_file = getattr(args, "file", "") or ""

        analyzed = 0
        skipped = 0
        errors = 0

        print(f"Analyzing {len(target_files)} file(s) in protocol '{protocol_name}'...")

        for fentry in target_files:
            step = fentry["step"]
            filename = fentry["filename"]

            # Single-file filter
            if single_file and filename != single_file:
                skipped += 1
                continue

            # Skip if already analyzed (unless --force)
            if not force and fentry.get("v_set") is not None:
                skipped += 1
                continue

            # Resolve file path
            filepath = pdir / step / filename
            if not filepath.exists():
                print(f"  [SKIP] File not found: {filename}")
                skipped += 1
                continue

            try:
                voltage, current, info = read_iv_csv(str(filepath))
                params = extract_iv_parameters(voltage, current)
            except Exception as exc:
                print(f"  [ERR]  {filename}: {exc}")
                errors += 1
                continue

            update_file_analysis(
                conn,
                protocol=protocol_name,
                step=step,
                filename=filename,
                v_set=params.get("v_set"),
                v_reset=params.get("v_reset"),
                i_set=params.get("i_set"),
                i_reset=params.get("i_reset"),
                on_off_ratio=params.get("on_off_ratio"),
                current_compliance=params.get("compliance"),
                compliance_confidence="high" if params.get("switching_detected") else "low",
            )
            analyzed += 1

        conn.commit()

        print(f"\nAnalyze complete:")
        print(f"  Analyzed: {analyzed}")
        print(f"  Skipped:  {skipped}")
        print(f"  Errors:   {errors}")

    except Exception as e:
        conn.rollback()
        print(f"  Analyze failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        close_db(conn)

    set_last_step(pdir.name)


# ── Command: validate ───────────────────────────────────────


def cmd_validate(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)
    issues = validate_config(config, protocol_dir=pdir)
    if not issues:
        print("No issues found.")
    else:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


# ── Command: stats ──────────────────────────────────────────


def cmd_stats(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    total = config.device.total_cells
    print(f"Device: {config.device.id} ({config.device.label})")
    print(f"Geometry: {config.device.rows} rows x {config.device.cols} cols = {total} cells")
    print(f"Measured cells: {config.measured_cells}/{total} ({100 * config.measured_cells / total:.1f}%)")
    print("Technique coverage:")
    for tech, count in sorted(config.technique_coverage.items()):
        pct = 100 * count / total
        print(f"  {tech}: {count}/{total} ({pct:.1f}%)")
    print(f"Total data files: {config.total_files}")
    if config.steps:
        print(f"Steps mapping: {dict(config.steps)}")
    if config.missing_cells:
        missing_str = ", ".join(f"r{r}c{c}" for r, c in sorted(config.missing_cells))
        print(f"Missing cells: [{missing_str}]")

    # ── Per-material breakdown ────────────────────────────────
    material_groups = config.get_points_by_material()
    if material_groups:
        print("\nIV coverage by material:")
        for mat_key in sorted(material_groups.keys()):
            points = material_groups[mat_key]
            iv_points = [p for p in points if p.has_technique("iv")]
            sorted_iv = sorted(iv_points, key=lambda p: (p.row, p.col))
            positions_str = ", ".join(f"r{p.row}c{p.col}" for p in sorted_iv)
            print(f"  {mat_key}: {len(iv_points):3d} cell(s)  ({positions_str})")


# ── Command: check ──────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> None:
    """Find data files not tracked in devices.yaml (recursive scan)."""
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    orphans = find_orphaned_files(pdir)
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


# ── Command: plot ───────────────────────────────────────────


def cmd_plot(args: argparse.Namespace) -> None:
    """Batch-generate IV curve SVGs from devices.yaml."""
    from science_cli.memristor.plotting import (
        read_iv_csv,
        build_plot_filename,
        build_plot_title,
        generate_iv_svg,
        collect_iv_files,
        build_fzf_line,
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
        from science_cli.core.fzf_utils import fzf_select

        display_map: dict[str, dict] = {}
        display_lines: list[str] = []
        for t in targets:
            line = build_fzf_line(t)
            display_lines.append(line)
            display_map[line] = t

        selected_lines = fzf_select(
            items=display_lines,
            prompt="Select IV files to plot >",
            multi=True,
            preview="echo {}",
            preview_window="",
        )
        if not selected_lines:
            print("No files selected.")
            return

        # Map back to targets
        targets = [display_map[line] for line in selected_lines if line in display_map]

    # Resolve results directory
    step_dir_name = config.steps.get("iv", "4_iv-characterization")
    results_dir = pdir / step_dir_name / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    overwrite = getattr(args, "overwrite", False)
    dpi = getattr(args, "dpi", 150)

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
            voltage, current, info = read_iv_csv(str(filepath))
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
            generate_iv_svg(voltage, current, metadata, str(output_path), dpi=dpi)
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
    from science_cli.memristor.dashboard import generate_dashboard, generate_cross_protocol_dashboard

    if getattr(args, "all", False):
        # ── Cross-protocol mode ──
        from science_cli.core.project import get_current_project_path

        sess = load_session()
        last_proj = sess.get("last_project", "")
        if not last_proj:
            print("No project open. Use 'open -m project <path>' first.")
            sys.exit(1)

        project_dir = get_current_project_path()
        if not project_dir or not project_dir.exists():
            print(f"Project directory not found: {project_dir}")
            sys.exit(1)

        # Ensure results dir exists
        results_dir = project_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        output_path = Path(args.output) if args.output else results_dir / "dashboard.html"
        force = getattr(args, "force", False)

        try:
            out = generate_cross_protocol_dashboard(project_dir, output_path, force=force)
            print(f"Cross-protocol dashboard generated: {out}")
            if getattr(args, "open", False):
                import subprocess
                subprocess.run(["open", str(out)], check=False)
        except Exception as exc:
            print(f"Error generating cross-protocol dashboard: {exc}")
            sys.exit(1)
        return

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    # Resolve results directory: try the first step from mapping
    step_dir_name = "4_iv"
    for tech_key in ("iv-sweep", "iv"):
        if tech_key in config.steps:
            step_dir_name = config.steps[tech_key]
            break

    results_dir = pdir / step_dir_name / "results"

    if not results_dir.exists():
        results_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Created results directory: {results_dir}")

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = results_dir / "dashboard.html"

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

    p_init = sub.add_parser("init", help="Scaffold a devices.yaml")
    p_init.add_argument("--rows", type=int, default=None)
    p_init.add_argument("--cols", type=int, default=None)
    p_init.add_argument("--matrix", default="",
        help="Shorthand: --matrix r6-c6 (sets rows=6, cols=6)")
    p_init.add_argument("--label", default="")
    p_init.add_argument(
        "--steps", default="",
        help="Step dirs: 4_iv-characterization or iv:4_iv,endurance:5_end",
    )
    p_init.set_defaults(func=cmd_init)

    p_ls = sub.add_parser("ls", help="List devices or matrix map")
    p_ls.add_argument("--step-dir", default="")
    p_ls.add_argument("--matrix", action="store_true", help="Grid view (per-material when data tagged)")
    p_ls.add_argument("--technique", default="", help="Filter by technique (e.g., iv)")
    p_ls.add_argument("--material", default="", help="Filter by material+batch (e.g., Ta-PDAc-ITO(1))")
    p_ls.set_defaults(func=cmd_ls)

    p_info = sub.add_parser("info", help="Show point details")
    p_info.add_argument("--row", type=int, required=True)
    p_info.add_argument("--col", type=int, required=True)
    p_info.add_argument("--step-dir", default="")
    p_info.set_defaults(func=cmd_info)

    p_add = sub.add_parser("add", help="Add file(s) to a point")
    p_add.add_argument("--row", type=int, default=None)
    p_add.add_argument("--col", type=int, default=None)
    p_add.add_argument("--technique", default="", help="Technique (inferred from filename)")
    p_add.add_argument("--file", default="")
    p_add.add_argument("--sweep-order", type=int, default=None)
    p_add.add_argument("--sweep-type", default=None)
    p_add.add_argument("--temperature", type=float, default=None)
    p_add.add_argument("--step-dir", default="")
    p_add.add_argument("--fzf", action="store_true", help="Interactive fzf (recursive)")
    p_add.add_argument(
        "--pattern", default="",
        help="Regex for batch: r(\\d+)c(\\d+) groups 1=row, 2=col",
    )
    p_add.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_add.add_argument("--yes", action="store_true", help="Skip confirmation")
    p_add.add_argument("--sync", action="store_true", help="Auto-run sweep detection after assignment")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("rm", help="Remove file, technique, or point")
    p_rm.add_argument("--row", type=int, required=True)
    p_rm.add_argument("--col", type=int, required=True)
    p_rm.add_argument("--technique", default="", help="Technique (inferred from filename)")
    p_rm.add_argument("--file", default="")
    p_rm.add_argument("--confirm", action="store_true", help="Confirm entire point removal")
    p_rm.add_argument("--step-dir", default="")
    p_rm.set_defaults(func=cmd_rm)

    p_sync = sub.add_parser("sync", help="Sync sweep metadata")
    p_sync.add_argument("--step-dir", default="")
    p_sync.add_argument("--reindex", action="store_true", help="Reindex SQLite from YAML only (no CSV re-read)")
    p_sync.set_defaults(func=cmd_sync)

    p_val = sub.add_parser("validate", help="Validate device config")
    p_val.add_argument("--step-dir", default="")
    p_val.set_defaults(func=cmd_validate)

    p_stats = sub.add_parser("stats", help="Aggregate statistics")
    p_stats.add_argument("--step-dir", default="")
    p_stats.set_defaults(func=cmd_stats)

    p_check = sub.add_parser("check", help="Find unassigned files (recursive)")
    p_check.add_argument("--list", action="store_true", help="List unassigned files")
    p_check.add_argument("--step-dir", default="")
    p_check.set_defaults(func=cmd_check)

    p_plot = sub.add_parser("plot", help="Generate IV curve SVGs from devices.yaml")
    p_plot.add_argument("--step-dir", default="")
    p_plot.add_argument("--all", action="store_true", help="Plot all IV files (default if no filter)")
    p_plot.add_argument("--fzf", action="store_true", help="Interactive fzf multi-select picker")
    p_plot.add_argument("--material", default="", help="Plot files for a specific material+batch")
    p_plot.add_argument("--row", type=int, default=None, help="Filter by matrix row")
    p_plot.add_argument("--col", type=int, default=None, help="Filter by matrix column")
    p_plot.add_argument("--overwrite", action="store_true", help="Re-plot even if SVG already exists")
    p_plot.add_argument("--dpi", type=int, default=150, help="SVG resolution (default: 150)")
    p_plot.set_defaults(func=cmd_plot)

    p_dash = sub.add_parser("dashboard", help="Generate HTML viewer for plotted IV SVGs")
    p_dash.add_argument("--step-dir", default="")
    p_dash.add_argument("--output", default="", help="Custom output path (default: results/dashboard.html)")
    p_dash.add_argument("--open", action="store_true", help="Open in browser after generation")
    p_dash.add_argument("--all", action="store_true", help="Cross-protocol dashboard (project-level)")
    p_dash.add_argument("--force", action="store_true", help="Force full re-analysis, ignore cache")
    p_dash.set_defaults(func=cmd_dashboard)

    p_analyze = sub.add_parser("analyze", help="Read CSVs and compute Vset/Vreset/ratio (depends on sync)")
    p_analyze.add_argument("--step-dir", default="")
    p_analyze.add_argument("--force", action="store_true", help="Re-analyze all files (ignore cached analysis)")
    p_analyze.add_argument("--file", default="", help="Single-file re-analysis")
    p_analyze.set_defaults(func=cmd_analyze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
