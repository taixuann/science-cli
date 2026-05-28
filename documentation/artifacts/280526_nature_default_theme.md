# PLAN: Nature Publication Theme as Global Default

## Classification
theme | config | feature

## Related Plans
- [[280526_themes]] — parent plan for symmetrical themes & technique templates
- [[280526_refactor]] — code reorganization context

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Make `publication-nature` the global default theme across all science-cli commands, and regenerate test-project plots to verify.

## Context
Nature theme YAML exists but is not the default. User already uses `config theme set publication-nature` in session. 25+ code locations hardcode `publication-acs` as fallback. The Nature figure spec from https://research-figure-guide.nature.com requires:
- Helvetica/Arial, editable text (`pdf.fonttype=42`)
- 5-7pt body, 8pt bold panel labels, open axes (L-shaped, top/right off)
- Ticks in, no grid, no colored text, no drop shadows
- 300 DPI min / 600 DPI save, RGB, vector PDF

## Specification

### 1. Update `publication-nature.yaml`
- Add `pdf.fonttype: 42` (critical for Nature compliance — editable fonts)
- Set axes `linewidth: 0.5` for thin spines
- Tick `major_width: 0.5` for fine ticks
- Adjust font sizes to match Nature spec precisely: axes_labelsize=7, tick_labelsize=6, legend_size=6
- Keep: Wong palette, no grid, spines top/right off, ticks in, 600 DPI save

### 2. Change global default `publication-acs` → `publication-nature`
All Python files with hardcoded `"publication-acs"` default:

| File | Lines | Change |
|------|-------|--------|
| `src/science_cli/core/config.py` | 629 | `theme: publication-nature` |
| `src/science_cli/core/session.py` | 24, 96 | default → `publication-nature` |
| `src/science_cli/config.py` | 11 | default → `publication-nature` |
| `src/science_cli/plot/base.py` | 16, 81 | default → `publication-nature` |
| `src/science_cli/plot/__init__.py` | 17 | default → `publication-nature` |
| `src/science_cli/plot/cv.py` | 23 | default → `publication-nature` |
| `src/science_cli/plot/ca.py` | 23 | default → `publication-nature` |
| `src/science_cli/plot/eis.py` | 34 | default → `publication-nature` |
| `src/science_cli/plot/overlays.py` | 19, 21 | default → `publication-nature` |
| `src/science_cli/cli/commands/info.py` | 70, 85 | default → `publication-nature` |
| `src/science_cli/cli/commands/chat_cmd.py` | 29, 30, 120 | defaults → `publication-nature` |
| `src/science_cli/cli/commands/status.py` | 278 | default → `publication-nature` |
| `src/science_cli/cli/commands/config.py` | 136 | `theme: publication-nature` |
| `src/science_cli/tui/status_bar.py` | 44, 70, 89, 140 | defaults → `publication-nature` |

### 3. Update `config.yaml` if needed
The global `~/.config/science-cli/config.yaml` currently says `theme: publication-acs`. Update to `publication-nature`.

### 4. Regenerate test-project plots
Run plot generation for all 8 techniques (iv-sweep, iv-breakdown, iv-leakage, ec-cv, ec-ca, ec-eis, mem-switching, mem-endurance, mem-retention, raman, uv-vis) to produce fresh `nature_*.png` plots under `test-project/plots/`.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/theme/themes/publication-nature.yaml` | Modify | Add pdf.fonttype=42, refine sizes/linewidths |
| `src/science_cli/core/session.py` | Modify | Change default theme |
| `src/science_cli/core/config.py` | Modify | Change default theme |
| `src/science_cli/config.py` | Modify | Change default theme |
| `src/science_cli/plot/base.py` | Modify | Change default theme |
| `src/science_cli/plot/__init__.py` | Modify | Change default theme |
| `src/science_cli/plot/cv.py` | Modify | Change default theme |
| `src/science_cli/plot/ca.py` | Modify | Change default theme |
| `src/science_cli/plot/eis.py` | Modify | Change default theme |
| `src/science_cli/plot/overlays.py` | Modify | Change default theme |
| `src/science_cli/cli/commands/info.py` | Modify | Change default theme |
| `src/science_cli/cli/commands/chat_cmd.py` | Modify | Change default theme |
| `src/science_cli/cli/commands/status.py` | Modify | Change default theme |
| `src/science_cli/cli/commands/config.py` | Modify | Change default theme |
| `src/science_cli/tui/status_bar.py` | Modify | Change default theme |
| `src/science_cli/theme/registry.py` | Modify | Update BUILTIN_THEMES list order |

## Dependencies
None

## Cross-PLAN Impact
Implements the core specification from [[280526_themes]] for Nature style.

## Test Strategy
- Run `pytest` to ensure nothing breaks
- Check that `config theme list` shows both ACS and Nature themes
- Verify plots render without errors

## Progress
- [x] PLAN created
- [x] User approved
- [x] publication-nature.yaml tuned
- [x] All Python defaults changed
- [x] config.yaml updated
- [x] Test-project plots regenerated
- [x] Tests pass (97/97)
- [x] DOCS updated
- [x] COMMIT done
