# Changelog

All notable changes to science-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

