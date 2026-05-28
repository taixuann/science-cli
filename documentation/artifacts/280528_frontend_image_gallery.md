# PLAN: Frontend Image Gallery — Single-Page File Browser

## Classification
feature

## Related Plans
- [[280526_dashboard]] — supersedes (simplifies the complex dashboard UI)

## Status
- **Created**: 2026-05-28
- **Status**: approved
- **Branch**: dev

## Objective
Replace the 3-page frontend (index + dashboard + gallery) with a single-page image gallery. User picks a project → picks a protocol → sees a thumbnail grid of all PDF/PNG figures per step.

## Context
Current `sci serve` has 3 separate HTML pages: project index with KPI cards, interactive dashboard with Plotly heatmaps/histograms/IV curves, and plot gallery. These are over-engineered for what the user needs — a simple visual file browser. The backend (API) works well but the frontend needs simplification.

## Specification

### Single page app: `index.html` (rewrite)
- **Sidebar**:
  - Project selector (dropdown, populated from `/api/project`)
  - Protocol selector (dropdown, filtered by selected project)
  - Step list (shown as clickable items under the selected protocol)
- **Main area**: Breadcrumb bar (project / protocol / step) + thumbnail grid
- **Thumbnail grid**: 3-4 columns, shows image previews. Click opens full PDF/PNG in a lightbox overlay.
- **Top bar**: Theme toggle (dark/light/oled)
- **Remove**: Material filters, technique filters, terminal simulator, KPI cards, Plotly chart, heatmap matrix, histogram panels

### Backend additions: `api.py`
- **New: `/api/protocol/{name}/files`** — returns list of result files (images) grouped by step for a given protocol. Simpler than full gallery, returns only path + type + filename.

### Backend additions: `server.py`
- **New route: `/files/protocol/{path}`** — serves actual files from the project's `protocol/` directory. This is critical because currently the server only serves from `frontend/`. PDFs/PNGs stored in project directories need a dedicated route.

### Frontend cleanup
- `frontend/gallery.html` — DELETE (functionality moved into index.html)
- `frontend/dashboard.html` — DELETE (no longer needed)
- `frontend/assets/dashboard.js` — Simplify: remove Plotly helpers (`drawHysteresisLoopSVG`, `drawVoltammetryLoopSVG`, `getPlotlyThemeLayout`), keep theme toggle, `apiFetch`, `formatDate`. Add thumbnail grid rendering. Add lightbox viewer.
- `frontend/assets/dashboard.css` — Remove unused classes (crossbar-matrix, histogram, plotly, terminal-related). Add thumbnail grid + lightbox styles.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/serve/api.py` | Add `get_protocol_files()` function | New endpoint for step-based file listing |
| `src/science_cli/serve/server.py` | Add `/api/protocol/{name}/files` route + `/files/protocol/{path}` static serve | Serve project files to browser |
| `src/science_cli/serve/frontend/index.html` | Complete rewrite as single-page gallery | Replace 3 pages with 1 unified page |
| `src/science_cli/serve/frontend/gallery.html` | Delete | Functionality merged into index.html |
| `src/science_cli/serve/frontend/dashboard.html` | Delete | No longer needed |
| `src/science_cli/serve/frontend/assets/dashboard.js` | Simplify — remove Plotly, keep theme/api, add gallery rendering | Match new single-page design |
| `src/science_cli/serve/frontend/assets/dashboard.css` | Strip unused classes, add gallery/lightbox styles | Match new single-page design |

## Dependencies
None. Backend changes are additive (no existing endpoints changed).

## Test Strategy
- Start `sci serve` — index page loads as single gallery
- Project dropdown populates with real projects
- Protocol dropdown filters by selected project
- Step list shows steps for selected protocol
- Thumbnails display correctly for steps with PNG files
- PDF files open in lightbox/browser when clicked
- Theme toggle works
- `curl` all API endpoints still return 200

## Progress
- [X] PLAN created
- [X] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] COMMIT done
