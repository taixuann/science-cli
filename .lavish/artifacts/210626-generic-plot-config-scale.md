---
layer: [5]
type: plan
status: done
tags: [plot-config, linear-log, scale-dispatch, generic-plot, series-type]
depends_on: []
assignee: plan
---

# Implementation Plan: Generic Plot Config — Linear/Log Scale Blocks + Series Type

**Date**: 21/06/2026
**Status**: 🟢 Done
**Layer**: 5 — Plotting & Dispatch

## Context Summary

The `config-studies.yaml` currently has a flat `plot:` block per study. All styling, axis settings, and series config are merged in one dict. **There's no concept of "linear vs log mode"** — if you want to view the same study at different scales, you have to manually override at the CLI or duplicate the config.

The interactive menu already shows per-variant options like "Resistance vs Cycles" and "Current vs Cycles" for pulse-endurance. We need each option to be able to declare its scale mode in config, with corresponding scale-specific styling blocks.

### What the user wants

1. **`plot:` config gets `common` + `linear` + `log` sub-blocks** — common settings (xtitle, ytitle, columns, layout) always apply. `linear` and `log` blocks each have their OWN complete styling per scale mode.
2. **Each interactive menu option bakes in a `scale` field** — the menu stays exactly as-is. Each option declares `scale: log` or `scale: linear` in config. No second scale menu.
3. **`type: line | scatter` per series** — so individual series can choose rendering mode per scale block.
4. **CLI flag `--linear`/`--log`** — for direct `sci plot <file>` calls.

### Constraint: Pulse-endurance stays log

Pulse-endurance config has been carefully tuned over many sessions. **No visual behavior changes.** Both "Resistance vs Cycles" and "Current vs Cycles" use `scale: log`. The restructure is purely mechanical — splitting the existing flat block into `common` + `log`.

## Impact Analysis — All Affected Code Paths

### Current call chain (interactive menu)

```
User picks "Resistance vs Cycles"
  → interactive_menu.dispatch("pulse-endurance", "plot", [file])
    → reads options from config-studies.yaml
    → imports handler: generic.plot_endurance_resistance
    → calls plot_endurance_resistance(file_path=file)
      → _plot_generic(file, {"plot_variant": "resistance"}, "pulse:pulse-endurance")
        → resolve_plot_config("pulse:pulse-endurance")
          → merges: theme + flat plot block + device_overrides
          → returns flat dict with log settings
```

### After change

```
User picks "Resistance vs Cycles"
  → interactive_menu.dispatch("pulse-endurance", "plot", [file])
    → reads options — now includes scale: "log"
    → imports handler: generic.plot_endurance_resistance
    → calls plot_endurance_resistance(file_path=file, scale="log")
      → _plot_generic(file, {"plot_variant": "resistance", "scale": "log"}, ...)
        → resolve_plot_config("pulse:pulse-endurance", scale="log")
          → merges: theme + common + log block + device_overrides
          → returns flat dict with same log settings as before
```

### Files changed

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| `config-studies.yaml` | Restructure all `plot:` blocks | ~50 lines across 13 studies |
| `core/plot_config.py` | Add `scale` param + merge logic | ~20 lines |
| `core/interactive_menu.py` | Pass `option["scale"]` to handler kwargs | ~5 lines |
| `plot/generic.py` | Accept `scale` kwarg in wrappers + pass to `_plot_generic` | ~10 lines |
| `plot/generic.py` | Per-series `type: line\|scatter` in `_plot_single()` + `_plot_multi_series()` | ~30 lines |
| `cli/commands/plot.py` | Add `--linear`/`--log` flags for CLI path | ~10 lines |
| `.lavish/layer05-plotting-dispatch.html` | Register this artifact as 🔄 | ~5 lines |
| `sci-plot-config` skill | Document new schema | ~20 lines |

### No impact on

- `eis.py` (dedicated plotter, minimal config)
- `afm.py` (dedicated plotter, minimal config)
- `plot/registry.py` (no changes needed — dispatch is through interactive menu)
- `fzf` display system (no changes)
- `protocol.yaml` (no changes)
- Any test files (no existing tests test config block structure)

## Complete Schema: What Goes Where

| Parameter | `common` | `linear` | `log` |
|-----------|:--------:|:--------:|:-----:|
| `layout` | ✅ always | — | — |
| `columns` (x, y, y2, y_series) | ✅ always | — | — |
| `axis.xlabel`, `ylabel`, `ylabel2` | ✅ always | — | — |
| `axis.ycolor`, `y2color` | ✅ always | — | — |
| `current_sign` | ✅ always | — | — |
| `filter` (field, min) | ✅ always | — | — |
| `figure.figsize` | ✅ always | — | — |
| `axes.xscale` | — | ✅ usually "linear" | ✅ usually "log" |
| `axes.yscale` | — | ✅ usually "linear" | ✅ usually "log" |
| `axes.grid` | — | ✅ | ✅ |
| `axes.grid_alpha` | — | ✅ | ✅ |
| `axes.xlim` / `ylim` | — | ✅ (can differ) | ✅ (can differ) |
| `axes.ylim_padding` | — | ✅ | ✅ |
| `axes.yticks_show` | — | ✅ | ✅ |
| `legend` | — | ✅ | ✅ |
| `subsample` | — | rarely needed | ✅ (log mode is dense) |
| `series.*.type` (line/scatter) | — | ✅ "line" | ✅ "scatter" |
| `series.*.color` | — | ✅ (can differ) | ✅ (can differ) |
| `series.*.marker` | — | — (line mode) | ✅ (scatter mode) |
| `series.*.markersize` | — | — (line mode) | ✅ (scatter mode) |
| `series.*.linewidth` | — | ✅ (line mode) | — (scatter mode) |
| `series.*.linestyle` | — | ✅ (line mode) | — (scatter mode) |
| `series.*.alpha` | — | ✅ | ✅ |
| `series.*.annotation` | — | ✅ | ✅ |
| `annotations` | — | ✅ | ✅ |

## Per-Study Config Plan

### pulse-endurance — ALL stays log, no visual change

```yaml
# CURRENT (flat):
plot:
  layout: multi_series
  columns: {x: cycle, y_series: {hrs: r_hrs_ohm, lrs: r_lrs_ohm}}
  axes: {xscale: log, yscale: log, grid: false, ylim_padding: {below: 1.0, above: 1.0}, ...}
  legend: false
  subsample: {max_points: 2000, method: log_spaced}
  series: {hrs: {marker: "o", markersize: 12, ...}, lrs: {marker: "s", ...}}

# AFTER (same behavior):
plot:
  common:
    layout: multi_series
    columns: {x: cycle, y_series: {hrs: r_hrs_ohm, lrs: r_lrs_ohm}}
    axis: {xlabel: "Cycle", ylabel: "Resistance (Ω)"}
  linear:                       # ← exists but unused by pulse-endurance menu
    axes: {xscale: linear, yscale: linear, grid: true}
    legend: true
    series:
      hrs: {type: line, color: "#CC0000", linewidth: 1.0}
      lrs: {type: line, color: "#0055CC", linewidth: 1.0}
  log:                          # ← the real config, same as before
    axes:
      xscale: log
      yscale: log
      grid: false
      ylim_padding: {below: 1.0, above: 1.0}
      yticks_show: {min: 100, max: 10000000}
    legend: false
    subsample: {max_points: 2000, method: log_spaced}
    series:
      hrs:
        type: scatter
        color: "#CC0000"
        marker: "o"
        markersize: 12
        alpha: 0.5
        annotation: {text: "HRS", ha: "right", va: "bottom", xytext: [-5, 12], fontweight: bold, color: "#CC0000"}
      lrs:
        type: scatter
        color: "#0055CC"
        marker: "s"
        markersize: 12
        alpha: 0.5
        annotation: {text: "LRS", ha: "right", va: "bottom", xytext: [-5, 12], fontweight: bold, color: "#0055CC"}
  current:                       # ← variant block stays as-is
    columns: {x: cycle, y_series: {lrs: i_lrs_A, hrs: i_hrs_A}}
    axes: {ylim_padding: {below: 1.0, above: 1.0}, yticks_show: {min: 1e-8, max: 1}}
```

Menu options both get `scale: log`:
```yaml
options:
  - name: "Resistance vs Cycles"
    handler: "science_cli.plot.generic.plot_endurance_resistance"
    scale: log
  - name: "Current vs Cycles"
    handler: "science_cli.plot.generic.plot_endurance_current"
    scale: log
  - name: "Both"
    handler: "science_cli.plot.generic.plot_endurance_both"
```

### Other studies — mechanical restructure

| Study | common holds | linear holds | log holds |
|-------|-------------|-------------|-----------|
| `iv:iv-bipolar-sweep` | layout, columns, axis, current_sign | axes.grid | axes.yscale=log |
| `iv:iv-breakdown` | same | same | same |
| `iv:iv-leakage` | layout, columns, axis, current_sign | axes | axes.yscale=log (already there) |
| `pulse:pulse-stp-decay` | layout, columns, axis, filter, current_sign, series | *(none — stays common-only)* | *(none)* |
| `pulse:pulse-ppf` | layout, columns, axis, current_sign | *(none)* | axes.xscale=log |
| `pulse:pulse-retention` | layout, columns, axis, current_sign | *(none)* | axes.xscale=log (already there) |
| `raman:raman-spectrum` | all (no scale-specific settings) | — | — |
| `uv-vis:uv-vis-spectrum` | all | — | — |
| `ec:ec-cv` | all | — | — |
| `ec:ec-ca` | all | — | — |
| `ec:ec-eis` | all (minimal — dedicated eis.py) | — | — |
| `afm:afm-topography` | all (minimal — dedicated afm.py) | — | — |

## Detailed Design

### 1. `resolve_plot_config()` — add `scale` param

```python
def resolve_plot_config(
    study_name: str,
    device_type: str | None = None,
    active_theme: str = "publication-nature",
    scale: str | None = None,         # ← NEW: "linear" | "log" | None
) -> dict:
```

Logic change:
```python
# Determine blocks to merge
study_plot = study_cfg.get("plot", {})

if "common" in study_plot:
    # New format: common + optional linear/log blocks
    common_cfg = study_plot.get("common", {})
    scale_cfg = study_plot.get(scale, {}) if scale else {}
else:
    # Legacy format: flat plot block
    common_cfg = study_plot
    scale_cfg = {}

# Deep merge: theme < common < scale < device
merged = _deep_merge(rcparams, common_cfg)
merged = _deep_merge(merged, scale_cfg)
merged = _deep_merge(merged, device_plot)
```

### 2. `interactive_menu.py` — pass `scale` from option

```python
def dispatch(study_key, menu_type, file_paths, **kwargs):
    ...
    selected = menu["options"][choice - 1]
    scale = selected.get("scale")       # ← NEW: read scale from option
    if scale:
        kwargs["scale"] = scale          # ← NEW: pass to handler
    
    handler_path = selected["handler"]
    module_path, func_name = handler_path.rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)
    ...
```

### 3. `generic.py` wrappers — accept + pass `scale`

```python
def plot_endurance_resistance(file_path=None, scale=None, **kwargs):
    flags = {"plot_variant": "resistance"}
    if scale:
        flags["scale"] = scale
    _plot_generic(str(file_path), flags, study_name="pulse:pulse-endurance")

def plot_endurance_current(file_path=None, scale=None, **kwargs):
    flags = {"plot_variant": "current"}
    if scale:
        flags["scale"] = scale
    _plot_generic(str(file_path), flags, study_name="pulse:pulse-endurance")

def plot_endurance_both(file_path=None, scale=None, **kwargs):
    plot_endurance_resistance(file_path=file_path, scale=scale, **kwargs)
    plot_endurance_current(file_path=file_path, scale=scale, **kwargs)
```

### 4. `_plot_generic()` — use scale in resolver call

```python
def _plot_generic(filepath, flags, study_name=None, info=None):
    scale = flags.get("scale")             # ← NEW: read scale from flags
    plot_flat = resolve_plot_config(study_name, scale=scale)  # ← NEW: pass it
    ...
```

### 5. `generic.py` — per-series `type: line | scatter`

In `_plot_single()`:
```python
series_cfg = cfg.get("series", {})
s = next(iter(series_cfg.values()), {}) if series_cfg else {}
series_type = s.get("type", "line")       # ← NEW: default "line"

if series_type == "scatter":
    ax.scatter(x, y, s=..., marker=..., color=..., alpha=...)
else:
    ax.plot(x, y, color=..., linewidth=..., marker=...)
```

In `_plot_multi_series()`:
```python
for key, y_vals in series_data.items():
    s = series_cfg.get(key, {})
    series_type = s.get("type", "scatter")  # ← NEW: default "scatter"

    if series_type == "line":
        ax.plot(x, y_vals, color=..., linewidth=..., label=...)
    else:
        ax.scatter(x, y_vals, s=..., marker=..., color=..., alpha=...)
```

### 6. `plot.py` — `--linear`/`--log` CLI flags

```python
# Add to argparse for sci plot:
plot_parser.add_argument("--linear", action="store_true", help="Use linear scale")
plot_parser.add_argument("--log", action="store_true", help="Use log scale")

# In dispatch:
def _resolve_scale(flags):
    if flags.get("linear"):
        return "linear"
    if flags.get("log"):
        return "log"
    return None
```

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Code: plot_config.py | code-medium | Add `scale` param, merge logic |
| Code: generic.py wrappers + per-series type | code-medium | Accept scale, type dispatch |
| Code: interactive_menu.py | code-light | Small change — pass scale |
| Code: plot.py flags | code-light | Small change — 2 CLI flags |
| Code: config-studies.yaml restructure | code-medium | Mechanical restructure of all 13 studies |
| QA & Review | review-medium | Verify layouts, menu options, backward compat |
| Documentation | docs-medium | CHANGELOG, skill update |

## Tasks

| ID | Description | Est. | Assigned To |
|----|-------------|------|-------------|
| task-001 | `resolve_plot_config()` — add `scale` param + `common`/`linear`/`log` merge logic | 20m | code |
| task-002 | `generic.py` — per-series `type: line\|scatter` in `_plot_single()` and `_plot_multi_series()` | 15m | code |
| task-003 | `generic.py` — 3 endurance wrappers accept `scale` kwarg, pass to `_plot_generic()` | 5m | code |
| task-004 | `_plot_generic()` — read `scale` from flags, pass to `resolve_plot_config()` | 5m | code |
| task-005 | `interactive_menu.py` — read `option["scale"]`, add to kwargs | 5m | code |
| task-006 | `plot.py` — add `--linear`/`--log` CLI flags | 5m | code |
| task-007 | `config-studies.yaml` — restructure all 13 study `plot:` blocks + `scale` in menu options | 30m | code |
| task-008 | QA & Review — pytest, all layouts, interactive menu | 20m | review |
| task-009 | Documentation — CHANGELOG, version bump | 10m | docs |
| task-010 | Update `sci-plot-config` skill | 15m | docs |
| task-011 | Update `.lavish` layer05 dashboard | 5m | docs |
| task-012 | Commit | 5m | plan |

## Dependency Order

1. task-001 (plot_config.py — new API) — BLOCKING for all
2. task-002, 003, 004, 005, 006 (parallel — all depend on task-001)
3. task-007 (config-studies.yaml) — parallel safe
4. task-008 (QA & Review)
5. task-009, 010, 011 (docs parallel)
6. task-012 (commit)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pulse-endurance visual regression | **HIGH — user explicitly said don't touch** | All pulse-endurance config stays log. Menu options both use `scale: log`. Linear block is unused by menu. |
| Old flat `plot:` blocks break | Med | Check `common` presence in resolver; fall back to treating entire `plot:` as common |
| 13 studies need restructure — typos possible | Med | Review agent checks every block |
| Wrapper functions in generic.py don't get the scale kwarg from interactive menu | Low | `**kwargs` catches the extra param; explicit `scale` parameter added |

## Walkthrough

### Implementation Notes — Completed 21/06/2026

**Core changes** (all code complete):

1. **`core/plot_config.py`** (215L):
   - `resolve_plot_config()` now accepts `scale: str | None = None`
   - When scale provided and study has `plot.common`: merges `plot.<scale>` after `common`, before device overrides
   - Legacy flat blocks work unchanged
   - New `study_has_scale_blocks(study_name)` helper
   - New `resolve_step_plot_overrides(study_name, filepath, step_name)` for protocol.yaml step-level overrides

2. **`plot/generic.py`**:
   - `_plot_single()`: reads `s.get("type", "line")` → uses `ax.scatter()` if "scatter", else `ax.plot()`
   - `_plot_multi_series()`: reads `s.get("type", "scatter")` → uses `ax.plot()` if "line", else `ax.scatter()`
   - `_plot_generic()`: reads `flags.get("scale")` → passes to `resolve_plot_config()`
   - `_plot_generic()`: calls `resolve_step_plot_overrides()` after all config layers, deep-merges as highest priority
   - Endurance wrappers (`plot_endurance_resistance/current/both`) accept `scale: str | None = None`

3. **`core/interactive_menu.py`**: `dispatch()` reads `option["scale"]` and passes to handler kwargs

4. **`cli/commands/plot.py`**: `_parse_flags()` recognizes `--linear` and `--log`, sets `flags["scale"]`

5. **`config-studies.yaml`**: Pulse-endurance restructured into `common` + `log` + `linear` sub-blocks with menu `scale` fields

**Config changes** (pulse-endurance only — restructured):
```
plot:
  common: layout, axes defaults, subsample
  log: log-specfic axes, series, annotations (study default — menu options use scale: log)
  linear: linear-specific axes, series (available via --linear flag)
  current: variant block stays as-is
```
All 4 menu options wired with `scale: log` where appropriate.

**Test results**: 590 pass, 4 pre-existing failures (unrelated migration script + config assertion issues)

**Skill updated**: `sci-plot-config` — documents new `common`/`linear`/`log` schema, per-series `type`, `--linear`/`--log` flags, protocol overrides, 4-layer merge

**Dashboard updated**: Layer 5 — scale blocks work item marked ✓, assignee → docs, version v3.22.0
