# Raman Spectroscopy

## Overview

Raman spectroscopy is a vibrational spectroscopic technique based on inelastic scattering of monochromatic light. When photons interact with molecular bonds, most scatter elastically (Rayleigh scattering — no energy change), but a small fraction (~1 in 10⁷) scatter inelastically, exchanging energy with molecular vibrations. This inelastic scattering is the **Raman effect**.

### Stokes and Anti-Stokes Scattering

The energy shift between incident and scattered photons corresponds to vibrational energy levels of the sample:

- **Stokes scattering**: Photon loses energy to the molecule (excites a vibrational mode). The scattered photon has lower energy (longer wavelength) than the incident light. Stokes lines appear at positive Raman shift (cm⁻¹) and are the dominant signal in spontaneous Raman at room temperature because most molecules start in the ground vibrational state.

- **Anti-Stokes scattering**: Molecule already in an excited vibrational state transfers energy to the photon. The scattered photon has higher energy (shorter wavelength) than the incident light. Anti-Stokes lines are weaker at room temperature but grow stronger with increasing temperature.

Raman shift (expressed in wavenumbers, cm⁻¹) is independent of the excitation wavelength:

$$\Delta\tilde{\nu} = \left(\frac{1}{\lambda_0} - \frac{1}{\lambda_1}\right) \times 10^7$$

where λ₀ and λ₁ are incident and scattered wavelengths in nm.

### What Raman Reveals

| Information | Physical Origin |
|------------|----------------|
| Vibrational modes | Characteristic bond stretching, bending, and torsion frequencies |
| Material identification | Fingerprint region (200-2000 cm⁻¹) uniquely identifies molecular species |
| Crystallinity | Sharp, narrow peaks for crystalline phases; broad features for amorphous |
| Stress/strain | Peak shifts under mechanical stress (piezospectroscopy effect) |
| Crystal orientation | Polarized Raman measurements reveal symmetry-dependent selection rules |
| Phase identification | Different polymorphs (e.g., anatase vs. rutile TiO₂) have distinct spectra |
| Doping/defect levels | Changes in peak ratios (e.g., D/G band ratio in carbon materials) |
| Temperature | Stokes/anti-Stokes intensity ratio yields local temperature via Boltzmann distribution |

### Raman Spectral Regions

| Region | Range (cm⁻¹) | Information Content |
|--------|-------------|-------------------|
| Lattice phonon | 10-200 | Crystal lattice vibrations, acoustic modes |
| Fingerprint | 200-1800 | Highly specific molecular bending, stretching, ring modes |
| Silent region | 1800-2500 | Few fundamental vibrations; useful for isotopic labels |
| X-H stretching | 2500-4000 | O-H, N-H, C-H stretching vibrations |

### Surface-Enhanced Raman Spectroscopy (SERS)

SERS amplifies the inherently weak Raman signal by 10⁶-10¹⁰× through two mechanisms:

1. **Electromagnetic enhancement**: Localized surface plasmon resonance (LSPR) in metallic nanostructures (Au, Ag, Cu) concentrates the electromagnetic field at the surface, amplifying both incident and scattered light.

2. **Chemical enhancement**: Charge transfer between adsorbed molecules and the metal surface increases the effective Raman cross-section.

SERS requires:
- Roughened metal surfaces or colloidal nanoparticles (typically Ag or Au, 20-100 nm)
- Close proximity (<5 nm) between analyte and metal surface
- Excitation wavelength matching the LSPR of the nanostructure

In science-cli, SERS files are identified by the `_sers_` filename infix and are listed in a separate table section by `sci raman ls`.

---

## Horiba LabRAM HR Evolution Format

science-cli reads Raman data from Horiba LabRAM HR Evolution instruments. The file format is:

- **Header**: 45 lines prefixed with `#` containing metadata fields
- **Data**: Tab-delimited, two columns — Raman shift (cm⁻¹) and Intensity (counts)
- **Decimal separator**: Comma (`,`) — European convention for decimal numbers
- **Encoding**: latin1 (ISO 8859-1)
- **Line endings**: Standard newline

### Header Structure

The 45-line header uses `# fieldname = value` syntax. Fields are separated by `#` markers at fixed lines representing spectrometer subsystems:

```
# HEADER
# Instrument = ...
# Detector = ...
# Laser = ...
# Grating = ...
...
# DATA
# Range =  ...
# full_time = ...
# acq_time_s = ...
# accumulations = ...
# detector_temperature_c = ...
# detector_gain = ...
# detector_adc = ...
...
# SITE
# x (um) = ...
# y (um) = ...
# z (um) = ...
# site = ...
# title = ...
# sample = ...
# remark = ...
# date = ...
# acquired = ...
...
# ACQUISITION
# autoexposure = ...
# autofocus = ...
# autoscann = ...
# spike_filter = ...
# delay_time_s = ...
# binning = ...
# readout_mode = ...
# denoise = ...
# ics_correction = ...
# dark_correction = ...
# inst_process = ...
...
# STAGE
# stagexy = ...
# stagez = ...
# ultght = ...
# PROJECT
# project = ...
```

### Extracted Metadata Fields (30+)

The `extract_raman_metadata()` function in `science_cli.core.data_loader` normalizes all header fields to snake_case keys:

| Key | Example Value | Description |
|-----|--------------|-------------|
| `instrument` | `LabRAM HR Evolution` | Spectrometer model |
| `detector` | `Synapse` | CCD/CMOS detector model |
| `laser` | `532 nm` | Excitation wavelength |
| `grating` | `1800 gr/mm` | Diffraction grating groove density |
| `objective` | `100x` | Microscope objective magnification |
| `nd_filter` | `10%` | Neutral density filter transmission |
| `hole` | `100` | Confocal hole diameter (µm) |
| `range` | `500-3200 cm⁻¹` | Spectral acquisition range |
| `full_time` | `60.0` | Total acquisition time (s) |
| `acq_time_s` | `10.0` | Single acquisition time (s) |
| `accumulations` | `6` | Number of accumulated spectra |
| `detector_temperature_c` | `-70.0` | Detector cooling temperature (°C) |
| `detector_gain` | `1` | Detector gain setting |
| `detector_adc` | `1 MHz` | Analog-to-digital converter rate |
| `x_m` | `1234.5` | Stage X position (µm) |
| `y_m` | `567.8` | Stage Y position (µm) |
| `z_m` | `10000.0` | Stage Z position (µm) |
| `site` | `Center` | Measurement site label |
| `title` | `Sample_A_1` | Acquisition title |
| `sample` | `HfO2_10nm` | Sample identifier |
| `remark` | `Fresh device` | Operator remark |
| `date` | `2024-01-15` | Acquisition date |
| `acquired` | `14:30:00` | Acquisition time |
| `autoexposure` | `Off` | Auto-exposure status |
| `autofocus` | `On` | Autofocus status |
| `autoscann` | `Off` | Auto-scanning status |
| `spike_filter` | `Off` | Cosmic ray spike filter |
| `delay_time_s` | `0.0` | Pre-acquisition delay (s) |
| `binning` | `1x1` | CCD pixel binning |
| `readout_mode` | `Standard` | CCD readout mode |
| `denoise` | `Off` | Hardware denoising |
| `ics_correction` | `Off` | Intra-scanner correction |
| `dark_correction` | `On` | Dark current subtraction |
| `inst_process` | `None` | Instrument processing |
| `stagexy` | `Motorized` | XY stage type |
| `stagez` | `Piezo` | Z stage type |
| `ultght` | `Off` | Ultra-light source status |
| `project` | `HfOx_project` | Project name |

### Data Columns

After the 45-line header, the file contains tab-delimited spectral data:

```
Raman Shift (cm-1)	Intensity (counts)
500,0	1234,5
501,5	1256,3
...
```

Note the European comma decimal separator and tab delimiter. The `horiba-usth` device configuration handles this automatically: `delimiter="\t"`, `decimal=","`, `encoding="latin1"`, `header_lines=45`.

### Filename-Based Technique Detection

Raman files are identified by containing any of these infixes (case-insensitive):
- `_raman_`
- `_sers_` (SERS files, listed separately)
- `_raman-sers_`

This is defined in `science_cli.core.technique.PATTERNS["raman"]` at `src/science_cli/core/technique.py:81`.

---

## CLI Commands

### `sci raman ls [--step <name>]`

List Raman and SERS files with an 8-column metadata table:

```
sci raman ls
sci raman ls --step deposition_01
```

Produces two separate Rich tables — one for Raman files, one for SERS files — each with:

| Column | Description | Source |
|--------|-------------|--------|
| File | Filename | Filesystem |
| Size | Formatted file size (KB/B) | `stat().st_size` |
| Accum | Accumulation count | `meta["accumulations"]` |
| Acq. Time (s) | Acquisition time per spectrum | `meta["acq_time_s"]` |
| ND Filter | Neutral density filter value | `meta["nd_filter"]` |
| Laser | Laser wavelength | `meta["laser"]` |
| Grating | Grating groove density | `meta["grating"]` |
| Range | Spectral range (min-max cm⁻¹) | Computed from data columns |

When `--step <name>` is provided, files are listed from the named protocol step directory instead of the project `data/raw` directory.

### `sci raman info [file...]`

Display the complete 30+ field metadata table for one or more Raman files:

```
sci raman info
sci raman info my_sample_raman.txt
sci raman info file1_raman.txt file2_sers.txt
```

Without a filename argument, launches an interactive **fzf** picker with metadata preview tags showing laser, ND filter, acquisition time, accumulations, and spectral range:

```
[     532 nm][  10%][10.0s][  6x][ 500-3200 cm⁻¹] my_sample_raman.txt
```

Multiple files can be selected for batch inspection. Each file gets its own metadata table with all 38 fields.

### `sci raman analyze [--ai] [--denoise] [--baseline] [--norm] [--prominence] [--plot] [--overlay] [--all]`

**Deprecated in favor of `sci analyze --technique raman`** but still functional.

Run the full RamanSPy preprocessing pipeline. See the Preprocessing Pipeline section below for complete details.

#### Flags

| Flag | Type | Description |
|------|------|-------------|
| `--denoise` | `savgol\|whittaker` | Denoising method |
| `--savgol-window` | int (odd) | SavGol window length (default 7) |
| `--savgol-order` | int | SavGol polynomial order (default 3) |
| `--baseline` | `asls\|airpls\|arpls\|poly\|modpoly\|iasls\|iarpls` | Baseline correction method |
| `--lam` | float | Regularization parameter for baseline/Whittaker |
| `--norm` | `vector\|minmax\|maxintensity\|auc` | Normalization method |
| `--prominence` | float | Minimum peak prominence (default: 15% of max intensity) |
| `--distance` | int | Minimum horizontal distance between peaks (cm⁻¹) |
| `--height` | float | Minimum peak height |
| `--width` | float | Minimum peak width |
| `--plot` | flag | Generate enhanced analysis PDF |
| `--overlay` | flag | Overlay multiple processed spectra |
| `--all` | flag | Generate individual plots for each file |
| `--ai` | flag | Use AI agent for smart flag recommendation |

### `sci plot --technique raman [file] [--laser] [--accumulation] [--acq-time] [--nd-filter]`

Unified plotting interface for Raman spectra. This is the preferred plotting method (supersedes `sci raman plot`).

```
sci plot --technique raman my_sample_raman.txt
sci plot --technique raman --xlabel "Raman shift (cm⁻¹)" --ylabel "Intensity (counts)" --grid
```

Supports overlay mode for multiple files, interactive fzf file selection, and theme-aware default styling. The Raman template provides defaults for labels, colors, and figure dimensions.

#### Plot Flags

| Flag | Description |
|------|-------------|
| `--name` / `-n` | Output filename (default: `raman_{stem}.pdf`) |
| `--xlabel` | X-axis label |
| `--ylabel` | Y-axis label |
| `--title` | Plot title |
| `--color` | Line color |
| `--linewidth` | Line width |
| `--linestyle` | Line style |
| `--grid` | Show grid |
| `--dpi` | Image resolution (default 300) |
| `--xlim` / `--zoom` | X-axis range, comma-separated (e.g., `500,1800`) |
| `--ylim` | Y-axis range |

#### Single Plot

With one file (or one selected via fzf), generates a single Raman spectrum plot:

```
sci plot --technique raman sample_raman.txt
```

#### Overlay Mode

With multiple files, prompts for overlay vs. individual plots:

```
sci plot --technique raman
# Interactive: select multiple files via fzf, then choose overlay (o) or individual (i)
```

Or programmatically:

```
sci plot --technique raman file1_raman.txt file2_raman.txt
# Prompts: Overlay all (o) or individual plots (i)?
```

#### File Name Enforcement

The plot command validates that filenames contain `_raman_`, `_sers_`, or `_raman-sers_`. Files that don't match any Raman pattern are rejected:

```
sci plot --technique raman not_a_raman.txt
# Error: File 'not_a_raman.txt' is not identified as Raman.
```

---

## Preprocessing Pipeline

The analysis pipeline is implemented in `_raman_analyze()` at `src/science_cli/cli/commands/raman.py:983`. It uses the **RamanSPy** library for spectral preprocessing and **SciPy** for peak detection.

The pipeline processes data as an `rp.Spectrum` object, chaining operations sequentially:

```
Raw intensity → Denoising → Baseline correction → Normalization → Peak detection
```

### Pipeline Control Flow

```
_raman_analyze(filepath, flags)
  |
  ├── _resolve_file(filepath)       → Resolve file path (project-aware)
  ├── _spectrum_from_file(resolved) → Load (shift, intensity) arrays
  ├── rp.Spectrum(intensity, spectral_axis=shift)  → Create RamanSPy spectrum
  │
  ├── 1. Denoising (optional)
  │     ├── savgol → rp.preprocessing.denoise.SavGol(window_length, polyorder)
  │     └── whittaker → rp.preprocessing.denoise.Whittaker(lam)
  │
  ├── 2. Baseline Correction (optional)
  │     ├── asls    → rp.preprocessing.baseline.ASLS(lam, p)
  │     ├── iasls   → rp.preprocessing.baseline.IASLS(lam, p)
  │     ├── airpls  → rp.preprocessing.baseline.AIRPLS(lam)
  │     ├── arpls   → rp.preprocessing.baseline.ARPLS(lam)
  │     ├── iarpls  → rp.preprocessing.baseline.IARPLS(lam)
  │     ├── poly    → rp.preprocessing.baseline.Poly()
  │     └── modpoly → rp.preprocessing.baseline.ModPoly()
  │
  ├── 3. Normalization (optional)
  │     ├── vector       → rp.preprocessing.normalise.Vector()
  │     ├── minmax       → rp.preprocessing.normalise.MinMax()
  │     ├── maxintensity → rp.preprocessing.normalise.MaxIntensity()
  │     └── auc          → rp.preprocessing.normalise.AUC()
  │
  ├── 4. Peak Detection
  │     └── spec.peaks(prominence=..., distance=..., height=..., width=...)
  │         └── scipy.signal.peak_widths(spec.spectral_data, peaks, rel_height=0.5)
  │
  ├── 5. CSV Export
  │     ├── {prefix}_peaks.csv (peak center, intensity, prominence, FWHM)
  │     └── {prefix}_processed.csv (corrected/normalized spectrum)
  │
  ├── 6. Text Report
  │     └── {prefix}_report.txt (metadata, pipeline config, peak table, summary)
  │
  └── 7. Enhanced Plot (if --plot)
        └── {prefix}_analysis.pdf (4 traces: raw, baseline, corrected, peaks)
```

### 1. Denoising

Raman spectra inherently contain shot noise from the photon detection process and read noise from the CCD. Two denoising methods are available:

#### Savitzky-Golay Filter

A convolutional smoothing filter that fits successive windows of data to a polynomial by least squares. Preserves peak position and width better than simple moving average.

```python
import ramanspy as rp
step = rp.preprocessing.denoise.SavGol(window_length=9, polyorder=3)
applied = step.apply(applied)
```

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| window_length | `--savgol-window` | 7 | Odd integer, number of points in the smoothing window. Larger values = smoother spectra, but risk distorting narrow peaks. |
| polyorder | `--savgol-order` | 3 | Polynomial order for the least-squares fit. Must be < window_length. Higher values follow fine structure more closely. |

Rules of thumb:
- window_length should be roughly 2-3× the FWHM of the narrowest peak (in data points)
- polyorder = 2 or 3 is typically sufficient for Raman spectra
- For noisy spectra: increase window_length first, then polyorder if needed

#### Whittaker Smoother

A penalized least-squares smoother based on Eilers (2003). Minimizes:

$$Q = \sum_i (y_i - z_i)^2 + \lambda \sum_i (\Delta^2 z_i)^2$$

where the first term penalizes residuals and the second term penalizes roughness (second differences). λ controls the trade-off.

```python
step = rp.preprocessing.denoise.Whittaker(lam=1e5)
applied = step.apply(applied)
```

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| λ (lambda) | `--lam` | 1e5 | Regularization parameter. Higher λ = smoother result. Range: 1e2 (weak) to 1e9 (very strong). |

The Whittaker smoother is especially effective for baseline-dominated regions where adaptive smoothing is preferred over fixed-window methods.

### 2. Baseline Correction

Raman spectra typically sit on a broad fluorescence background that must be removed before quantitative analysis. RamanSPy provides seven baseline correction algorithms, all accessible through `rp.preprocessing.baseline`:

#### ASLS (Asymmetric Least Squares)

Introduced by Eilers and Boelens (2005). Minimizes a weighted penalized least-squares function with asymmetric weighting that penalizes negative residuals more heavily than positive ones, allowing the baseline to follow the lower envelope of the spectrum.

```python
step = rp.preprocessing.baseline.ASLS(lam=1e7, p=0.01)
applied = step.apply(applied)
```

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| λ (lam) | `--lam` | 1e7 | Smoothness parameter. Higher λ = smoother baseline. |
| p | `--p` | 0.01 | Asymmetry parameter. Lower p = more aggressive baseline (follows lower envelope). Typical range: 0.001-0.1. |

#### IASLS (Improved Asymmetric Least Squares)

An iterative variant of ASLS that alternates between baseline estimation and smoothing parameter updates, providing more robust convergence for spectra with varying baseline curvature.

```python
step = rp.preprocessing.baseline.IASLS(lam=1e7, p=0.01)
```

Same parameters as ASLS. More stable for spectra with strong, broad Raman bands.

#### AIRPLS (Adaptive Iteratively Reweighted Penalized Least Squares)

Zhang et al. (2010). An iterative algorithm that adaptively updates weights based on the residuals from the previous iteration, using a sigmoid function to assign lower weights to positive residuals (peaks) and higher weights to negative residuals (baseline).

```python
step = rp.preprocessing.baseline.AIRPLS(lam=1e7)
```

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| λ (lam) | `--lam` | 1e7 | Smoothness parameter. Default in baseline context is 1e7 (vs 1e5 for Whittaker denoising). |

AIRPLS is generally robust and recommended as a first-choice baseline correction for most Raman spectra.

#### ARPLS (Asymmetrically Reweighted Penalized Least Squares)

An alternative reweighting scheme that uses a different weighting function than AIRPLS, often converging in fewer iterations.

```python
step = rp.preprocessing.baseline.ARPLS(lam=1e7)
```

#### IARPLS (Improved Asymmetrically Reweighted Penalized Least Squares)

A further refinement of the ARPLS approach with improved convergence properties.

```python
step = rp.preprocessing.baseline.IARPLS(lam=1e7)
```

#### Poly (Polynomial Baseline)

Fits a polynomial of specified order to the spectrum to estimate the baseline. Simpler than adaptive methods but effective when the baseline shape is known to be polynomial.

```python
step = rp.preprocessing.baseline.Poly()
```

No additional parameters. Uses a default polynomial order suitable for typical Raman baselines.

#### ModPoly (Modified Polynomial Baseline)

An iterative modification of polynomial fitting that progressively excludes peak regions from the fit, yielding a baseline that follows the lower envelope.

```python
step = rp.preprocessing.baseline.ModPoly()
```

#### Baseline Method Comparison

| Method | Type | Strength | Best For |
|--------|------|----------|----------|
| ASLS | Asymmetric weighting | Simple, well-understood | Flat/linear baselines with isolated peaks |
| IASLS | Iterative ASLS | More robust convergence | Spectra with broad overlapping bands |
| AIRPLS | Adaptive weights | Versatile, generally robust | Recommended first choice |
| ARPLS | Alternative reweighting | Fast convergence | Moderate baseline curvature |
| IARPLS | Improved ARPLS | Most stable | Noisy spectra with complex baselines |
| Poly | Polynomial regression | Simple, no parameters | Known polynomial baseline shapes |
| ModPoly | Iterative polynomial | Excludes peak regions | Baselines with sparse peaks |

### 3. Normalization

Normalization removes absolute intensity variation between spectra, enabling comparison of spectral shape across measurements.

#### Vector (L2 Normalization)

Divides the spectrum by its Euclidean norm (L2 norm):

$$I_{\text{norm}} = \frac{I}{\sqrt{\sum_i I_i^2}}$$

```python
step = rp.preprocessing.normalise.Vector()
```

Best for: Comparing spectral shape between spectra with different overall intensities (e.g., different laser powers, acquisition times).

#### MinMax

Scales the spectrum linearly to the range [0, 1]:

$$I_{\text{norm}} = \frac{I - I_{\text{min}}}{I_{\text{max}} - I_{\text{min}}}$$

```python
step = rp.preprocessing.normalise.MinMax()
```

Best for: Display and visual comparison where relative peak ratios matter.

#### MaxIntensity

Divides the spectrum by its maximum intensity, scaling the highest peak to 1:

$$I_{\text{norm}} = \frac{I}{I_{\text{max}}}$$

```python
step = rp.preprocessing.normalise.MaxIntensity()
```

Best for: Comparing relative peak ratios within the fingerprint region.

#### AUC (Area Under Curve)

Divides the spectrum by the integrated area (trapezoidal sum):

$$I_{\text{norm}} = \frac{I}{\sum_i I_i \cdot \Delta \tilde{\nu}}$$

```python
step = rp.preprocessing.normalise.AUC()
```

Best for: Spectra where total integrated intensity should be normalized (e.g., temperature-dependent measurements, or comparing spectra with different spectral ranges).

### 4. Peak Detection

Peak detection uses `scipy.signal.find_peaks` via the RamanSPy `.peaks()` method. After preprocessing, the spectrum is searched for local maxima that satisfy the specified constraints.

```python
peaks, props = spec.peaks(
    prominence=prominence,
    distance=distance,
    height=height,
    width=width,
)
```

#### `scipy.signal.find_peaks` Parameters

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| **prominence** | `--prominence` | 15% of max intensity | Minimum peak prominence (vertical distance between peak and its lowest contour line). Auto-computed as `max(0.15 * max_intensity, 1.0)` if not specified. This is the most important parameter for filtering noise. |
| **distance** | `--distance` | None | Minimum horizontal distance (in cm⁻¹) between neighboring peaks. Prevents double-counting broad peaks or detecting shoulder artifacts. |
| **height** | `--height` | None | Minimum peak height in intensity units. Filters out low-intensity features regardless of their prominence. |
| **width** | `--width` | None | Minimum peak width (in cm⁻¹) at half maximum. Filters out very narrow features (typically cosmic ray spikes). |

#### FWHM Calculation

After peak detection, full width at half maximum (FWHM) is computed using `scipy.signal.peak_widths` with `rel_height=0.5`:

```python
widths_result = peak_widths(spec.spectral_data, peaks, rel_height=0.5)
left_ips = widths_result[2]
right_ips = widths_result[3]
fwhms = spec.spectral_axis[round(right_ips)] - spec.spectral_axis[round(left_ips)]
```

The half-height intersections are interpolated and then converted from index space to wavenumber space using the spectral axis. FWHM values are reported in cm⁻¹.

#### Peak Output

Detected peaks are displayed in a Rich table and exported to CSV:

| Column | Description |
|--------|-------------|
| # | Peak index (1-based, sorted by shift position) |
| Shift (cm⁻¹) | Raman shift at peak maximum |
| Intensity (counts/a.u.) | Peak height (counts for raw, arbitrary units after normalization) |
| Prominence | Vertical prominence in intensity units |
| FWHM (cm⁻¹) | Full width at half maximum |

If no peaks are detected, a warning is displayed suggesting a lower prominence value:

```
No peaks found with prominence=15000.0. Try --prominence <lower>
```

---

## AI Mode (`--ai`)

The `--ai` flag delegates flag recommendations to the **sci-raman** opencode agent, which inspects spectral metadata and suggests preprocessing parameters automatically.

### Workflow

1. `_raman_analyze_ai()` collects spectral summaries (laser, ND filter, acquisition time, accumulations, data points, max intensity) for each file
2. Serializes the summaries as JSON to a temporary file
3. Calls opencode with the `--agent sci-raman` flag:
   ```bash
   opencode run --agent sci-raman --dir <sci_dir> -m opencode-go/mimo-v2.5-pro --format json \
     "Recommend preprocessing flags..." --file <tmp.json>
   ```
4. Parses the JSON response for the `flags` dictionary and optional `reasoning` object
5. Normalizes flag names via `_normalize_ai_flags()`:
   - Denoising: `savgol`, `whittaker`, `savgol-window`, `savgol-order`
   - Baseline: `asls`, `airpls`, `arpls`, `poly`, `modpoly`, `lam`
   - Normalization: `vector`, `maxintensity`, `minmax`, `auc`
   - Peak: `prominence`, `distance`
6. Colon-encoded values like `savgol:7:3` or `arpls:1e5` are expanded:
   - `denoise=savgol:7:3` → denoise=savgol, savgol-window=7, savgol-order=3
   - `baseline=arpls:1e5` → baseline=arpls, lam=1e5
7. Displays the recommended command, flags, and reasoning
8. Applies recommendations to the analysis if accepted

### Fallback Behavior

If opencode is not installed or times out, the analyzer falls back to interactive mode. If AI returns no parsable JSON, it uses the current flags.

---

## Outputs

All analysis outputs are saved to the project `results/` directory (or a step-specific results subdirectory if the file is part of a protocol).

### CSV: Peaks Table

`{filename}_peaks.csv` (e.g., `sample_raman_peaks.csv`)

```csv
peak_center(cm⁻¹),intensity(counts),prominence,fwhm(cm⁻¹)
520.7,15000.2,12000.1,8.5
1331.5,8500.3,7200.0,22.1
1580.2,12000.5,11000.2,18.3
```

Columns: `peak_center(cm⁻¹)`, `intensity(counts)` (or `intensity(a.u.)` if normalized), `prominence`, `fwhm(cm⁻¹)`.

### CSV: Processed Spectrum

`{filename}_processed.csv` — Only produced when baseline correction is applied.

```csv
shift(cm⁻¹),intensity
500.0,0.0123
501.5,0.0118
503.0,0.0109
...
```

### Text Report

`{filename}_report.txt` — Structured text report with:

```
================================================================================
  RAMAN ANALYSIS REPORT
================================================================================

File:        sample_raman.txt
Laser:       532 nm
ND Filter:   10%
Acq. Time:   10.0 s
Accums:      6

--------------------------------------------------------------------------------
  PIPELINE
--------------------------------------------------------------------------------
Denoising:      Savitzky-Golay (window=7, polyorder=3)
Baseline:       AIRPLS (lam=1e7)
Normalization:  Vector

--------------------------------------------------------------------------------
  DETECTED PEAKS
--------------------------------------------------------------------------------

  #     Shift (cm⁻¹)  Intensity (a.u.)    Prominence   FWHM (cm⁻¹)
 ---   ------------   ------------    -----------   -----------
   1          520.7          0.1500       12000.1          8.5
   2         1331.5          0.0850        7200.0         22.1
   3         1580.2          0.1200       11000.2         18.3

--------------------------------------------------------------------------------
  SUMMARY
--------------------------------------------------------------------------------
Total peaks:        3
Max intensity:      0.1500
Major bands:       521 cm⁻¹, 1332 cm⁻¹, 1580 cm⁻¹
```

### PDF Plot: Enhanced Analysis

`{filename}_analysis.pdf` — Generated when `--plot` flag is set. A single-panel figure with:

1. **Raw spectrum** (gray, thin, 0.4 alpha)
2. **Baseline curve** (orange dashed, only if baseline correction was applied)
3. **Corrected/normalized spectrum** (black, 1.0 linewidth)
4. **Detected peaks** (red scatter points)
5. **Peak labels** (red text, rotated 45°, annotated at shifts >15 cm⁻¹ apart)

File dimensions: 8×3.5 inches, tight layout.

### PDF Plot: Overlay

`raman_analyze_overlay.pdf` + `raman_analyze_overlay.png` — Generated with `--overlay` flag for multiple files. All corrected spectra overlaid on the same axes with distinct colors from a 10-color palette, labeled by filename stem.

### PDF Plot: All

`raman_analyze_all.pdf` + `raman_analyze_all.png` — Generated with `--all` flag. Stacked subplots (one per file) with individual y-axes and shared x-axis, showing corrected spectrum plus optional baseline and peak markers.

---

## YAML Schema

The following YAML structure captures the full Raman analysis configuration and results for integration with protocol definitions and the results dashboard:

```yaml
technique: raman
analysis:
  pipeline:
    denoising: savgol            # savgol | whittaker | none
    savgol_window: 7             # window length if savgol
    savgol_order: 3              # polynomial order if savgol
    whittaker_lam: 1e5           # lambda if whittaker
    baseline: airpls             # asls | iasls | airpls | arpls | iarpls | poly | modpoly | none
    baseline_lam: 1e7            # regularization parameter
    baseline_p: 0.01             # asymmetry parameter (asls/iasls only)
    normalization: vector        # vector | minmax | maxintensity | auc | none
  peak_detection:
    method: scipy_find_peaks
    prominence_auto: true        # true when 15% of max intensity auto-computed
    prominence_value: 15000.2    # actual prominence used (auto or user-specified)
    distance: null               # minimum cm⁻¹ between peaks (or null)
    height: null                 # minimum intensity (or null)
    width: null                  # minimum FWHM in cm⁻¹ (or null)
    n_peaks: 3
    peak_shifts_cm1: [520.7, 1331.5, 1580.2]
    peak_intensities: [15000.2, 8500.3, 12000.5]
    prominences: [12000.1, 7200.0, 11000.2]
    fwhms_cm1: [8.5, 22.1, 18.3]
  metadata:
    instrument: LabRAM HR Evolution
    detector: Synapse
    laser: "532 nm"
    grating: "1800 gr/mm"
    objective: "100x"
    nd_filter: "10%"
    hole: "100"
    range: "500-3200 cm⁻¹"
    full_time: "60.0"
    acq_time_s: "10.0"
    accumulations: "6"
    detector_temperature_c: "-70.0"
    detector_gain: "1"
    detector_adc: "1 MHz"
    x_m: "1234.5"
    y_m: "567.8"
    z_m: "10000.0"
    site: "Center"
    title: "Sample_A_1"
    sample: "HfO2_10nm"
    remark: "Fresh device"
    date: "2024-01-15"
    acquired: "14:30:00"
    autoexposure: "Off"
    autofocus: "On"
    autoscann: "Off"
    spike_filter: "Off"
    delay_time_s: "0.0"
    binning: "1x1"
    readout_mode: "Standard"
    denoise: "Off"
    ics_correction: "Off"
    dark_correction: "On"
    inst_process: "None"
    stagexy: "Motorized"
    stagez: "Piezo"
    ultght: "Off"
    project: "HfOx_project"
```

---

## Examples

### 1. List all Raman files in current project

```
sci raman ls
```

Shows two tables: Raman files and SERS files, each with metadata columns.

### 2. List files for a specific protocol step

```
sci raman ls --step deposition_01
```

Lists Raman files only within the named protocol step directory.

### 3. Inspect full metadata for a single file

```
sci raman info sample_raman.txt
```

Displays all 38 metadata fields in a Rich table.

### 4. Interactive file selection for metadata inspection

```
sci raman info
```

Opens fzf picker with metadata preview tags; supports multi-select.

### 5. Full analysis with SavGol denoising, AIRPLS baseline, Vector normalization

```
sci analyze --technique raman --denoise savgol --savgol-window 7 --savgol-order 3 --baseline airpls --lam 1e7 --norm vector --plot
```

### 6. Analysis with Whittaker denoising and ASLS baseline

```
sci analyze --technique raman --denoise whittaker --lam 1e5 --baseline asls --lam 1e7 --p 0.01 --plot
```

Note: `--lam` is used twice — first for Whittaker (1e5), second for ASLS (1e7). The pipeline separates these contexts (denoising lambda vs. baseline lambda).

### 7. Quick analysis with auto-computed prominence

```
sci analyze --technique raman --baseline arpls --plot
```

Peak prominence auto-computed as 15% of max intensity.

### 8. Analysis with custom peak detection parameters

```
sci analyze --technique raman --baseline airpls --norm maxintensity --prominence 5000 --distance 20 --width 5 --plot
```

Filters peaks: minimum prominence 5000, minimum 20 cm⁻¹ separation, minimum 5 cm⁻¹ width.

### 9. AI-recommended analysis

```
sci analyze --technique raman --ai
```

Calls the sci-raman opencode agent to recommend all preprocessing flags based on spectral metadata.

### 10. Interactive pipeline builder

```
sci analyze --technique raman
```

Without any pipeline flags, launches an interactive prompt for each step:

```
Raman Analysis — Interactive Pipeline Builder
Hit Enter for defaults (shown in brackets)

  Denoising? [none|savgol|whittaker] (none): savgol
    SavGol window length [7]: 9
    SavGol polyorder [3]: 3
  Baseline method? [asls|airpls|arpls|poly|modpoly|none] (none): airpls
    Lambda [1e7]: 1e7
  Normalization? [vector|minmax|maxintensity|auc|none] (none): vector
  Peak prominence [auto — 15% of max intensity]: 10000
  Min peak distance [none]: 10
  Generate plot? [y/N]: y
```

### 11. Simple single-plot with default theme

```
sci plot --technique raman sample_raman.txt --grid
```

Generates a single Raman spectrum plot with gridlines using the active theme defaults.

### 12. Overlay plot with multiple files

```
sci plot --technique raman sample1_raman.txt sample2_raman.txt
# Prompts: Overlay all (o) or individual plots (i)?
# Select: o
```

Generates an overlay plot with each spectrum colored distinctly.

### 13. High-resolution publication plot with zoom

```
sci plot --technique raman sample_raman.txt --dpi 600 --zoom 500,1800 --color black --linewidth 1.5 --name high_res_raman.pdf
```

### 14. Analysis with overlay of processed spectra

```
sci analyze --technique raman --baseline airpls --norm vector --overlay
```

With multiple files selected, generates an overlay plot of corrected spectra saved to `raman_analyze_overlay.pdf`.

### 15. Batch individual analysis plots

```
sci analyze --technique raman --baseline modpoly --norm auc --all
```

Processes all selected files individually and generates stacked subplot figure saved to `raman_analyze_all.pdf`.

### 16. Non-project file analysis

```
sci analyze --technique raman /absolute/path/to/data_raman.txt --denoise savgol --baseline airpls --plot
```

Works outside a project context by resolving the file path directly.

---

## References

1. Smith, E. & Dent, G. (2019). *Modern Raman Spectroscopy: A Practical Approach*. 2nd ed. Wiley.
2. Eilers, P.H.C. (2003). A perfect smoother. *Analytical Chemistry*, 75(14), 3631-3636.
3. Eilers, P.H.C. & Boelens, H.F.M. (2005). Baseline correction with asymmetric least squares smoothing. *Leiden University Medical Centre Report*.
4. Zhang, Z.M., Chen, S., & Liang, Y.Z. (2010). Baseline correction using adaptive iteratively reweighted penalized least squares. *Analyst*, 135(5), 1138-1146.
5. RamanSPy documentation: https://ramanspy.readthedocs.io/

---

## See Also

- [overview.md](../overview.md) — science-cli technique overview
- [reference/commands/raman.md](../reference/commands/raman.md) — CLI command reference for `sci raman`
- [reference/commands/analyze.md](../reference/commands/analyze.md) — Unified analysis command reference
- [reference/commands/plot.md](../reference/commands/plot.md) — Unified plot command reference
- [schemas/analysis-yaml.md](../schemas/analysis-yaml.md) — Analysis YAML schema specification
- [schemas/protocol-yaml.md](../schemas/protocol-yaml.md) — Protocol YAML schema for step definitions
