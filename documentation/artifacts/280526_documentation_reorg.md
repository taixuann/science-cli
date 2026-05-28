# PLAN: Documentation Reorganization & Sandbox Testing Guidelines

## Classification
cleanup | refactor | docs

## Related Plans
- [[280526_repo_restructure]] — related — continuation of repository cleanup

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: refactor/documentation-cleanup

## Objective
Rename `documentation/plans/` to `documentation/artifacts/`, delete unused folders (`prompts/` and `test-reports/`), build a structured `documentation/library/` containing subfolders for each technique, and establish strict guidelines in `RULES.md` and `SCHEMA.md` to:
- Run and test projects inside the sandboxed `active_projects/test-project/` folder.
- Execute all code changes on branch `dev` (NEVER touch branch `main`).
- Adhere to the strict 6-step workflow: `Making Artifacts` ➔ `Action-Code` ➔ `Review-Testing with CodeGraph` ➔ `Command Update` ➔ `Update Documents` ➔ `Commit`.

## Context
Reorganizing directories under `documentation/` creates a cleaner, more logical partition between transient workspace plans (now called "artifacts") and structured characterization reference guides (now called "library"). In addition, standardizing sandbox tests to run under `active_projects/test-project/` ensures that execution testing does not clutter the root workspace with temporary analysis/project files. Working strictly on branch `dev` with a precise 6-step code pipeline guarantees repository health and pristine branching structures.

## Specification

1. **Rename Plans Directory**: Rename `documentation/plans/` to `documentation/artifacts/`.
2. **Delete Unused Directories**: Completely remove `documentation/prompts/` and `documentation/test-reports/`.
3. **Build Technique Library**:
   - Create `documentation/library/` directory.
   - Create subfolders under it: `memristor/`, `electrochem/`, `iv/`, `raman/`, and `uv-vis/`.
   - Relocate files under `documentation/guides/` into `documentation/library/`:
     - Move `documentation/guides/memristor.md` to `documentation/library/memristor/memristor.md`.
     - Move `documentation/guides/electrochemistry.md` to `documentation/library/electrochem/electrochemistry.md`.
     - Move `documentation/guides/installation.md` to `documentation/library/installation.md`.
     - Delete the empty `documentation/guides/` folder.
4. **Update Developer Rules & Workflow**:
   - Update `RULES.md` and `SCHEMA.md` to mandate that sandbox execution tests must run inside `active_projects/test-project/`.
   - Add the strict branching constraint to `RULES.md`: Always commit and push on branch `dev`; never touch branch `main` under any circumstances.
   - Document the strict 6-step workflow pipeline:
     1. **Making Artifacts**: Create plan artifact under `documentation/artifacts/DDMMYY_<short_topic>.md`.
     2. **Action-Code**: Execute codebase edits carefully.
     3. **Review-Testing with CodeGraph**: Perform call/dependency analysis using CodeGraph context and verify logic.
     4. **Command Update**: If a CLI command is added or modified, update its COMMAND_TREE registration, CLI parsing, and help menu.
     5. **Update Documents**: Refactor READMEs, guides, and plans.
     6. **Commit**: Stage and commit immediately on `dev`.
   - Update `AGENTS.md` and `SCHEMA.md` to reflect `documentation/artifacts/` and `documentation/library/` paths, and add future consideration for grouping technique-specific code in `src/science_cli/library/`.
5. **Verify Guardrails**: Execute the guardrail test suite to ensure that all documentation compiles and complies with clean repository layout checks.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `documentation/plans/` | Rename | Rename to `documentation/artifacts/` |
| `documentation/prompts/` | [DELETE] | Delete unused directory |
| `documentation/test-reports/` | [DELETE] | Delete unused directory |
| `documentation/guides/` | Move/Delete | Move files to `documentation/library/` subfolders and delete guides directory |
| `AGENTS.md` | Modify | Update plans/ to artifacts/ references |
| `RULES.md` | Modify | Update workflow rules for artifacts/ and sandbox testing in `active_projects/test-project/` |
| `SCHEMA.md` | Modify | Update Directory Map, planning artifacts guidelines, and library reference structures |

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
