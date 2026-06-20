# Implementation Plan: Fix STP Origin Line (Multi-Cycle WGFMU)

**Date**: 20/06/2026
**Status**: 🟢 Done
**Layer**: 5 (Plotting Dispatch)
**Version**: v3.22.1 (patch)

---

## Context Summary

The generic plot executor (`plot/generic.py`) has a visible bug: when WGFMU STP decay files contain **multiple pulse cycles** in a single CSV, matplotlib draws a diagonal line through the origin connecting the end of one cycle to the start of the next.

**Investigation results** (file `150626-102320_keysight-b1500a_cu-c-pda(q5)-ito_r6-c2_pulse-stp-decay_001_questionable.csv`):
- File contains 3 complete pulse cycles, each starting at V≈0, I≈0 at t≈0µs
- After `df.sort_values(x_col)` (generic.py:218), cyclic time is reordered end-to-end
- The connection between cycle N's last point (t=119.95µs, V=1.75V, I=-299µA) and cycle N+1's first point (t=0.05µs, V≈0V, I≈0µA) creates a visible diagonal through origin
- Existing `voltage > 0.05` filter cannot fix this — the line traverses all voltages
- Existing NaN-drop cannot fix this — there are no NaN values at cycle boundaries

## Objectives

1. Insert NaN breaks at large time gaps between cycles so matplotlib does not draw connecting lines
2. No config changes needed — gap detection is universal, applies to any multi-cycle file
3. Verify on the problem file that the origin line is gone

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/plot/generic.py` | Insert NaN breaks at large time gaps (>10× median) after sort | Low |

## Root Cause Detail

```
Data flow:
  sort_values(time) → [cycle1_start, ..., cycle1_end, cycle2_start, ..., cycle2_end]
                                                      ↑
                                      matplotlib draws line here
                                      through (0,0)

Fix: insert NaN at gap:
  → [cycle1_end, NaN, cycle2_start, ...]
                                    ↑
                              matplotlib breaks line here
```

Time gap statistics (the problem file):
- Median gap (within cycle): **0.1 µs** (1e-7 s)
- Cycle boundary gaps: **30 µs** (3e-5 s)
- Ratio boundary/median: **300×** — well above the 10× threshold

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | ~10 lines in generic.py |
| QA & Review | review-light | Verify origin line gone on problem file |
| Documentation | docs-light | Update CHANGELOG, bump version |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | Add NaN break at large time gaps in generic.py | 15m | code-medium |
| task-002 | Smoke test on the problem STP file | 15m | review-light |
| task-003 | Update CHANGELOG + version bump | 10m | docs-light |

## Dependency Order

1. task-001 (code) → 2. task-002 (review) → 3. task-003 (docs)

## Risks

- **False positive**: If a file has naturally large time gaps within a single cycle (not between cycles), NaN breaks would incorrectly split the line. Mitigation: threshold at 10× median gap, which covers only cycle boundaries in WGFMU files where median is ~0.1µs and boundaries are ~30µs.
- **Empty plot**: If all points get NaN'd due to extreme gaps. Mitigation: only NaN the y_col, not x_col — matplotlib simply shows a gap.

## Fix

Removed analytical operations from plot path. Plot is for visualization, not processing:
1. **Removed `filter:`** block execution from `_plot_generic()` (voltage > 0.05 filter — belongs in `sci analyze`)
2. **Removed NaN break at time gaps** from `_plot_generic()` (multi-cycle gap break — belongs in `sci analyze`)
3. Kept only rendering fixes: NaN/Inf drop, sort by time, current_sign multiplier

The `filter:` config block stays in `config-studies.yaml` — will be used by `sci analyze` later.

---

## Walkthrough

### The zero-diff trap

The first implementation used `np.diff(times)` directly:

```python
median_gap = np.median(np.diff(times))
gap_indices = np.where(np.diff(times) > median_gap * 10)[0]
```

On a 5000-row STP file, `np.diff(times)` returns 4999 values. **~600 of them are zero** — identical timestamps within a single measurement pulse (multiple measurements at the same clock tick). These zero diffs pull the median down, causing **every non-zero gap** (even 1µs within a cycle) to exceed `10× median` and be falsely flagged as a cycle boundary.

The fix was to filter out zero diffs before computing the median:

```python
diffs = np.diff(times)
non_zero_diffs = diffs[diffs > 0]
median_gap = np.median(non_zero_diffs) if len(non_zero_diffs) > 0 else 1e-12
gap_indices = np.where(diffs > median_gap * 10)[0]
```

With `diffs[diffs > 0]`, only the 4400 positive diffs contribute to the median (~0.1µs), and only the 2 true cycle boundaries (~30µs) exceed 10×. **Zero false positives.**
