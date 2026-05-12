# PLAN: Config Expansion

## Classification
config

## Related Plans
- [[PLAN-command-restructure]] — **blocked-by** — depends on new command structure and GROUP 3 definition
- [[PLAN-version-bump]] — **affects** — config changes contribute to version 2.0.0 justification

## Status
- **Created**: 2026-05-12
- **Status**: draft
- **Branch**: cleanup/architecture-guardrails

## Objective
Expand `config` command to handle technique-specific configs (patterns, devices, delimiters, headers) stored as per-technique YAML files. Add `config set technique`, `config edit` subcommands. Integrate with existing 3-tier config system.

## Context
The current config system (`core/config.py`) supports 3-tier merging (hardcoded ← global ← project) but only handles themes and device configs inline. Users need to configure technique-specific settings: filename patterns, default devices, delimiters, decimal separators, header lines, column mappings. These should be stored as per-technique YAML files for easy editing.

## Specification

### Technique Config Structure

Global technique configs live in `~/.config/science-cli/techniques/<technique>.yaml`:

```yaml
# ~/.config/science-cli/techniques/iv-sweep.yaml
patterns: ["*IV*", "*iv*", "*sweep*"]
header_marker: "Voltage"
default_device: keithley-2400

devices:
  keithley-2400:
    delimiter: "\t"
    decimal: "."
    header_lines: 15
    encoding: "utf-8"
    columns:
      voltage: "SourceV"
      current: "MeasureI"
  keithley-clarius:
    delimiter: ","
    decimal: "."
    header_lines: 8
    encoding: "utf-8"
    columns:
      voltage: "V"
      current: "I"
```

### Per-Project Device Override

Per-project `devices.yaml` in project root overrides technique-level device configs:

```yaml
# <project_root>/devices.yaml
keithley-2400:
  delimiter: "\t"
  header_lines: 20          # override global
  columns:
    voltage: "SMU1V"        # project-specific column names
    current: "SMU1I"
```

**Resolution order:**
1. Per-project `devices.yaml` (highest priority)
2. Technique config `devices:` section
3. Global config `techniques.<name>.devices:` section
4. Hardcoded defaults in `data_loader.py`

### Config Command Subcommands

```bash
# Existing (unchanged)
config set theme <name>           # Set active theme
config show                       # Show merged config
config init                       # Generate default config.yaml

# New
config set technique <name> <device>   # Set default device for technique
config edit <technique>                # Open technique config in $EDITOR
config list techniques                 # List all configured techniques
config list devices <technique>        # List devices for a technique
```

### Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `cli/commands/config.py` | Modify | Add `set technique`, `edit`, `list` subcommands |
| `core/config.py` | Modify | Add technique config loading from `~/.config/science-cli/techniques/*.yaml` |
| `core/technique.py` | Modify | Read patterns from technique config files |
| `core/data_loader.py` | Modify | Read device config from technique config + per-project devices.yaml |
| `core/paths.py` | Modify | Add `techniques_dir()` method for config path resolution |

### Integration Points

- **`core/technique.py`**: `detect_technique()` reads patterns from technique config files, falls back to hardcoded `PATTERNS`
- **`core/data_loader.py`**: `load_data_file()` reads device config from technique config, falls back to auto-detection
- **`extensions.py`**: At discovery time, technique configs are registered into `ExtensionRegistry` alongside Python extensions

### Backward Compatibility

- If `~/.config/science-cli/techniques/` directory doesn't exist, system behaves identically to today
- All hardcoded values remain as fallbacks
- Existing `~/.config/science-cli/config.yaml` continues to work

## Dependencies
- PLAN-command-restructure must complete first (new command groups, `config` is in GROUP 3)

## Cross-PLAN Impact
- **PLAN-command-restructure**: This PLAN adds subcommands to `config` handler. No conflict — command restructuring only changes `project` → `-m` modes.
- **PLAN-extension-interface**: Technique configs and extension interface both register into `ExtensionRegistry`. Need to ensure no duplicate registration.

## Test Strategy
1. Verify technique config loading from `~/.config/science-cli/techniques/*.yaml`
2. Verify per-project `devices.yaml` override works
3. Verify `config set technique` writes to correct YAML file
4. Verify `config edit <technique>` opens correct file in editor
5. Verify `config list techniques` shows all configured techniques
6. Verify technique detection uses config patterns before hardcoded
7. Verify data loading uses device config from technique config
8. Verify backward compatibility (no config = same behavior as today)

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
