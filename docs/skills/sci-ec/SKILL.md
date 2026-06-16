---
name: sci-ec
description: "Electrochemistry analysis for CV/CA/EIS — cyclic voltammetry peak detection and charge integration, chronoamperometry Cottrell fitting, electrochemical impedance spectroscopy equivalent circuit fitting (RRC/RQR/RQRW/Randles) and Kramers-Kronig validation. Load when analyzing electrochemical data from potentiostat measurements."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [ec-cv, ec-ca, ec-eis, ec-lsv, ec-swv]
---

# sci-ec — Electrochemistry Skill

## Overview

`sci ec` provides specialized handling for 5 electrochemical techniques: cyclic voltammetry (CV), chronoamperometry (CA), electrochemical impedance spectroscopy (EIS), linear sweep voltammetry (LSV), and square wave voltammetry (SWV). Full analysis is supported for CV (peak detection + charge integration), CA (Cottrell fitting), and EIS (equivalent circuit fitting + KK validation). All subcommands use automatic technique detection from filenames.

### EC Technique Taxonomy

| Technique | Detection Patterns | Analysis |
|-----------|-------------------|----------|
| `ec-cv` | `_CV.`, `.cv`, `cv_`, `cv-` | Peak detection, charge integration, scan rate analysis |
| `ec-ca` | `_CA.`, `.ca`, `ca_`, `ca-` | Cottrell fit, steady-state current |
| `ec-eis` | `.mpt`, `_EIS.`, `.eis`, `.z` | Circuit fitting, KK test |
| `ec-lsv` | `_LSV.`, `.lsv` | (stub — CV analysis compatible) |
| `ec-swv` | `_SWV.`, `.swv` | (stub) |

### Biologic MPT Format

EC files from Biologic potentiostats use `.mpt` format: semicolon delimiter, UTF-8 encoding. Key columns: `WE(1).Potential (V)`, `WE(1).Current (A)`, `Corrected time (s)`, `Frequency (Hz)`, `Z' (Ω)`, `-Z'' (Ω)`.

The `autolab-usth` device config handles column remapping automatically. Column aliases resolve via `ColumnMap` — compatible with various potentiostat output formats.

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci ec ls` | List EC files with auto technique detection |
| `sci ec info [<file>...]` | Show columns, shape, value range |
| `sci ec analyze [<file>...] [flags]` | Run technique-specific analysis |

### Analysis Flags

| Flag | Techniques | Description |
|------|-----------|-------------|
| `--peaks` | ec-cv | Find redox peaks (anodic + cathodic) |
| `--charge` | ec-cv | Integrate total/anodic/cathodic charge |
| `--fit` | ec-ca | Fit CA decay to Cottrell equation |
| `--circuit <model>` | ec-eis | EIS equivalent circuit: RRC, RQR, RQRW, RC, Randles |
| `--kk` | ec-eis | Kramers-Kronig validation test |

## Analysis Details

### CV — Peak Finding & Charge Integration

**Peak detection** (`scipy.signal.find_peaks`): Anodic peaks from positive current maxima (forward scan), cathodic from inverted negative minima (reverse scan). Returns per-peak: index, potential (V), current (A), height, and average peak separation (ΔEp in V).

**Charge integration** (`numpy.trapezoid`): Q = ∫ I(V) dV / scan_rate, split into anodic and cathodic components.

**Scan rate analysis**: Fits peak current vs scan rate for linear (surface-confined: i_p ∝ v) and square-root (diffusion: i_p ∝ √v, Randles-Sevcik) models.

| Parameter | Description |
|-----------|-------------|
| E_pa | Anodic peak potential (V) |
| E_pc | Cathodic peak potential (V) |
| ΔE_p | Peak separation (V) |
| I_pa/I_pc | Peak current ratio |
| Q_total, Q_anodic, Q_cathodic | Charge (C) |

### CA — Cottrell Fit

**Model** (via `lmfit`): i(t) = slope/√t + intercept

| Parameter | Description |
|-----------|-------------|
| slope | Cottrell slope (A·√s) |
| intercept | Residual/background current |
| r_squared | Goodness of fit |
| steady_state_current | Mean of last 20% of transient |

### EIS — Circuit Fitting

**Equivalent circuits** (via `lmfit`):

| Circuit | Elements | Description |
|---------|----------|-------------|
| RC | R, C | Series RC |
| RRC | Rs, Rct, Cdl | Randles (R(RC)) |
| RQR | Rs, Rct, Q | Randles with CPE |
| Randles | Rs, Rct, Q | Alias for RQR |
| R_s(C[RW]) | Rs, Cdl, Rct, σ | + Warburg |
| R_s(Q[RW]) | Rs, Q, Rct, σ | CPE + Warburg |

**Kramers-Kronig test**: Validates data consistency via Voigt circuit (N log-spaced RC elements). Passes if mean relative residual < 5%.

## YAML Schema

### CV — `ec-cv_analysis.yaml`
```yaml
technique: ec-cv
peaks:
  n_anodic: 1
  anodic_peaks:
    - potential: 0.452; current: 3.45e-05
  n_cathodic: 1
  average_peak_separation: 0.239
charge:
  total_charge: 1.24e-05; unit: C
```

### CA — `ec-ca_analysis.yaml`
```yaml
technique: ec-ca
cottrell:
  slope: 2.34e-04; r_squared: 0.998
steady_state:
  steady_state_current: 1.23e-06
```

### EIS — `ec-eis_analysis.yaml`
```yaml
technique: ec-eis
circuit_fit:
  circuit: RRC
  parameter_names: [Rs, Rct, Cdl]
  fitted_params: [120.3, 4520.1, 3.21e-06]
  r_squared: 0.994
kk:
  passes: true
  consistency_score: 2.1
```

## AI Agent Usage

### EC analysis workflow
1. List files: `sci ec ls`
2. Inspect: `sci ec info <file>` — confirms auto-detected technique
3. Run analysis:
   - CV: `sci ec analyze <file> --peaks [--charge]`
   - CA: `sci ec analyze <file> --fit`
   - EIS: `sci ec analyze <file> --circuit RQR [--kk]`
4. Interpret:
   - CV: ΔE_p near 59 mV/n = reversible; I_pa/I_pc ≈ 1 = no side reactions
   - CA: R² > 0.99 = clean diffusion-limited behavior
   - EIS: Nyquist semicircle diameter = Rct; CPE n near 1 = ideal capacitor
5. KK test failing (< 5%): check for cable inductance, non-stationary sample, or saturation

### EIS circuit selection heuristic
- Single semicircle: RRC (simple Randles)
- Depressed semicircle: RQR (CPE accounts for electrode roughness)
- 45° tail at low frequency: add Warburg (R_s(C[RW]) or R_s(Q[RW]))
- Double semicircle: two time constants (not directly supported — use multi-RC manually)
