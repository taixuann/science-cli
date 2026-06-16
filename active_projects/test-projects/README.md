# test-projects — Synthetic Test Data for science-cli

This directory contains synthetic projects and measurement data for testing the science-cli pipeline. All data is programmatically generated — not from real measurements — and designed to exercise specific parsing, analysis, and visualization paths.

## Structure

```
test-projects/
├── iv-test-project/          # IV sweep + breakdown on memristor crossbar
│   ├── sci-config.yaml
│   └── protocol/1_iv-test/
│       ├── 1_iv-test.yaml
│       ├── iv-sweep/         # 2 files (r0c0, r1c0) Keithley 2400 format
│       └── iv-breakdown/     # 1 file with breakdown at ~3.5V
├── pulse-test-project/       # Pulse endurance + retention
│   ├── sci-config.yaml
│   └── protocol/1_pulse-test/
│       ├── 1_pulse-test.yaml
│       ├── mem-endurance/    # R_on/R_off cycling data
│       └── mem-retention/    # Resistance vs time
├── pulse-stp-test-project/   # Short-term plasticity (STP) + PPF
│   ├── sci-config.yaml
│   └── protocol/1_stp-test/
│       ├── 1_stp-test.yaml
│       ├── pulse-stp/        # Current decay over ms
│       └── pulse-ppf/        # Paired-pulse facilitation
├── pvd-test-project/         # Physical vapor deposition
│   ├── sci-config.yaml
│   └── protocol/1_pvd-deposition/
│       ├── 1_pvd-deposition.yaml
│       ├── pvd-layer/        # Layer stack Ta/Pt
│       └── pvd-rate/         # Deposition rate over time
├── uv-vis-test-project/      # UV-Vis spectroscopy
│   ├── sci-config.yaml
│   └── protocol/1_uv-vis-spectrum/
│       ├── 1_uv-vis-spectrum.yaml
│       ├── uv-vis-transmission/  # .txt format
│       └── uv-vis-absorbance/    # .txt format
└── multi-device-project/     # Multi-technique, multi-instrument
    ├── sci-config.yaml
    └── protocol/1_device-test/
        ├── 1_device-test.yaml
        ├── iv-sweep/         # Empty (no data files)
        └── mem-endurance/    # Empty (no data files)
```

## Techniques Covered

| Technique | Instrument | File Format | Columns |
|-----------|-----------|-------------|---------|
| iv-sweep | Keithley 2400 | CSV | Voltage (V), Current (A) |
| iv-breakdown | Keithley 2400 | CSV | Voltage (V), Current (A) |
| mem-endurance | Keithley 2400 | CSV | Cycle, R_on (Ω), R_off (Ω) |
| mem-retention | Keithley 2400 | CSV | Time (s), Resistance (Ω) |
| pulse-stp | Keithley 2400 | CSV | Time (ms), Current (A) |
| pulse-ppf | Keithley 2400 | CSV | Pulse, Current (A) |
| pvd-layer | Generic | CSV | Layer, Material, Thickness, Rate, Temperature, Pressure |
| pvd-rate | Generic | CSV | Time (s), Rate (nm/s), Temperature (C) |
| uv-vis-transmission | Generic | TXT | Wavelength (nm), T% |
| uv-vis-absorbance | Generic | TXT | Wavelength (nm), Abs |

## File Naming Convention

All files follow the pattern: `{date_code}_{material}_{matrix}_{technique}_{suffix}.{ext}`

Example: `140526_Ta-PDA-ITO_r0c0_iv_01.csv`
- `140526` = date code (2026-05-14)
- `Ta-PDA-ITO` = material stack
- `r0c0` = row 0, column 0
- `iv` = IV sweep technique
- `01` = file suffix
- `.csv` = extension

## Usage in Tests

```python
def test_iv_sweep_parsing(test_projects_root):
    iv_data = test_projects_root / "iv-test-project" / "protocol" / "1_iv-test" / "iv-sweep"
    # Parse 140526_Ta-PDA-ITO_r0c0_iv_01.csv
```
