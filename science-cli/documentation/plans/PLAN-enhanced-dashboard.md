# PLAN: Enhanced Memristor Dashboard

## Classification
feature

## Related Plans
- [[PLAN-plotly-dashboard]] — supersedes — the Plotly dashboard was Phase 1; this PLAN enhances it

## Status
- **Created**: 2026-05-13
- **Status**: draft
- **Branch**: `mysci-tui_mem-advanced`

## Objective
Replace `dashboard.py` with the dark-themed interactive Plotly dashboard design from `documentation/memristor_dashboard_layout.html`, wired to real IV data from `devices.yaml`. Add Keithley 2400 / LabVIEW Measurement (.lvm) data format support, Vset/Vreset extraction (both abrupt and gradual switching detection), user-configurable V_read parameter, and ON/OFF ratio computation for the dashboard.

## Context
The existing `dashboard.py` generates a light-themed dashboard with per-cell `<details>` sections, material matrix tables, and a filter bar. The reference design (`documentation/memristor_dashboard_layout.html`) shows a sophisticated dark-themed dashboard with sidebar navigation, KPI cards, clickable crossbar heatmap, device explorer with tabs, histograms, cycle evolution, confidence panel, and a review table.

Data files are in **LabVIEW Measurement (.lvm) tab-separated format** from a Keithley 2400 sourcemeter:
- LabVIEW key-value metadata headers delimited by `***End_of_Header***`
- Column 0 (X_Value / index) = row counter, skipped
- Column 1 (Untitled) = Voltage (V)
- Column 2 (Untitled 1) = Current (A)
- Column 3 (Untitled 2) = Timestamp (s)
- Column 4 (Comment) = ignored

The user wants:
1. Full dark-theme dashboard layout from mockup (Phase 1: IV panels data-driven, cycle/confidence/review as placeholders)
2. `.lvm` file format reader with Keithley 2400 auto-detection
3. Vset/Vreset extraction from IV sweeps (derivative-based detection)
4. V_read auto-detection and ON/OFF ratio computation
5. All wired into dashboard KPIs, heatmap, histograms, and IV overlay

## Specification

### A. LabVIEW Measurement (.lvm) Format Handler — `plotting.py`

New function `read_iv_lvm()`:

1. **Header parsing**: Scan line-by-line for `***End_of_Header***` markers to find the two header blocks
   - Block 1: General metadata (Separator, Decimal_Separator, Date, Time, Operator)
   - Block 2: Channel info (Channels, Samples, X0, Delta_X)
2. **Column detection**: After 2nd `***End_of_Header***`, read column header line
   - `X_Value` = row index (skip)
   - `Untitled` = Voltage (V)
   - `Untitled 1` = Current (A)
   - `Untitled 2` = Timestamp (s)
   - `Comment` = ignore
3. **Data reading**: Parse tab-separated numeric data rows
4. **Return**: `(voltage, current, metadata)` where metadata includes date/time/operator from header
5. **Auto-detection**: Detect ``"LabVIEW Measurement"`` in first line of file; `read_iv_csv()` routes to this automatically

Column mapping logic:
- By position: col0=skip, col1=Voltage, col2=Current, col3=Timestamp, col4=Comment
- If file has < 3 data columns: raise ValueError
- Multi-Headings=Yes means 2 header blocks; read past both

### B. Keithley 2400 Device Config — `core/config.py` + `techniques`

Add hardcoded device entry for `keithley-2400` under `iv-sweep`:

```python
_DEFAULT_TECHNIQUE_DEVICES = {
    "iv-sweep": {
        "keithley-2400": {
            "delimiter": "\t",
            "decimal": ".",
            "header_lines": 23,  # 2 LVM header blocks + column line
            "encoding": "utf-8",
            "columns": {
                "voltage": "Untitled",
                "current": "Untitled 1",
                "time": "Untitled 2",
            },
        },
    },
}
```

Add `iv-sweep` patterns for `.lvm` files:
```python
"iv-sweep": [
    r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_",
    r"\.lvm$",  # ← add LabVIEW Measurement format
]
```

### C. IV Parameter Extraction — `switching.py`

New functions for switching parameter detection:

**`detect_vset(voltage, current, v_read=0.1)`** → `float | None`
- Split bipolar sweep into forward (0→+Vmax) and backward (+Vmax→0) branches using reversal detection (reuse `_split_at_reversals()`)
- **Combined detection method** (catches both abrupt and gradual transitions):
  1. *Derivative method*: Compute d(log10|I|)/dV, find max (abrupt switching)
  2. *Threshold method*: Find where |I| exceeds baseline × threshold factor (gradual switching)
  3. Use the earlier (lower-voltage) result as Vset — this captures the onset of switching whether abrupt or gradual
- Return the switching voltage, or None if neither method detects clear switching

**`detect_vreset(voltage, current, v_read=0.1)`** → `float | None`
- Operates on negative sweep segments (0→-Vmax)
- Combined detection (derivative min + current drop threshold)
- Return reset voltage or None

**`compute_on_off_ratio(voltage, current, v_read=0.1)`** → `dict`
- `v_read` is user-settable (default 0.1V); no auto-detection
- Split sweep into forward (0→+Vmax) and backward (+Vmax→0) branches
- Interpolate current at v_read on both branches
- Forward branch current = I_off (device in HRS before switching)
- Backward branch current = I_on (device in LRS after switching)
- Compute: R_on = v_read / I_on, R_off = v_read / I_off, ratio = R_off / R_on
- Return: `{"v_read": float, "i_on": float, "i_off": float, "r_on": float, "r_off": float, "ratio": float}`

**`extract_iv_parameters(voltage, current, v_read=0.1)`** → `dict`
- Convenience wrapper calling detect_vset, detect_vreset, compute_on_off_ratio
- Returns: `{"v_set": ..., "v_reset": ..., "on_off_ratio": ..., "v_read": ..., "switching_detected": bool}`

### D. Enhanced Dashboard — `dashboard.py` (full rewrite)

**Architecture**: Same `generate_dashboard(config, results_dir, output_path)` API.

**Data Collection** (Phase 1 — IV-driven):
| Panel | Data Source | Real Data? |
|-------|------------|------------|
| KPI: Cells | `config.measured_cells / total_cells` | Yes |
| KPI: IV Files | `config.get_all_files("iv")` + file count | Yes |
| KPI: Materials | `get_points_by_material()` | Yes |
| KPI: Median Vset | `detect_vset()` across all devices | Yes |
| KPI: Median Vreset | `detect_vreset()` across all devices | Yes |
| KPI: ON/OFF Ratio | `compute_on_off_ratio()` across all devices | Yes |
| KPI: Yield | Fraction of cells with switching detected | Yes |
| Heatmap | Per-cell switching metric (ON/OFF ratio / yield / Vset / Vreset) | Yes |
| IV Overlay | All IV sweeps for selected cell via `read_iv_csv()`/`read_iv_lvm()` | Yes |
| Histograms | Vset, Vreset, ON/OFF ratio distributions | Yes |
| Cycle Evolution | Empty placeholder panel | Placeholder |
| Confidence | Empty placeholder panel | Placeholder |
| Review Table | Empty state | Placeholder |

**Layout** (exact mockup fidelity, all sections rendered):
```
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR (240px)  │  HEADER (selectors, search, export) │
│ ┌──────────────┐ │  ┌─────────────────────────────────┐│
│ │ Logo/Title   │ │  │ KPI Row (4 metric cards)        ││
│ │ Navigation   │ │  ├─────────────────────────────────┤│
│ │ Filters      │ │  │ Heatmap     │  Device Explorer  ││
│ │ Color Map    │ │  │ (clickable) │  (IV Overlay tab) ││
│ │ Device Info  │ │  ├─────────────────────────────────┤│
│ │ Review Queue │ │  │ Vset Hist  │ Vreset Hist │ Ratio││
│ │ Summary      │ │  ├─────────────────────────────────┤│
│ │ Quick Actions│ │  │ Cycle Evo  │  Confidence        ││
│ └──────────────┘ │  ├─────────────────────────────────┤│
│                   │  │ Review Table (empty state)     ││
└─────────────────────────────────────────────────────────┘
```

**CSS**: Full dark theme from mockup
- CSS variables: `--bg-deep: #050a14`, `--cyan: #00d4ff`, `--blue: #3b82f6`, etc.
- Fonts: JetBrains Mono (mono), DM Sans (UI) via Google Fonts CDN
- Sidebar, header, KPI cards, panels, tables, scrollbar styling
- Plotly transparent backgrounds + custom config
- Animations: glow pulses, hover transitions

**JavaScript**: Interactive elements from mockup
1. **Heatmap click → update all panels**: Click a cell on the heatmap → updates Device Info sidebar, IV Overlay plot, device badge, selected cell label
2. **Tab switching**: IV Overlay tab active; Extracted Params / Cycle Evo / Raw Data tabs show placeholder content
3. **Heatmap metric selector**: Dropdown to color heatmap by ON/OFF ratio / Vset / Vreset / Yield
4. **Sidebar filters**: Measurement Type, Material, Cycle Range sliders, Sweep Direction, Compliance, toggles (log scale, overlay mode, highlight outliers) — wired to show/hide plot-figure elements
5. **Color Map By radio**: Radio group for heatmap coloring metric
6. **Search box**: Filter device cells by ID

All JS interacts with pre-rendered Plotly divs (show/hide, no re-render needed for tab switching). Heatmap click triggers Plotly.relayout/restyle for selected cell highlight.

### E. `switching.py` — Add `analyze_all_devices()`

New function to batch-process all IV files in a `DeviceConfig`:

```python
def analyze_all_devices(config, results_dir) -> dict:
    """Run switching analysis across all IV files in config.
    
    Returns dict with:
      - per_device: { (row, col): { v_set, v_reset, ratio, ... } }
      - aggregate: { median_vset, median_vreset, median_ratio, yield_pct }
      - histograms: { vset_bins, vreset_bins, ratio_bins }
    """
```

This feeds directly into the dashboard's KPI cards, heatmap, and histograms.

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | **Rewrite** | Replace with new dark-themed interactive dashboard |
| `src/science_cli/memristor/plotting.py` | **Add** `read_iv_lvm()` + route detection in `read_iv_csv()` | Support Keithley 2400 LabVIEW Measurement format |
| `src/science_cli/memristor/switching.py` | **Add** `detect_vset()`, `detect_vreset()`, `compute_on_off_ratio()`, `detect_read_voltage()`, `analyze_all_devices()` | IV parameter extraction for dashboard |
| `src/science_cli/core/config.py` | **Add** keithley-2400 hardcoded device defaults, `.lvm` pattern to iv-sweep | Auto-detection of LabVIEW Measurement format |
| `documentation/plans/PLAN-enhanced-dashboard.md` | **Create** | This plan |

## Dependencies
- Existing `memristor/device.py` (DeviceConfig, FileEntry, MatrixPoint)
- Existing `memristor/plotting.py` (`read_iv_csv()`, `collect_iv_files()`, `_build_sweep_from_data()`)
- Existing `memristor/switching.py` (will add new functions)
- New: `detect_vset()`, `detect_vreset()` in switching.py
- Plotly.js 2.35.2 (CDN, same as current)
- Google Fonts CDN (JetBrains Mono, DM Sans)
- No new Python dependencies

## Test Strategy
1. **LVM reader**: Place a known `.lvm` file in a test protocol dir, run `read_iv_lvm()`, verify voltage/current arrays match expected values
2. **Vset/Vreset detection**: Feed synthetic IV data with known switching thresholds, verify detection within 5% accuracy
3. **ON/OFF ratio**: Verify computation matches manual calculation for simple cases
4. **Dashboard generation**: Run `memristor dashboard --open` on a real project with Keithley 2400 .lvm data
5. **Visual comparison**: Verify layout matches `documentation/memristor_dashboard_layout.html`
6. **Interactivity**: Click heatmap cell → verify all panels update, tabs switch

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT: `read_iv_lvm()` in plotting.py + auto-detection
- [ ] IMPLEMENT: Keithley 2400 config in core/config.py
- [ ] IMPLEMENT: `detect_vset()`, `detect_vreset()`, `compute_on_off_ratio()`, `detect_read_voltage()` in switching.py
- [ ] IMPLEMENT: `analyze_all_devices()` in switching.py
- [ ] IMPLEMENT: Dashboard data collection (per-device metrics)
- [ ] IMPLEMENT: Dashboard Plotly figure generators (heatmap, IV overlay, histograms, sparklines)
- [ ] IMPLEMENT: Dashboard HTML layout (sidebar, header, KPI row, panels, review table)
- [ ] IMPLEMENT: Dashboard CSS (dark theme from mockup)
- [ ] IMPLEMENT: Dashboard JavaScript (click-to-select, tabs, filters, search)
- [ ] TEST: LVM reader with real Keithley 2400 data
- [ ] TEST: Vset/Vreset detection with known test data
- [ ] TEST: Dashboard generation on real project
- [ ] TEST: All guardrail tests pass
- [ ] COMMIT to `mysci-tui_mem-advanced` branch
