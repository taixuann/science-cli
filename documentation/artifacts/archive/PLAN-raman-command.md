# PLAN: Raman Spectroscopy Command

## Classification
feature

## Related Plans
- (none)

## Status
- **Created**: 2026-05-28
- **Status**: completed
- **Branch**: dev

## Objective
Implement a `raman` CLI command for Raman spectroscopy data from the Horiba LabRAM HR Evolution (USTH), with device config, metadata extraction, fzf integration, and analysis (baseline correction, peak finding, normalization).

## Context
The user has ~25 Raman/SERS files from PDA(q)-ITO samples measured on a Horiba LabRAM HR Evolution at USTH. Data is tab-delimited, comma-decimal, latin1 encoded, with 45 `#` header lines and two columns: shift (cm⁻¹) and intensity (counts). Files named with `_raman`, `_sers`, `_raman-sers` patterns.

## Specification

### Device Config
- Device name: `horiba-usth`
- Data: tab-delimited, comma decimal, latin1 encoding, 45 header lines, `names: [shift, intensity]`
- Config added to both hardcoded defaults (`core/config.py`) and global config (`~/.config/science-cli/config.yaml`)

### CLI Commands
| Subcommand | Description |
|------------|-------------|
| `raman ls` | List Raman files with laser/grating/range columns |
| `raman info [--fzf]` | Show full 30-field metadata table |
| `raman plot [--fzf]` | Plot spectrum with metadata annotation |
| `raman analyze [--fzf]` | ASLS baseline + normalization + peak finding + CSV export |

### Analysis Features
- **ASLS baseline correction** (`--baseline`): scipy sparse-based Asymmetric Least Squares, adjustable `--lam` and `--p`
- **Max-intensity normalization** (`--norm`): normalize to 0-1 range
- **Peak finding** (`--peaks`): scipy `find_peaks` with configurable `--prominence`, `--distance`, `--height`, `--width`
- **Output**: CSV files (`_peaks.csv`, `_baseline.csv`, `_normalized.csv`) saved to results directory

### Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `core/config.py` | Add technique+device | Hardcoded fallback for horiba-usth |
| `core/data_loader.py` | Add `names` support + `extract_raman_metadata()` | Header-less CSV loading |
| `core/technique.py` | Add detection patterns | `_raman`, `_sers`, `_raman-sers` |
| `cli/commands/raman.py` | Create | New raman command (607 lines) |
| `cli/commands/__init__.py` | Register | Add to COMMAND_TREE |
| `cli/help.py` | Add help | Group 4 classification |
| `~/.config/science-cli/config.yaml` | Add device+technique | Global config entry |
| `README.md` | Docs | Add raman section |
| `AGENTS.md` | Docs | Add raman guide |

## Dependencies
- `scipy` (sparse ASLS, signal.find_peaks) — already installed
- `numpy` — already installed
- `matplotlib` — already installed

## Test Strategy
- Load actual Raman file: `260526_PDA(q)-ITO_raman-sers_01.txt`
- Verify `raman ls` shows correct laser/grating/range
- Verify `raman info` shows 30-field metadata
- Verify `raman plot` renders spectrum
- Verify `raman analyze --baseline --norm --peaks` detects peaks and saves CSVs
- Verify `--fzf` flag launches interactive picker

## Progress
- [x] PLAN created
- [x] User approved (iterative)
- [x] Device config in core/config.py + global config.yaml
- [x] Data loader names support + metadata extraction
- [x] Technique detection patterns
- [x] CLI command (raman.py) — ls, info, plot, analyze
- [x] COMMAND_TREE registration + help.py
- [x] FZF integration for all subcommands
- [x] ASLS baseline + normalization (scipy)
- [x] Peak finding with configurable params (scipy)
- [x] CSV output to results directory
- [x] TEST — all commands verified working on real data
- [x] DOCS — README.md + AGENTS.md updated
- [x] COMMIT done (c006eb8 — raman: add analyze subcommand + fzf integration)
