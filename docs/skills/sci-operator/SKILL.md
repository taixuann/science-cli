---
title: sci-operator
description: Comprehensive operational knowledge base for AI agents using science-cli v3.11.0. Every command, flag, technique, config tier, device system, grammar tier, theme, troubleshooting path, and workflow pattern.
version: 3.11.0
author: science-cli team
ontology: [skill, science-cli, operator, cli, data-analysis]
workspace: tools/science-cli
load: always
---

# sci-operator — science-cli Operational Knowledge Base

## 1. Overview

science-cli is a scientific data CLI for memristor, electrochemistry, and spectroscopy characterization. It manages the end-to-end lifecycle of measurement data — from project creation through protocol definition, file assignment, plotting, analysis, results collection, and dashboard serving.

**Version:** v3.11.0  
**Package:** `science-cli` on PyPI  
**Repository:** `tools/science-cli/` (git worktree at `~/.sci/`, branch `dev`)

### Four Interfaces

| Interface | Activation | Use Case |
|-----------|-----------|----------|
| **CLI** | `sci <command>` | Direct command execution, scripting |
| **CLI-REPL** | `sci --repl` | Interactive REPL with history |
| **TUI** | `sci` (no args) | Textual-based terminal UI |
| **AI Chat** | `sci chat "<query>"` | Natural language → CLI commands via LLM |

### Installation Methods

```bash
# PyPI (recommended)
pip install science-cli

# pipx (isolated)
pipx install science-cli

# uv (fast)
uv pip install science-cli

# Source (development)
git clone https://github.com/your-org/science-cli.git
cd science-cli
pip install -e ".[dev]"
```

### First-Time Setup

```bash
# Initialize global config
sci config init --global

# Verify installation
sci info --json
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCI_CONFIG_DIR` | `~/.config/science-cli` | Config directory override |
| `SCI_PROJECTS_ROOT` | config `projects_root` | Projects root directory override |
| `SCI_SERVE_PORT` | `8000` | Default port for `sci serve` |
| `SCI_LLM_API_KEY` | (none) | API key for `sci chat` |
| `SCI_LLM_MODEL` | `gpt-4o` | Model for `sci chat` |
| `SCI_LLM_BASE_URL` | `https://api.openai.com/v1` | Base URL for `sci chat` |

---

## 2. Complete Command Tree — 30+ Commands by Group

### Group 1 — Project Management

#### `sci add -m project <name>`

Creates a new project — the top-level container for all experimental data.

```bash
sci add -m project my-experiment
sci add -m project -n TaOx-Device-Study
```

**Structure created:**
```
<projects_root>/<name>/
├── data/
│   ├── raw/          # Place raw measurement files here
│   └── processed/    # Processed/transformed data
├── protocol/         # Protocol definitions
├── results/          # Analysis outputs and plots
└── sci-config.yaml   # Per-project default config
```

**Behavior:**
- Sanitizes name: lowercase, spaces → underscores, strips special characters
- Creates all four directories
- Generates minimal `sci-config.yaml` with description and empty defaults
- Auto-sets as current context (`last_project`)
- Refuses to overwrite existing project

#### `sci add -m protocol -n <name> [flags]`

Creates a measurement protocol with ordered steps.

```bash
sci add -m protocol -n 1_iv-test \
  --step 1_set,2_reset \
  -t iv-sweep,iv-sweep \
  --ins keithley-2400,keithley-2400 \
  --desc "Standard IV characterization" \
  --devices memristor
```

**Flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `-n, --name <name>` | Yes | Protocol name |
| `--desc, --description <text>` | No | Human-readable description |
| `--step <names>` | No | Comma-separated step names |
| `-t, --technique <types>` | No | Comma-separated technique names, one per step |
| `--ins, --instrument <names>` | No | Comma-separated instrument names, one per step. Replaces deprecated `-d/--device`. |
| `--devices <type>` | No | Per-protocol device type for analysis routing |
| `-d, --device` | **Deprecated** | Use `--ins/--instrument` instead |

**Auto-technique assignment:** When `--ins` is provided without `-t`, the instrument's default techniques are auto-filled from the instrument registry.

**Structure created:**
```
protocol/<name>/
├── <name>.yaml        # Protocol metadata YAML
├── <step1>/           # Step directory
│   └── results/       # Step-level results subdirectory
├── <step2>/
│   └── results/
└── ...
```

#### `sci add -m metadata -pt <protocol> --step <s> -t <t> [flags]`

Updates step metadata (technique, instrument) in an existing protocol YAML. Appends only — never deletes.

```bash
sci add -m metadata --step 1_deposition -pt doping -t ec-cv
sci add -m metadata --step 3_eis -pt doping -t ec-eis --ins biologic
sci add -m metadata --step 1_cv,2_ca -pt electro-test -t ec-cv,ec-ca --ins biologic,biologic
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--step <names>` | **Required.** Comma-separated step names |
| `-pt, --protocol <name>` | Protocol name (uses current protocol if omitted) |
| `-t, --technique <types>` | Comma-separated technique names |
| `--ins, --instrument <names>` | Comma-separated instrument names |

#### `sci add -m data [--all]`

Interactive file assignment via fzf. Links raw data files in `data/raw/` to protocol steps via symlinks.

```bash
sci add -m data        # Interactive — per-file prompt
sci add -m data --all  # Batch assign all selected files to one step
```

**Interactive workflow:**
1. Protocol selection — fzf picker if none is open
2. File selection — fzf multi-select from `data/raw/` with **F2** to toggle grouping
3. Step assignment — per-file (or one shot with `--all`)
4. File linking — creates symlinks: `data/raw/<file>` → `protocol/<name>/<step>/<file>`
5. YAML update — appends file entries to protocol YAML
6. Auto-detect IV sweep metadata — for IV files, detects sweep segments, direction, sweep rate

#### `sci delete -m protocol|metadata|data`

**Modes:**

| Mode | Description | Safety |
|------|-------------|--------|
| `delete -m protocol -n <name>` | Permanently deletes protocol + step dirs + YAML | `questionary.confirm()` prompt |
| `delete -m metadata -n <name> [--step s1] [--all]` | Removes file assignments from YAML only, not data files | `--all` requires confirmation |
| `delete -m data [--step <name>]` | Interactive fzf-based removal of file entries | Per-file selection |

```bash
sci delete -m protocol -n 1_iv-test
sci delete -m metadata -n 1_iv-test --step 1_set
sci delete -m metadata --all
sci delete -m data
sci delete -m data --step 1_set
```

#### `sci edit -m protocol|metadata|data`

Modifies existing resources.

**Protocol editing flags:**

| Flag | Description |
|------|-------------|
| `-n, --name <name>` | **Required.** Protocol name to edit |
| `--nn, --new-name <name>` | Rename the protocol (renames directory and YAML) |
| `--desc, --description <text>` | Update protocol description |
| `--step <names>` | Add or update steps |
| `-t, --technique <types>` | Technique(s) for steps |
| `--ins, --instrument <names>` | Instrument(s) for steps |
| `--rm-step <name>` | Remove a step (prompts to delete directory) |
| `--reorder <s1,s2,...>` | Reorder steps in YAML |
| `--devices <type>` | Set per-protocol device type |
| `--param <k=v,...>` | Set parameters on steps |

```bash
sci edit -m protocol -n 1_iv-test --nn 1_iv-characterization
sci edit -m protocol -n 1_iv-test --step 3_breakdown -t iv-breakdown --ins keithley-2400
sci edit -m protocol -n 1_iv-test --rm-step 2_reset
sci edit -m protocol -n 1_iv-test --reorder 3_breakdown,1_set,2_reset
sci edit -m protocol -n 1_iv-test --devices memristor
sci edit -m protocol -n 1_iv-test --step 1_set --param compliance=1e-3,sweeps=3
```

**Metadata editing:**

```bash
sci edit -m metadata -n 1_iv-test --step 1_set,2_reset -t iv-breakdown,iv-sweep
sci edit -m metadata -n 1_iv-test --step 1_set --ins keysight-b1500
sci edit -m metadata -n 1_iv-test --step 1_set --files 140526_file1.csv,140526_file2.csv
```

**Data editing:** `sci edit -m data` — interactive fzf-based file reassignment between steps.

#### `sci ls [flags] [<step>]`

Context-aware listing: shows different views depending on what's open.

| Context | Shows |
|---------|-------|
| Step open | Files in current step |
| Protocol open (no step) | Protocol steps table |
| Project open (no protocol) | Protocols in project |
| Nothing open | All projects list |

**Flags:**

| Flag | Description |
|------|-------------|
| `-m project` | List all projects |
| `-m protocol [--step] [--all]` | List protocols/steps |
| `-n <step>` | List files in a specific step |
| `--json` | Structured JSON output |

```bash
sci ls
sci ls -m project
sci ls -m project --json
sci ls -m protocol --step
sci ls -m protocol --all
sci ls -m protocol -n 1_iv-test
sci ls -n 1_set
sci ls 1_set              # positional also works
sci ls --json
```

---

### Group 2 — Navigation

#### `sci open -m project|protocol|step`

Sets the session context — the 3-level hierarchy of project → protocol → step. Context persists across commands and is saved to `~/.config/science-cli/session.json`.

```bash
sci open -m project my-experiment
sci open -m protocol -n 1_iv-test
sci open -m step 1_set
```

**3-Level Context Hierarchy:**

```
Project (last_project)
  └── Protocol (last_protocol)
       └── Step (last_step)
```

| Context | Plot | Analyze | ls |
|---------|------|---------|----|
| Project | All files in project | All techniques | Shows protocols |
| Protocol | Files in protocol steps | Protocol's techniques | Shows steps table |
| Step | Files in specific step | Step's technique | Shows files list |

#### `sci close -m step|protocol|project`

Saves current state and clears context pointer. Cascading: close protocol → clears step too; close project → clears everything.

```bash
sci close -m step        # Saves step state, clears step pointer
sci close -m protocol    # Saves protocol state, clears protocol + step
sci close -m project     # Saves all context, clears everything
```

**Auto-save architecture:**
```
close -m step:     save_step_state() → last_step = ""
close -m protocol: save_context_state() → last_protocol = "" → last_step = ""
close -m project:  save_context_state() → last_project = "" → last_protocol = "" → last_step = ""
```

Reopening via `open -m project <same>` restores prior saved state.

#### `sci status [-m project|protocol] [--json]`

Displays the current session context tree.

```bash
sci status                 # Full context tree
sci status -m project      # Project-level context table
sci status -m protocol     # Protocol-level context with steps
sci status --json          # Structured JSON context manifest
```

#### `sci info [--json]`

Complete project manifest — human-readable view and machine-readable JSON for AI agents.

```bash
sci info          # Human-readable context
sci info --json   # Machine-readable JSON manifest
```

**JSON structure (primary AI data source):**
```json
{
  "science_cli_version": "3.11.0",
  "project": {
    "name": "my-experiment",
    "path": "/path/to/project",
    "theme": "publication-nature",
    "raw_file_count": 12,
    "protocol_count": 3
  },
  "session": {
    "last_project": "my-experiment",
    "last_protocol": "1_iv-test",
    "last_step": "1_set",
    "theme": "publication-nature"
  },
  "protocols": [...],
  "themes": ["publication-nature", "publication-acs", "poster", "dark", "default", "tufte", "acs-annotated"],
  "techniques": [...],
  "plot_hints": {"iv-sweep": {"plot_style": "line", "figure": "iv_sweep"}, ...}
}
```

---

### Group 3 — Config System

#### `sci config init [--global|--project]`

Generate default configuration file with all sections documented and commented.

```bash
sci config init             # Writes to ~/.config/science-cli/config.yaml
sci config init --global    # Same as above
sci config init --project   # Writes to <current_project>/sci-config.yaml
```

#### `sci config show [--global|--project|--merged]`

Display the merged (or scoped) configuration as a color-coded Rich tree view.

```bash
sci config show             # Merged: hardcoded ← global ← project
sci config show --global    # Global config only
sci config show --project   # Per-project config only
sci config show --merged    # Same as default
```

#### `sci config theme list|set <name>`

Manage matplotlib themes.

```bash
sci config theme list                  # List all 7 themes, active marked with ●
sci config theme set publication-nature # Switch theme immediately
```

#### `sci config list techniques|devices|grammar`

List configured items.

```bash
sci config list techniques                 # All techniques with device config
sci config list devices iv-sweep           # Devices for a specific technique
sci config list grammar                    # Global grammar patterns
sci config list grammar --device-type memristor  # Device-type grammar
sci config list grammar --protocol 1_iv-test     # Protocol-level grammar
```

#### `sci config set technique <name> <device>`

Set the default device for a technique.

```bash
sci config set technique iv-sweep keithley-2400
sci config set techniques iv-sweep keysight-b1500a  # Plural alias
```

#### `sci config edit [--global|<technique>|devices|grammar|techniques]`

Open configuration files in `$EDITOR`.

```bash
sci config edit iv-sweep                  # Per-technique config
sci config edit iv-sweep --force          # Force-regenerate template
sci config edit techniques --global       # Global technique registry
sci config edit devices                   # Global device registry section
sci config edit grammar                   # Global grammar patterns
sci config edit grammar --device-type memristor  # Device-type grammar
sci config edit grammar --protocol 1_iv-test     # Protocol grammar
```

#### `sci config grammar list|edit|test <filename>`

Grammar subcommands.

```bash
sci config grammar list                   # List grammar patterns
sci config grammar edit                   # Edit grammar patterns
sci config grammar test "140526_Ta-PDA-ITO_r0c0_iv_01.csv"  # Test filename parsing
```

**Grammar test output:**
```
┌────────────┬──────────────────┐
│ Field      │ Value            │
├────────────┼──────────────────┤
│ date_code  │ 140526           │
│ material   │ Ta-PDA-ITO       │
│ technique  │ iv               │
│ matrix     │ r0c0             │
│ suffix     │ 1                │
│ row        │ 0                │
│ col        │ 0                │
└────────────┴──────────────────┘
```

---

### Group 4 — Data & Results

#### `sci results [--move]`

Interactive browsing and collection of saved figures and analysis outputs.

```bash
sci results           # Interactive fzf browse of result files (opens with system viewer)
sci results --move    # fzf multi-select → create symlinks in project/results/
```

**Supported formats:**
- Browse/open: `.pdf`, `.svg`, `.png`
- Move/symlink: `.pdf`, `.svg`, `.png`, `.csv`, `.json`, `.txt`

**Symlink structure:**
```
project/
├── protocol/
│   └── 1_iv-test/
│       └── 1_set/
│           └── results/
│               ├── 140526_iv_sweep.pdf       # original
│               └── 140526_analysis.yaml      # original
└── results/
    ├── 140526_iv_sweep.pdf                   # symlink
    └── 140526_analysis.yaml                  # symlink
```

---

### Group 5 — Plot & Analyze (Most Complex)

#### `sci plot [<file>...]`

The primary visualization interface. 13 technique plotters, interactive fzf, overlay mode, bulk export, figure management.

```
sci plot                           Interactive: fzf file selection → style → figure prompts
sci plot --overlay                 Interactive: overlay all chosen files in one plot
sci plot --all                     Interactive: export each file individually
sci plot <file>                    Direct: plot file(s) with auto-detected technique
sci plot --technique <type> <file> Direct: plot with explicit technique + technique-specific flags
sci plot results                   List all saved figures
sci plot open <name>               Open a saved figure with system viewer
sci plot delete <name>             Delete a saved figure (with confirmation)
```

**TECHNIQUE_PLOTTERS — 13 registered plotters:**

| # | Technique | Handler | Description |
|---|-----------|---------|-------------|
| 1 | `iv-sweep` | `_do_plot` (generic) | Voltage vs current line/scatter |
| 2 | `iv-breakdown` | `_do_plot` (generic) | Breakdown IV curve |
| 3 | `iv-leakage` | `_do_plot` (generic) | Leakage current IV curve |
| 4 | `pulse-endurance` | `_do_plot` (generic) | Resistance vs cycle |
| 5 | `pulse-retention` | `_do_plot` (generic) | Resistance vs time |
| 6 | `pulse-stp` | `_do_plot` (generic) | STP decay |
| 7 | `pulse-ppf` | `_do_plot` (generic) | Paired-pulse facilitation |
| 8 | `ec-cv` | `_do_plot` (generic) | Cyclic voltammogram |
| 9 | `ec-ca` | `_do_plot` (generic) | Chronoamperometry |
| 10 | `ec-eis` | `_do_eis_plot` (special) | Nyquist + Bode + circuit fit + KK |
| 11 | `uv-vis` | `_do_plot` (generic) | Transmission/absorbance spectrum |
| 12 | `raman` | `_wrap_raman_plot` (special) | Raman spectrum via RamanSPy |
| 13 | `afm-gwy` | `_wrap_afm_plot` (special) | AFM topography via AFMReader |

**Technique-specific plot flags:**

| Technique | Flag | Type | Description |
|-----------|------|------|-------------|
| raman | `--laser` | int | Laser wavelength (nm) — 532, 633, 785 |
| raman | `--accumulation` | int | Number of accumulations |
| raman | `--acq-time` | float | Acquisition time (s) |
| raman | `--nd-filter` | int | ND filter value (0-4) |
| ec-cv | `--scan-rate` | float | Scan rate (mV/s) |
| ec-cv | `--cycles` | int | Number of cycles |
| ec-eis | `--freq-range` | str | Frequency range filter (e.g. `"1Hz-1MHz"`) |
| ec-eis | `--nyquist` | flag | Generate Nyquist plot (default: True) |
| ec-eis | `--bode` | flag | Generate Bode plot (default: True) |
| ec-eis | `--circuit` | str | Circuit model for fit overlay (e.g. `RQR`, `RRC`) |
| ec-eis | `--kk` | flag | Kramers-Kronig validation test |
| uv-vis | `--wavelength-range` | str | Wavelength range filter (e.g. `"300-800"`) |
| afm | `--cross-section` | flag | Show cross-sectional line profile |
| afm | `--colormap` | str | Colormap name (default: `viridis`) |

**Generic plot flags:**

| Flag | Type | Description |
|------|------|-------------|
| `--type` | str | `line` or `scatter` |
| `--color` | str | Line/marker color |
| `--linewidth` | float | Line width (pt) |
| `--linestyle` | str | `solid`, `dashed`, `dotted`, `dashdot` |
| `--marker` | str | `o`, `s`, `^`, `D`, `*` |
| `--markersize` | float | Marker size (pt) |
| `--cmap` | str | Colormap (scatter plots) |
| `--title` | str | Plot title |
| `--xlabel` | str | X-axis label (auto-detected) |
| `--ylabel` | str | Y-axis label (auto-detected) |
| `--xlim` | str | `xmin,xmax` |
| `--ylim` | str | `ymin,ymax` |
| `--zoom` | str | `x1,x2` or `x1,x2,y1,y2` |
| `--size` | str | `width,height` (inches) |
| `--dpi` | int | Output DPI (default: 600) |
| `--grid` | flag | Show grid |
| `--legend` | flag | Show legend |
| `--name`/`-n` | str | Output filename (extension determines format) |
| `--label-name` | str | Comma-separated labels for overlay |

**Column resolution by technique:**

| Technique | X-axis candidates | Y-axis candidates |
|-----------|------------------|-------------------|
| `ec-ca` | `Corrected time (s)`, `time`, `t/s` | `WE(1).Current (A)`, `I`, `I/A` |
| `ec-cv` | `WE(1).Potential (V)`, `E`, `E/V` | `WE(1).Current (A)`, `I`, `I/A` |
| `ec-eis` | `Z' (Ω)`, `Re(Z)`, `z_real` | `-Z'' (Ω)`, `Im(Z)`, `z_imag` |
| `iv-sweep` | `Voltage (V)`, `V`, `BV`, `bias_voltage` | `Current (A)`, `I`, `I/A`, `Bi` |
| `uv-vis` | `wavelength`, `Wavelength nm.`, `nm` | `transmittance`, `T%`, `T` |
| **Default** | First numeric column | Second numeric column |

**EIS special behavior:** `_do_eis_plot()` always generates:
- **Nyquist plot**: Z' vs -Z'' (always)
- **Bode plot**: |Z| + phase vs frequency (if magnitude + phase columns available)
- **Circuit fit overlay** (with `--circuit` flag): fits model, overlays on Nyquist, saves fit JSON
- **KK test** (with `--kk`): Kramers-Kronig validation, prints pass/fail with consistency score

**Interactive mode flow:**
```
sci plot
    ↓
FZF file selector (multi-select, Tab to select multiple)
  - Shows protocol|step|filename columns
  - Preview window: first 20 lines via head
    ↓
Auto-detect technique from protocol step metadata (or filename)
    ↓
Prompt 1: Style options (--type, --color, --linewidth, etc.)
Prompt 2: Figure options (-n, --title, --xlabel, --grid, --legend, etc.)
    ↓
Multi-file: Overlay all (o) or individual plots (i)?
    ↓
Save PDF to step results/ → emit manifest.json
```

**Direct mode flag layering:**
```
Layer 1: template_to_flags(technique)  — theme template defaults
Layer 2: get_plot_labels(technique)     — config labels
Layer 3: CLI flags                      — user command line (highest priority)
```

#### `sci analyze [<file>...]`

Performs parameter extraction and numerical analysis. Returns quantitative results: switching voltages, peak positions, bandgap energies, circuit fit parameters.

```
sci analyze                        Interactive: fzf file selection, auto-detect technique
sci analyze -t/--technique <type>  Direct: fzf + explicit technique
sci analyze <file>                 Direct: analyze file with auto-detected technique
```

**TECHNIQUE_ANALYZERS — 13 registered analyzers:**

| Technique | Analyzer | Extracted Parameters |
|-----------|----------|---------------------|
| `iv-sweep` | `_analyze_iv` | V_set, V_reset, ON/OFF ratio, compliance |
| `iv-breakdown` | `_analyze_iv` | Same as iv-sweep |
| `iv-leakage` | `_analyze_iv` | Same as iv-sweep |
| `pulse-endurance` | `_analyze_pulse_endurance` | ⏳ Stub — use `sci pulse analyze` |
| `pulse-retention` | `_analyze_pulse_retention` | ⏳ Stub — use `sci pulse analyze` |
| `pulse-stp` | `_analyze_pulse_stp` | ⏳ Stub — use `sci pulse analyze` |
| `pulse-ppf` | `_analyze_pulse_ppf` | ⏳ Stub — use `sci pulse analyze` |
| `ec-cv` | `_analyze_cv` | Anodic/cathodic peaks, ΔE_p, charge |
| `ec-ca` | `_analyze_ca` | Cottrell slope, steady-state current |
| `ec-eis` | `_analyze_eis` | Circuit fit params, KK consistency |
| `raman` | `_analyze_raman` | Peak wavenumbers, intensities |
| `uv-vis` | `_analyze_uv_vis` | Peaks, inflection point, Tauc bandgap |
| `afm-gwy` | `_analyze_afm` | ⏳ Stub — use `sci afm analyze` |

**Analyze technique-specific flags:**

| Technique | Flag | Type | Description |
|-----------|------|------|-------------|
| iv-sweep | `--yaml` | flag | Output analysis YAML to results/ |
| iv-sweep | `--vset-only` | flag | Volatile mode: V_set only |
| iv-sweep | `--compliance` | float | Compliance current threshold (A) |
| raman | `--yaml` | flag | Output analysis YAML |
| raman | `--peaks` | flag | Find and report spectral peaks |
| raman | `--baseline` | str | `poly`, `asls`, `airpls` |
| uv-vis | `--yaml` | flag | Output analysis YAML |
| uv-vis | `--bandgap` | flag | Compute Tauc bandgap energy |
| ec-cv | `--charge` | flag | Compute charge integration |
| ec-ca | `--fit` | flag | Perform Cottrell fit |
| ec-eis | `--circuit` | str | `RRC`, `RQR`, `RQRW` |
| ec-eis | `--kk` | flag | Kramers-Kronig validation |
| afm | `--yaml` | flag | Output analysis YAML |
| afm | `--roughness` | flag | Compute Sa/Sq roughness |

**YAML output location:** `<project>/protocol/<protocol>/<step>/results/<technique>_analysis.yaml`

**Sweep metadata extraction:** After every successful analysis, automatically runs sweep metadata detection — extracts sweep segments, directions, and sweep rates, then updates the protocol YAML.

---

### Group 6 — Technique Commands

#### `sci iv ls|info|plot|analyze|sync|dashboard`

IV sweep analysis for memristor, junction, and crossbar characterization.

| Subcommand | Description | Status |
|------------|-------------|--------|
| `ls [--step <name>]` | List IV sweep files | ✅ |
| `info [<file>]` | Show columns, shape, value range | ✅ |
| `plot [--overlay] [--all] [--row] [--col]` | Plot IV curves with crossbar filtering | ✅ |
| `analyze [--vset-only] [--row] [--col]` | Extract Vset, Vreset, ON/OFF ratio | ✅ |
| `sync` | Sync IV data to SQLite cache | ⏳ Stub |
| `dashboard` | Launch IV analysis dashboard | ⏳ Stub |

**Analysis modes:**
- Default (bipolar): Extracts Vset + Vreset for junction devices
- `--vset-only` (volatile): Extracts Vset only for volatile memristors

**IV analysis library (`library/iv/`):**
- `analyze.py`: `extract_resistance()`, `extract_breakdown_voltage()`, `fit_iv_curve()` (Ohmic, Schottky, SCLC, Poole-Frenkel), `extract_on_off_ratio()`
- `volatile.py`: `analyze_volatile()` — Vset mean/std/CV, set_yield
- `bipolar.py`: `analyze_bipolar()` — Vset + Vreset stats, hysteresis area
- `metrics.py`: `detect_vset()`, `detect_vreset()` — derivative-based detection

#### `sci pulse ls|endurance|retention|stp|ppf|dashboard`

Pulse measurement analysis for memristor and neuromorphic devices.

| Subcommand | Description | Status |
|------------|-------------|--------|
| `ls` | List pulse measurement files | ✅ |
| `endurance [--file <file>]` | Endurance cycling analysis | ⏳ CLI stub (library ✅) |
| `retention [--file <file>]` | Retention decay (log-time + power-law) | ⏳ CLI stub (library ✅) |
| `stp [--file <file>]` | STP decay (mono/biexponential, AIC selection) | ⏳ CLI stub (library ✅) |
| `ppf [--file <file>]` | PPF ratio vs interval (exponential decay fit) | ⏳ CLI stub (library ✅) |
| `dashboard` | Launch pulse dashboard | ⏳ Not implemented |

**Pulse analysis library (`library/pulse/`):**
- `endurance.py`: `analyze_endurance()` — mean R_on/R_off, CV, failure_cycle (ratio < 10), Weibull fit, R_off trend
- `retention.py`: `analyze_retention()` — log-time + power-law fit, model selection by R², 10-year extrapolation, lifetime
- `stp.py`: `analyze_stp_decay()` — mono/biexponential fit, AIC selection, τ₁/τ₂, decay_pct
- `ppf.py`: `analyze_ppf()` — PPF(t) = 1 + A·exp(-t/τ), curve_fit with bounds
- `models.py`: `PulseData`, `EnduranceData`, `RetentionData`, `STPData`, `PPFData`

#### `sci ec ls|info|analyze`

Electrochemistry (CV/CA/EIS) specialized handling.

| Subcommand | Description |
|------------|-------------|
| `ls` | List EC files with auto technique detection |
| `info [<file>...]` | Show columns, shape, value range |
| `analyze [<file>...] [flags]` | Technique-specific analysis |

**EC analysis flags:**

| Technique | Flag | Description |
|-----------|------|-------------|
| ec-cv | `--peaks` | Peak detection (default: on) |
| ec-cv | `--charge` | Integrated charge (default: off) |
| ec-ca | `--fit` | Cottrell fit |
| ec-eis | `--circuit RRC|RQR|RQRW` | Circuit model |
| ec-eis | `--kk` | Kramers-Kronig test |

**Implementation:** `ec analyze` routes via auto-detected technique:
```python
if tech == "ec-cv":    _analyze_cv()
elif tech == "ec-ca":  _analyze_ca()
elif tech == "ec-eis": _analyze_eis()
```

**EIS circuit models:**
| Circuit | Elements | Description |
|---------|----------|-------------|
| `RC` | R, C | Series RC |
| `RRC` | Rs, Rct, Cdl | Randles R(RC) |
| `RQR` | Rs, Rct, Q (CPE) | Randles R(RQ) |
| `Randles` | Rs, Rct, Q | Alias for RQR |
| `R_s(C[RW])` | Rs, Cdl, Rct, σ | Randles + Warburg |
| `R_s(Q[RW])` | Rs, Q, Rct, σ | CPE + Warburg |

#### `sci raman ls|info|analyze`

Raman spectroscopy from Horiba LabRAM HR Evolution.

| Subcommand | Description |
|------------|-------------|
| `ls [--step <name>]` | List Raman/SERS files with metadata |
| `info [<file>...]` | Show 30+ header fields |
| `analyze [<file>...] [flags]` | RamanSPy preprocessing pipeline |

**Raman analyze pipeline (in order):**
1. **Denoising** (`--denoise`): `savgol` (window/order) or `whittaker` (lam)
2. **Baseline correction** (`--baseline`): `asls`, `iasls`, `airpls`, `arpls`, `iarpls`, `poly`, `modpoly`
3. **Normalization** (`--norm`): `vector`, `minmax`, `maxintensity`, `auc`
4. **Peak detection**: `--prominence`, `--distance`, `--height`, `--width`

**Raman analyze flags:**

| Flag | Type | Description |
|------|------|-------------|
| `--denoise` | str | `savgol` or `whittaker` |
| `--savgol-window` | int | SavGol window (default: 7) |
| `--savgol-order` | int | SavGol order (default: 3) |
| `--lam` | float | Smoothness parameter (default: 1e7) |
| `--baseline` | str | Baseline method |
| `--norm` | str | Normalization method |
| `--prominence` | float | Minimum peak prominence |
| `--distance` | float | Minimum peak separation (cm⁻¹) |
| `--height` | float | Minimum peak height |
| `--width` | float | Minimum peak width |
| `--ai` | flag | AI-assisted flag recommendations |
| `--overlay` | flag | Overlay all spectra |
| `--all` | flag | Subplot grid |
| `--plot` | flag | Generate analysis plot PDF |

**AI mode (`--ai`):** Sends file metadata to the `sci-raman` opencode agent, which returns recommended preprocessing flags.

**Output files:** `{stem}_peaks.csv`, `{stem}_processed.csv`, `{stem}_report.txt`, `{stem}_analysis.pdf`

#### `sci uv-vis ls|info|analyze`

UV-Vis transmission/absorbance spectroscopy.

| Subcommand | Description |
|------------|-------------|
| `ls` | List UV-Vis files |
| `info [<file>...]` | Show header info and data range |
| `analyze [<file>...] [--name <prefix>]` | Spectrum analysis |

**UV-Vis analysis computes:**
- Wavelength range (min/max)
- Peak intensity (max) and valley intensity (min) with positions
- Inflection point — wavelength of maximum absolute slope (gradient-based onset)
- Full derivative via `np.gradient`

**Output:** `{prefix}_analysis.csv` with columns `wavelength(nm)`, `intensity`, `derivative`

#### `sci afm ls|info|analyze|export|open`

AFM/SPM image analysis in 6 formats (.gwy, .spm, .ibw, .jpk, .stp, .top).

| Subcommand | Description |
|------------|-------------|
| `ls` | List AFM/SPM files with format detection |
| `info [<file>...]` | Show metadata: pixel calibration, dimensions, channels |
| `analyze [--psd] [--export <prefix>]` | Surface roughness (Sa, Sq, Rmax, Rsk, Rku, Sdr) |
| `export [--format png|csv|npy] [--cmap]` | Export image data |
| `open` | Gwyddion bridge — open .ibw in Gwyddion, record analysis |

**Roughness parameters (ISO 25178):**
| Parameter | Description |
|-----------|-------------|
| Sa (Ra) | Arithmetic mean height deviation (nm) |
| Rq | Root mean square roughness (nm) |
| Rmax | Maximum height range (nm) |
| Rsk | Skewness of height distribution |
| Rku | Kurtosis of height distribution |
| Sdr | Surface area ratio (%) |

**Export formats:**
| Format | Description |
|--------|-------------|
| `png` | Rendered image with colormap |
| `csv` | Pixel grid: row, col, height_nm |
| `npy` | Raw NumPy array |

**Gwyddion bridge (`afm open`):**
1. fzf picker for `.ibw` file
2. Launches Gwyddion
3. Prompts: Thickness (nm), Sa (nm), Sq (nm), Material
4. Saves to `afm_analysis.yaml` in step directory (incremental)

#### `sci pvd ls|info|add|edit|analyze`

PVD deposition records CRUD and analysis.

| Subcommand | Description |
|------------|-------------|
| `ls` | List PVD deposition steps |
| `info` | Show deposition details: layers, materials, thickness, rate, parameters |
| `add` | Interactive wizard: material, thickness, rate, temperature, pressure, power |
| `edit` | Interactive editor: current values as defaults |
| `analyze` | Avg deposition rate, rate stability, total thickness, uniformity |

---

### Group 7 — Infrastructure

#### `sci instrument ls|info|register|edit|rm`

Manage the instrument registry. Alias: `sci ins`.

```bash
sci instrument ls                          # List all registered instruments
sci instrument ls --technique iv-sweep     # Filter by technique compatibility
sci instrument info keithley-2400          # Show instrument details
sci instrument register my-device          # Register new (opens $EDITOR with template)
sci instrument edit keysight-b1500a        # Edit existing instrument config
sci instrument rm old-device --confirm     # Remove instrument (requires --confirm)
```

**Built-in instruments:**

| Name | Type | Techniques |
|------|------|------------|
| `keithley-2400` | sourcemeter | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance |
| `keysight-b1500a` | parameter-analyzer | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance, pulse-stp, pulse-ppf |
| `biologic` | potentiostat | ec-cv, ec-ca, ec-eis |
| `horiba-usth` | raman-spectrometer | raman |
| `iop-hanoi` | uv-vis-spectrometer | uv-vis |

**Instrument types:** sourcemeter, parameter-analyzer, potentiostat, lcr-meter, raman-spectrometer, uv-vis-spectrometer, afm, pvd-system, probe-station, function-generator, oscilloscope

#### `sci serve [--port] [--project] [--dev] [--open]`

Interactive dashboard server — serves the AI Studio frontend with REST API.

```bash
sci serve                       # Default port 8000
sci serve --port 8080           # Custom port
sci serve --dev --open          # Dev mode + auto-open browser
sci serve --project /path/to    # Force a specific project
```

**REST API endpoints:**

| Endpoint | Description |
|----------|-------------|
| `/api/projects` | List all projects |
| `/api/project` | Current project data |
| `/api/gallery` | Gallery of saved plots |
| `/api/protocol/{name}/files` | Protocol file listing |
| `/api/protocol/{name}/summary` | KPIs: yield, cells, median Vset/Vreset/ratio |
| `/api/protocol/{name}/heatmap` | Crossbar heatmap matrix |
| `/api/protocol/{name}/device/{cell}/iv` | Per-cell IV sweep data |
| `/api/protocol/{name}/histograms` | Vset, Vreset, ratio distributions |
| `/api/protocol/{name}/dashboard` | Comprehensive dashboard bundle |

#### `sci chat "<natural language query>"`

Natural language to CLI commands via LLM. Auto-gathers context via `sci info --json`.

```bash
sci chat "plot the IV data with grid and legend"
sci chat "analyze the raman data with baseline correction"
sci chat "use nature style"
```

**Config:** `SCI_LLM_API_KEY`, `SCI_LLM_MODEL` (default: `gpt-4o`), `SCI_LLM_BASE_URL`

#### Deprecated Commands

**`sci memristor`** — Deprecated, will be removed in v4.0.0. Auto-routes to `sci iv` or `sci pulse`.

| Deprecated | Replacement |
|-----------|-------------|
| `sci memristor ls` | `sci iv ls` |
| `sci memristor plot` | `sci iv plot` |
| `sci memristor analyze` | `sci iv analyze` |
| `sci memristor dashboard` | `sci iv dashboard` |
| `sci memristor endurance` | `sci pulse endurance` |
| `sci memristor retention` | `sci pulse retention` |

**`sci techniques`** — Deprecated. Use `sci config list techniques`.

---

## 3. Two-Level Device System

### Level 1: `--ins` / `--instrument` (Per-Step)

The instrument flag for protocol steps. Replaces deprecated `-d/--device`.

- **What it is:** The hardware used for measurement (e.g. `keithley-2400`, `keysight-b1500`)
- **Where:** Set per-step in `add -m protocol --ins ...` or `edit -m metadata --ins ...`
- **Auto-technique assignment:** If `--ins keithley-2400` given without `-t`, looks up instrument registry → auto-sets technique
- **Effect:** Determines file parsing config (delimiter, header_lines, decimal, encoding, column mapping)

### Level 2: `--devices` (Per-Protocol)

The device type for analysis mode routing. Always plural, never confused with deprecated `-d/--device`.

- **What it is:** The scientific device type (memristor, junction, deposition, electrochem, general)
- **Where:** Set per-protocol in `add -m protocol --devices <type>` or `edit -m protocol --devices <type>`
- **Effect:** Routes analysis mode in `DEVICE_TYPE_MODE_MAP`

**Device Type → Analysis Mode Routing:**

| Device Type | Mode | Description |
|-------------|------|-------------|
| `memristor` | `volatile` | V_set only (no V_reset) |
| `junction` | `bipolar` | V_set + V_reset |
| `deposition` | `linear` | Linear I-V for PVD monitoring |
| `pvd` | `linear` | Linear I-V for PVD monitoring |
| `electrochem` | `general` | General electrochemical analysis |
| `general` | `general` | Default mode |

**Override with CLI flag:** `sci analyze --vset-only` forces volatile mode regardless of device type.

---

## 4. Config System (4 Tiers)

Settings are resolved by merging four layers. Higher-numbered tiers override lower-numbered ones. Deep merge (nested dicts merge recursively).

```
Tier 1: Hardcoded Defaults (core/config.py, core/technique.py)
  ─ Always present, never removed
  ─ Built-in devices, technique patterns, grammar fallbacks, delimiters
    │ fallback
    ▼
Tier 2: Global Config (~/.config/science-cli/config.yaml, techniques/*.yaml)
  ─ Shared across ALL projects
  ─ Created by `sci config init --global`
  ─ Themes, project root, device registry, technique registry, file naming
    │ per-project override
    ▼
Tier 3: Per-Project Config (<project>/sci-config.yaml)
  ─ Overrides for one project only
  ─ Created by `sci config init --project`
  ─ Project-level technique/device overrides
    │ per-protocol override
    ▼
Tier 4: Per-Protocol YAML (<project>/protocol/<name>/<name>.yaml)
  ─ Highest priority
  ─ Step configs, instruments, sweep metadata, grammar: section
  ─ Created by `sci add -m protocol`
```

**Cache invalidation:** `config show` calls `invalidate_cache()` before display. Manual `config edit` also invalidates after editor exit.

**Config file locations:**

| File | Purpose | Created By |
|------|---------|------------|
| `~/.config/science-cli/config.yaml` | Global config | `sci config init --global` |
| `~/.config/science-cli/session.json` | Session state (theme, last project/protocol/step) | Auto on first `sci` |
| `~/.config/science-cli/techniques/<name>.yaml` | Per-technique overrides | `sci config edit <technique>` |
| `<project>/sci-config.yaml` | Per-project overrides | `sci config init --project` |
| `<project>/protocol/<name>/<name>.yaml` | Protocol YAML | `sci add -m protocol` |

---

## 5. Grammar System (5 Tiers)

File naming grammar resolves from five tiers. Higher-numbered tiers override lower-numbered ones. First matching regex wins.

```
Tier 1: Hardcoded Grammar Fallback (core/technique.py HARDCODED_GRAMMAR)
  ─ Catch-all regex: extracts date_code, material, technique, matrix, suffix
    │ overridden by
    ▼
Tier 2: Device-Type-Specific Grammar (config.yaml → file_naming.device_types)
  ─ memristor (crossbar-rNcN), junction (junction-basic), deposition (deposition-basic)
    │ overridden by
    ▼
Tier 3: Global Config Grammar (config.yaml → file_naming.patterns)
  ─ Standard conventions: rNcN, bN-tN
    │ overridden by
    ▼
Tier 4: Project-Level Grammar (sci-config.yaml → file_naming.patterns)
  ─ Per-project naming convention overrides
    │ overridden by
    ▼
Tier 5: Protocol-Level Grammar (protocol/<name>.yaml → grammar:)
  ─ Highest priority. Per-protocol custom patterns.
```

### Universal Grammar Fields

| Field | Description | Example |
|-------|-------------|---------|
| `date_code` | DDMMYY or YYYYMMDD | `140526`, `20240526` |
| `material` | Device/material name | `Ta-PDA-ITO` |
| `technique` | Measurement technique code | `iv`, `raman` |
| `matrix` | Crossbar position | `r0c0`, `b1-t1` |
| `suffix` | Order/cycle number | `01`, `001` |
| `batch` | Batch number (optional) | `2` |
| `type` | Measurement type | `uc` (unipolar), `dc` |
| `bot`, `top` | bN-tN electrode indices | `1`, `3` |
| `row`, `col` | Derived numeric indices | `0`, `0` |

**Separator:** ALWAYS `_` (underscore) — hardcoded in `core/config.py`, not configurable.

**Grammar test:** `sci config grammar test "140526_Ta-PDA-ITO_r0c0_iv_01.csv"` validates against merged grammar.

### Device-Type Grammar Patterns

**memristor (crossbar-rNcN):**
```
{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}
```
Matches: `140526_Ta-PDA-ITO_2_r0c0_iv_uc_01.csv`

**junction (junction-basic):**
```
{date_code}_{material}_{technique}_{suffix?}
```
Matches: `140526_Ta-PDA-ITO_iv_01.csv` (no matrix coords)

**deposition (deposition-basic):**
```
{date_code}_{material}_{technique}_{suffix?}
```
Same pattern as junction, for deposition/process records.

---

## 6. Theme System

### 7 Built-in Themes

| Theme | Use Case | Key Features |
|-------|----------|-------------|
| `default` | Quick previews | Standard matplotlib rcParams |
| `dark` | Screens / dark mode | Dark backgrounds, light text |
| `tufte` | Minimal ink, max data | Edward Tufte-inspired, minimal grid |
| `publication-acs` | ACS journal style | Helvetica, boxed axes, 600 DPI |
| `publication-nature` | Nature journal style | Helvetica, spines off, minimal |
| `poster` | Conference posters | Large fonts, high DPI |
| `acs-annotated` | ACS style with annotations | ACS base + annotation-friendly |

### Three-Tier Architecture

1. **Theme** (`theme/plot-theme/*.yaml`) — Global styling: colors, fonts, grid, axes, ticks, legend, figure defaults
2. **Template** (`theme/plot-templates/*.yaml`) — Per-technique curve presets: linewidth, markers, labels
3. **PlotTemplate** — Full figure blueprints (future, not yet implemented)

**Theme application flow:**
```
sci config theme set publication-nature
    ↓
set_active_theme("publication-nature")  → writes to session.json
    ↓
apply_theme("publication-nature")       → reads theme/plot-theme/...yaml
    ↓
theme_to_rcparams()                     → converts YAML to rcParams dict
    ↓
matplotlib.rcParams.update(rc)          → applied globally
```

**Switching:**
```bash
sci config theme set tufte              # Switch to tufte
sci config theme set poster             # Switch to poster (for conference)
sci config theme set publication-nature # Back to default
```

**Custom themes:** Create by adding YAML files to the `theme/plot-theme/` directory or by editing the `theme` section in config YAML.

---

## 7. AI-Aware Commands

Commands designed for AI agent consumption:

| Command | Output | Use Case |
|---------|--------|----------|
| `sci info --json` | Full project manifest JSON | Primary AI data source for context |
| `sci ls --json` | Context-aware JSON listing | Protocol/step/file structure |
| `sci ls -m project --json` | All projects as JSON | Workspace overview |
| `sci ls -m protocol --json` | Protocols + steps as JSON | Detailed protocol inspection |
| `sci status --json` | Context tree as JSON | Current session state |
| `sci chat "<query>"` | Natural language → CLI | Fuzzy interpretation |

**AI workflow pattern:**
```bash
# 1. Get context
sci info --json

# 2. Plan commands based on project structure
# 3. Execute with proper context
sci open -m project my-experiment
sci open -m protocol -n 1_iv-test
sci open -m step 1_set

# 4. Run batch operations
sci plot --technique iv-sweep file.csv --grid --legend

# 5. Verify
sci info --json
```

---

## 8. Technique Detection

`detect_technique()` in `core/technique.py` maps filenames to technique slugs using regex pattern matching. Case-insensitive, first match wins.

**Detection pattern resolution:**
1. Project-level overrides (sci-config.yaml) — highest priority
2. Global config patterns (config.yaml)
3. Hardcoded fallback (core/technique.py)

**Key detection patterns:**

| Technique | Regex Patterns |
|-----------|---------------|
| `iv-sweep` | `_IV\.`, `\.iv$`, `iv_`, `iv-`, `_sweep`, `sweep_` |
| `iv-breakdown` | `_bd\.`, `breakdown_`, `_Vbd`, `bd_` |
| `iv-leakage` | `_leak`, `leakage_`, `leak_` |
| `ec-cv` | `_CV\.`, `\.cv$`, `cv_`, `cv-` |
| `ec-ca` | `_CA\.`, `\.ca$`, `ca_`, `ca-` |
| `ec-eis` | `\.mpt$`, `_EIS\.`, `\.eis$`, `_impedance`, `\.z` |
| `raman` | `_raman`, `_sers`, `_raman-sers` |
| `uv-vis` | `_uv-vis`, `_uvvis`, `uv-vis`, `uvvis` |
| `afm-gwy` | `\.gwy$` |
| `pulse-endurance` | `_endurance`, `\.end`, `end_`, `endurance` |
| `pulse-stp` | `_stp`, `_STP`, `_stp_decay`, `_short-term` |
| `pulse-ppf` | `_ppf`, `_PPF`, `_paired-pulse` |

**Important: `mem-` vs `pulse-` overlap:** `mem-endurance`, `mem-retention`, `mem-switching` share identical patterns with `pulse-*` counterparts. `mem-*` appears first in insertion order, so it takes priority. To force `pulse-*`, use config overrides or explicit `--technique pulse-endurance`.

---

## 9. Per-Technique YAML Schemas

All analysis YAML files are written to `<step_dir>/results/<technique>_analysis.yaml`.

### Common Envelope

```yaml
technique: <technique_slug>
instrument: <instrument_name>
devices: <device_type>
timestamp: "2026-06-15T12:00:00Z"
```

### iv-sweep_analysis.yaml

```yaml
analysis:
  mode: volatile              # volatile or bipolar
  parameters:
    v_set: 1.23
    v_set_std: 0.045
    v_set_cv: 0.037
    v_set_min: 1.10
    v_set_max: 1.35
    v_reset: -0.89            # bipolar only
    on_off_ratio: 45.2
    compliance: 0.001
    set_yield: 92.5           # volatile only
    hysteresis_area: 0.42     # bipolar only
  n_events: 40
sweep_metadata:
  scan_rate_v_s: 0.5
  segments:
    - direction: forward
      sweep_rate_v_s: 0.48
    - direction: reverse
      sweep_rate_v_s: 0.52
conduction_fits:
  ohmic:        { model: ohmic,        params: {R_ohm: 1250000}, metrics: {r_squared: 0.992} }
  schottky:     { model: schottky,     params: {schottky_slope: 3.21}, metrics: {r_squared: 0.971} }
  sclc:         { model: sclc,         params: {n_exponent: 1.85, interpretation: "SCLC (trap-filled)"}, metrics: {r_squared: 0.988} }
  pool-frenkel: { model: pool-frenkel, params: {pf_slope: 2.78}, metrics: {r_squared: 0.965} }
```

### pulse-endurance_analysis.yaml

```yaml
analysis:
  parameters:
    cycles_to_failure: 9876
    r_high_initial: 54321.0
    r_low_initial: 1234.5
    cycle_to_cycle_variability_pct: 8.7
    n_cycles: 10000
    ratio_tail_mean: 12.3
    ratio_tail_std: 1.2
```

### pulse-retention_analysis.yaml

```yaml
analysis:
  parameters:
    decay_rate: -234.5
    decay_model: log          # log or power
    extrapolated_10yr: 34567.8
    lifetime_hours: 87654.0
    r_squared: 0.9934
    test_duration_hours: 168.0
    n_points: 100
```

### pulse-stp_analysis.yaml

```yaml
analysis:
  decay_fit:
    model: biexponential      # monoexponential or biexponential
    tau1_ms: 12.3
    tau2_ms: 145.6
    a1: 0.65
    a2: 0.35
    r_squared: 0.9978
  parameters:
    initial_current_ua: 12.34
    steady_state_current_ua: 3.21
    decay_pct: 74.0
```

### pulse-ppf_analysis.yaml

```yaml
analysis:
  ppf_ratio_vs_interval:
    - interval_ms: 50.0; ppf_ratio: 1.85
    - interval_ms: 100.0; ppf_ratio: 1.65
  facilitation_time_constant_ms: 85.3
  a_amplitude: 0.92
  ppf_ratio_max: 1.85
  ppf_ratio_min: 1.12
  r_squared: 0.9950
  n_intervals: 8
```

### ec-cv_analysis.yaml

```yaml
peaks:
  n_anodic: 1
  anodic_peaks:
    - index: 142; potential: 0.452; current: 3.45e-05
  n_cathodic: 1
  cathodic_peaks:
    - index: 318; potential: 0.213; current: -2.89e-05
  average_peak_separation: 0.239
charge:                       # with --charge flag
  total_charge: 1.24e-05
  anodic_charge: 6.80e-06
  cathodic_charge: 5.60e-06
  unit: C
```

### ec-ca_analysis.yaml

```yaml
cottrell:
  slope: 2.34e-04
  slope_stderr: 1.21e-06
  intercept: -5.32e-08
  r_squared: 0.998
steady_state:
  steady_state_current: 1.23e-06
  steady_state_std: 4.56e-08
  steady_state_time: 4.0
```

### ec-eis_analysis.yaml

```yaml
circuit_fit:
  circuit: RRC
  parameter_names: [Rs, Rct, Cdl]
  fitted_params: [120.3, 4520.1, 3.21e-06]
  param_stderr: [0.5, 15.2, 1.23e-08]
  r_squared: 0.994
  reduced_chi: 2.31e-03
kk:                           # with --kk flag
  passes: true
  consistency_score: 2.1
  n_poles: 10
```

### raman_analysis.yaml

```yaml
analysis:
  peaks:
    - wavenumber_cm: 520.7; intensity: 8500.0
    - wavenumber_cm: 1330.0; intensity: 3200.0
  preprocessing:
    - baseline: airpls
    - normalization: vector
```

### uv-vis-transmission_analysis.yaml

```yaml
analysis:
  mode: transmission
  peaks:
    - wavelength_nm: 550.0; absorbance: 0.45
  bandgap: 2.85               # with --bandgap flag (eV)
```

### pvd-deposition_analysis.yaml

```yaml
analysis:
  total_thickness_nm: 120.5
  layers:
    - material: Ta; thickness_nm: 10.0; rate_As: 0.5
    - material: PDA; thickness_nm: 100.0; rate_As: 2.0
  parameters:
    avg_deposition_rate_As: 1.2
    rate_cv_pct: 5.3
    uniformity_pct: 3.1
```

---

## 10. Library Routing

The `TECHNIQUE_LIBRARY_MAP` in `core/routing.py` determines which analysis library handles each technique.

| Technique | Library |
|-----------|---------|
| `iv-sweep`, `iv-breakdown`, `iv-leakage` | `iv` |
| `pulse-endurance` through `pulse-ppf` (10 techniques) | `pulse` |
| `ec-cv`, `ec-ca`, `ec-eis`, `ec-lsv`, `ec-swv` | `ec` |
| `raman` | `raman` |
| `uv-vis` | `uv-vis` |
| `afm-gwy` | `afm` |
| `mem-*`, `afm-*` (others) | `general` (fallback) |

```python
def resolve_library(technique, devices=None):
    result = TECHNIQUE_LIBRARY_MAP.get(technique)
    if result: return result
    for prefix, lib in [("iv-", "iv"), ("pulse-", "pulse"), ("ec-", "ec")]:
        if technique.startswith(prefix):
            return lib
    return "general"
```

---

## 11. Complete Technique Catalog

### IV Measurements (3 techniques)
- `iv-sweep` — DC IV sweep → `iv` library
- `iv-breakdown` — Breakdown voltage → `iv` library
- `iv-leakage` — Leakage current → `iv` library

### Pulse Measurements (11+2 legacy techniques)
- `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd`, `pulse-stp`, `pulse-ppf` + legacy `mem-*` aliases

### Electrochemistry (5 techniques)
- `ec-cv` (CV), `ec-ca` (CA), `ec-eis` (EIS), `ec-lsv` (LSV), `ec-swv` (SWV)

### Spectroscopy (2 techniques)
- `raman` (Raman), `uv-vis` (UV-Vis)

### Microscopy (6 AFM formats)
- `afm-gwy`, `afm-spm`, `afm-ibw`, `afm-jpk`, `afm-stp`, `afm-top`

### Deposition (1 technique)
- `pvd` (PVD Deposition)

**Total: 28+ technique slugs** registered in the system.

---

## 12. Project Lifecycle — End-to-End Workflow

```bash
# ── Phase 1: Setup ───────────────────────────────────────
sci config init                                            # One-time global config
sci config edit --global                                   # Set projects_root

# ── Phase 2: Create Project ───────────────────────────────
sci add -m project taox-study                              # Create project
sci open -m project taox-study                             # Set as context

# ── Phase 3: Define Protocol ──────────────────────────────
sci add -m protocol -n 1_iv-test \
  --step 1_set,2_reset \
  -t iv-sweep,iv-sweep \
  --ins keithley-2400,keithley-2400 \
  --desc "Standard IV characterization" \
  --devices memristor

# ── Phase 4: Open Protocol ────────────────────────────────
sci open -m protocol -n 1_iv-test                           # Set protocol context

# ── Phase 5: Assign Data Files ────────────────────────────
# Place files in data/raw/ first, then:
sci add -m data                                            # Interactive fzf assignment

# ── Phase 6: Plot & Analyze ───────────────────────────────
sci plot                                                    # Interactive plotting
sci plot --technique iv-sweep file.csv --grid --legend      # Direct plotting
sci analyze -t iv-sweep --vset-only --yaml                  # Analysis with YAML output

# ── Phase 7: Technique-Specific Analysis ──────────────────
sci iv analyze --vset-only                                  # IV-specific analysis
sci ec analyze --peaks --charge                             # EC-specific analysis
sci raman analyze --denoise savgol --baseline airpls        # Raman preprocessing
sci afm analyze sample.gwy --psd                            # AFM surface roughness
sci pulse endurance --file data.csv                         # Endurance cycling
sci pulse stp --file data.csv                               # STP decay

# ── Phase 8: Collect Results ──────────────────────────────
sci results --move                                          # Symlink to project/results/

# ── Phase 9: Serve Dashboard ──────────────────────────────
sci serve --open                                            # Start AI Studio dashboard
```

---

## 13. Troubleshooting Guide

### Config Not Found
```bash
# Symptom: "Config not found" errors
# Fix:
sci config init --global
```

### Instrument Not Found
```bash
# Symptom: "Instrument '<name>' not registered"
# Check registry:
sci instrument ls
# Register new:
sci instrument register my-new-device
```

### File Not Assigned
```bash
# Symptom: File exists in data/raw/ but not visible to plot/analyze
# Fix:
sci add -m data
```

### Wrong Technique Detection
```bash
# Symptom: A file is detected as the wrong technique
# Fix: Use explicit --technique flag
sci plot --technique iv-sweep file.csv
sci analyze -t raman file.txt
```

### FZF Not Working
```bash
# Symptom: "fzf: command not found" or empty fzf
# Fix: Install fzf
brew install fzf        # macOS
sudo apt install fzf    # Linux
# Alternative: Use direct file paths instead of interactive mode
sci plot data/raw/file.csv
```

### Session Context Issues
```bash
# Symptom: Commands behaving unexpectedly (wrong protocol/project)
# Check current context:
sci status
# Or machine-readable:
sci status --json
# Reset context:
sci close -m project
sci open -m project correct-project
```

### Plot/Output Not Saving
```bash
# Symptom: No output file after plotting
# Check results directory:
sci plot results
# Ensure project context is set:
sci open -m project my-project
```

### Theme Not Applying
```bash
# List available themes:
sci config theme list
# Set explicitly:
sci config theme set publication-nature
```

### Grammar Parse Failure
```bash
# Symptom: Filename fields not parsed correctly
# Test grammar:
sci config grammar test "140526_Ta-PDA-ITO_r0c0_iv_01.csv"
# Edit grammar:
sci config edit grammar
```

### Protocol YAML Corruption
```bash
# Symptom: YAML read errors
# Check protocol structure:
sci ls -m protocol -n <name>
# Rebuild if needed:
sci delete -m protocol -n <name>
sci add -m protocol -n <name> ...
```

### `sci memristor` Still Used
```bash
# Scripts using deprecated command:
grep -r "sci memristor" ~/scripts/
# Migrate to:
#   sci memristor ls         → sci iv ls
#   sci memristor analyze    → sci iv analyze
#   sci memristor endurance  → sci pulse endurance
```

### Dashboard Won't Start
```bash
# Port conflict:
sci serve --port 8080
# Or use environment variable:
export SCI_SERVE_PORT=9000
sci serve
# Check if port is free:
lsof -i :8000
```

### Chat Command Fails
```bash
# Set LLM API key:
export SCI_LLM_API_KEY=your-key-here
# Or in config.yaml:
# chat:
#   api_key: ${YOUR_API_KEY_VAR}
```

---

## 14. Quick Reference Card

### Most Common Commands

| Task | Command |
|------|---------|
| Create project | `sci add -m project <name>` |
| Create protocol | `sci add -m protocol -n <name> --step s1,s2 -t t1,t2 --ins i1,i2` |
| Open project | `sci open -m project <name>` |
| Open protocol | `sci open -m protocol -n <name>` |
| Open step | `sci open -m step <name>` |
| Assign files | `sci add -m data` |
| Plot | `sci plot [--technique <t>] [<file>] [--grid] [--legend]` |
| Analyze | `sci analyze [--technique <t>] [<file>] [--yaml]` |
| List projects | `sci ls -m project` |
| List protocols | `sci ls -m protocol` |
| Status | `sci status [--json]` |
| Info | `sci info [--json]` |
| Config init | `sci config init --global` |
| Config show | `sci config show` |
| Theme list | `sci config theme list` |
| Theme set | `sci config theme set <name>` |
| Results | `sci results [--move]` |
| Serve | `sci serve [--port] [--open]` |
| Edit protocol | `sci edit -m protocol -n <name> --step ...` |
| Delete protocol | `sci delete -m protocol -n <name>` |
| Chat | `sci chat "<query>"` |

### 4 Chars or Less

```bash
sci ls               # List context
sci info             # Show manifest
sci status           # Show context tree
sci plot             # Interactive plot
sci edit -m ...      # Edit resources
sci open -m ...      # Set context
sci close -m step    # Close step
sci ins ls           # List instruments
```
