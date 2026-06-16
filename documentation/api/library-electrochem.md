# Electrochemistry Analysis Library

**Module**: `science_cli.library.electrochem`

Analysis routines for cyclic voltammetry (CV), chronoamperometry (CA), and electrochemical impedance spectroscopy (EIS). Built on `numpy`, `scipy.signal`, and `lmfit`.

---

## Data Models (`models.py`)

### `CVData`

```python
@dataclass
class CVData:
    potential: np.ndarray       # Applied potential (V)
    current: np.ndarray         # Measured current (A)
    scan_rate: float = 0.0      # Scan rate (V/s)
    metadata: dict | None = None
```

Container for a single CV sweep. `scan_rate` is required for charge normalisation and multi-rate analysis.

---

### `CAData`

```python
@dataclass
class CAData:
    time: np.ndarray            # Elapsed time (s)
    current: np.ndarray         # Measured current (A)
    potential: float = 0.0      # Step potential (V)
    metadata: dict | None = None
```

Container for a single chronoamperometry transient.

---

### `EISData`

```python
@dataclass
class EISData:
    frequency: np.ndarray       # Frequency vector (Hz)
    impedance: np.ndarray       # Complex impedance (Ω)
    temperature: float = 0.0    # Measurement temperature (°C)
    metadata: dict | None = None
```

Computed properties on the complex `impedance` array:

| Property    | Expression                    | Description              |
|-------------|-------------------------------|--------------------------|
| `.real`     | `impedance.real`             | Z' (Ω)                   |
| `.imag`     | `impedance.imag`             | Z'' (Ω)                  |
| `.magnitude`| `np.abs(impedance)`          | \|Z\| (Ω)                |
| `.phase`    | `np.angle(impedance, deg=True)` | Phase angle (°)       |

---

## Public API (`__init__.py`)

```python
from .cv import analyze_cv, calculate_charge, peak_analysis, scan_rate_analysis
from .ca import analyze_ca, analyze_cottrell, analyze_steady_state
from .eis import analyze_eis, circuit_fit, kramers_kronig
from .models import CVData, CAData, EISData
```

---

### Column Alias Lists

Lists of recognised column header strings for data-loader column resolution:

| List            | Aliases                                                   |
|-----------------|-----------------------------------------------------------|
| `_cv_x_aliases` | `WE(1).Potential (V)`, `Potential (V)`, `E`, `V`, ...    |
| `_cv_y_aliases` | `WE(1).Current (A)`, `Current (A)`, `I`, `<I>/A`, ...    |
| `_ca_x_aliases` | `Corrected time (s)`, `Time`, `t/s`, ...                  |
| `_ca_y_aliases` | (same as CV current aliases)                              |
| `_eis_f_aliases` | `Frequency (Hz)`, `f/Hz`, `freq`, ...                    |
| `_eis_zr_aliases` | `Z' (Ω)`, `Re(Z)`, `Zre`, `z'`, ...                    |
| `_eis_zi_aliases` | `-Z'' (Ω)`, `Im(Z)`, `Zim`, `z''`, ...                 |

---

### `COLUMN_MAPS: dict[str, ColumnMap]`

| Key     | X column     | Y column     | Extras                                      |
|---------|--------------|--------------|---------------------------------------------|
| `ec-cv` | Potential    | Current      | —                                           |
| `ec-ca` | Time         | Current      | —                                           |
| `ec-eis`| Z'           | -Z''         | `frequency`, `z_real`, `z_imag`, `magnitude`, `phase`, `_f_aliases` |

Each `ColumnMap` carries `x_aliases`, `y_aliases`, `x_label`, `y_label`.

---

### `ANALYZERS: dict[str, callable]`

```python
{"ec-cv": analyze_cv, "ec-ca": analyze_ca, "ec-eis": analyze_eis}
```

Registry used by the generic `science-cli analyze` dispatcher.

---

### `PLOT_PRESETS: dict[str, dict]`

```python
{"ec-cv":  {"type": "line",    "xlabel": "Potential (V)", "ylabel": "Current (A)"},
 "ec-ca":  {"type": "line",    "xlabel": "Time (s)",      "ylabel": "Current (A)"},
 "ec-eis": {"type": "nyquist", "xlabel": "Z' (Ω)",        "ylabel": "-Z'' (Ω)"}}
```

The `nyquist` type triggers Z'-vs-Z'' scatter with equal aspect ratio.

---

## Cyclic Voltammetry (`cv.py`)

### `analyze_cv(data, options) -> dict`

```python
def analyze_cv(data: CVData, options: dict | None = None) -> dict
```

Top-level dispatch. Options: `peaks` (default `True`, runs `peak_analysis`), `charge` (default `False`, runs `calculate_charge`). Returns dict with keys matching enabled analyses.

---

### `peak_analysis(data, options) -> dict`

```python
def peak_analysis(data: CVData, options: dict | None = None) -> dict
```

Detects anodic and cathodic peaks via `scipy.signal.find_peaks`. Options passed through: `height`, `distance`, `prominence`, `peak_type` (`"anodic"`, `"cathodic"`, or `"both"` — default). Anodic peaks are positive maxima; cathodic peaks are detected on `-current` (inverted) then sign-flipped.

Returns:

```python
{"n_anodic": int, "anodic_peaks": [{"index", "potential", "current", "height"}, ...],
 "n_cathodic": int, "cathodic_peaks": [...],
 "average_peak_separation": float}   # present when both types found
```

---

### `_find_peaks(curve, **kwargs) -> tuple[np.ndarray, dict]`

Wrapper around `scipy.signal.find_peaks` with NaN safety. Returns empty arrays on NaN or exception.

---

### `calculate_charge(data) -> dict`

```python
def calculate_charge(data: CVData) -> dict
```

Trapezoidal integration (`numpy.trapezoid`) of current vs potential, divided by scan rate. Separates anodic (`current > 0`) and cathodic (`current < 0`) contributions.

Returns `{"total_charge": float, "anodic_charge": float, "cathodic_charge": float, "unit": "C"}`.

---

### `scan_rate_analysis(curves) -> dict`

```python
def scan_rate_analysis(curves: list[CVData]) -> dict
```

Multi-rate analysis across a list of CV sweeps. Extracts peak current (prefers first anodic peak). With 2+ valid scan rates fits two models via `numpy.polyfit(..., 1)`:

- **Linear**: $i_p = m \cdot v + b$ (keys `linear_fit_slope`, `linear_fit_intercept`)
- **Sqrt**:  $i_p = m \cdot \sqrt{v} + b$ (keys `sqrt_fit_slope`, `sqrt_fit_intercept`)

Returns `{"scan_rates": [...], "peak_currents": [...], "peak_potentials": [...], "linear_fit_slope": float, ...}`.

---

## Chronoamperometry (`ca.py`)

### `analyze_ca(data, options) -> dict`

```python
def analyze_ca(data: CAData, options: dict | None = None) -> dict
```

Top-level dispatch. Options: `fit` (default `True`, runs `analyze_cottrell`), `steady_state` (default `True`, runs `analyze_steady_state`). Returns dict with keys `cottrell` and/or `steady_state`.

---

### `analyze_cottrell(data) -> dict`

```python
def analyze_cottrell(data: CAData) -> dict
```

Cottrell fit via `lmfit.Model`: $i(t) = \text{slope} / \sqrt{t} + \text{intercept}$. Filters `t <= 0` to avoid division by zero.

Returns `{"slope": float, "slope_stderr": float, "intercept": float, "r_squared": float, "reduced_chi": float}`.

---

### `analyze_steady_state(data, fraction=0.2) -> dict`

```python
def analyze_steady_state(data: CAData, fraction: float = 0.2) -> dict
```

Tail-averaged steady-state current. Averages the last `fraction` of the transient.

Returns `{"steady_state_current": float, "steady_state_std": float, "steady_state_time": float, "steady_state_fraction": float}`.

---

## Electrochemical Impedance Spectroscopy (`eis.py`)

### Circuit Registry

```python
_circuit_functions: dict[str, callable] = {}
```

Module-level registry of circuit model functions. Each accepts `(f: np.ndarray, **params) -> np.ndarray` (complex impedance).

### `_register_circuit(name, func)`

```python
def _register_circuit(name: str, func: callable) -> None
```

Register a custom circuit. After registration the circuit is available to `circuit_fit()` and `best_circuit_fit()`.

### Built-in Circuit Models

| Key            | Function           | Parameters                         | Topology                    |
|----------------|--------------------|-----------------------------------|----------------------------|
| `RC`           | `_rc_series`       | `R`, `C`                          | Series RC                  |
| `RRC`          | `_rrc_randles`     | `Rs`, `Rct`, `Cdl`                | Rs + (Rct \|\| Cdl)        |
| `RQR`          | `_rq_randles`      | `Rs`, `Rct`, `Q_mag`, `Q_n`       | Rs + (Rct \|\| CPE)        |
| `Randles`      | `_rq_randles`      | (alias for RQR)                    | —                          |
| `R_s(C[RW])`   | `_rrc_w_randles`   | `Rs`, `Cdl`, `Rct`, `sigma`        | Rs + (Cdl \|\| (Rct + W)) |
| `R_s(Q[RW])`   | `_rqr_w_randles`   | `Rs`, `Q_mag`, `Q_n`, `Rct`, `sigma` | Rs + (CPE \|\| (Rct + W)) |

```python
def _rc_series(f, R, C)           # Z = R + 1/(jωC)
def _rrc_randles(f, Rs, Rct, Cdl) # Z = Rs + 1/(jωCdl + 1/Rct)
def _rq_randles(f, Rs, Rct, Q_mag, Q_n)  # Z = Rs + 1/(1/Zcpe + 1/Rct), Zcpe = 1/(Q_mag·(jω)^Q_n)
def _warburg_impedance(f, sigma)   # Zw = σ/√(jω), composed into other models
def _rrc_w_randles(f, Rs, Cdl, Rct, sigma)  # Rs + (Cdl || (Rct + Zw))
def _rqr_w_randles(f, Rs, Q_mag, Q_n, Rct, sigma)  # Rs + (CPE || (Rct + Zw))
```

---

### `analyze_eis(data, options) -> dict`

```python
def analyze_eis(data: EISData, options: dict | None = None) -> dict
```

Top-level dispatch. Options: `circuit` (default `True`, runs `circuit_fit`), `circuit_model` (default `"RRC"`), `kk` (default `False`, runs `kramers_kronig`).

---

### `circuit_fit(data, circuit="RRC") -> dict`

```python
def circuit_fit(data: EISData, circuit: str = "RRC") -> dict
```

lmfit `Minimizer` (Levenberg–Marquardt) fit of equivalent circuit to EIS data. Residual = concatenation of real and imaginary errors: $[\text{Re}(Z_{calc}) - \text{Re}(Z_{data}), \text{Im}(Z_{calc}) - \text{Im}(Z_{data})]$.

Parameter bounds are hardcoded per circuit type. Returns:

```python
{"circuit": str, "parameter_names": [str], "fitted_params": [float],
 "param_stderr": [float], "r_squared": float, "reduced_chi": float,
 "nfev": int, "fit_Z_real": [float], "fit_Z_imag": [float],
 "fit_frequency": [float]}
```

---

### `best_circuit_fit(data, candidates=None) -> dict`

```python
def best_circuit_fit(data: EISData, candidates: list[str] | None = None) -> dict
```

Runs `circuit_fit` for each candidate, returns the one with highest $R^2$. Default candidates exclude `RC`.

---

### `kramers_kronig(data) -> dict`

```python
def kramers_kronig(data: EISData) -> dict
```

Kramers–Kronig consistency test using a **Voigt model** (series of $n$ RC elements with log-spaced time constants). The Voigt model is inherently KK-compliant — a good fit implies KK-consistent data.

Procedure: $n = \min(10, \lfloor \text{len}(f)/2 \rfloor)$ poles log-spaced between $f_{min}$ and $f_{max}$; model $Z(f) = R_\infty + \sum R_k / (1 + j\omega\tau_k)$ fitted via lmfit; mean relative residual computed.

```python
{"passes": bool,               # True if consistency_score < 5.0
 "consistency_score": float,   # mean relative residual (%)
 "n_poles": int,
 "reduced_chi": float}
```
