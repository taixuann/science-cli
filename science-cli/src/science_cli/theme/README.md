# Theme System (`src/science_cli/theme/`)

## Architecture

```
theme/
├── __init__.py        ← Public API: MATCHA_COLORS, RICH_STYLES, get_matcha_questionary_style()
├── registry.py        ← Theme/template loading, YAML parsing, rcParams conversion
├── themes/            ← Global style themes
│   ├── default.yaml
│   ├── matcha.yaml
│   ├── tufte.yaml
│   ├── dark.yaml
│   ├── publication-acs.yaml
│   ├── publication-nature.yaml
│   └── poster.yaml
└── templates/         ← Per-technique plot defaults
    ├── iv-sweep.yaml
    ├── ec-cv.yaml
    ├── ec-ca.yaml
    ├── ec-eis.yaml
    └── ...
```

## Three-Tier System

| Tier | Purpose | Location | Controls |
|------|---------|----------|----------|
| **Theme** | Global visual style | `themes/*.yaml` | Colors, fonts, figure size, DPI, grid, spines |
| **Template** | Per-technique defaults | `templates/*.yaml` | Linewidth, marker, axis labels, scale |
| **Plot Presets** | Per-extension config | Extension `__init__.py` | Plot type, custom labels, extension-specific |

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
  family: sans-serif         # or serif, monospace
  size: 7                   # Base point size
  axes_labelsize: 8

colors:
  prop_cycle:                # Matplotlib color cycle
    - "#0072B2"
    - "#009E73"
    - "#D55E00"

savefig:
  dpi: 600                  # Output DPI (always higher)
  bbox: tight
  format: pdf                # ALWAYS PDF for publication
```

## How to Add a Theme

1. Copy an existing theme from `themes/` as a template
2. Adjust colors, fonts, figsize, DPI
3. Save as `themes/<name>.yaml`
4. The theme is auto-discovered by `list_themes()` — no code changes needed

## How to Add a Template

1. Create `templates/<technique>.yaml` using the technique key as filename
2. Define per-technique defaults:

```yaml
plot_type: line              # line, scatter, semilogy, loglog
linewidth: 1.5
marker: ""                   # or "o", "s", "^"
markersize: 4
alpha: 1.0
xlabel: "Voltage (V)"
ylabel: "Current (A)"
xscale: linear
yscale: linear               # or log
```

3. The template is auto-loaded by technique name — no code changes needed

## Matcha Green Palette

Used throughout the REPL for a consistent green aesthetic:

| Color | Hex | Usage |
|-------|-----|-------|
| Primary | `#8BAA89` | Headers, prompt text |
| Dark | `#6B8A6B` | Protocol names, selected text |
| Light | `#C5D6C5` | Backgrounds, highlights |
| Accent | `#4A7A4A` | Borders, separators |
| Dim | `#A0BBA0` | Subtle text, hints |

## Key API

```python
from science_cli.theme import (
    list_themes,        # → list[str] — all available theme names
    get_theme,          # → dict — theme YAML as dict
    apply_theme,        # → None — applies to matplotlib rcParams + Rich
    theme_to_rcparams,  # → dict — matplotlib rcParams dict
    template_to_flags,  # → dict — template values as plot flags
    MATCHA_COLORS,      # → dict — matcha green hex values
    get_matcha_questionary_style,  # → prompt_toolkit Style
)
```

## Theme Previews

Generate preview images for all themes:

```bash
python scripts/generate-theme-previews.py
```

Output goes to `theme-previews/{theme}/{plot}.pdf` — excluded from version control.
