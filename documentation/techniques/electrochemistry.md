# Electrochemistry — CV, CA, EIS Analysis

## Overview

science-cli supports 5 electrochemical techniques, with full analysis and plotting for CV, CA, and EIS:

| Technique | Code | Detection Patterns | Analysis | Plotting |
|-----------|------|-------------------|----------|----------|
| Cyclic Voltammetry | `ec-cv` | `_CV.`, `.cv`, `cv_`, `cv-` | Peak detection, charge integration | CV overlay, peak markers |
| Chronoamperometry | `ec-ca` | `_CA.`, `.ca`, `ca_`, `ca-` | Cottrell fit, steady-state | CA transient, Cottrell plot |
| Impedance Spectroscopy | `ec-eis` | `.mpt`, `_EIS.`, `.eis`, `.z` | Circuit fitting, KK test | Nyquist, Bode, fit overlay |
| Linear Sweep Voltammetry | `ec-lsv` | `_LSV.`, `.lsv` | (stub — CV analysis works) | (stub) |
| Square Wave Voltammetry | `ec-swv` | `_SWV.`, `.swv` | (stub) | (stub) |

Technique detection is regex-based (`technique.py:59`, `BUILTIN_TECHNIQUES:115`), case-insensitive. `.mpt` is the only extension-based detector — others match filename substrings. Resolution order: config patterns → hardcoded fallback → first match wins.

---

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
sci plot <file>                     (visualize)
sci ec analyze <file>               (compute parameters)
```

### Step 1: Global Config (One-Time)

```bash
sci config init
sci config edit --global
```

Set `projects_root` to your experiments folder.

### Step 2: Create a Project

```bash
sci add -m project my-experiment
sci open -m project my-experiment
```

Always `open` a project before working on it — sets context for all subsequent commands.

### Step 3: Create a Protocol with Steps

```bash
sci add -m protocol -n doping \
  --step "1_cv-deposition,2_ca-doping,3_eis" \
  -t ec-cv,ec-ca,ec-eis \
  -d autolab-usth,autolab-usth,autolab-usth
```

Each step gets a **technique** (`-t`) and a **device** (`-d`, optional). List:

```bash
sci ls -m protocol        # list all protocols
sci ls -m protocol --step # show steps with technique + device
```

### Step 4: Assign Data Files to Steps

Place raw files in `<project>/data/raw/`, then:

```bash
sci add -m data --fzf
```

Interactive fzf selector — pick unassigned files and choose their step.

### Step 5: Plot

```bash
sci plot data/raw/2105_CV.txt
```

Change theme:

```bash
sci config theme list
sci config theme set publication-nature
```

| Theme | Best For |
|-------|----------|
| `default` | Quick previews |
| `dark` | Screens / presentations |
| `tufte` | Minimal ink, max data |
| `publication-acs` | ACS journal submissions |
| `publication-nature` | Nature journal submissions |
| `poster` | Conference posters |
| `acs-annotated` | ACS style with annotations |

Output format auto-detected from extension:

```bash
sci plot file.csv                    # → PDF
sci plot file.csv --output plot.png  # → PNG
sci plot file.csv --output plot.svg  # → SVG
```

---

## Biologic MPT Format

EC files from Biologic potentiostats use `.mpt`: semicolon delimiter, UTF-8, header followed by columns: `WE(1).Potential (V)`, `WE(1).Current (A)`, `Corrected time (s)`, `Frequency (Hz)`, `Z' (Ω)`, `-Z'' (Ω)`.

Column aliases in `science_cli/library/electrochem/__init__.py`, resolved by `ColumnMap.resolve()` (`technique.py:37`):

- **CV x**: `WE(1).Potential (V)`, `Potential (V)`, `potential`, `E`, `E/V`, `V`
- **CV y**: `WE(1).Current (A)`, `Current (A)`, `current`, `I`, `I/A`
- **CA x**: `Corrected time (s)`, `corrected time`, `time`, `Time`, `t/s`
- **CA y**: same as CV y
- **EIS f**: `Frequency (Hz)`, `f/Hz`, `freq`, `frequency`
- **EIS Z'**: `Z' (Ω)`, `Z'`, `Re(Z)`, `ReZ`, `Zre`, `z'`
- **EIS Z''**: `-Z'' (Ω)`, `-Z''`, `Z''`, `Im(Z)`, `ImZ`, `z''`

```python
COLUMN_MAPS: dict[str, ColumnMap] = {
    "ec-cv": ColumnMap(x="WE(1).Potential (V)", y="WE(1).Current (A)", ...),
    "ec-ca": ColumnMap(x="Corrected time (s)", y="WE(1).Current (A)", ...),
    "ec-eis": ColumnMap(x="Z' (Ω)", y="-Z'' (Ω)",
        extras={"frequency": "Frequency (Hz)", "magnitude": "|Z| (Ω)", "phase": "Phase (°)"}),
}
```

---

## CLI Commands

### sci ec ls

List EC files in the current project's `data/raw/`:

```bash
sci ec ls
```

Rich table with File, Size, Technique, Path columns. Implementation: `ec.py:148`. Detects via `detect_technique()`.

### sci ec info [file]

Show file metadata, technique, columns, value ranges:

```bash
sci ec info 2105_CV.txt
```

If no file argument, interactive fzf selector opens (`ec.py:46`). Shows protocol/step context with 20-line preview.

### sci ec analyze [--peers] [--charge] [--circuit RRC] [--kk]

Runs technique-appropriate analysis (auto-detected):

```bash
sci ec analyze 2105_CV.txt
```

Options:
- `--peers` / `--no-peers`: peak detection (default: on)
- `--charge`: integrated charge (default: off)
- `--circuit` (EIS): circuit model (default: `RRC`)
- `--kk` (EIS): Kramers-Kronig test (default: off)

Routes via `ec.py:341`:
```python
if tech == "ec-cv":      _analyze_cv(str(p), flags)
elif tech == "ec-ca":    _analyze_ca(str(p), flags)
elif tech == "ec-eis":   _analyze_eis(str(p), flags)
```

Results written via `write_analysis_yaml()` (`analysis_output.py:24`) to `<step_dir>/results/<technique>_analysis.yaml`.

### sci eis [subcommand]

```bash
sci eis kk <file>                    # Kramers-Kronig test
sci eis fit <file> [--circuit RRC]   # Circuit fitting
sci eis batch                        # Batch fit all EIS files
sci eis simulate                     # (stub)
sci eis export <file>                # Export fit to JSON
```

See `eis.py:79` for handler dispatch, `eis.py:104-176` for subcommands.

---

## CV Analysis (Cyclic Voltammetry)

```bash
sci ec analyze -f 2105_CV.txt
```

Output:

```
CV Analysis: 2105_CV.txt
  Anodic peaks: 1
    E_pa=0.4520V  I_pa=3.45e-5A
  Cathodic peaks: 1
    E_pc=0.2130V  I_pc=-2.89e-5A
  ΔE_p = 0.2390V
  Charge: 1.24e-5 C  (with --charge flag)
```

### Implementation

**Data model** (`models.py:8`):

```python
@dataclass
class CVData:
    potential: np.ndarray
    current: np.ndarray
    scan_rate: float = 0.0
    metadata: dict | None = None
```

**Analyzer** (`cv.py:9`): `analyze_cv(data, options) → dict` dispatches to:
- `peak_analysis()` — `scipy.signal.find_peaks` with height/distance/prominence params
- `calculate_charge()` — `numpy.trapezoid` integration: `Q = ∫ i(E) dE / ν`

Anodic peaks on raw current (positive maxima). Cathodic by inverting signal (`-cur`). NaN-safe wrapper at `cv.py:93`.

**Scan rate analysis** (`cv.py:141`): `scan_rate_analysis(curves: list[CVData])` fits linear (surface-confined: `i_p ∝ v`) and square-root (diffusion: `i_p ∝ √v`) models. Randles-Sevcik: `i_p = 0.4463 nFAC √(nFvD/RT)`.

### Understanding CV Results

- **ΔE_p**: smaller → faster electron transfer. Reversible 1e⁻: ~59 mV at 25°C.
- **I_pa/I_pc**: ~1.0 reversible. Deviations → coupled reactions.
- **Charge**: proportional to surface coverage (Γ = Q/nFA).
- **Scan rate**: linear `i_p` vs `v` → surface control; linear vs `√v` → diffusion control.

### Plotting (`plot/cv.py`)

```python
plot_cv_curve(pot, cur, flags, label, ax)         # basic CV
plot_cv_overlay(curves, flags)                     # multi-curve
plot_cv_with_peaks(pot, cur, peaks, flags, label)  # with ▼ anodic / ▲ cathodic markers
```

### CV YAML Schema

```yaml
technique: ec-cv
instrument: autolab-usth
peaks:
  n_anodic: 1
  anodic_peaks:
    - index: 142
      potential: 0.452
      current: 3.45e-05
      height: 3.45e-05
  n_cathodic: 1
  cathodic_peaks:
    - index: 318
      potential: 0.213
      current: -2.89e-05
  average_peak_separation: 0.239
charge:
  total_charge: 1.24e-05
  anodic_charge: 6.80e-06
  cathodic_charge: 5.60e-06
  unit: C
```

---

## CA Analysis (Chronoamperometry)

```bash
sci ec analyze -f 2105_CA.txt
```

Output:

```
CA Analysis: 2105_CA.txt
  Cottrell slope: 2.34e-4 A·√s  R²=0.998
  Steady state: 1.23e-6A
```

### Implementation

**Data model** (`models.py:17`):

```python
@dataclass
class CAData:
    time: np.ndarray
    current: np.ndarray
    potential: float = 0.0
    metadata: dict | None = None
```

**Analyzer** (`ca.py:9`): `analyze_ca(data, options) → dict` dispatches to:
- `analyze_cottrell()` — lmfit of `i(t) = slope/√t + intercept` in t^{-1/2} space (`ca.py:24`)
- `analyze_steady_state()` — mean of last 20% of transient (`ca.py:62`)

Cottrell equation: `i(t) = nFAC√(D/πt)`. From slope: `nFAC√D = slope · √π`.

### Understanding CA Results

- **Cottrell slope**: proportional to electroactive species. Extract D if area/n known.
- **R²**: >0.99 → clean diffusion-limited behavior.
- **Steady-state**: plateau after diffusion stabilizes. Compare to Cottrell for convection effects.

### Plotting (`plot/ca.py`)

```python
plot_ca_decay(time, current, flags, label, ax)              # i vs t
plot_ca_cottrell(time, current, fit_x, fit_y, flags, label) # i vs t^{-1/2}
```

### CA YAML Schema

```yaml
technique: ec-ca
instrument: autolab-usth
cottrell:
  slope: 2.34e-04
  slope_stderr: 1.21e-06
  intercept: -5.32e-08
  r_squared: 0.998
steady_state:
  steady_state_current: 1.23e-06
  steady_state_std: 4.56e-08
  steady_state_time: 4.0
  steady_state_fraction: 0.2
```

---

## EIS Analysis (Electrochemical Impedance Spectroscopy)

```bash
sci ec analyze -f 2105_EIS.txt
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

KK test and circuit selection:

```bash
sci ec analyze -f 2105_EIS.txt --kk
sci ec analyze -f 2105_EIS.txt --circuit RQR
sci ec analyze -f 2105_EIS.txt --circuit R_s(C[RW])
sci ec analyze -f 2105_EIS.txt --circuit R_s(Q[RW])
```

### Implementation

**Data model** (`models.py:26`):

```python
@dataclass
class EISData:
    frequency: np.ndarray
    impedance: np.ndarray  # complex
    temperature: float = 0.0
    metadata: dict | None = None

    @property
    def real(self) -> np.ndarray:      # Z'
    @property
    def imag(self) -> np.ndarray:      # Z''
    @property
    def magnitude(self) -> np.ndarray:  # |Z|
    @property
    def phase(self) -> np.ndarray:     # degrees
```

**Equivalent circuits** (registered in `eis.py:83`):

| Name | Circuit | Parameters |
|------|---------|------------|
| `RC` | Series RC | R, C |
| `RRC` | Randles R(RC) | Rs, Rct, Cdl |
| `RQR` | Randles R(RQ) | Rs, Rct, Q_mag, Q_n |
| `R_s(C[RW])` | Randles + Warburg | Rs, Cdl, Rct, sigma |
| `R_s(Q[RW])` | CPE + Warburg | Rs, Q_mag, Q_n, Rct, sigma |

CPE: `Zcpe = 1/(Q·(jω)^n)`. Warburg: `Zw = σ/√(jω)`.

**Circuit fitting** (`eis.py:95`): `lmfit.Minimizer` on combined real+imag residuals. Parameter bounds: Rs (1–1e6), Cdl (1e-12–1), Q_n (0.5–1.0).

**Best circuit fit** (`eis.py:178`): tries all circuits (except RC), returns highest R².

**Kramers-Kronig** (`eis.py:203`): fits Voigt circuit (N RC elements, log-spaced τ). Passes if consistency_score < 5%. Common failures: cable inductance, non-stationary sample, saturation.

### Understanding EIS Results

- **Rs**: high-frequency intercept → electrolyte + contact resistance.
- **Rct**: semicircle diameter ↔ `i₀ = RT/nFRct`.
- **Cdl**: `ω_max = 1/Rct·Cdl`. Typical: 10–50 μF/cm².
- **CPE n**: 1 → ideal capacitor; 0.5 → Warburg; 0 → resistor.
- **Warburg σ**: `σ = RT/(n²F²A√2D·C)` — 45° tail at low frequencies.
- **Nyquist shape**: one semicircle → one time constant. Depressed → CPE (roughness). Two semicircles → two processes.

### Plotting (`plot/eis.py`)

```python
plot_eis_nyquist(z_real, z_imag, flags, label, ax)          # Z' vs -Z'' (equal aspect)
plot_eis_bode(frequency, magnitude, phase, flags)            # |Z| + phase vs f (twin axis)
plot_eis_fit(z_real, z_imag, fit_real, fit_imag, flags)     # Nyquist + dashed fit overlay
```

`_ensure_neg_imag()` (`eis.py:13`) detects sign convention from min value.

### EIS YAML Schema

```yaml
technique: ec-eis
instrument: autolab-usth
circuit_fit:
  circuit: RRC
  parameter_names: [Rs, Rct, Cdl]
  fitted_params: [120.3, 4520.1, 3.21e-06]
  param_stderr: [0.5, 15.2, 1.23e-08]
  r_squared: 0.994
  reduced_chi: 2.31e-03
kk:
  passes: true
  consistency_score: 2.1
  n_poles: 10
  reduced_chi: 1.89e-03
```

---

## Plot Types by Technique

| Technique | Plot Type | Function | Description |
|-----------|-----------|----------|-------------|
| ec-cv | CV overlay | `plot_cv_curve()` | Current vs potential |
| ec-cv | CV + peaks | `plot_cv_with_peaks()` | CV with ▼ anodic / ▲ cathodic |
| ec-cv | Multi-overlay | `plot_cv_overlay()` | Multiple CVs |
| ec-ca | Transient | `plot_ca_decay()` | Current vs time |
| ec-ca | Cottrell | `plot_ca_cottrell()` | i vs t^{-1/2} + fit |
| ec-eis | Nyquist | `plot_eis_nyquist()` | Z' vs -Z'' |
| ec-eis | Bode | `plot_eis_bode()` | |Z| + phase vs f |
| ec-eis | Fit overlay | `plot_eis_fit()` | Nyquist + fit |

---

## Plugin Registration

Exported by `science_cli/library/electrochem/__init__.py`:

```python
COLUMN_MAPS: dict[str, ColumnMap] = { ... }      # column name mapping
ANALYZERS: dict[str, callable] = {
    "ec-cv": analyze_cv,
    "ec-ca": analyze_ca,
    "ec-eis": analyze_eis,
}
PLOT_PRESETS: dict[str, dict] = {
    "ec-cv": {"type": "line", "xlabel": "Potential (V)", "ylabel": "Current (A)"},
    "ec-ca": {"type": "line", "xlabel": "Time (s)", "ylabel": "Current (A)"},
    "ec-eis": {"type": "nyquist", "xlabel": "Z' (Ω)", "ylabel": "-Z'' (Ω)"},
}
```

CLI handlers: `ec.py:126` (`ec_handler`), `eis.py:79` (`eis_handler`). The `ec plot` subcommand is deprecated — use `sci plot --technique <ec-cv|ec-ca|ec-eis>`.

---

## Advanced: Multi-File Overlays

```bash
sci plot file1_CV.txt,file2_CV.txt,file3_CV.txt
```

Overlays matching techniques on same axes. Useful for: before/after modification, scan rate study, aging, temperature-dependent EIS.

Individual plots: `sci plot file1.txt,file2.txt --all`

---

## Filename Parsing

```python
parse_filename_grammar("250101_Pt_electrode_CV_01.txt")
# → {"date_code": "250101", "material": "Pt_electrode",
#    "technique": "CV", "suffix": 1, "matrix": None}
```

Universal fields: `date_code`, `material`, `technique`, `matrix`, `suffix`. Matrix sub-grid: `r0c0` → `{"row": 0, "col": 0}`. See `technique.py:348`.

---

## See Also

- **cyclic-voltammetry.md** — Full CV guide: peak interpretation, reversibility, surface coverage
- **chronoamperometry.md** — Full CA guide: Cottrell derivation, diffusion coefficients
- **impedance-spectroscopy.md** — Full EIS guide: circuit models, KK validation, Warburg
- **overview.md** — General tool overview
- **workflows/electrochemistry-analysis.md** — End-to-end: project → analysis → export → figures
