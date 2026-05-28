# Electrochemistry Guide

science-cli supports three electrochemical techniques:

| Technique | Code | Analysis | Plotting |
|-----------|------|----------|----------|
| Cyclic Voltammetry | `ec-cv` | Peak detection, charge | CV overlays |
| Chronoamperometry | `ec-ca` | Cottrell fit, steady-state | CA transients |
| Electrochemical Impedance Spectroscopy | `ec-eis` | Circuit fitting, KK test | Nyquist, Bode |

## General Workflow

```
config init → config edit --global  (one-time setup)
    ↓
add -m project my-project           (create project)
    ↓
add -m protocol -n experiment       (create protocol with steps)
    ↓
add -m data --fzf                   (assign files to steps)
    ↓
sci plot <file>                      (visualize)
sci analyze -f <file>                (compute parameters)
```

## Step 1: Global Config (One-Time)

Before your first project, initialize and set your working directory:

```bash
sci config init
sci config edit --global
```

Set `projects_root` to your experiments folder (e.g. `/home/user/projects` or `~/experiments`).

## Step 2: Create a Project

```bash
sci add -m project my-experiment
sci open -m project my-experiment
```

Always `open` a project before working on it — this sets the context for all subsequent commands.

## Step 3: Create a Protocol with Steps

A protocol describes one experiment: what measurement steps exist, what technique each step uses, and what instrument collected the data.

```bash
sci add -m protocol -n doping \
  --step "1_cv-deposition,2_ca-doping,3_eis" \
  -t ec-cv,ec-ca,ec-eis \
  -d autolab-usth,autolab-usth,autolab-usth
```

Each step gets a **technique** (`-t`) and a **device** (`-d`, optional). The device tells the data loader how to parse the raw files (delimiter, header lines, column names, etc.).

List your protocols and steps:

```bash
sci ls -m protocol        # list all protocols
sci ls -m protocol --step # show steps with technique + device columns
```

## Step 4: Assign Data Files to Steps

Place your raw data files in `<project>/data/raw/`, then assign them to protocol steps:

```bash
sci add -m data --fzf
```

This opens an interactive fzf selector showing unassigned files. Pick files and choose which step to assign them to.

## Step 5: Plot

```bash
sci plot data/raw/2105_CV.txt
```

By default this uses the active theme. Change theme:

```bash
sci config theme list              # see available themes
sci config theme set publication-nature
```

Themes control figure size, font family, line colors, grid style, and DPI:

| Theme | Best For |
|-------|----------|
| `default` | Quick previews |
| `dark` | Screens / presentations |
| `tufte` | Minimal ink, max data |
| `publication-acs` | ACS journal submissions |
| `publication-nature` | Nature journal submissions |
| `poster` | Conference posters |
| `acs-annotated` | ACS style with annotations |

Output format is auto-detected from extension:

```bash
sci plot file.csv                    # → PDF (default)
sci plot file.csv --output plot.png  # → PNG
sci plot file.csv --output plot.svg  # → SVG
```

For multi-file overlays:

```bash
sci plot file1.csv,file2.csv,file3.csv
```

Or with wildcard-style comma-separated names within a session.

## CV Analysis (Cyclic Voltammetry)

```bash
sci analyze -f 2105_CV.txt
```

Output:

```
CV Analysis: 2105_CV.txt
  Anodic peaks: 1
    E_pa=0.4520V  I_pa=3.45e-5A
  Cathodic peaks: 1
    E_pc=0.2130V  I_pc=-2.89e-5A
  ΔE_p = 0.2390V
```

Calculate charge (requires `--charge` flag):

```bash
sci analyze -f 2105_CV.txt --charge
```

CV plots show potential vs current with peak markers automatically annotated.

### Understanding CV Results

- **Peak separation** (ΔE_p): Smaller values indicate faster electron transfer
- **Peak current ratio** (I_pa/I_pc): ~1.0 for reversible systems
- **Charge**: Integrated area under the curve, proportional to surface coverage

## CA Analysis (Chronoamperometry)

```bash
sci analyze -f 2105_CA.txt
```

Output:

```
CA Analysis: 2105_CA.txt
  Cottrell slope: 2.34e-4 A·√s  R²=0.998
  Steady state: 1.23e-6A
```

CA plots show current vs time with Cottrell fit overlay. The analyze command fits the Cottrell equation (`I = nFAC√(D/πt)`) to the decay region.

### Understanding CA Results

- **Cottrell slope**: Proportional to `nFAC√D` — larger means more electroactive species
- **Steady-state current**: Plateau current after diffusion layer stabilizes
- **R²**: Goodness of fit (>0.99 indicates clean Cottrell behavior)

## EIS Analysis (Electrochemical Impedance Spectroscopy)

```bash
sci analyze -f 2105_EIS.txt
```

Output:

```
EIS Analysis: 2105_EIS.txt
  Circuit fit: RRC
    R_solution: 120.3 Ω
    R_ct: 4520.1 Ω
    C_dl: 3.21e-6 F
    R²: 0.994
```

Run Kramers-Kronig validity test:

```bash
sci analyze -f 2105_EIS.txt --kk
```

Fit different equivalent circuits:

```bash
sci analyze -f 2105_EIS.txt --circuit RRC      # default
sci analyze -f 2105_EIS.txt --circuit RQR       # with CPE (Q)
sci analyze -f 2105_EIS.txt --circuit RQRW      # with Warburg
```

EIS plots support both Nyquist (Z' vs -Z'') and Bode (impedance vs frequency) views.

### Understanding EIS Results

- **R_solution**: Uncompensated resistance (intercept at high frequency)
- **R_ct**: Charge transfer resistance (diameter of semicircle)
- **C_dl**: Double-layer capacitance
- **Warburg (W)**: Diffusion tail at low frequencies
- **CPE (Q)**: Constant phase element for non-ideal capacitors

## Plot Types by Technique

| Technique | Plot Type | Description |
|-----------|-----------|-------------|
| ec-cv | CV overlay | Current vs potential, cycle overlay |
| ec-ca | CA transient | Current vs time with Cottrell fit |
| ec-eis | Nyquist | Z' vs -Z'' |
| ec-eis | Bode | |Z| vs frequency, phase vs frequency |

## Advanced: Multi-File Overlays

```bash
sci plot file1_CV.txt,file2_CV.txt,file3_CV.txt
```

science-cli detects matching techniques and overlays them on the same axes with a legend. This is useful for comparing:

- Before/after surface modification
- Different scan rates (multi-rate CV)
- Aging studies (day 0 vs day 7)
