# PLAN — science-cli Workflow Reference

## Project Setup

```bash
# Create a new project (raw data only, no processed/)
sci project create <name>

# List projects
sci project list

# Switch active project (resets protocol + step state)
sci project open <name>
```

## Protocol + Steps

```bash
# Create a protocol with multiple steps and techniques
sci add -m protocol -n <protocol_name> \
  --desc "description" \
  --step step-1,step-2,... \
  -t <technique1>,<technique2>,...

# List all protocols in the current project
sci ls -m protocol --all
```

### Supported Techniques
| Technique | Use |
|-----------|-----|
| `ec-cv` | Cyclic voltammetry |
| `ec-ca` | Chronoamperometry |
| `ec-eis` | Electrochemical impedance spectroscopy |
| `iv` | IV sweep |
| `iv-breakdown` | Breakdown IV |
| `iv-leakage` | Leakage current IV |
| `mem-switching` | Memristor switching |
| `mem-endurance` | Memristor endurance |
| `mem-retention` | Memristor retention |

## Data File Management

```bash
# Add data files to a protocol step
sci add -m data <file1> <file2> ...

# Assign files interactively with fzf
sci add -m data --fzf

# List data files in a step
sci ls -m data
```

## Plotting

```bash
# Auto-detect technique from filename and plot
sci plot <data_file>

# Specify output file
sci plot --output <path.pdf> <data_file>

# Overlay multiple files
sci plot <file1> <file2> <file3>

# Use a specific theme
sci plot --theme <theme_name> <data_file>
```

### Available Themes
- `default` — Matplotlib defaults
- `tufte` — Minimal ink
- `dark` — Dark background
- `publication-acs` — ACS journal style
- `publication-nature` — Nature journal style
- `poster` — Conference poster size

### Auto-Plot Steps (future workflow)
1. Navigate into a step directory
2. Run `sci plot` — detects technique from step's assigned technique
3. Plots all data files in that step with correct labels and style
4. Output saved to `results/` or `plots/`

## Analysis

```bash
# Run analysis on a data file
sci analyze <file>

# Analyze with sweep segment detection (IV)
sci analyze -f <file_with_metadata>
```

## Upcoming / To Try

- [ ] Navigate into a step directory and auto-plot all data files
- [ ] Batch plot across multiple steps
- [ ] Export protocol summary as PDF report
- [ ] Crossbar device mapping with `sci memristor`
