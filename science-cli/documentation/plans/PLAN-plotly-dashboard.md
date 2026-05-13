# PLAN: Plotly Interactive Dashboard (Phase 4)

## Classification
feature

## Related Plans
- [[PLAN-science-cli-2.0.0]] — parent plan, Phase 4

## Status
- **Created**: 2026-05-13
- **Status**: completed
- **Branch**: mysci-tui

## Objective
Replace the SVG-based dashboard (`dashboard.py`) with a Plotly-based interactive HTML dashboard that generates `dashboard.html` directly from raw CSV data — no intermediate SVG files, no server required.

## Context
The current dashboard reads generated SVG files from `results/` and embeds them via `<img>` tags. It has static, non-interactive plots. The new dashboard should:
- Read raw CSV data files directly (using `read_iv_csv()` from `plotting.py`)
- Generate Plotly scatter plots inline
- Embed as self-contained HTML with Plotly.js loaded via CDN
- Work with `file://` protocol (no web server)
- Provide zoom, pan, hover tooltips, and PNG export on all plots

## Specification

### Function Signature (Backward Compatible)
```python
def generate_dashboard(config, results_dir: Path, output_path: str | Path) -> Path:
```
- `config`: DeviceConfig from `devices.yaml`
- `results_dir`: Directory for output (e.g., `protocol/<name>/<step>/results/`)
- `output_path`: Where to write `dashboard.html`

### Data Flow
```
devices.yaml → DeviceConfig.get_all_files("iv")
     ↓
For each FileEntry:
  1. Resolve raw CSV path: results_dir.parent / fe.file
  2. Read CSV via read_iv_csv() → (voltage, current, info)
  3. Create Plotly Figure (go.Scatter)
  4. Convert to HTML div via fig.to_html(include_plotlyjs=False, full_html=False)
     ↓
Assemble full HTML page:
  - <head> with Plotly.js CDN + CSS
  - Header with device info + stats
  - Matrix row (per-material grid tables, clickable)
  - Filter bar (material, sweep type, cycle range dropdowns)
  - Cell details (<details> elements with Plotly divs)
     ↓
Write dashboard.html to output_path
```

### Dashboard Layout
```
┌─────────────────────────────────────────────────────────┐
│  HEADER                                                  │
│  Ta-PDA-ITO — IV Dashboard                               │
│  91 IV plots | 5 materials | 13 cells | 2026-05-13 10:00│
├─────────────────────────────────────────────────────────┤
│  MATRIX ROW (all materials side-by-side)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │ Mat A    │ │ Mat B    │ │ Mat C    │  ...            │
│  │ [grid]   │ │ [grid]   │ │ [grid]   │                 │
│  └──────────┘ └──────────┘ └──────────┘                 │
├─────────────────────────────────────────────────────────┤
│  FILTER BAR                                              │
│  [Material: All ▼] [Sweep: All ▼] [Cycles: 1-91]        │
├─────────────────────────────────────────────────────────┤
│  CELL DETAILS (expandable <details> per cell)           │
│  ▸ T1-B1 | Ta-PDA-ITO(1) | 18 files: #1-#18            │
│    ┌─────────────┐ ┌─────────────┐                      │
│    │ [Plotly IV] │ │ [Plotly IV] │                      │
│    │  #01 uc     │ │  #02 uc     │                      │
│    └─────────────┘ └─────────────┘                      │
│  ▸ T1-B2 | Ta-PDA-ITO(2) | 12 files: #19-#30           │
│    ...                                                   │
└─────────────────────────────────────────────────────────┘
```

### Plotly Features Per IV Curve
- Line type: `go.Scatter` with voltage on x, current on y
- Auto-detect log scale for current if range > 2 decades
- Modebar: zoom, pan, reset, download PNG
- Hover tooltips showing (V, I) values
- Responsive sizing (use container width)

### Filter Bar Implementation
- Three `<select>` dropdowns: Material, Sweep Type, Cycle Range
- "All" options for each
- JavaScript `onchange` handlers that show/hide plot containers via CSS classes
- Each plot div wrapped in a container with `data-material`, `data-sweep`, `data-cycle` attributes

### Interactive Features
1. **Zoom, pan, hover**: Built into Plotly modebar
2. **Click matrix cell → expand + scroll**: Native `<a href="#cell-r0c0">` links + JS to open `<details>`
3. **Filter by material, sweep type, cycle range**: JS dropdown handlers
4. **Toggle plot visibility**: Via filter bar
5. **Export PNG**: Built into Plotly modebar

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | **REPLACE** | Swap SVG-based dashboard for Plotly interactive version |

## Dependencies
- Phase 3a (memristor module in place) — ✅ COMPLETE
- `plotly>=5.0` — ✅ installed (6.6.0)
- `read_iv_csv()` from `plotting.py` — ✅ exists
- `_extract_sweep_annotations()` from `plotting.py` — ✅ exists

## Cross-PLAN Impact
- [[PLAN-science-cli-2.0.0]] Phase 4 — this PLAN IS that phase

## Test Strategy
1. Verify `plotly` is importable
2. Generate a minimal test dashboard (if test data available)
3. Verify HTML file is valid (well-formed)
4. Verify the `generate_dashboard()` function signature is unchanged
5. Manual: open in browser, verify Plotly plots render and are interactive

## Progress
- [x] PLAN created
- [x] User approved — auto-approved (from intent-router directive)
- [x] IMPLEMENT done
- [x] TEST passed — all 16 guardrail tests pass, imports verified, Plotly figure generation tested
- [ ] DOCS updated
- [x] COMMIT done — `c6196ad` Phase 4: Replace SVG dashboard with Plotly interactive HTML

## Implementation Notes
- `generate_dashboard()` reads raw CSV data via `read_iv_csv()` from `plotting.py`, no intermediate SVGs
- Each IV curve: `go.Scatter` figure → `fig.to_html(include_plotlyjs=False, full_html=False)`
- Plotly.js v2.35.2 loaded via CDN once in `<head>`, each plot div renders independently
- Data directory resolved as `results_dir.parent` (convention: results/ is sibling to raw data files)
- Filter bar: JS-driven show/hide via `data-material`, `data-sweep`, `data-cycle` attributes
- Expand/Collapse All + Reset buttons
- `_create_iv_figure()`: auto-detects log scale via `_should_use_log_scale()`
- PNG export: Plotly modebar with 2x scale for high-res output
- Auto-resize on `<details>` toggle to fix Plotly layout in hidden containers
- Backward-compatible signature: `generate_dashboard(config, results_dir, output_path) -> Path`
- Preserved helpers: `_format_number_ranges()`, `_get_material_color()`, sweep annotations from `plotting.py`
