---
layer: [4, 5]
type: plan
status: done
tags: [fzf, plot, metadata]
assignee: code
---

# Implementation Plan: Plot Help Cleanup + fzf Metadata + Interactive Style Form

**Date**: 16/06/2026
**Status**: 🟢 Done
## Context Summary

From previous session discussions and code review:

### Current state
- `plot --help` shows GROUP 2 — STUDIES with per-study subflags (e.g. `--laser`, `--accumulation`, `--scan-rate`, `--freq-range`)
- `fzf` file picker shows `protocol step filename` with data preview. No study-specific metadata columns.
- After fzf selection, two prompts: "Style / analysis options" and "Figure options"
- `help.py:_STUDY_ORDER` still references `pulse:pulse-endurance`, `pulse:pulse-retention` (leftover from previous cleanup — bug)
- AFM has no plot options (confirmed)
- `--gradient`, `--cmap`, `--describe` are kept as they're different from the other subflags

### User's confirmed intent

| Point | Decision |
|-------|----------|
| Per-study flags in plot --help | Remove `--laser`, `--accumulation`, `--acq-time`, `--nd-filter` from Raman. Keep `--gradient`, `--cmap`, `--describe` |
| fzf metadata columns | YES — step folder col 1, filename col 2, metadata in subsequent cols. Remove data preview. |
| Interactive style form after fzf | YES — editable form: name, label, markersize, color, linewidth, etc. Enter=default, type to change |
| `--studies` flag | Keep for early filtering |
| AFM no options | Confirmed — `--cross-section` and `--colormap` removed from AFM flags |
| Bug fix | `pulse:pulse-endurance` and `pulse:pulse-retention` still in `_STUDY_ORDER` — remove |

## Objectives

1. Clean up `plot --help`: remove per-study subflags except `--gradient`/`--cmap`/`--describe`, fix leftover deleted studies
2. Enhance fzf display: show config metadata columns (step → filename → technique/instrument/etc), remove data preview
3. Replace post-fzf prompts with interactive Rich-style editable form for figure options
4. Update plot/registry.py STUDY_FLAGS to match new reduced set

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `cli/help.py` | Rewrite `_STUDY_ORDER`: remove pulse-endurance/pulse-retention, remove per-study flags except gradient/cmap/describe. Update `_render_plot_subcommands()` | Low |
| `cli/help.py` | Update `plot` help examples — remove examples showing `--laser`, `--accumulation` etc. | Low |
| `plot/registry.py` | Trim `_RAMAN_FLAGS`, `_UV_VIS_FLAGS`, `_CV_FLAGS`, `_EIS_FLAGS`, `_AFM_FLAGS` to empty. Keep `_IV_SWEEP_FLAGS`, `_STP_FLAGS`, `_PPF_FLAGS` as-is. Update `STUDY_FLAGS` dict. | Low |
| `core/fzf_utils.py` | Add `build_fzf_metadata_display()` or enhance `build_fzf_display()` to accept metadata dict and render columns `step | file | metadata1 | metadata2 | ...`. Optionally remove preview. | Med |
| `cli/commands/plot.py` | Replace post-fzf dual prompt (`_plot_interactive()` lines ~488-501) with a single Rich-form Prompt.ask / Questionary form showing: `name`, `label`, `markersize`, `color`, `linewidth`, `linestyle`, `marker`, `dpi`, `grid`, `legend`. Defaults come from theme. | Med |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | All code changes |
| QA & Review | review-light | Smoke + lint + test |
| Documentation | docs-light | Update README (if needed), artifact-review |
| Calendar Sync | calendar | Create GCal events for tasks marked below |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Clean up `_STUDY_ORDER` in help.py — remove deleted studies + per-study flags except gradient/cmap/describe | 20m | code-medium | no |
| task-002 | Trim `STUDY_FLAGS` in registry.py — remove raman/uv-vis/cv/eis/afm flags | 15m | code-medium | no |
| task-003 | Build fzf metadata display — extend `build_fzf_display()` or add new function to show step → file → metadata columns, remove preview | 1h | code-medium | no |
| task-004 | Replace post-fzf prompts with interactive style form — Rich/Questionary prompt for name, label, markersize, color, linewidth, linestyle, marker, dpi, grid, legend | 1h | code-medium | no |
| task-005 | Update plot help examples in help.py | 10m | code-medium | no |
| task-006 | QA — test all 4 changes, run pytest, verify CLI output | 45m | review-light | no |
| task-007 | Documentation — artifact-review, update CHANGELOG | 15m | docs-light | no |

## Calendar

- calendar shall create/update GCal events for tasks marked `Calendar Event: yes`
- No tasks currently marked for calendar events

## Dependency Order

1. **task-001** + **task-002** (parallel — independent files) → assigned to code-medium
2. **task-003** (fzf_utils) → assigned to code-medium
3. **task-004** (plot.py interactive form) → assigned to code-medium
4. **task-005** (help examples) → assigned to code-medium
5. **task-006** (QA) → assigned to review-light
6. **task-007** (docs) → assigned to docs-light

## Risks

- fzf metadata display: may need new columns based on study config — need to handle varying metadata per study type
- Interactive style form: need to ensure defaults from theme are respected and prompt is not too complex
- Backward compat: `--laser`, `--accumulation` etc. should still be accepted (just not shown in help) to avoid breaking existing workflows? User says "remove" — clarify if we should deprecate or just hide from help.
- `build_fzf_display()` is used in 34+ locations — any signature change must be backward compatible or updated everywhere

## Walkthrough

### task-001: Clean up `_STUDY_ORDER` in help.py
- Removed `pulse:pulse-endurance` and `pulse:pulse-retention` from `_STUDY_ORDER`
- Removed per-study subflags (`--laser`, `--accumulation`, `--acq-time`, `--nd-filter`, `--scan-rate`, `--cycles`, `--freq-range`, `--wavelength-range`, `--cross-section`, `--colormap`) from GROUP 2 STUDIES display
- Kept `--gradient`/`--cmap` for iv-bipolar-sweep, `--describe` for stp-decay/ppf

### task-002: Trim STUDY_FLAGS in registry.py
- Cleared `_RAMAN_FLAGS`, `_UV_VIS_FLAGS`, `_CV_FLAGS`, `_EIS_FLAGS`, `_AFM_FLAGS`
- Updated `STUDY_FLAGS` dict accordingly

### task-003: Build fzf metadata display
- Extended `build_fzf_display()` with optional `metadata: dict` parameter
- Shows additional metadata columns (technique, instrument, etc.) in fzf picker
- Backward compatible — all 34+ existing call sites unchanged

### task-004: Replace post-fzf prompts with interactive style form
- Replaced dual-prompt flow with single multi-field Rich form
- Fields: name, label, markersize, color, linewidth, linestyle, marker, dpi, grid, legend
- Defaults pulled from active theme, Enter to accept

### task-005: Updated plot help examples
- Removed examples showing `--laser`, `--accumulation` etc. from plot --help

### task-006: QA
- Lint: ruff check passed
- Types: mypy passed
- Tests: pytest -q passed

## Changelog
- **16/06/2026**: Completed implementation
  - Files changed: `cli/help.py`, `plot/registry.py`, `core/fzf_utils.py`, `cli/commands/plot.py`
  - Key decisions: fzf metadata is an optional parameter (backward compat); style form uses Rich for consistent look
  - Deviations from plan: None
