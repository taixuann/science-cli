---
layer: [1, 5]
type: plan
status: planning
tags: [config, waveform, plot]
depends_on: [190626d_devices-studies-design-discussion]
assignee: plan
---

# Implementation Plan: Config Split + Waveform-as-Derived-Intermediate

**Date**: 19/06/2026
**Status**: 🟡 Planning
**Discussion Doc**: [[190626d_devices-studies-design-discussion]] (v6, design decisions)
---

## Context Summary

This plan implements the design from `190626d_devices-studies-design-discussion.md` v6. The user's mental model and all decisions (9 confirmed, 0 pending) are captured in that doc. This plan focuses on the **HOW** — file-by-file changes, phased execution, and agent delegation.

**Key design principles (v6, all confirmed):**
- **Hybrid layout**: Machine-level parsing lives in `instruments.<inst>.parsing`. Per-(study, inst) extractors live in `studies.<study>.metadata_extractors.<inst>`.
- **Waveform-as-derived-intermediate**: The analyzer produces a 2D `[time, voltage]` array as its primary output; scalars (v_set_v, set_width_us, etc.) are deterministically derived from the array. Both written to `protocol.yaml` under the file/step entry.
- **Base + variant analyzer dispatch**: Mirror `STUDY_PLOTTERS` device_variants pattern for the analyze side.
- **Per-instrument grammar**: `config-grammar.yaml` folded into `config-instruments.yaml:instruments.<inst>.filename_patterns`.
- **New `config-studies.yaml`**: Studies block moves out of `config-devices.yaml` into its own file, with canonical `derived_metadata` schema + per-device overrides + per-(study, inst) extractors.
- **Plot and fzf are NOT touched** in this plan.

---

## Objectives

1. **Split the config** — clean 5-file system (config.yaml, config-devices.yaml, config-instruments.yaml, config-studies.yaml, config-template.yaml)
2. **Decouple parsing config** — `delimiter`/`header_lines`/`columns` deduplicated (written once in `instruments.<inst>`, shared by all studies)
3. **Create `config-studies.yaml`** — studies own the metadata schema, device overrides, and per-(study, inst) extractors
4. **Fold grammar into instruments** — `config-grammar.yaml` deleted, patterns move to `instruments.<inst>.filename_patterns`
5. **Add `STUDY_ANALYZERS` registry** — base + variant analyzer dispatch (mirror plot)
6. **Refactor waveform analyzer** — split `analyze_waveform_params` into extraction + derivation; store array in `protocol.yaml`
7. **Cleanup** — remove dead code (`config-devices.yaml:techniques:` partial dead, `instruments.<inst>.techniques` derivable, `get_studies_for_instrument` dead)
8. **No regressions** — all 547 existing tests pass, 4 pre-existing baseline fails remain

---

## Current vs Target Architecture

### Current (v3.19.0)

```
config/
├── config.yaml                    # ~11 lines: projects_root, theme
├── config-devices.yaml            # ~454 lines: studies + device_types + legacy_to_study + techniques
│   └── studies.<tech>.<study>.instruments.<inst> contains:
│       - delimiter, columns, header_lines    ← DUPLICATED with config-instruments.yaml
│       - metadata: per-(study,inst) extractors
│   └── techniques: block          ← PARTIALLY DEAD (5+ legacy consumers)
├── config-instruments.yaml        # ~110 lines: instruments identity + techniques + config
│   └── instruments.<inst>.config: delimeter+columns  ← DUPLICATE source
│   └── instruments.<inst>.techniques               ← DERIVABLE, not source of truth
│   └── devices: <inst> block     ← DUPLICATE of instruments.<inst>.config
├── config-grammar.yaml            # ~34 lines: file_naming.patterns
└── config-template.yaml           # ~102 lines: templates

src/science_cli/core/metadata/waveform.py  # analyze_waveform_params produces scalars only
src/science_cli/plot/registry.py           # STUDY_PLOTTERS with device_variants
src/science_cli/cli/commands/analyze.py    # TECHNIQUE_ANALYZERS flat dict (no device dispatch)
```

### Target (after all phases)

```
config/
├── config.yaml                    # ~11 lines — routing + theme only (unchanged)
├── config-devices.yaml            # ~80 lines — device_types + legacy_to_study ONLY
├── config-instruments.yaml        # ~200 lines — instruments identity + machine-level parsing + filename_patterns
├── config-studies.yaml (NEW)      # ~400 lines — studies: data_shape + derived_metadata + device_overrides + metadata_extractors
└── config-template.yaml           # ~102 lines — unchanged
# config-grammar.yaml – DELETED (folded into instruments.<inst>.filename_patterns)
# config-devices.yaml:techniques – REMOVED (dead/derivable)
# config-instruments.yaml:devices – REMOVED (duplicate)
# config-instruments.yaml:techniques – REMOVED (derivable from studies)

src/science_cli/core/study_analyzers.py      # NEW: STUDY_ANALYZERS registry
src/science_cli/core/metadata/waveform.py     # REFACTORED: extract + derive split
src/science_cli/core/analysis_output.py       # UPDATED: writes array to protocol.yaml
```

---

## Phase 0: Pre-flight

**Assigned to:** plan-heavy (this session)

**Check:** We are on `dev` branch, last commit `bb52145` (v3.19.0). 547 tests passing, 4 pre-existing fails.

```bash
pytest tests/ -q
```

**Output expected:** 547 passed, 4 failed (baseline)

---

## Phase 1: Decouple parsing config (deduplicate delimiter/columns)

**Goal:** `delimiter`, `header_lines`, `columns` written ONCE in `instruments.<inst>.parsing`, referenced by studies instead of duplicated.

**Current state:** These are duplicated. `config-devices.yaml:studies.iv.iv-bipolar-sweep.instruments.keysight-b1500a` has `{delimiter: ',', header_lines: 245, columns: {voltage: V1, current: I2}}`. `config-instruments.yaml:instruments.keysight-b1500a.config` has `{delimiter: ',', header_lines: 246, decimal: '.', encoding: utf-8}`. The values slightly differ (245 vs 246 header_lines — the 245 in the study is correct for IV, 246 might be a bug).

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `config/config-instruments.yaml` | Add `parsing:` block under each `instruments.<inst>` with the canonical delimiter, header_lines, columns, decimal, encoding | Low |
| `config/config-devices.yaml` | Remove `delimiter`, `header_lines`, `columns` from `studies.*.*.instruments.<inst>` (keep `metadata:` extractors — they stay) | Medium — must ensure data_loader.py uses the new path |
| `config/config-instruments.yaml` | Remove duplicate `config:` (rename to `parsing:`) and `devices:` blocks | Low |
| `src/science_cli/core/config.py` | Update `load_global_config()` to expose `instruments.<inst>.parsing` as the canonical parsing source | Low |
| `src/science_cli/core/data_loader.py` | Update `_resolve_device_config()` to read from `instruments.<inst>.parsing` instead of `studies.<study>.instruments.<inst>` | Medium — the study-level instruments dict still contains metadata; only delimiter/columns are moved |
| `src/science_cli/core/studies.py` | Update any study→instrument resolution to prefer the canonical parsing source | Low |

**Key constraint:** The `metadata:` block inside `studies.<study>.instruments.<inst>` must remain unchanged. Only `delimiter`, `header_lines`, `columns`, `decimal`, `encoding` move.

**Test impact:** Check `tests/core/test_data_loader.py` — update test fixtures if they hardcode the old path. All existing tests should pass if the new path resolves to the same values.

**Effort:** 1 session

**Checkpoint:** `pytest tests/core/test_data_loader.py tests/core/test_config.py -q` passes.

---

## Phase 2: Create `config-studies.yaml` (migrate studies block)

**Goal:** New file `config-studies.yaml` owns the `studies:` block. `config-devices.yaml` loses `studies:`.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `config/config-studies.yaml` (NEW) | Move `studies:` block from `config-devices.yaml`. Add `data_shape:` declarations per study. Rename `metadata_schema:` to `derived_metadata:` where applicable. Keep `instruments.<inst>` sub-blocks with `parsing:` refed from Phase 1. | Medium — large block move, careful with YAML structure |
| `config/config-devices.yaml` | Delete `studies:` block entirely. Keep `device_types:`, `legacy_to_study:`, `techniques:`. | Low |
| `src/science_cli/core/config_defaults.py` | Update `_STUDIES` fallback to match new location. | Low |
| `src/science_cli/core/config.py` | Add `config-studies.yaml` to the 6-layer resolution as layer 2.5 (between config-devices and config-instruments). | Low |
| `src/science_cli/core/studies.py` | Update import paths — `load_study_config()` should read from `config-studies.yaml`, not from `studies:` inside `config-devices.yaml`. | Medium — check all callers |
| `src/science_cli/core/device_resolver.py` | Update device→study resolution to use the new study loader. | Low |

**Per-study entry shape (proposed, with v6 additions):**

```yaml
# config-studies.yaml
studies:
  pulse:
    pulse-stp-decay:
      label: "STP Decay — set pulse + current decay read"
      python_module: pulse.stp
      data_shape:
        kind: waveform_2d
        columns: [time_s, voltage_v]
        units: [s, V]
      derived_metadata:              # scalars computed FROM the 2D array
        - v_set_v
        - v_read_v
        - set_width_us
        - read_width_us
        - rise_us
        - fall_us
        - repeat_pattern
      device_overrides:
        volatile-memristor:
          add: [decay_tau_ms, r_read_ohm]
        non-volatile-memristor:
          add: [r_high_ohm, r_low_ohm]
      instruments:
        keysight-b1500a:
          # delimiter/columns moved to instruments.<inst>.parsing (Phase 1)
          # Only metadata extractors remain
          metadata:
            compliance:
              method: parse
              parser: compliance
            repeat_count:
              method: parse
              parser: repeat_count
            waveform:                # NEW: produces the 2D array
              method: analyze
              function: extract_waveform_from_data
              inputs: [time, voltage]
              outputs: [waveform]
            derived:                 # NEW: scalars derived from array
              method: derive
              function: derive_waveform_metadata
              inputs: [waveform]
              outputs: [v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern]
    pulse-endurance: ...
    pulse-ppf: ...
    pulse-retention: ...
  iv: ...
  ec: ...
  raman:
    raman-spectrum:
      data_shape: {kind: spectrum_2d, columns: [wavelength_nm, intensity]}
      derived_metadata: [peak_wavelength_nm, peak_intensity, fwhm_nm, snr]
  uv-vis: ...
```

**Test impact:** Update test fixtures and config mock paths. Check `tests/core/test_studies.py`, `tests/core/test_config.py`, `tests/core/test_device_resolver.py`.

**Effort:** 1 session

**Checkpoint:** `pytest tests/core/ -q` passes.

---

## Phase 3: Per-instrument grammar (fold `config-grammar.yaml`)

**Goal:** Grammar patterns move to `instruments.<inst>.filename_patterns`. `config-grammar.yaml` deleted.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `config/config-instruments.yaml` | Add `filename_patterns:` under each `instruments.<inst>` with the grammar regex(es) for that instrument. | Low |
| `config/config-grammar.yaml` | Delete. | Low |
| `src/science_cli/core/config_defaults.py` | Update `_GRAMMAR_PATTERNS` fallback to read from instruments. | Low |
| `src/science_cli/core/config.py` | Remove `config-grammar.yaml` from the resolution order. Update `load_grammar()` to read from instruments instead. | Low |
| `src/science_cli/core/technique.py` | Update `detect_study_from_filename()` to iterate instruments' `filename_patterns` instead of global grammar patterns. | Medium — detection logic lives here |

**Grammar per-instrument (concrete):**

```yaml
instruments:
  keysight-b1500a:
    parsing: {delimiter: ',', header_lines: 246, columns: {voltage: V1, current: I2}, decimal: '.', encoding: utf-8}
    filename_patterns:
      - id: rN-cN-stp-decay
        template: '{date_code}_{material}_r{row}-c{col}_stp-decay_{suffix}{tag?}.{ext}'
        regex: '^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)_(?P<matrix>r\d+-c\d+)_(?P<technique>stp-decay)_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$'
      - id: rN-cN-endurance
        ...
  horiba-usth:
    parsing: {delimiter: '\t', decimal: ',', header_lines: 45, encoding: latin1}
    filename_patterns:
      - id: raman-spectrum
        regex: '^(?P<date_code>\d{6})_(?P<material>.+)_raman-spectrum_?(?P<suffix>\d+)?\.(?P<ext>\w+)$'
  ...
```

**Test impact:** `tests/core/test_technique.py` — update detection tests. `tests/core/test_config.py` — update grammar loading tests.

**Effort:** 0.5 sessions

**Checkpoint:** `pytest tests/core/test_technique.py tests/core/test_config.py -q` passes.

---

## Phase 4: Remove `config-devices.yaml:techniques:` and `config-instruments.yaml:devices:` blocks

**Goal:** Cleanup after Phase 1-3. Dead/duplicate blocks removed.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `config/config-devices.yaml` | Remove `techniques:` block entirely. The 5+ legacy consumers in `core/config.py` should already be migrated by this point. | Medium — must verify all consumers migrated |
| `config/config-instruments.yaml` | Remove `devices:` block (duplicate of `instruments.<inst>.parsing`, now in the canonical location). | Low |
| `config/config-instruments.yaml` | Remove `instruments.<inst>.techniques:` field (derivable from `studies` — which instruments support which study is owned by the study, not the instrument). | Low |
| `src/science_cli/core/config.py` | Remove dead code that reads `techniques:` / `devices:` blocks. | Low |

**Cleanup check:** `grep -r "techniques" config/ src/` should only find the word "techniques" in comments or in `config-studies.yaml` (as part of study naming conventions like `ec-cv`), not as YAML keys. Similarly for `devices:` in `config-instruments.yaml`.

**Test impact:** Update test config fixtures that reference these blocks.

**Effort:** 0.5 sessions

---

## Phase 5: `STUDY_ANALYZERS` registry (base + variant dispatch)

**Goal:** Mirror `STUDY_PLOTTERS` device_variants pattern for the analyze side. Replace flat `TECHNIQUE_ANALYZERS` dict.

**Current state:** `cli/commands/analyze.py` has `TECHNIQUE_ANALYZERS: dict[str, str]` — a flat `technique → function-name` mapping. `device_type` is passed as a parameter but silently ignored by most analyzers. No per-device variant support.

**Target:** `StudyAnalyzer` dataclass + `STUDY_ANALYZERS` registry + `resolve_study_analyzer(study_name, device_type)` that returns a merged analyzer with device variant applied.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/study_analyzers.py` (NEW) | `StudyAnalyzer` dataclass (`analyze_fn`, `extract_metadata_fn`, `flags`, `hints`), `DeviceAnalyzerVariant` dataclass (override fields), `STUDY_ANALYZERS` registry dict, `resolve_study_analyzer()` function | Low — new file, no breaking changes |
| `src/science_cli/cli/commands/analyze.py` | Replace `TECHNIQUE_ANALYZERS` lookups with `resolve_study_analyzer()` calls. Add device variant dispatch. Keep backward compat (if no variant exists, use base). | Medium — dispatch logic change |
| `src/science_cli/library/pulse/stp.py` | Add `analyze_stp_decay` as base + `analyze_stp_decay_volatile` as variant (if needed) | Low — existing pattern |
| `src/science_cli/library/pulse/endurance.py` | Same as stp (volatile vs non-volatile variants already exist conceptually) | Low |
| `src/science_cli/library/pulse/ppf.py` | Same as above | Low |
| `src/science_cli/library/iv/analyze.py` | Same pattern for IV studies if needed | Low |
| `src/science_cli/core/config_defaults.py` | Remove `TECHNIQUE_ANALYZERS` fallback | Low |

**StudyAnalyzer dataclass shape:**

```python
@dataclass
class StudyAnalyzer:
    analyze_fn: str                           # function name in library/<technique>/
    extract_metadata_fn: str | None = None    # optional: produces the metadata dict
    flags: list[str] | None = None            # CLI flags this analyzer accepts
    hints: dict[str, Any] | None = None       # UX hints

@dataclass
class DeviceAnalyzerVariant:
    analyze_fn: str | None = None         # override
    extract_metadata_fn: str | None = None
    flags: list[str] | None = None
    hints: dict[str, Any] | None = None

STUDY_ANALYZERS: dict[str, StudyAnalyzer] = {
    "pulse:pulse-stp-decay": StudyAnalyzer(
        analyze_fn="analyze_stp_decay",
        extract_metadata_fn="extract_waveform_from_data",
        flags=["--device-type", "--model"],
        hints={},
        device_variants={
            "volatile-memristor": DeviceAnalyzerVariant(
                analyze_fn="analyze_stp_decay_volatile",
            ),
            # non-volatile-memristor: uses base (single-pulse, no decay)
        },
    ),
    ...
}

def resolve_study_analyzer(study_name: str, device_type: str | None = None) -> StudyAnalyzer:
    """Return a merged StudyAnalyzer with device variant applied if present."""
    ...
```

**Test impact:** Add `tests/core/test_study_analyzers.py` with tests for:
- Base resolution (no device_type)
- Device variant resolution
- Override merging
- Fallback to base when no variant exists
- All existing analyzers still work via wrap in the new API

**Effort:** 1.5 sessions

**Checkpoint:** `pytest tests/core/test_study_analyzers.py tests/cli/commands/test_analyze.py -q` passes.

---

## Phase 5b: Waveform-as-derived-intermediate refactor

**Goal:** The analyzer produces a 2D `[time, voltage]` array as its primary output. Scalars are derived from the array. Both are written to `protocol.yaml` under the file/step entry.

**Current state:** `analyze_waveform_params` in `core/metadata/waveform.py` produces scalars from raw data. The 2D array is NOT produced. Scalars and array are disconnected.

**Target:** Two functions:
- `extract_waveform_from_data(data)` → 2D `[[time, voltage], ...]` array
- `derive_waveform_metadata(waveform)` → `{v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern}`

Both functions are pure (data→array, array→scalars). Easy to test.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/metadata/waveform.py` | Refactor `analyze_waveform_params` into `extract_waveform_from_data` + `derive_waveform_metadata`. Keep backward compat shim (`analyze_waveform_params` calls both internally and returns dict). | Medium — the existing function's callers must not break |
| `src/science_cli/core/analysis_output.py` | Update `merge_analysis_to_metadata` to accept a `waveform:` key (the 2D array) alongside the scalars. Write both to the output dict. | Low |
| `src/science_cli/core/protocol.py` | Update `update_step_metadata` to store the waveform array under the file entry. (Schema: `waveform: [[time, voltage], ...]`) | Low — pending the deferred protocol.yaml layout discussion |
| `src/science_cli/library/pulse/stp.py` | Update call to `analyze_waveform_params` → use `extract_waveform_from_data` + `derive_waveform_metadata`. Store array in analysis results dict. | Low |
| `src/science_cli/library/pulse/ppf.py` | Same as stp. | Low |
| `src/science_cli/library/pulse/endurance.py` | Same, but with endurance-specific extraction method. | Low |
| `config/config-studies.yaml` | Add `waveform:` and `derived:` metadata extractors under `pulse:*.*.instruments.<inst>.metadata` | Low |
| `tests/core/metadata/test_waveform.py` (NEW or append) | Tests for: `extract_waveform_from_data` with known test data, `derive_waveform_metadata` with known array, round-trip (extract → derive → compare vs expected), edge cases (single pulse, repeated, no voltage column) | Medium — need test data files |

**`extract_waveform_from_data` — design sketch:**

```python
def extract_waveform_from_data(df, voltage_col=None, time_col=None) -> list[list[float]]:
    """Analyze time/voltage data → produce canonical 2D waveform array.
    
    Detects the pulse pattern in time-series data:
    - Sort by time
    - Detect voltage levels (histogram peaks)
    - Find transitions between levels (rising/falling edges)
    - Reduce to canonical representation: [[time, voltage], ...]
    
    Returns list of [time_s, voltage_v] pairs representing the pulse shape.
    """
    ...
```

**`derive_waveform_metadata` — design sketch:**

```python
def derive_waveform_metadata(waveform: list[list[float]]) -> dict:
    """Given the 2D waveform array, compute scalar metadata.
    
    This is DETERMINISTIC — same array → same scalars.
    - v_set_v = max voltage
    - v_read_v = second-highest or predefined read level
    - set_width_us = duration of highest level
    - read_width_us = duration of read level
    - rise_us = time from 10% to 90% of rising edge
    - fall_us = time from 90% to 10% of falling edge
    - repeat_pattern = single or repeated
    """
    ...
```

**Test data:** Use existing test CSV files. The array is produced from the same data that `analyze_waveform_params` already parses. No new raw data needed.

**Backward compat:** `analyze_waveform_params(df)` can be a thin wrapper:

```python
def analyze_waveform_params(df, ...):  # backward compat shim
    waveform = extract_waveform_from_data(df)
    derived = derive_waveform_metadata(waveform)
    # old callers get the dict they expect
    return {**derived, "waveform": waveform}  # dict as before, plus array
```

**Effort:** 2 sessions

**Checkpoint:** `pytest tests/core/metadata/test_waveform.py tests/core/test_analysis_output.py tests/core/test_protocol.py -q` passes. Verify with `sci info --json` in a pulse test project that the array appears in `protocol.yaml`.

---

## Phase 6: Remove dead code

**Goal:** Clean up known dead code identified in the discussion doc (code audit findings).

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/studies.py` | Remove `get_studies_for_instrument` (no callers). Remove `get_instruments_for_study` wrapper (inline if the 2 callers need the logic). | Low — grep for callers first |
| `src/science_cli/core/config.py` | Remove legacy helpers that read `config-devices.yaml:techniques:` block (after Phase 4). | Low |
| `config/config-devices.yaml` | Remove `techniques:` block (Phase 4 was the setup). | Low |

**Effort:** 0.5 sessions

---

## Phase 7: Documentation

**Goal:** CHANGELOG, README, AGENTS.md, and the sci-config-guide skill all updated to reflect the new config architecture.

**Changes:**

| File | Change | Risk |
|------|--------|------|
| `CHANGELOG.md` | Add entries for each phase: config split, grammar migration, STUDY_ANALYZERS, waveform refactor | Low |
| `README.md` | Update project structure description to reflect new config files | Low |
| `AGENTS.md` | Update skill inventory if config-related skills changed name/scope | Low |
| `~/.config/opencode/skills/sci-config-guide/SKILL.md` | Update to reflect the new 5-file layout (config-studies.yaml, no config-grammar.yaml, no techniques/devices blocks) | Low |
| `documentation/reference/config-system.md` | Update the 6-layer resolution diagram | Low |
| `documentation/schemas/config-yaml.md` | Add schema docs for `config-studies.yaml` | Low |

**Effort:** 1 session

---

## Phase 8: Integration tests + verification

**Goal:** End-to-end tests that the full pipeline works end-to-end.

**Tests:**

| Test | What it covers | Effort |
|------|----------------|--------|
| `tests/e2e/test_config_resolution.py` (NEW) | Trace a filename through grammar → study → device → instrument → parsing → extraction → protocol.yaml | 0.5 session |
| `tests/e2e/test_waveform_roundtrip.py` (NEW) | Load test CSV → extract waveform → derive scalars → write/read from protocol.yaml → verify array + scalars match | 0.5 session |
| `tests/e2e/test_analyzer_dispatch.py` (NEW) | Verify that (study, device) routes to correct analyzer with device variant applied | 0.5 session |
| Smoke test with `sci info --json` and `sci plot` in a test project | Confirm CLI still works | 0.5 session |

**Effort:** 1 session

---

## Agent Delegation (per phase)

| Phase | Agent | Notes |
|-------|-------|-------|
| Phase 1 | **code-medium** | Decouple parsing config — data_loader.py + config.py changes. Review: review-light. |
| Phase 2 | **code-medium** | Create config-studies.yaml, migrate studies block. Review: review-light. |
| Phase 3 | **code-medium** | Fold grammar into instruments. Review: review-light. |
| Phase 4 | **code-light** | Remove dead blocks. Review: review-light. |
| Phase 5 | **code-heavy** | STUDY_ANALYZERS registry — new file + dispatch logic. Review: review-light. |
| Phase 5b | **code-heavy** | Waveform refactor — extraction + derivation split. Review: review-medium (testing critical). |
| Phase 6 | **code-light** | Remove dead code. Review: review-light (check no regressions). |
| Phase 7 | **docs-medium** | CHANGELOG, README, AGENTS.md, sci-config-guide skill. |
| Phase 8 | **code-light** | Integration tests. |

**Ordering:** Phase 1 → 2 → 3 → 4 → 5 → 5b → 6 → 7 → 8. Phases 5 and 5b are independent of each other (but 5b depends on 1-3 for the clean config).

---

## Dependency Graph

```
Phase 1 (decouple parsing)
    │
    ▼
Phase 2 (config-studies.yaml)
    │
    ├──► Phase 3 (per-instrument grammar)
    │       │
    │       ▼
    │    Phase 4 (remove dead blocks)
    │
    ├──► Phase 5 (STUDY_ANALYZERS registry)
    │       │
    │       ▼
    │    Phase 5b (waveform refactor)
    │
    └──► Phase 6 (cleanup dead code) ──► Phase 7 (docs) ──► Phase 8 (e2e tests)
```

Phases 5 and 5b can conceptually be merged if the STUDY_ANALYZERS registry and the waveform refactor happen in the same session — but keeping them separate makes each phase reviewable on its own.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Config parser breaks if `studies:` block moves to new file | Low | Add validation tests in Phase 2. Keep backward compat fallback in config_defaults.py for 1 release. |
| `data_loader.py` uses old path for delimiter/columns | Medium | Phase 1 explicitly updates `_resolve_device_config()`. Test with real CSV files. |
| `technique.py` filename detection breaks with per-instrument grammar | Low | Phase 3 adds integration tests for grammar matching. |
| `analyze_waveform_params` callers in library/pulse/ break | Low | Keep a backward-compat shim in Phase 5b that wraps the new functions. Remove the shim in Phase 8. |
| protocol.yaml layout for the array needs user review | Medium | Deferred to separate discussion (user said "we will leave the protocol.yaml configuration later"). Phase 5b uses a minimal array block. |

---

## Summary of Effort

| Phase | Description | Effort | Agent |
|-------|-------------|--------|-------|
| 0 | Pre-flight check | 5 min | plan |
| 1 | Decouple parsing config | 1 session | code-medium |
| 2 | Create config-studies.yaml | 1 session | code-medium |
| 3 | Per-instrument grammar | 0.5 session | code-medium |
| 4 | Remove dead/duplicate blocks | 0.5 session | code-light |
| 5 | STUDY_ANALYZERS registry | 1.5 sessions | code-heavy |
| 5b | Waveform refactor | 2 sessions | code-heavy |
| 6 | Remove dead code | 0.5 session | code-light |
| 7 | Documentation | 1 session | docs-medium |
| 8 | Integration tests | 1 session | code-light |
| **Total** | | **~10 sessions** | |

**After each phase, I'll stop and let you review before proceeding to the next.**

---

## How I'll route

After you approve this plan:

1. **Phase 1**: I'll delegate to `code-medium` with a detailed task prompt that includes:
   - Exact file paths to modify
   - Exact YAML keys to move
   - The `_resolve_device_config()` update in `data_loader.py`
   - The config resolution update in `config.py`
   - The test update in `test_data_loader.py`
   
2. After Phase 1 code is done: **review-light** runs pytest + lint

3. After review passes: **I ask for your approval** before moving to Phase 2

4. Repeat for each phase through Phase 8.

**You approve each phase, I delegate, review confirms, we move on.** No surprises.

---

## Walkthrough

*(To be filled in during/after implementation)*
