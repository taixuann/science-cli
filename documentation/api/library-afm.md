# API Reference — `science_cli.library.afm`

AFM/SPM image loading, analysis, and plotting support. Built on
[AFMReader](https://github.com/OpenScienceLab/AFMReader) for file I/O and
numpy/scipy for analysis.

---

## Module layout

```
science_cli/library/afm/
├── models.py       # AfmData dataclass
├── loader.py       # load_afm(), list_channels(), internal helpers
├── analyze.py      # compute_roughness(), height_distribution(),
│                   # line_profile(), compute_psd(), internal helpers
```

Plotting functions live separately in `science_cli/plot/afm.py` (see
[Cross-reference](#cross-reference) below).

---

## `afm/models.py` — `AfmData`

```python
@dataclass
class AfmData:
    image: np.ndarray
    pixel_to_nm: float
    channels: list[str]
    filepath: str
    metadata: dict
```

| Field | Type | Description |
|---|---|---|
| `image` | `np.ndarray` | 2-D height map (or 3-D for multi-frame formats). |
| `pixel_to_nm` | `float` | Spatial calibration in nm per pixel. |
| `channels` | `list[str]` | Channel names discovered in the source file. |
| `filepath` | `str` | Path to the original AFM file. |
| `metadata` | `dict` | Raw metadata dict returned by AFMReader. |

Returned by `load_afm()` and consumed directly by the analyze & plot
functions.

---

## `afm/loader.py` — Loading

### `load_afm(filepath, channel=None)`

```python
def load_afm(filepath: str, channel: str | None = None) -> AfmData
```

Primary entry point for reading AFM/SPM files. Delegates to
`AFMReader.general_loader.LoadFile` which auto-detects format from the file
extension. Supported extensions (from AFMReader):

| Extension | Format |
|---|---|
| `.gwy` | Gwyddion native |
| `.spm` | Veeco / Bruker NanoScope |
| `.ibw` | WaveMetrics Igor Binary |
| `.jpk` | JPK NanoWizard |
| `.stp` | STP (Scanning Tunneling) |
| `.top` | TopoMetrix / generic topography |

**Parameters:**

- **`filepath`** — Path to the AFM file.
- **`channel`** — Optional channel name or index to load. The default
  (`None`) selects the first available channel.

**Returns:** An `AfmData` instance.

**Raises:**

- `FileNotFoundError` if the file does not exist.
- `ImportError` if AFMReader is not installed (with install hint).
- `ValueError` if the format is unsupported or the channel is not found.

**Example:**

```python
from science_cli.library.afm import load_afm

data = load_afm("sample.gwy", channel="Height")
# data.image -> 2-D np.ndarray
# data.pixel_to_nm -> e.g. 0.78
```

---

### `list_channels(filepath)`

```python
def list_channels(filepath: str) -> list[str]
```

Discover available channels without loading the full image data. Internally
calls `LoadFile()` on the file and extracts channel names from its metadata
or data shape.

**Returns:** A list of channel name strings (e.g. `["Height", "Amplitude",
"Phase"]`).

---

### Internal helpers (not exported)

```python
def _extract_pixel_to_nm(
    metadata: dict, img_data: np.ndarray | list
) -> float
```

Resolves the spatial calibration from a priority list of metadata keys:

1. `pixel_to_nm`, `pixel_size_nm`, `pixel_to_nm_x`, `pixel_size_x_nm`,
   `Pixel size`
2. Derivation from `scan_size_nm` / image dimension
3. Fallback — returns `1.0`

```python
def _extract_channels(
    metadata: dict, img_data: np.ndarray | list
) -> list[str]
```

Reads `channels`, `channel_names`, or `data_names` from metadata. If the
metadata lacks these keys, infers names from the shape of `img_data`
(mono-channel = `["Height"]`, list = `["Channel 0", …]`, 3-D =
`["Frame 0", …]`).

```python
def _select_channel(
    img_data: np.ndarray | list,
    metadata: dict,
    channel: str | None,
) -> np.ndarray
```

Indexes into multi-channel AFMReader output by name or integer index.
Raises `ValueError` if the requested channel does not exist.

---

## `afm/analyze.py` — Analysis

### `compute_roughness(image, px_to_nm=1.0)`

```python
def compute_roughness(
    image: np.ndarray, px_to_nm: float = 1.0
) -> dict
```

Calculates standard ISO 25178 surface roughness parameters.

| Parameter | Formula |
|---|---|
| **Ra** (arithmetic mean roughness) | $\frac{1}{N} \sum \|z_i - \bar{z}\|$ |
| **Rq** (root-mean-square roughness) | $\sqrt{\frac{1}{N} \sum (z_i - \bar{z})^2}$ |
| **Rmax** (peak-to-valley) | $\max(z) - \min(z)$ |
| **Rsk** (skewness) | $\frac{m_3}{Rq^3}$ where $m_3 = \frac{1}{N} \sum (z_i - \bar{z})^3$ |
| **Rku** (kurtosis) | $\frac{m_4}{Rq^4}$ where $m_4 = \frac{1}{N} \sum (z_i - \bar{z})^4$ |
| **Sdr** (surface area ratio, %) | See `_surface_area_ratio()` below |

**Returns** a dict with keys:

```
{
    "Ra_nm": float, "Rq_nm": float, "Rmax_nm": float,
    "Rsk": float, "Rku": float, "Sdr": float,
    "n_pixels": int
}
```

Returns `{"error": …}` if fewer than 9 valid (non-NaN) pixels exist.

---

### `height_distribution(image, bins=100)`

```python
def height_distribution(
    image: np.ndarray, bins: int = 100
) -> tuple[np.ndarray, np.ndarray]
```

Flattens the height map, discards NaN values, and computes a histogram via
`np.histogram`.

**Returns:** `(hist, bin_edges)` — two numpy arrays suitable for plotting
with `plot_afm_height_distribution()`.

---

### `line_profile(image, start, end)`

```python
def line_profile(
    image: np.ndarray,
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]
```

Extracts a cross-sectional height profile between two pixel coordinates.
Uses bilinear interpolation (via `_interpolate()`) to sample `length` evenly
spaced points along the line, where `length = hypot(Δrow, Δcol)`.

**Parameters:**

- **`start`** — `(row, col)` of the starting pixel.
- **`end`** — `(row, col)` of the ending pixel.

**Returns:** `(distances_px, heights)` — two 1-D numpy arrays. Distances are
in pixel units relative to the start point.

---

### `compute_psd(image, px_to_nm=1.0)`

```python
def compute_psd(
    image: np.ndarray, px_to_nm: float = 1.0
) -> tuple[np.ndarray, np.ndarray]
```

Power spectral density via 2-D FFT with radial averaging. Processing
pipeline:

1. **NaN fill** — replace missing values with the image mean.
2. **Detrend** — subtract a least-squares 2-D plane (linear ramp removal).
3. **Window** — multiply by a 2-D Hanning (Hann) window to reduce spectral
   leakage.
4. **FFT** — `np.fft.fft2` → shift → magnitude squared.
5. **Radial average** — average over concentric rings around the DC
   component. Zero-frequency and empty bins are discarded.

**Returns:** `(spatial_frequency_nm, power_density)` — 1-D numpy arrays.

Spatial frequency is in nm⁻¹; power density is in nm⁴ (height² × area).

---

### Internal helpers (not exported)

```python
def _interpolate(
    img: np.ndarray, rows: np.ndarray, cols: np.ndarray
) -> np.ndarray
```

Standard bilinear interpolation. For each query point `(rows[i], cols[i])`,
interpolates from the four enclosing pixel values. Clamps to image
boundaries. Used by `line_profile()`.

```python
def _surface_area_ratio(image: np.ndarray, px_to_nm: float) -> float
```

Computes the developed interfacial area ratio **Sdr** (%):

$$Sdr = \frac{A_{rough} - A_{flat}}{A_{flat}} \times 100$$

where each facet area is $\sqrt{dx^2 + dz_x^2} \cdot \sqrt{dy^2 + dz_y^2}$.
Uses forward finite differences for $dz_x$, $dz_y$. Called internally by
`compute_roughness()`.

---

## Cross-reference

### `science_cli.plot.afm`

| Function | Corresponding analysis function | Purpose |
|---|---|---|
| `plot_afm_image(image, px_to_nm, …)` | — | Colour-map render of the height map |
| `plot_afm_line_profile(distances, heights)` | `line_profile()` | 1-D line plot |
| `plot_afm_height_distribution(hist, bin_edges)` | `height_distribution()` | Histogram bar plot |
| `plot_afm_psd(freq, power)` | `compute_psd()` | Log-log PSD plot |

Each plotting function accepts an optional `ax: Axes | None` parameter for
integration with multi-panel figures.

### Dependencies

- **AFMReader** (`>=0.0.7`) — required runtime dependency for file loading.
  Not needed for pure analysis (roughness, PSD) if data is already loaded.
- **numpy** — shared numeric dependency.

---

## Usage example

```python
from science_cli.library.afm import load_afm, compute_roughness, compute_psd
from science_cli.plot.afm import plot_afm_image, plot_afm_psd

# Load
data = load_afm("film_topography.gwy", channel="Height")

# Roughness
rough = compute_roughness(data.image, data.pixel_to_nm)
print(f"Ra = {rough['Ra_nm']:.2f} nm, Rq = {rough['Rq_nm']:.2f} nm")

# PSD
freq, psd = compute_psd(data.image, data.pixel_to_nm)

# Plot
import matplotlib.pyplot as plt
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
plot_afm_image(data.image, data.pixel_to_nm, ax=ax1)
plot_afm_psd(freq, psd, ax=ax2)
plt.show()
```
