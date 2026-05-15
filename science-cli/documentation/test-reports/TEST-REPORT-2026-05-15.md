# TEST REPORT — Sprint 8 Config Fix Regression

- **Date**: 2026-05-15
- **Project**: science-cli
- **Scope**: Sprint 8 re-test after `.format()` → `.replace()` fix in `generate_default_config_yaml()`
- **Fix Verified**: `generate_default_config_yaml()` no longer throws `KeyError` on `{date_code}` etc.

---

## 1. Smoke Tests (6/6 ✅)

| Test | Result |
|------|--------|
| `generate_default_config_yaml()` — init + first 50 chars | ✅ |
| `get_global_device_config`, `list_global_devices`, `get_global_technique_config`, `list_global_techniques` | ✅ |
| `populate_from_grammar`, `populate_protocol_from_step_dirs` (db API) | ✅ |
| `standardize_grammar_fields`, `_resolve_grammar_from_merged_config` (technique API) | ✅ |
| `_collect_device_data_from_sqlite` (dashboard API) | ✅ |
| `cmd_analyze` (device_cli API) | ✅ |

## 2. Syntax Checks (7/7 ✅)

| File | Result |
|------|--------|
| `src/science_cli/core/config.py` | ✅ |
| `src/science_cli/cli/commands/config.py` | ✅ |
| `src/science_cli/memristor/db.py` | ✅ |
| `src/science_cli/memristor/device_cli.py` | ✅ |
| `src/science_cli/memristor/dashboard.py` | ✅ |
| `src/science_cli/core/technique.py` | ✅ |
| `src/science_cli/core/data_loader.py` | ✅ |

## 3. Full Test Suite (77 ✅ / 1 ❌)

**Result: 77 passed, 1 failed** in 0.33s

| Module | Tests | Pass | Fail |
|--------|-------|------|------|
| `test_cli.py` | 13 | 13 | 0 |
| `test_core/test_config.py` | 19 | 18 | 1 |
| `test_core/test_session.py` | 15 | 15 | 0 |
| `test_core/test_technique.py` | 17 | 17 | 0 |
| `test_memristor/test_db.py` | 14 | 14 | 0 |

### ❌ Failure Detail

```
FAILED test_core/test_config.py::TestConfigDefaults::test_generate_default_config_is_valid

yaml.scanner.ScannerError: while scanning a double-quoted scalar
  in "<unicode string>", line 40, column 14:
          regex: "^(?P<date_code>\d{6})_(?P<mater ...
                 ^
  found unknown escape character 'd'
```

**Root Cause**: The YAML template in `generate_default_config_yaml()` uses double-quoted scalars for regex patterns. Python's `\\d` string literal evaluates to `\d`, which is written into the output YAML. In YAML double-quoted scalars, `\d` is **not a valid escape sequence** (valid: `\n`, `\t`, `\\`, `\"`, `\xNN`, `\uNNNN`, etc.).

**Affected lines** (in generated YAML, lines 40-41):
```yaml
      regex: "^(?P<date_code>\d{6})_..."
      regex: "^(?P<date_code>\d{6})_..."
```

Also affects `\w`, `\d` usage throughout both regex patterns.

**Fix**: Either:
1. **In Python template**: Change `\\d` → `\\\\d`, `\\w` → `\\\\w` etc. so the YAML output has `\\d` (valid YAML double-quoted escape for `\d`)
2. **Switch to YAML single quotes**: Use `'regex': '...\d...'` in YAML — single-quoted scalars treat backslashes as literal

## 4. Functional Tests (✅ ALL PASS)

### 4a. Grammar Tests (`standardize_grammar_fields`)
| Test | Result |
|------|--------|
| rNcN parsing (`r0c0` → `row=0, col=0`) | ✅ |
| Missing fields → `None` | ✅ |
| Suffix conversion (`'005'` → `5`) | ✅ |
| Empty dict input | ✅ |
| `None` suffix handling | ✅ |
| Empty string suffix | ✅ (returns `''` — minor) |
| Multi-digit matrix (`r10c99`) | ✅ |
| Matrix with only `rN` (no `cN`) | ✅ |
| Uppercase keys preserved alongside lowercase | ✅ (minor note) |

### 4b. Config Lookup Tests
| Test | Result |
|------|--------|
| `keithley-2400` device config | ✅ |
| `keysight-b1500` device config | ✅ |
| `list_global_devices()` → 2 devices | ✅ |
| `iv-sweep` technique config | ✅ |
| `list_global_techniques()` → 11 techniques | ✅ |
| Non-existent device → `None` | ✅ |
| Tab delimiter repr (`'\t'`) | ✅ |

### 4c. YAML Content Validation (generate_default_config_yaml)
| Test | Result |
|------|--------|
| `projects_root` substitution works | ✅ |
| `{6}` regex quantifier present (not `{{6}}`) | ✅ |
| No `{{6}}` double-brace artifacts | ✅ |
| `\d{6}` present in pattern | ✅ |
| **YAML parseable by `yaml.safe_load()`** | **❌ FAIL** |

## 5. Error Audit

### 🔴 Critical (0)
None.

### 🟠 Major (1)
| Issue | Location | Description |
|-------|----------|-------------|
| **Invalid YAML output** | `generate_default_config_yaml()` regex patterns | YAML double-quoted scalars contain `\d`, `\w` — unknown escape chars. `sci config init` would write unparseable config file. |

### 🟡 Minor (2)
| Issue | Location | Description |
|-------|----------|-------------|
| Empty suffix not normalized | `standardize_grammar_fields` | `suffix: ''` returns `''` instead of `None` or `0` |
| Key casing not normalized | `standardize_grammar_fields` | Uppercase input keys (e.g. `DATE_CODE`) are preserved alongside lowercase defaults — could cause silent field duplication downstream |

### 🔵 Warning (0)
None.

---

## 6. Traffic Light

**TRAFFIC LIGHT: YELLOW**

### Rationale
- **77/78 tests pass** (98.7%)
- The sole failure is in a **YAML formatting validity test** for the `sci config init` output
- The **core fix works correctly**: `{date_code}` etc. are no longer misinterpreted by `.format()`, `{projects_root}` substitution succeeds, `{6}` regex quantifiers are properly unescaped
- All **functional tests pass**: grammar parsing, device config, technique config, edge cases
- The fix resolved the intended bug (KeyError on `.format()`), but exposed a **pre-existing YAML syntax issue** in the regex template strings
- **Impact is limited** to the `config init` command — users with existing config files are unaffected; hardcoded defaults work correctly
- **Fix is straightforward**: double-escape backslashes in the YAML template (6 occurrences), or switch regex values to YAML single-quoted scalars

### Recommendation
Fix the YAML escape issue before marking GREEN. Estimated effort: < 5 minutes (one file, ~2 lines changed).
