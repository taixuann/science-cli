# PLAN: Project-Aware Dashboard Backend & Plot Engine

## Classification
feature | docs | refactor

## Related Plans
- [[280526_artifacts_and_reference_guides]] — related — parent plan coordinating workspace re-organization.
- [[280526_ai_integration]] — related — AI agents interact with the backend APIs and static image generation.

## Status
- **Created**: 2026-05-28
- **Updated**: 2026-05-28
- **Status**: in-progress
- **Branch**: dev

## Objective
Create `sci serve` — an interactive web dashboard server backed by real CLI data. Uses the AI Studio-designed frontend template from `documentation/frontend 2/` to provide per-project protocol/step navigation with Plotly.js visualizations.

## Context
Currently `memristor dashboard` generates a **static** HTML page. The user wants an **interactive** dashboard where each project has clickable navigation (project → protocol → step → data views). A frontend template was created in AI Studio (`documentation/frontend 2/`) with HTML/CSS/JS/Express. We will:
1. Move the frontend assets into `src/science_cli/serve/frontend/`
2. Build a Python stdlib-based HTTP server (zero new deps)
3. Provide REST API endpoints backed by the CLI's real data (session state, SQLite, CSV files, analysis_data.json)
4. Auto-detect the project from session state

## Specification

### 1. New Directory: `src/science_cli/serve/`

```
src/science_cli/serve/
├── __init__.py
├── frontend/                 # Static frontend assets (from template)
│   ├── index.html            # Project index — protocol cards, KPIs, filters
│   ├── dashboard.html        # Per-protocol interactive dashboard
│   ├── gallery.html          # Plot gallery — all PNG/PDF across project
│   └── assets/
│       ├── dashboard.css     # Styles (dark/light/oled themes)
│       └── dashboard.js      # SciApp runtime: apiFetch, theme, Plotly helpers
├── server.py                 # Python HTTP server (stdlib HTTPServer)
│   - Routes: API endpoints + static file serving
│   - Port 6000 (configurable via --port / SCI_SERVE_PORT)
│   - CORS headers for dev-mode compatibility
└── api.py                    # Data providers (real CLI integration)
```

### 2. `sci serve` Command

- `sci serve` — starts server on port 6000
- `sci serve --port 8080` — custom port
- `sci serve --project /path` — override project (default: session state)
- `sci serve --dev` — CORS + verbose logging for development
- Opens `http://localhost:6000` automatically via `open` (optional)
- Registered in GROUP 3: LIBRARY PLOTTING or ADDITIONAL in help

### 3. API Endpoints

#### `GET /api/project`
Reads session state → resolves project path → scans protocol/step structure.

**Response shape** (matching template expectations):
```json
{
  "project_name": "my-experiment",
  "project_path": "/path/to/project",
  "protocols": [
    {
      "name": "1_iv-test",
      "steps": ["1_set", "2_reset"],
      "total_files": 24,
      "measured_cells": 12,
      "switching_yield": 78.3,
      "last_updated": "ISO8601"
    }
  ],
  "stats": {
    "total_protocols": 3,
    "total_files": 72,
    "total_cells_measured": 36,
    "overall_yield": 72.1
  }
}
```

#### `GET /api/protocol/{name}/summary`
Reads protocol YAML + SQLite → aggregate device statistics.

**Response**: Protocol metadata, device config (rows/cols), aggregate stats, materials list.

#### `GET /api/protocol/{name}/heatmap?metric=ratio&material=`
Queries SQLite or analysis_data.json for 2D crossbar grid data.

**Supported metrics**: `ratio`, `vset`, `vreset`, `files`, `yield`

**Response**: `{ rows: 6, cols: 6, metric: "ratio", data: [[...]], metadata: [[...]] }`

#### `GET /api/protocol/{name}/device/{cell}/iv`
Reads actual CSV files for a specific device cell → returns sweep data.

**Response**: `{ cell_id, row, col, material, sweeps: [ { label, voltage[], current[], v_set, v_reset } ] }`

#### `GET /api/protocol/{name}/histograms`
Derives Vset/Vreset/Ratio distribution bins from SQLite.

**Response**: `{ vset: { bins, counts }, vreset: { bins, counts }, ratio: { bins, counts } }`

#### `GET /api/gallery`
Scans all `results/` directories across the project:
- Project-level: `project/results/*.png` / `*.pdf`
- Per-step: `project/*/step/results/*.png` / `*.pdf`

**Response**: `{ plots: [{ id, plot_path, thumbnail_path, protocol, step, technique, theme, generated_at, title }], filters: { protocols, steps, techniques } }`

### 4. Navigation Flow (Step Drill-Down)

```
Project Index (index.html)
  └── Protocol Card (click)
       └── Protocol Dashboard (dashboard.html?protocol=1_iv-test)
            ├── Device heatmap (Plotly.js)
            ├── Aggregate stats (KPIs)
            ├── Step Selector (tabs/dropdown)
            │    └── Click Step → Step Detail Panel
            │         ├── File list for this step
            │         ├── IV curves from CSV data (Plotly.js)
            │         └── Links to gallery for this step
            └── Histograms (Plotly.js)
```

### 5. Server Implementation (stdlib, zero deps)

```python
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, os, re, urllib.parse

class SciServeHandler(SimpleHTTPRequestHandler):
    # Override do_GET() → route matching → API handler or static file
    # Static files served from frontend/ directory
    # Sendfile for large files, JSON encoding for API
    
    # Helper methods:
    # - _send_json(data) → 200 + JSON response
    # - _send_error(status, msg) → error JSON
    # - _read_session() → load session.py state
    # - _get_frontend_path() → frontend/ dir for static serving
```

Kept minimal. For development, add CORS headers when `--dev` flag is set.

### 6. Frontend Integration (template adaptation)

Modifications needed to the AI Studio template:

| File | Change |
|------|--------|
| `assets/dashboard.js` | Add `window.SciApp` (already exists — keep as-is) |
| `index.html` | Script calls remain; update title to current project |
| `dashboard.html` | Parameterize via URL search params (`?protocol=`) |
| `gallery.html` | Already uses `/api/gallery` — adapt to real data shape |

Minimal JS changes — the template's `window.SciApp.apiFetch()` pattern already matches.

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/serve/__init__.py` | **Create** | Package init |
| `src/science_cli/serve/frontend/index.html` | **Create** | Project index page (from template) |
| `src/science_cli/serve/frontend/dashboard.html` | **Create** | Per-protocol dashboard (from template) |
| `src/science_cli/serve/frontend/gallery.html` | **Create** | Plot gallery (from template) |
| `src/science_cli/serve/frontend/assets/dashboard.css` | **Create** | Styles (from template) |
| `src/science_cli/serve/frontend/assets/dashboard.js` | **Create** | SciApp runtime (from template) |
| `src/science_cli/serve/server.py` | **Create** | HTTP server + API routing |
| `src/science_cli/serve/api.py` | **Create** | Data providers wrapping CLI internals |
| `src/science_cli/cli/commands/serve.py` | **Create** | `sci serve` command handler |
| `src/science_cli/cli/commands/__init__.py` | **Modify** | Register `serve` in COMMAND_TREE |
| `src/science_cli/cli/help.py` | **Modify** | Add `serve` to help sections |

## Files NOT Modified
- `library/memristor/device_cli.py` — `memristor dashboard` static generation stays
- `library/memristor/dashboard.py` — unmodified
- `tui/app.py` — excluded per previous agreement

## Dependencies
- **Zero new Python dependencies** — uses only stdlib (`http.server`, `json`, `os`, `re`, `urllib.parse`)
- Frontend uses CDN-hosted Plotly.js (already in template)

## Cross-PLAN Impact
- `sci serve` replaces the workflow of manually opening static dashboards
- AI agents can use `http://localhost:6000/api/...` endpoints for data queries
- Future: `sci chat` could route to the serve API

## Test Strategy
- Start server → `curl localhost:6000/api/project` returns valid JSON
- Static files served correctly (index.html, dashboard.html)
- Step drill-down: each API endpoint returns expected shape
- Gallery: finds both project-level and per-step results
- Port flag: `sci serve --port 8000` → server on 8000
- Error handling: no open project → shows error page, not crash

## Progress
- [x] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
