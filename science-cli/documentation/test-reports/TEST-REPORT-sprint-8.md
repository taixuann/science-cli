# Test Report: Sprint 8 — Global Config Registry & sync/analyze Split

- **Date**: 2026-05-15
- **Project**: science-cli
- **Branch**: `refactor/2.1.0`
- **Tested by**: qa-tester (final: GREEN)

---

## 1. Smoke Tests (6/6 ✅)

| Test | Result |
|------|--------|
| `get_global_device_config`, `list_global_devices`, `get_global_technique_config`, `list_global_techniques` | ✅ PASS |
| `populate_from_grammar`, `populate_protocol_from_step_dirs` (db API) | ✅ PASS |
| `standardize_grammar_fields`, `_resolve_grammar_from_merged_config` (technique API) | ✅ PASS |
| `_collect_device_data_from_sqlite` (dashboard API) | ✅ PASS |
| `cmd_analyze` (device_cli API — new command) | ✅ PASS |
| `cmd_sync` (device_cli — pure filename parsing) | ✅ PASS |

---

## 2. Syntax Checks (7/7 ✅)

| File | Result |
|------|--------|
| `src/science_cli/core/config.py` | ✅ PASS |
| `src/science_cli/cli/commands/config.py` | ✅ PASS |
| `src/science_cli/memristor/db.py` | ✅ PASS |
| `src/science_cli/memristor/device_cli.py` | ✅ PASS |
| `src/science_cli/memristor/dashboard.py` | ✅ PASS |
| `src/science_cli/core/technique.py` | ✅ PASS |
| `src/science_cli/core/data_loader.py` | ✅ PASS |

---

## 3. Full Test Suite

**Result: 78 passed, 0 failed** (78 total)

| Module | Tests | Pass | Fail |
|--------|-------|------|------|
| `test_cli.py` | 13 | 13 | 0 |
| `test_core/test_config.py` | 19 | 19 | 0 |
| `test_core/test_session.py` | 15 | 15 | 0 |
| `test_core/test_technique.py` | 17 | 17 | 0 |
| `test_memristor/test_db.py` | 14 | 14 | 0 |

**All 78 tests pass.**

---

## 4. Functional Tests

### 4.1 `standardize_grammar_fields()`

| Test Case | Result |
|-----------|--------|
| rNcN parsing (row=0, col=0 extracted from 'r0c0') | ✅ PASS |
| Missing fields filled as None | ✅ PASS |
| Suffix string-to-int conversion ('005' → 5) | ✅ PASS |
| Empty dict returns all-None fields | ✅ PASS |
| None suffix handling | ✅ PASS |
| Empty string suffix | ✅ PASS |
| Multi-digit matrix (r10c99) | ✅ PASS |
| Matrix with only rN (no cN) | ✅ PASS |
| Uppercase keys preserved alongside lowercase | ✅ PASS |

### 4.2 Global Device/Technique Registry

| Test Case | Result |
|-----------|--------|
| `get_global_device_config('keithley-2400')` returns correct dict | ✅ PASS |
| `list_global_devices()` includes both keithley-2400 and keysight-b1500 | ✅ PASS |
| `get_global_technique_config('iv-sweep')` returns correct dict | ✅ PASS |
| `list_global_techniques()` includes all techniques | ✅ PASS |
| `get_file_naming_grammar()` returns separator='_' (hardcoded) | ✅ PASS |
| Non-existent device → None | ✅ PASS |
| Tab delimiter repr ('\t') correct | ✅ PASS |

### 4.3 DB Schema v2

| Test Case | Result |
|-----------|--------|
| SCHEMA_VERSION is 2 | ✅ PASS |
| files table created with universal grammar columns | ✅ PASS |
| technique_id, device_id, date_code, material, matrix, row, col, suffix exist | ✅ PASS |
| `insert_file()` with grammar fields | ✅ PASS |
| `update_file_analysis()` with current_compliance + compliance_confidence | ✅ PASS |
| `query_files()` with technique and material filters | ✅ PASS |
| `upsert_cells()` + `query_cells()` | ✅ PASS |
| `populate_from_grammar()` scans step dir and inserts parsed filenames | ✅ PASS |
| `populate_protocol_from_step_dirs()` scans all step dirs | ✅ PASS |

### 4.4 CLI Subcommands

| Test Case | Result |
|-----------|--------|
| `config devices list` — displays global device registry | ✅ PASS |
| `config grammar list` — shows grammar patterns | ✅ PASS |
| `config edit --global` — opens global config for editing | ✅ PASS |
| `config edit devices` — opens device registry section | ✅ PASS |
| `config edit grammar` — opens grammar patterns section | ✅ PASS |
| `config edit techniques --global` — opens technique registry section | ✅ PASS |
| `config init` — generates valid default config YAML | ✅ PASS |

### 4.5 YAML Config Generation

| Test Case | Result |
|-----------|--------|
| `generate_default_config_yaml()` — no KeyError on YAML templates | ✅ PASS |
| `projects_root` substitution works correctly | ✅ PASS |
| Regex patterns are valid YAML (single-quoted scalars) | ✅ PASS |
| `\d{6}` present in patterns | ✅ PASS |
| Output parseable by `yaml.safe_load()` | ✅ PASS |
| No `{{6}}` double-brace artifacts | ✅ PASS |

### 4.6 sync/analyze Split

| Test Case | Result |
|-----------|--------|
| `memristor sync` — pure filename parsing, populates SQLite metadata | ✅ PASS |
| `memristor analyze` — reads CSVs, computes Vset/Vreset/ratio | ✅ PASS |
| `memristor analyze --force` — re-analyzes cached files | ✅ PASS |
| `update_file_analysis()` — updates SQLite analysis columns | ✅ PASS |
| Dashboard reads SQLite first, falls back to CSV | ✅ PASS |

### 4.7 Global Device Fallback

| Test Case | Result |
|-----------|--------|
| `_resolve_device_config()` falls back to global device registry | ✅ PASS |
| `data_loader.load_data_file()` with global device config | ✅ PASS |

---

## 5. Bug Fixes Verified

| Bug | Status | Details |
|-----|--------|---------|
| `generate_default_config_yaml()` KeyError on `{date_code}` | ✅ FIXED | Changed from `.format()` to `.replace()` — YAML template braces preserved |
| Invalid YAML regex `\d` escape in double-quoted scalars | ✅ FIXED | Regex patterns now use single-quoted YAML scalars (`'...'`) |
| `standardize_grammar_fields(None)` raises TypeError | ✅ FIXED | Callers always pass dict; input validation added |

---

## 6. Error Audit

### Critical (0)

None.

### Major (0)

None.

### Minor (1)

| # | Issue | Severity | Notes |
|---|-------|----------|-------|
| M1 | New CLI subcommands not shown in help text (config devices, config grammar) | Minor | These commands work correctly but aren't listed in `--help` output yet |

### Warnings (0)

None.

---

## 7. Traffic Light

**TRAFFIC LIGHT: GREEN**

### Rationale

- **78/78 tests pass (100%)**
- All Sprint 8 features are implemented and tested:
  - **Global Config Registry**: 4-tier config with global device/technique registry
  - **Universal Grammar Fields**: 5 standardized fields, hardcoded `_` separator
  - **sync/analyze split**: `memristor sync` = pure filename parsing; `memristor analyze` = CSV computation
  - **SQLite auto-construction**: `populate_from_grammar()` without YAML intermediate
  - **SQLite v2 schema**: Universal grammar columns (technique_id, device_id, date_code, material, matrix, row, col, suffix)
  - **Config subcommands**: `config edit --global`, `config devices`, `config grammar`
  - **Dashboard SQLite fast path**: `_collect_device_data_from_sqlite()`
  - **Global device fallback**: `data_loader.py` resolves from global registry
- **Two bugs fixed** during the sprint:
  - `generate_default_config_yaml()` `KeyError` on `{date_code}` — fixed by switching from `.format()` to `.replace()`
  - Invalid YAML regex escape (`\d` in double-quoted scalars) — fixed by switching to single-quoted scalars
- No blocking issues remain. The single minor issue (help text not updated for new subcommands) does not affect functionality.
