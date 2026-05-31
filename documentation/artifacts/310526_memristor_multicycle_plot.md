# PLAN: Memristor Multi-Cycle Plotting & Parameter Analysis

## Classification
feature / refactor

## Related Plans
- [[300526_split_overlay_distinct_plots]] — related (modifying plotting layer)

## Status
- **Created**: 2026-05-31
- **Status**: draft
- **Branch**: dev

## Objective
Support multi-cycle memristor IV characterization by providing:
1. Beautiful **Multi-Cycle Highlight Plots**: Users can highlight specific cycles in distinct, bold colors while all other cycles (e.g. out of 600+) are rendered as a light grey background envelope, showing both variability envelope and specific cycle trajectories.
2. Direct **SET/RESET Statistics**: View comprehensive cycle-to-cycle switching characteristics (V_set, V_reset, ON/OFF ratio, and Weibull parameters) directly inside the CLI via the `info` command, populated instantly from the SQLite cache.

## Context
When running memristor endurance/cycling, users can collect hundreds or thousands of cycles (e.g. 667 cycles on cell `r1c4` in protocol `5_cu-c_ta-cu`).
- Currently, generating overlays of 600 files results in a solid, unreadable blob of colors.
- Users want to plot specific cycles (e.g., cycle 1, 10, 50, 100, 200, 500) in color to trace evolution, with other cycles muted in the background.
- Users also want to know the statistics (Mean, Std, Weibull fits) of SET/RESET parameters without manually opening a browser dashboard.

---

## Specification

### 1. Highlighted Multi-Cycle Plotting (`src/science_cli/library/memristor/plotting.py`)
Implement a new plotting function `generate_iv_highlighted_svg(traces, highlight_cycles, output_path, dpi=150)`:
- Accept `traces`, a list of `(voltage, current, metadata)` tuples sorted by cycle order.
- Accept `highlight_cycles`, a list of 1-based cycle indices (e.g. `[1, 5, 10, 50, 100]`).
- Separate traces into:
  - **Highlighted**: Plotted with solid lines, Nature-style distinct colors (using a beautiful colormap like `plasma`/`viridis` or discrete high-contrast theme colors), `linewidth=1.2`, and visible labels in the legend (e.g., `Cycle 1`, `Cycle 10`).
  - **Envelope (Background)**: Plotted with a light semi-transparent grey (`#D3D3D3` or `#E0E0E0`), `alpha=0.15`, `linewidth=0.5`, and `label=None` (omitted from legend to prevent clutter).
- Save to output SVG file.

### 2. Smarter `cmd_info` Switch Statistics (`src/science_cli/library/memristor/device_cli.py`)
Enhance the `cmd_info` CLI handler to print switching parameters directly from SQLite:
- If the point has `iv` data, connect to the project SQLite database.
- Query the `files` table for all rows matching `protocol`, `row`, and `col`.
- If data points are found, extract the non-null lists of `v_set`, `v_reset`, and `on_off_ratio`.
- If statistics are available, print a clean, beautiful block using `Rich Panel` or formatted text:
  - **Total Cycles**: N files.
  - **SET Voltages**: Mean ± Std, Median, Min/Max.
  - **RESET Voltages**: Mean ± Std, Median, Min/Max.
  - **ON/OFF Resistance Ratio**: Geometric mean or Median.
  - **Yield**: Percentage of successful switching cycles (where `compliance_confidence` is high or Vset/Vreset are detected).

### 3. Parse Cycle Ranges CLI Helper (`src/science_cli/library/memristor/device_cli.py`)
Create a helper function `parse_cycles_list(cycle_str: str) -> list[int]` that parses:
- Comma-separated cycle lists: `"1,5,10"` -> `[1, 5, 10]`
- Ranges: `"1-5,10"` -> `[1, 2, 3, 4, 5, 10]`
- Strip spaces and handle invalid inputs gracefully.

### 4. Enhance CLI Plot Parser & Handler (`src/science_cli/library/memristor/device_cli.py`)
- Register the `--highlight` flag in `build_parser()` for the `plot` command.
- In `cmd_plot(args)`:
  - If `args.highlight` is provided:
    - Parse into a list of integers.
    - If `args.row` and `args.col` are not specified, use `fzf` to let the user select a cell that has `iv` files.
    - Collect all IV files for the selected cell, sorted by cycle order.
    - Call the new `generate_iv_highlighted_svg` function.
    - Save as `iv_r{row}c{col}_{material}_multicycle.svg` in the step's `results/` directory.

---

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| [plotting.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/plotting.py) | [MODIFY] | Add `generate_iv_highlighted_svg` for multi-cycle highlighted plotting. |
| [device_cli.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/device_cli.py) | [MODIFY] | Add `--highlight` CLI argument, implement cycle parsing, update `cmd_plot` and `cmd_info` with switching analysis. |

---

## Dependencies
- Project SQLite cache (`res_internship.db` in the workspace). This database is already fully synced and analyzed for protocol 5, so metadata and computed switching parameters are immediately ready to read!

## Cross-PLAN Impact
- None. Extensions are fully encapsulated within the memristor library plotting and command layer.

---

## Verification Plan

### Automated Tests
- Run the pytest suite to ensure no existing tests are broken:
  ```bash
  pytest tests/
  ```

### Manual Verification
- Check switching statistics for `r1c4` in protocol 5:
  ```bash
  sci memristor info --row 1 --col 4
  ```
- Generate a multi-cycle highlighted plot for the same cell:
  ```bash
  sci memristor plot --row 1 --col 4 --highlight 1,5,10,50,100,200,500
  ```
- Inspect the generated `iv_r1c4_cu-c-pda(q)-ito_multicycle.svg` to ensure highlighted cycles are in colored, solid, labeled lines, and all other 660+ cycles are thin, light semi-transparent grey background lines.

---

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT: Highlighted multi-cycle plotting
- [ ] IMPLEMENT: Cycle range parser helper
- [ ] IMPLEMENT: Plot command CLI integrations
- [ ] IMPLEMENT: Info command switching statistics
- [ ] TEST: Run unit tests & verify manually
- [ ] COMMIT done
