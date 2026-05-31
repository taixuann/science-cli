# PLAN: Protocol-Driven Raw Data Splitting and Sorting Engine

## Classification
feature | core

## Related Plans
- [[290526_integrate_premium_frontend]] — completed (visualization layer now perfectly supports rendering split files)

## Status
- **Created**: 2026-05-29
- **Status**: draft
- **Branch**: dev

## Objective
Implement an automated data splitting and sorting engine (`sci protocol split` or `sci parse --split`) that parses the technique, device, and file registers in a protocol's `<protocol_name>.yaml` file, scans the central `data/raw` directory, and automatically copies/distributes raw measurement files into their corresponding step subdirectories under `protocol/<protocol_name>/<step_name>/`, while cleanly updating the project database and metadata caches.

## Context
Currently, raw experimental files from multiple distinct techniques (e.g., CV deposition, CA doping, EIS impedance, and IV state sweeps) are dumped together in the central `data/raw/` folder during active laboratory sessions. 

The protocol's YAML config (e.g., `protocol/3_ca-doping/3_ca-doping.yaml`) explicitly documents which files belong to which protocol steps, along with their associated characterization techniques and target measurement instruments. 

To bridge the gap between raw data collection and structured visualization/analysis, we need a robust pipeline that can understand this schema, perform safe path-traversal-free file copying, register the correct metadata, and sync with the SQLite database.

## Specification

### 1. Command Registration
- Register a new CLI subcommand: `sci protocol split <protocol_name>` (or integrate into `sci parse`).
- The command will:
  1. Read `<protocol_name>.yaml` from `protocol/<protocol_name>/`.
  2. Scan `data/raw/` in the active project.
  3. Validate that every file registered under a step exists in `data/raw/`.
  4. Create the step directories under `protocol/<protocol_name>/<step_name>/` if they do not exist.
  5. Copy/move the matched files into their respective step directories.
  6. Trigger a database synchronization to parse data points, extract parameters, and update the TUI dashboard caches.

### 2. Socratic Mirroring & Architectural Edge Cases (For Discussion)

> [!NOTE]
> **Edge Case 1: Overlapping Filenames / Duplicates**
> - If a file is registered in multiple steps or protocols, should the engine copy it to both destinations, or flag it as a warning?
> - *Recommendation*: Copy to both to maintain independent step contexts, but log a warning.

> [!IMPORTANT]
> **Edge Case 2: Missing or Extra Files**
> - What if a file listed in the protocol YAML is missing from `data/raw/`?
> - What if there are files in `data/raw/` that match naming conventions but are *not* explicitly registered in the protocol YAML? Should there be a "heuristic auto-assignment" mode?
> - *Recommendation*: If a file is missing, log a clear warning but proceed. If extra files exist, provide an `--auto` flag to heuristically assign them to steps using their technique suffixes (e.g., `_CV` goes to `ec-cv` steps).

> [!WARNING]
> **Edge Case 3: Metadata Synchronization**
> - When splitting files, should we automatically trigger parameter extraction (e.g. `v_set`, `v_reset`, `ratio` for `iv-sweep`) and populate SQLite?
> - *Recommendation*: Yes, execute the `memristor sync` or `memristor analyze` pipeline on the target step to keep the database fully aligned in real time.

## Proposed Changes

| File | Action | Reason |
|------|--------|--------|
| [protocol.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/cli/commands/protocol.py) | [MODIFY] | Add `split` subcommand parsing and print pretty Rich tables summarizing the copy status. |
| [protocol.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/core/protocol.py) | [MODIFY] | Implement the core splitting engine that parses step file lists, resolves paths, performs safe copies, and logs anomalies. |

---

## Verification Plan

### Automated Tests
- Create unit tests verifying the file sorter works against a mock workspace with mock raw data folders.
- Run `pytest` to verify guardrail compliance.

### Manual Verification
- Execute `sci protocol split 3_ca-doping` in `test-project`.
- Verify that `protocol/3_ca-doping/1_cv-deposition/` and other steps are correctly populated with data.
- Verify that `/api/project` returns the updated file lists.
