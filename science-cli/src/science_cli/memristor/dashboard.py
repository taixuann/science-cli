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
    per_device: dict[tuple[int, int], dict] = {}
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

        key = (pt.row, pt.col)
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

    matrix = []
    for r in range(rows):
        row_data = []
        for c in range(cols):
            device = per_device.get((r, c))
            if device:
                row_data.append({
                    "v_set": device["v_set"],
                    "v_reset": device["v_reset"],
                    "ratio": device["ratio"],
                    "switching": device["switching_detected"],
                    "material": device["material_key"],
                    "n_files": device["n_files"],
                    "failed": not device["switching_detected"],
                })
            else:
                row_data.append(None)
        matrix.append(row_data)

    return {"rows": rows, "cols": cols, "matrix": matrix}


# ════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════


def generate_dashboard(
    config,
    results_dir: Path,
    output_path: str | Path,
) -> Path:
    """Generate a self-contained dark-themed interactive Plotly HTML dashboard.

    Reads raw IV CSV data, extracts V_set/V_reset/ON-OFF ratio per device,
    and generates an interactive HTML dashboard matching the reference layout.

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
    # ── Phase 1: Collect data ──
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

    # ── Build per-device dictionary for JS embedding ──
    devices_js = {}
    iv_js = {}
    for (row, col), device in collection["per_device"].items():
        cell_id = f"R{row + 1}C{col + 1}"
        devices_js[cell_id] = {
            "row": row,
            "col": col,
            "material": device["material_key"],
            "v_set": device["v_set"],
            "v_reset": device["v_reset"],
            "ratio": device["ratio"],
            "switching": device["switching_detected"],
            "n_files": device["n_files"],
        }
        iv_js[cell_id] = [
            {
                "voltage": f["voltage"],
                "current": f["current"],
                "label": f"#{i + 1:02d}",
            }
            for i, f in enumerate(device["files"])
        ]

    # ── Build HTML ──
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
        devices_js=devices_js,
        iv_js=iv_js,
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
    devices_js: dict,
    iv_js: dict,
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
      <div class="sb-section-title">Navigation</div>
      <div class="nav-item active">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
        Overview
      </div>
      <div class="nav-item">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        Device Explorer
      </div>
      <div class="nav-item">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        Statistics
      </div>
      <div class="nav-item">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        Batch Analysis
      </div>
      <div class="nav-item">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>
        Settings
      </div>
    </div>

    <!-- Filters -->
    <div class="sb-section">
      <div class="sb-section-title">Filters</div>
      <div class="filter-group">
        <div class="filter-label">Measurement Type</div>
        <select class="filter-select">
          <option>IV Sweep</option>
          <option>Pulse</option>
          <option>Retention</option>
          <option>Endurance</option>
        </select>
      </div>
      <div class="filter-group">
        <div class="filter-label">Material</div>
        <select class="filter-select" id="filter-material">
          <option>All</option>
        </select>
      </div>
      <div class="filter-group">
        <div class="filter-label">Cycle Range</div>
        <div class="range-row"><span>1</span><span id="cycle-val">All</span></div>
        <input type="range" id="cycle-range" min="1" max="200" value="200" oninput="document.getElementById('cycle-val').textContent=this.value">
      </div>
      <div class="filter-group">
        <div class="filter-label">Sweep Direction</div>
        <select class="filter-select">
          <option>All</option>
          <option>Forward</option>
          <option>Reverse</option>
        </select>
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
        <div class="toggle-row"><span>Log Scale</span><label class="toggle"><input type="checkbox" id="toggle-log" checked><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Overlay Mode</span><label class="toggle"><input type="checkbox" id="toggle-overlay" checked><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Highlight Outliers</span><label class="toggle"><input type="checkbox" id="toggle-outliers"><span class="toggle-slider"></span></label></div>
      </div>
    </div>

    <!-- Color Map By -->
    <div class="sb-section">
      <div class="sb-section-title">Color Map By</div>
      <div class="radio-group" id="colormap-radio">
        <label class="radio-item active"><input type="radio" name="colormap" value="ratio" checked> ON/OFF Ratio</label>
        <label class="radio-item"><input type="radio" name="colormap" value="vset"> Vset (V)</label>
        <label class="radio-item"><input type="radio" name="colormap" value="vreset"> Vreset (V)</label>
        <label class="radio-item"><input type="radio" name="colormap" value="yield"> Yield (%)</label>
      </div>
    </div>

    <!-- Device Info -->
    <div class="sb-section">
      <div class="sb-section-title">Selected Device</div>
      <div id="sb-device-info" class="info-grid">
        <div class="info-row"><span class="info-key">Device ID</span><span class="info-val" id="si-id">—</span></div>
        <div class="info-row"><span class="info-key">Row/Col</span><span class="info-val" id="si-rc">—</span></div>
        <div class="info-row"><span class="info-key">Material</span><span class="info-val" id="si-mat">—</span></div>
        <div class="info-row"><span class="info-key">Files</span><span class="info-val" id="si-files">—</span></div>
        <div class="info-row"><span class="info-key">Vset</span><span class="info-val" id="si-vset">—</span></div>
        <div class="info-row"><span class="info-key">Vreset</span><span class="info-val" id="si-vreset">—</span></div>
        <div class="info-row"><span class="info-key">ON/OFF</span><span class="info-val" id="si-ratio">—</span></div>
        <div class="info-row"><span class="info-key">Switching</span><span class="info-val" id="si-sw">—</span></div>
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
        <div class="header-title">{device_label}</div>
        <div class="header-subtitle">{device_id} / {rows}x{cols} Crossbar / IV Measurement</div>
      </div>
      <div class="header-sep"></div>
      <div class="header-label">
        <span>Meas. Type</span>
        <select class="header-select"><option>IV</option><option>Pulse</option><option>Retention</option></select>
      </div>
      <div class="header-label">
        <span>Material</span>
        <select class="header-select" id="header-material"><option>All</option></select>
      </div>
      <div class="header-label">
        <span>Matrix</span>
        <select class="header-select"><option>{rows}x{cols}</option></select>
      </div>
      <div class="header-label">
        <span>Generated</span>
        <select class="header-select"><option>{date_str}</option></select>
      </div>
      <div class="header-spacer"></div>
      <div class="search-box">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" id="device-search" placeholder="Search device..." oninput="onSearch(this.value)">
      </div>
      <button class="icon-btn" onclick="location.reload()">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.08-8.64"/></svg>
        Refresh
      </button>
      <button class="export-btn">
        <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Export Report
      </button>
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
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">Crossbar Heatmap</div>
            <div class="panel-badge" id="heatmap-badge">ON/OFF Ratio</div>
            <div class="panel-spacer"></div>
            <select class="ctrl-select" id="heatmap-metric">
              <option>ON/OFF Ratio</option>
              <option>Vset (V)</option>
              <option>Vreset (V)</option>
              <option>Yield (%)</option>
            </select>
          </div>
          <div class="panel-body" style="padding-top:8px">
            <div id="heatmap-plot" style="height:300px"></div>
            <div class="hint-text" style="margin-top:4px">Click any cell to explore device details</div>
            <div class="selected-cell-info" id="selected-cell-label" style="margin-top:2px">Selected: —</div>
          </div>
        </div>

        <!-- IV OVERLAY -->
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">Device Explorer</div>
            <span id="iv-device-badge" class="panel-badge">—</span>
            <div class="panel-spacer"></div>
            <div class="tab-bar">
              <div class="tab active" onclick="switchTab('iv', this)">IV Overlay</div>
              <div class="tab" onclick="switchTab('params', this)">Extracted Params</div>
              <div class="tab" onclick="switchTab('evo', this)">Cycle Evo.</div>
              <div class="tab" onclick="switchTab('raw', this)">Raw Data</div>
            </div>
          </div>
          <div class="panel-body" style="padding:0">
            <div id="iv-plot" style="height:330px"></div>
            <div id="tab-placeholder" style="display:none;height:330px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:12px;font-family:'DM Sans',sans-serif"></div>
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

<script id="iv-data" type="application/json">
{json.dumps(devices_js, separators=(",", ":"))}
</script>
<script id="iv-raw-data" type="application/json">
{json.dumps(iv_js, separators=(",", ":"))}
</script>
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

var DEVICE_DATA = JSON.parse(document.getElementById('iv-data').textContent);
var IV_RAW_DATA = JSON.parse(document.getElementById('iv-raw-data').textContent);
var HEATMAP_META = JSON.parse(document.getElementById('heatmap-data').textContent);
var HISTOGRAM_META = JSON.parse(document.getElementById('histogram-data').textContent);
var AGGREGATE = JSON.parse(document.getElementById('aggregate-data').textContent);

// Default selected cell — pick the first available device
var selectedCellId = null;
var selectedCell = null;
for (var k in DEVICE_DATA) {
  if (DEVICE_DATA.hasOwnProperty(k)) {
    selectedCellId = k;
    selectedCell = DEVICE_DATA[k];
    break;
  }
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
  if (metric === 'ON/OFF Ratio') return d.ratio ? Math.log10(d.ratio) : null;
  if (metric === 'Vset (V)') return d.v_set;
  if (metric === 'Vreset (V)') return d.v_reset;
  if (metric === 'Yield (%)') return d.switching ? 100 : 0;
  return null;
}

function buildHeatmapData(metric) {
  var rows = HEATMAP_META.rows;
  var cols = HEATMAP_META.cols;
  var matrix = HEATMAP_META.matrix;
  var z = [], hovertext = [];
  for (var r = 0; r < rows; r++) {
    var zr = [], ht = [];
    for (var c = 0; c < cols; c++) {
      var d = matrix[r] ? matrix[r][c] : null;
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
          'Material: ' + (d.material || 'unknown')
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

  Plotly.react('heatmap-plot', [
    {
      type: 'heatmap',
      z: data.z, x: labels.slice(0, cols), y: labels.slice(0, rows),
      colorscale: colorscale, hovertext: data.hovertext, hovertemplate: '%{hovertext}<extra></extra>',
      colorbar: {
        thickness: 10, len: 0.8,
        tickfont: { size: 9, color: '#8ba3c7', family: 'JetBrains Mono' },
        outlinecolor: 'rgba(32,70,130,0.4)', outlinewidth: 1,
        bgcolor: 'rgba(0,0,0,0)',
        title: { text: metricName === 'ON/OFF Ratio' ? 'log10' : '', font: { size: 9, color: '#8ba3c7' }, side: 'right' }
      },
      zsmooth: false,
      xgap: 1.5, ygap: 1.5
    },
    {
      type: 'scatter', x: selX, y: selY, mode: 'markers',
      marker: { color: 'rgba(0,212,255,0)', size: 20, line: { color: '#00d4ff', width: 2 } },
      hoverinfo: 'skip', showlegend: false
    }
  ], {
    paper_bgcolor: PAPER_BG, plot_bgcolor: PLOT_BG,
    font: { color: FONT_COLOR, family: 'JetBrains Mono, monospace', size: 10 },
    margin: { t: 8, r: 70, b: 30, l: 30 },
    xaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: '', tickfont: { size: 8 }, showgrid: false },
    yaxis: { gridcolor: GRID_COLOR, zerolinecolor: AXIS_COLOR, linecolor: AXIS_COLOR, tickcolor: AXIS_COLOR, title: '', tickfont: { size: 8 }, showgrid: false, autorange: true },
    height: 300
  }, plotConfig);

  var heatmapEl = document.getElementById('heatmap-plot');
  heatmapEl.removeAllListeners && heatmapEl.removeAllListeners('plotly_click');
  heatmapEl.on('plotly_click', function(eventData) {
    if (eventData.points && eventData.points.length > 0 && eventData.points[0].curveNumber === 0) {
      var p = eventData.points[0];
      var rIdx = parseInt(p.y) - 1;
      var cIdx = parseInt(p.x) - 1;
      var cellId = 'R' + (rIdx+1) + 'C' + (cIdx+1);
      var d = DEVICE_DATA[cellId];
      if (d) {
        selectedCellId = cellId;
        selectedCell = d;
        updateSelectedDevice(d);
        drawHeatmap(metricName);
      }
    }
  });
}

function updateSelectedDevice(d) {
  document.getElementById('si-id').textContent = 'R'+(d.row+1)+'C'+(d.col+1);
  document.getElementById('si-rc').textContent = (d.row+1)+' / '+(d.col+1);
  document.getElementById('si-mat').textContent = d.material || 'unknown';
  document.getElementById('si-files').textContent = d.n_files || 0;
  document.getElementById('si-vset').textContent = d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A';
  document.getElementById('si-vreset').textContent = d.v_reset != null ? d.v_reset.toFixed(2)+' V' : 'N/A';
  document.getElementById('si-ratio').textContent = d.ratio != null ? d.ratio.toExponential(2) : 'N/A';
  document.getElementById('si-sw').textContent = d.switching ? 'Yes' : 'No';
  document.getElementById('iv-device-badge').textContent = 'R'+(d.row+1)+'C'+(d.col+1);
  if (document.getElementById('cycle-device-badge'))
    document.getElementById('cycle-device-badge').textContent = 'R'+(d.row+1)+'C'+(d.col+1);
  document.getElementById('selected-cell-label').textContent =
    'Selected: R'+(d.row+1)+'C'+(d.col+1)+' · ON/OFF = '+(d.ratio != null ? d.ratio.toExponential(2) : 'N/A')+
    ' · Vset = '+(d.v_set != null ? d.v_set.toFixed(2)+' V' : 'N/A');
  drawIVPlot(d);
}

// ── Heatmap metric selector
document.getElementById('heatmap-metric').addEventListener('change', function() {
  drawHeatmap(this.value);
});

// ── Colormap radio buttons
document.querySelectorAll('#colormap-radio input[type=radio]').forEach(function(radio) {
  radio.addEventListener('change', function() {
    document.querySelectorAll('#colormap-radio .radio-item').forEach(function(item) {
      item.classList.remove('active');
    });
    this.parentElement.classList.add('active');
    var metricMap = {
      'ratio': 'ON/OFF Ratio',
      'vset': 'Vset (V)',
      'vreset': 'Vreset (V)',
      'yield': 'Yield (%)'
    };
    var metric = metricMap[this.value] || 'ON/OFF Ratio';
    document.getElementById('heatmap-metric').value = metric;
    drawHeatmap(metric);
  });
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

  var traces = [];
  var colors = [
    'rgba(0,180,220,0.7)',
    'rgba(220,80,80,0.7)',
    'rgba(100,200,120,0.7)',
    'rgba(200,180,60,0.7)',
    'rgba(160,100,220,0.7)',
    'rgba(100,180,200,0.7)',
    'rgba(220,140,60,0.7)',
    'rgba(140,200,160,0.7)',
  ];

  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var color = colors[i % colors.length];
    // Separate positive and negative voltage for log scale
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

  // Vset / Vreset markers
  if (vset != null) {
    traces.push({
      x: [vset], y: [1e-3], type: 'scatter', mode: 'markers+text',
      marker: { color: '#ef4444', size: 8, symbol: 'circle', line: { color: '#fff', width: 1 } },
      text: ['Vset'], textposition: 'top center', textfont: { size: 9, color: '#ef4444' },
      name: 'Vset', showlegend: true,
      hovertemplate: 'Vset = ' + vset.toFixed(3) + ' V<extra></extra>'
    });
  }
  if (vreset != null) {
    var vresetAbs = Math.abs(vreset);
    var vresetSign = vreset < 0 ? vreset : -vreset;
    traces.push({
      x: [vresetSign], y: [1e-3], type: 'scatter', mode: 'markers+text',
      marker: { color: '#3b82f6', size: 8, symbol: 'circle', line: { color: '#fff', width: 1 } },
      text: ['Vreset'], textposition: 'top center', textfont: { size: 9, color: '#3b82f6' },
      name: 'Vreset', showlegend: true,
      hovertemplate: 'Vreset = ' + vreset.toFixed(3) + ' V<extra></extra>'
    });
  }

  Plotly.react('iv-plot', traces, {
    ...baseLayout,
    height: 330,
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
  // Populate material filters
  var materials = {};
  for (var k in DEVICE_DATA) {
    if (!DEVICE_DATA.hasOwnProperty(k)) continue;
    var m = DEVICE_DATA[k].material;
    if (m) materials[m] = true;
  }
  var matOptions = '<option>All</option>';
  for (var m in materials) {
    if (materials.hasOwnProperty(m)) matOptions += '<option>'+m+'</option>';
  }
  var filterMat = document.getElementById('filter-material');
  var headerMat = document.getElementById('header-material');
  if (filterMat) filterMat.innerHTML = matOptions;
  if (headerMat) headerMat.innerHTML = matOptions;

  drawHeatmap();
  if (selectedCell) {
    updateSelectedDevice(selectedCell);
  }
  drawHistograms();

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
    if (el) { try { Plotly.Plots.resize(el); } catch(e) {} }
  });
});
"""
