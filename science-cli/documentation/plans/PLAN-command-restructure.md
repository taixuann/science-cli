# PLAN: Command Restructuring

## Classification
command-restructure

## Related Plans
- [[PLAN-config-expansion]] — **blocks** — config expansion depends on new command structure (config subcommands reference new modes)
- [[PLAN-extension-interface]] — **blocks** — extension interface depends on COMMAND_TREE changes
- [[PLAN-version-bump]] — **affects** — command restructuring justifies version bump to 2.0.0

## Status
- **Created**: 2026-05-12
- **Status**: draft
- **Branch**: cleanup/architecture-guardrails

## Objective
Restructure commands so `open`, `ls`, `add`, `close` support `-m project`, `-m protocol`, `-m step` modes. Remove `project` command entirely. Add 3-level state memory with auto-save on close and restore on open.

## Context
Currently, `project` is a standalone command with subcommands (list, open, create, status, migrate). This creates inconsistency — other commands use `-m` mode flags. The session only tracks project + protocol, not step. Closing doesn't save state. Re-opening doesn't restore last state.

## Specification

### Command Changes

| Old Command | New Command | Mode |
|-------------|-------------|------|
| `project list` | `ls -m project` | List all projects |
| `project open <name>` | `open -m project <name>` | Open project, set session context |
| `project create` | `add -m project <name>` | Create new project |
| `project status` | `status -m project` | Show current project stats |
| `project migrate` | **removed** | Migrate is obsolete (nested layout is default) |
| `open -m protocol <name>` | `open -m protocol <name>` | **unchanged** |
| `ls -m protocol` | `ls -m protocol` | **unchanged** |
| `add -m protocol <name>` | `add -m protocol <name>` | **unchanged** |

### New Commands

**`close -m <level>`** — Close context at specified level with auto-save:
- `close -m step` — Close step context, remain in protocol + project. Save last step state.
- `close -m protocol` — Close protocol context, remain in project. Save last protocol state.
- `close -m project` — Close project context, return to global. Save last project state.

**`open -m step <step_id>`** — Open specific step within current protocol. Sets session context to step level.

### State Memory (3 Levels)

Session state (`~/.config/science-cli/session.json`) expanded:

```json
{
  "last_project": "res_internship",
  "last_protocol": "doping",
  "last_step": "4_iv-characterization",
  "project_state": {
    "res_internship": {
      "last_protocol": "doping",
      "last_step": "4_iv-characterization",
      "last_files": ["deviceA_IV.txt"],
      "last_command": "plot -f deviceA_IV.txt"
    }
  },
  "protocol_state": {
    "doping": {
      "last_step": "4_iv-characterization",
      "last_files": ["deviceA_IV.txt"],
      "last_command": "plot -f deviceA_IV.txt"
    }
  }
}
```

**Auto-save behavior:**
- On `close -m step`: save step context to `protocol_state[protocol].last_step`
- On `close -m protocol`: save protocol context to `project_state[project].last_protocol`
- On `close -m project`: save project context to top-level `last_project`
- On `open -m project <name>`: restore `project_state[name]` if exists
- On `open -m protocol <name>`: restore `protocol_state[name]` if exists

### Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `cli/commands/open_cmd.py` | Modify | Add `-m project`, `-m step` modes; restore state on open |
| `cli/commands/close.py` | **Create** | New close handler with 3 modes, auto-save logic |
| `cli/commands/ls_cmd.py` | Modify | Add `-m project` mode (list projects) |
| `cli/commands/add.py` | Modify | Add `-m project` mode (create project) |
| `cli/commands/status.py` | **Create** | New status handler for `-m project` mode |
| `cli/commands/__init__.py` | Modify | Remove `project` from COMMAND_TREE, add `close`, `status` |
| `cli/commands/project.py` | **Delete** | Replaced by `-m` modes in other commands |
| `cli/help.py` | Modify | Update help text for new command groups |
| `core/session.py` | Modify | Add 3-level state memory, auto-save, restore logic |
| `app.py` | Modify | Update REPL dispatch for new commands |

### Command Groups (Updated)

```
GROUP 1: File Management
  add -m project <name>     Create project
  add -m protocol <name>    Create protocol
  add -m data               Assign data files
  ls -m project             List projects
  ls -m protocol            List protocols
  ls -m step                List steps
  delete                    Delete protocol/metadata
  edit                      Edit protocol/metadata

GROUP 2: Navigation
  open -m project <name>    Open project
  open -m protocol <name>   Open protocol
  open -m step <step_id>    Open step
  close -m project          Close project (auto-save)
  close -m protocol         Close protocol (auto-save)
  close -m step             Close step (auto-save)

GROUP 3: Data Analysis
  plot                      Plot data
  analyze                   Analyze data
  config                    Configure themes, techniques

GROUP 4: Extensions & Special
  techniques                List techniques
  extensions                List installed extensions
  ext <name> <subcommand>   Extension commands
  memristor                 Memristor device management
  results                   List saved results

ADDITIONAL
  help                      Show help
  version                   Show version
  clear                     Clear screen
  history                   Show command history
```

## Dependencies
None — this is the foundational change that other PLANs depend on.

## Cross-PLAN Impact
- **PLAN-config-expansion**: This PLAN changes command structure. Config expansion's `config set technique` and `config edit` subcommands will reference the new command groups.
- **PLAN-extension-interface**: This PLAN removes `project` from COMMAND_TREE. Extension interface adds `ext` to COMMAND_TREE — both modify `__init__.py`.
- **PLAN-version-bump**: Command restructuring is the primary justification for version 2.0.0.

## Test Strategy
1. Verify all 14 existing commands still work after removing `project`
2. Verify `open -m project`, `open -m step` work correctly
3. Verify `close -m project`, `close -m protocol`, `close -m step` auto-save state
4. Verify re-open restores last saved state
5. Verify `ls -m project` lists projects correctly
6. Verify `add -m project` creates projects correctly
7. Verify session.json structure is backward-compatible (old sessions still load)
8. Run `test_guardrails.py` — all 16 tests must pass

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
