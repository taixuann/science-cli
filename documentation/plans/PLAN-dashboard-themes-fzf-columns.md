# PLAN: Dashboard Themes + FZF Column Standardization

## Status
- **Created**: 2026-05-17
- **Status**: in-progress
- **Branch**: feature/dashboard-themes-fzf-columns

## Objective
Add 3 themes (Dark, Full Black, Full White) to memristor dashboards, protocol filtering for `sci plot --fzf`, and standardize all fzf pickers to `protocol  step  filename` column format.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | Modify | Add theme CSS blocks, theme selector HTML, setTheme JS |
| `src/science_cli/core/fzf_utils.py` | Modify | Add `build_fzf_display()` helper |
| `src/science_cli/cli/commands/plot.py` | Modify | Protocol filter + fzf column format |
| `src/science_cli/cli/commands/add.py` | Modify | fzf column format |
| `src/science_cli/cli/commands/delete_cmd.py` | Modify | fzf column format |
| `src/science_cli/cli/commands/results.py` | Modify | fzf column format |
| `src/science_cli/cli/commands/edit_cmd.py` | Modify | fzf column format |
| `src/science_cli/memristor/plotting.py` | Modify | Update `build_fzf_line` signature |
| `src/science_cli/memristor/device_cli.py` | Modify | fzf column format |

## Dependencies
None — all changes are independent.

## Progress
- [x] PLAN created
- [x] IMPLEMENT done
- [x] TEST passed (78/78, YELLOW — minor None guard fixed)
- [x] Docs updated (docstrings: dark-themed → multi-themed)
- [x] COMMIT done
