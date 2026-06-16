# IV Analysis Library — Internal API Reference

Module: `science_cli.library.iv`

Six sub-modules for memristor / electrochemical IV data analysis: switching metrics, volatile/bipolar statistics, Weibull distributions, sweep-level extraction (resistance, scan rate, breakdown, curve fitting), and publication-quality SVG plotting.

---

## `metrics.py` — Switching Detection & Parameter Extraction

Core detection algorithms for memristor V_set / V_reset and ON/OFF ratio computation.

```python
def detect_vset(voltage, current, v_read=0.1) -> tuple[float | None, int | None]
```
Detect V_set using a three-tier strategy on the forward sweep segment (0 → +Vmax):

1. **SCLC Log-Log slope** — computes `d(log|I|)/d(log|V|)` in the positive-bias region (`|V| ≥ 0.05 V`). Plateau regions where slope ≥ 3.0 are scored by `plateau_length × max_slope × log10(I_at_start / I_baseline)`. The highest-scoring plateau determines V_set. This is the primary method.
2. **Derivative maximum** — fallback: `argmax(d(log|I|)/dV)` over the segment.
3. **Current threshold** — fallback: first point exceeding 10× median baseline current.

Returns `(V_set, global_index)` or `(None, None)` if no event is detected. Requires ≥10 clean data points and a current dynamic range ≥10× over baseline.

```python
def detect_vreset(voltage, current, v_read=0.1) -> tuple[float | None, int | None]
```
Detect V_reset on the negative sweep segment (→ −Vmax). Two-tier strategy:

1. **Derivative minimum** — `argmin(d(log|I|)/dV)` identifies the sharpest current drop.
2. **Current threshold** — first point where `|I|` drops below 30% of the segment baseline.

Returns `(V_reset, global_index)` or `(None, None)`.

```python
def compute_on_off_ratio(voltage, current, v_read=0.1) -> dict
```
Compute memristor ON/OFF resistance ratio from a bipolar sweep. Splits the trace at voltage reversals, identifies the forward branch (rising voltage) and backward branch (falling voltage). Interpolates `|I|` at `v_read` on each branch:

- **i_off** — forward-branch current at `v_read` (HRS / pristine state).
- **i_on** — backward-branch current at `v_read` (LRS / programmed state).

Returns `{v_read, i_on, i_off, r_on, r_off, ratio}`. Any field is `None` if the corresponding branch is missing or insufficiently sampled.

```python
def extract_iv_parameters(voltage, current, v_read=0.1) -> dict
```
Combined extraction: calls `detect_vset()`, `detect_vreset()`, and `compute_on_off_ratio()`, then attaches the switching-current values via `_current_at_voltage()`. Returns a flat dict with keys `{v_set, v_reset, v_set_idx, v_reset_idx, i_set, i_reset, on_off_ratio, v_read, i_on, i_off, r_on, r_off, switching_detected}`.

```python
def _split_at_reversals(voltage, hysteresis=0.1) -> list[tuple[int, int]]
```
Split a voltage array into monotonic segments by detecting direction changes. A reversal is registered when the accumulated opposite-direction drift exceeds `hysteresis` (volts). Returns `[(start, end), ...]` index pairs.

```python
def _current_at_voltage(v_target, voltage, current) -> float | None
```
Return the current value at the index closest to `v_target` in the voltage array. Returns `None` if target is `None`.

---

## `volatile.py` — Volatile Memristor Analysis

Volatile devices exhibit V_set with no V_reset (one-directional, threshold switching).

```python
def analyze_volatile(v_set_values, on_off_ratios=None, compliance=None) -> dict
```
Compute switching statistics from an array of V_set voltages:

- `n_events`, `v_set_mean`, `v_set_std`, `v_set_min`, `v_set_max`, `v_set_cv`
- `on_off_ratio_mean / std / median` (if `on_off_ratios` provided)
- `compliance` (if provided)
- `"error"` key and `n_events: 0` if input is empty.

```python
def volatile_summary(analysis: dict) -> str
```
Human-readable multiline string: number of events, mode, V_set statistics (±stdev, range, CV), and ON/OFF ratio.

```python
def analyze_volatile_to_yaml(v_set_values, step_dir: Path, on_off_ratios=None, compliance=None, instrument="", devices="") -> Path
```
Wraps `analyze_volatile()` and writes the result via `write_analysis_yaml(technique="iv-sweep", ...)` (see `core/analysis_output.py`). Returns the path to `<step_dir>/results/iv-sweep_analysis.yaml`. The output dict structure:

```yaml
analysis:
  mode: volatile
  parameters:
    v_set: <mean>
    v_set_std: ...
    v_set_cv: ...
    v_set_min/max: ...
    on_off_ratio: ...
    compliance: ...
    set_yield: <n_events / len(v_set_values) * 100>
  n_events: ...
```

---

## `bipolar.py` — Bipolar Junction Analysis

Bipolar devices exhibit both V_set (forward sweep) and V_reset (reverse sweep).

```python
def analyze_bipolar(v_set_values, v_reset_values, on_off_ratios=None, hysteresis_areas=None) -> dict
```
Compute paired switching statistics:

- `n_events`, `v_set_mean / std / cv`, `v_reset_mean / std / cv`
- `on_off_ratio_mean / std` (if provided)
- `hysteresis_area_mean / std` (if provided).

```python
def bipolar_summary(analysis: dict) -> str
```
Human-readable string: event count, V_set ±stdev, V_reset ±stdev, ON/OFF ratio, hysteresis area.

```python
def analyze_bipolar_to_yaml(v_set_values, v_reset_values, step_dir: Path, on_off_ratios=None, hysteresis_areas=None, instrument="", devices="") -> Path
```
Wraps `analyze_bipolar()` → `write_analysis_yaml(technique="iv-sweep")`. Output:

```yaml
analysis:
  mode: bipolar
  parameters:
    v_set: <mean>
    v_set_std: ...
    v_reset: <mean>
    v_reset_std: ...
    on_off_ratio: ...
    hysteresis_area: ...
  n_events: ...
```

---

## `switching.py` — Weibull Distribution Fits

```python
def analyze_switching_statistics(v_set_values, v_reset_values) -> dict
```
Compute means, standard deviations, and **Weibull_min fits** for the V_set and V_reset distributions (requires `scipy.stats`). Fits `weibull_min.fit(|V|, floc=0)` on positive-valued entries. Returns:

- `v_set_mean / std`, `v_reset_mean / std`, `n_set`, `n_reset`
- `weibull_set: {V0, beta}` (scale `V0`, shape `β`) or `None` if `< 3` data points
- `weibull_reset: {V0, beta}` or `None`.

Re-exports `detect_vset`, `detect_vreset`, `compute_on_off_ratio`, `extract_iv_parameters` from `metrics.py` for convenience.

---

## `analyze.py` — Sweep-Level Extraction & Curve Fitting

Per-sweep analysis: resistance, scan rate, breakdown voltage, conduction-model fitting, ON/OFF ratio, segment detection.

```python
def extract_resistance(voltage: np.ndarray, current: np.ndarray, window: float = 0.1) -> dict
```
Linear fit (`polyfit` degree-1) in the `±window` V region for Ohmic resistance. Returns `{resistance, resistance_stderr, slope, intercept, r_squared, n_points}`. If `< 3` points in window or zero slope, returns with `error` string and `None` values.

```python
def extract_scan_rate(voltage: np.ndarray, current: np.ndarray, time: np.ndarray | None = None) -> dict
```
Estimate scan rate in V/s. With time data: `ΔV / Δt` from first to last voltage extremum. Without time: heuristic using voltage range divided by `(n_inflection_points + 1)`, where inflection points are sign changes in the voltage derivative. Returns `{scan_rate_v_s, voltage_range, n_sweeps}`.

```python
def extract_breakdown_voltage(voltage: np.ndarray, current: np.ndarray, threshold_current: float = 1e-6) -> dict
```
Find the first point where `|I| > threshold_current`. Returns `{breakdown_voltage, breakdown_current, breakdown_index, threshold_a}`. If no point exceeds threshold, returns with `error` string.

```python
def fit_iv_curve(voltage: np.ndarray, current: np.ndarray, model: str = "ohmic") -> dict
```
Fit IV data using one of four conduction models (via `numpy.polyfit`, no lmfit required):

| Model | Equation | Region | Fit |
|-------|----------|--------|-----|
| `"ohmic"` | I = V/R | `\|V\| < 0.1 V` | polyfit(V, I, 1) → R = 1/slope |
| `"schottky"` | ln(I) ∝ √V | V > 0.1 V | polyfit(√V, ln\|I\|, 1) |
| `"sclc"` | log(I) ∝ n·log(V) | V > 0, I > 0 | polyfit(log V, log I, 1) → n exponent; interpretation: Ohmic (n<1.3), Transition (1.3–1.7), SCLC trap-filled (n>1.7) |
| `"pool-frenkel"` | ln(I/V) ∝ √V | V > 0.1 V | polyfit(√V, ln(I/V), 1) |

Each fit returns `{model, params, metrics: {r_squared, rmse, aic, bic}, success}`. Fails with `error` if insufficient points. Internal helpers: `_fit_ohmic()`, `_fit_schottky()`, `_fit_sclc()`, `_fit_pool_frenkel()`.

```python
def extract_on_off_ratio(voltage: np.ndarray, current: np.ndarray, read_voltage: float = 0.1) -> dict
```
Alternative ON/OFF ratio: finds the points closest to `+read_voltage` (I_on) and `-read_voltage` (|I_off|). Returns `{on_off_ratio, I_on_A, I_off_A, V_read, V_on_actual, V_off_actual}`.

```python
def detect_sweep_segments(voltage: np.ndarray, time: np.ndarray | None = None, min_segment_points: int = 5) -> list[dict]
```
Detect sweep segments by finding voltage direction reversals via sign changes of `diff(V)`. Optionally splits segments at zero-crossings if both halves exceed `min_segment_points`. Each segment dict:

```python
{start_idx, end_idx, direction: "forward"|"reverse", sweep_rate_v_s, voltage_range, duration_s}
```

---

## `plotting.py` — SVG Generation

File I/O and matplotlib-based SVG/PDF generation with ACS and Nature styling.

### Data Readers

```python
def read_iv_csv(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict]
```
Parse IV data CSV. Detects column conventions: `Time,BI,BV` (Keysight B1500A), `Time,Current,Voltage`, `Voltage (V), Current (A)`. Falls back to LabVIEW LVM parser if first line contains `"LabVIEW Measurement"`. Strips instrument metadata lines, extracts Clarius+ metadata (`_parse_clarius_metadata()`). Returns `(voltage, current, info)` where `info` includes detected column names, point count, skipped lines, optional time array, and first/last timestamps.

```python
def read_iv_lvm(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict]
```
Parse tab-separated LabVIEW Measurement file with two-block header delimited by `***End_of_Header***`. Column mapping: col1=Voltage, col2=Current, col3=Timestamp (optional), col4=Comment. Extracts metadata (Date, Operator, Channels, Samples). Returns same type signature as `read_iv_csv`.

```python
def _parse_clarius_metadata(rows: list[list[str]]) -> dict
```
Extract Keysight B1500A sweep configuration from metadata rows: `start_v`, `stop_v`, `step_v`, `n_points`, `compliance`, `dual_sweep_enabled`, `operation_mode`, `sweep_delay_s`, `hold_time_s`, `speed`, `sweep_rate_approx`.

### Scale / Segmentation Helpers

```python
def _should_use_log_scale(current: np.ndarray) -> bool
```
Returns `True` if `max(|I|) / min(|I|) > 100` (dynamic range heuristic).

```python
def _split_at_reversals(voltage: np.ndarray, hysteresis: float = 0.1) -> list[tuple[int, int]]
```
Identical logic to `metrics._split_at_reversals()` — local copy to avoid circular imports.

### Plotting Core

```python
def generate_iv_svg(voltage: np.ndarray, current: np.ndarray, metadata: dict, output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None)
```
Generate a publication-style IV curve SVG. **ACS style** (default): sans-serif font, no grid, inward ticks on all four axes, black lines (lw=0.8), legend without frame. **Nature style** (time-colored, when `time` in metadata): turbo colormap via `LineCollection`, open spines, colorbar for time.

Sweep metadata is used to build the plot title via `build_plot_title()`. Handles three plot types:

- **Time-colored** — if `time` array present and matches voltage length.
- **Bipolar** — if `sweep_type == "f"`, splits at reversals and plots forward (solid) / reverse (dashed) separately.
- **Simple** — single monotonic trace.

```python
def generate_iv_overlay_svg(traces: list[tuple[np.ndarray, np.ndarray, dict]], output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None)
```
Overlay multiple IV traces on one plot. Each trace gets a distinct color. Bipolar traces use `_plot_bipolar_sweep`, simple traces use `_plot_simple_sweep`.

```python
def generate_iv_highlighted_svg(traces: list[tuple[np.ndarray, np.ndarray, dict]], highlight_cycles: list[int], output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None)
```
Nature-quality overlay with specific cycles highlighted. Non-highlighted traces plot in light grey (`#E0E0E0`, α=0.08). Highlighted cycles get distinct colors from the Nature Research discrete palette. Figure size: 3.46×2.75 in. Open spines, scientific notation on y-axis (linear only).

### Title Building

```python
def build_plot_title(order: int, sweep: list[dict], sweep_type: str) -> str
```
Assemble title as `#N  |  X.XX V/s  |  direction_path`. Calls `_extract_sweep_annotations()`.

```python
def _extract_sweep_annotations(sweep: list[dict]) -> dict
```
Return `{sweep_rate, direction, voltage_range, duration}` from sweep segment metadata. Direction string is a `->`-joined path of start/end voltages or voltage range targets.

```python
def _build_sweep_from_data(voltage: np.ndarray, time: np.ndarray | None = None) -> list[dict]
```
Fallback metadata builder when no stored sweep segments exist. Detects voltage jumps (`> 1 V`) to find the sweep boundary, then extracts segments via `_split_at_reversals()`.

### Plot Internals

```python
def _plot_simple_sweep(ax, voltage, current, use_log: bool, order: int, file_index: int = 0, color=None, **kwargs)
```
Single-trace IV plot. Line style cycles through `_LINE_COLORS` / `_LINE_STYLES`.

```python
def _plot_bipolar_sweep(ax, voltage, current, use_log: bool, order: int, file_index: int = 0, color=None, **kwargs)
```
Bipolar trace: forward sweep in primary color (solid), reverse sweep in `#888888` (dashed).

```python
def _plot_time_colored_iv(ax, voltage, current, time, use_log: bool, order: int)
```
Time-colored V-I curve using `matplotlib.collections.LineCollection` with turbo colormap and colorbar.

```python
def _apply_figure_kw(ax, flags: dict, title_default: str = "")
```
Apply runtime overrides from a flags dict: `title`, `xlim`, `ylim`, `xlabel`, `ylabel`, `fontsize`, `grid`, `xscale`, `yscale`, `legend`.

---

## Cross-Reference: `core/analysis_output.py`

```python
def write_analysis_yaml(technique: str, step_dir: Path, analysis_results: dict, instrument: str = "", devices: str = "") -> Path
```
Universal YAML writer used by `analyze_volatile_to_yaml()` and `analyze_bipolar_to_yaml()`. Writes to `<step_dir>/results/<technique>_analysis.yaml` with envelope:

```yaml
technique: iv-sweep
instrument: <instrument>
devices: <devices>
timestamp: 2026-06-15T12:00:00Z
analysis:
  ...  # technique-specific results
```

Optionally validates `analysis_results` against a per-technique schema registered in `science_cli.analysis.validators.SCHEMA_VALIDATORS`.
