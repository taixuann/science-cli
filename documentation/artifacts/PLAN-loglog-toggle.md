# PLAN: IV Plot Log-Log Toggle

## Status
- **Created**: 2026-05-16
- **Status**: completed
- **Branch**: refactor/2.1.0

## Objective
Add an `IV` | `ln-ln` mode toggle to the Device Explorer IV plot, switching between linear-linear and log-log axis scales for SCLC regime analysis.

## Context
The current IV plot shows y-axis on log scale (semi-log). Users need log-log view to identify power-law regimes (ohmic slope ~1, Child's law ~2, trap-filled >2) for SCLC analysis. This is Phase 1 — visual toggle only, no auto-fitting yet.

## Specification

### HTML Changes (dashboard.py template)
Add a two-button toggle group next to Overlay/cycle controls (line ~679):
```
[IV] [ln-ln]    Overlay [x]   ◀ [1] ▶
```
- Implemented as two `<span>` or `<button>` elements with `.scale-btn` class
- `IV` mode active by default (matches current behavior but with linear y-axis)
- `ln-ln` mode switches both axes to log scale

Wait — need to clarify axis defaults:

### Axis Behavior per Mode

| Mode | X-axis | Y-axis | Use case |
|------|--------|--------|----------|
| **IV** | linear | **log** | Semi-log IV curve (existing default, unchanged) |
| **ln-ln** | log | log | SCLC regime identification (power-law slopes) |

IV mode = current behavior, kept as-is. ln-ln is additive only.

### JS Changes (dashboard.py inline JS)

1. **Add tracking variable**: `var ivScaleMode = 'iv';` (values: `'iv'` or `'lnln'`)

2. **Add toggle function**:
   ```js
   function setIVScale(mode) {
     ivScaleMode = mode;
     document.querySelectorAll('.scale-btn').forEach(function(b) {
       b.classList.toggle('active', b.dataset.scale === mode);
     });
     if (currentDevice) drawIVPlot(currentDevice);
   }
   ```

3. **Modify `drawIVPlot()`** — after line 2840, in the `Plotly.react` call:
   - Read `ivScaleMode`
   - In IV mode: `xaxis: { type: 'linear' }`, `yaxis: { type: 'linear' }`
   - In ln-ln mode: `xaxis: { type: 'log' }`, `yaxis: { type: 'log' }`
   - Also adjust `hovertemplate`:
     - IV mode: `%{y:.3e}` (scientific, fine for linear)
     - ln-ln mode: `%{y:.3e}` still fine since values span many orders of magnitude
   - Adjust `tickformat` for log mode if needed

4. **Handle negative voltages in ln-ln mode**: Since log x-axis can't show V < 0, in ln-ln mode all voltage values are converted to `Math.abs(v)` so both forward and reverse sweeps appear in the positive quadrant as |V| vs |I| on log-log. This is the standard SCLC plot convention.

5. **Update event binding**: wire up the scale toggle buttons.

### No DB / storage changes
This is purely a visualization toggle. No schema migration, no new columns, no heatmap metrics.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | Modify | Add HTML toggle, JS switching logic, axis config in drawIVPlot |

## Dependencies
None.

## Test Strategy
1. Regenerate demo dashboard, open in browser
2. Click IV → ln-ln toggle, verify axes switch
3. Verify markers (Vset/Vreset) still show correctly in both modes
4. Verify overlay mode + ln-ln combo works
5. Verify single-cycle mode + ln-ln combo works

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done — HTML toggle added at dashboard.py lines 721-722, `ivScaleMode` tracking at line 2595, `setIVScale()` JS at line 2912
- [x] TEST passed (97/97)
- [x] DOCS updated
- [x] COMMIT done

## Implementation Details
- IV mode keeps current behavior (semi-log: linear x, log y)
- ln-ln mode converts both axes to log scale
- Negative voltages converted to `Math.abs(v)` in ln-ln mode for SCLC convention
- Toggle buttons rendered as `.scale-btn` elements in dashboard.py inline HTML
