# Changelog

All notable changes to science-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-05-13

### Breaking Changes
- Removed `project` command. Use `ls -m project`, `open -m project`, `add -m project`, `status -m project` instead
- Removed `project migrate` subcommand. Nested protocol layout is now the default
- Session state format changed to support 3-level memory (step, protocol, project)
- Removed `memristor` top-level command. Use `ext memristor <subcommand>` instead
- Removed `extensions` top-level command. Use `ext list` instead
- Removed all `--filter` CLI flags. Use `--fzf` for interactive selection
- `config` command now uses `set technique` instead of inline technique config
- Version reset from 7.0.0 to 2.0.0 reflecting actual feature maturity

### Added
- **Textual TUI**: Interactive terminal UI with SCI banner, matcha green theme, command echo with timestamps, slash commands (/help, /clear, /history, /version)
- **Plotly Interactive Dashboard**: Self-contained `dashboard.html` with zoom, pan, hover tooltips, click-to-expand cells, filter by material/sweep/cycle, PNG export — no server required
- **Cross-Protocol Dashboard**: `ext memristor dashboard --all` aggregates IV data from ALL protocols with per-protocol stacked heatmaps, material filter, toggleable Vset/Vreset markers
- **Analysis Cache**: `analysis_data.json` with mtime tracking for incremental re-analysis
- **Extension Integration**: science-memristor merged into core (`src/science_cli/memristor/`), science-iv recovered from .pyc (`src/science_cli/iv/`), science-electrochem recovered from .pyc (`src/science_cli/electrochem/`)
- **LVM Format Reader**: Support for Keithley 2400 LabVIEW Measurement (.lvm) tab-separated format
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
- `memristor` top-level command (use `ext memristor`)
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

## [Unreleased]

### Planned
- Type checking with mypy/pyright
- Ruff linting configuration
- pytest test suite with fixtures and parametrized tests
- CI/CD pipeline (GitHub Actions: lint → test → build)
- LICENSE selection (MIT/Apache 2.0)
- Requirements lock file
- CONTRIBUTING.md guide
- TUI module README
- Migration guide (1.x → 2.0.0)
