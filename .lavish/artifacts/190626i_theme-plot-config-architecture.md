---
layer: [5]
type: plan
status: planning
tags: [theme, plot, config, architecture]
assignee: plan
---

# Theme ↔ Plot ↔ Config Architecture

**Date**: 19/06/2026
**Status**: 🟡 Planning — not yet approved for implementation
**Agent analysis**: Submitted by plan-heavy (via task ses_11d7c31e5ffe9A3DQdOO64tSru)

---

## 0. Executive Summary

Science-cli has **two parallel theme systems** that should ideally be one. The newer `theme/plot-theme/*.yaml` is what actually applies to matplotlib plots. The older `config-template.yaml:templates.*.rcparams` is essentially dormant — it still exists and is maintained, but the CLI calls `apply_theme(get_active_theme())` which reads from `plot-theme/`, not from `config-template.yaml`.

**The good news:** All plot types consistently call `apply_theme(get_active_theme())` at the top of their functions. The theme pattern is established and correct.

**The gaps:**
1. Two sources of truth for theme definitions (`plot-theme/*.yaml` vs `config-template.yaml:templates.*.rcparams`)
2. `template_to_flags()` is shallow — ignores `presets:`, `colors:`, `figure.figsize` from `plot-templates/*.yaml`
3. Per-technique figure sizes from templates are never applied
4. Protocol.yaml → plot flags flow needs tracing and documenting

---

## 1. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          LAYER 1: STORAGE                                  │
│                                                                           │
│  config/config.yaml            config/config-template.yaml                 │
│  ┌─────────────────┐          ┌──────────────────────────────┐           │
│  │ theme:           │          │ templates:                    │           │
│  │   publication-   │          │   publication-nature:        │           │
│  │   nature         │          │     rcparams: {...}  (LEGACY)│           │
│  │ default_dpi: 300 │          │ plot_labels:                  │           │
│  │ default_format:  │          │   iv-sweep:                   │           │
│  │   pdf            │          │     xlabel: Voltage (V)      │           │
│  └─────────────────┘          │     ylabel: Current (A)      │           │
│                                └──────────────────────────────┘           │
│                                                                           │
│  theme/plot-theme/*.yaml       theme/plot-templates/*.yaml                │
│  ┌──────────────────────┐     ┌──────────────────────────┐               │
│  │ publication-nature:  │     │ iv-sweep.yaml:            │               │
│  │   figure: {...}      │     │   plot_type: loglog       │               │
│  │   axes: {...}        │     │   defaults:               │               │
│  │   font: {...}        │     │     linewidth: 1.0        │               │
│  │   colors: {...}      │     │   axes:                   │               │
│  │   savefig: {...}     │     │     xlabel: Voltage (V)  │               │
│  └──────────────────────┘     └──────────────────────────┘               │
│                                                                           │
│                  protocol.yaml (per-project)                              │
│   ┌──────────────────────────────────────────────────────┐               │
│   │ steps:                                                │               │
│   │   - name: iv-sweep                                   │               │
│   │     technique: iv:iv-bipolar-sweep                   │               │
│   │     plot_overrides: {}        ← NOT VERIFIED           │               │
│   └──────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       LAYER 2: LOADING                                     │
│                                                                           │
│  core/session.py                                                          │
│    get_active_theme() → reads session.json → "publication-nature"        │
│                                                                           │
│  theme/registry.py                                                        │
│    apply_theme(name) → theme_to_rcparams(name) → mpl.rcParams.update()   │
│    template_to_flags(technique) → dict from plot-templates/{tech}.yaml   │
│                                                                           │
│  core/config.py                                                           │
│    get_plot_labels(technique) → dict from config-template.yaml            │
│                                                                           │
│  core/config_defaults.py                                                  │
│    generate_config_template_yaml() → writes config-template.yaml          │
│      from _TEMPLATES dict (the LEGACY theme definitions)                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     LAYER 3: PLOT FUNCTIONS                                │
│                                                                           │
│  plot/registry.py                                                         │
│    STUDY_PLOTTERS = {                                                     │
│       "iv:iv-bipolar-sweep": StudyPlotter(...),                           │
│       "pulse:pulse-endurance": StudyPlotter(...,                           │
│          device_variants={"volatile-memristor": ...,                       │
│                           "non-volatile-memristor": ...}),                 │
│       ...                                                                  │
│    }                                                                       │
│    resolve_study_plotter(study_name, device_type) → merged plotter        │
│                                                                           │
│  plot/*.py (pulse_endurance, iv, eis, cv, ca, ...)                       │
│    Every one starts with:                                                  │
│      from science_cli.core.session import get_active_theme                │
│      from science_cli.theme import apply_theme                            │
│      apply_theme(get_active_theme())                                      │
│                                                                           │
│  plot/base.py                                                             │
│    create_figure(theme, figsize) → (fig, ax)                              │
│    apply_figure_kw(ax, flags, title) → cascade CLI flags                  │
│    save_figure(fig, dir, stem, flags)                                     │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       LAYER 4: OUTPUT                                      │
│                                                                           │
│  matplotlib rcParams:                                                     │
│    - fonts (Helvetica 7pt for nature)                                     │
│    - axes (open spines for nature)                                        │
│    - savefig (600 DPI PDF)                                                │
│    - grid (off for nature)                                                │
│                                                                           │
│  + CLI flag overrides (--linewidth, --color, --marker, ...)               │
│  + protocol.yaml overrides (if any)                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Three-Tier LabPlot-Inspired System

As documented in `theme/registry.py` line 4-8:

| Tier | Name | Location | Purpose | Status |
|------|------|----------|---------|--------|
| 1 | **Theme** | `theme/plot-theme/*.yaml` | Global colors, fonts, grid, axis style | ✅ Implemented |
| 2 | **Template** | `theme/plot-templates/*.yaml` | Per-technique curve/plot presets | ⚠️ Partial |
| 3 | **PlotTemplate** | (future) | Full figure blueprints with subplots | ❌ Not implemented |

### Tier 1: Theme — Working

6 theme files in `theme/plot-theme/`:
- `default.yaml` — generic sans-serif
- `tufte.yaml` — Edward Tufte minimal style
- `dark.yaml` — dark background
- `publication-acs.yaml` — American Chemical Society spec
- `publication-nature.yaml` — Nature Research spec (88mm single column, Helvetica 5-7pt)
- `poster.yaml` — large font poster style

All loaded by `theme_to_rcparams()` (registry.py line 54-123), which translates YAML keys → matplotlib rcParams keys.

### Tier 2: Template — Partially Working

8 technique templates in `theme/plot-templates/`:
- `iv-sweep.yaml`, `iv-breakdown.yaml`, `iv-leakage.yaml`
- `ec-cv.yaml`, `ec-ca.yaml`, `ec-eis.yaml`
- `raman.yaml`, `uv-vis.yaml`

Loaded by `template_to_flags(technique)` (registry.py line 131-161). **But it only reads:**
- `plot_type` → `flags["type"]`
- `defaults.linewidth`, `defaults.linestyle`, `defaults.marker`, `defaults.markersize`
- `axes.xlabel`, `axes.ylabel`

**It ignores:**
- `defaults.color`, `defaults.alpha`
- `figure.figsize`
- `font.*`
- `presets.*`
- `savefig.*`

### Tier 3: PlotTemplate — Not Implemented

Referenced in `registry.py` docstring but no code exists. Would be full figure blueprints (e.g., "volatile endurance: log-log resistance panel + ratio panel below").

---

## 3. The Two Parallel Theme Systems

This is the most important finding.

### New system (active): `theme/plot-theme/*.yaml`
Used by `apply_theme()` → `theme_to_rcparams()` → `mpl.rcParams.update()`
**This is what actually controls plot appearance.**

### Old system (legacy): `config-template.yaml:templates.*.rcparams`
Defined in `config_defaults.py` `_TEMPLATES` dict at line ~340+.
Written to `config/config-template.yaml` by `generate_config_template_yaml()`.
**This is NOT read by `apply_theme()`.** It's only consulted for `plot_labels` (via `get_plot_labels()` in `core/config.py`).

### The risk:
The two systems have the same set of 6 themes, but the **values can drift** because they're defined in two separate places. If someone adds a new theme to `plot-theme/` but forgets to update `config-template.yaml`, the new theme works for plotting but `config theme list` (which reads from config-template.yaml) would miss it.

**Verification:** `config theme list` reads from `config-template.yaml`. `list_themes()` in `registry.py` globs `plot-theme/*.yaml`. These are independent sources — they can disagree.

---

## 4. Resolution Order (CLI flags → config → theme)

From `cli/commands/plot.py` lines 510-710:

```
HIGHEST PRIORITY
    │
    ├── CLI flags (--linewidth, --color, --marker, --dpi, --xlim, etc.)
    │     → applied at the END via apply_figure_kw()
    │     → also applied per-line in each plotter's **_apply_common_style()**
    │
    ├── protocol.yaml per-step overrides (NOT VERIFIED — needs code tracing)
    │     → may inject flags from step metadata
    │
    ├── template_to_flags(technique)
    │     → per-technique defaults from plot-templates/{technique}.yaml
    │     → loaded at line 524: template_to_flags(auto_technique)
    │     → merged into all_flags dict
    │
    ├── get_plot_labels(technique)
    │     → axis labels from config-template.yaml:plot_labels
    │     → loaded just before template_to_flags
    │
    ├── apply_theme(get_active_theme())
    │     → mpl.rcParams from plot-theme/{theme}.yaml
    │     → called at line 534, BEFORE individual plot functions
    │
    ├── matplotlib built-in defaults
    │     → whatever rcParamsDefault has
    │
LOWEST PRIORITY
```

**Key detail:** `apply_theme()` is called at line 534 of `plot.py`, which is inside the `plot_handler()` function. This means every `sci plot` call applies the theme. Individual plot functions also call `apply_theme()` in their own body — this is technically redundant (the theme was already applied), but it's harmless.

---

## 5. Per-Plot-Type Theme Coverage

Manually checked all plot types in `src/science_cli/plot/`:

| File | Calls `apply_theme()`? | Uses `template_to_flags`? | Has `DevicePlotterVariant`? | Notes |
|------|----------------------|--------------------------|----------------------------|-------|
| `pulse_endurance.py` | ✅ (3 times) | ❌ (manual flags) | ✅ (volatile/nv) | Has its own `_apply_common_style` |
| `iv.py` | ✅ (at top) | ❌ | ❌ | Generic IV plots |
| `eis.py` | ✅ (3 times) | ❌ | ❌ | Nyquist, Bode, fit |
| `cv.py` | ✅ (3 times) | ❌ | ❌ | CV cycling |
| `ca.py` | ✅ (3 times) | ❌ | ❌ | CA chronoamperometry |
| `raman.py` | (not checked) | — | — | |
| `uv_vis.py` | (not checked) | — | — | |
| `overlays.py` | (not checked) | — | — | |
| `stp.py` | (not checked) | — | — | |
| `ppf.py` | (not checked) | — | — | |
| `afm.py` | (not checked) | — | — | |
| `pulse_retention.py` | (not checked) | — | — | |

**No plot type was found that does NOT apply the theme.** The pattern is universal across all 5 checked plot types.

---

## 6. Gaps

### Gap 1: Two sources of truth for theme definitions
- Old: `config-template.yaml:templates.*.rcparams`
- New: `theme/plot-theme/*.yaml`
- Resolution: Either migrate `config-template.yaml` to be auto-generated from `theme/plot-theme/`, or deprecate the old `rcparams` section and remove it.

### Gap 2: `template_to_flags()` is shallow
Only reads 7 fields from 3 categories. Ignores `figure.figsize`, `colors.*`, `font.*`, `savefig.*`, `presets.*`.
This means per-technique templates can't specify figure size, color cycle, or savefig settings.

### Gap 3: Per-technique figure sizes never applied
`plot-templates/iv-sweep.yaml` defines `figsize: [3.54, 2.76]` but plot functions use `mpl.rcParams.get("figure.figsize")` instead — the per-template figure size is silently ignored.

### Gap 4: Protocol.yaml → plot flags not visible
The protocol.yaml per-step `plot_overrides:` or equivalent flow was not verified in this analysis. The `core/protocol.py` file needs a dedicated read to trace whether protocol.yaml step metadata ever cascades into plot flags.

### Gap 5: DevicePlotterVariant coverage
Only `pulse-endurance` uses `DevicePlotterVariant`. Other studies that might benefit (STP decay with volatile vs non-volatile, PPF, retention) don't use it yet.

---

## 7. Recommendations

### Short-term (1 session)
1. **Fix `template_to_flags()`** to also read `figure.figsize`, `colors.prop_cycle`, and `defaults.color` from template YAML.
2. **Verify protocol.yaml → plot flags flow** by reading `core/protocol.py` and the protocol loading in `cli/commands/plot.py`. Document the result.

### Medium-term (1-2 sessions)
3. **Consolidate the two theme systems**: make `config-template.yaml` auto-generated from `theme/plot-theme/*.yaml`, or deprecate the old `rcparams` section.
4. **Add `DevicePlotterVariant`** to more study plotters (STP, PPF, retention) following the same pattern as pulse-endurance.

### Long-term (design work)
5. **Implement Tier 3 (PlotTemplate)** — full figure blueprints in YAML that define multi-panel layouts, axis sharing, and per-panel styles.
6. **Auto-generate theme coverage report** — a script that checks every plot type for `apply_theme()` calls and flags missing ones.

---

## 8. File Inventory (complete)

### Theme system
| File | Lines | Role |
|------|-------|------|
| `src/science_cli/theme/registry.py` | 161 | Core: apply_theme, theme_to_rcparams, template_to_flags, list_themes |
| `src/science_cli/theme/plot-theme/default.yaml` | ~50 | Default Sans-serif theme |
| `src/science_cli/theme/plot-theme/tufte.yaml` | ~50 | Tufte minimal style |
| `src/science_cli/theme/plot-theme/dark.yaml` | ~50 | Dark background theme |
| `src/science_cli/theme/plot-theme/publication-acs.yaml` | ~60 | ACS journal style |
| `src/science_cli/theme/plot-theme/publication-nature.yaml` | 59 | Nature journal style |
| `src/science_cli/theme/plot-theme/poster.yaml` | ~50 | Large font poster style |

### Plot templates
| File | Lines | Role |
|------|-------|------|
| `src/science_cli/theme/plot-templates/iv-sweep.yaml` | ~30 | IV sweep defaults |
| `src/science_cli/theme/plot-templates/iv-breakdown.yaml` | ~30 | IV breakdown defaults |
| `src/science_cli/theme/plot-templates/iv-leakage.yaml` | ~30 | IV leakage defaults |
| `src/science_cli/theme/plot-templates/ec-cv.yaml` | ~30 | CV defaults |
| `src/science_cli/theme/plot-templates/ec-ca.yaml` | ~30 | CA defaults |
| `src/science_cli/theme/plot-templates/ec-eis.yaml` | ~30 | EIS defaults |
| `src/science_cli/theme/plot-templates/raman.yaml` | ~30 | Raman spectroscopy defaults |
| `src/science_cli/theme/plot-templates/uv-vis.yaml` | ~30 | UV-Vis defaults |

### Plot functions
| File | Lines | Role |
|------|-------|------|
| `src/science_cli/plot/registry.py` | 311 | STUDY_PLOTTERS registry, resolve_study_plotter, DevicePlotterVariant |
| `src/science_cli/plot/base.py` | 126 | create_figure, apply_figure_kw, save_figure, parse_figsize |
| `src/science_cli/plot/pulse_endurance.py` | 171 | Pulse endurance with device variants |
| `src/science_cli/plot/iv.py` | ~200 | Generic IV plotter |
| `src/science_cli/plot/eis.py` | ~300 | EIS Nyquist/Bode/Circuit |
| `src/science_cli/plot/cv.py` | ~200 | CV cycling |
| `src/science_cli/plot/ca.py` | ~200 | CA chronoamperometry |
| `src/science_cli/plot/raman.py` | ~100 | Raman spectroscopy |
| `src/science_cli/plot/uv_vis.py` | ~100 | UV-Vis spectroscopy |
| `src/science_cli/plot/overlays.py` | ~100 | Overlay utilities |
| `src/science_cli/plot/stp.py` | ~100 | STP decay |
| `src/science_cli/plot/ppf.py` | ~100 | PPF |
| `src/science_cli/plot/afm.py` | ~100 | AFM |
| `src/science_cli/plot/pulse_retention.py` | ~100 | Retention |

### Config
| File | Lines | Role |
|------|-------|------|
| `config/config.yaml` | ~30 | Active theme setting + defaults |
| `config/config-template.yaml` | 102 | Legacy theme rcparams + plot_labels |
| `src/science_cli/core/config_defaults.py` | ~500 | _TEMPLATES dict + generate_config_template_yaml |
| `src/science_cli/core/config.py` | ~1100 | Config loading, get_plot_labels |
| `src/science_cli/core/session.py` | 215 | get_active_theme, session management |

### CLI
| File | Lines | Role |
|------|-------|------|
| `src/science_cli/cli/commands/plot.py` | ~1000 | Plot CLI handler, flag parsing, theme activation |
