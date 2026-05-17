# science-cli v2.1.1 — Scientific Data CLI for Memristor & Electrochemistry

A Python CLI for managing, plotting, and analyzing experimental data — IV curves, CV, CA, EIS, memristor switching, endurance, and retention. Built for researchers who work with measurement files in the terminal.

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](documentation/guides/installation.md) | Install from PyPI, source, or one-liner |
| [Electrochemistry](documentation/guides/electrochemistry.md) | CV, CA, EIS analysis & plotting workflow |
| [Memristor](documentation/guides/memristor.md) | Crossbar device characterization pipeline |
| [CHANGELOG](CHANGELOG.md) | Release history |

## Quick Install

```bash
# One-liner (auto-installs via pipx or pip):
curl -fsSL https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.sh | bash

# Requires Python 3.9+
pip install science-cli

# Or with pipx (isolated, recommended for CLI tools):
pipx install science-cli

# Or with uv (Rust-based, faster):
uv tool install science-cli

# From source (editable, for development):
git clone https://github.com/taixuann/science-cli.git
cd science-cli
pip install -e .
```

### Dependencies

`numpy`, `pandas`, `matplotlib`, `scipy`, `lmfit`, `plotly`, `textual`, `pyyaml`, `rich`, `prompt_toolkit`, `questionary`, `pyarrow`

## Three Interfaces

science-cli provides three interaction modes:

| Mode | Command | Description |
|------|---------|-------------|
| **CLI** | `sci <command> [args]` | Run one command and exit. Scriptable, pipeable. |
| **CLI-REPL** | `sci --repl` | `prompt_toolkit` interactive shell with persistent session state, tab-completion, and command history. Stays in a project context across commands. |
| **TUI** | `sci` (no args) | Full Textual terminal UI with live data browser, plot preview, fzf-integrated file picking, and mouse support. |

## Quick Start

```bash
# Create a project
sci add -m project -n my-experiment

# Open it
sci open -m project -n my-experiment

# Create a protocol with steps (optionally with technique + device per step)
sci add -m protocol -n 1_iv-test --step "1_set,2_reset" -t iv,iv -d keithley-2400,keithley-2400

# Assign data files to steps
sci add -m data --fzf

# Remove files from protocol step lists
sci delete -m data --fzf [--step <name>]

# Plot a file
sci plot protocol/1_iv-test/1_set/IV_data.csv

# Launch the dashboard
sci memristor dashboard --open
```

## Command Reference

```
GROUP 1: FILE MANAGEMENT
  add       Add project/protocol/metadata/data
  delete    Delete protocol/metadata/data
  edit      Edit protocol/metadata
  ls        List projects/protocols/steps/files

GROUP 2: CONTEXT NAVIGATION
  open      Open project/protocol/step
  close     Close context with auto-save

GROUP 3: DATA ANALYSIS
  plot      Plot data with themes, output PDF/SVG/PNG
  analyze   Run analysis, print results
  config    Manage settings (theme, techniques, devices, grammar)
  status    Show current context status
  results   List saved results by protocol and step

GROUP 4: DEVICE & TECHNIQUES
  memristor   Manage device matrices, sync/analyze, dashboard
  techniques  List available techniques and usage guide (deprecated → use config)
```

### Config Subcommands (Sprint 8)

```bash
config edit                           # Edit per-project sci-config.yaml
config edit --global                  # Edit global config
config edit devices                   # Edit global device registry
config edit grammar                   # Edit file naming patterns
config edit techniques --global       # Edit global technique registry
config devices list                   # List devices in global registry
config grammar list                   # List grammar patterns
config grammar edit                   # Edit grammar patterns
```

### Protocol Step Metadata Flags

Protocol steps now support a **step → technique → device** triplet. The `-d`/`--device` flag mirrors the `-t`/`--technique` pattern:

```bash
# Create protocol with device per step
sci add -m protocol -n 1_iv-test --step "1_set,2_reset" -t iv,iv -d keithley-2400,keithley-2400

# Add metadata with device
sci add -m metadata -pt 1_iv-test --step "1_set" -d keithley-2400

# Edit existing step devices (without adding new steps)
sci edit -m protocol -n 1_iv-test -d keithley-2400,keysight-b1500

# Edit metadata device
sci edit -m metadata -n 1_iv-test -d keithley-2400

# List protocol steps with Device column
sci ls -m protocol --step

# Output:
# ┌─────────┬────────────┬────────────────┬───────┬─────────────┐
# │ Step    │ Technique  │ Device         │ Files │ Description │
# ├─────────┼────────────┼────────────────┼───────┼─────────────┤
# │ 1_set   │ iv         │ keithley-2400  │ 2     │ ...         │
# │ 2_reset │ iv         │ keithley-2400  │ 3     │ ...         │
# └─────────┴────────────┴────────────────┴───────┴─────────────┘
```

## Memristor Device Management

For crossbar device characterization:

```bash
# Initialize a device matrix (writes device: section to protocol YAML)
sci memristor init --matrix r6-c6 --label "My Device"
sci memristor init --rows 4 --cols 4                        # label auto: "4x4 crossbar"
sci memristor init --matrix r6-c6 --pt 1_pda-memristor      # write to specific protocol YAML

# Add data files to matrix points
sci memristor add --fzf

# Sync: pure filename parsing → SQLite metadata (fast, no CSV read)
sci memristor sync

# Force: clear stale DB entries, re-scan from scratch
sci memristor sync --force

# Analyze: read CSVs, compute Vset/Vreset/ratio → update SQLite
sci memristor analyze

# Force re-analysis of all files
sci memristor analyze --force

# Single-file re-analysis
sci memristor analyze --file X.csv

# Generate per-protocol dashboard
sci memristor dashboard --open

# Generate cross-protocol project dashboard
sci memristor dashboard --all --open

# Show device matrix from SQLite (Rich Table with styled output)
sci memristor matrix

# Filter by technique with grid override
sci memristor matrix --grid r6-c6 --technique iv-sweep
```

### sync/analyze Split (Sprint 8)

`memristor sync` and `memristor analyze` are now separate commands:

- **`sync`** — Pure filename parsing. Scans step dirs, matches filenames against grammar patterns from config, extracts universal fields (date_code, material, technique, matrix, suffix), populates SQLite. No CSV reading, no IV analysis. Filters to memristor-only techniques (`iv-sweep`, `iv-breakdown`, `iv-leakage`, `mem-endurance`, `mem-retention`, `mem-switching`).
- **`sync --reconcile`** — Three-phase sync: (1) populate SQLite from step dirs, (2) sync sweep metadata back to protocol YAML enriched `files[]` entries, (3) prune stale files from SQLite and YAML that no longer exist on disk.
- **`analyze`** — CSV-based computation. Reads raw CSV files using device config, computes Vset/Vreset/ON/OFF ratio/compliance, updates SQLite analysis columns. Depends on `sync` having populated metadata first.

Workflow: `memristor sync` (metadata) → `memristor analyze` (computation) → `memristor dashboard` (visualization).

### Vset/Vreset Extraction

The dashboard auto-extracts switching parameters:
- **Vset/Vreset** — derivative-based detection (abrupt + gradual switching)
- **ON/OFF ratio** — computed at user-settable V_read (default 0.1V)
- **Yield** — fraction of cells with detected switching
- Results cached in `<project>.db` (SQLite) and `project/results/analysis_data.json`

## Project Structure

```
<project>/
├── <project_name>.db               # SQLite query cache (Sprint 6+) — canonical machine store
├── sci-config.yaml                 # Per-project config (inherits global defaults)
├── data/raw/                       # Raw measurement files
├── protocol/
│   └── <protocol_name>/
│       ├── <protocol_name>.yaml    # Protocol YAML — now includes device: section + enriched files[]
│       ├── devices.yaml            # Legacy — still read as fallback (deprecated write path)
│       ├── <step>/
│       │   ├── *.csv / *.txt       # Data files (symlinked from data/raw/)
│       │   └── results/            # Generated plots + per-protocol dashboard
│       └── ...
└── results/
    ├── dashboard.html              # Cross-protocol dashboard (via --all)
    └── analysis_data.json          # Dashboard render cache
```

## Supported File Formats

| Format | Extension | Source |
|--------|-----------|--------|
| CSV | `.csv` | Any (comma/tab separated) |
| Text | `.txt` | Any (tab separated) |
| Keysight Clarius+ | `.csv` (B1500A) | Keysight |
| Biologic | `.mpt` | Biologic |

Filenames follow **universal grammar fields** separated by `_` (hardcoded): `date_code_material_matrix_technique_suffix` (e.g., `140526_Ta-PDA-ITO_r0c0_iv_01.csv`). The 5 universal fields are: `date_code`, `material`, `technique`, `matrix`, `suffix`. Parenthesized suffixes like `(c)`, `(q)`, `(n)` in filenames are part of `material`, not batch/suffix.

## Theme System

Seven built-in themes:

| Theme | Use |
|-------|-----|
| `default` | Matplotlib defaults |
| `dark` | Dark background, for screens |
| `tufte` | Minimal ink, max data |
| `publication-acs` | ACS style (Helvetica, boxed, 600 DPI) |
| `publication-nature` | Nature style (Helvetica, spines off) |
| `poster` | Large fonts, conference posters |
| `acs-annotated` | ACS style with annotations |

```bash
sci config set theme publication-nature
sci plot data/sample_IV.csv    # → PDF with Nature styling
```

## Architecture

All functionality is built-in — no separate extension packages needed.

```
science-cli/
├── src/science_cli/
│   ├── cli/commands/              ← CLI command handlers
│   │   └── config.py              ← config edit --global, config devices, config grammar
│   ├── core/                      ← Config, data loading, technique detection, protocol YAML
│   │   ├── config.py              ← 4-tier config + global device/technique registry
│   │   ├── data_loader.py         ← Device-aware file → DataFrame (global fallback)
│   │   ├── technique.py           ← Grammar-based filename parsing (4-tier resolution)
│   │   ├── protocol.py            ← Protocol YAML read/write helpers (device section, enriched files)
│   │   ├── parquet_store.py       ← Parquet storage for analysis results
│   │   └── paths.py               ← Directory layout resolution
│   ├── memristor/                 ← Memristor analysis + dashboard (integrated library)
│   │   ├── dashboard.py           ← Plotly interactive HTML dashboard (SQLite fast path)
│   │   ├── device.py              ← DeviceConfig, protocol YAML integration + devices.yaml fallback
│   │   ├── device_cli.py          ← CLI commands (sync/analyze split)
│   │   ├── db.py                  ← SQLite query cache (v4 schema, sweep metadata columns)
│   │   ├── switching.py           ← Vset/Vreset extraction
│   │   ├── endurance.py           ← Endurance analysis
│   │   ├── retention.py           ← Retention analysis
│   │   └── plotting.py            ← CSV/TXT reader, SVG generation
│   ├── electrochem/               ← CV, CA, EIS analysis
│   ├── iv/                        ← IV analysis models
│   ├── theme/                     ← 7 themes + per-technique templates
│   └── tui/                       ← Textual TUI (full-screen UI)
└── test_guardrails.py             ← 58 architecture guardrail tests
```

## 4-Tier Config System

```
Hardcoded defaults (core/config.py)
       ↓ overridden by
Global config (~/.config/science-cli/config.yaml)     ← device registry, technique templates, grammar
       ↓ overridden by
Per-project config (<project>/sci-config.yaml)         ← type→step mapping, project overrides
       ↓ overridden by
Per-protocol metadata (protocol/<name>/...)
```

The global config acts as a central "library" for instrument configs (Keithley 2400, Keysight B1500A), technique templates (iv-sweep, endurance), and file naming grammar patterns. Project configs inherit from it and only override what's different.

**Config merge fix (2026-05-16):** `get_global_device_config()` and `get_device_config()` now properly merge user's `~/.config/science-cli/config.yaml` values over hardcoded defaults instead of returning early. For example, setting `header_lines: 21` in config.yaml for `keithley-2400` now correctly overrides the hardcoded `23`.

### Protocol YAML Device Section (2026-05-17)

Device geometry is now stored in the protocol YAML itself rather than a separate `devices.yaml`:

```yaml
# protocol/<name>/<name>.yaml
name: 1_pda-memristor
description: "PDA memristor characterization"

device:                          # NEW: optional device geometry
  rows: 6
  cols: 6
  label: "6x6 PDA Crossbar"
  cell_area_um2: 2500

steps:
  - name: 4_iv
    technique: iv-sweep
    device: keithley-2400
    files:
      - file: 0505_Ta-PDA-ITO(1)_r0c0_IV-DC_uc_01.csv
        sweep_order: 1           # NEW: sweep metadata enriched in file entries
        sweep_type: uc
        temperature: 300.0
```

**Device configuration resolution order:**
1. Protocol YAML `device:` section (new primary source for geometry)
2. Legacy `devices.yaml` (fallback — maintained for backward compat)
3. `read_devices()` dispatches: protocol YAML first → legacy fallback

**Key changes:**
- `memristor init --matrix r6-c6` writes the `device:` section to the protocol YAML
- `memristor sync` now also syncs sweep metadata back to protocol YAML `steps[].files[]` entries
- SQLite schema v4 adds `sweep_order`, `sweep_type`, `sweep_segments`, `temperature` columns
- `write_devices()` deprecated (warning emitted, still functional for backward compat)

### Matrix Display (v2.1.1)

Both `memristor ls --matrix` and `memristor matrix` display a grid of matrix cells:

- Rendered with **Rich Table** — `bold cyan` headers, `bold green` numbers for populated cells, `dim ----` for empty cells
- Column headers on TOP, row labels on LEFT
- Cell counts drawn from SQLite `cells` table (`memristor matrix`) or `devices.yaml` (`memristor ls --matrix`)

**`memristor matrix` flags:**
| Flag | Description |
|------|-------------|
| `--grid r6-c6` | Force specific grid dimensions (overrides protocol YAML) |
| `--material <name>` | Filter by exact material name |
| `--technique <name>` | Filter by technique (e.g., `iv-sweep`) |
| `--all` / `-A` | Show matrix for ALL protocols in the project |
| `--status` | Show summary of what's loaded in the database |

```bash
# Default grid from protocol YAML
sci memristor matrix

# Force 6×6 grid, filter by technique
sci memristor matrix --grid r6-c6 --technique iv-sweep

# All protocols with status summary
sci memristor matrix --all --status
```

## Global Device & Technique Registry (Sprint 8)

Built-in device library and technique configs shared across all projects:

**Built-in devices:**
- `keithley-2400` — Keithley 2400 SourceMeter (tab-delimited, 23 header lines)
- `keysight-b1500` — Keysight B1500A Semiconductor Analyzer (CSV, 48 header lines)

**Built-in techniques:**
- `iv-sweep`, `iv-breakdown`, `iv-leakage` — with grammar codes and default devices

Add new devices or techniques once via `config edit`:
```bash
sci config edit --global                # Edit global config in $EDITOR
sci config edit devices                 # Edit device registry section
sci config edit grammar                 # Edit file naming patterns
sci config edit techniques --global     # Edit technique registry
sci config devices list                 # List all registered devices
sci config grammar list                 # List grammar patterns
```

### Universal Grammar Fields

Every filename is parsed into 5 standardized fields:

| Field | Description | Example |
|-------|-------------|---------|
| `date_code` | Date in DDMMYY or YYYYMMDD | `140526` |
| `material` | Material/device name | `Ta-PDA-ITO` |
| `technique` | Measurement technique | `iv-sweep` |
| `matrix` | Crossbar position (rNcN or bN-tN) | `r0c0` |
| `suffix` | Order/cycle number | `001` |

Separator is hardcoded to `_` (underscore) — not configurable.

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/ -v
```

## Acknowledgments

This project was developed with assistance from [OpenCode](https://opencode.ai) —
an AI-powered coding assistant that helped implement features, write tests,
refactor code, and maintain documentation throughout the development lifecycle.

## License

MIT
