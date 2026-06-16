# Pulse Measurements — Memristor Switching Dynamics

## Overview

Pulsed electrical measurements are the primary tool for probing the dynamical properties of memristive and neuromorphic devices. Unlike DC sweeps, which measure quasi-static I-V characteristics, pulse measurements reveal how a device behaves under realistic operating conditions — when voltage is applied for microseconds to milliseconds, then removed, and the device is left to relax. The time-domain response encodes the physical mechanisms of switching, retention, and plasticity.

### What Pulse Measurements Reveal

| Property | What It Tells You | Typical Timescale |
|---|---|---|
| **Switching speed** | How fast the device transitions between resistance states | ns — µs |
| **Endurance** | How many cycles the device survives before failure | 10³ — 10¹² cycles |
| **Retention** | How long the programmed state persists without power | s — years |
| **Short-term plasticity (STP)** | How conductance decays after a pulse — volatile memory dynamics | ms — s |
| **Paired-pulse facilitation (PPF)** | How the second pulse response depends on the inter-pulse interval — synaptic-like facilitation | ms — s |
| **Forming voltage** | The initial soft-breakdown voltage required to activate switching | single pulse |
| **Set/Reset characteristics** | Threshold voltage and current for each switching direction | single pulse |

### Physics Background

Pulse measurements isolate the kinetic response of oxygen vacancy migration, filament formation/rupture, and interfacial barrier modulation — processes with distinct time constants that are masked in slow DC sweeps. The conductance decay following a programming pulse, for instance, reflects the relaxation of metastable oxygen vacancy distributions back toward equilibrium. The timescale of this relaxation — captured by STP and PPF analysis — is a direct fingerprint of the material's defect dynamics and thermal activation barriers.

### Pulse Technique Taxonomy

Science-cli recognises 11 pulse technique slugs, each detected by regex filename patterns. All pulse techniques route to the `pulse` library for analysis.

| Technique | Label | Description | Filename Pattern |
|---|---|---|---|
| `pulse-endurance` | Pulse Endurance | Pulsed endurance cycling — R_high/R_low vs cycle count | `_endurance`, `.end`, `end_`, `endurance` |
| `pulse-retention` | Pulse Retention | Retention decay — time-dependent resistance change | `_retention`, `.ret`, `ret_`, `retention` |
| `pulse-switching` | Pulse Switching | Switching time and voltage statistics | `_switch`, `.sw`, `sw_`, `switch_` |
| `pulse-forming` | Pulse Forming | Initial electroforming step (soft breakdown) | `_forming`, `form_`, `_form` |
| `pulse-set` | Pulse Set | Set operation programming pulse | `_set`, `_SET` |
| `pulse-reset` | Pulse Reset | Reset operation programming pulse | `_reset`, `_RESET` |
| `pulse-read` | Pulse Read | Non-destructive read pulse | `_read`, `_READ` |
| `pulse-ivd` | Pulsed IV | Quasi-static pulsed IV measurement | `_ivd`, `_IVD`, `_pulsed-iv` |
| `pulse-stp` | STP Decay | Short-term plasticity decay — biexponential fitting | `_stp`, `_STP`, `_stp_decay`, `_short-term` |
| `pulse-ppf` | PPF Ratio | Paired-pulse facilitation ratio vs inter-pulse interval | `_ppf`, `_PPF`, `_paired-pulse` |

The three legacy techniques `mem-endurance`, `mem-retention`, and `mem-switching` share identical filename patterns and exist for backward compatibility but route to the `general` library (not `pulse`). New workflows should use the `pulse-*` slugs exclusively.

---

## CLI Commands

All pulse analysis is accessed through the `sci pulse` command group. The CLI parser is defined in `library/pulse/device_cli.py` and dispatched by `cli/commands/pulse.py`.

```
sci pulse <subcommand> [--file <path>]
```

### `sci pulse ls`

List pulse measurement files in the current project. Scans the active protocol's data directories for files matching pulse-related filename patterns.

```bash
sci pulse ls
# Pulse measurement files:
```

The output currently lists all detected files in the project directory. This command reads from the active protocol context (opened via `sci open`).

### `sci pulse endurance`

Analyze endurance cycling data — resistance in high (R_off) and low (R_on) states as a function of cycle number.

```
sci pulse endurance [--file <path>]
```

The `--file` flag points to a CSV or text file containing endurance cycling data with columns for cycle number, R_on, and R_off.

**Implementation status:** The CLI parser accepts the `--file` flag but the analysis body is a stub (`cmd_endurance` prints `"endurance analysis not yet implemented"`). The underlying analysis library (`library/pulse/endurance.py`) is fully implemented with `analyze_endurance()` and `analyze_endurance_to_yaml()`. Wiring the stub to the library is pending.

### `sci pulse retention`

Analyze retention decay — resistance as a function of time after programming.

```
sci pulse retention [--file <path>]
```

Fits both log-time and power-law decay models, selects the better model by R², and extrapolates to 10-year projections.

**Implementation status:** CLI stub. Library (`library/pulse/retention.py`) fully implemented.

### `sci pulse stp`

Analyze short-term plasticity decay — current vs time after a programming pulse.

```
sci pulse stp [--file <path>]
```

Fits monoexponential and biexponential decay models, selects the better model by AIC (Akaike Information Criterion). Reports time constants τ₁ (fast) and τ₂ (slow), amplitude weights, and decay percentage.

**Implementation status:** CLI stub. Library (`library/pulse/stp.py`) fully implemented with least-squares fitting and AIC-based model selection.

### `sci pulse ppf`

Analyze paired-pulse facilitation ratio as a function of inter-pulse interval.

```
sci pulse ppf [--file <path>]
```

Fits an exponential decay model PPF(Δt) = 1 + A·exp(-Δt/τ) to the ratio vs interval data. Reports the facilitation time constant τ, amplitude A, and ratio range.

**Implementation status:** CLI stub. Library (`library/pulse/ppf.py`) fully implemented with `scipy.optimize.curve_fit`.

### `sci pulse dashboard`

Launch the pulse analysis dashboard — an interactive Plotly HTML dashboard for exploring pulse measurement results across protocols.

```bash
sci pulse dashboard
```

**Implementation status:** Not yet implemented (stub prints `"dashboard not yet implemented"`).

---

## Data Models

The `library/pulse/models.py` module defines five dataclasses that standardize pulse data containers across the analysis library.

### PulseData

Generic container for single-pulse measurement data.

```python
@dataclass
class PulseData:
    time: np.ndarray           # Time (s or ms)
    current: np.ndarray        # Measured current (A)
    voltage: Optional[np.ndarray] = None  # Applied voltage (V)
    filename: str = ""
    metadata: dict = field(default_factory=dict)
```

### EnduranceData

Container for endurance cycling measurements. Expects arrays of R_on and R_off at each cycle.

```python
@dataclass
class EnduranceData:
    cycles: np.ndarray         # Cycle index (0 to N-1)
    r_on: np.ndarray           # Low-resistance state (Ohm)
    r_off: np.ndarray          # High-resistance state (Ohm)
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)
```

### RetentionData

Container for retention decay measurements. Resistance is measured at irregular time intervals after programming.

```python
@dataclass
class RetentionData:
    time: np.ndarray           # Elapsed time (s)
    resistance: np.ndarray     # Resistance at each time point (Ohm)
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)
```

### STPData

Container for short-term plasticity decay traces.

```python
@dataclass
class STPData:
    time: np.ndarray           # Time (ms)
    current: np.ndarray        # Current (A)
    metadata: dict = field(default_factory=dict)
```

### PPFData

Container for paired-pulse facilitation measurements.

```python
@dataclass
class PPFData:
    intervals_ms: np.ndarray   # Inter-pulse intervals (ms)
    ratios: np.ndarray         # PPF ratio = G₂/G₁ (dimensionless)
    metadata: dict = field(default_factory=dict)
```

---

## Endurance Cycling

### Physics

Endurance cycling measures how the resistance states of a memristor evolve under repeated programming. A typical endurance test applies alternating set (program to LRS) and reset (program to HRS) pulses for thousands to billions of cycles. The resistance in each state is read after every pulse (or every Nth pulse) using a low-voltage read pulse that does not disturb the state.

The failure of endurance is the collapse of the R_off/R_on ratio below a usable threshold (typically 10 for binary operation). Physically, failure can arise from:

- **Oxygen reservoir depletion:** Successive reset pulses exhaust the available oxygen ions in the switching layer, reducing the achievable HRS resistance.
- **Filament overgrowth:** Progressive filament thickening during set cycles increases the LRS minimum current, shrinking the ratio.
- **Dielectric breakdown:** Localized damage accumulation eventually creates a permanent conductive path that cannot be reset.
- **Thermal runaway:** Joule heating during switching accelerates diffusion, creating a positive feedback loop of degradation.

### Analysis

The `analyze_endurance()` function in `library/pulse/endurance.py` computes:

| Parameter | Description | Calculation |
|---|---|---|
| `mean_r_on` | Mean low-resistance state (Ohm) | `np.mean(r_on)` |
| `mean_r_off` | Mean high-resistance state (Ohm) | `np.mean(r_off)` |
| `mean_ratio` | Mean R_off / R_on ratio | `np.mean(r_off / r_on)` |
| `cv_r_on` | Coefficient of variation for LRS | `std(r_on) / mean(r_on)` |
| `cv_r_off` | Coefficient of variation for HRS | `std(r_off) / mean(r_off)` |
| `failure_cycle` | First cycle where ratio drops below 10 | `cycles[failed_mask][0]` |
| `weibull_fit` | Weibull minimum distribution parameters | `scipy.stats.weibull_min.fit()` |
| `trend_slope` | Linear trend of R_off degradation (Ohm/cycle) | `np.polyfit(cycles, r_off, 1)[0]` |
| `ratio_tail_mean` | Mean of ratio in last 10% of cycles | `np.mean(ratio[-tail_n:])` |
| `ratio_tail_std` | Std of ratio in last 10% of cycles | `np.std(ratio[-tail_n:])` |

**Failure detection:** Ratio < 10 triggers failure marking. If at least 3 failure points exist, a Weibull minimum distribution is fit to the cycles-to-failure data via `scipy.stats.weibull_min.fit(cycles_failed, floc=0)`. The Weibull shape parameter indicates the failure rate trend:

- Shape < 1: Infant mortality (decreasing failure rate)
- Shape = 1: Random failure (constant failure rate)
- Shape > 1: Wear-out failure (increasing failure rate)

**Degradation trend:** Linear regression on R_off vs cycles quantifies progressive degradation. The slope (Ohm/cycle) captures the drift rate, and R-squared measures how consistently the degradation follows a linear trend.

### Summary Display

The `endurance_summary()` function produces a human-readable summary:

```python
Endurance: 10000 cycles
  R_ON  = 1234.5 Ohm (CV=0.023)
  R_OFF = 54321.0 Ohm (CV=0.087)
  Ratio = 44.0
  FAILURE at cycle 9876
  R_OFF trend: 2.34e-01 Ohm/cycle (R-squared=0.8921)
```

### YAML Output

`analyze_endurance_to_yaml()` writes the analysis to `<step_dir>/results/pulse-endurance_analysis.yaml`. See [Appendix: YAML Schemas](#appendix-yaml-schemas) for the full schema.

---

## Retention Decay

### Physics

Retention measures how long a programmed resistance state persists after the programming pulse is removed. The data is obtained by programming the device to either HRS or LRS, then reading the resistance at logarithmically spaced time intervals without reapplying programming pulses. The resistance typically decays following a power-law or log-time dependence, reflecting the thermally activated relaxation of the metastable defect configuration.

The relevant physical processes include:

- **Oxygen vacancy diffusion:** Vacancies drift back toward equilibrium positions, reducing the filament's effective cross-section.
- **Charge detrapping:** Trapped charges at defect sites gradually de-trap, altering the barrier height at the electrode interface.
- **Structural relaxation:** The amorphous switching layer undergoes slow structural relaxation, changing the local bonding configuration and thus the conductivity.

### Analysis

The `analyze_retention()` function in `library/pulse/retention.py` fits two models:

**Log-time model:** R(t) = a · log₁₀(t) + b

**Power-law model:** R(t) = a · t^b

The model with the higher R² is selected. From the chosen model, the function extrapolates:

- **10-year resistance:** Projected resistance after 10 years of continuous operation
- **Lifetime:** Time to 50% degradation from initial resistance
- **Decay rate:** Slope of the log-time fit (Ohm/decade) — only meaningful for the log model

| Parameter | Description |
|---|---|
| `decay_rate` | Slope of log-time fit (Ohm/decade) |
| `decay_model` | Selected model: `"log"` or `"power"` |
| `extrapolated_10yr` | Projected resistance after 10 years (Ohm) |
| `lifetime_hours` | Estimated time to 50% degradation (hours) |
| `test_duration_hours` | Actual test duration (hours) |
| `r_squared` | Fit quality of the selected model |
| `n_points` | Number of valid data points |

**Extrapolation details (log model):**

```python
t_10yr = 10 * 365.25 * 24 * 3600  # seconds
R_10yr = a_log * log10(t_10yr) + b_log

lifetime = 10 ** ((R_threshold - b_log) / a_log)  # seconds
```

**Extrapolation details (power model):**

```python
R_10yr = a_power * t_10yr ** b_power

lifetime = (R_threshold / a_power) ** (1 / b_power)  # seconds
```

### Summary Display

```python
Retention @ 298.0 K: 168.0 h test, 100 points
  Model: log (R-squared=0.9934)
  Decay rate: -2.345e+02 Ohm/decade
  R(10yr): 34567.8 Ohm
  Lifetime: 87654 h (3652 days)
```

### YAML Output

See [Appendix: YAML Schemas](#appendix-yaml-schemas) for `pulse-retention_analysis.yaml`.

---

## STP Decay (Short-Term Plasticity)

### Physics

Short-term plasticity (STP) refers to the transient increase in conductance following a programming pulse. In memristive devices, this is analogous to the short-term synaptic plasticity observed in biological synapses. When a voltage pulse is applied, the conductance jumps (due to defect reconfiguration, filament growth, or charge injection) and then decays back toward baseline over milliseconds to seconds.

STP is the volatile component of memristive switching — it represents the part of the conductance change that is not permanently stored. The decay kinetics are determined by:

- **Oxygen vacancy relaxation:** Non-equilibrium vacancy distributions created by the pulse relax via diffusion back to equilibrium
- **Charge re-distribution:** Trapped charges at interfacial states de-trap with characteristic time constants
- **Local temperature decay:** Joule heating during the pulse creates a local temperature spike; the conductance transient partly reflects the cooling dynamics

The separation of fast and slow time constants (biexponential fit) distinguishes between:
- **τ₁ (fast):** Rapid charge de-trapping or thermal dissipation (1–50 ms)
- **τ₂ (slow):** Slower vacancy redistribution or structural relaxation (50–500 ms)

### Analysis

The `analyze_stp_decay()` function in `library/pulse/stp.py` normalises the time trace (t → t - t₀) and fits two models via `scipy.optimize.least_squares` with non-negativity bounds:

**Monoexponential:** I(t) = A · exp(-t / τ₁) + I₀

**Biexponential:** I(t) = A₁ · exp(-t / τ₁) + A₂ · exp(-t / τ₂) + I₀

**Model selection:** AIC (Akaike Information Criterion) penalises the biexponential model for its extra parameters:

```
AIC = n · ln(SS_res / n) + 2k
```

where k = 3 for monoexponential and k = 5 for biexponential. The model with the lower AIC is selected.

| Parameter | Description |
|---|---|
| `model` | Selected model: `"monoexponential"` or `"biexponential"` |
| `tau1_ms` | Fast time constant (ms) |
| `tau2_ms` | Slow time constant (ms, biexponential only) |
| `a1` | Relative amplitude weight of fast component |
| `a2` | Relative amplitude weight of slow component |
| `initial_current_ua` | Peak current after the pulse (µA) |
| `steady_state_current_ua` | Steady-state current (µA) |
| `decay_pct` | Percentage decay from peak to steady state |
| `r_squared` | Goodness of fit |

For the biexponential model, the amplitudes are normalised:

```python
total_amp = A₁ + A₂
a1 = A₁ / total_amp
a2 = A₂ / total_amp
```

### Summary Display

```python
STP Decay Analysis: biexponential
  Current: 12.34 uA -> 3.21 uA
  Decay: 74.0%
  tau1 = 12.3 ms
  tau2 = 145.6 ms (weight=0.35)
  R-squared = 0.9978
```

### YAML Output

See [Appendix: YAML Schemas](#appendix-yaml-schemas) for `pulse-stp_analysis.yaml`.

---

## PPF (Paired-Pulse Facilitation)

### Physics

Paired-pulse facilitation (PPF) measures how the conductance response to the second of two closely spaced pulses depends on the inter-pulse interval. In memristive devices, PPF arises from the same volatile relaxation processes captured by STP — the first pulse creates a metastable conductance increase that has not fully decayed by the time the second pulse arrives, so the second pulse builds on the residual conductance.

The PPF ratio is defined as:

```
PPF(Δt) = G₂ / G₁
```

where G₁ is the conductance immediately after the first pulse and G₂ is the conductance immediately after the second pulse. For short intervals (Δt < τ), the residual facilitation from the first pulse adds to the second pulse response, giving PPF > 1. As Δt increases beyond the relaxation time constant, the facilitation decays and PPF approaches 1.

The PPF ratio vs interval follows an exponential decay:

```
PPF(Δt) = 1 + A · exp(-Δt / τ)
```

where:
- **A:** Facilitation amplitude (the maximum PPF ratio minus 1 at Δt → 0)
- **τ:** Facilitation time constant (ms) — characterises the decay of the volatile conductance enhancement

PPF analysis is widely used in neuromorphic characterisation because it directly probes the short-term dynamics that determine how the device processes temporal patterns of spikes — fundamental to spike-timing-dependent plasticity (STDP) and temporal coding.

### Analysis

The `analyze_ppf()` function in `library/pulse/ppf.py` fits the exponential model via `scipy.optimize.curve_fit`:

```python
def ppf_model(t, a, tau):
    return 1 + a * np.exp(-t / tau)

popt, _ = optimize.curve_fit(ppf_model, intervals, ratios, p0=[max(ratios)-1, np.median(intervals)], bounds=([0, 0], [np.inf, np.inf]))
```

| Parameter | Description |
|---|---|
| `tau_facilitation_ms` | Facilitation decay time constant (ms) |
| `a_amplitude` | Facilitation amplitude (unitless) |
| `ppf_ratio_max` | Maximum measured PPF ratio |
| `ppf_ratio_min` | Minimum measured PPF ratio |
| `r_squared` | Goodness of fit |
| `n_intervals` | Number of interval-ratio pairs |

### Summary Display

```python
PPF Analysis: 8 intervals
  PPF ratio range: 1.12 - 1.85
  Facilitation time constant: 85.3 ms
  R-squared = 0.9950
```

### YAML Output

See [Appendix: YAML Schemas](#appendix-yaml-schemas) for `pulse-ppf_analysis.yaml`. The PPF YAML includes a per-interval data table.

---

## Switching Characterization

### Physics

Switching characterization measures the distribution of switching times and voltages in pulsed operation. The switching time (t_set for set, t_reset for reset) depends on the applied voltage amplitude and pulse width. The distribution of switching parameters across multiple devices or multiple cycles reveals:

- **Device-to-device variability:** Spread in switching threshold voltages across different cells
- **Cycle-to-cycle variability:** Fluctuations in switching parameters across successive cycles on the same device
- **Voltage-time dilemma:** The trade-off between lower voltage (slower switching, better reliability) and higher voltage (faster switching, more stress)

### Analysis

The `analyze_pulse_switching()` function in `library/pulse/switching.py` computes basic statistics:

| Parameter | Description |
|---|---|
| `t_set_mean` | Mean switching time |
| `t_set_std` | Standard deviation of switching time |
| `n_events` | Number of switching events |
| `v_set_mean` | Mean switching voltage (if data provided) |
| `v_set_std` | Standard deviation of switching voltage |

This is a lightweight analysis module. No `_to_yaml()` wrapper currently exists for switching analysis.

---

## Plotting

The `library/pulse/plotting.py` module provides dedicated SVG plot generators for three main pulse techniques. All use `matplotlib` with `Agg` backend for server-side rendering.

### Endurance Plot

`generate_endurance_plot(cycles, r_on, r_off)` returns an SVG string with:

- Dual y-axes: R_on (red circles) and R_off (blue squares) plotted vs cycle number on a log-scale y-axis
- Grid with 30% alpha
- 8×5 inch figure size

```python
fig, ax1 = plt.subplots(figsize=(8, 5))
ax1.plot(cycles, r_on, "o-", color="#E74C3C", markersize=3, label="R_ON")
ax1.plot(cycles, r_off, "s-", color="#3498DB", markersize=3, label="R_OFF")
ax1.set_yscale("log")
```

### Retention Plot

`generate_retention_plot(time, resistance)` returns an SVG string with:

- Semi-log x-axis (logarithmic time, linear resistance)
- Green circles with connecting line
- 8×5 inch figure size

```python
fig, ax = plt.subplots(figsize=(8, 5))
ax.semilogx(time, resistance, "o-", color="#2ECC71", markersize=4)
ax.set_xlabel("Time (s)")
ax.set_ylabel("Resistance (Ohm)")
```

### STP Plot

`generate_stp_plot(time, current)` returns an SVG string with:

- Linear axes
- Current in µA (converted from A)
- Purple circles with connecting line
- 8×5 inch figure size

```python
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(time, current * 1e6, "o-", color="#9B59B6", markersize=4)
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Current (uA)")
```

All three generators use `BytesIO` to write the SVG to a string buffer, then decode to UTF-8.

---

## Technique Detection: Pulse Filename Patterns

The `detect_technique()` function in `core/technique.py` uses regex patterns to identify pulse techniques from filenames. All pulse-* techniques share patterns with legacy mem-* techniques, with `mem-*` taking priority due to insertion order in the PATTERNS dict:

| Filename | Detected Technique | Matched Pattern |
|---|---|---|
| `2105_HfOx_endurance_001.txt` | `mem-endurance` (or `pulse-endurance` if mem- removed) | `_endurance` |
| `2105_HfOx_retention_01.csv` | `mem-retention` (or `pulse-retention`) | `_retention` |
| `2105_HfOx_switch_r0c0.txt` | `mem-switching` (or `pulse-switching`) | `_switch` |
| `S01_stp_decay_001.csv` | `pulse-stp` | `_stp` |
| `S01_ppf_001.csv` | `pulse-ppf` | `_ppf` |
| `device_forming_01.txt` | `pulse-forming` | `_forming` |
| `device_reset_01.txt` | `pulse-reset` | `_reset` |
| `device_set_01.txt` | `pulse-set` | `_set` |
| `pulsed_iv_data.csv` | `pulse-ivd` | `_ivd` |

To force `pulse-*` detection, either remove `mem-*` patterns via config overrides or use explicit `--technique pulse-endurance` CLI flags.

---

## Appendix: YAML Schemas

Each pulse analysis module writes structured YAML output via the shared `write_analysis_yaml()` function in `core/analysis_output.py`. Files are written to `<step_dir>/results/<technique>_analysis.yaml`.

### Common Envelope

Every analysis YAML has:

```yaml
technique: <technique_slug>
instrument: <instrument_name>
devices: <device_type>
timestamp: "2026-06-15T12:00:00Z"
```

### Pulse Endurance — `pulse-endurance_analysis.yaml`

```yaml
technique: pulse-endurance
instrument: keithley-2400
devices: memristor
timestamp: "2026-06-15T12:00:00Z"
analysis:
  mode: general
  parameters:
    cycles_to_failure: 9876
    r_high_initial: 54321.0
    r_low_initial: 1234.5
    cycle_to_cycle_variability_pct: 8.7
    n_cycles: 10000
    ratio_tail_mean: 12.3
    ratio_tail_std: 1.2
  per_cycle_sampling: 10000
```

**Key fields:**

| Field | Type | Description |
|---|---|---|
| `analysis.mode` | string | Device mode (`general` or device name) |
| `analysis.parameters.cycles_to_failure` | int | First cycle where ratio < 10 |
| `analysis.parameters.r_high_initial` | float | Mean high-resistance state (Ohm) |
| `analysis.parameters.r_low_initial` | float | Mean low-resistance state (Ohm) |
| `analysis.parameters.cycle_to_cycle_variability_pct` | float | CV of HRS × 100 |
| `analysis.parameters.n_cycles` | int | Total number of cycles tested |
| `analysis.parameters.ratio_tail_mean` | float | Mean ratio in last 10% of cycles |
| `analysis.parameters.ratio_tail_std` | float | Std of ratio in last 10% of cycles |
| `analysis.per_cycle_sampling` | int | Number of data points |

### Pulse Retention — `pulse-retention_analysis.yaml`

```yaml
technique: pulse-retention
instrument: keithley-2400
devices: memristor
timestamp: "2026-06-15T12:00:00Z"
analysis:
  mode: general
  parameters:
    decay_rate: -234.5
    decay_model: log
    extrapolated_10yr: 34567.8
    lifetime_hours: 87654.0
    r_squared: 0.9934
    test_duration_hours: 168.0
    n_points: 100
```

**Key fields:**

| Field | Type | Description |
|---|---|---|
| `analysis.parameters.decay_rate` | float | Log-time fit slope (Ohm/decade) |
| `analysis.parameters.decay_model` | string | `"log"` or `"power"` |
| `analysis.parameters.extrapolated_10yr` | float | Projected R after 10 years (Ohm) |
| `analysis.parameters.lifetime_hours` | float | Time to 50% degradation (hours) |
| `analysis.parameters.r_squared` | float | Selected model fit quality |
| `analysis.parameters.test_duration_hours` | float | Actual test duration |
| `analysis.parameters.n_points` | int | Number of valid data points |

### Pulse STP — `pulse-stp_analysis.yaml`

```yaml
technique: pulse-stp
instrument: keysight-b1500a
devices: memristor
timestamp: "2026-06-15T12:00:00Z"
analysis:
  mode: general
  decay_fit:
    model: biexponential
    tau1_ms: 12.3
    tau2_ms: 145.6
    a1: 0.65
    a2: 0.35
    r_squared: 0.9978
  parameters:
    initial_current_ua: 12.34
    steady_state_current_ua: 3.21
    decay_pct: 74.0
```

**Key fields:**

| Field | Type | Description |
|---|---|---|
| `analysis.decay_fit.model` | string | `"monoexponential"` or `"biexponential"` |
| `analysis.decay_fit.tau1_ms` | float | Fast time constant (ms) |
| `analysis.decay_fit.tau2_ms` | float | Slow time constant (ms, biexponential only) |
| `analysis.decay_fit.a1` | float | Fast component relative amplitude |
| `analysis.decay_fit.a2` | float | Slow component relative amplitude |
| `analysis.decay_fit.r_squared` | float | Fit quality |
| `analysis.parameters.initial_current_ua` | float | Peak current (µA) |
| `analysis.parameters.steady_state_current_ua` | float | Steady-state current (µA) |
| `analysis.parameters.decay_pct` | float | Decay fraction (percent) |

### Pulse PPF — `pulse-ppf_analysis.yaml`

```yaml
technique: pulse-ppf
instrument: keysight-b1500a
devices: memristor
timestamp: "2026-06-15T12:00:00Z"
analysis:
  mode: general
  ppf_ratio_vs_interval:
    - interval_ms: 50.0
      ppf_ratio: 1.85
    - interval_ms: 100.0
      ppf_ratio: 1.65
    - interval_ms: 200.0
      ppf_ratio: 1.35
    - interval_ms: 500.0
      ppf_ratio: 1.12
  facilitation_time_constant_ms: 85.3
  a_amplitude: 0.92
  ppf_ratio_max: 1.85
  ppf_ratio_min: 1.12
  r_squared: 0.9950
  n_intervals: 8
```

**Key fields:**

| Field | Type | Description |
|---|---|---|
| `analysis.ppf_ratio_vs_interval` | list | Per-interval table: `interval_ms` + `ppf_ratio` |
| `analysis.facilitation_time_constant_ms` | float | Exponential decay τ (ms) |
| `analysis.a_amplitude` | float | Facilitation amplitude (unitless) |
| `analysis.ppf_ratio_max` | float | Maximum ratio measured |
| `analysis.ppf_ratio_min` | float | Minimum ratio measured |
| `analysis.r_squared` | float | Fit quality |
| `analysis.n_intervals` | int | Number of data points |

### Pulse Switching — (no YAML schema yet)

The switching analysis module (`library/pulse/switching.py`) returns a plain dict with `t_set_mean`, `t_set_std`, `n_events`, and optionally `v_set_mean`/`v_set_std`. There is no `_to_yaml()` wrapper or YAML schema for `pulse-switching` at this time.

---

## Examples

### Endurance Cycling Analysis

```bash
# List pulse files in the project
sci pulse ls

# Analyze endurance data (stub — not yet implemented)
sci pulse endurance --file 260526_Ta-PDA-ITO_endurance_01.csv

# Expected output (once implemented):
# Endurance: 10000 cycles
#   R_ON  = 1234.5 Ohm (CV=0.023)
#   R_OFF = 54321.0 Ohm (CV=0.087)
#   Ratio = 44.0
#   FAILURE at cycle 9876
#   R_OFF trend: 2.34e-01 Ohm/cycle (R-squared=0.8921)
```

### Retention Decay Analysis

```bash
# Analyze retention (stub — not yet implemented)
sci pulse retention --file 260526_Ta-PDA-ITO_retention_01.csv

# Expected output (once implemented):
# Retention @ 298.0 K: 168.0 h test, 100 points
#   Model: log (R-squared=0.9934)
#   Decay rate: -2.345e+02 Ohm/decade
#   R(10yr): 34567.8 Ohm
#   Lifetime: 87654 h (3652 days)
```

### STP Decay Analysis

```bash
# Analyze STP decay (stub — not yet implemented)
sci pulse stp --file 260526_Ta-PDA-ITO_stp_01.csv

# Expected output (once implemented):
# STP Decay Analysis: biexponential
#   Current: 12.34 uA -> 3.21 uA
#   Decay: 74.0%
#   tau1 = 12.3 ms
#   tau2 = 145.6 ms (weight=0.35)
#   R-squared = 0.9978
```

### PPF Analysis

```bash
# Analyze PPF (stub — not yet implemented)
sci pulse ppf --file 260526_Ta-PDA-ITO_ppf_01.csv

# Expected output (once implemented):
# PPF Analysis: 8 intervals
#   PPF ratio range: 1.12 - 1.85
#   Facilitation time constant: 85.3 ms
#   R-squared = 0.9950
```

### Dashboard

```bash
# Launch pulse dashboard (stub — not yet implemented)
sci pulse dashboard
```

### Using sci analyze (alternative approach)

Once the analyze command routing is wired, pulse analyses can also be triggered through the generic `sci analyze` command with `--technique`:

```bash
# FZF-select a file and route through pulse-endurance analyzer
sci analyze --technique pulse-endurance

# FZF-select and route through pulse-stp with fit model flag
sci analyze --technique pulse-stp --fit-model biexponential

# FZF-select and route through pulse-ppf with custom intervals
sci analyze --technique pulse-ppf --intervals 10,50,100,200,500
```

---

## Implementation Status Summary

| Subcommand | CLI Parser | CLI Handler | Library Analysis | YAML Output | Dashboard |
|---|---|---|---|---|---|
| `ls` | ✅ | ✅ (basic) | N/A | N/A | N/A |
| `endurance` | ✅ | ⏳ Stub | ✅ `endurance.py` | ✅ | ❌ |
| `retention` | ✅ | ⏳ Stub | ✅ `retention.py` | ✅ | ❌ |
| `stp` | ✅ | ⏳ Stub | ✅ `stp.py` | ✅ | ❌ |
| `ppf` | ✅ | ⏳ Stub | ✅ `ppf.py` | ✅ | ❌ |
| `dashboard` | ✅ | ⏳ Stub | ❌ | N/A | ❌ |

The primary development task is wiring the CLI handlers (`cmd_endurance`, `cmd_retention`, `cmd_stp`, `cmd_ppf`) in `device_cli.py` to call their respective library analysis functions.

---

## See Also

- [overview.md](overview.md) — Complete technique taxonomy, detection, routing, analyzers, plotters
- [Pulse Command Reference](../reference/commands/pulse.md) — CLI syntax and flags
- [Analysis YAML Schemas](../schemas/analysis-yaml.md) — Complete per-technique YAML output reference
- [IV Sweeps](iv-sweeps.md) — DC sweep analysis (complementary to pulse measurements)
- [Crossbar Characterization](crossbar-characterization.md) — End-to-end memristor pipeline

### Source Files

- `src/science_cli/library/pulse/device_cli.py` — CLI parser builder and command handlers
- `src/science_cli/library/pulse/endurance.py` — Endurance cycling analysis
- `src/science_cli/library/pulse/retention.py` — Retention decay analysis
- `src/science_cli/library/pulse/stp.py` — STP decay fitting (mono/biexponential)
- `src/science_cli/library/pulse/ppf.py` — PPF ratio vs interval analysis
- `src/science_cli/library/pulse/switching.py` — Switching time statistics
- `src/science_cli/library/pulse/models.py` — Data containers (PulseData, EnduranceData, RetentionData, STPData, PPFData)
- `src/science_cli/library/pulse/plotting.py` — SVG plot generators
- `src/science_cli/cli/commands/pulse.py` — pulse_handler() dispatcher
- `src/science_cli/core/technique.py` — Technique detection patterns and grammar
- `src/science_cli/core/analysis_output.py` — write_analysis_yaml() shared function
