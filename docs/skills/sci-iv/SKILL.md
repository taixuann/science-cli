---
name: sci-iv
description: "IV sweep analysis for memristors and crossbar arrays — bipolar/volatile switching, Vset/Vreset extraction (derivative-based), ON/OFF ratio, crossbar matrix displays, conduction model fitting (Ohmic/Schottky/SCLC/Poole-Frenkel). Load when analyzing IV sweep data, interpreting switching parameters, or working with crossbar arrays."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [iv-sweep, iv-breakdown, iv-leakage]
---

# sci-iv — IV Sweep Analysis Skill

## Overview

`sci iv` characterizes current-voltage (IV) sweeps for memristor, junction, and crossbar array devices. It handles listing files, metadata inspection, plotting, parameter extraction (Vset/Vreset/ON-OFF ratio), SQLite syncing, and dashboard generation. Supports both **bipolar** (Vset + Vreset) and **volatile** (Vset-only) analysis modes, with conduction model fitting (Ohmic, Schottky, SCLC, Poole-Frenkel).

### IV Technique Taxonomy

| Technique | Description | Filename Patterns |
|-----------|-------------|-------------------|
| `iv-sweep` | Standard DC sweep for resistive switching | `_iv`, `_sweep`, `iv_`, `sweep_` |
| `iv-breakdown` | Ramped voltage stress to failure | `breakdown_` |
| `iv-leakage` | Low-bias leakage current | `leakage_` |

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci iv ls [--step <name>]` | List IV sweep files |
| `sci iv info [<file>]` | Show columns, shape, value range |
| `sci iv plot [--overlay] [--all] [--row ROW] [--col COL]` | Plot IV curves with crossbar filtering |
| `sci iv analyze [--vset-only] [--row ROW] [--col COL]` | Extract switching parameters |
| `sci iv sync` | Sync IV data to SQLite cache |
| `sci iv dashboard` | Launch IV analysis dashboard |

### Key Flags

| Flag | Applies To | Description |
|------|-----------|-------------|
| `--vset-only` | analyze | Force volatile mode (Vset only, no Vreset) |
| `--row ROW` | plot, analyze | Filter to specific crossbar row |
| `--col COL` | plot, analyze | Filter to specific crossbar column |
| `--overlay` | plot | Overlay all traces on single axes |
| `--all` | plot | Plot every file individually |
| `--step <name>` | ls | Filter to specific protocol step |

## Parameter Extraction

### Vset/Vreset Detection

Derivative-based: Vset = argmax(dI/dV) in forward sweep, Vreset = argmin(dI/dV) in reverse sweep. The raw dI/dV is smoothed with a moving average filter before peak finding.

| Parameter | Description |
|-----------|-------------|
| Vset | Voltage where device switches HRS→LRS |
| Vreset | Voltage where device switches LRS→HRS |
| R_on | Low resistance state (Ohmic fit at low bias) |
| R_off | High resistance state (Ohmic fit at low bias) |
| ON/OFF ratio | I(+V_read) / I(-V_read) at default 0.1 V |
| Hysteresis area | Integral of I(V) enclosed area |

### Analysis Modes

- **Bipolar** (default): Extracts Vset + Vreset for junction-type switching
- **Volatile** (`--vset-only`): Extracts Vset only for volatile memristors

### Conduction Models

| Model | Equation | Region |
|-------|----------|--------|
| Ohmic | I = V/R | Linear low-bias (<0.1 V) |
| Schottky | ln(I) ∝ sqrt(V) | Forward bias > 0.1 V |
| SCLC | log(I) ∝ n·log(V) | Positive V, positive I |
| Poole-Frenkel | ln(I/V) ∝ sqrt(V) | Forward bias > 0.1 V |

## YAML Schema

Analysis results are written to `{step}/results/iv-sweep_analysis.yaml`:

```yaml
technique: iv-sweep
instrument: keithley-2400
devices: memristor
timestamp: "2026-06-15T12:00:00Z"
analysis:
  mode: volatile  # or "bipolar"
  parameters:
    v_set: 1.23
    v_set_std: 0.045
    v_set_cv: 0.037
    v_set_min: 1.10
    v_set_max: 1.35
    on_off_ratio: 45.2
    compliance: 0.001
    v_reset: -0.89  # bipolar only
    hysteresis_area: 0.42  # bipolar only
    set_yield: 92.5  # volatile only
  n_events: 40
```

## AI Agent Usage

### IV analysis workflow
1. List files: `sci iv ls [--step <name>]`
2. Inspect metadata: `sci iv info <file>`
3. Determine device type from protocol YAML or ask user
4. Run analyze with appropriate mode:
   - Memristor/volatile: `sci iv analyze --vset-only`
   - Junction/bipolar: `sci iv analyze`
5. For crossbar arrays, filter by: `--row 0 --col 0`
6. Plot results: `sci iv plot [--overlay] [--row ROW] [--col COL]`

### Crossbar matrix tip
Crossbar cells parsed from filenames using `r{N}c{M}` patterns. The heatmap-style dashboard displays rows × cols with color-coded metrics.

### When to use which mode
- **Volatile devices**: Diffusive memristors, threshold switches (OTS), forming-free devices — use `--vset-only`
- **Bipolar devices**: Filamentary RRAM (ECM/VCM), interface-type switching — use default (no flag)
- **Breakdown testing**: `iv-breakdown` technique — extract V_bd at threshold current (default 1 µA)
