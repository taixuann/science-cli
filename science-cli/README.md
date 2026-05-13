# science-cli — Scientific Data Analysis CLI

Core engine for scientific data analysis. Handles **plotting, theming, output formatting, and CLI orchestration**. Extensions (science-iv, science-memristor, science-electrochem) provide analysis logic; science-cli renders the results.

## Architecture

```
science-cli (core)          ← themes, plotting, CLI, output
  ├── science-iv            ← IV analysis logic
  ├── science-memristor     ← memristor analysis logic
  └── science-electrochem   ← electrochemistry analysis logic
```

Extensions register techniques and analyzers. science-cli dispatches CLI commands to them, then plots results using the active theme.

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
s-cli config set theme publication-nature
s-cli config set theme publication-acs
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
s-cli plot data/sample_IV.csv                          # → sample_IV.pdf
s-cli plot --theme publication-acs data/sample_IV.csv
s-cli plot --output figure.pdf data/sample_IV.csv
```

PNG is only for quick previews. All publication figures must use PDF.

## Plotting

```bash
# Basic plot with current theme
s-cli plot data/sample_IV.csv

# Specify theme
s-cli plot --theme publication-nature data/sample_EIS.csv

# Custom output
s-cli plot --output ~/Desktop/figure.pdf data/sample_CV.csv

# Overlay multiple files
s-cli plot data/sample_IV_1.csv data/sample_IV_2.csv
```

### Technique Detection

`s-cli plot` auto-detects the technique from filename patterns, then applies the matching template (line style, axis labels) from `theme/templates/`.

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
from science_cli.extensions import ExtensionRegistry, TechniqueDef

def register(registry: ExtensionRegistry):
    registry.name = "science-iv"
    registry.techniques["iv-sweep"] = TechniqueDef(...)
    registry.analyzers["iv-sweep"] = extract_resistance
    registry.plot_presets["iv-sweep"] = {
        "type": "line",
        "xlabel": "Voltage (V)",
        "ylabel": "Current (A)",
    }
```

See extension READMEs for their analysis functions.

## CLI Commands

Commands are organized into four groups:

**Group 1 (Basic Operations):**
```bash
s-cli add       <target>           # Add protocol/metadata/data/project
s-cli delete    <target>           # Delete protocol/metadata
s-cli edit      <target>           # Edit protocol/metadata
s-cli ls        [options]          # List projects/protocols/steps/files
```

**Group 2 (Context Management):**
```bash
s-cli open      <target>           # Open project/protocol/step
s-cli close                 # Close context with auto-save
```

**Group 3 (Analysis & Configuration):**
```bash
s-cli plot      <file> [options]   # Plot with themes, output PDF
s-cli analyze   <file>             # Run analysis, print results
s-cli config    get/set <key> <val> # Manage config (theme, etc.)
s-cli status            # Show current context status
s-cli results           # List saved results by protocol and step
```

**Group 4 (Extensions & Info):**
```bash
s-cli ext       <name> [subcommand] # Unified extension interface
s-cli techniques          # List available techniques and usage guide
```

## Protocol System — Sweep Metadata

Protocols assign data files to technique steps. When files are assigned to IV-related techniques, the system auto-detects **sweep segments** (direction, rate) and stores them per-file in the protocol YAML.

### How it works

1. **File assignment**: `s-cli add -m data --fzf` — assign files to protocol steps
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

4. **Analysis time**: `s-cli analyze -f file` also detects sweep segments and updates the protocol YAML.

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

**`devices.yaml`** (science-memristor extension): Maps crossbar array data files to matrix positions (row, col), stores per-position sweep metadata, and tracks measurement order. See `tools/extensions/science-memristor/PLAN.md` for schema and CLI commands.

**Resolution order**: When both the protocol YAML and an extension YAML exist, the CLI resolves files and metadata from the extension YAML first, falling back to the protocol YAML. This avoids duplication while allowing extensions to add structured metadata that doesn't belong in the general-purpose protocol file.

### Cross-Protocol Dashboard

Generate a project-level dashboard that aggregates IV data from ALL protocols:

```bash
memristor dashboard --all [--open] [--force]
```

- Scans all `<project>/protocol/*/devices.yaml` files
- Caches analysis results in `project/results/analysis_data.json` (incremental via mtime tracking)
- Per-protocol stacked heatmaps with protocol selector dropdown
- Material filter, toggleable Vset/Vreset markers on IV overlay
- KPI cards with cross-protocol aggregate statistics (median Vset, Vreset, yield, ON/OFF ratio)
- Same dark-themed Plotly interactive dashboard as per-protocol mode
- `--force` flag forces full re-analysis, ignoring cache

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
paths.data_raw_dir                     # data/raw/
paths.results_dir                      # results/
paths.protocol_dir                     # protocol/

# Factory function (uses current session)
paths = get_project_paths()  # returns ProjectPaths or None if no project open
```

**Legacy support**: `protocol_yaml()` checks the new nested location (`protocol/<name>/<name>.yaml`) first, then falls back to the old flat location (`protocol/<name>.yaml`). New protocols are always created in the nested format. Existing protocols at the old location continue working — migration is opt-in.

## Textual TUI

The TUI (terminal user interface) replaces the old `prompt_toolkit` REPL. It's built on Textual and launches automatically when you run `sci` with no arguments.

### Launch

```bash
sci                # Launches the TUI
sci <cmd> <args>   # Direct CLI mode (bypasses TUI)
```

### TUI Features

| Feature | Description |
|---------|-------------|
| **Command prompt** | Type commands at the `>` prompt. Supports all CLI commands plus built-ins. |
| **Command echo** | Each command shows `> <cmd>` with a right-aligned timestamp on the same line. |
| **Slash commands** | `/help`, `/clear`, `/history`, `/version` — TUI-specific built-ins. |
| **Command history** | Up/down arrows navigate the last 50 commands. Persisted to `~/.config/science-cli/repl_history`. |
| **Grouped help** | `/help` lists commands organized by group (1–4) instead of a flat list. |
| **fzf suspend** | Commands with `--fzf` flags auto-suspend the TUI to run `fzf` in the real terminal. |
| **Status bar** | Shows active theme, context (`project/protocol/step`), and session uptime. |
| **Scroll indicator** | `▲ earlier output ▲` appears when scrolled up. Use PgUp/PgDown to scroll. |
| **Copy text** | Hold Shift while selecting, then Cmd+C (macOS) / Ctrl+Shift+C (Linux). |

### Output Format

```
> /help                                                    14:48:45

Group 1
Command   │  Description
──────────┼──────────────────────────────────────────────
add       │ Add protocol/metadata/data/project
delete    │ Delete protocol/metadata
...
```

Each command shows a `> <command>` echo with the timestamp right-aligned on the same line, followed by the command output.

## Generate Theme Previews

```bash
python scripts/generate-theme-previews.py
```

Output: `theme-previews/{theme}/{plot}.pdf`
