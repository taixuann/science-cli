# PLAN: Protocol CLI Fixes (5 Issues)

## Classification
feature / bugfix

## Related Plans
- [[280526_refactor]] — related (protocol YAML structure)
- [[280526_dashboard]] — affected (SQLite sync needs metadata awareness)

## Status
- **Created**: 2026-05-30
- **Status**: draft
- **Branch**: dev

## Objective
Fix 5 usability issues in the protocol CLI (`edit`, `delete`, `ls` commands) identified during dev branch testing.

## Context

During protocol workflow testing on dev branch, the following issues emerged:

1. **`edit -m protocol --step + -d` creates duplicate step entries** instead of updating existing ones (`edit_cmd.py:185-198` appends unconditionally).
2. **No `\n` support in descriptions** — `\n` is stored literally; Rich table cells don't render multiline text.
3. **No device/technique validation** — any string is accepted for `-d`/`-t` with no warning if it's not in the registry.
4. **Commas in protocol names are replaced with `_`** — `n2,q3` becomes `n2_q3` because `sanitize_protocol_name` doesn't allow `,`.
5. **PVD/fabrication steps need metadata** — instead of file lists, PVD steps should support params like power, rate, thickness.

## Specification

### Issue #1: `--step` creates duplicates

**Problem**: `edit_cmd.py:185-198` always appends new step entries when `--step` is given, even if steps with those names already exist. The subsequent `-t`/`-d` assignment then creates duplicate entries.

**Fix**: When `--step` is provided alongside `-d` or `-t`, check if each step name already exists in `data["steps"]`. If it does, update its `technique`/`device` fields in-place. Only append if the step doesn't exist.

```python
# Logic change:
for i, sn in enumerate(step_names):
    existing = next((s for s in data["steps"] if s["name"] == sn), None)
    if existing:
        if i < len(techs): existing["technique"] = techs[i]
        if i < len(devs):  existing["device"] = devs[i]
    else:
        entry = {"name": sn}
        if i < len(techs): entry["technique"] = techs[i]
        if i < len(devs):  entry["device"] = devs[i]
        data["steps"].append(entry)
        step_dir = paths.step_dir(safe_name, sn)
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "results").mkdir(parents=True, exist_ok=True)
```

### Issue #2: `\n` in descriptions

**Problem**: `\n` sequences typed in CLI (e.g., `--desc "line1\nline2"`) are stored as literal `\n` and displayed literally in Rich table cells.

**Fix (3 parts)**:
1. **Storage** (`edit_cmd.py`): Convert `\n` (`\\n` → `\n`) in description strings before saving. YAML's block scalar `|` handles multiline strings when `default_flow_style=False`.
2. **Table display** (`ls_cmd.py:250`): Replace newlines with `↵` symbol or space in table cells (Rich can't do multiline table rows).
3. **Footer display** (`ls_cmd.py:253`): Keep newlines intact — `console.print` handles them fine outside tables.

### Issue #3: Device/technique hints

**Problem**: `-d autolab-usth` or `-t ec-cv` accepts any string with no validation. Users can mistype device/technique names silently.

**Fix**: In `edit_cmd.py` (both `_edit_protocol` and `_edit_metadata`), add validation after parsing `-t`/`-d`:
- Import `list_global_devices()`, `list_global_techniques()` from `core.config`
- Check each value against known lists
- Print a `[yellow]Warning:[/yellow]` for unknown values (don't block — just warn)

Display a hint listing available values when a warning fires:
```
Warning: 'autolab-usth' not in global device registry
Known devices: keithley-2400, keysight-b1500, horiba-usth
```

### Issue #4: Comma in protocol names

**Problem**: `sanitize_protocol_name("5.3_cu-c-pda(n2,q3)")` → `5.3_cu-c-pda(n2_q3)`.

**Fix**: Add `,` to the allowed character set in `sanitize_protocol_name()` (`paths.py:24`). Protocol names are passed via the single-valued `-n` flag — never parsed as comma-separated lists — so there's no flag ambiguity.

```python
def sanitize_protocol_name(name: str) -> str:
    return sanitize_name(name, "._(),")
```

### Issue #5: PVD/fabrication step metadata

**Problem**: PVD (and other fabrication steps like AFM) currently show `—` for files with no way to capture deposition parameters.

**Fix**: Add a `params` dict field to step entries in the YAML:
```yaml
- name: 3_pvd
  technique: pvd
  device: ebeam-evaporator
  params:
    material: Ta
    thickness_nm: 50
    rate_angstrom_s: 1.0
    power_kw: 10
```

New CLI flag `--param` (repeatable or comma-separated `key=value`):
```
edit -m protocol -n 5.3 --step 3_pvd --param material=Ta --param thickness_nm=50
```

Display params in the Description column of `ls -m protocol --step`:
```
thickness: 50nm, rate: 1.0Å/s, material: Ta
```

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/cli/commands/edit_cmd.py` | Modify | Fix #1 (#185-198 dedup), Fix #2 (\\n→newline), Fix #3 (validation), Fix #5 (--param) |
| `src/science_cli/cli/commands/delete_cmd.py` | Modify | Fix #1 (add `--rm-step` for cleanup) — already exists, verify |
| `src/science_cli/cli/commands/ls_cmd.py` | Modify | Fix #2 (newline rendering in table), Fix #5 (show params column) |
| `src/science_cli/core/paths.py` | Modify | Fix #4 (add `,` to `sanitize_protocol_name`) |
| `documentation/AGENTS_SCHEMA.md` | Update | Document new `--param` flag, new device/technique validation |

## Dependencies

- Fix #1 blocks the workflow — without it, `edit -m protocol -d` corrupts the protocol YAML with duplicates
- Issues #2–5 are independent of #1 and each other

## Cross-PLAN Impact

- PVD metadata params should be excluded from SQLite sync (they're not measurement files)
- Dashboard may need to show PVD params in step cards

## Test Strategy

- **#1**: Create protocol, `edit -m protocol --step X -d Y` twice, verify no duplicates
- **#2**: `edit -m protocol -n test --desc "a\nb"`, verify YAML has multiline string and table shows `a↵b`
- **#3**: `edit -m protocol -n test -t nonexistent`, verify warning message
- **#4**: Create protocol `test(a,b)`, verify YAML file is `test(a,b).yaml`
- **#5**: `edit --param material=Ta --param thickness=50`, verify YAML has `params` dict and ls shows it

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] Fix #1: `--step` dedup in edit_cmd.py
- [ ] Fix #2: `\n` support in descriptions
- [ ] Fix #3: Device/technique validation
- [ ] Fix #4: Comma in protocol names
- [ ] Fix #5: PVD/metadata params
- [ ] Cleanup: Fix duplicate steps in 5.3_cu-c-pda(n2_q3)
- [ ] Test all fixes
- [ ] COMMIT done
