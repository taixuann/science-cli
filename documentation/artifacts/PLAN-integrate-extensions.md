# PLAN: Integrate Extensions as Built-In Modules

## Classification
refactor

## Related Plans
- [[PLAN-extension-interface]] — superseded by this refactor
- [[PLAN-enhanced-dashboard]] — `.lvm` references updated

## Status
- **Created**: 2026-05-13
- **Status**: completed
- **Branch**: refactor/2.1.0

## Objective
Integrate all extension modules (science-memristor, science-iv, science-electrochem) as built-in libraries. Remove the extension system entirely. Update all docs to remove `.lvm` references.

## Context
Extension modules already live in `src/science_cli/memristor/`, `iv/`, `electrochem/` — they're registered via the `ExtensionRegistry` in `extensions.py`. The extension system (`extensions.py`, `ext.py`, `extensions.py`, `memristor_cmd.py`) is an unnecessary indirection layer since these modules are already part of the core package.

The `ColumnMap` and `TechniqueDef` data classes need to be moved to `core/technique.py` since `extensions.py` will be deleted.

`.lvm` (LabVIEW Measurement) format is referenced in docs but user only uses `.csv`/`.txt`.

## Specification

### 1. Remove extension system files (DELETE)
- `src/science_cli/extensions.py` — ExtensionRegistry, discover_extensions, ColumnMap, TechniqueDef, _discover_config_techniques
- `src/science_cli/cli/commands/ext.py` — ext_handler, extension dispatch
- `src/science_cli/cli/commands/extensions.py` — extensions_handler
- `src/science_cli/cli/commands/memristor_cmd.py` — old bridge to ext system

### 2. Move data classes to core/technique.py
- Move `ColumnMap` into `core/technique.py`
- Move `TechniqueDef` into `core/technique.py` (alongside existing labels)
- Remove `_extension_patterns()` — all patterns already hardcoded in PATTERNS
- Update `technique_label()` to use hardcoded labels directly (remove extension fallback)
- Update `_all_patterns()` to remove extension layer (keep config + hardcoded)

### 3. Update subpackage __init__.py files
Each subpackage (memristor, iv, electrochem) keeps its existing public API.
- Remove `from science_cli.extensions import ...`
- Remove `register()` function
- Define column_maps, analyzers, plot_presets as module-level dicts where needed

### 4. Update 3rd-party import chains
- `cli/commands/__init__.py`: remove ext_handler import, remove "ext" from COMMAND_TREE, add "memristor"
- `cli/commands/techniques.py`: replace `discover_extensions()` with direct data
- `cli/help.py`: rename GROUP 4, replace `ext` with `memristor`
- `app.py`: no changes needed (uses only COMMAND_TREE)

### 5. Update test_guardrails.py
- Remove/replace test_extensions_discovery (Test 6)
- Update file list in test_all_modified_files_compile (remove extensions.py)
- Update expected command count

### 6. Remove .lvm references from source code
- `core/config.py` line 54: remove `r"\.lvm$"` from iv-sweep patterns
- `memristor/plotting.py` lines 49, 171, 184: remove LVM references

### 7. Update docs to remove .lvm references
- README.md: replace .lvm mentions
- documentation/plans/PLAN-enhanced-dashboard.md: replace all .lvm references
- documentation/plans/test-report-enhanced-dashboard.md: replace all .lvm references
- CHANGELOG.md: note format change
- AGENTS.md: update directory map, remove extension code examples

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| src/science_cli/extensions.py | DELETE | Extension system removed |
| src/science_cli/cli/commands/ext.py | DELETE | Extension dispatch removed |
| src/science_cli/cli/commands/extensions.py | DELETE | Duplicate extension listing |
| src/science_cli/cli/commands/memristor_cmd.py | DELETE | Replaced by direct COMMAND_TREE entry |
| src/science_cli/core/technique.py | MODIFY | Add ColumnMap, TechniqueDef; remove extension patterns |
| src/science_cli/memristor/__init__.py | MODIFY | Remove ExtensionRegistry, register() |
| src/science_cli/iv/__init__.py | MODIFY | Remove ExtensionRegistry, register() |
| src/science_cli/electrochem/__init__.py | MODIFY | Remove ExtensionRegistry, register() |
| src/science_cli/cli/commands/__init__.py | MODIFY | Replace ext with memristor |
| src/science_cli/cli/commands/techniques.py | MODIFY | Replace discover_extensions with direct data |
| src/science_cli/cli/help.py | MODIFY | Replace ext with memristor in help |
| src/science_cli/core/config.py | MODIFY | Remove .lvm pattern |
| src/science_cli/memristor/plotting.py | MODIFY | Remove LVM references |
| test_guardrails.py | MODIFY | Replace extension tests, update file lists |
| README.md | MODIFY | Remove .lvm references |
| CHANGELOG.md | MODIFY | Note format changes |
| documentation/plans/PLAN-enhanced-dashboard.md | MODIFY | Replace .lvm with .csv/.txt |
| documentation/plans/test-report-enhanced-dashboard.md | MODIFY | Replace .lvm with .csv/.txt |
| AGENTS.md | MODIFY | Update directory map, remove extension code |

## Dependencies
None — this is a self-contained refactoring.

## Test Strategy
1. Run `test_guardrails.py` — all tests must pass
2. Verify `python -c "from science_cli.cli.commands import COMMAND_TREE; print(COMMAND_TREE.keys())"` shows no "ext" but has "memristor"
3. Verify `sci --help` shows no "ext" command
4. Verify `sci memristor --help` works
5. Verify `python -c "from science_cli.core.technique import detect_technique; print(detect_technique('test_IV.csv'))"` returns "iv-sweep"

## Progress
- [x] PLAN created
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
