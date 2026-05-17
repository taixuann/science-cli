# QA Test Report — 2026-05-17

## Context
**Refactor**: Consolidate `devices.yaml` into protocol YAML
**Branch**: `version-2.1.1`
**Test constraint**: Only used `/Users/tai/workspace/projects/active_projects/test-project/` — no real data touched.

---

## 1. Existing Test Suite
```
cd /Users/tai/workspace/tools/science-cli
python -m pytest tests/ -x -v

Result: 78 passed in 0.49s
```
**Result: ✅ PASS (78/78)**

---

## 2. Guardrail Tests
```
python -m pytest test_guardrails.py -x -v

Result: 19 passed in 0.60s
```
**Result: ✅ PASS (19/19)**

---

## 3. Protocol YAML Device Section Read/Write

| Test | Result |
|------|--------|
| `write_device_section()` returns True | ✅ PASS |
| `has_device_section()` returns True after write | ✅ PASS |
| `read_device_section()` returns correct geometry (rows=6, cols=6) | ✅ PASS |
| `write_step_enriched_files()` with sweep metadata | ✅ PASS |
| `read_step_enriched_files()` returns file + sweep_order + sweep_type + temperature | ✅ PASS |
| Edge case: `read_device_section()` on missing file returns None | ✅ PASS |
| Edge case: `has_device_section()` False when no device section | ✅ PASS |
| Edge case: `read_device_section()` on empty file returns None | ✅ PASS |
| Edge case: `read_step_enriched_files()` for nonexistent step returns [] | ✅ PASS |

**Result: ✅ PASS**

---

## 4. SQLite Schema v4

| Test | Result |
|------|--------|
| Schema version is 4 | ✅ PASS |
| All v4 columns present (sweep_order, sweep_type, sweep_segments, temperature) | ✅ PASS |
| `insert_file()` with sweep metadata succeeds | ✅ PASS |
| `query_sweep_metadata()` returns correct values | ✅ PASS |
| `update_file_sweep_metadata()` updates correctly | ✅ PASS |
| `query_sweep_metadata()` with step filter works | ✅ PASS |
| `query_sweep_metadata()` for nonexistent protocol returns [] | ✅ PASS |
| `update_file_sweep_metadata()` partial update (only sweep_segments) | ✅ PASS |
| `update_file_sweep_metadata()` with no optional fields (noop) | ✅ PASS |

**Result: ✅ PASS**

---

## 5. Backward Compat — Legacy devices.yaml Still Reads

| Test | Result |
|------|--------|
| `read_devices()` falls back to legacy `devices.yaml` when no protocol YAML | ✅ PASS |
| Returns correct DeviceGeometry (rows=4, cols=4, label="Legacy") | ✅ PASS |
| Returns correct steps mapping (`{'iv': '4_iv'}`) | ✅ PASS |

**Result: ✅ PASS**

---

## 6. Migration — Legacy → Protocol YAML

| Test | Result |
|------|--------|
| `migrate_from_devices_yaml()` reports success | ✅ PASS |
| Device geometry copied correctly (rows=6, cols=6) | ✅ PASS |
| File entries migrated with sweep metadata (sweep_order, sweep_type, temperature) | ✅ PASS |
| Migration metadata written (`_meta.migrated_from`, `_meta.migrated_at`) | ✅ PASS |

**Result: ✅ PASS**

---

## 7. Integration — Sync SQLite → Protocol YAML

| Test | Result |
|------|--------|
| `sync_sweep_to_protocol_yaml()` updates step files with sweep data | ✅ PASS |
| sweep_segments JSON deserialized to `sweep` list on file entries | ✅ PASS |
| Sync is idempotent (running twice produces same result) | ✅ PASS |
| Protocol YAML structure preserved (device section, steps intact) | ✅ PASS |

**Result: ✅ PASS**

---

## 8. CLI Smoke Test

| Module | Result |
|--------|--------|
| `science_cli.app` | ✅ PASS |
| `science_cli.core.protocol` | ✅ PASS |
| `science_cli.memristor.db` | ✅ PASS |
| `science_cli.memristor.device` | ✅ PASS |
| `science_cli.cli.commands` | ✅ PASS |
| `science_cli.cli.commands.add` | ✅ PASS |
| `science_cli.cli.commands.memristor` | ✅ PASS |
| `science_cli.cli.commands.protocol` | ✅ PASS |
| `science_cli.core.config` | ✅ PASS |
| `science_cli.core.technique` | ✅ PASS |
| `science_cli.core.data_loader` | ✅ PASS |
| `science_cli.core.sweep_metadata` | ✅ PASS |
| `science_cli.core.session` | ✅ PASS |

**Result: ✅ PASS (all 13 modules import cleanly)**

---

## 9. Data Integrity Verification

Test-project (`/Users/tai/workspace/projects/active_projects/test-project/`) verified intact:
- Protocol YAML at `protocol/1_protocol-1/1_protocol-1.yaml` — unchanged
- `devices.yaml` at `protocol/1_protocol-1/devices.yaml` — unchanged
- `test-project.db` — exists, unmodified
- `sci-config.yaml` — unchanged
- `read_devices()` correctly reads from protocol YAML (device section) or falls back to legacy

**Result: ✅ PASS**

---

## Summary

| Category | Result | Details |
|----------|--------|---------|
| 1. Existing test suite | ✅ PASS | 78/78 |
| 2. Guardrail tests | ✅ PASS | 19/19 |
| 3. Protocol YAML I/O | ✅ PASS | 9/9 |
| 4. SQLite schema v4 | ✅ PASS | 9/9 |
| 5. Backward compat | ✅ PASS | 3/3 |
| 6. Migration | ✅ PASS | 4/4 |
| 7. Integration sync | ✅ PASS | 4/4 |
| 8. CLI smoke test | ✅ PASS | 13/13 |

**Issues found: 0**

### Key Findings
1. All 78 existing tests pass with no regressions
2. All 19 guardrail tests pass
3. Protocol YAML device section read/write works correctly
4. SQLite v4 has all 4 new sweep metadata columns with CRUD operations
5. Legacy `devices.yaml` backward compatibility fully preserved
6. Migration from legacy → protocol YAML works (device geometry + file entries + metadata)
7. Sync from SQLite → protocol YAML works with sweep_segments JSON deserialization
8. No real data was modified — all tests used temporary directories

---

**TRAFFIC LIGHT: GREEN** — All tests pass, no regressions, no issues found.
