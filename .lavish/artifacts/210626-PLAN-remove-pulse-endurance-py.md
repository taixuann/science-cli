---
layer: [5]       # Plotting & Dispatch
type: plan
status: in-progress
tags: [cleanup, pulse-endurance, module-removal, plot-refactor]
depends_on: [210626-endurance-plots]
assignee: plan
---

# Implementation Plan: Remove pulse_endurance.py — route through generic.py

**Date**: 21/06/2026
**Status**: 🟠 In Progress
**Layer**: 5 — Plotting & Dispatch

## Context Summary

After the endurance plot refactor (210626-endurance-plots), `pulse_endurance.py` is now just 3 thin wrapper functions that all call `generic._plot_generic()`:

- `plot_resistance()` → `_plot_generic(filepath, {"plot_variant": "resistance"}, study_name="pulse:pulse-endurance")`
- `plot_current()` → `_plot_generic(filepath, {"plot_variant": "current"}, study_name="pulse:pulse-endurance")`
- `plot_both()` → calls the above two

All actual styling, column mapping, labels come from `config-studies.yaml`. The module is dead weight.

## Objectives

1. Move the 3 wrapper functions into `generic.py` as public functions
2. Update `config-studies.yaml` menu handler paths
3. Delete `pulse_endurance.py`
4. Verify no stale references remain

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/plot/generic.py` | Add 3 public endurance plot functions at end | Low |
| `config/config-studies.yaml` | Update handler paths (3 lines) | Low |

## File to Delete

| File | Reason |
|------|--------|
| `src/science_cli/plot/pulse_endurance.py` | No longer needed — logic moved to generic.py wrappers |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Code changes | plan-heavy (self) | Small, fast edits — no need to delegate |
| QA & Review | review-medium | Verify menu routes, plot still works |
| Documentation | docs-medium | Update CHANGELOG, README, artifact-review |
| Lavish dashboard | docs-medium | Update layer05 dashboard |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | Add 3 public functions to generic.py | 5m | plan |
| task-002 | Update handler paths in config-studies.yaml | 2m | plan |
| task-003 | Delete pulse_endurance.py | 1m | plan |
| task-004 | Verify no stale references | 2m | plan |
| task-005 | Code review | 5m | review-medium |
| task-006 | Documentation + CHANGELOG | 10m | docs-medium |
| task-007 | Commit | 2m | plan |

## Dependency Order
1. task-001 → task-002 → task-003 (code changes)
2. task-004 (verify)
3. task-005 (review)
4. task-006 (docs)
5. task-007 (commit)

## Risks
- Low: `pulse_endurance.py` is imported nowhere except config-studies.yaml handler strings
- Must ensure `generic.py` doesn't exceed 600 lines — adding ~20 lines is fine
