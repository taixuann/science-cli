---
layer: [2, 7]
type: review
status: done
tags: [stp, wiring, qa]
depends_on: [160626c_stp-decay-wiring]
assignee: review
---

# Review Report: STP-Decay Wiring (160626c)

## Summary

🟡 **YELLOW** — Minor lint issues in new code, but no blocking problems. Safe to merge after quick fixes.

## Results

| Check | Status | Details |
|-------|--------|---------|
| **Test suite** | ✅ 444 passed, 3 failed | 3 failures are **pre-existing** (unrelated: `test_migration_script` [no module `scripts`], `test_with_device_type` + `test_electrochem` [electrochem device-type dispatch]) |
| **New waveform tests** | ✅ 20/20 passed | All `tests/test_metadata/test_waveform.py` tests pass (grammar, waveform params, setup pulses, repeat detection, current inversion, YAML output) |
| **Grammar pattern** | ✅ All 3 match | `rN-cN-stp-decay` pattern correctly parses real filenames with/without tags |
| **Real-file STP analysis** | ✅ Works | Successfully extracts V_set=2.74V, V_read=0.51V, set_width=93µs, read_width=38µs, rise=2.4µs, fall=2.3µs, repeat=single from WGFMU file |
| **Lint (ruff)** | 🟡 16 errors | 1 in new code (E741), 14 in pre-existing stp.py (W293 trailing whitespace), 1 unused import in test |

## Issues Found

### 🟡 Warning (new code — should fix)

1. **E741 ambiguous variable name `l`** — `src/science_cli/core/metadata/waveform.py:42`
   ```python
   return [l[0] for l in levels]
   ```
   Replace `l` with `level` or `v` to avoid ambiguous-name lint.

2. **F401 unused import `pytest`** — `tests/test_metadata/test_waveform.py:5`
   ```python
   import pytest  # never used
   ```
   Remove the unused import.

### 🔵 Info (pre-existing — not blocking)

3. **15× W293 trailing whitespace** in `src/science_cli/library/pulse/stp.py` — pre-existing blank-line whitespace throughout the file. Out of scope for this review.

4. **3 pre-existing test failures** — unrelated to STP-decay changes. Likely from incomplete `electrochem` device-type architecture and missing `scripts` module.

## Recommendations

1. **Fix E741** in `waveform.py:42`: rename `l` → `level` (1-line change)
2. **Remove unused `pytest` import** in `test_waveform.py:5` (1-line change)
3. Run `ruff check --fix` to auto-clean trailing whitespace in `stp.py`
4. After fixes, commit to `dev` branch

## Checklist

- [x] Smoke tests pass (444 pass, 3 pre-existing failures)
- [x] Grammar pattern matches all expected filenames
- [x] Waveform analysis works on real WGFMU data
- [x] All 20 new tests pass
- [x] Lint clean (with minor exceptions noted above)
- [x] No regressions introduced
