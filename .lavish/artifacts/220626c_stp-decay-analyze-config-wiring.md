---
layer: [1, 5, 6, 7]
type: plan
status: done
tags: [pulse-stp-decay, analyze, config, metadata-schema, skill]
depends_on: [220626-analyze-config-wiring]
assignee: plan
---

# Implementation Plan: Pulse-STP-Decay Analyze Config Wiring + Metadata Restructure

**Date**: 22/06/2026
**Status**: 🟢 Done
**Layer**: 1 (Config) + 5 (Plotting Dispatch) + 6 (Protocol) + 7 (Pulse Analyzers)

---

## Context Summary

`pulse_stp_decay.py` has two analyze functions (`analyze_all`, `analyze_overlay`) that work but:

1. **Hardcoded plot styling** — colors, markers, figure layout are all hardcoded in `_plot_*` functions. Unlike `pulse_endurance.py`, it does NOT call `resolve_analysis_plot_config()`.
2. **Metadata writes under flat `extracted_decay`** — should be restructured to per-function keys: `analyze.analyze_all.metadata.extracted_decay`.
3. **No per-file analyze config pathway** — can't override plot params via protocol.yaml for individual files.
4. **No `required_fields` defined** — need to declare what extracted-list CSVs must contain.

---

## Objectives

1. **Add key-based `interactive.analyze` with `plot:` config** in config-studies.yaml for pulse-stp-decay (following pulse-endurance pattern)
2. **Wire `resolve_analysis_plot_config()`** into `analyze_all()` and `analyze_overlay()` — move hardcoded plot params to config
3. **Restructure metadata output** — write per-file `analyze.<func>.metadata.extracted_decay` instead of flat `metadata.extracted_decay`
4. **Add `write_file_analyze_metadata()`** to `protocol.py` for writing per-function metadata namespaced under `analyze.<func_name>.metadata`
5. **Update `resolve_file_analyze_config()`** — check `.config` sub-key first, fall back to flat for backwards compat
6. **Add `required_fields`** for pulse-stp-decay
7. **Create `sci-stp-decay` skill** documenting metadata schema + config schema
8. **Regenerate STP PDFs** against real `res_internship` data
9. **Docs + .lavish updates**

---

## Architecture

### Protocol.yaml per-file structure (after restructure)

**For pulse-stp-decay, `metadata` IS the `waveform_pattern`** — a compressed 2D array of `[time_s, voltage_v]` at transition points (only where |ΔV| > 0.1V). This is already stored in protocol.yaml.

```yaml
steps:
  - name: 6_pulse-stp-decay
    files:
      - file: 200623-...stp-decay_extracted.csv
        metadata:                 # ← waveform_pattern IS the metadata
          waveform_pattern:       # ← 2D [time_s, voltage_v] transition points ONLY
            - [0.0, 0.0]
            - [2.2e-06, 1.75]     # V_set rising edge
            - [1.12e-05, 0.0]     # V_set falling edge
            - [1.44e-05, 0.14]    # V_read plateau
            - [8.46e-05, 0.11]    # Decay reference
        analyze:                  # ← Per-function config + metadata
          analyze_all:
            config:               # ← Per-file plot overrides
              series:
                current:
                  color: "#FF6600"
            metadata:             # ← Written by analyze_all
              extracted_decay:    # ← Generic seg_NNN (start+end points) + decay params
                seg_001:
                  t1_s: 2.2e-06
                  v1_v: 1.75
                  i1_a: 3.22e-06
                  t2_s: 8.46e-05
                  v2_v: 0.14
                  i2_a: ...
                seg_002:
                  t1_s: ...
                  v1_v: ...
                  i1_a: ...
                  t2_s: ...
                  v2_v: ...
                  i2_a: ...
                decay:
                  tau_ms: 12.3
                  r_squared: 0.995
```

### Backwards compatibility

Existing files with `analyze: { ratio_histogram: { x_pad_factor: 0.5 } }` (flat, no `config:` sub-key) continue to work. `resolve_file_analyze_config()` checks for `.config` sub-key first, falls back to the whole dict.

### Config wiring flow

```
config-studies.yaml                         protocol.yaml
  └─ pulse:                                      └─ step:
       pulse-stp-decay:                                files:
         interactive:                                     - file: ..._stp-decay.csv
           analyze:                                        metadata:
             analyze_all:                                    v_set_v: 1.8
               menu_title: ...                              analyze:
               handler: ...                                   analyze_all:
               plot:                                            config:
                 series:                                          series:
                   current: {color: "#CC0000"}                     current: {color: "#FF6600"}
                   voltage: {color: "#0055CC"}
                 fit:
                   color: "black"
                             │
                             ▼
              resolve_analysis_plot_config()
              ("pulse:pulse-stp-decay", "analyze_all", filepath="...")
                             │
                             ▼
                    Flat dict:
                    {"series.current.color": "#FF6600",
                     "series.voltage.color": "#0055CC",
                     ...}
                             │
                             ▼
                    pulse_stp_decay.py
                    cfg.get("series.current.color", "#CC0000")
```

---

## Config Schema to Add (config-studies.yaml)

### New key-based structure for pulse-stp-decay

```yaml
    pulse-stp-decay:
      # ... existing patterns, derived_metadata, instrument config, plot ...

      required_fields:
        - time_s
        - current_a
        - voltage_v

      interactive:
        analyze:
          analyze_all:
            menu_title: "Extract decay — fit segments, plot overview"
            handler: "science_cli.library.pulse.pulse_stp_decay.analyze_all"
            description: "Segment-aware: detect segments, fit each, overview plot, metadata"
            plot:
              figure:
                figsize: [10, 6]
                dpi: 150
              waveform:
                current_color: "#CC0000"
                current_label: "I(t)"
                voltage_color: "#0055CC"
                voltage_label: "V(t)"
                linewidth: 1.0
              fit:
                color: "black"
                style: "--"
                linewidth: 1.2
                markers: false
              rise_zoom:
                xpad: 0.15
                time_unit: "µs"
              segment_overview:
                layout: "grid"    # or "vertical"
                ncols: 3
                figsize: [12, 8]

          analyze_overlay:
            menu_title: "Overlay decay curves"
            handler: "science_cli.library.pulse.pulse_stp_decay.analyze_overlay"
            description: "Compare: plot fit curves of extracted-decay files"
            overlay: true
            plot:
              figure:
                figsize: [8, 3.5]
                dpi: 150
              colors:
                - "#CC0000"
                - "#0055CC"
                - "#2EA043"
                - "#CC7700"
              fit:
                style: "--"
                linewidth: 1.0
              legend:
                loc: "upper right"
                fontsize: 8
```

### New metadata schema (written to protocol.yaml)

**Key insight from user:** pulse-stp-decay metadata IS the `waveform_pattern` — a 2D array of `[time_s, voltage_v]` at voltage transition points only (|ΔV| > 0.1V). No separate v_set_v, v_read_v, widths, rise/fall needed — the waveform pattern captures everything about the pulse shape.

The `extracted_decay` should contain generic point-based segments + decay params:

```yaml
analyze:
  analyze_all:
    metadata:
      extracted_decay:
        seg_001:               # ← Generic numbered segments, each with START + END points
          t1_s: 2.2e-06        # Start: time (s)
          v1_v: 1.75           # Start: voltage
          i1_a: 3.22e-06       # Start: current
          t2_s: 8.46e-05       # End: time (s)
          v2_v: 0.14           # End: voltage
          i2_a: ...            # End: current
        seg_002:
          t1_s: ...
          v1_v: ...
          i1_a: ...
          t2_s: ...
          v2_v: ...
          i2_a: ...
        decay:
          tau_ms: <float>      # Decay time constant
          r_squared: <float>   # Fit quality
        # NOTE: No model field — user wants point data for plot markers
```

The key change vs. current `extracted_decay`:
- ❌ Remove `model` (monoexponential/biexponential)
- ❌ Remove per-segment fit details (a1, a2, initial_current_ua, steady_state_current_ua, decay_pct)
- ✅ Add `seg_NNN` — generic (V, I, t) point tuples for plot markers
- ✅ Keep `decay.tau_ms`, `decay.r_squared`

---

## Files to Modify

| # | File | Change | Risk |
|---|------|--------|------|
| M1 | `config/config-studies.yaml` | Add key-based `interactive.analyze` with `plot:` blocks for `analyze_all` + `analyze_overlay`; add `required_fields` | Low |
| M2 | `src/science_cli/library/pulse/pulse_stp_decay.py` | Add `resolve_analysis_plot_config()` calls; refactor `_plot_*` functions to read from config; restructure metadata to per-function keys; add `--show-config` | Med |
| M3 | `src/science_cli/core/protocol.py` | Add `write_file_analyze_metadata()`; update `resolve_file_analyze_config()` for `.config` sub-key with flat fallback | Low |
| M4 | `src/science_cli/library/pulse/pulse_endurance.py` | Update `_update_protocol_metadata()` → use `write_file_analyze_metadata()` (fixes step-level overwrite bug) | Med |

## Files to Create

| # | File | Change | Risk |
|---|------|--------|------|
| C1 | `~/.config/opencode/skills/sci-stp-decay/SKILL.md` | New skill documenting STP decay metadata schema, config schema, analysis workflow | Low |
| C2 | `.lavish/artifacts/220626d_stp-decay-skill.md` | Plan artifact for skill creation sub-task | Low |

---

## Task Decomposition

### Phase 4a: Config + Protocol (parallel)

**T1 — Config-studies.yaml update** (assignee: code)
- Convert pulse-stp-decay's `interactive.analyze` from flat `options:` to key-based with `plot:` blocks
- Add `required_fields`
- Skills to load: `sci-config-guide`
- Duration: 15m

**T2 — protocol.py: write_file_analyze_metadata** (assignee: code)
- Add `write_file_analyze_metadata(protocol_path, step_name, filename, function_name, metadata_dict)`
- Writes to `entry.analyze.<function_name>.metadata`
- Also update `resolve_file_analyze_config()` to check `.config` sub-key with fallback
- Skills to load: `clean-code`
- Duration: 20m

**T3 — pulse_endurance.py: fix metadata destination** (assignee: code)
- Replace `_update_protocol_metadata()` calls with `write_file_analyze_metadata()`
- This fixes the step-level overwrite bug
- Skills to load: `code-review`, `clean-code`
- Duration: 15m
- Depends on: T2

### Phase 4b: pulse_stp_decay.py refactor

**T4 — Add config wiring + restructure metadata** (assignee: code)
- Add `function_name` kwarg detection
- Call `resolve_analysis_plot_config("pulse:pulse-stp-decay", function_name, filepath=str(csv_path))`
- Refactor `_plot_full_waveform`, `_plot_rise_zoom`, `_plot_decay_zoom`, `_plot_single_segment`, `_plot_segment_overview` to accept config dict params
- Restructure `_tag_with_segment_metadata()` to use `write_file_analyze_metadata()`
- Add `--show-config` support
- Skills to load: `clean-code`, `code-splitting` (file is 861 lines — monitor)
- Duration: 2h
- Depends on: T1, T2

### Phase 4c: Skill creation

**T5 — Create sci-stp-decay skill** (assignee: config-opencode)
- Document the STP decay metadata schema (waveform params + extracted_decay)
- Document the analyze config schema (plot parameters for analyze_all + analyze_overlay)
- Document the analysis workflow (segment detection → fitting → plot → tag)
- Skills to load: `skill-creator`, `sci-config-guide`
- Duration: 30m

### Phase 4d: Validation

**T6 — QA with real data** (assignee: review)
- Run `analyze_all` on a real STP CSV from `res_internship`
- Verify config-driven colors/params are applied
- Verify metadata written correctly under `analyze.analyze_all.metadata`
- Verify per-file override works
- Verify `--show-config` prints resolved config
- Verify backwards compat (flat analyze config still works)
- Skills to load: `verify`, `review-report`
- Duration: 30m
- Depends on: T4

### Phase 4e: Documentation

**T7 — Docs + .lavish** (assignee: docs-heavy)
- Update CHANGELOG with new config wiring
- Version bump (v3.26.0 — feature)
- Update `.lavish/layer07-pulse-analyzers.html` with new STP artifacts
- Update `.lavish/layer01-config-grammar.html` for config changes
- Register all work items in `.lavish/` dashboards
- Notify Hermes if structural changes (skill creation = yes)
- Skills to load: `tool-docs`, `hermes-bridge`, `lavish-artifact`, `update-readme`
- Duration: 20m
- Depends on: T5, T6

---

## Agent Delegation

| Task | Sub-agent | Est. Time | Deps | Skills |
|------|-----------|-----------|------|--------|
| T1: config-studies.yaml | code | 15m | — | sci-config-guide |
| T2: protocol.py functions | code | 20m | — | clean-code |
| T3: fix endurance metadata | code | 15m | T2 | code-review, clean-code |
| T4: stp.py refactor | code | 2h | T1, T2 | clean-code, code-splitting |
| T5: create skill | config-opencode | 30m | T4 | skill-creator, sci-config-guide |
| T6: QA with real data | review | 30m | T4 | verify, review-report |
| T7: Docs + .lavish | docs-heavy | 20m | T5, T6 | tool-docs, hermes-bridge, lavish-artifact, update-readme |

## Dependency Graph

```
T1 ──┐
     ├── T4 ──┬── T5 ──┐
T2 ──┘        │        ├── T7
     └── T3   │        │
              └── T6 ──┘
```

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| pulse_stp_decay.py is 861 lines — close to 1000-line splitting threshold | Med | Keep refactor clean; split plotting into separate module if needed |
| `resolve_analysis_plot_config()` may need overlay vs single dispatch | Med | `analyze_overlay` has different config shape (color list); handle with `function_name` check |
| Backwards compat for flat analyze config (`x_pad_factor` directly under function key) | Low | `resolve_file_analyze_config()` checks `.config` sub-key first, falls back to whole dict |
| Metadata restructure breaks existing extracted_decay readers | Med | `_has_extracted_decay()` must check both old (`metadata.extracted_decay`) and new (`analyze.analyze_all.metadata.extracted_decay`) locations |

---

## Verification Plan

### Test 1: Default behavior (no per-file override)
1. `sci analyze --all` → FZF → select STP decay CSV → menu → pick "Extract decay"
2. Plots with config-studies.yaml defaults
3. Metadata written under `analyze.analyze_all.metadata.extracted_decay`

### Test 2: Per-file override
1. Add to protocol.yaml: `analyze.analyze_all.config.series.current.color: "#FF6600"`
2. Re-run → plot uses orange current line
3. `--show-config` dumps resolved config

### Test 3: Backwards compat
1. Existing `metadata.extracted_decay` entries still readable by `_has_extracted_decay()`
2. Old flat `analyze: { ratio_histogram: { x_pad_factor: 0.5 } }` still works

### Test 4: Overlay mode
1. `sci analyze` → multi-select STP files → pick "Overlay decay curves"
2. Config-driven colors applied

---

## Walkthrough (to be filled during implementation)

- [x] T1: Config schema updated ✓
- [x] T2: protocol.py functions added ✓
- [x] T3: pulse_endurance.py metadata fix ✓
- [x] T4: pulse_stp_decay.py refactored ✓
- [x] T5: Skill created ✓
- [x] T6: QA verified — 602 tests passing ✓
- [x] T7: Docs + .lavish updated ✓
