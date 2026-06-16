# AFM/SPM — Atomic Force Microscopy / Scanning Probe Microscopy

## Overview

Atomic force microscopy (AFM) is a scanning probe technique that maps surface
topography by raster-scanning a sharp tip mounted on a flexible cantilever
across the sample. As the tip interacts with the surface, the cantilever
deflects; a laser-photodiode detection system measures this deflection and a
feedback loop adjusts the tip-sample separation to maintain constant
interaction force. The feedback signal produces a three-dimensional height map
with sub-nanometre vertical resolution and nanometre lateral resolution.

AFM belongs to the broader family of scanning probe microscopy (SPM)
techniques, which includes scanning tunnelling microscopy (STM), conductive
AFM (C-AFM), electrostatic force microscopy (EFM), and magnetic force
microscopy (MFM). While science-cli currently focuses on topographic imaging,
the same analysis infrastructure applies to any SPM variant that produces a
spatially resolved 2D scalar field.

### Imaging Modes

**Contact mode** — The tip is in continuous physical contact with the sample
surface. The cantilever deflection (or the feedback adjustment to maintain
constant deflection) maps the topography. Contact mode provides the highest
scan rates but applies significant lateral forces, which can damage soft
samples or displace loosely bound surface features.

**Tapping mode (intermittent contact)** — The cantilever oscillates at its
resonant frequency (typically 50–500 kHz) with an amplitude of tens of
nanometres. The tip contacts the surface briefly at the bottom of each
oscillation cycle. The feedback loop maintains constant oscillation amplitude
by adjusting the tip height. Tapping mode dramatically reduces lateral forces
and is the preferred mode for most materials science applications — soft
polymers, biological specimens, and loosely bound nanoparticles.

**Non-contact mode** — The tip oscillates above the surface without touching
it, sensing attractive van der Waals forces. The feedback loop maintains
constant oscillation frequency or amplitude shift. Non-contact mode offers the
lowest tip-sample interaction but requires ultra-clean, contamination-free
surfaces in UHV conditions.

### What AFM Reveals

| Quantity | Physical Meaning | Typical Use |
|----------|-----------------|-------------|
| Surface morphology | 3D topographic map of the surface | Grain structure, film continuity, defect density |
| Surface roughness | Statistical deviation of heights from mean (Sa, Sq) | Thin-film quality, CMP polish, surface preparation |
| Grain size | Lateral grain diameter and height | Grain growth, recrystallisation, nucleation density |
| Step height | Vertical distance across a feature edge | Film thickness, etch depth, lithography steps |
| Height distribution | Histogram of all pixel heights | Surface uniformity, multi-modal height populations |
| Power spectral density | Frequency-domain roughness decomposition | Spatial correlation length, roughness scaling |

### Typical Applications in Memristor / Neuromorphic Research

- **Thin-film surface quality** — Roughness of HfO₂, TaOx, TiO₂ switching
  layers affects switching uniformity and variability
- **Electrode morphology** — Grain structure of Pt, TiN, or Ru bottom
  electrodes influences the local field enhancement and filament nucleation
- **Step height metrology** — Measuring the physical thickness of deposited
  films by scanning across a masked edge or scratch
- **Defect mapping** — Pinholes, hillocks, and delamination in thin-film
  stacks after deposition or annealing
- **C-AFM** — Correlating topography with local conductivity maps
  (future: conductive AFM support in science-cli)

---

## Supported Formats

science-cli supports six AFM/SPM file formats through the
[AFMReader](https://github.com/afmreader/AFMReader) backend library (v0.0.7+).
Format auto-detection uses the file extension, routed through
`detect_technique()` in `core/technique.py`.

| Format | Extension | Typical Source | Technique Slug | Column Map Key |
|--------|-----------|----------------|----------------|----------------|
| Gwyddion | `.gwy` | Gwyddion native format (FOSS) | `afm-gwy` | ColumnMap(x="", y="") |
| Bruker SPM | `.spm` | Bruker Dimension / Nanoscope | `afm-spm` | ColumnMap(x="", y="") |
| Igor Pro | `.ibw` | Asylum Research (Oxford) | `afm-ibw` | ColumnMap(x="", y="") |
| JPK | `.jpk` | JPK Instruments (Bruker) | `afm-jpk` | ColumnMap(x="", y="") |
| STP | `.stp` | Various SPM controllers | `afm-stp` | ColumnMap(x="", y="") |
| TOP | `.top` | Various SPM controllers | `afm-top` | ColumnMap(x="", y="") |

The AFM column maps are all empty on `x` and `y` since AFM data is inherently
2D image data — the column resolution system is designed for 1D tabular data
(IV sweeps, CV, etc.) and does not apply to image-based techniques.

All six variants share identical plot presets:

```python
PLOT_PRESETS = {
    "afm-gwy": {"type": "image", "cmap": "viridis",
                 "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-spm": {"type": "image", "cmap": "viridis",
                 "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    # ... identical for ibw, jpk, stp, top
}
```

### Technique Detection Patterns

Registered in `PATTERNS` in `core/technique.py`:

| Technique | Regex |
|-----------|-------|
| `afm-gwy` | `\.gwy$` |
| `afm-spm` | `\.spm$` |
| `afm-ibw` | `\.ibw$` |
| `afm-jpk` | `\.jpk$`, `jpk-`, `jpk_` |
| `afm-stp` | `\.stp$` |
| `afm-top` | `\.top$` |

Only `afm-gwy` is registered in `TECHNIQUE_LIBRARY_MAP` (routes to the `afm`
library). The other five variants fall through to the `general` library via
prefix fallback. This means that plot and analyze dispatch work for all six
formats through the CLI subcommands, but the automatic `sci analyze --technique`
routing explicitly requires `afm-gwy`. For other formats, use the `afm analyze`
subcommand directly or pass `--technique afm` if supported.

### Multiple Channels

AFM files often contain multiple data channels recorded simultaneously:
- **Height** — Primary topographic signal (the feedback z-piezo signal)
- **Amplitude** — Oscillation amplitude of the cantilever (tapping mode)
- **Phase** — Phase lag of the oscillation relative to the drive signal
  (material contrast: stiffness, adhesion, viscoelasticity)
- **Deflection** — Static cantilever deflection (contact mode)
- **Current** — Current map from conductive AFM (C-AFM)

The `_extract_channels()` function in `loader.py` attempts to recover channel
names from several metadata keys:
```python
channels = metadata.get("channels") or metadata.get("channel_names") or metadata.get("data_names")
```

If none are found, the loader falls back to `["Channel 0"]`, `["Channel 1"]`,
etc. from a list-type `img_data`, or `["Height"]` as the ultimate default.

---

## CLI Commands

### sci afm ls

List all AFM/SPM files in the current project's `data/raw/` directory.

```bash
sci afm ls
```

Displays a Rich table with columns: File, Size, Format, Path. Format detection
uses `detect_technique()` to show the human-readable technique label (e.g.
"AFM (Gwyddion)", "AFM (Bruker SPM)").

The recognised file extensions are `.gwy`, `.spm`, `.ibw`, `.jpk`, `.stp`, `.top`.

Example output:
```
┌──────────────────────────────────────────────────────┐
│                    AFM/SPM Files                      │
├─────────────┬──────────┬───────────────┬──────────────┤
│ File        │     Size │ Format        │ Path         │
├─────────────┼──────────┼───────────────┼──────────────┤
│ HfO2_5nm    │ 512.0 KB │ AFM (Igor)    │ data/raw/    │
│ sample.gwy  │  1.2 MB  │ AFM (Gwyddion)│ data/raw/    │
│ PT_001.spm  │  2.5 MB  │ AFM (Bruker)  │ data/raw/    │
└─────────────┴──────────┴───────────────┴──────────────┘
```

### sci afm info [file] [--channel]

Display metadata for one or more AFM files. When called without a filename,
opens an interactive fzf selector pre-filtered to the active protocol's AFM
step files. Supports multiple files.

```bash
sci afm info sample.gwy
sci afm info                     # interactive fzf selection
sci afm info file1.ibw file2.jpk # multi-file
```

This loads the file via `load_afm()` and displays:

| Property | Source |
|----------|--------|
| File path | `Path(filepath)` |
| Format | `suffix.lower()` |
| Technique | `detect_technique()` → `get_technique_label()` |
| File size | `os.stat().st_size` |
| Pixel calibration | `data.pixel_to_nm` (nm/pixel) |
| Image dimensions | `data.image.shape` (rows × cols) |
| Scan size | `cols * pixel_to_nm` × `rows * pixel_to_nm` (nm) |
| Channels | `list_channels()` result |
| Active channel | Channel 0 / default |
| Metadata keys | `len(data.metadata)` |

```bash
sci afm info HfO2_5nm.ibw
```

Example output:
```
┌──────────────────────────────────────────────────────────────────┐
│                      AFM File Info: HfO2_5nm.ibw                 │
├─────────────────────────────┬────────────────────────────────────┤
│ File                        │ data/raw/HfO2_5nm.ibw              │
│ Format                      │ .ibw                               │
│ Technique                   │ AFM (Igor)                         │
│ Size                        │ 512.0 KB                           │
│ Pixel calibration           │ 0.9766 nm/pixel                    │
│ Image dimensions            │ 512 × 512 px                       │
│ Scan size                   │ 500.0 × 500.0 nm                   │
│ Channels                    │ Height, Amplitude, Phase            │
│ Active channel              │ Height                             │
│ Metadata keys               │ 12                                 │
└─────────────────────────────┴────────────────────────────────────┘
```

The `--channel` flag is accepted but currently used only by the export
subcommand. The info subcommand always shows all available channels.

### sci afm analyze [file] [--psd] [--export prefix]

Compute surface roughness, height distribution, and line profiles from an
AFM image. When called without a filename, opens an interactive fzf selector.
This subcommand is deprecated in favour of `sci analyze --technique afm`
but still fully functional.

```bash
sci afm analyze sample.gwy
sci afm analyze sample.gwy --psd
sci afm analyze sample.gwy --export results/analysis
sci afm analyze sample.gwy --psd --export results/my_analysis
```

**Roughness parameters** — computed by `compute_roughness()` in
`library/afm/analyze.py`:

| Parameter | Symbol | Formula | Meaning |
|-----------|--------|---------|---------|
| Ra | Ra | (1/N) Σ │zᵢ − z̄│ | Arithmetic mean deviation from mean height |
| Rq | Rq | √[(1/N) Σ (zᵢ − z̄)²] | Root-mean-square roughness (standard deviation) |
| Rmax | Rz | max(z) − min(z) | Maximum peak-to-valley height |
| Rsk | Rsk | (1/N) Σ (zᵢ − z̄)³ / Rq³ | Skewness of height distribution |
| Rku | Rku | (1/N) Σ (zᵢ − z̄)⁴ / Rq⁴ | Kurtosis of height distribution |
| Sdr | Sdr | (A_dev − A_proj) / A_proj × 100 | Developed interfacial area ratio (%) |

- **Ra** is the most widely reported roughness metric. It is robust against
  outliers but insensitive to isolated spikes or pits.
- **Rq** weights extreme height deviations more heavily than Ra, making it
  more sensitive to defects.
- **Rsk** indicates surface asymmetry: Rsk > 0 means a surface dominated by
  peaks (plateau with pits), Rsk < 0 means valleys predominate (porous
  surface).
- **Rku** describes the sharpness of the height distribution: Rku > 3
  (leptokurtic) indicates spiky surfaces with extreme features; Rku < 3
  (platykurtic) indicates a bumpy surface with gradual height variation.
- **Sdr** expresses the percentage increase in true surface area relative to
  the projected flat area. A perfectly flat surface has Sdr = 0%.

**Height distribution** — computed by `height_distribution()` with 100 bins.
Reports the modal height (peak of the histogram) and the full height range.

**Line profiles** — extracted at the image centre in both horizontal and
vertical directions using `line_profile()` from `library/afm/analyze.py`:

```python
# Horizontal: (center_row, left) → (center_row, right)
dist_h, height_h = line_profile(img, (center_r, 0), (center_r, w - 1))
# Vertical: (top, center_col) → (bottom, center_col)
dist_v, height_v = line_profile(img, (0, center_c), (h - 1, center_c))
```

The line is sampled at `int(hypot(Δr, Δc))` points using bilinear
interpolation. Reports min-to-max height range for each profile.

**PSD** (with `--psd` flag) — computed by `compute_psd()` in
`library/afm/analyze.py`. The PSD computation pipeline:

1. NaN values are replaced with the image mean
2. A 2D linear plane is fit via least-squares and subtracted (tilt removal)
3. A Hanning window is applied to reduce spectral leakage
4. 2D FFT (fft2 → fftshift) computes the power spectrum
5. Radial averaging produces the 1D PSD: power density vs spatial frequency

Reports the valid frequency range in nm⁻¹. Low spatial frequencies correspond
to long-range waviness; high spatial frequencies correspond to short-range
roughness and noise. The roll-off in the PSD can be used to extract lateral
correlation length and the roughness exponent (Hurst exponent).

**Export** (with `--export prefix`) — writes three CSV files:
- `{prefix}_roughness.csv` — single-row table of all roughness parameters
- `{prefix}_height_distribution.csv` — bin centers and pixel counts
- `{prefix}_line_profiles.csv` — horizontal and vertical distance vs height

### sci afm export [file] --format png|csv|npy [--channel <name>]

Export AFM image data to a portable format.

```bash
sci afm export sample.gwy --format png
sci afm export sample.gwy --format csv --channel Phase
sci afm export sample.ibw --format npy
sci afm export sample.gwy --format png --cmap inferno --dpi 600 --suffix _highres
```

**Formats:**

| Format | Extension | Description | Implementation |
|--------|-----------|-------------|----------------|
| `png` | `.png` | Topographic image rendering | `plot_afm_image()` → `fig.savefig(dpi=300)` |
| `csv` | `.csv` | Pixelwise height grid (row, col, height_nm) | Full raster of all pixels |
| `npy` | `.npy` | NumPy binary array | `np.save()` — height map as native 2D array |

**PNG export flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--cmap` | `viridis` | Matplotlib colormap name |
| `--dpi` | `300` | Output resolution |
| `--suffix` | `""` | String appended to output filename |
| `--outdir` | parent dir | Output directory |

The PNG export renders the image via `plot_afm_image()` from
`library/plot/afm.py` with spatial calibration (axis in nm), a colour bar
labelled "Height (nm)", and the specified colormap. The resulting image is
publication-ready at 300 DPI.

**CSV export** — Each pixel becomes one row: `row, col, height_nm`. This is
the recommended format for importing into external analysis tools (Origin,
Python, MATLAB) or for custom scripting.

**NPY export** — The height map is saved as a raw 2D numpy array. This is the
most compact format for subsequent Python analysis. Load with:

```python
import numpy as np
image = np.load("sample.npy")
```

### sci afm open

Open an `.ibw` (Igor Pro binary wave) file in the Gwyddion GUI for
interactive measurement, then record structured analysis results to a YAML
file.

```bash
sci afm open
```

**Workflow:**

1. Opens an fzf file selector filtered to `.ibw` files in the project's
   `data/raw/` directory
2. Resolves the protocol step directory for the selected file (requires that
   the file has been assigned to an AFM step via `sci add -m data`)
3. Launches Gwyddion as a detached subprocess with the selected file:
   ```python
   subprocess.Popen([gwyddion, raw_path], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
   ```
4. Prompts the user interactively for measurement values:

```yaml
# afm_analysis.yaml — auto-generated by afm open
files:
  - name: HfO2_5nm.ibw
    thick_nm: 5.2
    sa_nm: 0.345
    sq_nm: 0.432
    material: HfO2
```

The prompts pre-fill with any existing values (from a previous run on the
same file), making it easy to update or refine measurements without retyping.

The YAML file is saved to the step directory as `afm_analysis.yaml`. Multiple
files are accumulated under the `files` key:

```yaml
files:
  - name: HfO2_5nm.ibw
    thick_nm: 5.2
    sa_nm: 0.345
    sq_nm: 0.432
    material: HfO2
  - name: TaOx_10nm.ibw
    thick_nm: 10.1
    sa_nm: 0.521
    sq_nm: 0.678
    material: TaOx
```

---

## Plotting

AFM images are plotted via `sci plot --technique afm` which dispatches through
the `_wrap_afm_plot()` pathway in `cli/commands/plot.py` and calls
`_do_afm_plot()` in `cli/commands/afm.py`.

```bash
sci plot --technique afm sample.gwy
sci plot --technique afm sample.gwy --cross-section --colormap inferno
sci plot --technique afm sample.ibw --name topography.pdf
```

The default layout displays two subplots side by side:

**Left: Topography image** — Rendered via `plot_afm_image()` with spatial
calibration (axes labelled in nm), specified colormap (default `viridis`), and
a colorbar labelled "Height (nm)". The aspect ratio is set to `"equal"` so the
image is not distorted.

**Right: Height distribution** — A histogram of all pixel height values
computed via `height_distribution()` with 100 bins. The bin width is adaptive:
`bin_centers[1] - bin_centers[0]`. Rendered as a steelblue bar chart with
black edges and 0.7 alpha.

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--cross-section` | store_true | — | Show cross-section (not yet fully implemented in plot dispatch) |
| `--colormap` | str | `viridis` | Matplotlib colormap name |
| `--name` | str | — | Save figure to file (path relative to `results/`) |
| `--dpi` | int | `300` | Saved figure DPI (when `--name` is set) |
| `--title` | str | filename stem | Figure title |

When `--name` is specified, the figure is saved to `<project>/results/` as
PDF (default) or any extension parsed from the filename. The figure is
closed after saving to prevent display.

### Plotting Library API

The four dedicated AFM plot functions in `library/plot/afm.py` are available
for scripting and custom analysis workflows:

```python
from science_cli.library.afm import load_afm, compute_roughness, compute_psd, height_distribution, line_profile
from science_cli.plot.afm import plot_afm_image, plot_afm_line_profile, plot_afm_height_distribution, plot_afm_psd

data = load_afm("sample.gwy")

# Topography
ax = plot_afm_image(data.image, data.pixel_to_nm, cmap="viridis", title="Sample")

# Line profile
dist, height = line_profile(data.image, (0, 0), (511, 511))
ax = plot_afm_line_profile(dist, height)

# Height distribution
hist, edges = height_distribution(data.image, bins=100)
ax = plot_afm_height_distribution(hist, edges)

# PSD (log-log)
freq, power = compute_psd(data.image, data.pixel_to_nm)
ax = plot_afm_psd(freq, power)
```

### plot_afm_image() Details

```python
def plot_afm_image(image, px_to_nm=1.0, cmap="viridis", title="", ax=None):
    h, w = image.shape
    extent = [0, w * px_to_nm, h * px_to_nm, 0]  # X from left to right
    im = ax.imshow(image, cmap=cmap, extent=extent, interpolation="nearest")
    plt.colorbar(im, ax=ax, label="Height (nm)")
    ax.set_xlabel("X (nm)")
    ax.set_ylabel("Y (nm)")
```

The interpolation is set to `"nearest"` to preserve pixel-level detail. Use
`--cmap` to switch between matplotlib colormaps — `viridis` (default) for
general topography, `inferno` for high contrast, `gray` for publication, or
`terrain` for emphasising topographic features.

---

## Data Models

The `AfmData` dataclass in `library/afm/models.py` is the universal data
container:

```python
@dataclass
class AfmData:
    image: np.ndarray       # 2D height map (rows × cols)
    pixel_to_nm: float      # Spatial calibration (nm per pixel)
    channels: list[str]     # Available channel names
    filepath: str           # Source file path
    metadata: dict          # Raw metadata from AFMReader
```

### Spatial Calibration Extraction

The `_extract_pixel_to_nm()` function in `loader.py` tries these metadata keys
in priority order:

1. `metadata["pixel_to_nm"]`
2. `metadata["pixel_size_nm"]`
3. `metadata["pixel_to_nm_x"]`
4. `metadata["pixel_size_x_nm"]`
5. `metadata["Pixel size"]`
6. Derived: `scan_size_nm / max(image.shape)` from `metadata["scan_size_nm"]`
   or `metadata["Scan Size"]`
7. Fallback: `1.0` nm/pixel

The fallback of 1.0 nm/pixel preserves the numerical image data but axis
labels and scan size reports will be incorrect. Always verify the pixel
calibration after loading.

### Channel Selection

Channel selection follows a priority cascade in `_select_channel()`:

1. If `img_data` is a list (multi-channel), index by channel name or integer
2. If `img_data` is a 3D ndarray (multi-frame), index by name or integer
3. Otherwise return the raw ndarray as-is

The `channel` parameter `None` returns the first available channel.

### Scan Size Computation

Scan size is not stored directly but computed from the image dimensions and
pixel calibration:

```python
size_nm_x = image.shape[1] * pixel_to_nm  # width
size_nm_y = image.shape[0] * pixel_to_nm  # height
```

Typical scan sizes in memristor research range from 500 nm × 500 nm (grain
structure of thin HfO₂ films) to 10 µm × 10 µm (electrode pattern
inspection, defect surveys).

---

## YAML Analysis Schema

The complete output schema for AFM analysis, written to
`<step_dir>/results/afm_analysis.yaml`:

```yaml
technique: afm
instrument: <instrument_name or null>
devices: <device_type or null>
timestamp: "2026-06-15T12:00:00Z"
analysis:
  scan_size:
    width_nm: 500.0
    height_nm: 500.0
    pixel_size_nm: 0.9766
  roughness:
    Ra_nm: 0.3452
    Rq_nm: 0.4321
    Rmax_nm: 3.2154
    Rsk: -0.1234
    Rku: 3.4567
    Sdr: 1.2345
    n_pixels: 262144
  height_distribution:
    bins: 100
    modal_height_nm: 0.1523
    min_nm: -1.8932
    max_nm: 1.3221
  cross_section:
    horizontal:
      start_px: [256, 0]
      end_px: [256, 511]
      height_range_nm: [-1.452, 1.234]
      distance_nm: [0.0, 500.0]
      height_profile_nm: [...]
    vertical:
      start_px: [0, 256]
      end_px: [511, 256]
      height_range_nm: [-1.321, 1.156]
      distance_nm: [0.0, 500.0]
      height_profile_nm: [...]
  psd:
    frequency_min_nm: 0.0020
    frequency_max_nm: 0.5120
    correlation_length_nm: 45.23
    n_frequencies: 255
  metadata:
    format: gwy
    channels:
      - Height
      - Amplitude
      - Phase
    active_channel: Height
    image_dimensions_px: [512, 512]
    file_size_kb: 1250.5
```

### YAML Schema Fields

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `technique` | string | Always `"afm"` | Hardcoded |
| `instrument` | string or null | Instrument name from metadata | `metadata`, may be null |
| `devices` | string or null | Device type from protocol | Protocol YAML, may be null |
| `timestamp` | string (ISO 8601) | Analysis time | `datetime.utcnow()` |
| `analysis.scan_size.width_nm` | float | Physical scan width | `image.shape[1] × pixel_to_nm` |
| `analysis.scan_size.height_nm` | float | Physical scan height | `image.shape[0] × pixel_to_nm` |
| `analysis.scan_size.pixel_size_nm` | float | Spatial calibration | `pixel_to_nm` from metadata |
| `analysis.roughness.Ra_nm` | float | Arithmetic mean roughness | `compute_roughness()` |
| `analysis.roughness.Rq_nm` | float | RMS roughness | `compute_roughness()` |
| `analysis.roughness.Rmax_nm` | float | Peak-to-valley height | `compute_roughness()` |
| `analysis.roughness.Rsk` | float | Skewness | `compute_roughness()` |
| `analysis.roughness.Rku` | float | Kurtosis | `compute_roughness()` |
| `analysis.roughness.Sdr` | float | Surface area ratio (%) | `compute_roughness()` |
| `analysis.roughness.n_pixels` | integer | Valid pixel count | `len(z)` after NaN removal |
| `analysis.height_distribution.bins` | integer | Histogram bins | Hardcoded 100 |
| `analysis.height_distribution.modal_height_nm` | float | Most frequent height | `bin_centers[argmax(hist)]` |
| `analysis.height_distribution.min_nm` | float | Minimum height | `bin_edges[0]` |
| `analysis.height_distribution.max_nm` | float | Maximum height | `bin_edges[-1]` |
| `analysis.cross_section.horizontal.start_px` | [int, int] | Profile start (row, col) | Centre cross: `(h//2, 0)` |
| `analysis.cross_section.horizontal.end_px` | [int, int] | Profile end (row, col) | Centre cross: `(h//2, w-1)` |
| `analysis.cross_section.horizontal.height_range_nm` | [float, float] | Min/max height along profile | `nanmin`, `nanmax` |
| `analysis.cross_section.vertical` | (same as horizontal) | Vertical centre cross | Centre cross: `(0, w//2)`, `(h-1, w//2)` |
| `analysis.psd.frequency_min_nm` | float | Lowest spatial frequency | `freq[1]` (after zero-freq removal) |
| `analysis.psd.frequency_max_nm` | float | Highest spatial frequency | `freq[-1]` |
| `analysis.psd.n_frequencies` | integer | Number of radial bins | `len(freq)` |
| `analysis.metadata.format` | string | File extension label | `Path(filepath).suffix` |
| `analysis.metadata.channels` | [string] | Channel names from file | `list_channels()` |
| `analysis.metadata.active_channel` | string | Loaded channel | `channels[0]` or specified |
| `analysis.metadata.image_dimensions_px` | [int, int] | Image size (rows, cols) | `image.shape` |
| `analysis.metadata.file_size_kb` | float | Source file size | `os.stat()` |

### Gwyddion Bridge YAML Schema

The `afm open` subcommand writes to `<step_dir>/afm_analysis.yaml` with a
different schema focused on user-interactive measurements:

```yaml
# afm_analysis.yaml — auto-generated by afm open
files:
  - name: HfO2_5nm.ibw
    thick_nm: 5.2
    sa_nm: 0.345
    sq_nm: 0.432
    material: HfO2
```

| Field | Type | Description |
|-------|------|-------------|
| `files[].name` | string | Filename (matching a file in `data/raw/`) |
| `files[].thick_nm` | float or null | Film thickness in nm (from Gwyddion step height) |
| `files[].sa_nm` | float or null | Sa roughness in nm (from Gwyddion) |
| `files[].sq_nm` | float or null | Sq roughness in nm (from Gwyddion) |
| `files[].material` | string or null | Material identifier |

---

## File Loading Pipeline

The complete load chain from user command to analysis-ready numpy array:

```
sci afm info / analyze / export <file>
    │
    ├─ _resolve_file(file)          # Search data/raw/ if not absolute
    │
    ├─ load_afm(filepath)           # library/afm/loader.py
    │   ├─ LoadFile(filepath)       # AFMReader.general_loader
    │   │   ├─ Detect format from extension
    │   │   ├─ Parse file with format-specific reader
    │   │   └─ Return (img_data, metadata)
    │   ├─ _extract_pixel_to_nm()   # Spatial calibration
    │   ├─ _extract_channels()      # Channel names from metadata
    │   ├─ _select_channel()        # Pick first or named channel
    │   └─ Return AfmData           # Image + calibration + channels + metadata
    │
    └─ AfmData dataclass passed to:
        ├─ compute_roughness()      # Ra, Rq, Rmax, Rsk, Rku, Sdr
        ├─ height_distribution()    # Histogram of pixel heights
        ├─ line_profile()           # Bilinear-interpolated cross-section
        └─ compute_psd()            # 2D FFT → radial average
```

### Error Handling

| Condition | Error | Message |
|-----------|-------|---------|
| File not found | `FileNotFoundError` | `"AFM file not found: {path}"` |
| AFMReader not installed | `ImportError` | `"AFMReader is not installed. Install it with: pip install AFMReader>=0.0.7"` |
| Unsupported format / parse failure | `ValueError` | `"Failed to load '{name}': {detail}"` |
| Channel not found | `ValueError` | `"Channel '{name}' not found. Available: {list}"` |
| Not enough valid pixels (roughness) | — | Returns `{"error": "Not enough valid pixels (minimum 9)"}` |

All commands catch these exceptions at the CLI level and display a
user-friendly error message with a Rich formatted `[red]` tag.

---

## Interactive File Selection

All AFM subcommands (`ls` is the exception) support fzf-based interactive file
selection when called without positional arguments. The fzf integration in
`_afm_fzf_pick_multi()` provides:

- **Protocol-awareness** — If a session has an active protocol, files are
  filtered to those assigned to AFM steps within that protocol
- **Step metadata display** — Each file entry shows its protocol → step →
  filename hierarchy in the fzf preview
- **Multi-select** — Tab to select multiple files for batch processing
- **Preview** — Shows the first 5 lines of each file in a right-side preview
  panel (50% width)

The selection logic:

1. If an active protocol exists and files are assigned to its AFM steps,
   show only those files (hide protocol column)
2. Otherwise, show all AFM files with full protocol → step → filename
   hierarchy

---

## Internal Analysis Functions

### compute_roughness(image, px_to_nm=1.0)

```python
def compute_roughness(image: np.ndarray, px_to_nm: float = 1.0) -> dict:
```

Nan values are masked out before computation. The function requires a minimum
of 9 valid pixels and a 2D input array. The Sdr (surface area ratio) uses
forward finite differences to compute the developed interfacial area:

```python
dz_dx = img[:, 1:] - img[:, :-1]        # x-gradient
dz_dy = img[1:, :] - img[:-1, :]        # y-gradient
area_dx = sqrt(dx² + dz_dx²)            # true width of each facet
area_dy = sqrt(dy² + dz_dy²)            # true height of each facet
sdr = (Σ(area_dx × area_dy) - A_proj) / A_proj × 100
```

Sdr is capped at 0% (no negative area ratios are reported).

### compute_psd(image, px_to_nm=1.0)

```python
def compute_psd(image: np.ndarray, px_to_nm: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
```

The PSD uses a standard spectral estimation pipeline:

1. **NaN handling** — All NaN pixels are replaced with `np.nanmean()`. This
   is a simple imputation; large NaN regions will produce artefacts.
2. **Tilt removal** — A 2D plane `z(x, y) = a·x + b·y + c` is fit via
   ordinary least squares and subtracted from the image. This removes
   sample tilt and scanner bow artefacts.
3. **Windowing** — A 2D separable Hanning window
   `w(i,j) = hanning(i) · hanning(j)` is applied to mitigate spectral leakage
   from finite-image boundaries.
4. **FFT** — 2D FFT with fftshift, power computed as `|FFT|² / (h × w)`.
5. **Radial average** — Power is averaged over concentric annuli in the
   frequency domain. The zero-frequency component is removed.
6. **Frequency axis** — `np.fft.fftfreq()` assigns spatial frequencies in
   nm⁻¹ using the pixel calibration.

The result is a log-log spectrum suitable for extracting the Hurst exponent H
(from the power-law scaling region at high frequencies) and the lateral
correlation length ξ (from the knee frequency where the PSD transitions from
constant to power-law).

### line_profile(image, start, end)

```python
def line_profile(
    image: np.ndarray,
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
```

The profile is sampled at `int(hypot(r2-r1, c2-c1))` points along the line
connecting the two pixel coordinates. Height values are bilinearly
interpolated from the four nearest neighbours at each fractional coordinate.
Both coordinates are clipped to image bounds.

The profile function is the primary tool for measuring:
- **Step heights** — Vertical distance across a film edge or scratch
- **Grain profiles** — Cross-sectional shape of individual grains
- **Feature dimensions** — Lateral width of trenches, lines, or particles

### height_distribution(image, bins=100)

```python
def height_distribution(
    image: np.ndarray, bins: int = 100
) -> tuple[np.ndarray, np.ndarray]:
```

Uses `np.histogram()` with the specified number of bins. The histogram
excludes NaN pixels. The resulting distribution reveals:
- **Multi-modal surfaces** — Two or more distinct height populations
  (e.g., substrate + film islands)
- **Skewness** — Asymmetric distribution indicating peak/valley dominance
- **Surface uniformity** — Narrow distribution = smooth surface

---

## Installation & Dependencies

The AFM module requires the external `AFMReader` package for file parsing:

```bash
pip install "AFMReader>=0.0.7"
```

AFMReader supports the following file format backends:

| Format | Backend Package | Notes |
|--------|----------------|-------|
| Gwyddion `.gwy` | Built-in | Native Gwyddion format, fully supported |
| Bruker `.spm` | Built-in | Bruker NanoScope SPM files |
| Igor `.ibw` | Built-in | Asylum Research / Oxford Instruments |
| JPK `.jpk` | Built-in | JPK Instruments |
| STP `.stp` | Built-in | Generic SPM topography format |
| TOP `.top` | Built-in | Generic topography format |

There are no separate per-format dependencies — AFMReader handles all six
formats with its base installation.

For the Gwyddion bridge (`sci afm open`), the Gwyddion application must be
installed separately:

```bash
brew install gwyddion   # macOS (Homebrew)
```

---

## Examples

### Basic workflow: roughness and topography

```bash
# Activate project
sci use project my_hfo2_study

# List available AFM files
sci afm ls

# Inspect file metadata
sci afm info HfO2_5nm.gwy

# Full analysis (interactive file picker)
sci afm analyze

# Full analysis with explicit file and PSD
sci afm analyze HfO2_5nm.gwy --psd

# Export analysis to CSV for external plotting
sci afm analyze HfO2_5nm.gwy --export results/hfo2_5nm

# Plot topography with height distribution
sci plot --technique afm HfO2_5nm.gwy

# Export publication-ready image
sci afm export HfO2_5nm.gwy --format png --cmap inferno --dpi 600

# Export raw height data for custom analysis
sci afm export HfO2_5nm.gwy --format csv
sci afm export HfO2_5nm.gwy --format npy

# Gwyddion interactive workflow
sci afm open
```

### Batch analysis of multiple files

```bash
# Interactive fzf — multi-select with Tab
sci afm analyze

# Analyze with PSD and export for each file
sci afm analyze HfO2_5nm.gwy --psd --export results/hfo2
sci afm analyze TaOx_10nm.ibw --psd --export results/taox
```

### Custom Python script using the library API

```python
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from science_cli.library.afm import load_afm, compute_roughness, compute_psd

data = load_afm("HfO2_5nm.gwy")
roughness = compute_roughness(data.image, data.pixel_to_nm)
freq, psd = compute_psd(data.image, data.pixel_to_nm)

print(f"Sa = {roughness['Ra_nm']:.4f} nm")
print(f"Rq = {roughness['Rq_nm']:.4f} nm")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
extent = [0, data.image.shape[1] * data.pixel_to_nm,
          data.image.shape[0] * data.pixel_to_nm, 0]
ax1.imshow(data.image, cmap="viridis", extent=extent)
ax1.set_xlabel("X (nm)")
ax1.set_ylabel("Y (nm)")
im = ax1.imshow(data.image, cmap="viridis", extent=extent)
plt.colorbar(im, ax=ax1, label="Height (nm)")

ax2.loglog(freq, psd, "k-", linewidth=1)
ax2.set_xlabel("Spatial frequency (nm⁻¹)")
ax2.set_ylabel("PSD (nm⁴)")
ax2.grid(True, alpha=0.3, which="both")

plt.tight_layout()
plt.savefig("HfO2_analysis.pdf", dpi=300)
```

### Roughness comparison across processing conditions

```python
from science_cli.library.afm import load_afm, compute_roughness

samples = [
    ("as-deposited.gwy", "As Deposited"),
    ("annealed-300C.gwy", "300°C Anneal"),
    ("annealed-500C.gwy", "500°C Anneal"),
]

for filepath, label in samples:
    data = load_afm(filepath)
    r = compute_roughness(data.image, data.pixel_to_nm)
    print(f"{label:20s}  Sa = {r['Ra_nm']:.4f} nm  Rq = {r['Rq_nm']:.4f} nm  "
          f"Rsk = {r['Rsk']:.4f}  Sdr = {r['Sdr']:.2f}%")
```

---

## See Also

- [Technique Taxonomy Overview](overview.md) — Complete technique catalogue,
  detection engine, library routing, and analyzer/plotter mapping
- [IV Sweeps](iv-sweeps.md) — Current-voltage characterisation for memristors
- [Pulse Measurements](pulse-measurements.md) — Pulse endurance, retention,
  STP, PPF

### Source Files

- `src/science_cli/library/afm/__init__.py` — Module exports, COLUMN_MAPS, PLOT_PRESETS
- `src/science_cli/library/afm/models.py` — AfmData dataclass
- `src/science_cli/library/afm/loader.py` — load_afm(), list_channels(), format auto-detection
- `src/science_cli/library/afm/analyze.py` — compute_roughness(), height_distribution(), line_profile(), compute_psd()
- `src/science_cli/plot/afm.py` — plot_afm_image(), plot_afm_line_profile(), plot_afm_height_distribution(), plot_afm_psd()
- `src/science_cli/cli/commands/afm.py` — afm_handler(), all subcommands (ls, info, analyze, export, open)
- `src/science_cli/core/technique.py` — PATTERNS, detect_technique(), BUILTIN_TECHNIQUES
- `src/science_cli/core/routing.py` — TECHNIQUE_LIBRARY_MAP, resolve_library()
- `src/science_cli/analysis/validators.py` — validate_afm_schema (YAML schema validator)
