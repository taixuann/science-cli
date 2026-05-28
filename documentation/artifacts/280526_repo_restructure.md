# PLAN: Repo Reorganization & Agent File Split

## Classification
cleanup | refactor | docs

## Related Plans
- None

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: refactor/repo-cleanup

## Objective
Remove the outdated `scripts/` folder completely, rename and relocate `MIGRATION.md` to `documentation/README-1.0.0.md`, and split the monolithic `AGENTS.md` file into separate, modular, gitignored files: `AGENTS.md` (router), `RULES.md` (guardrails/workflows), and `SCHEMA.md` (architecture).

## Context
The root of the repository contains several files and directories that are either outdated (`scripts/`), reference/guide material (`MIGRATION.md`), or monolithic developer guides (`AGENTS.md`). Completely removing `scripts/`, grouping guides into `documentation/` as `README-1.0.0.md`, and modularizing agent guidance will make the project structure cleaner and easier to maintain. Furthermore, keeping these agent-only reference documents (`AGENTS.md`, `RULES.md`, `SCHEMA.md`) gitignored ensures they do not pollute the git history.

## Specification

1. **Remove scripts**: Delete the `/scripts/` folder completely.
2. **Move and rename migration guide**: Rename `/MIGRATION.md` to `/documentation/README-1.0.0.md` and delete the old `/MIGRATION.md`.
3. **Split AGENTS.md**:
   - `AGENTS.md` (Router/Index): Serves as the main index that routes agents to `RULES.md` and `SCHEMA.md`. Includes current backlog/gaps and basic orientation instructions.
   - `RULES.md` (Guardrails/Workflow): Contains critical developer constraints ("NEVER delete user code", "Always commit and update") and detailed step-by-step session workflows (Phases 0-5). It will also emphasize planning requirements and how to structure plans.
   - `SCHEMA.md` (System Architecture): Contains directory map, CLI command patterns, theme extensions, config registry, and CodeGraph integration guide. It will explain that plans must always be created very carefully, checking `.codegraph` and project information before any execution, and that plans are named as artifacts in `DDMMYY_<short_topic>.md` format.
4. **Update `.gitignore`**: Add `/RULES.md` and `/SCHEMA.md` to the blocklist.
5. **Update Guardrail Tests**: Modify `/tests/test_guardrails.py` to point to `documentation/README-1.0.0.md` instead of `MIGRATION.md`, and ensure it expects the reorganized structure.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `MIGRATION.md` | [DELETE] | Replaced by `documentation/README-1.0.0.md` |
| `documentation/README-1.0.0.md` | [NEW] | Renamed migration guide for 1.x -> 2.0.0 |
| `scripts/` | [DELETE] | Remove outdated scripts folder completely |
| `AGENTS.md` | Modify | Rewrite as modular router and index |
| `RULES.md` | [NEW] | House strict guardrails and session workflow |
| `SCHEMA.md` | [NEW] | House directory map, configurations, and CodeGraph guide |
| `.gitignore` | Modify | Gitignore new `RULES.md` and `SCHEMA.md` files |
| `tests/test_guardrails.py` | Modify | Update paths to match new locations of README-1.0.0.md and check for AGENTS.md |

## Dependencies
None

## Cross-PLAN Impact
None

## Test Strategy
- Execute `pytest tests/test_guardrails.py` to ensure all structural changes are compliant with project guardrails.

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT done
- [x] TEST passed
- [x] DOCS updated
- [x] COMMIT done
