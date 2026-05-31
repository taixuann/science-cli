# PLAN: Dashboard on sci serve + Device Type Views

## Classification
feature

## Related Plans
- [[310526_memristor_backend_and_raw_plotting]] — blocked-by — provides SQLite classification
- [[310526_memristor_multicycle_plot]] — related — plotting infrastructure

## Status
- **Created**: 2026-05-31
- **Status**: completed
- **Branch**: dev

## Objective
Port the rich memristor dashboard into a live `/dashboard` route on `sci serve`, backed entirely by SQLite, with device-type awareness from the materials table.

## Context
`sci serve` has a basic dashboard page (`frontend/dashboard.html`) with heatmap, IV explorer, and histograms but it makes 3 separate API calls and has no device-type awareness. The 3764-line `dashboard.py` static HTML generator has richer views but requires regeneration. SQLite already has `materials` table with `device_type` per cell.

## Specification
1. **New API endpoint** `/api/protocol/{name}/dashboard` — single call returns all dashboard data (KPI aggregates, heatmap grid with device_type per cell, histograms, device type breakdown, materials list). Reads SQLite first, falls back to `analysis_data.json` cache.

2. **New `query_materials()` in `db.py`** — queries the `materials` table for device_type per cell.

3. **Update frontend `dashboard.html`** — use single `/dashboard` endpoint, add device-type KPI card, add device-type color dots on heatmap cells, add device_type to tooltips.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/library/memristor/db.py` | Add `query_materials()` | Query device_type from materials table |
| `src/science_cli/serve/api.py` | Add `get_dashboard_data()` | Comprehensive dashboard endpoint |
| `src/science_cli/serve/server.py` | Wire `/api/protocol/{name}/dashboard` | New API route |
| `src/science_cli/serve/frontend/dashboard.html` | Use single endpoint, add device-type views | Rich live dashboard |

## Dependencies
- SQLite `materials` table with `device_type` column (exists from Sprint 8)
- `classify_and_populate_materials()` already runs during `memristor analyze`

## Cross-PLAN Impact
None — standalone feature addition.

## Test Strategy
- `pytest tests/` — 100 tests pass
- Manual: `sci serve` → `/dashboard` → verify KPIs, heatmap with type dots, histograms load
- Manual: `memristor analyze` then `/dashboard` — device types populate from classification

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
