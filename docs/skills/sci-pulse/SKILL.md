---
name: sci-pulse
description: "Pulse measurement analysis for memristor and neuromorphic devices — endurance cycling, retention decay, short-term plasticity (STP), paired-pulse facilitation (PPF). Models include biexponential STP decay, log-time/power-law retention, Weibull endurance failure, and exponential PPF facilitation. Load when analyzing pulsed electrical measurements or neuromorphic characterization data."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [pulse-endurance, pulse-retention, pulse-switching, pulse-stp, pulse-ppf, pulse-forming, pulse-set, pulse-reset, pulse-read, pulse-ivd]
---

# sci-pulse — Pulse Measurement Analysis Skill

## Overview

`sci pulse` analyzes pulsed electrical measurements for memristive and neuromorphic device characterization. It supports 11 pulse technique slugs covering endurance cycling, retention decay, short-term plasticity (STP), paired-pulse facilitation (PPF), switching characterization, and forming/set/reset/read operations. All subcommands delegate to specialized analysis modules in `library/pulse/`.

### Pulse Technique Taxonomy

| Technique | Description | Filename Pattern |
|-----------|-------------|------------------|
| `pulse-endurance` | Pulsed endurance cycling | `_endurance`, `.end`, `end_` |
| `pulse-retention` | Retention decay over time | `_retention`, `.ret`, `ret_` |
| `pulse-switching` | Switching time/voltage stats | `_switch`, `.sw`, `sw_` |
| `pulse-forming` | Initial electroforming step | `_forming`, `form_`, `_form` |
| `pulse-set` | Set operation programming | `_set`, `_SET` |
| `pulse-reset` | Reset operation programming | `_reset`, `_RESET` |
| `pulse-read` | Non-destructive read pulse | `_read`, `_READ` |
| `pulse-ivd` | Quasi-static pulsed IV | `_ivd`, `_IVD`, `_pulsed-iv` |
| `pulse-stp` | STP decay (biexponential) | `_stp`, `_STP`, `_stp_decay`, `_short-term` |
| `pulse-ppf` | PPF ratio vs interval | `_ppf`, `_PPF`, `_paired-pulse` |

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci pulse ls` | List pulse measurement files |
| `sci pulse endurance [--file <path>]` | Analyze endurance cycling |
| `sci pulse retention [--file <path>]` | Analyze retention decay |
| `sci pulse stp [--file <path>]` | Analyze STP decay |
| `sci pulse ppf [--file <path>]` | Analyze PPF ratio |
| `sci pulse dashboard` | Launch pulse analysis dashboard |

## Analysis Details

### Endurance Cycling

**Model**: Weibull minimum distribution for cycles-to-failure. Linear regression for R_off degradation.

| Parameter | Description |
|-----------|-------------|
| `mean_r_on`, `mean_r_off` | Mean LRS and HRS resistance (Ohm) |
| `mean_ratio` | Mean R_off / R_on |
| `cv_r_on`, `cv_r_off` | Coefficient of variation per state |
| `failure_cycle` | First cycle where ratio < 10 |
| `weibull_fit` | Weibull min distribution parameters |
| `trend_slope` | Linear R_off degradation (Ohm/cycle) |

Failure detection: ratio < 10. Weibull shape < 1 = infant mortality, = 1 = random, > 1 = wear-out.

### Retention Decay

Two models, selected by higher R²:
- **Log-time**: R(t) = a·log₁₀(t) + b
- **Power-law**: R(t) = a·t^b

| Parameter | Description |
|-----------|-------------|
| `decay_rate` | Log-time fit slope (Ohm/decade) |
| `decay_model` | Selected: `log` or `power` |
| `extrapolated_10yr` | Projected R after 10 years |
| `lifetime_hours` | Time to 50% degradation |

### STP (Short-Term Plasticity)

Two models, selected by AIC:
- **Monoexponential**: I(t) = A·exp(-t/τ₁) + I₀
- **Biexponential**: I(t) = A₁·exp(-t/τ₁) + A₂·exp(-t/τ₂) + I₀

| Parameter | Description |
|-----------|-------------|
| `tau1_ms` | Fast time constant (ms) |
| `tau2_ms` | Slow time constant (ms, biexp only) |
| `a1`, `a2` | Relative amplitude weights |
| `decay_pct` | Percentage decay peak→steady state |

### PPF (Paired-Pulse Facilitation)

**Model**: PPF(Δt) = 1 + A·exp(-Δt/τ)

| Parameter | Description |
|-----------|-------------|
| `tau_facilitation_ms` | Facilitation decay time constant |
| `a_amplitude` | Facilitation amplitude |
| `ppf_ratio_max`, `ppf_ratio_min` | Measured PPF range |

## YAML Schemas

### Endurance — `pulse-endurance_analysis.yaml`
```yaml
technique: pulse-endurance
analysis:
  parameters:
    cycles_to_failure: 9876
    r_high_initial: 54321.0
    r_low_initial: 1234.5
    n_cycles: 10000
    ratio_tail_mean: 12.3
```

### Retention — `pulse-retention_analysis.yaml`
```yaml
technique: pulse-retention
analysis:
  parameters:
    decay_rate: -234.5
    decay_model: log
    extrapolated_10yr: 34567.8
    lifetime_hours: 87654.0
    r_squared: 0.9934
```

### STP — `pulse-stp_analysis.yaml`
```yaml
technique: pulse-stp
analysis:
  decay_fit:
    model: biexponential
    tau1_ms: 12.3
    tau2_ms: 145.6
    a1: 0.65
    a2: 0.35
  parameters:
    initial_current_ua: 12.34
    decay_pct: 74.0
```

### PPF — `pulse-ppf_analysis.yaml`
```yaml
technique: pulse-ppf
analysis:
  ppf_ratio_vs_interval:
    - interval_ms: 50.0; ppf_ratio: 1.85
    - interval_ms: 100.0; ppf_ratio: 1.65
  facilitation_time_constant_ms: 85.3
  r_squared: 0.9950
```

## AI Agent Usage

### Pulse analysis workflow
1. List pulse files: `sci pulse ls`
2. Select file matching desired technique (endurance/retention/stp/ppf)
3. Run subcommand with `--file <path>`:
   - `sci pulse endurance --file data_endurance.csv`
   - `sci pulse retention --file data_retention.csv`
   - `sci pulse stp --file data_stp.csv`
   - `sci pulse ppf --file data_ppf.csv`
4. Interpret results:
   - Endurance: Check failure_cycle and Weibull shape for failure mode
   - Retention: Compare R² between log and power models
   - STP: AIC selects model; τ₁ (fast) vs τ₂ (slow) indicates mechanism
   - PPF: τ determines temporal integration window for neuromorphic circuits

### Physics interpretation for agents
- **Endurance failure modes**: Oxygen reservoir depletion (gradual R_off decay), filament overgrowth (R_on decrease), dielectric breakdown (sudden failure)
- **STP τ₁** (1-50 ms): Rapid charge de-trapping or thermal dissipation
- **STP τ₂** (50-500 ms): Slower oxygen vacancy redistribution
- **PPF τ**: Directly probes the device's short-term dynamics for temporal spike processing
