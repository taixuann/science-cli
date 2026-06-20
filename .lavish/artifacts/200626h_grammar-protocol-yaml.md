---
layer: [1]
type: plan
status: in-progress
tags: [grammar, protocol, config]
depends_on: [200626g_merge-plot-config]
assignee: code
---

# Implementation Plan: Protocol-Centric Grammar Model

**Date**: 20/06/2026
**Status**: 🟠 In Progress (Phase 1-3 done, Phase 4 next)
## Context Summary

The current grammar system is distributed across:
- `config-instruments.yaml` — per-instrument `filename_patterns` (regex + template)
- `config.py` — aggregates patterns via `get_file_naming_grammar()`, `get_all_instrument_grammars()`
- `core/studies.py` — `detect_study_from_filename()` uses substring matching against patterns
- Data flow: filename → grammar pattern → detect technique → resolve study → load device config

This system was designed when study/device had to be DETECTED from filenames. Now that protocol.yaml explicitly declares device, instrument, and study per step, the grammar can be reduced to a **simple filename convention** — no regex registry, no per-instrument patterns, no config-driven detection.

## Current Reality (v3.21.0 + v7)

After config-first plot params + grammar rename exercise, **protocol.yaml** stores per-step metadata. The universal grammar now includes **instrument** in the filename, making `instrument:` in YAML redundant.

### Rename Exercise Results (144 files completed)

All 144 CSV files in `data/temp/` renamed to universal grammar:
```
DDMMYY-HHMMSS_instrument_device-id_study[_remarks][_flags].csv
```

| Category | Count | Example |
|----------|-------|---------|
| iv-bipolar-sweep | 83 | `190626-152411_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_iv-bipolar-sweep_01.csv` |
| pulse-stp-decay | 55 | `190626-161912_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_pulse-stp-decay.csv` |
| pulse-endurance | 6 | `180626-201537_keysight-b1500a_cu-c-pda(q5)-ito(2)_r5-c3_pulse-endurance.csv` |

Key decisions from the exercise:
- **Instrument is in the filename** — `_keysight-b1500a_` between timestamp and device-id
- **Device IDs normalize to lowercase** — `CU-C-PDA(Q5)-ITO(2)` → `cu-c-pda(q5)-ito(2)`
- **Iteration indices stripped** — `r5-c3(1)` → `r5-c3` (iteration number, not part of device ID)
- **Remarks preserved** — pulse params like `2V-100ns`, `2.75` kept as remarks
- **Flags cleaned** — `!` prefix removed, `small` removed, `Standard` removed
- **IV sweep timestamps** — extracted from CSV headers (`MetaData, TestRecord.RecordTime` at line ~107)

## Proposed Model

### 1. Filename Convention (universal, human-readable, no config)

```
DDMMYY-HHMMSS_instrument_device-id_study_remarks_flags_count.csv
```

| Field | Example | Mandatory | Notes |
|-------|---------|-----------|-------|
| `DDMMYY` | `200626` | Yes | Date (2-digit day, month, year) |
| `-HHMMSS` | `-122036` | Yes | Time (hour, minute, second), hyphen-separated from date |
| `_instrument` | `_keysight-b1500a` | Yes | Instrument ID (matches `config-instruments.yaml` keys) |
| `_device-id` | `_cu-c-pda(q5)-ito(2)_r3-c4` | Yes | Device identifier (material_matrix) |
| `_study` | `_pulse-endurance` | Yes | Study name (matches `studies.*.*.patterns`) |
| `_remarks` | `_initial-rerun` | No | Free-text differentiation note (pulse params, etc.) |
| `_flags` | `_flagged` | No | Status/highlight tag |
| `_count` | `_001` | No | Sequential counter for repeated tests |

This format is **human-readable, sortable by timestamp, self-documenting**. Instrument is embedded in the filename — no config needed to parse it.

### 2. protocol.yaml is the source of truth (instrument REMOVED from YAML, technique REMOVED)

```yaml
# protocol.yaml — instrument and technique are in filename/study, not YAML
device: volatile-memristor            # ONE device — the physical sample under test
steps:
  - name: 3_iv-sweep                  # step folder name
    study: iv:iv-bipolar-sweep        # study name (contains technique)
    files:
      - 190626-152411_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_iv-bipolar-sweep_01.csv
      - 190626-152411_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_iv-bipolar-sweep_02.csv
  - name: 5_pulse-endurance
    study: pulse:pulse-endurance      # study name (contains technique)
    files:
      - 180626-201537_keysight-b1500a_cu-c-pda(q5)-ito(2)_r5-c3_pulse-endurance.csv
```

Key changes:
- **`instrument:` removed** — embedded in filename via universal grammar
- **`technique:` removed** — redundant with `study:` field (study name encodes technique)
- **`study:` is the primary metadata** — format: `technique:study-name` (e.g., `iv:iv-bipolar-sweep`, `pulse:pulse-endurance`)

### 3. Resolution flow (simplified)

```
filename
  │
  ├── parse_filename() → instrument, device_id, study, remarks, flags, count
  │     ├── instrument ─────────────────→ config-instruments.yaml → parsing config
  │     ├── device_id ──────────────────→ config-devices.yaml → studies, library
  │     └── study ──────────────────────→ config-studies.yaml → technique (derived), plot
  │
  └── protocol.yaml (optional override)
        ├── device ─────────────────────→ config-devices.yaml (overrides filename)
        └── steps[].study ──────────────→ config-studies.yaml (overrides filename)
```

Key changes:
- **grammar drives everything from the filename**. protocol.yaml is optional metadata
- **technique is derived from study** — `pulse:endurance` → technique=`pulse`, study=`endurance`
- **no `technique:` field in YAML** — it's redundant with the study name

### 4. What changes in config

| Config File | Change | Reason |
|------------|--------|--------|
| `config-instruments.yaml` | **Remove** all `filename_patterns` from every instrument | No longer needed — grammar is universal |
| `config-instruments.yaml` | **Keep** instrument keys (keysight-b1500a, keithley-2400, etc.) | Still needed for parsing config (delimiter, columns, header_lines) |
| `config-devices.yaml` | No change | Device→studies mapping stays |
| `config-studies.yaml` | **Add** `column_mapping` and `current_sign` to Keysight studies | Config-based column resolution instead of hardcoding |
| `config-template.yaml` | No change | Theme system stays |

### 5. What changes in code

| File | Change | Risk |
|------|--------|------|
| `core/grammar.py` | **Update** RE pattern to include `instrument` field between timestamp and device_id | Low — already exists (269L) |
| `core/config.py` | **Remove** `get_file_naming_grammar()`, `get_instrument_grammar()`, `get_all_instrument_grammars()` | Med — need to check all callers |
| `core/config.py` | **Remove** grammar aggregation from `load_global_config()` | Low |
| `core/config.py` | **Keep** `get_file_naming_patterns()` as a thin wrapper | Low — always returns the single pattern |
| `core/protocol.py` | **Remove** `instrument:` AND `technique:` from step/file schema | Low — filename is source of truth, study contains technique |
| `core/studies.py` | **Keep** `detect_study_from_filename()` | Low — still useful fallback |
| `cli/commands/plot.py` | **Update** `_resolve_xy_columns()` to read from config instead of hardcoding | Med — config-based column mapping |
| `cli/commands/plot.py` | **Rename** "techniques" to "studies" throughout | Low — terminology update |
| `cli/commands/plot.py` | **Ensure** output filename always uses `{study}_{filename}.pdf` | Low — filename format |

### 6. Universal RE pattern (with instrument)

```python
import re

# The single pattern — works for ALL new files
_PATTERN = re.compile(
    r"^(?P<date_code>\d{6})-"
    r"(?P<timestamp>\d{6})_"
    r"(?P<instrument>[-a-z0-9]+)_"          # instrument (lowercase, hyphenated)
    r"(?P<device_id>[-A-Za-z0-9/()]+)_"
    r"(?P<study>[A-Za-z0-9/-]+)"
    r"(?:_(?P<remarks>[A-Za-z0-9.-]+))?"     # allow dots for voltage like 2.75
    r"(?:_(?P<flags>[A-Za-z0-9-]+))?"
    r"(?:_(?P<count>\d+))?"
    r"\.(?P<ext>\w+)$"
)

def parse_filename(filename: str) -> dict | None:
    m = _PATTERN.match(filename)
    if not m:
        return None
    return m.groupdict()
```

Returns `{"date_code": "200626", "timestamp": "122036", "instrument": "keysight-b1500a", "device_id": "...", "study": "pulse-endurance", "remarks": "2v-100ns", "flags": None, "count": None, "ext": "csv"}`.

### 7. Backward compatibility

Legacy files (existing naming conventions) still need detection. The current `detect_study_from_filename()` uses substring matching (not regex), which works on any naming style. This stays as an implicit fallback:

```python
def detect_study_from_filename(filename: str) -> str | None:
    """Fallback substring matching for legacy files.
    
    New files use the universal pattern → study is explicit.
    Legacy files use substring matching against studies.<tech>.<study>.patterns.
    """
```

## Phases

### Phase 1: Universal pattern + protocol.yaml ✅ DONE
- ✅ `core/grammar.py` created (269L) with `parse_filename()` + `filename_matches_convention()`
- ✅ 144 files renamed to universal grammar with instrument field
- ✅ Device IDs normalized to lowercase
- ✅ Iteration indices stripped
- ⚠️ grammar.py NOT committed to main (850 uncommitted lines on dev)

### Phase 2: Remove per-instrument grammar ✅ DONE
- ✅ Removed `filename_patterns` from all instruments in config-instruments.yaml (5 instruments, 104L → 52L)
- ✅ Removed `get_file_naming_grammar()`, `get_instrument_grammar()`, `get_all_instrument_grammars()` from config.py
- ✅ Removed `instrument:` from protocol YAML step/file schema (287 lines removed)
- ✅ Removed `technique:` from protocol YAML — redundant with `study:` field
- ✅ Added `study:` field to all steps that were missing it (iv-sweep, stp-decay)

### Phase 3: Symlink workflow + protocol YAML cleanup ✅ DONE
- ✅ Fixed 83 corrupted symlinks in `3_iv-sweep/` (removed broken, created new with correct names)
- ✅ Fixed 48 corrupted symlinks in `4_pulse-stp-decay/` (removed broken, created new with correct names)
- ✅ Fixed 6 corrupted symlinks in `5_pulse-endurance/` (removed broken, created new with correct names)
- ✅ Renamed step folder `4_stp-decay` → `4_pulse-stp-decay` for consistency
- ✅ Renamed 74 files from `stp-decay` to `pulse-stp-decay` in data/raw/
- ✅ Updated symlinks to point to renamed files
- ✅ Cleaned protocol YAML (removed 137 corrupted entries)
- ✅ Removed `technique:` fields from protocol YAML (4 lines removed)
- ✅ Added `study:` field to all steps that were missing it
- ✅ Updated pulse-endurance step with all 10 files (old + new)
- ✅ Updated 6_ppf step with correct filenames (pulse-stp-decay)
- ✅ Verified: 83 + 129 + 10 + 2 = 224 symlinks total, 0 broken
- ✅ Updated sci-file-rename skill with symlink workflow documentation

### Phase 4: Config-based column mapping ✅ DONE
- ✅ Added `column_mapping` to config-studies.yaml for all Keysight studies:
  - IV sweep: `x: voltage, y: current` (columns: V1, I2)
  - Pulse STP decay: `x: time, y: current` (columns: Time, MeasResult2_value)
  - Pulse PPF: `x: time, y: current` (columns: Time, MeasResult2_value)
  - Pulse endurance: `x: time, y: current` (columns: Time, MeasResult2_value)
- ✅ Added `current_sign: -1` to all Keysight studies (negative current for bipolar switching)
- ✅ Created artifact: `200626i_config-column-mapping.md` (plan for plot command refactor)

### Phase 5: Plot command refactor (NEXT)
- Update `_resolve_xy_columns()` to read from config instead of hardcoding
- Rename "techniques" to "studies" throughout
- Ensure output filename always uses `{study}_{filename}.pdf`

### Phase 6: Documentation + cleanup
- Update CHANGELOG, README, AGENTS.md
- Remove dead code found in audit (11 functions in config.py, library/pulse/plotting.py)
- Update sci-config-guide skill

## Agent Delegation

| Phase | Sub-agent | Notes |
|-------|-----------|-------|
| 1: Universal pattern + rename | ✅ Done | grammar.py + 144 files renamed |
| 2: Remove per-instrument grammar | ✅ Done | config-instruments.yaml, config.py cleaned |
| 3: Symlink workflow + YAML cleanup | ✅ Done | 224 symlinks fixed, protocol YAML cleaned |
| 4: Config-based column mapping | ✅ Done | column_mapping + current_sign in config-studies.yaml |
| 5: Plot command refactor | code-medium | Update _resolve_xy_columns(), rename techniques→studies |
| 6: Documentation | docs-light | CHANGELOG, README, AGENTS.md, skills |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Legacy files don't match universal pattern | High | Keep `detect_study_from_filename()` fallback indefinitely |
| Removing per-instrument grammar breaks existing workflows | Medium | Phase 2 is separate from Phase 1 — can be rolled back |
| `sci add` requires new metadata fields | Low | Make device/instrument/study optional with auto-detect fallback |
| Filename parsing moves from config to hardcoded | Low | The pattern is documented as a convention, not config — trade-off for simplicity |
| Protocol YAML files reference old filenames | ✅ Resolved | Phase 3 updated YAML with new filenames and fixed symlinks |

## Phase 3 Detail: Symlink Workflow (COMPLETED)

### Current folder structure
```
protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/
├── 2.5_cu-c-pda(n3,q4,q5)_ito(2).yaml   ← protocol YAML (cleaned)
├── 3_iv-sweep/                            ← 83 symlinks → data/raw/
├── 4_pulse-stp-decay/                     ← 129 symlinks → data/raw/
├── 5_pulse-endurance/                     ← 10 symlinks → data/raw/
├── 6_ppf/                                 ← 2 symlinks (PPF files)
└── temp/                                  ← empty (files moved to raw/)
```

### File count per step (verified)
| Step | Study | Symlinks | Target folder |
|------|-------|----------|---------------|
| 3_iv-sweep | iv:iv-bipolar-sweep | 83 | `3_iv-sweep/` |
| 4_pulse-stp-decay | pulse:pulse-stp-decay | 129 | `4_pulse-stp-decay/` |
| 5_pulse-endurance | pulse:pulse-endurance | 10 | `5_pulse-endurance/` |
| 6_ppf | pulse:stp-decay | 2 | `6_ppf/` |
| **Total** | | **224** | |

### Protocol YAML state
- Cleaned: removed 137 corrupted entries from `sci add` output
- Updated: all steps have `study:` field (format: `technique:study-name`)
- Removed: `technique:` fields (redundant with `study:`)
- Removed: `instrument:` fields (embedded in filename)
- All filenames follow universal grammar: `DDMMYY-HHMMSS_keysight-b1500a_device-id_study[_count].csv`
- `stp-decay` renamed to `pulse-stp-decay` for consistency
