# Memristor Module (`src/science_cli/memristor/`)

## Module Roles

| Module | Purpose |
|--------|---------|
| `device_cli.py` | CLI handlers for all `memristor` subcommands: init, ls, add, rm, info, sync, analyze, plot, dashboard |
| `db.py` | SQLite schema v4 — `files`, `cells`, `protocols`, `_meta` tables; CRUD; grammar-based population; sweep metadata columns (`sweep_order`, `sweep_type`, `sweep_segments`, `temperature`) |
| `dashboard.py` | Plotly interactive HTML dashboard with SQLite fast path and YAML fallback |
| `switching.py` | IV parameter extraction — Vset, Vreset, ON/OFF ratio, compliance detection |
| `plotting.py` | Raw CSV/TSV reading (`read_iv_csv`) and SVG figure generation |
| `device.py` | Data models — `DeviceConfig`, `MatrixPoint`, `FileEntry`; protocol YAML integration; `read_devices()` dispatches to protocol YAML first, falls back to legacy `devices.yaml` |
| `models.py` | Analysis result dataclasses — `SwitchingData`, `EnduranceData`, `RetentionData` |

## Pipeline: init → sync → analyze → dashboard

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│             │     │              │     │               │     │              │
│  init       │────▶│  sync        │────▶│  analyze      │────▶│  dashboard   │
│             │     │              │     │               │     │              │
└──────┬──────┘     └──────┬───────┘     └───────┬───────┘     └──────┬───────┘
       │                   │                     │                    │
       │ Writes            │ Pure filename       │ CSV-based         │ Plotly HTML
       │ device: section   │ parsing + sweep     │ computation       │ interactive
       │ to protocol YAML  │ metadata extract    │ (Vset/Vreset/    │ dashboard
       │                   │                     │  ratio/compliance)│
       ▼                   ▼                     ▼                    ▼
┌──────────────┐    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Protocol     │    │ SQLite:      │     │ SQLite:      │     │ SQLite read  │
│ YAML         │    │ files (meta  │     │ files (ana-  │     │ (fast path)  │
│ device:{}    │    │  + sweep)    │     │ lysis cols)  │     │ or YAML f/b  │
└──────┬───────┘    │ cells (agg)  │     │ cells (reagg)│     │              │
       │            │ protocols    │     │              │     │              │
       │ syncs      └──────┬───────┘     └──────────────┘     └──────────────┘
       │ sweep back        │
       ▼                   ▼
┌──────────────────────────────────┐
│ Protocol YAML enriched files[]   │
│ file: X.csv, sweep_order: 1,    │
│ sweep_type: uc, temperature: 300 │
└──────────────────────────────────┘
```

### Step 1: `init` — Write device section to Protocol YAML

```
memristor init --matrix r6-c6 --steps 4_iv
memristor init --matrix r6-c6 --pt 1_pda-memristor   # target specific protocol
```

Writes the `device:` section (rows, cols, label) into the **protocol YAML** (`protocol/<name>/<name>.yaml`). No longer creates a separate `devices.yaml`. The `--steps` argument maps step directory names to their technique (auto-resolved from the protocol YAML). `--matrix rN-cN` is shorthand for `--rows N --cols N`. Optionally migrates legacy `devices.yaml` data with `--migrate`.

### Step 2: `sync` — Populate SQLite from filenames + sweep metadata

```
memristor sync
memristor sync --reconcile    # 3-phase: populate → sync sweep → prune stale
memristor sync --force         # Clear stale DB entries first, re-scan from scratch
```

Scans step directories, parses every filename against the [grammar patterns](../core/technique.py) to extract `date_code`, `material`, `batch`, `technique`, `matrix` (row-col), and `suffix`. Only processes files matching **memristor-only techniques** (`iv-sweep`, `iv-breakdown`, `iv-leakage`, `mem-endurance`, `mem-retention`, `mem-switching`) — EC techniques (CV, CA, EIS) and fabrication steps (PVD, AFM) are skipped. Fills the SQLite `files` table with metadata only — **no CSV content is read**. The `cells` table is also computed (aggregated per-cell stats).

**Symlink resolution:** `populate_from_grammar()` now resolves working symlinks to their real targets in `data/raw/`. Broken symlinks are silently skipped with a `continue`. This ensures symlinked data files are properly indexed by their target filename rather than the symlink name.

**New in v2.1.1:** After populating SQLite from filenames, `sync` also sweeps CSV headers for sweep metadata (sweep segments, sweep_type, temperature) and stores them in the new `sweep_order`, `sweep_type`, `sweep_segments`, and `temperature` columns. Then writes enriched file entries back to the protocol YAML via `sync_sweep_to_protocol_yaml()`. The `--reconcile` flag runs all three phases: (1) populate SQLite from step dirs, (2) sync sweep metadata back to protocol YAML, (3) prune stale files from both SQLite and YAML. The full data flow is:

```
CSV files → SQLite (canonical store) → protocol YAML (human-readable sync)
```

### Step 3: `analyze` — IV parameter extraction

```
memristor analyze [--force]
```

Reads each raw CSV file using the [device config](../core/config.py). Computes Vset, Vreset, ON/OFF ratio, and compliance current from IV curves using derivative-based detection. Skips already-analyzed files unless `--force`.

### Step 4: `dashboard` — Interactive HTML

```
memristor dashboard --open
```

Generates a self-contained Plotly HTML dashboard (no server needed). Shows KPI cards, clickable cell heatmaps, IV curve overlays, and histograms. Reads from SQLite first (fast path), falls back to YAML if unavailable.

## Matrix Display (`memristor matrix`)

The `memristor matrix` command renders a device grid from SQLite data using Rich Table:

```
memristor matrix [--all] [--material <name>] [--technique <name>]
                 [--grid r6-c6] [--status]
```

- **Rich Table styling:** `bold cyan` headers, `bold green` numbers for populated cells, `dim ----` for empty cells, with borders and `show_lines=True`
- **Grid dimensions** come from the protocol YAML `device:` section by default
- **`--grid r6-c6`** overrides the grid dimensions (independent of sync/workflow)
- **`--status`** shows a summary table of protocols, materials, cells, and files
- **`--all`** renders matrices for every protocol in the project database
- Material and technique filtering apply to which cells are shown

## Key Design Decisions

- **Grammar-based filename parsing**: No manual YAML metadata needed for sync — the filename itself encodes all metadata fields. The grammar patterns are defined in the 4-tier config system (hardcoded → global → project → protocol).
- **SQLite as analysis cache**: The `.db` file is a materialized cache of filename metadata and computed IV parameters. It can always be rebuilt with `sync --reindex` followed by `analyze --force`.
- **Separation of sync and analyze**: `sync` (pure filename parsing) is fast and runs in seconds even for thousands of files. `analyze` (CSV reading + IV computation) is slower and skips previously analyzed files.
