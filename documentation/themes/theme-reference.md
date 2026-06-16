---
title: Theme System Reference
description: Complete reference for science-cli's 7 built-in Matplotlib themes — RC parameters, plot templates, customization, and per-technique overrides.
date: 2026-06-15
tags: [theme, plot, matplotlib, rcparams]
---

# Theme System Reference

science-cli has a three-tier plot styling system inspired by LabPlot:

1. **Theme** (global) — Colors, fonts, grid, axis style applied to all plots
2. **Template** (per-object) — Per-technique curve/plot presets (linewidth, markers)
3. **PlotTemplate** (full figure) — Complete figure blueprints

This document covers all three tiers.

## Built-In Themes

Seven themes ship with science-cli, stored as YAML files in `src/science_cli/theme/plot-theme/`:

| Theme | File | Best Use |
|-------|------|----------|
| `default` | `default.yaml` | Quick previews, exploration |
| `dark` | `dark.yaml` | Presentations, screen viewing, posters |
| `tufte` | `tufte.yaml` | Minimal ink, maximum data (Edward Tufte style) |
| `publication-acs` | `publication-acs.yaml` | ACS journal submissions |
| `publication-nature` | `publication-nature.yaml` | Nature journal submissions (default) |
| `poster` | `poster.yaml` | Conference posters, large displays |
| `acs-annotated` | `acs-annotated.yaml` | ACS style with annotation-friendly layout |

### Default Theme

The `publication-nature` theme is the **global default** (set in `~/.config/science-cli/config.yaml`):

- Helvetica 5-7pt fonts
- 88mm single-column figsize (3.46×2.75 inches)
- 300 DPI display / 600 DPI save
- Minimal ink: open axes (top/right spines off)
- `pdf.fonttype=42` for editable text in vector output
- Wong colorblind-friendly palette (black-first)

### Theme Comparison

| Parameter | `default` | `dark` | `tufte` | `pub-acs` | `pub-nature` | `poster` | `acs-annotated` |
|-----------|-----------|--------|---------|-----------|-------------|----------|-----------------|
| **figsize** | 6.4×4.8 | 6.4×4.8 | 6.4×4.8 | 3.35×2.6 | 3.46×2.75 | 12.0×8.0 | 4.0×3.2 |
| **figure.dpi** | 100 | 100 | 100 | 300 | 300 | 100 | 300 |
| **savefig.dpi** | 300 | 300 | 300 | 600 | 600 | 150 | 600 |
| **font.family** | sans-serif | sans-serif | serif | sans-serif | Helvetica | sans-serif | sans-serif |
| **font.size** | 10 | 10 | 9 | 8 | 7 | 18 | 8 |
| **axes.labelsize** | 12 | 12 | 11 | 9 | 7 | 24 | 10 |
| **axes.edgecolor** | black | #e0e0e0 | #555555 | black | black | black | black |
| **axes.spines.top** | true | false | false | true | false | false | true |
| **axes.spines.right** | true | false | false | true | false | false | true |
| **lines.linewidth** | 1.5 | 2.0 | 1.0 | 1.0 | 0.75 | 3.0 | 1.2 |
| **lines.markersize** | 6 | 6 | 4 | 4 | 3 | 10 | 5 |
| **ticks.direction** | in | in | out | in | in | in | in |
| **legend.frameon** | true | true | false | false | false | true | false |
| **savefig.format** | pdf | pdf | pdf | pdf | pdf | pdf | pdf |

### Theme RC Parameters

The `theme_to_rcparams()` function in `src/science_cli/theme/registry.py` converts each theme YAML to Matplotlib `rcParams`. Theme YAML sections map to rcParams as follows:

#### `figure:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `facecolor` | `figure.facecolor` | `white` | Figure background color |
| `figsize` | `figure.figsize` | `[6.4, 4.8]` | Figure dimensions in inches |
| `dpi` | `figure.dpi` | `100` | Display DPI |

#### `axes:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `facecolor` | `axes.facecolor` | `white` | Axes background |
| `edgecolor` | `axes.edgecolor` | `black` | Spine color |
| `labelcolor` | `axes.labelcolor` | `black` | Label text color |
| `titlecolor` | `axes.titlecolor` | `black` | Title text color |
| `grid` | `axes.grid` | `False` | Grid visibility |
| `linewidth` | `axes.linewidth` | `1.0` | Spine linewidth |
| `spines_top` | `axes.spines.top` | `True` | Top spine visibility |
| `spines_right` | `axes.spines.right` | `True` | Right spine visibility |

#### `grid:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `color` | `grid.color` | `#e0e0e0` | Grid line color |
| `alpha` | `grid.alpha` | `0.3` | Grid line opacity |
| `linestyle` | `grid.linestyle` | `-` | Grid line style |

#### `ticks:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `color` | `xtick.color`, `ytick.color` | `black` | Tick color |
| `direction` | `xtick.direction`, `ytick.direction` | `in` | Tick direction |
| `major_width` | `xtick.major.width`, `ytick.major.width` | `0.8` | Major tick width |

#### `font:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `family` | `font.family` | `sans-serif` | Font family |
| `size` | `font.size` | `10` | Base font size |
| `axes_labelsize` | `axes.labelsize` | `12` | Axis label size |
| `axes_titlesize` | `axes.titlesize` | `14` | Axis title size |
| `tick_labelsize` | `xtick.labelsize`, `ytick.labelsize` | `10` | Tick label size |
| `legend_size` | `legend.fontsize` | `10` | Legend font size |

#### `legend:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `frameon` | `legend.frameon` | `True` | Legend frame visibility |
| `fancybox` | `legend.fancybox` | `True` | Rounded legend corners |
| `loc` | `legend.loc` | `best` | Legend location |

#### `lines:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `linewidth` | `lines.linewidth` | `1.5` | Default line width |
| `markersize` | `lines.markersize` | `6` | Default marker size |
| `linestyle` | `lines.linestyle` | `-` | Default line style |

#### `colors:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `prop_cycle` | `axes.prop_cycle` | 8-color default | Color cycle (list of hex colors) |

#### `savefig:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `dpi` | `savefig.dpi` | `300` | Save figure DPI |
| `bbox` | `savefig.bbox` | `tight` | Bounding box mode |
| `pad_inches` | `savefig.pad_inches` | `0.1` | Padding around figure |
| `format` | `savefig.format` | `pdf` | Default output format |

#### `pdf:` Section

| YAML Key | rcParams Key | Default | Description |
|----------|-------------|---------|-------------|
| `fonttype` | `pdf.fonttype` | (none) | PDF font embedding type (42 = editable text) |

## Setting the Theme

```bash
# List available themes
sci config theme list

# Set global default theme
sci config set theme publication-nature

# Override via config file
sci config edit --global   # Set theme: poster
```

The theme is applied via `mpl.rcParams.update(rc)` before each plot.

## Plot Templates (Per-Technique overrides)

YAML templates in `src/science_cli/theme/plot-templates/` provide per-technique visual overrides that are applied on top of the global theme:

| File | Technique |
|------|-----------|
| `iv-sweep.yaml` | IV sweep plots |
| `iv-breakdown.yaml` | IV breakdown plots |
| `iv-leakage.yaml` | IV leakage plots |
| `mem-endurance.yaml` | Endurance cycling plots |
| `mem-retention.yaml` | Retention decay plots |
| `mem-switching.yaml` | Switching plots |
| `raman.yaml` | Raman spectroscopy plots |
| `uv-vis.yaml` | UV-Vis plots |
| `ec-cv.yaml` | CV plots |
| `ec-ca.yaml` | CA transient plots |
| `ec-eis.yaml` | EIS Nyquist/Bode plots |

### Template Format

```yaml
# theme/plot-templates/iv-sweep.yaml
plot_type: semilogy           # Default plot type
defaults:
  linewidth: 1.5
  linestyle: "-"
  marker: ""
  markersize: 0
axes:
  xlabel: "Voltage (V)"
  ylabel: "Current (A)"
```

Fields:

| Key | Description |
|-----|-------------|
| `plot_type` | Default plot type (`linear`, `semilogy`, `semilogx`, `loglog`) |
| `defaults.linewidth` | Line width for this technique |
| `defaults.linestyle` | Line style (`-`, `--`, `-.`, `:` `''`) |
| `defaults.marker` | Marker style (e.g., `o`, `s`, `^`, `D`, `''` for none) |
| `defaults.markersize` | Marker size |
| `axes.xlabel` | Default x-axis label |
| `axes.ylabel` | Default y-axis label |

The `template_to_flags()` function in `registry.py` loads these and returns a dict of matplotlib-compatible flags that are applied before plotting.

## Custom Theme Creation

To create a custom theme:

1. **Copy an existing theme YAML** as a starting point:
   ```bash
   cp src/science_cli/theme/plot-theme/publication-nature.yaml \
      ~/.config/science-cli/theme/my-theme.yaml
   ```

2. **Edit the RC parameters** to match your needs.

3. **Set the theme**:
   ```bash
   sci config set theme my-theme
   ```

Custom themes in `~/.config/science-cli/theme/` are auto-discovered by `list_themes()` and appear in `sci config list themes`.

## Per-Technique Plot Label Overrides

Custom axis labels can be set per-technique in config:

```yaml
# ~/.config/science-cli/config.yaml
plot:
  labels:
    uv-vis:
      xlabel: "Wavelength (nm)"
      ylabel: "Transmission (%)"
    raman:
      xlabel: "Raman shift (cm⁻¹)"
      ylabel: "Intensity (a.u.)"
```

Resolution chain: CLI flags (`--xlabel/--ylabel`) > config labels > column auto-detection > template defaults.

## See Also

- [Config System Reference](../reference/config-system.md) — Setting themes via `sci config`
- [README.md](../../README.md) — Quick theme command reference
- [Analysis YAML Schema](../schemas/analysis-yaml.md) — Per-technique output schemas
