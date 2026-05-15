# science-cli v2.1.0 — Scientific Data CLI for Memristor & Electrochemistry

A Python CLI for managing, plotting, and analyzing experimental data — IV curves, CV, CA, EIS, memristor switching, endurance, and retention. Built for researchers who work with measurement files in the terminal.

## Quick Install

```bash
# Requires Python 3.9+
pip install science-cli

# Or from source:
git clone https://github.com/taixuann/science-cli.git
cd science-cli
pip install -e .
```

### Dependencies

`numpy`, `pandas`, `matplotlib`, `scipy`, `lmfit`, `plotly`, `textual`, `pyyaml`, `rich`, `prompt_toolkit`, `questionary`, `pyarrow`

## Usage Modes

Three ways to use science-cli:

```bash
# (1) Full TUI — interactive terminal UI
sci

# (2) REPL — raw prompt_toolkit shell
sci --repl

# (3) Direct — run one command and exit
sci add -m project -n my-experiment
sci plot data/sample_IV.csv
```

## Quick Start

```bash
# Create a project
sci add -m project -n my-experiment

# Open it
sci open -m project -n my-experiment

# Create a protocol with steps
sci add -m protocol -n 1_iv-test --step "1_set,2_reset" -t iv,iv

# Assign data files to steps
sci add -m data --fzf

# Plot a file
sci plot protocol/1_iv-test/1_set/IV_data.csv

# Launch the dashboard
sci memristor dashboard --open
```

## Command Reference

```
GROUP 1: FILE MANAGEMENT
  add       Add project/protocol/metadata/data
  delete    Delete protocol/metadata
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

## Memristor Device Management

For crossbar device characterization:

```bash
# Initialize a device matrix
sci memristor init --rows 4 --cols 4 --label "My Device"

# Add data files to matrix points
sci memristor add --fzf

# Sync: pure filename parsing → SQLite metadata (fast, no CSV read)
sci memristor sync

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
```

### sync/analyze Split (Sprint 8)

`memristor sync` and `memristor analyze` are now separate commands:

- **`sync`** — Pure filename parsing. Scans step dirs, matches filenames against grammar patterns from config, extracts universal fields (date_code, material, technique, matrix, suffix), populates SQLite. No CSV reading, no IV analysis.
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
│       ├── devices.yaml            # Matrix map — optional (grammar-based sync doesn't need it)
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

Filenames follow **universal grammar fields** separated by `_` (hardcoded): `date_code_material_matrix_technique_suffix` (e.g., `140526_Ta-PDA-ITO_r0c0_iv_01.csv`). The 5 universal fields are: `date_code`, `material`, `technique`, `matrix`, `suffix`.

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

```
science-cli/                       ← Core CLI + plotting + themes
├── src/science_cli/
│   ├── cli/commands/              ← CLI command handlers
│   │   └── config.py              ← config edit --global, config devices, config grammar
│   ├── core/                      ← Config, data loading, technique detection
│   │   ├── config.py              ← 4-tier config + global device/technique registry
│   │   ├── data_loader.py         ← Device-aware file → DataFrame (global fallback)
│   │   ├── technique.py           ← Grammar-based filename parsing (4-tier resolution)
│   │   ├── parquet_store.py       ← Parquet storage for analysis results
│   │   └── paths.py               ← Directory layout resolution
│   ├── memristor/                 ← Memristor analysis + dashboard
│   │   ├── dashboard.py           ← Plotly interactive HTML dashboard (SQLite fast path)
│   │   ├── device.py              ← DeviceConfig, devices.yaml I/O
│   │   ├── device_cli.py          ← CLI commands (sync/analyze split)
│   │   ├── db.py                  ← SQLite query cache (v2 schema, grammar population)
│   │   ├── switching.py           ← Vset/Vreset extraction
│   │   ├── endurance.py           ← Endurance analysis
│   │   ├── retention.py           ← Retention analysis
│   │   └── plotting.py            ← CSV/TXT reader, SVG generation
│   ├── electrochem/               ← CV, CA, EIS analysis
│   ├── iv/                        ← IV analysis models
│   ├── theme/                     ← 7 themes + per-technique templates
│   └── tui/                       ← Textual TUI
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

# Run tests (78 total)
pytest tests/ -v

# Branch: main (stable), refactor/2.1.0 (development)
```

## License

MIT
