# PLAN: Project-Aware Dashboard Backend & Plot Engine

## Classification
feature | docs | refactor

## Related Plans
- [[280526_artifacts_and_reference_guides]] — related — parent plan coordinating workspace re-organization.
- [[280526_ai_integration]] — related — the AI agents interact with the backend APIs and static image generation systems documented here.

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Establish a robust, project-aware dashboard backend and plot engine. The backend is responsible for tracking project contexts, navigating protocols and steps, managing SQLite caches, and generating/organizing static images (overlays, sweeps, fits). This backend serves as a clean, standardized data controller for any frontends (e.g. developed in Google AI Studio or Textual TUI).

## Context
A major component of `science-cli` is the visualization of characterization data. The user has specified that the frontend interface will be developed in Google AI Studio, which means the CLI's primary responsibility is as a robust **backend data and plot controller**. The dashboard needs to sit within the context of a specific project, allow the user to easily browse protocols and steps, and handle the automatic generation and storage of static images (such as IV sweeps, overlays, EIS Nyquist/Bode plots, CV, and CA curves) inside respective step `results/` folders.

## Specification

### 1. Project, Protocol, and Step Navigation Backend
- **Data Model**: Establish a robust object model for navigating projects:
  - `Project`: Resolves via `sci-config.yaml` or search paths. Can list all available protocols.
  - `Protocol`: Represents a sequence of characterization steps (e.g. `1_iv-test`). Can list all child steps and check device configurations (`devices.yaml`).
  - `Step`: Represents a specific measurement phase (e.g., `1_set`, `2_reset`). Contains raw data files and a dedicated `results/` subdirectory for static images and JSON summaries.
- **Session State**: The 3-tier session memory (`session.py`) maintains the active cursor (`project_path`, `protocol_name`, `step_name`) so that commands can omit long paths and operate contextually.

### 2. Static Image Generation & Storage
- **Static Assets**: All plot commands (`sci plot`, `sci raman plot`, `sci eis`, etc.) generate high-quality static assets (PDFs/PNGs) and save them directly in the active step's `results/` directory.
- **Index Generation**: When static images are generated, the backend updates a local `analysis_data.json` cache within the step's `results/` directory, mapping each raw measurement file to its corresponding static plot asset.
- **Overlay Engine**:
  - `sci plot --overlay file1,file2,...` generates multi-curve overlays.
  - The overlay command automatically resolves relative file paths inside the active step directory and places the resulting overlay image in `results/`.

### 3. SQLite v2 Data Cache
- The SQLite database (`src/science_cli/memristor/db.py`) acts as a high-performance query cache.
- The `populate_from_grammar()` routine scans step directories, parses files via the universal filename grammar, and updates SQLite.
- The backend dashboard service queries SQLite to instantly return step-level details, file counts, measurement timestamps, and active device parameters without reading raw CSVs.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/session.py` | Modify | Enhance session state serialization and default project context discovery |
| `src/science_cli/core/project.py` | Modify | Provide clean Python APIs for listing protocols, steps, and static results |
| `src/science_cli/memristor/db.py` | Modify | Ensure SQLite schema supports direct step-level result index queries |
| `src/science_cli/plot/base.py` | Modify | Standardize static image output paths to step `results/` folders by default |

## Dependencies
None

## Cross-PLAN Impact
AI agents leverage the session navigation endpoints defined here to execute high-level tasks.

## Test Strategy
- Test that running a plot command inside a protocol step automatically outputs the plot asset to `results/`.
- Verify the 3-tier session state retains active protocol and step correctly during multi-command flows.

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
