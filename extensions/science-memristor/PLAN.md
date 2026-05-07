# Plan: Refine `memristor plot` and `memristor dashboard` — ACS style, matrix layout, T/B notation

## Objective

Apply user-requested refinements to IV curve plotting and dashboard layout:
1. Dashboard: all material matrices in a single horizontal row at page top
2. ACS publication style for plots (sans-serif, no grid, inward ticks, black lines)
3. T/B 1-indexed notation in titles
4. Two sweep type visual styles (uc vs f) with segment-aware coloring
5. Sweep direction annotation box

## Specification

### 1. Dashboard: matrices in one row at top

Current behavior: each `<section>` has matrix + plots stacked vertically.
New behavior:
- ALL material matrix grids rendered at page top in a single `<div class="matrix-row">` with `display: flex; flex-wrap: nowrap; overflow-x: auto;`
- Each matrix gets `flex: 1; min-width: 200px; max-width: 300px;`
- Below the matrix row, material sections contain only collapsible plot galleries (no matrix repetition)
- Matrix cells still clickable — anchor links point down to the plot galleries

Implementation:
- New `_build_matrices_row()` function: iterates material_groups, calls `_build_matrix_table()` for each, wraps in flex container
- Modify `_build_html()`: emit `matrices_row_html` before `sections_html`
- Modify `_build_material_section()`: remove `{matrix_html}` from output (matrix lives in the top row now)
- CSS: add `.matrix-row` styles

### 2. ACS publication style for `generate_iv_svg()`

ACS (American Chemical Society) style requirements:
- **NO grid lines**: remove `ax.grid(True, ...)`
- **Tick marks inward**: `ax.tick_params(direction='in', which='both')`
- **Sans-serif font**: set matplotlib rcParams
  ```python
  plt.rcParams.update({
      'font.family': 'sans-serif',
      'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
      'mathtext.fontset': 'dejavusans',
      'axes.linewidth': 1.0,
      'xtick.major.width': 0.8,
      'ytick.major.width': 0.8,
      'xtick.major.size': 4,
      'ytick.major.size': 4,
      'xtick.direction': 'in',
      'ytick.direction': 'in',
  })
  ```
- **All four spines visible**: top and right visible with thin lines
  ```python
  ax.spines['top'].set_visible(True)
  ax.spines['right'].set_visible(True)
  ax.spines['top'].set_linewidth(0.8)
  ax.spines['right'].set_linewidth(0.8)
  ```
- **Line color**: black (`'k-'`), not blue (`'b-'`)
- **Line width**: 0.8 (was 1.0)
- **Font sizes**: axis labels 10pt, tick labels 8pt, title 11pt bold
- **Legend**: no box/outline: `legend(frameon=False)`
- **Tick width**: 0.8

rcParams update should happen once at module level (or inside the function) to avoid global state pollution — safest to set inside `generate_iv_svg()` with a context manager, or just update the relevant Axes properties directly.

### 3. Plot title: T/B 1-indexed notation

Current: `r0c0 — Ta-PDAc-ITO(1) — f`
New: `T1-B1  |  Ta-PDAc-ITO(1)  |  f`

- `build_plot_title()`: change format from `r{row}c{col}` to `T{row+1}-B{col+1}`
- Separator changed from `—` to `|`
- Filename unchanged (`r{row}c{col}` stays for compatibility)

### 4. Two sweep type visual styles

**Type "uc" (uncategorized, single-direction)**:
- Simple black line plot (`'k-'`, linewidth=0.8)
- Title shows `uc` suffix

**Type "f" (full bipolar, 0-centered)**:
- Attempt to split data into forward/reverse segments at voltage reversal points
- Forward segments: black solid line (`'k-'`, linewidth=0.8)
- Reverse segments: dark gray solid line (e.g., `'#888888'`, linewidth=0.8)
- If splitting fails (only 1 segment detected): plot as single black line
- Title shows `f` suffix
- Annotation shows full sweep path: `0→+Vmax→0→-Vmax→0`

**Splitting algorithm for "f"**:
- Find voltage reversal points by detecting sign changes in voltage derivative (`np.diff(np.sign(np.diff(voltage)))`)
- Split data at reversal indices
- Alternate colors: even-indexed segments (0,2,4,...) = forward = black, odd-indexed segments (1,3,5,...) = reverse = gray

**Other types** (`sp`, `sn`): treat same as "uc" — single black line.

### 5. Sweep direction annotation

The annotation box (upper right) should show:
- Sweep rate: e.g., `±0.10 V/s` (from `sweep[0].sweep_rate_v_s`)
- Direction: human-readable sweep path, e.g., `0→+2V→0→-2V→0`

For "uc" sweeps: direction could be `0→+2V` or `0→-2V`
For "f" sweeps: build path from all sweep segments' direction + voltage_range

Updated `_extract_sweep_annotations()`:
- Build a readable direction string from ALL segments (not just `sweep[0]`)
- Format: `0→+{Vmax}V→0→-{Vmax}V→0` for bipolar, `0→+{Vrange}V` for unipolar
- Remove `Type: {sweep_type}` from annotation (it's in the title now)

### 6. File number in legend

Current: legend shows `I` or `|I|`.
New: legend shows `#01` or `#{order}` to identify the file sequence number.

Add `order` to metadata passed to `generate_iv_svg()` and use it in the legend label.

## Critical Analysis

- **Predicted output**: Clean, publication-ready ACS-style IV plots with T/B notation. Dashboard with compact top-row matrix strip.
- **Consequences**: 
  - Existing SVGs will look different if regenerated with `--overwrite`
  - Dashboard HTML structure changes — matrix no longer inside collapsible sections
  - No breaking changes to `devices.yaml` or file naming
- **Risks**: 
  - rcParams change is global — could affect other matplotlib users in the same interpreter. Mitigation: set inside function, restore after, or use `with plt.rc_context():`
  - Splitting data at reversal points may fail for noisy data. Mitigation: fall back gracefully to single-color plot
  - Dashboard anchor links must still work when matrix is at top
- **Skepticism**: The "f" sweep splitting is speculative — if the data doesn't have clear reversal points, the fallback is same as "uc" style. The visual difference may be subtle. Worth testing with real data.

## Approach

1. **`plotting.py`**: 
   - Refactor `generate_iv_svg()` with ACS styling, segment splitting, T/B title
   - Update `build_plot_title()` for T/B notation
   - Enhance `_extract_sweep_annotations()` for multi-segment direction strings
   - Add helper `_split_at_reversals()` for segment detection

2. **`dashboard.py`**:
   - Add `_build_matrices_row()` function
   - Modify `_build_html()` to emit matrix row first
   - Simplify `_build_material_section()` — remove matrix, keep plot gallery only
   - Add CSS for `.matrix-row` flex container

## Files to Modify

- `/Users/tai/workspace/tools/extensions/science-memristor/src/science_memristor/plotting.py`
  - `build_plot_title()` — change format to T/B notation
  - `generate_iv_svg()` — ACS style, segment splitting, new annotation format
  - `_extract_sweep_annotations()` — multi-segment direction string
  - New: `_split_at_reversals()` — voltage reversal detection

- `/Users/tai/workspace/tools/extensions/science-memristor/src/science_memristor/dashboard.py`
  - `_build_html()` — emit matrix row before sections
  - `_build_material_section()` — remove matrix, keep only plot gallery
  - New: `_build_matrices_row()` — flex row of all material matrices
  - `css()` — add `.matrix-row` styles

- `/Users/tai/workspace/tools/extensions/science-memristor/README.md` — update plot style docs

## Dependencies

None. All changes use existing matplotlib APIs.

## Test Strategy

1. Run existing tests: `pytest tests/`
2. Manual test: regenerate some plots with `memristor plot --all --overwrite` and verify:
   - SVG outputs look correct (ACS style, T/B title, proper colors)
   - Dashboard opens with matrices in top row
3. Verify dashboard anchor links still navigate correctly

## Progress

- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
  - `plotting.py`: ACS style, segment splitting, T/B title, multi-segment annotations
  - `dashboard.py`: matrix row at top, position-grouped galleries, flex layout
  - `device_cli.py`: updated `build_plot_title()` call site and metadata dict
  - `test_device.py`: updated `TestBuildPlotTitle` tests for new signature
- [x] TEST passed (101/101)
  - Verified: title formatting, direction paths, reversal splitting, dashboard HTML generation
- [x] DOCS updated
  - `README.md`: updated plot style section (ACS, title format, sweep types) and dashboard layout (matrix row, position groups)
- [ ] COMMIT done
