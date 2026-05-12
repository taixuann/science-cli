# PLAN: Version Bump to 2.0.0

## Classification
cleanup

## Related Plans
- [[PLAN-command-restructure]] — **blocked-by** — version bump justified by command restructuring
- [[PLAN-config-expansion]] — **blocked-by** — config changes contribute to major version
- [[PLAN-extension-interface]] — **blocked-by** — extension interface changes contribute to major version

## Status
- **Created**: 2026-05-12
- **Status**: draft
- **Branch**: cleanup/architecture-guardrails

## Objective
Bump version from 7.0.0 to 2.0.0 to reflect major command restructuring, config expansion, and extension interface changes. This is a breaking change release — old command patterns (`project list`, `project open`, etc.) will no longer work.

## Context
Current version is 7.0.0 but the command structure is being fundamentally restructured:
- `project` command removed entirely
- `open`, `ls`, `add` gain `-m project/protocol/step` modes
- `close` command added with 3-level state memory
- `ext` interface added for extensions
- Config system expanded with technique-specific configs

This warrants a major version bump. Resetting to 2.0.0 (not 8.0.0) because the previous versioning was inconsistent with actual feature maturity.

## Specification

### Version Changes

| File | Current | New |
|------|---------|-----|
| `src/science_cli/__init__.py` | `"7.0.0"` | `"2.0.0"` |
| `pyproject.toml` | `version = "7.0.0"` | `version = "2.0.0"` |

### Breaking Changes (Document in CHANGELOG)

1. **`project` command removed** — use `ls -m project`, `open -m project`, `add -m project`, `status -m project`
2. **`project migrate` removed** — nested protocol layout is now the default
3. **`close` command added** — use `close -m project`, `close -m protocol`, `close -m step`
4. **`open -m step` added** — open specific step within protocol
5. **Session state format changed** — 3-level state memory (step, protocol, project)
6. **`ext` interface added** — use `ext memristor <subcommand>` instead of `memristor <subcommand>`
7. **`memristor` command deprecated** — still works as alias, will be removed in 3.0.0

### Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/__init__.py` | Modify | Change `__version__` to `"2.0.0"` |
| `pyproject.toml` | Modify | Change version to `"2.0.0"` |
| `README.md` | Modify | Update version references, add migration notes |
| `CHANGELOG.md` | **Create** | Document breaking changes for 2.0.0 |

### CHANGELOG.md (Initial)

```markdown
# Changelog

## [2.0.0] - 2026-05-12

### Breaking Changes
- Removed `project` command. Use `ls -m project`, `open -m project`, `add -m project`, `status -m project` instead
- Removed `project migrate` subcommand. Nested protocol layout is now the default
- Session state format changed to support 3-level memory (step, protocol, project)
- `memristor` command deprecated. Use `ext memristor <subcommand>` instead

### Added
- `close -m project|protocol|step` — close context with auto-save
- `open -m step <step_id>` — open specific step within protocol
- `ext <name> <subcommand>` — unified extension command interface
- `config set technique <name> <device>` — set default device for technique
- `config edit <technique>` — open technique config in editor
- `config list techniques` — list all configured techniques
- `config list devices <technique>` — list devices for a technique
- Technique-specific config files in `~/.config/science-cli/techniques/*.yaml`
- Per-project device overrides in `<project>/devices.yaml`
- 3-level state memory with auto-save on close and restore on open

### Changed
- `ls -m project` replaces `project list`
- `open -m project` replaces `project open`
- `add -m project` replaces `project create`
- `status -m project` replaces `project status`

### Removed
- `project` command and all subcommands
- `project migrate` subcommand
- Dead code: `image.py`, `general.py`, `functions/` directory
```

## Dependencies
- PLAN-command-restructure must complete
- PLAN-config-expansion must complete
- PLAN-extension-interface must complete

## Cross-PLAN Impact
- This PLAN is the final step — it depends on all other PLANs completing first.
- No downstream PLANs depend on this one.

## Test Strategy
1. Verify `sci --version` outputs `2.0.0`
2. Verify `sci version` outputs `2.0.0`
3. Verify REPL banner shows `v2.0.0`
4. Verify CHANGELOG.md is valid markdown
5. Verify pyproject.toml version matches `__init__.py`

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
