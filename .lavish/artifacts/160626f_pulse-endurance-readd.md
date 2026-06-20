---
layer: [7]
type: plan
status: done
tags: [pulse, endurance, analysis]
depends_on: [160626c_device-study-relationship]
assignee: code
---

# Implementation Plan: Re-add pulse:endurance Study (Seq 2)

**Date**: 16/06/2026
**Status**: 🟢 Done
**Architecture ref**: `160626c_device-study-relationship.md` §5.1, §6.2, §6.8

## Context Summary

In Phase 1 (config-study-cleanup), `pulse:pulse-endurance` and `pulse:pulse-retention` were removed from `_STUDIES` to clean up the study registry. But the user's research workflow needs these — the artifact `160626c_device-study-relationship.md` §5.1 documents the contradiction.

User wants:
- `pulse:pulse-endurance` re-added as a study
- Support BOTH `volatile-memristor` AND `non-volatile-memristor` device types
- Different behavior per device type (per Problem E in artifact):
  - volatile: R_decay vs cycle (gradual decay)
  - non-volatile: R_high/R_low vs cycle (binary states)
- Plot styling: x-log scale, big markers, endurance-specific layout

## Objectives

1. **Re-add `pulse:pulse-endurance`** to `config-devices.yaml` under `pulse:` technique, with `keysight-b1500a` instrument config
2. **Update `_DEVICE_TYPES`** in `config-devices.yaml`:
   - `volatile-memristor.studies` includes `pulse:pulse-endurance`
   - `non-volatile-memristor.studies` includes `pulse:pulse-endurance` (NEW)
3. **Add device-type variants** to `StudyPlotter` (per artifact §6.2):
   - `_plot_endurance_volatile()` — R_decay vs cycle
   - `_plot_endurance_nv()` — R_high/R_low vs cycle
4. **New plot module** `src/science_cli/plot/pulse_endurance.py` with:
   - x-axis: cycle (log scale)
   - Big markers (markersize=10, marker='o')
   - Endurance-specific layout (overlay R_high and R_low as 2 panels)
5. **Update TECHNIQUE_HINTS** in `plot.py` (currently has no `pulse-endurance` entry)
6. **Update TECHNIQUE_ANALYZERS** in `analyze.py` (re-add `pulse-endurance` analyzer)
7. **Verify** with real data file

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `config/config-devices.yaml` | Add `pulse:pulse-endurance` to studies; update `_DEVICE_TYPES` | Low |
| `src/science_cli/plot/registry.py` | Register pulse-endurance plotters (volatile + nv variants) | Med |
| `src/science_cli/plot/pulse_endurance.py` (NEW) | New plot module with device-type variants | Low |
| `src/science_cli/cli/commands/plot.py` | Re-add `pulse-endurance` entry in TECHNIQUE_HINTS | Low |
| `src/science_cli/cli/commands/analyze.py` | Re-add `pulse-endurance` analyzer | Med |
| `src/science_cli/core/studies.py` | Verify pulse-endurance resolves correctly | Low |
| `tests/test_plot/test_pulse_endurance.py` (NEW) | Test plotter dispatch | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Re-add study + device types | code-medium | YAML edits |
| New plot module | code-medium | pulse_endurance.py |
| Plot registry + hints | code-medium | Wire up device-type variants |
| Analyzer re-add | code-medium | re-enable in analyze.py |
| QA | review-light | Test dispatch + spot-check |
| Docs | docs-light | CHANGELOG |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Add `pulse:pulse-endurance` to config-devices.yaml | 10m | code-medium | no |
| task-002 | Update `_DEVICE_TYPES` (volatile + non-volatile) | 10m | code-medium | no |
| task-003 | Write `plot/pulse_endurance.py` with device-type variants | 45m | code-medium | no |
| task-004 | Register plotters in `plot/registry.py` | 15m | code-medium | no |
| task-005 | Re-add `pulse-endurance` to TECHNIQUE_HINTS | 5m | code-medium | no |
| task-006 | Re-add `pulse-endurance` analyzer in analyze.py | 20m | code-medium | no |
| task-007 | Test dispatch with both device types | 20m | code-medium | no |
| task-008 | pytest + smoke | 15m | review-light | no |
| task-009 | CHANGELOG | 5m | docs-light | no |

## Dependency Order

1. task-001, 002 (config) — must be first
2. task-003 (plot module) — depends on config
3. task-004 (registry) — depends on plot module
4. task-005 (hints) — depends on config
5. task-006 (analyzer) — depends on config
6. task-007 (tests) — depends on all above
7. task-008 (QA) — depends on 007
8. task-009 (docs) — depends on 008

## Risks

- **Risk 1**: Real `pulse-endurance` data files don't exist in the project (only stp-decay and iv-sweep do). We may not have a real file to test against. Need to either find one or use synthetic data.
- **Risk 2**: Device-type variant dispatch — `StudyPlotter` currently has no `device_variants` field. Need to extend it carefully without breaking existing plotters.
- **Risk 3**: Re-adding `pulse:pulse-endurance` to `_DEFAULT_GLOBAL_TECHNIQUES` (config.py) is a separate concern — already partial in `_DEFAULT_TECHNIQUE_PATTERNS`.

## Walkthrough

Rewrote `src/science_cli/plot/pulse_endurance.py` (224 lines) with two device-type variants: `_plot_endurance_volatile()` plots R_decay vs cycle on a single log-log axis, and `_plot_endurance_nonvolatile()` shows a 2-panel layout with R_high and R_low. Registered `pulse:pulse-endurance` in `plot/registry.py` with `DevicePlotterVariant` dispatch. Added `pulse-endurance` to TECHNIQUE_HINTS with x-log and big markers. 13 new tests in `tests/test_plot/test_pulse_endurance.py`.
