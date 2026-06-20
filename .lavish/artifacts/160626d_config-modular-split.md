---
layer: [1]
type: plan
status: done
tags: [config, modular-split]
assignee: code
---

# Implementation Plan: Config Modular Split (4-Tier)

**Date**: 16/06/2026
**Status**: 🟡 Planning
## Context Summary

Current `~/.config/science-cli/config/` has:
- `config.yaml` (230 lines, monolithic) — routing + file_naming + devices + techniques + defaults + plot.labels
- `config-instruments.yaml` (1 line, empty stub `instruments: {}`)
- No `config-devices.yaml`, `config-grammar.yaml`, `config-template.yaml`

The code in `config.py` already supports the 4-tier modular split (Layers 0-5 in `load_global_config()`):
- Layer 0: hardcoded defaults (`_STUDIES`, `_DEVICE_TYPES`, `_GRAMMAR`, etc. in `config_defaults.py`)
- Layer 1: `config.yaml` (backward compat — merges into defaults)
- Layer 2: `config-devices.yaml` (REPLACES `studies`, `device_types`, `legacy_to_study`)
- Layer 3: `config-instruments.yaml` (REPLACES `instruments`)
- Layer 4: `config-grammar.yaml` (REPLACES `file_naming`)
- Layer 5: `config-template.yaml` (REPLACES `templates`)

The user wants:
- `config.yaml` → routing only (projects_root, theme, default_dpi, default_figure_format, defaults)
- `config-grammar.yaml` → file_naming.patterns
- `config-devices.yaml` → studies + device_types + legacy_to_study (moved from hardcoded defaults)
- `config-instruments.yaml` → instruments (= current `devices:` section in config.yaml)
- `config-template.yaml` → plot.labels (templates)

Update AGENTS.md to document the new config split.

## Objectives

1. **Move file_naming** to `config-grammar.yaml`
2. **Move instruments** to `config-instruments.yaml` (currently empty stub)
3. **Move techniques** to `config-devices.yaml` (study metadata)
4. **Move plot.labels** to `config-template.yaml`
5. **Move studies/device_types/legacy_to_study** from hardcoded defaults to `config-devices.yaml` (so the modular file is the source of truth)
6. **Slim config.yaml** to routing only
7. **Update AGENTS.md** to document the new config split
8. **Verify** all 444 tests still pass

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `config/config.yaml` | Strip down to routing only | Low |
| `config/config-grammar.yaml` (NEW) | file_naming.patterns | Low |
| `config/config-instruments.yaml` | Populate with `instruments` from config.yaml | Low |
| `config/config-devices.yaml` (NEW) | studies + device_types + legacy_to_study + techniques | Med |
| `config/config-template.yaml` (NEW) | plot.labels | Low |
| `src/science_cli/core/config_defaults.py` | Remove `_STUDIES`, `_DEVICE_TYPES`, `_LEGACY_TO_STUDY` (now in config-devices.yaml); keep `_GRAMMAR` as fallback only | Med |
| `src/science_cli/core/config.py` | Update docstring; verify resolution order still works | Low |
| `AGENTS.md` (root + science-cli) | Document new config split | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Config split + populate modular files | code-medium | Main refactor |
| Verify tests still pass | review-light | 444 pass expected |
| AGENTS.md + CHANGELOG + docs | docs-light | Document new layout |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Create `config-grammar.yaml` with file_naming.patterns | 10m | code-medium | no |
| task-002 | Populate `config-instruments.yaml` with current `devices:` | 10m | code-medium | no |
| task-003 | Create `config-devices.yaml` with studies + device_types + legacy_to_study + techniques | 20m | code-medium | no |
| task-004 | Create `config-template.yaml` with plot.labels | 10m | code-medium | no |
| task-005 | Slim `config.yaml` to routing only | 5m | code-medium | no |
| task-006 | Remove `_STUDIES`/`_DEVICE_TYPES`/`_LEGACY_TO_STUDY` from config_defaults.py | 15m | code-medium | no |
| task-007 | Run pytest — all 444 tests must still pass | 10m | review-light | no |
| task-008 | Update AGENTS.md (root + science-cli) with new config split | 15m | docs-light | no |
| task-009 | Update CHANGELOG.md | 5m | docs-light | no |

## Dependency Order

1. task-001, 002, 003, 004 (create modular files) — independent
2. task-005 (slim config.yaml) — depends on 001-004 (must not lose data)
3. task-006 (remove hardcoded studies) — depends on 003 (config-devices.yaml must have the data)
4. task-007 (pytest) — depends on all above
5. task-008, 009 (docs) — depends on 007 (need test results to confirm)

## Risks

- **Risk 1**: `_STUDIES` is referenced in many places. If we remove it from `config_defaults.py`, code that does `from science_cli.core.config_defaults import _STUDIES` will break. Need to check all imports.
- **Risk 2**: The current config.yaml `techniques:` section overlaps with hardcoded `_STUDIES` (study configs). After the split, `config-devices.yaml → techniques:` (from config.yaml) AND `config-devices.yaml → studies:` (moved from defaults) will be merged. Could cause conflicts.
- **Risk 3**: `_DEVICE_TYPES` and `techniques:` overlap. Studies are organized by technique (`pulse:pulse-stp-decay`) but device_types list study references. Need to make sure both stay in sync.

## Walkthrough

(Filled during/after implementation)
