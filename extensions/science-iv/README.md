# science-iv — IV Curve Analysis Extension

Analysis logic for current–voltage characterization. **Plotting and theming are handled by science-cli**, not this extension.

This extension registers techniques and analyzers with science-cli, which handles CLI dispatch, theme application, and PDF output.

## Install

```bash
pip install -e tools/extensions/science-iv
```

## Data Format

### Column naming conventions

The system auto-detects time, voltage, and current columns from a variety of naming conventions. This section documents all recognized column names.

#### Time columns

| Convention | Example(s) | Source |
|-----------|-----------|--------|
| Standard time | `Time`, `Time (s)`, `time` | Most instruments |
| Corrected time | `Corrected time (s)`, `corrected time` | Autolab (Nova) with IR compensation |
| Short notation | `t/s`, `time/s` | Compact CSV exports |

#### Voltage columns

| Convention | Example(s) | Source |
|-----------|-----------|--------|
| Standard voltage | `Voltage (V)`, `voltage`, `V (V)` | Most sourcemeters |
| Potential | `Potential (V)`, `Potential applied (V)`, `E (V)`, `E/V` | Autolab potentiostats |
| Working electrode | `WE(1).Potential (V)` | Autolab multi-channel |
| **Bias voltage (short)** | **`BV`**, **`bias_voltage`** | **Semiconductor parameter analyzers** |
| **Bias voltage (full)** | **`Bias Voltage (V)`** | **Custom LabVIEW/Python setups** |

#### Current columns

| Convention | Example(s) | Source |
|-----------|-----------|--------|
| Standard current | `Current (A)`, `current`, `I (A)`, `I/A` | Most sourcemeters |
| Working electrode | `WE(1).Current (A)` | Autolab multi-channel |
| Mean current | `<I>/A` | Some Nova exports |
| Short notation | `I` (exact match), `i)` | Compact CSV exports |
| **Bias current (short)** | **`Bi`**, **`bias_current`** | **Semiconductor parameter analyzers** |
| **Bias current (full)** | **`Bias Current (A)`** | **Custom LabVIEW/Python setups** |

**Bold entries** are the most recent additions, supporting the `Time, Bi, BV` column format used by semiconductor parameter analyzers (Keysight B1500A, Keithley 4200-SCS) and custom IV measurement setups.

#### `Bi` and `BV` semantics

- **`Bi`** = **B**ias current — the current flowing through the device under applied bias. This is the measured current response, equivalent to `I (A)` or `Current (A)` in other conventions.
- **`BV`** = **B**ias **V**oltage — the voltage applied across the device terminals. This is the driving stimulus, equivalent to `Voltage (V)` or `Potential (V)` in other conventions.

The `B` prefix originates from semiconductor characterization where "bias" distinguishes the applied stimulus from floating or measured potentials. It is used by:
- Keysight B1500A Semiconductor Device Analyzer
- Keithley 4200-SCS Parameter Analyzer
- Custom Python/LabVIEW measurement scripts using PyVISA

**Example file** (`deviceA_IV.txt`):

```
Time    Bi          BV
0.0     1.2e-9      0.0
0.1     3.4e-8      0.1
0.2     2.1e-7      0.2
...
```

This file is detected as an IV sweep (technique: `iv-sweep` or `iv-breakdown` based on filename patterns). The plotting system maps `BV` → x-axis (Voltage) and `Bi` → y-axis (Current).

### Detection mechanism

Column detection uses the `ColumnMap` system registered by the extension in its `__init__.py`:

```python
registry.column_maps["iv-sweep"] = ColumnMap(
    x="Voltage (V)", y="Current (A)",
    x_label="Voltage (V)", y_label="Current (A)",
    x_aliases=["BV", "bias_voltage", "WE(1).Potential (V)", ...],
    y_aliases=["Bi", "bias_current", "WE(1).Current (A)", ...],
)
```

1. **Registry `ColumnMap.resolve()`**: The core's `plot.py` and `analyze.py` call `registry.column_maps[technique].resolve(df_columns)` which tries the preferred `x`/`y` names first, then falls back through the alias lists. This handles `BV` → voltage, `Bi` → current, and all other conventions in one place.

2. **Fallback**: If no registry column map matches, per-technique hardcoded alias lists in `plot.py` are tried. If those also fail, the first two numeric columns are used as a universal last resort.

### Adding new column conventions

If your instrument uses different column names, file an issue or PR with:
1. The exact column headers
2. The instrument/model that produces them
3. Example data (first 5 rows)

The column mapping is defined in the extension's `__init__.py` via `ColumnMap` with `x_aliases` and `y_aliases`. The core resolves columns automatically from the registry at plot/analyze time.

## Techniques Registered

| Technique | Label | Patterns | Description |
|-----------|-------|----------|-------------|
| `iv-sweep` | IV Sweep | `_IV.`, `.iv`, `iv_`, `_sweep`, `sweep_` | Bipolar/unipolar voltage sweep |
| `iv-breakdown` | Breakdown | `_bd.`, `breakdown_`, `_Vbd`, `bd_` | Ramped voltage to breakdown |
| `iv-leakage` | Leakage | `_leak`, `leakage_`, `leak_` | Low-bias leakage measurement |

## Analysis Functions

### Resistance

```python
from science_iv.analyze import extract_resistance

result = extract_resistance(voltage, current, window=0.1)
# result["resistance"]       → Ω
# result["resistance_stderr"] → standard error
# result["r_squared"]        → goodness of fit
```

Linear fit in ±window V (±100 mV default). Returns Ohmic resistance.

### Sweep Direction & Rate

```python
from science_iv.analyze import detect_sweep_segments

segments = detect_sweep_segments(voltage, time)
#
# segments is a list of dicts:
#   start_idx       — index in the original array
#   end_idx
#   direction       — "forward" (V increasing) or "reverse" (V decreasing)
#   sweep_rate_v_s  — |dV/dt| for this segment
#   voltage_range   — voltage span of the segment
#   duration_s
```

Detection: finds voltage sign-change points. Each segment between reversals is classified as forward or reverse sweep.

### Scan Rate

```python
from science_iv.analyze import extract_scan_rate

result = extract_scan_rate(voltage, current, time=time)
# result["scan_rate_v_s"]   → estimated sweep rate
# result["voltage_range"]   → total voltage span
```

### On/Off Ratio

```python
from science_iv.analyze import extract_on_off_ratio

result = extract_on_off_ratio(voltage, current, read_voltage=0.1)
# result["on_off_ratio"]  → I_on / |I_off| at ±V_read
```

### Conduction Mechanism Fitting

```python
from science_iv.analyze import fit_iv_curve

# Supported models:
fit_iv_curve(voltage, current, model="ohmic")         # I = V/R
fit_iv_curve(voltage, current, model="schottky")      # ln(I) ∝ √V
fit_iv_curve(voltage, current, model="sclc")          # log(I) ∝ n·log(V)
fit_iv_curve(voltage, current, model="pool-frenkel")  # ln(I/V) ∝ √V
```

Each returns: `params`, `metrics` (R², RMSE, AIC, BIC), `success`, `error`.

### Breakdown Voltage

```python
from science_iv.analyze import extract_breakdown_voltage

result = extract_breakdown_voltage(voltage, current, threshold_current=1e-6)
# result["breakdown_voltage"]
# result["breakdown_current"]
```

## Data Model

```python
from science_iv.models import IVData

data = IVData(
    voltage=np.array([...]),
    current=np.array([...]),
    filename="sample_IV.txt",
)
data.resistance    # Ohmic resistance (Ω) from ±0.1 V linear region
data.compliance    # Max |current| (A)
data.on_off_ratio  # max(|I|) / min(|I|>0)
```

## Plotting (handled by science-cli)

```bash
sci plot data/sample_IV.csv --theme publication-acs

# With Bi/BV column format — automatic column detection:
sci plot data/deviceA_IV.txt --theme publication-nature
```

science-cli selects the template, applies the theme, and outputs PDF. See `science-cli/README.md` for theme configuration and output options.

## Sweep Metadata (Protocol Integration)

When files are assigned to IV steps in a protocol, the system auto-detects sweep direction and rate from the actual data:

```
add -m data --fzf       # assign file → protocol step
                        # ↳ auto-detects sweep segments
                        # ↳ stores per-file in protocol YAML
```

Protocol YAML after assignment:

```yaml
steps:
  - name: iv-sweep
    technique: iv
    files:
      - file: deviceA_IV.txt
        sweep:
          - direction: forward    # 0 → +V
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
          - direction: reverse    # +V → 0
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
          - direction: reverse    # 0 → -V
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
          - direction: forward    # -V → 0
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
```

The `detect_sweep_segments()` function identifies reversal points and zero-crossings to correctly split bipolar sweeps.

### Crossbar array context

In crossbar memristor arrays (see `tools/extensions/science-memristor/PLAN.md`), IV files are one of several techniques that can be measured at each (row, col) matrix point. A single junction may have separate SET and RESET IV files, alongside endurance, retention, and switching measurements — all organized in a per-step `devices.yaml`. The sweep metadata detection described here applies to each IV file independently, with results stored in the file entry's `sweep` field within the multi-technique device config.

## Typical Workflow

```
1. Measure:  sourcemeter records time(s), voltage(V), current(A) → CSV
2. Assign:   add -m data --fzf     (assign to protocol step, sweep metadata auto-detected)
3. Analyze:  sci analyze data.csv (extract resistance, on/off ratio, sweep segments)
4. Plot:     sci plot data.csv --theme publication-acs   → PDF
```

## Dependencies

- numpy ≥ 1.20
- scipy ≥ 1.7
- lmfit ≥ 1.0
- science-cli (for CLI integration)
