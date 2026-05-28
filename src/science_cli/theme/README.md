# Theme System (`src/science_cli/theme/`)

## Architecture

```
theme/
├── __init__.py           ← Public API: MATCHA_COLORS, RICH_STYLES
├── registry.py           ← Theme/template loading, YAML parsing, rcParams conversion
├── plot-theme/           ← Global visual style themes (publication-nature is default)
│   ├── default.yaml
│   ├── tufte.yaml
│   ├── dark.yaml
│   ├── publication-acs.yaml
│   ├── publication-nature.yaml
│   └── poster.yaml
└── plot-templates/       ← Per-technique plot presets (override global theme)
    ├── iv-sweep.yaml
    ├── iv-breakdown.yaml
    ├── iv-leakage.yaml
    ├── ec-cv.yaml
    ├── ec-ca.yaml
    ├── ec-eis.yaml
    ├── mem-switching.yaml
    ├── mem-endurance.yaml
    ├── mem-retention.yaml
    ├── raman.yaml
    └── uv-vis.yaml
```

## Three-Tier System

| Tier | Purpose | Location | Controls |
|------|---------|----------|----------|
| **Plot Theme** | Global visual style | `plot-theme/*.yaml` | Colors, fonts, figure size, DPI, grid, spines |
| **Plot Template** | Per-technique defaults | `plot-templates/*.yaml` | Linewidth, marker, axis labels, scale, aspect |
| **Plot Presets** | Per-extension config | Extension `__init__.py` | Plot type, custom labels, extension-specific |

The **plot theme** sets the base style (e.g., publication-nature). The **plot template** applies technique-specific overrides on top — e.g., EIS Nyquist forces `aspect: equal` while keeping the Nature font/color palette.

## Theme YAML Schema

```yaml
figure:
  facecolor: white          # Figure background
  figsize: [3.46, 2.75]     # Width, height in inches
  dpi: 300                  # Screen DPI

axes:
  edgecolor: black
  facecolor: white
  grid: false
  spines_top: false          # Nature: hide top/right
  spines_right: false

font:
  family: Helvetica          # or Arial, sans-serif
  size: 7                    # Base point size
  axes_labelsize: 7

colors:
  prop_cycle:                # Matplotlib color cycle (Wong palette)
    - "#000000"
    - "#0072B2"

savefig:
  dpi: 600                   # Output DPI (always higher)
  bbox: tight
  format: pdf                # ALWAYS PDF for publication

pdf:
  fonttype: 42               # Editable text (Nature requirement)
```

## How to Add a Plot Theme

1. Copy an existing theme from `plot-theme/` as a template
2. Adjust colors, fonts, figsize, DPI
3. Save as `plot-theme/<name>.yaml`
4. The theme is auto-discovered by `list_themes()` — no code changes needed

## How to Add a Plot Template

1. Create `plot-templates/<technique>.yaml` using the technique key as filename
2. Define per-technique defaults that override the global theme:

```yaml
plot_type: line              # line, scatter, semilogy, loglog
defaults:
  linewidth: 0.75
  marker: ""
  markersize: 3
labels:
  xlabel: "Voltage (V)"
  ylabel: "Current (A)"
```

3. The template is auto-loaded by technique name — no code changes needed

## Key API

```python
from science_cli.theme import (
    list_themes,        # → list[str] — all available theme names
    get_theme,          # → dict — theme YAML as dict
    apply_theme,        # → None — applies to matplotlib rcParams
    theme_to_rcparams,  # → dict — matplotlib rcParams dict
    template_to_flags,  # → dict — technique-specific plot flags
    MATCHA_COLORS,      # → dict — matcha green hex values
)
```
