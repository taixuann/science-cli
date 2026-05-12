# AGENTS.md — science-cli Developer Reference

## Directory Map

```
science-cli/
├── AGENTS.md                          ← This file
├── README.md                          ← User-facing documentation
├── pyproject.toml                     ← Build config, dependencies, entry points
├── bin/                               ← Shell helper scripts
├── scripts/                           ← Dev/utility scripts (e.g. theme previews)
├── theme-previews/                    ← Generated theme preview PDFs
├── test_changes.py                    ← Smoke tests
├── .codegraph/                        ← CodeGraph index (see below)
└── src/science_cli/
    ├── __init__.py                    ← __version__
    ├── app.py                         ← CLI entry point (run_cli + REPL)
    ├── config.py                      ← Legacy config (theme, projects_root)
    │
    ├── cli/                           ← CLI dispatch layer
    │   ├── commands/                  ← One module per command
    │   │   ├── __init__.py            ← COMMAND_TREE (all registered commands)
    │   │   ├── add.py                 ← add handler
    │   │   ├── analyze.py             ← analyze handler
    │   │   ├── config.py              ← config handler (theme, init, show)
    │   │   ├── data_cmd.py            ← data handler (import/export/assign)
    │   │   ├── delete_cmd.py          ← delete handler
    │   │   ├── edit_cmd.py            ← edit handler
    │   │   ├── eis.py                 ← EIS fitting helpers
    │   │   ├── extensions.py          ← extensions list handler
    │   │   ├── fit.py                 ← fit handler
    │   │   ├── ls_cmd.py              ← ls handler
    │   │   ├── memristor_cmd.py       ← memristor handler
    │   │   ├── metadata.py            ← metadata handler
    │   │   ├── open_cmd.py            ← open handler
    │   │   ├── parse.py               ← parse handler
    │   │   ├── plot.py                ← plot handler
    │   │   ├── project.py             ← project handler
    │   │   ├── protocol.py            ← protocol handler
    │   │   ├── results.py             ← results handler
    │   │   └── techniques.py          ← techniques handler
    │   └── help.py                    ← Help text rendering
    │
    ├── core/                          ← Core library — no CLI coupling
    │   ├── config.py                  ← ** Device-aware config system **
    │   ├── data_loader.py             ← File → DataFrame (device-aware)
    │   ├── file_utils.py              ← File I/O utilities
    │   ├── fzf_utils.py               ← fzf integration
    │   ├── legacy.py                  ← Backward-compat shims
    │   ├── manifest.py                ← Manifest management
    │   ├── paths.py                   ← ProjectPaths (directory layout)
    │   ├── project.py                 ← Project path resolution
    │   ├── protocol.py                ← Protocol YAML management
    │   ├── session.py                 ← Session state (JSON)
    │   ├── sweep_metadata.py          ← IV sweep segment detection
    │   └── technique.py               ← Technique detection from filenames
    │
    ├── plot/                          ← Plot engine
    │   ├── __init__.py                ← Re-exports + figure utilities
    │   ├── base.py                    ← ** Canonical base ** — create_figure, save_figure
    │   ├── ca.py                      ← Chronoamperometry plots
    │   ├── cv.py                      ← Cyclic voltammetry plots
    │   ├── eis.py                     ← EIS plots (Nyquist, Bode)
    │   ├── eis_circuits.py            ← EIS circuit fitting models
    │   └── overlays.py                ← Multi-file overlay plots
    │
    ├── theme/                         ← Theme & template system
    │   ├── __init__.py                ← Public API + matcha colors
    │   ├── registry.py                ← Theme/template registry + YAML loader
    │   ├── themes/                    ← Global style themes (*.yaml)
    │   └── templates/                 ← Per-technique defaults (*.yaml)
    │
    ├── tui/                           ← Textual TUI (if present)
    └── extensions.py                  ← ExtensionRegistry + entry-point discovery
```

## Where to Add New Features

### Adding a New CLI Command

1. Create `src/science_cli/cli/commands/<name>_cmd.py`
2. Define a `<name>_handler(args)` function
3. Import it in `src/science_cli/cli/commands/__init__.py`
4. Add it to `COMMAND_TREE` dict in `__init__.py`

**Pattern:**
```python
# cli/commands/my_cmd.py
from rich.console import Console
console = Console()

def my_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        console.print("[yellow]Usage: sci my <sub> [options][/yellow]")
        return
    # handle subcommands
```

### Adding a New Plot Type

1. Create `src/science_cli/plot/<technique>.py`
2. Define a `plot_<technique>(fig, ax, df, flags)` function
3. Import and dispatch from `src/science_cli/plot/base.py` or the `plot` command handler

**Pattern:**
```python
# plot/new_tech.py
def plot_new_tech(fig, ax, df, flags, xcol="", ycol=""):
    """Plot description."""
    x = df[xcol] if xcol in df.columns else df.iloc[:, 0]
    y = df[ycol] if ycol in df.columns else df.iloc[:, 1]
    ax.plot(x, y, **flags.get("line_kw", {}))
```

### Adding a New Theme

1. Create `src/science_cli/theme/themes/<name>.yaml`
2. Follow the schema: `figure`, `axes`, `font`, `colors`, `savefig` sections
3. The theme is auto-discovered by `list_themes()` in `registry.py`

**Pattern:**
```yaml
figure:
  facecolor: white
  figsize: [3.46, 2.75]
  dpi: 300
axes:
  edgecolor: black
font:
  family: sans-serif
  size: 7
colors:
  prop_cycle:
    - "#0072B2"
```

### Adding a New Technique (in Config)

Add to `~/.config/science-cli/config.yaml` or `<project>/sci-config.yaml`:

```yaml
techniques:
  my-technique:
    patterns: ["*MYTECH*", "*mtech*"]
    header_marker: "Time"
    devices:
      my-device:
        delimiter: ","
        decimal: "."
        header_lines: 5
        encoding: "utf-8"
        columns:
          time: "Timestamp"
          value: "Reading"

defaults:
  my-technique: my-device
```

### Adding a New Device Config

Devices live under their parent technique. A device config specifies how to load
files produced by that instrument:

```yaml
techniques:
  ec-eis:
    devices:
      new-instrument:
        delimiter: "\t"
        decimal: "."
        header_lines: 3
        encoding: "utf-8"
        columns:
          frequency: "Freq/Hz"
          z_real: "Z'/Ohm"
          z_imag: "-Z''/Ohm"
```

The same device name can appear under multiple techniques (e.g., `biologic-mpt`
under both `ec-eis` and `ec-cv` with different column mappings).

## What NOT to Do (Guardrails)

### Never:
- **Add hardcoded device-specific logic to data_loader.py** — use the config system instead
- **Add new hardcoded technique patterns directly to technique.py** — add via config or extensions
- **Create new top-level modules in science_cli/** — use core/, cli/, plot/, theme/
- **Modify config.py (legacy) to add new features** — use core/config.py (the new system)
- **Remove hardcoded defaults from technique.py or data_loader.py** — they are fallbacks
- **Add commands without registering them in COMMAND_TREE** — they won't be accessible
- **Hardcode file paths** — use `pathlib` and config-based resolution
- **Import from cli/commands in core/ modules** — core must not depend on CLI
- **Commit theme-previews/** — generated files, excluded from version control

### Always:
- Follow PEP 8, use type hints, f-strings, pathlib
- Tests go in `test_changes.py` or project root
- Documentation goes in README.md (user-facing) or AGENTS.md (dev-facing)
- Run `codegraph sync` after adding new modules

## Extension System Overview

Extensions are Python packages that register with `ExtensionRegistry`:

```python
from science_cli.extensions import ColumnMap, ExtensionRegistry, TechniqueDef

def register(registry: ExtensionRegistry):
    registry.name = "science-memristor"
    registry.techniques["mem-switching"] = TechniqueDef(
        name="mem-switching", label="Switching",
        patterns=["_switch", ".sw"],
    )
    registry.column_maps["mem-switching"] = ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
    )
```

Extensions are discovered via Python entry points (`science_cli.extensions` group)
and via the config file system. The config system adds techniques as "config extensions"
with lower priority than Python extensions.

## Config System Architecture

```
Hardcoded defaults (core/config.py)
       ↓ overridden by
Global config (~/.config/science-cli/config.yaml)
       ↓ overridden by
Per-project config (<project_root>/sci-config.yaml)
       ↓
Merged config (get_merged_config())
```

**Key modules:**
- `core/config.py` — loading, merging, caching, typed accessors
- `extensions.py` — registers config techniques in ExtensionRegistry
- `core/technique.py` — consults config for filename patterns
- `core/data_loader.py` — consults config for device loading params
- `core/project.py` — consults config for projects_root
- `cli/commands/config.py` — `config init` and `config show` commands

**Typed accessors:**
```python
from science_cli.core.config import (
    get_device_config,      # → dict or None
    get_technique_patterns,  # → list[str]
    get_default_device,      # → str
    get_projects_root,       # → Path
    get_header_marker,       # → str
    get_merged_config,       # → dict (raw)
)
```

## CodeGraph Usage

```bash
# Sync index after structural changes
codegraph sync

# Search
codegraph search "detect_technique" --language python

# Stats
codegraph stats
```

The `.codegraph/config.json` exclude list keeps generated/binary files out of the index.
