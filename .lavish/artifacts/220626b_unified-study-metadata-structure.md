---
layer: [1, 6, 7]
type: design-discussion
status: discussion
tags: [config-studies, metadata-schema, analyze, plot, structure]
depends_on: []
assignee: human
---

# Review: Unified Study Metadata & Config Structure

**Date**: 22/06/2026
**Status**: 🟡 Discussion

---

## Current State

The existing `config-studies.yaml` has an **inconsistent pattern** across studies:

| Study | `derived_metadata` | `required_fields` | `interactive.analyze` | Analyze has `plot:` config | Metadata written back |
|-------|-------------------|-------------------|-----------------------|---------------------------|----------------------|
| **pulse-endurance** | ✅ waveform params | ✅ cycle, R_HRS, R_LRS, I_HRS, I_LRS | ✅ 4 key-based functions | ✅ Fully config-driven | ✅ Step-level: ratio_mean, ratio_median, ratio_std, etc. |
| **pulse-stp-decay** | ✅ waveform params | ❌ | ✅ 2 functions, but key-based w/ menu | ❌ Hardcoded in code | ✅ Per-file: extracted_decay.segments/segment_N |
| **iv-bipolar-sweep** | ❌ (instruments.metadata) | ❌ | ❌ None | — | ❌ Only via CLI `sci analyze -t iv-sweep` |
| **pulse-ppf** | ✅ waveform params | ❌ | ❌ None | — | ❌ |
| **pulse-retention** | ✅ waveform params | ❌ | ❌ None | — | ❌ |

Also discovered: `pulse_stp_decay.py` hardcodes all plot styling (colors, markers, figure layout) — it does NOT use `resolve_analysis_plot_config()` unlike `pulse_endurance.py`.

---

## Proposed Unified File Entry Schema (per protocol.yaml)

Every file entry in protocol.yaml would have this structure:

```yaml
steps:
  - name: 5_pulse-endurance
    files:
      - file: 200626-111355_...extracted-list_[important].csv
        metadata:           # ← Sweep/measurement parameters (from header extraction)
          v_set_v: 1.8
          v_read_v: 0.5
          set_width_us: 50
          read_width_us: 1000
          compliance: 0.001
          step_v: 0.02
          delay_s: 0.1
        plot:               # ← Per-file plot overrides (for sci plot command)
          common:
            legend: false
        analyze:            # ← Per-function config + metadata outputs
          ratio_histogram:
            config:         # ← Analyze plot overrides (per-file)
              bins: 100
              x_pad_factor: 0.5
            metadata:       # ← What this function wrote (auto-populated)
              ratio_mean: 843.6
              ratio_median: 801.3
              ratio_std: 164.9
```

---

## Per-Study Metadata Assignment (what each study needs)

### pulse-endurance

```
metadata (file headers):   v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern
required_fields (data):    cycle, r_hrs_ohm, r_lrs_ohm, i_hrs_A, i_lrs_A
device_overrides:
  volatile:                + r_decay_ohm
  non-volatile:            + r_high_ohm, r_low_ohm

analyze:
  ratio_histogram:
    config:                bins, xscale, y_max_method, series.*, legend.*
    metadata output:       ratio_mean, ratio_median, ratio_std
  current_ratio_histogram:
    config:                (same as ratio_histogram)
    metadata output:       i_ratio_mean, i_ratio_median, i_ratio_std
  ratio_vs_cycles:
    config:                axes.*, series.scatter.*, series.fit.*, legend.*
    metadata output:       ratio_fit_slope, ratio_fit_r_squared
  i_ratio_vs_cycles:
    config:                (same structure)
    metadata output:       i_ratio_fit_slope, i_ratio_fit_r_squared
```

**Status**: ✅ Fully wired. The gold standard.

---

### pulse-stp-decay

```
metadata (file headers):   v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern
required_fields (data):    time_s, voltage_v, [none for extracted-list]
device_overrides:
  volatile:                + decay_tau_ms, r_read_ohm

analyze:
  analyze_all:
    config:                MISSING — hardcoded in code
    metadata output:       extracted_decay (segments, segment_NNN:
                           model, tau1_ms, tau2_ms, a1, a2,
                           initial_current_ua, steady_state_current_ua,
                           decay_pct, r_squared)
  analyze_overlay:
    config:                MISSING — hardcoded in code
    metadata output:       (none — overlay only draws)
```

**Status**: ⚠️ Partial. Config wiring needed for plot styling. Metadata writing works (per-file).

---

### iv-bipolar-sweep

```
metadata (file headers):   set_voltage, compliance, sweep_range (start/stop),
                           step_v, delay_s, repeat_count
                           → plus: compliance_analysis (analyze function outputs:
                           in_compliance, compliance_current, compliance_voltage)
required_fields (data):    voltage_v, current_a
device_overrides:
  (none yet)

analyze:
  extract_iv_parameters:   MISSING from interactive.analyze
    config:                MISSING
    metadata output:       v_set, v_reset, on_off_ratio, i_set, i_reset,
                           r_on, r_off, switching_detected
```

**Status**: 🔴 Not wired. Analyzer exists in CLI but not in interactive menu. No config-driven analyze.

---

### pulse-ppf

```
metadata (file headers):   v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern
required_fields (data):    [none]
device_overrides:          (none)

analyze:                   MISSING
```

**Status**: 🔴 Not wired. No interactive analyze at all.

---

### pulse-retention

```
metadata (file headers):   v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern
device_overrides:
  non-volatile:            + r_read_ohm

analyze:                   MISSING
```

**Status**: 🔴 Not wired. No interactive analyze at all.

---

## Gaps Found

### 1. pulse_stp_decay.py missing config-driven plots
Hardcoded colors, markers, figure layout. Should use `resolve_analysis_plot_config()` like `pulse_endurance.py`.

### 2. pulse-stp-decay has no `required_fields`
Should define what columns the extracted-list CSVs must contain (e.g., time_s, current_a, extracted_decay).

### 3. iv-bipolar-sweep has no interactive.analyze
The CLI analyze path (`sci analyze -t iv-sweep`) works independently via `analyze.py TECHNIQUE_ANALYZERS`, but there's no interactive menu entry. The **config-studies.yaml** should define analyze functions so the menu dispatch works.

### 4. metadata resolution is scattered
Some metadata lives in `config-devices.yaml` → `instruments.*.metadata.*`, some in `config-studies.yaml` → `studies.*.derived_metadata`. The user wants them unified in config-studies.yaml.

### 5. No protocol.yaml `plot:` overrides for pulse-stp-decay
The `resolve_step_plot_overrides` pathway exists for plot config, but pulse-stp-decay's plot section has no override pathway wired.

### 6. _update_protocol_metadata() overwrites step-level
In `pulse_endurance.py`, writing to `step.metadata` (not per-file) means the last file's values overwrite previous ones. Should write per-file under `analyze.<function>.metadata`.

---

## Proposed Changes (Scope)

### What to do:

1. **Define explicit analyze schema per study** in config-studies.yaml
   - Each function gets a `metadata_outputs:` list (what it writes back)
   - Each function gets a `plot:` config block
   - Standardize the key-based structure

2. **Wire pulse_stp_decay.py** to use `resolve_analysis_plot_config()`
   - Move hardcoded plot params to config-studies.yaml
   - Support per-file overrides via protocol.yaml

3. **Add interactive.analyze for iv-bipolar-sweep**
   - Create analyze function entry in config-studies.yaml
   - Wire v_set/v_reset extraction to metadata output

4. **Fix metadata write destination**
   - Move from step-level to per-file `analyze.<func>.metadata` in protocol.yaml
   - This fixes the overwrite bug in `_update_protocol_metadata()`

5. **Add `required_fields` for studies that have extracted-list CSVs**
   - pulse-stp-decay, pulse-ppf, pulse-retention

### What NOT to do (out of scope):

- Adding new analyze functions (only wiring existing ones)
- Restructuring config files (keep existing split)
- Changing data loading/parsing

---

## Questions for User

1. **Metadata location**: You want `metadata` in protocol.yaml per-file — should this be distinct from `analyze` function metadata? i.e.:
   - `metadata` = sweep params from header parsing
   - `analyze.<func>.metadata` = analysis results written by each analysis run
   
2. **Priority**: Which studies to wire first? Pulse-stp-decay (closest to done), or iv-bipolar-sweep (most used)?

3. **`required_fields` semantics**: Should these describe what columns the *extracted-list CSV* must contain (after preprocessing), or what the *raw CSV* from the instrument must contain?

4. **The step-level vs per-file issue**: Currently `_update_protocol_metadata()` writes to `step.metadata` (overwrite bug). Should we move ALL metadata to per-file entries? This means analyzing the same file twice creates `analyze.ratio_histogram.metadata.ratio_mean` + `analyze.ratio_vs_cycles.metadata.ratio_fit_slope` all on that file entry.
