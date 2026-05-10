# science-cli — Scientific Data Analysis CLI

Core engine for scientific data analysis. Handles **plotting, theming, output formatting, and CLI orchestration**. Extensions (science-iv, science-memristor, science-electrochem) provide domain-specific analysis, device management, dashboards, and column mappings.

## Architecture

```
science-cli (core)              ← themes, plotting, CLI, config, project/file mgmt
  ├── science-iv                ← IV analysis, column maps, plot presets
  ├── science-memristor         ← memristor analysis, devices.yaml, dashboard, plot presets
  └── science-electrochem       ← electrochemistry analysis, column maps, plot presets
```

**Core (`science_cli/core/`)** — library layer: session, project paths, data loading, technique detection, file utilities, legacy shims.
**Plot engine (`science_cli/plot/`)** — technique-specific plotting (CV, CA, EIS, base, overlays), figure creation, save utilities.
**Theme system (`science_cli/theme/`)** — 3-tier themes + per-technique templates.
**CLI dispatch (`science_cli/cli/commands/`)** — handlers for all commands, delegates work to core and plot modules.

Extensions register techniques, analyzers, plot presets, and **column maps** via `ExtensionRegistry`. The core detects technique from filename, auto-resolves columns using the registry, runs analysis, and plots — all through a unified `sci plot` / `sci analyze` interface.

## Theme System

Three-tier system inspired by LabPlot:

| Tier | Purpose | Location |
|------|---------|----------|
| **Theme** | Global style: colors, fonts, grid, axes, figure size, DPI | `src/science_cli/theme/themes/*.yaml` |
| **Template** | Per-technique defaults: linewidth, marker, axis labels | `src/science_cli/theme/templates/*.yaml` |
| **Plot Presets** | Per-extension plot config: plot type, axis labels | Extension `__init__.py` |

### Available Themes

| Theme | Description |
|-------|-------------|
| `default` | Matplotlib defaults, balanced |
| `tufte` | Minimal ink, max data |
| `dark` | Dark background, for screens |
| `publication-acs` | ACS style: Helvetica 6-9pt, boxed axes, 600 DPI |
| `publication-nature` | Nature style: Helvetica 5-7pt, top/right spines off |
| `poster` | Large fonts, high contrast, for conference posters |

### Set Theme

```bash
sci config set theme publication-nature
sci config set theme publication-acs
```

### Theme YAML Structure

Each theme file defines:

```yaml
figure:
  facecolor: white
  figsize: [3.46, 2.75]    # inches (Nature: 88 mm single column)
  dpi: 300
axes:
  edgecolor: black
  spines_top: false          # Nature: top/right off
  spines_right: false
font:
  family: sans-serif
  size: 7
  axes_labelsize: 8
colors:
  prop_cycle:
    - "#0072B2"             # ACS/Nature color palette
    - "#009E73"
    - ...
savefig:
  dpi: 600
  bbox: tight
  format: pdf               # ALWAYS use PDF for publication
```

## Output Format — Always PDF

science-cli defaults to **PDF** output for publication-quality vector graphics:

```bash
sci plot data/sample_IV.csv                          # → sample_IV.pdf
sci plot --theme publication-acs data/sample_IV.csv
sci plot --output figure.pdf data/sample_IV.csv
```

PNG is only for quick previews. All publication figures must use PDF.

## Plotting

```bash
# Basic plot with current theme
sci plot data/sample_IV.csv

# Specify theme
sci plot --theme publication-nature data/sample_EIS.csv

# Custom output
sci plot --output ~/Desktop/figure.pdf data/sample_CV.csv

# Overlay multiple files
sci plot data/sample_IV_1.csv data/sample_IV_2.csv
```

### EIS Plotting

EIS files are auto-detected from filename patterns (`.mpt`, `_EIS.`, `.eis`, `.z`). When an EIS file is detected, the plotting engine switches to dedicated EIS visualizations instead of a generic line plot:

```bash
# Default (no EIS flags): generates BOTH Nyquist + Bode as separate PDFs
sci plot -f sample_EIS.csv
# → sample_EIS_nyquist.pdf + sample_EIS_bode.pdf

# Nyquist only (Z' vs -Z'')
sci plot -f sample_EIS.csv --nyquist
# → sample_EIS_nyquist.pdf

# Bode only (|Z| + phase vs frequency)
sci plot -f sample_EIS.csv --bode
# → sample_EIS_bode.pdf

# Circuit fitting + Nyquist overlay
sci plot -f sample_EIS.csv --circuit RRC
# → sample_EIS_circuit_fit.pdf + sample_EIS_fit_results.csv

# Bare --circuit: auto-fit ALL models, pick best R²
sci plot -f sample_EIS.csv --circuit
# → tries RRC, RQR, RsRQW, RsRCW; uses winner

# Specify a particular model
sci plot -f sample_EIS.csv --circuit RsRQW

# Available circuit models:
#   RRC    — Rs + (Rct || Cdl)               [3 params: Rs, Rct, Cdl]
#   RQR    — Rs + (Rct || CPE)               [4 params: Rs, Rct, Q_mag, Q_n]
#   RsRQW  — Rs + CPE || (Rct + Warburg)     [5 params: Rs, Rct, Q_mag, Q_n, sigma]
#   RsRCW  — Rs + C || (Rct + Warburg)       [4 params: Rs, Rct, C, sigma]

# Kramers-Kronig validation
sci plot -f sample_EIS.csv --kk
# → prints KK test result (pass/fail + consistency score)
```

**Circuit fit console output** (with parameter % errors):

```
Circuit: RsRQW  R²=0.9998  red. χ²=1.23e-04
  Rs      1.234e+02  ±   0.5%  (stderr: 6.170e-01)
  Rct     4.567e+03  ±   1.2%  (stderr: 5.480e+01)
  Q_mag   1.234e-06  ±   3.1%  (stderr: 3.830e-08)
  Q_n     9.012e-01  ±   0.8%  (stderr: 7.210e-03)
  sigma   1.234e+02  ±   2.1%  (stderr: 2.590e+00)
```

**Circuit fit CSV format** (`*_fit_results.csv`):

```csv
parameter,value,stderr,error_pct,unit
Rs,1.000e+02,2.500e+00,2.50,Ω
Rct,1.000e+03,1.500e+01,1.50,Ω
Cdl,1.000e-06,5.000e-09,0.50,F

# Fit quality
r_squared,0.998000,,,
reduced_chi_squared,0.001000,,,
```

**Column aliases**: EIS data columns are resolved from filenames. Supported aliases include `ReZ`/`ImZ` (from Autolab `.txt` files), `Z' (Ω)`/`-Z'' (Ω)`, `Re(Z)`/`Im(Z)`, and variants.

### Technique Detection

`sci plot` auto-detects the technique from filename patterns using `core/technique.py` (which merges hardcoded patterns with extension-registered patterns from `ExtensionRegistry`). The matching template (line style, axis labels) and column map are then applied automatically.

### Column Resolution

When plotting or analyzing, the system resolves which columns to use via a 3-tier fallback:
1. **Registry `ColumnMap`** — extension-registered preferred columns + aliases (most reliable)
2. **Hardcoded per-technique aliases** — built-in fallback for each technique family
3. **First two numeric columns** — universal last-resort fallback

Extensions define `ColumnMap(name, x, y, x_label, y_label, x_aliases, y_aliases, extras)` in their `register()` function. See extension READMEs for their specific column mappings.

## Template Files

`src/science_cli/theme/templates/*.yaml` define per-technique plot defaults:

- `iv-sweep.yaml` — line plot, V vs I
- `iv-breakdown.yaml` — line plot, V vs I
- `iv-leakage.yaml` — line plot, V vs |I|
- `ec-cv.yaml` — line plot, Potential vs Current
- `ec-ca.yaml` — line plot, Time vs Current
- `ec-eis.yaml` — Nyquist, Z' vs -Z''
- `mem-switching.yaml` — scatter, Cycle vs Voltage
- `mem-endurance.yaml` — line, Cycle vs Resistance
- `mem-retention.yaml` — line, Time vs Resistance

## Extension Interface

Extensions register with science-cli via `ExtensionRegistry`:

```python
from science_cli.extensions import ColumnMap, ExtensionRegistry, TechniqueDef

def register(registry: ExtensionRegistry):
    registry.name = "science-iv"

    # Techniques
    registry.techniques["iv-sweep"] = TechniqueDef(
        name="iv-sweep", label="IV Sweep",
        patterns=["_IV.", ".iv", "iv_", "_sweep", "sweep_"],
        description="Current-Voltage sweep",
    )

    # Analyzers
    registry.analyzers["iv-sweep"] = extract_resistance

    # Plot presets
    registry.plot_presets["iv-sweep"] = {
        "type": "line",
        "xlabel": "Voltage (V)",
        "ylabel": "Current (A)",
    }

    # Column maps — core resolves columns from these automatically
    registry.column_maps["iv-sweep"] = ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
        x_aliases=["BV", "bias_voltage", "Potential (V)", "WE(1).Potential (V)"],
        y_aliases=["Bi", "bias_current", "WE(1).Current (A)"],
    )
```

The `ColumnMap.resolve(columns)` method tries the preferred `x`/`y` columns first, then falls back through `x_aliases`/`y_aliases` against the actual column headers in the data file. This replaces the old approach of hardcoding column detection in `sweep_metadata.py` and `plot.py`.

## Project Management

```bash
sci project create <name>       # Create new project (dirs: data/raw/, protocol/, results/)
sci project open <name>         # Switch active project (resets protocol state)
sci project list                # List all projects
```

- `project create` creates only `data/raw/` (no `data/processed/`).
- `project open` clears the active protocol and step — switching projects resets the session state.
- Creating a protocol (`sci add -m protocol`) does **not** auto-activate it. Use `sci open -m protocol -n <name>` to set it as the active context.

## CLI Commands

```bash
sci parse   <file>               # Parse and display data summary
sci analyze <file>               # Run analysis, print results
sci plot    <file> [options]     # Plot with themes, output PDF
sci config  get/set <key> <val>  # Manage config (theme, etc.)
```

### Protocol Context

```bash
sci open -m protocol -n <name>    # Set active protocol (context for plot/analyze)
sci close -m protocol             # Clear active protocol, return to project level
sci open -m protocol --close      # Alias: same as close -m protocol
```

After opening a protocol, the REPL prompt shows `(sci project protocol)`. Plot and analyze commands auto-reference that protocol's files. Close returns to `(sci project)` project-level mode.

All commands work in both direct CLI mode and the interactive REPL (`sci` or `sci --repl`).

## Protocol System — Sweep Metadata

Protocols assign data files to technique steps. When files are assigned to IV-related techniques, the system auto-detects **sweep segments** (direction, rate) and stores them per-file in the protocol YAML.

### How it works

1. **File assignment**: `sci add -m data --fzf` — assign files to protocol steps
2. **Auto-detection**: After assignment, the system reads each IV file, detects voltage reversal points, and computes:
   - `direction`: `forward` (V increasing) or `reverse` (V decreasing)
   - `sweep_rate_v_s`: |dV/dt| per segment
   - `voltage_range`: voltage span of the segment
   - `duration_s`: time span of the segment
3. **Storage**: Per-file metadata written back to the protocol YAML:

```yaml
steps:
  - name: 4_iv-characterization
    technique: iv
    files:
      - deviceA_IV.txt
      - file: deviceB_IV.txt
        sweep:
          - direction: forward
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
          - direction: reverse
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
          - direction: reverse
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
          - direction: forward
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
```

4. **Analysis time**: `sci analyze -f file` also detects sweep segments and updates the protocol YAML.

### Zero-crossing detection

For bipolar sweeps (0→+V→0→-V→0), long monotonic segments are automatically split at V=0 into their constituent forward/reverse halves. This produces the expected 4-segment pattern.

### Extension-owned per-step YAML files

Extensions may define their own YAML configuration files within step directories. These files complement (do not replace) the protocol-level YAML:

```
protocol/
└── <protocol_name>/
    ├── <protocol_name>.yaml       ← protocol-level: steps, techniques, file list
    └── <step_name>/
        ├── devices.yaml           ← extension-owned: device config, matrix map
        ├── results/               ← output figures, analysis results
        └── *.txt / *.csv          ← data files
```

**`devices.yaml`** (science-memristor extension): Maps crossbar array data files to matrix positions (row, col), stores per-position sweep metadata, and tracks measurement order. See `extensions/science-memristor/PLAN.md` for schema and CLI commands.

**Resolution order**: When both the protocol YAML and an extension YAML exist, the CLI resolves files and metadata from the extension YAML first, falling back to the protocol YAML. This avoids duplication while allowing extensions to add structured metadata that doesn't belong in the general-purpose protocol file.

### Central Path Config (`paths.py`)

All directory structure logic lives in `science_cli/core/paths.py`. `ProjectPaths` is the single source of truth for:

```python
from science_cli.core.paths import ProjectPaths, get_project_paths

paths = ProjectPaths(project_root)

# Protocol YAML resolution (backward-compatible)
paths.protocol_yaml("my_protocol")     # read: new location first, legacy fallback
paths.protocol_yaml_new("my_protocol") # write: always nested (protocol/<name>/<name>.yaml)
paths.list_protocol_yamls()            # glob: merges both formats, no duplicates
paths.protocol_names()                 # sorted list of protocol names

# Protocol subdirectory paths
paths.protocol_subdir("my_protocol")   # protocol/<name>/ (step dirs + devices.yaml)
paths.devices_yaml("my_protocol")      # protocol/<name>/devices.yaml
paths.step_dir("my_protocol", "step1") # protocol/<name>/<step>/
paths.step_results_dir("my_protocol", "step1")  # protocol/<name>/<step>/results/

# Project-level paths
paths.data_raw_dir                     # data/raw/ (no processed/ — raw-only)
paths.results_dir                      # results/
paths.protocol_dir                     # protocol/

# Factory function (uses current session)
paths = get_project_paths()  # returns ProjectPaths or None if no project open
```

**Legacy support**: `protocol_yaml()` checks the new nested location (`protocol/<name>/<name>.yaml`) first, then falls back to the old flat location (`protocol/<name>.yaml`). New protocols are always created in the nested format. Existing protocols at the old location continue working — migration is opt-in.

## Generate Theme Previews

```bash
python scripts/generate-theme-previews.py
```

Output: `theme-previews/{theme}/{plot}.pdf`
