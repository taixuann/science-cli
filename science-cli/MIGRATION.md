# Migration Guide: 1.x → 2.0.0

Version 2.0.0 introduced breaking changes. This guide helps you migrate your workflow.

## Command Changes

| Before (1.x) | After (2.0.0) |
|---|---|
| `project list` | `ls -m project` |
| `project open <name>` | `open -m project <name>` |
| `project create <name>` | `add -m project <name>` |
| `project status` | `status -m project` |
| `project migrate` | Removed |
| `extensions list` | Removed (extensions are built-in) |
| `memristor <subcmd>` | `memristor <subcmd>` (unchanged, was an alias) |

## Session State

Session file format changed to support 3-level state memory (project → protocol → step).
Old `session.json` files will still load — missing fields default to empty.

## File Format Support

- `.lvm` (LabVIEW Measurement) format is no longer detected by default
- Use Keithley 2400 CSV/TXT or Keysight Clarius+ CSV formats
- Filenames should follow: `DDMMYY_material_type_matrix_suffix`

## Config Changes

Technique configs now live in `~/.config/science-cli/techniques/*.yaml`:
```bash
# Old: no way to configure technique per project
# New:
config set technique iv-sweep keithley-2400
config edit iv-sweep
```

## If You Were Using Extensions

Extensions are now integrated as built-in modules:
- `science-memristor` → `src/science_cli/memristor/`
- `science-iv` → `src/science_cli/iv/`
- `science-electrochem` → `src/science_cli/electrochem/`

No separate extension install needed.
