# PLAN: Dashboard Redesign — Material Groups, Single-Cycle Viewer, Precise Markers

## Status
- **Created**: 2026-05-16
- **Status**: completed
- **Branch**: refactor/2.1.0

## Objective
Redesign the memristor dashboard for clearer material grouping, single-cycle navigation, and accurate Vset/Vreset markers.

## Specification

### 1. Material-Based Dashboard View
- Replace "6x6 crossbar" title with material selector at top
- Selecting a material switches entire dashboard to that material's view
- Navigation stripped to just Overview (remove Device Explorer, Batch Analysis, Settings sidebar items)
- Crossbar heatmap filtered to only cells with that material

### 2. Heatmap Hover Tooltip
Show on hover: row, col, material, technique, number of cycles (sweeps)

### 3. Single-Cycle IV Viewer
- Replace overlay mode with single-cycle view
- `<` `>` buttons to step through cycle index
- Dropdown/select box to jump to a specific cycle number
- Shows one IV trace at a time with Vset/Vreset markers

### 4. Fix Vset/Vreset Markers
- `detect_vset()` and `detect_vreset()` currently return only voltage
- Add `i_set` and `i_reset` (current at switching point) to return values
- Add columns to SQLite `files` table: `i_set`, `i_reset`
- Pass through dashboard data pipeline
- JS uses actual `(v_set, i_set)` instead of hardcoded `(v_set, 1e-3)`

### 5. Distribution Panels Show/Hide
- Add collapse toggle for Vset/Vreset/Ratio distribution panels

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `memristor/dashboard.py` | Major | Restructure HTML + JS for material view, single-cycle viewer, marker fix |
| `memristor/switching.py` | Modify | Return i_set/i_reset alongside v_set/v_reset |
| `memristor/db.py` | Modify | Add i_set/i_reset columns to files table |
| `memristor/device_cli.py` | Minor | Dashboard command adjustments if needed |

## Dependencies
- Previous config merge fix must be committed ✓
- resolve_technique_from_grammar must exist ✓

## Test Strategy
- Run `memristor dashboard --open` and verify all views render correctly
- Check Vset/Vreset markers land exactly on IV curve
- Verify material filter works end-to-end

## Progress
- [x] PLAN created
- [x] Material grouping + nav simplification
- [x] Heatmap hover with cycle count
- [x] Single-cycle IV viewer
- [x] Vset/Vreset marker fix (i_set/i_reset) — `i_set`/`i_reset` columns added to SQLite `files` table (db.py lines 49-50)
- [x] Distribution show/hide
- [x] Dry run dashboard test

## Post-Completion Notes
All features described in this plan have been implemented on the `refactor/2.1.0` branch:
- Per-material JS data chunks for dashboard rendering
- Single-cycle IV viewer with `<` `>` navigation
- Vset/Vreset markers correctly positioned using actual `(v_set, i_set)` coordinates
- Distribution panels with collapse toggle
- The `i_set`/`i_reset` columns existed in the SQLite schema from the start (db.py) - the dashboard JS was updated to use them
