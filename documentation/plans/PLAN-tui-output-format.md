# PLAN: TUI Output Format — Combined Command Echo + Timestamp

## Status
- **Created**: 2026-05-13
- **Status**: completed
- **Branch**: (none)

## Objective
Fix command echo and timestamp to display on one line with right-aligned timestamp, and fix grouped help table alignment.

## Context
Previously, `write_command_echo(command)` and `add_separator()` were separate methods producing two lines:
```
> /help

                                                                       15:16:38
```
User requested they be merged into one line:
```
> /help                                                    14:48:45
```

Additionally, the grouped help table header had misaligned column widths (`Command  │` was 9 chars before pipe vs 10 chars in data rows).

## Specification

### Change 1: One-line command header
- Replace `write_command_echo()` + `add_separator()` with single `write_command_header(command)` method
- Uses Rich `Table.grid()` with two columns: left (echo) and right (timestamp, right-aligned)
- All 8 call sites updated

### Change 2: Table alignment
- `Command  │` → `Command   │` (2→3 spaces, matching 10-char data column width)

## Files Modified
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/tui/output_panel.py` | Modified | New `write_command_header()`, removed old methods |
| `src/science_cli/tui/app.py` | Modified | All 8 call sites updated, header alignment fixed |
| `README.md` | Modified | Added Textual TUI documentation section |

## Dependencies
None.

## Test Strategy
- `python -m py_compile` on both modified files
- `from science_cli.tui import SCIApp` import check

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
