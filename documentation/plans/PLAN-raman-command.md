# PLAN: Raman Spectroscopy Command

## Classification
feature

## Related Plans
None — standalone feature.

## Status
- **Created**: 2026-05-28
- **Status**: completed
- **Branch**: (current branch)

## Objective
Add full Raman spectroscopy support: technique config, data loading for Horiba LabRAM format, and a `raman` CLI command with file listing, metadata viewing, and plotting.

## Context
The project now has Raman data files from a Horiba LabRAM HR Evolution spectrometer. Files follow the naming pattern `date_material_raman(-sers)_suffix.txt`. The data format is:
- 45 `#`-prefixed header lines (instrument, laser, grating, etc.)
- Tab-delimited, comma-decimal separator (European format)
- Two columns: Raman shift (cm⁻¹) and intensity (counts)
- No column header names in the data section

Current infrastructure has no `raman` technique, no compatible device config, and the data loader can't handle header-less files.

## Specification

### 1. Config Updates (`core/config.py`)
- Add `raman` technique to `_DEFAULT_TECHNIQUE_PATTERNS` with patterns: `_raman`, `_sers`, `_raman-sers`
- Add `raman` device `horiba-labram-hr-evolution` to `_DEFAULT_TECHNIQUE_DEVICES`
  - delimiter: `\t`, decimal: `,`, header_lines: 45
  - `names: [shift, intensity]` (new property — file has no column headers)
- Add `raman` to `_DEFAULT_GLOBAL_TECHNIQUES` with grammar_codes
- Add `horiba-labram-hr-evolution` to `_DEFAULT_GLOBAL_DEVICES`
- Add to `generate_default_config_yaml()`

### 2. Data Loader Fix (`core/data_loader.py`)
- In `_load_with_device_config()`: if device config has a `names` list, pass `header=None, names=names` to `pd.read_csv` to handle header-less files

### 3. Raman Metadata Extractor (`core/data_loader.py` or new utility)
- Function `extract_raman_metadata(filepath)` parsing the `#` header lines into a dict
- Keys: acquisition_time, accumulations, range, windows, autofocus, spike_filter, delay, binning, readout_mode, detector_gain, detector_adc, detector_temperature, instrument, detector, objective, grating, nd_filter, laser, hole, stage_xy, stage_z, x, y, z, full_time, project, sample, site, title, remark, date, acquired
- Called by the raman command on-the-fly (no persistence)
- Called in `load_data_file` when technique=raman to attach metadata

### 4. New `raman` Command (`cli/commands/raman.py`)
Handler function with subcommands:
- `raman ls [--step <name>]` — list Raman files in current step/project
- `raman info <file>` — parse and display all 45 header metadata fields in a Rich table
- `raman plot <file> [--grid] [--title] [--xlabel] [--ylabel]` — plot Raman spectrum (shift vs. intensity) with optional metadata annotation in the title
- `raman help` — show command help

### 5. Command Registration (`cli/commands/__init__.py`)
- Import `raman_handler` and add to `COMMAND_TREE`

### 6. Help System (`cli/help.py`)
- Add `raman` to `GROUP 4: DEVICE & TECHNIQUES`
- Add COMMAND_DESCRIPTIONS entry
- Add COMMAND_HELP entry with subcommands and flags

### 7. Technique Patterns (`core/technique.py`)
- Add `raman` patterns to `PATTERNS` dict

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/config.py` | Edit | Add raman technique + device config |
| `src/science_cli/core/data_loader.py` | Edit | Add `names` support + metadata extraction |
| `src/science_cli/core/technique.py` | Edit | Add raman detection patterns |
| `src/science_cli/cli/commands/__init__.py` | Edit | Register raman command |
| `src/science_cli/cli/commands/raman.py` | Create | New raman CLI handler |
| `src/science_cli/cli/help.py` | Edit | Add raman to help menus |

## Dependencies
None — all changes are self-contained.

## Test Strategy
- Load a Raman file and verify DataFrame has columns `shift`, `intensity`
- Verify `raman info` parses all 45 header fields
- Verify `raman ls` lists files correctly
- Verify `raman plot` generates a proper spectrum plot

## Progress
- [x] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
