---
layer: [4, 5]
type: plan
status: planning
tags: [waveform, fzf, plot, stdudy-scoping]
assignee: plan
---

# Implementation Plan: Waveform 2D Detection + core/fzf/ Subpackage + (study, device) Scoping

**Date**: 20/06/2026
**Status**: 🟡 Planning — awaiting your feedback
**Branch**: `dev` (continues v3.20.0 wave)
**Supersedes**: `190626e_config-split-waveform-plan.md` (Phases 5/5b/6/7/8) — this plan replaces those phases

---

## Context Summary

Phases 1–4 of the config split are committed on `dev`:
- `df078c1` Phase 1 — decouple parsing config
- `59162f5` Phase 2 — create `config-studies.yaml`
- `66210bb` Phase 3 — per-instrument grammar (folded `config-grammar.yaml` into `config-instruments.yaml`)
- `2086536` Phase 4 — remove dead `techniques:` blocks

Test status: 548 passed, 4 pre-existing failures (3 unrelated + 1 deferred bug from `get_technique_patterns()` study-fallback).

You expanded scope in m0181 with three new requirements:

1. **Waveform detection** — auto-detect pulse pattern from (time, voltage), produce a canonical 2D `[time, voltage]` array, derive scalars (v_set_v, v_read_v, set_width_us, read_width_us, …), write **both** the 2D array and the scalars to `protocol.yaml`. Every pulse file gets this.
2. **Restructure `core/`** — `metadata/` is already a subpackage. Make `fzf/` a subpackage too: `core/fzf_columns.py` + `core/fzf_utils.py` → `core/fzf/columns.py` + `core/fzf/display.py` (or keep names).
3. **(study, instrument, device) scoping** — both metadata extraction and fzf display should be scoped per (study, instrument, device) so the registry cleanly maps.

**Out of scope** (explicitly): refactor of `TECHNIQUE_ANALYZERS` (analyzer dispatch). Most analyzers are stubs and you don't want to expand the registry now. Waveform detection is a `library/` feature, not an analyzer-dispatch feature.

---

## Code Survey (callers of affected modules)

### `core/metadata/` (already a subpackage)

- 4 modules: `__init__.py` (171L), `keithley.py` (54L), `keysight.py` (215L), `raman_header.py` (41L), `waveform.py` (166L) — total 647 lines
- **External callers**: only `core/data_loader.py:221` (`extract_metadata`)
- **Internal dispatch**: `core/metadata/__init__.py` uses lazy imports for instrument-specific parsers (`keysight.py`, `waveform.py`)
- `waveform.py` already has detection logic for v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern. **Does NOT yet produce a 2D array.**

### `core/fzf_columns.py` + `core/fzf_utils.py` (flat modules)

- `fzf_columns.py` (87L) — `STUDY_COLUMN_REGISTRY`, `status_badge_for_file`, `get_step_columns`
- `fzf_utils.py` (349L) — `build_fzf_display`, `fzf_select`, helpers

**Importers of `fzf_utils`** (14 sites):
- CLI: `cli/commands/{plot,analyze,results,raman,uv_vis,add,afm,edit_cmd,delete_cmd,ec}.py`
- Library: `library/memristor/{device_cli,plotting}.py`, `library/pulse/device_cli.py`

**Importers of `fzf_columns`** (7 sites + 1 internal):
- CLI: `cli/commands/{plot,analyze,results}.py`
- Library: `library/pulse/device_cli.py`
- Internal: `core/fzf_utils.py:245` (uses `STUDY_COLUMN_REGISTRY`)
- Tests: `tests/test_core/test_fzf_columns.py`, `tests/test_core/test_status.py`

**Refactor cost**: medium. ~20 import sites to update. Mechanical change.

### `config-studies.yaml` current state (re relevant sections)

- 4 studies marked `kind: waveform_2d`: `pulse-stp-decay` (line 123), `pulse-endurance` (180), `pulse-ppf` (210), `pulse-retention` (294)
- `waveform_params:` block already defined for `pulse-stp-decay` (line 155) with `function: analyze_waveform_params`
- `derived_metadata:` blocks exist for the 4 pulse studies (v_set_v, v_read_v, etc.)
- **Gap**: `data_shape:` says `kind: waveform_2d` but nothing actually produces a 2D array. The waveform detection only writes scalars.

---

## Objectives

After this plan completes:

1. **Every pulse file loaded** gets a `waveform_pattern: [[t₀, v₀], [t₁, v₁], …]` entry in `protocol.yaml` step metadata, alongside the derived scalars.
2. **`core/fzf/` is a subpackage**: `core/fzf_columns.py` and `core/fzf_utils.py` are moved into `core/fzf/`. All 20+ import sites updated. Public API unchanged.
3. **(study, device) scoping works**: `get_step_columns()` and `build_fzf_display()` accept and use a `device_type` parameter, falling back to study-level defaults when no device override exists. `STUDY_COLUMN_REGISTRY` becomes `{(study, device): [cols], (study,): [cols]}` with merge logic.
4. **Metadata extraction is (study, instrument, device) aware**: `data_loader.py` resolves which `metadata_config` to use based on the (study, instrument) pair from `config-studies.yaml:studies.<study>.metadata_extractors.<inst>`, with per-device overrides.

---

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/metadata/waveform.py` | Add `detect_waveform_pattern_2d()` + `extract_waveform_metadata()` (orchestrator). No new module — waveform.py is the right home because it already houses `analyze_waveform_params()`. | Med |
| `src/science_cli/core/metadata/__init__.py` | Expose `detect_waveform_pattern_2d`; route `(study, device) → metadata_config` | Low |
| `src/science_cli/core/data_loader.py` | Call waveform detection when study kind == `waveform_2d`; attach `waveform_pattern` to meta | Med |
| `src/science_cli/core/protocol.py` | New `waveform_pattern` key in step metadata (no schema change — opaque list) | Low |
| `src/science_cli/core/analysis_output.py` | `merge_analysis_to_metadata()` writes `waveform_pattern` to protocol.yaml | Med |
| `src/science_cli/core/fzf/__init__.py` | **NEW** — package marker; re-export public API for backwards compat | Low |
| `src/science_cli/core/fzf/columns.py` | **MOVED from** `core/fzf_columns.py`; add `(study, device)` keying | Med |
| `src/science_cli/core/fzf/display.py` | **MOVED from** `core/fzf_utils.py`; `build_fzf_display` accepts `device_type` | Med |
| `src/science_cli/core/fzf_columns.py` | **DELETE** (after all importers updated) | Low |
| `src/science_cli/core/fzf_utils.py` | **DELETE** (after all importers updated) | Low |
| ~20 importer files | Update imports to `science_cli.core.fzf.{columns, display}` | Low (mechanical) |
| `config/config-studies.yaml` | Confirm 4 pulse studies have `data_shape: waveform_2d`; add `waveform_pattern_2d` to derived_metadata | Low |
| `src/science_cli/core/config.py` | New helper: `get_metadata_config_for(study, instrument, device) → dict` | Low |
| `tests/test_metadata/test_waveform.py` | **EXTEND** — add tests for `detect_waveform_pattern_2d()` + `extract_waveform_metadata()` (2D array output, scalar derivation, subsampling) | Low |
| `tests/test_core/test_fzf_columns.py` | Update imports; add (study, device) tests | Low |
| `tests/test_core/test_status.py` | Update imports | Low |
| `documentation/INDEX.md` | Note v3.20.0: waveform_pattern + fzf subpackage + (study, device) scoping | Low |
| `CHANGELOG.md` | Add v3.20.0 entry | Low |
| `~/.config/opencode/skills/sci-config-guide/SKILL.md` | Document waveform_pattern 2D output | Low |
| `~/.config/opencode/skills/sci-fzf-guide/SKILL.md` | Document (study, device) scoping | Low |
| `AGENTS.md` | Update directory map: `core/fzf/` is a subpackage | Low |
| `.lavish/ layer dashboards` | New `[sci]` artifacts for v3.20.0 phases | Low |

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Phase 5 (waveform 2D in core/metadata) | `code-medium` | Core feature; moderate complexity |
| Phase 6 (fzf subpackage) | `code-light` | Mechanical file move + import updates |
| Phase 7 ((study, device) scoping) | `code-medium` | Registry refactor, touches many sites |
| Phase 8 (docs) | `docs-medium` | CHANGELOG + skill updates + AGENTS.md |
| Phase 9 (integration tests) | `code-light` | Add tests; verify all pass |
| QA (each phase) | `review-light` | pytest + ruff + smoke |

---

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar |
|----|-------------|---------------|-------------|----------|
| w1 | Phase 5a — add `detect_waveform_pattern_2d()` in `core/metadata/waveform.py` | 1h | code | no |
| w2 | Phase 5b — add `extract_waveform_metadata()` orchestrator in `core/metadata/waveform.py` | 0.5h | code | no |
| w3 | Phase 5c — wire into `data_loader.py` and `analysis_output.py` (write to protocol.yaml) | 1h | code | no |
| w4 | Phase 5d — tests for waveform 2D detection (synthetic STP + endurance data) | 1h | code | no |
| w5 | Phase 6a — create `core/fzf/__init__.py`; move `fzf_columns.py` → `core/fzf/columns.py` | 0.5h | code | no |
| w6 | Phase 6b — move `fzf_utils.py` → `core/fzf/display.py`; re-export from `core/fzf/__init__.py` | 0.5h | code | no |
| w7 | Phase 6c — update 20+ import sites; delete old `fzf_columns.py` + `fzf_utils.py` | 1h | code | no |
| w8 | Phase 6d — update test imports (`test_fzf_columns.py`, `test_status.py`) | 0.5h | code | no |
| w9 | Phase 7a — `STUDY_COLUMN_REGISTRY` → `(study, device) → [cols]` registry with fall-through | 1.5h | code | no |
| w10 | Phase 7b — `get_step_columns()` accepts `device_type`; `build_fzf_display()` plumbs it through | 1h | code | no |
| w11 | Phase 7c — `get_metadata_config_for(study, instrument, device)` helper; wire into `data_loader.py` | 1.5h | code | no |
| w12 | Phase 7d — (study, device) tests for both fzf display and metadata extraction | 1h | code | no |
| w13 | Phase 8 — docs: CHANGELOG, INDEX, sci-config-guide, sci-fzf-guide, AGENTS.md | 1h | docs | no |
| w14 | Phase 9 — full test suite + ruff + smoke `sci info` + `sci plot`; commit | 1h | review | no |

**Total estimated: ~13h work, 4 sessions**.

---

## Dependency Order

```
5a (w1) ──> 5b (w2) ──> 5c (w3) ──> 5d (w4) ──┐
                                                  │
6a (w5) ──> 6b (w6) ──> 6c (w7) ──> 6d (w8) ─────┤
                                                  │
                            7a (w9) ──> 7b (w10) ─┼──> 7c (w11) ──> 7d (w12)
                                                  │
                                                  ▼
                                              8 (w13) ──> 9 (w14)
```

- Phases 5, 6 are independent and can run in parallel sessions.
- Phase 7 depends on both (uses new `core/fzf/` paths + new `core/metadata/waveform.py:extract_waveform_metadata()`).
- Phase 8 (docs) + Phase 9 (verify) are final.

---

## Phase 5 Detail: Split `core/metadata/` by Mechanism (parsers/ + analyzers/)

**Goal**: organize the metadata subpackage by mechanism. Parse functions (header scan) and analyze functions (DataFrame compute) live in separate folders. The dispatch layer in `core/metadata/__init__.py` keeps the external API stable so callers don't need to change.

**Why by mechanism, not by instrument:**
- Mechanism (parse vs analyze) is the natural axis — different inputs (lines vs df), different timing (load vs post-load), different failure modes (regex vs NaN)
- The dispatch code in `core/metadata/__init__.py` already separates `_parser_registry` and `ANALYSIS_REGISTRY`
- Files like `keysight.py` (215L) and `waveform.py` (166L) mix both — splitting keeps each file under 250L and growing future-proof
- When you open a file to find a parser, the folder name `parsers/keysight.py` answers "what is this" before you read the code

### 5a — Create the subfolders and move files

```
core/metadata/
├── __init__.py            # dispatch entry (extract_metadata, run_analysis, _parser_registry, ANALYSIS_REGISTRY)
├── parsers/
│   ├── __init__.py        # _parser_registry: {parser_name: callable}
│   ├── keysight.py        # parse_compliance, parse_sweep_range, parse_set_voltage, parse_repeat_count
│   ├── keithley.py        # (renamed/moved from core/metadata/keithley.py)
│   ├── raman.py           # (renamed from raman_header.py)
│   └── waveform.py        # parse_setup_pulses
└── analyzers/
    ├── __init__.py        # ANALYSIS_REGISTRY: {function_name: callable}
    ├── waveform.py        # analyze_waveform_params, detect_repeat_pattern, _detect_voltage_levels, _find_crossing_time
    ├── iv.py              # analyze_iv_compliance (moved from keysight.py)
    └── raman.py           # (placeholder for future raman analyzers)
```

**File moves:**
| From | To | New size |
|------|----|----------|
| `core/metadata/keysight.py` (215L) | split: `parsers/keysight.py` (parse_*, ~120L) + `analyzers/iv.py` (analyze_iv_compliance, ~80L) | 2 files |
| `core/metadata/keithley.py` (54L) | `parsers/keithley.py` | 1 file |
| `core/metadata/raman_header.py` (41L) | `parsers/raman.py` (renamed) | 1 file |
| `core/metadata/waveform.py` (166L) | split: `parsers/waveform.py` (parse_setup_pulses, ~10L) + `analyzers/waveform.py` (analyze_*, ~150L) | 2 files |

### 5b — Update `core/metadata/__init__.py` dispatch layer

The dispatch layer re-exports the registries from the new subfolders, keeping the public API unchanged:

```python
# core/metadata/__init__.py
"""Metadata extraction — parse (header scan) and analyze (DataFrame compute).

Public API (unchanged):
    - extract_metadata(raw_lines, metadata_config, df=None) -> (parsed, analysis)
    - run_analysis(name, df, raw_lines, inputs=None) -> dict
    - ANALYSIS_REGISTRY, _parser_registry
"""
from science_cli.core.metadata.parsers import _parser_registry
from science_cli.core.metadata.analyzers import ANALYSIS_REGISTRY

def run_analysis(name, df, raw_lines, inputs=None):
    fn = ANALYSIS_REGISTRY.get(name)
    return fn(df, raw_lines, inputs or {}) if fn else {}

def extract_metadata(raw_lines, metadata_config, df=None):
    parsed, analysis = {}, {}
    for field_name, field_cfg in metadata_config.items():
        method = field_cfg.get("method", "parse")
        if method == "parse":
            parsed[field_name] = _run_parse(field_name, field_cfg, raw_lines)
        elif method == "analyze" and df is not None:
            analysis[field_name] = run_analysis(
                field_cfg.get("function", ""), df, raw_lines,
                field_cfg.get("inputs", []),
            )
    return parsed, analysis

def _run_parse(field_name, field_cfg, raw_lines):
    """(unchanged from current) — uses _parser_registry from parsers/__init__.py"""
    ...
```

```python
# core/metadata/parsers/__init__.py
"""Parser registry — maps parser name to header-scanning function."""
from science_cli.core.metadata.parsers.keysight import (
    parse_set_voltage, parse_compliance, parse_sweep_range, parse_repeat_count,
)
from science_cli.core.metadata.parsers.keithley import (
    parse_compliance as keithley_parse_compliance,
    parse_sweep_range as keithley_parse_sweep_range,
)
from science_cli.core.metadata.parsers.raman import extract_raman_metadata
from science_cli.core.metadata.parsers.waveform import parse_setup_pulses

_parser_registry: dict[str, Callable] = {
    "set_voltage": parse_set_voltage,
    "compliance": parse_compliance,
    "sweep_range": parse_sweep_range,
    "repeat_count": parse_repeat_count,
    "setup_pulses": parse_setup_pulses,
    "raman_metadata": extract_raman_metadata,
}
```

```python
# core/metadata/analyzers/__init__.py
"""Analyzer registry — maps function name to DataFrame-compute function."""
from science_cli.core.metadata.analyzers.waveform import (
    analyze_waveform_params, detect_repeat_pattern,
)
from science_cli.core.metadata.analyzers.iv import analyze_iv_compliance

ANALYSIS_REGISTRY: dict[str, Callable] = {
    "analyze_waveform_params": analyze_waveform_params,
    "analyze_iv_compliance": analyze_iv_compliance,
    "detect_repeat_pattern": detect_repeat_pattern,
}
```

### 5c — Update all importers

| File | Old import | New import |
|------|-----------|------------|
| `data_loader.py:339` | `from science_cli.core.metadata.raman_header import extract_raman_metadata` | `from science_cli.core.metadata.parsers.raman import extract_raman_metadata` |
| `tests/test_core/test_metadata.py` (5 places) | `from science_cli.core.metadata.keysight import parse_*` | `from science_cli.core.metadata.parsers.keysight import parse_*` |
| `tests/test_core/test_metadata.py` (2 places) | `from science_cli.core.metadata.keithley import parse_*` | `from science_cli.core.metadata.parsers.keithley import parse_*` |
| `tests/test_core/test_metadata.py` (1 place) | `from science_cli.core.metadata.keysight import analyze_*` | `from science_cli.core.metadata.analyzers.iv import analyze_iv_compliance` |
| `tests/test_metadata/test_waveform.py` (12 places) | `from science_cli.core.metadata.waveform import …` | `from science_cli.core.metadata.{parsers,analyzers}.waveform import …` (split by function type) |
| `core/metadata/__init__.py` | `from science_cli.core.metadata.keysight import …` | `from science_cli.core.metadata.parsers.keysight import …` |
| `core/metadata/__init__.py` | `from science_cli.core.metadata.waveform import analyze_waveform_params` | `from science_cli.core.metadata.analyzers.waveform import analyze_waveform_params` |

`from science_cli.core.metadata import extract_metadata, run_analysis, ANALYSIS_REGISTRY` — **unchanged** (external API stable).

### 5d — Tests

All existing tests should pass after the move. Add a small test that verifies the new registries are populated:
- `tests/test_metadata/test_registries.py`:
  - `_parser_registry` contains all 6 parser names
  - `ANALYSIS_REGISTRY` contains all 3 analyzer names
  - `from science_cli.core.metadata import extract_metadata` works (external API stable)

---

## Phase 6 Detail: Waveform 2D Detection

**Goal**: every pulse file gets `waveform_pattern` (2D array) + derived scalars in protocol.yaml.

**Where**: `core/metadata/analyzers/waveform.py` (after Phase 5 split).

### 6a — `analyzers/waveform.py:detect_waveform_pattern_2d()`

```python
def detect_waveform_pattern_2d(df, max_points: int = 200) -> list[list[float]]:
    """Detect pulse waveform and return canonical 2D [[t, v], ...] array.

    Time in seconds, voltage in volts. Sorted by time.
    Subsampled to max_points evenly-spaced points to keep protocol.yaml small.
    Returns [] if no time/voltage column found.
    """
    voltage_col = _find_voltage_column(df)
    time_col = _find_time_column(df)
    if voltage_col is None or time_col is None:
        return []
    t = df[time_col].values.astype(float)
    v = df[voltage_col].values.astype(float)
    idx = np.argsort(t)
    t, v = t[idx], v[idx]
    if len(t) > max_points:
        step = len(t) // max_points
        t = t[::step][:max_points]
        v = v[::step][:max_points]
    return [[float(ti), float(vi)] for ti, vi in zip(t, v)]
```

### 6b — `analyzers/waveform.py:extract_waveform_metadata()` (orchestrator)

```python
def extract_waveform_metadata(
    df,
    study_name: str | None = None,
    device_type: str | None = None,
) -> dict:
    """Orchestrator: return waveform_pattern (2D) + derived scalars.

    Used when a study has data_shape.kind == "waveform_2d". Combines:
      - waveform_pattern: 2D [[t, v], ...] for plotting/illustration
      - derived scalars: v_set_v, v_read_v, set_width_us, read_width_us,
                         rise_us, fall_us, repeat_pattern, n_repeats

    The device_type parameter is reserved for future per-device specialization
    (e.g. volatile vs non-volatile memristor may emphasize different regions).
    """
    pattern = detect_waveform_pattern_2d(df)
    scalars = analyze_waveform_params(df, raw_lines=None, inputs={})
    repeats = detect_repeat_pattern(df)
    return {
        "waveform_pattern": pattern,
        **scalars,
        **repeats,
    }
```

### 6c — Wire into `data_loader.py` + `analysis_output.py`

In `data_loader.py:_load_with_device_config()` after `analysis_meta` is computed:
```python
# If study has data_shape == waveform_2d, also produce 2D pattern + scalars
study_cfg = device_cfg.get("study_config", {})  # populated by Phase 9c
if study_cfg.get("data_shape", {}).get("kind") == "waveform_2d":
    from science_cli.core.metadata.analyzers.waveform import extract_waveform_metadata
    device_type = study_cfg.get("device_type")
    pattern_meta = extract_waveform_metadata(df, study_name, device_type)
    if pattern_meta:
        analysis_meta["waveform_pattern"] = pattern_meta.get("waveform_pattern")
        analysis_meta.update({k: v for k, v in pattern_meta.items() if k != "waveform_pattern"})
```

In `analysis_output.py:merge_analysis_to_metadata()`:
- `waveform_pattern` flows into `step.metadata.waveform_pattern` as a list (YAML handles lists natively)

### 6d — Tests

`tests/test_metadata/test_waveform.py` (extend existing file):
- Synthetic STP data → check `waveform_pattern` is 2D list with correct shape
- Synthetic endurance data → check `waveform_pattern` + scalars
- Empty df → returns `{}`
- No time/voltage column → returns `{}`
- Subsampling: 1000-point input → output has 200 points

---

## Phase 7 Detail: Wire Waveform Detection (the implementation)

`detect_waveform_pattern_2d` and `extract_waveform_metadata` are written in Phase 6. Phase 7 is the **integration step** — calling them from `data_loader.py` and writing to `protocol.yaml`.

---

## Phase 6 Detail: core/fzf/ Subpackage

**Goal**: `core/fzf_columns.py` and `core/fzf_utils.py` become a subpackage. Public API unchanged.

### 6a/6b — Move files

```
src/science_cli/core/fzf_columns.py → src/science_cli/core/fzf/columns.py
src/science_cli/core/fzf_utils.py   → src/science_cli/core/fzf/display.py
```

NEW `src/science_cli/core/fzf/__init__.py`:
```python
"""fzf subpackage — column registry, display builder, and selection helpers."""
from science_cli.core.fzf.columns import (
    STUDY_COLUMN_REGISTRY,
    status_badge_for_file,
    get_step_columns,
)
from science_cli.core.fzf.display import (
    build_fzf_display,
    fzf_select,
)
```

### 6c — Update 20+ import sites

Mechanical replacement:
- `from science_cli.core.fzf_utils import …` → `from science_cli.core.fzf.display import …`
- `from science_cli.core.fzf_columns import …` → `from science_cli.core.fzf.columns import …`

Optionally keep shim at `core/fzf_columns.py` and `core/fzf_utils.py` for one release that re-exports from new location, then delete. **Recommendation: shim-then-delete** in two steps to keep the diff bisectable.

### 6d — Test imports

`tests/test_core/test_fzf_columns.py` + `tests/test_core/test_status.py` — same mechanical update.

---

## Phase 7 Detail: (study, device) Scoping

**Goal**: fzf display + metadata extraction are aware of the device context.

### 7a — `STUDY_COLUMN_REGISTRY` re-keying

Today: `dict[study_name, list[col_key]]`

After:
```python
STUDY_COLUMN_REGISTRY: dict[tuple[str, str | None], list[str]] = {
    # (study, device) — device-specific override
    ("pulse:pulse-endurance", "volatile-memristor"): [...],
    ("pulse:pulse-endurance", "non-volatile-memristor"): [...],
    # (study, None) — study default (fall-through)
    ("pulse:pulse-endurance", None): [...],
    ("pulse:pulse-stp-decay", None): [...],
    ...
}

def get_columns_for(study_name: str, device_type: str | None = None) -> list[str]:
    """Return column list, device-specific if registered, else study default."""
    if (study_name, device_type) in STUDY_COLUMN_REGISTRY:
        return STUDY_COLUMN_REGISTRY[(study_name, device_type)]
    return STUDY_COLUMN_REGISTRY.get((study_name, None), [])
```

**Backwards compat**: `STUDY_COLUMN_REGISTRY` keeps a flat alias `dict[str, list[str]]` for tests that index by study name only.

### 7b — `get_step_columns()` + `build_fzf_display()` accept `device_type`

```python
def get_step_columns(
    project_root, step_name: str,
    study_name: str | None = None,
    device_type: str | None = None,  # NEW
) -> dict:
    ...
    cols = get_columns_for(study_name, device_type)
    return {k: metadata.get(k) for k in cols if k in metadata}
```

`build_fzf_display()` propagates `device_type` to `get_step_columns()`.

### 7c — `get_metadata_config_for(study, instrument, device)` helper

```python
# src/science_cli/core/config.py
def get_metadata_config_for(
    study_name: str, instrument: str, device_type: str | None = None
) -> dict:
    """Resolve metadata_config for a (study, instrument) pair.

    Resolution order:
      1. studies.<study>.metadata_extractors.<inst> (canonical)
      2. instruments.<inst>.metadata (fallback)
    """
    studies = load_global_config().get("studies", {})
    # walk to studies.<study>.instruments.<inst>.metadata_extractors
    ...
```

In `data_loader.py`, replace the `device_cfg.get("metadata", {})` line with:
```python
metadata_config = get_metadata_config_for(study_name, device, device_type)
```

### 7d — Tests

- `STUDY_COLUMN_REGISTRY` test for (study, device) override
- `STUDY_COLUMN_REGISTRY` test for study default fall-through
- `get_metadata_config_for` test for (study, instrument) precedence

---

## Risks

| Risk | Mitigation |
|------|-----------|
| `waveform_pattern` makes protocol.yaml files large (200 × 8 bytes = 1.6KB per file × 1000 files = 1.6MB) | Subsample to 200 points; offer opt-out flag `protocol.write_waveform_pattern: false` in config |
| fzf subpackage move breaks callers I don't know about | Grep for all imports FIRST (done — 20 sites found); run pytest after each batch |
| (study, device) keying breaks `STUDY_COLUMN_REGISTRY` consumers that index by string | Provide flat alias dict for backwards compat; deprecate in 3.21.0 |
| `data_loader.py` is on the hot path | Waveform detection adds 1 numpy call + 1 list comp per pulse file. Benchmark before/after with sample STP file |
| `core/metadata/waveform.py` grows beyond 250 lines | Currently 166L. Adding two functions (~30L) keeps it under 250. If it grows, split into `waveform_pattern.py` + `waveform_params.py` (a future task) |

---

## Verification Plan (per phase)

| Phase | Verification |
|-------|--------------|
| 5a-d | `pytest tests/test_metadata/ -q` — all pass; new tests for 2D array output |
| 6a-d | `pytest tests/ -q` — all 548 still pass; imports updated; old files deleted |
| 7a-d | `pytest tests/ -q` — 548 still pass; new (study, device) tests pass |
| 8 | `sci info --json` runs cleanly in test project |
| 9 | `pytest tests/ -q` — 548 + new tests pass; `ruff check src/ tests/` clean |

---

## Open Questions for You

### Q1: Waveform 2D size cap

- (a) **Always 200 points** (subsampled). Small, fast, readable in protocol.yaml.
- (b) **Configurable per study** — `data_shape.max_points: 200` in `config-studies.yaml`.
- (c) **No cap** — full resolution. Risk: 10MB protocol.yaml files.

**My recommendation: (a)** with override flag in config for studies that need higher res.

### Q2: fzf subpackage naming

- (a) `core/fzf/columns.py` + `core/fzf/display.py` (recommended — short, descriptive)
- (b) `core/fzf/registry.py` + `core/fzf/render.py`
- (c) Keep file names: `core/fzf/fzf_columns.py` + `core/fzf/fzf_utils.py`

**My recommendation: (a)**.

### Q3: (study, device) registry keying — should device_type be optional?

- (a) **Always pass device_type, fall back to (study, None)**: `get_columns_for(study, device)` looks up `(study, device)`, then `(study, None)`. Callers always pass both. Cleanest.
- (b) **Device_type optional, only pass when known**: `get_columns_for(study)` looks up `(study, None)`; `get_columns_for(study, device)` looks up `(study, device)`. Backward compatible.

**My recommendation: (a)**. Forces callers to be explicit. Trivial to add `device_type=None` everywhere it isn't known yet.

### Q4: Should the `waveform_pattern` be written even for studies that aren't `waveform_2d`?

- (a) **No** — only `waveform_2d` studies get it. Clean.
- (b) **Yes for all pulse studies** — even if their `data_shape` is something else. More flexibility.

**My recommendation: (a)** — strict typing, no surprises.

### Q5: Branch decision

Stay on `dev` (continues v3.20.0 wave) or open `feat/waveform-2d-and-fzf-subpackage` for isolation?

**My recommendation: stay on dev** — these are all small, additive changes to existing config/schema, not breaking refactors.

---

## Walkthrough

(To be filled as phases complete.)

- Phase 5a — **Done** (`ea550b9`). Created `parsers/` and `analyzers/` subpackages under `core/metadata/`. Files moved:
  - `keysight.py` (215L) → `parsers/keysight.py` (110L, parsers only) + `analyzers/iv.py` (116L, `analyze_iv_compliance`)
  - `keithley.py` (54L) → `parsers/keithley.py` (55L, verbatim)
  - `raman_header.py` (41L) → `parsers/raman.py` (42L, renamed, `extract_raman_metadata` preserved)
  - `waveform.py` (166L) → `parsers/waveform.py` (16L, `parse_setup_pulses` only) + `analyzers/waveform.py` (156L, all analyze/detect/invert functions)
  - `__init__.py` (171L → 108L): imports `_parser_registry` from `parsers/` and `ANALYSIS_REGISTRY` from `analyzers/`; dispatch logic unchanged
  - Updated `data_loader.py:338` raman import → `parsers.raman`
  - Updated test imports in `tests/test_core/test_metadata.py` (5 keysight parser, 2 keithley parser, 5 analyzer imports) and `tests/test_metadata/test_waveform.py` (12 imports split by parser/analyzer)
  - Deleted old flat files. 548 passed, 4 pre-existing failures. Ruff clean on new files.
- Phase 5b — **Done** (`b40ecec`). Waveform 2D detection + metadata extractor. Added to `analyzers/waveform.py` (159L → 206L, +47L):
  - `detect_waveform_pattern_2d(df, max_points=200) → list[list[float]]`: Canonical 2D [[t, v], ...] array sorted by time, subsampled to max_points.
  - `extract_waveform_metadata(df, study_name, device_type) → dict`: Orchestrator combining 2D pattern + derived scalars (v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern, n_repeats).
  - Registered `extract_waveform_metadata` in `ANALYSIS_REGISTRY` (analyzers/__init__.py).
  - Wired into `data_loader.py:_load_with_device_config()`: added `study_name` parameter; after metadata extraction, looks up `data_shape.kind == "waveform_2d"` from global config and calls `extract_waveform_metadata()` to inject 2D pattern + scalars into `analysis_meta`.
  - Added 10 new tests: `TestDetectWaveformPattern2d` (6) + `TestExtractWaveformMetadata` (4).
  - 558 passed, 4 pre-existing failures. Commit: `b40ecec`.
- Phase 8 (fzf subpackage) — **Done** (`ab99652`). Created `core/fzf/`:
  - `core/fzf/columns.py` (from `core/fzf_columns.py`, verbatim)
  - `core/fzf/display.py` (from `core/fzf_utils.py`, internal import updated to `core.fzf.columns`)
  - `core/fzf/__init__.py` — re-exports public API for backwards compat
  - Updated 27 importer files (10 CLI commands + 3 library files + 5 test files)
  - Deleted `core/fzf_columns.py` + `core/fzf_utils.py`
  - 558 passed, 4 pre-existing failures.
- Phase 9 — **Done** (`fe72834`). (study, device) scoping for fzf display + metadata:
  - `STUDY_COLUMN_REGISTRY` re-keyed to `dict[tuple[str, str | None], list[str]]` with `(study, device)` tuples.
  - Device-specific overrides for pulse-endurance: volatile shows `v_read_v`, non-volatile shows `v_reset_v`.
  - Added `get_columns_for(study, device_type)` helper with fall-through logic.
  - Added `_STUDY_BY_NAME` backwards-compat alias.
  - `get_step_columns()` and `build_fzf_display()` now accept `device_type` parameter.
  - Added `get_metadata_config_for(study, instrument, device_type)` to `config.py` — resolves via study `metadata_extractors` with instrument-level fallback.
  - `data_loader._load_with_device_config()` uses `get_metadata_config_for()` when study known.
  - Extended `test_fzf_columns.py` with 10 new tests (registry shape, get_columns_for, device-type, build_fzf_display device override).
  - Added `TestGetMetadataConfigFor` class (4 tests) to `test_config.py`.
  - 572 passed, 4 pre-existing failures.
