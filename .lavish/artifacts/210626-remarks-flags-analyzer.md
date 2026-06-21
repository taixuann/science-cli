---
layer: [2, 4, 6, 7]
type: plan
status: planning
tags: [flags, remarks, add, analyzer, pulse-endurance, pulse-endurance-py]
depends_on: [210626-generic-plot-config-scale]
assignee: plan
---

# Implementation Plan: Remarks/Flags System + Pulse Endurance Analyzer

**Date**: 21/06/2026
**Status**: 🟡 Planning
**Layers**: 2 (Metadata), 4 (FZF Display), 6 (Protocol.yaml), 7 (Pulse Analyzers)

---

## Context Summary

Two independent proposals consolidated. The remarks/flags system adds a new `sci add -m remarks` and `sci add -m flags` mode for interactive human-readable annotation of data files. The pulse endurance analyzer creates a dedicated `pulse-endurance.py` in `library/` for 4 analysis views (ratio vs cycles + histograms).

---

## Proposal A: Remarks + Flags System

### Core Idea

Replace old status tags (keep/highlight/discard) with a **filename grammar-based approach**. Remarks and flags are embedded in the filename using the existing grammar pattern:

```
DDMMYY-HHMMSS_device-id_study_remarks_flags_count.ext
```

**Remarks**: Human-readable labels (e.g., `extracted-data`, `2V-10ns`, `set-voltage-sweep`) - free text, single hyphenated string.

**Flags**: Human-significance categories - multi-select from fixed set:
- `important` -> star symbol
- `valid` -> check symbol
- `invalid` -> cross symbol
- `discard` -> trash symbol
- `questionable` -> question mark

### Syntax

```
sci add -m remarks [files...] [--all]
sci add -m flags [files...] [--all]
```

| Variant | Behavior |
|---------|----------|
| `sci add -m remarks` | fzf multi-select files -> prompt for remarks text -> rename raw+symlink -> update protocol.yaml |
| `sci add -m remarks --all` | Batch: same remarks text applied to all detected files |
| `sci add -m flags` | fzf multi-select -> interactive multi-select for flags -> rename + update |
| `sci add -m flags --all` | Batch: same flags applied to all |
| `sci add -m remarks --all --overlay` | Overlay mode: batch assign remarks+flags together |

### Workflow Detail

1. File selection via fzf multi-select from `data/raw/`
2. Remarks prompt: Free text input (validated: letters, digits, hyphens only)
3. Flags prompt: Multi-select checkboxes (important, valid, invalid, discard, questionable)
4. Rename raw file via `os.rename()` in `data/raw/`
5. Rename symlink if exists in protocol step folder
6. Update protocol.yaml files[] entry + symlink entry
7. Immutable override: raw data content unchanged, only filename (metadata)

### Grammar Repair

If new name doesn't match grammar, auto-repair: replace invalid chars with `-`, strip leading/trailing hyphens, warn user.

### Badge Display in FZF

In `build_fzf_display()` prepend flag badge before row. Show remarks in existing Remarks column.

### Files to Modify

| File | Change | Risk |
|------|--------|------|
| `cli/commands/add.py` | New `-m remarks` and `-m flags` modes with fzf + prompt + rename logic | Medium |
| `cli/help.py` | Add help text for new modes | Low |
| `core/grammar.py` | Maybe expose `build_filename(parts)` helper | Low |
| `core/fzf/display.py` | Prepend flag badge from filename parsing | Low |
| `core/fzf/columns.py` | Return parsed flags for badge display | Low |
| `core/protocol.py` | Maybe add `update_step_filename()` helper | Low |
| `.lavish/layer02-metadata-parsers.html` | New artifact card for remarks/flags mode | Low |
| `.lavish/layer04-fzf-display.html` | New artifact card for flag badge display | Low |

---

## Proposal B: Pulse Endurance Analyzer

### Core Idea

Create dedicated `pulse-endurance.py` in `library/pulse/` for all pulse-endurance analysis. Library functions live here (plot is in `plot/generic.py` and `plot/registry.py`).

### New File: `src/science_cli/library/pulse/pulse-endurance.py`

Contains 4 analysis functions on extracted-list CSV:

1. **`ratio_vs_cycles(file_path, **kwargs)`** - NEW: R_HRS/R_LRS ratio vs cycle number (log-log), linear fit + trend slope, saves plot + writes metrics to protocol.yaml
2. **`ratio_histogram(file_path, **kwargs)`** - MOVED from endurance.py: existing histogram of ratio distribution
3. **`i_ratio_vs_cycles(file_path, **kwargs)`** - NEW: I_LRS/I_HRS ratio vs cycle number, linear fit, saves plot + metrics
4. **`current_ratio_histogram(file_path, **kwargs)`** - MOVED from endurance.py: existing current ratio histogram

### Discovery via sci analyze

When fzf detects `pulse:pulse-endurance` study, show 4-option interactive menu. Selected option runs on chosen file(s).

### Config-Studies.yaml Changes

Add `required_fields: [cycle, r_hrs_ohm, r_lrs_ohm, i_hrs_A, i_lrs_A]` and 4-option analyze menu under pulse-endurance.

### Files to Modify

| File | Change | Risk |
|------|--------|------|
| `library/pulse/pulse-endurance.py` | NEW file - 4 analysis functions | Medium |
| `config/config-studies.yaml` | Add analyze block with 4 options + required_fields | Low |
| `library/pulse/endurance.py` | Remove ratio_histogram() + current_ratio_histogram() | Low |
| `core/interactive_menu.py` | Maybe add required_fields validation | Low |
| `cli/commands/analyze.py` | Ensure --all mode with study detection works | Low |

---

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| Plan (this document) | plan-heavy | Done |
| Implementation A: add -m remarks mode | code-medium | New add mode + rename logic |
| Implementation A: add -m flags mode | code-medium | Similar structure |
| Implementation A: flag badge in FZF | code-medium | Read flags from filename |
| Implementation B: pulse-endurance.py | code-medium | New file, 4 functions |
| Implementation B: config-studies.yaml | code-medium | Add analyze block |
| Implementation B: remove from endurance.py | code-medium | Move, don't duplicate |
| QA + Tests | review-light | pytest + menu verification |
| Docs + Dashboard | docs-light | Skill update, lavish dashboard |

## Dependency Order

1. Create pulse-endurance.py with 4 functions
2. Add analyze block to config-studies.yaml
3. Remove histograms from endurance.py (move)
4. QA + verify interactive menu
5. Add add -m remarks mode
6. Add add -m flags mode
7. Add flag badge to FZF display
8. QA + tests for remarks/flags
9. Docs + dashboard update
10. CHANGELOG + version bump

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rename raw breaks existing symlinks | High | Always rename symlink + update protocol.yaml atomically |
| Grammar rejects user input | Medium | Auto-normalize remarks/flags |
| Duplicate code endurance.py vs pulse-endurance.py | Low | Move, don't copy |
