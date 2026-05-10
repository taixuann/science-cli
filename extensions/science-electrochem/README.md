# science-electrochem — Electrochemistry Analysis Extension

Analysis logic for electrochemical techniques: CV, CA, EIS. **Plotting and theming are handled by science-cli**, not this extension.

## Install

```bash
pip install -e tools/extensions/science-electrochem
```

## Techniques Registered

| Technique | Label | Patterns | Description |
|-----------|-------|----------|-------------|
| `ec-cv` | CV | `_CV.`, `.cv`, `cv_` | Cyclic Voltammetry |
| `ec-ca` | CA | `_CA.`, `.ca`, `ca_` | Chronoamperometry |
| `ec-eis` | EIS | `.mpt`, `_EIS.`, `.eis`, `_impedance`, `.z` | Electrochemical Impedance Spectroscopy |

## Analysis Functions

### Cyclic Voltammetry

```python
from science_electrochem.cv import peak_analysis, calculate_charge, scan_rate_analysis
from science_electrochem.models import CVData

data = CVData(potential=V, current=I, scan_rate=0.05)

peaks = peak_analysis(data, options={"prominence": 5e-6})
# peaks["anodic_peaks"]           → [{index, potential, current, height}, ...]
# peaks["cathodic_peaks"]
# peaks["average_peak_separation"] → ΔE_p (V)

charge = calculate_charge(data)
# charge["total_charge_C"]
# charge["anodic_charge_C"]
# charge["cathodic_charge_C"]
```

Peak detection uses `scipy.signal.find_peaks` with configurable height, distance, and prominence.

### Chronoamperometry

```python
from science_electrochem.ca import analyze_cottrell, analyze_steady_state
from science_electrochem.models import CAData

data = CAData(time=t, current=I, potential=0.5)

cottrell = analyze_cottrell(data)
# cottrell["slope"]           → Cottrell slope (A·√s)
# cottrell["r_squared"]

steady = analyze_steady_state(data)
# steady["steady_state_current"]  → I_ss (A)
```

Cottrell equation: I(t) = nFA·C₀·√(D/π) · 1/√t + I_baseline

### EIS

```python
from science_electrochem.eis import analyze_eis

results = analyze_eis(frequency=f, Z_real=Zr, Z_imag=Zi, model="randles")
# results["params"]               → {R_s, R_ct, C_dl, W, ...}
# results["goodness_of_fit"]      → {chi_squared, aic, bic}
```

Supported circuit models:
- `randles` — R_s + R_ct//C_dl + W (Warburg diffusion)
- `r-cpe` — R_s + CPE (constant-phase element)
- `r-rc` — R_s + R_ct//C_dl (simple RC)

## Data Models

```python
from science_electrochem.models import CVData, CAData, EISData

cv  = CVData(potential=..., current=..., scan_rate=0.05, cycle_number=3)
ca  = CAData(time=..., current=..., potential=0.5)
eis = EISData(frequency=..., Z_real=..., Z_imag=...)
```

## Plotting (handled by science-cli)

```bash
sci plot data/sample_CV.csv --theme publication-acs
sci plot data/sample_EIS.mpt --theme publication-nature
```

science-cli selects the template, applies the theme, and outputs PDF. See `science-cli/README.md` for theme configuration and output options.

## Typical Workflow

```
1. Measure:  potentiostat records CV/CA/EIS data → CSV or .mpt
2. Parse:    sci parse data.csv
3. Analyze:  sci analyze --technique ec-cv data.csv
4. Plot:     sci plot data.csv --theme publication-nature   → PDF
```

## Dependencies

- numpy ≥ 1.20
- scipy ≥ 1.7
- lmfit ≥ 1.0
- science-cli (for CLI integration)

## Future: Crossbar Array Characterization

In crossbar memristor arrays (see `tools/extensions/science-memristor/PLAN.md` §10d), electrochemical techniques could be applied to individual matrix junctions in future work — for example:

- **In situ CV monitoring** during electrodeposition of the switching layer at specific crosspoints
- **EIS measurement** of individual memristor states (LRS/HRS) to extract device capacitance and charge-transport parameters
- **CA monitoring** for studying filament formation kinetics at individual junctions

The crossbar `devices.yaml` schema already supports arbitrary technique keys under each matrix point's `techniques:` dict. Adding `cv`, `ca`, or `eis` keys requires no schema changes — just add the technique key and file references. The electrochem analysis code would need to understand crossbar file locations, but the storage layer is already compatible.
