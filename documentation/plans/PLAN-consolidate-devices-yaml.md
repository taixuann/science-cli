# PLAN: Consolidate devices.yaml into Protocol YAML

## Classification
refactor

## Related Plans
- [[PLAN-device-step-metadata]] — affected (both touch protocol YAML steps schema)
- [[PLAN-enhanced-dashboard]] — affects (dashboard data collection sources change)

## Status
- **Created**: 2026-05-17
- **Status**: completed
- **Branch**: version-2.1.1

## Objective
Consolidate `devices.yaml` (crossbar geometry, step mapping, per-cell point data) into the protocol YAML + SQLite, adding device geometry to protocol YAML and enriching file entries with sweep metadata. Eliminate `devices.yaml` as a write target while keeping backward-compat reads.

## Context

### Current Data Duplication
| Data | In Protocol YAML | In devices.yaml |
|------|-----------------|-----------------|
| Step names | `steps[].name` | `steps:` keys (technique→dir) |
| Technique per step | `steps[].technique` | Derived from `steps:` keys |
| Device per step | `steps[].device` | ❌ |
| Files per step | `steps[].files[]` (plain strings) | Per-cell `techniques[].files[]` (rich dicts) |
| Device geometry | ❌ | `device.{rows,cols}` |
| Sweep metadata | ❌ | `FileEntry.{sweep, sweep_order, sweep_type, temperature}` |
| Per-cell matrix points | ❌ | `points[]` with row/col/techniques |
| Material tags | ❌ | `MatrixPoint.tags[]` |

### SQLite Already Handles...
- Per-cell file→position mapping (via grammar filename parsing)
- Per-file analysis results (v_set, v_reset, ratios via `analyze`)
- Protocol metadata (rows, cols, materials)
- Fast-path dashboard reads

### What devices.yaml Still Provides
1. Device geometry (`rows`, `cols`) — moves to protocol YAML
2. Step technique→dir mapping — already in protocol YAML (reverse mapping)
3. **Sweep metadata** (sweep segments, sweep_type, sweep_order, temperature, plot filenames) — ONLY in devices.yaml per-file entries
4. Material tags per cell — reconstructable from filenames
5. Per-cell point matrix — reconstructable from SQLite

## Specification

### Part A: Fix ca-deposition / ca-doping Technique Recognition
These techniques exist as protocol steps but lack proper grammar patterns and technique definitions. Add them so they are recognized by grammar-based filename parsing and `detect_technique()`.

#### Changes:
1. **`src/science_cli/core/technique.py`** — `PATTERNS` / `BUILTIN_TECHNIQUES`:
   - Add `"ca-deposition"` pattern: `[r"_ca-deposition", r"ca-deposition_"]`
   - Add `"ca-doping"` pattern: `[r"_ca-doping", r"ca-doping_"]`

2. **`src/science_cli/core/config.py`** — `_DEFAULT_GLOBAL_TECHNIQUES`:
   - Add `ca-deposition` with `grammar_codes: ["ca-deposition", "ca_dep"]`
   - Add `ca-doping` with `grammar_codes: ["ca-doping", "ca_doping"]`

3. **`src/science_cli/core/technique.py`** — `HARDCODED_GRAMMAR.patterns`:
   - Add regex patterns for both techniques (with and without named `technique` capture group)

4. **`src/science_cli/memristor/db.py`** — `MEMRISTOR_TECHNIQUES`:
   - Keep `ca-deposition` and `ca-doping` OUT (they are not memristor techniques; they are fabrication/electrochem steps)

### Part B: Protocol YAML Schema Extension
Extend `protocol/<name>/<name>.yaml` with:
```yaml
name: 1_pda-memristor
description: "PDA memristor characterization"

# NEW: Device geometry (for crossbar projects)
device:
  rows: 6
  cols: 6
  label: "6x6 PDA Crossbar"   # optional
  cell_area_um2: 2500          # optional

steps:
  - name: 1_deposition
    technique: pvd
  - name: 2_afm
    technique: afm
  - name: 3_eis
    technique: ec-eis
    device: biologic-mpt
  - name: 4_iv
    technique: iv-sweep
    device: keithley-2400
    # ENRICHED: files entries become dicts with sweep metadata
    files:
      - file: 0505_Ta-PDA-ITO(1)_r0c0_IV-DC_uc_01.csv
        sweep_order: 1
        sweep_type: uc
        temperature: 300.0
        sweep:
          - direction: "0V -> 5V"
            sweep_rate_v_s: 0.1
            voltage_range: 5.0
            duration_s: 50.0
      - file: 0505_Ta-PDA-ITO(1)_r0c0_IV-DC_f_02.csv
        sweep_order: 2
        sweep_type: f
        sweep:
          - direction: "0V -> 5V"
            sweep_rate_v_s: 0.1
            voltage_range: 5.0
            duration_s: 50.0
          - direction: "5V -> -5V"
            sweep_rate_v_s: 0.1
            voltage_range: 10.0
            duration_s: 100.0
          - direction: "-5V -> 0V"
            sweep_rate_v_s: 0.1
            voltage_range: 5.0
            duration_s: 50.0
  - name: 5_endurance
    technique: mem-endurance
    device: keithley-2400
    files:
      - 0505_Ta-PDA-ITO(1)_endurance_01.csv
```

**Key rules:**
- `device:` section is OPTIONAL — non-crossbar projects omit it
- `steps[].files[]` entries remain BACKWARD COMPAT: plain strings still valid, dicts with `file:` key also valid
- `steps[].technique` is the canonical technique→step mapping (reverse it for step→technique)
- No per-cell matrix points in protocol YAML — filename parsing + SQLite handle this

### Part C: CLI Command Updates

#### `memristor init` — Writes to Protocol YAML
New interface:
```bash
memristor init --matrix r6-c6 --pt <protocol-name> --step 4_iv,5_endurance [--label "My Device"]
```
Where:
- `--matrix r6-c6` → sets `device: {rows: 6, cols: 6}` in protocol YAML
- `--pt <protocol-name>` → which protocol YAML to update (defaults to current session protocol)
- `--step <dir1,dir2,...>` → step subdirectory names; technique is auto-inferred from protocol YAML's `steps[].technique` or from filename detection
- `--label` → optional device label

**Behavior:**
1. Resolve protocol YAML path
2. Read existing protocol YAML
3. Add/update `device:` section with rows/cols
4. Build step mapping from `steps[].name` + `steps[].technique` in protocol YAML
5. Save protocol YAML
6. **No longer creates `devices.yaml`**

#### Other CLI Commands — Read from Protocol YAML + SQLite
- `memristor ls` — read device geometry from protocol YAML; per-cell data from SQLite
- `memristor stats` — read geometry from protocol YAML; coverage from SQLite
- `memristor info --row --col` — query SQLite for cell data
- `memristor check` — compare SQLite file list vs disk
- `memristor plot` — read sweep metadata from protocol YAML `steps[].files[].*`
- `memristor dashboard` — already uses SQLite fast path; fallback reads protocol YAML

#### `memristor sync` — Sweep Metadata Pipeline
1. Populate SQLite from step dirs (grammar parsing) — existing behavior
2. **NEW**: Read sweep metadata from CSVs → store in SQLite
3. **NEW**: Sync sweep metadata back to protocol YAML `steps[].files[].*` entries

Data flow: `CSV files → SQLite (source of truth) → protocol YAML (human-readable sync)`

### Part D: Backward Compat & Migration

#### Reading (Backward Compat)
1. `read_devices()` → first try protocol YAML for `device:` section + sweep-enriched `steps[].files[]`; fall back to legacy `devices.yaml`
2. A new `_migrate_devices_yaml()` function: on first `memristor init` or `memristor sync`, if legacy `devices.yaml` exists:
   - Copy `device:` geometry to protocol YAML
   - Copy sweep metadata from per-cell entries into protocol YAML `steps[].files[]` entries
   - Add `_migrated_from: "devices.yaml"` meta field

#### Writing (New Only)
1. `write_devices()` → **removed**. No more writing to `devices.yaml`.
2. Protocol YAML becomes the sole YAML write target.

#### DeviceConfig Data Model (`device.py`)
- Keep `DeviceConfig`, `DeviceGeometry`, `MatrixPoint`, etc. for in-memory use
- Add `read_device_from_protocol_yaml(protocol_dir)` function
- `read_devices()` becomes a dispatcher: try protocol YAML first → fall back to legacy

### Part E: SQLite Schema Extension
Add columns to `files` table for sweep metadata sync:
- `sweep_order INTEGER`
- `sweep_type TEXT`
- `sweep_segments TEXT` — JSON array of segment dicts
- `temperature REAL`
- `plot_figure_path TEXT` (already exists)

This makes SQLite the canonical store. A `sync_sweep_to_protocol_yaml()` function writes these back to the protocol YAML.

## Files to Modify

### Config/Grammar Fix (Part A)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/technique.py` | Edit — `PATTERNS`, `BUILTIN_TECHNIQUES`, `HARDCODED_GRAMMAR` | Add ca-deposition, ca-doping technique detection + grammar |
| `src/science_cli/core/config.py` | Edit — `_DEFAULT_GLOBAL_TECHNIQUES` | Add technique definitions with grammar_codes |

### Protocol YAML + Device Model (Part B)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/paths.py` | Edit — `protocol_yaml` docstring | Document new `device:` field |
| `src/science_cli/memristor/device.py` | Edit — `read_devices()` | Try protocol YAML first; fall back to legacy devices.yaml |
| `src/science_cli/memristor/device.py` | Edit — `write_devices()` | Mark deprecated; `memristor init` writes protocol YAML instead |
| `src/science_cli/memristor/device.py` | Add — `read_device_from_protocol_yaml()` | New function to read geometry + sweep metadata from protocol YAML |
| `src/science_cli/memristor/device.py` | Add — `sync_sweep_to_protocol_yaml()` | Sync SQLite sweep data back to protocol YAML file entries |
| `src/science_cli/memristor/device.py` | Add — `_migrate_devices_yaml()` | One-time migration from legacy devices.yaml |

### CLI Updates (Part C)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_init()` | Write to protocol YAML (`--pt`, `--matrix`, `--step`); stop creating devices.yaml |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_ls()` | Read geometry from protocol YAML; cell data from SQLite |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_info()` | Query SQLite instead of devices.yaml |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_stats()` | Read geometry from protocol YAML; coverage from SQLite |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_sync()` | After SQLite populate, sync sweep metadata back to protocol YAML |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_plot()` | Read sweep metadata from protocol YAML files entries |
| `src/science_cli/memristor/device_cli.py` | Edit — `cmd_check()` | Use SQLite file map instead of devices.yaml |
| `src/science_cli/memristor/device_cli.py` | Edit — build_parser() | Add `--pt`, `--matrix`, `--step` to init subparser |

### SQLite Schema (Part E)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/db.py` | Edit — `CREATE_FILES` DDL | Add `sweep_order`, `sweep_type`, `sweep_segments`, `temperature` columns |
| `src/science_cli/memristor/db.py` | Edit — `insert_file()` | Accept new sweep fields |
| `src/science_cli/memristor/db.py` | Edit — `populate_protocol_from_step_dirs()` | Also populate sweep columns during sync |
| `src/science_cli/memristor/db.py` | Edit — schema migration | Bump SCHEMA_VERSION, add ALTER TABLE for existing DBs |

### Dashboard & Others (Read-Only Consumers)
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/dashboard.py` | Minor edit | `_collect_device_data` — try protocol YAML sweep first, fall back to legacy |
| `src/science_cli/cli/commands/ls_cmd.py` | Edit — `_device_crossref()` | Read device summary from protocol YAML instead of devices.yaml |
| `src/science_cli/cli/help.py` | Edit | Update help text for `memristor init` new flags |

## Dependencies
None — all preceding work (version-2.1.1) is committed.

## Cross-PLAN Impact
- [[PLAN-device-step-metadata]] — this PLAN supersedes the previous approach (devices.yaml was the target of step-metadata changes; now protocol YAML is)
- [[PLAN-enhanced-dashboard]] — dashboard reads from SQLite (unchanged); the devices.yaml fallback path should be updated to also read protocol YAML

## Test Strategy

### Unit Tests
1. `test_technique_detection_ca.py` — test `detect_technique()` matches `ca_doping_01.csv`, `0505_Ta-PDA-ITO_ca-deposition_01.csv`
2. `test_grammar_parse_ca.py` — test `parse_filename_grammar()` extracts technique from ca-doping/ca-deposition filenames
3. `test_read_device_from_protocol_yaml.py` — test reads geometry + sweep metadata from extended protocol YAML
4. `test_backward_compat_read_devices_yaml.py` — test legacy devices.yaml still reads correctly

### Integration Tests
1. `test_memristor_init_to_protocol_yaml.py`:
   - Create project + protocol
   - `memristor init --matrix r6-c6 --pt <name> --step 4_iv,5_endurance`
   - Verify protocol YAML has `device: {rows: 6, cols: 6}`
   - Verify no `devices.yaml` created
2. `test_memristor_sync_sweep_to_protocol_yaml.py`:
   - Sync CSV files → SQLite → protocol YAML sweep entries
   - Verify sweep metadata in protocol YAML

### Existing Tests
- All existing tests in `tests/` must continue to pass
- `test_guardrails.py` — must pass

## Summary of Implementation

### New File: `src/science_cli/core/protocol.py`
- `read_device_section()`, `write_device_section()`, `has_device_section()` — manage optional `device:` block in protocol YAML
- `read_step_enriched_files()`, `write_step_enriched_files()` — backward-compatible file entries with sweep metadata
- `migrate_from_devices_yaml()` — one-time migration from legacy `devices.yaml`

### Schema v4: `src/science_cli/memristor/db.py`
- SCHEMA_VERSION bumped from 3 to 4
- New columns: `sweep_order INTEGER`, `sweep_type TEXT`, `sweep_segments TEXT`, `temperature REAL`
- v3→v4 migration via ALTER TABLE
- New functions: `update_file_sweep_metadata()`, `query_sweep_metadata()`
- `insert_file()` accepts new sweep params

### Protocol YAML Integration: `src/science_cli/memristor/device.py`
- `read_devices()` tries protocol YAML first, falls back to legacy `devices.yaml`
- `_read_from_protocol_yaml()` reads geometry from `device:` section + per-cell data from SQLite
- `write_devices()` emits `DeprecationWarning` (still functional)
- New: `sync_sweep_to_protocol_yaml()`, `_migrate_devices_yaml()`

### CLI Updates: `src/science_cli/memristor/device_cli.py`
- `cmd_init()` writes device section to protocol YAML (no longer creates `devices.yaml`)
- `cmd_init()` accepts `--pt`/`--protocol` flag
- `cmd_ls()`, `cmd_info()`, `cmd_stats()` gain None-check for empty config
- `cmd_sync()` calls `sync_sweep_to_protocol_yaml()` after SQLite populate
- `cmd_plot()`, `cmd_check()`, `_sqlite_reindex()` updated error messages

### Backward Compatibility Preserved
- Legacy `devices.yaml` still read correctly (fallback path)
- `write_devices()` still functional (deprecated, warning emitted)
- `cmd_add`, `cmd_add_pattern`, `cmd_add_fzf` unchanged
- `dashboard.py` unchanged (already uses SQLite fast path)
- All 97 tests pass (78 unit + 19 guardrail)

## Cross-PLAN Impact
- [[PLAN-device-step-metadata]] — superseded by this consolidation (protocol YAML replaces devices.yaml as the metadata target)
- [[PLAN-enhanced-dashboard]] — dashboard reads from SQLite (unchanged); the devices.yaml fallback now reads protocol YAML via `read_devices()`

## Progress
- [x] PLAN created (this document)
- [x] User approved
- [x] Part A: Config/Grammar fix — ca-deposition, ca-doping
- [x] Part B: Protocol YAML schema + device model changes
- [x] Part C: CLI command updates (init, ls, info, stats, sync, plot)
- [x] Part D: Backward compat + migration
- [x] Part E: SQLite schema extension
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
