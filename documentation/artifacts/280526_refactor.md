# PLAN: Code Reorganization & Technique-Library Consolidation

## Classification
refactor | cleanup | architecture

## Related Plans
- [[280526_artifacts_and_reference_guides]] — related — parent plan coordinating workspace re-organization.

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Consolidate standalone characterization modules (`memristor/`, `electrochem/`, `iv/`) under a unified `src/science_cli/library/` directory, update all internal imports, and carefully configure filepaths and databases to guarantee seamless path resolution across the plot engines, CLI command dispatches, and tests.

## Context
Currently, individual characterization modules (e.g., `memristor/`, `electrochem/`, `iv/`) reside directly under the canonical source root (`src/science_cli/`), which clutters the top-level folder. `SCHEMA.md` lists a "Future Consideration" to move these folders into a consolidated `library/` folder. The user has approved this code reorganization, emphasizing that we must "check and configure the filepath or path or something for correct and avoid things." Relocating these directories requires absolute precision to avoid breaking relative imports, file references, database queries, and test targets.

## Specification

### 1. Directory Restructuring
- Create the target folder `src/science_cli/library/`.
- Move the folders:
  - `src/science_cli/memristor/` ➔ `src/science_cli/library/memristor/`
  - `src/science_cli/electrochem/` ➔ `src/science_cli/library/electrochem/`
  - `src/science_cli/iv/` ➔ `src/science_cli/library/iv/`
- Ensure each subdirectory contains its respective `__init__.py`.

### 2. Import Refactoring
Every reference to these consolidated modules must be updated across the codebase.
- **CLI Commands (`src/science_cli/cli/commands/`)**:
  - Update `memristor.py`: change `from science_cli.memristor import ...` to `from science_cli.library.memristor import ...`.
  - Update `eis.py`, `fit.py`, `plot.py`, `chat_cmd.py`, and other commands importing from `electrochem` or `iv`.
- **Plotting Engine (`src/science_cli/plot/`)**:
  - Update any plot modules importing from technique modules.
- **Unit and Guardrail Tests (`tests/`)**:
  - Update `test_memristor/` and other tests to import from the new paths.
- **Internal Technique Imports**:
  - Update internal imports within each moved module (e.g., inside `library/memristor/` or `library/electrochem/`).

### 3. Filepath Configuration & Path Routing Guardrails
To prevent path resolution errors, we must verify and configure path references:
- **SQLite Database Path (`library/memristor/db.py`)**:
  - Verify how the SQLite database path is resolved. Ensure it continues to resolve relative to the active project's database location (typically `protocol/memristor.db` or `<project>/memristor.db`), rather than relative to the source code file's path.
  - If a path is calculated relative to `__file__`, update the offset to account for the new nested level in the folder structure (e.g., moving from source root to `library/`).
- **Config & Theme Resolution**:
  - Ensure all built-in templates and themes continue to load seamlessly via their path utilities.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/` | Move | Move directory to `src/science_cli/library/memristor/` |
| `src/science_cli/electrochem/` | Move | Move directory to `src/science_cli/library/electrochem/` |
| `src/science_cli/iv/` | Move | Move directory to `src/science_cli/library/iv/` |
| `src/science_cli/cli/commands/memristor.py` | Modify | Update imports to `science_cli.library.memristor` |
| `src/science_cli/cli/commands/eis.py` | Modify | Update imports to `science_cli.library.electrochem` |
| `src/science_cli/library/memristor/db.py` | Modify | Update any relative path calculations to keep DB loading safe |
| `tests/test_memristor/*.py` | Modify | Update test imports to the new consolidated library structure |
| `tests/test_guardrails.py` | Modify | Update path rules to expect consolidated library directories |

## Dependencies
None

## Cross-PLAN Impact
Requires updating CodeGraph index (`codegraph sync`) after files are moved so the graph index remains completely healthy.

## Test Strategy
- **AST Compilation**: Run `python tests/test_guardrails.py` (Test 7) to check that all modified modules compile cleanly.
- **Unit Tests**: Run the full test suite (`pytest tests/test_memristor/`) to verify database creation, sync, analysis, and data loading operate correctly.

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
