---
layer: [3, 5, 6, 7]
type: plan
status: done
tags: [stp, pulse, segment, decay, analyzer]
depends_on: [210626_compact-waveform]
assignee: docs
---

# Implementation Plan: STP Segment-Aware Decay Analysis

**Date**: 21/06/2026
**Status**: ✅ Done (v3.24.1)
**Layer**: 3 (Keysight Parsers) + 5 (Plotting) + 6 (Protocol) + 7 (Pulse Analyzers)

## Context Summary

STP decay files in res_internship/ have 3 categories:
1. Single — standard pulse-read, no further action needed
2. Multi-cycle — 11-56 genuine pulse-read repetitions in one CSV (large time gaps: 801s, 11s)
3. High-density sampled — many segments but small gaps (0.1us), actually continuous data

Current analyze_stp_decay() fits everything at once and fails on multi-cycle files.

Phase 1 complete: 32 flag filenames renamed to [important]/[questionable]/[valid]

## Objectives

1. Add detect_stp_segments() to split files by large time gaps
2. Refactor analyze_all() for per-segment fitting with markers
3. Per-segment metadata in protocol.yaml
4. Tag file with {extracted-decay} remark on first successful segment
5. Plot output: results/stp-decay-diagnostic_{stem}_overview.pdf + per-segment files
6. Overwrite support (skip existing [extracted-decay] files unless --overwrite)
7. Update config-studies.yaml interactive menu

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| src/science_cli/library/pulse/pulse_stp_decay.py | Add detect_stp_segments(), refactor analyze_all() | High |
| config/config-studies.yaml | Update interactive.analyze for STP decay | Low |

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Implementation | code-heavy | Segment detection + fitting + plot + YAML metadata |
| QA & Review | review-light | pytest + smoke test |
| Documentation | docs-light | Update README/artifacts |

## Tasks

| ID | Description | Est. Duration | Assigned To |
|----|-------------|---------------|-------------|
| T1 | detect_stp_segments() in pulse_stp_decay.py | 45m | code-heavy |
| T2 | Refactor analyze_all() with per-segment loop + overview plot | 1.5h | code-heavy |
| T3 | Per-segment YAML metadata in protocol.yaml | 30m | code-heavy |
| T4 | --overwrite flag + dispatch wiring | 30m | code-heavy |
| T5 | Update config-studies.yaml interactive.analyze | 15m | code-light |
| T6 | pytest + smoke test on res_internship | 30m | review-light |
| T7 | Documentation | 15m | docs-light |

## Dependency Order
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7

## Risks
- Multi-cycle files with very few points per segment (<5) -> skip with warning
- _get_results_dir() may need updating for segment-based filenames
- _tag_with_extracted_decay() currently marks extracted_decay: true -> needs to be dict with segments
