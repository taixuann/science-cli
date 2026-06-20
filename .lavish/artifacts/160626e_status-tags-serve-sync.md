---
layer: [4]
type: plan
status: done
tags: [status, tags, serve, dashboard]
depends_on: [160626c_device-study-relationship]
assignee: code
---

# Implementation Plan: Status Tags + Serve Sync (Seq 1)

**Date**: 16/06/2026
**Status**: 🟢 Done
**Architecture ref**: `160626c_device-study-relationship.md` §3.2, §6

## Context Summary

Currently `sci results --star` toggles a star (`⭐`) per result file. The stars are stored in `project/results/.stars.json` and shown in fzf. This is a binary state (starred or not).

User wants more expressive status tags for **discarding, highlighting, or keeping** files. The serve dashboard should reflect these tags immediately when set from CLI.

## Objectives

1. **Add status tags** beyond binary star. Allowed values: `keep`, `highlight`, `discard`, `star` (keep star as alias)
2. **Storage**: rename `.stars.json` → `.status.json` (or keep both with status superset). Key format: `{protocol}/{step_dir}/{filename}` → tag string.
3. **CLI**: `sci results --status <tag>` to assign tag, `--status clear` to remove
4. **fzf display**: `[KEEP]`, `[HIGHLIGHT]`, `[DISCARD]`, `⭐` badges before filenames
5. **Serve**: new `/api/status` endpoint to read/write status. Gallery shows status badges. Click to cycle status (or right-click menu).
6. **Sync**: CLI writes → serve reads (or vice versa) — share the same `.status.json` file

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/cli/commands/results.py` | Rename `.stars.json` → `.status.json`; add status value support; update fzf display | Low |
| `src/science_cli/serve/api.py` | Add `/api/status` GET + POST endpoints | Med |
| `src/science_cli/serve/frontend/index.html` | Add status badge UI + click handler | Med |
| `src/science_cli/serve/frontend/*.js` (compiled) | New behavior; may need rebuild | Med |
| `tests/test_results/test_status.py` (NEW) | Test status toggling | Low |
| `tests/test_serve/test_api.py` | Test `/api/status` endpoints | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Status CLI + storage | code-medium | Backward compat with stars |
| Serve API + frontend | code-medium | New endpoints + badge UI |
| QA review | review-light | Test status sync CLI ↔ serve |
| Docs | docs-light | CHANGELOG, README |

## Tasks

| ID | Description | Est. Duration | Assigned To | Calendar Event |
|----|-------------|---------------|-------------|----------------|
| task-001 | Refactor results.py to use `.status.json` with tag values | 30m | code-medium | no |
| task-002 | Update fzf display with status badges | 15m | code-medium | no |
| task-003 | Add `/api/status` GET/POST in api.py | 20m | code-medium | no |
| task-004 | Add status badge UI to gallery | 30m | code-medium | no |
| task-005 | Test status flow end-to-end | 20m | code-medium | no |
| task-006 | pytest + smoke | 15m | review-light | no |
| task-007 | CHANGELOG + docs | 10m | docs-light | no |

## Dependency Order

1. task-001 (status storage) → enables everything
2. task-002 (fzf badges) — independent
3. task-003 (API) — independent
4. task-004 (frontend) — depends on 003
5. task-005 (tests) — depends on all above
6. task-006 (QA) — depends on 005
7. task-007 (docs) — depends on 006

## Risks

- **Risk 1**: Existing users have `.stars.json` files. Migration path: read both, prefer `.status.json` if exists, else convert `.stars.json` to `.status.json` on first run.
- **Risk 2**: Frontend is a compiled React bundle. Editing the compiled JS is hard. May need to add inline CSS/JS or rebuild from source.
- **Risk 3**: Status sync between CLI (file write) and serve (file watch) — need a polling or file-watcher mechanism so serve picks up changes immediately.

## Walkthrough

Created `src/science_cli/cli/commands/results_status.py` (79 lines) with `load_status`, `save_status`, and `badge_for_file` functions. Refactored `results.py` to use the new module, replacing `--star` with `--status` flag and auto-migrating `.stars.json` → `.status.json` on first read. Added `GET /api/status` and `POST /api/status` endpoints to `serve/api.py` returning per-file badge data. Updated `serve/frontend/index.html` with inline JS that polls every 2s and draws clickable badge overlays on lazy-loaded gallery items. 26 new tests in `tests/test_core/test_status.py`.
