---
layer: [2]
type: plan
status: done
tags: [metadata, protocol, analysis]
assignee: code
---

# Implementation Plan: Auto-Write Analysis Metadata (Seq 4)

**Date**: 16/06/2026
**Status**: 🟢 Done
**Depends on**: Seq 1, 2, 3

## Context Summary

After all the analysis work in Seq 1-3, the analyzers should automatically write their per-file results back to `protocol.yaml` so the data flows naturally to the case-study overlay (Seq 3).

This is the final piece: when a user runs `sci analyze` on a pulse file, the metadata (V_set, V_read, R_high, R_low, R_decay, etc.) gets persisted to protocol.yaml automatically.

## Objectives

1. **Hook analysis into protocol.yaml write**:
   - For every analyzer that produces a YAML result, add a step to also write the relevant fields to the step's `metadata` section
2. **Schema** for `step.metadata`:
   ```yaml
   - name: stp-decay-041
     study: pulse:pulse-stp-decay
     files: [...]
     metadata:
       # Waveform (from analyze_waveform_params)
       v_set_v: 2.74
       v_read_v: 0.51
       set_width_us: 93.35
       read_width_us: 37.80
       rise_us: 2.39
       fall_us: 2.31
       repeat_pattern: single
       # Decay fit (from analyze_stp_decay)
       model: biexponential
       tau1_ms: ...
       tau2_ms: ...
       initial_current_ua: ...
       steady_state_current_ua: ...
       decay_pct: ...
   ```
3. **Reuse `update_step_metadata()`** from Seq 3 task-001
4. **Apply to all analyzers**: STP, endurance, IV bipolar, PPF

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/library/pulse/stp.py` | Call `update_step_metadata()` after analysis | Low (depends on Seq 3) |
| `src/science_cli/library/pulse/endurance.py` | Same | Low (depends on Seq 3) |
| `src/science_cli/library/iv/bipolar.py` | Same | Low |
| `src/science_cli/library/pulse/ppf.py` | Same | Low |
| `src/science_cli/core/analysis_output.py` | Helper to merge analysis dict into step metadata | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Analysis → metadata hook | code-medium | All 4 analyzers |
| QA | review-light | Test protocol.yaml gets updated |
| Docs | docs-light | CHANGELOG |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Add `merge_analysis_to_metadata()` helper | 15m | code-medium | no |
| task-002 | Hook into STP analysis | 10m | code-medium | no |
| task-003 | Hook into endurance analysis | 10m | code-medium | no |
| task-004 | Hook into IV bipolar analysis | 10m | code-medium | no |
| task-005 | Hook into PPF analysis | 10m | code-medium | no |
| task-006 | pytest + smoke | 15m | review-light | no |
| task-007 | CHANGELOG | 5m | docs-light | no |

## Dependency Order

1. task-001 (helper) — first
2. task-002-005 (hooks) — parallel
3. task-006 (QA) — depends on all hooks
4. task-007 (docs) — depends on QA

## Risks

- **Risk 1**: Atomic write — if analysis fails midway, protocol.yaml shouldn't be corrupted. Use `write_text(atomic=True)` or write-to-temp-then-rename.
- **Risk 2**: Metadata field naming consistency — V_set vs v_set_v vs Vset. Pick one convention.

## Walkthrough

Implemented `merge_analysis_to_metadata()` in `core/analysis_output.py` as the central helper for merging analysis results into `protocol.yaml` step metadata. Updated `analyze_bipolar_to_yaml()` and `analyze_ppf_to_yaml()` with `metadata`/`project_root`/`step_name` params that trigger auto-write after analysis. STP and endurance analyzers refactored to use the new helper. All pulse analyzers now persist their waveform params and fit results to `protocol.yaml` atomically via `_atomic_write_yaml()`.
