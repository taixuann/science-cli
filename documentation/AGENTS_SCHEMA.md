# AGENTS_SCHEMA.md — AI Agent Reference for science-cli

This document defines the machine-readable interface that AI agents (OpenCode, plotting-guy, etc.) use to discover project structure and generate `sci` CLI commands.

## Quick Start for AI Agents

```bash
# Run this FIRST to discover everything about the project
sci info --json

# Quick status check
sci status --json

# List protocols/steps/files
sci ls --json
```

## Project Directory Layout

```
<project_root>/
├── data/
│   └── raw/                    ← Raw measurement files
├── protocol/
│   └── <protocol_name>/
│       ├── <protocol_name>.yaml  ← Protocol descriptor
│       ├── devices.yaml         ← Memristor crossbar mapping
│       └── <step_name>/
│           ├── <data_files>...   ← CSV/TSV measurement files
│           └── results/          ← Generated PDFs/JSON
├── results/                     ← Project-level outputs
└── sci-config.yaml              ← Per-project config overrides
```

## Commands for AI Agents

### Discovery

| Command | Output | Use |
|---------|--------|-----|
| `sci info --json` | Full project manifest | Primary discovery — protocols, steps, files, themes, techniques, plot hints |
| `sci ls --json` | Protocols with steps/files | Quick listing |
| `sci ls -m project --json` | All projects | Cross-project discovery |
| `sci ls <step> --json` | Files in a step | Step-level file listing |
| `sci status --json` | Session state + project | Current context |

### Plotting

| Command | Purpose |
|---------|---------|
| `sci plot <file> [flags]` | Plot a single file |
| `sci plot --overlay <file1,file2,...> --label-name <l1,l2,...> [flags]` | Overlay multiple files |
| `sci memristor dashboard [--open]` | Crossbar device dashboard |
| `sci memristor plot <device_id>` | Plot specific device |
| `sci raman plot <file>` | Raman spectrum |
| `sci eis <file> --nyquist \| --bode` | EIS analysis |

### Universal Plot Flags

| Flag | Description |
|------|-------------|
| `--loglog` | Log-log axes |
| `--type line\|scatter` | Plot type |
| `--color <color>` | Override color |
| `--linewidth <n>` | Line width |
| `--linestyle -\|\--\|:\|-` | Line style |
| `--xlabel <text>` | X axis label |
| `--ylabel <text>` | Y axis label |
| `--title <text>` | Plot title |
| `--zoom x1,x2` | Zoom X axis |
| `--zoom x1,x2,y1,y2` | Zoom X and Y axes |
| `--grid` | Show grid |
| `--legend` | Show legend |
| `--theme <name>` | Use specific theme |
| `-n <name>.pdf` | Output filename |
| `--dpi <n>` | Resolution (default 150) |
| `--label-name <l1,l2,...>` | Custom labels for overlay |
| `--abs-y` | Absolute Y values |
| `--marker o\|s\|^` | Marker style |
| `--size <w>,<h>` | Figure size in inches |

### Available Themes

`publication-acs`, `publication-nature`, `poster`, `dark`, `default`, `tufte`, `acs-annotated`

Default: `publication-acs`. Only override with `--theme` when explicitly requested.

## The `sci info --json` Schema

```json
{
  "science_cli_version": "2.1.1",
  "project": {
    "name": "...",
    "path": "/abs/path",
    "theme": "publication-acs",
    "raw_file_count": 42,
    "protocol_count": 3
  },
  "session": {
    "last_project": "...",
    "last_protocol": "...",
    "last_step": "...",
    "theme": "publication-acs"
  },
  "protocols": [
    {
      "name": "1_iv-test",
      "description": "...",
      "device": {"rows": 6, "cols": 6},
      "step_count": 2,
      "steps": [
        {
          "name": "1_set",
          "technique": "mem-switching",
          "device": "keithley-2400",
          "description": "...",
          "file_count": 10,
          "files": [
            {
              "name": "IV_data_R1C1.csv",
              "path": "protocol/1_iv-test/1_set/IV_data_R1C1.csv",
              "technique": "iv-sweep",
              "size": 12345,
              "sweep_order": 1,
              "sweep_type": "forming"
            }
          ]
        }
      ]
    }
  ],
  "themes": ["publication-acs", "dark", ...],
  "techniques": [{"slug": "iv-sweep", "devices": [...]}],
  "plot_hints": {
    "iv-sweep": {
      "plot_style": "--type line|scatter | --color | --linewidth | --linestyle",
      "figure": "-n iv_curve.pdf | --label-name label1 | --xlabel | --ylabel | --zoom"
    }
  }
}
```

## Agent Workflow

### Basic Plot

```
1. sci info --json → parse output
2. Find file: iterate protocols[].steps[].files[] for matching path
3. Check technique: file.technique or step.technique
4. Look up flags: plot_hints[technique]
5. Construct: sci plot <file.path> <relevant flags>
6. Execute the command
```

### Overlay Plot

```
1. Find multiple files from info output
2. Construct: sci plot --overlay file1,file2,file3 --label-name Label1,Label2,Label3 [flags]
3. Execute
```

### Dashboard

```
sci memristor dashboard --open
```

## Rules for AI Agents

1. **ALWAYS run `sci info --json` first** — it's the single source of truth
2. **NEVER invent file paths** — use exact paths from the JSON output
3. **NEVER generate matplotlib/seaborn/plotly code** — always use `sci` CLI
4. **Follow existing themes** — use session theme unless user asks otherwise
5. **All plots output to PDF** — do not try to display inline
6. **Quote paths with spaces** — use proper shell quoting
7. **One command at a time** — `sci plot` handles one file or overlay; multiple files need multiple commands
