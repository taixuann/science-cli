# PLAN: Enhanced Memristor Dashboard

## Classification
feature

## Related Plans
- [[PLAN-plotly-dashboard]] — supersedes — the Plotly dashboard was Phase 1; this PLAN enhances it
- [[PLAN-science-cli-2.0.0]] — affects — Sprint 2 command restructuring updates the master plan groups
- [[PLAN-command-restructure]] — supersedes — command restructure is now fully implemented and superseded by Sprint 2
- [[PLAN-extension-interface]] — affects — GROUP 4 changed (removed extensions/memristor commands)

## Status
- **Created**: 2026-05-13
- **Status**: **COMPLETED (Sprint 1-8)** — Global Config Registry, sync/analyze split, SQLite auto-construction
- **Branch**: `refactor/2.1.0`

## Objective
Replace `dashboard.py` with the dark-themed interactive Plotly dashboard design from `documentation/memristor_dashboard_layout.html`, wired to real IV data from `devices.yaml`. Add Keithley 2400 / tab-separated data format support, Vset/Vreset extraction (both abrupt and gradual switching detection), user-configurable V_read parameter, and ON/OFF ratio computation for the dashboard.

## Context
The existing `dashboard.py` generates a light-themed dashboard with per-cell `<details>` sections, material matrix tables, and a filter bar. The reference design (`documentation/memristor_dashboard_layout.html`) shows a sophisticated dark-themed dashboard with sidebar navigation, KPI cards, clickable crossbar heatmap, device explorer with tabs, histograms, cycle evolution, confidence panel, and a review table.

Data files are in **tab-separated tab-separated format** from a Keithley 2400 sourcemeter:
- Key-value metadata headers delimited by `***End_of_Header***`
- Column 0 (X_Value / index) = row counter, skipped
- Column 1 (Untitled) = Voltage (V)
- Column 2 (Untitled 1) = Current (A)
- Column 3 (Untitled 2) = Timestamp (s)
- Column 4 (Comment) = ignored

The user wants:
1. Full dark-theme dashboard layout from mockup (Phase 1: IV panels data-driven, cycle/confidence/review as placeholders)
2. `.csv/.txt` file format reader with Keithley 2400 auto-detection
3. Vset/Vreset extraction from IV sweeps (derivative-based detection)
4. V_read auto-detection and ON/OFF ratio computation
5. All wired into dashboard KPIs, heatmap, histograms, and IV overlay

## Specification

### A. tab-separated Format Handler — `plotting.py`

New function `read_iv_csv()`:

1. **Header parsing**: Scan line-by-line for `***End_of_Header***` markers to find the two header blocks
   - Block 1: General metadata (Separator, Decimal_Separator, Date, Time, Operator)
   - Block 2: Channel info (Channels, Samples, X0, Delta_X)
2. **Column detection**: After 2nd `***End_of_Header***`, read column header line
   - `X_Value` = row index (skip)
   - `Untitled` = Voltage (V)
   - `Untitled 1` = Current (A)
   - `Untitled 2` = Timestamp (s)
   - `Comment` = ignore
3. **Data reading**: Parse tab-separated numeric data rows
4. **Return**: `(voltage, current, metadata)` where metadata includes date/time/operator from header
5. **Auto-detection**: Detect ``"tab-separated measurement"`` in first line of file; `read_iv_csv()` routes to this automatically

Column mapping logic:
- By position: col0=skip, col1=Voltage, col2=Current, col3=Timestamp, col4=Comment
- If file has < 3 data columns: raise ValueError
- Multi-Headings=Yes means 2 header blocks; read past both

### B. Keithley 2400 Device Config — `core/config.py` + `techniques`

Add hardcoded device entry for `keithley-2400` under `iv-sweep`:

```python
_DEFAULT_TECHNIQUE_DEVICES = {
    "iv-sweep": {
        "keithley-2400": {
            "delimiter": "\t",
            "decimal": ".",
            "header_lines": 23,  # 2 header blocks + column line
            "encoding": "utf-8",
            "columns": {
                "voltage": "Untitled",
                "current": "Untitled 1",
                "time": "Untitled 2",
            },
        },
    },
}
```

Add `iv-sweep` patterns for `.csv/.txt` files:
```python
"iv-sweep": [
    r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_",
    r"\.csv/.txt$",  # ← add tab-separated measurement format
]
```

### C. IV Parameter Extraction — `switching.py`

New functions for switching parameter detection:

**`detect_vset(voltage, current, v_read=0.1)`** → `float | None`
- Split bipolar sweep into forward (0→+Vmax) and backward (+Vmax→0) branches using reversal detection (reuse `_split_at_reversals()`)
- **Combined detection method** (catches both abrupt and gradual transitions):
  1. *Derivative method*: Compute d(log10|I|)/dV, find max (abrupt switching)
  2. *Threshold method*: Find where |I| exceeds baseline × threshold factor (gradual switching)
  3. Use the earlier (lower-voltage) result as Vset — this captures the onset of switching whether abrupt or gradual
- Return the switching voltage, or None if neither method detects clear switching

**`detect_vreset(voltage, current, v_read=0.1)`** → `float | None`
- Operates on negative sweep segments (0→-Vmax)
- Combined detection (derivative min + current drop threshold)
- Return reset voltage or None

**`compute_on_off_ratio(voltage, current, v_read=0.1)`** → `dict`
- `v_read` is user-settable (default 0.1V); no auto-detection
- Split sweep into forward (0→+Vmax) and backward (+Vmax→0) branches
- Interpolate current at v_read on both branches
- Forward branch current = I_off (device in HRS before switching)
- Backward branch current = I_on (device in LRS after switching)
- Compute: R_on = v_read / I_on, R_off = v_read / I_off, ratio = R_off / R_on
- Return: `{"v_read": float, "i_on": float, "i_off": float, "r_on": float, "r_off": float, "ratio": float}`

**`extract_iv_parameters(voltage, current, v_read=0.1)`** → `dict`
- Convenience wrapper calling detect_vset, detect_vreset, compute_on_off_ratio
- Returns: `{"v_set": ..., "v_reset": ..., "on_off_ratio": ..., "v_read": ..., "switching_detected": bool}`

### D. Enhanced Dashboard — `dashboard.py` (full rewrite)

**Architecture**: Same `generate_dashboard(config, results_dir, output_path)` API.

**Data Collection** (Phase 1 — IV-driven):
| Panel | Data Source | Real Data? |
|-------|------------|------------|
| KPI: Cells | `config.measured_cells / total_cells` | Yes |
| KPI: IV Files | `config.get_all_files("iv")` + file count | Yes |
| KPI: Materials | `get_points_by_material()` | Yes |
| KPI: Median Vset | `detect_vset()` across all devices | Yes |
| KPI: Median Vreset | `detect_vreset()` across all devices | Yes |
| KPI: ON/OFF Ratio | `compute_on_off_ratio()` across all devices | Yes |
| KPI: Yield | Fraction of cells with switching detected | Yes |
| Heatmap | Per-cell switching metric (ON/OFF ratio / yield / Vset / Vreset) | Yes |
| IV Overlay | All IV sweeps for selected cell via `read_iv_csv()`/`read_iv_csv()` | Yes |
| Histograms | Vset, Vreset, ON/OFF ratio distributions | Yes |
| Cycle Evolution | Empty placeholder panel | Placeholder |
| Confidence | Empty placeholder panel | Placeholder |
| Review Table | Empty state | Placeholder |

**Layout** (exact mockup fidelity, all sections rendered):
```
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR (240px)  │  HEADER (selectors, search, export) │
│ ┌──────────────┐ │  ┌─────────────────────────────────┐│
│ │ Logo/Title   │ │  │ KPI Row (4 metric cards)        ││
│ │ Navigation   │ │  ├─────────────────────────────────┤│
│ │ Filters      │ │  │ Heatmap     │  Device Explorer  ││
│ │ Color Map    │ │  │ (clickable) │  (IV Overlay tab) ││
│ │ Device Info  │ │  ├─────────────────────────────────┤│
│ │ Review Queue │ │  │ Vset Hist  │ Vreset Hist │ Ratio││
│ │ Summary      │ │  ├─────────────────────────────────┤│
│ │ Quick Actions│ │  │ Cycle Evo  │  Confidence        ││
│ └──────────────┘ │  ├─────────────────────────────────┤│
│                   │  │ Review Table (empty state)     ││
└─────────────────────────────────────────────────────────┘
```

**CSS**: Full dark theme from mockup
- CSS variables: `--bg-deep: #050a14`, `--cyan: #00d4ff`, `--blue: #3b82f6`, etc.
- Fonts: JetBrains Mono (mono), DM Sans (UI) via Google Fonts CDN
- Sidebar, header, KPI cards, panels, tables, scrollbar styling
- Plotly transparent backgrounds + custom config
- Animations: glow pulses, hover transitions

**JavaScript**: Interactive elements from mockup
1. **Heatmap click → update all panels**: Click a cell on the heatmap → updates Device Info sidebar, IV Overlay plot, device badge, selected cell label
2. **Tab switching**: IV Overlay tab active; Extracted Params / Cycle Evo / Raw Data tabs show placeholder content
3. **Heatmap metric selector**: Dropdown to color heatmap by ON/OFF ratio / Vset / Vreset / Yield
4. **Sidebar filters**: Measurement Type, Material, Cycle Range sliders, Sweep Direction, Compliance, toggles (log scale, overlay mode, highlight outliers) — wired to show/hide plot-figure elements
5. **Color Map By radio**: Radio group for heatmap coloring metric
6. **Search box**: Filter device cells by ID

All JS interacts with pre-rendered Plotly divs (show/hide, no re-render needed for tab switching). Heatmap click triggers Plotly.relayout/restyle for selected cell highlight.

### E. `switching.py` — Add `analyze_all_devices()`

New function to batch-process all IV files in a `DeviceConfig`:

```python
def analyze_all_devices(config, results_dir) -> dict:
    """Run switching analysis across all IV files in config.
    
    Returns dict with:
      - per_device: { (row, col): { v_set, v_reset, ratio, ... } }
      - aggregate: { median_vset, median_vreset, median_ratio, yield_pct }
      - histograms: { vset_bins, vreset_bins, ratio_bins }
    """
```

This feeds directly into the dashboard's KPI cards, heatmap, and histograms.

## Sprint 2 Results

- **Items 1, 2, 4, 5 implemented and committed**: Help menu restructured (4 groups, removed project/extensions/memristor), TUI banner with TechniquesBox, TuiHeader removed, REPL prompt simplified, `--filter` CLI flags removed (fzf only), `add -m data` already uses symlinks.
- **Test status**: 16/16 tests passing, GREEN status.
- **Item 5 (add symlink)**: Already implemented — `add.py:386-388` uses `link.symlink_to(src)`.
- **Open items for discussion**: 
  - Item 3: config unification (deferred)
  - Item 6: devices.yaml routing (see Sprint 3)
  - Item 7: distribution (keep simple — pip install)

## Sprint 3 Results

- **Items 1–6 implemented and committed**: Cross-protocol data collector (`collect_cross_protocol_data`), `analysis_data.json` cache with mtime tracking, `--all` / `--force` CLI flags, per-protocol stacked heatmaps, material filter, toggleable Vset/Vreset markers on IV overlay.
- **Test status**: 16/16 guardrail tests passing + integration tests GREEN.
- **Key design decisions**:
  - `analysis_data.json` stored at `project/results/` with file mtime tracking — enables incremental re-analysis
  - Per-protocol heatmaps rendered as stacked sections rather than unified grid (handles different matrix sizes)
  - Material filter works globally across all protocols
  - Vset/Vreset toggle switches added above IV overlay panel
  - HTML is self-contained, same dark theme as per-protocol dashboard
  - Filename pattern unified to `DDMMYY_material_type_matrix_suffix` only — non-matching files trigger rename reminder
  - `project.py` deleted (dead code, no imports reference it)

## Sprint 3: Cross-Protocol Dashboard

**Goal:** Create a single project-level dashboard at `project/results/dashboard.html` that aggregates data from ALL protocols instead of per-protocol dashboards.

**Key design decisions:**
- Single main dashboard at `project/results/dashboard.html`
- Scans all protocols' `devices.yaml` files
- Material-based filtering for analysis (only analyze files matching selected materials via `extract_material_batch()`)
- Heatmap rendered from each protocol's `devices.yaml` matrix definition (rows, cols, row_labels, col_labels). Different matrix sizes per-protocol are rendered as stacked per-protocol heatmaps, not one unified grid.
- Saves intermediate `project/results/analysis_data.json` with per-file extracted parameters for fast loading

**devices.yaml role (from discussion):**
- **devices.yaml = matrix MAP only**: defines grid structure (rows, cols, labels), which cells exist and are measured, technique-to-step mapping (steps.iv, etc.), and two sweep properties per file: sweep direction + sweep rate (populated by `sync`). No Vset/Vreset/ratio stored here.
- **Filename parsing = auto-discovery**: filenames follow **`DDMMYY_material_type_matrix_suffix` ONLY** (e.g., `0605_Ta-PDA-ITO_r0c0_iv_set.csv`). Parsing extracts material, sweep type, matrix position. Non-matching files → CLI reminds user to rename.
- **Analysis results (Vset, Vreset, ratio) = computed in `analysis_data.json`**: Run analysis on ALL files (batch). User inspects results on dashboard. For specific files needing recalibration, use a per-file command to re-analyze and update the JSON.
- **Source truth**: raw CSV files in the step directory. Never modified. All derived data is in `results/` directory.

**Analysis data structure (analysis_data.json):**
```json
{
  "files": [
    {
      "filepath": "protocol/<name>/<step>/results/iv_r0c0_set.svg",
      "material": "Ta-PDA-ITO",
      "v_set": 0.857,
      "v_reset": -0.534,
      "i_set": 1.2e-4,
      "i_reset": 8.5e-5,
      "on_off_ratio": 1.37,
      "row": 0, "col": 0,
      "protocol": "<protocol_name>"
    }
  ]
}
```

**Dashboard features:**
- Histogram distribution of Vset, Vreset, ON/OFF ratio (filterable by material)
- Matrix heatmap showing per-cell switching yield and median Vset values
- IV curve overlay panels with toggleable Vset/Vreset markers and read-point dots
- KPI cards (total files, devices with switching, yield %, median Vset/Vreset)
- Material selector filter dropdown

**Implementation approach:**
- New command: `sci dashboard --all` or restructure existing `memristor dashboard` to accept `--all`

- Cross-protocol data collector scanning all `devices.yaml` in all protocol dirs
- Analysis data file writer (JSON) saved to `project/results/`
- Updated Plotly dashboard HTML consuming aggregated JSON data

**JSON cache invalidation:**
- Store file modification timestamps in `analysis_data.json` alongside extracted parameters
- On dashboard regenerate: compare mtimes — only re-analyze changed/new files
- `--force` flag forces full re-analysis
- If `analysis_data.json` doesn't exist, analyze all files

**Known limitations from earlier sprints:**
- iv_reset files produce inverted ON/OFF ratios (WONTFIX — data organization issue)
- analyze_all_devices' per_device dict overwrites on each file (only stores last file's params per device)

## Gaps & Flaws Analysis

### 1. Data Flow: CSV → Analysis → JSON → Dashboard
- **Risk**: LOW. Clean flow exists: `read_iv_csv()`/`read_iv_lvm()` → `extract_iv_parameters()` → dict → JSON serialization. The JSON intermediate file is new but follows the existing pattern.
- **Mitigation**: Validate JSON schema against analysis_data.json structure before dashboard loading.

### 2. Performance with Large Datasets (100-1000+ files)
- **Risk**: MEDIUM. Re-analyzing all IV files on every dashboard regeneration could be slow for 1000+ files (each file requires full IV curve parsing + derivative computation).
- **Mitigation**: JSON intermediate file enables incremental updates — only re-analyze files whose modification time has changed. Add `--force` flag to force full re-analysis.

### 3. devices.yaml Role (RESOLVED)
- **Decision**: devices.yaml = matrix MAP only with sweep direction + sweep rate. No Vset/Vreset/ratio in YAML. Analysis goes to `analysis_data.json`. Filenames follow `DDMMYY_material_type_matrix_suffix` only — non-matching files get a rename reminder.

### 4. JSON Cache Invalidation Strategy
- **Risk**: MEDIUM. analysis_data.json becomes stale when new data files are added or existing ones modified.
- **Mitigation**: Store file modification timestamps in JSON. On dashboard regenerate, compare timestamps — only re-analyze changed files. Add `--force` flag for full re-analysis. Per-file recalc via `memristor analyze --row 0 --col 0 --file X.csv` updates the JSON in-place.

### 5. Cross-Protocol Matrix Heterogeneity (ACCEPTED)
- **Risk**: MEDIUM-HIGH. Different protocols use different matrix sizes/labels. This is expected — not a bug.
- **Mitigation**: Render per-protocol heatmaps stacked vertically with protocol headers. Protocol selector filter limits which are visible. No attempt to unify into one grid.

### 6. Cross-Plan References Outdated
- **Risk**: HIGH. PLAN-science-cli-2.0.0 still references `memristor` alias (removed in Sprint 2), old GROUP 4 with `extensions` command, and incomplete progress. PLAN-command-restructure and PLAN-extension-interface also reference old groups.
- **Mitigation**: Update PLAN-science-cli-2.0.0 to reflect Sprint 2 changes. Mark PLAN-command-restructure as superseded/complete.

### 7. `project` Handler Orphan File
- **Risk**: LOW. `src/science_cli/cli/commands/project.py` still exists on disk but is no longer imported in COMMAND_TREE. Not harmful but misleading.
- **Mitigation**: Either delete it or add a deprecation warning.

### 8. `plot` Command Save Path Verification
- **Risk**: LOW. `_get_results_dir()` in `plot.py:58` already checks session context for protocol/step and saves to `protocol/<name>/<step>/results/` when context is active. Falls back to `project/results/` otherwise. Already satisfies Item 8.
- **Mitigation**: Document this behavior in help text so users know to `open -m protocol` + `open -m step` before plotting.

### 9. Filename Pattern Auto-Parsing (DDMMYY_material_type_matrix_suffix)
- **Risk**: LOW. The `extract_material_batch()` function in `plotting.py` already parses material from filenames. But the row/col auto-detection from the `_rNcN_` or `_b#-t#_` patterns is only partially implemented in `device.py`'s `_parse_canonical_filename()`.
- **Mitigation**: Extend filename parsing to auto-populate row/col during `sync` so manual `devices.yaml` entry requires minimal config.

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | **Rewrite** | Replace with new dark-themed interactive dashboard |
| `src/science_cli/memristor/plotting.py` | **Add** `read_iv_csv()` + route detection in `read_iv_csv()` | Support Keithley 2400 tab-separated measurement format |
| `src/science_cli/memristor/switching.py` | **Add** `detect_vset()`, `detect_vreset()`, `compute_on_off_ratio()`, `detect_read_voltage()`, `analyze_all_devices()` | IV parameter extraction for dashboard |
| `src/science_cli/core/config.py` | **Add** keithley-2400 hardcoded device defaults, `.csv/.txt` pattern to iv-sweep | Auto-detection of tab-separated measurement format |
| `documentation/plans/PLAN-enhanced-dashboard.md` | **Create** | This plan |
| `src/science_cli/memristor/dashboard.py` | **Modify** | Add `--all` flag, cross-protocol collector, JSON writer |
| `src/science_cli/memristor/device_cli.py` | **Modify** | Add `dashboard --all` CLI handler |

## Dependencies
- Existing `memristor/device.py` (DeviceConfig, FileEntry, MatrixPoint)
- Existing `memristor/plotting.py` (`read_iv_csv()`, `collect_iv_files()`, `_build_sweep_from_data()`)
- Existing `memristor/switching.py` (will add new functions)
- New: `detect_vset()`, `detect_vreset()` in switching.py
- Plotly.js 2.35.2 (CDN, same as current)
- Google Fonts CDN (JetBrains Mono, DM Sans)
- No new Python dependencies

## Test Strategy
1. **tabular reader**: Place a known `.csv/.txt` file in a test protocol dir, run `read_iv_csv()`, verify voltage/current arrays match expected values
2. **Vset/Vreset detection**: Feed synthetic IV data with known switching thresholds, verify detection within 5% accuracy
3. **ON/OFF ratio**: Verify computation matches manual calculation for simple cases
4. **Dashboard generation**: Run `memristor dashboard --open` on a real project with Keithley 2400 tab-separated data
5. **Visual comparison**: Verify layout matches `documentation/memristor_dashboard_layout.html`
6. **Interactivity**: Click heatmap cell → verify all panels update, tabs switch

## Progress

### Sprint 1: Initial Implementation (Completed)
- [x] IMPLEMENT: `read_iv_csv()` in plotting.py + auto-detection
- [x] IMPLEMENT: Keithley 2400 config in core/config.py
- [x] IMPLEMENT: `detect_vset()`, `detect_vreset()`, `compute_on_off_ratio()`, `detect_read_voltage()` in switching.py
- [x] IMPLEMENT: `analyze_all_devices()` in switching.py
- [x] IMPLEMENT: Dashboard data collection (per-device metrics)
- [x] IMPLEMENT: Dashboard Plotly figure generators (heatmap, IV overlay, histograms, sparklines)
- [x] IMPLEMENT: Dashboard HTML layout (sidebar, header, KPI row, panels, review table)
- [x] IMPLEMENT: Dashboard CSS (dark theme from mockup)
- [x] IMPLEMENT: Dashboard JavaScript (click-to-select, tabs, filters, search)
- [x] TEST: tabular reader with real Keithley 2400 data
- [x] TEST: Vset/Vreset detection with known test data
- [x] TEST: Dashboard generation on real project
- [x] TEST: All guardrail tests pass
- [x] COMMIT to `mysci-tui_update` branch

### Sprint 2: Help Menu, TUI, --filter removal (Completed)
- [x] Restructure COMMAND_TREE into 4 groups, remove project/extensions/memristor
- [x] Update help.py with new groupings, descriptions
- [x] Add TechniquesBox to TUI banner
- [x] Remove TuiHeader, simplify REPL prompt
- [x] Remove --filter CLI flags from device_cli.py and add.py
- [x] Verify add -m data uses symlinks
- [x] Update guardrail tests for 13 commands
- [x] All 16 tests pass, commit + push

### Sprint 3: Cross-Protocol Dashboard (Completed)
- [x] DESIGN: Full architecture review (gaps analysis above)
- [x] Cross-plan updates: PLAN-sci-2.0.0, PLAN-command-restructure, PLAN-extension-interface
- [x] IMPLEMENT: Cross-protocol data collector (scan all protocols' devices.yaml)
- [x] IMPLEMENT: JSON cache writer with mtime tracking + `--force` flag
- [x] IMPLEMENT: Dashboard `--all` flag and routing in device_cli.py
- [x] IMPLEMENT: devices.yaml → protocol/step mapping for CSV path resolution
- [x] IMPLEMENT: Per-protocol stacked heatmaps (handles different matrix sizes)
- [x] IMPLEMENT: Protocol selector filter dropdown
- [x] IMPLEMENT: Material filter in dashboard UI
- [x] IMPLEMENT: Toggleable Vset/Vreset markers + read-point dots on IV overlay
- [x] IMPLEMENT: Filename pattern auto-parsing for row/col (DDMMYY_material_type_matrix_suffix)
- [x] TEST: 2-protocol integration test with synthetic data
- [x] TEST: JSON cache invalidation (modify file, regenerate, verify updated values)
- [x] TEST: Backward compatibility (per-protocol dashboard still works)
- [x] TEST: All guardrail tests pass
- [x] Delete orphan project.py handler
- [x] COMMIT to `mysci-tui_update` branch

## Sprint 4: UX Enhancements & Workflow Polish

**Goal:** Improve the CLI user experience with smarter context-aware listing, polished output formatting, and streamlined file assignment workflow.

**Status**: Proposed (features approved, not yet implemented)

### Feature F1: Context Awareness — `open protocol` clears step, `ls` filters by level

**Problem:** After navigating between protocols, the lingering step context causes confusion. `ls` does not adapt its output to the current context level, forcing users to always specify `-m` flags.

**Solution:**

1. **`open -m protocol -n <name>` clears step context** — when opening a new protocol, set `last_step` to `null` in session state. If a step was previously open, it is reset so the user starts fresh in the protocol context.

2. **`ls` adapts to the current context level:**
   - **No project open**: list projects (equivalent to `ls -m project`)
   - **Project open, no protocol**: list protocols in current project
   - **Protocol open, no step**: list steps in current protocol
   - **Step open**: list files in current step
   - `ls -m project` / `-m protocol` / `-m step` remain available for explicit level selection overriding the default behavior

**Files affected:**
- `src/science_cli/cli/commands/open_cmd.py` — clear `last_step` on protocol open
- `src/science_cli/cli/commands/ls_cmd.py` — context-aware level detection
- `src/science_cli/core/session.py` — verify session clear works

### Feature F2: `add -m data` FZF Sorted File Display

**Problem:** When running `add -m data --fzf`, the FZF selector shows all files in the step directory without distinguishing already-assigned files from unassigned ones. Users must remember which files they've already added.

**Solution:**

When displaying the FZF file selection for `add -m data --fzf`:
1. **Unassigned files listed first** — sorted alphabetically, clearly separated
2. **Already-assigned files listed below**, grouped by step with step headers
   - Format: `── Step Name ──` header, followed by indented file list
   - Makes it easy to see where each file is already assigned
3. Selected files that are already assigned should be skipped or warned about

**Files affected:**
- `src/science_cli/cli/commands/add.py` — FZF input generation logic
- `src/science_cli/core/manifest.py` — query assigned files per step

### Feature F3: Rich Table Format for All `ls` Commands

**Problem:** `ls` output uses plain text formatting, making it hard to scan. Section titles, descriptions, and file counts lack visual distinction.

**Solution:**

All `ls` subcommands (`ls -m project`, `-m protocol`, `-m step`, `ls files`) use Rich table format with consistent styling:
- **Bold title row** for each section (e.g., "Projects", "Protocols", "Steps")
- **Grey/italic descriptions** underneath each entry
- **File count badges** (e.g., "3 files", "12 files") in dim style, right-aligned
- Consistent color scheme across all list types
- Works in both CLI mode and TUI mode

**Files affected:**
- `src/science_cli/cli/commands/ls_cmd.py` — Rich table rendering
- `src/science_cli/core/` — may need helper for file counting per protocol/step

### Feature F4: No Global File Search (`ls -m file` removed)

**Problem:** `ls -m file` attempts to scan the entire project tree for data files, which is slow and meaningless outside a protocol context. Files only make sense within a specific protocol+step.

**Solution:**
- `ls -m file` is **removed** — no global file-level listing
- Files are only listed within a protocol context:
  - `ls` when a step is open (context-aware from F1)
  - `ls files` (if such a subcommand exists, scoped to current context)
- If a user tries to list files without an open step, show a helpful message:
  - *"No step open. Use `open -m step -n <name>` to select a step, or `ls` to see available steps."*

**Files affected:**
- `src/science_cli/cli/commands/ls_cmd.py` — remove `-m file` handler
- Help text / `help.py` — remove `ls -m file` from documentation

### Feature F8: `results --fzf` — Open Results Files via FZF

**Problem:** `results` lists output files (plots, dashboards, CSVs) but users must manually navigate to and open them. No quick way to open a specific file from the list.

**Solution:**

1. **`results --fzf`** — pipe the results file list through FZF for interactive selection
2. On selecting a file, open it with the system default application (`open` on macOS, `xdg-open` on Linux)
3. Show file metadata in FZF preview (file size, last modified, type badge)
4. When `results` is called without a specific step filter (showing many files), default to `--fzf` mode automatically

**Files affected:**
- `src/science_cli/cli/commands/results.py` — add `--fzf` flag and FZF invocation logic
- `src/science_cli/core/fzf_utils.py` — may need helper for preview window config

### Feature F9: `results` Grouped Rich Display

**Problem:** `results` output is plain text — protocol/step boundaries are hard to scan. Files from different steps blend together.

**Solution:**

Display `results` output as a **grouped Rich table**:

1. **Protocol header** — bold cyan, shows protocol name
2. **Step subheaders** — bold yellow, beneath each protocol grouping
3. **Files indented under each step** — dimmed descriptions with file size badges
4. Consistent with F3 (`ls` table format) for visual uniformity

**Example output:**
```
📁 protocol/1_protocol-1
  ┌─ step-4 ──────────────────────────────────────────┐
  │  iv_r0c0_Ta-PDA-ITO_forming_01.svg      12.3 KB   │
  │  iv_r0c1_Ta-PDA-ITO_set_01.svg          14.1 KB   │
  │  iv_overlay.pdf                          89.2 KB   │
  │  dashboard.html                         132.5 KB   │
  └───────────────────────────────────────────────────┘
  ┌─ 5_end ───────────────────────────────────────────┐
  │  endurance_r0c0.svg                      45.6 KB   │
  └───────────────────────────────────────────────────┘
```

**Files affected:**
- `src/science_cli/cli/commands/results.py` — Rich table rendering with nested grouping
- `src/science_cli/core/` — may need helper for collecting results by protocol/step

### Sprint 4 Progress

- [x] PLAN: Sprint 4 section created (this document)
- [x] Feature F1: `open` clears step context, `ls` context-aware filtering
- [x] Feature F2: `add -m data` sorted FZF display (unassigned first, grouped by step)
- [x] Feature F3: Rich table formatting for `ls` (protocols and steps)
- [x] Feature F4: Remove global `ls -m file` with helpful redirect message
- [x] Feature F8: `results --fzf` — FZF file selection + system open
- [x] Feature F9: `results` grouped Rich display (protocol→step→files)
- [x] TEST: All guardrail tests pass (19/19)
- [x] COMMIT to `refactor/2.1.0` branch

**Sprint 4 Results:**
- `open_cmd.py`: `_open_protocol()` now clears step context via `set_last_step("")`
- `ls_cmd.py`: Context-aware default level (step→protocol→project→global), Rich Table for `_ls_protocol()` and `_ls_step()`, `-m file` redirects to `open -m step`
- `add.py`: FZF display shows unassigned files first (sorted), then files grouped by assigned step
- `results.py`: `--fzf` flag for interactive file opening via system default; Rich grouped display with protocol headers, step subheaders, and file size badges
- `help.py`: Removed `ls -m protocol --files` from docs

## Sprint 5: Techniques → Config Integration

**Goal:** Reduce the standalone `techniques` command by integrating techniques management into the `config` command. This consolidates technique listing, configuration, and device display under a single command namespace, eliminating the need for a separate command.

**Status**: Proposed (features approved, not yet implemented)

### Feature F6: `config set techniques` — Technique Configuration Under Config

**Problem:** The standalone `techniques` command provides listing and workflow guidance, but technique configuration (patterns, devices, defaults) is managed via separate `config set technique` and `config edit` subcommands. Users must use two different commands to understand and configure techniques. The standalone `techniques` command duplicates listing functionality that could live under `config list`.

**Solution:**

1. **`config set techniques`** — unified subcommand for setting technique configuration, aligned with the current `techniques` command's purpose. Accepts technique name and device arguments to set defaults, mirroring the existing `config set technique` behavior but positioned as the primary way to configure techniques.
2. **Standalone `techniques` command** — retains the same top-level listing (technique ID, label, description, filename patterns) but workflow guidance moves into `config`'s enhanced listing output
3. **Workflow guidance** — the step-by-step usage guide (steps 1-4) from the current `techniques` command moves into `config list techniques` output as a help section

**Files affected:**
- `src/science_cli/cli/commands/config.py` — enhance technique display, add workflow guidance to `config list techniques`
- `src/science_cli/cli/commands/techniques.py` — reduce to a thin wrapper/delegator or retain standalone listing with deprecation note
- `src/science_cli/cli/commands/__init__.py` — update COMMAND_TREE if needed
- `src/science_cli/cli/help.py` — update help text for both config and techniques

### Feature F7: `config list techniques` — Enhanced Tabular Display with Per-Cell Device Config

**Problem:** Current `config list techniques` (via `_cmd_list_techniques()`) shows only Technique, Config File, and Devices columns — devices are comma-separated in one field, making it hard to scan. It does not show filename patterns (glob/regex) or per-device config details (delimiter, column mappings). Users must run `config list devices <technique>` separately to see device details.

**Solution:**

Redesign `config list techniques` output as a Rich table with four columns:

1. **Technique ID** — the technique name (bold cyan)
2. **Filename Pattern** — glob/regex patterns for auto-detection, shown as a bulleted list per technique
3. **Device Config** — each device config entry displayed as a structured cell (one row per device per technique, or multiline cell), NOT comma-separated:
   - Device name in **bold**
   - Key config fields in dim style: delimiter, decimal separator, header_lines, encoding
   - Column mappings in green: `voltage → Untitled`, `current → Untitled 1`, etc.
   
   Example formatted cell:
   ```
   ┌─ keithley-2400 ─────────────────────────┐
   │ delimiter: \t | decimal: .              │
   │ header_lines: 23 | encoding: utf-8      │
   │ columns: voltage→Untitled               │
   │          current→Untitled 1             │
   │          time→Untitled 2                │
   └─────────────────────────────────────────┘
   ```
   
4. **Default Device** — which device is configured as default for the technique

**Layout option (per-device row):** If multiline cells are too wide, each device can be rendered as its own row with Technique ID repeated (or merged via row span), with a separate sub-column for "Device Name" to keep cells compact.

**Files affected:**
- `src/science_cli/cli/commands/config.py` — rewrite `_cmd_list_techniques()` with four-column design and per-cell device rendering
- `src/science_cli/core/config.py` — may need new helpers: `get_technique_patterns()`, `get_device_config_detail()` to return full device config dict for a technique
- `src/science_cli/core/technique.py` — ensure `BUILTIN_TECHNIQUES` patterns are accessible via core/config helpers

**Implementation notes:**
- Use Rich `Table` with `show_lines=True` and `header_style` for clear cell boundaries
- Device config cells should use Rich `Panel` or custom string formatting with consistent indentation
- Handle techniques with 0 devices gracefully (show empty cell)
- Handle techniques with 5+ devices (may need scrollable or expandable format — start with sorted alphabetical, add `… and N more` for >5)

### Sprint 5 Progress

- [x] PLAN: Sprint 5 section created (this document)
- [x] Feature F6: `config set techniques` — technique management under config
- [x] Feature F7: Enhanced `config list techniques` with per-cell device config display
- [x] DEPRECATE: standalone `techniques` command functions absorbed into config
- [x] DOCS: Help text updated for `techniques` and `config list`
- [x] TEST: All guardrail tests pass
- [x] COMMIT to `refactor/2.1.0` branch

**Sprint 5 Results:**
- `config list techniques` now shows 4-column Rich table (Technique ID, Patterns, Device Config per-device rows, Default Device)
- Workflow guidance Panel added below table
- `config set techniques` added as alias for `config set technique`
- `techniques` command converted to thin wrapper with deprecation notice → delegates to `config list techniques`
- `core/config.py` added `get_technique_config()`, `get_device_config_detail()` helpers
- Help text updated for both `config` and `techniques` throughout
- All imports verified working
- Commit: `7a77772`

## Sprint 6: SQLite Query Cache

**Goal:** Add a SQLite query cache layer for fast dashboard/analysis reads. Dual-write on `memristor sync`: YAML remains the human-editable source of truth; SQLite provides a read-optimized machine-readable cache.

**Status**: Proposed (features approved, not yet implemented)

### Architecture

- **Dual-write on `memristor sync`**: YAML (human-editable) + SQLite (machine-readable)
- **SQLite file**: `<project_name>.db` at project root (e.g., `test-project.db` next to `sci-config.yaml`)
- **YAML stays** the source of truth for human editing
- **SQLite** is the read-optimized query cache for dashboard and analysis

### Schema

```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,                -- "1_protocol-1"
    step TEXT NOT NULL,                    -- "step-4"
    filename TEXT NOT NULL,                 -- full basename
    technique TEXT NOT NULL,                -- "iv", "endurance", "retention", "switching"
    date_code TEXT,                         -- DDMMYY extracted from filename
    material TEXT NOT NULL,                 -- from filename pattern
    row INTEGER,                            -- from matrix part ("r0c1" → 0, 1)
    col INTEGER,
    cycle_index INTEGER,                    -- suffix number (only for iv-sweep technique)
    timestamp_first REAL,                   -- first timestamp from Keithley column
    timestamp_last REAL,                    -- last timestamp from Keithley column
    v_set REAL,                             -- analyzed (nullable until analysis run)
    v_reset REAL,
    on_off_ratio REAL,
    current_compliance_1sf TEXT,            -- e.g. "5e-2" (1 sig fig)
    compliance_confidence TEXT,
    plot_figure_path TEXT,                  -- e.g. "step-4/results/iv_r0c0_material_01.svg"
    file_size INTEGER,
    mtime TEXT,
    UNIQUE(protocol, step, filename)
);

CREATE TABLE cells (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    material TEXT NOT NULL,                  -- each material = separate matrix
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    n_files INTEGER DEFAULT 0,
    median_v_set REAL,
    median_v_reset REAL,
    median_on_off_ratio REAL,
    UNIQUE(protocol, material, row, col)
);

CREATE TABLE protocols (
    name TEXT PRIMARY KEY,
    label TEXT,
    rows INTEGER,
    cols INTEGER,
    materials TEXT,                          -- JSON list
    last_sync TEXT
);
```

### Sync Flow in `memristor sync`

1. Read each IV CSV (as today)
2. Extract from filename: date_code (DDMMYY), material (from pattern), row, col (from matrix), cycle_index (suffix)
3. Read first and last values of Timestamp column from Keithley data
4. Run analysis: Vset, Vreset, ON/OFF, compliance detection
5. Write to devices.yaml (as today)
6. Write/update SQLite: `INSERT OR REPLACE INTO files`, upsert `cells` aggregates, upsert `protocols`

### Key Design Notes

- `cycle_index` only applies to iv-sweep technique (not endurance/retention)
- No batch field
- Temperature column excluded for now (future improvement)
- Material determines matrix classification (not row/col alone)
- `on_off_ratio` in `cells` is the median across files — files without switching contribute NULL (excluded from median)
- No sweep direction or sweep rate in SQLite — these remain YAML-only (per devices.yaml role from Sprint 3)

### Files Affected

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/db.py` | **NEW** | SQLite schema, create/read/write helpers |
| `src/science_cli/memristor/device_cli.py` | **Modify** | Add SQLite write to `cmd_sync()` |
| `src/science_cli/memristor/dashboard.py` | **Modify** | Add SQLite read path (optional, YAML fallback) |
| `src/science_cli/memristor/plotting.py` | **Modify** | Expose first/last timestamp in info dict |
| `test_guardrails.py` | **Modify** | Add SQLite-related guardrail tests |

### Sprint 6 Progress

- [x] PLAN: Sprint 6 section created (this document)
- [x] IMPLEMENT: `src/science_cli/memristor/db.py` — SQLite schema + CRUD helpers
- [x] IMPLEMENT: SQLite write in `cmd_sync()` — dual-write after YAML
- [x] IMPLEMENT: Analysis results (Vset/Vreset/ratio) written to SQLite during sync
- [x] IMPLEMENT: SQLite read path in `dashboard.py` — fallback to YAML if no DB
- [x] IMPLEMENT: `plotting.py` exposes `timestamp_first`, `timestamp_last` in info dict
- [x] TEST: SQLite schema created correctly (19/19 guardrail tests)
- [x] TEST: Dashboard reads from SQLite when available
- [x] TEST: YAML-only workflow still works (no DB = no crash)
- [x] TEST: Dual-write on sync with `--reindex` mode
- [x] TEST: All guardrail tests pass (19/19)
- [x] COMMIT to `refactor/2.1.0` branch (commit `2ac44c7`)

**Sprint 6 Results:**
- NEW `memristor/db.py`: SQLite module with 4 tables (files, cells, protocols, _meta), WAL mode, schema migration, CRUD helpers, index support
- `device_cli.py`: Dual-write in `cmd_sync()`, `--reindex` mode, `_sqlite_sync_from_yaml()`, `_sqlite_reindex()`
- `dashboard.py`: `read_dashboard_data_sqlite()` with SQLite-first read path, YAML fallback
- `plotting.py`: `timestamp_first`/`timestamp_last` exposed in both `read_iv_csv()` and `read_iv_lvm()`
- `test_guardrails.py`: 3 new SQLite guardrail tests (19 total)
- Bug fix: `dict(row)` → `{key: row[key] for key in row.keys()}` for `sqlite3.Row` compatibility

## Gaps & Flaws Analysis (Sprint 6)

### 1. `analysis_data.json` vs SQLite Overlap

**Risk**: MEDIUM. Both `analysis_data.json` (Sprint 3) and the SQLite `files` table store per-file Vset/Vreset/ratio. The JSON also stores file mtimes for incremental cache invalidation. Without alignment, two sources of truth can drift apart.

**Mitigation**: Clarify roles:
- `analysis_data.json` = **analysis cache** (tracks file mtimes for incremental re-analysis, stores intermediate analysis state)
- SQLite = **query cache** (fast indexed reads for dashboard/analysis panels)
- Both are populated from the same analysis pipeline during `sync`
- When SQLite is present and current, the dashboard reads from SQLite. When absent, it falls back to YAML + JSON.
- The `--force` flag (Sprint 3) should rebuild both caches.

### 2. Missing Indexes — Performance at Scale

**Risk**: MEDIUM. The `files` table has no indexes on `material`, `protocol`, `technique`, or `mtime`. Dashboard filters (material selector) would scan the entire table. Incremental sync would scan all rows to find stale mtimes.

**Mitigation**: Add indexes to the schema:

```sql
CREATE INDEX idx_files_material ON files(material);
CREATE INDEX idx_files_protocol ON files(protocol);
CREATE INDEX idx_files_mtime ON files(mtime);
CREATE INDEX idx_files_technique ON files(technique);
CREATE INDEX idx_cells_protocol_material ON cells(protocol, material);
```

### 3. Dual-Write Not Atomic

**Risk**: MEDIUM. `sync` writes to `devices.yaml` first, then to SQLite. If SQLite write fails (disk full, permission error, DB locked), YAML is updated but SQLite is stale. On next dashboard render, SQLite would have missing data while YAML is correct. Reverse failure (YAML fails, SQLite succeeds) is less likely but possible.

**Mitigation**:
- Wrap SQLite write in a transaction
- If SQLite write fails, log a warning and dashboard falls back to YAML
- Consider using WAL (Write-Ahead Log) mode for SQLite to improve concurrent read reliability
- A future enhancement could make writes atomic by using SQLite as the write target and deriving YAML from it

### 4. `protocols.materials` as JSON String

**Risk**: LOW-MEDIUM. `materials TEXT` stores a JSON list (e.g., `["Ta-PDA-ITO", "Pt-STO"]`). SQLite has no native JSON array type — querying individual materials requires `json_each()` or LIKE patterns. This makes protocol-level material queries slower.

**Mitigation**: Keep JSON for simplicity (single-row metadata per protocol). The `files` and `cells` tables already have a plain `material TEXT` column with proper indexing (see item 2). Protocol-level material queries are rare (only on project init/summary).

### 5. `on_off_ratio` Median in `cells` — NULL Handling

**Risk**: LOW. `median_on_off_ratio` in the `cells` table aggregates across all files for that cell. Devices without switching contribute NULL, which SQLite's `median()` aggregate handles inconsistently (no native median function — requires custom aggregate or subquery).

**Mitigation**:
- Exclude files with `v_set IS NULL` from the median computation
- Document that `median_on_off_ratio` reflects only switching files, not all files
- Implement median in Python before upsert, or use SQL window functions: `AVG(on_off_ratio) OVER(...)` with NULL exclusion

### 6. No Schema Migration Strategy

**Risk**: LOW. SQLite schema is created on first `sync`. Future changes (adding temperature column, batch field, new technique columns) require `ALTER TABLE` or version tracking. Existing `.db` files would be incompatible with a new schema.

**Mitigation**:
- Add a `schema_version` INTEGER pragma or version row in the `protocols` table
- On startup, check version and run migration SQL if needed
- Start at version 1 for the initial schema

### 7. Sweep Direction / Sweep Rate Missing (Deferred)

**Risk**: LOW. Sprint 3's `devices.yaml` stores sweep direction + sweep rate per file. These are not in SQLite. If the dashboard ever needs to filter or facet by sweep direction, it still requires parsing YAML.

**Mitigation**: Document as a deferred enhancement. Add sweep direction and sweep rate columns to `files` table in a future sprint when dashboard filtering requires them.

### 8. `cells` Table is Derived Data

**Risk**: LOW. The `cells` table stores aggregates (median Vset, n_files) that can always be recomputed from `files`. This is a classic denormalization — it speeds up dashboard cell queries but can drift if `files` is updated without updating `cells`.

**Mitigation**:
- Always upsert `cells` in the same transaction as `files` during sync
- Consider making `cells` a SQL view in a future iteration if consistency proves problematic
- Add a `memristor sync --rebuild-cells` flag to recompute cells from files

### 9. No `db rebuild` Command

**Risk**: LOW. Existing projects need a way to recreate the SQLite database from scratch (e.g., if DB is corrupted, deleted, or schema changes during development).

**Mitigation**: Add `memristor sync --rebuild-db` flag that drops and recreates the SQLite file, then re-syncs all files. Document in the Sprint 6 plan.

### 10. Temperature Column Excluded

**Risk**: LOW. Temperature is a relevant parameter for memristor characterization (SET/RESET voltage drift with temperature). Excluded per current spec as a future improvement.

**Mitigation**: Document in schema comments. When adding temperature, add `temperature` REAL column to `files` table. The parsing logic would need to extract temperature from filename pattern or metadata headers (neither currently supports it).

### Mitigation Notes

**Gap 1 (analysis_data.json overlap):** `analysis_data.json` = dashboard render cache (heatmaps, histogram bins). Generated by `dashboard --render-cache`, consumed by JS. SQLite = queryable metadata (files, cells, params). Populated by `sync`, consumed by CLI/analysis. Different lifecycle: SQLite on sync, JSON on dashboard render.

**Gap 3 (Dual-write atomicity):** Write SQLite first in a transaction (WAL mode). Then write YAML. If YAML fails, SQLite rollback. Next sync is idempotent. YAML remains source of truth — SQLite is cache, easily rebuilt via `--reindex`. Add `PRAGMA journal_mode=WAL` on DB open.

**Gap 6 (Schema migration):** Add `_meta` table: `CREATE TABLE _meta (schema_version INTEGER)`. On DB open, check version vs expected. Apply migration SQL for each version increment. Start at v1. Migration is append-only — never modify existing rows, only add/alter.

**Gap 8 (cells as derived data):** Keep as upserted table (not view). SQLite has no `MEDIAN()` aggregate. Upsert cells in same transaction as files. `INSERT INTO cells ... ON CONFLICT(protocol,material,row,col) DO UPDATE SET ...`

**Gap 9 (No rebuild command):** `memristor sync --reindex` reads devices.yaml (not CSV) and repopulates SQLite. Fast recovery for schema changes or corruption. Pipeline: read YAML → iterate FileEntry list → upsert SQLite → recompute cells table.

### Design Decisions

**Analysis data cache location:** `<project_root>/<project_name>_analysis-data.json` (JSON not YAML — machine cache, not human-editable).

**Sync directions:**
- `memristor sync` — CSV → YAML + DB (default, full sync)
- `memristor sync --reindex` — YAML → DB only (recovery, no CSV re-read)
- No `--db-to-yaml` — YAML has richer structure (sweep segments, extra dict, nested hierarchy). YAML stays canonical.

**Role separation:**
- **YAML**: Human editing, Git visibility, AI configurability, rich metadata
- **SQLite**: Fast queries, aggregation, joins across protocols/steps/cells/materials
- **Naming grammar:** Template-based YAML grammar (not position-based). Multiple patterns with fallback chain. Optional fields via `{field?}` syntax. Regex matching (not split-by-position) to handle field-internal separators.

## Sprint 7: Config-Driven Technique Registry &amp; Filename Naming Grammar

**Goal:** Replace hardcoded technique-to-filename-pattern mappings and filename parsing with a config-driven approach. Store technique patterns, device configs, and filename naming grammar in `sci-config.yaml`, using `BUILTIN_TECHNIQUES` and built-in regex patterns as fallback defaults.

**Status**: Proposed (features approved, not yet implemented)

### Feature F7.5: Config-Driven File Pattern Registration

**Problem:** Currently, filename patterns and technique→device mappings are hardcoded in `core/technique.py` (`BUILTIN_TECHNIQUES`). This makes:
- Adding new file formats requires code changes
- SQLite construction relies on implicit patterns
- AI/future tools can't configure new techniques without code

**Solution:** Store technique-to-filename-pattern mapping in `config.yaml` (the 4-tier config system), with the hardcoded patterns as fallback defaults:

```yaml
# In sci-config.yaml or ~/.config/science-cli/config.yaml
techniques:
  iv:
    label: "IV Sweep"
    description: "Current-Voltage characterization sweeps"
    patterns:
      - "*_iv_*.csv"
      - "*_IV-DC_*"
      - "DDMM_Material_rNcN_iv_*.csv"
    devices:
      keithley-2400:
        delimiter: ","
        header_lines: 1
        columns:
          time: "Time (s)"
          voltage: "Voltage (V)"
          current: "Current (A)"
  endurance:
    label: "Endurance"
    patterns: ["*_endurance_*.csv", "*_endurance_*.txt"]
    devices:
      keithley-2400:
        delimiter: ","
        header_lines: 1
        columns:
          cycle: "Cycle"
          r_on: "R_ON (Ohm)"
          r_off: "R_OFF (Ohm)"
```

**Steps → Technique → Device chain:**

```
devices.yaml
  points[].techniques.iv         ← technique ID from config
    └── files[].file              ← matched against patterns from config
         └── device param         ← loaded via `get_device_config(technique, device_name)` from config
```

**Benefits for SQLite:**
- `sync` reads technique patterns from config → no hardcoded mapping
- New techniques added via config → AI-editable, no code change
- SQLite DB construction is fully config-driven

**Benefits for AI:**
- AI reads `sci-config.yaml` → understands all techniques, patterns, devices
- AI writes new technique config → next `sync` picks it up
- Standard YAML — no special AI interface needed

**Files affected:**

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/technique.py` | **Modify** | Load patterns from config, fall back to BUILTIN_TECHNIQUES |
| `src/science_cli/core/config.py` | **Modify** | Add `get_technique_config()` returning full technique dict |
| `src/science_cli/memristor/device_cli.py` | **Modify** | `sync` uses config-driven pattern matching |
| `src/science_cli/memristor/db.py` | **Modify** | SQLite construction reads from config |

---

### Feature F7.6: Template-Based Filename Naming Grammar

**Problem:** Currently, filename parsing (extracting date, material, row, col, cycle from filenames like `140526_Ta-PDA-ITO_r0c0_iv_01.csv`) uses hardcoded regexes spread across `technique.py`, `plotting.py`, and `device_cli.py`. The earlier design used position-based fields which break on optional segments (batch number, extra type codes).

**Solution:** Template-based naming grammar in `sci-config.yaml` with named groups, optional field markers, and multi-pattern fallback:

```yaml
file_naming:
  separator: "_"
  patterns:
    # Canonical: DDMMYY_Material[_batch]_rNcN_Technique[_Type][_Suffix].ext
    - template: "{date_code}_{material}{batch?}_{matrix}_{technique}{type?}{suffix?}"
      description: "Canonical memristor naming with optional batch, type, and cycle suffix"
      regex: "^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:\((?P<batch>\d+)\))?_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$"
      fields:
        date_code: { sql_column: date_code, type: TEXT }
        material: { sql_column: material, type: TEXT }
        batch: { sql_column: batch, type: TEXT, nullable: true }
        matrix: { sql_column: null, type: null, extract: { row: "r(?P<row>\d+)c\d+", col: "r\d+c(?P<col>\d+)" } }
        technique: { sql_column: technique, type: TEXT }
        type: { sql_column: sweep_type, type: TEXT, nullable: true }
        suffix: { sql_column: cycle_index, type: INTEGER, nullable: true }
    
    # Fallback: bare minimum
    - template: "{date_code}_{material}_{matrix}_{technique}"
      description: "Minimal naming, no optional fields"
      regex: "^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)\.\w+$"
      fields:
        date_code: { sql_column: date_code }
        material: { sql_column: material }
        matrix: { sql_column: null, extract: { row: "r(?P<row>\d+)c\d+", col: "r\d+c(?P<col>\d+)" } }
        technique: { sql_column: technique }
```

**Template conventions:**
- `{field}` — required segment
- `{field?}` — optional segment
- `.ext` — any extension

**Template-based advantages over position-based:**
- Handles optional fields (batch, type, suffix) — position-based would shift all indexes
- Multi-pattern fallback — if first pattern fails, try second
- Matrix fields auto-extracted via `extract` sub-regexes
- AI-friendly: edit template string, named groups in regex are self-documenting
- Separator agnostic: regex matching, not split-by-position

**SQLite column mapping:**
- `fields[*].sql_column` maps to Sprint 6's `files` table columns
- `nullable: true` means the column accepts NULL when the field doesn't exist
- `extract` secondary regex extracts row/col from matrix string (e.g., `r0c1` → row=0, col=1)
- If no pattern matches, file is flagged with `parse_error: "no matching pattern"` in extra dict

**Files affected:**
- `src/science_cli/core/config.py` — add `get_file_naming_patterns()` returning list of pattern dicts
- `src/science_cli/core/technique.py` — load patterns from config, match in order, fall back to BUILTIN_TECHNIQUES
- `src/science_cli/memristor/plotting.py` — `_parse_filename_metadata()` uses template regexes
- `src/science_cli/memristor/device_cli.py` — `sync_devices()` uses template grammar for filename parsing
- `src/science_cli/memristor/db.py` — SQLite construction uses `fields.sql_column` to know which columns to populate

**F7.6 Progress:**
- [ ] F7.6 config: `get_file_naming_patterns()` in core/config.py
- [ ] F7.6 parser: Template-based filename parser in core/technique.py
- [ ] F7.6 sync: Integrate template parser into `sync_devices()`
- [ ] F7.6 plotting: Replace hardcoded `_extract_info_from_filename()` with config-driven parser
- [ ] F7.6 db: Map extracted fields to SQLite columns via `sql_column` config
- [ ] F7.6 test: New naming convention added via config → all parse paths work correctly
---

### Cross-Plumbing Code Audit

The following table catalogues every location where filename parsing, technique detection, or column mapping is hardcoded, and maps it to the config-driven future.

| Location | Current: Hardcoded | Future: Config-Driven | Effort |
|----------|-------------------|----------------------|--------|
| `technique.py`: `detect_technique()` (L123-136) | Iterates `_all_patterns()` dict built from `PATTERNS` + config merge | Load patterns from config grammar; fall back to `PATTERNS` dict | Small |
| `technique.py`: `BUILTIN_TECHNIQUES` dict (L70-82) | `TechniqueDef` objects with hardcoded patterns + labels per technique | Config `techniques.<name>.patterns` + `file_naming.per_technique` define all fields | Small |
| `technique.py`: `technique_label()` (L139-154) | Hardcoded `labels` dict maps technique IDs → display names | Derive labels from config `techniques.<name>.label` | Small |
| `device_cli.py`: `CANONICAL_RE` + `parse_canonical_filename()` (L130-171) | Single hardcoded regex for `DDMM_Material_b#-t#_Technique_Type_#.ext` format | Grammar `global` fields (position 0-2) + `per_technique` fields replace the entire regex | Medium |
| `device_cli.py`: `_parse_filename_metadata()` (L174-204) | Hardcoded regex patterns for `rNcN`, technique keywords, sweep_type extraction | Grammar `global.matrix` field provides `rNcN`; `per_technique` provides type/sweep_type | Medium |
| `device_cli.py`: `_infer_technique()` + `cmd_init()` TECH_MAP (L117-125, L268-272) | Duplicated dict mapping `iv-sweep` → `"iv"`, `mem-endurance` → `"endurance"`, etc. | Single source from config `file_naming.per_technique` keys → short name mapping | Small |
| `device.py`: `_MATERIAL_BATCH_RE` + `extract_material_batch()` (L295-328) | Hardcoded regex `^\\d{4}_Material(Batch)_b#-t#_` for material+batch extraction | Grammar `global.material` + `global.matrix` fields replace this entirely | Medium |
| `plotting.py`: `read_iv_csv()` column detection (L71-94) | If-elif chain matching known column header keywords | Config-driven column mapping per device config (already partially done via `get_device_config()`) | Medium |
| `plotting.py`: `collect_iv_files()` material extraction (L1014-1031) | Calls `extract_material_batch()` which uses hardcoded regex | Inherits from grammar-based `global.material` field | Small |
| `device_cli.py`: `cmd_sync()` sweep extraction (L744-755) | Calls `sync_devices()` which only processes `"iv"` technique — hardcoded technique filter | Use config grammar to determine which techniques support sweep extraction | Large |
| `device.py`: `read_devices()` (L334-402) | Hardcoded YAML field mapping to dataclass fields | **Should stay** — YAML model mapping is inherently static; not a candidate for config | None |

**Effort notes:**
- **Small**: Single-function refactor, no new module needed
- **Medium**: Cross-file changes, new helper needed in config.py
- **Large**: Changes affect sync flow, may need technique-agnostic sweep extraction

### Sprint 7 Progress

- [x] PLAN: Sprint 7 section created (this document)
- [x] Feature F7.5: Config-driven technique pattern registration
- [x] IMPLEMENT F7.5: Config-driven technique pattern loading in `core/technique.py`
- [x] IMPLEMENT F7.5: `get_technique_config()` in `core/config.py`
- [x] IMPLEMENT F7.5: Config-driven technique map in `device_cli.py` (`_build_tech_map()`)
- [ ] IMPLEMENT F7.5: Config-driven SQLite construction in `db.py` (deferred to Sprint 6)
- [x] FEATURE F7.6: Config-driven filename naming grammar
- [x] IMPLEMENT F7.6: `get_file_naming_grammar()` in `core/config.py`
- [x] IMPLEMENT F7.6: Grammar-aware technique detection in `technique.py`
- [x] IMPLEMENT F7.6: Grammar-driven filename parsing in `plotting.py`
- [x] IMPLEMENT F7.6: Grammar-driven sync/filename parsing in `device_cli.py`
- [x] IMPLEMENT F7.6: Grammar-driven material extraction in `device.py`
- [ ] IMPLEMENT F7.6: Grammar-aware SQLite column mapping in `db.py` (deferred to Sprint 6)
- [x] TEST: Config-driven patterns loaded correctly
- [x] TEST: Grammar parser returns parse_error when no grammar configured (expected)
- [x] TEST: Backward compatibility — no config.yaml = BUILTIN_TECHNIQUES + hardcoded regex fallback
- [x] TEST: All guardrail tests pass (16/16)
- [x] COMMIT to `refactor/2.1.0` branch (commit `004daa7`)

**Sprint 7 Results:**
- `core/config.py`: Added `get_file_naming_patterns()`, `get_file_naming_grammar()`
- `core/technique.py`: Updated `_config_patterns()` for dict-first loading, added `get_technique_label()`, `parse_filename_grammar()` with template-based regex matching and row/col extraction
- `device_cli.py`: Added `_build_tech_map()` for config-driven technique→shortname mapping, updated `_infer_technique()` and `cmd_init()`, enhanced `_parse_filename_metadata()` to try grammar parsing first
- `plotting.py`: Updated `collect_iv_files()` to try grammar-based extraction
- `device.py`: Updated `extract_material_batch()` to accept optional project_root for grammar-first parsing

## Pipeline Overview

**The complete data workflow tying all sprints together:**

```
Project root
  ├── sci-config.yaml              ← naming grammar, techniques, devices (Sprint 7)
  ├── protocol/<name>/
  │   ├── devices.yaml             ← cell matrix, file assignments (YAML = human)
  │   ├── step-4/
  │   │   ├── <date>_<material>_<matrix>_<technique>_<cycle>.csv
  │   │   └── results/
  │   └── ...
  ├── <project_name>.db            ← SQLite query cache (Sprint 6)
  └── <project_name>_analysis-data.json  ← dashboard render cache
```

**Commands:**

| Command | Reads | Writes | Sprint |
|---------|-------|--------|--------|
| `memristor init` | CSV files, sci-config.yaml | devices.yaml | existing |
| `memristor sync` | CSV files, sci-config.yaml | devices.yaml + `<project>.db` | Sprint 6 |
| `memristor sync --reindex` | devices.yaml, sci-config.yaml | `<project>.db` only (no CSV re-read) | Sprint 6 |
| `memristor dashboard` | `<project>.db` (fast) or devices.yaml (fallback) | `<project>_analysis-data.json` + dashboard.html | Sprint 3 |
| `config edit technique` | sci-config.yaml | sci-config.yaml (user edits) | Sprint 5 |

**Data flow:**
1. `sci-config.yaml` defines the naming grammar — how to parse date, material, row, col, cycle from filenames
2. `memristor sync` reads grammar → parses all CSVs → extracts metadata → runs IV analysis → writes YAML + SQLite
3. Dashboard reads from SQLite (fast) or YAML (fallback)
4. `--reindex` rebuilds SQLite from YAML without re-reading CSV (recovery)
5. All files belong to a specific protocol + step — assigned via devices.yaml, parsed via grammar

## Sprint 8: Global Config Registry &amp; sync/analyze Split (Proposed)

### Problem

Currently grammar patterns, device configs, and technique templates live **per-project** in `sci-config.yaml`:

```
test-project/sci-config.yaml:     keithley-2400 device config
another-project/sci-config.yaml:  (duplicated) keithley-2400 device config
```

This means:
- Same Keithley 2400 config (23 header lines, tab delimiter, columns) duplicated across N projects
- Same naming grammar patterns (`rNcN`, `bN-tN`) duplicated across N projects
- `config edit techniques` modifies per-project config — cannot share improvements
- No central registry of "how to parse instrument X"

### Solution: 4-Tier Config (Upgraded)

```
Hardcoded defaults (core/config.py)
       ↓ overridden by
Global config (~/.config/science-cli/config.yaml)     ← NEW: grammar, devices, technique templates
       ↓ overridden by
Per-project config (<project>/sci-config.yaml)         ← LIGHTER: type→step mapping only
       ↓
Per-protocol metadata (protocol/<name>/...)
```

### Universal Grammar Fields

Every filename is parsed into a fixed set of universal fields. These names are standardized across all projects, all techniques, all devices:

| Field | Description | Example Values | Required |
|-------|-------------|----------------|----------|
| `date_code` | Date in DDMMYY or YYYYMMDD format | `140526`, `20260514` | Yes |
| `material` | Material/device name (primary). Also accepts `device` as alias. | `Ta-PDA-ITO`, `Pt-STO` | Yes |
| `technique` | Measurement technique code | `iv-sweep`, `ca-doping`, `endurance` | Yes |
| `matrix` | Crossbar addressing: rNcN for rectangular, bN-tN for bottom/top | `r0c0`, `b1-t1`, `r2c3` | Yes |
| `suffix` | Order/cycle number (zero-padded integer) | `001`, `002`, `01` | No |

**Design decisions:**
- **Separator is hardcoded to `_` (underscore)** — not configurable. Every filename field is separated by `_`. This eliminates a source of config drift and keeps parsing deterministic.
- **`material` is the primary field name**; `device` is accepted as a config alias for compatibility.
- **`suffix` replaces the earlier `order`/`cycle_index` naming** — universal across all techniques.
- All fields map directly to SQLite columns with matching names (see SQLite Auto-Construction below).

#### Global config role (the "library"):

```yaml
# ~/.config/science-cli/config.yaml

file_naming:
  patterns:
    - id: rNcN
      template: "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}"
      description: "Standard rNcN convention (rectangular crossbar)"
      regex: "^(?P&lt;date_code&gt;\\d{6})_(?P&lt;material&gt;[^_]+?)(?:_(?P&lt;batch&gt;\\d+))?_(?P&lt;matrix&gt;r\\d+c\\d+)_(?P&lt;technique&gt;[^_]+)(?:_(?P&lt;type&gt;[^_]+))?(?:_(?P&lt;suffix&gt;\\d+))?\\.\\w+$"
      fields:
        date_code: { sql_column: date_code, type: TEXT }
        material: { sql_column: material, type: TEXT }
        batch: { sql_column: batch, type: TEXT, nullable: true }
        matrix: { sql_column: null, type: null, extract: { row: "r(?P&lt;row&gt;\\d+)c\\d+", col: "r\\d+c(?P&lt;col&gt;\\d+)" } }
        technique: { sql_column: technique, type: TEXT }
        type: { sql_column: sweep_type, type: TEXT, nullable: true }
        suffix: { sql_column: suffix, type: INTEGER, nullable: true }

    - id: bN-tN
      template: "{date_code}_{material}{batch?}_b{bot}-t{top}_{technique}_{type?}_{suffix?}"
      description: "Bottom/top crossbar convention"
      regex: "^(?P&lt;date_code&gt;\\d{6})_(?P&lt;material&gt;[^_]+?)(?:_(?P&lt;batch&gt;\\d+))?_b(?P&lt;bot&gt;\\d+)-t(?P&lt;top&gt;\\d+)_(?P&lt;technique&gt;[^_]+)(?:_(?P&lt;type&gt;[^_]+))?(?:_(?P&lt;suffix&gt;\\d+))?\\.\\w+$"
      fields:
        date_code: { sql_column: date_code, type: TEXT }
        material: { sql_column: material, type: TEXT }
        batch: { sql_column: batch, type: TEXT, nullable: true }
        matrix: { sql_column: null, type: null, extract: { bot: "b(?P&lt;bot&gt;\\d+)", top: "t(?P&lt;top&gt;\\d+)" } }
        technique: { sql_column: technique, type: TEXT }
        type: { sql_column: sweep_type, type: TEXT, nullable: true }
        suffix: { sql_column: suffix, type: INTEGER, nullable: true }

devices:
  keithley-2400:
    label: "Keithley 2400 SourceMeter"
    delimiter: "\t"
    decimal: "."
    header_lines: 23
    encoding: utf-8
    columns:
      voltage: Untitled
      current: "Untitled 1"
      time: "Untitled 2"
  keysight-b1500:
    label: "Keysight B1500A Semiconductor Analyzer"
    delimiter: ","
    header_lines: 48
    columns:
      voltage: "BV"
      current: "BI"
      time: "Time"

techniques:
  iv-sweep:
    label: "IV Sweep"
    grammar_codes: ["iv", "IV", "iv-sweep", "iv_dc"]
    default_device: keithley-2400
    types:
      forming: { label: "Forming", step_type: forming }
      set: { label: "Set", step_type: set }
      reset: { label: "Reset", step_type: reset }
    type_to_step:
      forming: "1_forming"
      set: "2_set"
      reset: "3_reset"
```

Note: `separator` is **not** a config field — it is hardcoded to `_` everywhere. The `file_naming` level has no `separator` key.

#### Project config role (light selector):

```yaml
# <project>/sci-config.yaml
description: "TaOx memristor characterization"

techniques:
  iv-sweep:
    types:
      forming: 1_forming       # override global default
      set: 2_set
      reset: 3_reset
```

The project config **inherits** device configs, grammar patterns, and technique defaults from the global config. It only specifies what's different (e.g., step names).

### sync vs analyze — Clear Separation

A key refinement in Sprint 8: `memristor sync` and `memristor analyze` are split into two distinct commands with separate responsibilities.

#### `memristor sync` — Pure Filename Parsing

`sync` does **not** read CSV content. It operates entirely on filenames:

1. **Scan** step directories for files matching grammar patterns
2. **Parse** filenames via grammar patterns from config (global → project)
3. **Extract** universal fields: date_code, material, technique, matrix, suffix
4. **Populate** SQLite metadata tables (`files`, `cells`, `protocols`) with extracted fields
5. **Skip** any file that doesn't match any grammar pattern (flag for review)
6. **No IV curve analysis** — no CSV reading, no Vset/Vreset computation

Sync is fast and pure metadata: filenames only, no content.

#### `memristor analyze` — CSV-Based Computation

`analyze` is a new command that performs the actual data analysis:

1. **Read** raw CSV files using device config for parsing (delimiter, columns, header_lines)
2. **Compute** Vset, Vreset, ON/OFF ratio, compliance from IV curves
3. **Update** SQLite rows with computed values via `update_file_analysis()`
4. **Optionally** write human-readable YAML summary (not required for SQLite operation)

Analyze is the heavy computation step. It depends on `sync` having already populated the metadata.

**Workflow:**
```bash
memristor sync              # Fast: parse filenames → SQLite metadata
memristor analyze           # Slow: read CSVs → compute params → update SQLite
memristor analyze --force   # Re-analyze all files (ignore cached analysis)
memristor analyze --file X.csv  # Single-file re-analysis
```

### SQLite Auto-Construction

SQLite populates itself without requiring a YAML intermediate:

1. **Read grammar** from config (global → project resolution chain)
2. **Scan** step directories for files matching grammar patterns
3. **Parse** filenames → extract universal fields → insert SQLite rows
4. **YAML is optional** — `devices.yaml` is written only for human readability, not required by SQLite

**Construction flow:**
```
Config grammar
       ↓
Scan step dirs → match filenames against patterns → extract universal fields
       ↓
SQLite INSERT OR REPLACE INTO files (...) VALUES (...)
       ↓
Optional: devices.yaml (human-readable snapshot, not required)
```

**SQLite is the canonical machine-readable store.** YAML is a view/debug aid:
- `memristor sync` → always updates SQLite
- `memristor sync --yaml` → also writes/updates devices.yaml (optional flag)
- `memristor analyze` → updates SQLite analysis columns
- Dashboard reads SQLite directly — no YAML needed

### Benefits

| Aspect | Before (Sprint 7) | After (Sprint 8) |
|--------|-------------------|------------------|
| New instrument support | Copy device config to each project | Add once to global config |
| Grammar sharing | Duplicate per project | Single source of truth |
| `config edit techniques` | Edits per-project | Edits global registry |
| SQLite schema | Full device config in DB | Reference `technique_id` + `device_id` |
| Adding new technique | Copy files, edit per-project | One `config edit techniques --global` |
| sync scope | CSV read + YAML + DB + analysis | **Pure filename parsing** (fast, no CSV) |
| analyze scope | Mixed into sync | **Separate command** (CSV reading + computation) |
| YAML role | Required intermediate | **Optional** (human-readable only) |
| Separator config | Configurable (`separator` key) | **Hardcoded `_`** (no config drift) |

### Impact on SQLite

With a global technique+device registry, SQLite stores normalized references and is auto-populated:

```sql
-- Files table: populated by sync (metadata) and analyze (computed values)
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    step TEXT NOT NULL,
    filename TEXT NOT NULL,
    technique_id TEXT,    -- references global techniques
    device_id TEXT,       -- references global devices
    -- Universal grammar fields (populated by sync)
    date_code TEXT,
    material TEXT NOT NULL,
    matrix TEXT,
    row INTEGER,
    col INTEGER,
    suffix INTEGER,
    -- Computed analysis values (populated by analyze)
    v_set REAL,
    v_reset REAL,
    on_off_ratio REAL,
    current_compliance REAL,
    compliance_confidence TEXT,
    -- Metadata
    file_size INTEGER,
    mtime TEXT,
    parse_error TEXT,     -- non-null if filename didn't match any grammar pattern
    UNIQUE(protocol, step, filename)
);

CREATE TABLE cells (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    material TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    n_files INTEGER DEFAULT 0,
    median_v_set REAL,
    median_v_reset REAL,
    median_on_off_ratio REAL,
    UNIQUE(protocol, material, row, col)
);

CREATE TABLE protocols (
    name TEXT PRIMARY KEY,
    label TEXT,
    rows INTEGER,
    cols INTEGER,
    materials TEXT,       -- JSON list
    last_sync TEXT
);
```

**Auto-population:**
- `sync` fills: protocol, step, filename, technique_id, device_id, date_code, material, matrix, row, col, suffix, file_size, mtime
- `analyze` fills: v_set, v_reset, on_off_ratio, current_compliance, compliance_confidence
- `cells` table: upserted by both sync (metadata counts) and analyze (aggregated stats)
- No YAML required — SQLite is self-constructing from filenames + grammar

### `config edit` Changes

New commands:
```bash
config edit                     # Edits project sci-config.yaml (existing)
config edit --global            # Edits ~/.config/science-cli/config.yaml (NEW)
config edit techniques          # Edits project technique config (existing)
config edit techniques --global # Edits global technique registry (NEW)
config edit devices             # Lists + edits device configs (NEW)
config edit grammar             # Lists + edits file naming patterns (NEW)
```

### Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `core/config.py` | Major update | Add `_load_global_config()`, merge order (global ← project), typed accessors for global |
| `core/technique.py` | Update | `parse_filename_grammar()` tries global patterns first, project overrides |
| `core/data_loader.py` | Update | `load_data_file()` resolves device config from global if not in project |
| `cli/commands/config.py` | Major update | Add `--global` flag, `devices` subparser, `grammar` subparser |
| `memristor/db.py` | Major update | Schema normalization, auto-construction from grammar, `update_file_analysis()` for analyze |
| `memristor/dashboard.py` | Update | `generate_dashboard()` resolves technique config from global registry |
| `memristor/device_cli.py` | Major update | Split `sync` into pure-filename-parsing; add `cmd_analyze()` handler |
| `memristor/device_cli.py` | **New command** | `memristor analyze` CLI handler calling `analyze_all_devices()` |

### Progress

- [x] Sprint 8 plan written
- [x] User approved
- [x] IMPLEMENT: Universal Grammar Fields — hardcode `_` separator, standardize 5 field names
- [x] IMPLEMENT: Add `_load_global_config()` to `core/config.py` → `load_global_config()`, `_DEFAULT_GLOBAL_DEVICES`, `_DEFAULT_GLOBAL_TECHNIQUES`
- [x] IMPLEMENT: Add `--global` flag to `config edit`
- [x] IMPLEMENT: Add `config edit devices` and `config edit grammar`
- [x] IMPLEMENT: Update technique resolution chain (4-tier: hardcoded → global → project → protocol)
- [x] IMPLEMENT: SQLite auto-construction — `populate_from_grammar()`, `populate_protocol_from_step_dirs()`
- [x] IMPLEMENT: `memristor sync` as pure filename parsing only (no CSV read, no analysis)
- [x] IMPLEMENT: `memristor analyze` — new command for CSV-based computation (`cmd_analyze()`)
- [x] IMPLEMENT: `update_file_analysis()` in `db.py` for SQLite analysis updates
- [x] IMPLEMENT: Update dashboard to resolve config from global registry (SQLite fast path)
- [x] TEST: Global config loaded before project config
- [x] TEST: Project config overrides global config correctly
- [x] TEST: `config edit --global` writes to correct file
- [x] TEST: `memristor sync` populates SQLite metadata (no CSV read)
- [x] TEST: `memristor analyze` reads CSVs and updates SQLite analysis columns
- [x] TEST: Dashboard resolves technique config globally if not in project
- [x] TEST: YAML-free workflow (sync → analyze → dashboard, no devices.yaml needed)
- [x] TEST: All existing tests still pass (78/78)
- [x] COMMIT to `refactor/2.1.0`

**Sprint 8 Results:**
- `core/config.py`: Added `_DEFAULT_GLOBAL_DEVICES` (keithley-2400, keysight-b1500), `_DEFAULT_GLOBAL_TECHNIQUES` (iv-sweep, iv-breakdown, iv-leakage), `get_global_device_config()`, `list_global_devices()`, `get_global_technique_config()`, `list_global_techniques()`. Hardcoded `_` separator in `get_file_naming_grammar()`. Updated `generate_default_config_yaml()` with file_naming, devices, techniques sections using `.replace()` (not `.format()`) to avoid YAML template conflicts.
- `cli/commands/config.py`: Added `config edit --global`, `config edit devices`, `config edit grammar`, `config edit techniques --global`, `config devices list`, `config grammar list|edit`.
- `memristor/db.py`: Schema v2 with universal grammar columns (technique_id, device_id, date_code, material, matrix, row, col, suffix). Added `populate_from_grammar()` — direct filename parsing without YAML. Added `populate_protocol_from_step_dirs()`. Added `update_file_analysis()` with current_compliance and compliance_confidence.
- `memristor/device_cli.py`: `cmd_sync()` rewritten as pure filename parsing. New `cmd_analyze()` command for CSV-based computation. `devices.yaml` is now optional.
- `memristor/dashboard.py`: Added `_collect_device_data_from_sqlite()` for reading pre-computed analysis. `generate_dashboard()` tries SQLite first, falls back to CSV.
- `core/technique.py`: Added `standardize_grammar_fields()` for universal field normalization. Added `_resolve_grammar_from_merged_config()` for 4-tier grammar resolution.
- `core/data_loader.py`: `_resolve_device_config()` falls back to `get_global_device_config()` if per-technique lookup fails.
- YAML template fix: `generate_default_config_yaml()` uses `.replace()` instead of `.format()` to prevent `KeyError` on YAML `{date_code}` etc.
- YAML escape fix: Regex patterns use single-quoted YAML scalars to avoid `\d`/`\w` escape errors.
- Final test suite: **78/78 passing** (GREEN).
