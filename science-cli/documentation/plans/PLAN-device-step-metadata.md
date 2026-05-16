# PLAN: Device as First-Class Step Property + Config Merge Fix

## Classification
feature / fix

## Related Plans
- [[PLAN-config-expansion]] — **affects** — config merge fix improves the 4-tier config system
- [[PLAN-tui-fzf-pty]] — **affects** — further fzf TUI improvements using subprocess dispatch

## Status
- **Created**: 2026-05-16
- **Status**: completed
- **Branch**: refactor/2.1.0

## Objective
Make `-d`/`--device` a first-class CLI flag for protocol step metadata (matching the existing `-t`/`--technique` pattern), add `--matrix` shorthand to `memristor init`, and fix config merge so user's `config.yaml` values correctly override hardcoded defaults.

## Context

### Config Merge Bug
`get_global_device_config()` in `core/config.py` was returning early from hardcoded defaults — if a device existed in `_DEFAULT_GLOBAL_DEVICES`, the global config.yaml `devices:` section was never consulted. So a user setting `header_lines: 21` in `~/.config/science-cli/config.yaml` for `keithley-2400` was silently ignored; the hardcoded `23` always won. Same issue in `get_device_config()` — the global device registry was not overlaid before per-project overrides.

### `-d`/`--device` for Steps
Protocol steps already had `name` and `technique` properties. Adding `device` as a third property creates a complete **step → technique → device** triplet, matching the real experimental workflow where a specific instrument is used for a specific measurement.

### `memristor init` UX
`memristor init` required `--rows` and `--cols` and `--label`. The new `--matrix r6-c6` shorthand is more intuitive for crossbar matrices, and `--label` auto-generates when omitted.

## Specification

### 1. Config Merge Fix (`core/config.py`)

**`get_global_device_config()`**:
- Start with hardcoded defaults as a base dict
- Overlay with user's `~/.config/science-cli/config.yaml` → `devices:` section via `.update()`
- Return merged result (or None if not found in either)
- Previously: returned hardcoded OR global, never both merged

**`get_device_config()`**:
- After resolving per-technique device config, overlay with global device registry (from `config.yaml → devices:`)
- Then apply per-project `devices.yaml` overrides as before
- Previously: global device registry was skipped for per-technique lookups

### 2. `memristor init` (`device_cli.py`)

- Add `--matrix rN-cN` argument (e.g. `--matrix r6-c6` → rows=6, cols=6)
- Parse via regex `r(\d+)[-.]c(\d+)`
- Make `--rows`/`--cols` `default=None` instead of `required=True`
- Make `--label` `default=""` instead of `required=True`
- Auto-generate label as `"{rows}x{cols} crossbar"` when `--label` is empty

### 3. `-d`/`--device` Flag

**`add.py` — `_add_protocol`**:
- Read `-d`/`--device` flag, comma-separated (matching `-t`/`--technique`)
- Store `device` key in step entries alongside `name` and `technique`
- Each step gets device from the corresponding position in the comma-separated list

**`add.py` — `_add_metadata`**:
- Read `-d`/`--device` flag
- Technique is no longer required (can set device without technique)
- Merge device into existing step entries or new ones
- Update output message to show devices when provided

**`edit_cmd.py` — `_edit_protocol`**:
- Read `-d`/`--device` flag
- When `--device` is provided without `--step`, modify existing steps' device field without adding new steps
- When both provided, new steps get device from the list

**`edit_cmd.py` — `_edit_metadata`**:
- Read `-d`/`--device` flag
- Match steps by name and update their device field

**`ls_cmd.py` — `_ls_protocol`**:
- Add "Device" column to the steps table (yellow styling)
- Show `—` when no device is set

### 4. fzf Subprocess Dispatch (`tui/app.py`)

- Remove `_TeeWriter` class (no longer needed)
- For fzf commands in TUI: stop application mode → `subprocess.run()` in a separate Python process → start application mode
- This avoids all asyncio nesting issues with questionary and fzf

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/config.py` | Modify | Fix config merge: overlay global config on top of hardcoded defaults |
| `src/science_cli/memristor/device_cli.py` | Modify | Add --matrix shorthand, optional --label |
| `src/science_cli/cli/commands/add.py` | Modify | Add -d/--device flag to _add_protocol and _add_metadata |
| `src/science_cli/cli/commands/edit_cmd.py` | Modify | Add -d/--device flag to _edit_protocol and _edit_metadata |
| `src/science_cli/cli/commands/ls_cmd.py` | Modify | Add Device column in protocol step listing |
| `src/science_cli/core/fzf_utils.py` | Modify | Use subprocess.Popen with /dev/tty stderr instead of pty.spawn |
| `src/science_cli/tui/app.py` | Modify | Subprocess dispatch for fzf, remove _TeeWriter |
| `src/science_cli/memristor/plotting.py` | Modify | Remove start/end scatter markers from time-colored IV |

## Dependencies
- None

## Test Strategy
1. **Config merge**: Verify `get_global_device_config('keithley-2400')` returns merged dict with user's `header_lines` from config.yaml overriding hardcoded `23`
2. **memristor init**: Verify `--matrix r6-c6` sets rows=6, cols=6; verify `--label` auto-generates; verify `--rows`/`--cols` still work
3. **-d/--device**: Verify `add -m protocol -d keithley-2400` stores device in step; verify `ls -m protocol --step` shows Device column; verify `edit -m protocol -d` updates existing steps
4. **fzf**: Verify fzf works in CLI, TUI suspend, and REPL

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
