# IV Sweeps — Current-Voltage Characterization

## Overview

Current-voltage (IV) sweeps are the foundational electrical characterization
technique for memristors and resistive switching devices. A voltage stimulus is
applied across the device terminals while the resulting current is measured,
producing a characteristic curve that reveals switching behaviour, conduction
mechanisms, and device quality.

### Sweep Topologies

**DC staircase sweep** — The most common topology. Voltage is stepped in
discrete increments with a hold time at each step. A complete sweep consists of
a forward branch (0 → +V_max or 0 → -V_max) followed by a reverse branch
(+V_max → -V_max or -V_max → +V_max). The resulting I(V) trace reveals
hysteresis when the forward and reverse branches do not coincide.

**Linear ramp sweep** — Voltage is swept continuously (analogue ramp) rather
than stepped. Produces smoother I(V) traces but requires a source-measure unit
with analogue sweep capability. Scan rate in V/s is a critical parameter that
affects switching dynamics.

**Pulsed IV** — Short voltage pulses (typically µs to ms) are applied instead
of DC steps. Used to study ultrafast switching dynamics and to avoid self-heating
artefacts that distort DC measurements. Not yet supported by science-cli's IV
analysis module (use the pulse-endurance technique instead).

### Key Switching Metrics

| Metric | Symbol | Definition |
|--------|--------|------------|
| Set voltage | V_set | Voltage at which the device switches from HRS to LRS |
| Reset voltage | V_reset | Voltage at which the device switches from LRS to HRS |
| ON/OFF ratio | R_ON/R_OFF | Ratio of currents at a read voltage in the ON and OFF states |
| Compliance current | I_cc | Current limit enforced by the SMU during set switching |
| Hysteresis area | H | Area enclosed by the forward and reverse sweep branches |
| Yield | η | Fraction of sweeps that exhibit switching |
| Switching uniformity | σ(V_set) | Cycle-to-cycle variability of the set voltage |

### Sub-Techniques

**iv-sweep** — Standard DC sweep for resistive switching characterisation.
Detects V_set, V_reset, ON/OFF ratio, and hysteresis. Supports both volatile
(V_set only) and bipolar (V_set + V_reset) modes. The primary technique for
memristor and junction characterisation.

**iv-breakdown** — Ramped voltage stress to device failure. Extracts breakdown
voltage V_bd by identifying the voltage at which the leakage current exceeds a
user-defined threshold (default 1 µA). Used for dielectric quality assessment
and endurance lifetime estimation.

**iv-leakage** — Low-bias leakage current measurement, typically at ±0.1–1 V.
Extracts Ohmic resistance from a linear fit in the ±0.1 V window. Used for
baseline device quality screening before switching tests.

These sub-techniques share the same data format and analysis pipeline; they are
distinguished by filename convention (e.g. `breakdown_001.dat` →
iv-breakdown, `leakage_001.dat` → iv-leakage, otherwise → iv-sweep).

---

## Volatile vs Bipolar Analysis

The science-cli IV analysis module supports two operational modes that reflect
fundamentally different device physics.

### Volatile Mode (V_set Only)

In volatile mode, the device switches from a high-resistance state (HRS) to a
low-resistance state (LRS) at V_set but does not switch back during the sweep.
The device remains in the LRS after the voltage is removed, or relaxes back to
HRS over time (transient volatility). There is no V_reset event.

Volatile behaviour is characteristic of:
- Diffusive memristors where the conducting filament dissolves spontaneously
- Threshold switching selectors (OTS) that return to HRS below a holding voltage
- Forming-free devices that exhibit a one-time permanent set

The `analyze_volatile()` function in `library/iv/volatile.py` computes:

```
v_set_mean  = mean(V_set over all switching events)
v_set_std   = standard deviation
v_set_cv    = coefficient of variation (std/mean)
set_yield   = n_switching_events / n_sweeps
```

### Bipolar Mode (V_set + V_reset)

In bipolar mode, the device switches ON at V_set (forward bias) and switches
back OFF at V_reset (reverse bias). The IV trace forms a pinched hysteresis
loop crossing through the origin. Both switching voltages are extracted.

Bipolar behaviour is characteristic of:
- Filamentary RRAM with electrochemical metallisation (ECM) or valence change
  mechanism (VCM)
- Interface-type switching where the Schottky barrier is modulated
- Complementary resistive switches (CRS) with nested hysteresis

The `analyze_bipolar()` function in `library/iv/bipolar.py` computes:

```
v_set_mean, v_set_std     — same as volatile
v_reset_mean, v_reset_std — V_reset statistics
on_off_ratio_mean         — mean ON/OFF ratio
hysteresis_area_mean      — mean hysteresis loop area
```

### Device Type Routing

The analysis pipeline routes to volatile or bipolar mode using the device type
declared in the protocol YAML:

- `memristor` → volatile mode (expects V_set only)
- `junction` → bipolar mode (expects V_set + V_reset)

Override with the `--vset-only` CLI flag, which forces volatile analysis
regardless of the device type declaration.

---

## Vset/Vreset Extraction

### Derivative-Based Detection

Both V_set and V_reset are detected using the first derivative dI/dV. The
algorithm finds the voltage where the rate of current change is maximal:

- V_set: argmax(dI/dV) in the forward sweep direction — the point of steepest
  current increase as the device turns ON.
- V_reset: argmin(dI/dV) in the reverse sweep direction — the point of steepest
  current decrease as the device turns OFF.

The detection is implemented in `library/iv/metrics.py` (imported by
`switching.py` as `detect_vset`, `detect_vreset`). The raw dI/dV is computed
as np.diff(current) / np.diff(voltage), then smoothed with a moving average
filter before peak finding.

### Abrupt vs Gradual Switching

- **Abrupt switching**: dI/dV shows a sharp, narrow peak. V_set is clearly
  defined. Typical of filamentary RRAM with fast conductive bridge formation.
- **Gradual switching**: dI/dV shows a broad, shallow peak. V_set is the
  midpoint of the transition. Typical of interface-type switching or devices
  with distributed filament growth.

The module does not yet classify abrupt vs gradual automatically; this remains
a visual inspection task using `sci iv plot`.

### Compliance Current Handling

When the current reaches the SMU compliance limit (I_cc), the voltage continues
to sweep but the current is clamped. The derivative dI/dV → 0 in compliance,
so compliance-clipped traces are excluded from V_set detection. The compliance
value is recorded in the YAML output if provided.

---

## ON/OFF Ratio Computation

The ON/OFF ratio is computed as:

```
ON/OFF = I(+V_read) / |I(-V_read)|
```

where V_read defaults to +0.1 V. The algorithm finds the measured voltage
points closest to ±V_read and takes the corresponding current ratio.

The implementation in `extract_on_off_ratio()` (library/iv/analyze.py:390)
searches the voltage array for the indices minimising |V - V_read| and
|V + V_read|, then returns:

```
on_off_ratio:  ratio of I_on / I_off
I_on_A:        current at +V_read
I_off_A:       current at -V_read
V_read:        read voltage (absolute)
V_on_actual:   actual voltage used (nearest to +V_read)
V_off_actual:  actual voltage used (nearest to -V_read)
```

V_read is configurable in the protocol YAML or passed as a parameter.

A ratio > 10 is generally considered acceptable for memory operation; ratios
of 100–1000 are typical of high-performance filamentary RRAM. Ratios < 3 may
indicate poor switching or a device that is stuck in the ON state.

---

## Conduction Model Fitting

The `fit_iv_curve()` function in `library/iv/analyze.py:125` fits the measured
I(V) data against four physical conduction models. Each fit returns goodness
metrics (R², RMSE, AIC, BIC) that allow model selection.

### Ohmic (I = V/R)

```
I = V / R
```

Linear fit to the low-bias region (|V| < 0.1 V). Slope = 1/R. If fewer than
3 points exist in the ±0.1 V window, the fit falls back to all available data.

**Physical meaning**: The device behaves as a linear resistor. Dominant at
low bias where the conducting filament (or Ohmic contact) governs transport.

### Schottky Emission (ln I ∝ √V)

```
ln(I) = a·√V + b      (V > 0.1 V, forward bias)
```

Fit to the high-bias forward region. The slope 'a' relates to the barrier
height φ_B and the material's Richardson constant A* and dielectric constant
ε_r. The implementation does not compute φ_B directly (requires material
constants) but reports `needs material constants (A*, T, ε_r)` as a placeholder.

**Physical meaning**: Thermionic emission over a Schottky barrier at the
metal-semiconductor interface. Dominant in interface-type switching and
Schottky diodes at moderate forward bias.

### Space-Charge-Limited Current (log I ∝ n·log V)

```
log(I) = n·log(V) + b      (V > 0, I > 0)
```

The exponent 'n' distinguishes transport regimes:
- n < 1.3: Ohmic (background carriers dominate)
- n ≈ 2: Trap-filled SCLC (trap-limited conduction, Mott-Gurney law)
- n > 3: Steep injection (deep traps or filament formation)

The implementation reports an `interpretation` field: `Ohmic`, `Transition`,
or `SCLC (trap-filled)`.

**Physical meaning**: Current is limited by space charge rather than electrode
injection. Dominant in insulating films at moderate bias before the onset of
filamentary switching.

### Poole-Frenkel Emission (ln I/V ∝ √V)

```
ln(I/V) = a·√V + b      (V > 0.1 V)
```

Similar functional form to Schottky but distinct mechanism: field-assisted
thermal emission from bulk trap states rather than from the electrode interface.
The slope 'a' is related to the dielectric constant of the insulator.

**Physical meaning**: Bulk-limited conduction via trap states in the insulator.
Dominant at high field in defect-rich oxide films.

### Model Selection

Compare the AIC (Akaike Information Criterion) and BIC (Bayesian Information
Criterion) metrics — lower values indicate a better fit penalised for model
complexity. R² alone can be misleading for nonlinear models.

---

## CLI Commands

The `sci iv` command group provides six subcommands. Commands marked as
(stub) print a placeholder message — their argument interfaces are defined
but the analysis logic is not yet wired to the CLI entry point.

### sci iv ls

List IV sweep files in the current step directory.

```bash
sci iv ls
sci iv ls --step my_step
```

`--step` filters to a specific step subdirectory. Currently a stub.

### sci iv info

Display file metadata: column names, shape, voltage/current range.

```bash
sci iv info
sci iv info data/iv_sweep_001.dat
```

If no file is given, operates on the first IV file found. Currently a stub.

### sci iv plot

Plot IV curves with overlay and multi-panel support.

```bash
sci iv plot
sci iv plot --overlay
sci iv plot --all
sci iv plot --row 1 --col 2
```

| Flag | Effect |
|------|--------|
| `--overlay` | Overlay all traces on a single axes |
| `--all` | Plot every file in the step directory |
| `--row N` | Filter to a specific crossbar row |
| `--col N` | Filter to a specific crossbar column |

Currently a stub. The Nature-style styling constants are defined in
`device_cli.py` (`ACCS_NATURE_STYLE` dict with Arial font family, 10 pt
title, 9 pt axis labels, 8 pt ticks, 1.2 pt line width).

### sci iv analyze

Perform IV analysis with mode selection.

```bash
sci iv analyze
sci iv analyze --vset-only
sci iv analyze --row 1 --col 2
```

| Flag | Effect |
|------|--------|
| `--vset-only` | Force volatile mode (V_set only, no V_reset) |
| `--row N` | Filter to a specific crossbar row |
| `--col N` | Filter to a specific crossbar column |

Prints the analysis mode and produces a `results/iv-sweep_analysis.yaml` file.
Currently a stub from the CLI standpoint — the analysis functions in
`library/iv/volatile.py`, `library/iv/bipolar.py`, and `library/iv/analyze.py`
are fully implemented and tested but not yet wired to the `cmd_analyze` entry
point.

### sci iv sync

Sync IV sweep data to an SQLite cache for fast crossbar queries.

```bash
sci iv sync
```

Currently a stub. Intended to pre-process all IV files in a step directory
into a relational cache, enabling crossbar-level queries (e.g. "show all
devices in row 3 with V_set > 1 V").

### sci iv dashboard

Launch an interactive Plotly HTML dashboard.

```bash
sci iv dashboard
```

Currently a stub. Intended to open a browser-based dashboard showing IV
curve thumbnails, statistics tables, and per-device parameter distributions.

---

## Analysis Pipeline

The full analysis pipeline from raw data to YAML output proceeds as follows:

```
Raw IV data file
    │
    ▼
1. Technique auto-detection
   ─ Filename matching (breakdown_* → iv-breakdown,
     leakage_* → iv-leakage, default → iv-sweep)
    │
    ▼
2. Data loading (data_loader.py)
   ─ Device config determines delimiter, header rows, column mapping
   ─ Loads voltage, current, and optional time arrays
    │
    ▼
3. Sweep metadata extraction
   ─ detect_sweep_segments() splits the trace at voltage reversals
   ─ extract_scan_rate() estimates V/s from time or inflection points
   ─ Returns ordered list of forward/reverse segments
    │
    ▼
4. Mode-dependent analysis
   ─ Device type == "memristor" or --vset-only → volatile path
   ─ Device type == "junction" → bipolar path
   ─ Calls analyze_volatile() or analyze_bipolar()
    │
    ▼
5. Resistance extraction
   ─ Linear fit in ±0.1 V window via extract_resistance()
   ─ Returns R (Ω), R_stderr, r_squared, slope, intercept
    │
    ▼
6. Vset/Vreset detection
   ─ Derivative-based: dI/dV maxima for V_set, minima for V_reset
   ─ Calls detect_vset() and detect_vreset() from metrics module
    │
    ▼
7. ON/OFF ratio calculation
   ─ I(+V_read) / I(-V_read) at default V_read = 0.1 V
   ─ Calls extract_on_off_ratio()
    │
    ▼
8. Optional conduction model fitting
   ─ fit_iv_curve() with ohmic/schottky/sclc/pool-frenkel models
   ─ R², RMSE, AIC, BIC for each model
    │
    ▼
9. YAML output
   ─ write_analysis_yaml() produces <step>/results/iv-sweep_analysis.yaml
   ─ Includes technique, instrument, devices, timestamp envelope
```

---

## YAML Schema

The output YAML file follows this structure, produced by
`write_analysis_yaml()` in `core/analysis_output.py:24`:

```yaml
technique: iv-sweep
instrument: keithley-2400
devices: memristor
timestamp: "2026-06-15T12:00:00Z"

analysis:
  mode: volatile

  parameters:
    v_set: 1.23
    v_set_std: 0.045
    v_set_cv: 0.037
    v_set_min: 1.10
    v_set_max: 1.35
    on_off_ratio: 45.2
    compliance: 0.001

    # Bipolar only
    v_reset: -0.89
    v_reset_std: 0.032
    v_reset_cv: 0.036
    hysteresis_area: 0.42

    # Volatile only
    set_yield: 92.5

  n_events: 40

sweep_metadata:
  scan_rate_v_s: 0.5
  voltage_range: 5.0
  segments:
    - start_idx: 0
      end_idx: 50
      direction: forward
      sweep_rate_v_s: 0.48
      voltage_range: 2.5
      duration_s: 5.2
    - start_idx: 50
      end_idx: 100
      direction: reverse
      sweep_rate_v_s: 0.52
      voltage_range: 5.0
      duration_s: 9.6

conduction_fits:
  ohmic:
    model: ohmic
    params:
      R_ohm: 1250000.0
      slope: 8.0e-07
      intercept: 2.1e-09
    metrics:
      r_squared: 0.992
      rmse: 3.4e-10
      aic: -42.3
      bic: -39.1
    success: true
  schottky:
    model: schottky
    params:
      schottky_slope: 3.21
      schottky_intercept: -8.45
      phi_b_eV: "needs material constants (A*, T, \u03b5_r)"
    metrics:
      r_squared: 0.971
      rmse: 2.1e-09
      aic: -28.7
      bic: -25.5
    success: true
  sclc:
    model: sclc
    params:
      n_exponent: 1.85
      log_intercept: -6.32
      interpretation: SCLC (trap-filled)
    metrics:
      r_squared: 0.988
      rmse: 5.6e-10
      aic: -36.1
      bic: -32.9
    success: true
  pool-frenkel:
    model: pool-frenkel
    params:
      pf_slope: 2.78
      pf_intercept: -10.12
    metrics:
      r_squared: 0.965
      rmse: 4.2e-09
      aic: -24.3
      bic: -21.1
    success: true
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `technique` | string | Technique slug, always `iv-sweep` |
| `instrument` | string | SMU identifier (from protocol YAML) |
| `devices` | string | Device type: `memristor` or `junction` |
| `timestamp` | string | ISO 8601 UTC generation time |
| `analysis.mode` | string | `volatile` or `bipolar` |
| `analysis.parameters.v_set` | float | Mean set voltage (V) |
| `analysis.parameters.v_set_std` | float | Set voltage standard deviation (V) |
| `analysis.parameters.v_set_cv` | float | Coefficient of variation (σ/μ) |
| `analysis.parameters.v_set_min` | float | Minimum V_set observed (V) |
| `analysis.parameters.v_set_max` | float | Maximum V_set observed (V) |
| `analysis.parameters.v_reset` | float | Mean reset voltage (V, bipolar only) |
| `analysis.parameters.v_reset_std` | float | Reset voltage std dev (V, bipolar only) |
| `analysis.parameters.on_off_ratio` | float | Mean ON/OFF ratio |
| `analysis.parameters.compliance` | float | Compliance current (A) |
| `analysis.parameters.hysteresis_area` | float | Hysteresis loop area (V·A, bipolar only) |
| `analysis.parameters.set_yield` | float | Switching yield (%, volatile only) |
| `analysis.n_events` | int | Number of detected switching events |
| `sweep_metadata.scan_rate_v_s` | float | Estimated global sweep rate (V/s) |
| `sweep_metadata.voltage_range` | float | Full voltage range (V) |
| `sweep_metadata.segments` | list | Ordered list of sweep segments |
| `sweep_metadata.segments[].direction` | string | `forward` or `reverse` |
| `conduction_fits.*.model` | string | Model name |
| `conduction_fits.*.params` | dict | Model-specific fit parameters |
| `conduction_fits.*.metrics.r_squared` | float | Coefficient of determination |
| `conduction_fits.*.metrics.rmse` | float | Root mean squared error (A) |
| `conduction_fits.*.metrics.aic` | float | Akaike Information Criterion |
| `conduction_fits.*.metrics.bic` | float | Bayesian Information Criterion |
| `conduction_fits.*.success` | bool | Whether the fit converged |

---

## Examples

### List available IV sweep files

```bash
sci iv ls
sci iv ls --step forming
```

### Inspect an IV data file

```bash
sci iv info data/iv_sweep_001.dat
```

### Plot all sweeps with overlay

```bash
sci iv plot --all --overlay
```

### Plot a specific crossbar device

```bash
sci iv plot --row 3 --col 5
```

### Analyze with default (bipolar) mode

```bash
sci iv analyze
```

### Force volatile mode analysis

```bash
sci iv analyze --vset-only
```

### Analyze a specific crossbar device

```bash
sci iv analyze --row 1 --col 2
```

### Sync IV data to SQLite cache

```bash
sci iv sync
```

### Launch the interactive dashboard

```bash
sci iv dashboard
```

### Full workflow: list, inspect, analyze

```bash
sci iv ls
sci iv info data/iv_sweep_001.dat
sci iv analyze --vset-only --row 0 --col 0
```

---

## Source Code Reference

| Module | Key Functions |
|--------|---------------|
| `library/iv/analyze.py` | `extract_resistance()`, `extract_scan_rate()`, `extract_breakdown_voltage()`, `fit_iv_curve()`, `extract_on_off_ratio()`, `detect_sweep_segments()` |
| `library/iv/volatile.py` | `analyze_volatile()`, `analyze_volatile_to_yaml()`, `volatile_summary()` |
| `library/iv/bipolar.py` | `analyze_bipolar()`, `analyze_bipolar_to_yaml()`, `bipolar_summary()` |
| `library/iv/switching.py` | `analyze_switching_statistics()` — Weibull fits |
| `library/iv/device_cli.py` | `build_iv_parser()`, `cmd_ls`, `cmd_info`, `cmd_plot`, `cmd_analyze`, `cmd_sync`, `cmd_dashboard` |
| `cli/commands/iv.py` | `iv_handler()` — route subcommand to device_cli |
| `core/analysis_output.py` | `write_analysis_yaml()` — universal YAML writer |

## See Also

- `reference/commands/iv.md` — full CLI reference
- `overview.md` — technique taxonomy
- `schemas/analysis-yaml.md` — schema specification
- `tutorials/iv-characterization.md` — practical measurement guide
- `crossbar-characterization.md` — crossbar-level analysis
