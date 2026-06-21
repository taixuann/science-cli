---
layer: [3, 5, 6, 7]
type: plan
status: completed
tags: [pulse, endurance, plotting, metadata, extracted-list, menu-driven, config-driven]
depends_on: [160626f_pulse-endurance-readd, 190626f_fix-endurance-plot, 190626h_pulse-plot-analyze-pipeline]
assignee: plan
---

# Implementation Plan: Config-Driven Menu for Endurance Plots + Metadata

**Date**: 21/06/2026
**Status**: 🟢 Complete
**Version**: v3.23.0

## Context Summary

We have 7 pulse-endurance data file pairs (raw + extracted-list) in the `res_internship` project. All `_extracted-list.csv` files now have a 9-column format with per-cycle voltages + currents:

```
V_LRS,2.66851043701172
V_HRS,0.25056886672973605
cycle,v_lrs_V,v_hrs_V,i_lrs_A,i_hrs_A,r_lrs_ohm,r_hrs_ohm,ratio,i_ratio
1,2.687e+00,2.510e-01,1.241e-03,1.281e-07,2.165e+03,1.959e+06,9.051e+02,9.690e+03
```

The plotter needs to:
1. Only process `_extracted-list.csv` files (skip `_raw.csv`)
2. Parse the 2-line voltage header + 9-column data
3. Generate plot types via **config-driven Rich menu** (not CLI flags)
4. Extract raw CSV metadata to protocol.yaml

---

## Design: Config-Driven Menu Workflow

### `sci plot --all` → After FZF
```
1. FZF shows all files (as today)
2. User picks a file → detect study (e.g. pulse-endurance)
3. interactive_menu.py reads config-studies.yaml for the study's plot menu
4. Rich menu shown:
   ┌────────────────────────────────────────────┐
   │ Select plot type for pulse-endurance:      │
   │                                            │
   │ > 1) Resistance vs Cycles                  │
   │   2) Current vs Cycles                     │
   │   3) Both (2 separate files)               │
   └────────────────────────────────────────────┘
5. interactive_menu.py dynamically imports the selected handler and calls it
```

### `sci analyze --all` → After FZF
```
1. FZF shows all files
2. User picks pulse-endurance files
3. interactive_menu.py reads config-studies.yaml
4. Rich menu shown:
   ┌────────────────────────────────────────────┐
   │ Select analysis for pulse-endurance:       │
   │                                            │
   │ > 1) Ratio Histogram (R_HRS/R_LRS)         │
   │   2) Current Ratio Histogram (I_LRS/I_HRS) │
   └────────────────────────────────────────────┘
5. Dynamic import + call handler
```

---

## Architecture: Config-Driven Routing

### Core idea
Menu options live in `config-studies.yaml`. `core/interactive_menu.py` reads config → renders Rich menu → dynamically imports/routes to handler. **No hardcoded dispatch chains.**

### Config schema (add to config-studies.yaml)

```yaml
studies:
  pulse:
    pulse-endurance:
      # ... existing config ...

      interactive:
        plot:
          menu_title: "Select plot type for pulse-endurance:"
          options:
            - name: "Resistance vs Cycles"
              handler: "science_cli.plot.pulse_endurance.plot_resistance"
              description: "R_HRS, R_LRS, ratio over cycle number"
            - name: "Current vs Cycles"
              handler: "science_cli.plot.pulse_endurance.plot_current"
              description: "I_LRS (V_set), I_HRS (V_read)"
            - name: "Both"
              handler: "science_cli.plot.pulse_endurance.plot_both"
              description: "Both resistance and current as separate files"
        analyze:
          menu_title: "Select analysis for pulse-endurance:"
          options:
            - name: "Ratio Histogram"
              handler: "science_cli.library.pulse.endurance.ratio_histogram"
              description: "Distribution of R_HRS / R_LRS"
            - name: "Current Ratio Histogram"
              handler: "science_cli.library.pulse.endurance.current_ratio_histogram"
              description: "Distribution of I_LRS / I_HRS"
```

### `core/interactive_menu.py`

```python
"""Config-driven interactive menu + routing.
Reads menu options from config-studies.yaml, renders a Rich menu,
and dynamically imports/calls the selected handler.
"""
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.prompt import Prompt
from importlib import import_module
import yaml

console = Console()

def show_menu(title: str, options: list[dict], default: int = 1) -> int:
    """Show a numbered Rich menu and return the user's choice."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print("─" * 50)
    for i, opt in enumerate(options, 1):
        marker = "▸" if i == default else " "
        console.print(f"  {marker} [bold]{i}[/bold]) {opt['name']}")
        console.print(f"      {opt.get('description', '')}")
    console.print()
    choice = Prompt.ask(
        "Enter choice",
        choices=[str(i) for i in range(1, len(options) + 1)],
        default=str(default),
    )
    return int(choice)


def load_study_menu(study_key: str, menu_type: str) -> dict:
    """Load interactive menu config for a study from config-studies.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config-studies.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    for group in config.get("studies", {}).values():
        if study_key in group:
            return group[study_key].get("interactive", {}).get(menu_type, {})
    raise KeyError(f"Study '{study_key}' not found")


def dispatch(study_key: str, menu_type: str, file_path: Path, **kwargs: Any) -> None:
    """Show menu, route to handler via dynamic import."""
    menu = load_study_menu(study_key, menu_type)
    choice = show_menu(menu["menu_title"], menu["options"])
    selected = menu["options"][choice - 1]

    module_path, func_name = selected["handler"].rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)
    handler(file_path=file_path, **kwargs)
```

### Integration in CLI

In `cli/commands/plot.py`:
```python
# After FZF selection
from science_cli.core.interactive_menu import dispatch
dispatch(study_key="pulse-endurance", menu_type="plot", file_path=selected)
```

In `cli/commands/analyze.py`:
```python
dispatch(study_key="pulse-endurance", menu_type="analyze", file_path=selected)
```

---

## File Tree

```
src/science_cli/
├── core/
│   └── interactive_menu.py        # [NEW] Config-driven menu + routing
├── plot/
│   ├── pulse_endurance.py          # [MODIFY] Refactor: plot_resistance(), plot_current(), plot_both()
├── cli/commands/
│   ├── plot.py                     # [MODIFY] After FZF → dispatch
│   └── analyze.py                 # [MODIFY] After FZF → dispatch
├── library/pulse/
│   └── endurance.py                # [MODIFY] Add ratio_histogram(), current_ratio_histogram()
config/
└── config-studies.yaml             # [MODIFY] Add interactive: block

.lavish/artifacts/210626-endurance-plots.md  # This plan
```

---

## Agent Delegation Table

| # | Task | Sub-Agent | Files | Time | Deps |
|---|------|-----------|-------|------|------|
| 1 | Config schema | code-light | config-studies.yaml | 10m | None |
| 2 | interactive_menu.py | code-medium | core/interactive_menu.py | 30m | 1 |
| 3 | Parse 9-col + header | code-medium | pulse_endurance.py | 15m | None |
| 4 | plot_resistance() | code-medium | pulse_endurance.py | 15m | 3 |
| 5 | plot_current() | code-medium | pulse_endurance.py | 20m | 3 |
| 6 | plot_both() | code-medium | pulse_endurance.py | 10m | 4,5 |
| 7 | Wire plot dispatch | code-medium | plot.py | 15m | 1,2,4-6 |
| 8 | ratio_histogram() | code-medium | endurance.py | 20m | None |
| 9 | current_ratio_histogram() | code-medium | endurance.py | 15m | 8 |
| 10 | Wire analyze dispatch | code-medium | analyze.py | 15m | 1,2,8,9 |
| 11 | Voltage annotations | code-medium | pulse_endurance.py | 10m | 3 |
| 12 | QA + pytest | review-medium | All + tests/ | 30m | All |
| 13 | Docs + skill | docs-heavy | CHANGELOG, skill | 20m | All |
| 14 | Skill maintenance | skill-maint | All skills | 10m | All |
| | **Total** | | | **~3.5h** | |

---

## Detailed Design

### `_load_preprocessed()`
```python
def _load_preprocessed(csv_path):
    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])
    df = pd.read_csv(csv_path, skiprows=2)
    return df, v_set, v_read
```

### Plot handlers
```python
def plot_resistance(file_path, **kwargs):
    df, v_set, v_read = _load_preprocessed(file_path)
    # r_hrs_ohm, r_lrs_ohm, ratio vs cycle (log-log)
    # Annotate: V_set={v_set:.2f}V, V_read={v_read:.2f}V

def plot_current(file_path, **kwargs):
    df, v_set, v_read = _load_preprocessed(file_path)
    # i_lrs_A, i_hrs_A vs cycle (log-log)

def plot_both(file_path, **kwargs):
    plot_resistance(file_path)
    plot_current(file_path)
```

### Analyze handlers
```python
def ratio_histogram(file_path, **kwargs):
    df, _, _ = _load_preprocessed(file_path)
    # Histogram of df.ratio, 50 bins, log Y, mean/median lines

def current_ratio_histogram(file_path, **kwargs):
    df, _, _ = _load_preprocessed(file_path)
    # Histogram of df.i_ratio, 50 bins, log Y, mean/median lines
```

---

## Backwards Compatibility

- `sci plot --file x.csv` → direct resistance plot (no menu)
- `sci plot --all` + non-endurance file → normal plot (no menu)
- Old 4-column extracted-list → detect missing cols, compute currents from V/R
- No `--all` → unchanged

---

## Risks

| Risk | Mitigation |
|------|------------|
| Dynamic import error | try/except + clear message |
| Config YAML wrong | Validate schema in load_study_menu() |
| pulse_endurance.py > 250 lines | TODO marker, refactor follow-up |
| Old files lack current columns | Detect + fallback to V/R computation |

---

## Critical Pipeline Finding (from trace)

### Current `_load_preprocessed()` WILL BREAK
```python
# Current code (pulse_endurance.py line ~21):
df = pd.read_csv(filepath)  
# With 2-line header, this reads V_LRS and V_HRS as NaN data rows!
```

**Fix required**: `pd.read_csv(csv_path, skiprows=2)` to skip the 2-line voltage header.

### Config-studies.yaml — `interactive:` is SAFE to add
The `interactive:` key is **new** — no existing code reads it. Zero overlap with:
- `patterns:` → read by `detect_study_from_filename()`
- `instruments:` → read by `data_loader.py`
- `plot:` → read by `resolve_plot_config()`
- `device_overrides:` → read by `resolve_plot_config()`

### Menu insertion point
After FZF selection in `_plot_interactive()` (plot.py line ~615), before `_do_plot()`:
```python
# Check if study has interactive menu
if study has interactive.plot in config:
    from science_cli.core.interactive_menu import dispatch
    dispatch(study_key=study_name, menu_type="plot", file_path=filepath)
    return  # skip default _do_plot path
```

### What needs NO change
- `registry.py` — study plotter dispatch unchanged
- `data_loader.py` — raw CSV parsing unchanged
- `config-devices.yaml` — device type resolution unchanged
- `fzf/` — FZF selection unchanged
- `project.py`, `paths.py`, `session.py` — unchanged

### Files to modify (6 files)
| File | Change |
|------|--------|
| `config/config-studies.yaml` | Add `interactive:` block under pulse-endurance |
| `core/interactive_menu.py` | NEW — config-driven menu + dynamic routing |
| `plot/pulse_endurance.py` | Fix `_load_preprocessed()` skiprows=2 + refactor into plot_resistance(), plot_current(), plot_both() |
| `cli/commands/plot.py` | After FZF → detect interactive menu → dispatch |
| `cli/commands/analyze.py` | Same for analyze |
| `library/pulse/endurance.py` | Add ratio_histogram(), current_ratio_histogram() |

### Verify no breakage
- `_load_preprocessed()` fix: `pd.read_csv(skiprows=2)` — changes only 1 line
- Config schema: adds new `interactive:` key, no existing code reads it
- Menu insertion: early return after dispatch, skips `_do_plot()` — no interference

---

## ✅ Implementation Complete (21 Jun 2026)

All 6 files implemented and verified. Status summary:

| # | Action | File | Status |
|---|--------|------|--------|
| 1 | NEW | `core/interactive_menu.py` | ✅ |
| 2 | MODIFY | `config/config-studies.yaml` | ✅ |
| 3 | MODIFY | `plot/pulse_endurance.py` | ✅ |
| 4 | MODIFY | `cli/commands/plot.py` | ✅ |
| 5 | MODIFY | `cli/commands/analyze.py` | ✅ |
| 6 | MODIFY | `library/pulse/endurance.py` | ✅ |
| - | QA | `pytest tests/ -q` | ✅ 596 passed, 4 pre-existing failures |

**Skill update**: `sci-keysight-endurance` updated in parallel — 9-column format, voltage header, naming conventions documented.

### User-facing commands
- `sci plot --all` → FZF → select `_extracted-list.csv` → Rich menu: Resistance / Current / Both
- `sci analyze --all` → FZF → select pulse-endurance file → Rich menu: Ratio Histogram / Current Ratio Histogram
