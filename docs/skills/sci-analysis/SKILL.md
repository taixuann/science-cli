---
name: sci-analysis
description: "Analysis-specific operational knowledge for science-cli v3.11.0 — TECHNIQUE_ANALYZERS registry, per-technique analysis flags, YAML output schemas, IV Vset/Vreset extraction, CV peak detection, CA Cottrell fitting, EIS circuit fitting, Raman preprocessing pipeline, UV-Vis bandgap computation, and AFM roughness analysis. Load when constructing `sci analyze` commands or interpreting analysis output."
version: 3.11.0
author: science-cli team
ontology: [skill, science-cli, analysis, parameter-extraction, yaml, iv, raman, eis, cv, ca, uv-vis, afm]
workspace: tools/science-cli
load: on_request
---

# sci-analysis — science-cli Analysis Skill

## 1. Entry Point

The `sci analyze` command performs parameter extraction and numerical analysis. Unlike `sci plot`, it returns **quantitative results** — switching voltages, peak positions, bandgap energies, circuit fit parameters.

```
sci analyze                        Interactive: fzf file selection, auto-detect technique
sci analyze -t/--technique <type>  Direct: fzf + explicit technique context
sci analyze <file>                 Direct: analyze file with auto-detected technique
```

### Mode Selection for AI Agents

| Scenario | Command |
|----------|---------|
| Select and analyze any file interactively | `sci analyze` |
| Analyze with explicit technique context | `sci analyze -t iv-sweep` |
| Direct file analysis (skip fzf) | `sci analyze <path>` |
| Analysis with YAML output | `sci analyze -t iv-sweep --yaml` |
| Analysis with specific parameters | `sci analyze -t ec-eis --circuit RQR --kk` |

---

## 2. TECHNIQUE_ANALYZERS Registry — 13 Entries

The `TECHNIQUE_ANALYZERS` dict maps technique slugs to analyzer handler functions:

| # | Technique Slug | Analyzer Function | Extracted Parameters |
|---|---------------|-------------------|---------------------|
| 1 | `iv-sweep` | `_analyze_iv` | V_set, V_reset, ON/OFF ratio, compliance flag |
| 2 | `iv-breakdown` | `_analyze_iv` | Same as iv-sweep |
| 3 | `iv-leakage` | `_analyze_iv` | Same as iv-sweep |
| 4 | `pulse-endurance` | `_analyze_pulse_endurance` | ⏳ Stub — use `sci pulse analyze` |
| 5 | `pulse-retention` | `_analyze_pulse_retention` | ⏳ Stub — use `sci pulse analyze` |
| 6 | `pulse-stp` | `_analyze_pulse_stp` | ⏳ Stub — use `sci pulse analyze` |
| 7 | `pulse-ppf` | `_analyze_pulse_ppf` | ⏳ Stub — use `sci pulse analyze` |
| 8 | `ec-cv` | `_analyze_cv` | Anodic/cathodic peaks, ΔE_p, charge |
| 9 | `ec-ca` | `_analyze_ca` | Cottrell slope, steady-state current |
| 10 | `ec-eis` | `_analyze_eis` | Circuit fit params, KK consistency |
| 11 | `raman` | `_analyze_raman` | Peak wavenumbers, intensities |
| 12 | `uv-vis` | `_analyze_uv_vis` | Peaks, inflection point, Tauc bandgap |
| 13 | `afm-gwy` | `_analyze_afm` | ⏳ Stub — use `sci afm analyze` |

### Dispatch Routing

After every successful direct analysis (`analyze.py:213-237`), the handler automatically:
1. Runs sweep metadata extraction — detects sweep segments, directions, sweep rates
2. Updates the protocol YAML with sweep metadata
3. Prints segment summary: `sweep: 2 seg [up, down] @ 0.1 V/s`

**Important:** Pulse (endurance/retention/stp/ppf) and AFM analyzers are **placeholder stubs** that redirect to dedicated subcommands. For those measurements, use:
- `sci pulse analyze --type endurance|retention|stp|ppf`
- `sci afm analyze --psd`

---

## 3. Per-Technique Flags with Validation Rules

### IV Sweep (`-t iv-sweep`, `iv-breakdown`, `iv-leakage`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--yaml` | flag | False | Output analysis results as YAML to `results/` |
| `--vset-only` | flag | False | Volatile mode: extract V_set only, skip V_reset |
| `--compliance` | float | — | Compliance current threshold (A). Flags sweeps exceeding this value. |

**Extracted:** `v_set`, `v_reset` (bipolar), `on_off_ratio`, `switching_detected`

**Code:** Delegates to `science_cli.library.iv.metrics.extract_iv_parameters()`.

### Raman (`-t raman`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--yaml` | flag | False | Output analysis results as YAML |
| `--peaks` | flag | False | Find and report spectral peaks via `scipy.signal.find_peaks` |
| `--baseline` | str | — | Baseline correction: `poly`, `asls`, `airpls` |

**Extracted:** List of `{wavenumber_cm, intensity}` peaks. Up to 10 printed to console; YAML saves all.

**Peak detection:** Uses `find_peaks(prominence=0.1 * max(y))`.

### UV-Vis (`-t uv-vis`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--yaml` | flag | False | Output analysis results as YAML |
| `--bandgap` | flag | False | Compute Tauc bandgap energy (eV) |

**Extracted:** `peaks[{wavelength_nm, absorbance}]`, `bandgap` (eV)

**Peak detection:** `find_peaks(prominence=0.05 * max(y))`.

### EC-CV (`-t ec-cv`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--peaks` | flag | False | Force peak detection output (default behavior) |
| `--charge` | flag | False | Compute anodic and cathodic charge integration |

**Extracted:** `anodic_peaks[{potential, current}]`, `cathodic_peaks[{potential, current}]`, `n_anodic`, `n_cathodic`, `average_peak_separation` (ΔE_p, V), `charge.total_charge` (C), `charge.anodic_charge` (C), `charge.cathodic_charge` (C)

**Code:** Delegates to `science_cli.library.electrochem.cv.peak_analysis()` and `calculate_charge()`.

### EC-CA (`-t ec-ca`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--fit` | flag | True | Perform Cottrell fit on current decay |

**Extracted:** `cottrell.slope` (A·√s), `cottrell.r_squared`, `steady_state.steady_state_current` (A)

**Code:** Delegates to `science_cli.library.electrochem.ca.analyze_ca()`.

### EC-EIS (`-t ec-eis`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--circuit` | str | `RRC` | Equivalent circuit: `RRC`, `RQR`, `RQRW` |
| `--kk` | flag | False | Kramers-Kronig validation test |

**Extracted:** `circuit_fit.circuit`, `circuit_fit.parameter_names`, `circuit_fit.fitted_params`, `circuit_fit.r_squared`, `kk.passes`, `kk.consistency_score`

**Code:** Delegates to `science_cli.library.electrochem.eis.circuit_fit()` and `kramers_kronig()`.

### AFM / Pulse (stubs)

These registrations emit yellow warning text and redirect:
- `sci afm analyze` for AFM surface roughness
- `sci pulse analyze --type endurance|retention|stp|ppf` for pulse measurements

---

## 4. YAML Output System

### Enabling YAML Output

Use `--yaml` flag with any technique that supports it (iv-sweep, raman, uv-vis). For CV/CA/EIS, output is console-only by default.

### YAML Output Location

```
<project>/protocol/<protocol>/<step>/results/<technique>_analysis.yaml
```

### YAML Envelope Structure

```yaml
technique: iv-sweep
timestamp: "2026-06-15T10:30:00.123456"
source_file: "device_cycle_001.csv"
analysis:
  mode: general
  parameters:
    v_set: 1.23
    v_reset: -0.89
    on_off_ratio: 45.6
    switching_detected: true
```

### Technique YAML Slugs Used in Filenames

| Analyzer | Technique Slug |
|----------|---------------|
| `_analyze_iv` | `iv-sweep` |
| `_analyze_cv` | `cv` (no YAML output by default) |
| `_analyze_ca` | `ca` (no YAML output by default) |
| `_analyze_eis` | `eis` (no YAML output by default) |
| `_analyze_raman` | `raman-spectrum` |
| `_analyze_uv_vis` | `uv-vis-transmission` |

### Per-Technique YAML Schemas

**iv-sweep_analysis.yaml:**
```yaml
analysis:
  mode: volatile              # volatile or bipolar
  parameters:
    v_set: 1.23
    v_set_std: 0.045
    v_set_cv: 0.037
    v_reset: -0.89            # bipolar only
    on_off_ratio: 45.2
    compliance: 0.001
    set_yield: 92.5           # volatile only
    hysteresis_area: 0.42     # bipolar only
  n_events: 40
sweep_metadata:
  scan_rate_v_s: 0.5
  segments:
    - direction: forward; sweep_rate_v_s: 0.48
    - direction: reverse; sweep_rate_v_s: 0.52
conduction_fits:
  ohmic:        { model: ohmic,        params: {R_ohm: 1250000}, metrics: {r_squared: 0.992} }
  schottky:     { model: schottky,     params: {schottky_slope: 3.21}, metrics: {r_squared: 0.971} }
  sclc:         { model: sclc,         params: {n_exponent: 1.85}, metrics: {r_squared: 0.988} }
  pool-frenkel: { model: pool-frenkel, params: {pf_slope: 2.78}, metrics: {r_squared: 0.965} }
```

**ec-cv_analysis.yaml:**
```yaml
peaks:
  n_anodic: 1
  anodic_peaks:
    - index: 142; potential: 0.452; current: 3.45e-05
  n_cathodic: 1
  cathodic_peaks:
    - index: 318; potential: 0.213; current: -2.89e-05
  average_peak_separation: 0.239
charge:
  total_charge: 1.24e-05
  anodic_charge: 6.80e-06
  cathodic_charge: 5.60e-06
  unit: C
```

**ec-ca_analysis.yaml:**
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

**ec-eis_analysis.yaml:**
```yaml
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
```

**raman_analysis.yaml:**
```yaml
analysis:
  peaks:
    - wavenumber_cm: 520.7; intensity: 8500.0
    - wavenumber_cm: 1330.0; intensity: 3200.0
  preprocessing:
    - baseline: airpls
    - normalization: vector
```

**uv-vis-transmission_analysis.yaml:**
```yaml
analysis:
  mode: transmission
  peaks:
    - wavelength_nm: 550.0; absorbance: 0.45
  bandgap: 2.85               # eV (with --bandgap flag)
```

---

## 5. IV Analysis: Vset/Vreset Extraction

### Analysis Modes

| Mode | Flag | Description | Device Type |
|------|------|-------------|-------------|
| **Volatile** | `--vset-only` | V_set only (no V_reset) | `memristor` |
| **Bipolar** | (default) | V_set + V_reset | `junction` |

### Library Implementation

- `library/iv/metrics.py` — `detect_vset()`, `detect_vreset()` (derivative-based detection)
- `library/iv/volatile.py` — `analyze_volatile()`: Vset mean/std/CV, set_yield
- `library/iv/bipolar.py` — `analyze_bipolar()`: Vset + Vreset stats, hysteresis area
- `library/iv/analyze.py` — `extract_resistance()`, `extract_breakdown_voltage()`, `fit_iv_curve()` (Ohmic, Schottky, SCLC, Poole-Frenkel), `extract_on_off_ratio()`

### Conduction Models (fitted automatically)

| Model | Key Parameter | Interpretation |
|-------|--------------|----------------|
| Ohmic | R_ohm | Linear I-V (low field) |
| Schottky | schottky_slope | Thermionic emission |
| SCLC | n_exponent | Space-charge-limited (n=2 ideal, n>2 trap-filled) |
| Poole-Frenkel | pf_slope | Field-assisted detrapping |

### Sweep Metadata

After each analysis, the system extracts:
- **Segments**: up/down sweep directions
- **Sweep rate**: V/s for each segment
- Written back to protocol YAML → feeds dashboard

---

## 6. Pulse Analysis (via `sci pulse analyze`)

The main `sci analyze` command has **stubs only** for pulse techniques. Use dedicated subcommands:

```bash
# Endurance cycling — cycles to failure, R_high/R_low drift
sci pulse analyze --type endurance [--file <file>]

# Retention decay — log-time + power-law fit, 10-year extrapolation
sci pulse analyze --type retention [--file <file>]

# STP decay — mono/biexponential fit, AIC selection, tau1/tau2
sci pulse analyze --type stp [--file <file>] [--fit-model biexponential]

# PPF — ratio vs interval, exponential decay fit
sci pulse analyze --type ppf [--file <file>] [--intervals 10,50,100]
```

### Library Parameters

| Type | Key Parameters |
|------|---------------|
| endurance | `cycles_to_failure`, `r_high_initial`, `r_low_initial`, `ratio_tail_mean/std` |
| retention | `decay_rate`, `decay_model` (log/power), `extrapolated_10yr`, `lifetime_hours`, `r_squared` |
| stp | `tau1_ms`, `tau2_ms`, `a1`, `a2`, `r_squared`, `decay_pct` |
| ppf | `facilitation_time_constant_ms`, `a_amplitude`, `ppf_ratio_max/min`, `r_squared` |

---

## 7. EC Analysis: CV, CA, EIS

### CV Peak Detection

- `library/electrochem/cv.py` — `peak_analysis()`:
  - Identifies anodic (positive current) and cathodic (negative current) peaks
  - Computes E_pa (anodic peak potential), E_pc (cathodic peak potential)
  - ΔE_p = |E_pa - E_pc| — smaller = more reversible
  - With `--charge`: `calculate_charge()` integrates area under peaks

### CA Cottrell Fitting

- `library/electrochem/ca.py` — `analyze_ca()`:
  - Cottrell equation: I(t) = nFAC√(D/πt) = slope · 1/√t
  - Fits I vs 1/√t in the decay region
  - Reports slope, intercept, R²
  - Steady-state current from tail of decay

### EIS Circuit Fitting

Six supported circuit models:

| Model | Elements | Parameters |
|-------|----------|------------|
| `RC` | R, C | Simple series |
| `RRC` | Rs, Rct, Cdl | Randles R(RC) |
| `RQR` | Rs, Rct, Q (CPE) | Randles R(RQ) |
| `R_s(C[RW])` | Rs, Cdl, Rct, σ | Randles + Warburg |
| `R_s(Q[RW])` | Rs, Q, Rct, σ | CPE + Warburg |
| `RQRW` | Rs, Rct, Q, W | RQR + Warburg |

- `library/electrochem/eis.py` — `circuit_fit()` fits a specific model; `best_circuit_fit()` compares candidates
- `kramers_kronig()` validates data consistency (pass/fail + score)

---

## 8. Raman Analysis: RamanSPy Pipeline

The `--peaks` and `--baseline` flags access the RamanSPy preprocessing pipeline:

```
Raw spectrum → Denoising → Baseline correction → Normalization → Peak detection
```

For full control, use `sci raman analyze`:

| Flag | Type | Description |
|------|------|-------------|
| `--denoise` | str | `savgol` or `whittaker` |
| `--savgol-window` | int | SavGol window (default: 7) |
| `--savgol-order` | int | SavGol order (default: 3) |
| `--lam` | float | Whittaker smoothness (default: 1e7) |
| `--baseline` | str | `asls`, `iasls`, `airpls`, `arpls`, `iarpls`, `poly`, `modpoly` |
| `--norm` | str | `vector`, `minmax`, `maxintensity`, `auc` |
| `--prominence` | float | Minimum peak prominence |
| `--distance` | float | Minimum peak separation (cm⁻¹) |
| `--height` | float | Minimum peak height |
| `--width` | float | Minimum peak width |
| `--ai` | flag | AI-assisted flag recommendations via sci-raman agent |

**Output files:** `{stem}_peaks.csv`, `{stem}_processed.csv`, `{stem}_report.txt`, `{stem}_analysis.pdf`

**Horiba format:** Tab-delimited, comma decimal, latin1 encoding, 45-line header.

---

## 9. UV-Vis Analysis: Peak Detection and Bandgap

UV-Vis analyzer (`_analyze_uv_vis`, `analyze.py:490-532`) computes:
- Wavelength range (min/max)
- Peak intensity (max) and valley intensity (min) with positions
- Inflection point — wavelength of maximum absolute slope (gradient-based onset)
- Full derivative via `np.gradient`
- With `--bandgap`: Tauc plot bandgap energy (eV)

---

## 10. AFM Analysis (via `sci afm analyze`)

Use `sci afm analyze` instead of `sci analyze -t afm`:

```bash
sci afm analyze [--psd] [--export <prefix>]
```

**Roughness parameters (ISO 25178):**

| Parameter | Description |
|-----------|-------------|
| Sa (Ra) | Arithmetic mean height deviation (nm) |
| Rq (RMS) | Root mean square roughness (nm) |
| Rmax | Maximum height range (nm) |
| Rsk | Skewness of height distribution |
| Rku | Kurtosis of height distribution |
| Sdr | Surface area ratio (%) |

**Supported formats:** `.gwy`, `.spm`, `.ibw`, `.jpk`, `.stp`, `.top`

---

## 11. Manifest.json Output

Every analysis call emits a `manifest.json` to the results directory:

```json
{
  "command": "analyze device_cycle_001.csv",
  "source_files": ["/path/to/device_cycle_001.csv"],
  "output_files": [],
  "technique": "IV",
  "parameters": {
    "peaks": 2,
    "charge": false
  },
  "project": "my-project",
  "timestamp": "2026-06-15T10:30:00"
}
```

---

## 12. Analysis Column Resolution

| Analyzer | X/Y Columns |
|----------|------------|
| IV sweep | Voltage: `Voltage (V)`, `V`, `BV`, `bias_voltage` / Current: `Current (A)`, `I`, `I/A`, `Bi` |
| EC-CV | Potential: `WE(1).Potential (V)`, `E`, `E/V` / Current: `WE(1).Current (A)`, `I`, `I/A` |
| EC-CA | Time: `Corrected time (s)`, `time`, `t/s` / Current: `WE(1).Current (A)`, `I`, `<I>/A` |
| EC-EIS | Freq: `frequency`, `Frequency (Hz)` / Z': `z_real`, `Z' (Ω)` / Z'': `z_imag`, `-Z'' (Ω)` |
| Raman | Column 0 = shift (cm⁻¹), Column 1 = intensity |
| UV-Vis | Column 0 = wavelength (nm), Column 1 = absorbance/transmittance |

---

## 13. Flag Validation

`_validate_analyze_flags()` (`analyze.py:555-575`):
- If no technique specified: unknown flags silently ignored
- Builds allowed set from `ANALYZE_TECHNIQUE_FLAGS`
- Cross-technique flag warnings in yellow (non-blocking)

### Allowed Flag Mapping

| `--technique` | Allowed Flags |
|---------------|---------------|
| `iv-sweep` | `--yaml`, `--vset-only`, `--compliance` |
| `raman` | `--yaml`, `--peaks`, `--baseline` |
| `uv-vis` | `--yaml`, `--bandgap` |
| `ec-cv` | `--peaks`, `--charge` |
| `ec-ca` | `--fit` |
| `ec-eis` | `--circuit`, `--kk` |

---

## 14. Constructing `sci analyze` Commands for AI Agents

### Template

```bash
sci analyze -t <technique> {<file>} {--technique-flags}
```

### Best Practices
1. Always use `-t <technique>` for explicit context (avoids auto-detection errors)
2. Add `--yaml` for reproducible, machine-readable output
3. Use `--vset-only` for volatile memristors (no reset)
4. Use `--compliance` to flag compliance-limited sweeps
5. For EC multi-technique projects: analyze CV → CA → EIS sequentially
6. For pulse/AFM analysis: redirect to dedicated subcommands
7. After analysis, check `sweep:` console output to verify metadata extraction
