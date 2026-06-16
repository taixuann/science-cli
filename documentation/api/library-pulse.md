# Pulse Analysis Library

**Module**: `science_cli.library.pulse`

Analysis routines for memristor pulse characterisation: endurance cycling, retention decay, switching time distributions, short-term plasticity (STP) decay, and paired-pulse facilitation (PPF). Built on `numpy`, `scipy.optimize`, `scipy.stats`, and `matplotlib`.

---

## Public API (`__init__.py`)

```python
from .endurance import analyze_endurance, analyze_endurance_to_yaml, endurance_summary
from .ppf import analyze_ppf, analyze_ppf_to_yaml, ppf_summary
from .retention import analyze_retention, analyze_retention_to_yaml, retention_summary
from .stp import analyze_stp_decay, analyze_stp_decay_to_yaml, stp_summary
from .switching import analyze_pulse_switching
```

---

### `ANALYZERS: dict[str, callable]`

```python
ANALYZERS = {
    "pulse-endurance": analyze_endurance,
    "pulse-retention": analyze_retention,
    "pulse-stp":       analyze_stp_decay,
    "pulse-ppf":       analyze_ppf,
    "pulse-switching": analyze_pulse_switching,
}
```

Registry used by the generic `science-cli analyze` dispatcher.

---

## Data Models (`models.py`)

### `PulseData`

```python
@dataclass
class PulseData:
    time: np.ndarray
    current: np.ndarray
    voltage: np.ndarray | None = None
    filename: str = ""
    metadata: dict = field(default_factory=dict)
```

Generic container for pulse I–V measurement traces.

---

### `EnduranceData`

```python
@dataclass
class EnduranceData:
    cycles: np.ndarray         # Cycle index
    r_on: np.ndarray           # Low-resistance state (Ohm)
    r_off: np.ndarray          # High-resistance state (Ohm)
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)
```

---

### `RetentionData`

```python
@dataclass
class RetentionData:
    time: np.ndarray           # Elapsed time (s)
    resistance: np.ndarray     # Resistance (Ohm)
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)
```

---

### `STPData`

```python
@dataclass
class STPData:
    time: np.ndarray           # Time after pulse (ms)
    current: np.ndarray        # Synaptic current (A)
    metadata: dict = field(default_factory=dict)
```

---

### `PPFData`

```python
@dataclass
class PPFData:
    intervals_ms: np.ndarray   # Inter-pulse intervals (ms)
    ratios: np.ndarray         # PPF ratio (A₂/A₁)
    metadata: dict = field(default_factory=dict)
```

---

## Endurance Analysis (`endurance.py`)

### `analyze_endurance(r_on, r_off, cycles) -> dict`

```python
def analyze_endurance(
    r_on: ArrayLike,
    r_off: ArrayLike,
    cycles: ArrayLike,
) -> dict
```

Returns: `mean_r_on`, `mean_r_off`, `mean_ratio`, `cv_r_on`, `cv_r_off` (mean and CV of each state), `failure_cycle` (first cycle where R_off/R_on < 10; `None` if no failure), `n_cycles`, `weibull_fit` (Weibull minimum fit to failure region via `scipy.stats.weibull_min.fit` — dict with `shape`, `location`, `scale`; `None` if no failure or <3 failure points), `trend_slope` / `trend_r_squared` (linear fit of R_off vs cycles via `numpy.polyfit`), `ratio_tail_mean` / `ratio_tail_std` (mean and STD of ratio in last 10 % of cycles).

### `endurance_summary(data: EnduranceData) -> str`

```python
def endurance_summary(data: EnduranceData) -> str
```

Human-readable summary. Reports R_on / R_off, CV, failure status, and R_off linear trend. Delegates to `analyze_endurance()`.

### `analyze_endurance_to_yaml(r_on, r_off, cycles, step_dir, instrument="", devices="") -> Path`

```python
def analyze_endurance_to_yaml(
    r_on: ArrayLike,
    r_off: ArrayLike,
    cycles: ArrayLike,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
) -> Path
```

Analyse endurance and write YAML via `science_cli.core.analysis_output.write_analysis_yaml()`. Technique key `"pulse-endurance"`. Writes `analysis.mode`, `analysis.parameters` (cycles_to_failure, r_high_initial, r_low_initial, cycle_to_cycle_variability_pct, n_cycles, ratio_tail_mean, ratio_tail_std), and `analysis.per_cycle_sampling`. Returns path to the written file.

---

## Retention Analysis (`retention.py`)

### `analyze_retention(time, resistance) -> dict`

```python
def analyze_retention(
    time: ArrayLike,
    resistance: ArrayLike,
) -> dict
```

Fits two models and selects the better one by R². Filters `t > 0`; requires ≥3 valid points.

- **Log-time**: $R(t) = a \cdot \log_{10}(t) + b$ via `numpy.polyfit(log10(t), R, 1)`
- **Power-law**: $R(t) = a \cdot t^b$ via `numpy.polyfit(log10(t), log(R), 1)` then exponentiated

Returns: `decay_rate` (slope of log-time fit, Ohm/decade), `decay_model` (`"log"` or `"power"`), `extrapolated_10yr` (resistance at 10 years, Ohm), `lifetime_hours` (time to ±50 % of initial R; `None` if unbounded), `r_squared`, `test_duration_hours`, `n_points`.

### `retention_summary(data: RetentionData) -> str`

Reports temperature, test duration, selected model, R², decay rate, 10-year extrapolation, and lifetime estimate.

### `analyze_retention_to_yaml(time, resistance, step_dir, instrument="", devices="") -> Path`

Technique key `"pulse-retention"`. Writes `analysis.mode`, `analysis.parameters` (decay_rate, decay_model, extrapolated_10yr, lifetime_hours, r_squared, test_duration_hours, n_points).

---

## Switching Time Analysis (`switching.py`)

### `analyze_pulse_switching(switching_times, switching_voltages=None) -> dict`

```python
def analyze_pulse_switching(
    switching_times: ArrayLike,
    switching_voltages: ArrayLike | None = None,
) -> dict
```

Flattens inputs to 1-D arrays. Returns: `t_set_mean`, `t_set_std`, `n_events`. When `switching_voltages` is provided, also returns `v_set_mean` and `v_set_std`. All numeric outputs are native Python floats.

---

## STP Decay Analysis (`stp.py`)

### `analyze_stp_decay(time, current) -> dict`

```python
def analyze_stp_decay(
    time: ArrayLike,
    current: ArrayLike,
) -> dict
```

Fits monoexponential ($A \cdot e^{-t/\tau} + I_0$) and biexponential ($A_1 e^{-t/\tau_1} + A_2 e^{-t/\tau_2} + I_0$) models via `scipy.optimize.least_squares`, selects by AIC. Requires ≥5 points. Bounds: all params ≥ 0.

Returns: `model` (`"monoexponential"` or `"biexponential"`), `tau1_ms`, `tau2_ms` (`None` for mono), `a1` / `a2` (normalised amplitudes; `None` for mono), `initial_current_ua`, `steady_state_current_ua` (median of last 20 %), `decay_pct`, `r_squared`.

### `stp_summary(analysis: dict) -> str`

```python
def stp_summary(analysis: dict) -> str
```

Formats STP analysis dict into a multi-line report: model type, initial → steady-state current, decay percentage, time constants, and R².

### `analyze_stp_decay_to_yaml(time, current, step_dir, instrument="", devices="") -> Path`

```python
def analyze_stp_decay_to_yaml(
    time: ArrayLike,
    current: ArrayLike,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
) -> Path
```

Technique key `"pulse-stp"`. Uses `_to_native()` helper to convert numpy scalars. Writes `analysis.mode`, `analysis.decay_fit` (model, tau1_ms, tau2_ms, a1, a2, r_squared), `analysis.parameters` (initial_current_ua, steady_state_current_ua, decay_pct).

### `_to_native(val) -> Any`

Converts numpy scalars to native types; maps `NaN` to `None`.

---

## PPF Analysis (`ppf.py`)

### `analyze_ppf(intervals_ms, ratios) -> dict`

```python
def analyze_ppf(
    intervals_ms: ArrayLike,
    ratios: ArrayLike,
) -> dict
```

Fit exponential decay $\text{PPF}(t) = 1 + A \cdot e^{-t/\tau}$ via `scipy.optimize.curve_fit`. Bounds: $A \geq 0$, $\tau \geq 0$. Requires ≥2 points.

Returns: `tau_facilitation_ms`, `a_amplitude`, `ppf_ratio_max`, `ppf_ratio_min`, `r_squared`, `n_intervals`. On fit failure, `tau_facilitation_ms` and `a_amplitude` are `None` and `fit_error` contains the message.

### `ppf_summary(analysis: dict) -> str`

```python
def ppf_summary(analysis: dict) -> str
```

Formats PPF analysis dict into a multi-line report: interval count, ratio range, facilitation time constant, and R².

### `analyze_ppf_to_yaml(intervals_ms, ratios, step_dir, instrument="", devices="") -> Path`

```python
def analyze_ppf_to_yaml(
    intervals_ms: ArrayLike,
    ratios: ArrayLike,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
) -> Path
```

Technique key `"pulse-ppf"`. Writes `analysis.mode`, `analysis.ppf_ratio_vs_interval` (array of `{interval_ms, ppf_ratio}` rows), `analysis.facilitation_time_constant_ms`, `a_amplitude`, `ppf_ratio_max`, `ppf_ratio_min`, `r_squared`, `n_intervals`.

---

## Plotting (`plotting.py`)

All functions use `matplotlib` with `Agg` backend. Figures are serialised to SVG via `BytesIO` and returned as XML strings. Figure size: 8×5 in.

### `generate_endurance_plot(cycles, r_on, r_off) -> str`

Dual-trace plot: R_on in red (`o-`), R_off in blue (`s-`), y-axis log-scale.

### `generate_retention_plot(time, resistance) -> str`

Semilog-x plot of resistance vs time (s). Green (`o-`).

### `generate_stp_plot(time, current) -> str`

STP decay trace: current converted to $\mu$A ($\times 10^6$). Purple (`o-`).
