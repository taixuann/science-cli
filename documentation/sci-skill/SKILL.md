---
name: science-cli
description: >
  Use when working with scientific data analysis — IV, CV, CA, EIS, Raman, AFM,
  UV-Vis, memristor characterization (endurance, retention, switching). Provides
  CLI, REPL, TUI, and AI Chat interfaces for managing projects, analyzing data,
  and generating publication-quality plots.
version: 3.11.1
author: science-cli contributors
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [science-cli, analysis, plotting, memristor, electrochemistry, spectroscopy]
    related_skills: [research-tools/quartz, research-tools/illustration, hermes-bridge-receiver]
---

# science-cli — Scientific Data CLI

## Overview

A Python CLI for managing, plotting, and analyzing experimental data — IV curves,
CV, CA, EIS, memristor switching, endurance, retention, Raman spectroscopy,
UV-Vis, AFM/SPM, and PVD deposition. Built for researchers who work with
measurement files in the terminal.

- **Source:** `~/workspace/tools/science-cli/`
- **Full docs:** `~/workspace/tools/science-cli/documentation/INDEX.md`
- **Install:** `pipx install science-cli` or `uv tool install science-cli`

## Four Interfaces

| Mode | Command | Use Case |
|------|---------|----------|
| **CLI** | `sci <command> [args]` | One-shot, scriptable, pipeable |
| **CLI-REPL** | `sci --repl` | Interactive shell with persistent session state |
| **TUI** | `sci` (no args) | Full Textual TUI with data browser, plot preview |
| **AI Chat** | `sci chat "<query>"` | Natural language → plot commands |

## Quick Start

```bash
sci add project my-project        # Create new project
sci open my-project               # Open context
sci add data ./data/*.csv         # Add measurement files
sci iv --sweep                    # Analyze IV sweep
sci plot iv --theme nature        # Plot with Nature theme
sci results --move ./figures      # Collect outputs
sci close                         # Close with auto-save
```

## Command Reference

| Command | Description |
|---------|-------------|
| `sci add` | Add project, protocol, metadata, or data files |
| `sci delete` | Delete protocol, metadata, or data |
| `sci edit` | Edit protocol or metadata |
| `sci ls` | List projects, protocols, steps, files |
| `sci open` | Open project/protocol/step context |
| `sci close` | Close context with auto-save |
| `sci config` | Manage settings — theme, techniques, devices, grammar |
| `sci status` | Show current context status |
| `sci results` | List saved results; `--move` to collect symlinks |
| `sci info` | Project manifest — machine-readable JSON for AI agents |
| `sci chat` | AI chat — natural language to plot commands via LLM |
| `sci plot` | Plot data with themes, per-technique flags, PDF/SVG/PNG |
| `sci analyze` | Run per-technique analysis with YAML output |
| `sci instrument` | Hardware/instrument model registry |
| `sci serve` | Launch interactive dashboard server |
| `sci iv` | IV sweep measurements and analysis |
| `sci pulse` | Pulse measurements (endurance, retention, STP, PPF) |
| `sci pvd` | PVD deposition records |
| `sci raman` | Raman spectroscopy |
| `sci ec` | Electrochemistry CV/CA/EIS |
| `sci afm` | AFM/SPM image analysis |
| `sci uv-vis` | UV-Vis spectroscopy |

## Supported Techniques

| Technique | Commands | Output |
|-----------|----------|--------|
| IV Sweeps | `sci iv --sweep`, `sci iv --breakdown` | I-V curves, switching ratios |
| Pulse | `sci pulse --endurance`, `sci pulse --retention` | Endurance cycles, retention decay |
| Electrochemistry | `sci ec --cv`, `sci ec --ca`, `sci ec --eis` | Cyclic voltammetry, Cottrell, Nyquist |
| Raman | `sci raman` | Horiba format, RamanSPy pipeline, peak assignment |
| UV-Vis | `sci uv-vis` | Transmission, absorbance, Tauc bandgap |
| AFM/SPM | `sci afm` | Roughness, cross-section, PSD, Gwyddion bridge |
| PVD Deposition | `sci pvd` | Layer stack, deposition parameters |

## Configuration System

4-tier inheritance: Hardcoded → Global → Project → Protocol
5-tier grammar resolution: Defaults → Device-type → Global → Project → Protocol

```bash
sci config GLOBAL set theme nature
sci instrument register keithley-4200
sci config PROJECT set grammar "{device}_{date}"
```

## Project Lifecycle

```
sci add project → sci open → add data → analyze → plot → results --move → serve
```

Full crossbar pipeline:
```
sci memristor init → sci memristor sync → analyze → dashboard
```

## Path Reference

| Resource | Path |
|----------|------|
| Source repo | `~/workspace/tools/science-cli/` |
| Documentation | `~/workspace/tools/science-cli/documentation/INDEX.md` |
| This skill | `~/workspace/tools/science-cli/documentation/sci-skill/SKILL.md` |
| Global config | `~/.config/science-cli/config.yaml` |
| Global data root | `~/science-data/` (default) |

## Integration

- **Researcher profile** loads this skill for data analysis and plotting
- **Wiki profile** references science-cli output (technique results, instrument configs)
- **Hermes bridge** tracks structural changes to this tool and auto-updates this skill
