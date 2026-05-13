# QA Test Report — Sprint 3: Cross-Protocol Dashboard

**Date:** 2026-05-13  
**Branch:** `mysci-tui_update`  
**Test Suite:** Cross-Protocol Dashboard (Sprint 3)  
**Tester:** qa-tester agent

---

## Summary

| Phase | Status |
|-------|--------|
| 1. Import Check | ✅ PASS |
| 2. Guardrail Tests (16/16) | ✅ PASS |
| 3. Smoke Test — Empty Project | ✅ PASS |
| 4. CLI Flags Smoke Test | ✅ PASS |
| 5. Integration Test — Mini Project | ✅ PASS |
| 6. Compile Check | ✅ PASS |
| — HTML Structure & Content | ✅ PASS |
| — Edge Cases | ✅ PASS |
| **TRAFFIC LIGHT** | **🟢 GREEN** |

---

## 1. Import Check

```python
from science_cli.memristor.dashboard import (
    generate_dashboard,
    generate_cross_protocol_dashboard,
    collect_cross_protocol_data,
    _build_cross_protocol_html,
)
```
**Result:** ✅ All imports OK

## 2. Guardrail Tests

All 16 architecture guardrail tests pass:
- Deleted files confirmed removed (`image.py`, `general.py`, `functions/`)
- Clean imports (`__init__.py`, `app.py`)
- COMMAND_TREE has 13 commands
- Config accessors, backward compat, YAML generation
- Technique detection (8 test cases)
- Extension registry with 3 techniques
- All 12 modified files compile cleanly
- All 4 documentation files exist

**Result:** ✅ 16/16 PASS

## 3. Smoke Test — Empty Project

| Test | Result |
|------|--------|
| `collect_cross_protocol_data()` on empty project | Returns 0 protocols (no crash) |
| `generate_cross_protocol_dashboard()` on empty project | Raises `ValueError` with helpful message |
| Cache JSON written with 0 protocols | ✅ Written correctly |

**Result:** ✅ PASS

## 4. CLI Flags Smoke Test

| Flag | Present |
|------|---------|
| `--all` | ✅ |
| `--force` | ✅ |

Dashboard CLI `--help` renders correctly:
```
usage: device_cli.py dashboard [-h] [--step-dir STEP_DIR] [--output OUTPUT]
                               [--open] [--all] [--force]
```

**Result:** ✅ PASS

## 5. Integration Test — Mini Project (2 Protocols)

### Data Collection
| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Protocols detected | 2 | 2 | ✅ |
| PDA-1 devices | 2 | 2 | ✅ |
| PDA-2 devices | 1 | 1 | ✅ |
| Total files | 3 | 3 | ✅ |
| Median Vset | ~0.8–1.2 V | 0.869 V | ✅ |

### Cache Behavior
- Cache file written: ✅
- Cache reuse (no re-analysis): ✅
- Force re-analysis: ✅

### HTML Generation Checks
| Check | Status |
|-------|--------|
| Plotly CDN included | ✅ PASS |
| KPI cards present (`kpi-card` class) | ✅ PASS |
| Protocol selector (`<select>` element) | ✅ PASS |
| Material filter text | ✅ PASS |
| Toggle switches | ✅ PASS |
| Heatmap references | ✅ PASS |
| CSS dark theme (`--bg-deep`) | ✅ PASS |
| JavaScript (`_CROSS_PROTOCOL_JS` / functions) | ✅ PASS |

### HTML Structural Checks
| Check | Status |
|-------|--------|
| DOCTYPE declaration | ✅ PASS |
| HTML tag | ✅ PASS |
| Head / Body sections | ✅ PASS |
| Protocol dropdown | ✅ PASS |
| Heatmap div / Plotly reference | ✅ PASS |
| No stack traces in output | ✅ PASS |
| Balanced `<div>` tags | ✅ PASS |

**Result:** ✅ PASS

## 6. Compile Check

| File | Status |
|------|--------|
| `src/science_cli/memristor/dashboard.py` | ✅ OK |
| `src/science_cli/memristor/device_cli.py` | ✅ OK |
| `src/science_cli/cli/commands/memristor_cmd.py` | ✅ OK |

## 7. Additional Verifications

| Check | Result |
|-------|--------|
| `_CROSS_PROTOCOL_JS` exists (20835 chars) | ✅ Contains heatmap draw/update functions |
| Empty protocol subdirectory | ✅ 0 protocols, no crash |
| `devices.yaml` with empty `points` list | ✅ 0 devices, no crash |
| Missing `results/` directory | ✅ Auto-created, no crash |
| Bad YAML in `devices.yaml` | ⚠️ Unhandled `yaml.ParserError` with stack trace (minor — pre-existing behavior, not a Sprint 3 regression) |

---

## Error Audit

| Severity | Count | Details |
|----------|-------|---------|
| 🔴 Critical | 0 | — |
| 🟠 Major | 0 | — |
| 🟡 Minor | 1 | Bad YAML in `devices.yaml` produces full stack trace from `yaml.ParserError`. The `collect_cross_protocol_data()` function delegates to `read_devices()` which does not catch YAML parse errors. This is pre-existing behavior shared with `generate_dashboard()`. Consider wrapping in a future cleanup sprint. |
| 🔵 Suggestion | 0 | — |

---

## Conclusion

All functional tests pass across all categories:

- **Import integrity:** ✅ No broken module references
- **Guardrails:** ✅ 16/16 architecture constraints satisfied
- **Happy path:** ✅ Full pipeline from protocol scan → data collection → cache → HTML generation works with 2 protocols, 3 IV files
- **Edge cases:** ✅ Empty projects, missing directories, empty YAML points all handled gracefully
- **CLI integration:** ✅ `--all` and `--force` flags registered and displayed in help
- **HTML quality:** ✅ Valid document structure with Plotly, KPIs, heatmaps, dark theme, and interactive controls
- **Compilation:** ✅ No syntax errors in any modified file

---

```
TRAFFIC LIGHT: GREEN
```
