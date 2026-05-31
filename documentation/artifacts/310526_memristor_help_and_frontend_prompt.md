# PLAN: Memristor CLI Help Grouping & Frontend Prompt Package

## Classification
`command-restructure | docs`

## Status
- **Created**: 2026-05-31
- **Status**: completed
- **Branch**: dev

## Objective
To restructure the `sci memristor --help` command line menu to group subcommands into three intuitive sections matching the top-level CLI aesthetics, and provide a clear, comprehensive prompt along with the list of React codebase files that can be uploaded to Google AI Studio to enhance the frontend gallery.

## Context
Currently, the `memristor` command help menu shows an unsorted lists of 13 positional subcommands, making it hard to quickly discover the right command. Grouping them creates an organized, premium experience. In parallel, the user wants a detailed prompt and files list to upload to Google AI Studio to customize their interactive visualization React dashboard.

## Specification

### Part 1: CLI Help Grouping
The subcommands will be classified into three clear sections:
1. **GROUP 1: DEVICE GEOMETRY & ASSIGNMENT**
   - `init`: Scaffold device geometry in protocol YAML
   - `ls`: List devices or matrix map
   - `info`: Show point details
   - `add`: Add file(s) to a point
   - `rm`: Remove file, technique, or point

2. **GROUP 2: CACHE SYNCHRONIZATION & HEALTH**
   - `sync`: Sync sweep metadata
   - `validate`: Validate device config
   - `stats`: Aggregate statistics
   - `check`: Find unassigned files (recursive)

3. **GROUP 3: CURVES PLOTTING, MATRIX & DASHBOARD**
   - `plot`: Generate IV curve SVGs from devices.yaml
   - `analyze`: Read CSVs and compute Vset/Vreset/ratio (depends on sync)
   - `dashboard`: Generate per-protocol dashboards + main index page
   - `matrix`: Show device matrix from SQLite (no YAML required)

We will intercept `--help`/`-h` in `memristor_handler` and register a custom `.print_help` function on the `argparse` parser inside `build_parser` to output a stunning Rich console panel and command group list.

### Part 2: AI Studio Prompt & File Package
Create a robust, tailored prompt that packages:
- `documentation/science-cli-plot-gallery/src/App.tsx` (the central React app)
- `documentation/science-cli-plot-gallery/src/index.css` (the styles)

The prompt will instruct Google AI Studio to:
- Add a split-screen layout: "Plot Gallery / Sweep Overlays" vs. "Parameter Summaries & Yield Metrics".
- Support interactive filters for $V_{set}$, $V_{reset}$, ON/OFF ratio, and cycle highlights.
- Replace microscopic file/PDF Thumbnails with crisp, direct inline SVGs.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| [memristor.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/cli/commands/memristor.py) | MODIFY | Intercept empty args or `-h` to call beautiful Rich help function. |
| [device_cli.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/library/memristor/device_cli.py) | MODIFY | Add `show_memristor_help` utility and override `parser.print_help`. |

## Test Strategy
- Validate execution of `sci memristor --help` and `sci memristor -h`.
- Verify standard subcommand execution (e.g. `sci memristor init --help`) is unaffected.
- Verify pytest suite passes entirely.

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
