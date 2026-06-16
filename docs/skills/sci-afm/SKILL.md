---
name: sci-afm
description: "AFM/SPM image analysis — surface roughness (Sa/Sq/Rsk/Rku/Sdr), height distributions, line profiles, power spectral density (PSD), multi-format support (.gwy/.spm/.ibw/.jpk/.stp/.top), Gwyddion interactive bridge for thickness/roughness recording. Load when analyzing topographic AFM images or scanning probe microscopy data."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [afm-gwy, afm-spm, afm-ibw, afm-jpk, afm-stp, afm-top]
---

# sci-afm — AFM/SPM Image Analysis Skill

## Overview

`sci afm` manages and analyzes AFM/SPM image data via the **AFMReader** backend (v0.0.7+). It supports 6 file formats, surface roughness computation (ISO 25178 parameters), height distribution analysis, center cross-section line profiles, 1D power spectral density (PSD), image export (PNG/CSV/NPY), and an interactive Gwyddion bridge for recording measurements.

### Supported Formats

| Format | Extension | Typical Source |
|--------|-----------|----------------|
| Gwyddion | `.gwy` | Gwyddion native format |
| Bruker SPM | `.spm` | Bruker Dimension/Nanoscope |
| Igor Pro | `.ibw` | Asylum Research (Oxford) |
| JPK | `.jpk` | JPK Instruments |
| STP | `.stp` | Various SPM controllers |
| TOP | `.top` | Various SPM controllers |

AFMReader auto-detects format by extension. Install: `pip install AFMReader>=0.0.7`.

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci afm ls` | List AFM files with format detection |
| `sci afm info [<file>...]` | Show metadata, channels, calibration, scan size |
| `sci afm analyze [<file>...] [--psd] [--export <prefix>]` | Surface roughness, height distribution, PSD |
| `sci afm export <file> --format png|csv|npy [--channel <name>]` | Export image data |
| `sci afm open` | Open .ibw in Gwyddion, record analysis |

### Key Flags

| Flag | Subcommand | Description |
|------|-----------|-------------|
| `--psd` | analyze | Include power spectral density |
| `--export <prefix>` | analyze | Export roughness + height + profile CSVs |
| `--channel <name>` | analyze, export | Select specific channel (default: first) |
| `--format png|csv|npy` | export | Export format |
| `--cmap <name>` | export, plot | Colormap: viridis, gray, terrain, plasma, inferno |
| `--dpi <int>` | export, plot | Figure resolution (default: 300) |

## Analysis Details

### Surface Roughness Parameters (ISO 25178)

| Parameter | Symbol | Description |
|-----------|--------|-------------|
| Ra | Sa | Arithmetic mean height deviation (nm) |
| Rq | Sq | Root-mean-square roughness (nm) |
| Rmax | Sz | Maximum peak-to-valley height (nm) |
| Rsk | Ssk | Skewness (asymmetry of height distribution) |
| Rku | Sku | Kurtosis (sharpness of height distribution) |
| Sdr | Sdr | Surface area ratio (%) |

**Interpretation**: Rsk > 0 = peak-dominated surface, Rsk < 0 = valley-dominated. Rku > 3 = spiky surface with extreme features, Rku < 3 = bumpy surface.

### Height Distribution

100-bin histogram reporting modal height, min/max range. Reveals multi-modal surfaces (substrate + film islands) and surface uniformity.

### Line Profiles

Center cross-sections in horizontal and vertical directions via bilinear interpolation. Used for step height measurement, grain profiles, and feature dimensions.

### Power Spectral Density (PSD)

Computed via 2D FFT with Hanning windowing and tilt removal (plane subtraction). Radial averaging produces 1D PSD. Used to extract lateral correlation length and Hurst exponent (roughness scaling).

### Export Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| PNG | Rendered image with colormap | Publication figures |
| CSV | Pixel grid: row, col, height_nm | External analysis |
| NPY | Raw NumPy array (2D) | Python analysis |

### Gwyddion Bridge (afm open)

Interactive workflow: selects `.ibw` file → launches Gwyddion → prompts user for thickness (nm), Sa (nm), Sq (nm), material → saves to `afm_analysis.yaml`. Incremental: existing entries updated, new files appended.

```yaml
files:
  - name: HfO2_5nm.ibw
    thick_nm: 5.2
    sa_nm: 0.345
    sq_nm: 0.432
    material: HfO2
```

## YAML Schema

```yaml
technique: afm
instrument: null
analysis:
  scan_size:
    width_nm: 500.0; height_nm: 500.0; pixel_size_nm: 0.9766
  roughness:
    Ra_nm: 0.3452; Rq_nm: 0.4321; Rmax_nm: 3.2154
    Rsk: -0.1234; Rku: 3.4567; Sdr: 1.2345; n_pixels: 262144
  height_distribution:
    bins: 100; modal_height_nm: 0.1523
  cross_section:
    horizontal: {start_px: [256,0], height_range_nm: [-1.452, 1.234]}
    vertical: {start_px: [0,256], height_range_nm: [-1.321, 1.156]}
  psd:
    frequency_min_nm: 0.0020; frequency_max_nm: 0.5120
```

## AI Agent Usage

### AFM analysis workflow
1. List files: `sci afm ls`
2. Inspect: `sci afm info <file>` — check channels, pixel calibration, scan size
3. Analyze: `sci afm analyze <file> [--psd] [--export prefix]`
4. Export: `sci afm export <file> --format png [--cmap terrain]`
5. For interactive thickness/roughness: `sci afm open` (requires Gwyddion)
6. Plot: `sci plot --technique afm <file>`

### Tips for AI agents
- **Rsk/Rku**: Report these alongside Sa/Sq for complete surface characterization
- **PSD slope**: log-log slope relates to Hurst exponent H (slope = -2-2H for 1D PSD)
- **Crossbar device films**: Expected Sa < 1 nm for smooth bottom electrodes; > 2 nm may indicate roughness-related variability
- **Channel selection**: Always check available channels — Phase channel provides material contrast
- **Spatial calibration**: Verify `pixel_to_nm` is not 1.0 (fallback) — request metadata confirmation
