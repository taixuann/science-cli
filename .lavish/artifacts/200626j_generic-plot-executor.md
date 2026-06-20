# Implementation Plan: Generic Plot Executor

**Date**: 20/06/2026
**Status**: 🟡 Planning
**Layer**: 5 (Plotting Dispatch)
**Version**: v3.22.0 (proposed)

---

## Context Summary

The plot system currently has 14 separate Python files in `src/science_cli/plot/`, each with its own data loading, column selection, filtering, and matplotlib logic. The user wants **config to define everything, plot just for execution**. This means moving column mapping, axis labels, filtering, layout, and styling from Python code into `config-studies.yaml`, and having a single generic executor read config and plot.

Current state:
- `plot/registry.py` (311 lines) — STUDY_PLOTTERS dispatch, 12 dedicated plotters
- `plot/stp.py` (378 lines) — STP decay with twin-axis, --describe panel
- `plot/iv.py`, `cv.py`, `ca.py`, `raman.py`, `uv_vis.py`, `ppf.py`, `pulse_retention.py` — study-specific plotters
- `plot/pulse_endurance.py` — complex dual-panel with pre-processed CSV
- `plot/eis.py` — complex dual-panel Nyquist + Bode
- `plot/afm.py` — image-type plot
- `core/plot_config.py` (144 lines) — merges theme + study + device config

Target: 14 files → 4 files (generic.py + endurance.py + eis.py + afm.py)

---

## Objectives

1. Add `layout`, `columns`, `filter`, `annotations` blocks to all studies in config-studies.yaml
2. Create `plot/generic.py` — config-driven executor that handles 80% of studies
3. Simplify `plot/registry.py` — use generic as default, keep 3 complex plotters
4. Remove 9 study-specific plot files (stp.py, iv.py, cv.py, ca.py, raman.py, uv_vis.py, ppf.py, pulse_retention.py, overlays.py)
5. Update CLI plot command to route through new architecture

---

## Config Schema Additions

### New fields in `config-studies.yaml` per study

```yaml
study-name:
  plot:
    # EXISTING (already works)
    figure: {figsize: [3.46, 2.75]}
    axes: {xscale: log, yscale: log}
    series: {hrs: {color: "#CC0000", marker: "o"}}

    # NEW — layout type
    layout: single | dual_axis | dual_panel | grid_2x2

    # NEW — column mapping for plot
    columns:
      x: time           # column name or config key
      y: current        # column name or config key
      y2: voltage       # optional second Y axis (for dual_axis)

    # NEW — axis labels
    axis:
      xlabel: "Time (µs)"
      ylabel: "Current (A)"
      ylabel2: "Voltage (V)"  # optional for dual_axis

    # NEW — data filtering
    filter:
      field: voltage     # filter on this column
      min: 0.05          # exclude rows where value < min

    # NEW — current sign correction
    current_sign: -1     # multiply Y values by this

    # NEW — annotations (already exists for pulse-endurance)
    annotations:
      current:
        text: "I(t)"
        position: top_right
        color: "#CC0000"
```

### Example: pulse-stp-decay (currently 378 lines of Python)

```yaml
pulse:pulse-stp-decay:
  plot:
    layout: dual_axis
    columns:
      x: time
      y: current
      y2: voltage
    axis:
      xlabel: "Time (µs)"
      ylabel: "Current (A)"
      ylabel2: "Voltage (V)"
    current_sign: -1
    filter:
      field: voltage
      min: 0.05
    figure: {figsize: [3.46, 2.75]}
    series:
      current: {color: "tab:red", linewidth: 1.0}
      voltage: {color: "tab:blue", linewidth: 1.0}
```

### Example: iv-bipolar-sweep (currently 280 lines)

```yaml
iv:iv-bipolar-sweep:
  plot:
    layout: single
    columns:
      x: voltage
      y: current
    axis:
      xlabel: "Voltage (V)"
      ylabel: "Current (A)"
    current_sign: -1
    figure: {figsize: [3.46, 2.75]}
    series:
      sweep: {color: "#1f77b4", linewidth: 1.5}
```

---

## Files to Modify/Create

| File | Change | Risk |
|------|--------|------|
| `config/config-studies.yaml` | Add layout, columns, axis, filter, current_sign to all 13 studies | Low |
| `src/science_cli/plot/generic.py` | **NEW** — config-driven plot executor (~250 lines) | Medium |
| `src/science_cli/plot/registry.py` | Simplify — generic as default, keep 3 complex | Low |
| `src/science_cli/cli/commands/plot.py` | Route through registry → generic | Low |
| `src/science_cli/plot/stp.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/iv.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/cv.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/ca.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/raman.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/uv_vis.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/ppf.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/pulse_retention.py` | **DELETE** — replaced by generic | Low |
| `src/science_cli/plot/overlays.py` | **DELETE** — generic handles overlays | Low |

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Config schema update | code-medium | Add layout/columns/axis/filter to all studies |
| Generic executor | code-heavy | Core implementation — new plot/generic.py |
| Registry simplification | code-light | Update registry.py to use generic default |
| CLI routing | code-light | Update plot.py to route through new registry |
| Delete old files | code-light | Remove 9 replaced plot files |
| QA & Review | review-medium | Smoke test all studies, verify plots match |
| Documentation | docs-medium | Update sci-plot-config skill, README |

---

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | Add layout/columns/axis/filter/current_sign to all 13 studies in config-studies.yaml | 1h | code-medium |
| task-002 | Create plot/generic.py — config-driven executor with single, dual_axis, dual_panel layouts | 3h | code-heavy |
| task-003 | Simplify registry.py — generic as default, keep endurance/eis/afm | 30m | code-light |
| task-004 | Update CLI plot.py routing to use new architecture | 30m | code-light |
| task-005 | Delete 9 replaced plot files | 15m | code-light |
| task-006 | Run pytest tests/ -q — verify no regressions | 30m | review-medium |
| task-007 | Smoke test: sci plot on each study type | 1h | review-medium |
| task-008 | Update sci-plot-config skill with new architecture | 1h | docs-medium |

---

## Dependency Order

1. **task-001** (config) — no dependencies
2. **task-002** (generic.py) — depends on task-001 (needs config schema)
3. **task-003** (registry) — depends on task-002 (needs generic.py to exist)
4. **task-004** (CLI routing) — depends on task-003
5. **task-005** (delete old files) — depends on task-003, task-004
6. **task-006** (tests) — depends on task-005
7. **task-007** (smoke test) — depends on task-006
8. **task-008** (docs) — depends on task-007

---

## Risks

1. **STP --describe panel** — current stp.py has a complex --describe mode that extracts waveform parameters and shows a side panel. Generic executor won't support this initially. Mitigation: keep --describe as a flag that falls back to the old stp.py logic temporarily, or implement a simpler describe in generic.

2. **Overlay layouts** — current overlay logic varies per study (1x2 panels for STP, Nyquist+Bode for EIS). Generic needs to handle overlay_layout from config. Mitigation: add `overlay_layout: single | 1x2_panels | nyquist_bode` to config.

3. **IV gradient mode** — current iv.py has --gradient flag that colors sweep points by position. Generic won't support this initially. Mitigation: keep iv.py for --gradient mode, or add gradient as a config option.

4. **Data loading differences** — some studies load via load_data_file(), others read CSV directly. Generic needs a consistent loading strategy. Mitigation: always use load_data_file() with study_name, let data_loader handle instrument-specific loading.

---

## Generic Executor Design

```python
# plot/generic.py (~250 lines)

def _plot_generic(filepath: str, flags: dict, study_name: str) -> None:
    """Config-driven plot executor. Reads layout, columns, axis, filter from config."""
    
    # 1. Load config
    plot_cfg = resolve_plot_config(study_name)
    layout = plot_cfg.get("layout", "single")
    
    # 2. Load data
    df, info = load_data_file(filepath, study_name=study_name)
    
    # 3. Apply current_sign
    current_sign = float(plot_cfg.get("current_sign", 1))
    
    # 4. Apply filter
    filter_cfg = plot_cfg.get("filter")
    if filter_cfg:
        field = filter_cfg.get("field")
        min_val = filter_cfg.get("min")
        if field and min_val is not None:
            df = df[df[field] > min_val]
    
    # 5. Get columns
    x_col = plot_cfg.get("columns.x")
    y_col = plot_cfg.get("columns.y")
    y2_col = plot_cfg.get("columns.y2")  # optional
    
    # 6. Create figure based on layout
    if layout == "single":
        _plot_single(df, x_col, y_col, current_sign, plot_cfg, flags, filepath)
    elif layout == "dual_axis":
        _plot_dual_axis(df, x_col, y_col, y2_col, current_sign, plot_cfg, flags, filepath)
    elif layout == "dual_panel":
        _plot_dual_panel(df, plot_cfg, flags, filepath)
    
    # 7. Save
    _save_fig(plot_cfg, flags, filepath, study_name)


def _plot_single(df, x_col, y_col, sign, cfg, flags, filepath):
    """Single-axis X vs Y plot."""
    fig, ax = plt.subplots(figsize=cfg.get("figure.figsize"))
    ax.plot(df[x_col], df[y_col] * sign, **cfg.get("series.sweep", {}))
    ax.set_xlabel(cfg.get("axis.xlabel", x_col))
    ax.set_ylabel(cfg.get("axis.ylabel", y_col))
    # Apply axis settings (xscale, yscale, grid, xlim, ylim)
    _apply_axis_settings(ax, cfg)
    # Add annotations
    _add_annotations(ax, cfg)


def _plot_dual_axis(df, x_col, y_col, y2_col, sign, cfg, flags, filepath):
    """Dual Y-axis: y on left, y2 on right."""
    fig, ax1 = plt.subplots(figsize=cfg.get("figure.figsize"))
    ax2 = ax1.twinx()
    ax1.plot(df[x_col], df[y_col] * sign, **cfg.get("series.current", {}))
    ax2.plot(df[x_col], df[y2_col], **cfg.get("series.voltage", {}))
    ax1.set_ylabel(cfg.get("axis.ylabel", y_col))
    ax2.set_ylabel(cfg.get("axis.ylabel2", y2_col))
    _apply_axis_settings(ax1, cfg)
```

---

## Walkthrough

(To be filled during/after implementation)
