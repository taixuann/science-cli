---
layer: [4]
type: plan
status: done
tags: [fzf, columns, study-aware]
assignee: code
---

# Implementation Plan: Per-Study fzf Columns (Global + Study-Specific)

**Date**: 19/06/2026
**Status**: 🟢 Done
**Depends on**: v3.18.0 (status tags, pulse command, auto-metadata)

## Context Summary

User wants to redesign fzf columns to be:
1. **Global fzf** — current behavior, no data preview, ADD status column
2. **Per-study fzf** — for each study type, show study-specific metadata columns

The `fzf_utils.py` already has `build_fzf_display()` with optional `metadata` dict. The pulse command group already loads metadata from `protocol.yaml` for `pulse list`. We need to extend this pattern to ALL fzf calls (results, plot, analyze, etc.) and make the metadata column selection study-aware.

### Current State
- `fzf_utils.py` has `build_fzf_display(protocol, step, filename, show_protocol=True, metadata=None)` — takes metadata as a free-form dict
- Pulse `cmd_list` already builds display with `v_set_v, v_read_v, set_width_us, read_width_us, repeat_pattern` columns
- Status tags stored in `.status.json` — already accessible via `load_status()` from `results_status.py`
- Most fzf calls (plot, analyze, results) don't pass metadata or status

## Objectives

1. **Status column everywhere** — add a status badge column (★/✓/✗/—) to all fzf displays
2. **Remove data preview from global fzf** — `preview=None` for all fzf calls (was already there for some)
3. **Per-study column registry** — define which metadata columns to show for each study type
4. **Auto-load metadata from `protocol.yaml`** — when study is known, fetch `step.metadata` and pass to `build_fzf_display`
5. **Apply to all CLI commands** — `results`, `plot`, `analyze`, `pulse list`, etc.

### Column Specifications per Study

| Study | Columns (after step, filename, status) |
|-------|----------------------------------------|
| `pulse:pulse-stp-decay` | pattern_waveform: v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern |
| `pulse:pulse-endurance` | pattern_waveform: v_set_v, v_reset_v, set_width_us, reset_width_us, read_width_us, n_cycles, repeat_pattern |
| `pulse:pulse-ppf` | pattern_waveform: v_set_v, v_read_v, set_width_us, read_width_us, interval_min_ms, interval_max_ms |
| `iv:iv-bipolar-sweep` | sweep_pattern (0→V+→V-→0, V+→V-, etc.), v_set, v_reset, compliance_a, step_v, delay_s |
| `ec:ec-cv` | v_min, v_max, scan_rate_mv_s, n_cycles |
| `ec:ec-ca` | v_step, duration_s, sample_interval_s |
| `ec:ec-eis` | freq_min_hz, freq_max_hz, amplitude_v, n_points |
| `raman:raman-spectrum` | laser_nm, nd_filter, accumulation, acq_time_s |
| `uv-vis:uv-vis-spectrum` | wavelength_min_nm, wavelength_max_nm, scan_rate_nm_min |
| (default) | technique, instrument |

### Pattern Waveform Definition

For pulse studies, the "pattern waveform" is the recurring pulse structure:
- V_set (set pulse voltage)
- V_read (read pulse voltage, often smaller)
- V_reset (for non-volatile endurance, the reset pulse voltage)
- set_width_us / read_width_us / reset_width_us (pulse widths at 50% height)
- rise_us / fall_us (transition times)
- repeat_pattern (single, repeated, etc.)

This data is already captured by `analyze_waveform_params()` in `core/metadata/waveform.py` and auto-written to `protocol.yaml` step metadata (Seq 4).

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/fzf_utils.py` | Add `STUDY_COLUMN_REGISTRY` dict; refactor `build_fzf_display` to accept `study_name` and auto-resolve columns | Med |
| `src/science_cli/core/protocol.py` | Add `get_step_columns(step_name, study_name)` helper | Low |
| `src/science_cli/cli/commands/results.py` | Use `build_fzf_display` with study-aware columns + status badge | Low |
| `src/science_cli/cli/commands/plot.py` | Use study-aware columns when fzf-selecting files | Low |
| `src/science_cli/cli/commands/analyze.py` | Same | Low |
| `src/science_cli/library/pulse/device_cli.py` | Verify `pulse list` uses the new registry | Low |
| `tests/test_core/test_fzf_columns.py` (NEW) | Test study column registry, build_fzf_display with study_name | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| fzf_utils refactor + registry | code-medium | Core change |
| Wire into all CLI commands | code-medium | Results, plot, analyze, pulse list |
| Tests | code-medium | Unit tests for registry + integration |
| QA | review-light | Smoke test each CLI command |
| Docs | docs-light | CHANGELOG entry |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Add `STUDY_COLUMN_REGISTRY` in `fzf_utils.py` | 20m | code-medium | no |
| task-002 | Refactor `build_fzf_display` to accept `study_name` and auto-resolve | 20m | code-medium | no |
| task-003 | Add `get_step_columns()` helper in `protocol.py` | 15m | code-medium | no |
| task-004 | Add status badge to all fzf displays | 15m | code-medium | no |
| task-005 | Wire into `results.py` | 20m | code-medium | no |
| task-006 | Wire into `plot.py` | 20m | code-medium | no |
| task-007 | Wire into `analyze.py` | 15m | code-medium | no |
| task-008 | Verify `pulse list` works with new registry | 10m | code-medium | no |
| task-009 | Tests | 30m | code-medium | no |
| task-010 | pytest + smoke | 15m | review-light | no |
| task-011 | CHANGELOG + AGENTS.md | 10m | docs-light | no |

## Dependency Order

1. task-001, 002 (registry + refactor) — first
2. task-003 (helper) — depends on 001
3. task-004 (status badge) — independent
4. task-005, 006, 007, 008 (CLI wiring) — depend on 002, 003, 004
5. task-009 (tests) — depends on all above
6. task-010 (QA) — depends on 009
7. task-011 (docs) — depends on 010

## Risks

- **Risk 1**: fzf column widths may need tuning per study — different studies have different column counts. Use sensible defaults (width_meta=12 or 14) for compactness.
- **Risk 2**: Backward compat — existing `build_fzf_display(protocol, step, filename)` calls without metadata must still work. Make `metadata` and `study_name` both optional.
- **Risk 3**: Status badge may not be in `protocol.yaml` — load from `.status.json` via `load_status()`.

## Walkthrough

### task-001 (registry) ✅
Created `src/science_cli/core/fzf_columns.py` (~87 lines) with `STUDY_COLUMN_REGISTRY` covering 9 studies (3 pulse + iv-bipolar + 3 EC + raman + uv-vis), `status_badge_for_file`, and `get_step_columns`.

### task-002 (build_fzf_display extension) ✅
`build_fzf_display()` extended with optional `study_name`, `status_badge`, `status` kwargs. When `study_name` matches registry, only registered columns are shown at compact `width_meta=12`. 100% backward compatible — all existing call sites work unchanged.

### task-003 (get_step_columns helper) ✅
Lives in `fzf_columns.py` (not `protocol.py`) to avoid circular imports. Reads `step.metadata` from `protocol.yaml`, filters to registry columns when study provided.

### task-004 (status badge everywhere) ✅
`status_badge_for_file()` returns `★` (highlight/star), `✓` (keep), `✗` (discard), or empty. Wired into all fzf displays (results, plot, analyze, pulse list).

### task-005 (results.py wiring) ✅
All 3 handlers (`results_handler`, `_results_status`, `_results_move`) use `build_fzf_display(..., study_name=..., status_badge=...)`. Added `_build_file_step_map()` helper to extract study names from protocol YAMLs.

### task-006 (plot.py wiring) ✅
`_plot_interactive()` loads study-specific metadata via `get_step_columns()` and passes `study_name` + `status_badge` to `build_fzf_display()`.

### task-007 (analyze.py default path) ✅
The fallback path in `analyze_handler()` (when no technique/study flag) was using plain `item_names` — now uses the same study-aware display pattern as `_analyze_with_technique()`. Also extended `_analyze_with_technique()` to load `get_step_columns()` + `status_badge_for_file()`.

### task-008 (pulse list study-aware) ✅
`cmd_list` in `device_cli.py` reads column keys from `STUDY_COLUMN_REGISTRY` based on `--study-filter` or the most-common study across the project's pulse steps, with a generic pulse fallback.

### task-009 (tests) ✅
Created `tests/test_core/test_fzf_columns.py` (21 tests). **All 21 pass.**

### task-010 (verification) ✅
- New tests: 21/21 pass
- Full suite: 547 passed, 4 failed (all pre-existing baseline: `test_generate_devices_yaml_is_valid`, `test_migration_script`, `test_with_device_type`, `test_electrochem`)
- Pre-fix: 3 status tests in `test_status.py` were broken because their mocked fzf output used the old `show_protocol=True` format. Fixed (option A) by updating the mocks to use `build_fzf_display(..., show_protocol=False, status_badge=...)` to match the production-side display.
- Lint: my changes clean (fixed 1 unused `pytest` import in `test_fzf_columns.py`); 3 pre-existing F401s left untouched.

### task-011 (docs) ✅
This file. CHANGELOG `[3.19.0] - 2026-06-19`, `AGENTS.md` "Per-Study fzf Columns" section, `tools/AGENTS.md` row note updated.
