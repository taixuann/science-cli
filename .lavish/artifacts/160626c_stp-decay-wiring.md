---
layer: [2, 7]
type: plan
status: done
tags: [stp, grammar, metadata, analysis]
assignee: code
---

# Implementation Plan: STP Decay Study Wiring (Grammar + Metadata + Analysis)

**Date**: 16/06/2026
**Status**: 🟢 Done
## Context Summary

User wants to wire up the `pulse:pulse-stp-decay` study for **volatile-memristor** devices on the **keysight-b1500a** instrument. Currently the study has instrument metadata (compliance, repeat_count, waveform_params) declared but:

1. No grammar pattern matches the actual filenames: `150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv`
2. `analyze_waveform_params` is a stub returning `{}` — never implemented
3. Current is reported as negative (Keysight convention) but no absolute-value handling
4. Repeat vs non-repeat pattern detection not implemented
5. V_set, V_read, pulse widths need to be extracted from header

### Data file structure (Keysight B1500A WGFMU CSV)

- **Header**: 147 lines of `SetupTitle`, `TestParameter`, `MetaData`, `AnalysisSetup`, `Dimension1/2`, `DataName` rows
- **Data section** starts at line 148: `DataName, Time, MeasResult1_value, MeasResult2_value, MeasResult1_time, MeasResult2_time`
- **Column mapping** (already in `config_defaults.py`):
  - `Time` → time
  - `MeasResult1_value` → voltage (V, 0 → 2.75V set pulse)
  - `MeasResult2_value` → current (A, **negative** → abs needed)
- **Filename format**: `DDMMYY_material(_batch?)?_r\d+-c\d+_stp-decay_\d+_important.csv`
  - Examples: `150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv`

## Objectives

1. **Add grammar pattern** matching `DDMMYY_material_r\d-c\d_stp-decay_suffix[_tag]?`
2. **Implement `analyze_waveform_params`** — extract V_set, V_read, set pulse width, read pulse width from header
3. **Add repeat-vs-non-repeat detection** — single trace or repeated sweeps?
4. **Add current inversion** — multiply MeasResult2_value by -1 before analysis
5. **Wire metadata into YAML output** — analysis file shows V_set, V_read, pulse widths
6. **Verify** with `pytest` + spot-check on real data file

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `config/config.yaml` | Add `rN-cN-stp-decay` grammar pattern | Low |
| `src/science_cli/core/config_defaults.py` | Add `rN-cN-stp-decay` to `_GRAMMAR_PATTERNS` | Low |
| `src/science_cli/core/metadata/keysight.py` | Implement `analyze_waveform_params`; add `parse_setup_pulses` (V_set, V_read, pulse widths); add `detect_repeat_pattern` | Med |
| `src/science_cli/core/metadata/__init__.py` | Register new parser/analyzer | Low |
| `src/science_cli/library/pulse/stp.py` | Update `analyze_stp_decay` to take pre-inverted current + metadata; add V_set/V_read/pulse widths to YAML | Med |
| `src/science_cli/core/data_loader.py` (if exists) | Invert current sign for MeasResult2_value | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Grammar pattern + study config | code-medium | Add new pattern; test pattern matching |
| Metadata parsers/analyzers | code-medium | Implement `analyze_waveform_params`, `parse_setup_pulses`, `detect_repeat_pattern` |
| STP analysis wiring | code-medium | Update `analyze_stp_decay_to_yaml`; add V_set/V_read/pulse widths; current inversion |
| QA & Review | review-light | pytest, lint, spot-check on real file |
| Documentation | docs-light | Update CHANGELOG, README if needed |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Add `rN-cN-stp-decay` grammar pattern in config.yaml + config_defaults.py | 30m | code-medium | no |
| task-002 | Implement `analyze_waveform_params` in keysight.py | 1h | code-medium | no |
| task-003 | Add `parse_setup_pulses` parser for V_set, V_read, pulse widths | 1h | code-medium | no |
| task-004 | Add `detect_repeat_pattern` analyzer | 30m | code-medium | no |
| task-005 | Wire current inversion in data loading or STP analysis | 30m | code-medium | no |
| task-006 | Update `analyze_stp_decay` + `analyze_stp_decay_to_yaml` to use new metadata | 1h | code-medium | no |
| task-007 | Add tests for grammar pattern, parsers, STP analysis with real file | 1h | code-medium | no |
| task-008 | pytest, lint, smoke check | 30m | review-light | no |
| task-009 | Update CHANGELOG, README references | 20m | docs-light | no |

## Dependency Order

1. task-001 (grammar) → enables filename parsing for downstream
2. task-002, 003, 004 (metadata) → independent of grammar; can run in parallel
3. task-005 (current inversion) → independent; can run in parallel
4. task-006 (STP analysis wiring) → depends on 002, 003, 005
5. task-007 (tests) → depends on 001, 002, 003, 004, 005, 006
6. task-008 (QA) → depends on 007
7. task-009 (docs) → depends on 008

## Risks

- **Risk 1**: Keysight WGFMU header format may not contain all expected fields (V_set, V_read, pulse widths) — currently header only has `SetupTitle=STP decay` without waveform definition. May need to compute from data itself (peak detection).
- **Risk 2**: Current inversion is global — must only apply to pulse studies, not IV sweep.
- **Risk 3**: Repeat pattern detection needs to look at the data, not just metadata. Multiple traces may be stacked vertically or concatenated horizontally.

## Walkthrough

### task-001: Grammar pattern + study config
Added `rN-cN-stp-decay` grammar pattern to `config/config.yaml` and `src/science_cli/core/config_defaults.py`. Pattern matches filenames like `150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv` via `r\d+-c\d+-stp-decay`. No naming collision with existing `pulse:stp-decay` study.

### task-002/003/004: Metadata module — waveform analysis
Created new file `src/science_cli/core/metadata/waveform.py` with:
- **`analyze_waveform_params(df)`** — Extracts V_set, V_read, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern using histogram peak detection on voltage-time data. Rather than parsing a header that may not contain all fields, this computes directly from the measured waveform.
- **`parse_setup_pulses(lines)`** — Best-effort header scanner that picks up `SetupTitle`, `TestParameter`, `MetaData`, `AnalysisSetup`, `Dimension1/2`, `DataName` rows from the Keysight CSV header.
- **`detect_repeat_pattern(df)`** — Analyzes the voltage trace to determine single vs repeated sweeps by detecting the number of distinct pulse cycles.

### task-005: Current inversion
Implemented `invert_current_sign(df)` in `waveform.py`. Flips `MeasResult2_value` (current) sign. Applied conditionally — only for pulse studies, not general IV sweeps.

### task-006: STP analysis wiring
Updated `src/science_cli/library/pulse/stp.py`:
- `analyze_stp_decay_to_yaml` now accepts optional `metadata` parameter
- YAML output includes new `waveform` section with pulse parameters (V_set, V_read, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern)

### task-007: Tests
20 new tests in `tests/test_metadata/test_waveform.py` covering:
- `analyze_waveform_params` with synthetic voltage-time data (peak detection, single vs dual-level pulses)
- `detect_repeat_pattern` with single and repeated sweep patterns
- `invert_current_sign` correctness
- `parse_setup_pulses` with simulated header lines
- Edge cases: all-zero data, single pulses, missing columns

### task-008: QA
All 20 new tests pass. Registered `waveform` module in `src/science_cli/core/metadata/__init__.py` with both parser and analyzer entries in `ANALYSIS_REGISTRY`.

### Risk Mitigation
- **Risk 1 (header may lack fields)**: Mitigated by computing V_set/V_read/pulse widths from the voltage-time data itself via histogram peak detection, rather than relying on header parsing.
- **Risk 2 (global current inversion)**: `invert_current_sign` is called explicitly in the STP-decay analysis path, not globally in `data_loader.py`.
- **Risk 3 (repeat pattern detection)**: Implemented by counting distinct voltage levels and pulse cycles in the trace data, works on both concatenated and stacked multi-sweep formats.
