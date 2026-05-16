"""Self-contained dark-themed interactive dashboard for memristor crossbar characterization.

Reads raw IV CSV data, extracts switching parameters, and generates a
self-contained ``dashboard.html`` with a dark-themed interactive Plotly layout.

Works with ``file://`` protocol — no web server required.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  Data Collection (Phase 1 — IV-driven)
# ════════════════════════════════════════════════════════════════


def _collect_device_data(config, results_dir: Path) -> dict:
    """Collect all IV data from config, extract parameters per device.

    Returns a dict with:
      - per_device: {(row, col): {row, col, material_key, v_set, v_reset,
          ratio, switching_detected, n_files, files: [...raw data...]}}
      - all_vset: list of all per-file V_set values
      - all_vreset: list of all per-file V_reset values
      - all_ratios: list of all per-file ON/OFF ratio values
      - total_iv_files: int
      - switching_count: int
      - total_measured_devices: int
    """
    from science_cli.memristor.plotting import read_iv_csv
    from science_cli.memristor.switching import extract_iv_parameters
    from science_cli.memristor.device import extract_material_batch

    data_dir = results_dir.parent
    per_device: dict[tuple, dict] = {}
    all_vset: list[float] = []
    all_vreset: list[float] = []
    all_ratios: list[float] = []
    total_iv_files = 0

    for pt, fe in config.get_all_files("iv"):
        csv_path = data_dir / fe.file
        if not csv_path.exists():
            logger.warning(f"Raw data file not found, skipping: {csv_path}")
            continue

        try:
            voltage, current, _info = read_iv_csv(csv_path)
            params = extract_iv_parameters(voltage, current)
        except Exception:
            logger.warning(
                f"Skipping unreadable file: {fe.file}", exc_info=True,
            )
            continue

        # Extract material+batch key
        mb = extract_material_batch(fe.file)
        if mb:
            mat_name, batch = mb
            mat_key = f"{mat_name}({batch})" if batch else mat_name
        else:
            mat_key = "unknown"

        key = (pt.row, pt.col, mat_key)
        if key not in per_device:
            per_device[key] = {
                "row": pt.row,
                "col": pt.col,
                "material_key": mat_key,
                "v_set_values": [],
                "v_reset_values": [],
                "ratio_values": [],
                "switching_detected": False,
                "files": [],
            }

        device = per_device[key]
        device["files"].append({
            "voltage": voltage.tolist(),
            "current": current.tolist(),
            "v_set": params["v_set"],
            "v_reset": params["v_reset"],
            "i_set": params.get("i_set"),
            "i_reset": params.get("i_reset"),
            "ratio": params["on_off_ratio"],
        })
        total_iv_files += 1

        if params["switching_detected"]:
            device["switching_detected"] = True
        if params["v_set"] is not None:
            device["v_set_values"].append(float(params["v_set"]))
            all_vset.append(float(params["v_set"]))
        if params["v_reset"] is not None:
            device["v_reset_values"].append(float(params["v_reset"]))
            all_vreset.append(float(params["v_reset"]))
        if params["on_off_ratio"] is not None:
            device["ratio_values"].append(float(params["on_off_ratio"]))
            all_ratios.append(float(params["on_off_ratio"]))

    # Compute per-device medians
    for key, device in per_device.items():
        device["v_set"] = (
            float(np.median(device["v_set_values"]))
            if device["v_set_values"]
            else None
        )
        device["v_reset"] = (
            float(np.median(device["v_reset_values"]))
            if device["v_reset_values"]
            else None
        )
        device["ratio"] = (
            float(np.median(device["ratio_values"]))
            if device["ratio_values"]
            else None
        )
        device["n_files"] = len(device["files"])

    switching_count = sum(
        1 for d in per_device.values() if d["switching_detected"]
    )

    return {
        "per_device": per_device,
        "all_vset": all_vset,
        "all_vreset": all_vreset,
        "all_ratios": all_ratios,
        "total_iv_files": total_iv_files,
        "switching_count": switching_count,
        "total_measured_devices": len(per_device),
    }


def _collect_device_data_from_sqlite(config, results_dir: Path, db_files: list[dict]) -> dict:
    """Collect IV data from SQLite cache (pre-computed analysis).

    Uses v_set, v_reset, on_off_ratio from the files table.
    Falls back to CSV reading for files that don't have analysis values.
    """
    from science_cli.memristor.plotting import read_iv_csv
    from science_cli.memristor.device import extract_material_batch

    data_dir = results_dir.parent
    per_device: dict[tuple[int, int], dict] = {}
    all_vset: list[float] = []
    all_vreset: list[float] = []
    all_ratios: list[float] = []
    total_iv_files = 0

    for fentry in db_files:
        step = fentry.get("step", "")
        filename = fentry.get("filename", "")
        material = fentry.get("material", "unknown")
        row = fentry.get("row")
        col = fentry.get("col")

        if row is None or col is None:
            continue

        csv_path = data_dir / filename
        if not csv_path.exists():
            csv_path = data_dir.parent / step / filename
        if not csv_path.exists():
            continue

        # Try to read CSV for overlay data
        try:
            voltage, current, _info = read_iv_csv(str(csv_path))
        except Exception:
            continue

        # Use pre-computed analysis from SQLite
        v_set = fentry.get("v_set")
        v_reset = fentry.get("v_reset")
        ratio = fentry.get("on_off_ratio")
        switching = v_set is not None or v_reset is not None

        # Compute i_set/i_reset on-the-fly from voltage/current
        i_set = fentry.get("i_set")
        i_reset = fentry.get("i_reset")
        if i_set is None and v_set is not None and voltage is not None:
            idx = int(np.argmin(np.abs(voltage - v_set))) if len(voltage) else -1
            i_set = float(current[idx]) if idx >= 0 else None
        if i_reset is None and v_reset is not None and voltage is not None:
            r_abs = abs(v_reset)
            idx = int(np.argmin(np.abs(np.abs(voltage) - r_abs))) if len(voltage) else -1
            i_reset = float(current[idx]) if idx >= 0 else None

        # Extract material+batch
        mb = extract_material_batch(filename)
        if mb:
            mat_name, batch = mb
            mat_key = f"{mat_name}({batch})" if batch else mat_name
        else:
            mat_key = material

        key = (row, col, mat_key)
        if key not in per_device:
            per_device[key] = {
                "row": row,
                "col": col,
                "material_key": mat_key,
                "v_set_values": [],
                "v_reset_values": [],
                "ratio_values": [],
                "switching_detected": False,
                "files": [],
            }

        device = per_device[key]
        device["files"].append({
            "voltage": voltage.tolist(),
            "current": current.tolist(),
            "v_set": v_set,
            "v_reset": v_reset,
            "i_set": i_set,
            "i_reset": i_reset,
            "ratio": ratio,
        })
        total_iv_files += 1

        if switching:
            device["switching_detected"] = True
        if v_set is not None:
            device["v_set_values"].append(float(v_set))
            all_vset.append(float(v_set))
        if v_reset is not None:
            device["v_reset_values"].append(float(v_reset))
            all_vreset.append(float(v_reset))
        if ratio is not None:
            device["ratio_values"].append(float(ratio))
            all_ratios.append(float(ratio))

    # Compute per-device medians
    for key, device in per_device.items():
        device["v_set"] = (
            float(np.median(device["v_set_values"]))
            if device["v_set_values"] else None
        )
        device["v_reset"] = (
            float(np.median(device["v_reset_values"]))
            if device["v_reset_values"] else None
        )
        device["ratio"] = (
            float(np.median(device["ratio_values"]))
            if device["ratio_values"] else None
        )
        device["n_files"] = len(device["files"])

    switching_count = sum(1 for d in per_device.values() if d["switching_detected"])

    return {
        "per_device": per_device,
        "all_vset": all_vset,
        "all_vreset": all_vreset,
        "all_ratios": all_ratios,
        "total_iv_files": total_iv_files,
        "switching_count": switching_count,
        "total_measured_devices": len(per_device),
    }


def _compute_aggregate(collection: dict, config) -> dict:
    """Compute aggregate statistics from collected data."""
    all_vset = collection["all_vset"]
    all_vreset = collection["all_vreset"]
    all_ratios = collection["all_ratios"]
    per_device = collection["per_device"]

    measured = collection["total_measured_devices"]
    switching_count = collection["switching_count"]

    return {
        "total_cells": config.device.total_cells,
        "measured_cells": config.measured_cells,
        "total_iv_files": collection["total_iv_files"],
        "median_vset": round(float(np.median(all_vset)), 3) if all_vset else None,
        "median_vreset": round(float(np.median(all_vreset)), 3) if all_vreset else None,
        "median_ratio": float(np.median(all_ratios)) if all_ratios else None,
        "yield_pct": round((switching_count / measured * 100.0), 1) if measured > 0 else 0.0,
        "n_devices_with_switching": switching_count,
        "n_devices_measured": measured,
    }


def _build_histogram_data(collection: dict) -> dict:
    """Build histogram bin/count data for Vset, Vreset, Ratio distributions."""
    result = {}

    for label, values in [
        ("vset", collection["all_vset"]),
        ("vreset", collection["all_vreset"]),
        ("ratio", collection["all_ratios"]),
    ]:
        if not values:
            result[label] = {"bins": [], "counts": []}
            continue
        n_bins = min(30, max(5, len(values) // 3))
        counts, bin_edges = np.histogram(values, bins=n_bins)
        result[label] = {
            "bins": bin_edges.tolist(),
            "counts": counts.tolist(),
        }

    return result


def _build_heatmap_matrix(config, per_device: dict) -> dict:
    """Build a 2D matrix of per-cell values for the heatmap."""
    rows = config.device.rows
    cols = config.device.cols

    # Collect materials at each cell for the selector
    cell_materials: dict[tuple[int, int], list[str]] = {}
    for (r, c, mat), dev in per_device.items():
        cell_materials.setdefault((r, c), []).append(mat)

    matrix = []
    for r in range(rows):
        row_data = []
        for c in range(cols):
            mats = cell_materials.get((r, c))
            if mats:
                # Use the first material at this cell
                first_dev = per_device.get((r, c, mats[0]))
                if first_dev:
                    row_data.append({
                        "v_set": first_dev["v_set"],
                        "v_reset": first_dev["v_reset"],
                        "ratio": first_dev["ratio"],
                        "switching": first_dev["switching_detected"],
                        "material": first_dev["material_key"],
                        "n_files": first_dev["n_files"],
                        "failed": not first_dev["switching_detected"],
                        "materials": mats,
                    })
                else:
                    row_data.append(None)
            else:
                row_data.append(None)
        matrix.append(row_data)

    return {"rows": rows, "cols": cols, "matrix": matrix, "all_materials": sorted(set(m for (r, c, m) in per_device))}


# ════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════


def generate_dashboard(
    config,
    results_dir: Path,
    output_path: str | Path,
) -> Path:
    """Generate a self-contained dark-themed interactive Plotly HTML dashboard.
    
    Reads from SQLite cache first for analysis data, falls back to
    raw CSV reading if SQLite data is not available.
    
    Config is resolved from the global registry — technique configs,
    device configs, and grammar patterns are loaded from the 4-tier
    config system (hardcoded → global → project → protocol).

    Args:
        config: DeviceConfig instance loaded from devices.yaml.
        results_dir: Directory containing (or sibling to) raw data files.
            Raw files are resolved as ``results_dir.parent / fe.file``.
        output_path: Where to write the HTML file.

    Returns:
        Path to the generated ``dashboard.html`` file.

    Raises:
        ValueError: If no IV files are found or no data could be collected.
    """
    # ── Try SQLite fast-read path ──
    from science_cli.core.project import get_current_project_path
    from science_cli.memristor.db import open_db, query_files, close_db
    
    proj = get_current_project_path()
    sqlite_available = False
    sqlite_data = None
    
    if proj:
        try:
            db_path = proj / f"{proj.name}.db"
            if db_path.exists():
                conn = open_db(proj)
                db_files = query_files(conn)
                close_db(conn)
                if db_files and len(db_files) > 0:
                    sqlite_available = True
                    sqlite_data = db_files
        except Exception:
            pass
    
    # ── Phase 1: Collect data (SQLite or CSV) ──
    if sqlite_available:
        collection = _collect_device_data_from_sqlite(config, results_dir, sqlite_data)
    else:
        collection = _collect_device_data(config, results_dir)

    if not collection["per_device"]:
        raise ValueError(
            "No IV data files found or none could be read successfully. "
            "Check that devices.yaml has IV entries and raw data files "
            "exist in the step directory."
        )

    # ── Compute aggregates and histograms ──
    aggregate = _compute_aggregate(collection, config)
    histograms = _build_histogram_data(collection)
    heatmap = _build_heatmap_matrix(config, collection["per_device"])

    # ── Build per-device dictionary, grouped by material ──
    all_materials: set[str] = set()
    per_mat_devices: dict[str, dict] = {}
    per_mat_iv: dict[str, dict] = {}
    for (row, col, mat_key), device in collection["per_device"].items():
        all_materials.add(mat_key)
        if mat_key not in per_mat_devices:
            per_mat_devices[mat_key] = {}
            per_mat_iv[mat_key] = {}
        cell_id = f"R{row + 1}C{col + 1}"
        per_mat_devices[mat_key][cell_id] = {
            "row": row,
            "col": col,
            "material": mat_key,
            "v_set": device["v_set"],
            "v_reset": device["v_reset"],
            "ratio": device["ratio"],
            "switching": device["switching_detected"],
            "n_files": device["n_files"],
        }
        per_mat_iv[mat_key][cell_id] = [
            {
                "voltage": f["voltage"],
                "current": f["current"],
                "v_set": f["v_set"],
                "v_reset": f["v_reset"],
                "i_set": f.get("i_set"),
                "i_reset": f.get("i_reset"),
                "label": f"#{i + 1:02d}",
            }
            for i, f in enumerate(device["files"])
        ]

    # Write per-material JS data files
    results_dir = Path(output_path).parent
    all_mat_keys = sorted(all_materials)
    for mat_key in all_mat_keys:
        data_js = f"window._MAT_DATA=window._MAT_DATA||{{}};window._MAT_DATA[{json.dumps(mat_key)}]={{devices:{json.dumps(per_mat_devices[mat_key], separators=(',',':'))},iv:{json.dumps(per_mat_iv[mat_key], separators=(',',':'))}}};"
        data_path = results_dir / f"data_{mat_key.replace('(','').replace(')','').replace('-','_')}.js"
        data_path.write_text(data_js, encoding="utf-8")
        logger.info(f"Data chunk written: {data_path}")

    # ── Build HTML (main shell only — data loaded dynamically) ──
    device_label = config.device.label or config.device.id or "Memristor Device"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = _build_html(
        device_label=device_label,
        device_id=config.device.id,
        rows=config.device.rows,
        cols=config.device.cols,
        aggregate=aggregate,
        heatmap=heatmap,
        histograms=histograms,
        mat_keys=all_mat_keys,
        date_str=date_str,
    )

    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written to {out}")
    return out


# ════════════════════════════════════════════════════════════════
#  HTML Assembly
# ════════════════════════════════════════════════════════════════


def _build_html(
    device_label: str,
    device_id: str,
    rows: int,
    cols: int,
    aggregate: dict,
    heatmap: dict,
    histograms: dict,
    mat_keys: list[str],
    date_str: str,
) -> str:
    """Assemble the full self-contained HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{device_label} — Memristor Crossbar Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body>
<div id="app">

  <!-- ══════════════ SIDEBAR ══════════════ -->
  <nav id="sidebar">
    <!-- Logo -->
    <div class="sb-logo">
      <div class="sb-logo-title">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="1" y="1" width="6" height="6" rx="1" stroke="#00d4ff" stroke-width="1.2"/>
          <rect x="9" y="1" width="6" height="6" rx="1" stroke="#00d4ff" stroke-width="1.2" opacity="0.6"/>
          <rect x="1" y="9" width="6" height="6" rx="1" stroke="#00d4ff" stroke-width="1.2" opacity="0.6"/>
          <rect x="9" y="9" width="6" height="6" rx="1" stroke="#00d4ff" stroke-width="1.2"/>
          <line x1="4" y1="4" x2="12" y2="12" stroke="#00d4ff" stroke-width="0.8" opacity="0.4"/>
        </svg>
        Memristor Lab
      </div>
      <div class="sb-logo-sub">{device_id} · v2.4.1</div>
    </div>

    <!-- Navigation -->
    <div class="sb-section">
      <div class="sb-section-title">Overview</div>
    </div>

    <!-- Filters -->
    <div class="sb-section">
      <div class="sb-section-title">Filters</div>
      <div class="filter-group">
        <div class="filter-label">Cycle Range</div>
        <div class="range-row"><span>1</span><span id="cycle-val">All</span></div>
        <input type="range" id="cycle-range" min="1" max="200" value="200" oninput="document.getElementById('cycle-val').textContent=this.value">
      </div>
      <div class="filter-group">
        <div class="filter-label">Compliance (A)</div>
        <select class="filter-select">
          <option>All</option>
          <option>1 mA</option>
          <option>100 uA</option>
          <option>10 uA</option>
        </select>
      </div>
      <div style="margin-top:8px">
        <div class="toggle-row"><span>Highlight Outliers</span><label class="toggle"><input type="checkbox" id="toggle-outliers"><span class="toggle-slider"></span></label></div>
      </div>
    </div>

    <!-- Review Queue -->
    <div class="sb-section">
      <div class="sb-section-title">Review Queue <span style="color:var(--orange);margin-left:4px" class="mono">0</span></div>
      <div class="review-scroll" id="review-list">
        <div style="font-size:10px;color:var(--text-dim);padding:8px 0">No devices flagged for review.</div>
      </div>
    </div>

    <!-- Summary -->
    <div class="sb-section">
      <div class="sb-section-title">Summary</div>
      <div class="stat-row"><span class="stat-key">Total Cells</span><span class="stat-val" id="sum-total">{aggregate["total_cells"]}</span></div>
      <div class="stat-row"><span class="stat-key">Measured</span><span class="stat-val green" id="sum-measured">{aggregate["measured_cells"]}</span></div>
      <div class="stat-row"><span class="stat-key">Switching</span><span class="stat-val green" id="sum-switching">{aggregate["n_devices_with_switching"]}</span></div>
      <div class="stat-row"><span class="stat-key">IV Files</span><span class="stat-val" id="sum-files">{aggregate["total_iv_files"]}</span></div>
    </div>

    <!-- Quick Actions -->
    <div class="sb-section" style="padding-bottom:16px">
      <div class="sb-section-title">Quick Actions</div>
      <button class="qa-btn">Open Raw Data</button>
      <button class="qa-btn">Export Device Report</button>
      <button class="qa-btn">Mark for Review</button>
      <button class="qa-btn danger">Exclude Device</button>
    </div>
  </nav>

  <!-- ══════════════ MAIN ══════════════ -->
  <div id="main">
    <!-- HEADER -->
    <header id="header">
      <div>
        <div class="header-title" id="header-title">{rows}x{cols} Crossbar</div>
        <div class="header-subtitle" id="header-subtitle">IV Sweep Characterization</div>
      </div>
      <div class="header-sep"></div>
      <div class="header-label">
        <span>Material</span>
        <select class="header-select" id="header-material"><option>All</option></select>
      </div>
      <div class="header-label">
        <span>Matrix</span>
        <select class="header-select"><option>{rows}x{cols}</option></select>
      </div>
      <div class="header-spacer"></div>
      <div class="device-badge">
        <div class="badge-dot"></div>
        <span class="badge-text" id="badge-count">{aggregate["measured_cells"]} Devices</span>
      </div>
    </header>

    <!-- CONTENT -->
    <div id="content">

      <!-- KPI ROW -->
      <div class="kpi-row">
        <div class="kpi-card" style="--kpi-color: var(--cyan)">
          <div class="kpi-header"><div class="kpi-label">Median V<sub>set</sub></div><div class="kpi-badge">IV Sweep</div></div>
          <div class="kpi-val" id="kpi-vset">{_fmt_kpi_val(aggregate["median_vset"])} <span style="font-size:13px;opacity:0.7">V</span></div>
          <div class="kpi-sub">n = {aggregate["n_devices_measured"]}</div>
        </div>
        <div class="kpi-card" style="--kpi-color: var(--blue-bright)">
          <div class="kpi-header"><div class="kpi-label">Median V<sub>reset</sub></div><div class="kpi-badge">IV Sweep</div></div>
          <div class="kpi-val" id="kpi-vreset">{_fmt_kpi_val(aggregate["median_vreset"])} <span style="font-size:13px;opacity:0.7">V</span></div>
          <div class="kpi-sub">n = {aggregate["n_devices_measured"]}</div>
        </div>
        <div class="kpi-card" style="--kpi-color: var(--purple)">
          <div class="kpi-header"><div class="kpi-label">ON/OFF Ratio</div><div class="kpi-badge">Median</div></div>
          <div class="kpi-val" id="kpi-ratio">{_fmt_kpi_ratio(aggregate["median_ratio"])}</div>
          <div class="kpi-sub">n = {aggregate["n_devices_measured"]}</div>
        </div>
        <div class="kpi-card" style="--kpi-color: var(--green)">
          <div class="kpi-header"><div class="kpi-label">Yield</div><div class="kpi-badge">Switching</div></div>
          <div class="kpi-val" id="kpi-yield">{aggregate["yield_pct"]} <span style="font-size:13px;opacity:0.7">%</span></div>
          <div class="kpi-sub">{aggregate["n_devices_with_switching"]} / {aggregate["n_devices_measured"]} devices</div>
        </div>
      </div>

      <!-- MAIN ROW: Heatmap + IV Overlay -->
      <div class="main-row">

        <!-- HEATMAP -->
        <div class="panel-card heatmap-card">
          <div class="panel-header">
            <div class="panel-title">Crossbar Heatmap</div>
            <div class="panel-spacer"></div>
            <select id="heatmap-metric" style="background:var(--bg-card);border:1px solid var(--border);color:var(--text-primary);padding:1px 6px;border-radius:4px;font-size:10px;margin-right:6px">
              <option>ON/OFF Ratio</option>
              <option>Vset (V)</option>
              <option>Vreset (V)</option>
              <option>Yield (%)</option>
            </select>
            <label style="font-size:10px;color:var(--text-dim);display:flex;align-items:center;gap:4px;margin-right:6px;cursor:pointer">
              <input type="checkbox" id="toggle-log" checked style="accent-color:var(--accent)"> Log
            </label>
            <span class="panel-badge" id="heatmap-badge">ON/OFF Ratio</span>
          </div>
          <div class="panel-body" style="padding-top:6px">
            <div id="heatmap-plot" style="height:100%;width:100%;min-height:300px"></div>
            <div id="selected-device-info" style="margin-top:3px;padding:4px 8px;background:var(--bg-card2);border-radius:4px;border:1px solid var(--border);font-size:10px;line-height:1.5;min-height:18px">
              <span style="color:var(--text-dim)">Click a cell to select</span>
            </div>
          </div>
        </div>

        <!-- IV OVERLAY -->
        <div class="panel-card iv-card">
          <div class="panel-header">
            <div class="panel-title">Device Explorer</div>
            <span id="iv-device-badge" class="panel-badge">—</span>
            <div class="panel-spacer"></div>
            <!-- Overlay toggle + cycle nav -->
            <div style="display:flex;align-items:center;gap:8px;margin-right:8px">
              <label style="font-size:10px;color:var(--text-dim);display:flex;align-items:center;gap:4px;cursor:pointer">
                <input type="checkbox" id="toggle-overlay" checked style="accent-color:var(--accent)"> Overlay
              </label>
              <div id="cycle-nav" style="display:none;align-items:center;gap:3px">
                <button id="sweep-prev" style="padding:0 6px;cursor:pointer;background:var(--bg-surface);border:1px solid var(--border);color:var(--text-primary);border-radius:3px;font-size:11px;line-height:1.6">&#9664;</button>
                <select id="sweep-select" style="width:60px;background:var(--bg-surface);border:1px solid var(--border);color:var(--text-primary);padding:1px 2px;border-radius:3px;font-size:10px"></select>
                <button id="sweep-next" style="padding:0 6px;cursor:pointer;background:var(--bg-surface);border:1px solid var(--border);color:var(--text-primary);border-radius:3px;font-size:11px;line-height:1.6">&#9654;</button>
              </div>
            </div>
            <div class="tab-bar">
              <div class="tab active" onclick="switchTab('iv', this)">IV</div>
              <div class="tab" onclick="switchTab('params', this)">Params</div>
              <div class="tab" onclick="switchTab('evo', this)">Evo</div>
              <div class="tab" onclick="switchTab('raw', this)">Raw</div>
            </div>
          </div>
          <div class="panel-body" style="padding:0;flex:1;min-height:0">
            <div id="iv-plot" style="width:100%;height:100%;min-height:300px"></div>
            <div id="tab-placeholder" style="display:none;align-items:center;justify-content:center;color:var(--text-dim);font-size:12px;font-family:'DM Sans',sans-serif">No IV data available</div>
          </div>
        </div>

      </div>

      <!-- HISTOGRAM ROW -->
      <div class="hist-row">
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">V<sub>set</sub> Distribution</div>
            <div class="panel-badge">All Devices</div>
          </div>
          <div class="panel-body" style="padding:6px">
            <div id="hist-vset" style="height:170px"></div>
          </div>
        </div>
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">V<sub>reset</sub> Distribution</div>
            <div class="panel-badge">All Devices</div>
          </div>
          <div class="panel-body" style="padding:6px">
            <div id="hist-vreset" style="height:170px"></div>
          </div>
        </div>
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">ON/OFF Ratio Distribution</div>
            <div class="panel-badge">All Devices</div>
          </div>
          <div class="panel-body" style="padding:6px">
            <div id="hist-ratio" style="height:170px"></div>
          </div>
        </div>
      </div>

      <!-- TEMPORAL + CONFIDENCE ROW -->
      <div class="bottom-row">
        <!-- Cycle Evolution -->
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">Cycle Evolution</div>
            <span id="cycle-device-badge" class="panel-badge">—</span>
            <div class="panel-spacer"></div>
            <select class="ctrl-select">
              <option>Vset vs Cycle</option>
              <option>Vreset vs Cycle</option>
              <option>Ron vs Cycle</option>
            </select>
          </div>
          <div class="panel-body" style="padding:6px">
            <div id="cycle-plot" style="height:190px"></div>
            <div style="text-align:center;color:var(--text-dim);font-size:10px;padding:8px;font-family:'DM Sans',sans-serif">Cycle evolution analysis requires endurance cycling data.</div>
          </div>
        </div>

        <!-- Extraction Confidence -->
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">Extraction Confidence</div>
            <div class="panel-badge">All Devices</div>
          </div>
          <div class="panel-body" style="padding:6px">
            <div id="conf-plot" style="height:150px"></div>
            <div class="conf-stats">
              <div class="conf-stat-card"><div class="conf-stat-val" style="color:var(--green)" id="conf-valid">{aggregate["n_devices_with_switching"]}</div><div class="conf-stat-key">Valid</div></div>
              <div class="conf-stat-card"><div class="conf-stat-val" style="color:var(--yellow)">0</div><div class="conf-stat-key">Low Conf.</div></div>
              <div class="conf-stat-card"><div class="conf-stat-val" style="color:var(--red)">0</div><div class="conf-stat-key">Failed</div></div>
            </div>
            <div style="text-align:center;color:var(--text-dim);font-size:10px;padding:4px;font-family:'DM Sans',sans-serif">Extraction confidence analysis will be available in a future update.</div>
          </div>
        </div>
      </div>

      <!-- REVIEW TABLE -->
      <div class="panel-card">
        <div class="panel-header">
          <div class="panel-title">Low-Confidence Device Review</div>
          <div class="panel-badge" style="background:rgba(249,115,22,0.1);border-color:rgba(249,115,22,0.3);color:var(--orange)">0 Flagged</div>
          <div class="panel-spacer"></div>
          <select class="ctrl-select"><option>All Issues</option><option>Weak Vset</option><option>No Switching</option><option>High Noise</option></select>
        </div>
        <div class="panel-body" style="padding:20px 14px">
          <table class="review-table">
            <thead>
              <tr>
                <th>Device ID</th>
                <th>Issue</th>
                <th>Confidence</th>
                <th>Ext. Method</th>
                <th>Vset est.</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="review-tbody">
              <tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:16px;font-family:'DM Sans',sans-serif">No devices flagged for review. All confidence scores are acceptable.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /app -->

<script id="heatmap-data" type="application/json">
{json.dumps(heatmap, separators=(",", ":"))}
</script>
<script id="histogram-data" type="application/json">
{json.dumps(histograms, separators=(",", ":"))}
</script>
<script id="aggregate-data" type="application/json">
{json.dumps(aggregate, separators=(",", ":"))}
</script>
<script>
{_JS}
</script>
<script>
(function(){{
var mats = {json.dumps(mat_keys, separators=(",", ":"))};
window._MAT_KEYS = mats;
window._MAT_DATA = {{}};
var loaded = {{}};
window._loadMatData = function(mat) {{
  if (loaded[mat]) return Promise.resolve();
  return new Promise(function(resolve, reject) {{
    var key = mat.replace(/\\(/g,'').replace(/\\)/g,'').replace(/-/g,'_');
    var s = document.createElement('script');
    s.src = 'data_' + key + '.js';
    s.onload = function() {{ loaded[mat] = true; resolve(); }};
    s.onerror = function() {{ reject('Failed to load data for ' + mat); }};
    document.head.appendChild(s);
  }});
}};
}})();
</script>

</body>
</html>"""


# ════════════════════════════════════════════════════════════════
#  Cross-Protocol Dashboard (Sprint 3)
# ════════════════════════════════════════════════════════════════


def collect_cross_protocol_data(project_dir: Path, force: bool = False) -> dict:
    """Scan all <project>/protocol/*/devices.yaml, collect IV data across all protocols.

    Args:
        project_dir: Path to project root (contains protocol/ subdir).
        force: If True, re-analyze all files; otherwise use cached analysis_data.json.

    Returns:
        dict with keys: protocols, aggregate, generated_at, file_mtimes.
    """
    from science_cli.memristor.device import read_devices, extract_material_batch
    from science_cli.memristor.plotting import read_iv_csv
    from science_cli.memristor.switching import extract_iv_parameters

    results_dir = project_dir / "results"
    cache_path = results_dir / "analysis_data.json"

    # ── Check cache ──
    if not force and cache_path.exists():
        try:
            with open(cache_path) as fh:
                cached = json.load(fh)
            valid = True
            for rel_path, cached_mtime in cached.get("file_mtimes", {}).items():
                abs_p = project_dir / rel_path
                if not abs_p.exists():
                    valid = False
                    break
                try:
                    cur_mtime = abs_p.stat().st_mtime
                    if abs(cur_mtime - cached_mtime) > 0.1:
                        valid = False
                        break
                except OSError:
                    valid = False
                    break
            # Also check for new protocol directories
            proto_dir = project_dir / "protocol"
            cached_names = {p["name"] for p in cached.get("protocols", [])}
            if proto_dir.exists() and valid:
                for sub in proto_dir.iterdir():
                    if sub.is_dir() and sub.name not in cached_names:
                        if (sub / "devices.yaml").exists():
                            valid = False
                            break
            if valid:
                if "generated_at" not in cached:
                    cached["generated_at"] = datetime.now(timezone.utc).isoformat()
                return cached
        except Exception:
            logger.debug("Cache invalid or corrupt, rebuilding.", exc_info=True)

    # ── Full scan ──
    proto_dir = project_dir / "protocol"
    protocols_data: list[dict] = []
    all_vset: list[float] = []
    all_vreset: list[float] = []
    all_ratios: list[float] = []
    file_mtimes: dict[str, float] = {}

    if proto_dir.exists():
        for sub in sorted(proto_dir.iterdir()):
            if not sub.is_dir():
                continue
            config = read_devices(sub)
            if config is None:
                continue

            proto_name = sub.name
            devices: dict[str, dict] = {}

            for pt, fe in config.get_all_files("iv"):
                csv_path = config.resolve_file_path(sub, "iv", fe.file)
                if not csv_path.exists():
                    logger.warning(f"Skipping missing file: {csv_path}")
                    continue

                try:
                    voltage, current, _info = read_iv_csv(csv_path)
                    params = extract_iv_parameters(voltage, current)
                except Exception:
                    logger.warning(
                        f"Skipping unreadable file: {fe.file}", exc_info=True,
                    )
                    continue

                # Track mtime for cache invalidation
                try:
                    rel = str(csv_path.relative_to(project_dir))
                except ValueError:
                    rel = str(csv_path)
                file_mtimes[rel] = csv_path.stat().st_mtime

                # Extract material
                mb = extract_material_batch(fe.file)
                mat_key = f"{mb[0]}({mb[1]})" if mb and mb[1] else (
                    mb[0] if mb else "unknown"
                )

                cell_id = f"R{pt.row + 1}C{pt.col + 1}"
                if cell_id not in devices:
                    devices[cell_id] = {
                        "row": pt.row,
                        "col": pt.col,
                        "material": mat_key,
                        "v_set_values": [],
                        "v_reset_values": [],
                        "ratio_values": [],
                        "switching": False,
                        "n_files": 0,
                        "files": [],
                    }

                dev = devices[cell_id]
                dev["files"].append({
                    "voltage": voltage.tolist(),
                    "current": current.tolist(),
                    "v_set": params["v_set"],
                    "v_reset": params["v_reset"],
                    "ratio": params["on_off_ratio"],
                    "filename": fe.file,
                })
                dev["n_files"] += 1

                if params["switching_detected"]:
                    dev["switching"] = True
                if params["v_set"] is not None:
                    dev["v_set_values"].append(float(params["v_set"]))
                    all_vset.append(float(params["v_set"]))
                if params["v_reset"] is not None:
                    dev["v_reset_values"].append(float(params["v_reset"]))
                    all_vreset.append(float(params["v_reset"]))
                if params["on_off_ratio"] is not None:
                    dev["ratio_values"].append(float(params["on_off_ratio"]))
                    all_ratios.append(float(params["on_off_ratio"]))

            # Compute per-device medians
            for cell_id, dev in devices.items():
                dev["v_set"] = (
                    float(np.median(dev["v_set_values"]))
                    if dev["v_set_values"] else None
                )
                dev["v_reset"] = (
                    float(np.median(dev["v_reset_values"]))
                    if dev["v_reset_values"] else None
                )
                dev["ratio"] = (
                    float(np.median(dev["ratio_values"]))
                    if dev["ratio_values"] else None
                )
                # Keep files for IV overlay; drop intermediate lists
                del dev["v_set_values"]
                del dev["v_reset_values"]
                del dev["ratio_values"]

            # Track devices.yaml mtime
            yaml_p = sub / "devices.yaml"
            try:
                rel_y = str(yaml_p.relative_to(project_dir))
            except ValueError:
                rel_y = str(yaml_p)
            file_mtimes[rel_y] = yaml_p.stat().st_mtime

            switching_count = sum(1 for d in devices.values() if d["switching"])

            protocols_data.append({
                "name": proto_name,
                "device_label": config.device.label or config.device.id,
                "device_id": config.device.id,
                "rows": config.device.rows,
                "cols": config.device.cols,
                "row_labels": config.device.row_labels,
                "col_labels": config.device.col_labels,
                "devices": devices,
                "switching_count": switching_count,
                "total_devices": len(devices),
            })

    # ── Aggregate ──
    total_files = sum(
        sum(d["n_files"] for d in p["devices"].values())
        for p in protocols_data
    )
    total_devices = sum(p["total_devices"] for p in protocols_data)

    aggregate = {
        "total_files": total_files,
        "total_devices": total_devices,
        "total_protocols": len(protocols_data),
        "median_vset": round(float(np.median(all_vset)), 3) if all_vset else None,
        "median_vreset": round(float(np.median(all_vreset)), 3) if all_vreset else None,
        "median_ratio": float(np.median(all_ratios)) if all_ratios else None,
        "yield_pct": round(
            (sum(p["switching_count"] for p in protocols_data)
             / max(1, total_devices) * 100.0),
            1,
        ),
        "switching_count": sum(p["switching_count"] for p in protocols_data),
    }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocols": protocols_data,
        "aggregate": aggregate,
        "file_mtimes": file_mtimes,
    }

    # ── Persist cache ──
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as fh:
        json.dump(result, fh, indent=2, default=str)

    return result


def read_dashboard_data_sqlite(project_root: Path) -> Optional[dict]:
    """Read dashboard data from SQLite cache.

    Returns dict with keys: files, cells, or None if DB not available.
    """
    from science_cli.memristor.db import open_db, query_files, query_cells, close_db

    db_path = project_root / f"{project_root.name}.db"
    if not db_path.exists():
        return None

    try:
        conn = open_db(project_root)
        files = query_files(conn)
        cells = query_cells(conn)
        close_db(conn)
        return {"files": files, "cells": cells}
    except Exception:
        return None


def generate_cross_protocol_dashboard(
    project_dir: Path,
    output_path: str | Path,
    force: bool = False,
) -> Path:
    """Generate a project-level cross-protocol dashboard.

    Scans all protocols, collects data (with caching), generates HTML.

    Args:
        project_dir: Path to project root.
        output_path: Where to write the HTML file.
        force: If True, ignore cache and re-analyze all.

    Returns:
        Path to generated dashboard.html.

    Raises:
        ValueError: If no IV data could be collected from any protocol.
    """
    # Try SQLite first for fast reads
    if not force:
        sqlite_data = read_dashboard_data_sqlite(project_dir)
        if sqlite_data:
            logger.info("Using SQLite cache for dashboard data")
            # SQLite data is available but we still need IV raw data
            # for the overlay, so fall through to full collection.
            # The SQLite read provides a fast check — future
            # enhancements will use SQLite directly for dashboard
            # rendering without re-running the full analysis.

    data = collect_cross_protocol_data(project_dir, force=force)

    if not data.get("protocols"):
        raise ValueError(
            "No protocol data found. "
            "Ensure protocol/*/devices.yaml files exist with IV entries."
        )

    html = _build_cross_protocol_html(data)
    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    logger.info(f"Cross-protocol dashboard written to {out}")
    return out


def _build_cross_protocol_html(data: dict) -> str:
    """Assemble the full self-contained cross-protocol HTML document."""
    protocols = data["protocols"]
    aggregate = data["aggregate"]
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Build flat device / IV maps for JS ──
    cross_devices: dict[str, dict] = {}
    cross_iv: dict[str, list[dict]] = {}
    all_vset: list[float] = []
    all_vreset: list[float] = []
    all_ratios: list[float] = []
    materials_set: set[str] = set()

    for proto in protocols:
        for cell_id, dev in proto["devices"].items():
            key = f"{proto['name']}::{cell_id}"
            cross_devices[key] = {
                "row": dev["row"],
                "col": dev["col"],
                "material": dev["material"],
                "v_set": dev["v_set"],
                "v_reset": dev["v_reset"],
                "ratio": dev["ratio"],
                "switching": dev["switching"],
                "n_files": dev["n_files"],
                "protocol": proto["name"],
            }
            cross_iv[key] = [
                {
                    "voltage": f["voltage"],
                    "current": f["current"],
                    "v_set": f["v_set"],
                    "v_reset": f["v_reset"],
                    "label": f"#{i + 1:02d}",
                }
                for i, f in enumerate(dev.get("files", []))
            ]
            if dev.get("v_set") is not None:
                all_vset.append(dev["v_set"])
            if dev.get("v_reset") is not None:
                all_vreset.append(dev["v_reset"])
            if dev.get("ratio") is not None:
                all_ratios.append(dev["ratio"])
            materials_set.add(dev.get("material", "unknown"))

    mat_options = "".join(
        f'<option>{m}</option>' for m in sorted(materials_set)
    )
    proto_options = "".join(
        f'<option value="{p["name"]}">{p["name"]}</option>'
        for p in protocols
    )

    # ── Build heatmap matrices per protocol ──
    for proto in protocols:
        rows, cols = proto["rows"], proto["cols"]
        matrix = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                dev = proto["devices"].get(f"R{r + 1}C{c + 1}")
                if dev:
                    row_data.append({
                        "v_set": dev["v_set"],
                        "v_reset": dev["v_reset"],
                        "ratio": dev["ratio"],
                        "switching": dev["switching"],
                        "material": dev["material"],
                        "n_files": dev["n_files"],
                        "failed": not dev["switching"],
                    })
                else:
                    row_data.append(None)
            matrix.append(row_data)
        proto["heatmap_matrix"] = matrix

    protocols_json = json.dumps(protocols, separators=(",", ":"))
    aggregate_json = json.dumps(aggregate, separators=(",", ":"))
    cross_devices_json = json.dumps(cross_devices, separators=(",", ":"))
    cross_iv_json = json.dumps(cross_iv, separators=(",", ":"))
    all_vset_json = json.dumps(all_vset, separators=(",", ":"))
    all_vreset_json = json.dumps(all_vreset, separators=(",", ":"))
    all_ratios_json = json.dumps(all_ratios, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cross-Protocol Memristor Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
{_CSS}
/* Cross-protocol additions */
.proto-section {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
}}
.proto-section-header {{
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card2);
  border-bottom: 1px solid var(--border);
}}
.proto-section-title {{
  font-size: 13px; font-weight: 600; color: var(--cyan);
}}
.proto-section-sub {{
  font-size: 10px; color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
}}
.proto-section-body {{
  padding: 8px;
}}
.proto-section-body .js-plotly-plot {{
  height: 300px !important;
}}
.marker-toggle-row {{
  display: flex; gap: 16px; align-items: center;
  margin-bottom: 4px; padding: 0 12px;
}}
.marker-toggle-label {{
  font-size: 10px; color: var(--text-dim);
  display: flex; align-items: center; gap: 4px;
}}
.marker-toggle-label input[type=checkbox] {{
  accent-color: var(--cyan); cursor: pointer;
}}
</style>
</head>
<body>
<div id="cross-app">

  <!-- ═════════ HEADER ═════════ -->
  <header id="cross-header">
    <div class="header-title">Cross-Protocol Dashboard</div>
    <div class="header-sep"></div>
    <div class="header-label">
      <span>Protocol</span>
      <select class="header-select" id="proto-filter" onchange="onProtoFilter()">
        <option value="">All</option>
        {proto_options}
      </select>
    </div>
    <div class="header-label">
      <span>Material</span>
      <select class="header-select" id="material-filter" onchange="onMaterialFilter()">
        <option value="">All</option>
        {mat_options}
      </select>
    </div>
    <div class="header-label">
      <span>Generated</span>
      <select class="header-select"><option>{date_str}</option></select>
    </div>
    <div class="header-spacer"></div>
    <div class="search-box">
      <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" id="cross-search" placeholder="Search device..." oninput="onCrossSearch(this.value)">
    </div>
    <div class="device-badge">
      <div class="badge-dot"></div>
      <span class="badge-text" id="cross-badge">{aggregate["total_devices"]} Devices</span>
    </div>
  </header>

  <!-- ═════════ CONTENT ═════════ -->
  <div id="cross-content">

    <!-- KPI ROW -->
    <div class="kpi-row">
      <div class="kpi-card" style="--kpi-color: var(--cyan)">
        <div class="kpi-header"><div class="kpi-label">Total Files</div><div class="kpi-badge">All Protocols</div></div>
        <div class="kpi-val">{aggregate["total_files"]}</div>
        <div class="kpi-sub">{aggregate["total_protocols"]} protocols</div>
      </div>
      <div class="kpi-card" style="--kpi-color: var(--blue-bright)">
        <div class="kpi-header"><div class="kpi-label">Median V<sub>set</sub></div><div class="kpi-badge">All Protocols</div></div>
        <div class="kpi-val" id="kpi-vset">{_fmt_kpi_val(aggregate["median_vset"])} <span style="font-size:13px;opacity:0.7">V</span></div>
        <div class="kpi-sub">n = {aggregate["total_devices"]}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: var(--purple)">
        <div class="kpi-header"><div class="kpi-label">Median V<sub>reset</sub></div><div class="kpi-badge">All Protocols</div></div>
        <div class="kpi-val" id="kpi-vreset">{_fmt_kpi_val(aggregate["median_vreset"])} <span style="font-size:13px;opacity:0.7">V</span></div>
        <div class="kpi-sub">n = {aggregate["total_devices"]}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: var(--green)">
        <div class="kpi-header"><div class="kpi-label">Yield</div><div class="kpi-badge">Switching</div></div>
        <div class="kpi-val" id="kpi-yield">{aggregate["yield_pct"]} <span style="font-size:13px;opacity:0.7">%</span></div>
        <div class="kpi-sub">{aggregate["switching_count"]} / {aggregate["total_devices"]} devices</div>
      </div>
    </div>

    <!-- PROTOCOL SECTIONS (stacked heatmaps) -->
    <div id="proto-sections"></div>

    <!-- DEVICE EXPLORER -->
    <div class="panel-card">
      <div class="panel-header">
        <div class="panel-title">Device Explorer</div>
        <span id="cross-dev-badge" class="panel-badge">—</span>
        <div class="panel-spacer"></div>
        <div class="tab-bar">
          <div class="tab active" onclick="switchCrossTab('iv', this)">IV Overlay</div>
          <div class="tab" onclick="switchCrossTab('params', this)">Extracted Params</div>
          <div class="tab" onclick="switchCrossTab('raw', this)">Raw Data</div>
        </div>
      </div>
      <div class="panel-body" style="padding:0">
        <div class="marker-toggle-row">
          <label class="marker-toggle-label"><input type="checkbox" id="toggle-vset" checked onchange="onMarkerToggle()"> Show V<sub>set</sub></label>
          <label class="marker-toggle-label"><input type="checkbox" id="toggle-vreset" checked onchange="onMarkerToggle()"> Show V<sub>reset</sub></label>
          <span style="flex:1"></span>
          <span id="cross-cell-info" style="font-size:10px;color:var(--text-dim);font-family:'JetBrains Mono',monospace">Selected: —</span>
        </div>
        <div id="cross-iv-plot" style="height:330px"></div>
        <div id="cross-tab-placeholder" style="display:none;height:330px;align-items:center;justify-content:center;color:var(--text-dim);font-size:12px;font-family:'DM Sans',sans-serif"></div>
      </div>
    </div>

    <!-- HISTOGRAMS -->
    <div class="hist-row">
      <div class="panel-card">
        <div class="panel-header"><div class="panel-title">V<sub>set</sub> Distribution</div><div class="panel-badge">All Protocols</div></div>
        <div class="panel-body" style="padding:6px"><div id="cross-hist-vset" style="height:170px"></div></div>
      </div>
      <div class="panel-card">
        <div class="panel-header"><div class="panel-title">V<sub>reset</sub> Distribution</div><div class="panel-badge">All Protocols</div></div>
        <div class="panel-body" style="padding:6px"><div id="cross-hist-vreset" style="height:170px"></div></div>
      </div>
      <div class="panel-card">
        <div class="panel-header"><div class="panel-title">ON/OFF Ratio Distribution</div><div class="panel-badge">All Protocols</div></div>
        <div class="panel-body" style="padding:6px"><div id="cross-hist-ratio" style="height:170px"></div></div>
      </div>
    </div>

  </div><!-- /cross-content -->
</div><!-- /cross-app -->

<script id="cross-protocol-data" type="application/json">
{protocols_json}
</script>
<script id="cross-aggregate-data" type="application/json">
{aggregate_json}
</script>
<script id="cross-device-data" type="application/json">
{cross_devices_json}
</script>
<script id="cross-iv-data" type="application/json">
{cross_iv_json}
</script>
<script id="cross-all-vset" type="application/json">
{all_vset_json}
</script>
<script id="cross-all-vreset" type="application/json">
{all_vreset_json}
</script>
<script id="cross-all-ratios" type="application/json">
{all_ratios_json}
</script>
<script>
{_CROSS_PROTOCOL_JS}
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════════
#  Cross-Protocol JavaScript
# ════════════════════════════════════════════════════════════════

_CROSS_PROTOCOL_JS = r"""
// ══════════════════════════════════════════════════════
//  DATA LOADING
// ══════════════════════════════════════════════════════

var CROSS_PROTOCOLS = JSON.parse(document.getElementById('cross-protocol-data').textContent);
var CROSS_AGGREGATE = JSON.parse(document.getElementById('cross-aggregate-data').textContent);
var CROSS_DEVICES = JSON.parse(document.getElementById('cross-device-data').textContent);
var CROSS_IV = JSON.parse(document.getElementById('cross-iv-data').textContent);
var ALL_VSET = JSON.parse(document.getElementById('cross-all-vset').textContent);
var ALL_VRESET = JSON.parse(document.getElementById('cross-all-vreset').textContent);
var ALL_RATIOS = JSON.parse(document.getElementById('cross-all-ratios').textContent);

// ── Plotly theme defaults
var PAPER_BG = 'rgba(0,0,0,0)';
var PLOT_BG = 'rgba(0,0,0,0)';
var FONT_COLOR = '#8ba3c7';
var GRID_COLOR = 'rgba(32,70,130,0.25)';
var AXIS_COLOR = 'rgba(32,70,130,0.5)';

var baseLayout = {
  paper_bgcolor: PAPER_BG, plot_bgcolor: PLOT_BG,
  font: { color: FONT_COLOR, family: 'JetBrains Mono, monospace', size: 10 },
  margin: { t: 10, r: 10, b: 30, l: 40 },
  xaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR },
  yaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR },
  legend: { bgcolor: 'rgba(15,26,46,0.7)', bordercolor: AXIS_COLOR, borderwidth: 1, font: { size: 9 } },
  hoverlabel: {
    bgcolor: 'rgba(8,14,28,0.95)', bordercolor: '#00d4ff',
    font: { family: 'JetBrains Mono, monospace', size: 10, color: '#e8f0fe' }
  }
};
var plotConfig = { displayModeBar: false, responsive: true };

// Current selection
var currentProtoKey = null;   // "PDA-1::R1C1"
var currentDevice = null;
var currentTab = 'iv';

// ══════════════════════════════════════════════════════
//  PROTOCOL FILTER
// ══════════════════════════════════════════════════════

function onProtoFilter() {
  var sel = document.getElementById('proto-filter').value;
  var sections = document.querySelectorAll('.proto-section');
  sections.forEach(function(sec) {
    if (!sel || sec.id === 'proto-' + sel) {
      sec.style.display = '';
    } else {
      sec.style.display = 'none';
    }
  });
  // Redraw visible heatmaps for responsive sizing
  sections.forEach(function(sec) {
    if (sec.style.display !== 'none') {
      var plotEl = sec.querySelector('[id^="cross-hm-"]');
      if (plotEl) { try { Plotly.Plots.resize(plotEl); } catch(e) {} }
    }
  });
}

function onMaterialFilter() {
  var mat = document.getElementById('material-filter').value;
  // Reload heatmap and histogram data filtered by material
  drawAllHeatmaps(null, mat);
  drawCrossHistograms(mat);
}

// ══════════════════════════════════════════════════════
//  HEATMAPS (per protocol, stacked)
// ══════════════════════════════════════════════════════

function getMetricValue(d, metric) {
  if (!d) return null;
  if (d.failed) return null;
  if (metric === 'ON/OFF Ratio') return d.ratio ? Math.log10(d.ratio) : null;
  if (metric === 'Vset (V)') return d.v_set;
  if (metric === 'Vreset (V)') return d.v_reset;
  if (metric === 'Yield (%)') return d.switching ? 100 : 0;
  return null;
}

function buildHeatmapZ(proto, metric) {
  var m = proto.heatmap_matrix;
  var z = [], ht = [];
  for (var r = 0; r < proto.rows; r++) {
    var zr = [], htr = [];
    for (var c = 0; c < proto.cols; c++) {
      var d = m[r] ? m[r][c] : null;
      var v = getMetricValue(d, metric);
      zr.push(v);
      if (!d) {
        htr.push('<b>R'+(r+1)+'C'+(c+1)+'</b><br>No data');
      } else {
        htr.push(
          '<b>R'+(r+1)+'C'+(c+1)+'</b><br>' +
          'ON/OFF: ' + (d.ratio ? d.ratio.toExponential(2) : 'N/A') + '<br>' +
          'Vset: ' + (d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A') + '<br>' +
          'Vreset: ' + (d.v_reset != null ? d.v_reset.toFixed(2)+' V' : 'N/A') + '<br>' +
          'Switching: ' + (d.switching ? 'Yes' : 'No') + '<br>' +
          'Material: ' + (d.material || 'unknown')
        );
      }
    }
    z.push(zr);
    ht.push(htr);
  }
  return { z: z, hovertext: ht };
}

function drawOneHeatmap(proto, metric) {
  var divId = 'cross-hm-' + proto.name;
  var data = buildHeatmapZ(proto, metric);
  var labels = Array.from({length: Math.max(proto.rows, proto.cols)}, function(_,i){return ''+(i+1)});

  var colorscale = metric === 'ON/OFF Ratio' ?
    [[0,'#0a0f1f'],[0.2,'#0d2040'],[0.4,'#0e3d60'],[0.6,'#1a6b7a'],[0.75,'#24a88c'],[0.88,'#6ec96f'],[1.0,'#fde74c']] :
    [[0,'#0a0f1f'],[0.3,'#1a3a6e'],[0.6,'#2196c8'],[0.8,'#5ed4e6'],[1.0,'#e2f3ff']];

  Plotly.react(divId, [{
    type: 'heatmap',
    z: data.z, x: labels.slice(0, proto.cols), y: labels.slice(0, proto.rows),
    colorscale: colorscale, hovertext: data.hovertext, hovertemplate: '%{{hovertext}}<extra></extra>',
    colorbar: {
      thickness: 10, len: 0.8,
      tickfont: { size: 9, color: '#8ba3c7', family: 'JetBrains Mono' },
      outlinecolor: 'rgba(32,70,130,0.4)', outlinewidth: 1,
      bgcolor: 'rgba(0,0,0,0)',
      title: { text: metric === 'ON/OFF Ratio' ? 'log10' : '', font: { size: 9, color: '#8ba3c7' }, side: 'right' }
    },
    zsmooth: false, xgap: 1.5, ygap: 1.5
  }], {
    paper_bgcolor: PAPER_BG, plot_bgcolor: PLOT_BG,
    font: { color: FONT_COLOR, family: 'JetBrains Mono, monospace', size: 10 },
    margin: { t: 8, r: 70, b: 30, l: 30 },
    xaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: '', tickfont: { size: 8 }, showgrid: false },
    yaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: '', tickfont: { size: 8 }, showgrid: false, autorange: true },
    height: 300
  }, plotConfig);

  var el = document.getElementById(divId);
  el.removeAllListeners && el.removeAllListeners('plotly_click');
  el.on('plotly_click', (function(p) {
    return function(eventData) {
      if (eventData.points && eventData.points.length > 0 && eventData.points[0].curveNumber === 0) {
        var pt = eventData.points[0];
        var rIdx = parseInt(pt.y) - 1;
        var cIdx = parseInt(pt.x) - 1;
        var cellId = 'R' + (rIdx+1) + 'C' + (cIdx+1);
        var key = p.name + '::' + cellId;
        var d = CROSS_DEVICES[key];
        if (d) {
          currentProtoKey = key;
          currentDevice = d;
          updateCrossDevice(d);
          drawCrossIVPlot();
        }
      }
    };
  })(proto));
}

function drawAllHeatmaps(metric, materialFilter) {
  metric = metric || 'ON/OFF Ratio';
  materialFilter = materialFilter || '';

  var container = document.getElementById('proto-sections');
  container.innerHTML = '';

  CROSS_PROTOCOLS.forEach(function(proto) {
    // Check if any device matches material filter
    if (materialFilter) {
      var hasMatch = false;
      for (var cellId in proto.devices) {
        if (proto.devices.hasOwnProperty(cellId)) {
          if (proto.devices[cellId].material === materialFilter) {
            hasMatch = true;
            break;
          }
        }
      }
      if (!hasMatch) return;
    }

    var materials = [];
    var matMap = {};
    for (var cid in proto.devices) {
      if (proto.devices.hasOwnProperty(cid)) {
        var m = proto.devices[cid].material;
        if (m && !matMap[m]) { matMap[m] = true; materials.push(m); }
      }
    }

    var sec = document.createElement('div');
    sec.className = 'proto-section';
    sec.id = 'proto-' + proto.name;
    sec.innerHTML =
      '<div class="proto-section-header">' +
        '<div class="proto-section-title">' + proto.device_label + '</div>' +
        '<div class="proto-section-sub">' + proto.device_id + ' / ' + proto.rows + 'x' + proto.cols + '</div>' +
        '<div style="flex:1"></div>' +
        '<div class="proto-section-sub">' + materials.join(', ') + '</div>' +
      '</div>' +
      '<div class="proto-section-body">' +
        '<div id="cross-hm-' + proto.name + '" style="height:300px"></div>' +
        '<div style="text-align:center;color:var(--text-dim);font-size:10px;padding:4px">Click cell to explore</div>' +
      '</div>';
    container.appendChild(sec);
  });

  // Now draw each heatmap
  CROSS_PROTOCOLS.forEach(function(proto) {
    if (materialFilter) {
      var hasMatch = false;
      for (var cid in proto.devices) {
        if (proto.devices.hasOwnProperty(cid) && proto.devices[cid].material === materialFilter) {
          hasMatch = true; break;
        }
      }
      if (!hasMatch) return;
    }
    drawOneHeatmap(proto, metric);
  });

  // Re-apply protocol filter
  onProtoFilter();
}

// ══════════════════════════════════════════════════════
//  DEVICE SELECTION & IV OVERLAY
// ══════════════════════════════════════════════════════

function updateCrossDevice(d) {
  document.getElementById('cross-dev-badge').textContent = d.protocol + ' / R'+(d.row+1)+'C'+(d.col+1);
  document.getElementById('cross-cell-info').textContent =
    'Selected: ' + d.protocol + '::R'+(d.row+1)+'C'+(d.col+1) +
    ' | ON/OFF = ' + (d.ratio != null ? d.ratio.toExponential(2) : 'N/A') +
    ' | Vset = ' + (d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A');
}

function drawCrossIVPlot() {
  if (!currentProtoKey || !currentDevice) {
    Plotly.react('cross-iv-plot', [], {
      ...baseLayout, height: 330,
      annotations: [{ text: 'Click a cell in any heatmap to view IV data', showarrow: false, font: {size:14, color:'#4a6a96'}, xref:'paper',yref:'paper',x:0.5,y:0.5 }]
    }, plotConfig);
    return;
  }

  var files = CROSS_IV[currentProtoKey] || [];
  var d = currentDevice;
  var vset = d.v_set;
  var vreset = d.v_reset;

  if (files.length === 0) {
    Plotly.react('cross-iv-plot', [], {
      ...baseLayout, height: 330,
      annotations: [{ text: 'No IV data available', showarrow: false, font: {size:14, color:'#4a6a96'}, xref:'paper',yref:'paper',x:0.5,y:0.5 }]
    }, plotConfig);
    return;
  }

  var traces = [];
  var colors = [
    'rgba(0,180,220,0.7)', 'rgba(220,80,80,0.7)', 'rgba(100,200,120,0.7)',
    'rgba(200,180,60,0.7)', 'rgba(160,100,220,0.7)', 'rgba(100,180,200,0.7)',
    'rgba(220,140,60,0.7)', 'rgba(140,200,160,0.7)'
  ];

  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var color = colors[i % colors.length];
    var posV = [], posI = [], negV = [], negI = [];
    for (var j = 0; j < f.voltage.length; j++) {
      var v = f.voltage[j];
      var absI = Math.abs(f.current[j]);
      if (absI < 1e-14) continue;
      if (v >= 0) { posV.push(v); posI.push(absI); }
      else { negV.push(v); negI.push(absI); }
    }
    if (posV.length > 0) {
      traces.push({
        x: posV, y: posI, type: 'scatter', mode: 'lines',
        line: { color: color, width: 1.0 },
        name: f.label || ('#'+ (i+1)),
        hovertemplate: 'V: %{x:.3f} V<br>|I|: %{y:.3e} A<extra>'+(f.label||'')+'</extra>'
      });
    }
    if (negV.length > 0) {
      traces.push({
        x: negV, y: negI, type: 'scatter', mode: 'lines',
        line: { color: color, width: 1.0, dash: 'dash' },
        showlegend: false,
        hovertemplate: 'V: %{x:.3f} V<br>|I|: %{y:.3e} A<extra></extra>'
      });
    }
  }

  // Vset / Vreset markers (toggleable)
  if (document.getElementById('toggle-vset').checked && vset != null) {
    traces.push({
      x: [vset], y: [1e-3], type: 'scatter', mode: 'markers+text',
      marker: { color: '#ef4444', size: 8, symbol: 'circle', line: { color: '#fff', width: 1 } },
      text: ['Vset'], textposition: 'top center', textfont: { size: 9, color: '#ef4444' },
      name: 'Vset', showlegend: true,
      hovertemplate: 'Vset = ' + vset.toFixed(3) + ' V<extra></extra>'
    });
  }
  if (document.getElementById('toggle-vreset').checked && vreset != null) {
    var vresetSign = vreset < 0 ? vreset : -vreset;
    traces.push({
      x: [vresetSign], y: [1e-3], type: 'scatter', mode: 'markers+text',
      marker: { color: '#3b82f6', size: 8, symbol: 'circle', line: { color: '#fff', width: 1 } },
      text: ['Vreset'], textposition: 'top center', textfont: { size: 9, color: '#3b82f6' },
      name: 'Vreset', showlegend: true,
      hovertemplate: 'Vreset = ' + vreset.toFixed(3) + ' V<extra></extra>'
    });
  }

  Plotly.react('cross-iv-plot', traces, {
    ...baseLayout,
    height: 330,
    margin: { t: 10, r: 140, b: 40, l: 60 },
    xaxis: {
      ...baseLayout.xaxis, title: { text: 'Voltage (V)', font: { size: 10 } },
      zeroline: true, zerolinecolor: 'rgba(100,150,200,0.3)', tickfont: { size: 9 }
    },
    yaxis: {
      ...baseLayout.yaxis, title: { text: '|Current| (A)', font: { size: 10 } },
      type: 'log', tickfont: { size: 9 }
    },
    legend: {
      ...baseLayout.legend, x: 1.01, y: 0.95, xanchor: 'left',
      bgcolor: 'rgba(8,14,28,0.7)', font: { size: 9 }
    },
    showlegend: true
  }, plotConfig);
}

function onMarkerToggle() {
  drawCrossIVPlot();
}

// ══════════════════════════════════════════════════════
//  TAB SWITCHING
// ══════════════════════════════════════════════════════

function switchCrossTab(tab, el) {
  document.querySelectorAll('#cross-app .tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  currentTab = tab;
  var ivPlot = document.getElementById('cross-iv-plot');
  var placeholder = document.getElementById('cross-tab-placeholder');

  if (tab === 'iv') {
    ivPlot.style.display = '';
    placeholder.style.display = 'none';
    drawCrossIVPlot();
  } else if (tab === 'params') {
    ivPlot.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.textContent = 'Extracted parameters view will be available in a future update.';
  } else if (tab === 'raw') {
    ivPlot.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.textContent = 'Raw data table view will be available in a future update.';
  }
}

// ══════════════════════════════════════════════════════
//  SEARCH
// ══════════════════════════════════════════════════════

function onCrossSearch(query) {
  query = query.trim().toUpperCase();
  if (!query) return;
  // Try exact match: "PDA-1::R1C1"
  var d = CROSS_DEVICES[query];
  if (!d) {
    // Try partial match on key
    for (var k in CROSS_DEVICES) {
      if (CROSS_DEVICES.hasOwnProperty(k) && k.toUpperCase().indexOf(query) >= 0) {
        d = CROSS_DEVICES[k];
        currentProtoKey = k;
        break;
      }
    }
  } else {
    currentProtoKey = query;
  }
  if (d) {
    currentDevice = d;
    updateCrossDevice(d);
    drawCrossIVPlot();
  }
}

// ══════════════════════════════════════════════════════
//  HISTOGRAMS
// ══════════════════════════════════════════════════════

function drawCrossHistograms(materialFilter) {
  materialFilter = materialFilter || '';
  var histBase = { ...baseLayout, margin: { t: 8, r: 8, b: 32, l: 36 }, bargap: 0.06 };

  // Filter values by material if needed
  var vsetVals = [], vresetVals = [], ratioVals = [];
  for (var k in CROSS_DEVICES) {
    if (!CROSS_DEVICES.hasOwnProperty(k)) continue;
    var d = CROSS_DEVICES[k];
    if (materialFilter && d.material !== materialFilter) continue;
    if (d.v_set != null) vsetVals.push(d.v_set);
    if (d.v_reset != null) vresetVals.push(Math.abs(d.v_reset));
    if (d.ratio != null && d.ratio > 0) ratioVals.push(d.ratio);
  }

  // Vset
  if (vsetVals.length > 0) {
    var m = vsetVals.reduce(function(a,b){return a+b},0)/vsetVals.length;
    var s = Math.sqrt(vsetVals.map(function(v){return (v-m)*(v-m)}).reduce(function(a,b){return a+b},0)/vsetVals.length);
    var nb = Math.min(30, Math.max(5, Math.floor(vsetVals.length / 3)));
    Plotly.react('cross-hist-vset', [{
      x: vsetVals, type: 'histogram', nbinsx: nb,
      marker: { color: 'rgba(0,180,220,0.7)', line: { color: 'rgba(0,212,255,0.3)', width: 0.5 } },
      hovertemplate: 'Vset: %{x:.2f} V<br>Count: %{y}<extra></extra>'
    }, {
      x: [m, m], y: [0, Math.max(1, vsetVals.length/5)], type: 'scatter', mode: 'lines',
      line: { color: '#00d4ff', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: { ...histBase.xaxis, title: { text: 'Vset (V)', font:{size:10} }, tickfont:{size:9} },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+m.toFixed(2)+' V<br>'+String.fromCharCode(0x03C3)+' = '+s.toFixed(2)+' V',
        font: { size: 9, color: '#7dd3fc' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }

  // Vreset
  if (vresetVals.length > 0) {
    var mr = vresetVals.reduce(function(a,b){return a+b},0)/vresetVals.length;
    var sr = Math.sqrt(vresetVals.map(function(v){return (v-mr)*(v-mr)}).reduce(function(a,b){return a+b},0)/vresetVals.length);
    var nbr = Math.min(30, Math.max(5, Math.floor(vresetVals.length / 3)));
    Plotly.react('cross-hist-vreset', [{
      x: vresetVals, type: 'histogram', nbinsx: nbr,
      marker: { color: 'rgba(220,80,80,0.7)', line: { color: 'rgba(239,100,100,0.3)', width: 0.5 } },
      hovertemplate: '|Vreset|: %{x:.2f} V<br>Count: %{y}<extra></extra>'
    }, {
      x: [mr, mr], y: [0, Math.max(1, vresetVals.length/5)], type: 'scatter', mode: 'lines',
      line: { color: '#ef4444', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: { ...histBase.xaxis, title: { text: '|Vreset| (V)', font:{size:10} }, tickfont:{size:9}, autorange: true },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+mr.toFixed(2)+' V<br>'+String.fromCharCode(0x03C3)+' = '+sr.toFixed(2)+' V',
        font: { size: 9, color: '#fca5a5' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }

  // Ratio
  if (ratioVals.length > 0) {
    var logRs = ratioVals.map(function(v){return Math.log10(v)});
    var lm = logRs.reduce(function(a,b){return a+b},0)/logRs.length;
    var ls = Math.sqrt(logRs.map(function(v){return (v-lm)*(v-lm)}).reduce(function(a,b){return a+b},0)/logRs.length);
    var nbl = Math.min(25, Math.max(5, Math.floor(ratioVals.length / 3)));
    Plotly.react('cross-hist-ratio', [{
      x: logRs, type: 'histogram', nbinsx: nbl,
      marker: { color: 'rgba(100,200,120,0.7)', line: { color: 'rgba(34,197,94,0.3)', width: 0.5 } },
      hovertemplate: '10^%{x:.1f}<br>Count: %{y}<extra></extra>'
    }, {
      x: [lm, lm], y: [0, Math.max(1, ratioVals.length/4)], type: 'scatter', mode: 'lines',
      line: { color: '#22c55e', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: { ...histBase.xaxis, title: { text: 'log10(ON/OFF)', font:{size:10} }, tickfont:{size:9} },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+Math.pow(10, lm).toExponential(2),
        font: { size: 9, color: '#86efac' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }
}

// ══════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════

function initCrossDashboard() {
  drawAllHeatmaps('ON/OFF Ratio', '');
  drawCrossHistograms('');
  // Select first device if any
  if (CROSS_PROTOCOLS.length > 0) {
    var first = CROSS_PROTOCOLS[0];
    var firstKey = null;
    for (var k in CROSS_DEVICES) {
      if (CROSS_DEVICES.hasOwnProperty(k)) {
        firstKey = k;
        break;
      }
    }
    if (firstKey) {
      currentProtoKey = firstKey;
      currentDevice = CROSS_DEVICES[firstKey];
      updateCrossDevice(currentDevice);
      drawCrossIVPlot();
    }
  }
}

window.addEventListener('load', initCrossDashboard);
window.addEventListener('resize', function() {
  ['cross-iv-plot','cross-hist-vset','cross-hist-vreset','cross-hist-ratio'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) { try { Plotly.Plots.resize(el); } catch(e) {} }
  });
  // Also resize heatmaps
  CROSS_PROTOCOLS.forEach(function(proto) {
    var el = document.getElementById('cross-hm-' + proto.name);
    if (el) { try { Plotly.Plots.resize(el); } catch(e) {} }
  });
});
"""


def _fmt_kpi_val(val) -> str:
    """Format a KPI value for display."""
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def _fmt_kpi_ratio(val) -> str:
    """Format ON/OFF ratio for KPI display."""
    if val is None:
        return "N/A"
    if val >= 1000:
        return f"{val:.1e}"
    return f"{val:.1f}"


# ════════════════════════════════════════════════════════════════
#  CSS — Full Dark Theme from Mockup
# ════════════════════════════════════════════════════════════════

_CSS = r"""
:root {
  --bg-deep: #050a14;
  --bg-base: #080e1c;
  --bg-panel: #0c1525;
  --bg-card: #0f1a2e;
  --bg-card2: #111e33;
  --bg-hover: #162038;
  --border: rgba(32, 70, 130, 0.35);
  --border-bright: rgba(0, 200, 255, 0.25);
  --cyan: #00d4ff;
  --cyan-dim: rgba(0, 212, 255, 0.6);
  --cyan-glow: rgba(0, 212, 255, 0.15);
  --blue: #3b82f6;
  --blue-bright: #60a5fa;
  --purple: #a855f7;
  --purple-dim: rgba(168, 85, 247, 0.6);
  --teal: #2dd4bf;
  --orange: #f97316;
  --red: #ef4444;
  --green: #22c55e;
  --yellow: #eab308;
  --text-primary: #e8f0fe;
  --text-secondary: #8ba3c7;
  --text-dim: #4a6a96;
  --text-mono: #7dd3fc;
  --sidebar-w: 240px;
  --header-h: 52px;
  --radius: 12px;
  --radius-sm: 8px;
  --glow-cyan: 0 0 20px rgba(0, 212, 255, 0.2), 0 0 40px rgba(0, 212, 255, 0.08);
  --glow-blue: 0 0 20px rgba(59, 130, 246, 0.2), 0 0 40px rgba(59, 130, 246, 0.08);
  --shadow: 0 4px 20px rgba(0,0,0,0.5);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; overflow: hidden; background: var(--bg-deep); color: var(--text-primary); font-family: 'DM Sans', sans-serif; font-size: 13px; }

/* ── LAYOUT ── */
#app { display: flex; height: 100vh; overflow: hidden; }

/* ── SIDEBAR ── */
#sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
  z-index: 10;
}
#sidebar::-webkit-scrollbar { width: 4px; }
#sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.sb-logo {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border);
}
.sb-logo-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--cyan);
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 7px;
}
.sb-logo-title svg { flex-shrink: 0; }
.sb-logo-sub { font-size: 10.5px; color: var(--text-dim); margin-top: 3px; font-family: 'JetBrains Mono', monospace; }

.sb-section { padding: 10px 14px; border-bottom: 1px solid var(--border); }
.sb-section-title {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 8px;
}

/* Nav items */
.nav-item {
  display: flex; align-items: center; gap: 9px;
  padding: 7px 10px; border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.18s ease;
  color: var(--text-secondary); font-size: 12.5px; font-weight: 500;
}
.nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.active { background: rgba(0,212,255,0.1); color: var(--cyan); border: 1px solid rgba(0,212,255,0.2); }
.nav-item svg { opacity: 0.7; }
.nav-item.active svg { opacity: 1; }

/* Filter controls */
.filter-group { margin-bottom: 10px; }
.filter-label { font-size: 10px; color: var(--text-dim); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.08em; }
.filter-select {
  width: 100%; background: var(--bg-card2); border: 1px solid var(--border);
  color: var(--text-primary); padding: 5px 8px; border-radius: 6px;
  font-size: 11.5px; outline: none; cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%234a6a96' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}
.filter-select:focus { border-color: var(--cyan-dim); }

.range-row { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim); margin-bottom: 3px; }
input[type=range] {
  width: 100%; height: 3px; appearance: none;
  background: linear-gradient(to right, var(--cyan) 0%, var(--cyan) 80%, var(--border) 80%);
  border-radius: 2px; outline: none; cursor: pointer;
}
input[type=range]::-webkit-slider-thumb {
  appearance: none; width: 12px; height: 12px;
  background: var(--cyan); border-radius: 50%;
  box-shadow: 0 0 6px var(--cyan);
}

.toggle-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px; font-size: 11.5px; color: var(--text-secondary);
}
.toggle { position: relative; width: 28px; height: 15px; cursor: pointer; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: var(--bg-card2); border: 1px solid var(--border);
  border-radius: 15px; transition: 0.2s;
}
.toggle-slider:before {
  content: ''; position: absolute; height: 9px; width: 9px;
  left: 2px; bottom: 2px; background: var(--text-dim);
  border-radius: 50%; transition: 0.2s;
}
.toggle input:checked + .toggle-slider { background: rgba(0,212,255,0.2); border-color: var(--cyan-dim); }
.toggle input:checked + .toggle-slider:before { transform: translateX(13px); background: var(--cyan); }

/* Radio group */
.radio-group { display: flex; flex-direction: column; gap: 4px; }
.radio-item { display: flex; align-items: center; gap: 7px; cursor: pointer; font-size: 11.5px; color: var(--text-secondary); padding: 3px 0; }
.radio-item input[type=radio] { accent-color: var(--cyan); cursor: pointer; }
.radio-item.active { color: var(--text-primary); }

/* Device info */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3px 8px; }
.info-row { display: flex; flex-direction: column; padding: 4px 0; border-bottom: 1px solid rgba(32,70,130,0.2); }
.info-key { font-size: 9.5px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.06em; }
.info-val { font-size: 11.5px; font-family: 'JetBrains Mono', monospace; color: var(--text-mono); font-weight: 500; }

/* Review queue */
.review-item {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 8px; border-radius: 6px; margin-bottom: 4px;
  background: var(--bg-card2); border: 1px solid var(--border);
  cursor: pointer; transition: all 0.18s;
}
.review-item:hover { border-color: var(--orange); background: rgba(249,115,22,0.05); }
.conf-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.review-info { flex: 1; min-width: 0; }
.review-id { font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--text-primary); }
.review-conf { font-size: 10px; color: var(--text-dim); }
.review-btn {
  font-size: 9.5px; padding: 2px 7px; border-radius: 4px;
  background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3);
  color: var(--blue-bright); cursor: pointer; font-family: 'DM Sans', sans-serif;
  transition: all 0.18s; flex-shrink: 0;
}
.review-btn:hover { background: rgba(59,130,246,0.3); }

/* Summary stats */
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid rgba(32,70,130,0.15); }
.stat-key { font-size: 11px; color: var(--text-secondary); }
.stat-val { font-size: 11px; font-family: 'JetBrains Mono', monospace; color: var(--text-mono); font-weight: 500; }
.stat-val.green { color: var(--green); }
.stat-val.yellow { color: var(--yellow); }
.stat-val.red { color: var(--red); }

/* ── MAIN AREA ── */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
#main .panel-body { flex: 1; min-height: 0; }
#main .panel-card { display: flex; flex-direction: column; min-height: 0; }
#main .panel-card.heatmap-card { flex: 4; }
#main .panel-card.iv-card { flex: 6; }
#heatmap { width: 100%; height: 100%; min-height: 300px; }
#iv-plot { width: 100%; height: 100%; min-height: 280px; }

/* ── HEADER ── */
#header {
  height: var(--header-h);
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px;
  padding: 0 16px; flex-shrink: 0; z-index: 9;
}
.header-title { font-size: 14px; font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.header-subtitle { font-size: 11px; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; white-space: nowrap; margin-left: 2px; }
.header-sep { width: 1px; height: 24px; background: var(--border); flex-shrink: 0; }

.header-select {
  background: var(--bg-card2); border: 1px solid var(--border);
  color: var(--text-primary); padding: 4px 22px 4px 8px; border-radius: 6px;
  font-size: 11.5px; outline: none; cursor: pointer;
  font-family: 'DM Sans', sans-serif; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5' viewBox='0 0 8 5'%3E%3Cpath d='M1 1l3 3 3-3' stroke='%234a6a96' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 6px center;
}
.header-label { font-size: 9.5px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em; display: flex; flex-direction: column; gap: 2px; }

.header-spacer { flex: 1; }

.search-box {
  display: flex; align-items: center; gap: 6px;
  background: var(--bg-card2); border: 1px solid var(--border);
  border-radius: 6px; padding: 4px 10px; transition: all 0.18s;
}
.search-box:focus-within { border-color: var(--cyan-dim); box-shadow: 0 0 0 2px var(--cyan-glow); }
.search-box input { background: none; border: none; outline: none; color: var(--text-primary); font-size: 11.5px; font-family: 'DM Sans', sans-serif; width: 120px; }
.search-box input::placeholder { color: var(--text-dim); }

.icon-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 10px; border-radius: 6px; cursor: pointer;
  background: var(--bg-card2); border: 1px solid var(--border);
  color: var(--text-secondary); font-size: 11.5px; transition: all 0.18s;
  font-family: 'DM Sans', sans-serif;
}
.icon-btn:hover { border-color: var(--cyan-dim); color: var(--cyan); background: var(--cyan-glow); }

.export-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 12px; border-radius: 6px; cursor: pointer;
  background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(59,130,246,0.15));
  border: 1px solid rgba(0,212,255,0.35);
  color: var(--cyan); font-size: 11.5px; font-weight: 600;
  transition: all 0.18s; font-family: 'DM Sans', sans-serif;
}
.export-btn:hover { background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(59,130,246,0.25)); box-shadow: var(--glow-cyan); }

.device-badge {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 20px;
  background: linear-gradient(135deg, rgba(0,212,255,0.12), rgba(59,130,246,0.12));
  border: 1px solid rgba(0,212,255,0.3);
  box-shadow: var(--glow-cyan);
}
.badge-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 6px var(--cyan); animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.4; } }
.badge-text { font-size: 11.5px; font-weight: 700; color: var(--cyan); font-family: 'JetBrains Mono', monospace; }

/* ── CONTENT ── */
#content {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 12px; display: flex; flex-direction: column; gap: 10px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  background: var(--bg-base);
}
#content::-webkit-scrollbar { width: 5px; }
#content::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── KPI ROW ── */
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.kpi-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px 14px;
  transition: all 0.22s; cursor: default;
  position: relative; overflow: hidden;
}
.kpi-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--kpi-color, var(--cyan)), transparent);
}
.kpi-card:hover { border-color: var(--border-bright); transform: translateY(-1px); box-shadow: var(--shadow); }
.kpi-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.kpi-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); font-weight: 600; }
.kpi-badge { font-size: 9px; padding: 2px 6px; border-radius: 10px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: var(--text-dim); }
.kpi-val { font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--kpi-color, var(--cyan)); line-height: 1; margin-bottom: 2px; }
.kpi-sub { font-size: 10px; color: var(--text-dim); }

/* ── PANEL CARDS ── */
.panel-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
}
.panel-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-bottom: 1px solid var(--border); background: var(--bg-card2);
}
.panel-title { font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
.panel-badge {
  font-size: 9.5px; padding: 2px 7px; border-radius: 10px;
  background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.2);
  color: var(--cyan-dim); font-family: 'JetBrains Mono', monospace;
}
.panel-spacer { flex: 1; }
.panel-body { padding: 12px; }

/* ── MAIN ROW ── */
.main-row { display: grid; grid-template-columns: 1fr 1.5fr; gap: 10px; }

/* ── HEATMAP PANEL ── */
.heatmap-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ctrl-select {
  background: var(--bg-card2); border: 1px solid var(--border);
  color: var(--text-primary); padding: 3px 18px 3px 7px;
  border-radius: 5px; font-size: 10.5px; outline: none; cursor: pointer;
  font-family: 'DM Sans', sans-serif; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='7' height='4' viewBox='0 0 7 4'%3E%3Cpath d='M1 1l2.5 2 2.5-2' stroke='%234a6a96' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 5px center;
}

/* ── IV TAB BAR ── */
.tab-bar { display: flex; gap: 2px; }
.tab {
  padding: 5px 12px; border-radius: 5px; cursor: pointer;
  font-size: 11.5px; color: var(--text-dim); transition: all 0.18s;
  border: 1px solid transparent;
}
.tab:hover { color: var(--text-secondary); background: var(--bg-hover); }
.tab.active { background: rgba(0,212,255,0.1); color: var(--cyan); border-color: rgba(0,212,255,0.2); }

/* ── HISTOGRAM ROW ── */
.hist-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }

/* ── BOTTOM ROW ── */
.bottom-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

/* ── REVIEW TABLE ── */
.review-table { width: 100%; border-collapse: collapse; }
.review-table th {
  text-align: left; font-size: 9.5px; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-dim); padding: 5px 8px;
  border-bottom: 1px solid var(--border); font-weight: 600;
}
.review-table td { padding: 6px 8px; border-bottom: 1px solid rgba(32,70,130,0.15); font-size: 11px; vertical-align: middle; }
.review-table tr:hover td { background: var(--bg-hover); }
.conf-bar { display: flex; align-items: center; gap: 6px; }
.conf-track { flex: 1; height: 3px; background: var(--bg-card2); border-radius: 2px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 2px; }
.conf-num { font-family: 'JetBrains Mono', monospace; font-size: 10.5px; min-width: 28px; }
.issue-tag {
  font-size: 9.5px; padding: 2px 6px; border-radius: 4px;
  background: rgba(249,115,22,0.1); border: 1px solid rgba(249,115,22,0.25); color: var(--orange);
}
.tbl-btn {
  font-size: 9.5px; padding: 2px 8px; border-radius: 4px;
  background: rgba(59,130,246,0.12); border: 1px solid rgba(59,130,246,0.3);
  color: var(--blue-bright); cursor: pointer; font-family: 'DM Sans', sans-serif;
  transition: all 0.15s;
}
.tbl-btn:hover { background: rgba(59,130,246,0.25); }

/* ── CONFIDENCE PANEL ── */
.conf-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 6px; margin-top: 8px; }
.conf-stat-card {
  background: var(--bg-card2); border-radius: 7px; padding: 7px 10px;
  border: 1px solid var(--border); text-align: center;
}
.conf-stat-val { font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono', monospace; line-height: 1; }
.conf-stat-key { font-size: 9px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }

/* Plotly override */
.js-plotly-plot .plotly .modebar { display: none !important; }
.js-plotly-plot .plotly .modebar-container { display: none; }

/* ── SCROLLBAR for review list ── */
.review-scroll { max-height: 180px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }

/* ── UTIL ── */
.mono { font-family: 'JetBrains Mono', monospace; }
.text-cyan { color: var(--cyan); }
.text-dim { color: var(--text-dim); }
.row-flex { display: flex; gap: 8px; align-items: center; }
.flex-1 { flex: 1; }
.hint-text { font-size: 10px; color: var(--cyan); margin-top: 4px; padding: 0 2px; }

/* Quick actions */
.qa-btn {
  display: block; width: 100%; text-align: center; padding: 7px;
  border-radius: 6px; font-size: 11.5px; cursor: pointer; margin-bottom: 5px;
  background: var(--bg-card2); border: 1px solid var(--border); color: var(--text-secondary);
  transition: all 0.18s; font-family: 'DM Sans', sans-serif;
}
.qa-btn:hover { background: var(--bg-hover); border-color: var(--blue); color: var(--blue-bright); }
.qa-btn.danger { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.3); color: var(--red); }
.qa-btn.danger:hover { background: rgba(239,68,68,0.15); }

.selected-cell-info {
  font-size: 10px; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; padding: 0 2px;
}
"""


# ════════════════════════════════════════════════════════════════
#  JavaScript — Interactive Elements (with real data)
# ════════════════════════════════════════════════════════════════

_JS = r"""
// ══════════════════════════════════════════════════════
//  DATA LOADING
// ══════════════════════════════════════════════════════

var DEVICE_DATA = {};
var IV_RAW_DATA = {};
var HEATMAP_META = JSON.parse(document.getElementById('heatmap-data').textContent);
var HISTOGRAM_META = JSON.parse(document.getElementById('histogram-data').textContent);
var AGGREGATE = JSON.parse(document.getElementById('aggregate-data').textContent);
var CURRENT_MATERIAL = '';

var selectedCellId = null;
var selectedCell = null;

function switchMaterial(mat) {
  CURRENT_MATERIAL = mat;
  return window._loadMatData(mat).then(function() {
    var md = window._MAT_DATA[mat];
    DEVICE_DATA = md.devices || {};
    IV_RAW_DATA = md.iv || {};
    // Select first device
    selectedCellId = null;
    selectedCell = null;
    for (var k in DEVICE_DATA) {
      if (DEVICE_DATA.hasOwnProperty(k)) {
        selectedCellId = k;
        selectedCell = DEVICE_DATA[k];
        break;
      }
    }
    // Update header title to show current material
    var titleEl = document.getElementById('header-title');
    if (titleEl) titleEl.textContent = mat;
    // Refresh UI
    var metric = document.getElementById('heatmap-metric').value;
    drawHeatmap(metric);
    if (selectedCell) {
      updateSelectedDevice(selectedCell);
    }
    drawHistograms();
  });
}

// ── Plotly theme defaults
var PAPER_BG = 'rgba(0,0,0,0)';
var PLOT_BG = 'rgba(0,0,0,0)';
var FONT_COLOR = '#8ba3c7';
var GRID_COLOR = 'rgba(32,70,130,0.25)';
var AXIS_COLOR = 'rgba(32,70,130,0.5)';

var baseLayout = {
  paper_bgcolor: PAPER_BG, plot_bgcolor: PLOT_BG,
  font: { color: FONT_COLOR, family: 'JetBrains Mono, monospace', size: 10 },
  margin: { t: 10, r: 10, b: 30, l: 40 },
  xaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR },
  yaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR },
  legend: { bgcolor: 'rgba(15,26,46,0.7)', bordercolor: AXIS_COLOR, borderwidth: 1, font: { size: 9 } },
  hoverlabel: {
    bgcolor: 'rgba(8,14,28,0.95)', bordercolor: '#00d4ff',
    font: { family: 'JetBrains Mono, monospace', size: 10, color: '#e8f0fe' }
  },
  transition: { duration: 300, easing: 'cubic-in-out' }
};

var plotConfig = {
  displayModeBar: false,
  responsive: true
};

// ══════════════════════════════════════════════════════
//  HEATMAP
// ══════════════════════════════════════════════════════

function getMetricValue(d, metric) {
  if (!d) return null;
  if (d.failed) return null;
  var useLog = document.getElementById('toggle-log') ? document.getElementById('toggle-log').checked : true;
  if (metric === 'ON/OFF Ratio') return d.ratio ? (useLog ? Math.log10(d.ratio) : d.ratio) : null;
  if (metric === 'Vset (V)') return d.v_set;
  if (metric === 'Vreset (V)') return d.v_reset;
  if (metric === 'Yield (%)') return d.switching ? 100 : 0;
  return null;
}

function buildHeatmapData(metric) {
  var rows = HEATMAP_META.rows;
  var cols = HEATMAP_META.cols;
  var z = [], hovertext = [];
  for (var r = 0; r < rows; r++) {
    var zr = [], ht = [];
    for (var c = 0; c < cols; c++) {
      // Look up device in current DEVICE_DATA
      var d = null;
      for (var k in DEVICE_DATA) {
        if (DEVICE_DATA.hasOwnProperty(k) && DEVICE_DATA[k].row === r && DEVICE_DATA[k].col === c) {
          d = DEVICE_DATA[k];
          break;
        }
      }
      var v = getMetricValue(d, metric);
      zr.push(v);
      if (!d) {
        ht.push('<b>R'+(r+1)+'C'+(c+1)+'</b><br>No data');
      } else {
        ht.push(
          '<b>R'+(r+1)+'C'+(c+1)+'</b><br>' +
          'ON/OFF: ' + (d.ratio ? d.ratio.toExponential(2) : 'N/A') + '<br>' +
          'Vset: ' + (d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A') + '<br>' +
          'Vreset: ' + (d.v_reset != null ? d.v_reset.toFixed(2)+' V' : 'N/A') + '<br>' +
          'Switching: ' + (d.switching ? 'Yes' : 'No') + '<br>' +
          'Files: ' + (d.n_files || 0)
        );
      }
    }
    z.push(zr);
    hovertext.push(ht);
  }
  return { z: z, hovertext: hovertext };
}

function drawHeatmap(metric) {
  var metricName = metric || 'ON/OFF Ratio';
  document.getElementById('heatmap-badge').textContent = metricName;

  var data = buildHeatmapData(metricName);
  var rows = HEATMAP_META.rows;
  var cols = HEATMAP_META.cols;
  var labels = Array.from({length: Math.max(rows, cols)}, function(_,i){return ''+(i+1)});

  var colorscale = metricName === 'ON/OFF Ratio' ?
    [[0,'#0a0f1f'],[0.2,'#0d2040'],[0.4,'#0e3d60'],[0.6,'#1a6b7a'],[0.75,'#24a88c'],[0.88,'#6ec96f'],[1.0,'#fde74c']] :
    [[0,'#0a0f1f'],[0.3,'#1a3a6e'],[0.6,'#2196c8'],[0.8,'#5ed4e6'],[1.0,'#e2f3ff']];

  var selX = selectedCell ? [selectedCell.col + 0.5] : [];
  var selY = selectedCell ? [selectedCell.row + 0.5] : [];
  // Build opacity mask: dim unselected cells
  var opacityMask = [];
  if (selectedCell) {
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        opacityMask.push((r === selectedCell.row && c === selectedCell.col) ? 1.0 : 0.12);
      }
    }
  }

  Plotly.react('heatmap-plot', [
    {
      type: 'heatmap',
      z: data.z, x: labels.slice(0, cols), y: labels.slice(0, rows).reverse(),
      colorscale: colorscale, hovertext: data.hovertext, hovertemplate: '%{hovertext}<extra></extra>',
      colorbar: {
        thickness: 10, len: 0.8,
        tickfont: { size: 9, color: '#8ba3c7', family: 'JetBrains Mono' },
        outlinecolor: 'rgba(32,70,130,0.4)', outlinewidth: 1,
        bgcolor: 'rgba(0,0,0,0)',
        title: { text: metricName === 'ON/OFF Ratio' ? 'log10' : '', font: { size: 9, color: '#8ba3c7' }, side: 'right' }
      },
      opacity: opacityMask.length ? opacityMask : undefined,
      zsmooth: false, xgap: 1.5, ygap: 1.5
    },
    {
      type: 'scatter',
      x: selectedCell ? [selectedCell.col + 1] : [],
      y: selectedCell ? [rows - selectedCell.row] : [],
      mode: 'markers',
      marker: { color: 'rgba(0,212,255,0)', size: 24, line: { color: '#00d4ff', width: 2.5 } },
      hoverinfo: 'skip', showlegend: false
    }
  ], {
    paper_bgcolor: PAPER_BG, plot_bgcolor: PLOT_BG,
    font: { color: FONT_COLOR, family: 'JetBrains Mono, monospace', size: 10 },
    margin: { t: 22, r: 70, b: 26, l: 30 },
    xaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: { text: 'Column', standoff: 12 }, tickfont: { size: 8 }, showgrid: false, side: 'top', tickangle: 0 },
    yaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: 'Row', tickfont: { size: 8 }, showgrid: false, autorange: false, range: [-0.5, rows - 0.5] },
    height: 400
  }, plotConfig);

  var heatmapEl = document.getElementById('heatmap-plot');
  heatmapEl.removeAllListeners && heatmapEl.removeAllListeners('plotly_click');
  heatmapEl.on('plotly_click', function(eventData) {
    if (eventData.points && eventData.points.length > 0 && eventData.points[0].curveNumber === 0) {
      var p = eventData.points[0];
      var rIdx = HEATMAP_META.rows - 1 - (parseInt(p.y) - 1);
      var cIdx = parseInt(p.x) - 1;
      // Find device for this cell matching the selected material
      var mat = document.getElementById('header-material').value;
      var d = null;
      if (mat && mat !== 'All') {
        var key = 'R' + (rIdx+1) + 'C' + (cIdx+1) + '_' + mat;
        d = DEVICE_DATA[key];
      }
      if (!d) {
        // Fall back to first device at this cell
        for (var k in DEVICE_DATA) {
          if (DEVICE_DATA.hasOwnProperty(k) && k.indexOf('R'+(rIdx+1)+'C'+(cIdx+1)) === 0) {
            d = DEVICE_DATA[k];
            break;
          }
        }
      }
      if (d) {
        selectedCellId = 'R'+(rIdx+1)+'C'+(cIdx+1)+'_'+(d.material||'');
        selectedCell = d;
        updateSelectedDevice(d);
        drawHeatmap(metricName);
      }
    }
  });
}

function updateSelectedDevice(d) {
  var rc = 'R'+(d.row+1)+'C'+(d.col+1);
  // Update info panel under heatmap
  var infoDiv = document.getElementById('selected-device-info');
  if (infoDiv) {
    infoDiv.innerHTML =
      '<div style="font-family:\'DM Sans\',sans-serif;font-size:10px;line-height:1.8">'+
        '<div style="font-weight:600;color:var(--accent);font-size:12px;margin-bottom:2px">'+rc+' — '+(d.material||'unknown')+'</div>'+
        '<div style="display:grid;grid-template-columns:auto 1fr;gap:1px 10px">'+
          '<span style="color:var(--text-dim)">Files</span><span>'+(d.n_files||0)+'</span>'+
          '<span style="color:var(--text-dim)">ON/OFF</span><span><b>'+(d.ratio != null ? d.ratio.toExponential(2) : 'N/A')+'</b></span>'+
          '<span style="color:var(--text-dim)">Vset</span><span><b style="color:#ef4444">'+(d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A')+'</b></span>'+
          '<span style="color:var(--text-dim)">Vreset</span><span><b style="color:#3b82f6">'+(d.v_reset != null ? d.v_reset.toFixed(2)+' V' : 'N/A')+'</b></span>'+
          '<span style="color:var(--text-dim)">Switching</span><span>'+(d.switching ? '<b style="color:#22c55e">Yes</b>' : '<b style="color:#ef4444">No</b>')+'</span>'+
        '</div>'+
      '</div>';
  }
  document.getElementById('iv-device-badge').textContent = rc;

  // Populate sweep cycle selector FIRST, then draw IV plot
  var files = IV_RAW_DATA[rc] || [];
  var sel = document.getElementById('sweep-select');
  var nav = document.getElementById('cycle-nav');
  var overlayToggle = document.getElementById('toggle-overlay');
  var overlayMode = overlayToggle ? overlayToggle.checked : true;
  if (files.length > 1 && sel) {
    nav.style.display = overlayMode ? 'none' : 'flex';
    sel.innerHTML = '';
    var allOpt = document.createElement('option');
    allOpt.value = '-1';
    allOpt.textContent = 'All';
    sel.appendChild(allOpt);
    for (var si = 0; si < files.length; si++) {
      var opt = document.createElement('option');
      opt.value = si;
      opt.textContent = '#' + (si+1);
      if (files[si].label && files[si].label !== '#'+(si+1))
        opt.textContent = files[si].label;
      sel.appendChild(opt);
    }
    sel.value = overlayMode ? '-1' : '0';
  } else if (sel) {
    nav.style.display = 'none';
  }
  drawIVPlot(d);
}

// ── Heatmap metric selector
document.getElementById('heatmap-metric').addEventListener('change', function() {
  drawHeatmap(this.value);
});



// ── Overlay toggle: show/hide cycle nav
// ── Material selector
function onMaterialChange() {
  var mat = document.getElementById('header-material').value;
  if (mat && mat !== 'All') {
    switchMaterial(mat);
  }
}
document.getElementById('header-material').addEventListener('change', onMaterialChange);

document.getElementById('toggle-overlay').addEventListener('change', function() {
  var nav = document.getElementById('cycle-nav');
  if (nav) nav.style.display = this.checked ? 'none' : 'flex';
  // When turning off overlay, reset sweep to first
  if (!this.checked) {
    var sel = document.getElementById('sweep-select');
    if (sel && sel.options.length > 1) sel.value = '0';
  }
  if (selectedCell) drawIVPlot(selectedCell);
});

// ── Log scale for heatmap
document.getElementById('toggle-log').addEventListener('change', function() {
  drawHeatmap(document.getElementById('heatmap-metric').value);
});

// ── Sweep cycle navigation
document.getElementById('sweep-select').addEventListener('change', function() {
  if (selectedCell) drawIVPlot(selectedCell);
});
document.getElementById('sweep-prev').addEventListener('click', function() {
  var sel = document.getElementById('sweep-select');
  var idx = parseInt(sel.value);
  if (isNaN(idx) || idx < 0) idx = sel.options.length - 1;
  else idx = Math.max(0, idx - 1);
  sel.value = idx;
  if (selectedCell) drawIVPlot(selectedCell);
});
document.getElementById('sweep-next').addEventListener('click', function() {
  var sel = document.getElementById('sweep-select');
  var idx = parseInt(sel.value);
  if (isNaN(idx) || idx < 0) idx = 0;
  else idx = Math.min(sel.options.length - 1, idx + 1);
  sel.value = idx;
  if (selectedCell) drawIVPlot(selectedCell);
});

// ══════════════════════════════════════════════════════
//  IV OVERLAY PLOT (Real Data)
// ══════════════════════════════════════════════════════

var currentTab = 'iv';

function drawIVPlot(deviceInfo) {
  var cellId = 'R'+(deviceInfo.row+1)+'C'+(deviceInfo.col+1);
  var files = IV_RAW_DATA[cellId] || [];
  var vset = deviceInfo.v_set;
  var vreset = deviceInfo.v_reset;

  if (files.length === 0) {
    Plotly.react('iv-plot', [], {
      ...baseLayout, height: 330,
      annotations: [{ text: 'No IV data available', showarrow: false, font: {size:14, color:'#4a6a96'}, xref:'paper',yref:'paper',x:0.5,y:0.5 }]
    }, plotConfig);
    return;
  }

  var overlayMode = document.getElementById('toggle-overlay') ? document.getElementById('toggle-overlay').checked : true;
  var currentSweepIdx = document.getElementById('sweep-select') ? parseInt(document.getElementById('sweep-select').value) : -1;
  var isSingleSweep = !overlayMode && currentSweepIdx >= 0 && currentSweepIdx < files.length;
  var sweepIdx = isSingleSweep ? currentSweepIdx : -1;
  var total = isSingleSweep ? 1 : files.length;

  // Color gradient from blue (early) → cyan → teal → red (late)
  function cycleColor(idx, total) {
    var t = total > 1 ? idx / (total - 1) : 0.5;
    var r = Math.round(30 + 200 * t);
    var g = Math.round(180 - 120 * t);
    var b = Math.round(220 - 180 * t);
    return 'rgba(' + r + ',' + g + ',' + b + ',0.8)';
  }

  var traces = [];
  var fileName = '';

  for (var i = 0; i < files.length; i++) {
    if (isSingleSweep && i !== sweepIdx) continue;
    var f = files[i];
    // Determine trace color: by cycle index if colorByCycle, else by position
    var color = cycleColor(i, files.length);

    var posV = [], posI = [], negV = [], negI = [];
    for (var j = 0; j < f.voltage.length; j++) {
      var v = f.voltage[j];
      var absI = Math.abs(f.current[j]);
      if (absI < 1e-14) continue;
      if (v >= 0) { posV.push(v); posI.push(absI); }
      else { negV.push(v); negI.push(absI); }
    }
    if (posV.length > 0) {
      traces.push({
        x: posV, y: posI, type: 'scatter', mode: 'lines',
        line: { color: color, width: isSingleSweep ? 1.8 : 1.2 },
        name: isSingleSweep ? (f.label || ('#'+ (i+1))) : 'IV',
        showlegend: isSingleSweep,
        hovertemplate: 'V: %{x:.3f} V<br>|I|: %{y:.3e} A<extra>'+(f.label||'')+'</extra>'
      });
    }
    if (negV.length > 0) {
      traces.push({
        x: negV, y: negI, type: 'scatter', mode: 'lines',
        line: { color: color, width: isSingleSweep ? 1.8 : 1.2, dash: 'dash' },
        showlegend: false,
        hovertemplate: 'V: %{x:.3f} V<br>|I|: %{y:.3e} A<extra></extra>'
      });
    }

    // Per-file Vset/Vreset markers — visible in both modes, legend only in single-cycle
    var showMarkerLegend = isSingleSweep;
    if (f.v_set != null && f.i_set != null) {
      var iAbs = Math.abs(f.i_set);
      if (iAbs > 0) {
        traces.push({
          x: [f.v_set], y: [iAbs], type: 'scatter', mode: 'markers+text',
          marker: { color: '#ef4444', size: isSingleSweep ? 10 : 7, symbol: 'circle', line: { color: '#fff', width: 1.5 } },
          text: [isSingleSweep ? 'Vset' : ''], textposition: 'top center', textfont: { size: 9, color: '#ef4444', weight: 'bold' },
          name: 'Vset', showlegend: showMarkerLegend,
          hovertemplate: 'Vset = ' + f.v_set.toFixed(3) + ' V<br>I = ' + iAbs.toFixed(3) + ' A<extra></extra>'
        });
      }
    }
    if (f.v_reset != null && f.i_reset != null) {
      var rAbs = Math.abs(f.i_reset);
      if (rAbs > 0) {
        var rSign = f.v_reset < 0 ? f.v_reset : -f.v_reset;
        traces.push({
          x: [rSign], y: [rAbs], type: 'scatter', mode: 'markers+text',
          marker: { color: '#3b82f6', size: isSingleSweep ? 10 : 7, symbol: 'circle', line: { color: '#fff', width: 1.5 } },
          text: [isSingleSweep ? 'Vreset' : ''], textposition: 'top center', textfont: { size: 9, color: '#3b82f6', weight: 'bold' },
          name: 'Vreset', showlegend: showMarkerLegend,
          hovertemplate: 'Vreset = ' + f.v_reset.toFixed(3) + ' V<br>I = ' + rAbs.toFixed(3) + ' A<extra></extra>'
        });
      }
    }
    if (isSingleSweep) break;
  }

  // Time-colored segments for single-cycle mode
  if (isSingleSweep) {
    var f = files[sweepIdx];
    if (f.voltage && f.current && f.voltage.length > 2) {
      var n = f.voltage.length;
      var groupSize = Math.max(1, Math.floor(n / 30));
      for (var si = 0; si < n - 1; si += groupSize) {
        var ei = Math.min(si + groupSize + 1, n);
        var segV = [], segI = [];
        for (var j = si; j < ei; j++) {
          var absI = Math.abs(f.current[j]);
          if (absI < 1e-14) continue;
          segV.push(f.voltage[j]);
          segI.push(absI);
        }
        if (segV.length < 2) continue;
        var t = si / (n - 1);
        var r = Math.round(20 + 210 * t);
        var g = Math.round(180 - 140 * t);
        var b = Math.round(220 - 200 * t);
        traces.push({
          x: segV, y: segI, type: 'scatter', mode: 'lines',
          line: { color: 'rgba(' + r + ',' + g + ',' + b + ',0.9)', width: 1.8 },
          showlegend: false, hovertemplate: 'V: %{x:.3f} V<br>|I|: %{y:.3e} A<extra></extra>'
        });
      }
      // Color bar
      traces.push({
        x: [null], y: [null], type: 'scatter', mode: 'markers',
        marker: {
          colorscale: [[0, 'rgb(20,180,220)'], [1, 'rgb(230,40,20)']],
          cmin: 0, cmax: 1,
          colorbar: { title: { text: 'Time →', font: { size: 9 } }, tickfont: { size: 8 }, len: 0.3, thickness: 8 },
          size: 0
        },
        showlegend: false, hoverinfo: 'none'
      });
    }
  } else if (files.length > 1) {
    // Color bar for overlay mode
    traces.push({
      x: [null], y: [null], type: 'scatter', mode: 'markers',
      marker: {
        colorscale: [[0, 'rgb(30,180,220)'], [1, 'rgb(230,60,40)']],
        cmin: 1, cmax: files.length,
        colorbar: { title: { text: 'Cycle', font: { size: 9 } }, tickfont: { size: 8 }, len: 0.4, thickness: 8 },
        size: 0
      },
      showlegend: false, hoverinfo: 'none'
    });
  }

  Plotly.react('iv-plot', traces, {
    ...baseLayout,
    height: 400,
    margin: { t: 10, r: 140, b: 40, l: 60 },
    xaxis: {
      ...baseLayout.xaxis, title: { text: 'Voltage (V)', font: { size: 10 } },
      zeroline: true, zerolinecolor: 'rgba(100,150,200,0.3)',
      tickfont: { size: 9 }
    },
    yaxis: {
      ...baseLayout.yaxis, title: { text: '|Current| (A)', font: { size: 10 } },
      type: 'log', tickfont: { size: 9 }
    },
    legend: {
      ...baseLayout.legend, x: 1.01, y: 0.95, xanchor: 'left',
      bgcolor: 'rgba(8,14,28,0.7)', font: { size: 9 }
    },
    showlegend: true
  }, plotConfig);
}

// ══════════════════════════════════════════════════════
//  TAB SWITCHING
// ══════════════════════════════════════════════════════

function switchTab(tab, el) {
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  currentTab = tab;
  var ivPlot = document.getElementById('iv-plot');
  var placeholder = document.getElementById('tab-placeholder');

  if (tab === 'iv') {
    ivPlot.style.display = '';
    placeholder.style.display = 'none';
    if (selectedCell) drawIVPlot(selectedCell);
  } else if (tab === 'params') {
    ivPlot.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.textContent = 'Extracted parameters view will be available in a future update.';
  } else if (tab === 'evo') {
    ivPlot.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.textContent = 'Cycle evolution analysis requires endurance cycling data.';
  } else if (tab === 'raw') {
    ivPlot.style.display = 'none';
    placeholder.style.display = 'flex';
    placeholder.textContent = 'Raw data table view will be available in a future update.';
  }
}

// ══════════════════════════════════════════════════════
//  SEARCH
// ══════════════════════════════════════════════════════

function onSearch(query) {
  query = query.trim().toUpperCase();
  if (!query) {
    // Reset
    return;
  }
  // Try to find device by ID
  var d = DEVICE_DATA[query];
  if (!d) {
    // Try partial match
    for (var k in DEVICE_DATA) {
      if (DEVICE_DATA.hasOwnProperty(k) && k.toUpperCase().indexOf(query) >= 0) {
        d = DEVICE_DATA[k];
        break;
      }
    }
  }
  if (d) {
    selectedCellId = 'R'+(d.row+1)+'C'+(d.col+1);
    selectedCell = d;
    updateSelectedDevice(d);
    drawHeatmap(document.getElementById('heatmap-metric').value);
  }
}

// ══════════════════════════════════════════════════════
//  HISTOGRAMS
// ══════════════════════════════════════════════════════

function drawHistograms() {
  var histBase = {
    ...baseLayout,
    margin: { t: 8, r: 8, b: 32, l: 36 },
    bargap: 0.06
  };

  // Collect all values from DEVICE_DATA
  var vsetVals = [], vresetVals = [], ratioVals = [];
  for (var k in DEVICE_DATA) {
    if (!DEVICE_DATA.hasOwnProperty(k)) continue;
    var d = DEVICE_DATA[k];
    if (d.v_set != null) vsetVals.push(d.v_set);
    if (d.v_reset != null) vresetVals.push(Math.abs(d.v_reset));
    if (d.ratio != null && d.ratio > 0) ratioVals.push(d.ratio);
  }

  // Vset histogram
  if (vsetVals.length > 0) {
    var vsetMean = vsetVals.reduce(function(a,b){return a+b},0)/vsetVals.length;
    var vsetStd = Math.sqrt(vsetVals.map(function(v){return (v-vsetMean)*(v-vsetMean)}).reduce(function(a,b){return a+b},0)/vsetVals.length);
    var nbins = Math.min(30, Math.max(5, Math.floor(vsetVals.length / 3)));
    Plotly.react('hist-vset', [{
      x: vsetVals, type: 'histogram', nbinsx: nbins,
      marker: { color: 'rgba(0,180,220,0.7)', line: { color: 'rgba(0,212,255,0.3)', width: 0.5 } },
      hovertemplate: 'Vset: %{x:.2f} V<br>Count: %{y}<extra></extra>'
    }, {
      x: [vsetMean, vsetMean], y: [0, Math.max(1, vsetVals.length/5)], type: 'scatter', mode: 'lines',
      line: { color: '#00d4ff', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: { ...histBase.xaxis, title: { text: 'Vset (V)', font:{size:10} }, tickfont:{size:9} },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+vsetMean.toFixed(2)+' V<br>'+
              String.fromCharCode(0x03C3)+' = '+vsetStd.toFixed(2)+' V',
        font: { size: 9, color: '#7dd3fc' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }

  // Vreset histogram
  if (vresetVals.length > 0) {
    var vresetMean = vresetVals.reduce(function(a,b){return a+b},0)/vresetVals.length;
    var vresetStd = Math.sqrt(vresetVals.map(function(v){return (v-vresetMean)*(v-vresetMean)}).reduce(function(a,b){return a+b},0)/vresetVals.length);
    var nbins = Math.min(30, Math.max(5, Math.floor(vresetVals.length / 3)));
    Plotly.react('hist-vreset', [{
      x: vresetVals, type: 'histogram', nbinsx: nbins,
      marker: { color: 'rgba(220,80,80,0.7)', line: { color: 'rgba(239,100,100,0.3)', width: 0.5 } },
      hovertemplate: '|Vreset|: %{x:.2f} V<br>Count: %{y}<extra></extra>'
    }, {
      x: [vresetMean, vresetMean], y: [0, Math.max(1, vresetVals.length/5)], type: 'scatter', mode: 'lines',
      line: { color: '#ef4444', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: { ...histBase.xaxis, title: { text: '|Vreset| (V)', font:{size:10} }, tickfont:{size:9}, autorange: true },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+vresetMean.toFixed(2)+' V<br>'+
              String.fromCharCode(0x03C3)+' = '+vresetStd.toFixed(2)+' V',
        font: { size: 9, color: '#fca5a5' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }

  // ON/OFF Ratio histogram (log)
  if (ratioVals.length > 0) {
    var logRatios = ratioVals.map(function(v){return Math.log10(v)});
    var logMean = logRatios.reduce(function(a,b){return a+b},0)/logRatios.length;
    var logStd = Math.sqrt(logRatios.map(function(v){return (v-logMean)*(v-logMean)}).reduce(function(a,b){return a+b},0)/logRatios.length);
    var nbins = Math.min(25, Math.max(5, Math.floor(ratioVals.length / 3)));
    Plotly.react('hist-ratio', [{
      x: logRatios, type: 'histogram', nbinsx: nbins,
      marker: { color: 'rgba(100,200,120,0.7)', line: { color: 'rgba(34,197,94,0.3)', width: 0.5 } },
      hovertemplate: '10^%{x:.1f}<br>Count: %{y}<extra></extra>'
    }, {
      x: [logMean, logMean], y: [0, Math.max(1, ratioVals.length/4)], type: 'scatter', mode: 'lines',
      line: { color: '#22c55e', width: 1.5, dash: 'dash' }, showlegend: false, hoverinfo: 'skip'
    }], {
      ...histBase,
      xaxis: {
        ...histBase.xaxis, title: { text: 'log10(ON/OFF)', font:{size:10} }, tickfont:{size:9}
      },
      yaxis: { ...histBase.yaxis, title: { text: 'Count', font:{size:10} }, tickfont:{size:9} },
      annotations: [{
        x: 0.05, y: 0.95, xref:'paper', yref:'paper', showarrow: false,
        text: String.fromCharCode(0x03BC)+' = '+Math.pow(10, logMean).toExponential(2),
        font: { size: 9, color: '#86efac' }, align: 'left',
        bgcolor: 'rgba(8,14,28,0.6)', bordercolor: 'rgba(32,70,130,0.4)', borderwidth:1, borderpad:4
      }]
    }, plotConfig);
  }
}

// ══════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════

function init() {
  var mats = window._MAT_KEYS || [];
  var matOptions = '';
  for (var i = 0; i < mats.length; i++) {
    matOptions += '<option>' + mats[i] + '</option>';
  }
  var headerMat = document.getElementById('header-material');
  if (headerMat) headerMat.innerHTML = matOptions;

  // Load first material's data
  if (mats.length > 0) {
    switchMaterial(mats[0]).then(function() {
      drawHeatmap(document.getElementById('heatmap-metric').value);
      drawHistograms();
    }).catch(function(e) {
      console.error('Failed to load data:', e);
      var info = document.getElementById('selected-device-info');
      if (info) info.innerHTML = '<span style="color:var(--red)">Error loading data: ' + e + '</span>';
    });
  } else {
    drawHeatmap();
    drawHistograms();
  }

  // Placeholder for Cycle Evolution
  Plotly.react('cycle-plot', [], {
    ...baseLayout, height: 190,
    annotations: [{ text: 'Cycle evolution analysis requires endurance cycling data.', showarrow: false, font: {size:11, color:'#4a6a96'}, xref:'paper',yref:'paper',x:0.5,y:0.5 }]
  }, plotConfig);

  // Placeholder for confidence plot
  Plotly.react('conf-plot', [], {
    ...baseLayout, height: 150,
    annotations: [{ text: 'Confidence scores calculated from switching detection quality.', showarrow: false, font: {size:11, color:'#4a6a96'}, xref:'paper',yref:'paper',x:0.5,y:0.5 }]
  }, plotConfig);
}

window.addEventListener('load', init);
window.addEventListener('resize', function() {
  ['heatmap-plot','iv-plot','hist-vset','hist-vreset','hist-ratio','cycle-plot','conf-plot'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el && el.layout) Plotly.Plots.resize(el);
  });
  if (selectedCell) drawIVPlot(selectedCell);
});
"""
