# PLAN: Artifact Reorganization & Core System Plans

## Classification
cleanup | docs | refactor

## Related Plans
- [[280526_documentation_reorg]] — related — continuation of documentation cleanup and folder structure refinement.
- [[280526_repo_restructure]] — related — final phase of cleaning root-level files and structuring reference guides.

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Establish a clean, organized `documentation/artifacts/` folder by moving historical legacy plans and reports to a new `archive/` subdirectory, and construct three brand-new, detailed date-prefixed plans in `documentation/artifacts/` covering:
1. **AI Integration (`280526_ai_integration.md`)**: Full specifications for machine-readable CLI commands, the JSON schema, the `sci chat` router, and guidelines for LLM agent interaction.
2. **Dashboard & Plotting (`280526_dashboard.md`)**: Detailed plans for the Textual TUI dashboard, plot engine, overlays, themes, templates, and session memory.
3. **Structure Refactoring (`280526_refactor.md`)**: Architectural plans to consolidate technique-specific source modules under a unified `src/science_cli/library/` directory.

## Context
Over many iterative development cycles, `documentation/artifacts/` has accumulated 23 legacy plan and test report files. Archiving these into a dedicated `archive/` subfolder will dramatically clean up the active plan workspace, ensuring developers and agent systems focus strictly on current, date-prefixed plan files. In addition, we will author three robust, date-prefixed plans to layout upcoming premium features and code reorganizations.

## Specification

1. **Create Archive Subdirectory**:
   - Create the directory `documentation/artifacts/archive/`.

2. **Move Legacy Plan & Report Files**:
   - Move all 22 historical files matching `PLAN-*.md` from `documentation/artifacts/` to `documentation/artifacts/archive/`.
   - Move `test-report-enhanced-dashboard.md` from `documentation/artifacts/` to `documentation/artifacts/archive/`.
   - Keep only the active date-prefixed plans (`280526_repo_restructure.md`, `280526_documentation_reorg.md`, and these new plan files) in the top-level `documentation/artifacts/` directory.

3. **Construct Core System Plans**:
   - Create `documentation/artifacts/280526_ai_integration.md`:
     - Specifications for `sci info --json`, `sci ls --json`, and `sci status --json`.
     - System workflow and schema definitions for external LLM-driven agents like `plotting-guy`.
     - Intent-routing capabilities of the `sci chat` router.
   - Create `documentation/artifacts/280526_dashboard.md`:
     - Visual and functional specs for the Textual TUI dashboard (`tui/app.py`).
     - Overlay capabilities (`sci plot --overlay`), custom styling flags, publication-quality themes, and templates.
     - Triple-tier session memory context tracking (project -> protocol -> step).
   - Create `documentation/artifacts/280526_refactor.md`:
     - Step-by-step plan to relocate standalone technique directories (`memristor/`, `electrochem/`, `iv/`, etc.) from the source root to `src/science_cli/library/` (e.g. `src/science_cli/library/memristor/`).
     - Import update tracking and dependency mapping across the CLI and plot engine.

4. **Update Main Index and Schema Files**:
   - Update `AGENTS.md`, `RULES.md`, and `SCHEMA.md` to reference `documentation/artifacts/archive/` and index the three new plan files.

5. **Verify Guardrail Compliance**:
   - Update and execute the test suite `pytest tests/test_guardrails.py` to verify all documentation and structural checks pass.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `documentation/artifacts/PLAN-*.md` (22 files) | Move | Archive legacy plan files to `documentation/artifacts/archive/` |
| `documentation/artifacts/test-report-*.md` (1 file) | Move | Archive legacy test report to `documentation/artifacts/archive/` |
| `documentation/artifacts/280526_ai_integration.md` | [NEW] | Detailed workspace plan for AI agent systems and command schemas |
| `documentation/artifacts/280526_dashboard.md` | [NEW] | Detailed workspace plan for plotting engine, dashboard TUI, and templates |
| `documentation/artifacts/280526_refactor.md` | [NEW] | Detailed architectural plan for code restructuring under src/science_cli/library/ |
| `AGENTS.md` | Modify | Update paths and index to link the new plan artifacts |
| `RULES.md` | Modify | Document the new plan archiving system and date-prefixed artifact naming rules |
| `SCHEMA.md` | Modify | Update Directory Map to include new plan artifacts and the archive directory |
| `tests/test_guardrails.py` | Modify | Ensure guardrails test suite accounts for archived plans and new artifacts |

## Dependencies
None

## Cross-PLAN Impact
Updates directory structure referenced by `280526_documentation_reorg.md` and `280526_repo_restructure.md`.

## Test Strategy
- Run `pytest tests/test_guardrails.py` to ensure that all documentation checks pass.
- Verify through manual file listings that all legacy files are neatly relocated and only date-prefixed files are in the root of `documentation/artifacts/`.

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
