---
layer: [1, 5]
type: plan
status: planning
tags: [config, plot, params]
assignee: plan
---

# Implementation Plan: Config-First Plot Parameters

**Date**: 19/06/2026
**Status**: 🟡 Planning
## Context Summary

Science-cli currently has **two parallel theme systems**:
1. `theme/plot-theme/*.yaml` — the active one, loaded by `apply_theme()` → `theme_to_rcparams()` → `mpl.rcParams`
2. `config-template.yaml:templates.*.rcparams` — legacy, maintained separately, can drift

Additionally, every plot function has **hardcoded defaults** for markers, colors, linewidths, and figure sizes. These are scattered across `plot/` (12+ files). There is no single place to see "what does a pulse-endurance plot look like?" — you have to read the Python code.

## Proposal (from user)

**Single source of truth**: `config-studies.yaml` gets a per-study `plot:` block that defines:
- Marker style, marker size
- Colors (per-series where needed)
- Line width
- Figure size
- Grid on/off, grid alpha
- Axis scale (linear/log)
- Axis limits (xlim, ylim)
- Show/hide legend
- Inline annotations (label text, position)
- Any other per-study plot defaults

**dpi is always 600** — global default, not per-study. Set once, forget.

**CLI override always wins**: if user passes `--marker s --color red`, that overrides the config. If they don't, the config value is used. If config has no value, the hardcoded fallback in Python runs.

**`--label-name` stays manual** — for overlays where you want custom legend labels. Config doesn't need to know your overlay labels.

**Auto-detect studies/devices/instruments** — this already works. `data_loader.py` resolves study from filename patterns (grammar → study). `plot_handler()` resolves the plotter via `resolve_study_plotter(study_name, device_type)`. The config loader just plugs into the existing pipeline — no new detection needed.

**Device can override plot params too** — not just metadata. The existing `device_overrides` in `config-studies.yaml` (used for metadata keys like `r_decay_ohm`) should also accept a nested `plot:` block that overrides the study-level plot config per device:

```yaml
device_overrides:
  volatile-memristor:
    add: [r_decay_ohm]
    plot:
      ylabel: "R_decay ($\Omega$)"
      series:
        hrs:
          color: "#2176AE"
  non-volatile-memristor:
    add: [r_high_ohm, r_low_ohm]
    plot:
      ylabel_hi: "R_high ($\Omega$)"
      ylabel_lo: "R_low ($\Omega$)"
      series:
        hrs:
          color: "#D64045"
        lrs:
          color: "#1B998B"
```

This way the YAML is the single source for both *what to extract* and *how to plot it* — no Python code guesses default colors per device.

**Resolution order** (highest → lowest):
```
CLI flags > protocol.yaml step overrides > device-level plot overrides > study-level plot config > theme YAML > matplotlib defaults
```

**Single theme source**: deprecate `theme/plot-theme/*.yaml` in favor of `config-template.yaml` as the sole theme definition. Or consolidate them first (decided in Phase 2).

**Config metadata + plot + instrument integration**: The plot config must work with the existing detection pipeline. When a file is loaded:
1. Grammar pattern → detects **study** (e.g. `pulse:pulse-endurance`)
2. Config → detects **device_type** from file naming pattern (e.g. `volatile-memristor`)
3. Config → detects **instrument** from header structure (e.g. `keysight-b1500a`)
4. Plot config → reads `config-studies.yaml: studies.<group>.<study>.plot`
5. Plot config → optionally reads `device_overrides` for per-device variant

All three (study + device + instrument) together select the `plot:` config and the plotter dispatch. This already works in the pipeline — the config loader just adds a new leaf to read from.

**What "combine well" means**: The metadata extracted by the instrument parser (V_set, compliance, sweep_range, etc.) should flow naturally into plot annotations and the `--report` feature. The instrument says *how to read the file* and *what metadata exists*. The plot config says *how to draw it*. These don't fight each other — they're complementary layers.

**Transitions to avoid overlap**: When a device produces multiple studies (e.g. STP decay + endurance + PPF), the plot config per-study should ensure:
- Consistent color schemes across studies (same device = same family of colors)
- Non-overlapping annotation positions (HRS/LRS labels don't collide)
- Consistent figure sizing (all pulse studies share the same figsize)
- Per-device `device_overrides` in the study definition handle the device-specific plot differences

This is managed by putting the shared defaults (figsize, font, global colors) in the theme, and per-study specifics (series, annotations, axis limits) in the study config. The merge logic ensures theme defaults → study overrides → CLI overrides — each layer fills in what the layer above doesn't specify.

---

## Phase 1: Define the `plot:` schema in `config-studies.yaml`

### New `plot:` block structure

Under each study entry in `config-studies.yaml`, add a `plot:` block:

```yaml
studies:
  pulse:
    pulse-endurance:
      # ... existing keys (label, patterns, data_shape, derived_metadata, instruments)
      plot:
        figure:
          figsize: [3.46, 2.75]       # Nature single-column width
        axes:
          xscale: log
          yscale: log
          xlim: [0.8, 2e6]            # default x-axis range
          grid: true
          grid_alpha: 0.25
        legend: false                  # no legend — annotations instead
        series:
          hrs:
            label: "HRS"
            color: "#CC0000"
            marker: "o"
            markersize: 4
            linewidth: 0
            alpha: 0.8
          lrs:
            label: "LRS"
            color: "#0055CC"
            marker: "s"
            markersize: 4
            linewidth: 0
            alpha: 0.8
          ratio:
            label: "HRS/LRS"
            color: "#CC7700"
            marker: "^"
            markersize: 4
            linewidth: 0
            alpha: 0.8
        annotations:
          hrs:
            text: "HRS"
            position: last
            offset_x: 1.10           # x-offset multiplier
            offset_y_below: 0.93      # y-offset fraction (below the line)
            color: "#CC0000"
            fontweight: bold
          lrs:
            text: "LRS"
            position: last
            offset_x: 1.10
            offset_y_above: 1.07     # y-offset fraction (above the line)
            color: "#0055CC"
            fontweight: bold
```

For simpler studies (like IV sweep), it's shorter:

```yaml
    iv-bipolar-sweep:
      plot:
        figure:
          figsize: [3.46, 2.75]
        axes:
          xlabel: "Voltage (V)"
          ylabel: "Current (A)"
          xlim: [-0.5, 2.0]
          ylim: [-1e-3, 1e-3]
          grid: true
        legend: true                   # legend on for IV
        series:
          sweep:
            color: "#000000"
            linewidth: 1.0
            marker: "none"
```

### Design principles

1. **Minimal by default** — a study can specify `plot:` with just a few overrides; missing keys fall through to theme defaults
2. **Series-based** — each trace line in a plot is a named series (`hrs`, `lrs`, `sweep`, `nyquist`, etc.)
3. **Annotations are part of config** — inline annotations (HRS/LRS text near the points) are configured per-series, not hardcoded
4. **dpi is always 600** — set once in `config-template.yaml: templates.publication-nature.savefig.dpi`, never per-study
5. **`--label-name` stays manual** — overlays need custom labels the user provides; no config needed

---

## Phase 2: Build the Config Loader

### New function: `resolve_plot_config(study_name, device_type=None)`

Location: `src/science_cli/core/plot_config.py` (new file)

```python
def resolve_plot_config(study_name: str, device_type: str | None = None) -> dict:
    """Load per-study plot config from config-studies.yaml, merge with theme defaults.
    
    Resolution order:
      1. Start with theme defaults (from config-template.yaml: themes.<active>)
      2. Override with study-level plot config
      3. (Future) override with device-level plot config
    
    Returns a flat dict with keys like:
      figure.figsize, axes.xscale, series.hrs.color, annotations.hrs.text, etc.
    """
```

### How it merges

The config loader reads:
1. `config.yaml` → get active theme name
2. `config-template.yaml` → `templates.<theme>.rcparams` for global defaults
3. `config-studies.yaml` → `studies.<technique_group>.<study>.plot` for per-study overrides
4. `config-studies.yaml` → `studies.<technique_group>.<study>.device_overrides.<device>.plot` for per-device overrides (if device_type is resolved)

Merge is deep and follows resolution order:
- Start with theme defaults
- Merge in study-level `plot:` block (study overrides theme)
- If device_type is known, merge in `device_overrides.<device>.plot:` (device overrides study)
- CLI flags are applied last, overriding everything

### Integration with existing flag system

The existing `flags: dict` that flows through `all_flags` → `apply_figure_kw()` would be **pre-populated** with config values before CLI parsing. So:

```python
# In cli/commands/plot.py plot_handler():
study_name = resolve_study(...)
plot_config = resolve_plot_config(study_name)
flags = {}                        # from CLI parser
flags = merge(plot_config, flags) # config defaults, CLI overrides
```

This means `flags.get("color")` would return CLI value if given, else config value, else None. The plot function's hardcoded defaults become the final fallback.

---

## Phase 3: Migrate Plot Functions

### Phase 3a: `pulse_endurance.py` (pilot — we already know this study)

Remove hardcoded:
```python
color = flags.get("color", "#2176AE")  # becomes flags.get("series.hrs.color") from config
marker = flags.get("marker", "o")       # becomes flags.get("series.hrs.marker") from config
markersize = float(flags.get("markersize", 10))  # from config
```

The plot function becomes:
```python
def _plot_endurance_volatile(filepath: str, flags: dict) -> None:
    apply_theme(get_active_theme())
    data = _load_and_resolve(...)
    # ... load data ...
    fig, ax = plt.subplots(figsize=parse_figsize(flags, study="pulse:pulse-endurance"))
    
    hrs_cfg = flags.get("series.hrs", {})
    lrs_cfg = flags.get("series.lrs", {})
    
    ax.loglog(cycles, r_hrs, 
              marker=hrs_cfg.get("marker", "o"),
              markersize=float(hrs_cfg.get("markersize", 4)),
              color=hrs_cfg.get("color", "#CC0000"),
              alpha=float(hrs_cfg.get("alpha", 0.8)))
    # ... annotations from config ...
```

### Phase 3b: Apply to all other plot types

- `iv.py` — single series, simple migration
- `eis.py` — multiple series (nyquist, bode, fit)
- `cv.py` — multiple cycles/sweeps
- `ca.py` — single series
- `raman.py`, `uv_vis.py` — single series
- `stp.py`, `ppf.py`, `pulse_retention.py` — pulse studies, similar to endurance
- `afm.py` — image-based, different pattern (pseudocolor maps)

### Phase 3c: Deprecate `template_to_flags()`

The `template_to_flags()` function in `registry.py` reads from `plot-templates/*.yaml`. After migration, this is redundant — the config is the source. Phase 3c removes `plot-templates/` and `template_to_flags()`.

---

## Phase 4: Consolidate Theme Systems

With per-study `plot:` blocks, the theme system's role shrinks to:
- Global fonts (family, size)
- Global axis styling (spines, tick direction)
- Legend defaults
- Savefig defaults

Consolidation plan:
1. Move all theme definitions from `theme/plot-theme/*.yaml` into `config-template.yaml:templates.*`
2. Update `apply_theme()` in `registry.py` to read from `config-template.yaml` instead of `plot-theme/*.yaml`
3. Remove `theme/plot-theme/` directory
4. Keep `apply_theme()` as the entry point — it still applies mpl.rcParams, just reads from a different source

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Update config-studies.yaml with plot: blocks | code-light or code-medium | Add `plot:` to every study that has a plotter |
| Build `core/plot_config.py` | code-medium | New file: resolve_plot_config(), merge logic, tests |
| Migrate `pulse_endurance.py` | code-medium | Pilot migration, verify plots match current output |
| Migrate `iv.py`, `eis.py`, `cv.py`, `ca.py` | code-medium | Standard plot types |
| Migrate `raman.py`, `uv_vis.py`, `afm.py` | code-light | Simpler plot types |
| Migrate `stp.py`, `ppf.py`, `pulse_retention.py` | code-medium | Pulse studies |
| Consolidate theme systems | code-heavy | Merge plot-theme/ → config-template.yaml |
| Remove `plot-templates/` + `template_to_flags()` | code-light | Cleanup after migration |
| QA + review | review-medium | Verify each plot type still matches, flag diffs |
| Docs update | docs-medium | CHANGELOG, AGENTS.md, sci-theme-plotting skill update |
| Skill propagation | skill-maintenance | Update sci-config-guide, sci-fzf-guide if affected |

---

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| PLOT-001 | Design and write `resolve_plot_config()` in `core/plot_config.py` | 1.5h | code-medium |
| PLOT-002 | Add `plot:` blocks to all studies in `config-studies.yaml` | 1h | code-light |
| PLOT-003 | Migrate `pulse_endurance.py` to use config values | 1h | code-medium |
| PLOT-004 | Migrate `iv.py`, `eis.py`, `cv.py`, `ca.py` | 2h | code-medium |
| PLOT-005 | Migrate `raman.py`, `uv_vis.py`, `afm.py` | 1h | code-light |
| PLOT-006 | Migrate `stp.py`, `ppf.py`, `pulse_retention.py` | 1.5h | code-medium |
| PLOT-007 | Consolidate theme: move plot-theme/ → config-template.yaml | 1.5h | code-heavy |
| PLOT-008 | Remove `plot-templates/` + `template_to_flags()` | 30m | code-light |
| PLOT-009 | QA review — verify all plot types match | 1.5h | review-medium |
| PLOT-010 | Update documentation + skills | 1h | docs-medium |

**Total estimated time**: ~12h (3-4 sessions)

---

## Dependency Order

```
Phase 1: Schema design (PLOT-002)
    │
    ▼
Phase 2: Config loader (PLOT-001) — needed before any migration
    │
    ▼
Phase 3a: Pilot — pulse_endurance (PLOT-003)
    │        Verify plots match before proceeding
    ▼
Phase 3b: All other plot types (PLOT-004, PLOT-005, PLOT-006)
    │
    ▼
Phase 4: Theme consolidation (PLOT-007, PLOT-008)
    │
    ▼
QA + Docs (PLOT-009, PLOT-010)
```

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Plots don't look the same after migration | High | Phase 3a pilot + review-medium in Phase 3b compares pixel diffs |
| Config YAML becomes bloated | Low | `plot:` blocks are per-study, not per-file. ~20 lines per study, ~15 studies = ~300 lines total |
| CLI flag override doesn't work | High | Must test that CLI flags override config during Phase 2+3a |
| Protocol.yaml integration delayed | Medium | Phase 2 can skip protocol.yaml for now; add it in a follow-up |
| Config merge is complex (nested dicts) | Medium | Use `deepmerge` library or simple recursive merge; test thoroughly |

---

## Walkthrough (step-by-step, filled after implementation)

```
Phase 1:
  [ ] Define YAML schema for plot: block
  [ ] Add plot: blocks to all 15 studies

Phase 2:
  [ ] Create core/plot_config.py
  [ ] Implement resolve_plot_config()
  [ ] Integrate with CLI plot_handler()

Phase 3:
  [ ] Migrate pulse_endurance.py
  [ ] Verify plots match
  [ ] Migrate all other plot types
  [ ] Remove template_to_flags()

Phase 4:
  [ ] Move plot-theme/ → config-template.yaml
  [ ] Update apply_theme() source
  [ ] Remove plot-theme/ directory

QA:
  [ ] Compare plots before/after for all types
  [ ] Test CLI flag overrides
  [ ] Test protocol.yaml overrides (if integrated)

Docs:
  [ ] CHANGELOG
  [ ] AGENTS.md
  [ ] sci-theme-plotting skill update

---

## Phase 5 (Future): `plot --matrix NxM` — Generic Multi-Panel Grid

**Status**: 🟡 Not started. Estimated 1-2 sessions after Phase 4.
**Requires**: Phase 1-4 complete (config-driven per-study plot params).

### How it works
```
sci plot file1.csv file2.csv file3.csv file4.csv --matrix 2x2
```
Creates a 2×2 grid figure. Each file gets one panel. The panel's study-based plot config is applied per-panel.

### What config needs
Nothing new — `--matrix` reads the same per-study `plot:` blocks. The grid layout is purely a CLI/UI concern:

```python
# In plot_handler():
if flags.get("matrix"):
    rows, cols = map(int, flags["matrix"].lower().split("x"))
    fig, axes = plt.subplots(rows, cols, ...)
    for idx, (ax, filepath) in enumerate(zip(axes.flat, files)):
        plot_fn(filepath, flags, ax=ax)  # inject ax into plot function
```

### Design decisions to make
1. What happens if `#files > rows×cols`? (trim? next page?)
2. What if `#files < rows×cols`? (empty panels? hide extras?)
3. Axis sharing — shared x/y scales across panels?
4. Does `--matrix` work with `--overlay`? (probably not — they're different things)

### Limitations for now
- All panels must be the same study (mixing IV + EIS in one grid = later)
- Grid is rectangular — `--matrix 2x2`, `--matrix 3x1`, `--matrix 1x4`
- No cross-panel axis sharing (yet)

---

## Phase 6 (Future): `plot --report` — Figures + Metadata Annotations

**Status**: 🟡 Not started. Estimated 2-3 sessions after Phase 5.
**Requires**: Phase 1-4 complete + metadata available from protocol.yaml.

### How it works
```
sci plot file1.csv --report
```
Creates a plot that includes:
- The data plot (using study plot config)
- A metadata panel/annotations showing: study name, device, instrument, date, key parameters

### What config needs
The metadata fields come from `protocol.yaml` step metadata (which is already populated after `sci analyze`). The `--report` flag triggers a **composite template** that composes the plot + metadata box.

### Output sketch
```
┌──────────────────────────────────┐
│  Resistance vs Cycle               │
│  ┌─────────────────────┐  ┌────┐  │
│  │    plot data         │  │Meta│  │
│  │    (log-log)        │  │    │  │
│  │    HRS ● ● ●        │  │    │  │
│  │    LRS ■ ■ ■        │  │    │  │
│  └─────────────────────┘  └────┘  │
│  Cycle                            │
├──────────────────────────────────┤
│  CU-C-PDA(Q5)-ITO(2) · R5-C3    │
│  2026-06-18 · Keysight B1500A   │
│  R_LRS: 4.6 kΩ · R_HRS: 0.82 MΩ│
└──────────────────────────────────┘
```

### Data sources
- **Study/device/instrument**: from filename → grammar → study + config → instrument
- **Date**: from file header (e.g. `MetaData, TestRecord.RecordTime`)
- **Key parameters**: from `protocol.yaml` step metadata (written by `merge_analysis_to_metadata()`)
- **Analysis results**: from `results/` YAML files (written by analyze)

### Design decisions to make
1. Metadata as overlay (text on the plot) vs sidebar (extra axes)?
2. Which fields to show and in what order? (per-study configurable?)
3. Output format: PNG for sharing vs PDF for publication?
4. Annotated metadata in figure caption vs in the image itself?
```

---

## Appendix A: Full Config-Plot Audit (19/06/2026)

### Data Flow Map (as-is)

```
Filename
   │
   ▼
Grammar patterns (config-instruments.yaml: instruments.<name>.filename_patterns)
   → detects technique word from filename (e.g. "stp-decay", "endurance", "iv-sweep")
   │
   ▼
detect_study_from_filename (core/studies.py:60)
   → matches technique word against studies.<technique>.<study>.patterns
   → returns "technique:study-name" (e.g. "pulse:pulse-endurance")
   │
   ▼
get_device_config (core/config.py:466)
   → reads studies.<technique>.<study>.instruments.<device> for parsing config
   → falls back to _DEFAULT_TECHNIQUE_DEVICES hardcoded dict
   → falls back to config-instruments.yaml: instruments.<name>.parsing
   │
   ▼
resolve_study_plotter (plot/registry.py:70)
   → looks up STUDY_PLOTTERS["technique:study-name"]
   → if device_type provided, merges device_variants.<device>
   → returns StudyPlotter(plot_fn, overlay_fn, flags, hints)
   │
   ▼
plot_handler (cli/commands/plot.py)
   → apply_theme(get_active_theme()) — reads from theme/plot-theme/*.yaml
   → template_to_flags(technique) — reads from theme/plot-templates/*.yaml (3rd source!)
   → get_plot_labels(technique) — reads from config-template.yaml:plot_labels
   → calls plot_fn(filepath, all_flags)
   │
   ▼
Plot function (plot/*.py)
   → applies global flags from all_flags dict
   → applies hardcoded defaults for colors, markers, sizes, annotations
   → draws using mpl with rcParams set by apply_theme()
```

### Full Config File Cross-Reference

| What | Where defined | Where read | Status |
|------|--------------|-----------|--------|
| Device types | config-devices.yaml | core/studies.py lazy | ✅ |
| Device→studies mapping | config-devices.yaml | core/studies.py:get_studies_for_device_type | ✅ |
| Legacy technique mapping | config-devices.yaml:legacy_to_study | core/studies.py:resolve_legacy_technique | ✅ |
| Study definitions (patterns, labels, metadata, instruments) | config-studies.yaml | core/studies.py:get_study_config, config.py:get_study_config | ✅ |
| Study→instrument metadata extractors | config-studies.yaml:studies.*.*.instruments.*.metadata | core/config.py:get_device_config (lines 510-527) | ✅ |
| Device overrides for metadata | config-studies.yaml:device_overrides.<device>.add | merge_analysis_to_metadata() | ✅ |
| **Device overrides for plot** | config-studies.yaml:device_overrides.<device>.plot | **❌ NOT IMPLEMENTED** | ❌ |
| **Per-study plot params (colors, markers, annotations)** | config-studies.yaml:studies.*.*.plot | **❌ NOT IMPLEMENTED** | ❌ |
| Global theme (active choice) | config.yaml:theme | core/session.py:get_active_theme → plot/*.py | ✅ |
| Theme rcParams (active source) | theme/plot-theme/*.yaml | theme/registry.py:theme_to_rcparams → apply_theme | ✅ |
| Theme rcParams (legacy, duplicate) | config-template.yaml:templates.*.rcparams | **⬇️ NOT READ by apply_theme** | 🟡 Dormant |
| Plot axis labels | config-template.yaml:templates.plot_labels | config.py:get_plot_labels | ✅ |
| Per-technique plot presets (Tier 2) | theme/plot-templates/*.yaml | theme/registry.py:template_to_flags | 🟡 Shallow read |
| Instrument parsing config (delimiter, columns, encoding) | config-instruments.yaml:instruments.*.parsing | config.py:get_device_config (lines 540-546) | ✅ |
| Instrument→grammar patterns | config-instruments.yaml:instruments.*.filename_patterns | config.py:get_instrument_grammar | ✅ |
| Per-project config overrides | <project>/devices.yaml | config.py:get_device_config (lines 549-554) | ✅ |

### Issues Found

| # | Issue | Severity | File(s) |
|---|-------|----------|---------|
| 1 | `template_to_flags()` reads from theme/plot-templates/*.yaml — a 3rd overlapping source | Medium | theme/registry.py |
| 2 | No pulse study plot labels in config-template.yaml — hardcoded in Python | Low | config-template.yaml, plot/*.py |
| 3 | config.yaml default_dpi:300 vs user wants 600 | Low | config.yaml |
| 4 | No plot:block exists in config-studies.yaml | **High** | config-studies.yaml |
| 5 | device_overrides only handles metadata, not plot | Medium | config-studies.yaml |
| 6 | Duplicate theme definitions: theme/plot-theme/ vs config-template.yaml:rcparams | Medium | both sources |
| 7 | Plot-templates/*.yaml duplicates config-template.yaml:plot_labels | Low | both sources |
| 8 | Hardcoded _DEFAULT_* dicts in config.py duplicate YAML values | Acceptable | core/config.py |

### No Broken Links

- Every study in config-studies.yaml maps to an instrument (or empty `{}`)
- Every device type in config-devices.yaml maps to real studies
- Every entry in STUDY_PLOTTERS registry has a corresponding study in config-studies.yaml
- legacy_to_study maps all 11 old technique names to new study names
- Grammar patterns in config-instruments.yaml match the naming conventions in use
