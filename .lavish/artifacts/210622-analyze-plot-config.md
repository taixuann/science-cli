---
layer: [1, 5, 6]
type: plan
status: planning
tags: [analyze, plot-config, protocol-override, skill]
depends_on: [210626-generic-plot-config-scale]
assignee: plan
---

# Implementation Plan: Analyze-Plot Config System

**Date**: 22/06/2026
**Status**: 🟡 Planning
**Layer**: 1 (Config) + 5 (Plotting Dispatch) + 6 (Protocol.yaml)

## Context Summary

The plot system already has a config-driven architecture — `config-studies.yaml` defines layout, columns, axis, scales, and series styling for every study. The analyze system does NOT use this — each analyze function hardcodes its own plot parameters (colors, bin counts, fit lines, axis limits) directly in Python.

This plan extends the config schema to cover analyze plots, letting users tune colors, y-axis limits, fit styles, bin counts, and other plot parameters per analysis function — with per-file overrides in protocol.yaml.

## Architecture

```
config-studies.yaml                  protocol.yaml
  └─ study:                            └─ step:
       analyze: {                          files:
         function_name: {                      - file: ...
           plot: {                              metadata:
             series: {color, marker}              analyze_overrides:
             y_max: "2nd-bin*1.5"                    function_name:
             bins: 50                                  plot:
             fit: {color, style}                         y_max: 1000
             legend: {loc, fontsize}
           }
         }
     }
```

### Resolution Order (lowest → highest priority)

1. **Defaults** (hardcoded in Python function — fallback)
2. **Config layer** (`config-studies.yaml:studies.<technique>.<study>.analyze.<function>.plot`)
3. **Device overrides** (`...device_overrides.<device>.analyze.<function>.plot`)
4. **Protocol file overrides** (`protocol.yaml:steps[].files[].metadata.analyze_overrides.<function>`)

## Objectives

1. Add `analyze.plot` schema to `config-studies.yaml` — each analyze function gets plot config sub-block
2. Create `resolve_analysis_plot_config(study_name, function_name, device_type, filepath)` — single entry point
3. Update pulse-endurance analyze functions (`ratio_histogram`, `i_ratio_histogram`, `ratio_vs_cycles`, `i_ratio_vs_cycles`) to read from resolved config
4. Extend STP decay analyze functions similarly
5. Migrate hardcoded parameters (bar colors, fit colors, legend position, bin counts, y-limit method) to config
6. Create `analyze-plot` skill for AI-driven tuning
7. QA + docs

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `config/config-studies.yaml` | Add `analyze.plot` blocks for pulse-endurance + STP (pulse-stp-decay) | Low |
| `src/science_cli/core/plot_config.py` | Add `resolve_analysis_plot_config()` function | Med |
| `src/science_cli/library/pulse/pulse_endurance.py` | Refactor 4 functions to read from config | Med |
| `src/science_cli/library/pulse/pulse_stp_decay.py` | Refactor analyze_all/analyze_overlay to read from config (if affected) | Med |
| `src/science_cli/core/protocol.py` | Add `resolve_file_analyze_overrides(filepath, function_name)` | Med |
| `config/config-instruments.yaml` | Optional: add instrument-level analyze config | Low |

## New Files

| File | Purpose |
|------|---------|
| `~/.config/opencode/skills/analyze-plot/SKILL.md` | Analyze-plot tuning skill |
| `~/.config/opencode/skills/analyze-plot/scripts/tune_analyze.py` | Script for AI-driven tuning |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| 1. Config schema + YAML changes | `code-medium` | Add analyze.plot blocks to config-studies.yaml |
| 2. `resolve_analysis_plot_config()` | `code-medium` | New function in core/plot_config.py |
| 3. Protocol file override getter | `code-medium` | New function in core/protocol.py |
| 4. Refactor pulse_endurance.py | `code-medium` | 4 functions read from config |
| 5. Create analyze-plot skill | `config-opencode` | Skill + script |
| 6. QA | `review-light` | pytest + verify |
| 7. Docs + dashboard | `docs-light` | README, CHANGELOG, .lavish |

## Tasks

| ID | Description | Est. Duration | Assigned To | 
|----|-------------|---------------|-------------|
| T1 | Add `analyze.plot` schema to config-studies.yaml | 30m | code |
| T2 | `resolve_analysis_plot_config()` in core/plot_config.py | 45m | code |
| T3 | `resolve_file_analyze_overrides()` in core/protocol.py | 30m | code |
| T4 | Refactor ratio_histogram + current_ratio_histogram | 1h | code |
| T5 | Refactor ratio_vs_cycles + i_ratio_vs_cycles | 30m | code |
| T6 | Refactor STP analyze functions (if affected) | 30m | code |
| T7 | Create analyze-plot skill | 30m | config-opencode |
| T8 | QA | 20m | review |
| T9 | Docs + dashboard | 20m | docs |

## Dependency Order

1. T1 (config schema) → T2 (config resolver) → T3 (protocol overrides) → T4+T5+T6 (function refactors) → T7 (skill) → T8 (QA) → T9 (docs)

## Config Schema Design

### Pulse-endurance analyze plot config

```yaml
    pulse-endurance:
      analyze:
        options:
          - name: "Ratio vs Cycles"
            handler: "science_cli.library.pulse.pulse_endurance.ratio_vs_cycles"
            # ...
        plot_defaults:
          ratio_vs_cycles:
            layout: single
            axes:
              xscale: log
              yscale: log
            series:
              scatter:
                color: "#CC7700"
                size: 6
                alpha: 0.6
                label: "Data"
              fit:
                color: "red"
                style: "--"
                linewidth: 1.2
            legend:
              loc: "upper right"
              fontsize: 8
            title_template: "V_set={v_set:.2f}V, V_read={v_read:.2f}V"
          ratio_histogram:
            bins: 50
            y_max_method: "2nd-bin*1.5"    # Auto cap
            series:
              bar:
                color: "#2EA043"
                alpha: 0.7
                edgecolor: "black"
                linewidth: 0.5
              fit:
                type: "log-normal"
                color: "black"
                style: "--"
                linewidth: 1.2
              mean_line:
                color: "red"
                style: "--"
              median_line:
                color: "blue"
                style: ":"
            legend:
              loc: "upper right"
              fontsize: 8
```

### Protocol per-file overrides

```yaml
files:
  - file: 200626-140448_keysight-b1500a_cu-c-pda(q5)-ito(2)_r5-c4_pulse-endurance_{extracted-list}_[important].csv
    metadata:
      analyze_overrides:
        ratio_histogram:
          plot:
            y_max: 300
            bar_color: "#8B0000"
            fit_color: "#333333"
```

## `resolve_analysis_plot_config()` API

```python
def resolve_analysis_plot_config(
    study_name: str,            # e.g. "pulse:pulse-endurance"
    function_name: str,         # e.g. "ratio_histogram"
    device_type: str | None,    # e.g. "volatile-memristor"
    filepath: str | Path | None = None,  # for protocol overrides
) -> dict:
```

Returns flat dot-separated dict (same pattern as `resolve_plot_config()`).

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Circular import in plot_config.py | Med | Keep analyze resolver in separate module (core/analyze_config.py) |
| Backwards compatibility | Low | Functions fallback to hardcoded values if no config found |
| Per-file overrides explode protocol.yaml size | Low | Only store overrides that differ from defaults |
