# Changelog

All notable changes to science-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-06-02

### Added
- **Memristor Plotting Flags & Prompts**: Integrated custom Matplotlib styling parameter forwarding (`color`, `linestyle`, `linewidth`, `marker`, `markersize`, `zoom`, `grid`, `legend`) and theme overrides into `sci memristor plot`. Implemented interactive prompts for "Style / analysis options" and "Figure options" in FZF mode.
- **Protocol-Aware FZF Filtering**: Programmed FZF file selection to parse technique configurations from active protocol YAMLs for `raman`, `uv-vis`, and `ec` commands. The displayed list dynamically narrows to active protocol files mapping to matching techniques (`raman`, `uv-vis`, or starting with `ec-`), falling back to all raw files if no active protocol matches.
- **Automated Testing Coverage**: Added a comprehensive test suite `tests/test_core/test_fzf_technique_filtering.py` verifying protocol-aware FZF technique filtering under active protocol scopes.

### Changed
- **Plotting Fixes & Background Automation**: Resolved undefined `rprint` error in `raman.py`, enabled automatic FZF selection bypass when `--all` or `--overlay` is supplied in CLI args, and configured automated plotting modes to automatically save figures (`raman_<file_stem>.pdf` or `raman_overlay.pdf`) to results, avoiding GUI popup freezes.
- **Reverted Explicit --fzf Flag**: Reverted the redundant `--fzf` plot subcommand argument in `device_cli.py` while preserving interactive prompts and FZF file selection when positional arguments are omitted.

## [3.1.0] - 2026-06-02

### Added
- **Symmetric Characterization Plotting**: Fully aligned specialized plotting namespaces (`sci ec plot`, `sci uv-vis plot`, and `sci raman plot`) with the global `sci plot` capabilities. Added support for `--all` and `--overlay` flags in each namespace.
- **Robust FZF Protocol Filtering & Fallback**: Designed and implemented a smart intersection between technique-specific files and active protocol mapping. If technique files exist in the active protocol, FZF displays only those files; if none are assigned, it gracefully falls back to showing all raw files of that technique.
- **Technique Boundaries Check**: Symmetrical, strict validation gates in all specialized plot handlers (`ec`, `uv-vis`, and `raman`) preventing cross-technique file processing.
- **Safe Pandas Coercion in Raman Plotting**: Implemented robust numeric casting using `pd.to_numeric(..., errors='coerce')` in `raman.py` to prevent numpy `isnan` TypeErrors when loading custom textual file layouts with headers.

### Changed
- **Aligned Raman Plot Handler**: Restructured `_raman_plot` to match the clean, unified `(args: list) -> None` CLI handler signature, removing the complex `"--fzf"` internal flag and aligning it perfectly with `_ec_plot` and `_uv_plot`.
- **Simplified File Stripping**: Replaced regex column stripping with a clean, bulletproof `.split()[-1]` last-token extraction method to resolve filenames from FZF selections, regardless of column formatting.

## [3.0.0] - 2026-05-31

### Added
- **Premium React/Vite Frontend (`sci serve`)**: Full AI Studio-generated frontend with dynamic project switching, integrated Plotly dashboard, protocol/step navigation, gallery with PDF/PNG/SVG rendering, and lightbox viewer
- **Live Dashboard View on `sci serve`**: Crossbar heatmap with per-cell KPI overlay (Vset/Vreset/ON-OFF ratio), click-to-load IV curves, device-type classification display, histograms for Vset/Vreset/Ratio distributions
- **Multi-Cycle Highlight Plotting**: `generate_iv_highlighted_svg()` — highlight specific sweep cycles in color with grey background traces, Vset/Vreset annotations in legend, publication-Nature themed
- **Raw Current Plotting Support**: `raw_current` flag on `generate_iv_svg()` and `generate_iv_overlay_svg()` to disable automatic log-scale detection, preserving raw linear-scale current visualization
- **Device Classification & Materials DB**: SQLite materials table with `classify_and_populate_materials()` — automated device-type classification (volatile/short/non-volatile) based on Vset/Vreset/ratio heuristics
- **Device CLI (`memristor device`)**: Per-cell device-type override commands (`set-device-type`, `set-device-errors`) and matrix display with device-type coloring
- **Subcommand Grouped Help Menu**: `memristor` subcommands grouped by category with cleaner AI Studio-friendly output
- **Numpy Import Fix**: Robust numpy import handling in classification module
- **Manual Device Overrides**: CLI flags for overriding detected device classification per cell
- **`ls_cmd.py` Sorting/Search**: Improved step file listing with configurable sort and search
- **New Documentation Artifacts**: 9 planning and walkthrough documents for serve frontend, multi-cycle plot, device CLI, and raw plotting

### Changed
- **`sci serve` API Refactored**: Switched from `get_protocol_files()` to comprehensive `get_dashboard_data()` endpoint with SQLite-first, cache-fallback strategy — serves heatmap, histograms, device type breakdown, and KPI aggregates in a single call
- **Frontend Assets**: Replaced single-page gallery frontend with premium React/Vite bundled frontend (`index-DvsT4CeK.js`, `index-rv64M7Al.css`)
- **PDF Rendering**: PDF iframes now append `#toolbar=0` to hide native browser toolbars; PDFs/SVGs/PNGs natively scale to 100% canvas width and height
- **Gallery Layout**: Split gallery thumbnails into "Overlays & Summaries" (warm gold) and "Individual Sweeps" (indigo) categories with distinct styling
- **MIME Type Handling**: Custom `guess_type()` override in server guarantees correct JS/CSS MIME types for frontend assets
- **CLI Flags Cleanup**: Consolidated and cleaned up `memristor` CLI flags for consistency
- **`edit_cmd.py`**: Protocol edition path resolution improvements

### Fixed
- **Frontend Blank Page on React**: Resolved premium frontend blank page and file loading bugs
- **System Directory Filtering**: `__pycache__` and system directories filtered out from projects workspace list in serve API
- **PDF Thumbnail Magnifier Overflows**: Replaced PDF iframe thumbnails with custom SVG document icons in sidebar
- **Duplicate `_api_protocol_files` handler**: Missing handler for protocol file listing API endpoint restored
- **Test Suite**: Added `TestDbMaterialsAndClassification` tests for materials CRUD and device-type heuristics

## [2.0.0] - 2026-05-13

### Breaking Changes
- Removed `project` command. Use `ls -m project`, `open -m project`, `add -m project`, `status -m project` instead
- Removed `project migrate` subcommand. Nested protocol layout is now the default
- Session state format changed to support 3-level memory (step, protocol, project)
- Removed `memristor` alias. Use `memristor <subcommand>` directly
- Removed `extensions` top-level command. Use `ext list` instead
- Removed all `--filter` CLI flags. Use `--fzf` for interactive selection
- `config` command now uses `set technique` instead of inline technique config
- Version reset from 7.0.0 to 2.0.0 reflecting actual feature maturity

### Added
- **Textual TUI**: Interactive terminal UI with SCI banner, matcha green theme, command echo with timestamps, slash commands (/help, /clear, /history, /version)
- **Plotly Interactive Dashboard**: Self-contained `dashboard.html` with zoom, pan, hover tooltips, click-to-expand cells, filter by material/sweep/cycle, PNG export — no server required
- **Cross-Protocol Dashboard**: `memristor dashboard --all` aggregates IV data from ALL protocols with per-protocol stacked heatmaps, material filter, toggleable Vset/Vreset markers
- **Analysis Cache**: `analysis_data.json` with mtime tracking for incremental re-analysis
- **Extension Integration**: science-memristor merged into core (`src/science_cli/memristor/`), science-iv recovered from .pyc (`src/science_cli/iv/`), science-electrochem recovered from .pyc (`src/science_cli/electrochem/`)
- **CSV/TXT Format Support**: Reader for Keithley 2400 tab-separated format and Clarius+ CSV
- **Vset/Vreset Extraction**: Derivative-based IV parameter extraction with abrupt and gradual switching detection
- **ON/OFF Ratio Computation**: Per-sweep resistance ratio with configurable V_read
- **File Management**: `close -m project|protocol|step` with auto-save, `open -m step <id>` for step-level context
- **Config Expansion**:
  - Per-technique YAML config files at `~/.config/science-cli/techniques/<technique>.yaml`
  - Per-project device overrides at `<project_root>/devices.yaml`
  - `config set technique <name> <device>` — set default device for technique
  - `config edit <technique>` — open technique config in $EDITOR
  - `config list techniques` — list all configured techniques
  - `config list devices <technique>` — list devices for a technique
- **Parquet Support**: Processed features stored as `.parquet` files
- `CHANGELOG.md` — initial changelog following Keep a Changelog

### Changed
- `ls -m project` replaces `project list`
- `open -m project` replaces `project open`
- `add -m project` replaces `project create`
- `status -m project` replaces `project status`
- Commands reorganized into 4 groups: File Management, Context Navigation, Data Analysis, Extensions & Techniques
- `ext` is now the unified extension interface (replaces standalone `memristor`, `extensions`)
- Help menu now shows commands organized by group with descriptions
- TUI REPL prompt simplified to `sci>`
- TUI output now shows `> <command>` with right-aligned timestamp on single line
- `config` command updated with technique management subcommands
- All plots default to interactive Plotly (SVG generation removed)

### Removed
- `project` command and all subcommands
- `project migrate` subcommand
- `memristor` alias removed (use `memristor` directly)
- `extensions` top-level command (use `ext list`)
- All `--filter` CLI flags across all commands
- Dead code: `image.py`, `general.py`, `functions/` directory
- SVG-based dashboard generation (replaced by Plotly)
- `project.py` orphan handler

### Fixed
- TUI output format: command echo and timestamp now on one line
- Help table column alignment for grouped display
- Session state now persists across close/open cycles
- Extension entry points with non-callable handlers silently skipped

### Security
- No authentication or network features — all operations are local filesystem

## [2.1.0] - 2026-05-14

### Added
- **Sprint 4: UX Enhancements** — context-aware `ls`, FZF sorted `add -m data`, Rich table output, `results --fzf`, grouped display
- **Sprint 5: Techniques → Config Integration** — `config set techniques`, enhanced `config list techniques` with per-cell device config, `techniques` command deprecated as thin wrapper
- **Sprint 6: SQLite Query Cache** — `memristor/db.py` (4 tables, WAL mode, schema migration), dual-write on `sync`, SQLite read path in dashboard
- **Sprint 7: Config-Driven Technique Registry** — template-based filename naming grammar in `sci-config.yaml`, config-driven technique patterns, grammar-aware filename parsing
- **Project Health**:
  - MIT LICENSE file
  - CI/CD pipeline (`.github/workflows/ci.yml`)
  - `requirements.txt` from pyproject.toml
  - Ruff linting configuration (`ruff.toml`)
  - Mypy type checking config in `pyproject.toml`
  - pytest test suite (`tests/`) with fixtures, core/memristor/session/CLI tests
  - `CONTRIBUTING.md` developer guide
  - `MIGRATION.md` (1.x → 2.0.0)
  - TUI module README (`src/science_cli/tui/README.md`)

### Changed
- Commands reorganized to 4 groups (File Management, Context Navigation, Data Analysis, Extensions & Techniques)
- `ext` command removed — `memristor` is now a direct command
- `config list techniques` shows 4-column Rich table with per-cell device config
- Filename parsing is now config-driven via `file_naming` in `sci-config.yaml`
- All PLAN documentation statuses updated (Sprints 1-7 completed)

### Fixed
- Banner truncated by generic `Horizontal { height: 1 }` — now shows full SCI ASCII art
- Input row gap restored with `#input-row { height: 1 }`
- TUI separators restored and dimmed

## [2.1.1] - 2026-05-17

### Added
- **`-d`/`--device` flag for step metadata** — first-class `device` property on protocol steps, matching `-t`/`--technique`:
  - `add -m protocol`: comma-separated `-d`/`--device` per step
  - `add -m metadata`: set device for existing or new steps (technique no longer required)
  - `edit -m protocol`: set device on steps; `-d` without `--step` modifies existing steps
  - `edit -m metadata`: update device by step name
  - `ls -m protocol --step`: shows Device column in the Rich table
- **`memristor init --matrix` shorthand**: `--matrix r6-c6` as alternative to `--rows 6 --cols 6`
- **`memristor init --label` optional**: auto-generates `"NxM crossbar"` from dimensions when omitted
- **Consolidate devices.yaml into protocol YAML** (`core/protocol.py`):
  - New `device:` section in protocol YAML replaces legacy `devices.yaml`
  - `read_devices()` dispatches to protocol YAML first, falls back to `devices.yaml`
  - `memristor init --matrix` writes device geometry directly to protocol YAML
  - `write_devices()` deprecated with `DeprecationWarning`
  - SQLite schema v4: `sweep_order`, `sweep_type`, `sweep_segments`, `temperature` columns
- **`memristor sync --reconcile`**: 3-phase sync — populate SQLite → sync sweep metadata to YAML → prune stale files
- **Memristor-only technique filter**: DB skips EC techniques (CV, CA, EIS) and fabrication steps (PVD, AFM)
- **Grammar regex fix**: `(?P<technique>...)` named capture groups added to `cv-deposition` and `ca-doping` patterns
- **Matrix display**: R/C labels (R1→R6 top→bottom, C1→C6 left→right), column headers on top, file counts per cell from SQLite

### Changed
- **fzf TUI dispatch**: `tui/app.py` now uses `subprocess.run()` with stop/start application mode instead of `_TeeWriter` capture — avoids asyncio nesting issues
- **fzf execution**: `fzf_utils.py` uses `subprocess.Popen` with `/dev/tty` stderr instead of `pty.spawn()` — cleaner, cross-platform, no ANSI stripping needed
- **Repo restructured**: `git mv science-cli/* .` — repo root IS science-cli content, no more nested `science-cli/` prefix
- **`extensions/` removed from git tracking** (integrated as built-in modules)
- **`theme-previews/` removed from git tracking** (generated artifacts, gitignored)
- `.gitignore` switched to allowlist-based (`/*` + exceptions)
- `memristor/plotting.py`: removed start/end scatter markers (lime/red dots) from time-colored IV plots

### Fixed
- Config merge bug: `get_global_device_config()` and `get_device_config()` returned early from hardcoded defaults, ignoring user's `config.yaml` settings (e.g. `header_lines: 21` was silently overridden by hardcoded `23`)
- `ls_cmd.py`: handle enriched file entries (dicts with `file` key) in matrix display
- Matrix grid rendering: inverted axes, missing column headers

## [2.7.0] - 2026-05-28

### Added
- **Publication-Nature as Global Default Theme**: Full Nature journal compliance — Helvetica 5-7pt, ticks in, open axes (top/right spines off), 300/600 DPI, `pdf.fonttype=42` for editable vector output, Wong colorblind-friendly palette (black-first)
- **`sci serve` Interactive Dashboard Server**: Zero-dependency stdlib HTTP server with REST API endpoints (`/api/project`, `/api/protocol/{name}/summary`, `/api/protocol/{name}/heatmap`, `/api/protocol/{name}/device/{cell}/iv`, `/api/protocol/{name}/histograms`, `/api/gallery`) — serves Plotly.js-powered per-project protocol/step navigation
- **AI Studio Frontend Template**: Complete dashboard frontend (`documentation/frontend 2/`) with React + TypeScript + Vite, gallery page, Plotly.js integration
- **Per-Technique Plot Template Overrides**: `theme/plot-templates/` YAMLs now configure per-technique visual overrides (linewidth, markers, axis labels) on top of global theme

### Changed
- **Global Default Theme**: Changed from `publication-acs` to `publication-nature` across all 17 Python files — every plot command now defaults to Nature style
- **Theme Directory Rename**: `theme/themes/` → `theme/plot-theme/`, `theme/templates/` → `theme/plot-templates/` for clarity
- **fzf as Default Selection Mode**: All file/step/protocol selection uses fzf by default with manual fallback
- **Help Restructured**: Merged GROUP 4 into GROUP 3 as technique-specific subsection for cleaner DX
- **TUI Updated**: `_is_fzf_command` logic updated for fzf-as-default mode
- **Removed Migration Guide**: `documentation/README-1.0.0.md` deleted — `CHANGELOG.md` serves the same purpose
- **All 4 Active Plans Completed**: `refactor`, `ai_integration`, `dashboard`, `themes` — marked done

### Fixed
- **Plot Theme Compliance**: Overlay and single-plot commands (`_do_plot`, `_do_overlap`, `_do_eis_plot`) now read `rcParams` for figsize, linewidth, markersize, and DPI instead of hardcoded `(10,7)`, `1.5`, `6`, `150`
- **fzf Fallback**: Graceful fallback when active protocol has no files
- **Duplicate Step Names**: `add-metadata` and `edit-rm-step` now handle duplicate step names correctly

## [2.2.0] - 2026-05-28

### Added
- **Consolidated Library Namespace**: Added `src/science_cli/library/` package with `__init__.py` to organize technique-specific backends symmetrically.
- **Local AI Subagent**: Localized `plotting-guy` agent profile to the repository root under `.opencode/agents/plotting-guy.md` for project-contained plotting/visualization task orchestration.
- **New Active Workspace Plans**: Established four comprehensive date-prefixed active planning documents under `documentation/artifacts/` covering `refactor`, `ai_integration`, `dashboard`, and `themes`.
- **Strict Checklist Enforcement Rule**: Updated developer instructions in `RULES.md` and codebase documentation in `SCHEMA.md` to mandate real-time checklist checkbox updates (`[x]`) for active plans.

### Changed
- **Symmetric Technique Reorganization**: Consolidated and relocated standalone technique modules (`memristor/`, `electrochem/`, `iv/`) from the source root to `src/science_cli/library/`.
- **Refactored CLI Commands**: Reorganized technique imports in CLI modules (`memristor.py`, `analyze.py`, `eis.py`, `plot.py`) under `src/science_cli/cli/commands/` to map 1:1 to the consolidated library paths.
- **Comprehensive Import Migration**: Automatically executed package-wide python glob script refactoring all internal relative and absolute module references to nested `library/` paths.
- **Test Suite Realignment**: Updated entire unit test suite (`tests/`), including `tests/test_memristor/test_db.py` and `tests/test_guardrails.py`, to correctly reference consolidated namespaces.
- **Artifact Reorganization & Archiving**: Moved 23 historical legacy plans and reports from `documentation/artifacts/` to `documentation/artifacts/archive/` to keep the active planning workspace clean.

### Fixed
- **CLI Command Verification Tests**: Fixed expected command list validations in `tests/test_cli.py` to accurately verify all 16 registered CLI commands.
- **Recursive Import Resolver Error**: Resolved a `ValueError` in relative path calculation when scanning and compiling deeply nested submodules.

## [3.3.0] - 2026-06-06

### Added
- **AFM/SPM Image Analysis Module**: New `src/science_cli/library/afm/` backend wrapping AFMReader to load and analyze AFM/SPM images. Supports `.gwy` (Gwyddion), `.spm` (Bruker), `.ibw` (Igor/Asylum), `.jpk` (JPK), `.stp`/`.top` (WSxM) formats. Depends on `AFMReader>=0.0.7`.
- **AFM CLI Commands**: `sci afm ls|info|plot|analyze|export` registered under `src/science_cli/cli/commands/afm.py` for listing, inspecting, visualizing, analyzing, and exporting AFM data.
- **AFM Plotting Module**: Dedicated `src/science_cli/plot/afm.py` for publication-quality AFM image rendering with Nature-compliant colormaps, scale bars, and cross-section overlays.

## [3.7.0] - 2026-06-09

### Added
- **`sci serve` gallery improvements**: Auto-fit figures to viewing area (viewport-relative sizing), prev/next navigation buttons for browsing figures, and copy filename button (with "Copied!" indicator)
- **`scripts/patch-gallery-bundle.py`**: Repeatable patch script for gallery bundle modifications

## [3.6.0] - Unreleased

### Added
- **Categorized `--help` Flag Output**: Restructured `COMMAND_HELP` dicts from flat lists to categorized dicts (THEME / ANALYSIS / OUTPUT / OPERATION groups) for raman, uv-vis, ec, afm, plot, analyze, add, edit, delete commands. Updated `show_command_help()` to render category sub-headers.
- **Spectral Range in Raman fzf Pickers**: `sci raman ls`, `raman plot`, `raman info`, and `raman analyze` now display a `Range` column showing the spectral range (first-to-last Raman shift) computed from actual data via `_raman_spectral_range()`.

### Fixed
- **Robust Horiba Header Parsing**: Added `_load_raman_data()` which drops data rows where the first column starts with `#`, handling Horiba `.txt` files with variable header line counts (46 instead of 45) where `#AxisUnit[1]=1/cm` was incorrectly read as a data row.

## [3.5.0] - 2026-06-06

### Added
- **`raman analyze --overlay`**: When processing multiple files, renders all corrected spectra overlaid on a single figure with auto-generated title and color cycling.
- **`raman analyze --all`**: When processing multiple files, renders a subplot grid with each corrected spectrum in its own panel, including baseline (dashed) and peak markers.
- **`raman analyze --no-legend`**: Hides the legend on overlay and regular plots.
- **Multi-file `--ai` mode**: `sci raman analyze --ai` now supports multiple file selection via fzf, with agent recommendations applied across all chosen files.

## [3.4.0] - 2026-06-06

### Added
- **RamanSPy Preprocessing Pipeline (`sci raman analyze`)**: Full RamanSPy-powered pipeline with four-stage processing: denoising (Savitzky-Golay / Whittaker), baseline correction (ASLS, AIRPLS, ARPLS, Poly, ModPoly), normalization (Vector, MinMax, MaxIntensity, AUC), and peak detection with configurable prominence/distance/height/width thresholds.
- **Enhanced Analysis Plot**: Dedicated matplotlib figure showing raw data (gray), baseline curve (orange dashed), corrected/normalized spectrum (black), and annotated peaks (red scatter + text labels with wavenumber annotations).
- **Automatic Text Report**: `{prefix}_report.txt` written alongside CSV exports, containing file metadata (laser, ND filter, acq time, accumulations), full pipeline description, detected peaks table (shift, intensity, prominence, FWHM), and summary statistics.
- **`--ai` Interactive Wizard**: New `sci raman analyze --ai` mode that delegates flag recommendations to the `sci-raman` opencode agent (mimo-v2.5-pro). Picks files via fzf, extracts spectral metadata, sends a structured JSON payload to the agent, parses the returned JSON recommendations (flags with reasoning), and applies the normalized flags automatically. Includes flag name normalization with aliases (e.g. `savgol:7:3`, `area` → `auc`).
- **`sci-raman` Agent**: Created agent definition at `tools/science-cli/.opencode/agents/sci-raman.md` with domain expertise in Raman spectroscopy preprocessing and band assignment.
- **`sci-raman` Skill**: Created skill at `tools/science-cli/.opencode/skills/sci-raman/SKILL.md` providing Raman peak table references and preprocessing guidance for the agent.
- **Updated Help Text**: Enhanced `raman analyze` help description covering pipeline, enhanced plot, text report, `--ai` mode, and all CLI flags.

### Changed
- **Raman Analyze Interactive Prompt**: Replaced static flag defaults with a guided step-by-step interactive pipeline builder for denoising, baseline, normalization, peak finding, and plot generation.
- **RamanSPy Integration**: Under-the-hood migration from manual scipy processing to RamanSPy's preprocessing modules (`rp.preprocessing.denoise`, `rp.preprocessing.baseline`, `rp.preprocessing.normalise`) with standardized spectrometer object handling.

