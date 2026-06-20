---
layer: [5, 7]
type: plan
status: planning
tags: [device-dispatch, plot, analyze]
assignee: plan
---

# Implementation Plan: Device-Type-Aware Plot/Analyze Dispatch Architecture

**Date**: 17/06/2026
**Status**: 🟡 Planning
---

## Context Summary

**(from review-documents — science-cli, plot/analyze dispatch chain, config resolution)**

`science-cli` v3.14.0 has a study-based dispatch system (`StudyPlotter` in `plot/registry.py`) that maps one study → one plot function. The `_DEVICE_TYPES` config (volatile-memristor, non-volatile-memristor) groups studies but does not flow through the dispatch chain. This causes problems when the same study (e.g., `pulse:pulse-endurance`) needs different analysis/plotting depending on the device type.

Key subsystems involved:
- **Config layer**: `core/config_defaults.py` (_STUDIES, _DEVICE_TYPES, _LEGACY_TO_STUDY), `core/config.py` (_DEFAULT_TECHNIQUE_PATTERNS, _DEFAULT_GLOBAL_TECHNIQUES, _DEFAULT_TECHNIQUE_DEVICES)
- **Technique detection**: `core/technique.py` (PATTERNS, BUILTIN_TECHNIQUES, detect_technique, detect_study_or_technique)
- **Plot dispatch**: `plot/registry.py` (StudyPlotter, STUDY_PLOTTERS, resolve_study_plotter, _init_dedicated_plotters)
- **CLI handlers**: `cli/commands/plot.py` (_dispatch_technique_plot, _resolve_device, _do_plot), `cli/commands/analyze.py` (analyze_handler, TECHNIQUE_ANALYZERS)
- **Study model**: `core/studies.py` (Study, detect_study_from_filename, resolve_technique_from_study, get_studies_for_device_type)
- **Data loading**: `core/data_loader.py` (load_data_file, _resolve_device_config — already accepts study_name)

---

## Objectives

1. **Thread `device_type` through the full plot/analyze dispatch chain** so that shared studies (e.g., `pulse:pulse-endurance`) route to different plot/analysis functions depending on volatile-vs-non-volatile context
2. **Extend `StudyPlotter` registry** with per-device-type plot variants (no breaking changes to existing study→plotter mapping)
3. **Add `--device-type`/`-dt` CLI flag** to `plot` and `analyze` commands for explicit device-type override
4. **Auto-detect device_type** from: protocol YAML `devices:` field, study→device_type reverse lookup, CLI flag
5. **Complete `_DEFAULT_GLOBAL_TECHNIQUES`** — add missing entries for ec-cv, ec-ca, ec-eis, pulse-endurance, pulse-retention
6. **Resolve `ec-cv` vs `iv-sweep` pattern collision** — both share `_CV\.`, `\.cv$`, `cv_`, `cv-` patterns
7. **Fix `_resolve_device()` to accept `study_name`** for instrument fallback resolution
8. **Create device-type-aware plot functions** for `pulse:endurance` (volatile vs non-volatile variants)
9. **Keep `-t/--technique` working** with full backward compatibility throughout the transition

---

## Current Architecture Analysis

### Entity Relationships

```
┌──────────────────────────────────────────────────────────────────────┐
│                        _STUDIES (config_defaults.py)                 │
│                                                                      │
│  technique ──── study_name ──── {label, patterns[], legacy_codes[], │
│  (e.g., "iv")    (e.g.,             instruments: {                    │
│                  "iv-bipolar-         keysight-b1500a: {columns,     │
│                   sweep")              metadata, ...}                 │
│                                      }                               │
│                                   }                                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ grouped by
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    _DEVICE_TYPES (config_defaults.py)                 │
│                                                                      │
│  volatile-memristor ──► {                                            │
│    studies: ["iv:iv-bipolar-sweep", "pulse:pulse-endurance",        │
│              "pulse:pulse-stp-decay", "pulse:pulse-ppf"],           │
│    analysis_mode: "volatile",                                        │
│    library: "iv"                                                     │
│  }                                                                   │
│  non-volatile-memristor ──► {                                        │
│    studies: ["iv:iv-bipolar-sweep", "pulse:pulse-endurance",        │
│              "pulse:pulse-retention"],                               │
│    analysis_mode: "bipolar",                                         │
│    library: "iv"                                                     │
│  }                                                                   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ flows THROUGH
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  StudyPlotter (plot/registry.py)                      │
│                                                                      │
│  map: study_name → { plot_fn, overlay_fn, flags, hints,             │
│                      single_layout, overlay_layout }                 │
│                                                                      │
│  ❌ NO device_type dimension                                         │
│  ❌ "pulse:pulse-endurance" maps to ONE plotter regardless of device │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Current plot dispatch

```
plot_handler()
  │
  ├─ _plot_direct(files, args)
  │     │
  │     ├─ _parse_flags(args) → technique, study_name, flags
  │     ├─ _detect_study(filename) or auto_study
  │     ├─ if --describe: _show_describe(fp, study_name)
  │     └─ _dispatch_technique_plot(filepath, flags, technique, study_name)
  │           │
  │           ├─ _init_dedicated_plotters()  # lazy import
  │           ├─ resolve_study_plotter(study_name) → StudyPlotter
  │           └─ plotter.plot_fn(filepath, flags)  # ❌ no device_type
  │              or _do_plot(filepath, flags, technique, study_name)
  │                    │
  │                    ├─ _resolve_device(technique, filepath)
  │                    │     │
  │                    │     ├─ Check protocol YAML steps → instrument
  │                    │     └─ get_default_device(technique)
  │                    │           └─ ❌ doesn't use study_name
  │                    │
  │                    ├─ load_data_file(filepath, technique, device, study_name)
  │                    └─ _resolve_xy_columns(df, info, technique) → plot
  │
  └─ _plot_interactive(args)
        └─ (same pipeline through _do_plot)
```

### Pain Points (numbered by severity)

| # | Pain Point | Location | Impact |
|---|-----------|----------|--------|
| **P1** | `StudyPlotter` has no device_type dimension — `pulse:pulse-endurance` can't disambiguate volatile vs non-volatile behavior | `plot/registry.py` | **Critical** — same study name routes to same plotter regardless of device context |
| **P2** | `_resolve_device()` does not accept/use `study_name` for instrument fallback | `cli/commands/plot.py:69` | **High** — device resolution relies on technique-level config, not study-level instruments |
| **P3** | `_DEFAULT_GLOBAL_TECHNIQUES` missing entries for `ec-cv`, `ec-ca`, `ec-eis`, `pulse-endurance`, `pulse-retention` | `core/config.py:971` | **Medium** — `get_default_device()` returns "" for EC techniques, forcing fallback scan |
| **P4** | Pattern collision: `ec-cv` and `iv-sweep` share identical regex patterns (`_CV\.`, `\.cv$`, `cv_`, `cv-`) | `core/config.py:36-46` | **Medium** — `detect_technique("test_cv.csv")` is order-dependent; could match wrong technique |
| **P5** | Pattern detection duplicated across 3 sources: `_DEFAULT_TECHNIQUE_PATTERNS` (config.py), `PATTERNS` (technique.py), `_STUDIES.*[].patterns` (config_defaults.py) | 3 files | **Medium** — maintenance burden, subtle divergence over time |
| **P6** | `TECHNIQUE_ANALYZERS` maps technique → analyzer function (string) with no device_type dimension | `cli/commands/analyze.py:13` | **Medium** — same issue as P1 but for analyze dispatch |
| **P7** | Plot functions hardcode technique keys in `load_data_file()` calls (e.g., `technique="pulse-endurance"`) | `plot/*.py` | **Low** — works now but fragile for refactored device loading |
| **P8** | `_resolve_device()` duplicated between `plot.py` and `analyze.py` (two identical copies) | 2 files | **Low** — maintenance burden, should be factored out |
| **P9** | `STUDY_FLAGS` dict in `registry.py` is separate from flag definitions per plot function; some studies have empty flag lists | `plot/registry.py:88-100` | **Low** — cosmetic, but flags should live with their plotter |

---

## Proposed Architecture

### Core Concept: `device_type` Threads Through the Dispatch Chain

The fundamental change: `device_type` becomes a first-class parameter throughout the plot/analyze dispatch, enabling:

1. **Study + device_type → plot function resolution** (not just study alone)
2. **Device-type-aware analysis modes** (volatile single-state vs bipolar HRS/LRS)
3. **Device-type-aware instrument resolution** (which instrument config to use)

New dispatch chain:

```
filename
  │
  ├─ detect_study(filename) → study_name  (existing)
  ├─ detect_device_type(protocol_yaml, study_name, --dt flag) → device_type  (NEW)
  │     │
  │     ├─ Protocol YAML "devices:" field (highest priority)
  │     ├─ --device-type / -dt CLI flag
  │     ├─ Reverse lookup: which device_type has this study?
  │     └─ None (generic/no device type)
  │
  └─ dispatch(study_name, device_type) → actual plot/analyze function
        │
        ├─ resolve_study_plotter(study_name, device_type)
        │     │
        │     ├─ Lookup: StudyPlotter for study_name
        │     ├─ If device_type in plotter.device_variants → use variant
        │     └─ Else → use base plotter
        │
        └─ Invoke plot_fn(filepath, flags, device_type=device_type)
              │
              ├─ Passes device_type to load_data_file() for device config resolution
              └─ Uses analysis_mode from device_type config for algorithm selection
```

### Registry Changes

#### 1. New `DevicePlotterVariant` Dataclass

```python
# plot/registry.py (new)
@dataclass
class DevicePlotterVariant:
    """Device-type-specific override for a StudyPlotter."""
    plot_fn: Callable | None = None       # Override plot_fn for this device type
    overlay_fn: Callable | None = None    # Override overlay_fn for this device type
    analysis_mode: str = ""               # "volatile", "bipolar", "linear", etc.
    extra_flags: list[dict] = field(default_factory=list)  # Additional flags
    overlay_layout: str = ""              # Override layout for this device type
```

#### 2. `StudyPlotter` Gains `device_variants`

```diff
 @dataclass
 class StudyPlotter:
     plot_fn: Callable
     overlay_fn: Callable
     flags: list[dict] = field(default_factory=list)
     hints: dict | None = None
     single_layout: str = "single_axis"
     overlay_layout: str = "single_axis"
+    device_variants: dict[str, DevicePlotterVariant] = field(default_factory=dict)
```

#### 3. Resolution Function Signature Change

```python
# plot/registry.py
def resolve_study_plotter(
    study_name: str,
    device_type: str | None = None,
) -> StudyPlotter | None:
    """Resolve a StudyPlotter for a given study name.
    
    Args:
        study_name: Study name in "technique:study-name" format or legacy name.
        device_type: Optional device type for variant resolution.
                     Callers should use plotter.device_variants.get(device_type)
                     to resolve the actual plot/overlay functions.
    
    Returns:
        StudyPlotter or None. The caller is responsible for checking
        device_variants for device-type-specific overrides.
    """
```

#### 4. Device-Type Variant Registration for `pulse:pulse-endurance`

```python
# plot/registry.py — in _init_dedicated_plotters()
from science_cli.plot.pulse_endurance import (
    _plot_endurance_volatile,
    _plot_endurance_nonvolatile,
    _overlay_endurance_volatile,
    _overlay_endurance_nonvolatile,
)

STUDY_PLOTTERS["pulse:pulse-endurance"].device_variants = {
    "volatile-memristor": DevicePlotterVariant(
        plot_fn=_plot_endurance_volatile,
        overlay_fn=_overlay_endurance_volatile,
        analysis_mode="volatile",
    ),
    "non-volatile-memristor": DevicePlotterVariant(
        plot_fn=_plot_endurance_nonvolatile,
        overlay_fn=_overlay_endurance_nonvolatile,
        analysis_mode="bipolar",
    ),
}
```

### Dispatch Changes

#### 1. `_dispatch_technique_plot()` Receives `device_type`

```python
# cli/commands/plot.py
def _dispatch_technique_plot(
    filepath: str,
    flags: dict,
    technique: str,
    study_name: str | None = None,
    device_type: str | None = None,  # NEW
) -> None:
    """Route to technique/study-specific plotter via registry.
    
    When device_type is provided, checks for device-type-specific
    plotter variant before falling back to the base study plotter.
    """
    from science_cli.plot.registry import _init_dedicated_plotters, resolve_study_plotter
    _init_dedicated_plotters()

    plotter = None
    if study_name:
        plotter = resolve_study_plotter(study_name)
    if plotter is None and technique:
        plotter = resolve_study_plotter(technique)

    if plotter is not None and plotter.plot_fn.__name__ != '_fallback_plot':
        # Resolve device-type-specific variant
        variant = None
        if device_type:
            variant = plotter.device_variants.get(device_type)
        actual_plot_fn = variant.plot_fn if variant and variant.plot_fn else plotter.plot_fn
        actual_plot_fn(filepath, flags)
    else:
        _do_plot(filepath, flags, technique, study_name=study_name, device_type=device_type)
```

#### 2. `_do_plot()` and `_do_overlap()` Receive `device_type`

```python
def _do_plot(
    filepath: str,
    flags: dict,
    technique: str = "",
    study_name: str | None = None,
    device_type: str | None = None,  # NEW
) -> None:
    # Use device_type to resolve the correct device config
    # Also pass device_type through to _resolve_device for study-aware resolution
```

#### 3. `_resolve_device()` Receives `study_name`

```diff
 def _resolve_device(
     technique: str,
     filepath: str,
+    study_name: str | None = None,  # NEW
 ) -> str:
     """Determine which device was used for this file.
     
     Resolution order:
         1. Protocol YAML steps → instrument field
         2. Study instruments (if study_name provided)  # NEW
-        2. get_default_device(technique) from config
+        3. get_default_device(technique, study_name=study_name) from config
     """
```

#### 4. Device Type Auto-Detection

```python
# NEW: cli/commands/plot.py
def _detect_device_type(
    technique: str,
    study_name: str | None = None,
    flags: dict | None = None,
    project_root: Path | None = None,
) -> str | None:
    """Auto-detect device type from multiple sources.
    
    Resolution order:
        1. CLI flag: --device-type / -dt
        2. Protocol YAML "devices:" field (from session context)
        3. Reverse lookup: which device_types include this study?
    
    Returns:
        Device type slug (e.g. "volatile-memristor") or None.
    """
    # 1. Explicit CLI flag
    if flags:
        dt = flags.get("device-type") or flags.get("dt", "")
        if dt:
            return dt

    # 2. Protocol YAML devices field
    from science_cli.core.session import load_session
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    
    proj = project_root or get_current_project_path()
    session = load_session()
    pname = session.get("last_protocol", "")
    
    if pname and proj:
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(pname)
        if yaml_path.exists():
            import yaml
            with open(yaml_path) as f:
                proto = yaml.safe_load(f) or {}
            devices_field = proto.get("devices", "")
            if devices_field and devices_field != "general":
                return devices_field

    # 3. Reverse lookup: which device types include this study?
    if study_name:
        from science_cli.core.config import load_global_config
        config = load_global_config()
        device_types = config.get("device_types", {})
        for dt_slug, dt_cfg in device_types.items():
            if study_name in dt_cfg.get("studies", []):
                return dt_slug
    
    return None
```

### Config Changes

#### 1. Complete `_DEFAULT_GLOBAL_TECHNIQUES`

Add missing entries:

```python
# core/config.py — _DEFAULT_GLOBAL_TECHNIQUES additions
"ec-cv": {
    "label": "Cyclic Voltammetry",
    "grammar_codes": ["ec-cv", "cv", "CV"],
    "default_device": "autolab-usth",
},
"ec-ca": {
    "label": "Chronoamperometry",
    "grammar_codes": ["ec-ca", "ca", "CA"],
    "default_device": "autolab-usth",
},
"ec-eis": {
    "label": "EIS — Electrochemical Impedance Spectroscopy",
    "grammar_codes": ["ec-eis", "eis", "EIS", "impedance"],
    "default_device": "autolab-usth",
},
"pulse-endurance": {
    "label": "Pulse Endurance Cycling",
    "grammar_codes": ["endurance", "pulse-endurance", "end"],
    "default_device": "keysight-b1500a",
},
"pulse-retention": {
    "label": "Pulse Retention Time",
    "grammar_codes": ["retention", "pulse-retention", "ret"],
    "default_device": "keysight-b1500a",
},
```

#### 2. Fix `ec-cv` vs `iv-sweep` Pattern Collision

**Problem**: Both `ec-cv` and `iv-sweep` patterns include `_CV\.`, `\.cv$`, `cv_`, `cv-`. This is because the legacy system used the same filename codes for both CV (electrochemistry) and CV (capacitance-voltage). The fix: **remove the ambiguous patterns from `iv-sweep`** in `_DEFAULT_TECHNIQUE_PATTERNS` and `PATTERNS`, keeping only study-level patterns (`_STUDIES`) which use substring matching and are less ambiguous. For `ec-cv`, keep the patterns since `.mpt` files are unambiguous. For iv-sweep, rely on study patterns like `iv-sweep`, `_IV`, `iv-bipolar`, `sweep_`.

```diff
 _DEFAULT_TECHNIQUE_PATTERNS: dict[str, list[str]] = {
     "ec-cv": [r"_CV\.", r"\.cv$", r"cv_", r"cv-"],
     "ec-ca": [r"_CA\.", r"\.ca$", r"ca_", r"ca-"],
     "ec-eis": [r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"],
-    "iv-sweep": [r"_CV\.", r"\.cv$", r"cv_", r"cv-"],
+    "iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"],
     "iv-breakdown": [r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"],
     "iv-leakage": [r"_leak", r"leakage_", r"leak_"],
     ...
 }
```

Same change needed in `core/technique.py:PATTERNS` (already has `_IV\.`, `\.iv$`, `iv_`, `iv-`, `_sweep`, `sweep_` for iv-sweep — but ALSO has the `_CV\.` ones. The technique.py version already has the correct patterns for iv-sweep since v3.12.0. Let me verify... Actually, looking at technique.py line 66: `"iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"]` — this is already correct! The collision is only in `_DEFAULT_TECHNIQUE_PATTERNS` in config.py which still has the old patterns.)

#### 3. Consolidate Pattern Sources (Documentation-Level)

The three pattern sources serve different purposes and should remain but with clear documentation:

| Source | Purpose | Priority |
|--------|---------|----------|
| `_DEFAULT_TECHNIQUE_PATTERNS` (config.py) | Hardcoded fallback when no config files exist | **Lowest** |
| `PATTERNS` (technique.py) | Legacy comprehensive fallback, marked deprecated | **Low** |
| `_STUDIES.*[].patterns` (config_defaults.py) | Study-level substring patterns, used by `detect_study_from_filename()` | **Highest** |

The eventual goal (v4.0) is to remove `_DEFAULT_TECHNIQUE_PATTERNS` and `PATTERNS` entirely, relying solely on study-level patterns from config files. For now, the collision fix in (2) above is sufficient.

#### 4. `get_default_device()` Gains `study_name` Parameter

```diff
 def get_default_device(
     technique: str,
     project_root: Path | None = None,
+    study_name: str | None = None,  # NEW
 ) -> str:
     """Return the preferred default device name for a technique.
     
     Resolution order:
         1. ``defaults`` section of merged config
         2. ``default_device`` field in ``_DEFAULT_GLOBAL_TECHNIQUES``
         3. Study instruments (first instrument of the mapped study)
+        4. study_name instruments (first instrument of the given study)  # NEW
     """
```

### Analyze Dispatch Changes

The `analyze` command has similar issues. `TECHNIQUE_ANALYZERS` maps technique → analyzer function name, with no device-type dimension. The fix is similar:

```python
# cli/commands/analyze.py
def _analyze_with_technique(
    technique: str,
    flags: dict,
    study_name: str | None = None,
    device_type: str | None = None,  # NEW
) -> None:
    """Route analysis to the correct analyzer, now device-type-aware."""
```

And the `_analyze_pulse_endurance` function (or its dispatch) should use device_type to decide between volatile (single-state cycling) and non-volatile (bipolar HRS/LRS) analysis.

---

## Migration Path

### Phase 1: Foundation — Data Model & Registry (Minimal Risk)

**Goal**: Add `device_type` threading infrastructure without changing any behavior.

| Task ID | Description | Files | Est. Duration | Difficulty |
|---------|-------------|-------|---------------|------------|
| **T1** | Add `DevicePlotterVariant` dataclass to `plot/registry.py` | `plot/registry.py` | 30m | Low |
| **T2** | Add `device_variants` field to `StudyPlotter` | `plot/registry.py` | 15m | Low |
| **T3** | Update `resolve_study_plotter()` signature to accept `device_type` (backward compat: optional, default None) | `plot/registry.py` | 15m | Low |
| **T4** | Add `_detect_device_type()` function to `cli/commands/plot.py` | `cli/commands/plot.py` | 45m | Medium |
| **T5** | Add `--device-type`/`-dt` CLI flag support in `plot_handler()`, `_plot_direct()`, `_plot_interactive()` | `cli/commands/plot.py` | 30m | Low |

### Phase 2: Config Completion & Fixes (Low-Medium Risk)

**Goal**: Fix the known config gaps and pattern collision.

| Task ID | Description | Files | Est. Duration | Difficulty |
|---------|-------------|-------|---------------|------------|
| **T6** | Add missing entries to `_DEFAULT_GLOBAL_TECHNIQUES`: `ec-cv`, `ec-ca`, `ec-eis`, `pulse-endurance`, `pulse-retention` | `core/config.py` | 20m | Low |
| **T7** | Fix `ec-cv` vs `iv-sweep` pattern collision in `_DEFAULT_TECHNIQUE_PATTERNS` (remove `_CV\.` etc. from iv-sweep) | `core/config.py` | 15m | **Medium** |
| **T8** | Add `study_name` parameter to `_resolve_device()` in both `plot.py` and `analyze.py` | `cli/commands/plot.py`, `cli/commands/analyze.py` | 30m | Low |
| **T9** | Add `study_name` parameter to `get_default_device()` in `core/config.py` | `core/config.py` | 20m | Low |

### Phase 3: Device-Type-Aware Dispatch (Medium Risk)

**Goal**: Thread `device_type` through the dispatch chain. Plot functions that differ by device type get variants.

| Task ID | Description | Files | Est. Duration | Difficulty |
|---------|-------------|-------|---------------|------------|
| **T10** | Update `_dispatch_technique_plot()` to accept and use `device_type`, resolving variants from `StudyPlotter.device_variants` | `cli/commands/plot.py`, `plot/registry.py` | 45m | Medium |
| **T11** | Update `_do_plot()` signature to accept `device_type` and pass to `_resolve_device()` + `load_data_file()` | `cli/commands/plot.py` | 30m | Medium |
| **T12** | Update `_do_overlap()` similarly | `cli/commands/plot.py` | 30m | Medium |
| **T13** | Update `_plot_direct()`, `_plot_interactive()` to call `_detect_device_type()` and pass result through chain | `cli/commands/plot.py` | 30m | Medium |
| **T14** | Create `_plot_endurance_volatile()` and `_plot_endurance_nonvolatile()` variants in `plot/pulse_endurance.py` | `plot/pulse_endurance.py` | 1.5h | **High** |
| **T15** | Register device-type variants for `pulse:pulse-endurance` in `_init_dedicated_plotters()` | `plot/registry.py` | 15m | Low |
| **T16** | Update `analyze_handler()` and `_analyze_with_technique()` to pass `device_type` to analyzer functions | `cli/commands/analyze.py` | 45m | Medium |
| **T17** | Update `_analyze_pulse_endurance()` (or its dispatch) to use device_type for volatile vs non-volatile analysis mode | `cli/commands/analyze.py` (or `library/pulse/endurance.py`) | 1h | **High** |

### Phase 4: Documentation & Testing (Low Risk)

| Task ID | Description | Files | Est. Duration | Difficulty |
|---------|-------------|-------|---------------|------------|
| **T18** | Write tests for `_detect_device_type()`, device-variant resolution, and pattern collision fix | `tests/` | 1.5h | Medium |
| **T19** | Update CLI help text (`plot --help`, `analyze --help`) to document `--device-type`/`-dt` flag | `cli/help.py` | 20m | Low |
| **T20** | Update `CHANGELOG.md` with v3.15.0 entries | `CHANGELOG.md` | 20m | Low |
| **T21** | Update README.md with device-type-aware dispatch documentation | `README.md` | 30m | Low |
| **T22** | De-duplicate `_resolve_device()` — extract to shared utility | `cli/commands/plot.py`, `cli/commands/analyze.py`, new `core/device_resolver.py` | 45m | Medium |

---

## Backward Compatibility

### Strategy: Progressive Enhancement, No Breaking Changes

1. **`-t/--technique` flag continues to work**: The legacy flag is already deprecated (removal in v4.0.0) but fully functional. All new code paths default to study-name-based resolution, falling back to technique-based resolution with a deprecation notice.

2. **`StudyPlotter.device_variants` defaults to empty dict**: All existing plotters continue to work exactly as before. Only studies with registered device variants get different behavior.

3. **`--device-type`/`-dt` is optional**: When not provided, the system auto-detects from protocol YAML or reverse study lookup. If neither produces a device type, behavior is identical to current (no device type = base plotter used).

4. **Pattern collision fix (`ec-cv` vs `iv-sweep`) preserves both techniques**: Removing `_CV\.` etc. from `iv-sweep` in `_DEFAULT_TECHNIQUE_PATTERNS` doesn't break `iv-sweep` detection because:
   - `PATTERNS` in `technique.py` already has the correct iv-sweep patterns (`_IV\.`, `\.iv$`, `iv_`, `iv-`, `_sweep`, `sweep_`)
   - Study-level patterns in `_STUDIES["iv"]["iv-bipolar-sweep"]["patterns"]` use substring matching (`iv-sweep`, `_IV`, `iv-bipolar`, `sweep_`)
   - `detect_study_from_filename()` (study-level detection) is tried FIRST by `detect_study_or_technique()`

5. **`_resolve_device()` signature change is backward-compat**: `study_name=None` is the default, so existing callers without study_name continue to work.

6. **Plot function signatures unchanged for existing functions**: Only new device-variant plot functions receive `device_type` parameter. Existing functions (`_plot_iv_bipolar`, `_plot_stp_decay`, etc.) are NOT modified.

### Transition Timeline

```
v3.14.0 (current)     ── study-based dispatch, device_type in config only
         │
v3.15.0 (this plan)   ── device_type threads through dispatch
         │               --device-type/-dt flag added
         │               ec-cv/iv-sweep pattern collision fixed
         │               _DEFAULT_GLOBAL_TECHNIQUES completed
         │               pulse:endurance gets volatile/non-volatile variants
         │
v4.0.0 (future)       ── -t/--technique removed
                        _DEFAULT_TECHNIQUE_PATTERNS removed
                        PATTERNS removed from technique.py
                        device_type becomes required for ambiguous studies
```

---

## Files to Modify

| File | Change Description | Risk | Phase |
|------|-------------------|------|-------|
| `plot/registry.py` | Add `DevicePlotterVariant` dataclass; add `device_variants` to `StudyPlotter`; update `resolve_study_plotter()`; register endurance variants in `_init_dedicated_plotters()` | **Low** | 1, 3 |
| `cli/commands/plot.py` | Add `_detect_device_type()`; add `--device-type`/`-dt` flag; update `_dispatch_technique_plot()`, `_do_plot()`, `_do_overlap()`, `_plot_direct()`, `_plot_interactive()` to accept/pass `device_type`; add `study_name` to `_resolve_device()` | **Medium** | 1, 2, 3 |
| `cli/commands/analyze.py` | Add `study_name` to `_resolve_device()`; update `analyze_handler()` and `_analyze_with_technique()` to accept/pass `device_type`; update `_analyze_pulse_endurance()` dispatch | **Medium** | 2, 3 |
| `core/config.py` | Add ec-cv/ec-ca/ec-eis/pulse-endurance/pulse-retention to `_DEFAULT_GLOBAL_TECHNIQUES`; fix iv-sweep patterns in `_DEFAULT_TECHNIQUE_PATTERNS`; add `study_name` to `get_default_device()` | **Medium** | 2 |
| `core/config_defaults.py` | No changes needed — `_DEVICE_TYPES` already defines the device_type → studies mapping | — | — |
| `core/technique.py` | No changes needed — `PATTERNS` already has correct iv-sweep patterns (lines 66-67) | — | — |
| `core/studies.py` | No changes needed — `get_studies_for_device_type()` already exists | — | — |
| `core/data_loader.py` | Already accepts `study_name` (no change needed for Phase 1-3) | — | — |
| `plot/pulse_endurance.py` | Create `_plot_endurance_volatile()` and `_plot_endurance_nonvolatile()` variants; create overlay variants | **High** | 3 |
| `plot/pulse_retention.py` | Minor: ensure `_plot_retention()` works with device_type for future non-volatile context | **Low** | 3 |
| `core/device_resolver.py` | **NEW**: Extract duplicated `_resolve_device()` from plot.py and analyze.py | **Low** | 4 |
| `cli/help.py` | Add `--device-type`/`-dt` to plot and analyze help text | **Low** | 4 |
| `tests/test_core/test_config.py` | Add tests for new `_DEFAULT_GLOBAL_TECHNIQUES` entries and pattern collision fix | **Low** | 4 |
| `tests/test_plot/test_registry.py` | Add tests for `DevicePlotterVariant` resolution and device-variant dispatch | **Medium** | 4 |
| `tests/test_cli/test_plot.py` | Add integration tests for `--device-type` flag and auto-detection | **Medium** | 4 |
| `CHANGELOG.md` | Document v3.15.0 changes | **Low** | 4 |
| `README.md` | Update with device-type-aware dispatch section | **Low** | 4 |

---

## Agent Delegation

| Task | Sub-Agent | Model | Notes |
|------|-----------|-------|-------|
| Phase 1: Registry + detection foundation | `code-heavy` | deepseek-v4-pro | Data model changes — must be precise |
| Phase 2: Config fixes + resolve_device | `code-medium` | qwen3-coder | Pattern collision fix needs care |
| Phase 3: Dispatch threading + endurance variants | `code-heavy` | deepseek-v4-pro | Core dispatch logic — verify all paths |
| Phase 4: Tests + docs + de-duplicate | `code-medium` | qwen3-coder | Routine test/doc work |
| QA & Integration Review | `review-heavy` | qwen3.7-plus | Run full test suite, check backward compat |
| Documentation | `docs-heavy` | qwen3.7-plus | CHANGELOG, README, help text update |
| Calendar Sync | `calendar` | — | Create/update GCal events for calendar-marked tasks |

---

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| **T1** | Add `DevicePlotterVariant` dataclass to `plot/registry.py` | 30m | code-medium | no |
| **T2** | Add `device_variants` field to `StudyPlotter` dataclass | 15m | code-medium | no |
| **T3** | Update `resolve_study_plotter()` signature for `device_type` | 15m | code-medium | no |
| **T4** | Add `_detect_device_type()` function to `cli/commands/plot.py` | 45m | code-heavy | yes |
| **T5** | Add `--device-type`/`-dt` CLI flag in plot_handler, _plot_direct, _plot_interactive | 30m | code-medium | no |
| **T6** | Add missing entries to `_DEFAULT_GLOBAL_TECHNIQUES` | 20m | code-medium | no |
| **T7** | Fix ec-cv vs iv-sweep pattern collision in `_DEFAULT_TECHNIQUE_PATTERNS` | 15m | code-medium | yes |
| **T8** | Add `study_name` param to `_resolve_device()` in plot.py and analyze.py | 30m | code-medium | no |
| **T9** | Add `study_name` param to `get_default_device()` in `core/config.py` | 20m | code-medium | no |
| **T10** | Update `_dispatch_technique_plot()` for device-type-aware dispatch | 45m | code-heavy | yes |
| **T11** | Update `_do_plot()` to accept and use `device_type` | 30m | code-heavy | no |
| **T12** | Update `_do_overlap()` to accept and use `device_type` | 30m | code-heavy | no |
| **T13** | Wire `_detect_device_type()` into _plot_direct and _plot_interactive | 30m | code-heavy | no |
| **T14** | Create `_plot_endurance_volatile()` and `_plot_endurance_nonvolatile()` | 1.5h | code-heavy | yes |
| **T15** | Register device variants for pulse:endurance in _init_dedicated_plotters | 15m | code-heavy | no |
| **T16** | Update analyze dispatch for device_type | 45m | code-heavy | yes |
| **T17** | Update endurance analyze dispatch for device_type | 1h | code-heavy | yes |
| **T18** | Write tests for device detection, variant resolution, pattern fix | 1.5h | code-medium | no |
| **T19** | Update `plot --help` and `analyze --help` text | 20m | docs-light | no |
| **T20** | Update `CHANGELOG.md` | 20m | docs-light | no |
| **T21** | Update `README.md` | 30m | docs-medium | no |
| **T22** | De-duplicate `_resolve_device()` to shared utility | 45m | code-medium | no |

---

## Calendar

- Calendar shall create/update GCal events for tasks marked `Calendar Event: yes`
- Events use UPSERT semantics (update if exists, create if not)
- Session tracking: start time is when code begins implementation, end time is when review passes
- Calendar queries `git log --since` / `git diff` timestamps to determine actual work windows
- Event descriptions include `Task-ID: {task-id}` for bidirectional lookup

**Calendar-marked tasks**: T4, T7, T10, T14, T16, T17 (6 total)

---

## Dependency Order

```
Phase 1 (Foundation):
  T1 → T2 → T3  (registry data model)
  T4, T5        (device detection + CLI flags — can run parallel to T1-T3)

Phase 2 (Config Fixes):
  T6, T7, T8, T9  (all independent, can run parallel)

Phase 3 (Dispatch):
  T10 → T11, T12  (dispatch plumbing)
  T13             (wiring auto-detection — depends on T4, T5, T10)
  T14 → T15       (endurance variants — depends on T1-T3, T10)
  T16, T17        (analyze dispatch — depends on T4, T10)

Phase 4 (Docs & Tests):
  T18             (tests — depends on all Phase 1-3 completion)
  T19, T20, T21   (docs — after T18)
  T22             (de-duplicate — after T8)
```

### Critical Path

```
T1 → T2 → T3 → T10 → T11 → T12 → T13 → T18 → T20
                     ↘ T14 → T15 ↗
```

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Pattern collision fix breaks iv-sweep detection** | Medium | iv-sweep already has correct patterns in `PATTERNS` (technique.py) and study-level patterns. The `_DEFAULT_TECHNIQUE_PATTERNS` entry was duplicative. Test with actual filenames before committing. |
| **Endurance variant plot functions diverge** | Medium | Share common code via `plot/base.py` helpers (`apply_figure_kw`, `parse_figsize`, `save_figure`). Only the analysis logic (HRS/LRS extraction vs single-state extraction) should differ. |
| **`device_type` auto-detection ambiguous** | Low | When a study (like `iv:iv-bipolar-sweep`) belongs to multiple device types, auto-detection returns the first match. Mitigation: `--device-type` flag for explicit override. Future: prompt user when ambiguous. |
| **EC pattern collision not fully resolved** | Low | `ec-cv` and `iv-sweep` patterns still overlap in _DEFAULT_TECHNIQUE_PATTERNS. But `ec-cv` is only tested after file extension check (`.mpt` is EC-specific), and study-level detection is tried first, reducing ambiguity. |
| **Break backward compat for old `config.yaml` users** | Low | No changes to the config loading path. Only `_DEFAULT_GLOBAL_TECHNIQUES` (hardcoded fallback) additions. |
| **Circular imports from `device_resolver.py`** | Low | Extract `_resolve_device()` to a standalone utility that depends only on `core/config.py` and `core/session.py`. These are already imported in both plot.py and analyze.py. |

---

## Walkthrough

*(To be filled during implementation — step-by-step notes on what was actually done, any deviations from plan, and lessons learned.)*

### Phase 1 Notes

### Phase 2 Notes

**Date**: 17/06/2026
**Agent**: code-medium
**Status**: ✅ Complete

#### T6 — Add missing `_DEFAULT_GLOBAL_TECHNIQUES` entries
- Added 5 new entries to `_DEFAULT_GLOBAL_TECHNIQUES` in `core/config.py`:
  - `ec-cv` → `default_device: autolab-usth`
  - `ec-ca` → `default_device: autolab-usth`
  - `ec-eis` → `default_device: autolab-usth`
  - `pulse-endurance` → `default_device: keysight-b1500a`
  - `pulse-retention` → `default_device: keysight-b1500a`
- Verified: `get_default_device('ec-cv')` returns `'autolab-usth'`, etc.

#### T7 — Fix `ec-cv` vs `iv-sweep` pattern collision
- Changed `_DEFAULT_TECHNIQUE_PATTERNS["iv-sweep"]` from:
  `[r"_CV\.", r"\.cv$", r"cv_", r"cv-"]` → `[r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"]`
- Verified: zero overlapping patterns between `iv-sweep` and `ec-cv`.
- `technique.py:PATTERNS` already had the correct `iv-sweep` patterns (no change needed there).
- No deviation from plan.

#### T8 — Add `study_name` to `_resolve_device()` in plot.py and analyze.py
- Updated `_resolve_device()` in both `cli/commands/plot.py` and `cli/commands/analyze.py`:
  - Added `study_name: str | None = None` parameter
  - Added new resolution step 2: when `study_name` provided and technique is empty, try `get_study_config()` for instrument fallback
  - Changed fallback from `get_default_device(technique)` → `get_default_device(technique, study_name=study_name)`
  - Updated docstrings to reflect new resolution order
- No deviation from plan.

#### T9 — Add `study_name` to `get_default_device()` in core/config.py
- Added `study_name: str | None = None` parameter to `get_default_device()`
- Renamed local `study_name` variable to `legacy_study` to avoid shadowing
- Added new resolution step 4: when `study_name` provided and earlier steps fail, check `get_study_config()` for instruments
- Updated docstring
- Verified backward compat: `get_default_device('ec-cv')` still works with no `study_name`

#### Test Results
- 412 tests pass, 3 pre-existing failures (unrelated: migration script path, electrochem device type undefined)
- `pytest tests/ -q --tb=short`: 3 failed, 412 passed — all 3 failures are pre-existing

### Phase 3 Notes

### Phase 4 Notes
