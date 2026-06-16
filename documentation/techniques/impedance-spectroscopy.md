# Electrochemical Impedance Spectroscopy (EIS)

## Overview

Electrochemical impedance spectroscopy measures the frequency-dependent impedance of an electrochemical system by applying a small-amplitude sinusoidal AC perturbation and measuring the resulting current response. The perturbation is typically ±10 mV (or ±5–20 mV) superimposed on a DC bias potential, swept across a frequency range from ~1 MHz down to ~1 mHz.

### Fundamental Principle

The AC perturbation voltage at angular frequency ω = 2πf is:

```
V(t) = V₀ · sin(ωt)
```

The resulting current response is phase-shifted and amplitude-modulated:

```
I(t) = I₀ · sin(ωt + φ)
```

The complex impedance Z(ω) is defined as the frequency-domain ratio:

```
Z(ω) = V(ω) / I(ω) = Z' + jZ'' = |Z| · e^{jφ}
```

Where:
- **Z'** = real part (resistive, in-phase component)
- **Z''** = imaginary part (capacitive/inductive, out-of-phase component)
- **|Z|** = magnitude = √(Z'² + Z''²)
- **φ** = phase angle = arctan(Z''/Z')

### Nyquist Representation

A Nyquist plot shows Z' on the x-axis versus -Z'' on the y-axis (negative Z'' so capacitive arcs point upward). Each point corresponds to a single frequency, with high-frequency data on the left and low-frequency data on the right.

Key features of a Nyquist plot:
- **High-frequency intercept** (leftmost point, ω → ∞): solution/electrolyte resistance R_s
- **Semicircle**: parallel combination of charge-transfer resistance R_ct and double-layer capacitance C_dl. The semicircle diameter equals R_ct.
- **Characteristic frequency**: ω_max = 1 / (R_ct · C_dl), at the top of the semicircle
- **Low-frequency tail**: 45° line → Warburg diffusion impedance (semi-infinite linear diffusion)
- **Low-frequency intercept** (rightmost, ω → 0): R_s + R_ct (total DC resistance if no diffusion limitation)

### Bode Representation

A Bode plot shows log|Z| and phase angle φ versus log frequency on the same figure (twin y-axes). The Bode format is preferred for:
- Comparing high- and low-frequency behavior on equal footing
- Identifying time constants as peaks/valleys in phase
- Presenting data when the Z range spans many orders of magnitude

At very high frequencies, |Z| → R_s (phase → 0°). At very low frequencies, |Z| → R_s + R_ct (phase → 0° for a simple Randles cell). In the mid-frequency region, the capacitive phase approaches -90° (ideal capacitor) or -(90 × n)° (CPE with exponent n).

### Time Constants and Process Separation

Each physical process (charge transfer, ion diffusion, adsorption, bulk transport) has a characteristic time constant τ = RC = 1/ω_max. Processes with time constants separated by at least 1–2 orders of magnitude are resolvable in the impedance spectrum as distinct semicircles or phase peaks. Overlapping time constants produce depressed or merged arcs that require deconvolution via circuit fitting.

---

## Data Format

The `ec-eis` technique resolves frequency, real impedance, imaginary impedance, magnitude, and phase columns from arbitrary file headers using the `ColumnMap` alias system defined in `science_cli/library/electrochem/__init__.py:78`.

### Column Aliases

The first alias match wins in order of priority. EIS columns are stored in `extras` because there are five primary fields (not just x/y).

**Frequency aliases (`_eis_f_aliases`):**
```
Frequency (Hz)
Frequency
f/Hz
freq
frequency
f
```

**Real impedance aliases (`_eis_zr_aliases`):**
```
Z' (Ω)
Z'
Re(Z)
ReZ
Zre
Z_real
z'
z_re
```

**Imaginary impedance aliases (`_eis_zi_aliases`):**
```
-Z'' (Ω)
-Z''
Z''
-Z"
Im(Z)
ImZ
Zim
Z_imag
z''
z_im
```

Note that `-Z''` (with leading minus sign) is the Autolab convention where the stored column values are already positive for capacitive impedance. Other instruments store raw Z'' values that are negative for capacitive behavior. The data loader handles both conventions — see `_ensure_neg_imag()` in plot/eis.py.

### ColumnMap Definition

The EIS column map in `science_cli/library/electrochem/__init__.py:78`:

```python
COLUMN_MAPS["ec-eis"] = ColumnMap(
    x="Z' (Ω)", y="-Z'' (Ω)",
    x_label="Z' (Ω)", y_label="-Z'' (Ω)",
    x_aliases=_eis_zr_aliases,
    y_aliases=_eis_zi_aliases,
    extras={
        "frequency": "Frequency (Hz)",
        "z_real": "Z' (Ω)", "z_imag": "-Z'' (Ω)",
        "magnitude": "|Z| (Ω)", "phase": "Phase (°)",
        "_f_aliases": _eis_f_aliases,
    },
)
```

The `extras` dictionary holds the six non-primary fields that are EIS-specific. The `_f_aliases` key stores the frequency column alias list for internal column resolution.

### Biologic MPT Format

Files from Biologic potentiostats use `.mpt` extension with semicolon (`;`) delimiter and UTF-8 encoding. The header contains metadata rows followed by column headers. Common EIS columns in MPT files:

```
Frequency (Hz);Z' (Ω);-Z'' (Ω);|Z| (Ω);Phase (°)
```

The column alias mapper resolves these automatically regardless of the exact column label. The `.mpt` extension alone is sufficient for technique detection — it is the only extension-based detector in the system (`technique.py:115`, `BUILTIN_TECHNIQUES`), matching the Biologic software output convention.

### Generic CSV/Text Format

Any comma-, tab-, semicolon-, or whitespace-delimited file with headers matching the alias lists above works. `science-cli` auto-detects delimiter and encoding. At minimum, the file must have `frequency`, `Z'`, and `Z''` columns. Magnitude and phase are optional — they are computed internally from the complex impedance if absent.

### EISData Model

Loaded EIS data is stored in the `EISData` dataclass (`models.py:27`):

```python
@dataclass
class EISData:
    frequency: np.ndarray
    impedance: np.ndarray  # complex array
    temperature: float = 0.0
    metadata: dict | None = None

    @property
    def real(self) -> np.ndarray:       # Z' — real part
    @property
    def imag(self) -> np.ndarray:       # Z'' — imaginary part
    @property
    def magnitude(self) -> np.ndarray:  # |Z|
    @property
    def phase(self) -> np.ndarray:      # degrees
```

The `impedance` field holds the full complex array from which real, imaginary, magnitude, and phase are computed via properties. The `temperature` field can be set for temperature-dependent studies.

---

## CLI Usage

### Analyzing EIS Data

```bash
sci ec analyze <file> [--circuit RRC|RQR|R_s(C[RW])|R_s(Q[RW])|RC|Randles] [--kk]
```

The `--circuit` flag selects the equivalent circuit model for fitting. The `--kk` flag runs the Kramers-Kronig consistency test. Circuit fitting runs by default (model: `RRC` if not specified); KK test requires the explicit `--kk` flag.

#### Default Analysis

```bash
sci ec analyze 2105_HfOx_EIS_001.mpt
```

Output:

```
EIS Analysis: 2105_HfOx_EIS_001.mpt
  Circuit fit: RRC
    Rs: 120.3 Ω
    Rct: 4520.1 Ω
    Cdl: 3.21e-06 F
    R²: 0.994
```

#### With KK Test

```bash
sci ec analyze 2105_HfOx_EIS_001.mpt --kk
```

Output:

```
EIS Analysis: 2105_HfOx_EIS_001.mpt
  KK test: ✓ passed  (score=2.133)
  Circuit fit: RRC
    Rs: 120.3 Ω
    Rct: 4520.1 Ω
    Cdl: 3.21e-06 F
    R²: 0.994
```

#### Selecting a Different Circuit

```bash
sci ec analyze 2105_HfOx_EIS_001.mpt --circuit R_s(Q[RW])
```

Output:

```
EIS Analysis: 2105_HfOx_EIS_001.mpt
  Circuit fit: R_s(Q[RW])
    Rs: 118.7 Ω
    Q_mag: 2.89e-06 F·s^(n-1)
    Q_n: 0.87
    Rct: 4601.2 Ω
    sigma: 152.3 Ω·s^(-1/2)
    R²: 0.998
```

### Using the `eis` Subcommand

The dedicated EIS subcommand provides additional operations:

```bash
sci eis kk <file>                        # Kramers-Kronig test only
sci eis fit <file> [--circuit MODEL]     # Circuit fitting only
sci eis batch                            # Batch fit all EIS files in project
sci eis simulate                         # (stub)
sci eis export <file> [--circuit MODEL]  # Export fit to JSON
```

#### KK Test Subcommand

```bash
sci eis kk 2105_HfOx_EIS_001.mpt
```

Output:

```
KK Test: 2105_HfOx_EIS_001.mpt
  Status: ✓ passed
  Score:  2.1334
  Points: 10
```

#### Batch Fitting

Batch fits all EIS files in the current project's `data/raw/` directory with the RRC model:

```bash
sci eis batch
```

Output:

```
Batch EIS Fit (RRC)
  2105_HfOx_EIS_001.mpt: R²=0.9943
  2105_HfOx_EIS_002.mpt: R²=0.9912
  2105_HfOx_EIS_003.mpt: R²=0.9967
```

#### Export Fit to JSON

Exports the fit result as a structured JSON file to `project/results/`:

```bash
sci eis export 2105_HfOx_EIS_001.mpt --circuit R_s(Q[RW])
```

Output:

```
✓ Exported to results/2105_HfOx_EIS_001_eis_fit.json
```

JSON:

```json
{
  "file": "2105_HfOx_EIS_001.mpt",
  "circuit": "R_s(Q[RW])",
  "parameters": {
    "Rs": 118.7,
    "Q_mag": 2.89e-06,
    "Q_n": 0.87,
    "Rct": 4601.2,
    "sigma": 152.3
  },
  "r_squared": 0.998
}
```

### Using `sci analyze --technique`

The generic analyze command dispatches to the same EIS analyzer:

```bash
sci analyze --technique ec-eis 2105_HfOx_EIS_001.mpt --circuit RQR --kk
```

This follows the same code path as `sci ec analyze` (`analyze.py:353`, `_analyze_eis`).

### Plotting EIS Data

```bash
sci plot --technique ec-eis <file> [--freq-range]
```

Plot flags for `ec-eis`:

| Flag | Type | Description |
|------|------|-------------|
| `--freq-range` | str | Frequency range to display, e.g. `"1 10000"` |
| `--amplitude` | float | AC amplitude annotation (mV) |

#### Examples

Basic Nyquist plot (default for `ec-eis`):

```bash
sci plot 2105_HfOx_EIS_001.mpt
```

The `ec-eis` technique auto-detects from filename (pattern `.mpt` or `_EIS.`), resolves Z' vs -Z'' columns, and generates a Nyquist plot with equal aspect ratio and axes labeled "Z' (Ω)" and "-Z'' (Ω)".

Bode plot with explicit technique:

```bash
sci plot 2105_HfOx_EIS_001.mpt --technique ec-eis --type bode
```

Fit overlay (Nyquist with dashed fit line):

```bash
sci plot --technique ec-eis 2105_HfOx_EIS_001.mpt --circuit RRC
```

The `--circuit` flag triggers `plot_eis_fit()` in `plot/eis.py:83` which overlays the fitted model as a dashed red line on the Nyquist data.

Interactive FZF selection:

```bash
sci plot
```

Opens fzf with protocol/step context, prompts for style and figure options, then renders with theme defaults.

### Alternative Plot Entry Points

```bash
sci ec plot 2105_EIS.mpt            # deprecated — use sci plot --technique ec-eis
sci plot file1.mpt,file2.mpt         # overlay multiple EIS spectra
sci plot file1.mpt,file2.mpt --all   # individual plots per file
```

---

## Equivalent Circuit Models

science-cli implements six equivalent circuit models registered in `eis.py:83`. Each model has a canonical circuit diagram, parameter set with initial guesses and bounds, and physical interpretation.

### 1. RC — Series RC Circuit

**Circuit:**
```
     R       C
  ---/\/\----||----
```

**Diagram:**
```
     ┌─R ─ C─┐
     │       │
  ───┤       ├───
     │       │
     └───────┘
```

**Impedance:**

```
Z(ω) = R + 1/(jωC)
```

**Parameters:**

| Name | Initial Guess | Min | Max | Unit |
|------|--------------|-----|-----|------|
| R | 1000 | 1 | 1 × 10⁹ | Ω |
| C | 1 × 10⁻⁶ | 1 × 10⁻¹² | 1 | F |

**Physical meaning:** A single resistor in series with a single capacitor. Represents a blocking electrode (no Faradaic reaction) with solution resistance and geometric/double-layer capacitance. The Nyquist plot is a vertical line (ideal capacitor) shifted by R from the origin. Used for: simple dielectric measurements, electrolyte conductivity cells, metal-insulator-metal capacitors.

**Registration key:** `"RC"` — function: `_rc_series()` at `eis.py:38`

### 2. RRC — Randles Circuit (R(RC))

**Circuit:**
```
        ┌─Cdl─┐
  ──Rs──┤     ├──
        └─Rct─┘
```

**Diagram:**
```
        ┌──Cdl──┐
        │       │
  ──Rs──┼       ├───
        │       │
        └──Rct──┘
```

**Impedance:**

```
Z(ω) = R_s + 1 / (jω·C_dl + 1/R_ct)
```

**Parameters:**

| Name | Initial Guess | Min | Max | Unit | Meaning |
|------|--------------|-----|-----|------|---------|
| Rs | 100 | 1 | 1 × 10⁶ | Ω | Solution / electrolyte resistance |
| Rct | 1000 | 1 | 1 × 10⁹ | Ω | Charge transfer resistance |
| Cdl | 1 × 10⁻⁶ | 1 × 10⁻¹² | 1 | F | Double-layer capacitance |

**Nyquist shape:** A single perfect semicircle centered on the real axis. High-frequency intercept = R_s. Semicircle diameter = R_ct. Apex frequency ω_max = 1/(R_ct·C_dl).

**Physical meaning:** The simplest Faradaic model. R_s captures the ohmic drop through the electrolyte, contacts, and wiring. R_ct is inversely proportional to the exchange current density i₀ = RT/(nF·R_ct). C_dl represents the electrode-electrolyte double layer capacitance, typically 10–50 μF/cm² for a smooth electrode. Use this model when: your system has one clear semicircle, no depressed arcs, no diffusion tail.

**Registration key:** `"RRC"` — function: `_rrc_randles()` at `eis.py:45`

### 3. RQR — Randles with CPE (R(RQ))

**Circuit:**
```
        ┌──Z_Q──┐
  ──Rs──┤       ├──
        └──Rct──┘
```

Where Z_Q = 1/[Q·(jω)^n] is the constant phase element.

**Diagram:**
```
        ┌───Q───┐
        │       │
  ──Rs──┼       ├───
        │       │
        └──Rct──┘
```

**Impedance:**

```
Z(ω) = R_s + 1 / (1/Z_Q + 1/R_ct)

Z_Q = 1 / [Q · (jω)^n]
```

**Parameters:**

| Name | Initial Guess | Min | Max | Unit | Meaning |
|------|--------------|-----|-----|------|---------|
| Rs | 100 | 1 | 1 × 10⁶ | Ω | Solution resistance |
| Rct | 1000 | 1 | 1 × 10⁹ | Ω | Charge transfer resistance |
| Q_mag | 1 × 10⁻⁶ | 1 × 10⁻¹² | 1 | F·s^(n−1) | CPE magnitude |
| Q_n | 0.8 | 0.5 | 1.0 | — | CPE exponent |

**CPE interpretation:**

The CPE exponent n determines the behavior:
- **n = 1.0**: Ideal capacitor (Q_mag = C_dl). The CPE impedance reduces to 1/(jωC).
- **n = 0.5**: Warburg-like diffusion (45° line). Q_mag relates to the Warburg coefficient.
- **n = 0**: Pure resistor (Z_Q = 1/Q). Rarely used in practice.
- **0.8 < n < 1.0**: Depressed semicircle — surface roughness, porosity, or distributed time constants. The effective capacitance can be estimated as C_eff = (Q_mag · R_ct^(1−n))^(1/n) (Brug formula).

**Nyquist shape:** A depressed semicircle with its center below the real axis. The depression angle is (1−n) × 90°. More depressed → smaller n → rougher or more heterogeneous electrode surface.

**Registration key:** `"RQR"` — function: `_rq_randles()` at `eis.py:52`. Also registered as `"Randles"` (alias, same function).

### 4. R_s(C[RW]) — Full Randles with Warburg

**Circuit:**
```
        ┌──Cdl──┐
  ──Rs──┤       ├──
        └─Rct─Zw┘
```

**Diagram:**
```
        ┌──Cdl──────┐
        │           │
  ──Rs──┼           ├───
        │           │
        └──Rct──Zw──┘
```

Where Z_w = σ/√(jω) is the semi-infinite Warburg diffusion impedance.

**Impedance:**

```
Z(ω) = R_s + 1 / [jω·C_dl + 1/(R_ct + Z_w)]

Z_w = σ / √(jω)
```

**Parameters:**

| Name | Initial Guess | Min | Max | Unit | Meaning |
|------|--------------|-----|-----|------|---------|
| Rs | 100 | 1 | 1 × 10⁶ | Ω | Solution resistance |
| Cdl | 1 × 10⁻⁶ | 1 × 10⁻¹² | 1 | F | Double-layer capacitance |
| Rct | 1000 | 1 | 1 × 10⁹ | Ω | Charge transfer resistance |
| sigma | 100 | 1 × 10⁻⁶ | 1 × 10⁶ | Ω·s^(-1/2) | Warburg coefficient |

**Warburg impedance derivation:**

```
Z_w = σ / √(jω) = σ/√(2ω) · (1 − j)
```

In the Nyquist plot, the Warburg element produces a 45° straight line at low frequencies because the real and imaginary parts are equal: Z'_w = Z''_w = σ/√(2ω).

**Warburg coefficient σ:**

```
σ = RT / (n²F²A·√2 · D^(1/2) · C*)
```

Where C* is the bulk concentration of the diffusing species and D is its diffusion coefficient.

**Nyquist shape:** Semicircle at high frequencies (kinetic control) transitioning to a 45° line at low frequencies (diffusion control). The transition frequency ω_transition ≈ (1.27/R_ct·C_dl) × (R_ct/σ)² separates kinetic-dominated from diffusion-dominated regimes.

**Physical meaning:** Add this model when your data shows a 45° tail at low frequencies following the charge-transfer semicircle. Common in: rotating disk electrode measurements, batteries (Li⁺ diffusion in electrolyte), supercapacitors with diffusion-limited processes, corrosion with diffusion-controlled reactions.

**Registration key:** `"R_s(C[RW])"` — function: `_rrc_w_randles()` at `eis.py:66`

### 5. R_s(Q[RW]) — CPE + Warburg Randles

**Circuit:**
```
        ┌───Z_Q───┐
  ──Rs──┤         ├──
        └─Rct─Zw──┘
```

**Diagram:**
```
        ┌────Q──────┐
        │           │
  ──Rs──┼           ├───
        │           │
        └──Rct──Zw──┘
```

**Impedance:**

```
Z(ω) = R_s + 1 / (1/Z_Q + 1/(R_ct + Z_w))

Z_Q = 1 / [Q · (jω)^n]
Z_w = σ / √(jω)
```

**Parameters:**

| Name | Initial Guess | Min | Max | Unit | Meaning |
|------|--------------|-----|-----|------|---------|
| Rs | 100 | 1 | 1 × 10⁶ | Ω | Solution resistance |
| Q_mag | 1 × 10⁻⁶ | 1 × 10⁻¹² | 1 | F·s^(n−1) | CPE magnitude |
| Q_n | 0.8 | 0.5 | 1.0 | — | CPE exponent |
| Rct | 1000 | 1 | 1 × 10⁹ | Ω | Charge transfer resistance |
| sigma | 100 | 1 × 10⁻⁶ | 1 × 10⁶ | Ω·s^(-1/2) | Warburg coefficient |

**Nyquist shape:** Depressed semicircle at high frequencies (n < 1) followed by a 45° diffusion tail at low frequencies. The transition region between kinetic and diffusion control is also affected by the CPE — the overall arc is broader and flatter than the ideal R_s(C[RW]) model.

**Physical meaning:** The most general Randles-type model. Use this when your data shows both a depressed semicircle (rough/porous electrode, n ≠ 1) and a low-frequency Warburg tail. This is the default model for many practical systems: porous battery electrodes, rough metal surfaces in corrosion, supercapacitors with pseudocapacitance, conducting polymer films.

**Registration key:** `"R_s(Q[RW])"` — function: `_rqr_w_randles()` at `eis.py:73`

### Model Selection Guide

| Nyquist Features | Recommended Circuit | Parameters |
|-----------------|-------------------|------------|
| Ideal semicircle, no tail | RRC | Rs, Rct, Cdl |
| Depressed semicircle, no tail | RQR | Rs, Rct, Q_mag, Q_n |
| Semicircle + 45° tail | R_s(C[RW]) | Rs, Cdl, Rct, sigma |
| Depressed semicircle + 45° tail | R_s(Q[RW]) | Rs, Q_mag, Q_n, Rct, sigma |
| Vertical line only | RC | R, C |
| Two semicircles | Not directly supported | Requires custom circuit |

### Best Circuit Fit

`best_circuit_fit()` at `eis.py:178` tries all registered circuits (except RC) and returns the model with the highest R²:

```python
def best_circuit_fit(data: EISData, candidates: list[str] | None = None) -> dict:
    if candidates is None:
        candidates = [n for n in _circuit_functions if n != "RC"]
    best = {"r_squared": -1e9}
    for name in candidates:
        try:
            fit = circuit_fit(data, name)
            if "error" not in fit and fit.get("r_squared", -1) > best["r_squared"]:
                best = fit
        except Exception:
            continue
    if best.get("r_squared", -1) < -1e8:
        return {"error": "all circuit fits failed"}
    return best
```

This is useful for automated screening: run all models and let R² guide the selection. Note that R² is not the sole criterion for model selection — physical plausibility and parsimony (fewer parameters) should also be considered.

---

## Circuit Fitting

### Algorithm

Circuit fitting is performed by `circuit_fit()` at `eis.py:95` using `lmfit` least-squares minimization.

**Residual function** (`eis.py:111`):

```python
def residuals(params, f, Z_real, Z_imag):
    Z_calc = func(f, **{k: params[k].value for k in params})
    return np.concatenate([Z_calc.real - Z_real, Z_calc.imag - Z_imag])
```

The real and imaginary residuals are concatenated into a single 1D array and minimized simultaneously. This ensures both the real and imaginary parts of the impedance are fit with equal weight.

**Minimizer setup** (`eis.py:143`):

```python
from lmfit import Minimizer
minner = Minimizer(residuals, params, fcn_args=(f, Z_real, Z_imag))
result = minner.minimize(method="leastsq")
```

The `leastsq` method (Levenberg-Marquardt) is used for all circuit models. It requires no explicit bounds handling internally — bounds are enforced via lmfit parameter constraints (parameter transformation to unbounded space).

### Parameter Bounds

Bounds prevent unphysical parameter values:

| Parameter | Min | Max | Rationale |
|-----------|-----|-----|-----------|
| Rs | 1 | 1 × 10⁶ | Positive; realistic max for most electrolytes |
| R, Rct | 1 | 1 × 10⁹ | Positive; up to GΩ for insulating films |
| C, Cdl, Q_mag | 1 × 10⁻¹² | 1 | pF to 1F; covers most electrochemical systems |
| Q_n | 0.5 | 1.0 | CPE exponent range; n < 0.5 is rare for double layers |
| sigma | 1 × 10⁻⁶ | 1 × 10⁶ | Warburg coefficient; wide range covers dilute to concentrated |

### Goodness of Fit

**R² metric** (`eis.py:159`):

```python
residuals_abs = np.abs(Z_fit - Z)
r_squared = 1 - (np.sum(residuals_abs ** 2) / np.sum(np.abs(Z - np.mean(Z)) ** 2))
```

This is the coefficient of determination computed on complex residuals. R² = 1.0 indicates a perfect fit. Values above 0.99 are typical for well-behaved systems. Below 0.95 suggests model mismatch (wrong circuit, noisy data, or non-stationary system).

**Reduced χ²** (`result.redchi`):

The reduced chi-squared statistic (χ² / dof) is also returned. Values near 1 indicate that the model fits the data within the estimated error. χ² >> 1 suggests underfitting or underestimated errors.

### Output Fields

The circuit_fit return dictionary has the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `circuit` | str | Circuit model name |
| `parameter_names` | list[str] | Ordered list of parameter names |
| `fitted_params` | list[float] | Fitted parameter values |
| `param_stderr` | list[float] | Standard errors from covariance matrix (0 if not estimable) |
| `r_squared` | float | Complex R² |
| `reduced_chi` | float | Reduced chi-squared |
| `nfev` | int | Number of function evaluations |
| `fit_Z_real` | list[float] | Real part of model impedance at each frequency |
| `fit_Z_imag` | list[float] | Imaginary part of model impedance at each frequency |
| `fit_frequency` | list[float] | Frequency array (same as input) |

---

## Kramers-Kronig Validation

The Kramers-Kronig (KK) relations are integral transforms that connect the real and imaginary parts of a causal, linear, stable, and finite system. For electrochemical impedance, a KK-compliant dataset satisfies:

```
Z'(ω) = Z'(∞) + (2/π) ∫₀^∞ x·Z''(x) / (x² - ω²) dx
Z''(ω) = -(2ω/π) ∫₀^∞ Z'(x) / (x² - ω²) dx
```

In practice, direct integration is numerically challenging because EIS data is finite-bandwidth and discrete. Instead, the KK test in science-cli uses the **Voigt model fitting method** (`eis.py:203`).

### Voigt Circuit Model

A Voigt circuit consists of a high-frequency resistor R_∞ in series with N parallel RC elements (poles), each with a fixed time constant τ_k = R_k · C_k:

```
Z(ω) = R_∞ + Σ R_k / (1 + jωτ_k)
```

This model is inherently KK-compliant (it is a linear, causal, stable network). By fitting it to the data, we can assess how KK-compliant the data is: if the Voigt model reproduces the data well, the data passes the KK test.

### Algorithm

1. **Pole selection** (`eis.py:216`): N = min(10, n_freq/2) poles, log-spaced across the measured frequency range. More poles → better fit, but risk of overfitting. The cap at 10 prevents overfitting for typical datasets of 50–100 points.

2. **Parameter initialization**: R_∞ is initialized to the minimum of the real impedance. Each R_k is initialized to Z'.mean() / N and constrained to be non-negative (physical — all resistors positive).

3. **Fitting**: Same Levenberg-Marquardt minimization as circuit fitting. Residuals are concatenated real and imaginary differences.

4. **Consistency score** (`eis.py:253`):

```python
rel_residuals = residuals_abs / np.abs(Z) * 100
score = float(np.mean(rel_residuals))
```

The score is the mean absolute relative residual in percent. A score below 5% indicates the data is KK-compliant.

### Pass/Fail Criteria

- **Score < 5%**: PASS — data is consistent with KK relations. Circuit fitting is valid.
- **Score ≥ 5%**: FAIL — data violates KK assumptions. Circuit fitting may produce misleading results.

### Common KK Failure Modes

| Failure Source | Signature | Mitigation |
|---------------|-----------|------------|
| Inductive coupling at high frequencies | Z' dips below R_s at high f | Shorter leads, better shielding |
| Non-stationary system (drift) | Low-frequency points wander | Shorter measurement at each frequency |
| Instrument saturation | Distorted semicircle | Reduce AC amplitude |
| Cable inductance | High-frequency loop crossing | Compensation, shorter cables |
| Noise or glitches | Scattered points | Lower amplitude, better averaging |
| DC bias instability | Drift in low-frequency Z | Potentiostatic control |

### KK Output Fields

| Key | Type | Description |
|-----|------|-------------|
| `passes` | bool | True if consistency_score < 5.0 |
| `consistency_score` | float | Mean absolute relative residual (%) |
| `n_poles` | int | Number of Voigt RC elements |
| `reduced_chi` | float | Reduced chi-squared of Voigt fit |

---

## YAML Schema

When analysis results are written via `write_analysis_yaml()` (`analysis_output.py:24`), the EIS output follows this structure:

```yaml
technique: ec-eis
instrument: autolab-usth
devices: electrochem
timestamp: "2026-06-15T12:00:00Z"
analysis:
  circuit_fit:
    circuit: R_s(Q[RW])
    parameter_names:
      - Rs
      - Q_mag
      - Q_n
      - Rct
      - sigma
    fitted_params:
      - 118.7
      - 2.89e-06
      - 0.87
      - 4601.2
      - 152.3
    param_stderr:
      - 0.5
      - 1.23e-08
      - 0.02
      - 15.2
      - 3.1
    r_squared: 0.998
    reduced_chi: 1.23e-03
    nfev: 42
    fit_Z_real:
      - 120.3
      - 119.8
      - ...
    fit_Z_imag:
      - -0.5
      - -1.2
      - ...
    fit_frequency:
      - 100000.0
      - 50000.0
      - ...
  kk:
    passes: true
    consistency_score: 2.13
    n_poles: 10
    reduced_chi: 1.89e-03
```

### Field Reference

| Path | Type | Required | Description |
|------|------|----------|-------------|
| `technique` | str | yes | Fixed: `"ec-eis"` |
| `instrument` | str | yes | Instrument identifier from protocol or config |
| `devices` | str | no | Device type string |
| `timestamp` | str | yes | ISO-8601 UTC timestamp |
| `analysis` | dict | yes | Wrapper for analysis results |
| `analysis.circuit_fit` | dict | yes | Equivalent circuit fitting result |
| `analysis.circuit_fit.circuit` | str | yes | Circuit model name (e.g. `"R_s(Q[RW])"`) |
| `analysis.circuit_fit.parameter_names` | list | yes | Ordered parameter name array |
| `analysis.circuit_fit.fitted_params` | list | yes | Fitted values (same order) |
| `analysis.circuit_fit.param_stderr` | list | yes | Standard errors (0 if not estimable) |
| `analysis.circuit_fit.r_squared` | float | yes | Complex R² |
| `analysis.circuit_fit.reduced_chi` | float | yes | Reduced chi-squared |
| `analysis.circuit_fit.nfev` | int | yes | Function evaluations |
| `analysis.circuit_fit.fit_Z_real` | list | no | Model real impedance at each frequency |
| `analysis.circuit_fit.fit_Z_imag` | list | no | Model imaginary impedance at each frequency |
| `analysis.circuit_fit.fit_frequency` | list | no | Frequency array |
| `analysis.kk` | dict | no | Present only with `--kk` flag |
| `analysis.kk.passes` | bool | yes | KK compliance pass/fail |
| `analysis.kk.consistency_score` | float | yes | Mean relative residual (%) |
| `analysis.kk.n_poles` | int | yes | Voigt RC element count |
| `analysis.kk.reduced_chi` | float | yes | KK fit reduced chi-squared |

---

## Understanding EIS Results

### Solution Resistance R_s

The high-frequency intercept of the Nyquist plot with the real axis. R_s is the sum of:
- **Electrolyte resistance**: σ_el · (L/A) where σ_el is the ionic conductivity and L/A is the cell geometry factor. Concentrated electrolytes (1 M KCl) give ~10 Ω·cm; dilute or organic electrolytes give much higher values.
- **Contact resistance**: electrode leads, current collector interfaces
- **Wiring resistance**: typically negligible (< 1 Ω)

R_s should be subtracted from the potential when reporting true electrode potentials: E_corrected = E_applied − I · R_s (iR compensation).

### Charge Transfer Resistance R_ct

The diameter of the semicircle in the Nyquist plot. R_ct is inversely proportional to the exchange current density i₀:

```
i₀ = RT / (nF · R_ct)
```

For a simple redox reaction O + ne⁻ → R:
- Small R_ct (Ω) → fast kinetics → large i₀ (A/cm²)
- Large R_ct (kΩ-MΩ) → slow kinetics → small i₀

Typical values:
- Fast outer-sphere redox (e.g., [Ru(NH₃)₆]³⁺/²⁺ on clean Pt): R_ct ~ 10–100 Ω
- Slow reactions (e.g., O₂ reduction on glassy carbon): R_ct ~ 10⁴–10⁶ Ω
- Corrosion processes: R_ct = polarization resistance R_p (Stern-Geary equation)

### Double-Layer Capacitance C_dl

The capacitance of the electrical double layer at the electrode-electrolyte interface. The characteristic frequency of the semicircle apex gives:

```
C_dl = 1 / (R_ct · ω_max)
```

Typical values:
- Smooth metal electrode: 10–50 μF/cm²
- Rough or porous electrode: 50–500 μF/cm² (higher due to increased effective area)
- Porous carbon supercapacitors: 1–100 F (total, large area)

The phase angle at the characteristic frequency is -45° (the point on the semicircle where Z' = R_s + R_ct/2 and -Z'' = R_ct/2 for an ideal model).

### CPE Exponent n

The CPE exponent quantifies deviation from ideal capacitive behavior:

| n | Interpretation | Common Cause |
|---|---------------|-------------|
| 1.0 | Ideal capacitor | Perfectly smooth, homogeneous electrode |
| 0.9–0.99 | Near-ideal | Slight surface roughness |
| 0.8–0.9 | Moderate depression | Surface roughness, porosity, heterogeneity |
| 0.7–0.8 | Significant depression | Highly porous, rough, or composite electrodes |
| 0.5 | Warburg-like | Semi-infinite diffusion |
| < 0.5 | Anomalous | Unusual geometry, ion sieving, constant-phase behavior |

The effective capacitance (Brug formula) for a non-ideal CPE in parallel with R_ct:

```
C_eff = (Q_mag · R_ct^(1−n))^(1/n)
```

This gives a physically meaningful capacitance in Farads, comparable across different roughness levels.

### Warburg Coefficient σ

The Warburg coefficient σ quantifies the resistance to semi-infinite linear diffusion:

```
σ = RT / (n²F²A√2 · D^(1/2) · C*)
```

Rearranged to extract the diffusion coefficient:

```
D = [RT / (n²F²A√2 · σ · C*)]²
```

All quantities must be in SI units. For a known concentration C* and area A, the diffusion coefficient D can be extracted from the Warburg fit. Common values:
- Aqueous ions at 25°C: D ~ 0.5–2 × 10⁻⁵ cm²/s (σ ~ 10–100 Ω·s^(-1/2))
- Solid-state diffusion in battery electrodes: D ~ 10⁻⁸–10⁻¹² cm²/s (σ ~ 10³–10⁶ Ω·s^(-1/2))

### Nyquist Shape Interpretation

| Nyquist Shape | Time Constants | Physical Interpretation |
|--------------|---------------|------------------------|
| One perfect semicircle | 1 | Single Faradaic process on smooth electrode |
| One depressed semicircle | 1 (distributed) | Rough/porous electrode, CPE behavior |
| Two overlapping semicircles | 2 | Two charge-transfer steps, or film + interface |
| Semicircle + 45° tail | 1 + diffusion | Kinetic control → diffusion control |
| Semicircle + near-vertical tail | 1 + blocking | Finite diffusion / ion accumulation (battery) |
| Inductive loop at high f | — | Cable inductance, measurement artifact |
| Low-frequency inductive loop | — | Adsorption intermediate, negative capacitance |
| Rising Z' at low frequency | — | Electrode degradation, film formation |

### Non-Stationarity and Drift

EIS assumes the system is stationary (time-invariant) during the measurement. A full frequency sweep takes minutes to hours, and slow processes (adsorption, film growth, potential drift) violate this assumption. Symptoms:
- Low-frequency points randomly scattered (not forming a smooth curve)
- Negative resistance at low frequencies (drift artifact)
- Different results from high-to-low vs low-to-high frequency sweeps

Mitigation: shorter sweeps, frequency-by-frequency analysis, single-frequency monitoring before the sweep, using the KK test as a diagnostic.

---

## Examples

### Basic EIS Analysis

```bash
cd ~/experiments/pedot-pss
sci open -m project pedot-pss
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt
```

Expected output:

```
EIS Analysis: 250101_PEDOT_EIS_001.mpt
  Circuit fit: RRC
    Rs: 120.3 Ω
    Rct: 4520.1 Ω
    Cdl: 3.21e-06 F
    R²: 0.994
```

### Full Analysis with KK Test and Advanced Circuit

```bash
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt --circuit R_s(Q[RW]) --kk
```

Expected output:

```
EIS Analysis: 250101_PEDOT_EIS_001.mpt
  KK test: ✓ passed  (score=2.133)
  Circuit fit: R_s(Q[RW])
    Rs: 118.7 Ω
    Q_mag: 2.89e-06 F·s^(n-1)
    Q_n: 0.87
    Rct: 4601.2 Ω
    sigma: 152.3 Ω·s^(-1/2)
    R²: 0.998
```

The lower R² for RRC (0.994) vs R_s(Q[RW]) (0.998) and the depressed semicircle visible in the plot suggest the CPE + Warburg model is a better physical description.

### Comparing Multiple Circuits

```bash
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt --circuit RRC
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt --circuit RQR
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt --circuit R_s(C[RW])
sci ec analyze data/raw/250101_PEDOT_EIS_001.mpt --circuit R_s(Q[RW])
```

Compare R² values and parameter plausibility across models. The simplest model with R² > 0.99 and physically sensible parameters is preferred.

### Nyquist Plot

```bash
sci plot data/raw/250101_PEDOT_EIS_001.mpt --technique ec-eis
```

Saves PDF with Nyquist plot, equal aspect ratio. If the file has `.mpt` extension, technique auto-detection works without `--technique`.

### Bode Plot

```bash
sci plot data/raw/250101_PEDOT_EIS_001.mpt --technique ec-eis --type bode
```

Generates a dual-axis Bode plot: log|Z| (blue, left axis) and phase angle (red, right axis) vs log frequency.

### Nyquist with Fit Overlay

```bash
sci plot data/raw/250101_PEDOT_EIS_001.mpt --technique ec-eis --circuit R_s(Q[RW])
```

Runs the circuit fit internally and overlays the model as a dashed red line on the Nyquist data.

### Interactive FZF Workflow

```bash
sci ec analyze
```

Opens fzf showing all EC files with protocol→step annotations. Select EIS file(s), then enter `--circuit R_s(Q[RW]) --kk` at the prompt.

### Batch KK Testing All EIS Files

```bash
for f in data/raw/*.mpt; do
    sci eis kk "$f"
done
```

### Batch Fitting and Exporting

```bash
for f in data/raw/*.mpt; do
    sci eis export "$f" --circuit R_s(Q[RW])
done
```

JSON files are written to `project/results/`.

### High-Quality Publication Plot

```bash
sci config theme set publication-nature
sci plot data/raw/250101_PEDOT_EIS_001.mpt --technique ec-eis
```

Saves PDF with Nature journal styling.

### Temperature-Dependent EIS

```bash
sci ec analyze data/raw/PEDOT_EIS_25C.mpt
sci ec analyze data/raw/PEDOT_EIS_50C.mpt
sci ec analyze data/raw/PEDOT_EIS_75C.mpt
```

Compare R_ct and sigma values. Arrhenius plot of ln(1/R_ct) vs 1/T gives the activation energy of charge transfer. Note: temperature must be manually tracked — the `--temperature` flag is not yet implemented in the CLI.

### Quality Publication Plot with Fit and Custom Options

```bash
sci plot data/raw/250101_PEDOT_EIS_001.mpt --technique ec-eis --circuit R_s(Q[RW])
```

When prompted for style options:

```
--color "#2563eb" --linewidth 1.5
```

When prompted for figure options:

```
--width 6 --height 6 --grid
```

---

## See Also

- **electrochemistry.md** — Electrochemistry overview: workflow, technique detection, column mapping, all EC techniques
- **cyclic-voltammetry.md** — CV analysis: peak detection, charge integration, scan rate studies
- **chronoamperometry.md** — CA analysis: Cottrell fitting, steady-state current, diffusion coefficient extraction
- **overview.md** — Full technique taxonomy, detection engine, analyzer/plotter dispatch
- **schemas/analysis-yaml.md** — Complete YAML schema reference for all technique analyzers

### Source Files

| File | Description |
|------|-------------|
| `science_cli/library/electrochem/eis.py` | EIS analyzer: 6 circuit models, fitting, KK test, best-fit selection |
| `science_cli/library/electrochem/models.py` | EISData dataclass with computed properties |
| `science_cli/library/electrochem/__init__.py` | EIS column maps, analyzer registry, plot presets |
| `science_cli/plot/eis.py` | EIS plotting: Nyquist, Bode, fit overlay |
| `science_cli/cli/commands/ec.py` | CLI handler: ec analyze (dispatch to _analyze_eis) |
| `science_cli/cli/commands/eis.py` | CLI handler: eis kk, eis fit, eis batch, eis export |
| `science_cli/cli/commands/analyze.py` | _analyze_eis(): data loading, column resolution, result printing |
| `science_cli/core/analysis_output.py` | YAML output writer with envelope and optional validation |
