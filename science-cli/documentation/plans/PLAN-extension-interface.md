# PLAN: Extension Command Interface

## Classification
extension

## Related Plans
- [[PLAN-command-restructure]] — **was blocked-by** — is now superseded by Sprint 2; GROUP 4 refined
- [[PLAN-version-bump]] — **affects** — extension interface contributed to version 2.0.0
- [[PLAN-enhanced-dashboard]] — **supersedes** — Sprint 2 removed extensions command and memristor alias

## Status
- **Created**: 2026-05-12
- **Status**: superseded (fully implemented; GROUP 4 further refined in Sprint 2)
- **Branch**: mysci-tui_update

## Objective
Create unified `ext <name> <subcommand>` interface for extension commands. Replace direct extension commands (like `memristor`) with central dispatch. Extensions register subcommands via `ExtensionRegistry`. Keep extensions as separate packages but expose through unified interface.

## Context
Currently, extensions expose commands directly in COMMAND_TREE (e.g., `memristor` → `memristor_handler`). This creates inconsistency — each extension has its own top-level command. A unified `ext` interface provides:
- Consistent command pattern: `ext <name> <subcommand> [flags]`
- Easier extension discovery
- Cleaner COMMAND_TREE
- Future-proof for merging extensions into core later

## Specification

### Command Interface

```bash
# Unified extension dispatch
ext <extension_name> <subcommand> [flags]

# Examples
ext memristor init
ext memristor ls
ext memristor add --name device1
ext memristor info --id device1
ext memristor sync
ext memristor validate
ext memristor stats
ext memristor rm --id device1
ext memristor check

# Future extensions (when science-iv, science-electrochem are integrated)
ext iv analyze --file data.csv
ext electrochem eis-fit --file data.mpt --circuit RRC
```

### Extension Registration

Extensions register subcommands via `ExtensionRegistry`:

```python
from science_cli.extensions import ExtensionRegistry

def register(registry: ExtensionRegistry):
    registry.name = "science-memristor"
    registry.short_name = "memristor"  # used in `ext memristor ...`
    registry.subcommands = {
        "init": {"handler": init_handler, "desc": "Initialize device database"},
        "ls": {"handler": ls_handler, "desc": "List devices"},
        "add": {"handler": add_handler, "desc": "Add new device"},
        "info": {"handler": info_handler, "desc": "Show device info"},
        "sync": {"handler": sync_handler, "desc": "Sync device data"},
        "validate": {"handler": validate_handler, "desc": "Validate device data"},
        "stats": {"handler": stats_handler, "desc": "Show device statistics"},
        "rm": {"handler": rm_handler, "desc": "Remove device"},
        "check": {"handler": check_handler, "desc": "Check device health"},
    }
```

### Backward Compatibility

During transition, keep `memristor` as an alias that delegates to `ext memristor`:

```python
# In COMMAND_TREE (temporary)
"memristor": {"handler": lambda args: ext_handler(["memristor"] + args), "desc": "Alias: ext memristor"},
```

This was removed in Sprint 2. All users must use `ext memristor <subcommand>` now.

### Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `cli/commands/ext.py` | **Create** | New ext handler with subcommand dispatch |
| `cli/commands/__init__.py` | Modify | Add `ext` to COMMAND_TREE, add `memristor` alias |
| `extensions.py` | Modify | Add `short_name`, `subcommands` to ExtensionRegistry |
| `cli/help.py` | Modify | Add ext command help, list extension subcommands |
| `cli/commands/memristor_cmd.py` | Modify | Wrap as alias to ext handler (temporary) |

### Command Groups (GROUP 4 — updated in Sprint 2)

```
GROUP 4: EXTENSIONS & TECHNIQUES
  ext <name> <subcommand>   Extension commands (unified interface)
  techniques                List available techniques
```

Note: `extensions` and `memristor` were removed as top-level commands in Sprint 2. Use `ext list` to list extensions, `ext memristor` to run memristor commands.

### Extension Discovery

`extensions` command output updated to show subcommands:

```
Installed Extensions:
  science-memristor (ext memristor)
    init      Initialize device database
    ls        List devices
    add       Add new device
    info      Show device info
    sync      Sync device data
    validate  Validate device data
    stats     Show device statistics
    rm        Remove device
    check     Check device health
```

## Dependencies
- PLAN-command-restructure must complete first (GROUP 4 definition, COMMAND_TREE changes)

## Cross-PLAN Impact
- **PLAN-command-restructure**: This PLAN adds `ext` to COMMAND_TREE. Command restructuring removes `project` — no conflict.
- **PLAN-config-expansion**: Both modify `extensions.py` — need to ensure technique config registration and subcommand registration don't conflict.

## Test Strategy
1. Verify `ext memristor <subcommand>` dispatches correctly
2. Verify `extensions` command lists subcommands
3. Verify `memristor` alias works (backward compat)
4. Verify extension registration with `short_name` and `subcommands`
5. Verify help text shows extension subcommands
6. Verify error handling for unknown extension/subcommand
7. Run `test_guardrails.py` — all tests must pass

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
