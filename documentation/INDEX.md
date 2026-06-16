---
title: science-cli Documentation Index
description: Master navigation hub for all science-cli documentation — commands, techniques, workflows, config system, YAML schemas, theme system, AI agent skills, and Python API.
date: 2026-06-15
tags: [index, navigation, reference]
---

# science-cli v3.11.0 — Documentation Index

This is the central navigation hub for science-cli documentation. science-cli is a full-featured scientific data CLI for managing, plotting, and analyzing experimental data — IV curves, CV, CA, EIS, memristor switching, endurance, retention, Raman spectroscopy, UV-Vis, AFM/SPM, and PVD deposition.

## Quick Start

| Guide | Description |
|-------|-------------|
| [Installation](reference/installation.md) | Install from PyPI, source, or one-liner. macOS, Linux, Windows. |
| [Quick Start](reference/quick-start.md) | First project in 10 minutes — full beginner walkthrough |
| [The Four Interfaces](reference/four-interfaces.md) | CLI, CLI-REPL, TUI, AI Chat — when to use each |

## Command Reference

| Command | Doc | Description |
|---------|-----|-------------|
| `sci add` | [add.md](reference/commands/add.md) | Add project, protocol, metadata, or data files |
| `sci delete` | [delete.md](reference/commands/delete.md) | Delete protocol, metadata, or data |
| `sci edit` | [edit.md](reference/commands/edit.md) | Edit protocol or metadata |
| `sci ls` | [ls.md](reference/commands/ls.md) | List projects, protocols, steps, files |
| `sci open` | [open.md](reference/commands/open.md) | Open project/protocol/step context |
| `sci close` | [close.md](reference/commands/close.md) | Close context with auto-save |
| `sci config` | [config.md](reference/commands/config.md) | Manage settings — theme, techniques, devices, grammar |
| `sci status` | [status.md](reference/commands/status.md) | Show current context status |
| `sci results` | [results.md](reference/commands/results.md) | List saved results; `--move` to collect symlinks |
| `sci info` | [info.md](reference/commands/info.md) | Project manifest — machine-readable JSON for AI agents |
| `sci chat` | [chat.md](reference/commands/chat.md) | AI chat — natural language to plot commands via LLM |
| `sci plot` | [plot.md](reference/commands/plot.md) | Plot data with themes, per-technique flags, output to PDF/SVG/PNG |
| `sci analyze` | [analyze.md](reference/commands/analyze.md) | Run per-technique analysis with YAML output |
| `sci instrument` | [instrument.md](reference/commands/instrument.md) | Hardware/instrument model registry |
| `sci serve` | [serve.md](reference/commands/serve.md) | Launch interactive dashboard server |
| `sci iv` | [iv.md](reference/commands/iv.md) | IV sweep measurements |
| `sci pulse` | [pulse.md](reference/commands/pulse.md) | Pulse measurements |
| `sci pvd` | [pvd.md](reference/commands/pvd.md) | PVD deposition records |
| `sci raman` | [raman.md](reference/commands/raman.md) | Raman spectroscopy |
| `sci ec` | [ec.md](reference/commands/ec.md) | Electrochemistry CV/CA/EIS |
| `sci afm` | [afm.md](reference/commands/afm.md) | AFM/SPM image analysis |
| `sci uv-vis` | [uv-vis.md](reference/commands/uv-vis.md) | UV-Vis spectroscopy |
| `sci memristor` | [memristor.md](reference/commands/memristor.md) | [DEPRECATED] Use `sci iv` or `sci pulse` |
| `sci techniques` | [techniques.md](reference/commands/techniques.md) | [DEPRECATED] Use `config list techniques` |

## Technique Guides (Phase 3)

| Guide | Techniques |
|-------|-----------|
| [IV Sweeps](techniques/iv-sweeps.md) (Phase 3) | iv-sweep, iv-breakdown, iv-leakage — volatile vs bipolar |
| [Pulse Measurements](techniques/pulse-measurements.md) (Phase 3) | endurance, retention, STP, PPF, switching |
| [Electrochemistry](techniques/electrochemistry.md) | CV, CA, EIS — existing guide moved from `documentation/library/` |
| [Crossbar Characterization](techniques/crossbar-characterization.md) | Memristor pipeline: init → sync → analyze → dashboard |
| [Raman Spectroscopy](techniques/raman-spectroscopy.md) (Phase 3) | Horiba format, RamanSPy pipeline, peak assignment |
| [UV-Vis Spectroscopy](techniques/uv-vis-spectroscopy.md) (Phase 3) | Transmission, absorbance, Tauc bandgap |
| [AFM/SPM](techniques/afm-spm.md) (Phase 3) | Roughness, cross-section, PSD, Gwyddion bridge |
| [PVD Deposition](techniques/pvd-deposition.md) (Phase 3) | Layer stack, deposition parameters |

## Configuration System

| Reference | Description |
|-----------|-------------|
| [Config System Reference](reference/config-system.md) | Complete 4-tier inheritance chain, 5-tier grammar resolution |
| 4-Tier Inheritance | Hardcoded → Global → Project → Protocol |
| 5-Tier Grammar | Defaults → Device-type → Global → Project → Protocol |
| `sci config` subcommands | GLOBAL, THEME, TECHNIQUE, INSTRUMENT, GRAMMAR groups |
| `sci instrument` registry | Built-in instruments, registration, assignment |

## Workflows (Phase 4)

| Workflow | Steps |
|----------|-------|
| Full Project Lifecycle | config init → add/open project → add protocol → add data → analyze → plot → results --move → serve |
| Crossbar Characterization | memristor init → sync → analyze → dashboard |
| Electrochemistry Analysis | CV scan → peak analysis → CA Cottrell → EIS Nyquist/Bode |
| Raman Processing | Denoise → baseline → normalize → peak detect |
| Pulse Characterization | Endurance → retention → STP → PPF |
| Multi-Technique Analysis | Combined IV + Raman + AFM |
| Instrument Management | Register → configure → assign → verify |
| Results Collection | `results --move` → symlinks → manifest.json |

## Tutorials (Phase 4)

| Tutorial | Description |
|----------|-------------|
| Beginner Quickstart | First project in 10 minutes |
| IV Characterization | Full IV characterization session |
| Multi-Protocol Project | IV + Raman + AFM combined |
| Custom Instrument | Adding a custom instrument |
| Custom Grammar | Customizing filename grammar |
| Dashboard Deployment | `sci serve` in production |

## YAML Schemas

| Schema | Description |
|--------|-------------|
| [Protocol YAML](schemas/protocol-yaml.md) | Protocol structure: devices, steps, files, grammar |
| [Analysis YAML](schemas/analysis-yaml.md) | Per-technique analysis output schemas |
| [Config YAML](schemas/config-yaml.md) | Global and per-project config formats |
| Instrument YAML | Instrument registration template format |

## Theme System

| Reference | Description |
|-----------|-------------|
| [Theme Reference](themes/theme-reference.md) | All 7 built-in themes, RC parameters, plot templates |

## AI Agent Skills (Phase 5)

| Skill | Scope | Status |
|-------|-------|--------|
| `sci-operator` | Full operational knowledge — all commands, config, project lifecycle | Skill dir created |
| `sci-plotting` | Plotting-specific — technique flags, theme system, dispatch | Skill dir created |
| `sci-analysis` | Analysis-specific — per-technique analyzers, YAML output | Skill dir created |
| `sci-config` | Config management — grammar, instruments, devices | Skill dir created |
| `sci-iv` | IV sweep analysis domain knowledge | Skill dir created |
| `sci-pulse` | Pulse measurement analysis domain knowledge | Skill dir created |
| `sci-raman` | Raman spectroscopy (update existing skill) | Existing at `.opencode/skills/sci-raman/` |
| `sci-ec` | Electrochemistry domain knowledge | Skill dir created |
| `sci-afm` | AFM/SPM image analysis domain knowledge | Skill dir created |
| `sci-uv-vis` | UV-Vis spectroscopy domain knowledge | Skill dir created |
| `sci-pvd` | PVD deposition domain knowledge | Skill dir created |
| `sci-serve` | Dashboard server domain knowledge | Skill dir created |
| `sci-project-lifecycle` | End-to-end project lifecycle | Skill dir created |

## Python API (Phase 4)

Developer reference for internal modules — config API, data loading, technique detection, routing, library modules (iv, pulse, ec, afm, pvd), plotting subsystem, theme programming API, analysis validators.

## See Also

- [README.md](../README.md) — Quick-start, command reference, architecture overview
- [CHANGELOG.md](../CHANGELOG.md) — Full version history (2.0.0 → 3.11.0)
