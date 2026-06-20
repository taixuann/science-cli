---
layer: [3]
type: plan
status: planning
tags: [keysight, parsers, data-loading]
assignee: plan
---

# Implementation Plan: Fix Keysight B1500A Data Loading & Plotting

**Date**: 15/06/2026
**Status**: 🟡 Planning
## Context Summary

The science-cli has device-aware data loading via `core/data_loader.py:_load_with_device_config()` and `core/config.py` builtin configs for `keysight-b1500a` under `iv-sweep`, `pulse-stp`, and `pulse-ppf`. However, the plot and analyze code paths fail to pass the correct device to `load_data_file()` in several scenarios:

### Root cause 1: `get_default_device()` doesn't check `_DEFAULT_GLOBAL_TECHNIQUES`

In `core/config.py`, `get_default_device()` at line 369 reads only from the merged config's `defaults:` section — NOT from `_DEFAULT_GLOBAL_TECHNIQUES[technique]["default_device"]`. The generated default config YAML (`generate_default_config_yaml()`) only lists `iv-sweep: keithley-2400`, `raman: horiba-usth`, `uv-vis: iop-hanoi` under `defaults:`. There is no `pulse-stp` or `pulse-ppf` entry, so `get_default_device("pulse-stp")` returns `""`.

### Root cause 2: `_analyze_direct` doesn't pass technique/device to `load_data_file`

Every analyzer function in `cli/commands/analyze.py` calls `load_data_file(filepath)` without technique/device kwargs (except `_analyze_eis` and `_analyze_uv_vis`). This means even for `iv-sweep`, the analyzer loads with generic CSV parsing.

### Root cause 3: `_resolve_xy_columns` doesn't handle `pulse-stp`/`pulse-ppf`

In `cli/commands/plot.py`, the technique-specific column resolution (line 657-780) handles `ec-ca`, `ec-cv`, `ec-eis`, `iv-sweep/breakdown/leakage`, `uv-vis`, and `mem-endurance/retention` — but NOT `pulse-stp` or `pulse-ppf`. After device-aware loading remaps columns to `time`, `voltage`, `current`, the fallback picks `time` (first numeric) as x and `voltage` (second numeric) as y, instead of `time` vs `current`.

### Root cause 4: `DataName` filter column mismatch

The factory default config says `header_lines: 245` for `keysight-b1500a` IV, but the user's context says `header_lines: 246`. Also the `_load_with_device_config` already drops `DataName` rows (line 136-138), but this only works if the header_lines skips the right number of rows.

## Objectives

1. Fix `get_default_device()` to also check `_DEFAULT_GLOBAL_TECHNIQUES[technique]["default_device"]` so pulse techniques resolve to `keysight-b1500a`
2. Add a shared `_resolve_device(filepath, technique)` helper that checks protocol step metadata for `instrument` field, falling back to `get_default_device()`
3. Wire the helper into `_do_plot`, `_do_overlap`, and `_analyze_direct`
4. Add `pulse-stp`/`pulse-ppf` column resolution in `_resolve_xy_columns`
5. Add `pulse-stp`/`pulse-ppf` routing in `_analyze_direct` with device-aware loading
6. Correct `header_lines` for keysight-b1500a IV from 245 → 246 in `_DEFAULT_TECHNIQUE_DEVICES`
7. Verify/test the `DataName` dropping logic handles edge cases

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `core/config.py` | Fix `get_default_device()` to check `_DEFAULT_GLOBAL_TECHNIQUES` + add `pulse-stp`/`pulse-ppf` defaults in `generate_default_config_yaml()` + fix `keysight-b1500a` IV `header_lines` from 245 → 246 | Low |
| `core/config.py` | Add `keysight-b1500a` as default device for `pulse-stp` and `pulse-ppf` in `_DEFAULT_GLOBAL_TECHNIQUES` | Low |
| `core/data_loader.py` | Verify `DataName` row dropping in `_load_with_device_config` handles case where `DataName` column values have whitespace variations; add `.str.strip()` safeguard | Low |
| `cli/commands/plot.py` | Create shared `_resolve_device()` helper; wire into `_do_plot()` and `_do_overlap()`; add `pulse-stp`/`pulse-ppf` to `_resolve_xy_columns()` | Med |
| `cli/commands/analyze.py` | Create shared `_resolve_device()` helper (or import from plot.py); wire into `_analyze_direct()`; add `pulse-stp`/`pulse-ppf` routing with device-aware loading | Med |
| `tests/test_core/test_keysight_loader.py` | New test file with 5 tests for device resolution, column mapping, STP data loading, IV plot columns, and protocol-step metadata resolution | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | tools-code-medium | All 5 source-file changes |
| QA & Review | tools-review-light | Ruff + mypy + pytest pass |
| Documentation | tools-docs-light | Update CHANGELOG, artifact-review |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Config fix: `get_default_device()` fallback + header_lines fix + defaults | 20m | tools-code | no |
| task-002 | Data loader verify: `DataName` stripping safeguard | 10m | tools-code | no |
| task-003 | Plot: `_resolve_device()` helper + wire into `_do_plot`/`_do_overlap` + xy columns | 45m | tools-code | no |
| task-004 | Analyze: `_resolve_device()` helper + wire into `_analyze_direct` + pulse routing | 30m | tools-code | no |
| task-005 | Tests: 5 test functions for each scenario | 30m | tools-code | no |
| task-006 | Lint + typecheck | 10m | tools-review | no |
| task-007 | CHANGELOG + artifact-review | 10m | tools-docs | no |

## Dependency Order

1. **task-001** (config fix) — foundational, no deps
2. **task-002** (data loader verify) — no deps
3. **task-003** (plot wiring) — depends on task-001 for `get_default_device()` working
4. **task-004** (analyze wiring) — depends on task-001
5. **task-005** (tests) — depends on all above
6. **task-006** (review) — after tasks 1-5
7. **task-007** (docs) — after review passes

Tasks 001 and 002 can be done in parallel.

## Detailed Change Descriptions

### task-001: `core/config.py`

**a) Fix `get_default_device()` — also check `_DEFAULT_GLOBAL_TECHNIQUES`**

```python
def get_default_device(technique: str, project_root: Path | None = None) -> str:
    config = get_merged_config(project_root)
    defaults = config.get("defaults", {})
    device = defaults.get(technique, "")
    if not device:
        # Fallback to _DEFAULT_GLOBAL_TECHNIQUES[technique]["default_device"]
        from science_cli.library.instruments.registry import (
            _merged_instrument_registry,
        )
        # Check the technique config in _DEFAULT_GLOBAL_TECHNIQUES
        global_tech = _DEFAULT_GLOBAL_TECHNIQUES.get(technique, {})
        device = global_tech.get("default_device", "")
    return device
```

Wait — `_DEFAULT_GLOBAL_TECHNIQUES` is in `core/config.py` itself, not in the instrument registry. So this is a simple local dict lookup:

```python
def get_default_device(technique: str, project_root: Path | None = None) -> str:
    config = get_merged_config(project_root)
    defaults = config.get("defaults", {})
    device = defaults.get(technique, "")
    if not device:
        # Fallback to hardcoded default_device per technique
        tech_cfg = _DEFAULT_GLOBAL_TECHNIQUES.get(technique, {})
        device = tech_cfg.get("default_device", "")
    return device
```

**b) Fix `keysight-b1500a` IV `header_lines`**

Change line 89-98 from `header_lines: 245` to `header_lines: 246`.

**c) Update `_DEFAULT_GLOBAL_TECHNIQUES` for pulse techniques**

Change lines 867-876 to use `keysight-b1500a` as the default device for pulse techniques:

```python
"pulse-stp": {
    ...
    "default_device": "keysight-b1500a",
},
"pulse-ppf": {
    ...
    "default_device": "keysight-b1500a",
},
```

**d) Update `generate_default_config_yaml()` defaults section**

Add `pulse-stp` and `pulse-ppf` to the generated config's `defaults:` section so users who run `sci config init` get the correct defaults.

### task-002: `core/data_loader.py`

In `_load_with_device_config()` (line 136-138):

```python
# Filter Keysight B1500A format: keep only DataValue rows
if "DataName" in df.columns:
    df = df[df["DataName"].str.strip() == "DataValue"].copy()
    df = df.drop(columns=["DataName"])
```

Add safeguard: chain `.str.strip()` on the comparison and handle case where `DataName` column has leading/trailing whitespace. Also consider adding a warning if no `DataValue` rows remain (all rows got filtered out).

### task-003: `cli/commands/plot.py`

**a) Add `_resolve_device()` helper** (near `_detect_technique` around line 164-168):

```python
def _resolve_device(technique: str, filepath: str) -> str:
    """Resolve device name for a file by checking protocol step metadata first,
    then falling back to the global default device for the technique."""
    # Try protocol step metadata first
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session
    session = load_session()
    current_protocol = session.get("last_protocol")
    proj = get_current_project_path()
    if current_protocol and proj:
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(current_protocol)
        if yaml_path.exists():
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            fname = Path(filepath).name
            for s in data.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    ins = s.get("instrument") or s.get("device", "")
                    if ins:
                        return ins
    # Fallback to global default
    from science_cli.core.config import get_default_device
    return get_default_device(technique)
```

**b) Wire into `_do_plot()`** (around line 790-797):

Replace the current `get_default_device()` call with `_resolve_device()`:

```python
def _do_plot(filepath: str, flags: dict, technique: str = "") -> None:
    ...
    try:
        load_kwargs = {}
        if technique:
            device = _resolve_device(technique, filepath)
            if device:
                load_kwargs["technique"] = technique
                load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    ...
```

**c) Wire into `_do_overlap()`** (around line 1054-1063):

Same pattern — replace `get_default_device()` with `_resolve_device()`.

**d) Add `pulse-stp`/`pulse-ppf` to `_resolve_xy_columns()`** (after line 746):

```python
elif technique in ("pulse-stp", "pulse-ppf"):
    # STP/PPF: time vs current (with voltage as optional)
    for candidate in ("time", "Time", "t/s", "t"):
        if candidate in df.columns:
            xcol = candidate
            break
    for candidate in ("current", "Current (A)", "I", "I/A", "MeasResult2_value"):
        if candidate in df.columns:
            ycol = candidate
            break
```

### task-004: `cli/commands/analyze.py`

**a) Add the `_resolve_device()` helper** — same implementation as in plot.py. Could also be a shared utility but the two modules don't share imports currently, so duplicating is safer (avoids creating cross-dependency).

**b) Wire into `_analyze_direct()`** — before each analyzer call that calls `load_data_file()`, the technique-specific routing needs to pass device info. For `_analyze_iv` and `_analyze_pulse_stp`/`_analyze_pulse_ppf`:

- `_analyze_iv` currently calls `load_data_file(filepath)` (line 409) — needs `load_data_file(filepath, technique=tech, device=...)`
- `_analyze_pulse_stp` is a stub — needs full implementation OR at minimum load the file with correct device config before attempting analysis

For now, the pulse analyzers are stubs (`console.print("not implemented")`). The minimal fix is to ensure `_analyze_direct` passes technique/device to `load_data_file` for the analyzers that currently work (iv-sweep). For pulse stubs, add device-aware loading as a precursor.

**c) Add `pulse-stp`/`pulse-ppf` routing** in `_analyze_direct()` (around line 203):

```python
elif tech in ("pulse-stp",):
    _analyze_pulse_stp(filepath, flags)
elif tech in ("pulse-ppf",):
    _analyze_pulse_ppf(filepath, flags)
```

**d) Update `_analyze_pulse_stp` and `_analyze_pulse_ppf`** — at minimum, load the data with the correct device config and show a summary, even if full analysis is not yet implemented. This makes `sci analyze file_stp.csv` not crash.

### task-005: Tests

New file `tests/test_core/test_keysight_loader.py`:

```python
"""Tests for Keysight B1500A data loading and plotting."""

def test_load_data_file_with_keysight_iv(tmp_path):
    """load_data_file(file, technique='iv-sweep', device='keysight-b1500a') returns voltage/current columns"""

def test_load_data_file_with_keysight_stp(tmp_path):
    """load_data_file(file, technique='pulse-stp', device='keysight-b1500a') returns time/voltage/current columns"""

def test_keysight_iv_plot_columns():
    """_resolve_xy_columns returns correct x/y for keysight-b1500a IV data"""

def test_keysight_stp_plot_loads():
    """_do_plot handles keysight-b1500a STP file without parse error"""

def test_device_resolution_from_step(tmp_path):
    """_resolve_device resolves from protocol step instrument field"""
```

## Risks

- **Backward compat**: Existing protocol YAMLs use `device:` field (not `instrument:`). The `_resolve_device()` helper must check both: `s.get("instrument") or s.get("device", "")`.
- **`get_default_device` side effects**: Changing `get_default_device()` to also check `_DEFAULT_GLOBAL_TECHNIQUES` may affect other callers that expect `""` for unconfigured techniques. But returning a hardcoded default is safer than returning `""` (which causes generic CSV loading and garbled data).
- **Modularity**: Duplicating `_resolve_device()` in both plot.py and analyze.py is intentional to avoid cross-module coupling. If it grows, extract to a shared utility in `core/`.
- **Test data**: Need synthetic Keysight CSV files. The existing `tests/conftest.py` has test fixtures for creating synthetic test data — follow that pattern.

## Walkthrough

(To be filled during/after implementation)
