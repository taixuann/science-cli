# PLAN: Memristor Backend Improvements, SQLite v5 & Raw Plotting

## Classification
`feature | config | refactor`

## Related Plans
- [[310526_memristor_help_and_frontend_prompt.md]] — related — coordinating CLI changes

## Status
- **Created**: 2026-05-31
- **Status**: draft
- **Branch**: dev

## Objective
To simplify sweep metadata syncing, establish default temperatures (298K), restructure protocol tracking to introduce a normalized `materials` table, implement automated volatile/non-volatile/short/open device classification, and add raw linear plotting support to the CLI vector engine.

## Context
Currently, the database stores sweep segments and sweep types which are often unnecessary for pure time-based analyses. Furthermore, the `protocols` table is unnormalized and serializes material arrays as flat strings, making detailed material-by-coordinate screening and yield checks hard. Volatile memristors (relaxation switching with clean SET sweeps but unstable or absent RESET sweeps) are not formally distinguished from non-volatile memristors in the backend. Finally, the SVG generator lacks a native flag to plot raw linear current (rather than log absolute current) which is critical for linear devices or symmetric switching curves.

## Specification

### Part 1: Sweep Metadata Defaults & Simplification
- Default temperature will be set to `298.0` K (26°C + 273) globally:
  - Add `temperature REAL DEFAULT 298.0` to the `files` table DDL.
  - When syncing, if the temperature is not explicitly parsed, default to `298.0` K.
- Make sweep type, sweep order, and sweep segments optional, hiding them or bypassing them cleanly where time-based sweeping is present.

### Part 2: SQLite Schema Upgrade (v4 → v5)
- Update `SCHEMA_VERSION = 5` in `db.py`.
- **Streamline `protocols` table**:
  - Keep `name` and `last_sync`.
  - Add `has_memristors INTEGER DEFAULT 1` to designate whether a protocol contains memristor measurements.
  - Drop active reliance on serialized `materials`, `rows`, and `cols` in `protocols` (relying instead on the new `materials` table).
- **Create new `materials` table**:
  ```sql
  CREATE TABLE IF NOT EXISTS materials (
      id INTEGER PRIMARY KEY,
      protocol TEXT NOT NULL,
      row INTEGER NOT NULL,
      col INTEGER NOT NULL,
      material TEXT NOT NULL,
      device_type TEXT DEFAULT 'non-volatile', -- 'non-volatile', 'volatile', 'resistor', 'short', 'open'
      errors TEXT DEFAULT '',
      UNIQUE(protocol, row, col)
  )
  ```
- **Automatic Migration**:
  - In `_run_migrations()`, add a block from `from_version < 5 <= to_version` that executes:
    1. `ALTER TABLE protocols ADD COLUMN has_memristors INTEGER DEFAULT 1`
    2. `CREATE TABLE IF NOT EXISTS materials` (creates the new table).

### Part 3: Automated Device Classification (during `analyze`)
During the `sci memristor analyze` command execution:
1. Extract standard parameters ($V_{set}$, $V_{reset}$, ON/OFF ratio, switching detected).
2. Gather all analyzed sweeps for each unique `(row, col)` coordinate within the protocol.
3. Compute coordinates-level diagnostics and update the `materials` table:
   - **Volatile Memristor (`volatile`)**: Clean $V_{set}$ exists, but $V_{reset}$ is consistently absent (None) or median $|V_{reset}| < 0.15\text{ V}$ (relaxation style).
   - **Non-Volatile Memristor (`non-volatile`)**: Clean, stable bi-stable $V_{set}$ and $V_{reset}$ sweeps both exist.
   - **Shorted Cell (`short`)**: Median ON/OFF ratio is $< 1.2$, switching is not detected, and the compliance limit is reached instantly (high leakage).
   - **Insulating Cell (`insulating`)**: No switching detected, very low current across all cycles.

### Part 4: CLI Raw Current Plotting (Linear)
- Add a new `--raw` flag to `sci memristor plot`:
  - When `--raw` is specified, the SVG generator plots the linear raw `current` directly without taking `np.abs(current)`.
  - Automatically disables logarithmic scaling (`use_log = False`).
  - Sets the Y-axis label to "Current (A)" instead of "Absolute Current (A)".

---

## Proposed Changes

### [Component Name: memristor]

#### [MODIFY] [db.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/db.py)
- Change `SCHEMA_VERSION = 5`.
- Define `CREATE_MATERIALS` schema DDL.
- Add `CREATE_MATERIALS` to `init_db`.
- Add `from_version < 5 <= to_version` migration block to `_run_migrations` that creates the `materials` table and alters `protocols` to add `has_memristors`.
- Implement `upsert_material` and `classify_and_populate_materials(conn, protocol_name)`.
- Update `populate_from_grammar` to call `upsert_material` on every successfully parsed file coordinates.

#### [MODIFY] [device_cli.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/device_cli.py)
- In `cmd_analyze`, call `classify_and_populate_materials` at the end of each analyzed protocol to dynamically write classifications to the database.
- Add `--raw` argument to `plot` sub-parser (`p_plot.add_argument("--raw", action="store_true", help="Plot raw current on linear scale (no absolute value)")`).
- In `cmd_plot`, pass `raw_current=args.raw` to plotting functions.

#### [MODIFY] [plotting.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/plotting.py)
- Add `raw_current: bool = False` parameter to `generate_iv_svg`, `generate_iv_overlay_svg`, and `generate_iv_highlighted_svg`.
- When `raw_current` is `True`, bypass log-scaling, plot raw currents, and adjust axes labels accordingly.

---

## Verification Plan

### Automated Tests
- Create unit test cases in `tests/test_memristor/` checking:
  - Database schema v5 migrations successfully run.
  - Files synced correctly populate row/col coordinates in the `materials` table.
  - Volatile/non-volatile cell categorization matches the mathematical heuristics.
  - `sci memristor plot --raw` runs without error and generates SVGs.

### Manual Verification
- Run `sci memristor sync --all` and verify `materials` table is populated.
- Run `sci memristor analyze` and verify cells are classified as volatile or non-volatile.
- Run `sci memristor plot --raw --row 1 --col 4` and verify linear current SVGs are cleanly drawn.

---

## Progress
- [x] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
