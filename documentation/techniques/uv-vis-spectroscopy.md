# UV-Vis Spectroscopy

## Overview

Ultraviolet-visible (UV-Vis) spectroscopy measures the absorption or transmission of light in the ultraviolet (200–400 nm) and visible (400–800 nm) regions of the electromagnetic spectrum. When photons in this energy range interact with a sample, electronic transitions occur — electrons are excited from the ground state to higher-energy molecular orbitals. The wavelengths and intensities of these transitions provide information about chemical structure, conjugation, band structure in solids, and concentration via the Beer-Lambert law.

### Beer-Lambert Law

The fundamental relationship governing absorption spectroscopy:

$$A = \varepsilon b c$$

where:

| Symbol | Meaning | Units |
|--------|---------|-------|
| $A$ | Absorbance (optical density) | dimensionless (AU) |
| $\varepsilon$ | Molar attenuation coefficient | L·mol⁻¹·cm⁻¹ |
| $b$ | Path length through the sample | cm |
| $c$ | Concentration of the absorbing species | mol·L⁻¹ |

In practice, most spectrometers measure transmission ($T$) rather than absorbance directly:

$$T = \frac{I}{I_0} \qquad A = -\log_{10}(T)$$

where $I_0$ is the incident light intensity and $I$ is the transmitted intensity.

### Transmission vs. Absorbance Mode

| Mode | Definition | Typical Range | Common in |
|------|-----------|---------------|-----------|
| Transmission ($T\%$) | $100 \times I/I_0$ | 0–100% | Thin films, solutions |
| Absorbance ($A$) | $-\log_{10}(T)$ | 0–3+ | Solution concentration analysis |
| Reflectance ($R\%$) | $100 \times I_{\text{reflected}}/I_0$ | 0–100% | Opaque solids, thin films on substrates |

The IOP Hanoi spectrometer used in science-cli outputs transmission mode by default.

### Electronic Transitions in UV-Vis

#### Molecular Transitions

In molecular systems, UV-Vis absorption arises from electronic transitions between molecular orbitals:

| Transition Type | Energy Range (nm) | Typical Chromophores |
|----------------|-------------------|---------------------|
| $\sigma \to \sigma^*$ | <200 (vacuum UV) | C-C, C-H single bonds |
| $n \to \sigma^*$ | 200–300 | O, N, S, X lone pairs |
| $\pi \to \pi^*$ | 200–700 | C=C, C=O, aromatic rings, conjugated systems |
| $n \to \pi^*$ | 250–600 | C=O, C=N, N=O (weak, ~100× weaker than $\pi \to \pi^*$) |
| d–d transitions | 400–800 | Transition metal complexes (Ligand Field transitions) |
| Charge transfer (CT) | 200–800 | Metal-to-ligand (MLCT) or ligand-to-metal (LMCT) |

The energy gap between the highest occupied molecular orbital (HOMO) and the lowest unoccupied molecular orbital (LUMO) determines the wavelength of the lowest-energy absorption. Extended conjugation shifts absorption to longer wavelengths (red shift or bathochromic shift).

#### Band-to-Band Transitions in Solids

In semiconductors and insulators, UV-Vis absorption probes the band structure. Near the band edge, the absorption coefficient $\alpha$ follows the Tauc relation:

$$(\alpha h\nu)^{1/n} = B(h\nu - E_g)$$

where:

| Symbol | Meaning |
|--------|---------|
| $\alpha$ | Absorption coefficient (cm⁻¹) |
| $h\nu$ | Photon energy (eV) |
| $B$ | Band tailing parameter |
| $E_g$ | Optical bandgap energy (eV) |
| $n$ | Exponent depending on transition type |

The exponent $n$ determines the nature of the electronic transition:

| Transition Type | $n$ | $(\alpha h\nu)^n$ vs. $h\nu$ |
|----------------|-----|-----------------------------|
| Direct allowed | 1/2 | $(\alpha h\nu)^2$ |
| Direct forbidden | 2/3 | $(\alpha h\nu)^{3/2}$ |
| Indirect allowed | 2 | $(\alpha h\nu)^{1/2}$ |
| Indirect forbidden | 3 | $(\alpha h\nu)^{1/3}$ |

In practice, the two most common Tauc plots are:

- **Direct bandgap** ($n = 1/2$): $(\alpha h\nu)^2$ vs. $h\nu$ — used for direct-gap semiconductors (GaAs, CdTe, halide perovskites, most transition metal oxides)
- **Indirect bandgap** ($n = 2$): $(\alpha h\nu)^{1/2}$ vs. $h\nu$ — used for indirect-gap semiconductors (Si, Ge, some metal oxides like TiO₂ anatase)

The bandgap energy $E_g$ is obtained by fitting the linear region of the Tauc plot and extrapolating to the x-intercept ($\alpha = 0$).

### What UV-Vis Reveals

| Information | Physical Origin |
|------------|----------------|
| Bandgap energy | Onset of absorption — Tauc plot linear extrapolation |
| Film thickness | Interference fringes in transmission spectra |
| Defect states | Sub-bandgap absorption tails (Urbach energy) |
| Crystallinity | Sharpness of absorption edge |
| Quantum confinement | Blue shift of absorption onset in nanocrystals |
| Alloy composition | Vegard's law — bandgap varies linearly with composition |
| Molecular concentration | Beer-Lambert law: $A = \varepsilon b c$ |
| Conjugation length | $\lambda_{\max}$ shifts with extended $\pi$-systems |
| Protein/DNA concentration | 280 nm (Trp/Tyr) and 260 nm (DNA) absorbance |

---

## IOP Hanoi Spectrometer Format

science-cli reads UV-Vis data from IOP Hanoi UV-Vis spectrometers (used in the Hanoi University of Science and Technology / IOP lab context). The device configuration is registered in the built-in device registry:

```yaml
iop-hanoi:
  label: "UV-Vis Spectrometer (IOP Hanoi)"
  delimiter: ","
  decimal: "."
  header_lines: 1
  encoding: "latin1"
  columns:
    wavelength: "Wavelength nm."
    transmittance: "T%"
```

### File Format

| Property | Value | Details |
|----------|-------|---------|
| Header | 1 line (column names) | Or no header — auto-detected |
| Delimiter | Comma (`,`) | Unix-style CSV |
| Encoding | latin1 (ISO 8859-1) | Handles special characters, degree symbols |
| Decimal separator | Period (`.`) | Standard decimal notation |
| Columns | Wavelength (nm), T% | Two columns, first = wavelength, second = transmission |

### Example Raw File

```
Wavelength nm.,T%
300.0,85.234
301.0,85.112
302.0,84.989
...
800.0,92.345
```

### Column Mapping

The device config remaps the raw column names to canonical names:

| Raw Column Name | Canonical Name | Role |
|-----------------|----------------|------|
| `Wavelength nm.` | `wavelength` | X-axis — spectral position in nanometers |
| `T%` | `transmittance` | Y-axis — percent transmission (0–100%) |

The `data_loader.py` applies this remapping automatically via the `_load_with_device_config()` function when `technique="uv-vis"` is passed.

### Filename-Based Technique Detection

UV-Vis files are identified by containing any of these substrings (case-insensitive):

- `_uv-vis`
- `_uvvis`
- `uv-vis`
- `uvvis`

These patterns are defined in `science_cli.core.technique.PATTERNS["uv-vis"]` at `src/science_cli/core/technique.py:82`:

```python
"uv-vis": [r"_uv-vis", r"_uvvis", r"uv-vis", r"uvvis"],
```

The fallback detection in `_get_uv_files()` also matches any filename containing `_uv` as a substring, catching additional naming variants.

### Canonical Filename Convention

Following the standard science-cli grammar convention:

```
260526_PDA-ITO_uvvis_01.txt
│      │      │      │
│      │      │      └── Run suffix (01)
│      │      └── Technique code (uvvis)
│      └── Material (PDA-ITO)
└── Date code (260526 — 26 May 2026)
```

Grammar codes registered for UV-Vis: `uv-vis`, `uvvis`, `uv_vis` (defined in `config.py` technique registry).

---

## CLI Commands

### `sci uv-vis ls`

List UV-Vis files in the current project.

```
sci uv-vis ls
```

Displays a Rich table with:

| Column | Description | Source |
|--------|-------------|--------|
| File | Filename | Filesystem |
| Size | Formatted file size (KB/B) | `stat().st_size` |
| Path | Parent directory | Filesystem |

**Implementation**: `_uv_ls()` at `uv_vis.py:181` reads the project `data/raw/` directory and filters by either `detect_technique() == "uv-vis"` or filename infix match (`_uv`, `_uv-vis`, `uvvis`). Results are rendered in a cyan-bordered Rich table.

### `sci uv-vis info [file...]`

Show file metadata and data range.

```
sci uv-vis info <file>
sci uv-vis info                  # Interactive fzf multi-select picker
```

Displays for each file:

- **Data Points**: Number of rows in the loaded DataFrame
- **Columns**: Available column names (after remapping)
- **Per-column value range**: min and max for each numeric column

**Implementation**: `_uv_info()` at `uv_vis.py:207` loads each file with `load_data_file(technique="uv-vis")`, then iterates columns printing formatted min/max ranges. When no file argument is provided, it launches `_uv_fzf_pick_multi()` — the interactive fzf picker with step-aware display (protocol name, step name, and filename columns).

#### fzf Interactive Picker

The `_uv_fzf_pick_multi()` function (`uv_vis.py:78`) provides a rich interactive file selection:

1. Scans `data/raw/` for UV-Vis files
2. Builds a step-aware context by reading all protocol YAML files
3. Maps each file to its parent protocol and step
4. When an active protocol session exists, pre-filters to that protocol's files
5. Displays files in fzf with:

   ```
   > deposition_01  uv-vis  260526_PDA-ITO_uvvis_01.txt
     annealing_01   uv-vis  260527_PDA-ITO_uvvis_02.txt
   ```

6. Shows a file preview window (first 20 lines, right panel)
7. Supports multi-select with Tab

### `sci uv-vis plot [file...]` (deprecated)

Deprecated in favor of `sci plot --technique uv-vis`.

```
sci uv-vis plot                  # Interactive (fzf picker + style prompts)
sci uv-vis plot 260526_PDA-ITO_uvvis_01.txt --name spectrum.pdf
```

**Warning**: Use `sci plot --technique uv-vis` instead. The `uv-vis plot` subcommand still works but displays a deprecation notice.

**Interactive flow** when called without arguments:

1. Opens fzf multi-select picker for file selection
2. Pre-fills style flags from the UV-Vis template (line style, colors)
3. Pre-fills plot labels from config (`Wavelength (nm)`, `Transmission (%)`)
4. Prompts for additional style flags (`--type`, `--color`, `--linewidth`)
5. Prompts for figure flags (`--name`, `--xlabel`, `--ylabel`, `--grid`, `--zoom`)
6. For single file: generates one plot
7. For multiple files: prompts "Overlay all (o) or individual plots (i)?"
8. Enforces technique boundaries — rejects non-UV-Vis files

### `sci plot --technique uv-vis [file...]` (preferred)

Preferred plotting method. Unified interface shared across all techniques.

```
sci plot --technique uv-vis 260526_PDA-ITO_uvvis_01.txt
sci plot --technique uv-vis --xlabel "Wavelength (nm)" --ylabel "Transmission (%)" --grid
sci plot --technique uv-vis 260526_PDA-ITO_uvvis_01.txt --name uv_vis_spectrum.pdf
```

#### UV-Vis Template Defaults

The UV-Vis plot template (`plot.py:287`) defines:

```python
"uv-vis": {
    "plot_style": "--type line | --color | --linewidth",
    "figure": "-n uv-vis.pdf | --xlabel Wavelength (nm) | --ylabel Transmission (%) | --grid | --zoom x1,x2,y1,y2",
}
```

#### Column Auto-Detection

The plot command (`plot.py:781`) automatically finds the correct columns using a candidate list:

```python
# X-axis candidates (wavelength)
for candidate in ("wavelength", "Wavelength nm.", "Wavelength", "nm"):
    if candidate in df.columns:
        xcol = candidate
        break

# Y-axis candidates (transmission)
for candidate in ("transmittance", "T%", "T", "Transmittance"):
    if candidate in df.columns:
        ycol = candidate
        break
```

This means plots work automatically for IOP Hanoi files (which have columns `Wavelength nm.` and `T%`).

#### Available Plot Flags

| Flag | Description |
|------|-------------|
| `--name` / `-n` | Output filename (default: `{technique}_{stem}.pdf`) |
| `--xlabel` | X-axis label |
| `--ylabel` | Y-axis label |
| `--title` | Plot title |
| `--color` | Line color |
| `--linewidth` | Line width |
| `--linestyle` | Line style (`-`, `--`, `:`, `-.`) |
| `--grid` | Show grid on plot |
| `--dpi` | Image resolution (default 300) |
| `--xlim` / `--zoom` | X-axis range, comma-separated (e.g., `350,700`) |
| `--ylim` | Y-axis range |
| `--overlay` | Overlay multiple spectra in one figure |
| `--all` | Generate separate plots for each file |

#### Overlay Mode

With multiple files, prompts for overlay vs. individual:

```
sci plot --technique uv-vis
# Select multiple files via fzf
# Prompts: Overlay all (o) or individual plots (i)?
```

Or programmatically:

```
sci plot --technique uv-vis file1_uvvis.txt file2_uvvis.txt
```

Pass `--overlay` to force overlay mode:

```
sci plot --technique uv-vis file1.txt file2.txt --overlay
```

### `sci uv-vis analyze [file...]` (deprecated)

Deprecated in favor of `sci analyze --technique uv-vis`.

```
sci uv-vis analyze 260526_PDA-ITO_uvvis_01.txt
sci uv-vis analyze               # Interactive fzf selection
sci uv-vis analyze 260526_PDA-ITO_uvvis_01.txt --name my_analysis
```

### `sci analyze --technique uv-vis [file...]` (preferred)

Unified analysis command. Computes spectral parameters and peak detection.

```
sci analyze --technique uv-vis 260526_PDA-ITO_uvvis_01.txt
sci analyze --technique uv-vis --bandgap     # Compute Tauc bandgap (planned)
sci analyze --technique uv-vis --yaml        # Output analysis YAML
```

#### Analysis Output

For each analyzed file, the console output shows:

```
UV-Vis Analysis: 260526_PDA-ITO_uvvis_01.txt
  Peaks found: 3
    420.5 nm  (A=0.534)
    550.0 nm  (A=0.213)
    680.2 nm  (A=0.145)
```

#### Analysis CSV

Results are saved to `{prefix}_analysis.csv` with columns:

| Column | Description |
|--------|-------------|
| `wavelength(nm)` | Wavelength in nanometers |
| `intensity` | Measured intensity (transmission % or absorbance) |
| `derivative` | First derivative dI/dλ (computed via `numpy.gradient`) |

The derivative column is useful for identifying inflection points in the spectrum, particularly the absorption onset.

#### Manifest

Analysis provenance is recorded in `manifest.json` alongside the CSV:

```json
{
  "command": "uv-vis analyze /path/to/260526_PDA-ITO_uvvis_01.txt",
  "source_files": ["/path/to/260526_PDA-ITO_uvvis_01.txt"],
  "output_files": ["/path/to/results/260526_PDA-ITO_uvvis_01_analysis.csv"],
  "technique": "uv-vis",
  "parameters": {},
  "project": "my-project"
}
```

---

## Peak Detection

The `_analyze_uv_vis()` function (`analyze.py:542`) uses `scipy.signal.find_peaks` for peak detection on the UV-Vis spectrum.

### Algorithm

1. Load the UV-Vis file with `load_data_file(filepath, technique="uv-vis")`
2. Extract columns — first column as wavelength (x), second as intensity (y)
3. Filter NaN values via numpy masking
4. Apply `scipy.signal.find_peaks(y, prominence=0.05 * max(y))`
   - Prominence threshold is set to 5% of the maximum intensity
   - Peaks below this threshold are treated as noise
5. Collect detected peaks into a list of `{wavelength_nm, absorbance}` dicts
6. Display in console (up to 10 peaks; any excess noted)

### Peak Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **prominence** | Minimum vertical distance between a peak and its lowest contour line | 5% of max intensity |
| **wavelength_nm** | X-position (nm) at peak maximum | — |
| **absorbance** | Y-value at peak maximum | — |

### Output

Peaks are displayed in the console:

```
UV-Vis Analysis: 260526_PDA-ITO_uvvis_01.txt
  Peaks found: 3
    420.5 nm  (A=0.534)
    550.0 nm  (A=0.213)
    680.2 nm  (A=0.145)
```

And recorded in the analysis results for YAML export.

---

## Tauc Bandgap Computation

The `--bandgap` flag is defined in the UV-Vis analysis flags schema (`analyze.py:48-51`) but the computation is planned for implementation. This section describes the intended algorithm.

### The Tauc Plot Method

The Tauc method determines the optical bandgap energy $E_g$ of a semiconductor from its absorption spectrum. The approach:

1. **Absorption coefficient** $\alpha$ from transmission $T$:

   For a sample of thickness $d$ (cm):

   $$\alpha = \frac{1}{d} \ln\left(\frac{1}{T}\right) = \frac{2.303}{d} A$$

   When thickness is unknown, $\alpha \propto A$ (absorbance is proportional to $\alpha$), and relative Tauc plots can still yield meaningful $E_g$ values.

2. **Photon energy** $h\nu$ from wavelength $\lambda$ (nm):

   $$h\nu (\text{eV}) = \frac{1239.84}{\lambda (\text{nm})}$$

3. **Tauc plot construction**:

   - Direct bandgap: plot $(\alpha h\nu)^2$ vs. $h\nu$
   - Indirect bandgap: plot $(\alpha h\nu)^{1/2}$ vs. $h\nu$

4. **Linear region identification**: Fit a straight line to the linear portion of the Tauc plot near the absorption edge

5. **Bandgap extraction**: The x-intercept of the linear fit gives $E_g$:

   $$(\alpha h\nu)^n = 0 \quad \Rightarrow \quad h\nu = E_g$$

### Implementation Plan

```python
def compute_tauc_bandgap(wavelength, absorbance, thickness_cm=1.0, direct=True):
    # Convert wavelength (nm) to photon energy (eV)
    energy_eV = 1239.84 / np.array(wavelength)

    # Convert absorbance to absorption coefficient
    alpha = 2.303 * np.array(absorbance) / thickness_cm

    # Build Tauc function
    if direct:
        tauc = (alpha * energy_eV) ** 2     # n = 1/2
    else:
        tauc = (alpha * energy_eV) ** 0.5   # n = 2

    # Find linear region near absorption edge
    # Fit line to tauc vs energy_eV
    # Bandgap = x-intercept
    return bandgap_eV, r_squared
```

### Output Schema (planned)

When implemented, `--bandgap` will produce:

```
Tauc Bandgap Analysis:
  Direct bandgap:   3.24 eV   (R² = 0.995)
  Indirect bandgap: 2.87 eV   (R² = 0.991)
  Method: Tauc plot
  Linear region: 3.0 eV to 3.5 eV
```

---

## Spectral Features and Interpretation

### Absorption Edge

The most prominent feature in most UV-Vis spectra is the absorption edge — a sharp increase in absorbance (or decrease in transmission) at a specific wavelength corresponding to the bandgap energy.

```
Transmission (%)
    |
100 |    ┌──────────────────────┐
    |    │                      │
    |    │    Transmission      │
 50 |    │    region            │
    |    │                      │
    |    │          ╲           │
    |    │           ╲          │ ← Absorption edge
    |    │            ╲         │
   0 |    └─────────────╲───────┘
    |________________________________
    300     400     500     600
                    Wavelength (nm)
```

The absorption edge position ($\lambda_{\text{onset}}$) is often reported as a qualitative bandgap indicator:

$$E_g (\text{eV}) \approx \frac{1239.84}{\lambda_{\text{onset}} (\text{nm})}$$

### Interference Fringes

In thin films with smooth surfaces and optically flat interfaces, the transmission spectrum may show periodic oscillations — interference fringes caused by constructive and destructive interference of multiply-reflected light within the film:

$$T(\lambda) = \frac{2n_s}{n_f^2 + 1} \quad \text{(at extrema)}$$

| Quantity | Determined From |
|----------|----------------|
| Film thickness $d$ | Fringe spacing: $d = \frac{\lambda_1 \lambda_2}{2n_f(\lambda_2 - \lambda_1)}$ |
| Refractive index $n_f$ | Fringe amplitude and envelope |
| Absorption coefficient $\alpha$ | Envelope of transmission maxima |

The Swanepoel method uses the envelope of interference fringes to extract both thickness and optical constants from a single transmission spectrum.

### Urbach Tail

Below the bandgap, the absorption edge often shows an exponential tail described by the Urbach rule:

$$\alpha = \alpha_0 \exp\left(\frac{h\nu}{E_U}\right)$$

where $E_U$ is the Urbach energy — a measure of disorder in the material. Higher $E_U$ indicates more structural disorder, defect states, or thermal fluctuations.

---

## YAML Schema

The analysis results can be exported to YAML with the `--yaml` flag. The schema follows the science-cli analysis convention:

```yaml
technique: uv-vis-transmission
analysis:
  peaks:
    - wavelength_nm: 420.5
      absorbance: 0.534
    - wavelength_nm: 550.0
      absorbance: 0.213
    - wavelength_nm: 680.2
      absorbance: 0.145
```

For bandgap analysis (when implemented):

```yaml
technique: uv-vis-absorbance
analysis:
  wavelength_range:
    min_nm: 300.0
    max_nm: 800.0
  peaks:
    - wavelength_nm: 420.5
      transmission: 29.3
      absorbance: 0.534
    - wavelength_nm: 550.0
      transmission: 61.2
      absorbance: 0.213
    - wavelength_nm: 680.2
      transmission: 71.6
      absorbance: 0.145
  bandgap:
    direct_eV: 3.24
    indirect_eV: 2.87
    method: Tauc
    linear_region_start_eV: 3.0
    linear_region_end_eV: 3.5
    r_squared: 0.995
```

### Technique Registration

The analysis validators (`validators.py:54`) register two UV-Vis technique variants:

```python
@register("uv-vis-transmission")
@register("uv-vis-absorbance")
def validate_uv_vis_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("UV-Vis results must contain 'analysis' key")
    return results
```

Both variants share the same schema validation — they require an `analysis` key containing the analysis results.

---

## Instrument Registry

The IOP Hanoi spectrometer is registered in the instrument registry (`registry.py:41`):

```python
"iop-hanoi": {
    "name": "IOP Hanoi UV-Vis",
    "type": "uv-vis-spectrometer",
    "techniques": ["uv-vis"],
    "config_ref": "devices.iop-hanoi",
},
```

The instrument type `uv-vis-spectrometer` is defined in `types.py`:

```python
"uv-vis-spectrometer": "UV-Vis Spectrometer",
```

---

## Examples

### 1. List UV-Vis files in current project

```
sci uv-vis ls
```

Displays a Rich table of all detected UV-Vis files with sizes.

### 2. Show file info (interactive)

```
sci uv-vis info
```

Opens fzf picker for interactive file selection, then shows data point count, column names, and per-column value ranges.

### 3. Show specific file info

```
sci uv-vis info 260526_PDA-ITO_uvvis_01.txt
```

### 4. Analyze with custom prefix

```
sci uv-vis analyze 260526_PDA-ITO_uvvis_01.txt --name my_analysis
```

### 5. Analyze using unified command

```
sci analyze --technique uv-vis 260526_PDA-ITO_uvvis_01.txt
```

### 6. Analyze with YAML output

```
sci analyze --technique uv-vis 260526_PDA-ITO_uvvis_01.txt --yaml
```

### 7. Analyze with bandgap (planned)

```
sci analyze --technique uv-vis 260526_PDA-ITO_uvvis_01.txt --bandgap
```

### 8. Simple plot with default theme

```
sci plot --technique uv-vis 260526_PDA-ITO_uvvis_01.txt --grid
```

Generates a single UV-Vis transmission spectrum plot with gridlines using the active theme defaults.

### 9. Publication-quality plot

```
sci plot --technique uv-vis 260526_PDA-ITO_uvvis_01.txt \
  --dpi 600 \
  --color black \
  --linewidth 1.5 \
  --xlabel "Wavelength (nm)" \
  --ylabel "Transmission (%)" \
  --zoom 350,700,0,100 \
  --name publication_uv_vis.pdf
```

### 10. Overlay multiple spectra

```
sci plot --technique uv-vis 260526_PDA-ITO_uvvis_01.txt 260527_PDA-ITO_uvvis_02.txt
# Prompts: Overlay all (o) or individual plots (i)?
# Select: o
```

### 11. Interactive plot with fzf file selection

```
sci plot --technique uv-vis
# Opens fzf multi-select picker
# Prompts for style and figure options
```

### 12. Non-project file analysis

```
sci analyze --technique uv-vis /absolute/path/to/data_uvvis.txt
```

### 13. Quick listing with specific wavelength window in plot

```
sci plot --technique uv-vis sample_uvvis.txt --zoom 400,600
```

Focuses on the 400–600 nm region where the absorption edge is expected.

### 14. Batch export multiple analyses

```
sci uv-vis analyze 260526_PDA-ITO_uvvis_01.txt 260527_PDA-ITO_uvvis_02.txt
```

### 15. Plot outside a project directory

```
sci plot --technique uv-vis ~/Desktop/measurement_uvvis.txt --name quick_plot.pdf
```

---

## Device Configuration Reference

The IOP Hanoi device config (from `data_loader.py` and `config.py`) in full:

```yaml
devices:
  iop-hanoi:
    label: "UV-Vis Spectrometer (IOP Hanoi)"
    delimiter: ","
    decimal: "."
    header_lines: 1
    encoding: "latin1"
    columns:
      wavelength: "Wavelength nm."
      transmittance: "T%"
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `delimiter` | `,` | Comma-separated CSV |
| `decimal` | `.` | Period as decimal separator |
| `header_lines` | `1` | Single header line with column names |
| `encoding` | `latin1` | ISO 8859-1 character encoding |
| `columns.wavelength` | `Wavelength nm.` | Raw column name for wavelength |
| `columns.transmittance` | `T%` | Raw column name for percent transmission |

### Technique-to-Device Routing

When `technique="uv-vis"` is passed without a device argument, the routing chain is:

1. **Config**: `techniques.uv-vis.default_device` → `iop-hanoi` (from `config.py:859`)
2. **Fallback**: Built-in default `uv-vis: iop-hanoi` (from `config.py:1032`)

---

## Technique Detection Flow

```
detect_technique(filename)
  │
  ├── 1. Try config patterns (project-level overrides)
  ├── 2. Try global config patterns
  └── 3. Fall back to hardcoded patterns
        └── "uv-vis": [r"_uv-vis", r"_uvvis", r"uv-vis", r"uvvis"]
              └── e.g., "260526_PDA-ITO_uvvis_01.txt" → MATCH → "uv-vis"
```

The `_uv_ls()` and `_uv_fzf_pick_multi()` functions also check for `_uv` infix as a fallback to catch files with non-standard naming:

```python
any(p in f.name.lower() for p in ["_uv", "_uv-vis", "uvvis"])
```

---

## Data Loading Flow

When a UV-Vis file is loaded via `load_data_file(filepath, technique="uv-vis")`:

1. `_resolve_device_config("uv-vis", "")` is called
   - With no device specified, the technique-to-device routing resolves `iop-hanoi`
2. `_load_with_device_config(path, device_cfg, "uv-vis", "iop-hanoi")` runs
   - Reads the file with `pandas.read_csv()`
   - Uses `sep=","`, `header=None` with `names`, `encoding="latin1"`
   - Strips quotes from column names
   - Remaps `Wavelength nm.` → `wavelength` and `T%` → `transmittance`
   - Coerces all columns to numeric (NaN for unparseable values)
3. Returns `(DataFrame, metadata_dict)` where DataFrame has columns `wavelength` and `transmittance`

If the file is loaded without a technique hint (e.g., generic `_load_txt()`), the automatic delimiter detection reads the first line and infers comma-separated format. Column names remain as-is from the raw file.

---

## See Also

- [overview.md](overview.md) — science-cli technique overview
- [reference/commands/uv-vis.md](../reference/commands/uv-vis.md) — CLI command reference for `sci uv-vis`
- [reference/commands/analyze.md](../reference/commands/analyze.md) — Unified analysis command reference
- [reference/commands/plot.md](../reference/commands/plot.md) — Unified plot command reference
- [schemas/analysis-yaml.md](../schemas/analysis-yaml.md) — Analysis YAML schema specification
- [schemas/config-yaml.md](../schemas/config-yaml.md) — Configuration YAML schema for device definitions
