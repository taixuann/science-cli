---
layer: [4, 5]
type: plan
status: in-progress
tags: [fzf, plot, device, architecture]
assignee: code
---

# Implementation Plan: Plot FZF Metadata + Device Architecture

**Date**: 17/06/2026
**Status**: 🟠 In Progress
## Context Summary

Previous sessions completed:
1. **Config/study cleanup** — removed 13 studies, restructured ls -m device/study
2. **Plot help cleanup** — removed per-study flags (laser, accumulation, etc.), kept --gradient/--cmap/--describe
3. **fzf metadata** — `build_fzf_display()` now accepts optional `metadata: dict` param
4. **Interactive style form** — replaced dual input() with single form (name, label, markersize, color, etc.)
5. **Device types** — only volatile-memristor + non-volatile-memristor remain
6. **Re-added pulse-endurance/pulse-retention** to _STUDIES and _DEVICE_TYPES
7. **config.py warning** — removed _warn_migrate_once()

### Remaining Issues

| # | Issue | Location |
|---|-------|----------|
| 1 | `pulse:pulse-endurance` + `pulse:pulse-retention` missing from `_STUDY_ORDER` in help.py | `help.py` |
| 2 | `_ls_study()` assigns each study to only ONE device type (bug — shared studies like iv:iv-bipolar-sweep only show in first matching section) | `ls_cmd.py` |
| 3 | fzf metadata display NOT wired — `metadata` param exists but no callers pass it | `plot.py` |
| 4 | There's a preview on fzf (`head -n 20`) — user said "we don't need the data preview anymore" | `plot.py` |
| 5 | No device-type-aware plot dispatch — one StudyPlotter per study regardless of device type | `plot/registry.py` |
| 6 | Dual pattern detection (study substring + legacy technique regex) can return different results | `core/config.py`, `core/technique.py` |
| 7 | `_resolve_device()` doesn't use study_name for instrument fallback | `plot.py` |
| 8 | `_DEFAULT_GLOBAL_TECHNIQUES` missing EC entries | `core/config.py` |

## Objectives

- **Phase A**: Fix immediate bugs (help.py, ls_cmd.py study display)
- **Phase B**: Wire fzf metadata columns for rich file browsing
- **Phase C**: Design/implement device-type-aware plot dispatch architecture

## Files to Modify

### Phase A (code-light)

| File | Change | Risk |
|------|--------|------|
| `cli/help.py` | Add pulse-endurance/pulse-retention to _STUDY_ORDER | Low |
| `cli/commands/ls_cmd.py` | Fix _ls_study() multi-device-type bug — show shared studies in ALL matching sections | Low |

### Phase B (code-medium)

| File | Change | Risk |
|------|--------|------|
| `cli/commands/plot.py` | Wire metadata into `build_fzf_display()` call; remove preview param | Med |
| `core/fzf_utils.py` | Potential tweaks to metadata column formatting | Low |

### Phase C (plan-heavy → code-heavy)

| File | Change | Risk |
|------|--------|------|
| `plot/registry.py` | Add device_type_variants to StudyPlotter | Med |
| `cli/commands/plot.py` | Thread device_type through dispatch chain | Med |
| `core/config.py` | Consolidate pattern detection; add EC to _DEFAULT_GLOBAL_TECHNIQUES | Med |
| `core/config_defaults.py` | Ensure patterns/legacy_codes are consistent | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Phase A — Immediate fixes | code-light | help.py + ls_cmd.py study bug |
| Phase B — fzf metadata wiring | code-medium | Wire metadata into plot.py fzf |
| Phase C — Device dispatch architecture | plan-heavy → code-heavy | Architectural analysis then implementation |
| QA & Review | review-light | Smoke + lint check |
| Documentation | docs-light | Update README, CHANGELOG, artifact-review |
| Calendar Sync | calendar | Create/update GCal events for calendar-marked tasks |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| A-001 | Re-add pulse-endurance/pulse-retention to help.py _STUDY_ORDER | 10m | code-light | no |
| A-002 | Fix _ls_study() multi-device-type display bug | 15m | code-light | no |
| B-001 | Wire fzf metadata columns in plot.py fzf display | 30m | code-medium | no |
| B-002 | Remove preview from fzf_select call in plot.py | 5m | code-medium | no |
| C-001 | Plan-heavy: design device-type dispatch architecture | 45m | plan-heavy | no |
| C-002 | Implement device-type variants in StudyPlotter | 1h | code-heavy | no |
| C-003 | Thread device_type through plot dispatch chain | 1h | code-heavy | no |
| C-004 | Consolidate pattern detection (study vs technique) | 45m | code-heavy | no |
| QA-001 | Run test suite, verify all changes | 20m | review-light | no |
| DOC-001 | Update CHANGELOG.md and artifact | 15m | docs-light | no |

## Dependency Order

1. Phase A (A-001 → A-002) — code-light
2. Phase B (B-001 → B-002) — code-medium (can run parallel with Phase A)
3. Phase C design (C-001) — plan-heavy
4. Phase C implementation (C-002 → C-003 → C-004) — code-heavy (after C-001 approved)
5. QA-001 — review-light (after all code changes)
6. DOC-001 — docs-light (after QA passes)

## Risks

- **Multi-device-type dispatch**: The current architecture has no mechanism for same-study-different-device-type plotting. Adding this cleanly requires careful design to avoid breaking existing dispatch.
- **Pattern detection consolidation**: Two parallel systems (study substring matching + legacy technique regex) exist. Removing one risks breaking backward compat for users who rely on `-t/--technique` flag.
- **Test coverage**: Many tests reference specific study names that may need updating.

## Walkthrough

(Step-by-step notes filled during/after implementation)
