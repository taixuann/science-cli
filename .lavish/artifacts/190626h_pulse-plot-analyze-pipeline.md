---
layer: [2, 7]
type: plan
status: in-progress
tags: [pulse, plot, analyze, pipeline, analysis-yaml]
assignee: code
---

# Implementation Plan: Pulse Plot & Analyze Pipeline

**Date**: 19/06/2026
**Status**: 🟠 In Progress  
## Architecture: step/ folder for analysis YAML

Each analyze run writes to `step/<step_name>/<filename_stem>.analysis.yaml` with standardized metrics. The plot functions can optionally read from this YAML for faster rendering (vs parsing raw CSV each time).

---

## Study 1: pulse:pulse-endurance

### Current state (from temp-src/ exploration)
- Raw Keysight CSV has Measurement Result sections with V/I at 7.5µs (LRS read) and 145µs (HRS read) per cycle
- 410 sections → 206 unique cycles (grouped by 5s timestamp proximity)
- Protocol: 9000 initial silent cycles → log-spaced read-backs C[n] = 9000 × 10^(n/95) from C9000 to ~C1M

### Plot: _plot_endurance_volatile()
Problems with current implementation:
1. Uses `_load_and_resolve()` which guesses columns from raw CSV — doesn't handle 2-row-per-cycle HRS/LRS format
2. Plots all R values as one series instead of separating HRS and LRS
3. No per-cycle averaging (should average 15 LRS samples + 15 HRS samples per cycle)
4. No ratio panel

Fix:
- Parse Measurement Result sections from CSV (same logic as `plot_endurance_extract.py`)
- Group by timestamp proximity (5s threshold)
- Compute per-cycle: HRS_R = |V_145µs / I_145µs|, LRS_R = |V_7.5µs / I_7.5µs|
- Generate cycle indices using log formula: C[n] = base × 10^(n/95)
- 2-panel figure: top panel R(HRS + LRS) vs cycle, bottom panel ratio vs cycle
- Log x from 8000-2e6, log y for R, log y for ratio, inline annotations (no legend)

### Analyze: _analyze_pulse_endurance()
Current: stub ("not yet implemented")

Standard metrics to compute (from `library/pulse/endurance.py`):
```
analysis:
  mode: volatile-memristor
  parameters:
    mean_r_high: float        # mean of HRS over all cycles
    mean_r_low: float         # mean of LRS over all cycles
    mean_ratio: float         # mean of HRS/LRS ratio
    cv_r_high: float          # cycle-to-cycle HRS variability
    cv_r_low: float           # cycle-to-cycle LRS variability
    n_cycles: int             # total valid cycles
    window_closure_pct: float # (ratio_end - ratio_start) / ratio_start × 100
    failure_cycle: int|null   # first cycle where ratio < 10
    r_high_trend: float       # linear trend of HRS vs cycles (Ω/cycle)
    ratio_tail_mean: float    # mean ratio over last 10% of cycles
    weibull_shape: float|null # Weibull fit shape parameter
    weibull_scale: float|null # Weibull fit scale parameter
  per_cycle:
    cycles: [int]
    r_high: [float]          # per-cycle HRS values
    r_low: [float]           # per-cycle LRS values
    ratios: [float]          # per-cycle HRS/LRS
```

### Files to modify
| File | Change | Risk |
|------|--------|------|
| `plot/pulse_endurance.py` | Rewrite _plot_endurance_volatile with Measurement Result section parser + 2-panel plot | Med |
| `cli/commands/analyze.py` | Implement _analyze_pulse_endurance | Med |
| `library/pulse/endurance.py` | Reuse analyze_endurance() for stats | Low |

---

## Study 2: pulse:pulse-stp-decay

### Current state (from temp-src/ exploration)
- WGFMU time/voltage/current data with repeating pulses
- Each cycle: V≈2V read (5-10µs) → negative SET pulse → V≈0V decay (1-10µs)
- Current decays within the V=2V plateau from ~9.8mA to ~2.9mA (file 01) or stable at ~3.25mA (file 02)
- File 01: 6µs cycle (5µs read, 1µs gap), 12k pts, 10 repeats
- File 02: 20µs cycle (10µs read, 10µs gap), 40k pts, 10 repeats × 2 blocks

### Plot: _plot_stp_decay()
Current: twin Y-axis (V blue, I red) with segment splitting

Additions needed:
- Add `_plot_stp_decay_trend()` — single-panel current vs time, y-limited to V_set plateau range
- V_set range: auto-detect from data (file 01: ~1.5mA, file 02: ~3.25mA) or user-specified `--ylim`
- Detect V≈2V plateaus → sample current at middle (20-pt average) → plot per-pulse
- Optional `--trend` flag to switch between waveform and trend view

### Analyze: _analyze_pulse_stp()
Current: stub ("not yet implemented")

Standard metrics:
```
analysis:
  mode: pulse-stp-decay
  parameters:
    n_pulses: int
    i_initial_mA: float         # first pulse V_set current
    i_final_mA: float           # last pulse V_set current
    depression_pct: float       # (i_final - i_initial) / i_initial * 100
    depression_trend: float     # linear slope of I vs pulse (mA/pulse)
    i_vset_values: [float]      # per-pulse V_set currents
    tau_fast_us: float|null     # fast decay time constant (within-pulse)
    tau_slow_us: float|null     # slow decay time constant (within-pulse)
    v_read_v: float             # read voltage (~2.0V)
    pulse_interval_us: float    # time between pulses
    pulse_width_us: float       # V=2V read pulse width
```

### Files to modify
| File | Change | Risk |
|------|--------|------|
| `plot/stp.py` | Add _plot_stp_decay_trend() | Med |
| `cli/commands/analyze.py` | Implement _analyze_pulse_stp | Med |
| `plot/registry.py` | Register --ylim flag for STP | Low |

---

## Study 3: pulse:pulse-ppf

### Current state
- `_plot_ppf_single()` — twin Y-axis, same format as STP
- `_analyze_pulse_ppf()` — stub

### Plot
Current view (waveform) is sufficient for now. Can add ratio view later.

### Analyze: _analyze_pulse_ppf()
Standard PPF metrics:
```
analysis:
  mode: ppf
  parameters:
    intervals_ms: [float]       # inter-pulse intervals tested
    i1_values: [float]          # current response to first pulse
    i2_values: [float]          # current response to second pulse
    ppf_ratios: [float]         # I2/I1 per interval (facilitation index)
    mean_ppf: float             # mean PPF ratio across intervals
    max_ppf: float              # maximum PPF ratio
    tau_facilitation_ms: float|null  # characteristic facilitation decay time
```

### Files to modify
| File | Change | Risk |
|------|--------|------|
| `cli/commands/analyze.py` | Implement _analyze_pulse_ppf | Med |
| `plot/ppf.py` | Minor tweaks if needed | Low |

---

## step/ folder structure

Analysis YAML goes in `step/<step>/results/<technique>_analysis.yaml` (standard `write_analysis_yaml()` pattern).

```
step/5_pulse-endurance/
└── results/
    ├── pulse-endurance_analysis.yaml    # analyze output
    ├── endurance_hrs_lrs.pdf           # plot output
    └── ...
```

```yaml
# step/5_pulse-endurance/results/pulse-endurance_analysis.yaml
technique: pulse-endurance
instrument: keysight-b1500a
timestamp: 2026-06-19T20:00:00Z
analysis:
  mode: volatile-memristor
  parameters:
    mean_r_high: 1456723.0
    mean_r_low: 4392.0
    mean_ratio: 331.8
    cv_r_high: 0.31
    cv_r_low: 0.02
    n_cycles: 206
```

```yaml
# step/6_ppf/results/pulse-stp_analysis.yaml
technique: pulse-stp
instrument: keysight-b1500a
timestamp: 2026-06-19T19:00:00Z
analysis:
  mode: pulse-stp-decay
  parameters:
    n_pulses: 20
    i_initial_mA: 3.247
    i_final_mA: 2.991
    depression_pct: -7.9
    depression_trend: -6.54e-6
    v_read_v: 2.0
    pulse_interval_us: 20.0
    pulse_width_us: 10.0
```

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Endurance plot rewrite | code-medium | Measurement Result parsing + 2-panel plot |
| Endurance analyze | code-medium | Read clean CSV → stats → YAML |
| STP trend plot | code-medium | V_set plateau detection + trend view |
| STP analyze | code-medium | Per-pulse extraction → stats → YAML |
| PPF analyze | code-medium | Pulse pairing → ratio → YAML |
| QA & Review | review-light | Test with R3-C3 and R5-C3 files |
| Documentation | docs-light | Update CHANGELOG |

## Dependency Order
1. Endurance: plot → analyze (we have temp script for plot)
2. STP: plot → analyze (we have temp script for plot)
3. PPF: analyze only (plot can wait)

## Walkthrough
(To be filled during implementation)
