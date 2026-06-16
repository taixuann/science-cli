---
name: sci-uv-vis
description: "UV-Vis spectroscopy analysis — IOP Hanoi spectrometer format, transmission/absorbance modes, peak detection, Tauc bandgap computation (direct/indirect), derivative onset analysis. Load when analyzing UV-Vis absorption or transmission spectra for bandgap determination or optical characterization."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [uv-vis]
---

# sci-uv-vis — UV-Vis Spectroscopy Skill

## Overview

`sci uv-vis` analyzes UV-Vis absorbance and transmission spectroscopy data from IOP Hanoi spectrometers. It supports listing files, inspecting metadata, spectral analysis (peak/valley detection, inflection onset, derivative), and CSV export. Tauc bandgap computation (direct/indirect) is available through the unified `sci analyze` path.

### IOP Hanoi Spectrometer Format

| Property | Value |
|----------|-------|
| Header | 1 line (column names) |
| Delimiter | Comma (`,`) |
| Encoding | latin1 (ISO 8859-1) |
| Decimal | Period (`.`) |
| Columns | Wavelength (nm), T% |
| Instrument config | `iop-hanoi` |

### Transmission vs Absorbance Mode

| Mode | Definition | Typical Range |
|------|-----------|---------------|
| Transmission (T%) | 100 × I/I₀ | 0–100% |
| Absorbance (A) | -log₁₀(T/100) | 0–3+ |
| Reflectance (R%) | 100 × I_reflected/I₀ | 0–100% |

The IOP Hanoi spectrometer outputs transmission mode by default.

### Filename Detection

Files identified by substrings: `_uv-vis`, `_uvvis`, `uv-vis`, `uvvis`, or `_uv` (fallback).

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci uv-vis ls` | List UV-Vis files |
| `sci uv-vis info [<file>...]` | Show header info and data range |
| `sci uv-vis analyze [<file>...] [--name <prefix>]` | Spectral analysis + CSV export |

### Analysis Output

Console output for each file:
```
UV-Vis Analysis: 260526_PDA-ITO_uvvis_01.txt
  Data points: 1001
  Wavelength range: 300.0 nm to 800.0 nm
  Max value: 92.3456 at 550.0 nm
  Min value: 15.2345 at 380.0 nm
  Inflection Point: 420.5 nm (slope=-1.2345e+00)
```

### Analysis CSV Columns

| Column | Description |
|--------|-------------|
| `wavelength(nm)` | Wavelength in nanometers |
| `intensity` | Measured intensity (transmission % or absorbance) |
| `derivative` | First derivative dI/dλ (via numpy.gradient) |

### Plotting

Preferred: `sci plot --technique uv-vis <file> [--xlabel "Wavelength (nm)"] [--ylabel "Transmission (%)"]`

Template defaults: line plot with wavelength (nm) x-axis, transmission (%) y-axis, grid option.

## Analysis Algorithm

1. **Data loading**: `load_data_file(technique="uv-vis")` with `iop-hanoi` device config
2. **Column extraction**: First column = wavelength (nm), second = intensity
3. **NaN filtering**: numpy masking for invalid points
4. **Peak/valley**: `y.argmax()` and `y.argmin()` for positions
5. **Onset/inflection**: `np.gradient(y, x)` → `abs(dy).argmax()` for steepest slope
6. **CSV export**: Wavelength, intensity, derivative to three-column CSV

### Tauc Bandgap Computation (via `--bandgap`)

The Tauc method determines optical bandgap from absorption spectra:

| Type | Plot | n |
|------|------|---|
| Direct allowed | (αhν)² vs hν | 1/2 |
| Indirect allowed | (αhν)^(1/2) vs hν | 2 |

Photon energy: hν (eV) = 1239.84 / λ (nm). Bandgap = x-intercept of linear region in Tauc plot.

## YAML Schema

```yaml
technique: uv-vis-transmission
analysis:
  peaks:
    - wavelength_nm: 420.5
      absorbance: 0.534
    - wavelength_nm: 550.0
      absorbance: 0.213
  bandgap:        # when --bandgap is used
    direct_eV: 3.24
    indirect_eV: 2.87
    method: Tauc
    r_squared: 0.995
```

## AI Agent Usage

### UV-Vis analysis workflow
1. List files: `sci uv-vis ls`
2. Inspect: `sci uv-vis info <file>`
3. Analyze: `sci uv-vis analyze <file> [--name prefix]`
4. For bandgap: use unified `sci analyze --technique uv-vis --bandgap`
5. Plot: `sci plot --technique uv-vis <file> --grid`

### Interpreting results for agents
- **Absorption edge**: Sharp decrease in transmission (or increase in absorbance) at bandgap wavelength
- **Peaks**: Usually broad; prominence threshold is 5% of max intensity
- **Interference fringes**: Periodic oscillations in transmission for thin films with smooth surfaces
- **Inflection point**: Closely related to bandgap; E_g ≈ 1239.84 / λ_onset
- **Urbach tail**: Exponential absorption below bandgap indicates disorder

### Common use cases
- **Thin film bandgap**: Tauc plot with direct gap assumption (most transition metal oxides)
- **Solution concentration**: Beer-Lambert A = εbc at peak absorbance
- **Quantum dots**: Blue-shifted absorption onset relative to bulk
