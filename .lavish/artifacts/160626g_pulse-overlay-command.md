---
layer: [7]
type: plan
status: done
tags: [pulse, overlay, case-study]
depends_on: [160626c_device-study-relationship]
assignee: code
---

# Implementation Plan: Pulse Command + Case-Study Overlay (Seq 3)

**Date**: 16/06/2026
**Status**: 🟢 Done
**Architecture ref**: `160626c_device-study-relationship.md` §6.7, §3

## Context Summary

User wants to overlay multiple pulse files (e.g., stp-decay traces) to compare their behavior under different parameters (V_set, V_read, pulse widths).

Design (refined by user):
- **NO separate `.cases/` directory** — instead, use `protocol.yaml` as the single source of truth
- After `sci analyze` runs on a file, **write metadata back to protocol.yaml** under that step:
  ```yaml
  steps:
    - name: stp-decay-041
      study: pulse:pulse-stp-decay
      files: [150626_..._041_important.csv]
      metadata:
        v_set_v: 2.74
        v_read_v: 0.51
        set_width_us: 93.35
        read_width_us: 37.80
        notes: highlight
  ```
- `sci pulse overlay` command reads protocol.yaml, lets user select grouping variable, generates overlay plot

## Objectives

1. **Auto-write metadata to protocol.yaml** when pulse study is analyzed. Add `metadata` field to step if not present.
2. **New `pulse` command group**:
   - `sci pulse overlay <study>` — overlay multiple files, grouped by chosen variable
   - `sci pulse list` — show all pulse files with their metadata in fzf
3. **Grouping logic**:
   - Read protocol.yaml steps with matching study
   - For each step, extract `metadata.<variable>` (e.g., `v_set_v`)
   - Group files by variable value (within tolerance)
   - Each group = one overlay trace
4. **Plot**:
   - x-axis: time
   - y-axis: current
   - color per group (using `__color__` field in style)
   - legend: variable value

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/library/pulse/stp.py` | After analysis, write metadata back to protocol.yaml | Med |
| `src/science_cli/library/pulse/endurance.py` (NEW) | Similar pattern for endurance | Med |
| `src/science_cli/cli/commands/pulse.py` (NEW) | New command group: `pulse overlay`, `pulse list` | Med |
| `src/science_cli/cli/main.py` | Register `pulse` command | Low |
| `src/science_cli/core/protocol.py` | Add `update_step_metadata()` helper | Low |
| `tests/test_pulse/test_overlay.py` (NEW) | Test grouping + overlay | Med |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Write metadata to protocol.yaml | code-medium | Update step files |
| New `pulse` command | code-medium | CLI + fzf + overlay |
| Grouping logic | code-medium | Tolerance-based grouping |
| QA | review-light | Test end-to-end |
| Docs | docs-light | CHANGELOG + help text |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Add `update_step_metadata()` to protocol.py | 20m | code-medium | no |
| task-002 | Auto-write metadata from STP analysis | 20m | code-medium | no |
| task-003 | Auto-write metadata from endurance analysis | 20m | code-medium | no |
| task-004 | New `pulse` CLI command | 30m | code-medium | no |
| task-005 | `pulse list` — fzf display with metadata | 20m | code-medium | no |
| task-006 | `pulse overlay` — grouping + plot | 45m | code-medium | no |
| task-007 | Tests for grouping + overlay | 30m | code-medium | no |
| task-008 | pytest + smoke | 15m | review-light | no |
| task-009 | CHANGELOG + help text | 10m | docs-light | no |

## Dependency Order

1. task-001 (protocol helper) — first
2. task-002, 003 (auto-write metadata) — depends on 001
3. task-004 (CLI skeleton) — depends on 001
4. task-005 (list command) — depends on 002, 003, 004
5. task-006 (overlay) — depends on 005
6. task-007 (tests) — depends on all above
7. task-008 (QA) — depends on 007
8. task-009 (docs) — depends on 008

## Risks

- **Risk 1**: protocol.yaml update could conflict with concurrent edits. Need atomic write (read → modify → write).
- **Risk 2**: Grouping tolerance — V_set values like 2.74 vs 2.75 should be in the same group. Need to define tolerance per variable (e.g., ±0.01V for voltage, ±10µs for widths).
- **Risk 3**: Metadata extraction from analysis YAML → writing to protocol.yaml requires reading the analysis output back. Need a consistent schema.

## Walkthrough

Built `src/science_cli/library/pulse/device_cli.py` (460 lines) with `sci pulse list` and `sci pulse overlay` subcommands. `pulse list` reads `protocol.yaml` steps matching study filter and displays metadata columns. `pulse overlay` implements tolerance-based numeric grouping (±5% of median by default) with color-per-group matplotlib plots. Extended `core/protocol.py` with `update_step_metadata()`, `read_step_metadata()`, `get_pulse_steps_with_metadata()`, and `_atomic_write_yaml()`. STP and endurance analyzers auto-write metadata after analysis. 27 new tests.
