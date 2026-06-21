# Implementation Plan: Pulse Analyzers + Waveform Subfigure

**Date**: 21/06/2026
**Status**: 🟢 Done
**Layer**: 7 (Pulse Analyzers) + 5 (Plotting Dispatch)
**Version**: v3.24.2 (final) — see `210626_stp-segment-decay.md` for segment-aware extraction (v3.24.1) and `--describe` redesign (v3.24.2)

---

## Context Summary

Layer 7 has **4 CLI analyzers that are all stubs** — they just print "not implemented". Meanwhile, the library code already has working analysis functions (`library/pulse/stp.py`, `endurance.py`, `ppf.py`) with `analyze_*_to_yaml()` that write to `<step>/results/<technique>_analysis.yaml`. The gap is **wiring**: the CLI stubs don't load data, call library code, or save results.

Additionally, the user wants `sci plot --all --describe` to show the waveform segments as a **subfigure on the right** of the main plot, instead of a terminal text table.

### Current Pulse Analyzer Stubs (analyze.py:650-686)

```python
def _analyze_pulse_stp(filepath, flags):
    console.print("[yellow]STP decay analysis not yet implemented.[/yellow]")

def _analyze_pulse_endurance(filepath, flags, device_type=None, study_name=None):
    console.print("[yellow]...[/yellow]")

def _analyze_pulse_ppf(filepath, flags):
    console.print("[yellow]...[/yellow]")

def _analyze_pulse_retention(filepath, flags):
    console.print("[yellow]...[/yellow]")
```

### Existing Library Code

| Module | Functions | What it computes |
|--------|-----------|-----------------|
| `library/pulse/stp.py` | `analyze_stp_decay(time, current)`, `analyze_stp_decay_to_yaml(...)` | Mono/biexponential fit, tau, decay %, R² |
| `library/pulse/endurance.py` | `analyze_endurance(r_on, r_off, cycles)`, `analyze_endurance_to_yaml(...)` | Mean R, CV, Weibull failure, tail stats |
| `library/pulse/ppf.py` | `analyze_ppf(intervals_ms, ratios)`, `analyze_ppf_to_yaml(...)` | Facilitation tau, A amplitude, R² |

### TECHNIQUE_ANALYZERS Registry (analyze.py:13)
Already has entries:
- `pulse-stp` → `_analyze_pulse_stp`
- `pulse-endurance` → `_analyze_pulse_endurance`
- `pulse-ppf` → `_analyze_pulse_ppf`
- `pulse-retention` → `_analyze_pulse_retention`

### Data Flow for Each Analyzer
```
sci analyze --study pulse:pulse-stp-decay file.csv
    ↓
load_data_file(filepath, study_name=study_name)
    ↓
df, info = (DataFrame with columns: time, voltage, current)
    ↓
_extract_columns(df, study_name) → time, current, voltage
    ↓
library/pulse/stp.py: analyze_stp_decay_to_yaml(time, current, step_dir, ...)
    ↓
write_analysis_yaml() → <step>/results/pulse-stp_analysis.yaml
    ↓
Also writes summary to protocol.yaml via merge_analysis_to_metadata()
```

---

## Objectives

### Workstream A: Pulse Analyzers (Layer 7)

1. Implement `_analyze_pulse_stp()` — load STP data, call library, save YAML
2. Implement `_analyze_pulse_endurance()` — load endurance data (pre-processed CSV), call library, save YAML
3. Implement `_analyze_pulse_ppf()` — load PPF data, call library, save YAML
4. Implement `_analyze_pulse_retention()` — stub for now (no library code exists)
5. All analyzers write to `<step>/results/<technique>_analysis.yaml` + protocol.yaml

### Workstream B: Waveform Subfigure (Layer 5)

6. When `--describe` flag is passed with `plot`, add a **second subfigure** on the right showing the waveform segments as a stepped voltage-time diagram
7. Read `waveform_pattern` from file metadata (protocol.yaml or in-memory analysis)
8. Draw voltage steps with labels (wait, set_rise, set, read, hold)

---

## Files to Modify

| File | Change | Risk | Workstream |
|------|--------|------|-----------|
| `cli/commands/analyze.py` | Replace 4 stubs with real implementations | Med | A |
| `cli/commands/plot.py` | Add `--describe` subfigure dispatch | Low | B |
| `plot/registry.py` | Update `_show_describe()` to return data for subfigure | Low | B |
| `plot/generic.py` | Add waveform subfigure rendering | Med | B |

No new files needed.

---

## Analyzer Implementation Details

### _analyze_pulse_stp (easiest — most library code ready)

```python
def _analyze_pulse_stp(filepath: str, flags: dict) -> None:
    df, info = load_data_file(filepath, study_name="pulse:pulse-stp-decay")
    time = df["time"].values
    current = df["current"].values * -1  # current_sign
    
    fp = Path(filepath)
    step_dir = fp.parent
    metadata = info.get("metadata", {})
    project_root = fp.parent.parent.parent  # protocol/
    
    from science_cli.library.pulse.stp import analyze_stp_decay_to_yaml
    result_path = analyze_stp_decay_to_yaml(
        time, current, step_dir,
        metadata=metadata,
        project_root=project_root,
        step_name=fp.parent.name,
    )
    console.print(f"[green]Analysis saved: {result_path}[/green]")
```

### _analyze_pulse_endurance (needs pre-processed CSV with cycle/r_hrs/r_lrs/ratio)

```python
def _analyze_pulse_endurance(filepath, flags, device_type=None, study_name=None):
    df, info = load_data_file(filepath, study_name="pulse:pulse-endurance")
    # Detect columns: cycle, r_hrs_ohm, r_lrs_ohm, ratio (from pre-processed CSV)
    # or raw measurement columns (from raw CSV)
    if "cycle" in df.columns and "r_hrs_ohm" in df.columns:
        r_hrs = df["r_hrs_ohm"].values
        r_lrs = df["r_lrs_ohm"].values
        cycles = df["cycle"].values
    else:
        # For raw endurance files, use the existing endurance hot parser
        from science_cli.library.pulse.endurance import analyze_endurance_to_yaml
        ...
    
    analyze_endurance_to_yaml(r_hrs, r_lrs, cycles, step_dir, ...)
```

### _analyze_pulse_ppf

```python
def _analyze_pulse_ppf(filepath, flags):
    df, info = load_data_file(filepath, study_name="pulse:pulse-ppf")
    # PPF files have: interval_ms, ratio columns (pre-processed)
    # or raw pulses to compute A2/A1 ratio
    intervals = df["interval_ms"].values
    ratios = df["ratio"].values
    analyze_ppf_to_yaml(intervals, ratios, step_dir, ...)
```

### _analyze_pulse_retention
No library code — keep as stub with more helpful message.

---

## Waveform Subfigure Design (Workstream B)

When `--describe` flag is passed with `plot`:

```
┌─────────────────────┬────────────────────┐
│                     │                    │
│   Main Plot         │   Waveform         │
│   (current vs time) │   (V vs time)      │
│                     │   with segments    │
│                     │                    │
│                     │                    │
└─────────────────────┴────────────────────┘
```

**Implementation**:
1. In `_do_plot()`, check if `--describe` flag is present
2. If yes, create a `plt.subplots(1, 2, figsize=(6.92, 2.75))` instead of single axes
3. Right axes: read `waveform_pattern` from `info["analysis"]`, draw a **step plot**: voltage vs time
4. Label segments with their type (wait → set_rise → set → read → hold)
5. If no waveform_pattern available, show a text box with available metadata

**Config**: Add `subfigure_layout: wave | none` to config-studies.yaml later, but initially just detect `--describe` flag.

---

## Agent Delegation

| Task | Sub-agent | Est. | Notes |
|------|-----------|------|-------|
| task-001: Wire _analyze_pulse_stp | code-medium | 30m | Easiest: direct library call |
| task-002: Wire _analyze_pulse_endurance | code-heavy | 1h | Pre-processed CSV + raw fallback |
| task-003: Wire _analyze_pulse_ppf | code-medium | 30m | Direct library call |
| task-004: Wire _analyze_pulse_retention | code-light | 10m | Keep stub, better message |
| task-005: Waveform subfigure in plot | code-heavy | 2h | Subplot layout + step rendering |
| task-006: QA & Review | review-medium | 1h | Test all 4 analyzers + plot change |
| task-007: Documentation | docs-light | 30m | Update CHANGELOG, version bump |

---

## Dependency Order

1. **task-001, -002, -003, -004** (analyzers) — can all run in parallel
2. **task-005** (waveform subfigure) — independent of analyzers, can also run in parallel
3. **task-006** (review) — depends on all code tasks completing
4. **task-007** (docs) — depends on review passing

---

## Risks

1. **Endurance data format varies** — some files are pre-processed CSV (cycle/r_hrs/r_lrs/ratio), some are raw WGFMU. The analyzer needs to detect format and handle both. Mitigation: try pre-processed first, fall back to raw parsing.

2. **STP decay analysis requires V_set current region** — `analyze_stp_decay()` expects the current during the V_set plateau, not the full trace including transitions. Need to filter data first (use voltage > 0.05 threshold or select points in the V_set plateau).

3. **PPF analysis requires pre-processed data** — raw WGFMU files don't have interval_ms/ratio columns. PPF analysis requires pre-computed A1/A2 ratios. Mitigation: document this as pre-processing requirement (same model as endurance).

4. **Waveform subfigure may slow down plotting** — adding a subplot doubles figure width. Use conditional: only create subfigure when `--describe` flag is active.

---

## Walkthrough

(To be filled during/after implementation)
