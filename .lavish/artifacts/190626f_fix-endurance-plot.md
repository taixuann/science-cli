---
layer: [5, 7]
type: plan
status: planning
tags: [endurance, plot, pulse]
assignee: plan
---

# Implementation Plan: Fix endurance volatile plot

**Date**: 19/06/2026
**Status**: 🟡 Planning
## Context Summary

Current `_plot_endurance_volatile()` in `src/science_cli/plot/pulse_endurance.py` uses `_load_and_resolve()` which:
- Reads raw CSV DataValue rows
- Tries to find V and I columns but doesn't handle the 2-row-per-cycle format (HRS+LRS rows)
- Computes R = |V/I| for each row, then plots ALL as one series
- This loses the HRS/LRS separation

**Key discovery**: The Keysight CSV files have Measurement Result sections with timestamped V/I readouts. Each endurance cycle produces 2 sections (SET + READ waveform), giving ~410 sections grouped into ~205 unique cycles. The `raw_cycles` data section has 9205 entries but only 207 with non-zero data.

**Protocol**: 9000 initial silent cycles, then log-spaced read-backs from C9000 to ~C1M with step_log=95 (multiplier = 10^(1/95) ~ 1.0246).

## Objectives

- Rewrite `_plot_endurance_volatile()` to:
  1. Parse Measurement Result sections from the CSV
  2. Extract V and I at 2 time points (7.5µs for LRS, 145µs for HRS) per section
  3. Group adjacent sections by timestamp proximity (within 5s)
  4. Compute R = |V/I| for HRS and LRS separately
  5. Generate cycle index using log formula: C[n] = 9000 × 10^(n/95)
  6. Plot 2-panel figure: top = R vs cycle (HRS red, LRS blue, log scale), bottom = ratio
  7. X-axis: log scale from 8000 to 2e6, hide pre-C9000 region
  8. Annotations inline (no legend)
- Keep temp-src/ scripts as reference before integrating

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/plot/pulse_endurance.py` | Rewrite volatile variant with Measurement Result parsing + per-cycle HRS/LRS extraction + log-spaced cycle mapping | Med |
| `temp-src/plot_endurance_extract.py` | Keep as reference | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | Rewrite pulse_endurance.py volatile variant |
| QA & Review | review-light | Smoke test with R3-C3 and R5-C3 files |
| Documentation | docs-light | Update CHANGELOG |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | Build Measurement Result section parser module | 1h | code-medium |
| task-002 | Implement per-cycle HRS/LRS extraction + log-spaced cycle mapping | 1h | code-medium |
| task-003 | Rewrite _plot_endurance_volatile with 2-panel plot (R + ratio) | 1h | code-medium |
| task-004 | Test with R3-C3 and R5-C3 files, verify output | 30m | review-light |
| task-005 | Update CHANGELOG | 15m | docs-light |

## Dependency Order
1. task-001 → task-002 → task-003 → task-004 → task-005

## Walkthrough

### task-001: Measurement Result section parser
New helper function `_parse_endurance_sections(filepath)` that:
- Opens CSV, scans for `Setup.Title = Measurement Result`
- For each section: reads `RecordTime` timestamp, `YAxis.Bottom`/`Top`, and `DataValue` rows
- Returns list of dicts: `{ts, lrs_v, lrs_i, hrs_v, hrs_i}`

### task-002: Per-cycle extraction + cycle mapping
- Group sections by timestamp proximity (5s threshold)
- For each group: average HRS/LRS resistance
- Generate cycle index: `cycle = base × 10^(n/step_log)` where n = normalized position within sequence
- Return `(cycles[], hrs[], lrs[])` arrays

### task-003: Plot rewrite
- Create 2-panel figure: R panel + ratio panel
- HRS red circles, LRS blue squares, no legend, inline annotations
- Log x scale from 8000 to 2e6, only major ticks at 10⁴ 10⁵ 10⁶
- Log y scale for R panel
