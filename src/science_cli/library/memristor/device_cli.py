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
    mem-device plot --all [--overlay] [--material ...] [--row R --col C] [--dpi 150]

    # Interactive:
    mem-device plot [--fzf] [--overlay | --all] [--material ...] [--row R --col C] [--dpi 150]
    mem-device dashboard [--output path] [--open]
    
In the sci REPL, use 'memristor' instead of 'mem-device'.
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich import print as rprint
from rich.table import Table

from science_cli.core.session import (
    load_session,
    set_last_step,
)
from science_cli.library.memristor.device import (
    FileEntry,
    MatrixPoint,
    TechniqueGroup,
    extract_material_batch,
    find_orphaned_files,
    generate_rich_grid,
    read_devices,
    sync_devices,
    write_devices,
)
from science_cli.library.memristor.device import (
    validate as validate_config,
)

logger = logging.getLogger(__name__)


# ── Protocol directory resolution ───────────────────────────


def _resolve_file(pdir: Path, config, fe, step_ov: str | None, target: dict) -> Path:
    """Resolve file path with fallback when config or pdir is wrong."""
    if config is not None:
        filepath = config.resolve_file_path(pdir, "iv", fe.file, step_override=step_ov)
    else:
        filepath = (pdir / step_ov / fe.file) if step_ov else (pdir / fe.file)
    if not filepath.exists() and step_ov:
        from science_cli.core.project import get_current_project_path as _gpp
        _proj = _gpp()
        if _proj:
            _pdir = _proj / "protocol" / target.get("protocol", "")
            if _pdir.exists():
                filepath = _pdir / step_ov / fe.file
            else:
                for _pd in sorted(_proj.glob("protocol/*")):
                    _candidate = _pd / step_ov / fe.file
                    if _candidate.exists():
                        filepath = _candidate
                        break
    return filepath


def _resolve_protocol_dir(args) -> Path:
    """Resolve protocol directory: --step -> session -> cwd().

    If --step is a short name (e.g. ``4_iv``), search for a matching
    step directory under the session protocol and resolve to its parent.
    """
    step_name = getattr(args, "step", None)
    if step_name:
        # First: try as a step name under the session protocol
        sess = load_session()
        last_proj = sess.get("last_project", "")
        last_proto = sess.get("last_protocol", "")
        if last_proj and last_proto:
            from science_cli.core.project import get_current_project_path
            proj = get_current_project_path()
            if proj:
                proto_dir = proj / "protocol" / last_proto
                if proto_dir.exists():
                    for pdir in sorted(proto_dir.iterdir()):
                        if pdir.is_dir() and pdir.name == step_name:
                            # step_name IS the proto dir name — return it
                            return pdir.resolve()
                    # Search all protocol dirs for a step matching this name
                    for pdir in sorted(proto_dir.parent.iterdir()):
                        if pdir.is_dir() and (pdir / step_name).is_dir():
                            return pdir.resolve()
        # Second: treat as direct path
        return Path(step_name).resolve()

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
            # Search for matching protocol dir by name prefix
            for _pd in sorted(proj.glob("protocol/*")):
                if last_proto.replace("_", "").replace("-", "") in _pd.name.replace("_", "").replace("-", ""):
                    return _pd.resolve()

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
    from science_cli.library.memristor.device import DATA_SUFFIXES, YAML_EXCLUDE

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

    # ── NEW: Write to protocol YAML instead of devices.yaml ──
    protocol_yaml = pdir / f"{pdir.name}.yaml"

    # Check if protocol YAML exists
    if not protocol_yaml.exists():
        print(f"  Error: protocol YAML not found at {protocol_yaml}")
        print("  Create a protocol first with 'protocol create' or navigate to a protocol directory.")
        sys.exit(1)

    # Check if device section already exists
    from science_cli.core.protocol import has_device_section, write_device_section
    if has_device_section(protocol_yaml):
        print("  Protocol YAML already has a device section. Use --matrix to update.")

    # Build geometry dict
    geometry = {
        "rows": rows,
        "cols": cols,
        "label": label,
        "id": f"crossbar-{rows}x{cols}",
    }
    if not write_device_section(protocol_yaml, geometry):
        print(f"  Error: Failed to write device section to {protocol_yaml}")
        sys.exit(1)

    # Build steps mapping from protocol YAML (or --step arg)
    proto_data = {}
    try:
        import yaml
        with open(protocol_yaml) as f:
            proto_data = yaml.safe_load(f) or {}
    except Exception:
        pass

    step_techniques = {}
    for s in proto_data.get("steps", []):
        if isinstance(s, dict) and s.get("name") and s.get("technique"):
            step_techniques[s["name"]] = s["technique"]

    steps = {}
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
                # Look up technique from protocol YAML
                tech = step_techniques.get(part, "")
                if tech:
                    steps[tech] = part
                else:
                    # Try auto-detection
                    from science_cli.core.config import resolve_technique_from_grammar
                    from science_cli.core.technique import detect_technique
                    ft = detect_technique(part)
                    if ft:
                        tid = resolve_technique_from_grammar(ft)
                        if tid:
                            steps[tid] = part
                            continue
                    print(f"  Warning: could not infer technique from '{part}', skipping")

    print(f"Initialized device in {protocol_yaml}")
    print(f"  Device: {label} ({rows}x{cols})")
    print(f"  Cells: {rows * cols}")
    if steps:
        print(f"  Steps mapping: {steps}")

    # Optional: migrate legacy devices.yaml
    legacy_path = pdir / "devices.yaml"
    if legacy_path.exists():
        from science_cli.library.memristor.device import _migrate_devices_yaml
        report = _migrate_devices_yaml(pdir)
        if report.get("migrated"):
            print(f"  Migrated {report.get('files_migrated', 0)} file(s) from legacy devices.yaml")

    set_last_step(pdir.name)


# ── Command: ls ─────────────────────────────────────────────


def cmd_ls(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    if config is None:
        print(f"No device configuration found in {pdir}")
        print("  (Check for protocol YAML with device section or legacy devices.yaml)")
        sys.exit(1)

    material_filter = getattr(args, "material", "") or ""
    technique = args.technique or ""

    if args.matrix:
        from rich.console import Console

        # Load cell counts from SQLite
        proj = pdir.parent.parent
        cell_counts: dict[tuple[int, int], int] = {}
        try:
            from science_cli.library.memristor.db import get_db_path
            db_path = get_db_path(proj)
            if db_path.exists():
                import sqlite3
                with sqlite3.connect(db_path) as _conn:
                    rows = _conn.execute(
                        "SELECT row, col, n_files FROM cells WHERE protocol=?",
                        (pdir.name,),
                    ).fetchall()
                    for r, c, n in rows:
                        cell_counts[(r, c)] = n
        except Exception:
            pass

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
                    config, occupied=occupied, technique=technique, title=title,
                    cell_counts=cell_counts or None,
                )
            )
        elif not material_groups:
            # No material data — single grid (backward-compatible)
            console.print(generate_rich_grid(config, technique=technique, cell_counts=cell_counts or None))
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
                        cell_counts=cell_counts or None,
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


# ── Command: matrix ─────────────────────────────────────────


def _render_matrix_grid(
    protocol: str,
    material: str,
    cells: dict[tuple[int, int], int],
    technique: str = "",
    grid_rows: int | None = None,
    grid_cols: int | None = None,
) -> Table | None:
    """Render a Rich Table grid of file counts for one protocol+material from DB data.

    Args:
        protocol: Protocol name (for title).
        material: Material name (for title).
        cells: Dict of (row, col) -> file count.
        technique: Optional technique filter label.
        grid_rows: Fixed grid rows from protocol YAML (default: infer from data).
        grid_cols: Fixed grid columns from protocol YAML (default: infer from data).
    """
    if grid_rows is not None and grid_cols is not None:
        rows, cols = grid_rows, grid_cols
    elif cells:
        rows = max(r for r, _ in cells) + 1
        cols = max(c for _, c in cells) + 1
    else:
        return None

    title_parts = [protocol, material]
    if technique:
        title_parts.append(f"[{technique}]")
    title = " / ".join(title_parts)

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        show_lines=True,
        padding=(0, 1),
    )

    table.add_column("", style="bold bright_white", width=3)
    for j in range(cols):
        table.add_column(f"C{j + 1}", justify="right", width=5)

    for i in range(rows):
        row_data: list[str] = []
        for j in range(cols):
            n = cells.get((i, j), 0)
            if n > 0:
                row_data.append(f"[bold green]{n}[/]")
            else:
                row_data.append("[dim]----[/]")
        table.add_row(f"R{i + 1}", *row_data)

    return table


def _get_protocol_grid_dims(proj: Path, protocol_name: str) -> tuple[int | None, int | None]:
    """Read device grid dimensions from protocol YAML device section.

    Returns (rows, cols) or (None, None) if not defined.
    """
    yaml_path = proj / "protocol" / protocol_name / f"{protocol_name}.yaml"
    if not yaml_path.exists():
        return None, None
    try:
        import yaml
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        device = data.get("device", {})
        rows = device.get("rows")
        cols = device.get("cols")
        if rows is not None and cols is not None:
            return int(rows), int(cols)
    except Exception:
        pass
    return None, None


def cmd_matrix(args: argparse.Namespace) -> None:
    """Show device matrix from SQLite (no YAML required).

    Queries the ``files`` table for row/col coordinates parsed from filenames
    and renders a grid per protocol+material.

    Flags:
        --all: Show matrix for ALL protocols in the project.
        --material: Filter by exact material name.
        --technique: Filter by technique (e.g., ``iv-sweep``).
        --status: Show summary of what's loaded in the database.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.library.memristor.db import close_db, open_db

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    db_path = proj / f"{proj.name}.db"
    if not db_path.exists():
        print(f"No database found at {db_path}")
        print("Run 'memristor sync' first to populate the database.")
        return

    technique = getattr(args, "technique", "") or ""
    material = getattr(args, "material", "") or ""

    # ── --status mode: summary table ──
    if getattr(args, "status", False):
        conn = open_db(proj)
        try:
            rows = conn.execute(
                """SELECT protocol,
                          COUNT(DISTINCT material) AS n_materials,
                          COUNT(DISTINCT CASE WHEN row IS NOT NULL AND col IS NOT NULL
                            THEN CAST(row AS TEXT) || '-' || CAST(col AS TEXT) END) AS n_cells,
                          COUNT(*) AS n_files
                   FROM files
                   GROUP BY protocol
                   ORDER BY protocol"""
            ).fetchall()
            if not rows:
                print("No data in database.")
                return
            print(f"Database: {db_path.name}")
            print(f"{'Protocol':45s} {'Materials':>10s} {'Cells':>8s} {'Files':>8s}")
            print("-" * 75)
            for r in rows:
                print(f"{r[0]:45s} {r[1]:>10d} {r[2]:>8d} {r[3]:>8d}")
            print("-" * 75)
            total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            print(f"{'TOTAL':45s} {'':>10s} {'':>8s} {total:>8d}")
        finally:
            close_db(conn)
        return

    # ── Matrix mode ──

    # Determine which protocols to show
    all_flag = getattr(args, "all", False)
    if all_flag:
        conn = open_db(proj)
        try:
            proto_rows = conn.execute(
                "SELECT DISTINCT protocol FROM files ORDER BY protocol"
            ).fetchall()
            protocols = [r[0] for r in proto_rows]
        finally:
            close_db(conn)
        if not protocols:
            print("No protocols found in database.")
            print("Run 'memristor sync --all' first to populate the database.")
            return
    else:
        pdir = _resolve_protocol_dir(args)
        protocol_name = pdir.name

        # Check if this protocol has data in the DB
        conn_check = open_db(proj)
        try:
            has_data = conn_check.execute(
                "SELECT 1 FROM files WHERE protocol = ? LIMIT 1", (protocol_name,)
            ).fetchone()
        finally:
            close_db(conn_check)

        if not has_data:
            # Show available protocols from DB
            conn_check2 = open_db(proj)
            try:
                available = [
                    r[0] for r in conn_check2.execute(
                        "SELECT DISTINCT protocol FROM files ORDER BY protocol"
                    ).fetchall()
                ]
            finally:
                close_db(conn_check2)

            if available:
                print(f"Protocol '{protocol_name}' has no data in the database.")
                print(f"Available protocols: {', '.join(available)}")
                print("Use 'memristor matrix --all' or 'open -m protocol -n <name>'")
            else:
                print("No data in database. Run 'memristor sync' first.")
            return

        protocols = [protocol_name]

    conn = open_db(proj)
    try:
        first = True
        for protocol_name in protocols:
            # Query matrix data
            sql = """SELECT material, row, col, COUNT(*) AS n_files
                     FROM files
                     WHERE protocol = ?
                       AND row IS NOT NULL
                       AND col IS NOT NULL"""
            params: list = [protocol_name]
            if material:
                sql += " AND material = ?"
                params.append(material)
            if technique:
                sql += " AND technique_id = ?"
                params.append(technique)
            sql += " GROUP BY material, row, col ORDER BY material, row, col"

            qrows = conn.execute(sql, params).fetchall()
            if not qrows:
                continue

            # Group by material
            mat_cells: dict[str, dict[tuple[int, int], int]] = {}
            for qr in qrows:
                mat_name = qr[0]
                r, c = qr[1], qr[2]
                n = qr[3]
                mat_cells.setdefault(mat_name, {})[(r, c)] = n

            if not first:
                print()
            first = False

            g_rows, g_cols = _get_protocol_grid_dims(proj, protocol_name)

            # --grid override
            grid_str = getattr(args, "grid", "") or ""
            if grid_str:
                m = re.match(r"r(\d+)[-._]?c(\d+)", grid_str.strip(), re.IGNORECASE)
                if m:
                    g_rows, g_cols = int(m.group(1)), int(m.group(2))

            for mat_name in sorted(mat_cells.keys()):
                grid = _render_matrix_grid(
                    protocol_name, mat_name, mat_cells[mat_name], technique,
                    grid_rows=g_rows, grid_cols=g_cols,
                )
                if grid:
                    rprint(grid)
                    rprint()
    finally:
        close_db(conn)


# ── Command: info ───────────────────────────────────────────


def cmd_info(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    if config is None:
        print(f"No device configuration found in {pdir}")
        sys.exit(1)

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

    # ── Switching statistics from SQLite ──
    import numpy as np

    from science_cli.core.project import get_current_project_path
    from science_cli.library.memristor.db import close_db, open_db

    proj = get_current_project_path()
    if proj:
        conn = None
        try:
            conn = open_db(proj)
            db_rows = conn.execute(
                "SELECT filename, v_set, v_reset, i_set, i_reset, on_off_ratio, compliance_confidence "
                "FROM files WHERE protocol = ? AND row = ? AND col = ? AND technique_id = 'iv-sweep'",
                (pdir.name, args.row, args.col)
            ).fetchall()

            if db_rows:
                v_sets = [r["v_set"] for r in db_rows if r["v_set"] is not None]
                v_resets = [r["v_reset"] for r in db_rows if r["v_reset"] is not None]
                ratios = [r["on_off_ratio"] for r in db_rows if r["on_off_ratio"] is not None]

                print("\n  Switching Statistics (from SQLite):")
                print(f"    Total cycles: {len(db_rows)}")

                # Volatile memristors might have only SET or only RESET. We report yields distinctly.
                set_yield = (len(v_sets) / len(db_rows)) * 100.0 if db_rows else 0.0
                reset_yield = (len(v_resets) / len(db_rows)) * 100.0 if db_rows else 0.0

                print(f"    SET events detected:   {len(v_sets)}/{len(db_rows)} ({set_yield:.1f}% yield)")
                print(f"    RESET events detected: {len(v_resets)}/{len(db_rows)} ({reset_yield:.1f}% yield)")

                if v_sets:
                    print(f"    V_set   = {np.mean(v_sets):.3f} ± {np.std(v_sets):.3f} V (range: {np.min(v_sets):.2f} to {np.max(v_sets):.2f} V)")
                if v_resets:
                    print(f"    V_reset = {np.mean(v_resets):.3f} ± {np.std(v_resets):.3f} V (range: {np.min(v_resets):.2f} to {np.max(v_resets):.2f} V)")
                if ratios:
                    med_ratio = np.median(ratios)
                    print(f"    Median ON/OFF Ratio:   {med_ratio:.2e}")
        except Exception:
            # Silently skip if DB query fails or table is uninitialized
            pass
        finally:
            if conn:
                close_db(conn)



# ── Command: add ────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> None:
    pdir = _resolve_protocol_dir(args)

    device_type = getattr(args, "device_type", None)
    error_msg = getattr(args, "error", None)

    if not args.file and not args.pattern:
        if device_type or error_msg is not None:
            if args.row is None or args.col is None:
                print("Error: --row and --col are required to set cell device type.")
                sys.exit(1)

            from science_cli.core.project import get_current_project_path
            from science_cli.library.memristor.db import close_db, open_db, upsert_material
            proj = get_current_project_path()
            if not proj:
                print("No project open. Use 'open -m project <path>' first.")
                sys.exit(1)

            conn = open_db(proj)
            try:
                # Retrieve existing material if we can, else default
                cursor = conn.execute(
                    "SELECT material FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                    (pdir.name, args.row, args.col)
                )
                row_res = cursor.fetchone()
                existing_material = row_res[0] if row_res else "unknown"

                existing_type = "non-volatile"
                existing_errors = ""
                if row_res:
                    cursor2 = conn.execute(
                        "SELECT device_type, errors FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                        (pdir.name, args.row, args.col)
                    )
                    row2 = cursor2.fetchone()
                    if row2:
                        existing_type, existing_errors = row2[0], row2[1]

                final_type = device_type if device_type else existing_type
                final_errors = error_msg if error_msg is not None else existing_errors

                upsert_material(
                    conn,
                    protocol=pdir.name,
                    row=args.row,
                    col=args.col,
                    material=existing_material,
                    device_type=final_type,
                    errors=final_errors,
                )
                conn.commit()
                print(f"Manually set cell r{args.row}c{args.col} properties: type={final_type}, errors='{final_errors}'")
            finally:
                close_db(conn)
            return
        else:
            cmd_add_fzf(args)
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
        temperature=getattr(args, "temperature", None),
    )
    pt.techniques[technique].files.append(fe)
    _add_material_tag(pt, args.file)

    if device_type or error_msg is not None:
        from science_cli.core.project import get_current_project_path
        from science_cli.library.memristor.db import close_db, open_db, upsert_material
        from science_cli.library.memristor.device import extract_material_batch
        proj = get_current_project_path()
        if proj:
            conn = open_db(proj)
            try:
                mb = extract_material_batch(args.file)
                mat_key = f"{mb[0]}({mb[1]})" if mb and mb[1] else (mb[0] if mb else "unknown")

                cursor = conn.execute(
                    "SELECT material FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                    (pdir.name, args.row, args.col)
                )
                row_res = cursor.fetchone()
                existing_material = row_res[0] if row_res else mat_key

                existing_type = "non-volatile"
                existing_errors = ""
                if row_res:
                    cursor2 = conn.execute(
                        "SELECT device_type, errors FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                        (pdir.name, args.row, args.col)
                    )
                    row2 = cursor2.fetchone()
                    if row2:
                        existing_type, existing_errors = row2[0], row2[1]

                final_type = device_type if device_type else existing_type
                final_errors = error_msg if error_msg is not None else existing_errors

                upsert_material(
                    conn,
                    protocol=pdir.name,
                    row=args.row,
                    col=args.col,
                    material=existing_material,
                    device_type=final_type,
                    errors=final_errors,
                )
                conn.commit()
                print(f"Manually set cell r{args.row}c{args.col} properties: type={final_type}, errors='{final_errors}'")
            finally:
                close_db(conn)

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
        fe = FileEntry(file=f.name)
        pt.techniques[tech].files.append(fe)
        _add_material_tag(pt, f.name)

    write_devices(pdir, config)
    print(f"Added {len(matches)} file(s) via pattern.")
    set_last_step(pdir.name)


def cmd_add_fzf(args: argparse.Namespace) -> None:
    """Interactive fzf file picker — scans all step subdirs recursively."""
    from science_cli.core.fzf_utils import build_fzf_display, fzf_select

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

    proto_name = pdir.name
    display_names = [build_fzf_display(proto_name, step_name, rel, show_protocol=False) for rel, step_name, _ in unassigned]

    selected = fzf_select(
        items=display_names,
        prompt=f"{proto_name} | Select data files to assign >",
        multi=True,
    )
    if not selected:
        print("No files selected.")
        return

    # Build a lookup from display name → (rel_path, step, path)
    lookup = {}
    for rel, step, path in unassigned:
        display_key = build_fzf_display(proto_name, step, rel, show_protocol=False)
        lookup[display_key] = (rel, step, path)

    assignments = []
    for display in selected:
        rel_path, step_name, fpath = lookup[display]
        # Try canonical parser first, fall back to legacy parser
        canonical = parse_canonical_filename(fpath.name)
        if canonical:
            tech = canonical["technique_mapped"] or _infer_technique(fpath.name) or "iv"
            row = args.row if args.row is not None else canonical["row"]
            col = args.col if args.col is not None else canonical["col"]
        else:
            meta = _parse_filename_metadata(fpath.name)
            tech = meta["technique"] or _infer_technique(fpath.name) or "iv"
            row = args.row if args.row is not None else (meta["row"] or 0)
            col = args.col if args.col is not None else (meta["col"] or 0)
        assignments.append({
            "file": fpath.name,
            "row": row,
            "col": col,
            "technique": tech,
            "step_name": step_name,
            "fpath": fpath,
        })

    print("\nAssignments:")
    print(f"  {'File':30s} {'Row':4s} {'Col':4s} {'Technique':12s}")
    print("  " + "-" * 65)
    for a in assignments:
        print(f"  {a['file']:30s} {a['row']:4d} {a['col']:4d} {a['technique']:12s}")

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
        fe = FileEntry(file=a["file"])
        pt.techniques[a["technique"]].files.append(fe)
        _add_material_tag(pt, a["file"])

    write_devices(pdir, config)
    print(f"Added {len(assignments)} file(s).")

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


# ── Reconcile helper ────────────────────────────────────────


def _reconcile_protocol_yaml(pdir: Path) -> dict:
    """Reconcile protocol YAML step file lists with actual files on disk.

    Reads the protocol YAML (``<protocol>.yaml``), scans each step directory,
    and updates the YAML's ``steps[].files[]`` to match current disk contents.

    - Files in YAML but not on disk → removed from YAML
    - Files on disk but not in YAML → appended as plain strings (no sweep metadata)
    - Sweep metadata for removed files is discarded (identity may have changed)

    Returns dict with keys: steps_found, added, removed, errors
    """
    import yaml

    proto_yaml_path = pdir / f"{pdir.name}.yaml"
    if not proto_yaml_path.exists():
        return {"steps_found": 0, "added": 0, "removed": 0, "errors": ["protocol YAML not found"]}

    with open(proto_yaml_path) as f:
        proto_data = yaml.safe_load(f) or {}

    from science_cli.library.memristor.db import DATA_SUFFIXES

    total_added = 0
    total_removed = 0
    errors: list[str] = []

    for step in proto_data.get("steps", []):
        step_name = step.get("name", "")
        if not step_name:
            continue

        step_dir = pdir / step_name
        disk_files: set[str] = set()
        if step_dir.is_dir():
            for entry in step_dir.iterdir():
                if not entry.is_file():
                    continue
                if entry.name.startswith("."):
                    continue
                if entry.suffix.lower() not in DATA_SUFFIXES:
                    continue
                disk_files.add(entry.name)

        # Extract filenames from YAML entries (dict → "file" key, or plain string)
        yaml_entries = step.get("files", [])
        yaml_names: dict[str, str | dict] = {}
        for entry in yaml_entries:
            if isinstance(entry, dict):
                fname = entry.get("file", "")
                if fname:
                    yaml_names[fname] = entry
            elif isinstance(entry, str):
                yaml_names[entry] = entry

        yaml_files = set(yaml_names.keys())

        to_remove = yaml_files - disk_files
        to_add = disk_files - yaml_files

        if not to_remove and not to_add:
            continue

        total_removed += len(to_remove)
        total_added += len(to_add)

        # Build new files list: keep existing entries, remove stale, add new
        new_files: list = []
        for entry in yaml_entries:
            fname = entry["file"] if isinstance(entry, dict) else entry
            if fname not in to_remove:
                new_files.append(entry)

        for fname in sorted(to_add):
            new_files.append(fname)

        step["files"] = new_files

    if total_added > 0 or total_removed > 0:
        with open(proto_yaml_path, "w") as f:
            yaml.dump(proto_data, f, default_flow_style=False, sort_keys=False)

    return {
        "steps_found": len(proto_data.get("steps", [])),
        "added": total_added,
        "removed": total_removed,
        "errors": errors,
    }


# ── Command: sync ───────────────────────────────────────────


def _sync_one_protocol(
    conn: sqlite3.Connection,
    proj: Path,
    protocol_name: str,
    pdir: Path,
    reconcile: bool,
    force: bool = False,
) -> dict:
    """Sync a single protocol: populate SQLite, prune, sweep-to-yaml.

    Returns the reconcile report (or empty dict if no reconcile).
    Side effects: prints per-protocol output.
    """
    from science_cli.library.memristor.db import (
        DATA_SUFFIXES,
        MEMRISTOR_TECHNIQUES,
        populate_protocol_from_step_dirs,
        prune_stale_files,
    )

    # ── Phase 1: Reconcile protocol YAML (if --reconcile) ──
    reconcile_report = None
    if reconcile:
        reconcile_report = _reconcile_protocol_yaml(pdir)
        if reconcile_report["errors"]:
            for err in reconcile_report["errors"]:
                print(f"  [YAML] {err}")

    # ── Phase 2: Force reset (if --force) ──
    if force:
        deleted = conn.execute(
            "DELETE FROM files WHERE protocol = ?", (protocol_name,)
        ).rowcount
        print(f"  Force: cleared {deleted} stale file(s)")

    # ── Phase 3: Populate SQLite from grammar (disk scan) ──
    report = populate_protocol_from_step_dirs(
        conn, protocol=protocol_name, project_root=proj,
    )

    # ── Phase 4: Prune stale DB entries (if --reconcile) ──
    pruned_total = 0
    if reconcile_report:
        step_techniques: dict[str, str] = {}
        try:
            import yaml as _yaml
            yaml_path = pdir / f"{protocol_name}.yaml"
            if yaml_path.is_file():
                with open(yaml_path) as _f:
                    _data = _yaml.safe_load(_f)
                for _s in (_data.get("steps") or []):
                    if isinstance(_s, dict):
                        step_techniques[_s.get("name", "")] = _s.get("technique", "")
        except Exception:
            pass

        for step_name in sorted(
            d.name for d in pdir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ):
            technique = step_techniques.get(step_name, "")
            if technique and technique not in MEMRISTOR_TECHNIQUES:
                continue
            step_dir = pdir / step_name
            disk_files = set()
            if step_dir.is_dir():
                for entry in step_dir.iterdir():
                    if not entry.is_file():
                        continue
                    if entry.name.startswith("."):
                        continue
                    if entry.suffix.lower() not in DATA_SUFFIXES:
                        continue
                    disk_files.add(entry.name)
            pruned_total += prune_stale_files(conn, protocol_name, step_name, disk_files)

    # ── Phase 5: Sync sweep metadata back to protocol YAML ──
    from science_cli.library.memristor.device import sync_sweep_to_protocol_yaml
    sweep_report = sync_sweep_to_protocol_yaml(pdir, conn)
    if sweep_report.get("files_updated", 0) > 0:
        print(f"  Sweep metadata synced: {sweep_report['files_updated']} file(s)")

    # ── Report ──
    if reconcile_report:
        print(f"  Reconcile: {reconcile_report['steps_found']} steps, "
              f"{reconcile_report['added']} added, "
              f"{reconcile_report['removed']} removed, "
              f"{pruned_total} pruned")

    print(f"  Steps: {report['steps_found']} | Files: {report['total_files']} | "
          f"Matched: {report['total_matched']} | Inserted: {report['total_inserted']}")
    if report['errors']:
        for err in report['errors'][:5]:
            print(f"    - {err}")

    return reconcile_report or {}


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync: pure filename parsing — scan step dirs, parse filenames via grammar, populate SQLite.

    Does NOT read CSV content. Does NOT compute Vset/Vreset.
    Use 'memristor analyze' for CSV-based computation.

    With ``--reconcile`` / ``-r``: also reconcile the protocol YAML's
    file list with actual files on disk, then prune stale SQLite entries.

    With ``--all`` / ``-A``: sync ALL protocols in the current project.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.library.memristor.db import close_db, open_db, rebuild_cells

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    reconcile = getattr(args, "reconcile", False)
    force = getattr(args, "force", False)

    # ── --all mode: iterate every protocol in the project ──
    if getattr(args, "all", False):
        from science_cli.core.paths import ProjectPaths
        ppaths = ProjectPaths(proj)
        protocols = ppaths.protocol_names()
        if not protocols:
            print("No protocols found in project.")
            return

        conn = open_db(proj)
        try:
            for protocol_name in protocols:
                pdir = proj / "protocol" / protocol_name
                if not pdir.exists():
                    print(f"  Skipping '{protocol_name}' — directory not found.")
                    continue
                print(f"\n── Syncing '{protocol_name}' ──")
                _sync_one_protocol(conn, proj, protocol_name, pdir, reconcile,
                                   force=force)

            rebuild_cells(conn)
            conn.commit()
            print(f"\nAll protocols synced to {proj.name}.db")
        except Exception as e:
            conn.rollback()
            print(f"  Sync (--all) failed: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            close_db(conn)
        return

    # ── Single-protocol mode (default) ──
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    protocol_name = pdir.name

    conn = open_db(proj)
    try:
        _sync_one_protocol(conn, proj, protocol_name, pdir, reconcile,
                           force=force)
        rebuild_cells(conn)
        conn.commit()
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
    from science_cli.library.memristor.db import (
        close_db,
        insert_file,
        open_db,
        rebuild_cells,
        upsert_protocol,
    )
    from science_cli.library.memristor.device import extract_material_batch, read_devices

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
    from science_cli.library.memristor.db import (
        close_db,
        insert_file,
        open_db,
        rebuild_cells,
        upsert_protocol,
    )
    from science_cli.library.memristor.device import extract_material_batch, read_devices

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    config = read_devices(pdir)
    if not config:
        print(f"No device configuration found in {pdir}")
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


def _analyze_protocol(
    conn: sqlite3.Connection,
    proj: Path,
    protocol_name: str,
    step_filter: str = "",
    force: bool = False,
    single_file: str = "",
) -> dict:
    """Analyze all files in one protocol: read CSV, extract IV params, update DB.

    Returns dict with: protocol, total, analyzed, skipped, errors.
    """
    from science_cli.library.memristor.db import query_files, update_file_analysis
    from science_cli.library.memristor.plotting import read_iv_csv
    from science_cli.library.memristor.switching import extract_iv_parameters

    pdir = proj / "protocol" / protocol_name
    if not pdir.exists():
        return {"protocol": protocol_name, "total": 0, "analyzed": 0, "skipped": 0, "errors": 0,
                "message": "directory not found"}

    files = query_files(conn, protocol=protocol_name)
    target_files = [f for f in files if not f.get("parse_error")]

    if not target_files:
        return {"protocol": protocol_name, "total": 0, "analyzed": 0, "skipped": 0, "errors": 0,
                "message": "no parseable files"}

    analyzed = 0
    skipped = 0
    errors = 0

    for fentry in target_files:
        step = fentry["step"]
        filename = fentry["filename"]

        # Step filter
        if step_filter and step != step_filter:
            skipped += 1
            continue

        # Single-file filter
        if single_file and filename != single_file:
            skipped += 1
            continue

        # Skip if already analyzed (unless --force)
        # compliance_confidence is always set after analysis, even when
        # no switching is detected (v_set remains NULL).
        if not force and fentry.get("compliance_confidence") is not None:
            skipped += 1
            continue

        # Resolve file path
        filepath = pdir / step / filename
        if not filepath.exists():
            skipped += 1
            continue

        try:
            voltage, current, info = read_iv_csv(str(filepath))
            params = extract_iv_parameters(voltage, current)
        except Exception as exc:
            print(f"  [ERR]  {protocol_name}/{step}/{filename}: {exc}")
            # Mark as failed so it won't be retried
            update_file_analysis(
                conn,
                protocol=protocol_name,
                step=step,
                filename=filename,
                compliance_confidence="error",
            )
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
            v_set_idx=params.get("v_set_idx"),
            v_reset_idx=params.get("v_reset_idx"),
            on_off_ratio=params.get("on_off_ratio"),
            current_compliance=params.get("compliance"),
            compliance_confidence="high" if params.get("switching_detected") else "low",
        )
        analyzed += 1

    try:
        from science_cli.library.memristor.db import classify_and_populate_materials
        classify_and_populate_materials(conn, protocol_name)
    except Exception as exc:
        print(f"  [WARN] Device classification failed for {protocol_name}: {exc}")

    return {
        "protocol": protocol_name,
        "total": len(target_files),
        "analyzed": analyzed,
        "skipped": skipped,
        "errors": errors,
    }


def expand_material_cluster(pattern: str) -> list[str]:
    """Expand bracketed clusters like 'cu-c-pda(q,q2,q3)-ito' to separate material strings.
    
    E.g. 'cu-c-pda(q,q2,q3)-ito' -> ['cu-c-pda(q)-ito', 'cu-c-pda(q2)-ito', 'cu-c-pda(q3)-ito']
    """
    import re
    match = re.search(r'\(([^)]+)\)', pattern)
    if not match:
        return [pattern]
    inner = match.group(1)
    items = [item.strip() for item in inner.split(',') if item.strip()]
    start_idx, end_idx = match.span()
    prefix = pattern[:start_idx]
    suffix = pattern[end_idx:]
    return [f"{prefix}({item}){suffix}" for item in items]


def update_yaml_device_overrides(pdir: Path, mat_overrides: dict = None, cell_overrides: dict = None) -> None:
    """Merge and write material/cell overrides into the protocol YAML file."""
    yaml_path = pdir / f"{pdir.name}.yaml"
    if not yaml_path.exists():
        print(f"  [WARN] Protocol YAML not found at {yaml_path}, cannot save overrides persistently.")
        return
    import yaml
    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        data = {}
    overrides = data.setdefault("device_overrides", {})
    mat_section = overrides.setdefault("materials", {})
    cell_section = overrides.setdefault("cells", {})
    if mat_overrides:
        for mat, dev_type in mat_overrides.items():
            mat_section[mat] = dev_type
    if cell_overrides:
        for cell, dev_type in cell_overrides.items():
            cell_section[cell] = dev_type
    try:
        with open(yaml_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        print(f"  [INFO] Persistent overrides written to {yaml_path.name}")
    except Exception as e:
        print(f"  [WARN] Failed to write persistent overrides to protocol YAML: {e}")


def cmd_analyze(args: list) -> None:
    """Analyze: read CSVs, compute Vset/Vreset/ratio/compliance, update SQLite.

    Depends on 'memristor sync' having populated the metadata.

    Modes:
        --all: analyze ALL protocols in the database.
        --pt <name>: analyze a specific protocol by name.
        (default): analyze the current session protocol.
        --step <name>: filter to a specific step within the protocol(s).
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.library.memristor.db import close_db, open_db

    proj = get_current_project_path()
    if not proj:
        print("No project open. Use 'open -m project <path>' first.")
        sys.exit(1)

    # ── Override Processing (Tier B writing to Tier A) ──
    override_mat = getattr(args, "mat", "") or ""
    override_cell = getattr(args, "cell", "") or ""
    override_type = getattr(args, "type", "") or ""
    extra_args = getattr(args, "extra_args", []) or []

    # Support natural language format: --mat cu-c-pda(q,q2,q3)-ito is volatile
    if not override_type and len(extra_args) >= 2 and extra_args[0].lower() == "is":
        override_type = extra_args[1].lower()

    if (override_mat or override_cell) and not override_type:
        print("  Error: Please specify the classification type (e.g., 'is volatile' or '--type volatile')")
        sys.exit(1)

    if override_type and override_type not in ("volatile", "non-volatile", "short", "insulating", "resistor"):
        print(f"  Error: Invalid type '{override_type}'. Valid types: volatile, non-volatile, short, insulating, resistor")
        sys.exit(1)

    if (override_mat or override_cell):
        # Resolve target protocol directory
        if getattr(args, "all", False):
            print("  Error: Overrides cannot be run with --all. Specify a single protocol.")
            sys.exit(1)
        elif getattr(args, "protocol", "") or getattr(args, "pt", ""):
            protocol_name = getattr(args, "protocol", "") or getattr(args, "pt", "")
            pdir = proj / "protocol" / protocol_name
        else:
            pdir = _resolve_protocol_dir(args)
            
        if pdir and pdir.exists():
            mat_overrides = {}
            cell_overrides = {}
            if override_mat:
                expanded = expand_material_cluster(override_mat)
                for mat in expanded:
                    mat_overrides[mat] = override_type
                    print(f"  [INFO] Designating material '{mat}' as {override_type}")
            if override_cell:
                cell_overrides[override_cell] = override_type
                print(f"  [INFO] Designating cell '{override_cell}' as {override_type}")
                
            update_yaml_device_overrides(pdir, mat_overrides, cell_overrides)
        else:
            print("  Error: Could not resolve protocol directory for overrides.")
            sys.exit(1)

    force = getattr(args, "force", False)
    single_file = getattr(args, "file", "") or ""
    step_filter = getattr(args, "step", "") or ""

    conn = open_db(proj)

    try:
        # ── --all mode: analyze all protocols in DB ──
        if getattr(args, "all", False):
            protocol_rows = conn.execute(
                "SELECT DISTINCT protocol FROM files ORDER BY protocol"
            ).fetchall()
            if not protocol_rows:
                print("No protocols found in database. Run 'memristor sync --all' first.")
                close_db(conn)
                return

            protocols = [r[0] for r in protocol_rows]
            results: list[dict] = []
            for pt in protocols:
                print(f"\n── Analyzing '{pt}' ──")
                r = _analyze_protocol(conn, proj, pt, step_filter, force, single_file)
                results.append(r)

            conn.commit()
            print("\n── Analyze (--all) complete ──")
            total_a = sum(r["analyzed"] for r in results)
            total_s = sum(r["skipped"] for r in results)
            total_e = sum(r["errors"] for r in results)
            for r in results:
                msg = f"  {r['protocol']}: {r['analyzed']} analyzed, {r['skipped']} skipped"
                if r.get("message"):
                    msg += f" ({r['message']})"
                print(msg)
            print(f"  TOTAL: {total_a} analyzed, {total_s} skipped, {total_e} errors")

        # ── --pt mode: analyze a named protocol ──
        elif getattr(args, "protocol", "") or getattr(args, "pt", ""):
            protocol_name = getattr(args, "protocol", "") or getattr(args, "pt", "")
            pdir = proj / "protocol" / protocol_name
            if not pdir.exists():
                print(f"Protocol directory not found: {pdir}")
                sys.exit(1)
            print(f"\n── Analyzing '{protocol_name}' ──")
            r = _analyze_protocol(conn, proj, protocol_name, step_filter, force, single_file)
            conn.commit()
            print(f"  {r['protocol']}: {r['analyzed']} analyzed, {r['skipped']} skipped, {r['errors']} errors")

        # ── Default: session protocol ──
        else:
            pdir = _resolve_protocol_dir(args)
            if not _validate_protocol_dir(pdir):
                sys.exit(1)
            protocol_name = pdir.name
            print(f"\n── Analyzing '{protocol_name}' ──")
            r = _analyze_protocol(conn, proj, protocol_name, step_filter, force, single_file)
            conn.commit()
            print(f"  {r['protocol']}: {r['analyzed']} analyzed, {r['skipped']} skipped, {r['errors']} errors")
            set_last_step(pdir.name)

    except Exception as e:
        conn.rollback()
        print(f"  Analyze failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        close_db(conn)


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

    if config is None:
        print(f"No device configuration found in {pdir}")
        sys.exit(1)

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
    """Find data files not tracked in device configuration (recursive scan)."""
    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)

    orphans = find_orphaned_files(pdir)
    if not orphans:
        print("All files are assigned in device configuration.")
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


def parse_cycles_list(cycle_str: str) -> list[int]:
    """Parse a string like '1,2,5,10-15,50' into a list of 1-based cycle indices."""
    if not cycle_str:
        return []
    cycles = set()
    for part in cycle_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start, end = part.split("-")
                cycles.update(range(int(start), int(end) + 1))
            except ValueError:
                pass
        else:
            try:
                cycles.add(int(part))
            except ValueError:
                pass
    return sorted(list(cycles))


# ── Command: plot ───────────────────────────────────────────


def cmd_plot(args: argparse.Namespace) -> None:

    """Batch-generate IV curve SVGs from devices.yaml."""
    from science_cli.library.memristor.plotting import (
        build_fzf_line,
        build_plot_filename,
        build_plot_title,
        collect_iv_files,
        generate_iv_overlay_svg,
        generate_iv_svg,
        read_iv_csv,
    )

    raw_current = getattr(args, "raw", False)

    pdir = _resolve_protocol_dir(args)
    if not _validate_protocol_dir(pdir):
        sys.exit(1)
    config = read_devices(pdir)

    row_filter = args.row if getattr(args, "row", None) is not None else None
    col_filter = args.col if getattr(args, "col", None) is not None else None
    material_filter = getattr(args, "material", "") or ""

    # ── Collect targets from devices.yaml (if it exists) ──
    targets: list[dict] = []
    if config is not None:
        total_sweep = sum(1 for _, fe in config.get_all_files("iv") if fe.sweep)
        if total_sweep == 0:
            print("No sweep metadata found. Running sync first...")
            sync_devices(pdir)
            config = read_devices(pdir)

        if config is not None:
            targets = collect_iv_files(config, material=material_filter, row=row_filter, col=col_filter)

    if not targets:
        # ── SQLite fallback: query files table directly ──
        from science_cli.core.project import get_current_project_path
        from science_cli.library.memristor.db import close_db, open_db
        from science_cli.core.session import load_session

        proj = get_current_project_path()
        if proj:
            sess = load_session()
            proto_name = sess.get("last_protocol", pdir.name)
            db_path = proj / f"{proj.name}.db"
            if db_path.exists():
                conn = open_db(proj)
                try:
                    # Query ALL iv files (no protocol filter) then pick best protocol
                    all_rows = conn.execute(
                        """SELECT protocol, step, filename, material, row, col
                           FROM files
                           WHERE technique_id LIKE 'iv%'
                             AND row IS NOT NULL AND col IS NOT NULL
                           ORDER BY protocol, row, col, filename""",
                    ).fetchall()
                finally:
                    close_db(conn)

                if all_rows:
                    # Group rows by protocol, prefer protocol with existing dir
                    from collections import defaultdict
                    by_proto: dict[str, list] = defaultdict(list)
                    for r in all_rows:
                        by_proto[r["protocol"]].append(r)

                    # Score protocols: existing dir first, then match material filter
                    def proto_score(pname: str) -> tuple:
                        dir_exists = (proj / "protocol" / pname).exists()
                        has_material = any(
                            r["material"] == material_filter
                            for r in by_proto[pname]
                        ) if material_filter else False
                        # Sort by dir_exists (desc), has_material (desc), then name
                        return (not dir_exists, not has_material, pname)

                    chosen_proto = min(by_proto, key=proto_score)

                    # If chosen protocol dir doesn't exist, fuzzy search
                    if not (proj / "protocol" / chosen_proto).exists():
                        for pd in sorted(proj.glob("protocol/*")):
                            for pname in by_proto:
                                if pname.replace("_", "").replace("-", "") in pd.name.replace("_", "").replace("-", "").replace(".", ""):
                                    # Re-check this dir has matching rows
                                    candidate_proto = by_proto[pname]
                                    if material_filter:
                                        candidate_proto = [r for r in candidate_proto if r["material"] == material_filter]
                                    if candidate_proto:
                                        chosen_proto = pd.name
                                        break
                            if chosen_proto and (proj / "protocol" / chosen_proto).exists():
                                break

                    db_files = by_proto.get(chosen_proto, [])
                    if db_files:
                        print(f"  Found {len(db_files)} file(s) in SQLite ({chosen_proto}). Using them for plotting.")
                        actual_pdir = proj / "protocol" / chosen_proto
                        if actual_pdir.exists():
                            pdir = actual_pdir.resolve()
                            config = read_devices(pdir)
                        else:
                            # Fuzzy search for existing directory
                            for pd in sorted(proj.glob("protocol/*")):
                                if chosen_proto.replace("_", "").replace("-", "") in pd.name.replace("_", "").replace("-", "").replace(".", ""):
                                    pdir = pd.resolve()
                                    config = read_devices(pdir)
                                    break
                    for r in db_files:
                        step = r["step"]
                        filename = r["filename"]
                        material = r["material"]
                        db_row, db_col = r["row"], r["col"]

                        mat_key = material
                        if material_filter and mat_key != material_filter:
                            continue
                        if row_filter is not None and db_row != row_filter:
                            continue
                        if col_filter is not None and db_col != col_filter:
                            continue

                        targets.append({
                            "file_entry": FileEntry(file=filename),
                            "material_key": mat_key,
                            "order": len(targets) + 1,
                            "sweep_type": "uc",
                            "row": db_row,
                            "col": db_col,
                            "step": step,
                            "protocol": r["protocol"],
                        })

    if not targets:
        print("No IV files found in devices.yaml or SQLite database.")
        return

    # Default to fzf when no specific filter flags given
    use_fzf = not material_filter and row_filter is None and col_filter is None
    
    # Parse CLI extra/remaining arguments
    from science_cli.cli.commands.plot import _parse_flags as plot_parse
    _, extra_flags = plot_parse(getattr(args, "extra_args", []))
    all_flags = {}
    all_flags.update(extra_flags)

    if use_fzf:
        from science_cli.core.fzf_utils import fzf_select

        display_map: dict[str, dict] = {}
        display_lines: list[str] = []
        for t in targets:
            line = build_fzf_line(t, protocol=pdir.name)
            display_lines.append(line)
            display_map[line] = t

        selected_lines = fzf_select(
            items=display_lines,
            prompt=f"{pdir.name} | Select IV files to plot >",
            multi=True,
        )
        if not selected_lines:
            print("No files selected.")
            return

        # Map back to targets
        targets = [display_map[line] for line in selected_lines if line in display_map]

        if targets:
            from science_cli.cli.commands.plot import _technique_hints
            from rich import print as rprint
            rprint(f"\n[bold]Selected {len(targets)} file(s) for memristor plotting.[/bold]")

            # Prompt 1: Style / analysis flags
            style_hint = _technique_hints("iv-sweep").get(
                "plot_style",
                "--type line|scatter | --color | --linewidth | --linestyle | --marker | --markersize",
            )
            rprint(f"  [dim]# {style_hint}[/dim]")
            raw_style = input("  Style / analysis options (Enter to skip — uses theme defaults): ").strip()
            if raw_style:
                _, style_flags = plot_parse(raw_style.split())
                all_flags.update(style_flags)

            # Prompt 2: Figure / output flags
            fig_hint = _technique_hints("iv-sweep").get(
                "figure",
                "-n name.pdf|png|svg | --label-name n1,n2,... | --title | --xlabel | --ylabel | --xlim | --ylim | --zoom x1,x2,y1,y2 | --size | --dpi | --grid | --legend",
            )
            rprint(f"  [dim]# {fig_hint}[/dim]")
            raw_figure = input("  Figure options (Enter to skip — uses theme defaults): ").strip()
            if raw_figure:
                _, figure_flags = plot_parse(raw_figure.split())
                all_flags.update(figure_flags)

    # Resolve results directory
    if targets and "step" in targets[0] and targets[0]["step"]:
        step_dir_name = targets[0]["step"]
    else:
        step_dir_name = config.steps.get("iv") or config.steps.get("iv-sweep") or "4_iv" if config else "4_iv"
    results_dir = pdir / step_dir_name / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    dpi = getattr(args, "dpi", 150)

    # ── Multi-Cycle Highlight Plot Mode ──
    highlight_str = getattr(args, "highlight", "") or ""
    if highlight_str:
        from science_cli.library.memristor.plotting import generate_iv_highlighted_svg
        highlight_cycles = parse_cycles_list(highlight_str)
        if not highlight_cycles:
            print("Invalid highlight cycles specified.")
            return

        unique_cells = sorted(list(set((t["row"], t["col"], t["material_key"]) for t in targets)))
        if not unique_cells:
            print("No cells found for plotting.")
            return

        if len(unique_cells) > 1:
            from science_cli.core.fzf_utils import fzf_select
            cell_displays = [f"r{row}c{col} ({mat})" for row, col, mat in unique_cells]
            selected = fzf_select(cell_displays, prompt="Select cell for multi-cycle highlighted plot >", multi=False)
            if not selected:
                print("No cell selected.")
                return
            selected_display = selected[0]
            # Parse back
            selected_cell = None
            for r, c, m in unique_cells:
                if f"r{r}c{c} ({m})" == selected_display:
                    selected_cell = (r, c, m)
                    break
            if not selected_cell:
                return
            r_val, c_val, m_val = selected_cell
        else:
            r_val, c_val, m_val = unique_cells[0]

        # Filter targets to the selected cell
        cell_targets = [t for t in targets if t["row"] == r_val and t["col"] == c_val]
        # Sort targets by cycle order
        cell_targets.sort(key=lambda x: x["order"])

        # Fetch SQLite analysis cache to populate Vset/Vreset in the legend
        from science_cli.core.project import get_current_project_path
        from science_cli.library.memristor.db import close_db, open_db, query_files
        proj = get_current_project_path()
        analysis_map = {}
        if proj:
            try:
                conn = open_db(proj)
                db_files = query_files(conn, protocol=pdir.name)
                close_db(conn)
                analysis_map = {f["filename"]: f for f in db_files}
            except Exception as e:
                print(f"Warning: could not query analysis results from database: {e}")

        all_traces = []
        for t in cell_targets:
            fe = t["file_entry"]
            step_ov = t.get("step")
            filepath = _resolve_file(pdir, config, fe, step_ov, t)
            try:
                voltage, current, info = read_iv_csv(str(filepath))
            except Exception as exc:
                print(f"  Error reading {fe.file}: {exc}")
                continue

            db_record = analysis_map.get(fe.file, {})
            metadata = {
                "row": t["row"],
                "col": t["col"],
                "material": t["material_key"],
                "order": t["order"],
                "sweep_type": fe.sweep_type or "uc",
                "v_set": db_record.get("v_set"),
                "v_reset": db_record.get("v_reset"),
            }
            all_traces.append((voltage, current, metadata))

        if all_traces:
            m_safe = m_val.replace("/", "-").replace(" ", "_")
            output_filename = f"iv_r{r_val}c{c_val}_{m_safe}_multicycle_raw.pdf" if raw_current else f"iv_r{r_val}c{c_val}_{m_safe}_multicycle.pdf"
            output_path = results_dir / output_filename
            try:
                generate_iv_highlighted_svg(all_traces, highlight_cycles, str(output_path), dpi=dpi, raw_current=raw_current, flags=all_flags)
                print(f"\n  ✓ Multi-cycle highlight plot generated: {output_path.name}")
                print(f"  Highlighted cycles: {highlight_cycles}")
                print(f"  Output path: {output_path}")
            except Exception as exc:
                print(f"  Error generating multi-cycle highlight plot: {exc}")
        else:
            print("No trace data successfully read.")
        return


    # Determine overlay vs individual mode
    overlay_mode = getattr(args, "overlay", False)
    all_mode = getattr(args, "plot_all", False)

    if use_fzf and not overlay_mode and not all_mode and len(targets) > 1:
        choice = input("  Overlay all (o) or individual plots (i)? [o/i] ").strip().lower()
        if choice == "i":
            all_mode = True
        else:
            overlay_mode = True

    if overlay_mode and all_mode:
        all_mode = False

    plotted = 0
    errors = 0

    if overlay_mode:
        # ── Overlay mode: one plot with all traces ──
        all_traces = []
        for t in targets:
            fe = t["file_entry"]
            step_ov = t.get("step")
            filepath = _resolve_file(pdir, config, fe, step_ov, t)
            try:
                voltage, current, info = read_iv_csv(str(filepath))
            except Exception as exc:
                print(f"  Error reading {fe.file}: {exc}")
                errors += 1
                continue
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
                "label": fe.file,
            }
            all_traces.append((voltage, current, metadata))

        if all_traces:
            output_path = results_dir / ("overlay_raw.pdf" if raw_current else "overlay.pdf")
            try:
                generate_iv_overlay_svg(all_traces, str(output_path), dpi=dpi, raw_current=raw_current, flags=all_flags)
                plotted = len(all_traces)
                print(f"  ✓ {output_path.name} ({len(all_traces)} traces)")
            except Exception as exc:
                print(f"  Error generating overlay: {exc}")
                errors += 1
    else:
        # ── Individual mode: one SVG per file ──
        position_files: dict[tuple[int, int], list[dict]] = {}
        for t in targets:
            pos = (t["row"], t["col"])
            position_files.setdefault(pos, []).append(t)
        for pos, files in position_files.items():
            files.sort(key=lambda x: x["order"])
            for i, f in enumerate(files):
                f["file_index"] = i

        for t in targets:
            fe = t["file_entry"]
            step_ov = t.get("step")
            filepath = _resolve_file(pdir, config, fe, step_ov, t)
            try:
                voltage, current, info = read_iv_csv(str(filepath))
            except Exception as exc:
                print(f"  Error reading {fe.file}: {exc}")
                errors += 1
                continue

            plot_filename = build_plot_filename(
                row=t["row"],
                col=t["col"],
                material_key=t["material_key"],
                sweep_type=t["sweep_type"],
                order=t["order"],
            )
            if raw_current:
                plot_filename = plot_filename.replace(".svg", "_raw.svg")
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
                "time": info.get("time"),
            }

            output_path = results_dir / plot_filename
            try:
                generate_iv_svg(voltage, current, metadata, str(output_path), dpi=dpi, raw_current=raw_current, flags=all_flags)
            except Exception as exc:
                print(f"  Error plotting {fe.file}: {exc}")
                errors += 1
                continue

            fe.extra["plot"] = plot_filename
            plotted += 1
            print(f"  ✓ {plot_filename}")

        if plotted > 0:
            write_devices(pdir, config)

    # Summary
    if overlay_mode and plotted > 0:
        print(f"\nPlotted: {plotted} | Errors: {errors}")
        print(f"Results: {results_dir}/")
    elif not overlay_mode:
        if plotted > 0:
            print(f"\nPlotted: {plotted} | Errors: {errors}")
            print(f"Results: {results_dir}/")

    set_last_step(pdir.name)


# ── Command: dashboard ──────────────────────────────────────


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Generate per-protocol dashboards + main index page (default)."""
    from pathlib import Path
    from science_cli.core.project import get_current_project_path
    from science_cli.library.memristor.dashboard import (
        generate_main_dashboard,
        generate_standalone_dashboard,
    )

    # Allow --project to override session (useful in CI)
    project_override = getattr(args, "project", "") or ""
    if project_override:
        project_dir = Path(project_override).resolve()
        if not project_dir.exists():
            print(f"Project path not found: {project_dir}")
            sys.exit(1)
    else:
        sess = load_session()
        last_proj = sess.get("last_project", "")
        if not last_proj:
            print("No project open. Use 'open -m project <path>' or --project.")
            sys.exit(1)
        project_dir = get_current_project_path()
        if not project_dir or not project_dir.exists():
            print(f"Project directory not found: {project_dir}")
            sys.exit(1)

    force = getattr(args, "force", False)
    proto_filter = getattr(args, "protocol", "") or ""
    standalone = getattr(args, "standalone", False)
    deploy = getattr(args, "deploy", False)
    repo_url = getattr(args, "repo", "") or ""
    branch = getattr(args, "branch", "") or "gh-pages"

    if deploy and not repo_url:
        try:
            import subprocess
            res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                repo_url = res.stdout.strip()
                print(f"Automatically detected git remote origin URL: {repo_url}")
        except Exception as e:
            print(f"Could not automatically detect git remote origin URL: {e}")

    # Ensure results dir exists
    results_dir = project_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    if standalone:
        output_path = Path(args.output) if args.output else results_dir / "dashboard_standalone.html"
        print("Generating standalone React HTML dashboard with embedded SQLite database cache...")
        try:
            out = generate_standalone_dashboard(project_dir, output_path)
            print(f"Standalone dashboard generated successfully at: {out}")
            
            if deploy:
                import subprocess
                if repo_url:
                    import shutil
                    deploy_dir = results_dir / "deploy"
                    deploy_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy standalone dashboard to index.html for hosting at root of GitHub Pages
                    index_path = deploy_dir / "index.html"
                    shutil.copy(str(out), str(index_path))
                    print(f"Prepared index.html at {index_path} for GitHub Pages deployment.")
                    
                    try:
                        # 1. Initialize git if not already present
                        if not (deploy_dir / ".git").exists():
                            subprocess.run(["git", "init", "-b", branch], cwd=deploy_dir, check=True)
                        else:
                            subprocess.run(["git", "checkout", "-B", branch], cwd=deploy_dir, check=True)
                        
                        # 2. Add or update remote origin
                        has_remote = False
                        try:
                            res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=deploy_dir, capture_output=True, text=True)
                            if res.returncode == 0:
                                has_remote = True
                        except Exception:
                            pass
                            
                        if has_remote:
                            subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=deploy_dir, check=True)
                        else:
                            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=deploy_dir, check=True)
                            
                        # 3. Stage, commit, and force-push
                        subprocess.run(["git", "add", "index.html"], cwd=deploy_dir, check=True)
                        
                        # Check if there is anything to commit
                        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=deploy_dir, capture_output=True, text=True)
                        if status_res.stdout.strip():
                            subprocess.run(["git", "commit", "-m", "deploy: update standalone dashboard [compiled]"], cwd=deploy_dir, check=True)
                        else:
                            print("No changes to commit in deploy folder.")
                            
                        print(f"Pushing compiled standalone dashboard to remote origin {repo_url} on branch '{branch}'...")
                        subprocess.run(["git", "push", "-u", "origin", branch, "--force"], cwd=deploy_dir, check=True)
                        print(f"Successfully deployed standalone dashboard online on GitHub at: {repo_url} [{branch}]!")
                    except Exception as g_err:
                        print(f"Git deployment to remote failed: {g_err}")
                else:
                    print(f"Deploying {out.name} to local repository GitHub...")
                    try:
                        subprocess.run(["git", "add", str(out)], check=True)
                        subprocess.run(["git", "commit", "-m", "deploy: update standalone dashboard [compiled]"], check=True)
                        print("Pushing commits to git origin...")
                        subprocess.run(["git", "push"], check=True)
                        print("Successfully pushed and deployed to GitHub origin!")
                    except Exception as g_err:
                        print(f"Git deployment failed: {g_err}")
                        
            if getattr(args, "open", False):
                import subprocess
                subprocess.run(["open", str(out)], check=False)
        except Exception as exc:
            print(f"Error generating standalone dashboard: {exc}")
            sys.exit(1)
        return

    output_path = Path(args.output) if args.output else results_dir / "dashboard.html"

    try:
        out = generate_main_dashboard(
            project_dir,
            output_path,
            protocol_filter=proto_filter,
            force=force,
        )
        print(f"Main dashboard generated: {out}")
        
        if deploy:
            import subprocess
            if repo_url:
                import shutil
                deploy_dir = results_dir / "deploy"
                deploy_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy results/dashboard.html to index.html for remote deployment
                shutil.copy(str(out), str(deploy_dir / "index.html"))
                
                # Copy entire results directory contents to deploy folder
                for item in results_dir.iterdir():
                    if item.name == "deploy":
                        continue
                    dest = deploy_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                        
                print(f"Prepared results folder at {deploy_dir} for GitHub Pages deployment.")
                
                try:
                    if not (deploy_dir / ".git").exists():
                        subprocess.run(["git", "init", "-b", branch], cwd=deploy_dir, check=True)
                    else:
                        subprocess.run(["git", "checkout", "-B", branch], cwd=deploy_dir, check=True)
                        
                    has_remote = False
                    try:
                        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=deploy_dir, capture_output=True, text=True)
                        if res.returncode == 0:
                            has_remote = True
                    except Exception:
                        pass
                        
                    if has_remote:
                        subprocess.run(["git", "remote", "set-url", "origin", repo_url], cwd=deploy_dir, check=True)
                    else:
                        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=deploy_dir, check=True)
                        
                    subprocess.run(["git", "add", "."], cwd=deploy_dir, check=True)
                    
                    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=deploy_dir, capture_output=True, text=True)
                    if status_res.stdout.strip():
                        subprocess.run(["git", "commit", "-m", "deploy: update results dashboard [compiled]"], cwd=deploy_dir, check=True)
                    else:
                        print("No changes to commit in deploy folder.")
                        
                    print(f"Pushing compiled results dashboard to remote origin {repo_url} on branch '{branch}'...")
                    subprocess.run(["git", "push", "-u", "origin", branch, "--force"], cwd=deploy_dir, check=True)
                    print(f"Successfully deployed results dashboard online on GitHub at: {repo_url} [{branch}]!")
                except Exception as g_err:
                    print(f"Git deployment to remote failed: {g_err}")
            else:
                print(f"Deploying {out.name} to local repository GitHub...")
                try:
                    subprocess.run(["git", "add", str(out)], check=True)
                    # Stage the rest of the results folder as well
                    subprocess.run(["git", "add", str(project_dir / "results")], check=True)
                    subprocess.run(["git", "commit", "-m", "deploy: update results dashboard [compiled]"], check=True)
                    print("Pushing commits to git origin...")
                    subprocess.run(["git", "push"], check=True)
                    print("Successfully pushed and deployed to GitHub origin!")
                except Exception as g_err:
                    print(f"Git deployment failed: {g_err}")
                
        if getattr(args, "open", False):
            import subprocess
            subprocess.run(["open", str(out)], check=False)
    except Exception as exc:
        print(f"Error generating dashboard: {exc}")
        sys.exit(1)


# ── CLI entry point ─────────────────────────────────────────


def show_memristor_help() -> None:
    """Show a beautifully grouped Rich-based help menu for 'sci memristor'."""
    from rich.console import Console
    from rich.panel import Panel
    try:
        from science_cli import __version__
    except ImportError:
        __version__ = "3.0.0"

    accent_r = "green"
    try:
        from science_cli.theme import RICH_STYLES
        accent_r = RICH_STYLES.get("accent", "green")
    except ImportError:
        pass

    console = Console()
    console.print()
    console.print(Panel(
        f"[bold]sci memristor[/bold] — Crossbar Device Manager for Memristor Characterization [dim]v{__version__}[/dim]\n"
        "[dim]Manage device geometry, sync sweep metadata, and analyze IV/endurance/retention measurements.[/dim]",
        border_style=accent_r,
    ))
    console.print()

    groups = {
        "GROUP 1: DEVICE GEOMETRY & ASSIGNMENT": {
            "init": "Scaffold device geometry in protocol YAML",
            "ls": "List devices or matrix map",
            "info": "Show point details",
            "add": "Add file(s) to a point",
            "rm": "Remove file, technique, or point",
        },
        "GROUP 2: CACHE SYNCHRONIZATION & HEALTH": {
            "sync": "Sync sweep metadata",
            "validate": "Validate device config",
            "stats": "Aggregate statistics",
            "check": "Find unassigned files (recursive)",
        },
        "GROUP 3: CURVES PLOTTING, MATRIX & DASHBOARD": {
            "plot": "Generate IV curve SVGs from devices.yaml",
            "analyze": "Read CSVs and compute Vset/Vreset/ratio (depends on sync)",
            "dashboard": "Generate per-protocol dashboards + main index page",
            "matrix": "Show device matrix from SQLite (no YAML required)",
        }
    }

    for group_name, cmds in groups.items():
        console.print(f"  [bold]{group_name}[/bold]")
        for cmd_name, desc in cmds.items():
            console.print(f"    {cmd_name:<18} [dim]{desc}[/dim]")
        console.print()

    console.print("  [dim]Use `sci memristor <subcommand> --help` for more details on a specific subcommand.[/dim]")
    console.print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crossbar device manager for memristor characterization"
    )
    parser.print_help = lambda file=None: show_memristor_help()
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    p_init = sub.add_parser("init", help="Scaffold device geometry in protocol YAML")
    p_init.add_argument("--rows", type=int, default=None)
    p_init.add_argument("--cols", type=int, default=None)
    p_init.add_argument("--matrix", default="",
        help="Shorthand: --matrix r6-c6 (sets rows=6, cols=6)")
    p_init.add_argument("--label", default="")
    p_init.add_argument(
        "--pt", "--protocol",
        dest="protocol_name",
        default="",
        help="Protocol name (default: current session protocol)",
    )
    p_init.add_argument(
        "--steps", default="",
        help="Step dirs: 4_iv-characterization or iv:4_iv,endurance:5_end",
    )
    p_init.set_defaults(func=cmd_init)

    p_ls = sub.add_parser("ls", help="List devices or matrix map")
    p_ls.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_ls.add_argument("--matrix", action="store_true", help="Grid view (per-material when data tagged)")
    p_ls.add_argument("--technique", default="", help="Filter by technique (e.g., iv)")
    p_ls.add_argument("--material", default="", help="Filter by material+batch (e.g., Ta-PDAc-ITO(1))")
    p_ls.set_defaults(func=cmd_ls)

    p_info = sub.add_parser("info", help="Show point details")
    p_info.add_argument("--row", type=int, required=True)
    p_info.add_argument("--col", type=int, required=True)
    p_info.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_info.set_defaults(func=cmd_info)

    p_add = sub.add_parser("add", help="Add file(s) to a point")
    p_add.add_argument("--row", type=int, default=None)
    p_add.add_argument("--col", type=int, default=None)
    p_add.add_argument("--technique", default="", help="Technique (inferred from filename)")
    p_add.add_argument("--file", default="")
    p_add.add_argument("--temperature", type=float, default=None)
    p_add.add_argument("--device-type", default=None, choices=["volatile", "non-volatile", "resistor", "short", "insulating"], help="Manually set cell device type")
    p_add.add_argument("--error", default=None, help="Manually set cell error or remark")
    p_add.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_add.add_argument(
        "--pattern", default="",
        help="Regex for batch: r(\\d+)c(\\d+) groups 1=row, 2=col",
    )
    p_add.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_add.add_argument("--yes", action="store_true", help="Skip confirmation")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("rm", help="Remove file, technique, or point")
    p_rm.add_argument("--row", type=int, required=True)
    p_rm.add_argument("--col", type=int, required=True)
    p_rm.add_argument("--technique", default="", help="Technique (inferred from filename)")
    p_rm.add_argument("--file", default="")
    p_rm.add_argument("--confirm", action="store_true", help="Confirm entire point removal")
    p_rm.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_rm.set_defaults(func=cmd_rm)

    p_matrix = sub.add_parser("matrix", help="Show device matrix from SQLite (no YAML required)")
    p_matrix.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_matrix.add_argument("--all", "-A", action="store_true",
                          help="Show matrix for ALL protocols in the project")
    p_matrix.add_argument("--material", default="", help="Filter by exact material name")
    p_matrix.add_argument("--technique", default="", help="Filter by technique (e.g., iv-sweep)")
    p_matrix.add_argument("--grid", default="",
                          help="Force grid dimensions (e.g. r6-c6). Overrides protocol YAML.")
    p_matrix.add_argument("--status", action="store_true",
                          help="Show summary of what's loaded in the database")
    p_matrix.set_defaults(func=cmd_matrix)

    p_sync = sub.add_parser("sync", help="Sync sweep metadata")
    p_sync.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_sync.add_argument("--all", "-A", action="store_true",
                        help="Sync ALL protocols in the current project")
    p_sync.add_argument("--reindex", action="store_true", help="Reindex SQLite from YAML only (no CSV re-read)")
    p_sync.add_argument("--reconcile", "-r", action="store_true",
                        help="Reconcile protocol YAML file list with disk, then sync DB")
    p_sync.add_argument("--force", "-F", action="store_true",
                        help="Delete stale DB entries first, then re-scan from scratch")
    p_sync.set_defaults(func=cmd_sync)

    p_val = sub.add_parser("validate", help="Validate device config")
    p_val.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_val.set_defaults(func=cmd_validate)

    p_stats = sub.add_parser("stats", help="Aggregate statistics")
    p_stats.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_stats.set_defaults(func=cmd_stats)

    p_check = sub.add_parser("check", help="Find unassigned files (recursive)")
    p_check.add_argument("--list", action="store_true", help="List unassigned files")
    p_check.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_check.set_defaults(func=cmd_check)

    p_plot = sub.add_parser("plot", help="Generate IV curve SVGs from devices.yaml")
    p_plot.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_plot.add_argument("--overlay", action="store_true", help="Overlay all selected files in one plot")
    p_plot.add_argument("--all", action="store_true", dest="plot_all", help="Export each file individually")
    p_plot.add_argument("--material", default="", help="Plot files for a specific material+batch")
    p_plot.add_argument("--row", type=int, default=None, help="Filter by matrix row")
    p_plot.add_argument("--col", type=int, default=None, help="Filter by matrix column")
    p_plot.add_argument("--dpi", type=int, default=150, help="SVG resolution (default: 150)")
    p_plot.add_argument("--highlight", default="",
                        help="Multi-cycle overlay: highlight specific cycles, grey out rest. "
                             "Comma/range syntax (e.g. '1,5,10-15,50,100'). "
                             "Merges all files for a single cell into one Nature-style plot.")
    p_plot.add_argument("--raw", action="store_true",
                        help="Plot raw linear current (no |I|, no log scale). "
                             "Recommended with --highlight for direct current readout.")
    p_plot.set_defaults(func=cmd_plot)


    p_dash = sub.add_parser("dashboard", help="Generate per-protocol dashboards + main index page")
    p_dash.add_argument("--step", default="", help="Step directory name (short name OK)")
    p_dash.add_argument("--output", default="", help="Custom output path (default: results/dashboard.html)")
    p_dash.add_argument("--open", action="store_true", help="Open in browser after generation")
    p_dash.add_argument("--pt", "--protocol", default="", dest="protocol",
                        help="Single protocol name (e.g. 'batch-demo')")
    p_dash.add_argument("--project", default="",
                        help="Project directory path (for CI/automation; overrides session)")
    p_dash.add_argument("--all", action="store_true", help="(default) Build all protocols — kept for compatibility")
    p_dash.add_argument("--force", action="store_true", help="Force full re-generation, ignore cache")
    p_dash.add_argument("--standalone", action="store_true",
                        help="Generate a self-contained static HTML build of the dashboard")
    p_dash.add_argument("--deploy", action="store_true",
                        help="Stages, commits, and pushes the compiled dashboard directly to GitHub")
    p_dash.add_argument("--repo", default="",
                        help="Git repository URL to deploy the dashboard to (for isolating and publishing online)")
    p_dash.add_argument("--branch", default="gh-pages",
                        help="Git branch to push deployment to (default: gh-pages)")
    p_dash.set_defaults(func=cmd_dashboard)

    p_analyze = sub.add_parser("analyze", help="Read CSVs and compute Vset/Vreset/ratio (depends on sync)")
    p_analyze.add_argument("--all", "-A", action="store_true", help="Analyze all protocols in the database")
    p_analyze.add_argument("--pt", "--protocol", default="", dest="protocol",
                           help="Protocol name to analyze (e.g. '5_cu-c_ta-cu')")
    p_analyze.add_argument("--step", default="", help="Filter to a specific step name (e.g. '4_iv')")
    p_analyze.add_argument("--force", action="store_true", help="Re-analyze all files (ignore cached analysis)")
    p_analyze.add_argument("--file", default="", help="Single-file re-analysis")
    p_analyze.add_argument("--mat", default="", help="Material name or pattern to override (supports bracket clusters)")
    p_analyze.add_argument("--cell", default="", help="Coordinate cell (row,col) to override")
    p_analyze.add_argument("--type", default="", help="Target classification type (volatile, non-volatile, short, insulating)")
    p_analyze.add_argument("extra_args", nargs="*", help="Capture trailing custom expressions (e.g. 'is volatile')")
    p_analyze.set_defaults(func=cmd_analyze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
