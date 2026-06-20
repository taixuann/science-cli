---
layer: [5, 7]
type: plan
status: planning
tags: [stp, plot, pulse]
assignee: plan
---

# Implementation Plan: Fix STP decay plot

**Date**: 19/06/2026
**Status**: 🟡 Planning
## Context Summary

Current `_plot_stp_decay()` in `src/science_cli/plot/stp.py` uses `load_data_file()` to load the CSV, then plots twin Y-axis (V blue, I red) vs time with segment splitting at time wraps. Issues discovered:

1. **V_set current is wrong**: The plot shows ALL current data including spikes up to ±10mA. Need y-limits to zoom into the V_set plateau current (~1.5mA for file 01, ~3.25mA for file 02).

2. **Only shows raw waveform**: No per-pulse trend analysis. STP decay should show how the V_set current changes across successive pulses (depression/potentiation trend).

3. **Twin Y-axis isn't always needed**: User wants to see just the V_set current clearly, with y-limit clipped to hide the transition spikes.

4. **Different pulse intervals**: File 01 has 1µs 0V gap (6µs total cycle), file 02 has 10µs 0V gap (20µs total cycle). The plot should handle both.

5. **Current decay within the V=2V read pulse**: The current decays during the read plateau itself (from ~9.8mA down to ~2.9mA). Need to distinguish the actual read current at a consistent point within the plateau.

## Key discovery
Within a single V=2V read pulse (5-10µs), the current DECAYS from ~9.8mA to ~2.9mA. The "V_set current" is not a single value — it's a curve. User wants to see the current at the MIDDLE of the V_set plateau, averaged over ~20 points.

## Objectives

- Add a new plot mode to show V_set current only (not twin Y-axis)
- Implement per-pulse V_set current extraction:
  - Find each V≈2V plateau segment
  - Sample current at the middle of each plateau (averaged over 20 pts)
  - Plot I(mA) vs Pulse # with y-limit focused on the range
- Add optional: overlay trend line
- Keep existing `_plot_stp_decay` for backward compat (full waveform view)
- New entry: `_plot_stp_decay_trend()` for the pulse-level view

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/plot/stp.py` | Add `_plot_stp_decay_trend()` function | Med |
| `src/science_cli/plot/registry.py` | Register new variant or add flag | Low |
| `temp-src/plot_stp_decay.py` | Keep as reference | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | Add V_set trend function to stp.py |
| QA & Review | review-light | Test with both STP files |
| Documentation | docs-light | Update CHANGELOG |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | Add V_set plateau detection + middle-20-point averaging to stp.py | 45m | code-medium |
| task-002 | Implement `_plot_stp_decay_trend()` with single-panel I vs pulse plot | 45m | code-medium |
| task-003 | Add CLI flag to switch between waveform (default) and trend view | 30m | code-medium |
| task-004 | Test: run `sci plot` on both STP files, verify trend output | 30m | review-light |
| task-005 | Update CHANGELOG | 15m | docs-light |

## Dependency Order
1. task-001 → task-002 → task-003 → task-004 → task-005
