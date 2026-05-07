# s-cli — Scientific Data Analysis REPL

## Usage

```
s-cli              # Start REPL (select project at startup)
s-cli --repl       # Same
(s-cli) <command> [flags]
```

## --help Preview

```
USAGE
  s-cli <command> [flags]

COMMAND GROUPS

GROUP 1: FILE MANAGEMENT
  add:    Add protocol/metadata/data
  ls:     List projects/protocols/steps (global, not session-bound)

GROUP 2: PROTOCOL NAVIGATION
  open:   Open protocol-specific view (sets session context)

GROUP 3: DATA ANALYSIS
  plot:   Plot data (interactive or direct)
  plot -theme: Configure plot theme (placeholder)
  analyze: Analyze data (peaks, fit, circuit)

ADDITIONAL COMMANDS
  help:      Show help
  clear:     Clear screen
  history:   Show command history
  exit:      Exit REPL

FLAGS
  -m, --mode       Mode: single, overlay
  -t, --technique  Technique: ec-cv, ec-ca, ec-eis
  -f, --file       File(s), comma-separated
  --step           Step ID (e.g., 1_deposition)
  -n, --name       Output filename (format from extension: .svg, .pdf, .png)
  --desc           Description
  --fzf            Interactive fzf selection

EXAMPLES
  $ s-cli                    # Start REPL → select project
  $ (sci) add -m protocol -n doping --step 1_deposition -t ec-ca
  $ (sci) add -m metadata -step 1_deposition -pt doping -t ec-ca
  $ (sci) add -m data --fzf
  $ (sci) ls -m protocol --step
  $ (sci) ls -m protocol --all
  $ (sci) ls -m protocol --files
  $ (sci) open -m protocol -n doping
  $ (sci) plot --fzf
  $ (sci) plot -f 2105_CV.txt
  $ (sci) plot -f 2105_CV.txt,2106_CV.txt
  $ (sci) plot -theme                  # Configure theme (placeholder)
  $ (sci) analyze -f 2105_CV.txt --peaks

LEARN MORE
  Use `s-cli <command> --help` for more information.
```

---

## Workflow

### Startup → Project Selection

```
$ s-cli
→ Select project from active_projects/:
  [1] res_internship
  [2] amsn-synthesis
→ res_internship activated
(sci)
```

### Project Structure

```
projects/active_projects/<project-name>/
├── data/
│   ├── raw/                    # Original data files
│   │   ├── 2104_CA.txt
│   │   ├── 2105_CV.txt
│   │   └── 2106_EIS.mpt
│   └── processed/              # Analyzed outputs
├── protocol/
│   ├── <protocol-name>.yaml   # Protocol definition
│   ├── 1_deposition/           # Step folder (symlinks to raw/)
│   │   └── results/            # Analysis results for this step
│   └── 2_characterization/    # Step folder (symlinks to raw/)
│       └── results/            # Analysis results for this step
└── results/                    # General analysis outputs
```

**Note**: All results stored in `protocol/<step>/results/` — belongs to specific protocol/step.

---

## Session Memory

When REPL starts and project is selected:

```
(sci) [project: res_internship]
```

After `open -m protocol -n <name>`:

```
(sci) [project: res_internship] [protocol: doping]
```

**Session shows**: current project + current protocol (if set)

---

## Theme & Banner

- Banner displays on REPL startup (animated or static based on `SCIENCE_CLI_NO_ANIM`)
- Theme system ready via `plot -theme` (placeholder, will be implemented later)
- Theme affects: colors, fonts, matplotlib style defaults

---

## GROUP 1: FILE MANAGEMENT (add, ls)

### add — Add protocol/metadata/data

#### add -m protocol

```
add -m protocol -n <name> [flags]

Required:
  -n, --name       Protocol name (e.g., "doping")

Optional:
  --desc           Description (e.g., "P-type doping protocol")
  --step           Steps (comma-separated): 1_deposition,2_characterization
  -t, --technique  Techniques per step: ec-ca,ec-cv,ec-eis

Example:
  (sci) add -m protocol -n doping --desc "ZnO doping" --step 1_deposition,2_characterization -t ec-ca,ec-cv

Output: protocol/doping.yaml
```

#### add -m metadata

```
add -m metadata -step <steps> -pt <protocol> -t <techniques> [flags]

Required:
  --step           Step ID(s): 1_deposition,2_characterization
  -pt, --protocol   Protocol name: doping, annealing
  -t, --technique   Techniques: ec-cv,ec-ca,ec-eis

Example:
  (sci) add -m metadata -step 1_deposition -pt doping -t ec-ca

Output: Updates protocol/<protocol>.yaml with file assignments
```

#### add -m data

```
add -m data --fzf

Flow:
  1. fzf opens → select files from data/raw/
  2. Tab to multi-select, Enter to confirm
  3. Menu-driven: assign each file to step(s)
  4. Confirm → creates symlinks in step folders

Example:
  (sci) add -m data --fzf
  → [fzf] Select: 2104_CA.txt, 2105_CV.txt
  → [menu] Assign:
    [1] 1_deposition
    [2] 2_characterization
  → Confirm → symlinks created
```

### ls — List (global, not session-bound)

```
ls                          # List all protocols and steps in current project
ls -m protocol              # List all protocols
ls -m protocol --step       # Show protocol steps only
ls -m protocol --all       # Show steps + files (full view)
ls -m protocol --files    # Show files only (no steps)
ls <step>                   # List files in specific step

Examples:
  (sci) ls
  (sci) ls -m protocol
  (sci) ls -m protocol --step
  (sci) ls -m protocol --all
  (sci) ls -m protocol --files
  (sci) ls 1_deposition
```

---

## GROUP 2: PROTOCOL NAVIGATION (open)

### open — Open protocol, sets session context

```
open -m protocol -n <name>

Flow:
  1. Opens protocol-specific view
  2. Session context set to this protocol
  3. Subsequent plot/analyze use this context
  4. To change: run open again or use ls

Example:
  (sci) open -m protocol -n doping
  → Protocol: doping
  → Steps:
    [1] 1_deposition (ec-ca) → 2104_CA.txt
    [2] 2_characterization (ec-cv) → 2105_CV.txt

  (sci) plot --fzf          # Plots from this protocol context
  (sci) analyze --peaks    # Analyzes from this context
```

---

## GROUP 3: DATA ANALYSIS (plot, analyze)

### plot — Plot data (interactive or direct)

```
plot --fzf                    # Interactive: fzf file selection
plot -f <file>                # Single file → single plot
plot -f <file1>,<file2>       # Multiple files → overlay plot
```

#### Interactive Flow (plot --fzf)

```
(sci) plot --fzf

→ [fzf] Select file(s) from data/raw/
  - Tab for multi-select
  - Enter to confirm → proceed to next step

→ [prompt] Technique/Plot options (Enter to skip):
  # Hint (grey): --default | --cycle-N (CV) | --peaks (CV) | --zoom (CA/EIS)
  --default                  # Default plot
  --cycle-N                  # CV: show cycle N
  --peaks                    # CV: highlight peaks
  --zoom                     # CA/EIS: zoom region

→ [prompt] Analyze options (Enter to skip):
  # Hint (grey): --peaks --charge (CV) | --fit (CA) | --circuit --kk (EIS)
  --peaks --charge           # CV: find peaks, integrate charge
  --fit                      # CA: fit decay
  --circuit RRC --kk         # EIS: fit circuit, K-K validation

→ [prompt] Style options (Enter to skip):
  # Hint (grey): --type line|scatter | --color | --linewidth | --marker | --markersize | --cmap
  --type line|scatter
  --color #1f77b4
  --linewidth 2.0
  --linestyle solid|dashed|dotted
  --marker o|s|^|D
  --markersize 8

→ [prompt] Figure options (Enter to skip):
  # Hint (grey): -n name.svg|pdf|png | --title | --xlabel | --ylabel | --xlim | --ylim | --size | --dpi | --grid | --legend | --save
  -n "plot.svg"              # Format from extension: .svg, .pdf, .png
  --title "CV Cycle 1"
  --xlabel "Potential (V)"
  --ylabel "Current (A)"
  --xlim -0.5,0.5
  --ylim -1e-3,1e-3
  --size 8,6
  --dpi 150
  --grid
  --legend
  --save

[Plot displayed]
→ Results saved to protocol/<step>/results/
```

**Fzf hints**: Grey text shows available options for each step (technique, analyze, style, figure)

#### Direct Flow (plot -f)

```
(sci) plot -f 2105_CV.txt
→ Auto-detect: ec-cv
→ Apply default plot

(sci) plot -f 2105_CV.txt --peaks --charge -n analysis.svg --grid --save
→ Technique: ec-cv
→ Options: --peaks, --charge (analyze), -n analysis.svg (format: SVG), --grid, --save
→ Results → protocol/1_deposition/results/analysis.svg

(sci) plot -f 2105_CV.txt,2106_CV.txt --overlay --grid
→ Two files → overlay mode
→ Auto-detect: both ec-cv
```

### analyze — Analyze data (no plotting)

```
analyze -f <file> [options]

Options by technique:
  ec-cv:  --peaks, --peaks-type anodic|cathodic|both, --peaks-range, --charge
  ec-ca:  --fit, --scale, --steady-state
  ec-eis: --circuit <model>, --kk, --impedance

Output: protocol/<step>/results/manifest.json

Examples:
  (sci) analyze -f 2105_CV.txt --peaks --charge
  (sci) analyze -f 2104_CA.txt --fit
  (sci) analyze -f 2106_EIS.mpt --circuit RRC --kk
```

**Note**: `analyze` produces analysis results only (manifest.json). Use `plot` for visualization with analysis options.

### plot -theme (Placeholder)

```
plot -theme

# Future: configure matplotlib theme, colors, fonts
# Currently: placeholder, will be implemented
```

---

## Style Options

---

## --type: line vs scatter

### --type line
Uses [`matplotlib.pyplot.plot()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.plot.html)

- Connected points (line segments)
- Best for: continuous data, CV curves, CA decay
- Style options: `--color`, `--linewidth`, `--linestyle`, `--marker`, `--markersize`

### --type scatter
Uses [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html)

- Unconnected points
- Best for: discrete data points, EIS data, error visualization
- Style options: `--color`, `--marker`, `--markersize`, `--cmap`

---

## Technique Options

| Technique | Plot Options | Analyze Options |
|-----------|--------------|------------------|
| ec-cv | `--default`, `--cycle-N`, `--peaks`, `--zoom` | `--peaks`, `--peaks-type`, `--peaks-range`, `--charge` |
| ec-ca | `--default`, `--zoom`, `--fit` | `--fit`, `--scale`, `--steady-state` |
| ec-eis | `--default`, `--nyquist`, `--bode` | `--circuit`, `--kk`, `--impedance` |

## Style Options (--type line)

| Option | Example |
|--------|---------|
| `--type` | `line` |
| `--color` | `#1f77b4`, `red` |
| `--linewidth` | `1.5`, `2.0` |
| `--linestyle` | `solid`, `dashed`, `dotted` |
| `--marker` | `o`, `s`, `^`, `D` |
| `--markersize` | `8`, `10` |

## Style Options (--type scatter)

| Option | Example |
|--------|---------|
| `--type` | `scatter` |
| `--color` | `#e74c3c` |
| `--marker` | `o`, `s` |
| `--markersize` | `50`, `80` |
| `--cmap` | `viridis`, `plasma` |

## Figure Options

| Option | Example |
|--------|---------|
| `-n, --name` | `"plot.svg"` → saves as SVG, `"plot.pdf"` → PDF, `"plot.png"` → PNG |
| `--title` | `"CV Analysis"` |
| `--xlabel` | `"Potential (V)"` |
| `--ylabel` | `"Current (A)"` |
| `--xlim` | `-0.5,0.5` |
| `--ylim` | `-1e-3,1e-3` |
| `--size` | `8,6` |
| `--dpi` | `150`, `300` |
| `--grid` | (show grid) |
| `--legend` | (show legend) |
| `--save` | (save figure, uses --name if provided) |

---

## Results Location

All analysis results stored in protocol-specific folder:

```
protocol/
├── doping.yaml
├── 1_deposition/
│   ├── 2104_CA.txt → symlink to data/raw/
│   └── results/
│       ├── manifest.json
│       ├── peaks.csv
│       └── plot.png
└── 2_characterization/
    ├── 2105_CV.txt → symlink to data/raw/
    └── results/
        ├── manifest.json
        └── plot.png
```

---

## MORE Commands

```
s-cli --help              → Show this help
s-cli --version          → Show version
(sci) help plot          → Plot help
(sci) help analyze      → Analyze help
(sci) clear             → Clear screen
(sci) history           → Show command history
(sci) exit              → Exit REPL
```

---

## Protocol.yaml Format

Filename = `<protocol-name>.yaml` (e.g., `doping.yaml`)

```yaml
name: <protocol-name>
description: <description>
steps:
  - name: <stepID>
    technique: ec-cv | ec-ca | ec-eis
    files:
      - <filename>
      - <filename>
```

---

## Auto-Detection Logic

| Input | Detection | Mode |
|-------|-----------|------|
| `plot -f file.txt` | Detect from filename → ec-cv/ca/eis | Single |
| `plot -f f1.txt,f2.txt` | Detect each | Overlay |
| `plot --fzf` | User selects → detect | Interactive |

Filename patterns:
- `*_CV.txt` → ec-cv
- `*_CA.txt` → ec-ca
- `*.mpt` → ec-eis