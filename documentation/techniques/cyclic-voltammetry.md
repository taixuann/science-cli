# Cyclic Voltammetry (CV)

## Overview

Cyclic voltammetry is an electroanalytical technique that measures the current response of a working electrode to a linearly swept potential waveform. The potential is swept between two vertex values at a constant scan rate ν (V/s), and the resulting current-potential curve (voltammogram) reveals oxidation and reduction processes at the electrode surface.

### Fundamental Principle

The potential waveform is triangular: starting at E_start, sweeping to E_vertex1 at rate ν, reversing direction and sweeping to E_vertex2 (often the same potential on the opposite side), then optionally returning to E_start. The resulting current contains contributions from:

- **Faradaic current** — electron transfer to/from electroactive species in solution or immobilized on the electrode surface. This is the signal of interest, proportional to concentration and electrode kinetics.
- **Capacitive/charging current** — non-Faradaic double-layer charging, proportional to scan rate and electrode area. This is the background that limits detection sensitivity.

### Reversible vs Irreversible vs Quasi-Reversible Systems

The shape of a voltammogram is governed by the electron transfer rate constant k⁰ relative to the scan rate.

**Reversible (Nernstian) systems** (k⁰ >> ν):
- Rapid electron transfer: surface concentrations obey the Nernst equation at all potentials.
- Peak separation ΔE_p = 59/n mV at 25°C (for an ideal 1e⁻ process: ~59 mV, 2e⁻: ~30 mV).
- Peak current ratio |I_pa / I_pc| = 1.
- Peak current i_p ∝ ν¹/² (diffusion-controlled, Randles-Ševčík equation).
- E_p is independent of scan rate.

**Irreversible systems** (k⁰ << ν):
- Slow electron transfer: significant overpotential required to drive the reaction.
- No reverse peak (or severely attenuated).
- ΔE_p increases with scan rate.
- Peak current i_p ∝ ν¹/² but with different proportionality: i_p = 0.4958 · nFAC · √(nFνD/RT).
- Peak potential E_p shifts with scan rate (~30/αn mV per decade for a cathodic process at 25°C).

**Quasi-reversible systems** (k⁰ ≈ ν):
- Intermediate behavior: peaks are broader and more separated than the reversible case.
- ΔE_p increases with scan rate (from ~59 mV at low ν to much larger at high ν).
- Peak ratio deviates from unity.
- Full Nicholson-Shain analysis can extract k⁰ and α (transfer coefficient).

### Randles-Ševčík Equation (Diffusion-Controlled)

For a reversible system at 25°C:

```
i_p = (2.69 × 10⁵) · n³/² · A · C · √(nνD)
```

Where:
- i_p = peak current (A)
- n = number of electrons transferred
- A = electrode area (cm²)
- C = bulk concentration (mol/cm³)
- D = diffusion coefficient (cm²/s)
- ν = scan rate (V/s)

### Surface-Confined Species

For electroactive species adsorbed on the electrode surface (thin-film limit):

```
i_p = n²F²Γν / 4RT
```

Here i_p ∝ ν (linear with scan rate), distinct from the ν¹/² dependence of diffusion control. This is the diagnostic criterion distinguishing surface-bound from solution-phase species.

### Capacitive Current

```
i_c = C_dl · A · ν
```

The charging current is linear in scan rate and constant with potential (assuming constant double-layer capacitance C_dl). At high scan rates, i_c can dominate i_f, degrading the Faradaic signal-to-background ratio.

---

## Data Format

The `ec-cv` technique resolves potential and current columns from arbitrary file headers using the `ColumnMap` alias system defined in `science_cli/library/electrochem/__init__.py`.

### Column Aliases

The first alias match wins in order of priority.

**Potential (x-axis) aliases:**
```
WE(1).Potential (V)
Potential (V)
potential
Potential applied (V)
E
E/V
V
Voltage (V)
```

**Current (y-axis) aliases:**
```
WE(1).Current (A)
Current (A)
current
I
I/A
<I>/A
```

### ColumnMap Definition

The system register at `science_cli/library/electrochem/__init__.py:68`:

```python
COLUMN_MAPS["ec-cv"] = ColumnMap(
    x="WE(1).Potential (V)",
    y="WE(1).Current (A)",
    x_label="Potential (V)",
    y_label="Current (A)",
    x_aliases=_cv_x_aliases,
    y_aliases=_cv_y_aliases,
)
```

### Biologic MPT Format

Files from Biologic potentiostats use `.mpt` extension with semicolon delimiter and UTF-8 encoding. The header contains metadata rows followed by a column header row. Common columns include `WE(1).Potential (V)`, `WE(1).Current (A)`, `Corrected time (s)`, and `Cycle Number`. The column alias mapper resolves these automatically.

### Generic CSV/Text Format

Any two-column delimiter-separated file with headers matching the alias list above. science-cli auto-detects delimiter (comma, tab, semicolon, whitespace) and encoding.

### CVData Model

Loaded CV data is stored in the `CVData` dataclass (`models.py:9`):

```python
@dataclass
class CVData:
    potential: np.ndarray
    current: np.ndarray
    scan_rate: float = 0.0
    metadata: dict | None = None
```

The `scan_rate` field is optional and defaults to 0.0. It is used by `calculate_charge()` to normalize integrated charge (Q = ∫I dE / ν) and by `scan_rate_analysis()` to fit multiple curves at different rates.

---

## CLI Usage

### Analyzing CV Data

```bash
sci ec analyze <file> [--peaks] [--charge]
```

Peak detection is enabled by default. Charge integration requires the `--charge` flag.

#### Example

```bash
sci ec analyze 2105_HfOx_CV_001.txt
```

Output:

```
CV Analysis: 2105_HfOx_CV_001.txt
  Anodic peaks: 1
    E_pa=0.4520V  I_pa=3.45e-5A
  Cathodic peaks: 1
    E_pc=0.2130V  I_pc=-2.89e-5A
  ΔE_p = 0.2390V
```

With charge integration:

```bash
sci ec analyze 2105_HfOx_CV_001.txt --charge
```

Output:

```
CV Analysis: 2105_HfOx_CV_001.txt
  Anodic peaks: 1
    E_pa=0.4520V  I_pa=3.45e-5A
  Cathodic peaks: 1
    E_pc=0.2130V  I_pc=-2.89e-5A
  ΔE_p = 0.2390V
  Charge: 1.24e-5 C
  Anodic: 6.80e-6 C  Cathodic: 5.60e-6 C
```

### Interactive FZF Selection

Without a file argument, `sci ec analyze` opens the fzf selector:

```bash
sci ec analyze
```

This shows all electrochemistry files in the current project's `data/raw/`, annotated with protocol and step metadata. Multi-select with Tab.

### Analyzing Multiple Files

Pass multiple files:

```bash
sci ec analyze 2105_CV_001.txt 2105_CV_002.txt 2105_CV_003.txt
```

Each file is analyzed independently with its results printed sequentially.

### Using sci analyze --technique

The generic analyze command with explicit technique flag dispatches to the same analyzer:

```bash
sci analyze --technique ec-cv 2105_HfOx_CV_001.txt
```

### Plotting CV Data

```bash
sci plot --technique ec-cv <file> [--scan-rate] [--cycles]
```

Plot flags for `ec-cv`:

| Flag | Type | Description |
|------|------|-------------|
| `--scan-rate` | float | Scan rate in mV/s (display annotation) |
| `--cycles` | int | Number of CV cycles (display annotation) |

#### Examples

Basic CV plot:

```bash
sci plot 2105_HfOx_CV_001.txt
```

The `ec-cv` technique auto-detects from filename (pattern `_CV.`), resolves Potential vs Current columns, and generates a publication-quality line plot with axes labeled "Potential (V)" and "Current (A)".

Overlay multiple CV curves:

```bash
sci plot 2105_CV_10mVs.txt,2105_CV_50mVs.txt,2105_CV_100mVs.txt
```

The overlay mode prompts: "Overlay all (o) or individual plots (i)?" With overlay, all traces appear on the same axes with auto-legend.

Interactive FZF selection:

```bash
sci plot
```

Opens fzf with protocol/step context, prompts for style and figure options, then renders with theme defaults.

### Alternative Plot Entry Points

```bash
sci ec plot 2105_CV.txt      # deprecated — use sci plot --technique ec-cv
sci plot file.txt --all       # individual plots for multiple files
```

---

## Peak Detection

Peak detection is performed by `peak_analysis()` in `science_cli/library/electrochem/cv.py:24` using `scipy.signal.find_peaks` with configurable parameters.

### Algorithm

1. **Anodic peaks**: `find_peaks` is called on the raw current array. Positive current maxima correspond to oxidation events.
2. **Cathodic peaks**: The current signal is inverted (`-cur`), turning reduction minima into maxima for detection. Detected values are re-inverted in the output.
3. **NaN handling**: The `_find_peaks` wrapper (`cv.py:93`) returns empty results if any NaN values are present.

### Parameters

All parameters are optional and passed through from the CLI flags dict:

| Parameter | Type | Default | Effect |
|-----------|------|---------|--------|
| `height` | float | None | Minimum peak height (absolute current). Filters out noise. |
| `distance` | int | None | Minimum number of samples between neighboring peaks. Prevents double-counting. |
| `prominence` | float | None | Minimum peak prominence — the vertical distance between a peak and its lowest contour line. Most robust noise filter. |
| `peak_type` | str | "both" | `"anodic"`, `"cathodic"`, or `"both"` (default). |

### Output

Each detected peak returns:

| Field | Type | Description |
|-------|------|-------------|
| `index` | int | Array index in the potential/current arrays |
| `potential` | float | Potential at the peak (V) |
| `current` | float | Current at the peak (A) |
| `height` | float | Peak height from `find_peaks` metadata |

### Aggregate Output

| Field | Type | Description |
|-------|------|-------------|
| `n_anodic` | int | Number of detected anodic peaks |
| `anodic_peaks` | list[dict] | List of anodic peak dicts |
| `n_cathodic` | int | Number of detected cathodic peaks |
| `cathodic_peaks` | list[dict] | List of cathodic peak dicts |
| `average_peak_separation` | float | Mean ΔE_p across all anodic-cathodic pairs (V). Only present when both anodic and cathodic peaks exist. |

### Average Peak Separation

When multiple peaks are detected on each scan direction, `peak_analysis` computes the all-pairs mean separation:

```python
separations = []
for ap in anodic_peaks:
    for cp in cathodic_peaks:
        separations.append(abs(ap["potential"] - cp["potential"]))
result["average_peak_separation"] = float(np.mean(separations))
```

For a simple 1-peak system this equals ΔE_p = |E_pa - E_pc|. For multi-peak systems it provides a summary statistic, though pair-wise interpretation is recommended.

### Peak Plotting

The `plot_cv_with_peaks()` function (`plot/cv.py:60`) overlaid red ▼ markers on anodic peaks and blue ▲ markers on cathodic peaks:

```python
def plot_cv_with_peaks(potential, current, peaks, flags, label=""):
    fig, ax = plot_cv_curve(potential, current, flags, label)
    for pk in anodic:
        ax.plot(ep, ip, "v", color="red", markersize=8)
    for pk in cathodic:
        ax.plot(ep, ip, "^", color="blue", markersize=8)
    return fig, ax
```

---

## Charge Integration

Charge integration is performed by `calculate_charge()` in `cv.py:104`. The charge Q is the area under the current-potential curve, normalized by scan rate.

### Algorithm

```python
Q_total   = ∫ I(E) dE / ν
Q_anodic  = ∫ I⁺(E) dE / ν    (current > 0)
Q_cathodic = ∫ I⁻(E) dE / ν   (current < 0)
```

Integration uses `numpy.trapezoid` (or `scipy.integrate.trapezoid` as fallback for older NumPy). The division by scan rate ν converts the potential-domain integral to time-domain charge.

### Key Details

- The scan rate ν is taken from `CVData.scan_rate`. If not set (defaults to 0.0), it falls back to 1.0 to avoid division by zero.
- Anodic charge integrates only points where I > 0.
- Cathodic charge integrates only points where I < 0, and its absolute value is returned (positive in output).
- The unit is Coulombs (C), though in a potential-domain integral the physical meaning is closer to a capacitance-equivalent: Q/ν has units of C = A·s = A·(V/V) · (V/s)⁻¹ etc.

### Nomenclature

If scan rate is known, the integrated charge relates to:

- **Surface coverage** (adsorbed species): Γ = Q/nFA (mol/cm²)
- **Capacitance**: C = Q/ΔE (F), often used for supercapacitor characterization
- **Electroactive loading**: For thin films, Q tracks Faradaic efficiency

### CLI

```bash
sci ec analyze 2105_CV.txt --charge
```

Without `--charge`, charge integration is skipped entirely (`analyze_cv` checks `options.get("charge", False)`).

---

## Multi-Rate Analysis

The `scan_rate_analysis()` function (`cv.py:141`) analyzes peak current vs scan rate across multiple CV curves to diagnose the rate-limiting mechanism.

### Usage

```python
from science_cli.library.electrochem import scan_rate_analysis
from science_cli.library.electrochem.models import CVData

curves = [
    CVData(potential=p1, current=i1, scan_rate=0.01),
    CVData(potential=p2, current=i2, scan_rate=0.05),
    CVData(potential=p3, current=i3, scan_rate=0.10),
]
result = scan_rate_analysis(curves)
```

### Output

```python
{
    "scan_rates": [0.01, 0.05, 0.10],
    "peak_currents": [1.2e-6, 2.7e-6, 3.8e-6],
    "peak_potentials": [0.45, 0.46, 0.47],
    "linear_fit_slope": 2.9e-5,
    "linear_fit_intercept": 8.1e-7,
    "sqrt_fit_slope": 1.1e-5,
    "sqrt_fit_intercept": 1.5e-7,
}
```

### Fitting Models

**Linear fit** (i_p ∝ ν):
- Slope and intercept from `np.polyfit(sr, ip, 1)`.
- Diagnostic for surface-confined species: adsorbed electroactive monolayers, conductive polymer films, pseudocapacitive materials.
- For true surface processes, i_p should be linear with ν and pass near zero.

**Square-root fit** (i_p ∝ √ν — Randles-Ševčík):
- Slope and intercept from `np.polyfit(np.sqrt(sr), ip, 1)`.
- Diagnostic for diffusion-controlled processes: solution-phase redox, intercalation, ion diffusion in solid-state films.
- For reversible diffusion, i_p is linear with √ν and passes near zero.

### Mechanism Discrimination

In practice, many systems show mixed behavior. The standard approach:

1. Plot log(i_p) vs log(ν). The slope b (from i_p ∝ ν^b) indicates:
   - b = 0.5 → diffusion-controlled
   - b = 1.0 → surface-controlled (capacitive)
   - 0.5 < b < 1.0 → mixed contribution
2. Compare R² of linear vs sqrt fits as a secondary indicator.

### Scan Rates Extraction

The function calls `peak_analysis()` on each CVData internally, extracting the first anodic peak current (falling back to the first cathodic peak if no anodic peak exists). It requires at least 2 curves with positive scan rates to perform fitting.

---

## Understanding CV Results

### Peak Separation ΔE_p

ΔE_p = |E_pa - E_pc| is the primary diagnostic for electron transfer kinetics.

| ΔE_p (at 25°C) | Interpretation |
|----------------|---------------|
| 59/n mV | Reversible 1e⁻ (59 mV), 2e⁻ (30 mV), assuming no coupled chemistry |
| < 59 mV | Unlikely for simple electron transfer; consider ohmic drop or film effects |
| 60-80 mV | Slight kinetic limitation — quasi-reversible |
| 80-200 mV | Moderately quasi-reversible |
| > 200 mV | Slow electron transfer or significant uncompensated resistance |
| No reverse peak | Irreversible or EC mechanism (follow-up chemical reaction) |

The theoretical minimum of 59/n mV assumes:
- Nernstian behavior
- Rapid electron transfer (k⁰ > 0.3 cm/s for ν = 0.1 V/s)
- Diffusion-only mass transport
- No iR drop (uncompensated resistance)
- Planar electrode geometry

iR drop broadens ΔE_p artificially. Correcting with positive feedback compensation or post-processing is standard practice.

### Peak Current Ratio

|I_pa / I_pc| = 1.0 for a reversible system. Deviations indicate:

- **Ratio < 1**: Product of the forward reaction is consumed by a follow-up chemical reaction (EC mechanism).
- **Ratio > 1**: Reactant is regenerated by a preceding chemical reaction (CE mechanism).
- **Ratio varying with scan rate**: Kinetic competition — the follow-up reaction has less time at high scan rates.

### Formal Potential

The formal reduction potential E⁰' is approximated by the midpoint:

```
E_1/2 ≈ (E_pa + E_pc) / 2
```

For a reversible system, E_1/2 ≈ E⁰'. For quasi-reversible systems, E_1/2 shifts with scan rate, and the formal potential must be obtained from the scan-rate-independent limit.

### Charge vs Coverage

For surface-confined electroactive species:

```
Γ = Q / nFA
```

Where:
- Γ = surface coverage (mol/cm²)
- Q = integrated anodic or cathodic charge (C)
- n = number of electrons
- F = Faraday constant (96485 C/mol)
- A = electrode area (cm²)

For a monolayer, Γ is typically 10⁻¹⁰ to 10⁻⁹ mol/cm².

### Scan Rate Dependence Summary

| Diagnostic | Surface-Confined | Diffusion-Controlled |
|-----------|-----------------|----------------------|
| i_p vs ν | Linear | Linear in √ν |
| i_p vs √ν | Quadratic | Linear |
| log i_p vs log ν | Slope = 1 | Slope = 0.5 |
| ΔE_p vs ν | Often ~0 (fast) | ~59/n mV (reversible), increases (quasi-rev) |
| Peak shape | Symmetric, narrow | Asymmetric, broader |
| Peak width at half-height | 90.6/n mV | Variable |

### Common Artifacts

- **iR drop**: Shifts peaks apart, broadens them. Symptom: ΔE_p increases with current magnitude.
- **Capacitive background**: Subtracts as baseline. Check with blank electrolyte.
- **Adsorption/desorption spikes**: Additional peaks that do not follow scan rate dependence of Faradaic peaks.
- **Ohmic distortion**: Steep current rise followed by rounded peak — especially in dilute electrolyte or large electrode areas.
- **Nucleation loop**: Current crossover on forward vs reverse scan — electrodeposition / phase formation.

---

## YAML Schema

When analysis results are written via `write_analysis_yaml()` (`analysis_output.py:24`), the output follows this structure:

```yaml
technique: ec-cv
instrument: autolab-usth
devices: electrochem
timestamp: "2026-06-15T12:00:00Z"
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
      height: 2.89e-05
  average_peak_separation: 0.239
charge:
  total_charge: 1.24e-05
  anodic_charge: 6.80e-06
  cathodic_charge: 5.60e-06
  unit: C
```

### Field Reference

| Path | Type | Required | Description |
|------|------|----------|-------------|
| `technique` | str | yes | Fixed: `"ec-cv"` |
| `instrument` | str | yes | Instrument identifier from protocol or config |
| `devices` | str | no | Device type string |
| `timestamp` | str | yes | ISO-8601 UTC timestamp |
| `peaks` | dict | yes | Peak analysis results |
| `peaks.n_anodic` | int | yes | Number of detected anodic peaks |
| `peaks.anodic_peaks` | list | yes | Array of anodic peak objects |
| `peaks.anodic_peaks[].index` | int | yes | Array index in data |
| `peaks.anodic_peaks[].potential` | float | yes | Peak potential (V) |
| `peaks.anodic_peaks[].current` | float | yes | Peak current (A) |
| `peaks.anodic_peaks[].height` | float | yes | find_peaks height metric |
| `peaks.n_cathodic` | int | yes | Number of detected cathodic peaks |
| `peaks.cathodic_peaks` | list | yes | Array of cathodic peak objects |
| `peaks.cathodic_peaks[].index` | int | yes | Array index in data |
| `peaks.cathodic_peaks[].potential` | float | yes | Peak potential (V) |
| `peaks.cathodic_peaks[].current` | float | yes | Peak current (A) |
| `peaks.cathodic_peaks[].height` | float | yes | find_peaks height metric |
| `peaks.average_peak_separation` | float | no | Mean ΔE_p (V); present if both anodic and cathodic peaks exist |
| `charge` | dict | no | Charge integration results (present only with --charge flag) |
| `charge.total_charge` | float | yes | Integrated charge (C) |
| `charge.anodic_charge` | float | yes | Positive current contribution (C) |
| `charge.cathodic_charge` | float | yes | Negative current contribution, absolute value (C) |
| `charge.unit` | str | yes | Fixed: `"C"` |

### Schema Validation

No dedicated schema validator is currently registered for `ec-cv` (`SCHEMA_VALIDATORS` in `validators.py` returns None). The YAML output is written directly from the analysis dict without structural validation. This means:

- No required-field enforcement
- No type coercion
- Extra fields are silently passed through

---

## Examples

### Basic Analysis

```bash
cd ~/experiments/pedot-pss
sci open -m project pedot-pss
sci ec analyze data/raw/250101_PEDOT_CV_001.txt
```

Expected output:

```
CV Analysis: 250101_PEDOT_CV_001.txt
  Anodic peaks: 1
    E_pa=0.3421V  I_pa=2.15e-5A
  Cathodic peaks: 1
    E_pc=0.2893V  I_pc=-1.98e-5A
  ΔE_p = 0.0528V
```

The ΔE_p ≈ 53 mV suggests a nearly reversible 1e⁻ process.

### Scan Rate Study

```bash
sci ec analyze data/raw/250101_PEDOT_CV_10mVs.txt
sci ec analyze data/raw/250101_PEDOT_CV_50mVs.txt
sci ec analyze data/raw/250101_PEDOT_CV_100mVs.txt
```

Or pick interactively:

```bash
sci ec analyze
```

(fzf opens → select all three with Tab)

### Scan Rate Study — Plot Overlay

```bash
sci plot data/raw/250101_PEDOT_CV_10mVs.txt,data/raw/250101_PEDOT_CV_50mVs.txt,data/raw/250101_PEDOT_CV_100mVs.txt --technique ec-cv
```

Overlay mode → single figure with legend showing all three scan rates.

### Charge Integration for Surface Coverage

```bash
sci ec analyze data/raw/250101_PEDOT_CV_001.txt --charge
```

If Q_anodic = 1.24 × 10⁻⁵ C, n = 1, A = 0.071 cm²:

```
Γ = 1.24 × 10⁻⁵ / (1 × 96485 × 0.071) = 1.81 × 10⁻⁹ mol/cm²
```

### High-Quality Publication Plot

```bash
sci config theme set publication-nature
sci plot data/raw/250101_PEDOT_CV_001.txt --technique ec-cv
```

Saves PDF with Nature journal styling.

### Multi-File with Custom Labels

```bash
sci plot 2105_CV_10mVs.txt,2105_CV_50mVs.txt,2105_CV_100mVs.txt --technique ec-cv
```

When prompted for style options, enter:

```
--color "#1f77b4,#ff7f0e,#2ca02c" --legend "10 mV/s,50 mV/s,100 mV/s"
```

### FZF Interactive Analysis from Project

```bash
sci open -m project my-experiment
sci ec analyze
```

FZF shows all EC files in the project with their protocol→step→filename annotations, 20-line preview, and multi-select support.

### Saving Analysis YAML

```bash
sci analyze --technique ec-cv --yaml data/raw/250101_PEDOT_CV_001.txt
```

Writes to `<step_dir>/results/ec-cv_analysis.yaml` with the full envelope:

```yaml
technique: ec-cv
instrument: autolab-usth
devices: electrochem
timestamp: "2026-06-15T14:30:00Z"
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
      height: 2.89e-05
  average_peak_separation: 0.239
```

### Batch Analysis Across Multiple Files

```bash
for f in data/raw/250101_PEDOT_CV_*.txt; do
    sci ec analyze "$f" --charge
done
```

---

## See Also

- **electrochemistry.md** — Electrochemistry overview: workflow, technique detection, column mapping, all EC techniques
- **chronoamperometry.md** — CA analysis: Cottrell fitting, steady-state current, diffusion coefficient extraction
- **impedance-spectroscopy.md** — EIS analysis: Nyquist/Bode plots, circuit fitting, Kramers-Kronig validation
- **overview.md** — Full technique taxonomy, detection engine, analyzer/plotter dispatch
- **schemas/analysis-yaml.md** — Complete YAML schema reference for all technique analyzers

### Source Files

| File | Description |
|------|-------------|
| `science_cli/library/electrochem/cv.py` | CV analyzer: peak detection, charge integration, scan rate analysis |
| `science_cli/library/electrochem/models.py` | CVData, CAData, EISData dataclasses |
| `science_cli/library/electrochem/__init__.py` | Column maps, analyzer registry, plot presets |
| `science_cli/plot/cv.py` | CV plotting functions: curve, overlay, peaks |
| `science_cli/cli/commands/ec.py` | CLI handler: ec analyze, ec ls, ec info |
| `science_cli/cli/commands/analyze.py` | _analyze_cv(): data loading, column resolution, result printing |
| `science_cli/core/analysis_output.py` | YAML output writer with envelope and optional validation |
