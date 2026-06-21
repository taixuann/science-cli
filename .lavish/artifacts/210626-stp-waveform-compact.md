---
layer: [3, 5]
type: plan
status: planning
tags: [stp, waveform, compact, analyze, interactive-menu, extracted-decay]
depends_on: [210626-remarks-flags-analyzer]
assignee: plan
---

# Implementation Plan: STP Decay Analyze + Compact Waveform

**Date**: 21/06/2026
**Status**: 🟡 Planning
**Layer**: 3 (metadata/analyzers) + 5 (plot/interactive)

## Context Summary

Two related features for the STP decay workflow:

1. **Compact waveform representation** — The current `detect_waveform_pattern_2d()` stores 200 [[t,v],...] points in protocol.yaml. For square pulses, this is wasteful. User wants a compact representation: just transition times (rise start/end, fall start/end, V_set, V_read). Full 200-point array reconstructed on-demand for plotting only.

2. **STP decay analyze — two modes** — Currently `pulse-stp-decay` has no `interactive` section in config-studies.yaml. User wants two analysis modes:
   - `--all` (batch diagnostic): For each file, generate full waveform plot with fit line, zoom rise phase, zoom decay phase, summary table, and tag with `[extracted-decay]` remark
   - `--overlay` (comparison): Read files tagged with `[extracted-decay]`, plot all fit curves on same axes for cross-file comparison

## Objectives

- [ ] Replace 200-point `waveform_pattern` with compact `waveform_transitions` dict in protocol.yaml
- [ ] Create `library/pulse/pulse_stp_decay.py` — STP decay analysis/plotting module
- [ ] Add `interactive.analyze` menu to `pulse-stp-decay` in config-studies.yaml
- [ ] Two modes: `--all` (per-file diagnostic) and `--overlay` (cross-file comparison)
- [ ] `[extracted-decay]` remark bridges `--all` → `--overlay`
- [ ] Ensure backward compat: old protocol.yaml files with `waveform_pattern` still work

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/core/metadata/analyzers/waveform.py` | Add `compute_waveform_transitions()`, modify `extract_waveform_metadata()` to return compact form | Medium |
| `src/science_cli/core/protocol.py` | `update_step_metadata()` handles `waveform_transitions` dict | Low |
| `src/science_cli/core/data_loader.py` | Reconstruct full waveform from transitions when `waveform_2d` needed for plotting | Medium |
| `config/config-studies.yaml` | Add `interactive.analyze` section to `pulse-stp-decay` | Low |
| `src/science_cli/library/pulse/pulse_stp_decay.py` | **NEW FILE** — STP decay analysis/plotting (all + overlay modes) | Medium |
| `src/science_cli/core/interactive_menu.py` | Modify `dispatch()` to support `--all` (batch) and `--overlay` (multi-file) modes | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | Main feature work |
| QA & Review | review-light | Smoke + lint check |
| Documentation | docs-light | Update README, CHANGELOG |

## Tasks

### Compact Waveform (Layer 3)

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-001 | `compute_waveform_transitions()` in waveform.py — extract 8 transition values from 200-point array | 1.5h | code |
| task-002 | `extract_waveform_metadata()` returns compact `waveform_transitions` instead of `waveform_pattern` | 1h | code |
| task-003 | `data_loader.py` reconstructs full array from transitions for plotting | 1h | code |

### STP Decay Analyze (Layer 5)

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-004 | Create `library/pulse/pulse_stp_decay.py` — `analyze_all()` function: loop files, fit, plot full+zoom, summary table, tag `[extracted-decay]` | 2.5h | code |
| task-005 | `pulse_stp_decay.py` — `analyze_overlay()` function: read `[extracted-decay]` files, plot all fit curves on same axes | 1.5h | code |
| task-006 | Add `interactive.analyze` to config-studies.yaml with two menu options | 30m | code |
| task-007 | Modify `dispatch()` for `--all` (batch) and `--overlay` (multi-file) modes | 1h | code |

### Verification

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| task-008 | Verify: pytest + manual smoke test of both modes | 1h | review |

## Dependency Order

1. task-001 → task-002 → task-003 (compact waveform chain)
2. task-004 + task-005 + task-006 + task-007 (STP analyze chain, can run in parallel with 1-3)
3. task-008 (verification after all)

## Risks

- **Backward compat**: Old protocol.yaml files with `waveform_pattern` (2D array) must still work. Add fallback in `data_loader.py` to detect old format and pass through.
- **Compact transitions fidelity**: Some waveforms may not be clean square pulses (e.g., rounded edges, ringing). The compact representation assumes clean transitions. Need validation against real data.
- **Batch dispatch**: `interactive_menu.py:dispatch()` currently iterates one file at a time. `--all` and `--overlay` modes need different dispatch patterns. Must not break existing per-file handlers.

## Two-Mode Design

### Mode 1: `sci analyze pulse-stp-decay --all` (Batch Diagnostic)

For EACH file in the step:
```
┌─────────────────────────────────────────────┐
│ 1. Full waveform plot                        │
│    - markers = raw data points               │
│    - smooth line = fitted decay curve         │
│    - annotate: tau, I_init, I_final, r²      │
│                                              │
│ 2. Zoom: rise phase                          │
│    - close-up of voltage rise                │
│    - where it hits V_set                     │
│                                              │
│ 3. Zoom: decay phase                         │
│    - the actual decay curve                  │
│    - fitted line + residuals                 │
│                                              │
│ 4. Summary table in terminal                 │
│    - model (mono/biexp), tau1, tau2, r²      │
│    - I_initial, I_steady, decay_pct          │
│                                              │
│ 5. Tag with [extracted-decay] remark         │
└─────────────────────────────────────────────┘
```

### Mode 2: `sci analyze pulse-stp-decay --overlay` (Comparison)

Reads files tagged with `[extracted-decay]`:
- Plots all fit curves on same axes
- Markers (data) + lines (fits) colored by file
- Annotated with tau values
- Single comparison PNG

### Bridge: `[extracted-decay]` Remark

| Mode | Action | Bridge |
|------|--------|--------|
| `--all` | Fits, plots, tags | writes `[extracted-decay]` |
| `--overlay` | Reads tagged files | reads `[extracted-decay]` |

## Compact Waveform Design

**Current** (protocol.yaml):
```yaml
waveform_pattern: [[0.0, 0.0], [1.2e-6, 1.5], [5.2e-6, 1.5], [5.2e-6, 0.2], ...]  # 200 points
```

**New** (protocol.yaml):
```yaml
waveform_transitions:
  rise_start_us: 0.0
  rise_end_us: 5.2
  v_set_start_us: 5.2
  v_set_end_us: 105.2
  fall_start_us: 105.2
  fall_end_us: 110.5
  v_set_v: 1.5
  v_read_v: 0.2
  repeat_pattern: single
```

**Reconstruction** (for plotting):
```python
def reconstruct_waveform(transitions: dict, n_points: int = 200) -> list[list[float]]:
    """Reconstruct [[t,v],...] array from compact transitions."""
    # Rise: linear ramp from v_read to v_set over rise_us
    # Plateau: constant v_set from v_set_start to v_set_end
    # Fall: linear ramp from v_set to v_read over fall_us
    # Read: constant v_read from fall_end to end
```

## Interactive Menu (config-studies.yaml)

```yaml
pulse-stp-decay:
  interactive:
    analyze:
      menu_title: "Select analysis for STP decay:"
      options:
        - name: "Analyze all files (--all)"
          handler: "science_cli.library.pulse.pulse_stp_decay.analyze_all"
          description: "Batch: fit, plot full+zoom, summary, tag [extracted-decay]"
          batch: true
        - name: "Overlay decay curves (--overlay)"
          handler: "science_cli.library.pulse.pulse_stp_decay.analyze_overlay"
          description: "Compare: plot fit curves of [extracted-decay] files"
          overlay: true
```

## Walkthrough
(To be filled during/after implementation)
