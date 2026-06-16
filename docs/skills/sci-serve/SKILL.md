---
name: sci-serve
description: "Interactive dashboard server for science-cli — REST API endpoints for project data, IV analysis, crossbar heatmaps, gallery browsing, and protocol summaries. Frontend features include theme-aware rendering, interactive heatmaps, lightbox gallery, and responsive design. Load when deploying or interacting with the science-cli dashboard server."
version: 3.11.0
author: science-cli team
knowledge_type: feature
techniques: []
---

# sci-serve — Dashboard Server Skill

## Overview

`sci serve` starts a local HTTP server that serves the science-cli AI Studio frontend with a full REST API backend. Provides a graphical dashboard for browsing projects, visualizing IV data, inspecting protocol heatmaps, and exploring the saved plots gallery. Built on Python's stdlib `http.server.ThreadingHTTPServer`.

## CLI Reference

### Usage

```bash
sci serve [--port 8000] [--project /path] [--dev] [--open]
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8000 or `$SCI_SERVE_PORT` | Port to listen on |
| `--project` | session project | Override project path (otherwise uses session) |
| `--dev` | False | Enable CORS headers + verbose request logging |
| `--open` | False | Auto-open browser after 1s delay |

### Examples

```bash
# Default start
sci serve

# Custom port
sci serve --port 8080

# Development mode with auto-browser
sci serve --dev --open

# Force specific project
sci serve --project /path/to/my-project

# Use environment variable
export SCI_SERVE_PORT=9000
sci serve
```

### Deployment Options

| Method | Command | Pros | Cons |
|--------|---------|------|------|
| Direct (screen) | `screen -dmS sci-dash sci serve --port 8000` | Simple, persistent | No auto-restart |
| Direct (tmux) | `tmux new-session -d -s sci-dash 'sci serve --port 8000'` | Session management | Requires tmux |
| systemd | Service file with `ExecStart` | Auto-restart, logging | More setup |

## REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all projects in workspace root |
| `/api/project` | GET | Current project data (protocols, stats, files) |
| `/api/gallery` | GET | Gallery of saved plots with filters |
| `/api/protocol/{name}/files` | GET | File listing for a protocol |
| `/api/protocol/{name}/summary` | GET | Protocol KPIs (yield, cells, median Vset/Vreset/ratio) |
| `/api/protocol/{name}/heatmap` | GET | Crossbar heatmap matrix (`?metric=ratio|vset|vreset|files|yield&material=`) |
| `/api/protocol/{name}/device/{cell}/iv` | GET | Per-cell IV sweep data with Vset/Vreset markers |
| `/api/protocol/{name}/histograms` | GET | Histogram bins for Vset, Vreset, ON/OFF ratio |
| `/api/protocol/{name}/dashboard` | GET | Comprehensive dashboard bundle (heatmap + histograms + device types + KPIs) |

### Heatmap Query Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `metric` | ratio, vset, vreset, files, yield | ratio | Metric to color the heatmap |
| `material` | material name | empty (all) | Filter by material |

### Frontend Routes

| Path | Serves |
|------|--------|
| `/` or empty | `index.html` |
| `/dashboard` or `/dashboard/{protocol}` | `dashboard.html` |
| `/neurophase` | NeuroPhase memristor diagnostics frontend |
| `/files/{relative_path}` | Files from project protocol dir |

## Frontend Features

- **Dashboard view**: Protocol selector, KPI cards (yield, cells, median Vset/Vreset/ratio), heatmap matrix with color-coded cells, material filter dropdown
- **Gallery view**: Thumbnail grid of saved plots (SVG/PNG/PDF), filterable by protocol and step, lightbox for full-size viewing with zoom
- **Plot detail**: Per-device IV curve viewer with sweep navigation, Vset/Vreset markers, and R_on/R_off annotation
- **Theme-aware rendering**: Uses active science-cli theme colors
- **Responsive design**: Desktop and tablet support

### Gallery Plot Categories

| Category | Description |
|----------|-------------|
| `distinct` | Matched to specific raw data file (same stem) |
| `overlay` | Multi-file overlay plots (no single-file correspondence) |

## Data Source Resolution

The server resolves data in priority order:

1. **SQLite database** (`{project}.db`) — Fastest, most complete (per-cell Vset/Vreset/R_on/R_off)
2. **Analysis cache** (`results/analysis_data.json`) — JSON blob from previous analysis run
3. **Filesystem scan** — Direct directory traversal (slow, minimal analysis)

The server is **read-only** — no files are modified through the API.

## Server Architecture

Source: `src/science_cli/serve/server.py`

- `SciServeServer` extends `ThreadingHTTPServer`
- `SciServeHandler` extends `SimpleHTTPRequestHandler`
- Serves frontend from `serve/frontend/` directory (bundled JS/CSS/HTML)
- Resolves project context via `--project` override, active session project, or last-opened project
- Dev mode: `Access-Control-Allow-Origin: *` for hot-reload development
- Binds to `0.0.0.0` — accessible from other machines on the same network
- Port binding requires free port; no auto-retry on bind failure

## AI Agent Usage

### Dashboard deployment workflow
1. Ensure a project is open: `sci open -m project <name>`
2. Start server: `sci serve [--port PORT] [--open]`
3. For development: `sci serve --dev --open`
4. For long-running: use screen/tmux/systemd
5. Access at `http://localhost:<port>`

### API usage for agents
- Fetch project overview: `GET /api/project`
- Check protocol yields: `GET /api/protocol/{name}/summary`
- Visualize crossbar: `GET /api/protocol/{name}/heatmap?metric=ratio`
- Get device data: `GET /api/protocol/{name}/device/{cell}/iv`
- Get dashboard bundle: `GET /api/protocol/{name}/dashboard`

### Troubleshooting
- **Port in use**: Change port or kill existing process (`lsof -ti:8000 | xargs kill`)
- **No project data**: Ensure project is open (`sci open -m project <name>`) or use `--project`
- **Gallery empty**: Run analysis commands first (e.g., `sci iv analyze`) to generate plots
- **CORS errors in dev**: Use `--dev` flag to enable cross-origin headers
- **Production**: Consider nginx/Caddy reverse proxy for TLS and performance
