# PLAN: EIS Multi-Output + Warburg Circuits

## Status
- **Created**: 2026-05-17
- **Status**: in-progress
- **Branch**: main

## Objective
When `ec-eis` technique is detected, generate Nyquist + Bode PDFs per file by default, add `--nyquist`/`--bode`/`--circuit`/`--kk` flags, and implement Warburg diffusion element for improved circuit fitting.

## Context
Currently `_do_plot()` produces one generic line plot per file. For EIS, users need both Nyquist (Z' vs -Z'', equal aspect) and Bode (|Z| + phase vs frequency, dual y-axis) plots. The `--nyquist`/`--bode` hints shown in the prompt are decorative only — no flag handling exists. Circuit models lack Warburg diffusion, so semi-infinite diffusion behavior fits poorly (R²=0.38 for GCE-PDA).

## Specification

### Part A — EIS Multi-Plot Output (`cli/commands/plot.py`)

When `technique == "ec-eis"` in `_do_plot()`:

| Flags | Output file(s) |
|---|---|
| (none) | `ec-eis-nyquist_<stem>.pdf` + `ec-eis-bode_<stem>.pdf` |
| `--nyquist` | `ec-eis-nyquist_<stem>.pdf` only |
| `--bode` | `ec-eis-bode_<stem>.pdf` only |
| `--circuit [model]` | adds `ec-eis-fit-nyquist_<stem>.pdf` (best-fit overlay) |
| `--kk` | prints KK result to console, no extra file |

Flags parsed from user input in `_plot_interactive()` and forwarded in `all_flags`. The ec-eis branch in `_do_plot()` loads data with `technique="ec-eis"` to get normalized columns, then calls `plot_eis_nyquist()` / `plot_eis_bode()` / `plot_eis_fit()`.

Each save updates `manifest.json` with all output files.

### Part B — Warburg Circuit Models (`electrochem/eis.py`)

New impedance function:
- `_warburg_impedance(f, sigma)` → Z_w = sigma / sqrt(j * omega) = sigma/sqrt(omega) * (1 - 1j)

New circuit models:

| Name | Z(omega) | Parameters | Bounds |
|---|---|---|---|
| `R_s(C[RW])` | Rs + 1/(jωCdl + 1/(Rct + σ/√(jω))) | Rs, Cdl, Rct, sigma | Rs[1,1e6], Cdl[1e-12,1], Rct[1,1e9], sigma[1e-6,1e6] |
| `R_s(Q[RW])` | Rs + 1/(1/Z_Q + 1/(Rct + σ/√(jω))) | Rs, Q_mag, Q_n, Rct, sigma | Rs[1,1e6], Q_mag[1e-12,1], Q_n[0.5,1.0], Rct[1,1e9], sigma[1e-6,1e6] |

`--circuit` with no model → try both R_s(C[RW]) and R_s(Q[RW]), pick best R².
`--circuit RRC` → use specific model (existing).

### Part C — Bode Plot (already fixed)
Dual y-axis via `twinx()`, |Z| blue left, Phase red right, log-log, themed. Done in prior session.

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `cli/commands/plot.py` | Modify `_do_plot()` + `_plot_interactive()` | Add ec-eis branch, wire flags |
| `electrochem/eis.py` | Add Warburg + 2 new circuits | Required for diffusion fitting |
| `plot/eis.py` | No changes needed | Already fixed in prior session |

## Dependencies
None.

## Test Strategy
1. Run `sci plot -f <eis_file>` and verify Nyquist + Bode PDFs appear
2. Run `sci plot -f <eis_file> --nyquist` and verify only Nyquist PDF
3. Run `sci plot -f <eis_file> --bode` and verify only Bode PDF
4. Run `sci plot -f <eis_file> --circuit` and verify fit overlay PDF + console output
5. Run `sci plot -f <eis_file> --circuit RRC` and verify specific model
6. Run `sci plot -f <eis_file> --kk` and verify KK test output
7. Open PDFs and verify visually

## Progress
- [x] PLAN created
- [ ] Warburg circuits implemented
- [ ] ec-eis branch in _do_plot()
- [ ] Flags wired in _plot_interactive()
- [ ] Tested
- [ ] Committed
