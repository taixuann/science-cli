# PLAN: Code Reorganization & Technique-Library Consolidation

## Classification
refactor | cleanup | architecture | feature

## Related Plans
- [[280526_artifacts_and_reference_guides]] — related — parent plan coordinating workspace re-organization.
- [[280526_dashboard]] — related — the dashboard backend pulls from the unified technique controllers defined here.

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Symmetrically reorganize the codebase and CLI interface by:
1. Consolidating technique modules (`memristor/`, `electrochem/`, `iv/`, `raman/`, `uv-vis/`) under `src/science_cli/library/`.
2. Restructuring CLI commands to expose global operations (`sci plot`, `sci analyze` search-driven) alongside technique namespaces (`sci memristor`, `sci raman`, `sci iv`, `sci ec`, `sci uv-vis`) with a standardized set of subcommands (`ls`, `info`, `plot`, `analyze`).
3. Configuring filepaths and database query routing to prevent path resolution breaks.

## Context
Currently, CLI commands and libraries are partially decoupled and unevenly structured (e.g. `sci raman` exists, but CV/CA/EIS are scattered). The user has proposed a symmetric layout where technique folders under `src/science_cli/library/` map 1:1 to dedicated command namespaces (`sci memristor`, `sci raman`, `sci iv`, `sci ec`, `sci uv-vis`). Each namespace gets a standardized, intuitive interface (`ls`, `info`, `plot`, `analyze`), while global commands (`sci plot`, `sci analyze`) remain search-driven utilities that operate across the entire workspace.

## Specification

### 1. Directory Structure Consolidation
- Create the target folder `src/science_cli/library/`.
- Consolidate technique code folders:
  - `src/science_cli/memristor/` ➔ `src/science_cli/library/memristor/`
  - `src/science_cli/electrochem/` ➔ `src/science_cli/library/electrochem/`
  - `src/science_cli/iv/` ➔ `src/science_cli/library/iv/`
  - Create `src/science_cli/library/raman/` (and migrate Horiba metadata parser).
  - Create `src/science_cli/library/uv-vis/` (for absorption spectra).

### 2. Symmetrical CLI Command Architecture
Expose the commands under two distinct layers:

#### Layer 1: Search-Driven Global Commands
- `sci plot <query>`: Autodetects the technique of the target file via filename grammar and renders standard plots (line/scatter/Nyquist/etc.) using publication themes.
- `sci analyze <query>`: Autodetects technique and runs standard parameter extractions.

#### Layer 2: Technique Namespaces (Group 4)
Expose dedicated command modules with standardized subcommands:
- **`sci memristor <subcommand>`**
  - Subcommands: `init`, `add`, `ls`, `info`, `sync`, `validate`, `stats`, `rm`, `check`, `plot`, `dashboard`.
- **`sci raman <subcommand>`**
  - Subcommands: `ls` (list files/metadata), `info` (inspect laser/grating fields), `plot` (plot spectra), `analyze` (baseline, normalizations, peaks).
- **`sci iv <subcommand>`**
  - Subcommands: `ls`, `info`, `plot`, `analyze` (parameters like R_on/R_off).
- **`sci ec <subcommand>`** (Electrochemistry - CV/CA/EIS)
  - Subcommands: `ls`, `info`, `plot` (Nyquist/Bode/CV/CA), `analyze` (circuit fitting).
- **`sci uv-vis <subcommand>`**
  - Subcommands: `ls`, `info`, `plot`, `analyze` (Tauc bandgap extraction).

### 3. Filepath Safety & Database Query Routing
- **Relative Path Checks**: Ensure any references to databases (`memristor.db` or `<project>.db`) in `library/memristor/db.py` are absolute or correctly offset relative to the new nested directory structure.
- **Built-in Templates & Themes**: Ensure core path resolution in `core/paths.py` and `theme/registry.py` resolve correctly without reference breaks.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/memristor/` | Move | Relocate to `src/science_cli/library/memristor/` |
| `src/science_cli/electrochem/` | Move | Relocate to `src/science_cli/library/electrochem/` |
| `src/science_cli/iv/` | Move | Relocate to `src/science_cli/library/iv/` |
| `src/science_cli/cli/commands/__init__.py` | Modify | Register new commands (`ec`, `iv`, `uv-vis`) in `COMMAND_TREE` |
| `src/science_cli/cli/commands/memristor.py` | Modify | Update imports to `library.memristor` |
| `src/science_cli/cli/commands/eis.py` | Modify | Replaced by `src/science_cli/cli/commands/ec.py` |
| `src/science_cli/cli/commands/ec.py` | [NEW] | Handles CV, CA, EIS commands symmetrically (`ls`, `info`, `plot`, `analyze`) |
| `src/science_cli/cli/commands/iv.py` | [NEW] | Handles IV sweep commands symmetrically (`ls`, `info`, `plot`, `analyze`) |
| `src/science_cli/cli/commands/uv_vis.py` | [NEW] | Handles UV-Vis commands symmetrically (`ls`, `info`, `plot`, `analyze`) |
| `tests/test_guardrails.py` | Modify | Update path guardrails for consolidated structure and check compilation |

## Dependencies
None

## Cross-PLAN Impact
Requires updating CodeGraph index (`codegraph sync`) after files are moved so the graph index remains completely healthy.

## Test Strategy
- **AST Compilation**: Run `python tests/test_guardrails.py` to check that all modified modules compile.
- **Unit Tests**: Run the full test suite (`pytest tests/`) to verify database creation, sync, analysis, and data loading operate correctly.

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
