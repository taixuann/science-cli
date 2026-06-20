---
layer: [1]
type: plan
status: planning
tags: [config, studies, instruments]
assignee: plan
---

# Implementation Plan: Config/Study/Instrument Cleanup

**Date**: 16/06/2026
**Status**: 🟡 Planning
## Context Summary

After reviewing the `science-cli` codebase, I've mapped out the full scope of changes. The config system has two layers:

1. **Hardcoded defaults** in `src/science_cli/core/config_defaults.py` — `_STUDIES`, `_INSTRUMENTS`, `_DEVICE_TYPES`, `_LEGACY_TO_STUDY`
2. **Hardcoded defaults** in `src/science_cli/core/config.py` — `_DEFAULT_TECHNIQUE_PATTERNS`, `_DEFAULT_TECHNIQUE_DEVICES`, `_DEFAULT_GLOBAL_DEVICES`, `_DEFAULT_GLOBAL_TECHNIQUES`
3. **Legacy monolithic config.yaml** at `~/.config/science-cli/config/config.yaml` — still the active user config (modular migration not fully applied — `config-instruments.yaml` is empty `{}`, `config-devices.yaml` doesn't exist)
4. **`cli/commands/ls_cmd.py`** — `ls -m device` incorrectly delegates to `_ls_instrument()` (bug)
5. **`core/studies.py`** — `render_study_table()` and `_ls_study()` in `ls_cmd.py` control study table rendering

## Objectives

1. **Remove instruments** `iop-hanoi` and `keysight-b1500` from both hardcoded defaults and config.yaml
2. **Fix `ls -m device`** to show Device Types (not Instruments)
3. **Fix `ls -m study`** table — technique column first, study names without prefix, add autolab-usth instrument for all ec studies, add device-type category grouping
4. **Remove ~12 studies** from ALL layers (config_defaults.py, config.py, config.yaml, plot templates)
5. **Update `config.yaml`** — cleanup techniques, defaults, plot labels

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `core/config_defaults.py` | Remove studies from `_STUDIES`, update `_LEGACY_TO_STUDY`, update `_DEVICE_TYPES`, add autolab-usth to ec studies | Med |
| `core/config.py` | Remove studies from `_DEFAULT_TECHNIQUE_PATTERNS`, `_DEFAULT_TECHNIQUE_DEVICES`, `_DEFAULT_GLOBAL_DEVICES` (keysight-b1500), `_DEFAULT_GLOBAL_TECHNIQUES` | High |
| `cli/commands/ls_cmd.py` | Add `_ls_device()` function, fix `ls -m device` routing, restructure `_ls_study()` table | Low |
| `config/config.yaml` | Remove iop-hanoi, keysight-b1500 from `devices:`; remove purged studies from `techniques:`, `plot.labels:`, `defaults:` | Med |
| `theme/plot-templates/mem-endurance.yaml` | Delete file (study removed) | Low |
| `theme/plot-templates/mem-retention.yaml` | Delete file (study removed) | Low |
| `theme/plot-templates/mem-switching.yaml` | Delete file (study removed) | Low |

## Studies to Remove

| Study | Technique | Reason |
|-------|-----------|--------|
| `mem-endurance` | memristor | Remove entire `memristor` technique |
| `mem-retention` | memristor | Same |
| `mem-switching` | memristor | Same |
| `pulse-endurance` | pulse | Redundant with iv-based analysis |
| `pulse-retention` | pulse | Not used |
| `pulse-switching` | pulse | Not used |
| `pulse-forming` | pulse | Not used |
| `pulse-set` | pulse | Not used |
| `pulse-reset` | pulse | Not used |
| `pulse-read` | pulse | Not used |
| `pulse-ivd` | pulse | Not used |
| `ec-lsv` | ec | Not used |
| `ec-swv` | ec | Not used |

**Studies to KEEP:**
- `iv:iv-bipolar-sweep`, `iv:iv-breakdown`, `iv:iv-leakage`
- `pulse:pulse-stp-decay`, `pulse:pulse-ppf`
- `raman:raman-spectrum`
- `uv-vis:uv-vis-spectrum`
- `ec:ec-cv`, `ec:ec-ca`, `ec:ec-eis`
- `afm:afm-topography`

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-medium | Main config/study cleanup work |
| QA & Review | review-light | Smoke test + lint check |
| Documentation | docs-light | Update README if behavior changed |
| Calendar Sync | calendar | Create/update GCal events for calendar-marked tasks |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Remove instruments iop-hanoi and keysight-b1500 from config_defaults.py, config.py, config.yaml | 15m | code | no |
| task-002 | Remove 12 studies from _STUDIES in config_defaults.py + update _LEGACY_TO_STUDY + _DEVICE_TYPES | 20m | code | no |
| task-003 | Remove studies from config.py (_DEFAULT_TECHNIQUE_PATTERNS, _DEFAULT_TECHNIQUE_DEVICES, _DEFAULT_GLOBAL_TECHNIQUES) | 20m | code | no |
| task-004 | Fix ls -m device: add _ls_device() function, change routing | 15m | code | no |
| task-005 | Fix ls -m study: column order + naming + autolab-usth for ec + device-type grouping | 20m | code | no |
| task-006 | Clean up config.yaml: remove purged entries from techniques/defaults/plot.labels | 15m | code | no |
| task-007 | Delete removed plot templates (mem-endurance, mem-retention, mem-switching) | 5m | code | no |
| task-008 | QA: pytest tests/ -q, verify ls -m commands work | 15m | review | no |

## Dependency Order

1. task-001 (Remove instruments from all layers)
2. task-002 + task-003 (Remove studies from all hardcoded defaults) — parallel
3. task-006 (Clean up config.yaml)
4. task-007 (Delete plot templates)
5. task-004 + task-005 (Fix CLI display commands) — parallel
6. task-008 (QA)

## Risks

- **High**: Changes to `core/config.py` affect ALL config resolution. Must ensure backward compat for remaining studies.
- **Medium**: The `config.yaml` still uses the old monolithic format — removal from it must be precise to avoid YAML parse errors.
- **Low**: CLI display changes are cosmetic and isolated to `ls_cmd.py`.

## Walkthrough

### task-001: Remove instruments
- `core/config_defaults.py`: `iop-hanoi` and `keysight-b1500` not in `_INSTRUMENTS` — no change needed here.
- `core/config.py`: Remove `keysight-b1500` from `_DEFAULT_GLOBAL_DEVICES` (~lines 991-999).
- `config/config.yaml`: Remove `iop-hanoi:` block (lines 91-99) and `keysight-b1500:` block (lines 74-81) from `devices:` section.

### task-002: Remove studies from config_defaults.py
- `_STUDIES`: Remove entire `memristor` key and its 3 studies. Remove from `pulse`: `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd`. Remove from `ec`: `ec-lsv`, `ec-swv`.
- Add `autolab-usth` instrument entry to `ec-cv`, `ec-ca`, `ec-eis` in `_STUDIES` (with Biologic .mpt config).
- `_LEGACY_TO_STUDY`: Remove entries for all removed studies.
- `_DEVICE_TYPES`: Remove removed studies from the `studies:` lists.

### task-003: Remove studies from config.py
- `_DEFAULT_TECHNIQUE_PATTERNS`: Remove entries for all removed studies.
- `_DEFAULT_TECHNIQUE_DEVICES`: Keep only iv-sweep, raman, uv-vis, pulse-stp, pulse-ppf.
- `_DEFAULT_GLOBAL_TECHNIQUES`: Remove entries for all removed pulse/memristor studies.

### task-004: Fix ls -m device
- Create `_ls_device()` function that reads device types from config and renders a Rich table with columns: Name, Label, Description, Analysis Mode, Library.
- Change line 64-66 from `_ls_instrument()` to `_ls_device()`.

### task-005: Fix ls -m study table
- Reorder columns: Technique first, then Study (without `technique:` prefix), Label, Instruments.
- Study name column shows just `ec-cv` not `ec:ec-cv`.
- For ec studies: `autolab-usth` will show as instrument (from updated config_defaults.py).
- Add device-type category grouping: group rows under device type headers.

### task-006: Cleanup config.yaml
- Remove from `techniques:` section all removed entries.
- Remove from `defaults:` section entries for removed techniques.
- Remove from `plot.labels:` section mem-* and removed pulse-* entries.
- Change `uv-vis` default_device from `iop-hanoi` to `spectrometer-iop`.

### task-007: Delete plot templates
- Delete `theme/plot-templates/mem-endurance.yaml`
- Delete `theme/plot-templates/mem-retention.yaml`
- Delete `theme/plot-templates/mem-switching.yaml`
