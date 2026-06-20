# Implementation Plan: Waveform Pattern to Protocol YAML + Describe

**Date**: 21/06/2026
**Status**: 🟡 Planning
**Layer**: 2 (Metadata Parsers) + 6 (Protocol.yaml)
**Version**: v3.22.2 (proposed)

---

## Context Summary

Parser is done (uncommitted): `parse_wgfmu_waveform_segments()` extracts waveform_2d from WGFMU Waveform1 columns, stored in-memory via `info["analysis"]`. User wants it written **directly to protocol.yaml** per filename, then `plot --describe` to display it as formatted segments.

---

## Objectives

1. Write `waveform_pattern` to `protocol.yaml` → `steps[].files[].metadata.waveform_pattern` for all STP files
2. Update `_show_describe()` to format waveform_2d as segment table (Start/End/Width/Voltage)
3. Run on all pulse-stp-decay files in protocol 2.5
4. Commit everything

---

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `core/protocol.py` | Add `write_file_metadata(filename, step_name, metadata_dict)` function | Low |
| `core/data_loader.py` | After waveform extraction, call `write_file_metadata()` to persist | Low |
| `cli/commands/plot.py` or `plot/registry.py` | Update `_show_describe()` to format waveform_2d as Rich Table | Low |

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Add `write_file_metadata()` to protocol.py | code-medium | ~30 lines |
| Wire into data_loader.py | code-light | ~5 lines |
| Update `_show_describe()` | code-medium | ~40 lines |
| Run on all STP files | code-light | single command |
| Docs + commit | docs-light | CHANGELOG, version bump |

---

## Dependency Order

1. task-001 (protocol.py) → 2. task-002 (data_loader wiring)
3. task-003 (describe) → 4. task-004 (run) → 5. task-005 (docs)

---

## Risks

- protocol.yaml write must be atomic (use tempfile + replace pattern)
- waveform_pattern is a 2D list → YAML serialization must handle nested lists
- Large files with many metadata writes could slow down data_loader (mitigate: only write if pattern changes)
