# science-memristor — Memristor Characterization Extension

Analysis logic for memristor device characterization: switching statistics, endurance cycling, retention decay. **Plotting and theming are handled by science-cli**, not this extension.

Depends on `science-iv` for IV curve parameter extraction.

## Install

```bash
pip install -e tools/extensions/science-iv
pip install -e tools/extensions/science-memristor
```

`science-iv` must be installed first (cross-package dependency).

## Data Format

### Column naming conventions

The system recognizes these column names in IV data files:

| Domain | Recognized names |
|--------|-----------------|
| Time | `Time`, `Corrected time (s)`, `t/s`, `time/s` |
| Voltage | `Voltage (V)`, `Potential (V)`, `E (V)`, `BV`, `Bias Voltage (V)`, `bias_voltage` |
| Current | `Current (A)`, `I (A)`, `WE(1).Current (A)`, `Bi`, `Bias Current (A)`, `bias_current` |

**`Bi`** = bias current — the current flowing through the device under applied bias.
**`BV`** = bias voltage — the voltage applied across the device terminals.

This shorthand convention is common in semiconductor parameter analyzers (Keysight B1500A, Keithley 4200-SCS) and custom LabVIEW/Python measurement setups. The `B` prefix distinguishes applied bias from internally measured quantities.

**Example file** (`r0c0_IV.txt`):

```
Time    Bi          BV
0.0     1.2e-9      0.0
0.1     3.4e-8      0.1
0.2     2.1e-7      0.2
...
```

### Sweep metadata auto-detection

When `Bi`/`BV` files are assigned to protocol steps, sweep direction and rate are auto-detected from the data:

- **Column mapping**: `BV` → voltage, `Bi` → current, `Time` → time
- **Segment detection**: Voltage reversal points split the data into forward/reverse sweeps
- **Zero-crossing split**: Bipolar sweeps (e.g., `+V → 0 → -V`) are split at `V = 0`
- **Storage**: Per-file metadata written to protocol YAML or `devices.yaml`

See `PLAN.md` for the full crossbar device configuration system and `science-iv/README.md` for sweep detection details.

## Crossbar Device System

The `science-memristor` extension provides crossbar array device organization supporting **multi-technique measurements per matrix point**. Each (row, col) junction in a crossbar is a complete device under test — it may undergo IV characterization, endurance cycling, retention testing, and switching statistics, each producing one or more data files. See [`PLAN.md`](PLAN.md) for the full design document.

Key features:

| Feature | Description |
|---------|-------------|
| `devices.yaml` | Per-protocol YAML mapping files → (row, col) positions with multi-technique and cross-step support |
| `DeviceGeometry` model | Dataclass for array geometry (rows, cols, cell area) |
| `FileEntry` model | Dataclass for a single data file with sweep metadata, sweep type, temperature |
| `TechniqueGroup` model | Dataclass grouping files by technique (IV, endurance, retention, switching) at a point |
| `MatrixPoint` model | Dataclass for a (row, col) position holding multiple technique groups |
| `DeviceConfig` model | Aggregate config with query methods (get all IV files, technique coverage, etc.) |
| `memristor init` | Scaffold `devices.yaml` at protocol level with optional `--steps` mapping |
| `memristor ls --matrix` | Matrix map with per-technique status (I/E/R/S icons). Supports `--material` filter and per-material grids |
| `memristor ls --material "Ta-PDAc-ITO(1)"` | Filter matrix or point listing to a specific material+batch |
| `memristor info` | Show all techniques + files for a specific matrix point |
| `memristor add` | Add files with `--technique`, `--sweep-type`, `--sweep-order`. Auto-tags with material+batch from canonical filenames |
| `memristor add --fzf` | Interactive fzf file picker — scans all step directories recursively. Auto-tags with material+batch |
| `memristor add --pattern` | Batch regex assignment with preview and `--dry-run`. Auto-tags with material+batch |
| `memristor sync` | Auto-detect sweep metadata from IV files, resolves per-technique via `steps:` mapping |
| `memristor validate` | Check file refs, position bounds, duplicate sweep_order, step dir existence |
| `memristor rm` | Remove file entries, technique groups, or entire points |
| `memristor stats` | Technique coverage, measured cells, total files summary, **per-material IV coverage breakdown** |
| `memristor check --list` | Find unassigned files across all step directories recursively |
| `memristor plot --all` | Batch-generate publication-style IV curve SVGs for all IV files. Stores plot filenames in `devices.yaml` |
| `memristor plot --fzf` | Interactive fzf multi-select picker to choose which IV files to plot |
| `memristor plot --material "Ta-PDAc-ITO(1)"` | Plot all IV files for a specific material+batch |
| `memristor plot --row 0 --col 0` | Plot IV files at a specific cell position |
| `memristor plot --overwrite` | Re-plot even if SVGs already exist |
| `memristor dashboard` | Generate a self-contained HTML dashboard with per-material matrix grids and inline SVG plots |
| `memristor dashboard --open` | Generate dashboard and open in browser |
| `memristor dashboard --output custom.html` | Write dashboard to a custom path |
### `devices.yaml` preview (protocol-level with `steps:` mapping)

```yaml
device:
  id: "crossbar-4x4"
  label: "ITO/PDA/Ta 4×4"
  rows: 4
  cols: 4
  cell_area_um2: 10000

steps:                                  # ← technique → step subdirectory mapping
  iv: "4_iv-characterization"
  endurance: "5_endurance"
  retention: "6_retention"
  switching: "7_switching"

points:
  - row: 0
    col: 0
    techniques:
      iv:
        - file: "D1_r0c0_IV_set.txt"
          sweep_order: 1
          sweep_type: SET
          sweep:                          # Auto-populated by device sync
            - direction: forward
              sweep_rate_v_s: 0.1
              voltage_range: 2.0
              duration_s: 20.0
        - file: "D1_r0c0_IV_reset.txt"
          sweep_order: 2
          sweep_type: RESET
      endurance:
        - file: "D1_r0c0_endurance.txt"
      retention:
        - file: "D1_r0c0_retention.txt"
          temperature: 300
      switching:
        - file: "D1_r0c0_switching.txt"
    tags:
      - "forming"
      - "pristine"

  - row: 0
    col: 1
    techniques:
      iv:
        - file: "D1_r0c1_IV_set.txt"
          sweep_order: 1
          sweep_type: SET
      switching:
        - file: "D1_r0c1_switching.txt"
    # endurance and retention not measured at r0c1 → simply omitted
```

**Multi-technique design**: Each `point` lists only the techniques actually measured — if retention wasn't measured at r0c1, the `retention` key is simply absent. IV may have multiple files (SET + RESET) via `sweep_order`. The schema allows any technique key (not just the four standard ones), so adding CV or EIS per-point requires no schema changes.

**Cross-step resolution**: Files are resolved via `steps:` mapping. `iv` files live in `protocol/<proto>/4_iv-characterization/`, `endurance` files in `protocol/<proto>/5_endurance/`, etc. The `steps:` mapping is defined once at the device level; individual points simply reference filenames.

File location: `protocol/<protocol_name>/devices.yaml`

## Techniques Registered

| Technique | Label | Patterns | Description |
|-----------|-------|----------|-------------|
| `mem-switching` | Switching | `_switch`, `.sw`, `sw_`, `switch_` | V_set/V_reset statistics, Weibull, KS test |
| `mem-endurance` | Endurance | `_endurance`, `.end`, `end_`, `endurance` | DC/pulsed endurance cycling, failure detection |
| `mem-retention` | Retention | `_retention`, `.ret`, `ret_`, `retention` | Retention decay, 10-year extrapolation |

## Analysis Functions

### Switching

```python
from science_memristor.switching import analyze_switching

stats = analyze_switching(v_set, v_reset, t_set=None, t_reset=None)
# stats["v_set_mean"]        → mean SET voltage
# stats["v_reset_mean"]      → mean RESET voltage
# stats["v_set_cv"]          → coefficient of variation
# stats["weibull_set"]       → {V0, beta, polarity}
# stats["ks_set_vs_reset"]   → {statistic, p_value, different_distributions}
```

Weibull minimum distribution fitted to |V| magnitudes. KS test checks if V_set and V_reset distributions are significantly different (bipolar asymmetry detection).

### IV Parameter Extraction (cross-package)

```python
from science_memristor.switching import extract_iv_parameters

params = extract_iv_parameters(voltage, current, read_voltage=0.1)
# Delegates to science_iv.analyze.extract_resistance + extract_on_off_ratio
```

**Note**: When using `Time,Bi,BV` column format, pass columns explicitly:

```python
import pandas as pd
df = pd.read_csv("r0c0_IV.txt", sep="\t")
voltage = df["BV"].values    # BV → voltage
current = df["Bi"].values    # Bi → current
params = extract_iv_parameters(voltage, current)
```

### Endurance

```python
from science_memristor.endurance import analyze_endurance

stats = analyze_endurance(r_on, r_off, cycles)
# stats["failure_cycle"]    → first cycle where R_OFF/R_ON < 10 (or None)
# stats["weibull_fit"]      → {shape, scale, mean_cycles_to_failure}
# stats["trend_slope"]      → Ω/cycle degradation rate
# stats["ratio_tail_mean"]  → mean ratio over last 10% of cycles
```

### Retention

```python
from science_memristor.retention import analyze_retention

stats = analyze_retention(time, resistance)
# stats["decay_model"]         → "log" or "power" (selected by best R²)
# stats["extrapolated_10yr"]   → R at 10 years (Ω)
# stats["lifetime_hours"]      → hours to 50%/200% threshold crossing
```

Two models are fit: log-time (R = a·log₁₀(t) + b) and power-law (R = a·t^b). The better fit by R² is selected.

## Data Models

```python
from science_memristor.models import SwitchingData, EnduranceData, RetentionData

sd = SwitchingData(v_set=..., v_reset=..., t_set=..., t_reset=...)
ed = EnduranceData(cycles=..., r_on=..., r_off=...)
rd = RetentionData(time=..., resistance=..., temperature=300)
```

### Crossbar device models

```python
from science_memristor.device import (
    DeviceGeometry, FileEntry, TechniqueGroup, MatrixPoint, DeviceConfig,
    extract_material_batch,
)

# Load from protocol-level devices.yaml
config = read_devices("protocol/my-proto/")

# Access steps mapping
print(config.steps)  # {"iv": "4_iv", "endurance": "5_end", ...}

# Query points
point = config.get_point(row=0, col=0)

# Get all files for a technique at this point
for fe in point.get_files("iv"):
    print(f"  [{fe.sweep_type}] {fe.file}")

# Get all IV files across the array
iv_files = config.get_all_files("iv")

# Check technique coverage
print(config.technique_coverage)  # {"iv": 10, "endurance": 8, ...}

# Group points by material
material_groups = config.get_points_by_material()
# {"Ta-PDA-ITO(1)": [point, ...], "Ta-PDAc-ITO(1)": [point, ...]}

# Extract material+batch from a filename
material, batch = extract_material_batch("0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv")
# ("Ta-PDAc-ITO", "1")

# Resolve a file's physical path via steps mapping
path = config.resolve_file_path(
    Path("protocol/my-proto/"), "iv", "D1_r0c0_IV_set.txt"
)
# -> protocol/my-proto/4_iv/D1_r0c0_IV_set.txt
```

See [`PLAN.md`](PLAN.md) §4 for full data model specification.

## Plotting (handled by science-cli)

```bash
s-cli plot data/deviceA_endurance.csv --theme publication-acs
s-cli plot data/deviceA_switch.csv --theme publication-nature

# With Bi/BV columns — column detection handles "BV" → voltage, "Bi" → current
s-cli plot data/r0c0_IV.txt --theme publication-acs
```

science-cli selects the template, applies the theme, and outputs PDF. See `science-cli/README.md` for theme configuration and output options.

## IV Sweep Metadata

Memristor switching characterization depends on IV sweeps. When IV files are assigned to protocol steps, the science-iv extension auto-detects sweep direction and rate:

```
add -m data --fzf       # assign IV file to protocol step
                        # ↳ auto-detects sweep direction + rate
                        # ↳ stored per-file in protocol YAML
```

For crossbar arrays, sweep metadata is stored in the per-step `devices.yaml` (see `PLAN.md`).

See `science-iv/README.md` for sweep detection details.

## Typical Workflow

```
1. Measure:  sourcemeter records time(s), voltage(V), current(A) → CSV
2. Assign:   add -m data --fzf      (assign to protocol step)
3. Analyze:  s-cli analyze data.csv  (extract switching stats, Weibull, KS)
4. Plot:     s-cli plot data.csv --theme publication-acs   → PDF
```

**Crossbar workflow**:

```
# In the sci REPL or CLI:

1. memristor init --rows 4 --cols 4 --label "ITO/PDA/Ta 4x4" \
       --steps iv:4_iv,endurance:5_end,retention:6_ret,switching:7_sw
   (creates protocol/<proto>/devices.yaml with steps: mapping)

2. memristor add --fzf --filter ,iv,set
   (recursive scan across all step dirs, fzf picker, auto-parses row/col)

   # Or batch via regex pattern:
   memristor add --pattern 'D1_r(\d+)c(\d+)_IV_set\.txt' --technique iv --dry-run

3. memristor sync              (auto-detect IV sweep metadata per file)
4. memristor validate          (check file refs, step dirs, duplicates)
5. memristor ls --matrix       (matrix map with I/E/R/S status icons)
6. memristor check --list      (find unassigned files across all step dirs)
7. memristor stats             (technique coverage: 10 IV, 8 endurance, ...)
8. memristor plot --all         (generate IV curve SVGs → results/)
9. memristor dashboard --open   (HTML viewer for plotted SVGs)
```

## IV Curve Plotting

The `memristor plot` command batch-generates publication-style IV curve SVGs from all files tracked in `devices.yaml`:

```bash
# Plot all IV files
memristor plot --all

# Plot a specific material
memristor plot --material "Ta-PDAc-ITO(1)"

# Interactive fzf picker
memristor plot --fzf

# Re-plot existing SVGs
memristor plot --all --overwrite --dpi 300
```

**Output**: SVGs saved to `protocol/<name>/<iv_step>/results/` with naming convention:
`iv_r{row}c{col}_{material}_{sweep_type}_{order:02d}.svg`

e.g., `iv_r0c0_Ta-PDAc-ITO(1)_f_01.svg`

Each SVG includes:
- IV curve with voltage (x-axis) vs current (y-axis)
- Automatic log scale for current when span exceeds 2 decades
- **ACS publication style**: sans-serif font (Arial/Helvetica), no grid lines,
  inward tick marks, all four axes visible, black lines (0.8 pt)
- **Sweep-aware plotting**: bipolar sweeps (``f`` type) split into forward
  (black) and reverse (gray) segments; unipolar sweeps drawn as a single line
- **Title**: ``#01  |  0.10 V/s  |  0→+2V→0→-2V→0`` (file order, sweep rate, direction path)
- **Legend**: shows ``#01`` (or ``#01 fwd`` / ``#01 rev`` for bipolar sweeps), drawn without box frame; thin-axis spines on all four sides

Plot filenames are stored in `devices.yaml` as `FileEntry.extra["plot"]` for tracking.

### CSV column detection

The plotter auto-detects voltage and current columns from common conventions:
- `Time,BI,BV` (Keysight B1500A style)
- `Time,Current,Voltage`
- `Voltage (V)`, `Current (A)`, `Potential (V)`, etc.

Robust against embedded instrument metadata (common in Autolab exports) by reading only fully numeric data rows.

## Dashboard

The `memristor dashboard` command generates a self-contained HTML viewer for plotted SVGs:

```bash
# Generate dashboard
memristor dashboard

# Generate and open in browser
memristor dashboard --open

# Custom output path
memristor dashboard --output ~/Desktop/iv_dashboard.html
```

**Dashboard layout** (pure HTML+CSS, no JavaScript frameworks):
- **Header**: device label, total plots, generation date
- **Matrix row** (at page top): all material crossbar grids in a single horizontal
  flex row (scrollable) — clickable cell entries link to plot galleries below
- **Plot galleries** (grouped by `T#-B#  |  material  |  sweep_type`):
  - Each group has a heading like ``T1-B1  |  Ta-PDAc-ITO(1)  |  f``
  - Inline SVG gallery (2 per row) with captions showing cell, material, sweep type, and sweep parameters
- **Material-specific color coding** for matrix cells
- **Self-contained**: works with `file://` protocol — just open in a browser

### Programmatic access

```python
from science_memristor.plotting import (
    read_iv_csv,
    build_plot_filename,
    generate_iv_svg,
    collect_iv_files,
)
from science_memristor.dashboard import generate_dashboard
from science_memristor.device import read_devices

# Load config
config = read_devices("protocol/my-proto/")

# Collect IV files to plot
targets = collect_iv_files(config, material="Ta-PDAc-ITO(1)")

# Read CSV and generate SVG
for t in targets:
    voltage, current, info = read_iv_csv("path/to/file.csv")
    filename = build_plot_filename(t["row"], t["col"], t["material_key"], t["sweep_type"], t["order"])
    generate_iv_svg(voltage, current, {"title": filename}, f"results/{filename}")

# Generate dashboard
generate_dashboard(config, Path("results/"), Path("results/dashboard.html"))
```

## Material & Batch Tracking

Files following the canonical naming convention `DDMM_Material(Batch)_b#-t#_Technique_Type_##.csv` are auto-tagged with material+batch identifiers during `memristor add`. Tags are stored per `MatrixPoint` in `devices.yaml`:

```yaml
points:
  - row: 0
    col: 0
    techniques:
      iv:
        - file: "0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv"
    tags:
      - "material:Ta-PDAc-ITO(1)"
```

When material tags are present (or detectable from filenames), `--matrix` automatically splits the display into one grid per material+batch:

```bash
$ memristor ls --matrix

# Shows separate grids for each material:
#   Material: Ta-PDA-ITO (batch 1) — 8 cell(s)
#   Material: Ta-PDAc-ITO (batch 1) — 5 cell(s)
#   Material: Ta-PDAc-ITO (batch 2) — 2 cell(s)
#   Material: Ta-PDAq-ITO (batch 1) — 4 cell(s)
```

**Filter by material**: Use `--material` to view a single material+batch:

```bash
memristor ls --matrix --material "Ta-PDAc-ITO(1)"
memristor ls --technique iv --material "Ta-PDAc-ITO(1)"
```

**Stats breakdown**: `memristor stats` shows per-material IV coverage:

```
IV coverage by material:
  Ta-PDA-ITO(1):   8 cell(s)  (r0c0, r1c0, r2c0, r2c1, r3c0, r3c1, r4c0, r4c1)
  Ta-PDA-ITO(2):   3 cell(s)  (r1c0, r2c0, r3c0)
  Ta-PDAc-ITO(1):  5 cell(s)  (r0c0, r0c2, r1c2, r2c2, r3c2)
  Ta-PDAc-ITO(2):  2 cell(s)  (r0c0, r1c0)
  Ta-PDAq-ITO(1):  4 cell(s)  (r0c0, r1c0, r2c1, r2c3)
```

**Filename convention** (`extract_material_batch`):

| Filename | Material | Batch |
|----------|----------|-------|
| `0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv` | `Ta-PDA-ITO` | `1` |
| `0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv` | `Ta-PDAc-ITO` | `1` |
| `0605_Ta-PDAc-ITO(2)_b1-t1_IV-DC_f_01.csv` | `Ta-PDAc-ITO` | `2` |
| `0605_Ta-PDAq-ITO(1)_b1-t1_IV-DC_f_01.csv` | `Ta-PDAq-ITO` | `1` |

**For legacy data** (no tags): `get_points_by_material()` falls back to scanning filenames on each point to determine material groups. Tags are written on the next `memristor add` or `memristor sync`.

## Cross-Package Integration

```
science_memristor.switching.extract_iv_parameters()
    └── science_iv.analyze.extract_resistance()
    └── science_iv.analyze.extract_on_off_ratio()

science_memristor.device_config (planned)
    └── science_cli.core.sweep_metadata.extract_sweep_from_file()
    └── science_cli.core.sweep_metadata.detect_iv_columns()
```

## Dependencies

- numpy ≥ 1.20
- scipy ≥ 1.7
- lmfit ≥ 1.0
- science-iv ≥ 0.1.0
- science-cli (for CLI integration)
- PyYAML (for devices.yaml loading)
