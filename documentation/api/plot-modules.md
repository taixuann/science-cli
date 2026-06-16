# Plot Engine — Internal API Reference

**Source:** `src/science_cli/plot/`
**Purpose:** matplotlib-based plotting for electrochemistry (CV, CA, EIS) and AFM/SPM techniques, with a theme system and overlay support.

---

## Architecture Overview

```
plot/
├── base.py          ← **CANONICAL** — all figure/save/plot utilities
├── __init__.py      ← Re-exports + thin wrappers (see Canonical Caveat)
├── cv.py            ← Cyclic voltammetry (I vs E)
├── ca.py            ← Chronoamperometry (I vs t)
├── eis.py           ← EIS (Nyquist, Bode, fit overlay)
├── afm.py           ← AFM/SPM (topography, line profile, histogram, PSD)
└── overlays.py      ← Multi-curve overlay with theme-aware color cycling
```

### Canonical Caveat

**`base.py` is canonical.** `__init__.py` re-exports all public functions from `base.py` but **duplicates** several by value (`setup_backend`, `create_figure`, `apply_figure_kw`, `parse_figsize`, `save_figure`) with differences:

| Function | `base.py` (canonical) | `__init__.py` (duplicate) |
|---|---|---|
| `parse_figsize` | Returns `None` when no size flag | Returns `(6.4, 4.8)` default |
| `save_figure` | Simple ext logic | Additional ext parsing from `flags["n"]` |
| Others | Identical | Identical |

All technique modules import from `base.py`, not `__init__.py`. Change `base.py` first.

### Theme Application

All plotters use `science_cli.theme`:
- `apply_theme(name: str)` — loads YAML theme from `theme/plot-theme/`, applies via `mpl.rcParams.update()`
- `get_theme(name: str)` — returns raw theme dict (used by `overlays.py` for color cycling)
- `theme_to_rcparams(name: str)` — converts theme YAML → rcParams dict
- `template_to_flags(technique: str)` — loads technique template YAML → flags dict

Built-in themes: `default`, `tufte`, `dark`, `publication-acs`, `publication-nature`, `poster`.

---

## `base.py` — Core Utilities

### `setup_backend(interactive: bool = False)`

Set matplotlib backend. When `interactive=False` (default), switches to `"Agg"` for headless generation.

```python
def setup_backend(interactive: bool = False):
    if not interactive:
        matplotlib.use("Agg")
```

### `create_figure(theme: str = "publication-nature", figsize: tuple | None = None) -> tuple`

Create `(fig, ax)` with theme applied via `apply_theme(theme)`, then `plt.subplots(figsize=figsize)`.

```python
def create_figure(theme: str = "publication-nature", figsize: tuple | None = None) -> tuple:
    apply_theme(theme)
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax
```

### `apply_figure_kw(ax, flags: dict, title_default: str = "")`

Apply CLI-parsed keyword flags to an Axes:

| Key | Effect |
|---|---|
| `title` | `ax.set_title(flags["title"])` |
| `xlabel` / `ylabel` | `ax.set_xlabel/label(…)` |
| `xlim` / `ylim` | `ax.set_xlim/ylim(*map(float, "min,max".split(",")))` |
| `xscale` / `yscale` | `ax.set_xscale/yscale(…)` |
| `grid` | `ax.grid(True, alpha=0.3)` |
| `legend` | `ax.legend()` |

### `parse_figsize(flags: dict) -> tuple | None`

Extract `(width, height)` from `flags["size"]` string `"width,height"`. Returns `None` when absent.

```python
def parse_figsize(flags: dict) -> tuple | None:
    size = flags.get("size", "")
    if size:
        try:
            parts = str(size).split(",")
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return None
```

### `save_figure(fig, output_dir: Path, stem: str, flags: dict) -> Path`

Save figure to disk. Creates `output_dir` if needed. Filename from `flags["n"]` / `flags["name"]` or `f"{stem}.png"`. DPI from `flags["dpi"]` (default 300). `bbox_inches="tight"`.

```python
def save_figure(fig, output_dir: Path, stem: str, flags: dict) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = flags.get("n") or flags.get("name") or f"{stem}.png"
    save_path = output_dir / name
    dpi = int(flags.get("dpi", 300))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    return save_path
```

### `plot_line(x, y, ax=None, flags: dict | None = None, label: str = "") -> tuple`

Generic line plot. Creates figure with `create_figure(flags.get("theme", "publication-nature"))` if `ax is None`.

| Flag key | Effect | Default |
|---|---|---|
| `color` | Line colour | rcParams |
| `linewidth` | Line width | `1.5` |
| `linestyle` | Line style (`"-"`, `"--"`, etc.) | `"-"` |
| `marker` | Marker style (`"o"`, `"s"`, etc.) | None (no markers) |
| `markersize` | Marker size | `6` |

### `plot_scatter(x, y, ax=None, flags: dict | None = None, label: str = "") -> tuple`

Generic scatter plot. Creates figure with `create_figure(flags.get("theme", "default"))` if `ax is None`.

| Flag key | Effect | Default |
|---|---|---|
| `color` | Marker colour (`c`) | rcParams |
| `markersize` | Marker area (`s`) | `36` |
| `marker` | Marker shape | `"o"` |
| `cmap` | Colormap for colour mapping | None |

Alpha is hard-coded to `0.8`.

---

## `cv.py` — Cyclic Voltammetry

### `plot_cv_curve(potential, current, flags=None, label="", ax=None) -> (Figure, Axes)`

Single CV cycle via `plot_line`. Auto-labels: `"Potential (V)"`, `"Current (A)"`.

| Param | Type | Description |
|---|---|---|
| `potential` | `np.ndarray` | Applied potential sweep (x-axis) |
| `current` | `np.ndarray` | Measured current response (y-axis) |
| `flags` | `dict \| None` | Theme defaults to `"publication-nature"` |
| `label` | `str` | Legend label |
| `ax` | `Axes \| None` | Existing axes or create new |

### `plot_cv_overlay(curves: list[dict], flags=None) -> (Figure, Axes)`

Multiple CV curves on shared axes. Each curve dict: `{"x": ndarray, "y": ndarray, "label": str}`. Auto-enables legend.

### `plot_cv_with_peaks(potential, current, peaks=None, flags=None, label="") -> (Figure, Axes)`

CV with peak potential markers. `peaks` format:
```python
peaks = {
    "anodic_peaks": [{"potential": 0.5, "current": 1e-4}, ...],
    "cathodic_peaks": [{"potential": -0.3, "current": -8e-5}, ...],
}
```
Anodic peaks: red `"v"` triangles. Cathodic peaks: blue `"^"` triangles.

---

## `ca.py` — Chronoamperometry

### `plot_ca_decay(time, current, flags=None, label="", ax=None) -> (Figure, Axes)`

Current decay vs time. Uses `plot_line`. Auto-labels: `"Time (s)"`, `"Current (A)"`. Forces linear x-scale unless overridden in flags. Theme defaults to `"publication-nature"`.

| Param | Type | Description |
|---|---|---|
| `time` | `np.ndarray` | Time axis (seconds) |
| `current` | `np.ndarray` | Current response (amperes) |
| `flags` | `dict \| None` | Keyword flags |
| `label` | `str` | Legend label |
| `ax` | `Axes \| None` | Existing axes or create new |

### `plot_ca_cottrell(time, current, fit_x=None, fit_y=None, flags=None, label="") -> (Figure, Axes)`

Cottrell plot: `I` vs `t^{-1/2}`. Data rendered as scatter (`s=8`, `alpha=0.6`). Optional fit overlay as red solid line. Auto-label: `"t^{-1/2} (s^{-1/2})"`. Theme defaults to `"default"`.

| Param | Type | Description |
|---|---|---|
| `time` | `np.ndarray` | Raw time values (inverted internally) |
| `current` | `np.ndarray` | Raw current values |
| `fit_x` | `np.ndarray \| None` | Fitted x values (t^{-1/2}) |
| `fit_y` | `np.ndarray \| None` | Fitted y values (current) |
| `flags` | `dict \| None` | Keyword flags |
| `label` | `str` | Legend label |

Auto-sets x-label to `"t^{-1/2} (s^{-1/2})"` and y-label to `"Current (A)"` unless overridden.

---

## `eis.py` — Electrochemical Impedance Spectroscopy

### Internal: `_ensure_neg_imag(z_imag: np.ndarray) -> np.ndarray`

Normalise to `-Z''` (positive-upward). Negates if min value < 0 (raw `Z''` from instruments that report negative capacitive values).

### `plot_eis_nyquist(z_real, z_imag, flags=None, label="", ax=None) -> (Figure, Axes)`

Nyquist: `-Z''` vs `Z'`. Calls `_ensure_neg_imag()` to normalise sign convention. Enforces equal aspect ratio. Auto-labels: `"Z' (Ω)"`, `"-Z'' (Ω)"`. Theme defaults to `"publication-nature"`.

| Param | Type | Description |
|---|---|---|
| `z_real` | `np.ndarray` | Real impedance |
| `z_imag` | `np.ndarray` | Imaginary impedance (raw, auto-normalised) |
| `flags` | `dict \| None` | Keyword flags |
| `label` | `str` | Legend label |
| `ax` | `Axes \| None` | Existing axes or create new |

### `plot_eis_bode(frequency, magnitude, phase=None, flags=None) -> (Figure, Axes)`

Bode plot with dual y-axes. Magnitude on primary axis (log-log, default colour `#2563eb`). Optional phase on secondary `twinx` axis (default colour `#dc2626`). Grid on both axes. Returns `(fig, ax1)` where `ax1` is the magnitude axis.

| Param | Type | Description |
|---|---|---|
| `frequency` | `np.ndarray` | Frequency in Hz |
| `magnitude` | `np.ndarray` | Impedance magnitude `\|Z\|` in Ω |
| `phase` | `np.ndarray \| None` | Phase angle in degrees |
| `flags` | `dict \| None` | Keyword flags |

### `plot_eis_fit(z_real, z_imag, fit_real, fit_imag, flags=None) -> (Figure, Axes)`

Nyquist overlay of data + fitted curve. Data via `plot_line`, fit styled as red dashed `"--"`. Both normalised through `_ensure_neg_imag()`. Equal aspect, auto legend. Theme defaults to `"default"`.

| Param | Type | Description |
|---|---|---|
| `z_real` | `np.ndarray` | Measured real impedance |
| `z_imag` | `np.ndarray` | Measured imaginary impedance |
| `fit_real` | `np.ndarray` | Fitted real impedance |
| `fit_imag` | `np.ndarray` | Fitted imaginary impedance |
| `flags` | `dict \| None` | Keyword flags |

---

## `afm.py` — AFM / SPM

All AFM plotters return `Axes` (not `(Figure, Axes)`). No theme integration — hard-coded styling.

### `plot_afm_image(image, px_to_nm=1.0, cmap="viridis", title="", ax=None) -> Axes`

2D height map rendered via `imshow` with colorbar. Extent computed as `[0, w * px_to_nm, h * px_to_nm, 0]`.

| Param | Type | Default | Description |
|---|---|---|---|
| `image` | `np.ndarray` | — | 2D height map (rows × cols) |
| `px_to_nm` | `float` | `1.0` | Spatial calibration (nm per pixel) |
| `cmap` | `str` | `"viridis"` | Matplotlib colormap |
| `title` | `str` | `""` | Optional plot title |
| `ax` | `Axes \| None` | `None` | Existing axes or create new |

### `plot_afm_line_profile(distances, heights, ax=None) -> Axes`

1D line profile. Black line (`linewidth=1.0`). `figsize=(6, 3)`. Labels: `"Distance (pixels)"`, `"Height (nm)"`. Grid enabled.

| Param | Type | Description |
|---|---|---|
| `distances` | `np.ndarray` | Distance along profile |
| `heights` | `np.ndarray` | Height values |
| `ax` | `Axes \| None` | Existing axes or create new |

### `plot_afm_height_distribution(hist, bin_edges, ax=None) -> Axes`

Histogram of pixel height values as a bar chart. Bin centres computed from edges. Steelblue bars (`alpha=0.7`), black edge (`linewidth=0.5`). `figsize=(6, 3)`. Labels: `"Height (nm)"`, `"Pixel count"`.

| Param | Type | Description |
|---|---|---|
| `hist` | `np.ndarray` | Histogram counts |
| `bin_edges` | `np.ndarray` | Bin edge positions |
| `ax` | `Axes \| None` | Existing axes or create new |

### `plot_afm_psd(freq, power, ax=None) -> Axes`

Power spectral density on log-log axes. Black line (`linewidth=1.0`). Grid on both major and minor ticks. `figsize=(6, 3)`. Labels: `"Spatial frequency (nm⁻¹)"`, `"PSD (nm⁴)"`.

| Param | Type | Description |
|---|---|---|
| `freq` | `np.ndarray` | Spatial frequency (nm⁻¹) |
| `power` | `np.ndarray` | Power density (nm⁴) |
| `ax` | `Axes \| None` | Existing axes or create new |

---

## `overlays.py` — Multi-Curve Overlay

### `plot_overlay(curves: list[dict], flags=None) -> (Figure, Axes)`

Multi-curve overlay with theme-aware color cycling. Reads `get_theme()["colors"]["prop_cycle"]` (falls back to 8-color palette). Each curve: `{"x", "y", "label"}`. Colors wrap if curves exceed palette size. Auto-enables legend. Theme defaults to `"publication-nature"`.

---

## `__init__.py` — Re-exports

Re-exports all public functions (with `# noqa: F401`):

```python
# Base: setup_backend, create_figure, apply_figure_kw, parse_figsize, save_figure
#       plot_line, plot_scatter
# CV:   plot_cv_curve, plot_cv_overlay, plot_cv_with_peaks
# CA:   plot_ca_decay, plot_ca_cottrell
# EIS:  plot_eis_nyquist, plot_eis_bode, plot_eis_fit
# AFM:  plot_afm_image, plot_afm_line_profile, plot_afm_height_distribution, plot_afm_psd
# OL:   plot_overlay
```

Also duplicates `setup_backend`, `create_figure`, `apply_figure_kw`, `parse_figsize`, `save_figure` by value (see [Canonical Caveat](#canonical-caveat)). Prefer importing from `base.py` in new code.

---

## Adding a New Plot Module

1. Create `plot/<technique>.py`. Import helpers from `science_cli.plot.base` (`create_figure`, `apply_figure_kw`, `save_figure`, `parse_figsize`, `plot_line`, `plot_scatter`).
2. Add `from science_cli.plot.<technique> import <funcs>  # noqa: F401` in `__init__.py`.
3. Add dispatch logic in `cli/commands/plot.py`.
