# PLAN: Dashboard Server (`sci serve`)

## Classification
feature

## Related Plans
- [[PLAN-dashboard-redesign]] — related — previous dashboard visual redesign work
- [[PLAN-plotly-dashboard]] — related — existing Plotly static HTML dashboard generation
- [[PLAN-enhanced-dashboard]] — related — cross-protocol dashboard features

## Status
- **Created**: 2026-05-26
- **Status**: draft
- **Branch**: dev

## Objective

Add a `sci serve` command that starts a **free, localhost-only HTTP server** to dynamically browse all project dashboards, plot galleries, and live data — replacing the static `file://` workflow with a unified web interface that fetches data on demand from SQLite.

## Context

### What Exists Now
1. **Static Plotly dashboards** (`memristor dashboard --open`) generate self-contained `dashboard.html` files with all data embedded as JSON blobs. Works with `file://` protocol but:
   - Requires regeneration every time data changes
   - All IV data is embedded in HTML (slow for large datasets)
   - No unified gallery view across protocols
   - `file://` CORS restrictions in some browsers
2. **matplotlib plots** (`sci plot`) generate PDF/SVG/PNG into `protocol/<name>/<step>/results/`
3. **SQLite cache** (`<project>.db`) stores analysis data, parameters, and metadata
4. **Textual TUI** (`sci` no args) provides terminal browsing but no web view
5. **Session state** (`session.py`) tracks `last_project`, `last_protocol`, `last_step`

### What Problem This Solves
- **Fragmented viewing**: Plots live in scattered directories; dashboards are per-protocol HTML files
- **Stale data**: Static HTML must be regenerated after every `memristor analyze`
- **No plot gallery**: No way to see all generated plots side-by-side
- **No plot provenance**: Static plots don't link back to their source data file or parameters
- **Large payloads**: Cross-protocol dashboard embeds all IV data in one HTML file

## Specification

### `.dashboard/` Directory (Per Project)

A hidden directory under each project root to store server state, plot manifests, and cached metadata. Auto-created on first `sci serve` or `sci plot`.

```
<project>/
├── .dashboard/
│   ├── manifest.json       ← Plot metadata registry (auto-written by `sci plot`)
│   ├── settings.json       ← Server prefs: last port, theme, filters
│   └── cache/
│       └── thumbs/         ← Auto-generated thumbnails for gallery
├── sci-config.yaml
├── protocol/
└── <project>.db
```

**`manifest.json`** schema (auto-updated by `sci plot`):
```json
{
  "version": 1,
  "updated_at": "2026-05-26T10:30:00Z",
  "plots": [
    {
      "plot_path": "protocol/1_iv-test/1_set/results/iv_overlay.pdf",
      "data_files": ["data/raw/0505_Ta-PDA-ITO_r0c0_iv_01.csv"],
      "protocol": "1_iv-test",
      "step": "1_set",
      "technique": "iv-sweep",
      "device": "keithley-2400",
      "theme": "publication-nature",
      "generated_at": "2026-05-26T10:30:00Z",
      "flags": {"title": "IV Curve", "xlabel": "Voltage (V)"}
    }
  ]
}
```

This gives **plot provenance**: the gallery knows which data file produced each plot, what protocol/step it belongs to, and what parameters were used.

### Context Awareness

The server reads the CLI session state to set the default project and show breadcrumbs:

```
Dashboard: my-project / 1_iv-test / 1_set
```

- If `sci open -m project -n my-project` was run, the server defaults to that project
- The index page shows quick links to the last-opened protocol and step
- Gallery can be filtered by protocol, step, technique, or material

### Two Views Architecture

| View | Route | Purpose | Data Source |
|------|-------|---------|-------------|
| **Project Index** | `/` | Overview: protocols, stats, quick links | SQLite + manifest |
| **Plotly Dashboard** | `/dashboard/<protocol>` | Interactive IV exploration, heatmaps, params | SQLite live queries |
| **Static Gallery** | `/gallery` | Publication plot review with provenance | `manifest.json` + image files |
| **Data Browser** | `/browse` | Raw file listing, CSV preview | File system |
| **JSON API** | `/api/*` | Live data endpoints for dynamic pages | SQLite |

### Architecture Overview

```
User runs: sci serve [--port 8080] [--host 127.0.0.1] [--no-open]

┌─────────────────────────────────────────────────────────────┐
│              Python http.server (stdlib only)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  /       │ │/gallery  │ │/dashboard│ │/api/*        │   │
│  │  Index   │ │ Plot     │ │ Plotly   │ │ JSON data    │   │
│  │  page    │ │ gallery  │ │ dynamic  │ │ endpoints    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────────┐   │
│  │/browse   │ │/static/  │ │/project/<name>           │   │
│  │ Raw data │ │ Plots,   │ │ Project-specific views   │   │
│  │ browser  │ │ CSS, JS  │ │ (future multi-project)   │   │
│  └──────────┘ └──────────┘ └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
              ↕                              ↕
         manifest.json                   SQLite cache
      (.dashboard/manifest.json)       (<project>.db)
```

### Phased Implementation

#### Phase 1: Static Server + Manifest + Gallery (MVP)
**Goal**: `sci serve` starts a server; `sci plot` writes to manifest; gallery shows plots with provenance.

**New command**: `sci serve [port] [--host HOST] [--no-open]`

**Auto-behaviors**:
- `sci plot` now **appends to** `.dashboard/manifest.json` after saving a figure
- `.dashboard/` auto-created if missing

**Pages**:
| Route | Content |
|-------|---------|
| `/` | Project index: open context, protocol list, stats, quick links to gallery + last protocol |
| `/gallery` | Thumbnail grid of all plots with filter sidebar (by protocol, step, technique, material). Each card shows: thumbnail, filename, source data file, theme, timestamp |
| `/gallery/<protocol>` | Filtered gallery for one protocol |
| `/gallery/<protocol>/<step>` | Filtered gallery for one step |
| `/static/*` | Serve existing files from project directory |

**Implementation**:
- `cli/commands/serve.py` — command handler + argument parsing
- `core/manifest.py` — read/write `.dashboard/manifest.json` (used by both `plot` and `serve`)
- `server/` module (new):
  - `server/__init__.py` — `start_server()` public API
  - `server/handler.py` — custom `http.server.SimpleHTTPRequestHandler`
  - `server/routes.py` — URL route dispatch table
  - `server/gallery.py` — gallery HTML generator (reads manifest.json)
  - `server/index.py` — project index HTML generator
  - `server/assets.py` — embedded CSS/JS strings (no CDN)

**Key behaviors**:
- Server roots at `<project>/` — serves files naturally
- Gallery reads from `manifest.json` first; falls back to file scanning if manifest missing
- Gallery cards link to: (1) plot image, (2) source data file, (3) Plotly dashboard for that protocol
- No external dependencies — 100% Python stdlib

#### Phase 2: JSON API Endpoints
**Goal**: Add REST-ish API endpoints so pages can fetch data dynamically.

**New routes**:
| Endpoint | Returns |
|----------|---------|
| `/api/protocols` | List of all protocols with summary stats |
| `/api/protocol/<name>/files` | Files in protocol (from SQLite) |
| `/api/protocol/<name>/cells` | Cell matrix with counts (from SQLite) |
| `/api/protocol/<name>/device/<id>/iv` | IV curve data for a device |
| `/api/protocol/<name>/aggregate` | Vset/Vreset/Ratio/Yield aggregates |
| `/api/manifest` | Full plot manifest |
| `/api/manifest?protocol=1_iv-test` | Filtered manifest |

**Implementation**:
- `server/api.py` — route dispatch + SQLite query helpers
- Uses existing `memristor/db.py` functions

#### Phase 3: Dynamic Plotly Dashboard
**Goal**: `/dashboard/<protocol>` generates Plotly HTML on-the-fly from SQLite + manifest.

**Behavior**:
- Query SQLite for protocol data
- Call existing `_build_html()` from `dashboard.py` with injected data dicts
- Supports URL filters: `?material=Ta-PDA-ITO&technique=iv-sweep`
- Cross-protocol dashboard at `/dashboard`
- Links back to gallery: "View plots for this protocol"

**Implementation**:
- `server/dashboard_renderer.py` — wraps existing HTML builder
- `server/handler.py` — route `/dashboard/<protocol>` to renderer

### File Structure (new)

```
src/science_cli/
├── cli/commands/
│   └── serve.py              ← New: CLI command
├── core/
│   └── manifest.py           ← New: manifest.json read/write
├── server/                   ← New module
│   ├── __init__.py           ← start_server() public API
│   ├── handler.py            ← Custom HTTPRequestHandler
│   ├── routes.py             ← Route dispatch table
│   ├── api.py                ← JSON API endpoints
│   ├── gallery.py            ← Gallery page generator
│   ├── index.py              ← Project index page generator
│   ├── dashboard_renderer.py ← Dynamic Plotly HTML generation
│   └── assets.py             ← Embedded CSS/JS strings
```

### CLI Integration

**Command registration**:
```python
# In cli/commands/serve.py
COMMAND_TREE["serve"] = {
    "handler": serve_handler,
    "desc": "Start localhost dashboard server (group 3)",
}
```

**Usage**:
```bash
# Start server on default port 8080
sci serve

# Custom port
sci serve 9090

# Custom host (default 127.0.0.1)
sci serve --host 0.0.0.0

# Don't auto-open browser
sci serve --no-open

# Serve a specific project
sci serve --project /path/to/my-project
```

### Design Principles

1. **Zero-cost hosting**: 100% Python standard library. No Flask, FastAPI, or external HTTP deps.
2. **Read-only server**: Server only reads data. All writes still go through CLI commands.
3. **Graceful degradation**: If SQLite is missing → file scanning. If manifest is missing → scan `results/` directories.
4. **Context-aware**: Reads CLI session for default project/protocol/step.
5. **Theme-aware**: Gallery and index pages respect user's configured theme.
6. **Security**: Bind to `127.0.0.1` by default. `--host 0.0.0.0` requires explicit opt-in.
7. **Manifest as source of truth**: Gallery uses `manifest.json` for plot metadata; falls back to filesystem scanning.

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/cli/commands/serve.py` | Create | New CLI command handler |
| `src/science_cli/cli/commands/__init__.py` | Edit | Register `serve` in `COMMAND_TREE` |
| `src/science_cli/core/manifest.py` | Create | Read/write `.dashboard/manifest.json` |
| `src/science_cli/plot/base.py` | Edit | Call `manifest.add_plot()` in `save_figure()` |
| `src/science_cli/server/__init__.py` | Create | Module init + `start_server()` API |
| `src/science_cli/server/handler.py` | Create | Custom HTTPRequestHandler |
| `src/science_cli/server/routes.py` | Create | URL route dispatch |
| `src/science_cli/server/api.py` | Create | JSON API endpoints |
| `src/science_cli/server/gallery.py` | Create | Gallery HTML generator |
| `src/science_cli/server/index.py` | Create | Project index HTML generator |
| `src/science_cli/server/assets.py` | Create | Embedded CSS/JS for pages |
| `src/science_cli/server/dashboard_renderer.py` | Create | Dynamic Plotly dashboard builder |
| `src/science_cli/memristor/dashboard.py` | Edit | Extract `_build_html()` to be reusable by renderer |
| `README.md` | Edit | Document `sci serve` command |
| `AGENTS.md` | Edit | Update directory map, add server module |
| `tests/server/` | Create | pytest tests for API, gallery, routing |
| `tests/core/test_manifest.py` | Create | Tests for manifest read/write |

## Dependencies

**Zero external dependencies** — everything from Python standard library:
- `http.server` — HTTP request handling
- `socketserver` — Server socket management
- `sqlite3` — Database queries
- `json`, `pathlib`, `mimetypes` — Data handling
- `webbrowser` — Auto-open (`--open` flag)

## Test Strategy

| Test | Type | How |
|------|------|-----|
| Server startup | Smoke | Start server in thread, verify `200 OK` on `/` |
| Manifest read/write | Unit | Write manifest, read back, verify schema |
| Plot → manifest | Integration | Run `sci plot`, verify manifest entry exists |
| Gallery generation | Unit | Mock manifest, verify HTML contains thumbnails + provenance |
| API endpoints | Unit | Mock SQLite connection, verify JSON response |
| Route dispatch | Unit | Verify correct handler called per path |
| Security | Unit | Verify default bind is `127.0.0.1` |
| No external deps | Guardrail | Verify `server/` module imports no 3rd-party packages |

## Progress

- [x] PLAN created
- [ ] User approved
- [ ] Phase 1: Manifest + static server + gallery
- [ ] Phase 2: JSON API endpoints
- [ ] Phase 3: Dynamic Plotly dashboard
- [ ] TEST passed
- [ ] DOCS updated (README, AGENTS.md)
- [ ] COMMIT done

## Updated Workflow (Frontend by AI Studio)

Instead of hand-coding all HTML/CSS/JS, we will:
1. **You** feed `documentation/prompts/frontend-dashboard-prompt.md` to Google AI Studio to generate the frontend files
2. **Me** (OpenCode) build the Python server backend that serves those files + JSON API endpoints
3. **Integration**: Drop generated HTML/CSS/JS into `src/science_cli/server/templates/` and wire routes

This splits the work cleanly — AI Studio handles the visual design, I handle the data plumbing.
