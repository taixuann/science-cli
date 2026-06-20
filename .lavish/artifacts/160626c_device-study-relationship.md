---
layer: [1]
type: design-discussion
status: done
tags: [config, grammar, architecture]
assignee: human
---

# Architecture Analysis: Devices ↔ Studies ↔ Instruments ↔ Grammar ↔ Parsers ↔ Plotting ↔ Analyze ↔ Metadata

**Date**: 16/06/2026
**Status**: 🟢 Done (analysis artifact — no implementation required)

---

## 1. Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEVICE TYPE                                         │
│  (volatile-memristor, non-volatile-memristor, electrochem, deposition,       │
│   general)                                                                    │
│                                                                              │
│  Properties: analysis_mode (volatile/bipolar/linear/general)                 │
│               library (iv/pulse/ec/pvd/general)                              │
│               studies[] — list of study names it supports                     │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         │ 1:N "has studies"
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STUDY                                               │
│  (iv:iv-bipolar-sweep, pulse:pulse-stp-decay, ec:ec-cv, ...)                │
│                                                                              │
│  Properties: technique (iv/pulse/ec/raman/afm/uv-vis)                        │
│               patterns[] — filename substring patterns for detection          │
│               legacy_codes[] — backward-compat technique codes               │
│               instruments{} — per-instrument loading configs                 │
│               label — human-readable description                             │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         │ 1:N "uses"
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INSTRUMENT                                          │
│  (keithley-2400, keysight-b1500a, autolab-usth, horiba-usth,                │
│   spectrometer-iop)                                                           │
│                                                                              │
│  Properties: type (sourcemeter/parameter-analyzer/potentiostat/...)          │
│               location                                                       │
│               techniques[] — list of technique names compatible              │
│               config{} — delimiter, header_lines, decimal, encoding          │
│               columns{} — per-instrument default column mapping              │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         │ contains per-study instrument config (columns,
                         │ delimiter, header_lines, metadata::{parse/analyze} )
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INSTRUMENT × STUDY CONFIG                                │
│  (embedded in _STUDIES[technique][study].instruments[instrument])            │
│                                                                              │
│  Properties: columns{} — column name remapping for THIS study               │
│               header_lines — may differ from instrument default              │
│               delimiter, decimal, encoding                                    │
│               metadata{} — parsers (header scan) + analyzers (computation)   │
│                 ├── parse_* functions (header line extraction)               │
│                 └── analyze_* functions (column computation)                 │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         │ loaded by
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA LOADER (data_loader.py)                            │
│                                                                              │
│  Flow: study_name → get_study_config() → instruments[device] →              │
│        device_cfg (columns, header_lines, delimiter, metadata)              │
│        → pandas read_csv with config → column remapping →                   │
│        → metadata pipeline (parse headers + analyze columns)                 │
│        → (DataFrame, info_dict)                                              │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         │ consumed by two dispatch chains
                         ▼
┌─────────────────────────────────────┬──────────────────────────────────────┐
│         PLOT DISPATCH                │        ANALYZE DISPATCH              │
│  (plot.py, plot/registry.py)        │  (analyze.py)                        │
│                                      │                                      │
│  study_name → resolve_study_plotter │  technique → TECHNIQUE_ANALYZERS    │
│  → StudyPlotter (plot_fn, overlay)  │  → analyzer function                │
│  OR fallback _do_plot() →           │  → loads data via load_data_file()  │
│  _resolve_xy_columns(df, technique) │  → runs computation                 │
│  → matplotlib plot                  │  → outputs YAML/results             │
└─────────────────────────────────────┴──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        METADATA PIPELINE                                     │
│  (core/metadata/__init__.py + keysight.py + keithley.py)                    │
│                                                                              │
│  Two-stage system:                                                          │
│  Stage 1 — PARSE: Header-line extraction via parser functions               │
│    parse_set_voltage, parse_compliance, parse_sweep_range,                  │
│    parse_repeat_count                                                       │
│  Stage 2 — ANALYZE: Computation on loaded DataFrame columns                 │
│    analyze_waveform_params, analyze_iv_compliance                           │
│                                                                              │
│  Invoked from _load_with_device_config() when device_cfg has                │
│  a "metadata" section defined in the instrument config.                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow: Raw File Through the System

```
STEP 1: RAW FILE
  filename: "140526_Ta-PDA-ITO_r0c0_iv-sweep_01.csv"

STEP 2: GRAMMAR MATCHING (technique.py + config.py grammar)
  → get_merged_grammar() with 5-tier resolution (hardcoded → device-type →
    global config → project → protocol)
  → Regex pattern match → extract fields:
    {date_code: "140526", material: "Ta-PDA-ITO", matrix: "r0c0",
     technique: "iv-sweep", suffix: "01"}

STEP 3: STUDY DETECTION (studies.py: detect_study_from_filename)
  → Substring match against study patterns from _STUDIES
  → "iv-sweep" matches iv:iv-bipolar-sweep (pattern list contains "iv-sweep")
  → Returns "iv:iv-bipolar-sweep"

  OR via legacy detection (technique.py: detect_technique)
  → Regex pattern match against _DEFAULT_TECHNIQUE_PATTERNS
  → Matches "iv-sweep" → technique = "iv-sweep"
  → Then _LEGACY_TO_STUDY maps "iv-sweep" → "iv:iv-bipolar-sweep"

  FALLBACK: If no study matches, _LEGACY_TO_STUDY maps old technique names
  to their corresponding study names.

STEP 4: INSTRUMENT RESOLUTION (plot.py: _resolve_device)
  → Check protocol YAML step metadata for 'instrument' field
  → Fallback: get_default_device("iv-sweep") → _DEFAULT_GLOBAL_TECHNIQUES
    → "keithley-2400"
  → Result: device = "keithley-2400"

STEP 5: DEVICE TYPE RESOLUTION (from protocol YAML devices: field)
  → Check protocol YAML for 'devices:' field → e.g., "memristor"
  → This determines analysis_mode (volatile/bipolar) and library routing
  → get_studies_for_device_type("volatile-memristor") → studies available
  → NOT directly used in data loading; used in analysis routing

STEP 6: DATA LOADING (data_loader.py: load_data_file)
  → study_name="iv:iv-bipolar-sweep", technique="iv-sweep", device="keithley-2400"
  → _resolve_device_config(technique, device, study_name)
    → get_study_config("iv:iv-bipolar-sweep") → returns study config
    → finds instruments.keithley-2400 with:
      delimiter="\t", header_lines=23, columns={voltage, current, time}
      metadata={compliance: {parser: compliance}, sweep_range: {parser: sweep_range}}
    → Merges with _DEFAULT_DEVICE defaults
  → _load_with_device_config(path, device_cfg, ...)
    → pd.read_csv with device config parameters
    → Column remapping: "Untitled" → "voltage", "Untitled 1" → "current"
    → Metadata pipeline:
      → parse compliance from raw header lines
      → parse sweep_range from raw header lines
    → Returns (DataFrame with columns [voltage, current, time], info_dict)

STEP 7: PLOTTING/ANALYSIS
  PLOT PATH:
    → Study plotter resolved via resolve_study_plotter("iv:iv-bipolar-sweep")
    → _plot_iv_bipolar(filepath, flags) [dedicated plotter]
    → x=voltage, y=current, applies sweep-specific formatting

  ANALYZE PATH:
    → technique="iv-sweep" → _analyze_iv(filepath, flags)
    → Vset/Vreset extraction, ON/OFF ratio, compliance detection
    → Output: YAML to results/iv-sweep_analysis.yaml
```

---

## 3. Current Architecture Review

### 3.1 Well-Defined Relationships

| Relationship | How it works | Where |
|---|---|---|
| **Device Type → Studies** | `_DEVICE_TYPES[name].studies[]` lists study names; `get_studies_for_device_type()` accessor | `config_defaults.py:267-299`, `studies.py:163-175` |
| **Study → Technique** | `parse_study_name()` extracts technique prefix from `technique:study-name` | `studies.py:30-42` |
| **Study → Instruments** | `_STUDIES[technique][study].instruments{}` maps instrument name → per-study config; `get_instruments_for_study()` accessor | `config_defaults.py:22-261`, `studies.py:196-210` |
| **Grammar → Study** | `_STUDIES[technique][study].patterns[]` are substring patterns matched against filename; `detect_study_from_filename()` | `config_defaults.py` (patterns fields), `studies.py:48-78` |
| **Study → Plotter** | `STUDY_PLOTTERS[study_name]` maps study → `StudyPlotter(plot_fn, overlay_fn, flags)`; `resolve_study_plotter()` dispatches | `plot/registry.py:21-163` |
| **Study → Data Loading** | `load_data_file(filepath, study_name=...)` resolves technique + device config through `_resolve_device_config()` → study instruments | `data_loader.py:16-66`, `data_loader.py:69-132` |
| **Study → Metadata** | Instrument config per study has `metadata{}` with parser/analyzer references | `config_defaults.py` nested under each instrument in each study |
| **Instrument → Techniques** | `_INSTRUMENTS[name].techniques[]` lists compatible technique names | `config_defaults.py:325-362` |
| **Device Type → Analysis Mode** | `_DEVICE_TYPES[name].analysis_mode` (volatile/bipolar/linear/general) | `config_defaults.py:263-300` |
| **Device Type → Library** | `_DEVICE_TYPES[name].library` → which analysis library to use | `config_defaults.py:263-300` |

### 3.2 Gaps and Problems

#### Problem A: Dual-layer pattern detection (fragmentation)
There are **three separate** pattern+matching systems that overlap:

1. **Study patterns** (`_STUDIES[technique][study].patterns[]`) — substring matching, used by `detect_study_from_filename()`
2. **Legacy technique patterns** (`_DEFAULT_TECHNIQUE_PATTERNS` in config.py) — regex patterns, used by `detect_technique()`
3. **Legacy PATTERNS** (`technique.py:PATTERNS`) — regex patterns, deprecated duplicate of #2

These use **different formats** (substring vs regex) and **different values**. Example:
- `_STUDIES` has `"iv-bipolar-sweep": {"patterns": ["iv-sweep", "_IV", "iv-bipolar", "sweep_"]}`
- `_DEFAULT_TECHNIQUE_PATTERNS` has `"iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"]`

A filename `140526_test_iv-sweep_001.csv` might match the study pattern (`"iv-sweep"` is in filename) but NOT the technique pattern (no `_IV.` or `.iv$` match). This means study detection and technique detection can return DIFFERENT results for the same file.

#### Problem B: `_DEFAULT_GLOBAL_TECHNIQUES` is incomplete
`_DEFAULT_GLOBAL_TECHNIQUES` in config.py (lines 989-1030) has entries for: `iv-sweep`, `iv-breakdown`, `iv-leakage`, `raman`, `uv-vis`, `pulse-stp`, `pulse-ppf`. Missing:
- `ec-cv`, `ec-ca`, `ec-eis` — EC techniques only exist in `_STUDIES`, not in `_DEFAULT_GLOBAL_TECHNIQUES`
- `pulse-endurance`, `pulse-retention` etc. — were removed from `_STUDIES` but still referenced in instruments and TECHNIQUE_HINTS

But `list_global_techniques()` adds study technique prefixes, so EC studies show up anyway via `_STUDIES` keys. This means `get_global_technique_config("ec-cv")` returns `None` (no entry + no `_LEGACY_TO_STUDY` mapping) — which then fails to resolve via the fallback chain.

#### Problem C: Removed studies still clutter the codebase
The 160626_config-study-cleanup plan removed 13 studies from `_STUDIES`, but many files still reference them:

| File | Stale Reference |
|---|---|
| `config.py:_DEFAULT_TECHNIQUE_PATTERNS` | `mem-endurance`, `mem-retention`, `mem-switching`, `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd` (all still present) |
| `technique.py:PATTERNS` | Same — all removed studies still defined |
| `technique.py:BUILTIN_TECHNIQUES` | Same — all removed studies still defined |
| `routing.py:TECHNIQUE_LIBRARY_MAP` | `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd` (all still present) |
| `routing.py:DEVICE_TYPE_MODE_MAP` | `memristor`, `junction` keys — still uses old terminology |
| `cli/commands/plot.py:TECHNIQUE_HINTS` | `mem-endurance`, `mem-retention`, `mem-switching` hints still defined |
| `cli/commands/analyze.py:TECHNIQUE_ANALYZERS` | `pulse-endurance`, `pulse-retention` analyzers still registered |
| `config_defaults.py:_INSTRUMENTS` | `keithley-2400.techniques` still lists `pulse-endurance`; `keysight-b1500a.techniques` still lists `pulse-endurance` |
| `config_defaults.py:_DEFAULT_GLOBAL_DEVICES` | (no issue — doesn't store techniques) |

#### Problem D: `non-volatile-memristor` device type has no pulse studies
The `_DEVICE_TYPES` data in `config_defaults.py`:
```python
"non-volatile-memristor": {
    "studies": ["iv:iv-bipolar-sweep"],
    ...
}
```
Per user's description, non-volatile memristors should also support `pulse:pulse-endurance` and `pulse:pulse-retention`. The user explicitly stated:
> same study name (pulse:pulse-endurance) can appear in both device types but behaves differently

The current `_DEVICE_TYPES` only has `iv:iv-bipolar-sweep` for `non-volatile-memristor`. The pulse endurance/retention studies were removed in the cleanup plan, which contradicts the user's intent.

#### Problem E: Study name = same → different behavior per device type
The user's key insight: `pulse:pulse-endurance` would appear in BOTH `volatile-memristor` and `non-volatile-memristor`, but with **different behavior**. The current architecture has **no mechanism** for a study to behave differently based on device type.

- `STUDY_PLOTTERS` maps study → single `StudyPlotter`. There's no device-type dimension.
- `_init_dedicated_plotters()` installs one plotter per study, globally.
- The device type (`_DEVICE_TYPES[name].analysis_mode`) is only used in `resolve_analysis_mode()` via routing.py — it's NOT passed to the plotter or analyzer.

Currently `pulse:pulse-endurance` doesn't exist as a study at all (removed). But if re-added, plotting/analyzing a pulse endurance file from a volatile vs non-volatile device would invoke the **same** plotter/analyzer — no differentiation.

#### Problem F: `_resolve_xy_columns()` has gaps
`_resolve_xy_columns()` in plot.py lines 608-722 handles: `ec-ca`, `ec-cv`, `ec-eis`, `iv-sweep/breakdown/leakage`, `uv-vis`, `mem-endurance/retention`. Missing:
- `pulse-stp` — no column resolution → falls back to first-two-numeric, which picks `time` + `voltage` instead of `time` + `current`
- `pulse-ppf` — same issue
- `raman` — covered by dedicated plotter, but fallback path would fail

#### Problem G: Study detection and technique detection can conflict
There are two detection paths in the CLI:
1. `_detect_study(filename)` → `detect_study_from_filename()` (substring matching on study patterns)
2. `_detect_technique(filename)` → `detect_technique()` (regex matching on technique patterns)

These can return different results. In `_plot_direct()`:
```python
technique = ... # from flag or study
if not technique:  # falls back to detect_study_or_technique()
    tech, study_name = _tech_module.detect_study_or_technique(...)
```
`detect_study_or_technique()` returns both study and technique — but the downstream dispatch chain may use one or the other inconsistently. For example, `_dispatch_technique_plot()` uses study for plotter resolution but `_do_plot()` uses technique for column resolution. If study says "pulse-stp-decay" but technique says "pulse-stp", they should match — but with different pattern systems, they might not.

#### Problem H: `_DEFAULT_GLOBAL_TECHNIQUES` lacks keysight-b1500a entries for IV studies
`_DEFAULT_GLOBAL_TECHNIQUES["iv-sweep"]["default_device"]` = `"keithley-2400"`. If the actual measurement was done with `keysight-b1500a`, the fallback picks the wrong device. The protocol YAML step instrument field is supposed to override this — but if the protocol wasn't configured with `--ins`, the default is wrong for Keysight IV data. The per-study instrument config in `_STUDIES` has both instruments, so `study_name` routing helps — but only if `study_name` is passed through correctly.

#### Problem I: `_resolve_device()` doesn't use study_name
In `plot.py:69-101`, `_resolve_device(technique, filepath)` checks protocol YAML step metadata for `instrument`, falling back to `get_default_device(technique)`. It does NOT check `study_name` to find the first instrument for that study. If the protocol has no instrument set, `get_default_device("iv-sweep")` returns `keithley-2400` even though `keysight-b1500a` is the only instrument that has metadata parsers for that study.

---

## 4. Relationship Matrix

| Device Type | Studies | Instruments | Grammar Patterns | Parsers | Plotters | Analyzers |
|---|---|---|---|---|---|---|
| **volatile-memristor** | iv:iv-bipolar-sweep, pulse:pulse-stp-decay, pulse:pulse-ppf | keithley-2400, keysight-b1500a | rNcN crossbar (`r\d+c\d+`) + study patterns | compliance, sweep_range, set_voltage, repeat_count, analyze_iv_compliance, analyze_waveform_params | iv_bipolar (gradient), stp_decay (1x2_panels), ppf (1x2_panels) | iv-sweep (Vset only, volatile mode), pulse-stp (biexponential fit), pulse-ppf (ratio vs interval) |
| **non-volatile-memristor** | iv:iv-bipolar-sweep [gap: no pulse-endurance, pulse-retention] | keithley-2400, keysight-b1500a | rNcN crossbar | compliance, sweep_range, set_voltage, repeat_count, analyze_iv_compliance | iv_bipolar (gradient) | iv-sweep (Vset+Vreset, bipolar mode) |
| **electrochem** | ec:ec-cv, ec:ec-ca, ec:ec-eis | autolab-usth | .mpt, _CV, _CA, _EIS, .cv, .ca, .eis, .z | (none currently) | cv, ca, eis (nyquist_bode) | ec-cv (peaks, charge), ec-ca (Cottrell fit), ec-eis (Nyquist, circuit fit) |
| **deposition** | (none) | (none) | Basic naming | (none) | fallback | pvd (layer analysis) |
| **general** | (none) | (none) | All patterns | (none) | fallback | fallback |

---

## 5. Problem Spots

### 5.1 Pulse endurance/retention re-addition (high priority)
The user's intent is clear: `pulse:pulse-endurance` and `pulse:pulse-retention` should exist as studies and appear on BOTH `volatile-memristor` and `non-volatile-memristor` device types. However, the 160626_config-study-cleanup plan REMOVED them. This creates a contradiction:
- If re-added: the `non-volatile-memristor` device type would have `pulse:pulse-endurance` and `pulse:pulse-retention`
- But currently `pulse-endurance` and `pulse-retention` analyzer functions still exist in `analyze.py`
- The `plot/` directory still has `pulse_endurance.py` and `pulse_retention.py` plot modules
- They were just removed from `_STUDIES` and `_STUDY_ORDER`/`plot --help`

### 5.2 Same study, different behavior per device type (design gap)
If `pulse:pulse-endurance` is shared by both `volatile-memristor` and `non-volatile-memristor`:
- A volatile memristor endurance test might analyze cycles-to-failure differently (gradual decay vs abrupt)
- A non-volatile memristor endurance test might track R_high/R_low differently
- The current `STUDY_PLOTTERS` registry maps one study → one plotter → no device-type dimension
- **No mechanism exists** to differentiate behavior per device type for the same study

Possible solutions (in order of preference):
1. **Device-type-aware plotters**: Expand `StudyPlotter` to accept optional `device_type` and maintain a `(study, device_type) → plotter` mapping
2. **Study parameterization**: Study plotter receives `analysis_mode` (from device type) and branches internally
3. **Separate studies**: Create `pulse:pulse-endurance-volatile` and `pulse:pulse-endurance-nv` — but this violates user intent

### 5.3 `_DEFAULT_GLOBAL_TECHNIQUES` doesn't match `_STUDIES`
Config.py's `_DEFAULT_GLOBAL_TECHNIQUES` only has 7 entries. `_STUDIES` has 15+ entries across 7 technique groups. The accessor `get_global_technique_config()` falls back to study data when it can, but `get_default_device()` only checks `_DEFAULT_GLOBAL_TECHNIQUES` and the config's `defaults:` section — NOT the study instruments for ec/afm techniques.

### 5.4 Three overlapping pattern systems
As described in Problem A, three different pattern matching systems coexist. This is a migration artifact (old technique patterns → new study patterns → config grammar). All three must be kept synchronized, which is error-prone. Every time you add a study pattern, you must update:
1. `_STUDIES[technique][study].patterns[]` (substring)
2. `_DEFAULT_TECHNIQUE_PATTERNS[technique]` (regex)
3. `technique.py:PATTERNS` (regex, deprecated)

### 5.5 Plot column resolution is technique-based, not study-based
`_resolve_xy_columns()` maps by technique name (`iv-sweep`, `ec-cv`, etc.). If two studies share the same technique (e.g., `pulse:pulse-stp-decay` and `pulse:pulse-ppf` both have technique "pulse" with keysight-b1500a columns), the column resolution works. But studies with different column expectations under the same technique would conflict.

### 5.6 Metadata pipeline only works for Keysight B1500A
The `metadata` sections in `_STUDIES` instrument configs are only defined for `keysight-b1500a` (iv-bipolar-sweep, stp-decay) and `keithley-2400` (iv-bipolar-sweep, with 2 parsers). No other instruments have metadata defined. The Keithely 2400 parsers (`keithley.py`) and Keysight parsers (`keysight.py`) are separate modules — but Keithely parsers may not work if the Keithely 2400 header format differs from what `parse_compliance` expects.

---

## 6. Recommendations

### 6.1 Resolve the pulse endurance/retention contradiction
Decide: should `pulse:pulse-endurance` and `pulse:pulse-retention` be re-added as studies or not?
- If **yes** (matching user intent): Re-add them to `_STUDIES` under `pulse:` technique, add instruments, update `_DEVICE_TYPES` for both volatile and non-volatile memristors, re-enable their analyzers and plotters, re-add to `_STUDY_ORDER`
- If **no** (keeping cleanup): Remove ALL stale references — `TECHNIQUE_ANALYZERS`, `TECHNIQUE_HINTS`, `TECHNIQUE_LIBRARY_MAP`, `_INSTRUMENTS.techniques[]`, `_DEFAULT_TECHNIQUE_PATTERNS`, `technique.py:PATTERNS`, `plot/pulse_endurance.py`, `plot/pulse_retention.py`

### 6.2 Add device-type dimension to StudyPlotter
```python
@dataclass
class StudyPlotter:
    plot_fn: Callable
    overlay_fn: Callable
    flags: list[dict] = field(default_factory=list)
    hints: dict | None = None
    single_layout: str = "single_axis"
    overlay_layout: str = "single_axis"
    device_type_variants: dict[str, Callable] = field(default_factory=dict)
    # e.g., {"volatile-memristor": _plot_endurance_volatile,
    #        "non-volatile-memristor": _plot_endurance_nv}
```
Then `resolve_study_plotter("pulse:pulse-endurance", device_type="volatile-memristor")` picks the right variant.

### 6.3 Consolidate pattern detection into one system
Phase out `_DEFAULT_TECHNIQUE_PATTERNS` and `technique.py:PATTERNS`. Keep `_STUDIES` as the single source of truth for all filename patterns. Make `detect_technique()` delegate to `detect_study_from_filename()` and then map back via `resolve_technique_from_study()`.

Update `detect_study_from_filename()` to support both substring and regex matching to maintain full backward compat.

### 6.4 Add `study_name` to `_resolve_device()`
Modify `_resolve_device(technique, filepath, study_name=None)` to check study instruments when protocol metadata is missing. This ensures Keysight B1500A IV sweeps get the correct instrument even without protocol configuration.

```python
def _resolve_device(technique, filepath, study_name=None):
    # 1. Check protocol YAML step instrument (as before)
    # 2. Check study instruments if study_name provided
    if not device and study_name:
        instrs = get_instruments_for_study(study_name)
        if instrs:
            device = instrs[0]  # use first instrument
    # 3. Fallback to get_default_device(technique) (as before)
```

### 6.5 Add study-based column resolution
Add `_resolve_xy_columns_for_study()` delegate that maps study → column pairs, falling back to technique-based resolution. This way `pulse:pulse-stp-decay` and `pulse:pulse-ppf` can each define their own column mappings independent of the generic `pulse-stp` technique entry.

### 6.6 Complete the `_DEFAULT_GLOBAL_TECHNIQUES` entries
Add entries for `ec-cv`, `ec-ca`, `ec-eis` with appropriate `default_device` (`autolab-usth`) and `grammar_codes`. This eliminates the inconsistency where `get_global_technique_config("ec-cv")` returns `None`.

### 6.7 Pass device_type through the full dispatch chain
Currently `device_type` is only used by `resolve_analysis_mode()` in routing.py. It should be threaded through:
- `_dispatch_technique_plot()` → passes to plotter
- `_do_plot()` → passes to `_resolve_xy_columns()` (for study-based column maps)
- `_do_overlap()` → same
- `_analyze_direct()` → passes to analyzer (for mode-aware analysis)

The device type is available from protocol YAML `devices:` field and already loaded in `_plot_interactive()` → accessible via `load_session()`.

### 6.8 Clean up stale references systematically
Create a checklist and sweep all files:

| File | Action |
|---|---|
| `config.py:_DEFAULT_TECHNIQUE_PATTERNS` | Remove entries for removed studies |
| `technique.py:PATTERNS` | Sync with _STUDIES |
| `technique.py:BUILTIN_TECHNIQUES` | Sync with _STUDIES |
| `routing.py:TECHNIQUE_LIBRARY_MAP` | Remove removed studies |
| `routing.py:DEVICE_TYPE_MODE_MAP` | Update to match _DEVICE_TYPES |
| `plot.py:TECHNIQUE_HINTS` | Remove mem-endurance/retention/switching |
| `analyze.py:TECHNIQUE_ANALYZERS` | Remove pulse-endurance/retention (or re-add consistently) |
| `config_defaults.py:_INSTRUMENTS` | Remove pulse-endurance from instrument techniques[] |
| `config_defaults.py:_DEVICE_TYPES` | Update non-volatile-memristor studies[] |
| `config.py:_DEFAULT_GLOBAL_TECHNIQUES` | Add ec-* entries, remove removed pulse-* entries |

### 6.9 Fix the `ls -m device` bug
`cli/commands/ls_cmd.py` line ~64-66 routes `ls -m device` to `_ls_instrument()` instead of showing Device Types. This needs a proper `_ls_device()` function that displays `_DEVICE_TYPES` with columns: Name, Label, Description, Analysis Mode, Library, Studies.

---

## Summary of Key Architectural Insights

1. **Studies are the central organizing concept** — they connect filename patterns → instruments → column configs → metadata parsers → plotters → analyzers
2. **Device types add a cross-cutting dimension** — same study can behave differently per device type, but the current architecture has no mechanism for this
3. **The instrument config is nested inside studies** — an instrument's loading params (columns, header_lines) can vary PER STUDY, not just per instrument
4. **Grammar is separate from studies** — grammar regex patterns extract raw fields (date_code, material, matrix, technique), while study patterns match the extracted technique field to a specific study
5. **The metadata pipeline is instrument-agnostic** — parsers/analyzers are registered by name in the instrument config; the pipeline dispatches dynamically
6. **Three pattern systems need consolidation** — the migration from old technique patterns to study patterns is incomplete, creating a maintenance burden
