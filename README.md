# science-cli v3.20.0 — Scientific Data CLI for Memristor & Electrochemistry

A Python CLI for managing, plotting, and analyzing experimental data — IV curves, CV, CA, EIS, memristor switching, endurance, and retention. Built for researchers who work with measurement files in the terminal.

## Documentation

Full documentation is at [`documentation/INDEX.md`](documentation/INDEX.md) — the master navigation hub.

| Guide | Description |
|-------|-------------|
| [Documentation Index](documentation/INDEX.md) | Master navigation — all docs in one place |
| [Installation](documentation/reference/installation.md) | Install from PyPI, source, or one-liner |
| [Config System](documentation/reference/config-system.md) | 4-tier inheritance, 5-tier grammar, instrument registry |
| [Theme Reference](documentation/themes/theme-reference.md) | All 7 built-in themes, RC params, customization |
| [Protocol YAML Schema](documentation/schemas/protocol-yaml.md) | Protocol YAML structure and grammar |
| [Analysis YAML Schemas](documentation/schemas/analysis-yaml.md) | Per-technique analysis output schemas |
| [Crossbar Characterization](documentation/techniques/crossbar-characterization.md) | Memristor pipeline: init → sync → analyze → dashboard |
| [Electrochemistry](documentation/techniques/electrochemistry.md) | CV, CA, EIS analysis & plotting workflow |
| [CHANGELOG](CHANGELOG.md) | Release history |
| [sci-skill](sci-skill/) | AI-agent documentation — commands, config, studies, file formats |

### Documentation Directory Structure

```
sci-skill/               ← AI-consumable docs (curated for LLM agents)
├── SKILL.md              ← Entry point
├── INDEX.md              ← Navigation
├── COMMANDS.md           ← All commands
├── CONFIG.md             ← 4-module config system
├── STUDIES.md            ← Study/technique/device system
├── INSTRUMENTS.md        ← Hardware registry
├── PLOTTING.md           ← Plotting reference
├── ANALYSIS.md           ← Analysis reference
└── WORKFLOWS.md          ← Common workflows

documentation/
├── INDEX.md              ← Master navigation hub
├── reference/            ← Command reference, config system
│   ├── installation.md
│   ├── config-system.md
│   ├── commands/         ← Per-command reference (Phase 2)
│   └── four-interfaces.md (Phase 2)
├── techniques/           ← Per-technique guides
│   ├── crossbar-characterization.md
│   └── electrochemistry.md
├── workflows/            ← End-to-end workflows (Phase 4)
├── themes/
│   └── theme-reference.md
├── schemas/              ← YAML schema reference
│   ├── protocol-yaml.md
│   ├── analysis-yaml.md
│   └── config-yaml.md
├── api/                  ← Python API reference (Phase 4)
└── tutorials/            ← Step-by-step tutorials (Phase 4)
```

## Quick Install

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.sh | bash
```

### Windows
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
irm https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.ps1 | iex
```

### Manual Installation (all platforms)
```bash
# Requires Python 3.9+
pipx install science-cli     # recommended (isolated)
# or
pip install science-cli
```

### Using uv (fast, cross-platform)
```bash
uv tool install science-cli
```

### fzf Dependency

science-cli uses **fzf** for interactive file selection. The install scripts above will install fzf automatically. If you install manually, you need fzf separately:

- **macOS**: `brew install fzf`
- **Linux**: Download from https://github.com/junegunn/fzf/releases
- **Windows**: `winget install fzf` or download from https://github.com/junegunn/fzf/releases

### Dependencies

`numpy`, `pandas`, `matplotlib`, `scipy`, `lmfit`, `plotly`, `textual`, `pyyaml`, `rich`, `prompt_toolkit`, `questionary`, `pyarrow`

## Four Interfaces

science-cli provides four interaction modes:

| Mode | Command | Description |
|------|---------|-------------|
| **CLI** | `sci <command> [args]` | Run one command and exit. Scriptable, pipeable. |
| **CLI-REPL** | `sci --repl` | `prompt_toolkit` interactive shell with persistent session state, tab-completion, and command history. Stays in a project context across commands. |
| **TUI** | `sci` (no args) | Full Textual terminal UI with live data browser, plot preview, fzf-integrated file picking, and mouse support. |
| **AI Chat** | `sci chat "<query>"` | Natural language to `sci plot` commands via LLM. Also available as an OpenCode subagent (`plotting-guy`). |

### AI Agent Integration

science-cli is designed to be driven by AI agents (OpenCode, plotting-guy). Key commands:

```bash
# Full project manifest for AI consumption
sci info --json

# Machine-readable listing and status
sci ls --json
sci status --json

# Natural language plotting via LLM (set SCI_LLM_API_KEY env var)
sci chat "plot the IV data from protocol 1_iv-test with loglog axes"
```

AI agents discover project structure via `sci info --json`, find files, look up technique-specific flags, and construct `sci plot` commands. See [`AGENTS.md`](AGENTS.md) and [`SCHEMA.md`](SCHEMA.md) for the complete reference.

## Quick Start

```bash
# Create a project
sci add -m project -n my-experiment

# Open it
sci open -m project -n my-experiment

# Create a protocol with steps (optionally with technique + instrument per step)
sci add -m protocol -n 1_iv-test --step "1_set,2_reset" -t iv,iv --ins keithley-2400,keithley-2400

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
  info      Project manifest — machine-readable JSON (--json) for AI agents
  chat      AI chat — natural language to plot commands via LLM

GROUP 4: DEVICE & TECHNIQUES
  instrument  Hardware/instrument model registry (list, info, register, edit, rm)
  iv          IV sweep measurements (list, info, plot, analyze, sync, dashboard)
  pulse       Pulse measurements (endurance, retention, switching, STP, PPF)
  pvd         PVD deposition records (list, info, add, edit, analyze)
  raman       Raman spectroscopy: list, info, plot, analyze (with fzf)
  techniques  List available techniques and usage guide (deprecated → use config)
  memristor   [DEPRECATED] Use 'sci iv' or 'sci pulse' instead
```

### Raman Spectroscopy

Raman spectra from Horiba LabRAM HR Evolution (USTH) — 45-line `#` header with instrument metadata:

```bash
# List Raman files with laser/grating/range columns
sci raman ls

# Show full 30-field metadata table (pick with fzf)
sci raman info --fzf

# Plot spectrum with annotation (pick with fzf)
sci raman plot --fzf

# Analyze: baseline correction + normalization + peak finding + CSV export
sci raman analyze --fzf --baseline --norm --peaks

# Custom peak parameters
sci raman analyze --fzf --baseline --prominence 200 --distance 10
```

**Technique:** `raman` | **Device:** `horiba-usth` (tab-delimited, comma decimal, latin1, 45 header lines). Filenames match `*_raman*`, `*_sers*`, `*_raman-sers*`.

### Instrument Command (v3.10.0)

`sci instrument` manages the hardware/instrument model registry — the measurement equipment used for each technique:

```bash
# List all registered instruments
sci instrument ls

# List instruments compatible with a technique
sci instrument ls --technique iv-sweep

# Show instrument detail
sci instrument info keithley-2400

# Register a new instrument (opens $EDITOR with template)
sci instrument register new-instrument-name

# Edit an existing instrument config
sci instrument edit keithley-2400

# Remove an instrument from registry
sci instrument rm old-instrument --confirm

# Show instrument assignments in current protocol
sci instrument protocol 1_iv-test
```

**Built-in instruments:**

| Name | Type | Manufacturer | Techniques |
|------|------|-------------|------------|
| `keithley-2400` | sourcemeter | Keithley/Tektronix | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance |
| `keysight-b1500a` | parameter-analyzer | Keysight (SMU + WGFMU) | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance, pulse-stp, pulse-ppf |
| `biologic` | potentiostat | BioLogic | ec-cv, ec-ca, ec-eis |
| `horiba-usth` | raman-spectrometer | Horiba | raman |
| `iop-hanoi` | uv-vis-spectrometer | IOP | uv-vis |

Keysight B1500A uses **comma-delimited CSV** with variable header length per technique (245 lines for IV, 147 lines for pulse). The loader auto-filters `DataName` column rows, keeping only `DataValue` rows.

**Alias**: `sci ins` also works as shorthand for `sci instrument`.

### Two-Level Device System (v3.10.0)

The refactor clarified "device" into two distinct concepts:

#### Level 1: `--ins` (per-step, instrument)
The measurement **hardware** used for a technique, registered in config:

```bash
sci add -m protocol --step "1_set" -t iv-sweep --ins keithley-2400
sci edit -m protocol -n 1_iv-test --step "1_set" --ins keithley-2400
```

#### Level 2: `--devices` (per-protocol, device type)
The **device category** assigned per protocol. Determines analysis routing:

```bash
sci add -m protocol -n 1_iv-test --devices memristor
sci edit -m protocol -n 1_iv-test --devices junction
```

**Device types**: `memristor` (volatile, V_set only), `junction` (bipolar, V_set + V_reset), `deposition`, `pvd`, `electrochem`, `general`.

The `devices:` field in protocol YAML routes analysis to the correct library:

```yaml
# devices: memristor + technique: iv-sweep → library/iv/ (volatile mode: V_set only)
# devices: memristor + technique: pulse-stp → library/pulse/ (STP decay analysis)
# devices: junction  + technique: iv-sweep → library/iv/ (bipolar mode: V_set + V_reset)
```

### Technique Restructuring (v3.10.0)

The old `sci memristor` conflated device type with measurement technique. It has been split:

| Old | New | Purpose |
|-----|-----|---------|
| `sci memristor` | `sci iv` | IV sweep analysis (DC sweeps, V_set/V_reset) |
| `sci memristor endurance` | `sci pulse endurance` | Pulse endurance cycling |
| `sci memristor retention` | `sci pulse retention` | Retention decay analysis |
| — | `sci pulse stp` | STP decay (short-term plasticity) |
| — | `sci pulse ppf` | Paired-pulse facilitation |
| — | `sci pvd` | PVD deposition records |

`sci memristor` still works as a **deprecated alias** — it prints a warning and dispatches to `sci iv` or `sci pulse` based on subcommand context. It will be removed in v4.0.0.

**New technique taxonomy:**

| Technique | Scope | Analysis |
|-----------|-------|----------|
| `iv-sweep` | memristor, junction | V_set detection, ON/OFF ratio |
| `iv-breakdown` | memristor, junction | Breakdown voltage |
| `iv-leakage` | memristor, junction | Leakage current |
| `pulse-endurance` | memristor | Cycles to failure |
| `pulse-retention` | memristor | Retention decay |
| `pulse-stp` | memristor | STP decay time constant |
| `pulse-ppf` | memristor | PPF ratio vs interval |

### Unified Plotting with `--technique` (v3.10.0)

`sci plot` now accepts a `--technique` / `-t` flag to set the technique context and unlock technique-specific flags:

```bash
# Auto-detect technique from filename (existing behavior)
sci plot 140526_Ta-PDA-ITO_r0c0_iv_01.csv

# Explicit technique with technique-specific options
sci plot --technique raman file.txt --laser 632 --accumulation 3

# Per-technique plot subcommands are deprecated:
#   sci raman plot  →  sci plot --technique raman
#   sci ec plot     →  sci plot --technique ec
#   sci afm plot    →  sci plot --technique afm
```

**Technique-specific flags by technique:**

| Technique | Flags |
|-----------|-------|
| `raman` | `--laser`, `--accumulation`, `--acq-time`, `--nd-filter` |
| `ec-cv` | `--scan-rate`, `--cycles`, `--potential-range` |
| `ec-eis` | `--freq-range`, `--amplitude` |
| `uv-vis` | `--wavelength-range`, `--baseline-correction` |
| `afm` | `--cross-section`, `--colormap` |
| `iv-*` | `--loglog`, `--highlight` |

**Plot help layout (v3.11.0):** `sci plot --help` now renders plot subcommands as a 3-column Rich Table (Command | Description | Flags) with per-technique flag rows shown inline. THEME sections with 10+ flags auto-format into 2-3 columns via Rich Columns for compact display.

### Device-Type-Aware Dispatch (v3.15.0)

Studies shared across device types can have different plot/analysis behavior.
Use `--device-type`/`-dt` to explicitly specify the device type:
```bash
sci plot --device-type volatile-memristor file.csv --study pulse:pulse-endurance
```
When omitted, device type is auto-detected from the protocol YAML or config.

### Per-Technique YAML Schemas (v3.10.0)

Each technique now produces structured YAML analysis output in `results/<technique>_analysis.yaml`:

```bash
# Analyze with YAML output
sci analyze file.csv --yaml
```

**Available schemas:**

| Technique | YAML File | Key Fields |
|-----------|-----------|------------|
| IV sweep | `iv-sweep_analysis.yaml` | v_set, on_off_ratio, mode (volatile/bipolar) |
| Pulse endurance | `pulse-endurance_analysis.yaml` | cycles_to_failure, r_high/r_low drift |
| Pulse STP | `pulse-stp_analysis.yaml` | tau1, tau2, decay fit model |
| Pulse PPF | `pulse-ppf_analysis.yaml` | ppf_ratio vs interval, facilitation tau |
| Raman | `raman_analysis.yaml` | peak positions, assignments, FWHM |
| EC/UV-Vis | `ec-cv_analysis.yaml`, etc. | Per-technique spectra parameters |
| PVD | `pvd-deposition_analysis.yaml` | thickness, layer stack, deposition params |
| AFM | `afm_analysis.yaml` | thickness, roughness, scan size (existing) |

### 5-Tier Config Grammar System (v3.10.0)

Filename grammar now resolves across 5 tiers:

```
1. Hardcoded defaults (core/technique.py)
2. Global config (~/.config/science-cli/config.yaml)
3. Device-type grammar (technique defaults per device type)
4. Per-protocol grammar (<project>/protocol/<name>/<name>.yaml grammar: section)
5. Per-step grammar (syntax extension per step)
```

```bash
# Manage grammar patterns
sci config grammar list
sci config grammar edit
sci config grammar test "140526_Ta-PDA-ITO_r0c0_iv_01.csv"

# Set per-protocol grammar overrides
sci edit -m protocol -n 1_iv-test --grammar '{"technique_codes": {"iv": "iv-sweep"}}'
```

`sci config --help` now groups subcommands into categories:

```
GLOBAL:
  config edit --global             Edit global config
  config edit techniques --global  Edit global technique registry

THEME:
  config set theme <name>          Set default theme
  config list themes               List available themes

TECHNIQUE:
  config edit <technique>          Edit per-technique config
  config list techniques           List registered techniques

INSTRUMENT:
  config edit instruments          Edit instrument registry
  config instruments list          List registered instruments

GRAMMAR:
  config edit grammar              Edit file naming patterns
  config grammar list              List grammar patterns
  config grammar edit              Edit grammar patterns
  config grammar test <pattern>    Test a grammar pattern against a filename
```

### Protocol Step Instrument Flags

Protocol steps now support a **step → technique → instrument** triplet. The `--ins`/`--instrument` flag mirrors the `-t`/`--technique` pattern. The old `-d`/`--device` flag is **deprecated** (v3.11.0) but still accepted with a deprecation warning.

```bash
# Create protocol with instrument per step
sci add -m protocol -n 1_iv-test --step "1_set,2_reset" -t iv,iv --ins keithley-2400,keithley-2400

# Add metadata with instrument
sci add -m metadata -pt 1_iv-test --step "1_set" --ins keithley-2400

# Edit existing step instruments (without adding new steps)
sci edit -m protocol -n 1_iv-test --ins keithley-2400,keysight-b1500

# Edit metadata instrument
sci edit -m metadata -n 1_iv-test --ins keithley-2400

# Auto-detect technique from instrument (no -t needed)
sci add -m protocol -n 2_raman --step "1_raman" --ins horiba-usth

# List protocol steps with Instrument column
sci ls -m protocol --step

# Output:
# ┌─────────┬────────────┬────────────────┬───────┬─────────────┐
# │ Step    │ Technique  │ Instrument     │ Files │ Description │
# ├─────────┼────────────┼────────────────┼───────┼─────────────┤
# │ 1_set   │ iv         │ keithley-2400  │ 2     │ ...         │
# │ 2_reset │ iv         │ keithley-2400  │ 3     │ ...         │
# └─────────┴────────────┴────────────────┴───────┴─────────────┘
```

### results --move (v3.11.0)

`sci results --move` / `-m` creates **symlinks** from selected result files into `project/results/`:

```bash
# FZF multi-select result files across all protocol steps
sci results --move

# Symlinks created in project/results/; originals stay in place
# Auto-rename on name collision: file.pdf → file_1.pdf, file_2.pdf, etc.
```

Useful for collecting analysis outputs (PDFs, CSVs, PNGs) into a single directory for publication, presentations, or archival.

### analyze --technique (v3.11.0)

`sci analyze -t`/`--technique` selects files via FZF and routes them to technique-specific analyzers from the `TECHNIQUE_ANALYZERS` registry (13 entries):

```bash
# FZF file selection → technique-specific analyzer
sci analyze -t raman --peaks --baseline

# Per-technique flags with validation
sci analyze -t uv-vis --bandgap
sci analyze -t afm --roughness
sci analyze -t iv-sweep --vset-only --compliance
sci analyze -t pulse-stp --fit-model biexponential
sci analyze -t pulse-ppf --intervals 50,100,200

# Wrong flag for technique → warning
sci analyze -t raman --bandgap
# ⚠ Warning: --bandgap is not used by raman technique. Ignored.
```

**Per-technique flags:**

| Technique | Flags |
|-----------|-------|
| `raman` | `--peaks`, `--baseline`, `--prominence`, `--distance` |
| `uv-vis` | `--bandgap`, `--wavelength-range` |
| `iv-sweep` | `--vset-only`, `--compliance` |
| `afm` | `--roughness`, `--cross-section` |
| `pulse-stp` | `--fit-model` |
| `pulse-ppf` | `--intervals` |

**Deprecation:** `sci raman analyze`, `sci uv-vis analyze`, `sci afm analyze` are deprecated — use `sci analyze --technique <name>` instead. They still work but emit a deprecation warning.

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
| Keysight Clarius+ | `.csv` (B1500A) | Keysight — comma-delimited, variable header (245 IV / 147 pulse), `DataName` column auto-filtered |
| Biologic | `.mpt` | Biologic |

Filenames follow **universal grammar fields** separated by `_` (hardcoded): `date_code_material_matrix_technique_suffix` (e.g., `140526_Ta-PDA-ITO_r0c0_iv_01.csv`). The 5 universal fields are: `date_code`, `material`, `matrix`, `technique`, `suffix`. Parenthesized suffixes like `(c)`, `(q)`, `(n)` in filenames are part of `material`, not batch/suffix.

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
│   │   ├── technique.py           ← Grammar-based filename parsing (5-tier resolution)
│   │   ├── protocol.py            ← Protocol YAML read/write helpers (device section, enriched files, devices: field)
│   │   ├── analysis_output.py     ← Shared per-technique YAML writer (v3.10.0)
│   │   ├── routing.py             ← Device-type-aware library routing (v3.10.0)
│   │   ├── parquet_store.py       ← Parquet storage for analysis results
│   │   └── paths.py               ← Directory layout resolution
│   ├── memristor/                 ← Memristor analysis + dashboard (DEPRECATED compat shim, use library/iv/ or library/pulse/)
│   │   ├── dashboard.py           ← Plotly interactive HTML dashboard (SQLite fast path)
│   │   ├── device.py              ← DeviceConfig, protocol YAML integration + devices.yaml fallback
│   │   ├── device_cli.py          ← CLI commands (sync/analyze split)
│   │   ├── db.py                  ← SQLite query cache (v4 schema, sweep metadata columns)
│   │   ├── switching.py           ← Vset/Vreset extraction
│   │   ├── endurance.py           ← Endurance analysis
│   │   ├── retention.py           ← Retention analysis
│   │   └── plotting.py            ← CSV/TXT reader, SVG generation
│   ├── iv/                        ← IV sweep analysis (v3.10.0)
│   │   ├── device_cli.py          ← CLI logic for sci iv
│   │   ├── plotting.py            ← IV-specific plots
│   │   ├── switching.py           ← Vset/Vreset extraction
│   │   ├── metrics.py             ← Vset/Vreset extraction utilities
│   │   ├── volatile.py            ← Volatile memristor analysis (V_set only)
│   │   └── bipolar.py             ← Bipolar junction analysis (V_set + V_reset)
│   ├── pulse/                     ← Pulse measurement analysis (v3.10.0)
│   │   ├── device_cli.py          ← CLI logic for sci pulse
│   │   ├── endurance.py           ← Pulse endurance cycling
│   │   ├── retention.py           ← Retention decay analysis
│   │   ├── switching.py           ← Switching time analysis
│   │   ├── plotting.py            ← Pulse-specific plots
│   │   ├── models.py              ← Pulse data models
│   │   ├── analyze.py             ← Pulse analysis routines
│   │   ├── stp.py                 ← STP decay time constant fitting
│   │   └── ppf.py                 ← PPF ratio vs interval analysis
│   ├── pvd/                       ← PVD deposition records (v3.10.0)
│   │   ├── device_cli.py          ← CLI logic for sci pvd
│   │   ├── models.py              ← Deposition data models
│   │   ├── analyze.py             ← Deposition analysis
│   │   └── yaml_io.py             ← Read/write PVD YAML
│   ├── instruments/               ← Instrument model registry (v3.10.0)
│   │   ├── registry.py            ← Instrument CRUD (wraps config accessors)
│   │   ├── types.py               ← Model type categorizations
│   │   └── models.py              ← Instrument data models
│   ├── electrochem/               ← CV, CA, EIS analysis
│   ├── afm/                       ← AFM/SPM image analysis
│   ├── analysis/                  ← Per-technique YAML schema validators (v3.10.0)
│   │   └── validators.py          ← Mode-aware (volatile/bipolar) schema validation
│   ├── theme/                     ← 7 themes + per-technique templates
│   └── tui/                       ← Textual TUI (full-screen UI)
└── tests/                         ← 245 pytest tests (core, memristor, session, CLI, technique, config, grammar)
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
    instrument: keithley-2400
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
- `keysight-b1500a` — Keysight B1500A Semiconductor Parameter Analyzer (CSV, variable header: 245 IV / 147 pulse, SMU + WGFMU modules)
- `horiba-usth` — Horiba LabRAM HR Evolution (tab-delimited, comma decimal, 45 header lines)

**Built-in techniques:**
- `iv-sweep`, `iv-breakdown`, `iv-leakage` — with grammar codes and default devices (`keithley-2400`)
- `pulse-stp`, `pulse-ppf` — default device is `keysight-b1500a`

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
