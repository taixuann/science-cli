# QA Test Report — PLAN-2 Config Expansion + Phase 6 Parquet

**Date:** 2026-05-13  
**Branch:** `mysci-tui_update`  
**Commits under test:**
- `64def42` — feat(config): implement PLAN-2 config expansion
- `8708b9a` — feat(core): implement Phase 6 — parquet storage for processed data
- `247c0a3` — feat(docs): create CHANGELOG.md for 2.0.0 release

**Tester:** qa-tester agent

---

## Summary

| Phase | Status |
|-------|--------|
| 1. Smoke Tests (4/4) | ✅ PASS |
| 2. Functional Tests — Technique Config (5/5) | ✅ PASS |
| 3. Functional Tests — Parquet Store (5/5) | ✅ PASS |
| 4. Guardrail Tests (16/16) | ✅ PASS |
| 5. CLI Command Dispatching (5/5) | ✅ PASS |
| 6. Edge Case Tests — Parquet (4/4) | ✅ PASS |
| 7. Edge Case Tests — Config Subcommands (5/5) | ✅ PASS |
| 8. Edge Case Tests — Technique Config Logic (5/5) | ✅ PASS |
| 9. CHANGELOG Validation | ✅ PASS |
| **TRAFFIC LIGHT** | **🟢 GREEN** |

---

## 1. Smoke Tests (Import Verification)

### Test 1.1: Config expansion imports
```python
from science_cli.core.config import list_technique_names, list_technique_devices, write_technique_config, load_technique_configs
```
**Result:** ✅ PASS — All imports resolve without error

### Test 1.2: Parquet store imports
```python
from science_cli.core.parquet_store import write_features, read_features, append_features, list_feature_files, feature_metadata
```
**Result:** ✅ PASS — All imports resolve without error

### Test 1.3: CLI config command imports
```python
from science_cli.cli.commands.config import _cmd_set_technique, _cmd_edit_technique, _cmd_list_techniques, _cmd_list_devices
```
**Result:** ✅ PASS — All imports resolve without error

### Test 1.4: Techniques config directory path
```python
from science_cli.core.paths import get_techniques_config_dir
# Returns: /Users/tai/.config/science-cli/techniques
```
**Result:** ✅ PASS — Path resolves to correct user config directory

---

## 2. Functional Tests — Technique Config

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 2.1 | `write_technique_config('test-tech', data)` | Writes YAML file, returns Path | Written to `~/.config/science-cli/techniques/test-tech.yaml` | ✅ PASS |
| 2.2 | `load_technique_configs()` returns written config | `test-tech` in keys | `test-tech` found with matching data | ✅ PASS |
| 2.3 | `list_technique_names()` includes new technique | 12 total names | 12 names including `test-tech` | ✅ PASS |
| 2.4 | `list_technique_devices('test-tech')` returns devices | `['test-device']` | `['test-device']` | ✅ PASS |
| 2.5 | Cleanup + cache invalidation | Config removed, cache cleared | `test-tech` gone after `invalidate_cache()` + rmtree | ✅ PASS |

**Result:** ✅ 5/5 PASS

---

## 3. Functional Tests — Parquet Store

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 3.1 | `write_features(df, tmp)` | Writes .parquet, returns Path | `features.parquet` (2350 bytes) | ✅ PASS |
| 3.2 | `read_features(tmp)` | Returns 3-row DataFrame | 3 rows, 3 columns | ✅ PASS |
| 3.3 | `append_features(df3, tmp)` | Appends 1 row, total 4 | 4 rows after append | ✅ PASS |
| 3.4 | `list_feature_files(tmp)` | Lists .parquet files | `[features.parquet]` | ✅ PASS |
| 3.5 | `feature_metadata(path)` | Returns metadata dict | `num_rows: 4, num_columns: 3, columns: [...], file_size_bytes: 2367` | ✅ PASS |

**Result:** ✅ 5/5 PASS

---

## 4. Guardrail Tests

All 16 architecture guardrail tests pass:

| # | Test | Status |
|---|------|--------|
| 4.1 | `image.py` deleted | ✅ PASS |
| 4.2 | `general.py` deleted | ✅ PASS |
| 4.3 | `functions/` deleted | ✅ PASS |
| 4.4 | `__init__.py` cleaned of dead imports | ✅ PASS |
| 4.5 | `app.py` cleaned of GENERAL_COMMANDS import | ✅ PASS |
| 4.6 | COMMAND_TREE has 13 commands | ✅ PASS |
| 4.7 | All config accessors import | ✅ PASS |
| 4.8 | Config backward compat without config file | ✅ PASS |
| 4.9 | `generate_default_config_yaml()` produces valid YAML | ✅ PASS |
| 4.10 | Config with sample project file | ✅ PASS |
| 4.11 | Technique detection (8 test cases) | ✅ PASS |
| 4.12 | `load_data_file` has technique and device params | ✅ PASS |
| 4.13 | `_get_projects_root` returns Path | ✅ PASS |
| 4.14 | `discover_extensions` returns ExtensionRegistry (3 techniques) | ✅ PASS |
| 4.15 | All 12 modified files compile cleanly | ✅ PASS |
| 4.16 | All 4 documentation files exist and have content | ✅ PASS |

**Result:** ✅ 16/16 PASS

---

## 5. CLI Command Dispatching

| # | Test | Result |
|---|------|--------|
| 5.1 | `config_handler(['set', 'technique', 'iv-sweep', 'keithley-2400'])` | ✅ Dispatches to `_cmd_set_technique`, writes technique config, prints confirmation |
| 5.2 | `config_handler(['list'])` | ✅ Dispatches to `_cmd_list_techniques`, renders Rich table |
| 5.3 | `config_handler(['list', 'devices'])` (no technique) | ✅ Prints usage message, no crash |
| 5.4 | `config_handler(['set'])` (no args) | ✅ Prints usage message, no crash |
| 5.5 | `config_handler(['edit'])` (no technique) | ✅ Prints usage message, no crash |
| 5.6 | `config_handler(['unknown-sub'])` | ✅ Prints error + help, no crash |

**Result:** ✅ 6/6 PASS

---

## 6. Edge Case Tests — Parquet Store

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 6.1 | `write_features(pd.DataFrame(), tmp)` | Raises `ValueError` | `ValueError: Cannot write empty DataFrame to parquet` | ✅ PASS |
| 6.2 | `read_features('/nonexistent')` | Returns `None` | `None` | ✅ PASS |
| 6.3 | `feature_metadata('/nonexistent.parquet')` | Returns `None` | `None` | ✅ PASS |
| 6.4 | `append_features()` with duplicate rows | Deduplicates | 3 rows kept out of 6 (3 original + 3 duplicate) | ✅ PASS |

**Result:** ✅ 4/4 PASS

---

## 7. Edge Case Tests — Config Subcommands

| # | Test | Result |
|---|------|--------|
| 7.1 | `config list` — renders techniques table | ✅ Rich table with 11 techniques displayed |
| 7.2 | `config list devices <technique>` — no technique given | ✅ Friendly usage error |
| 7.3 | `config set` — no subcommand | ✅ Friendly usage error |
| 7.4 | `config edit` — no technique | ✅ Friendly usage error |
| 7.5 | `config unknown-sub` — unknown subcommand | ✅ Error message + help displayed |

**Result:** ✅ 5/5 PASS

---

## 8. Edge Case Tests — Technique Config Logic

| # | Test | Expected | Actual | Status |
|---|------|----------|--------|--------|
| 8.1 | `list_technique_devices('iv-sweep')` | Contains `keithley-2400` | `['keithley-2400']` | ✅ PASS |
| 8.2 | `list_technique_devices('nonexistent-tech')` | Empty list | `[]` | ✅ PASS |
| 8.3 | `list_technique_names()` includes hardcoded defaults | `iv-sweep`, `ec-cv`, `mem-endurance` present | All present (11 total) | ✅ PASS |
| 8.4 | `get_merged_config()` includes techniques section | `'techniques'` in merged | `'techniques'` key present | ✅ PASS |
| 8.5 | Technique config 4th layer integration | Technique configs override global but are overridden by project config | Verified via merge chain | ✅ PASS |

**Result:** ✅ 5/5 PASS

---

## 9. CHANGELOG Validation

| Check | Status |
|-------|--------|
| File exists (4596 bytes) | ✅ PASS |
| `## [2.0.0] - 2026-05-13` header present | ✅ PASS |
| `### Breaking Changes` section | ✅ PASS |
| `### Added` section | ✅ PASS |
| `### Changed` section | ✅ PASS |
| `### Removed` section | ✅ PASS |
| `### Fixed` section | ✅ PASS |
| `### Security` section | ✅ PASS |
| `### Planned` (Unreleased) section | ✅ PASS |

**Result:** ✅ PASS — Valid Keep a Changelog format

---

## Error Audit

| Severity | Count | Details |
|----------|-------|---------|
| 🔴 Critical | 0 | — |
| 🟠 Major | 0 | — |
| 🟡 Minor | 0 | — |
| 🔵 Suggestion | 1 | The `config set technique` handler writes technique configs with `default_device` placed under the technique root rather than in a `defaults:` subsection. While functional, future schema consistency could place default devices under a dedicated `defaults:` key at the config root. Non-blocking. |

---

## Detailed Observations

### Technique config merge chain (4th layer)
The `get_merged_config()` function now correctly merges 4 layers:
1. Hardcoded defaults (`_DEFAULT_TECHNIQUE_PATTERNS`, `_DEFAULT_TECHNIQUE_DEVICES`)
2. Global config (`~/.config/science-cli/config.yaml`)
3. **NEW:** Technique configs (`~/.config/science-cli/techniques/*.yaml`)
4. Per-project config (`<project_root>/sci-config.yaml`)

Verified that technique configs are injected before project config, ensuring project-level overrides take highest priority.

### Per-project devices.yaml override
The `get_device_config()` function checks `project_root / "devices.yaml"` for per-project device overrides. Verified the merge logic uses `_merge_dicts()` for deep merging.

### Parquet store robustness
All edge cases handled:
- Empty DataFrame → `ValueError` with clear message
- Missing file → `None` returned gracefully
- Append with duplicates → `drop_duplicates()` removes redundant rows
- Metadata returns typed column info including numpy dtypes

### CLI subcommand error handling
All subcommands provide helpful usage messages on incorrect invocation. No stack traces are exposed to the user.

---

## Conclusion

All tests pass across all categories:

- **Import integrity:** ✅ All new modules resolve cleanly
- **Technique config CRUD:** ✅ Write, read, list, query, cleanup all work correctly
- **Parquet round-trip:** ✅ Write, read, append, list, metadata all work correctly with proper edge case handling
- **Guardrails:** ✅ 16/16 architecture constraints satisfied
- **CLI integration:** ✅ All 3 new subcommands (`config set technique`, `config edit`, `config list techniques/devices`) dispatch correctly with proper error handling
- **Config merge chain:** ✅ 4-layer merge (hardcoded ← global ← technique configs ← project config) verified
- **CHANGELOG:** ✅ Valid Keep a Changelog format with all required sections

```
TRAFFIC LIGHT: GREEN
```
