# science-cli v2.0.0 — Scientific Data CLI for Memristor & Electrochemistry

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
  config    Manage settings (theme, techniques, devices)
  status    Show current context status
  results   List saved results by protocol and step

GROUP 4: EXTENSIONS & TECHNIQUES
  memristor   Launch cross-protocol dashboard, manage device matrices
  techniques  List available techniques and usage guide
```

## Memristor Device Management

For crossbar device characterization:

```bash
# Initialize a device matrix
sci memristor init --rows 4 --cols 4 --label "My Device"

# Add data files to matrix points
sci memristor add --fzf

# Sync sweep metadata from data files
sci memristor sync

# Generate per-protocol dashboard
sci memristor dashboard --open

# Generate cross-protocol project dashboard
sci memristor dashboard --all --open
```

### Vset/Vreset Extraction

The dashboard auto-extracts switching parameters:
- **Vset/Vreset** — derivative-based detection (abrupt + gradual switching)
- **ON/OFF ratio** — computed at user-settable V_read (default 0.1V)
- **Yield** — fraction of cells with detected switching
- Results cached in `project/results/analysis_data.json`

## Project Structure

```
<project>/
├── data/raw/                        # Raw measurement files
├── protocol/
│   └── <protocol_name>/
│       ├── devices.yaml             # Matrix map (rows, cols, sweep metadata)
│       ├── <step>/
│       │   ├── *.csv / *.txt        # Data files (symlinked from data/raw/)
│       │   └── results/             # Generated plots + per-protocol dashboard
│       └── ...
└── results/
    └── dashboard.html               # Cross-protocol dashboard (via --all)
```

## Supported File Formats

| Format | Extension | Source |
|--------|-----------|--------|
| CSV | `.csv` | Any (comma/tab separated) |
| Text | `.txt` | Any (tab separated) |
| Keysight Clarius+ | `.csv` (B1500A) | Keysight |
| Biologic | `.mpt` | Biologic |

Filenames should follow: `DDMMYY_material_type_matrix_suffix` (e.g., `0106_PDA_r0c0_iv_set_01.csv`)

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
│   ├── core/                      ← Config, data loading, technique detection
│   │   ├── config.py              ← 4-tier config (hardcoded → technique → global → project)
│   │   ├── data_loader.py         ← Device-aware file → DataFrame
│   │   ├── parquet_store.py       ← Parquet storage for analysis results
│   │   └── paths.py               ← Directory layout resolution
│   ├── memristor/                 ← Memristor analysis + dashboard
│   │   ├── dashboard.py           ← Plotly interactive HTML dashboard
│   │   ├── device.py              ← DeviceConfig, devices.yaml I/O
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

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest test_guardrails.py -v

# Branch: main (stable), mysci-tui_update (development)
```

## License

MIT
