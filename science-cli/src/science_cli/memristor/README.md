# Memristor Module (`src/science_cli/memristor/`)

## Module Roles

| Module | Purpose |
|--------|---------|
| `device_cli.py` | CLI handlers for all `memristor` subcommands: init, ls, add, rm, info, sync, analyze, plot, dashboard |
| `db.py` | SQLite schema v2 — `files`, `cells`, `protocols`, `_meta` tables; CRUD; grammar-based population |
| `dashboard.py` | Plotly interactive HTML dashboard with SQLite fast path and YAML fallback |
| `switching.py` | IV parameter extraction — Vset, Vreset, ON/OFF ratio, compliance detection |
| `plotting.py` | Raw CSV/TSV reading (`read_iv_csv`) and SVG figure generation |
| `device.py` | Data models — `DeviceConfig`, `MatrixPoint`, `FileEntry` |
| `models.py` | Analysis result dataclasses — `SwitchingData`, `EnduranceData`, `RetentionData` |

## Pipeline: init → sync → analyze → dashboard

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│             │     │              │     │               │     │              │
│  init       │────▶│  sync        │────▶│  analyze      │────▶│  dashboard   │
│             │     │              │     │               │     │              │
└─────────────┘     └──────────────┘     └───────────────┘     └──────────────┘
                     │                     │                    │
                     │ Pure filename       │ CSV-based         │ Plotly HTML
                     │ parsing only        │ computation       │ interactive
                     │ (no CSV read)       │ (Vset/Vreset/    │ dashboard
                     │                     │  ratio/compliance)│
                     ▼                     ▼                    ▼
              ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
              │ SQLite:      │     │ SQLite:      │     │ SQLite read  │
              │ files (meta) │     │ files (ana-  │     │ (fast path)  │
              │ cells (agg)  │     │ lysis cols)  │     │ or YAML f/b  │
              | protocols    |     | cells (reagg)|     |              |
              └──────────────┘     └──────────────┘     └──────────────┘
```

### Step 1: `init` — Scaffold `devices.yaml`

```
memristor init --matrix r6-c6 --steps 4_iv
```

Creates a `devices.yaml` in the protocol directory defining the crossbar matrix dimensions. The `--steps` argument maps step directory names to their technique (auto-resolved from the protocol YAML). `--matrix rN-cN` is shorthand for `--rows N --cols N`.

### Step 2: `sync` — Populate SQLite from filenames

```
memristor sync
```

Scans step directories, parses every filename against the [grammar patterns](../core/technique.py) to extract `date_code`, `material`, `batch`, `technique`, `matrix` (row-col), and `suffix`. Fills the SQLite `files` table with metadata only — **no CSV content is read**. The `cells` table is also computed (aggregated per-cell stats).

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

## Key Design Decisions

- **Grammar-based filename parsing**: No manual YAML metadata needed for sync — the filename itself encodes all metadata fields. The grammar patterns are defined in the 4-tier config system (hardcoded → global → project → protocol).
- **SQLite as analysis cache**: The `.db` file is a materialized cache of filename metadata and computed IV parameters. It can always be rebuilt with `sync --reindex` followed by `analyze --force`.
- **Separation of sync and analyze**: `sync` (pure filename parsing) is fast and runs in seconds even for thousands of files. `analyze` (CSV reading + IV computation) is slower and skips previously analyzed files.
