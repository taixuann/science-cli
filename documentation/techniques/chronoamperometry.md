# Chronoamperometry (CA)

## Overview

Chronoamperometry (CA) is an electrochemical technique in which the working electrode potential is stepped from an initial value `E_init` to a step potential `E_step`, and the resulting faradaic current is recorded as a function of time. The potential step creates an instantaneous change in the electrode surface concentration of the electroactive species, driving a diffusion-limited current that decays according to the **Cottrell equation**.

### Principle

At `t = 0`, the potential is stepped into the mass-transport-limited regime (typically beyond the formal potential of the redox couple). The concentration gradient at the electrode surface steepens instantly, producing a large capacitive charging current that decays exponentially (time constant `τ = R_s · C_dl`), followed by the faradaic current governed by semi-infinite linear diffusion of analyte to the electrode surface.

The current response follows the Cottrell equation for a planar electrode under diffusion control:

```
i(t) = nFA C √(D / π t)
```

where:

| Symbol | Meaning | Units |
|--------|---------|-------|
| `i(t)` | Current at time t | A |
| `n` | Number of electrons transferred | dimensionless |
| `F` | Faraday constant (96485.33) | C·mol⁻¹ |
| `A` | Electrode area | cm² |
| `C` | Bulk concentration of electroactive species | mol·cm⁻³ |
| `D` | Diffusion coefficient | cm²·s⁻¹ |
| `t` | Time after potential step | s |

Key observation: **current is proportional to `t^{-1/2}`**. A plot of `i` vs `t^{-1/2}` yields a straight line with slope `= nFA C √(D/π)` and intercept ideally zero. Any deviation from linearity at short times indicates contributions from charging current, ohmic drop, or non-planar diffusion geometry. Deviation at long times may indicate convection, finite diffusion (thin-layer cell), or electrode fouling.

### Current Components

1. **Charging (capacitive) current**: `i_c(t) = (ΔE / R_s) · exp(-t / R_s C_dl)` — decays rapidly (milliseconds for typical microelectrodes). In nanosecond or microsecond CA, this dominates early times and must be gated out or fit separately.

2. **Faradaic current**: The Cottrell component — persists as long as the concentration gradient is maintained. In stirred solutions or at ultramicroelectrodes (UMEs), a steady-state current replaces the decaying transient once the diffusion layer reaches a steady-state thickness.

3. **Convective contribution**: In stirred solutions or rotating disk electrode (RDE) experiments, convection truncates the Cottrell decay at long times, producing a plateau current given by the Levich equation: `i_lim = 0.62 nFA D^{2/3} ω^{1/2} ν^{-1/6} C`.

### Applications

- **Diffusion coefficient measurement**: From the Cottrell slope, compute `D = π (slope / nFA C)²`.
- **Electroactive area determination**: With known `n`, `C`, and `D`, electrode area `A` is obtained from the slope.
- **Kinetic studies**: Potential-step chronoamperometry can probe heterogeneous electron-transfer rate constants via the method of Gileadi or Klingler–Kochi.
- **Nucleation and growth**: Current maximum followed by Cottrell decay indicates 3D nucleation (Scharifker–Hills model).
- **Sensor calibration**: Steady-state current at UMEs is proportional to bulk concentration, forming the basis for amperometric sensors.
- **Electrochromic devices**: CA transients reveal ion insertion kinetics, diffusion coefficients in thin films, and coloration efficiency.
- **Corrosion studies**: Passivation and pitting kinetics from current decay transients.

---

## Data Format

science-cli reads CA data files in standard columnar formats (CSV, TSV, TXT, Biologic `.mpt`). The data loader uses `ColumnMap` resolution via column aliases defined in `science_cli/library/electrochem/__init__.py` to detect the time and current columns independently of the instrument's column naming convention.

### Column Aliases

**Time (x-axis)** — resolved by `_ca_x_aliases`:

```
"Corrected time (s)", "corrected time", "time", "Time", "Time (s)", "t/s"
```

**Current (y-axis)** — resolved by `_ca_y_aliases` (shared with CV):

```
"WE(1).Current (A)", "Current (A)", "current", "I", "I/A", "<I>/A"
```

### Biologic MPT Format

Biologic potentiostats export `.mpt` files with semicolon delimiters and UTF-8 encoding. The CA-relevant columns are:

- `Corrected time (s)` — ohmic-drop-corrected time (preferred by the `COLUMN_MAPS` default)
- `WE(1).Current (A)` — working electrode current

Other instruments (CH Instruments, Gamry, Metrohm Autolab NOVA, Princeton PAR, PalmSens) export similar column headers that match the alias lists. The `ColumnMap.resolve()` method (`science_cli/core/technique.py`) performs case-insensitive substring matching against all aliases.

If a column cannot be resolved, the loader falls back to the first two numeric columns in order, emitting a warning.

### Resolution Priority

```python
COLUMN_MAPS: dict[str, ColumnMap] = {
    "ec-ca": ColumnMap(
        x="Corrected time (s)",
        y="WE(1).Current (A)",
        x_label="Time (s)",
        y_label="Current (A)",
        x_aliases=_ca_x_aliases,
        y_aliases=_ca_y_aliases,
    ),
}
```

---

## Data Model

The CA data container is a simple dataclass in `science_cli/library/electrochem/models.py`:

```python
@dataclass
class CAData:
    time: np.ndarray
    current: np.ndarray
    potential: float = 0.0
    metadata: dict | None = None
```

`time` and `current` are 1D NumPy arrays of equal length. The `potential` field records the step potential (the potential applied during the CA transient), typically extracted from file metadata. The `metadata` dict can carry instrument parameters (temperature, electrolyte resistance, electrode area, etc.) for downstream analysis.

---

## CLI Usage

### Core Subcommand

```bash
sci ec analyze <file> [--fit] [--steady-state]
```

The `sci ec analyze` command auto-detects the technique from the filename (via `detect_technique()` in `science_cli/core/technique.py`). Files matching patterns `_CA`, `.ca`, `ca_`, `ca-` are routed to the CA analyzer.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--fit` | `True` | Run Cottrell linear regression (i vs t^{-1/2}) |
| `--steady-state` | `True` | Compute steady-state current from tail |

Both are enabled by default. Use `--no-fit` or `--no-steady-state` to selectively disable.

### Examples

**Basic CA analysis:**

```bash
sci ec analyze 250101_Pt_electrode_CA_01.mpt
```

Output:
```
CA Analysis: 250101_Pt_electrode_CA_01.mpt
  Cottrell slope: 2.34e-4 A·√s  R²=0.998
  Steady state: 1.23e-6A
```

**Cottrell fit only (no steady-state):**

```bash
sci ec analyze 250101_Pt_electrode_CA_01.mpt --fit --no-steady-state
```

**Steady-state only:**

```bash
sci ec analyze 250101_Pt_electrode_CA_01.mpt --no-fit --steady-state
```

**Multi-file analysis (via fzf):**

```bash
sci ec analyze
```

Without a file argument, an interactive `fzf` selector opens showing all EC files in the current project's `data/raw/` directory, grouped by protocol and step. Select one or more files with Tab.

### Plotting

```bash
sci plot --technique ec-ca <file>
```

Generates a current-vs-time transient plot with the `publication-nature` theme by default. The `--technique` flag sets plot labels, axis scales, and theme defaults.

**Cottrell plot (i vs t^{-1/2}):**

```bash
sci plot --technique ec-ca <file> --type scatter
```

Override theme and output format:

```bash
sci plot --technique ec-ca <file> --theme dark --output cottrell.png
```

### General Workflow

```bash
# One-time setup
sci config init
sci config edit --global

# Create project
sci add -m project ca-experiment
sci open -m project ca-experiment

# Create protocol with CA step
sci add -m protocol -n diffusion-measurement \
  --step "1_ca-step" \
  -t ec-ca \
  -d autolab-usth

# Assign data
# Place 250101_Pt_electrode_CA_01.mpt in data/raw/
sci add -m data --fzf

# Analyze
sci ec analyze 250101_Pt_electrode_CA_01.mpt --fit

# Plot
sci plot --technique ec-ca 250101_Pt_electrode_CA_01.mpt --output ca_transient.pdf
```

---

## Cottrell Fit

The Cottrell analysis performs a linear regression of `i(t)` against `t^{-1/2}` using the `lmfit` library.

### Algorithm (`ca.py:24`)

```python
def analyze_cottrell(data: CAData) -> dict:
    t = data.time
    i = data.current
    mask = t > 0
    t_pos = t[mask]
    i_pos = i[mask]
    t_inv = 1.0 / np.sqrt(t_pos)

    def cottrell(t_inv, slope, intercept):
        return slope * t_inv + intercept

    model = Model(cottrell)
    params = model.make_params(slope=0.0001, intercept=0)
    result = model.fit(i_pos, params, t_inv=t_inv)

    return {
        "slope": result.params["slope"].value,
        "slope_stderr": result.params["slope"].stderr,
        "intercept": result.params["intercept"].value,
        "r_squared": result.rsquared,
        "reduced_chi": result.redchi,
    }
```

### Key details

1. **Zero-time exclusion**: `t = 0` is excluded to avoid division by zero. In real data, the `t = 0` point corresponds to the instant of the potential step and contains almost entirely charging current, so its exclusion is physically justified.

2. **Linear model**: `i = slope · t^{-1/2} + intercept`. The slope is proportional to `nFA C √(D/π)`. The intercept accounts for residual currents (background faradaic processes, leakage, amplifier offset).

3. **lmfit goodness-of-fit**: `r_squared` (coefficient of determination) and `reduced_chi` (reduced chi-squared = χ²/ν, where ν = N_data - N_params) quantify fit quality. For clean diffusion-controlled systems, `R² > 0.99` is typical.

4. **Slope uncertainty**: `slope_stderr` is the standard error of the slope parameter from the lmfit covariance matrix. Large stderr relative to slope indicates poor data quality or non-Cottrell behavior (convection, thin-layer effects, adsorption).

### From Slope to Diffusion Coefficient

```
slope = nFA C √(D/π)

⇒  D = π · (slope / nFA C)²
```

This requires independent knowledge of `n`, `A`, and `C`. For a known redox couple (e.g., 1 mM ferrocenemethanol in 0.1 M KCl at a Pt disk electrode of known area), the diffusion coefficient `D` can be extracted. Conversely, if `D` is known from literature, the electroactive area `A` is obtained.

### Plotting the Cottrell Fit (`plot/ca.py:40`)

```python
plot_ca_cottrell(time, current, fit_x, fit_y, flags, label)
```

This generates a scatter plot of `i` vs `t^{-1/2}` with the lmfit linear model overlaid as a red line. The `fit_x` / `fit_y` arrays are the predicted values from the fit, enabling visual assessment of linearity.

---

## Steady-State Current

### Algorithm (`ca.py:62`)

```python
def analyze_steady_state(data: CAData, fraction: float = 0.2) -> dict:
    t = data.time
    i = data.current
    n = len(t)
    tail_start = int(n * (1 - fraction))
    tail_i = i[tail_start:]

    return {
        "steady_state_current": float(np.mean(tail_i)),
        "steady_state_std": float(np.std(tail_i)),
        "steady_state_time": float(t[tail_start]),
        "steady_state_fraction": fraction,
    }
```

### Key details

1. **Tail fraction**: The last 20% of data points are used by default. This is adjustable via the `fraction` parameter (0.0–1.0). For very long transients (tens of seconds), a smaller fraction may suffice; for short transients (milliseconds), a larger fraction may be needed to capture the plateau.

2. **Mean and standard deviation**: `steady_state_current` is the arithmetic mean of the tail current. `steady_state_std` quantifies the noise level at the plateau. High std relative to mean suggests instability (convection, bubbles, electrochemical noise from pitting or metastable passivation).

3. **Steady-state time**: The time at which the tail window begins (`t[tail_start]`). This helps interpret whether the system actually reached a plateau. If the current is still decaying at the end of the transient, the reported steady-state value overestimates the true plateau.

### Physical Interpretation

In unstirred solution with a macroelectrode, the Cottrell decay never truly reaches a steady state — `i(t) → 0` as `t → ∞` (theoretically). The "steady-state" current reported here is the current at the end of the measurement window, which can be compared to:

- **Ultramicroelectrodes (UMEs)**: At UMEs (radius < 25 μm), radial diffusion dominates and a true steady-state current is reached: `i_ss = 4 n F D C r` (for a disk UME). This is independent of time.
- **Rotating disk electrodes (RDEs)**: The Levich current `i_lim = 0.62 n F A D^{2/3} ω^{1/2} ν^{-1/6} C` is reached after the Cottrell decay crosses over to convective steady state.
- **Thin-layer cells**: When the diffusion layer thickness `√(πDt)` exceeds the cell thickness `l`, the current drops exponentially to a thin-layer steady state.

The comparison between Cottrell fit and steady-state current provides a diagnostic: if the ratio `steady_state_current / Cottrell_predict(t_end)` is significantly greater than 1, convection or non-planar diffusion is likely active.

---

## YAML Schema

When CA analysis is run within a protocol context (via `sci add -m data` and `sci ec analyze`), results are automatically saved to `<step_dir>/results/ec-ca_analysis.yaml` via `write_analysis_yaml()` in `science_cli/core/analysis_output.py`.

```yaml
technique: ec-ca
instrument: autolab-usth
devices: Pt-electrode
timestamp: "2026-06-15T14:30:00Z"
cottrell:
  slope: 2.34e-04
  slope_stderr: 1.21e-06
  intercept: -5.32e-08
  r_squared: 0.9982
  reduced_chi: 3.45e-12
steady_state:
  steady_state_current: 1.23e-06
  steady_state_std: 4.56e-08
  steady_state_time: 4.0
  steady_state_fraction: 0.2
```

### Schema Details

| Key | Type | Description |
|-----|------|-------------|
| `technique` | string | Always `"ec-ca"` |
| `instrument` | string | Instrument slug from protocol device assignment |
| `devices` | string | Device/sample description from protocol |
| `timestamp` | string (ISO 8601) | UTC timestamp of analysis |
| `cottrell.slope` | float | Cottrell slope `A·√s` |
| `cottrell.slope_stderr` | float | Standard error of slope (from lmfit covariance) |
| `cottrell.intercept` | float | Intercept current (A) |
| `cottrell.r_squared` | float | Coefficient of determination (R²) |
| `cottrell.reduced_chi` | float | Reduced chi-squared (χ²/ν) |
| `steady_state.steady_state_current` | float | Mean current of tail window (A) |
| `steady_state.steady_state_std` | float | Standard deviation of tail current (A) |
| `steady_state.steady_state_time` | float | Time at start of tail window (s) |
| `steady_state.steady_state_fraction` | float | Fraction of data used for tail (default 0.2) |

### Schema Notes

- The `cottrell` block is present only when `--fit` is enabled (default: on). If the fit fails (lmfit exception, e.g., all data points are NaN), the block contains `error: str` instead.
- The `steady_state` block is present only when `--steady-state` is enabled (default: on).
- `reduced_chi` is meaningful for comparing fits across different data ranges. Values much smaller than 1 may indicate overestimated error bars; values much larger than 1 indicate poor fit.
- `slope_stderr` of zero indicates that lmfit could not estimate the parameter uncertainty (singular covariance matrix), typically from insufficient data or collinear parameters.

---

## Plot Reference

Two plot functions are available in `science_cli/plot/ca.py`:

### CA Decay (`plot_ca_decay`)

```python
plot_ca_decay(time, current, flags, label, ax)
```

- **Type**: Current (A) vs Time (s), linear axes
- **Use**: Raw data visualization — inspect transient shape, noise level, capacitive spike at t=0
- **Default theme**: `publication-nature`
- **Implementation**: Delegates to `plot_line()` with axis labels and linear x-scale

### Cottrell Plot (`plot_ca_cottrell`)

```python
plot_ca_cottrell(time, current, fit_x, fit_y, flags, label)
```

- **Type**: Scatter (data) + line (fit) — Current (A) vs `t^{-1/2} (s^{-1/2})`
- **Use**: Assess linearity of Cottrell regression; detect deviations at short or long times
- **Default theme**: `default`
- **Implementation**: Filters `t > 0`, computes `t_inv_sqrt = 1/√t`, plots scatter of data and red line of lmfit model

### Plot Presets

Registered in `__init__.py`:

```python
PLOT_PRESETS: dict[str, dict] = {
    "ec-ca": {"type": "line", "xlabel": "Time (s)", "ylabel": "Current (A)"},
}
```

Used automatically when invoking `sci plot --technique ec-ca`.

---

## Interpretation Guidelines

### Good Cottrell Behavior

- **R² > 0.995**: Clean diffusion-limited decay across the transient
- **Intercept near zero**: Minimal background current or charging contribution
- **Steady-state std < 5% of mean**: Stable plateau, no convection or noise
- **Cottrell plot linear over 2+ decades of t**: Confirms semi-infinite linear diffusion

### Red Flags

| Observation | Possible Cause |
|-------------|---------------|
| R² < 0.98 | Non-Cottrell behavior: convection, adsorption, ohmic drop, fouling |
| Large negative intercept | Background reduction at step potential (e.g., oxygen reduction) |
| Large positive intercept | Charging current not fully decayed (measurement too short) |
| Current increases after step | Nucleation and growth (i-t transient with maximum) |
| Steady-state >> Cottrell extrapolation | Convection, forced mass transport, thin-layer depletion |
| Steady-state << Cottrell extrapolation | Electrode passivation, film formation, analyte depletion |
| High reduced_chi | Poor model; residuals not normally distributed |
| Slope stderr > 10% of slope | Insufficient data, noisy signal, or non-Cottrell behavior |
| Oscillations on tail | Electromagnetic interference, bubble formation, unstable reference |

### Short-Time Artifacts

At very short times (sub-millisecond for macroelectrodes, sub-microsecond for UMEs), the current is dominated by:

1. **Charging current**: `i_c(t) = (ΔE / R_s) · exp(-t / τ)` where `τ = R_s C_dl`. The RC time constant of the cell determines the earliest time at which Cottrell behavior applies. Typically, `t > 5τ` is safe.

2. **Ohmic drop**: If the solution resistance `R_s` is large (> kΩ) and the step potential `ΔE` is large (> 1 V), the applied potential differs from the true interfacial potential during the charging period.

3. **Instrument bandwidth**: Potentiostat rise time (typically 1–10 μs for commercial instruments) limits the fidelity of the earliest data points.

---

## Advanced: Double-Potential Step Chronoamperometry

While the current implementation focuses on single-potential-step CA, the Cottrell analysis framework extends naturally to double-potential-step experiments:

1. **Forward step**: `E_init → E_step` (the standard analysis above)
2. **Reverse step**: `E_step → E_init` (or to a second step potential)

For a reversible couple, the reverse-step current is:

```
i_rev(t) = i_forward(t) - i_forward(t - τ)
```

where `τ` is the forward step duration. The ratio `i_rev / i_forward` at matched times yields the ratio `D_ox / D_red` and can distinguish reversible from quasi-reversible kinetics.

This analysis is available for extension via the `CAData` data model — the same `analyze_cottrell` function applies to each segment independently.

---

## See Also

- [electrochemistry.md](electrochemistry.md) — General EC workflow: Biologic MPT format, column maps, multi-technique projects
- [overview.md](../overview.md) — General tool overview, project lifecycle, command reference
- [cyclic-voltammetry.md](cyclic-voltammetry.md) — CV analysis: peak detection, scan rate study, Randles-Sevcik
- [impedance-spectroscopy.md](impedance-spectroscopy.md) — EIS analysis: circuit fitting, Kramers-Kronig, Warburg
- [analysis-yaml.md](../schemas/analysis-yaml.md) — YAML schema specifications for all techniques
- [plot.md](../reference/commands/plot.md) — Plot system: themes, output formats, per-technique flags
- [analyze.md](../reference/commands/analyze.md) — Analysis command: flags, dispatch, YAML output
- **Source**: `science_cli/library/electrochem/ca.py` — Cottrell fit and steady-state implementation
- **Source**: `science_cli/plot/ca.py` — CA and Cottrell plot functions
