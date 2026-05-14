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
- **Status**: draft (Sprint 1-3 completed, Sprint 4 proposed)
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

### Sprint 4 Progress

- [ ] PLAN: Sprint 4 section created (this document)
- [ ] Feature F1: `open` clears step context, `ls` context-aware filtering
- [ ] Feature F2: `add -m data` sorted FZF display
- [ ] Feature F3: Rich table formatting for `ls`
- [ ] Feature F4: Remove global `ls -m file`
- [ ] Feature F5: Docs update (this entry)
- [ ] TEST: All guardrail tests pass
- [ ] COMMIT to `refactor/2.1.0` branch
