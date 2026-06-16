# Memristor Characterization Guide

science-cli provides a complete pipeline for crossbar memristor device characterization — from raw measurement files to interactive dashboards.

Supported techniques:

| Technique | Code | Description |
|-----------|------|-------------|
| IV Sweep | `iv-sweep` | DC current-voltage sweep |
| IV Breakdown | `iv-breakdown` | Dielectric breakdown measurement |
| IV Leakage | `iv-leakage` | Leakage current measurement |
| Endurance | `mem-endurance` | Cycling endurance test |
| Retention | `mem-retention` | Data retention test |
| Switching | `mem-switching` | Bipolar/unipolar switching analysis |

## Pipeline Overview

```
memristor init            Setup device matrix geometry
    ↓
memristor sync            Parse filenames → SQLite metadata
    ↓
memristor analyze         Read CSVs → compute IV parameters
    ↓
memristor dashboard       Generate interactive HTML dashboard
```

## Step 1: Project Setup

```bash
sci config init                       # one-time: create global config
sci config edit --global              # set projects_root
sci add -m project my-memristor       # create project
sci open -m project my-memristor      # set as working project
```

Create a protocol with characterization steps:

```bash
sci add -m protocol -n pda-memristor \
  --step "1_iv-characterization,2_endurance,3_retention" \
  -t iv-sweep,mem-endurance,mem-retention \
  -d keithley-2400,keithley-2400,keithley-2400
```

## Step 2: Init — Device Matrix

If your sample is a crossbar array, initialize the device geometry:

```bash
sci memristor init --matrix r6-c6 --label "6x6 PDA Crossbar"
```

This writes a `device:` section to the protocol YAML:

```yaml
# protocol/pda-memristor/pda-memristor.yaml
device:
  rows: 6
  cols: 6
  label: "6x6 PDA Crossbar"
```

The `--matrix` flag is shorthand for `--rows N --cols N`. Without `--label`, it auto-generates one (e.g. "6x6 crossbar").

If your protocol file is in a different location:

```bash
sci memristor init --matrix r6-c6 --pt pda-memristor
```

## Step 3: File Naming Convention

Filenames encode metadata through a grammar-based system. The universal format is:

```
<date_code>_<material>_<matrix>_<technique>_<suffix>.csv
```

| Field | Description | Example |
|-------|-------------|---------|
| `date_code` | Date in DDMMYY format | `140526` |
| `material` | Material or device name | `Ta-PDA-ITO(c)` |
| `matrix` | Crossbar position (rNcN) | `r0c0` |
| `technique` | Measurement technique | `iv-sweep` |
| `suffix` | Cycle / replicate number | `001` |

Examples:

```
140526_Ta-PDA-ITO(c)_r0c0_iv-sweep_001.csv
140526_Ta-PDA-ITO(c)_r0c1_iv-sweep_002.csv
140526_Ta-PDA-ITO(c)_r1c0_iv-sweep_003.csv
150601_PDA-Au(q)_r3c3_mem-endurance_001.csv
```

Parenthesized suffixes like `(c)`, `(q)`, `(n)` in filenames are treated as part of `material`, not as batch/suffix fields.

Place raw data files in `<project>/data/raw/`. They will be symlinked into protocol step directories during assignment.

## Step 4: Assign Files to Steps

```bash
sci add -m data --fzf
```

This opens an interactive fzf selector. Pick your IV-sweep CSV files and assign them to `1_iv-characterization`, endurance files to `2_endurance`, etc.

## Step 5: Sync — Filename Parsing

```bash
sci memristor sync
```

Scans all step directories, matches filenames against grammar patterns, and populates SQLite with metadata. No CSV files are read — this is pure filename parsing and completes in seconds.

Key behaviors:

- **Only memristor techniques** are processed (`iv-sweep`, `iv-breakdown`, `iv-leakage`, `mem-endurance`, `mem-retention`, `mem-switching`). EC techniques (CV, CA, EIS) and fabrication steps (PVD, AFM) are skipped.
- The `files` table gets: `date_code`, `material`, `technique`, `matrix` (row, col), `suffix`, `technique_id`
- The `cells` table is computed — per-cell aggregate stats (file count per matrix position)

To also sync sweep metadata back to the protocol YAML and prune stale entries:

```bash
sci memristor sync --reconcile
```

Three-phase operation:
1. Populate SQLite from step directories
2. Read CSV headers → extract sweep segments, sweep type, temperature → write to SQLite `sweep_order`, `sweep_type`, `sweep_segments`, `temperature` columns → sync enriched file entries back to protocol YAML `steps[].files[]`
3. Remove stale entries from SQLite and YAML that no longer exist on disk

## Step 6: Analyze — IV Parameter Extraction

```bash
sci memristor analyze
```

Reads each raw CSV file using the device config (delimiter, header lines, column mapping). Computes:

- **Vset** — Set voltage (derivative-based detection)
- **Vreset** — Reset voltage
- **ON/OFF ratio** — Resistance ratio at V_read (default 0.1 V)
- **Compliance current** — Current compliance limit

Skips already-analyzed files. Force re-analysis:

```bash
sci memristor analyze --force
# Or for a single file:
sci memristor analyze --file X.csv
```

## Step 7: Dashboard — Interactive HTML

```bash
sci memristor dashboard --open
```

Generates a self-contained Plotly HTML dashboard (no server needed). Shows:

- **KPI cards**: Yield, mean Vset/Vreset, median ON/OFF ratio
- **Heatmap**: Clickable cell grid with color-coded switching parameters
- **IV curve overlays**: Select cells to overlay their I-V traces
- **Histograms**: Parameter distributions across the array

Cross-protocol dashboard (aggregates IV data from ALL protocols):

```bash
sci memristor dashboard --all --open
```

Dashboard reads from SQLite first (fast path), falls back to CSV reading if SQLite is unavailable.

## Matrix Display

View the device matrix layout with file counts:

```bash
sci memristor ls --matrix
```

Output:

```
┌─────┬──────┬──────┬──────┬──────┬──────┬──────┐
│     │  C1  │  C2  │  C3  │  C4  │  C5  │  C6  │
├─────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ R1  │  2   │  0   │  3   │  1   │  0   │  2   │
│ R2  │  1   │  4   │  0   │  2   │  1   │  0   │
└─────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

- R1→R6 rows (top→bottom), C1→C6 columns (left→right)
- Each cell shows file count from SQLite

Other `memristor ls` subcommands:

```bash
sci memristor ls              # list all devices
sci memristor ls --matrix     # matrix grid view
sci memristor info            # detailed stats for current protocol
sci memristor info --pt name  # detailed stats for a specific protocol
```

## Device Types

| Subcommand | Description |
|-----------|-------------|
| `init` | Initialize device matrix (writes to protocol YAML) |
| `add` | Add device data files (same as `add -m data`) |
| `ls` | List devices or show matrix grid |
| `info` | Show detailed protocol device stats |
| `rm` | Remove device data |
| `sync` | Filename-only SQLite population |
| `analyze` | CSV-based IV parameter computation |
| `plot` | Plot IV curves |
| `dashboard` | Generate interactive HTML dashboard |
| `check` | Validate device configuration |
| `stats` | Show file count statistics |
| `validate` | Validate device data integrity |

## Workflow Example: Full Session

```bash
# Setup
sci config init
sci config edit --global                          # set projects_root

# Project
sci add -m project pda-study
sci open -m project pda-study

# Protocol
sci add -m protocol -n pda-memristor \
  --step "1_iv,2_endurance,3_retention" \
  -t iv-sweep,mem-endurance,mem-retention \
  -d keithley-2400,keithley-2400,keithley-2400

# Device matrix
sci memristor init --matrix r6-c6 --label "PDA 6x6"

# Assign data
cp ~/data/*.csv data/raw/
sci add -m data --fzf

# Sync + analyze + dashboard
sci memristor sync --reconcile
sci memristor analyze
sci memristor dashboard --open
```

## Protocol YAML Structure

When you run `init`, `sync`, or `analyze`, the protocol YAML is updated to reflect the current state:

```yaml
name: pda-memristor
description: "PDA memristor characterization"

device:
  rows: 6
  cols: 6
  label: "PDA 6x6"

steps:
  - name: 1_iv
    technique: iv-sweep
    device: keithley-2400
    files:
      - file: 140526_Ta-PDA_r0c0_iv-sweep_001.csv
        sweep_order: 1
        sweep_type: uc
        temperature: 300.0
      - file: 140526_Ta-PDA_r0c1_iv-sweep_002.csv
        sweep_order: 1
        sweep_type: uc
        temperature: 300.0
```

The `device:` section is the **canonical source** for geometry. A legacy `devices.yaml` file is still read as fallback but `write_devices()` is deprecated.

## Built-In Device Configs

science-cli includes built-in instrument configurations:

| Device | Type | Delimiter | Header Lines |
|--------|------|-----------|--------------|
| `keithley-2400` | SourceMeter | Tab | 23 |
| `keysight-b1500` | Semiconductor Analyzer | Comma | 48 |
| `autolab-usth` | Potentiostat | Comma | custom |
