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
        return None

    proj = get_current_project_path()
    if proj:
        return proj

    sess = load_session()
    name = sess.get("last_project", "")
    if name:
        root = Path.home() / "workspace" / "projects" / "active_projects"
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


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


def _scan_protocol_dirs(
    project_path: Path,
) -> list[dict]:
    proto_dir = project_path / "protocol"
    if not proto_dir.exists():
        return []

    protocols = []
    for sub in sorted(proto_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue

        steps = []
        for entry in sorted(sub.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                steps.append(entry.name)

        if not steps:
            continue

        csv_count = 0
        for sdir in steps:
            sd = sub / sdir
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
    match = re.match(r"R(\d+)C(\d+)", cell_id, re.IGNORECASE)
    if not match:
        return {"error": f"invalid cell_id '{cell_id}' — expected R<n>C<m>"}

    row = int(match.group(1)) - 1
    col = int(match.group(2)) - 1

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
            pattern = rf"r{row}[c_\-]c{col}"
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
                    sweeps.append({
                        "label": f"Sweep #{len(sweeps) + 1:02d}",
                        "voltage": voltages,
                        "current": currents,
                        "v_set": v_set,
                        "v_reset": v_reset,
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


def get_protocol_files(
    project_path: Path,
    protocol_name: str,
) -> dict:
    proto_dir = project_path / "protocol" / protocol_name
    if not proto_dir.exists():
        return {"error": f"protocol '{protocol_name}' not found", "steps": []}

    steps = []
    for step_sub in sorted(proto_dir.iterdir()):
        if not step_sub.is_dir() or step_sub.name.startswith("."):
            continue

        results_dir = step_sub / "results"
        files = []
        if results_dir.exists():
            for f in sorted(results_dir.iterdir()):
                if f.suffix.lower() in (".png", ".pdf", ".svg"):
                    files.append({
                        "name": f.name,
                        "path": f"protocol/{protocol_name}/{step_sub.name}/results/{f.name}",
                        "type": f.suffix.lower().lstrip("."),
                        "size": f.stat().st_size,
                    })

        steps.append({
            "name": step_sub.name,
            "files": files,
        })

    return {"protocol": protocol_name, "steps": steps}


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
