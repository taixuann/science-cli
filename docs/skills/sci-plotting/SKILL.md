---
name: sci-plotting
description: "Plotting-specific operational knowledge for science-cli v3.11.0 — technique dispatch, TECHNIQUE_PLOTTERS registry, technique-specific flags, generic style flags, EIS special plotting, overlay mode, output format detection, and interactive fzf plotting. Load when constructing `sci plot` commands or troubleshooting plot output."
version: 3.11.0
author: science-cli team
ontology: [skill, science-cli, plotting, visualization, matplotlib, eis, raman, afm]
workspace: tools/science-cli
load: on_request
---

# sci-plotting — science-cli Plotting Skill

## 1. Entry Point

The `sci plot` command is the primary visualization interface. It supports **four modes**:

```
sci plot                           Interactive: fzf file selection → style/figure prompts → save
sci plot --overlay                 Interactive with --overlay preset (skip prompt)
sci plot --all                     Interactive with --all preset (individual per file)
sci plot <file>                    Direct: plot file(s) with auto-detected technique
sci plot --technique <type> <file> Direct: explicit technique + technique-specific flags
sci plot results                   List all saved figures in current project
sci plot open <name>               Open a saved figure with system viewer
sci plot delete <name>             Delete a saved figure (with confirmation)
```

### Mode Selection for AI Agents

| Scenario | Command |
|----------|---------|
| Interactive file selection needed | `sci plot` |
| Batch-plot all files individually | `sci plot --all` |
| Overlay multiple files into one figure | `sci plot --overlay` |
| Plot a single known file | `sci plot <path>` |
| Plot with explicit technique + flags | `sci plot --technique raman file.txt --laser 532` |
| List saved figures | `sci plot results` |
| Open a saved figure | `sci plot open <name>` |
| Delete a saved figure | `sci plot delete <name>` |

---

## 2. TECHNIQUE_PLOTTERS Registry — 13 Entries

The `TECHNIQUE_PLOTTERS` dict in `plot.py:19-33` maps technique slugs to handler functions:

| # | Technique Slug | Handler | Description |
|---|---------------|---------|-------------|
| 1 | `iv-sweep` | `_do_plot` (generic) | Voltage vs current line/scatter |
| 2 | `iv-breakdown` | `_do_plot` (generic) | Breakdown IV curve |
| 3 | `iv-leakage` | `_do_plot` (generic) | Leakage current IV curve |
| 4 | `pulse-endurance` | `_do_plot` (generic) | Resistance vs cycle |
| 5 | `pulse-retention` | `_do_plot` (generic) | Resistance vs time |
| 6 | `pulse-stp` | `_do_plot` (generic) | STP decay |
| 7 | `pulse-ppf` | `_do_plot` (generic) | Paired-pulse facilitation |
| 8 | `ec-cv` | `_do_plot` (generic) | Cyclic voltammogram |
| 9 | `ec-ca` | `_do_plot` (generic) | Chronoamperometry |
| 10 | `ec-eis` | `_do_eis_plot` (special) | Nyquist + Bode + circuit fit + KK |
| 11 | `uv-vis` | `_do_plot` (generic) | Transmission/absorbance spectrum |
| 12 | `raman` | `_wrap_raman_plot` (special) | Raman spectrum via RamanSPy |
| 13 | `afm-gwy` | `_wrap_afm_plot` (special) | AFM topography via AFMReader |

**Routing logic** (`_dispatch_technique_plot`, `plot.py:99-109`):
- `raman` → `_wrap_raman_plot()` → delegates to `raman._do_single_raman_plot()`
- `afm-gwy` / `afm` → `_wrap_afm_plot()` → delegates to `afm._do_afm_plot()`
- `ec-eis` → `_do_eis_plot()` → multi-output Nyquist + Bode + fit + KK
- All others → `_do_plot()` → generic matplotlib line/scatter

---

## 3. Technique-Specific Flags

Defined in `TECHNIQUE_FLAGS` (`plot.py:35-56`). Only usable with `--technique <type>`.

### Raman (`--technique raman`)

| Flag | Type | Description | Example Values |
|------|------|-------------|----------------|
| `--laser` | int | Laser wavelength (nm) | `532`, `633`, `785` |
| `--accumulation` | int | Number of accumulations | `3`, `5`, `10` |
| `--acq-time` | float | Acquisition time (s) | `1.0`, `5.0`, `30.0` |
| `--nd-filter` | int | ND filter value (0-4) | `0`, `1`, `2` |

### EC-CV (`--technique ec-cv`)

| Flag | Type | Description | Example |
|------|------|-------------|---------|
| `--scan-rate` | float | Scan rate (mV/s) for labeling | `50`, `100` |
| `--cycles` | int | Number of cycles for multi-cycle CV | `3` |

### EC-EIS (`--technique ec-eis`)

| Flag | Type | Description | Example |
|------|------|-------------|---------|
| `--freq-range` | str | Frequency range filter | `"1Hz-1MHz"` |
| `--nyquist` | flag | Generate Nyquist plot (default: True) | `--nyquist` |
| `--bode` | flag | Generate Bode plot (default: True) | `--bode` |
| `--circuit` | str | Circuit model for fit overlay | `RQR`, `RRC` |
| `--kk` | flag | Kramers-Kronig validation test | `--kk` |

### UV-Vis (`--technique uv-vis`)

| Flag | Type | Description | Example |
|------|------|-------------|---------|
| `--wavelength-range` | str | Wavelength range filter (nm) | `"300-800"` |

### AFM (`--technique afm`)

| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--cross-section` | flag | Show cross-sectional line profile | `False` |
| `--colormap` | str | Matplotlib colormap name | `viridis` |

---

## 4. Generic Style Flags (All Techniques)

### Style

| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--type` | str | Plot type: `line` or `scatter` | `line` |
| `--color` | str | Line/marker color (any mpl color) | theme |
| `--linewidth` | float | Line width in points | theme |
| `--linestyle` | str | `solid`, `dashed`, `dotted`, `dashdot` | theme |
| `--marker` | str | Marker style: `o`, `s`, `^`, `D`, `*` | theme |
| `--markersize` | float | Marker size in points | theme |
| `--cmap` | str | Colormap (scatter plots only) | theme |

### Figure

| Flag | Type | Description |
|------|------|-------------|
| `--title` | str | Plot title |
| `--xlabel` | str | X-axis label (auto-detected from columns if omitted) |
| `--ylabel` | str | Y-axis label (auto-detected from columns if omitted) |
| `--xlim` | str | X-axis limits: `xmin,xmax` |
| `--ylim` | str | Y-axis limits: `ymin,ymax` |
| `--zoom` | str | Zoom: `x1,x2` or `x1,x2,y1,y2` |
| `--size` | str | Figure size: `width,height` (inches) |
| `--dpi` | int | Output DPI (default: 600) |
| `--grid` | flag | Show grid (alpha=0.3) |
| `--legend` | flag | Show legend |

### Output

| Flag | Alias | Type | Description |
|------|-------|------|-------------|
| `--name` | `-n` | str | Output filename. Format from extension: `.pdf`, `.svg`, `.png`. Default: `<technique>_<filestem>.pdf` |

### Overlay-Only

| Flag | Type | Description |
|------|------|-------------|
| `--label-name` | str | Comma-separated legend labels for overlay (e.g., `"Run 1,Run 2"`) |
| `--labels` | str | Alias for `--label-name` |

---

## 5. Output Format Auto-Detection

The output format is determined **entirely from the filename extension** on `--name` / `-n`:

| Extension | Format | Use Case |
|-----------|--------|----------|
| `.pdf` | Vector PDF | Publication, print (default) |
| `.svg` | Vector SVG | Web, vector editing |
| `.png` | Raster PNG | Quick preview, screenshots |

**Default:** If no `--name` is given, the filename is `<technique>_<filestem>.pdf` with DPI from the active theme (default 600).

### Examples

```bash
sci plot --technique raman file.txt --name spectrum.svg       # SVG vector output
sci plot data.csv --name figure.png --dpi 300                 # PNG at 300 DPI
sci plot data.csv                                              # Default PDF at 600 DPI
```

---

## 6. Overlay Mode vs All Mode

### Overlay Mode (`--overlay`, `_do_overlap`)

- Combines **all selected files** into a **single figure** with shared axes
- Each file gets a line; colors come from the **theme color cycle** (`axes.prop_cycle`), not hardcoded
- Use `--label-name "Run1,Run2"` for custom legend labels
- If no labels provided, each line uses its file stem as label
- **Scatter mode not supported** — always uses `ax.plot()` (line)
- Auto-legend added
- Saved as `<technique>_overlay.pdf`

```bash
sci plot --overlay                                          # Interactive: overlay chosen files
sci plot file1.csv file2.csv file3.csv                      # Direct: auto-overlay multi-file
sci plot --overlay --label-name "Sample A,Sample B"         # Overlay with custom labels
sci plot file1.csv file2.csv --overlay --label-name "A,B" --grid --legend
```

### All Mode (`--all`)

- Plots **each selected file individually** as a separate figure
- Equivalent to running `sci plot <file>` for each file
- Useful for batch exporting a directory of data

```bash
sci plot --all         # Interactive: export each file individually
```

### Interactive Choice

When multiple files are selected and neither `--overlay` nor `--all` is specified:
```
Overlay all (o) or individual plots (i)? [o/i]
```
- `o` → overlay (calls `_do_overlap()`)
- `i` → individual (calls `_do_plot()` for each file)

---

## 7. Flag Validation Rules

**`_validate_technique_flags()`** in `plot.py:76-97` enforces two rules:

### Rule 1: Technique Flag Without `--technique`

If any technique-specific flag is used without `--technique <type>`:
```
Flag '--laser' requires --technique <type>. Use 'sci plot --technique <technique> ...'
```

### Rule 2: Wrong Technique Flag

If a flag from technique A is used with `--technique B`:
```
Flag '--laser' is not valid for technique 'ec-cv'. Allowed flags: --scan-rate, --cycles
```

### Allowed Flag Mapping

| `--technique` | Allowed Flags |
|---------------|---------------|
| `raman` | `--laser`, `--accumulation`, `--acq-time`, `--nd-filter` |
| `ec-cv` | `--scan-rate`, `--cycles` |
| `ec-eis` | `--freq-range`, `--nyquist`, `--bode`, `--circuit`, `--kk` |
| `uv-vis` | `--wavelength-range` |
| `afm` | `--cross-section`, `--colormap` |
| All others | Generic style/figure/output flags only |

---

## 8. EIS Special Plotting (`_do_eis_plot`)

`_do_eis_plot()` (`plot.py:881-1033`) is the most specialized plotter. It can generate **up to 4 outputs**:

### Nyquist Plot (always)

```
Z' (Ω) on x-axis vs -Z'' (Ω) on y-axis
```

Column resolution order for Z': `Z' (Ω)`, `Z'`, `Re(Z)`, `ReZ`, `Zre`, `z'`, `z_re`, `z_real`
Column resolution order for -Z'': `-Z'' (Ω)`, `-Z''`, `Z''`, `-Z"`, `Im(Z)`, `ImZ`, `Zim`, `z''`, `z_im`, `z_imag`

Saved as: `ec-eis-nyquist_<filestem>.pdf`

### Bode Plot (if magnitude + phase columns available)

Dual-axis: |Z| (Ω) vs frequency (Hz) and -Phase (°) vs frequency (Hz).

Column resolution: `magnitude`, `Z (Ω)` for |Z|; `phase`, `-Phase (°)`, `Phase (°)` for phase.

Saved as: `ec-eis-bode_<filestem>.pdf`

### Circuit Fit Overlay (with `--circuit` flag)

1. If `--circuit` value is a specific model string (e.g., `RRC`, `RQR`, `RQRW`), fits that circuit
2. If `--circuit` is bare (no model), runs `best_circuit_fit()` with `["R_s(C[RW])", "R_s(Q[RW])"]`
3. Overlays fitted impedance on Nyquist
4. Saves fit results as JSON: `ec-eis-fit-nyquist_<filestem>.json`

### Kramers-Kronig Test (with `--kk` flag)

Runs `kramers_kronig()` validation. Prints pass/fail with consistency score.

### Complete EIS Example

```bash
sci plot --technique ec-eis sample.mpt --circuit RQR --kk
# Generates:
#   ec-eis-nyquist_sample.pdf
#   ec-eis-bode_sample.pdf
#   ec-eis-fit-nyquist_sample.pdf  (with RQR circuit overlay)
#   ec-eis-fit-nyquist_sample.json (fit params)
# Console: KK test result + circuit parameters
```

---

## 9. Column Resolution by Technique

`_resolve_xy_columns()` maps technique-specific column name conventions:

| Technique | X-axis Candidates | Y-axis Candidates |
|-----------|------------------|-------------------|
| `ec-ca` | `Corrected time (s)`, `time`, `Time`, `t/s` | `WE(1).Current (A)`, `Current (A)`, `I`, `I/A` |
| `ec-cv` | `WE(1).Potential (V)`, `Potential (V)`, `E`, `E/V` | `WE(1).Current (A)`, `Current (A)`, `I`, `I/A` |
| `ec-eis` | `Z' (Ω)`, `Z'`, `Re(Z)`, `Zre`, `z_real` | `-Z'' (Ω)`, `-Z''`, `Im(Z)`, `Zim`, `z_imag` |
| `iv-sweep` | `Voltage (V)`, `V`, `BV`, `bias_voltage` | `Current (A)`, `I`, `I/A`, `Bi` |
| `uv-vis` | `wavelength`, `Wavelength nm.`, `nm` | `transmittance`, `T%`, `T` |
| **Fallback** | First numeric column | Second numeric column |

---

## 10. Interactive Mode Flow (`_plot_interactive`)

```
sci plot
    ↓
1. FZF file selector (multi-select via Tab)
   - Columns: protocol | step | filename
   - Preview: first 20 lines via head -n 20
   - Filters to active protocol if one is set
    ↓
2. Auto-detect technique from protocol step metadata (or filename)
    ↓
3. Prompt 1: Style flags (--type, --color, --linewidth, etc.)
   - Empty = use theme defaults
   - Technique-specific hints shown where available
    ↓
4. Prompt 2: Figure flags (--name, --title, --grid, --legend, etc.)
    ↓
5. If multiple files: "Overlay all (o) or individual plots (i)? [o/i]"
    ↓
6. Save to step results/ directory
   - Emit manifest.json
```

---

## 11. Flag Layering in Direct Mode

Three layers, with later layers overriding earlier:

```
Layer 1: template_to_flags(technique)   — Theme template defaults
Layer 2: get_plot_labels(technique)      — Config labels from sci-config.yaml
Layer 3: CLI flags                       — User command line (highest priority)
```

---

## 12. Interactive Mode Hints

The system shows technique-specific hints at each prompt:

```python
_technique_hints = {
    "raman": {
        "style": "--laser 532 | --accumulation 3 | --acq-time 1.0 | --nd-filter 1",
        "figure": "-n spectrum.pdf | --title | --grid",
    },
    "ec-cv": {
        "style": "--scan-rate 50 | --cycles 3",
        "figure": "-n cv.pdf | --title | --grid | --legend",
    },
}
```

---

## 13. Results Directory Resolution

`_get_results_dir()` determines output location:

1. File belongs to a protocol step → `<project>/protocol/<name>/<step>/results/`
2. No protocol matched → `<project>/results/`
3. No project → `<file_parent>/results/`

---

## 14. Common Plotting Patterns for AI Agents

### Single IV sweep with publication styling

```bash
sci config theme set publication-nature
sci plot --technique iv-sweep data.csv --grid --legend --size 5.7,3.5 --dpi 600
```

### Raman spectrum with metadata

```bash
sci plot --technique raman file.txt --laser 532 --accumulation 3 --name spectrum.svg
```

### CV with scan rate annotation

```bash
sci plot --technique ec-cv file.mpt --scan-rate 100 --cycles 3 --grid
```

### EIS full analysis

```bash
sci plot --technique ec-eis sample.mpt --circuit RQR --kk --nyquist --bode
```

### Multi-file overlay with custom labels

```bash
sci plot --overlay --label-name "Device A,Device B,Device C" file1.csv file2.csv file3.csv
```

### High-resolution zoomed scatter

```bash
sci plot --technique iv-sweep data.csv --type scatter --cmap viridis --zoom 0.5,1.5,-1e-6,1e-6 --dpi 1200
```

---

## 15. Constructing `sci plot` Commands for AI Agents

### Template

```bash
sci plot {--technique <technique>} {<files>} {--style-flags} {--figure-flags} {--name output.ext}
```

### Rules
1. For known technique + file, always use `--technique <type>` to unlock technique-specific flags
2. Default DPI is 600 (publication quality)
3. Format is inferred from `--name` extension — no separate `--format` flag
4. Multi-file input always triggers overlay (line plot)
5. Use `--overlay` to force overlay in interactive mode
6. Theme applies automatically from session config — no need to set per-plot
7. Always check `sci info --json` for context before constructing plot commands

### Complete Mode Decision Chart

```
User wants to plot
    ↓
Has specific files?   → Direct mode: sci plot <files>
    ↓ No
Has technique in mind? → sci plot --technique <type>
    ↓ No
Use interactive fzf   → sci plot

Want single figure from multiple files? → Add --overlay
Want individual files from batch?        → Add --all
```
