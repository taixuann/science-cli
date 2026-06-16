---
name: sci-project-lifecycle
description: "End-to-end project lifecycle knowledge for science-cli v3.11.0 — complete 9-phase project workflow, decision trees for command selection, common patterns (crossbar characterization, EC analysis, multi-technique), error recovery, and AI agent best practices. Load when planning, executing, or troubleshooting a full science-cli project workflow."
version: 3.11.0
author: science-cli team
ontology: [skill, science-cli, project-lifecycle, workflow, analysis, plotting, dashboard]
workspace: tools/science-cli
load: on_request
---

# sci-project-lifecycle — Full Project Lifecycle Skill

## 1. Overview

The full project lifecycle is the master workflow that ties together every subsystem in science-cli. It covers the complete journey from a blank filesystem to a published dashboard with analyzed results.

```
sci config init → sci add -m project → sci add -m protocol → sci add -m data
→ sci analyze → sci plot → sci results --move → sci serve
```

### Who This Skill Is For

This skill is designed for AI agents that need to:

1. **Plan** a complete experimental data analysis session
2. **Execute** each step in the correct order with proper context
3. **Recover** from common errors (no project open, wrong device type, missing files)
4. **Optimize** workflow for specific patterns (crossbar, EC, multi-technique)

---

## 2. Full Project Workflow — 9 Phases

### Phase 1: One-Time Configuration

```bash
sci config init --global
```

**What it does:** Creates `~/.config/science-cli/config.yaml` with default settings for themes, device registry, technique patterns, and file naming grammar.

**When to run:** Once per machine/install. Skip if already configured.

**Verify:** `sci config show --global` should show config sections.

### Phase 2: Create Project

```bash
sci add -m project <name>
```

Creates the project directory structure:

```
<projects_root>/<name>/
├── data/raw/           # Place measurement files here
├── data/processed/     # Processed/transformed data
├── protocol/           # Protocol definitions
├── results/            # Analysis outputs and plots
└── sci-config.yaml     # Per-project config
```

**Guidelines:**
- One project per material system
- Name should be descriptive: `taox-characterization`, `pda-memristors`
- Auto-sets as current context

### Phase 3: Open Project Context

```bash
sci open -m project <name>
```

Sets the session context — without this, subsequent commands won't know which project to work on.

**Context hierarchy:**

```
Project (last_project)
  └── Protocol (last_protocol)
       └── Step (last_step)
```

**Always verify after opening:**
```bash
sci status
```

### Phase 4: Add Protocol with Techniques and Instruments

```bash
sci add -m protocol -n <name> \
  --step <step_names> \
  -t <techniques> \
  --ins <instruments> \
  --devices <device_type>
```

**Required decisions before running:**
1. How many steps? (e.g., 1_set, 2_reset)
2. What technique per step? (e.g., iv-sweep, raman, ec-cv)
3. What instrument per step? (e.g., keithley-2400, horiba-usth)
4. What device type for analysis routing? (e.g., memristor, junction, general)

**Examples:**

```bash
# IV-only (volatile memristor)
sci add -m protocol -n 1_iv-test \
  --step 1_set,2_reset \
  -t iv-sweep,iv-sweep \
  --ins keithley-2400,keithley-2400 \
  --devices memristor

# Multi-technique (IV + Raman + AFM)
sci add -m protocol -n 2_multi-char \
  --step 1_iv,2_raman,3_afm \
  -t iv-sweep,raman,afm-gwy \
  --ins keithley-2400,horiba-usth,horiba-usth \
  --devices general

# Electrochemistry (CV + CA + EIS)
sci add -m protocol -n 3_ec-test \
  --step 1_cv,2_ca,3_eis \
  -t ec-cv,ec-ca,ec-eis \
  --ins biologic,biologic,biologic \
  --devices electrochem
```

**Structure created:**
```
protocol/<name>/
├── <name>.yaml     # Protocol metadata
├── <step1>/
│   └── results/
├── <step2>/
│   └── results/
└── ...
```

**Open the protocol:**
```bash
sci open -m protocol -n <name>
```

### Phase 5: Add Data Files

First, copy measurement files to `data/raw/`:

```bash
cp ~/measurements/*.csv <project>/data/raw/
```

Then assign them to protocol steps:

```bash
# Interactive per-file assignment (recommended)
sci add -m data

# Batch assignment (all files to same step)
sci add -m data --all
```

**Interactive fzf workflow:**
1. Protocol selection (if none open)
2. File multi-select (Tab to select, F2 to toggle grouping)
3. Per-file step assignment (or batch with `--all`)
4. Symlinks created: `data/raw/<file>` → `protocol/<name>/<step>/<file>`
5. YAML updated with file entries

**Verify:**
```bash
sci ls
# Shows: step name, technique, instrument, file count
```

### Phase 6: Analyze Data

```bash
# Interactive fzf analysis
sci analyze

# Explicit technique with specific flags
sci analyze -t iv-sweep --vset-only --yaml
sci analyze -t raman --baseline airpls --peaks
sci analyze -t ec-cv --charge
sci analyze -t ec-eis --circuit RQR --kk
sci analyze -t uv-vis --bandgap --yaml
```

**Post-analysis sweep metadata extraction:**
After each analysis, the system extracts sweep segments and writes them to the protocol YAML. Verify:
```
sweep: 2 seg [up, down] @ 0.1 V/s
```

**For pulse measurements (use dedicated subcommands):**
```bash
sci pulse analyze --type endurance
sci pulse analyze --type retention
sci pulse analyze --type stp --fit-model biexponential
sci pulse analyze --type ppf --intervals 10,50,100
```

**For AFM:**
```bash
sci afm analyze --psd
```

### Phase 7: Plot Data

```bash
# Interactive plotting
sci plot

# Direct plotting with specific files
sci plot protocol/1_iv-test/1_set/data.csv

# Overlay multiple files
sci plot --overlay --label-name "A,B" file1.csv file2.csv

# Technique-specific with flags
sci plot --technique raman file.txt --laser 532 --accumulation 3
sci plot --technique ec-eis sample.mpt --circuit RQR --kk

# Publication styling
sci config theme set publication-nature
sci plot data.csv --grid --legend --size 5.7,3.5
```

**Manage saved figures:**
```bash
sci plot results        # List all saved figures
sci plot open <name>    # Open a figure
sci plot delete <name>  # Delete a figure (with confirmation)
```

### Phase 8: Collect Results

After analysis and plotting, results are scattered across step directories. Collect them into the project-level `results/` directory:

```bash
sci results --move
```

**What it does:** Opens fzf with all result files from all steps → creates symlinks in `<project>/results/`.

**Auto-rename on collision:**
```
260526_iv_sweep.pdf     → 260526_iv_sweep.pdf     (first)
                          260526_iv_sweep_1.pdf     (second, auto-renamed)
```

### Phase 9: Serve Dashboard

```bash
sci serve --open
```

Starts HTTP server on port 8000 (default). Opens browser with AI Studio frontend.

**Dashboard features:**
- **Dashboard view:** Protocol selector, KPI cards (yield, median Vset/Vreset/ratio), heatmap matrix
- **Gallery view:** Thumbnail grid of saved plots, filterable by protocol/step, lightbox viewer
- **Per-device IV viewer:** Plot detail with sweep navigation, Vset/Vreset markers

**Options:**
```bash
sci serve --port 8080           # Custom port
sci serve --dev --open          # Dev mode + auto-open
sci serve --project /path/to    # Force specific project
```

---

## 3. Decision Tree: When to Use Each Command

```
Are you starting from scratch?
  ├─ No config yet?       → sci config init --global
  ├─ Need a new project?  → sci add -m project <name>
  └─ Project exists?      → sci open -m project <name>

Need to define measurements?
  ├─ Define protocol      → sci add -m protocol -n <name> --step ...
  └─ Edit protocol        → sci edit -m protocol -n <name> ...

Need to manage files?
  ├─ Files in data/raw/?  → sci add -m data (or --all)
  ├─ List files/steps?    → sci ls
  ├─ Open a step?         → sci open -m step <name>
  └─ Close context?       → sci close -m step|protocol|project

Need to analyze?
  ├─ IV sweep?            → sci analyze -t iv-sweep [--vset-only|--compliance] [--yaml]
  ├─ Raman?               → sci analyze -t raman [--baseline|--peaks] [--yaml]
  ├─ UV-Vis?              → sci analyze -t uv-vis [--bandgap] [--yaml]
  ├─ EC-CV?               → sci analyze -t ec-cv [--charge]
  ├─ EC-CA?               → sci analyze -t ec-ca [--fit]
  ├─ EC-EIS?              → sci analyze -t ec-eis [--circuit RQR|RRC|RQRW] [--kk]
  ├─ Pulse?               → sci pulse analyze --type endurance|retention|stp|ppf
  └─ AFM?                 → sci afm analyze [--psd]

Need to plot?
  ├─ Interactive?         → sci plot (fzf)
  ├─ Direct file?         → sci plot <file>
  ├─ Overlay multiple?    → sci plot --overlay file1.csv file2.csv
  ├─ Technique-specific?  → sci plot --technique <type> <file> [flags]
  ├─ List figures?        → sci plot results
  └─ Open/delete figure?  → sci plot open|delete <name>

Need to collect/share?
  ├─ Collect results?     → sci results --move
  ├─ Serve dashboard?     → sci serve [--open]
  └─ Get context info?    → sci info --json
```

---

## 4. Common Pattern 1: Crossbar Characterization

For pure crossbar array characterization (memristor/junction IV sweeps):

```
1. sci config init --global                     # One-time
2. sci add -m project crossbar-study
3. sci open -m project crossbar-study
4. sci add -m protocol -n 1_iv-test \
      --step 1_set,2_reset \
      -t iv-sweep,iv-sweep \
      --ins keithley-2400,keithley-2400 \
      --devices memristor                      # volatile: Vset only
      # OR --devices junction                  # bipolar: Vset + Vreset
5. sci open -m protocol -n 1_iv-test
6. cp ~/data/*.csv crossbar-study/data/raw/
7. sci add -m data --all                       # Batch assign all files
8. sci iv sync                                 # SQLite cache for large arrays
9. sci analyze -t iv-sweep --vset-only --yaml  # Per-file analysis
   # OR sci analyze -t iv-sweep --yaml         # Bipolar analysis
10. sci plot --technique iv-sweep file.csv --grid --legend
11. sci results --move                         # Collect to project/results/
12. sci serve --open                           # Dashboard
```

**Key decisions:**
- `--devices memristor` → volatile (Vset only, automatic reset)
- `--devices junction` → bipolar (Vset + Vreset, deliberate reset)
- `sci iv sync` is optional but recommended for 100+ files

---

## 5. Common Pattern 2: EC Analysis (CV → CA → EIS)

For electrochemistry projects with sequential measurements:

```
1. sci add -m project ec-study
2. sci open -m project ec-study
3. sci add -m protocol -n 3_ec-analysis \
      --step 1_cv,2_ca,3_eis \
      -t ec-cv,ec-ca,ec-eis \
      --ins biologic,biologic,biologic \
      --devices electrochem
4. sci open -m protocol -n 3_ec-analysis
5. cp ~/data/*.mpt ec-study/data/raw/
6. sci add -m data

7. # Step 1: CV analysis
   sci open -m step 1_cv
   sci analyze -t ec-cv --charge

8. # Step 2: CA analysis
   sci open -m step 2_ca
   sci analyze -t ec-ca --fit

9. # Step 3: EIS analysis
   sci open -m step 3_eis
   sci analyze -t ec-eis --circuit RQR --kk

10. # Plotting
    sci plot --technique ec-cv cv_data.mpt --scan-rate 50 --cycles 3 --grid
    sci plot --technique ec-eis eis_data.mpt --circuit RQR --kk --nyquist --bode

11. sci results --move
12. sci serve --open
```

**EC-specific considerations:**
- Biologic .mpt format is auto-detected
- CV needs scan rate and cycle count for proper annotation
- CA Cottrell fit is automatic with `--fit`
- EIS circuit fitting takes most of the computation time
- KK validation should always be run for publication-quality EIS

---

## 6. Common Pattern 3: Multi-Technique (IV + Raman + AFM)

For comprehensive device characterization combining electrical, spectral, and topographical data:

```
1. sci add -m project multi-char-study
2. sci open -m project multi-char-study
3. sci add -m protocol -n 1_comprehensive \
      --step 1_iv,2_raman,3_afm \
      -t iv-sweep,raman,afm-gwy \
      --ins keithley-2400,horiba-usth,horiba-usth \
      --devices general
4. sci open -m protocol -n 1_comprehensive
5. cp ~/data/*.csv ~/data/*.txt ~/data/*.gwy multi-char-study/data/raw/
6. sci add -m data

7. # IV analysis
   sci open -m step 1_iv
   sci analyze -t iv-sweep --vset-only --yaml

8. # Raman analysis (full preprocessing)
   sci open -m step 2_raman
   sci raman analyze --baseline airpls --norm vector --ai

9. # AFM analysis
   sci open -m step 3_afm
   sci afm analyze --psd

10. # Plot all results
    sci plot --technique iv-sweep step_data.csv --grid --legend
    sci plot --technique raman spectrum.txt --laser 532 --name raman_plot.pdf
    sci plot --technique afm topography.gwy --colormap terrain

11. sci results --move
12. sci serve --open
```

---

## 7. Common Pattern 4: Pulse Characterization

For neuromorphic device characterization (endurance, retention, STP, PPF):

```
1. sci add -m project pulse-study
2. sci open -m project pulse-study
3. sci add -m protocol -n 1_pulse-char \
      --step 1_endurance,2_retention,3_stp,4_ppf \
      -t pulse-endurance,pulse-retention,pulse-stp,pulse-ppf \
      --ins keysight-b1500a,keysight-b1500a,keysight-b1500a,keysight-b1500a \
      --devices memristor
4. sci open -m protocol -n 1_pulse-char
5. sci add -m data

6. sci pulse analyze --type endurance
7. sci pulse analyze --type retention
8. sci pulse analyze --type stp --fit-model biexponential
9. sci pulse analyze --type ppf --intervals 10,50,100,200,500

10. sci results --move
```

**Note:** `sci analyze -t pulse-*` are stubs that redirect to `sci pulse analyze`. Always use the dedicated subcommands for pulse measurements.

---

## 8. Error Recovery Patterns

### "No project open"

```
$ sci plot
[red]No project open.[/red]
```
**Fix:** `sci open -m project <name>`

### "No files found in data/raw/"

```
$ sci add -m data
[red]No files found in data/raw/.[/red]
```
**Fix:** Copy files to `data/raw/` first, or verify `projects_root` in config.

### "Protocol already exists"

```
$ sci add -m protocol -n 1_iv-test
[red]Protocol '1_iv-test' already exists[/red]
```
**Fix:** Use `sci delete -m protocol -n 1_iv-test` to remove, or use a different name.

### Wrong analysis mode (volatile vs bipolar)

If IV analysis shows only `--vset-only` mode but you need bipolar:
```bash
sci edit -m protocol -n 1_iv-test --devices junction
```

### Wrong instrument for technique

If data loads with wrong column mappings:
```bash
# Check what's currently assigned
sci config list devices iv-sweep

# Set the correct instrument
sci config set technique iv-sweep keysight-b1500a
```

### Fzf not available

Interactive modes gracefully fall back to Rich-table display with grouped result output.

---

## 9. AI Agent Best Practices

### Context Gathering

Before any operation, gather context:

```bash
# Full project manifest (primary AI data source)
sci info --json

# Current session state
sci status --json

# Protocol and file structure
sci ls --json
```

### Command Construction Rules

1. **Always open context first**: `open -m project` → `open -m protocol` → `open -m step`
2. **Use `--technique` for explicit routing**: avoids auto-detection errors
3. **Add `--yaml` for reproducibility**: YAML output captures all analysis parameters
4. **Use `--json` for AI-readable output**: `info`, `ls`, `status` support JSON mode
5. **Check error output**: errors are `[red]`, warnings are `[yellow]`

### Workflow Optimization

| Scenario | Optimization |
|----------|-------------|
| 100+ IV files | Use `sci iv sync` for SQLite cache, then `sci iv analyze` |
| Large crossbar arrays | Use `sci iv dashboard` for matrix heatmap visualization |
| Multi-step EC analysis | Process CV → CA → EIS sequentially within one protocol |
| Publication-ready plots | Set theme once before plotting: `config theme set publication-nature` |
| Dashboard deployment | Run `results --move` before `serve` for reliable cross-referencing |

### Common Mistakes to Avoid

1. **Forgetting to `open` context** — commands silently fail or operate on wrong project
2. **Not using `--technique`** — auto-detection can misidentify technique from filename
3. **Mixing volatile/bipolar** — wrong `--devices` setting produces meaningless Vreset values
4. **Skipping `results --move`** — dashboard works but cross-references are less reliable
5. **Not checking sweep metadata** — IV analysis may have incorrect sweep direction

### Quick Reference: Context-Aware Commands

| Command | Without Context | With Project Open | With Protocol Open |
|---------|----------------|-------------------|-------------------|
| `sci ls` | All projects | Protocols in project | Steps in protocol + files |
| `sci analyze` | Error: no project | fzf from `data/raw/` | Filtered to protocol steps |
| `sci plot` | Error: no project | fzf from `data/raw/` | Filtered to protocol steps |
| `sci add -m data` | Error: no project | Protocol selection fzf | Files from `data/raw/` |
