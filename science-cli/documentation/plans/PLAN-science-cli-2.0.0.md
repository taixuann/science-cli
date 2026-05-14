# PLAN: science-cli 2.0.0 — TUI, Extension Integration, Plotly Dashboard

## Classification
major-release

## Related Plans
- [[PLAN-command-restructure]] — **supersedes** — this PLAN incorporates command restructuring
- [[PLAN-config-expansion]] — **supersedes** — this PLAN incorporates config expansion
- [[PLAN-extension-interface]] — **supersedes** — this PLAN incorporates extension interface
- [[PLAN-version-bump]] — **supersedes** — this PLAN IS the version bump to 2.0.0

## Status
- **Created**: 2026-05-13
- **Status**: draft
- **Branch**: mysci-tui

## Objective

Three major goals:
1. **Rebuild TUI** — Textual TUI was deleted (only `.pyc` remains). Rebuild with SCI banner, matcha green theme, two-column header, command separators, slash commands.
2. **Integrate extensions as main library** — science-iv and science-electrochem source is deleted (only `.pyc`). science-memristor is intact. Merge extension functionality into science-cli core as a unified library.
3. **Plotly Dashboard** — Replace SVG-based dashboard with interactive Plotly dashboard that opens directly as `dashboard.html` (no server needed).

## Context

### Current State
- **science-cli**: v7.0.0, 13 commands, prompt_toolkit REPL (no TUI source)
- **science-memristor**: Fully intact extension (8 source files, dashboard generator, plotting, analysis)
- **science-iv**: Source DELETED — only `.pyc` in `__pycache__/`
- **science-electrochem**: Source DELETED — only `.pyc` in `__pycache__/`
- **TUI**: Source DELETED — only `.pyc` in `__pycache__/`
- **Dashboard**: Static HTML with SVG images, works with `file://` protocol

### Design Constraints
- Keep code modular and flat
- Avoid unnecessary abstraction layers
- Prefer readable scientific Python over enterprise architecture
- Use dataclasses or simple models only when needed
- NO authentication, databases, servers, APIs, or microservices
- Prefer filesystem-based workflows
- Use parquet for processed data
- Preserve raw measurements unchanged
- Manual corrections stored separately from extracted features
- Dashboard opens as `dashboard.html` — no local server
- All interactions inside standalone HTML using Plotly interactivity
- Prioritize: fast iteration, scientific debugging, visual verification, extraction transparency
- Do NOT optimize prematurely

---

## Phase 1: Version Bump + Branch Setup

### 1.1 Branch
- Create and switch to branch `mysci-tui`

### 1.2 Version Changes
| File | Current | New |
|------|---------|-----|
| `src/science_cli/__init__.py` | `"7.0.0"` | `"2.0.0"` |
| `pyproject.toml` | `version = "7.0.0"` | `version = "2.0.0"` |

### 1.3 Dependencies
Add to `pyproject.toml`:
```toml
"plotly>=5.0",
"textual>=0.40",
"pyarrow>=10.0",  # for parquet support
```

---

## Phase 2: Rebuild TUI (Textual)

### 2.1 TUI Architecture
**File**: `src/science_cli/tui/app.py`

Rebuild from session notes (`session-scienc-cli tui.md`):
- ASCII "SCI" banner at top
- Two-column header:
  - Left: context `(sci project/proto) v2.0.0`
  - Right: workflow `1.project 2.protocol 3.data 4.plot`
- Matcha green theme:
  - Background: `#1a1f1a`
  - Accent: `#8BAA89`
  - Borders: `#4A7A4A`
- Timestamped command separators (`--- HH:MM:SS ---`)
- Slash commands: `/help`, `/clear`, `/history`, `/version`
- Bare `sci` (no args) launches TUI instead of `sci --repl`

### 2.2 TUI Components
```
src/science_cli/tui/
├── __init__.py
├── app.py              # Main Textual App
├── header.py           # Two-column header widget
├── banner.py           # ASCII SCI banner
├── input_bar.py        # Command input with timestamp separators
├── output_panel.py     # Scrollable output display
└── theme.py            # Matcha green color scheme
```

### 2.3 TUI Command Dispatch
- TUI dispatches to same COMMAND_TREE handlers as CLI
- Output captured and displayed in output panel
- Session history persisted to `session.json`

---

## Phase 3: Integrate Extensions into Core

### 3.1 Merge science-memristor into core
Move from `tools/extensions/science-memristor/` into `src/science_cli/`:

```
src/science_cli/
├── memristor/
│   ├── __init__.py          # Extension registration (keep for compat)
│   ├── device.py            # DeviceConfig, MatrixPoint, etc.
│   ├── device_cli.py        # CLI commands (init, ls, add, info, sync, etc.)
│   ├── dashboard.py         # HTML dashboard generator (REPLACE with Plotly version)
│   ├── endurance.py         # Endurance analysis (Weibull fit, failure detection)
│   ├── retention.py         # Retention analysis (log-time, power-law models)
│   ├── switching.py         # Switching analysis (Weibull, KS test)
│   ├── models.py            # SwitchingData, EnduranceData, RetentionData
│   └── plotting.py          # IV SVG generation, CSV parsing
```

### 3.2 Rebuild science-iv from .pyc — ✅ COMPLETE
Recovered via `dis.dis()` bytecode analysis (uncompyle6 3.9.3 doesn't support Python 3.11 bytecode).

**Recovered into `src/science_cli/iv/`:**
- `models.py`: `IVData` dataclass (voltage, current, filename, metadata) with `resistance`, `compliance`, `on_off_ratio` properties
- `analyze.py`: 10 functions — `extract_resistance`, `extract_scan_rate`, `extract_breakdown_voltage`, `fit_iv_curve`, `_fit_ohmic`, `_fit_schottky`, `_fit_sclc`, `_fit_pool_frenkel`, `extract_on_off_ratio`, `detect_sweep_segments`
- `__init__.py`: Extension registration (3 techniques: iv-sweep, iv-breakdown, iv-leakage) with analyzers, plot presets, column maps

All imports updated from `science_iv` to `science_cli.iv` namespace.
All function signatures and return values verified against bytecode.

### 3.3 Rebuild science-electrochem from .pyc (best effort)
Same approach as science-iv. Key techniques: CV, CA, EIS.

### 3.4 Unified Extension Registry
Update `extensions.py` to support:
- Core techniques (built-in): iv-sweep, iv-breakdown, iv-leakage, mem-*, ec-*
- External extensions (entry points): still supported for future plugins
- `short_name` and `subcommands` for `ext` interface

### 3.5 Command Interface
```bash
# Unified extension dispatch
memristor init
  
memristor ls
  
memristor dashboard

memristor plot --all

# Backward compat (deprecated, still works)
memristor init
memristor ls
memristor dashboard
memristor plot --all
```

---

## Phase 4: Plotly Dashboard (Replace SVG Dashboard)

### 4.1 Dashboard Architecture
**File**: `src/science_cli/memristor/dashboard.py` (replace existing)

Generate self-contained `dashboard.html` with:
- **Plotly.js** embedded via CDN (or inline for offline use)
- **No server required** — works with `file://` protocol
- **Interactive features**:
  - Zoom, pan, hover tooltips on all plots
  - Click matrix cell → scroll to and expand that cell's details
  - Filter by material, sweep type, cycle range
  - Toggle plot visibility
  - Export individual plots as PNG

### 4.2 Dashboard Layout

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

### 4.3 Plotly Integration
- Use `plotly.io.to_html()` with `include_plotlyjs='cdn'` for each IV curve
- Embed as `<div>` elements inside the HTML
- Each plot gets a unique ID for filtering/interaction
- JavaScript handles:
  - Matrix cell click → expand `<details>` + scroll
  - Filter bar → show/hide plots by material/sweep type
  - Number range formatting (e.g., `#1-18`)

### 4.4 Data Flow
```
devices.yaml → read device config
results/*.txt → read raw CSV data (preserve unchanged)
     ↓
Plotly figures generated inline (no SVG intermediates)
     ↓
dashboard.html written to results/
     ↓
User opens dashboard.html in browser (file://)
```

### 4.5 Dashboard Features
1. **Per-material matrix grids** — crossbar array visualization, clickable cells
2. **Click-to-expand** — `<details>` elements per cell position
3. **Interactive Plotly plots** — zoom, pan, hover, export
4. **Filter bar** — filter by material, sweep type, cycle range
5. **Number range formatting** — `#1-18` instead of `1,2,3,...,18`
6. **Material color coding** — consistent colors across dashboard
7. **Works offline** — Plotly.js embedded or cached
8. **Fast generation** — no intermediate SVG files needed

---

## Phase 5: Command Restructuring (Incorporated)

### 5.1 Command Changes
| Old Command | New Command |
|-------------|-------------|
| `project list` | `ls -m project` |
| `project open <name>` | `open -m project <name>` |
| `project create` | `add -m project <name>` |
| `project status` | `status -m project` |
| `project migrate` | **removed** |

### 5.2 New Commands
- `close -m step|protocol|project` — close context with auto-save
- `open -m step <step_id>` — open specific step
- `ext <name> <subcommand>` — unified extension interface
- `memristor` — direct command (integrated as built-in)

### 5.3 3-Level State Memory
Session state expanded with `project_state` and `protocol_state` for auto-save/restore.

---

## Phase 6: Parquet Support for Processed Data

### 6.1 Processed Data Storage
- Raw measurements: preserve unchanged in original format (`.txt`, `.csv`)
- Processed/extracted features: store as `.parquet` files
- Manual corrections: stored separately (e.g., `corrections.yaml`)

### 6.2 File Structure
```
protocol/<name>/<step>/
├── results/
│   ├── dashboard.html          # Interactive Plotly dashboard
│   ├── features.parquet        # Extracted features (V_set, V_reset, R_HRS, R_LRS)
│   ├── corrections.yaml        # Manual corrections (separate from features)
│   └── analysis.json           # Analysis results (Weibull params, etc.)
└── devices.yaml                # Device configuration
```

---

## Files to Modify/Create

### Modify
| File | Action |
|------|--------|
| `src/science_cli/__init__.py` | Version → `"2.0.0"` |
| `pyproject.toml` | Version → `"2.0.0"`, add plotly/textual/pyarrow deps |
| `src/science_cli/app.py` | Bare `sci` launches TUI, `sci --repl` still works |
| `src/science_cli/core/technique.py` | Add `BUILTIN_TECHNIQUES`, `TechniqueDef`, `ColumnMap` (moved from extensions.py) |
| `src/science_cli/cli/commands/__init__.py` | Add `ext`, `close`, `status`; deprecate `memristor` |
| `src/science_cli/cli/commands/memristor.py` | Direct memristor command handler |
| `src/science_cli/core/session.py` | 3-level state memory |
| `src/science_cli/cli/commands/open_cmd.py` | Add `-m project`, `-m step` modes |
| `src/science_cli/cli/commands/ls_cmd.py` | Add `-m project` mode |
| `src/science_cli/cli/commands/add.py` | Add `-m project` mode |
| `src/science_cli/cli/help.py` | Update help text |
| `README.md` | Update for 2.0.0, TUI, Plotly dashboard |
| `src/science_cli/memristor/dashboard.py` | **REPLACE** with Plotly version |

### Create
| File | Purpose |
|------|---------|
| `src/science_cli/tui/__init__.py` | TUI package |
| `src/science_cli/tui/app.py` | Main Textual TUI |
| `src/science_cli/tui/header.py` | Two-column header widget |
| `src/science_cli/tui/banner.py` | ASCII SCI banner |
| `src/science_cli/tui/input_bar.py` | Command input |
| `src/science_cli/tui/output_panel.py` | Output display |
| `src/science_cli/tui/theme.py` | Matcha green theme |
| `src/science_cli/cli/commands/close.py` | Close handler |
| `src/science_cli/cli/commands/status.py` | Status handler |
| `src/science_cli/cli/commands/ext.py` | Extension dispatch |
| `src/science_cli/memristor/__init__.py` | Memristor package (moved from extension) |
| `src/science_cli/memristor/device.py` | Device models |
| `src/science_cli/memristor/device_cli.py` | Device CLI |
| `src/science_cli/memristor/endurance.py` | Endurance analysis |
| `src/science_cli/memristor/retention.py` | Retention analysis |
| `src/science_cli/memristor/switching.py` | Switching analysis |
| `src/science_cli/memristor/models.py` | Data models |
| `src/science_cli/memristor/plotting.py` | IV plotting |
| `src/science_cli/iv/` | ✅ Recovered from .pyc — 3 files (models, analyze, __init__) |
| `src/science_cli/electrochem/` | (recovered from .pyc) |
| `CHANGELOG.md` | 2.0.0 breaking changes |

---

## Dependencies

1. Phase 1 (version bump) → no deps
2. Phase 2 (TUI) → Phase 1
3. Phase 3 (extension integration) → Phase 1
4. Phase 4 (Plotly dashboard) → Phase 3 (memristor module in place)
5. Phase 5 (command restructuring) → Phase 1
6. Phase 6 (parquet) → Phase 3

---

## Test Strategy

1. `sci --version` → `2.0.0`
2. `sci` (no args) → launches TUI
3. `sci --repl` → still works
4. `memristor ls` → works

6. `memristor dashboard --open` → generates dashboard.html, opens in browser
7. dashboard.html opens with `file://` protocol, Plotly plots interactive
8. `close -m project` → auto-saves state
9. `open -m project <name>` → restores state
10. `test_guardrails.py` → all 16 tests pass
11. Verify parquet files generated for processed data
12. Verify raw measurements unchanged

---

## Progress

- [x] PLAN created ✅
- [x] User approved ✅
- [x] Phase 1: Version bump + branch setup ✅ (`315bb1f`)
- [x] Phase 2: Rebuild TUI ✅ (`9b20605`, `6a4655c`)
- [x] Phase 3a: Merge science-memristor into core ✅ (`9b20605`)
- [x] Phase 3b: Recover science-iv from .pyc ✅ (`682b9a3`)
- [x] Phase 3c: Rebuild science-electrochem from .pyc ✅ (`9b20605`)
- [x] Phase 4: Plotly dashboard ✅ (`c6196ad`)
- [x] Phase 5: Command restructuring ✅ (`9b20605`)
- [x] TUI CSS fix: hardcoded color values in DEFAULT_CSS ✅ (`6a4655c`)
- [x] extensions.py: silent skip of non-callable entry points ✅ (`72f2e8a`)
- [x] _TeeWriter class for fzf output capture during TUI suspend ✅ (this commit)
- [x] plot.py fzf: step/protocol display + raw_dir preview path ✅ (this commit)
- [x] Phase 6: Parquet support ✅ (`8708b9a`)
- [x] TEST passed: 16/16 guardrails ✅
- [x] DOCS updated ✅
- [x] COMMIT done ✅

## Post-2.0.0 Changes (Sprint 2 — mysci-tui_update)

The following changes were made after the master plan was marked complete:

### Command Restructure Refinements
- Removed `project`, `extensions`, `memristor` from COMMAND_TREE entirely (no deprecation aliases)
- Re-grouped commands: GROUP 1 (add/delete/edit/ls), GROUP 2 (open/close), GROUP 3 (plot/analyze/config/status/results), GROUP 4 (ext/techniques)
- `ext` is now the ONLY way to access memristor/extension commands

### TUI Enhancements
- Added TechniquesBox widget next to ASCII art in banner (reads merged config)
- Removed TuiHeader from compose
- REPL prompt simplified to `sci>`

### CLI Simplification
- Removed all `--filter` CLI flags — `--fzf` is the only interactive selection method
- `add -m data` already uses symlinks (verified)

### Current Command Groups (post-Sprint 2)
```
GROUP 1: FILE MANAGEMENT
  add                     Add project/protocol/metadata/data
  delete                  Delete protocol/metadata
  edit                    Edit protocol/metadata
  ls                      List projects/protocols/steps/files

GROUP 2: CONTEXT NAVIGATION
  open                    Open project/protocol/step
  close                   Close context with auto-save

GROUP 3: DATA ANALYSIS
  plot                    Plot data
  analyze                 Analyze data
  config                  Configure settings
  status                  Show current context status
  results                 List saved results

GROUP 4: EXTENSIONS & TECHNIQUES
  ext                     Unified extension interface
  techniques              List available techniques

ADDITIONAL
  help, version, clear, history
```

## Cross-PLAN Update (2026-05-13)
- **Sprint 2 Complete**: Help menu restructured (4 groups), `project`/`extensions`/`memristor` top-level commands removed, memristor now direct command. PLAN-command-restructure and PLAN-extension-interface marked superseded.
- **Sprint 3 Complete**: Cross-protocol dashboard implemented (`dashboard --all`, stacked heatmaps, material filter, `analysis_data.json` cache). See [[PLAN-enhanced-dashboard]] for details.
- **PLAN-2 (Config Expansion)**: Completed — technique config files in `~/.config/science-cli/techniques/*.yaml`, `config set technique`, `config edit`, `config list techniques`, `config list devices` subcommands.
- **PLAN-4 (Version Bump)**: Completed — version 2.0.0 already set, CHANGELOG.md created.
- **Phase 6 (Parquet)**: Completed — `core/parquet_store.py` with `write_features()`, `read_features()`, `append_features()`, `list_feature_files()`, `feature_metadata()`.

## Cross-PLAN Update (2026-05-14)
- **Sprint 5 Proposed**: Techniques → Config Integration added to [[PLAN-enhanced-dashboard]] as Sprint 5. Features F6 (`config set techniques`) and F7 (enhanced `config list techniques` with per-cell device config display) are proposed to reduce the standalone `techniques` command. See Sprint 5 in PLAN-enhanced-dashboard.md for details.
- **GROUP 4 impact**: The `techniques` command in GROUP 4 (Extensions & Techniques) may be deprecated or reduced once Sprint 5 is implemented. This affects the command listing in this PLAN's "Current Command Groups" section.

## Cross-PLAN Update (2026-05-14) — Sprint 6
- **Sprint 6 Proposed**: SQLite Query Cache added to [[PLAN-enhanced-dashboard]] as Sprint 6. New `db.py` module for SQLite schema/CRUD, dual-write on `memristor sync` (YAML + SQLite), SQLite read path in dashboard. New file: `src/science_cli/memristor/db.py`. See Sprint 6 in PLAN-enhanced-dashboard.md for details.
- **Data flow impact**: `analysis_data.json` (Sprint 3) remains the analysis cache with mtime tracking; SQLite becomes the read-optimized query cache. Both populated during sync.
- **No command group changes**: Sprint 6 adds no new CLI commands — all behavior is internal to `memristor sync` and `dashboard`.
