# Plan: Fix multi-segment detection bug & first-cycle-only default

## Objective
Fix `_split_at_reversals()` to use hysteresis-based reversal detection with a `min_step` threshold, add first-cycle-only plotting as default, and expose `--multi-cycle` flag in CLI.

## Specification

### 1. `_split_at_reversals(voltage, min_step=0.1)` — rewrite

**Current**: Detects ANY sign change in `dv` as reversal. With noise → 94 false segments.

**New algorithm (hysteresis-based)**:
- Track a running maximum (when voltage is rising) or running minimum (when falling)
- A reversal is detected when voltage falls below `running_max - min_step` (on a rising sweep) or rises above `running_min + min_step` (on a falling sweep)
- Noise of ±0.5mV can never trigger a reversal because it can't cross the 0.1V threshold
- Clean bipolar sweep (0→+3.5V→−3.5V) produces exactly 2 segments

**Why this beats other approaches**:
- Sign-change + cumulative tracking fails because noise flips `last_sign`, causing false reversals when cumulative grows later
- Smoothing adds latency and requires knowing the window size
- Running max/min with hysteresis is equivalent to a Schmidt trigger — standard in EE for debouncing

### 2. First-cycle-only plotting (DEFAULT)

- `generate_iv_svg()` takes only `segments[:2]` after splitting (first forward + first reverse)
- If 1 segment → plot as simple sweep (same as before)
- Forward segment → black (#000000), solid
- Reverse segment → gray (#888888), dashed
- Add `multi_cycle: bool = False` parameter to `generate_iv_svg()`

### 3. Update `_build_sweep_from_data()` 

- Remove the `result[:3]` hack (line 554) — no longer needed since `_split_at_reversals` now returns correct segments
- The function limits to first continuous sweep by detecting >1V jumps (lines 495-508), which is correct behavior

### 4. CLI `--multi-cycle` flag

- Add `--multi-cycle` to `cmd_plot` parser in `device_cli.py`
- Pass `multi_cycle` through metadata to `generate_iv_svg()`
- Default: first cycle only (matches user expectation for clean plots)

### 5. Title

After the fix, `build_plot_title` + auto-detection in `generate_iv_svg` already produces correct titles because:
- `_split_at_reversals` returns correct segments → `_build_sweep_from_data` derives correct direction path
- `_extract_sweep_annotations` builds direction string from segments
- `generate_iv_svg` overrides title when sweep metadata is incomplete

No title format change needed — the fix naturally produces clean titles.

## Critical Analysis

- **Predicted output**: Clean IV SVGs with 2 segments (forward black, reverse gray) instead of 94 tangled segments
- **Consequences**: Existing stored sweep metadata (`fe.sweep` from `memristor sync`) may contain old broken segment data. The plot auto-detection fallback in `generate_iv_svg()` handles this — but users should re-run `memristor sync` after this fix for accurate stored metadata.
- **Risks**: 
  - `min_step=0.1V` might be too large for very slow sweeps with small voltage ranges (e.g., 0→0.2V). Mitigation: make `min_step` configurable; default 0.1V handles all Clarius+ data (step size 0.05V).
  - Hysteresis approach assumes voltage goes through well-defined peaks/troughs. For weird waveforms (pulse trains, AC), it might misbehave. Unlikely for IV sweeps.
- **Skepticism**: The first-cycle-only default is reasonable for display but might hide data in multi-sweep files. The `--multi-cycle` flag provides an escape hatch.

## Files to Modify
- `plotting.py` — rewrite `_split_at_reversals()`, modify `_plot_bipolar_sweep()` for first-cycle mode, update `generate_iv_svg()`, remove hack in `_build_sweep_from_data()`
- `device_cli.py` — add `--multi-cycle` flag to plot subparser, pass to `generate_iv_svg()`

## Dependencies
No new packages. Pure numpy logic change.

## Test Strategy
Run `memristor plot --all --overwrite` on the protocol directory. Verify:
1. Each SVG shows exactly 1 forward (black) + 1 reverse (gray) line
2. Segment count for first uc file reduces from 94 to 2
3. Title shows clean direction path, not sweep count

## Branching
- [ ] No new branch needed (bug fix)

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
