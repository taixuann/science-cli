---
layer: [1, 2, 3, 4, 5, 7]
type: review
status: done
tags: [v3.20.0, verification, qa]
assignee: review
---

# Review Report: science-cli v3.20.0 Verification

## Summary
**YELLOW** ⚠️ — Non-critical issues found. See below.

## Results

### Step 1: Full Test Suite — ✅ PASS
```
4 failed, 572 passed, 1 warning in 5.44s
```
**Expected**: 572 passed, 4 pre-existing failures. **Matches exactly.**

Pre-existing failures (all known):
| Test | Issue |
|------|-------|
| `test_config.py::TestConfigDefaults::test_migration_script` | Migration script path |
| `test_studies.py::TestResolveLibrary::test_with_device_type` | Device type resolution |
| `test_studies.py::TestStudiesForDeviceType::test_electrochem` | Electrochem study routing |
| `test_technique.py::TestTechniqueDetection::test_detect_unknown_returns_empty` | `detect_technique("unknown.xyz")` returns `'ec-eis'` instead of `''` |

No new regressions detected.

---

### Step 2: Smoke Test (`sci info --json`) — ✅ PASS
Clean JSON output returned successfully, containing:
- Project metadata (name: `res_internship`, 2640 raw files, 12 protocols)
- Session info (last project, protocol, step, theme)
- Full protocol tree with device, step, and file listings

**🔵 Note:** The `science_cli_version` field reports **`3.9.0`** rather than `3.20.0`. This may indicate the `__version__` string in the source has not been bumped to match the release tag.

---

### Step 3: Import Check — ✅ PASS
```
All imports OK
Registry entries: 11
```
All critical imports resolve cleanly:
- `parse_set_voltage` (Keysight parser)
- `detect_waveform_pattern_2d`, `extract_waveform_metadata` (waveform analyzers)
- `STUDY_COLUMN_REGISTRY`, `get_columns_for` (fzf columns)
- `build_fzf_display` (fzf display)
- `get_metadata_config_for` (config)

---

### Step 4: Git Status — ✅ PASS (with note)
```
 M .opencode/artifacts/200626f_waveform-core-restructure.md
 M temp-src/plot_endurance_theme_r3c4.py
```
Two uncommitted files:
- `.opencode/artifacts/200626f_waveform-core-restructure.md` — plan artifact (expected, working artifact)
- `temp-src/plot_endurance_theme_r3c4.py` — temporary plotting script (non-critical)

No source code modifications pending. Clean working state for core code.

---

### Step 5: Last 5 Commits — ✅ PASS
```
fe72834 feat(scoping): add (study, device) scoping for fzf display and metadata extraction
ab99652 refactor(fzf): move fzf_columns.py + fzf_utils.py into core/fzf/ subpackage
a5d979f docs(plan): update walkthrough for Phase 5b (waveform 2D detection)
b40ecec feat(waveform): add 2D waveform pattern detection + metadata extractor
ea550b9 refactor(metadata): split core/metadata/ into parsers/ + analyzers/ by mechanism
```
All commits are on `dev` branch and consistent with v3.20.0 features:
- FZF scoping and subpackage refactor (core/fzf/)
- Waveform 2D detection and metadata extraction
- Metadata module split (parsers/ + analyzers/)

---

## Issues Found

### 🟡 Warning
1. **Version string mismatch**: `sci info --json` reports version `3.9.0`, not `3.20.0`. The `__version__` attribute in the source may need updating.

### 🔵 Info
1. **Two uncommitted files**: artifact doc + temp script — expected during development, no source changes pending.
2. **4 pre-existing test failures**: all known, no new regressions.

---

## Checklist
- [x] **Step 1** — Full test suite (572 passed, 4 failed — as expected)
- [x] **Step 2** — Smoke test (clean JSON output)
- [x] **Step 3** — Import check (all imports OK, 11 registry entries)
- [x] **Step 4** — Git status (clean core code, 2 uncommitted non-source files)
- [x] **Step 5** — Commit history (5 commits on dev, consistent with v3.20.0)

## Recommendations
1. Bump `__version__` from `3.9.0` to `3.20.0` if this release is tagged.
2. Commit or clean up the `temp-src/` file.
