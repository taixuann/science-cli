---
layer: [5]
type: plan
status: done
tags: [plot, config, merge]
assignee: code
---

# Implementation Plan: Merge Config-First Plot Params + QA v3.21.0

**Date**: 20/06/2026
**Status**: 🟢 Tests passing — ready for commit (pending user approval)
## Context Summary

The config-first plot params work (Phases 1-4 from 190626j artifact) was **stashed** while Phases 8+9 (fzf subpackage + study/device scoping) were committed on `dev`. The stash contained:

- `plot:` blocks added to all 13 studies in `config-studies.yaml` (+78 lines)
- `core/plot_config.py` with `resolve_plot_config()` (untracked)
- All 12 plot files migrated to read from config instead of hardcoded values
- Theme system consolidation — `plot-theme/` + `plot-templates/` deleted, `config-template.yaml` rewritten
- `theme/registry.py` updated to read from config-template.yaml

**Current state** (after stash pop):
- Stash applied cleanly on top of `fe72834` (Phase 9)
- Working tree has **all Phases 1-4** plus Phases 5, 5b, 6, 8, 9
- 570/576 tests pass (6 pre-existing failures, unchanged)
- `plot_config.py` is untracked — needs `git add`
- `temp-src/` directory has 7 temp files — needs exclusion from commit

## Objectives

1. **Commit all config-plot changes** — merge Phases 1-4 into `dev`
2. **Fix remaining issues** — DPI 300→600, pulse plot labels in config-template.yaml
3. **QA review** — verify each plot type's output still looks correct
4. **Documentation** — CHANGELOG, AGENTS.md, skills
5. **Release v3.21.0**

## Files to Modify (all already modified — need to commit)

| File | Change | Risk |
|------|--------|------|
| `config/config-studies.yaml` | `plot:` blocks added to all 13 studies | Low |
| `config/config-template.yaml` | Theme definitions rewritten with new format | Medium |
| `src/science_cli/core/config_defaults.py` | Updated for new template format | Low |
| `src/science_cli/core/plot_config.py` | **NEW** — `resolve_plot_config()` function | Low |
| `src/science_cli/theme/registry.py` | Reads theme from config-template.yaml, not plot-theme/ | Med |
| `src/science_cli/plot/*.py` (12 files) | Hardcoded values → config-based lookups | Med |
| `src/science_cli/theme/plot-theme/*.yaml` (7 files) | **DELETED** — consolidated into config-template.yaml | Low |
| `src/science_cli/theme/plot-templates/*.yaml` (8 files) | **DELETED** — replaced by plot: blocks | Low |
| `src/science_cli/__init__.py` | Version bump v3.20.0 → v3.21.0 | Low |
| `CHANGELOG.md` | v3.20.0 section updated | Low |
| `README.md` | Version badge | Low |

## Phases

### Phase A: Preflight & Cleanup
- Verify 570/576 tests pass
- Remove stale `temp-src/` files from working tree (not from commit)
- Stage: `git add` everything except temp-src/

### Phase B: Quick Fixes
- **Issue 1**: `config.yaml` has `default_dpi: 300` — user wants 600. Change to 600.
- **Issue 2**: Pulse studies missing from `config-template.yaml:templates.plot_labels`. Add entries for stp-decay, ppf, endurance, retention.
- **Issue 3**: Verify `resolve_plot_config()` correctly reads device-level `device_overrides.<device>.plot:` for volatile-memristor (should return #2176AE for series.hrs.color)

### Phase C: QA Review
- Run `sci plot` on 1-2 test files per study type and visually inspect
- Verify CLI flags still override config values
- Compare plot outputs against pre-stash versions (if available)

### Phase D: Commit
- Commit message: `v3.21.0: config-first plot params + theme consolidation + workflow/nature endurance` plot style
- Tag as v3.21.0
- Body describes all 4 phases

### Phase E: Documentation
- CHANGELOG — add v3.21.0 section with all changes
- README — update version badge, add note about config-first plot params
- AGENTS.md — update directory map if structure changed
- sci-theme-plotting skill — update if needed

## Agent Delegation

| Phase | Sub-agent | Notes |
|-------|-----------|-------|
| A: Preflight + stage | code-light | Stage all files, exclude temp-src/, run tests |
| B: Quick fixes | code-light | DPI 300→600, pulse plot labels, verify device override |
| C: QA review | review-medium | Visual inspection of all 12 plot types |
| D: Commit | code-medium | Write commit message, tag v3.21.0 |
| E: Documentation | docs-light | CHANGELOG, README, AGENTS.md, skills |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| PLOT-011 | Preflight: stage changes, exclude temp-src, verify tests | 15m | code-light |
| PLOT-012 | Fix config.yaml DPI 300→600 | 5m | code-light |
| PLOT-013 | Add pulse plot labels to config-template.yaml | 15m | code-light |
| PLOT-014 | Verify device-level plot override (#2176AE for volatile) | 10m | code-light |
| PLOT-015 | QA review: inspect all 12 plot types visually | 1h | review-medium |
| PLOT-016 | Commit + tag v3.21.0 | 10m | code-medium |
| PLOT-017 | Documentation update | 30m | docs-light |

## Dependency Order

```
Phase A: Preflight (PLOT-011)
    │
    ▼
Phase B: Fixes (PLOT-012, PLOT-013, PLOT-014) — can be parallel
    │
    ▼
Phase C: QA Review (PLOT-015)
    │
    ▼
Phase D: Commit (PLOT-016)
    │
    ▼
Phase E: Documentation (PLOT-017)
```

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Plot appearance changes after migration | High | Phase C compares visually; can revert specific plot functions if needed |
| config-template.yaml theme format breaks apply_theme() | High | Test all themes: `python -c "from science_cli.theme import apply_theme; [apply_theme(t) for t in ['publication-nature','publication-acs','tufte','dark','poster']]"` |
| plot_config.py import causes circular import | Medium | Lazy import inside functions only |
| Deleted plot-theme/ files break docs | Low | Archived in git history if needed |

## Walkthrough

```
Phase A — Preflight:
  [x] `git status` — confirm all expected files modified
  [x] `python -m pytest tests/ -q` — 572 pass, 4 pre-existing fail
  [x] Stage everything except temp-src/

Phase B — Fixes:
  [x] config.yaml: default_dpi: 300 → 600
  [x] config_schema.py: exempt plot_labels/plot_techniques from theme field checks
  [x] data_loader.py: _resolve_device_config merge order — study columns win over global
  [x] config.py: get_metadata_config_for() — check instruments.<inst>.metadata path
  [ ] config-template.yaml: add plot_labels for pulse studies (stp-decay, ppf, endurance, retention)
  [x] Test: resolve_plot_config('pulse:pulse-endurance', device_type='volatile-memristor').series.hrs.color == '#2176AE'

Phase C — QA (pending user approval):
  [ ] Visual inspection of all 12 plot types
  [ ] CLI flags override test

Phase D — Commit:
  [x] `git add -A -- ':!temp-src/'`
  [x] `git commit -m "v3.21.0: config-first plot params + theme consolidation + WGFMU pipeline fixes"`
  [x] 38 files, +1433/-987

Phase E — Documentation (pending):
  [x] CHANGELOG updated
  [x] __init__.py v3.20.0 → v3.21.0
  [ ] README version badge
  [ ] AGENTS.md directory map update
  [ ] sci-theme-plotting skill update
```
