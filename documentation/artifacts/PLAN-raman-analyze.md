# PLAN: Raman Analyze + FZF Integration

## Classification
feature

## Related Plans
- [[PLAN-raman-command]] — blocks (raman CLI must exist before adding analyze subcommand)

## Status
- **Created**: 2026-05-28
- **Status**: in-progress
- **Branch**: (current branch)

## Objective
Add `raman analyze` subcommand (peak finding, ASLS baseline correction, max-intensity normalization, CSV output) + integrate fzf into all Raman subcommands.

## Context
The `raman` CLI command exists (list, info, plot) but lacks:
1. **fzf integration** — user must type filenames; wants `--fzf` flag on `info`, `plot` (and `analyze`)
2. **Peak analysis** — needs peak detection via scipy.signal.find_peaks for Raman/SERS spectra (PDA, ITO)
3. **Baseline correction** — ASLS algorithm for removing fluorescence background
4. **Normalization** — max-intensity normalization for comparison
5. **CSV output** — save results as structured CSV for future configurability

25 Raman files exist in the internship project, format: Horiba LabRAM HR Evolution, tab-delimited with 45-line `#` header, comma-decimal.

## Specification

### 1. FZF Integration (all subcommands)
- `raman info --fzf` — fzf single-select from raw_dir Raman files with preview (head -n 20)
- `raman plot --fzf` — fzf single-select same as info
- `raman analyze --fzf [options...]` — fzf single-select then run analysis
- Without `--fzf`: existing behavior (file argument required)
- Add `raman info --fzf` and `raman plot --fzf` as entries in help examples

### 2. `raman analyze` Subcommand

**Syntax:**
```
raman analyze <filename> [--fzf] [options]
raman analyze --fzf [options]
```

**Analysis pipeline (order):**
1. Load data → pair (shift, intensity)
2. Baseline correction (if `--baseline`) → subtract baseline from intensity
3. Normalization (if `--norm`) → max-intensity normalize
4. Peak finding → detect peaks via prominence

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--prominence` | 500 | Min peak prominence (conservative default) |
| `--distance` | (auto) | Min peak separation in cm⁻¹ |
| `--height` | (auto) | Min peak height in counts |
| `--width` | (auto) | Min peak width in cm⁻¹ |
| `--baseline` | False | Enable ASLS baseline correction |
| `--lam` | 1e7 | ASLS smoothness parameter |
| `--p` | 0.01 | ASLS asymmetry parameter |
| `--norm` | False | Enable max-intensity normalization |
| `--name` | (auto) | Output filename prefix (default: file stem) |

**CSV output** (saved to `protocol/<step>/results/` or `results/`):
- `{prefix}_peaks.csv`: peak_center(cm⁻¹), intensity(counts), prominence, fwhm(cm⁻¹)
- `{prefix}_baseline.csv`: shift(cm⁻¹), baseline(counts) — only if `--baseline`
- `{prefix}_normalized.csv`: shift(cm⁻¹), intensity_norm(a.u.) — only if `--norm`

**Console output:**
- Peak count, peak positions + intensities table (Rich table)
- Baseline correction: "ASLS baseline subtracted (lam={lam}, p={p})"
- Normalization: "Max-intensity normalized (factor={max_intensity})"
- Output file paths

### 3. ASLS Baseline Implementation
Pure numpy/scipy implementation in `raman.py` or extracted to utility:
- Whittaker smoother with asymmetric weighting
- Iterative refinement until convergence
- Returns baseline array same length as input

### 4. Help & Registration Updates
- `help.py`: Add `raman analyze` subcommand, flags, examples, `--fzf` flags
- `raman.py`: Already registered in COMMAND_TREE

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/cli/commands/raman.py` | Edit | Add fzf integration + analyze subcommand + ASLS impl |
| `src/science_cli/cli/help.py` | Edit | Add analyze subcommand, fzf flags, examples |

## Dependencies
- scipy.signal.find_peaks — already available (scipy is a project dep)
- numpy — already available

## Test Strategy
1. `raman analyze <file>` — verify console output + CSV files created
2. `raman analyze <file> --baseline` — verify ASLS produces baseline
3. `raman analyze <file> --baseline --norm` — verify baseline + norm pipeline
4. `raman analyze --fzf` — verify fzf opens
5. `raman info --fzf` — verify fzf opens with preview
6. `raman plot --fzf` — verify fzf opens with preview
7. Verify help: `raman --help` shows new subcommand + flags
8. Regression: `raman ls`, `raman info <file>`, `raman plot <file>` still work

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT: fzf integration (info, plot, analyze)
- [x] IMPLEMENT: ASLS baseline (scipy sparse diags, fixed singular matrix bug)
- [x] IMPLEMENT: peak finding + CSV output (prominence, FWHM)
- [x] IMPLEMENT: normalization (max-intensity)
- [x] IMPLEMENT: `raman analyze` dispatcher + flag parsing
- [x] IMPLEMENT: help.py updates (subcommand, flags, examples)
- [x] IMPLEMENT: config.py fix (horiba-usth device rename, uv-vis indent fix)
- [x] TEST passed (lint: ruff clean, functional: real Raman data tested)
- [ ] DOCS updated
- [ ] COMMIT done
