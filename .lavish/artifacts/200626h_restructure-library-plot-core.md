---
layer: [5]
type: plan
status: planning
tags: [restructure, library, plot, core]
assignee: plan
---

# Implementation Plan: Restructure library/ + plot/ + core/ — v3.22.0

**Date**: 20/06/2026
**Status**: 🟡 Planning
**Branch**: `dev` (continues from v3.21.0 `6b63cc0`)

---

## Context Summary

v3.21.0 shipped config-first plot params: `resolve_plot_config()` merges theme → study → device styling, `plot:` blocks in all 13 studies, theme consolidation. Plot is now config-driven.

The user identified that with config-driven plots, most per-study plot files are redundant. `library/` should be pure analysis (no plotting). `library/instruments/` is not analysis.

**Key design principle (user's words):**
> "SVG generators NOT needed. Plot is now general + config-driven. Library = pure analysis only."

---

## Objectives

1. **`library/`** — Pure analysis only. Remove all `plotting.py` and `device_cli.py` files. Move `instruments/` to `core/`.
2. **`plot/`** — Replace 9 per-study files with generic `single.py` (dispatches by `data_shape.kind`). Keep specialists: afm.py (image), eis.py (dual-panel Nyquist/Bode), overlay.py (multi-file), registry.py + base.py.
3. **`cli/commands/`** — Merge `library/iv/device_cli.py` → `cli/commands/iv.py`. Merge `library/pulse/device_cli.py` → `cli/commands/pulse.py`.
4. Clear dead code + duplicated SVG generators.

---

## Current → Target Structure

### `library/` (before → after)

```
BEFORE:                          AFTER:
library/                        library/
├── afm/ (4 files)              ├── afm/ (4 files)        ← same
├── electrochem/ (5 files)      ├── electrochem/ (5 files) ← same
├── instruments/ (4 files)      ← MOVED to core/
├── iv/                         ├── iv/
│   ├── __init__.py              │   ├── __init__.py
│   ├── analyze.py               │   ├── analyze.py
│   ├── bipolar.py               │   ├── bipolar.py
│   ├── device_cli.py            │   ├── volatile.py      ← same
│   ├── metrics.py               │   ├── metrics.py
│   ├── models.py                │   └── models.py
│   ├── plotting.py     ⛔       │   DELETED: plotting.py (1006L)
│   ├── switching.py             │   DELETED: device_cli.py
│   └── volatile.py              │   
├── memristor/                  ├── memristor/ (compat shim)
│   ├── __init__.py              │   ├── __init__.py (re-exports)
│   ├── dashboard.py             │   ├── dashboard.py ← keep
│   ├── db.py                    │   ├── db.py ← keep
│   ├── device_assignment.py     │   ├── device_assignment.py ← keep
│   ├── device_cli.py            │   DELETED: device_cli.py
│   ├── device.py                │   DELETED: plotting.py (1447L)
│   ├── endurance.py             │   DELETED: endurance.py → use pulse/
│   ├── models.py                │   ...etc (all analysis→pulse/ or iv/)
│   ├── plotting.py      ⛔      │
│   ├── switching.py             │
│   └── retention.py             │
├── pulse/                      ├── pulse/
│   ├── __init__.py              │   ├── __init__.py
│   ├── device_cli.py            │   ├── analyze.py    ← NEW entry
│   ├── endurance.py             │   ├── stp.py        ← volatile
│   ├── models.py                │   ├── endurance.py  ← volatile + non-volatile
│   ├── plotting.py      ⛔      │   ├── ppf.py        ← volatile
│   ├── ppf.py                   │   ├── retention.py  ← non-volatile
│   ├── retention.py             │   ├── switching.py  ← non-volatile
│   ├── stp.py                   │   ├── analyze.py    ← NEW entry
│   └── switching.py             │   └── models.py
└── pvd/ (5 files)              └── pvd/ (5 files)    ← same
                                    
core/                           core/
├── instruments/                ← NEW from library/instruments/
├── (all existing files)        ← unchanged
```

### `plot/` (before → after)

```
BEFORE:                          AFTER:
plot/                           plot/
├── __init__.py                 ├── __init__.py
├── base.py                     ├── base.py          ← keep
├── overlays.py                 ├── overlays.py      ← keep (multi-file)
├── registry.py                 ├── registry.py      ← keep (STUDY_PLOTTERS)
├── afm.py                      ├── afm.py           ← keep (image)
├── eis.py                      ├── eis.py           ← keep (dual-panel)
├── iv.py               ⛔      ├── single.py        ← NEW: generic dispatch
├── cv.py               ⛔       DELETED: iv.py, cv.py, ca.py,
├── ca.py               ⛔        raman.py, uv_vis.py, stp.py,
├── raman.py            ⛔        ppf.py, pulse_endurance.py,
├── uv_vis.py           ⛔        pulse_retention.py
├── stp.py              ⛔
├── ppf.py              ⛔
├── pulse_endurance.py  ⛔
├── pulse_retention.py  ⛔
└── README.md                    ← keep
```

---

## Phase 1: Move `library/instruments/` → `core/instruments/`

**Assigned**: code-light

Move 4 files:
- `library/instruments/__init__.py`
- `library/instruments/registry.py`
- `library/instruments/models.py`
- `library/instruments/types.py`

Update all importers: `grep -rn "from science_cli.library.instruments" src/` finds 3-4 import sites.

**Risk**: Low. Mechanical file move + import updates.

**Effort**: 0.5 session.

---

## Phase 2: Delete `library/*/plotting.py` files + `library/*/device_cli.py`

**Assigned**: code-light

| File | Size | Action |
|------|------|--------|
| `library/pulse/plotting.py` | 59L | **Delete** — dead code |
| `library/iv/plotting.py` | 1006L | **Delete** — SVG generators |
| `library/memristor/plotting.py` | 1447L | **Delete** — SVG generators |
| `library/iv/device_cli.py` | ? | **Delete** — merge to cli/commands/ |

Verify no callers before deleting.

**Risk**: Medium — must verify SVG generators aren't imported by `serve/api.py`. If they are, need to either (a) inline the needed functions in serve/ or (b) keep a thin compat shim.

**Effort**: 0.5 session.

---

## Phase 3: Merge `device_cli.py` → `cli/commands/`

**Assigned**: code-medium

Merge `library/iv/device_cli.py` content into `cli/commands/iv.py`.
Merge `library/pulse/device_cli.py` content into `cli/commands/pulse.py`.

These files contain CLI-specific logic (list files, analyze, plot with fzf). The functions must keep their signatures but live in the cli/commands/ directory.

**Risk**: Medium — the device_cli functions are imported by the cli/commands/ wrappers. Must update import paths and verify CLI still works.

**Effort**: 1 session.

---

## Phase 4: Create `plot/single.py` (generic config-driven plot)

**Assigned**: code-medium

New file that replaces 9 per-study plot files. One generic entry point:

```python
# plot/single.py
from science_cli.core.plot_config import resolve_plot_config
from science_cli.core.data_loader import load_data_file

def plot_single(filepath: str, flags: dict, 
                study_name: str = "",
                device_type: str | None = None) -> None:
    """Generic plot function. Dispatches by data_shape.kind."""
    
    # 1. Resolve config
    cfg = resolve_plot_config(study_name, device_type)
    
    # 2. Load data
    df, info = load_data_file(filepath, study_name=study_name)
    
    # 3. Get data_shape from study config
    data_shape = cfg.get("data_shape", {}).get("kind", "trace_2d")
    columns = cfg.get("data_shape", {}).get("columns", [])
    
    # 4. Dispatch by shape
    if data_shape == "image_2d":       # AFM
        _plot_single_image(df, cfg, flags)
    elif data_shape == "trace_2d":     # IV, CV, CA, EIS
        _plot_single_trace(df, cfg, flags, columns)
    elif data_shape == "waveform_2d":  # pulse
        _plot_single_scatter(df, cfg, flags, columns)
    elif data_shape == "spectrum_2d":  # Raman, UV-Vis
        _plot_single_spectrum(df, cfg, flags, columns)
```

Each `_plot_single_*` function reads series definitions from `cfg.get("series.hrs.*")` and applies them to matplotlib calls.

This is already what the current per-study plot files do — the difference is the dispatch is generic (by data_shape), not hardcoded (by study name).

**Key concern**: Some studies have special axis requirements:
- STP/PPF: twin y-axis (left=voltage, right=current)
- These can be handled by `flags` override or a config key like `twin_y: true` in the plot block

**Risk**: Medium — some plot functions have unique behaviors not cleanly captured by generic dispatch. Solution: the generic `plot_single` dispatches to the common case; if a study needs custom logic, it can override via a config key or a thin wrapper.

**Effort**: 2 sessions.

---

## Phase 5: Register `plot/single.py` in registry.py

**Assigned**: code-light

In `plot/registry.py:STUDY_PLOTTERS`, register `single.py:plot_single` as the default plot function for all trace/waveform/spectrum studies. The per-study files are no longer imported.

```python
# In _init_dedicated_plotters():
from science_cli.plot.single import plot_single

# Register for all studies except afm and eis
for study_name in STUDY_PLOTTERS:
    if study_name not in ("afm:afm-topography", "ec:ec-eis"):
        STUDY_PLOTTERS[study_name].plot_fn = plot_single
```

**Risk**: Low.

**Effort**: 0.5 session.

---

## Phase 6: Delete old per-study plot files

**Assigned**: code-light

Delete: `iv.py`, `cv.py`, `ca.py`, `raman.py`, `uv_vis.py`, `stp.py`, `ppf.py`, `pulse_endurance.py`, `pulse_retention.py`

**Risk**: Low — only after Phase 5 confirms `single.py` covers all cases.

**Effort**: 0.5 session.

---

## Phase 7: Update `cli/commands/plot.py` dispatch

**Assigned**: code-medium

The `cli/commands/plot.py` currently dispatches through `resolve_study_plotter()` → per-study plot function. With `single.py` as the generic handler, the dispatch stays the same but the resolved plot function is now `plot_single` for most studies.

Update `plot_handler()` to pass `study_name` and `device_type` to `plot_single` (it already does this for the current per-study functions).

**Risk**: Low.

**Effort**: 0.5 session.

---

## Phase 8: Update `memristor/` compat shim

**Assigned**: code-light

`library/memristor/` currently re-exports from `library/iv/` and `library/pulse/`. After the reorg:
- `endurance.py`, `retention.py`, `switching.py` → these exist in both `memristor/` and `pulse/` — delete the memristor versions, update the shim to point to `library/pulse/`.
- `plotting.py` → delete (was SVG generators)

**Risk**: Low.

**Effort**: 0.5 session.

---

## Phase 9: Run tests + fix

**Assigned**: review-medium

After all deletions/moves, run full test suite. Expected: 572+ tests pass (some may be removed with deleted files, some may need import path updates).

Key risks:
- `serve/api.py` imports SVG generators from `library/memristor/plotting.py` — need to verify
- Dashboard functions (`dashboard.py`, `db.py`) import plotting — may need to inline SVG functions

**Effort**: 1 session.

---

## Phase 10: Documentation

**Assigned**: docs-light

- CHANGELOG — v3.22.0 section
- README — update architecture diagram
- AGENTS.md — update directory map
- sci-theme-plotting skill — update if needed

**Effort**: 0.5 session.

---

## Agent Delegation Table

| Phase | Description | Agent | Effort |
|-------|-------------|-------|--------|
| 1 | Move instruments/ → core/instruments/ | code-light | 0.5 |
| 2 | Delete plotting.py + device_cli.py | code-light | 0.5 |
| 3 | Merge device_cli → cli/commands/ | code-medium | 1 |
| 4 | Create plot/single.py (generic dispatch) | code-medium | 2 |
| 5 | Register single.py in registry | code-light | 0.5 |
| 6 | Delete old per-study plot files | code-light | 0.5 |
| 7 | Update cli/commands/plot.py dispatch | code-medium | 0.5 |
| 8 | Update memristor/ compat shim | code-light | 0.5 |
| 9 | Run tests + fix regressions | review-medium | 1 |
| 10 | Documentation | docs-light | 0.5 |

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `serve/api.py` depends on SVG generators | High | Inline the 2-3 SVG functions needed by serve/ in `serve/api.py` itself |
| Dashboard depends on memristor/plotting.py | High | Dashboard uses `read_iv_csv` only — already available in `core/data_loader.py` or inline |
| Generic `single.py` misses study-specific details | Medium | Keep the per-study files during transition; delete only after verification |
| Import paths change and tests fail | Medium | Phase 9 catches these; fix incrementally |

---

## Dependency Order

```
Phase 1 (instruments/) ──┐
                          ├──> Phase 2 (delete plotting.py) ──> Phase 3 (merge device_cli)
                          │                                              │
                          ▼                                              ▼
Phase 4 (create single.py) ──────────> Phase 5 (register in registry) ──> Phase 6 (delete old files)
                                            │
                                            ▼
                                      Phase 7 (update CLI dispatch)
                                            │
                                            ▼
                                      Phase 8 (update memristor shim)
                                            │
                                            ▼
                                      Phase 9 (tests + fix)
                                            │
                                            ▼
                                      Phase 10 (docs)
```

Phases 1-3 can run in parallel initially, but Phase 4 depends on knowing what capabilities each study's plot needs. Phase 5+6 depend on Phase 4.

---

## Walkthrough

(filled during/after implementation)
