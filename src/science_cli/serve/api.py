"""Data providers for the sci serve REST API.

All functions are **read-only** — no files are written to the project.
Caches (analysis_data.json, SQLite) are read if available; otherwise
lightweight filesystem scans are used."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _resolve_project(project_override: str | None = None) -> Path | None:
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    if project_override:
        p = Path(os.path.expanduser(project_override))
        if p.exists():
            return p
        # Try resolving relative to get_projects_root()
        from science_cli.core.config import get_projects_root
        root = get_projects_root()
        candidate = root / project_override
        if candidate.exists():
            return candidate
        return None

    proj = get_current_project_path()
    if proj:
        return proj

    sess = load_session()
    name = sess.get("last_project", "")
    if name:
        from science_cli.core.config import get_projects_root
        root = get_projects_root()
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def get_projects_list() -> dict:
    """Scan the configured projects root and list active projects."""
    from science_cli.core.config import get_projects_root
    root = get_projects_root()
    projects = []
    if root.exists() and root.is_dir():
        for item in sorted(root.iterdir()):
            if (
                item.is_dir()
                and not item.name.startswith(".")
                and not item.name.startswith("__")
                and item.name not in ("node_modules", "venv", "env")
            ):
                projects.append(item.name)
    return {
        "workspace": str(root),
        "projects": projects
    }



def _read_analysis_cache(project_path: Path) -> dict | None:
    cache = project_path / "results" / "analysis_data.json"
    if not cache.exists():
        return None
    try:
        with open(cache) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _read_sqlite_data(project_path: Path) -> dict | None:
    db_path = project_path / f"{project_path.name}.db"
    if not db_path.exists():
        return None
    try:
        from science_cli.library.memristor.db import close_db, open_db, query_cells, query_files
        conn = open_db(project_path)
        files = query_files(conn)
        cells = query_cells(conn)
        close_db(conn)
        return {"files": files, "cells": cells}
    except Exception:
        return None


def _get_step_files(
    project_name: str,
    protocol_name: str,
    step_name: str,
    step_path: Path,
) -> list[dict]:
    files = []

    # Check results/ directory first
    results_dir = step_path / "results"
    scan_dirs = []
    if results_dir.exists() and results_dir.is_dir():
        scan_dirs.append((results_dir, f"protocol/{protocol_name}/{step_name}/results"))
    # Also support files directly in step_path
    scan_dirs.append((step_path, f"protocol/{protocol_name}/{step_name}"))

    # Gather raw experimental filenames (excluding results/)
    raw_data_stems = set()
    try:
        for entry in step_path.iterdir():
            if entry.is_file() and entry.suffix.lower() in (".csv", ".txt", ".dat", ".tsv"):
                raw_data_stems.add(entry.stem.lower())
    except Exception:
        pass

    seen_names = set()
    for directory, relative_url_prefix in scan_dirs:
        for entry in sorted(directory.iterdir()):
            if entry.is_file() and not entry.name.startswith("."):
                ext = entry.suffix.lower()
                if ext in (".png", ".pdf", ".svg"):
                    if entry.name in seen_names:
                        continue
                    seen_names.add(entry.name)
                    st = entry.stat()

                    # Classify category
                    name_lower = entry.stem.lower()
                    is_distinct = False
                    if name_lower in raw_data_stems:
                        is_distinct = True
                    else:
                        import re
                        # Strip common technique prefixes: raman_, ec-cv_, ec-ca_, ec-eis_, iv-sweep_, sers_ etc
                        cleaned = re.sub(
                            r"^(ec-cv|ec-ca|ec-eis|iv-sweep|iv-dc|iv_dc|raman|sers|uv-vis|cv|ca|eis|iv|afm)[_\-]",
                            "",
                            name_lower,
                        )
                        if cleaned in raw_data_stems:
                            is_distinct = True
                        else:
                            # Substring match fallback
                            for stem in raw_data_stems:
                                if stem in name_lower:
                                    is_distinct = True
                                    break

                    category = "distinct" if is_distinct else "overlay"

                    files.append({
                        "name": entry.name,
                        "path": f"{project_name}/{relative_url_prefix}/{entry.name}",
                        "type": ext[1:],  # svg, pdf, png
                        "size": f"{round(st.st_size / 1024, 1)} KB",
                        "created": datetime.fromtimestamp(
                            st.st_mtime, tz=timezone.utc
                        ).strftime("%Y-%m-%d"),
                        "dimensions": "1280x800 px",
                        "category": category,
                    })
    return files


def get_protocol_files(project_path: Path, protocol_name: str) -> dict:
    proto_dir = project_path / "protocol" / protocol_name
    if not proto_dir.exists():
        return {"error": f"protocol '{protocol_name}' not found"}

    proj_name = project_path.name
    steps_list = []

    for sdir in sorted(proto_dir.iterdir()):
        if not sdir.is_dir() or sdir.name.startswith("."):
            continue

        step_name = sdir.name
        step_files_data = _get_step_files(proj_name, protocol_name, step_name, sdir)
        steps_list.append({
            "name": step_name,
            "files": step_files_data,
        })

    return {
        "protocol": protocol_name,
        "steps": steps_list,
    }


def _get_protocol_materials(project_path: Path) -> set[str]:
    """Return set of protocol names that have entries in the materials table."""
    import sqlite3
    db_path = project_path / f"{project_path.name}.db"
    if not db_path.exists():
        return set()
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT DISTINCT protocol FROM materials")
        result = {row[0] for row in cur.fetchall()}
        conn.close()
        return result
    except (sqlite3.Error, Exception):
        return set()


def _scan_protocol_dirs(
    project_path: Path,
) -> list[dict]:
    proto_dir = project_path / "protocol"
    if not proto_dir.exists():
        return []

    proj_name = project_path.name
    materials_set = _get_protocol_materials(project_path)
    protocols = []
    for sub in sorted(proto_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue

        protocol_name = sub.name
        steps = []
        for entry in sorted(sub.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                step_name = entry.name
                step_files_data = _get_step_files(proj_name, protocol_name, step_name, entry)
                steps.append({
                    "name": step_name,
                    "files": step_files_data,
                })

        if not steps:
            continue

        csv_count = 0
        for step_item in steps:
            sd = sub / step_item["name"]
            if sd.is_dir():
                csv_count += len([
                    f for f in sd.iterdir()
                    if f.suffix.lower() in (".csv", ".txt", ".dat", ".tsv")
                ])

        protocols.append({
            "name": sub.name,
            "steps": steps,
            "total_files": csv_count,
            "measured_cells": 0,
            "switching_yield": 0.0,
            "has_devices": (sub / "devices.yaml").exists(),
            "has_materials": sub.name in materials_set,
            "last_updated": datetime.fromtimestamp(
                sub.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        })

    return protocols


def _enrich_from_cache(protocols: list[dict], cache: dict | None) -> list[dict]:
    if not cache:
        return protocols

    proto_map = {p["name"]: p for p in cache.get("protocols", [])}
    for proto in protocols:
        cached = proto_map.get(proto["name"])
        if cached:
            devices = cached.get("devices", {})
            proto["measured_cells"] = len(devices)
            switching = sum(1 for d in devices.values() if d.get("switching"))
            proto["switching_yield"] = (
                round(switching / len(devices) * 100, 1)
                if devices else 0.0
            )
    return protocols


def get_project_data(
    project_path: Path,
) -> dict:
    proj_name = project_path.name

    cache = _read_analysis_cache(project_path)
    protocols = _scan_protocol_dirs(project_path)
    protocols = _enrich_from_cache(protocols, cache)

    total_files = sum(p["total_files"] for p in protocols)
    total_cells = sum(p["measured_cells"] for p in protocols)
    total_yield = 0.0
    if total_cells > 0:
        switching_total = sum(
            p["switching_yield"] * p["measured_cells"] / 100.0
            for p in protocols
        )
        total_yield = round(switching_total / max(1, total_cells) * 100, 1)

    return {
        "project_name": proj_name,
        "project_path": str(project_path),
        "last_protocol": "",
        "last_step": "",
        "protocols": protocols,
        "stats": {
            "total_protocols": len(protocols),
            "total_files": total_files,
            "total_cells_measured": total_cells,
            "overall_yield": total_yield,
        },
    }


def get_protocol_summary(
    project_path: Path,
    protocol_name: str,
) -> dict:
    all_protocols = _scan_protocol_dirs(project_path)
    proto = next((p for p in all_protocols if p["name"] == protocol_name), None)
    if proto is None:
        return {"error": f"protocol '{protocol_name}' not found"}

    cache = _read_analysis_cache(project_path)
    _enrich_from_cache(all_protocols, cache)
    proto = next((p for p in all_protocols if p["name"] == protocol_name), proto)

    aggregate = {
        "total_cells": 0,
        "measured_cells": proto["measured_cells"],
        "switching_count": 0,
        "yield_pct": proto["switching_yield"],
        "median_vset": 0.0,
        "median_vreset": 0.0,
        "median_ratio": 0.0,
        "total_iv_files": proto["total_files"],
    }

    device = {"rows": 0, "cols": 0, "label": f"{protocol_name}"}
    materials: list[str] = []

    if cache:
        cached_proto = next(
            (p for p in cache.get("protocols", []) if p["name"] == protocol_name),
            None,
        )
        if cached_proto:
            device = {
                "rows": cached_proto.get("rows", 0),
                "cols": cached_proto.get("cols", 0),
                "label": cached_proto.get("device_label", protocol_name),
            }
            devices = cached_proto.get("devices", {})
            switching = sum(1 for d in devices.values() if d.get("switching"))
            aggregate["total_cells"] = device["rows"] * device["cols"]
            aggregate["switching_count"] = switching
            aggregate["total_iv_files"] = sum(
                d.get("n_files", 0) for d in devices.values()
            )

            vset_vals = sorted(
                d["v_set"] for d in devices.values()
                if d.get("v_set") and d.get("switching")
            )
            vreset_vals = sorted(
                d["v_reset"] for d in devices.values()
                if d.get("v_reset") and d.get("switching")
            )
            ratio_vals = sorted(
                d["ratio"] for d in devices.values()
                if d.get("ratio") and d.get("ratio") > 0
            )

            def _med(vals):
                if not vals:
                    return 0.0
                n = len(vals)
                if n % 2 == 1:
                    return round(vals[n // 2], 2)
                return round((vals[n // 2 - 1] + vals[n // 2]) / 2, 2)

            aggregate["median_vset"] = _med(vset_vals)
            aggregate["median_vreset"] = _med(vreset_vals)
            aggregate["median_ratio"] = _med(ratio_vals)

            materials = sorted(set(
                d.get("material", "unknown")
                for d in devices.values()
            ))

    return {
        "protocol": protocol_name,
        "device": device,
        "aggregate": aggregate,
        "materials": materials,
    }


def get_heatmap_data(
    project_path: Path,
    protocol_name: str,
    metric: str = "ratio",
    material_filter: str = "",
) -> dict | None:
    cache = _read_analysis_cache(project_path)
    if not cache:
        return _heatmap_from_filesystem(project_path, protocol_name)
    return _heatmap_from_cache(project_path, protocol_name, metric, material_filter, cache)


def _heatmap_from_filesystem(
    project_path: Path,
    protocol_name: str,
) -> dict:
    proto_dir = project_path / "protocol" / protocol_name
    if not proto_dir.exists():
        return {"error": f"protocol '{protocol_name}' not found"}

    rows, cols = 6, 6
    data: list[list] = []
    metadata: list[list] = []

    for r in range(rows):
        row_data: list = []
        row_meta: list = []
        for c in range(cols):
            row_data.append(None)
            row_meta.append({
                "cell": f"R{r + 1}C{c + 1}",
                "material": "unknown",
                "n_files": 0,
                "status": "Unmeasured",
                "v_set": 0,
                "v_reset": 0,
                "r_on": 0,
                "r_off": 0,
                "ratio": 0,
            })
        data.append(row_data)
        metadata.append(row_meta)

    return {"rows": rows, "cols": cols, "metric": "ratio", "data": data, "metadata": metadata}


def _heatmap_from_cache(
    project_path: Path,
    protocol_name: str,
    metric: str,
    material_filter: str,
    cache: dict,
) -> dict:
    proto = next(
        (p for p in cache.get("protocols", []) if p["name"] == protocol_name),
        None,
    )
    if not proto:
        return _heatmap_from_filesystem(project_path, protocol_name)

    rows = proto.get("rows", 6)
    cols = proto.get("cols", 6)
    devices = proto.get("devices", {})
    data: list[list] = []
    metadata: list[list] = []

    for r in range(rows):
        row_data: list = []
        row_meta: list = []
        for c in range(cols):
            cell_id = f"R{r + 1}C{c + 1}"
            dev = devices.get(cell_id)
            if not dev or (material_filter and dev.get("material", "") != material_filter):
                row_data.append(None)
                row_meta.append({
                    "cell": cell_id,
                    "material": dev.get("material", "unknown") if dev else "unknown",
                    "n_files": dev.get("n_files", 0) if dev else 0,
                    "status": "Unmeasured" if not dev else
                        ("Active Switching" if dev.get("switching") else "Non-Switching"),
                    "v_set": dev.get("v_set", 0) if dev else 0,
                    "v_reset": dev.get("v_reset", 0) if dev else 0,
                    "r_on": 0,
                    "r_off": 0,
                    "ratio": dev.get("ratio", 0) if dev else 0,
                })
                continue

            switching = dev.get("switching", False)
            val = None
            if metric == "ratio":
                val = dev.get("ratio")
            elif metric == "vset":
                val = dev.get("v_set") if switching else None
            elif metric == "vreset":
                val = dev.get("v_reset") if switching else None
            elif metric == "files":
                val = dev.get("n_files")
            elif metric == "yield":
                val = 100 if switching else 0

            row_data.append(val)
            row_meta.append({
                "cell": cell_id,
                "material": dev.get("material", "unknown"),
                "n_files": dev.get("n_files", 0),
                "status": "Active Switching" if switching else "Non-Switching",
                "v_set": dev.get("v_set", 0),
                "v_reset": dev.get("v_reset", 0),
                "r_on": 0,
                "r_off": 0,
                "ratio": dev.get("ratio", 0),
            })
        data.append(row_data)
        metadata.append(row_meta)

    return {"rows": rows, "cols": cols, "metric": metric, "data": data, "metadata": metadata}


def get_device_iv(
    project_path: Path,
    protocol_name: str,
    cell_id: str,
) -> dict:
    import re
    import numpy as np
    match = re.match(r"R(\d+)C(\d+)", cell_id, re.IGNORECASE)
    if not match:
        return {"error": f"invalid cell_id '{cell_id}' — expected R<n>C<m>"}

    row = int(match.group(1)) - 1
    col = int(match.group(2)) - 1

    db_path = project_path / f"{project_path.name}.db"
    if db_path.exists():
        try:
            from science_cli.library.memristor.db import open_db, close_db
            from science_cli.library.memristor.switching import compute_on_off_ratio
            from science_cli.library.memristor.plotting import read_iv_csv
            
            conn = open_db(project_path)
            qfiles = conn.execute(
                """SELECT step, filename, v_set, v_reset, on_off_ratio, sweep_order
                   FROM files
                   WHERE protocol = ? AND row = ? AND col = ?
                   ORDER BY COALESCE(sweep_order, filename)""",
                (protocol_name, row + 1, col + 1)
            ).fetchall()
            close_db(conn)
            
            if qfiles:
                sweeps = []
                for idx, f in enumerate(qfiles):
                    step = f["step"]
                    filename = f["filename"]
                    filepath = project_path / "protocol" / protocol_name / step / filename
                    
                    # Read experimental data points
                    voltage, current, info = read_iv_csv(str(filepath))
                    
                    # Compute LRS/HRS resistances dynamically at v_read=0.1 V
                    ratio_data = compute_on_off_ratio(voltage, current)
                    
                    sweeps.append({
                        "label": f"Sweep #{f['sweep_order'] if f['sweep_order'] is not None else idx + 1:02d}",
                        "voltage": voltage.tolist() if hasattr(voltage, "tolist") else list(voltage),
                        "current": current.tolist() if hasattr(current, "tolist") else list(current),
                        "v_set": f["v_set"] or 0.0,
                        "v_reset": f["v_reset"] or 0.0,
                        "r_on": ratio_data.get("r_on") or 0.0,
                        "r_off": ratio_data.get("r_off") or 0.0,
                    })
                
                # Fetch material and dynamic classification
                conn2 = open_db(project_path)
                mat_row = conn2.execute(
                    "SELECT material, device_type FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                    (protocol_name, row + 1, col + 1)
                ).fetchone()
                close_db(conn2)
                
                material = mat_row["material"] if mat_row else "unknown"
                device_type = mat_row["device_type"] if mat_row else "non-volatile"
                switching = device_type in ("volatile", "non-volatile")
                
                return {
                    "cell_id": cell_id,
                    "row": row,
                    "col": col,
                    "material": material,
                    "v_set": sweeps[0]["v_set"] if sweeps else 0.0,
                    "v_reset": sweeps[0]["v_reset"] if sweeps else 0.0,
                    "ratio": sweeps[0]["r_off"] / sweeps[0]["r_on"] if sweeps and sweeps[0]["r_on"] else 0.0,
                    "switching": switching,
                    "sweeps": sweeps,
                }
        except Exception as e:
            # Fall back to filesystem scan on failure
            print(f"[WARN] SQLite fetch in get_device_iv failed: {e}")

    # Fallback to direct cache scan
    cache = _read_analysis_cache(project_path)
    if cache:
        proto = next(
            (p for p in cache.get("protocols", []) if p["name"] == protocol_name),
            None,
        )
        if proto:
            devices = proto.get("devices", {})
            dev = devices.get(cell_id)
            if dev:
                sweeps = []
                for i, f in enumerate(dev.get("files", [])):
                    sweeps.append({
                        "label": f"Sweep #{i + 1:02d}",
                        "voltage": f.get("voltage", []),
                        "current": f.get("current", []),
                        "v_set": f.get("v_set", 0),
                        "v_reset": f.get("v_reset", 0),
                        "r_on": 0.0,
                        "r_off": 0.0,
                    })
                return {
                    "cell_id": cell_id,
                    "row": dev.get("row", row),
                    "col": dev.get("col", col),
                    "material": dev.get("material", "unknown"),
                    "v_set": dev.get("v_set", 0),
                    "v_reset": dev.get("v_reset", 0),
                    "ratio": dev.get("ratio", 0),
                    "switching": dev.get("switching", False),
                    "sweeps": sweeps if sweeps else _generate_empty_sweeps(),
                }

    return _iv_from_csv_direct(project_path, protocol_name, row, col, cell_id)


def _generate_empty_sweeps() -> list[dict]:
    n = 100
    voltage = [round(3.0 * (i / (n - 1)), 2) for i in range(n)]
    current = [0.0] * n
    return [{
        "label": "Sweep #01",
        "voltage": voltage,
        "current": current,
        "v_set": 0,
        "v_reset": 0,
    }]


def _iv_from_csv_direct(
    project_path: Path,
    protocol_name: str,
    row: int,
    col: int,
    cell_id: str,
) -> dict:
    proto_dir = project_path / "protocol" / protocol_name
    if not proto_dir.exists():
        return {
            "cell_id": cell_id,
            "row": row,
            "col": col,
            "material": "unknown",
            "v_set": 0,
            "v_reset": 0,
            "ratio": 0,
            "switching": False,
            "sweeps": _generate_empty_sweeps(),
        }

    sweeps = []
    material = "unknown"

    for sdir in sorted(proto_dir.iterdir()):
        if not sdir.is_dir() or sdir.name.startswith("."):
            continue

        for f in sorted(sdir.iterdir()):
            if f.suffix.lower() not in (".csv", ".txt", ".dat", ".tsv"):
                continue

            fname = f.name.lower()

            import re
            pattern = rf"r{row + 1}[c_\-]c{col + 1}"
            if not re.search(pattern, fname):
                continue

            try:
                with open(f) as fh:
                    lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

                voltages = []
                currents = []
                for line in lines:
                    parts = line.replace(",", "\t").split("\t")
                    if len(parts) < 2:
                        continue
                    try:
                        v = float(parts[0])
                        c = float(parts[1])
                        voltages.append(v)
                        currents.append(c)
                    except ValueError:
                        continue

                if voltages:
                    v_set, v_reset = _estimate_switching(voltages, currents)
                    from science_cli.library.memristor.switching import compute_on_off_ratio
                    ratio_data = compute_on_off_ratio(np.array(voltages), np.array(currents))
                    sweeps.append({
                        "label": f"Sweep #{len(sweeps) + 1:02d}",
                        "voltage": voltages,
                        "current": currents,
                        "v_set": v_set,
                        "v_reset": v_reset,
                        "r_on": ratio_data.get("r_on") or 0.0,
                        "r_off": ratio_data.get("r_off") or 0.0,
                    })
            except Exception:
                continue

    if not sweeps:
        sweeps = _generate_empty_sweeps()

    v_set = sweeps[0]["v_set"] if sweeps else 0
    v_reset = sweeps[0]["v_reset"] if sweeps else 0
    switching = v_set != 0 or v_reset != 0

    return {
        "cell_id": cell_id,
        "row": row,
        "col": col,
        "material": material,
        "v_set": v_set,
        "v_reset": v_reset,
        "ratio": 0.0,
        "switching": switching,
        "sweeps": sweeps,
    }


def _estimate_switching(voltage, current):
    v_set = 0.0
    v_reset = 0.0
    try:
        n = len(voltage)
        for i in range(1, n):
            if voltage[i] > 0 and current[i] > 0:
                d = abs(current[i] - current[i - 1])
                if d > 0 and current[i] > 0:
                    ratio_up = abs(current[i] / max(abs(current[i - 1]), 1e-12))
                    if ratio_up > 10 and voltage[i] > 0.5:
                        v_set = round(voltage[i], 2)
                        break
        for i in range(1, n):
            if voltage[i] < 0:
                ratio_down = abs(current[i] / max(abs(current[i - 1]), 1e-12))
                if ratio_down > 5 and voltage[i] < -0.5:
                    v_reset = round(voltage[i], 2)
                    break
    except Exception:
        pass
    return v_set, v_reset


def get_histograms(
    project_path: Path,
    protocol_name: str,
) -> dict:
    cache = _read_analysis_cache(project_path)

    vset_vals = []
    vreset_vals = []
    ratio_vals = []

    if cache:
        proto = next(
            (p for p in cache.get("protocols", []) if p["name"] == protocol_name),
            None,
        )
        if proto:
            for dev in proto.get("devices", {}).values():
                if dev.get("switching"):
                    vs = dev.get("v_set")
                    vr = dev.get("v_reset")
                    if vs is not None and vs != 0:
                        vset_vals.append(abs(vs) if vs > 0 else vs)
                    if vr is not None and vr != 0:
                        vreset_vals.append(abs(vr) if vr > 0 else vr)
                r = dev.get("ratio")
                if r is not None and r > 0:
                    ratio_vals.append(r)

    return {
        "vset": _bin_1d(vset_vals, 1.0, 3.0, 7) if vset_vals else {"bins": [], "counts": []},
        "vreset": _bin_1d(vreset_vals, 0.5, 2.5, 6) if vreset_vals else {"bins": [], "counts": []},
        "ratio": _bin_1d(ratio_vals, 0, 1000, 7) if ratio_vals else {"bins": [], "counts": []},
    }


def _bin_1d(values: list[float], vmin: float, vmax: float, n_bins: int) -> dict:
    if not values:
        return {"bins": [], "counts": []}
    step = (vmax - vmin) / n_bins
    edges = [round(vmin + i * step, 2) for i in range(n_bins + 1)]
    bins = []
    counts = []
    for i in range(n_bins):
        lo = edges[i]
        hi = edges[i + 1]
        if i == n_bins - 1:
            bins.append(f"{lo}+")
        else:
            bins.append(f"{lo:.1f}-{hi:.1f}")
        c = sum(1 for v in values if lo <= v < hi)
        counts.append(c)
    return {"bins": bins, "counts": counts}


def get_dashboard_data(
    project_path: Path,
    protocol_name: str,
    metric: str = "ratio",
    material_filter: str = "",
) -> dict:
    """Comprehensive dashboard data for one protocol — reads SQLite first, falls back to cache.

    Returns everything the dashboard frontend needs in one call:
    - protocol info
    - KPI aggregates
    - heatmap matrix with device_type per cell
    - histograms
    - device type breakdown
    - materials list
    """
    db_path = project_path / f"{project_path.name}.db"
    has_sqlite = db_path.exists()

    rows, cols = 6, 6

    # Default response structure
    result = {
        "protocol": protocol_name,
        "device": {"rows": rows, "cols": cols, "label": protocol_name},
        "aggregate": {
            "total_cells": 0, "measured_cells": 0,
            "switching_count": 0, "yield_pct": 0.0,
            "median_vset": 0.0, "median_vreset": 0.0, "median_ratio": 0.0,
            "total_iv_files": 0,
        },
        "materials": [],
        "device_types": {},
        "heatmap": None,
        "histograms": {"vset": {"bins": [], "counts": []}, "vreset": {"bins": [], "counts": []}, "ratio": {"bins": [], "counts": []}},
    }

    if has_sqlite:
        try:
            from science_cli.library.memristor.db import (
                close_db,
                open_db,
                query_files,
                query_materials,
            )

            conn = open_db(project_path)

            # Get unique materials first from files table for this protocol!
            materials_cursor = conn.execute(
                "SELECT DISTINCT material FROM files WHERE protocol = ? AND material IS NOT NULL ORDER BY material",
                (protocol_name,)
            )
            all_materials = [row["material"] for row in materials_cursor.fetchall()]

            if not material_filter and all_materials:
                material_filter = all_materials[0]

            files = query_files(conn, protocol=protocol_name, material=material_filter if material_filter else None)
            materials_rows = query_materials(conn, protocol=protocol_name)

            close_db(conn)

            # Compute dynamic grid dimensions from actual data
            all_rs: set[int] = set()
            all_cs: set[int] = set()
            for f in files:
                r, c = f.get("row"), f.get("col")
                if r is not None:
                    all_rs.add(r)
                if c is not None:
                    all_cs.add(c)
            for m in materials_rows:
                r, c = m.get("row"), m.get("col")
                if r is not None:
                    all_rs.add(r)
                if c is not None:
                    all_cs.add(c)
            rows = max(6, max(all_rs)) if all_rs else rows
            cols = max(6, max(all_cs)) if all_cs else cols

            # Build device_type lookup: (row, col) -> type
            type_lookup: dict[tuple[int, int], str] = {}
            for m in materials_rows:
                type_lookup[(m["row"], m["col"])] = m.get("device_type", "non-volatile")
            for f in files:
                r, c = f.get("row"), f.get("col")
                if r is not None and c is not None:
                    if (r, c) not in type_lookup:
                        mat_lower = f.get("material", "").lower()
                        if "cu-c-pda" in mat_lower:
                            type_lookup[(r, c)] = "volatile"
                        elif "ta-pda" in mat_lower:
                            type_lookup[(r, c)] = "non-volatile"
                        else:
                            type_lookup[(r, c)] = "non-volatile"

            # Build material lookup: (row, col) -> material
            mat_lookup: dict[tuple[int, int], str] = {}
            for m in materials_rows:
                r, c = m.get("row"), m.get("col")
                if r is not None and c is not None:
                    mat_lookup[(r, c)] = m.get("material", "unknown")
            for f in files:
                r, c = f.get("row"), f.get("col")
                if r is not None and c is not None:
                    mat_lookup[(r, c)] = f.get("material", "unknown")

            # Build per-cell analysis from files
            cell_data: dict[tuple[int, int], dict] = {}
            for f in files:
                r, c = f.get("row"), f.get("col")
                if r is None or c is None:
                    continue
                key = (r, c)
                if key not in cell_data:
                    cell_data[key] = {
                        "v_set": [], "v_reset": [], "ratio": [],
                        "switching": False, "n_files": 0,
                    }
                cell_data[key]["n_files"] += 1

                vs = f.get("v_set")
                vr = f.get("v_reset")
                rat = f.get("on_off_ratio")
                conf = f.get("compliance_confidence")

                if vs is not None:
                    cell_data[key]["v_set"].append(vs)
                if vr is not None:
                    cell_data[key]["v_reset"].append(vr)
                if rat is not None and rat > 0:
                    cell_data[key]["ratio"].append(rat)
                if conf == "high":
                    cell_data[key]["switching"] = True

            # Aggregate KPI values
            all_vset: list[float] = []
            all_vreset: list[float] = []
            all_ratio: list[float] = []
            switching_count = 0
            measured_count = 0

            # Build grid data
            grid_data: list[list] = []
            grid_meta: list[list] = []

            for r in range(rows):
                row_data: list = []
                row_meta: list = []
                for c in range(cols):
                    cd = cell_data.get((r + 1, c + 1))
                    if not cd:
                        row_data.append(None)
                        row_meta.append({
                            "cell": f"R{r + 1}C{c + 1}",
                            "material": mat_lookup.get((r + 1, c + 1), "unknown"),
                            "n_files": 0,
                            "status": "Unmeasured",
                            "v_set": 0, "v_reset": 0, "ratio": 0,
                            "device_type": type_lookup.get((r + 1, c + 1), "unknown"),
                        })
                        continue

                    measured_count += 1
                    switching = cd["switching"]

                    # Per-cell aggregates
                    def _median(vals):
                        if not vals:
                            return None
                        sv = sorted(vals)
                        n = len(sv)
                        return sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2

                    med_vset = _median(cd["v_set"])
                    med_vreset = _median(cd["v_reset"])
                    med_ratio = _median(cd["ratio"])

                    if med_vset is not None:
                        all_vset.append(abs(med_vset))
                    if med_vreset is not None:
                        all_vreset.append(abs(med_vreset))
                    if med_ratio is not None:
                        all_ratio.append(med_ratio)
                    if switching:
                        switching_count += 1

                    val = None
                    if metric == "ratio":
                        val = round(med_ratio, 1) if med_ratio else None
                    elif metric == "vset":
                        val = round(med_vset, 2) if med_vset and switching else None
                    elif metric == "vreset":
                        val = round(med_vreset, 2) if med_vreset and switching else None
                    elif metric == "files":
                        val = cd["n_files"]
                    elif metric == "yield":
                        val = 100 if switching else 0
                    else:
                        val = round(med_ratio, 1) if med_ratio else None

                    row_data.append(val)
                    row_meta.append({
                        "cell": f"R{r + 1}C{c + 1}",
                        "material": mat_lookup.get((r + 1, c + 1), "unknown"),
                        "n_files": cd["n_files"],
                        "status": "Active Switching" if switching else "Non-Switching",
                        "v_set": round(med_vset, 2) if med_vset else 0,
                        "v_reset": round(med_vreset, 2) if med_vreset else 0,
                        "ratio": round(med_ratio, 1) if med_ratio else 0,
                        "device_type": type_lookup.get((r + 1, c + 1), "non-volatile"),
                    })

                grid_data.append(row_data)
                grid_meta.append(row_meta)

            # Aggregate medians
            def _med(vals):
                if not vals:
                    return 0.0
                sv = sorted(vals)
                n = len(sv)
                if n % 2:
                    return round(sv[n // 2], 2)
                return round((sv[n // 2 - 1] + sv[n // 2]) / 2, 2)

            # Histograms
            h_vset = _bin_1d(sorted(all_vset), 0.5, 3.0, 8) if all_vset else {"bins": [], "counts": []}
            h_vreset = _bin_1d(sorted(all_vreset), 0.5, 2.5, 8) if all_vreset else {"bins": [], "counts": []}
            h_ratio = _bin_1d(sorted(all_ratio), 0, 1000, 8) if all_ratio else {"bins": [], "counts": []}

            # Device type breakdown
            type_counts: dict[str, int] = {}
            for t in type_lookup.values():
                type_counts[t] = type_counts.get(t, 0) + 1

            # Unique materials (computed from files table initially)
            unique_materials = all_materials

            result["device"] = {
                "rows": rows, "cols": cols,
                "label": protocol_name,
            }
            result["aggregate"] = {
                "total_cells": rows * cols,
                "measured_cells": measured_count,
                "switching_count": switching_count,
                "yield_pct": round(switching_count / max(1, measured_count) * 100, 1),
                "median_vset": _med(all_vset),
                "median_vreset": _med(all_vreset),
                "median_ratio": _med(all_ratio),
                "total_iv_files": sum(cd["n_files"] for cd in cell_data.values()),
            }
            result["materials"] = unique_materials
            result["device_types"] = type_counts
            result["heatmap"] = {
                "rows": rows, "cols": cols,
                "metric": metric,
                "data": grid_data,
                "metadata": grid_meta,
            }
            result["histograms"] = {
                "vset": h_vset,
                "vreset": h_vreset,
                "ratio": h_ratio,
            }

            return result

        except Exception:
            # Fall through to cache-based approach
            pass

    # ── SQLite unavailable: fall back to analysis_data.json cache ──
    cache = _read_analysis_cache(project_path)
    if not cache:
        return result

    # Use existing cache-based heatmap + summary logic
    proto = next(
        (p for p in cache.get("protocols", []) if p["name"] == protocol_name),
        None,
    )
    if not proto:
        return result

    hm = _heatmap_from_cache(project_path, protocol_name, metric, material_filter, cache)
    summary = get_protocol_summary(project_path, protocol_name)
    hists = get_histograms(project_path, protocol_name)

    result["aggregate"] = summary.get("aggregate", result["aggregate"])
    result["device"] = summary.get("device", result["device"])
    result["materials"] = summary.get("materials", [])
    result["heatmap"] = hm
    result["histograms"] = hists

    return result


def get_gallery_data(
    project_path: Path,
) -> dict:
    plots = []
    protocols_set: set[str] = set()
    steps_set: set[str] = set()
    techniques_set: set[str] = set()
    materials_set: set[str] = set()

    proto_dir = project_path / "protocol"
    if proto_dir.exists():
        for protocol_sub in sorted(proto_dir.iterdir()):
            if not protocol_sub.is_dir() or protocol_sub.name.startswith("."):
                continue

            proto_name = protocol_sub.name
            protocols_set.add(proto_name)

            for step_sub in sorted(protocol_sub.iterdir()):
                if not step_sub.is_dir() or step_sub.name.startswith("."):
                    continue

                step_name = step_sub.name
                steps_set.add(step_name)

                results_dir = step_sub / "results"
                if not results_dir.exists():
                    continue

                for img in sorted(results_dir.iterdir()):
                    if img.suffix.lower() not in (".png", ".pdf", ".svg"):
                        continue

                    pdf_path = None
                    png_path = None
                    img_path = f"protocol/{proto_name}/{step_name}/results/{img.name}"

                    if img.suffix.lower() == ".png":
                        png_path = img_path
                        pdf_candidate = results_dir / f"{img.stem}.pdf"
                        if pdf_candidate.exists():
                            pdf_path = (
                                f"protocol/{proto_name}/{step_name}/results/"
                                f"{pdf_candidate.name}"
                            )
                        else:
                            pdf_path = img_path
                    elif img.suffix.lower() == ".pdf":
                        pdf_path = img_path
                        png_candidate = results_dir / f"{img.stem}.png"
                        if png_candidate.exists():
                            png_path = (
                                f"protocol/{proto_name}/{step_name}/results/"
                                f"{png_candidate.name}"
                            )
                    elif img.suffix.lower() == ".svg":
                        pdf_path = img_path
                        png_path = img_path

                    st = img.stat()
                    generated_at = datetime.fromtimestamp(
                        st.st_mtime, tz=timezone.utc
                    ).isoformat()

                    title = f"{img.stem.replace('_', ' ').title()}"

                    plots.append({
                        "id": f"plot_{len(plots) + 1:03d}",
                        "plot_path": pdf_path or img_path,
                        "thumbnail_path": png_path or pdf_path or img_path,
                        "data_files": [],
                        "protocol": proto_name,
                        "step": step_name,
                        "technique": "iv-sweep",
                        "device": "",
                        "theme": "",
                        "generated_at": generated_at,
                        "title": title,
                        "flags": {"xlabel": "", "ylabel": ""},
                    })

    return {
        "plots": plots[:50],
        "filters": {
            "protocols": sorted(protocols_set),
            "steps": sorted(steps_set),
            "techniques": sorted(techniques_set),
            "materials": sorted(materials_set),
        },
    }
