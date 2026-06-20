# Implementation Plan: WGFMU Waveform Column Parser (Tier 1 + Tier 2)

**Date**: 21/06/2026
**Status**: 🟡 Planning
**Layer**: 2 (Metadata Parsers) + 3 (Keysight Parsers)
**Version**: v3.22.1 (proposed)

---

## Context Summary

Keysight WGFMU (B1500A) pulse files contain **Waveform columns** embedded in ~14 of 127 STP files. These columns store the **programmed pulse pattern** — the ground truth for what the instrument was instructed to do:

- `Waveform1_time` / `Waveform1_voltage` — Ch1 programmed pulses (three levels: 0V, 0.5V, 1.75V)
- `Waveform2_time` / `Waveform2_voltage` — Ch2 measurement timing

For the remaining ~110 files without these columns, the existing `analyze_waveform_params()` histogram-based detection handles extraction.

## Two-Tier Approach

| Tier | When | Method | Extracts |
|------|------|--------|----------|
| **1** | Waveform columns present | Direct column parse | Full segment decomposition: wait, set_rise, set, read, hold widths + voltages as 2D array |
| **2** | No Waveform columns | Histogram on measured voltage (exists) | V_set, V_read, pulse widths (existing) |

---

## Config Schema Addition

No new config fields needed — the parser detects Tier 1 vs Tier 2 automatically by checking if `Waveform1_voltage` exists in the loaded DataFrame.

---

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `core/metadata/parsers/keysight.py` | Add `parse_wgfmu_waveform_segments()` — decompose Waveform columns into segment list | Low |
| `core/metadata/analyzers/waveform.py` | Update `extract_waveform_metadata()` — try Tier 1 first, fall back to Tier 2 | Low |
| `core/metadata/__init__.py` | Update `extract_metadata()` to pass raw_lines + DataFrame to waveform analysis | Low |

---

## Parser Design: `parse_wgfmu_waveform_segments()`

### Input
DataFrame columns: `Waveform1_time`, `Waveform1_voltage`, `Waveform2_time`, `Waveform2_voltage`

### Algorithm
```
1. Get unique (Waveform1_time, Waveform1_voltage) pairs sorted by time
2. Compute pairwise differences in time and voltage
3. Segment boundaries: where voltage changes
4. For each segment:
   - start_time, end_time, width = end - start
   - voltage (rounded to nearest 0.5 or 0.25 — user preference: "2.494532 → 2.5")
5. Label segments by pattern:
   - V=0 at start = "wait"
   - V=V_set rising = "set_rise"
   - V=V_set stable = "set"
   - V=V_read stable = "read"
   - V=0 after read = "hold"
6. Build 2D array: [[t_start, t_end, v_rounded], ...]
```

### Output
```python
{
    "waveform_programmed": True,  # Tier 1 flag
    "waveform_2d": [
        [0.0, 5e-6, 0.0],      # wait: 0V, 5µs
        [5e-6, 15e-6, 0.5],    # set_rise: 0.5V, 10µs  
        [15e-6, 16e-6, 1.75],  # set: 1.75V, 1µs
        [16e-6, 26e-6, 0.5],   # read: 0.5V, 10µs
        [26e-6, 27e-6, 0.0],   # hold: 0V, 1µs
        ...
    ],
    "segments": {
        "v_set_v": 1.75,
        "v_read_v": 0.5,
        "wait_width_us": 5.0,
        "set_rise_width_us": 10.0,
        "set_width_us": 1.0,
        "read_width_us": 10.0,
        "hold_width_us": 1.0,
    },
    "repeat_pattern": "single" | "repeated",
    "n_repeats": 3,
}
```

### Voltage Rounding
User asks: "2.494532 → 2.5". Round to nearest 0.25V for pulse voltages:
- 1.749828 → 1.75
- 0.501234 → 0.50
- 0.024556 → 0.00 (sub-threshold, treated as 0)

---

## Analyzer Integration: Updated `extract_waveform_metadata()`

```python
def extract_waveform_metadata(df, raw_lines=None, ...):
    """Orchestrator: Tier 1 (Waveform columns) → Tier 2 (histogram)."""
    
    # Tier 1: Waveform columns present?
    if "Waveform1_voltage" in df.columns:
        segments = parse_wgfmu_waveform_segments(df)
        if segments["waveform_programmed"]:
            # Use programmed pattern for scalars
            scalars = {
                "v_set_v": round(segments["segments"]["v_set_v"], 2),
                "v_read_v": round(segments["segments"]["v_read_v"], 2),
                "set_width_us": segments["segments"]["set_width_us"],
                "read_width_us": segments["segments"]["read_width_us"],
            }
            # 2D pattern from programmed waveform (not measured)
            pattern = segments["waveform_2d"]
            return {
                "waveform_pattern": pattern,
                "waveform_programmed": True,
                **scalars,
                **segments["segments"],
                "repeat_pattern": segments["repeat_pattern"],
                "n_repeats": segments["n_repeats"],
            }
    
    # Tier 2: No Waveform columns → histogram detection (existing)
    pattern = detect_waveform_pattern_2d(df)
    scalars = analyze_waveform_params(df, raw_lines, {})
    repeats = detect_repeat_pattern(df)
    return {
        "waveform_pattern": pattern,
        "waveform_programmed": False,
        **scalars,
        **repeats,
    }
```

---

## Segment Labeling Rules

Segment labels follow standard pulse terminology:

| Label | Voltage | Position | Description |
|-------|---------|----------|-------------|
| `wait` | 0V → V_start | First segment | Baseline wait before pulse |
| `set_rise` | V_start → V_set | Rising edge | Voltage ramping up |
| `set` | V_set | At set voltage | Pulse set phase |
| `set_fall` | V_set → V_read | Falling to read | Transition to read |
| `read` | V_read | At read voltage | Pulse read phase |
| `hold` | 0V | After read | Baseline hold between pulses |

If a segment doesn't match any labeled pattern, it's labeled generically as `segment_{N}`.

---

## Test Strategy

| Test | File Type | Expected |
|------|-----------|----------|
| Tier 1: parse Waveform columns | `001_questionable.csv` | 5-6 segments per cycle, 3 cycles |
| Tier 1: voltage rounding | 1.7498 → 1.75, 0.5012 → 0.50 | Correct rounding |
| Tier 2: fallback | File without Waveform columns | Uses existing histogram |
| repeat_pattern | 3-cycle file → "repeated" | 3 repeats |
| No Waveform, single cycle | Standard file | "single" |

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Add `parse_wgfmu_waveform_segments()` to keysight.py | code-medium | ~80 lines |
| Update `extract_waveform_metadata()` for Tier 1→Tier 2 | code-medium | ~30 lines |
| QA & Review | review-light | Test both tiers, verify metadata output |
| Documentation | docs-light | Update CHANGELOG, update Layer 2 dashboard |

## Dependency Order

1. task-001 (parser) → 2. task-002 (analyzer integration) → 3. task-003 (review) → 4. task-004 (docs)

## Risks

1. **Some files have Waveform1 but not Waveform2 columns** — parser must handle partial Waveform columns gracefully
2. **Voltage noise on Waveform columns** — Waveform columns are digital commands (0/0.5/1.75), not analog measurements, so noise should be minimal. But verify on all 14 files.
3. **Multi-cycle repeat detection** — Waveform columns repeat for each cycle. Parser needs to detect where the pattern wraps and count repeats.
