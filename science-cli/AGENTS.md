# AGENTS.md — science-cli Developer Reference

## Session Workflow (Read This First)

Every session follows this loop. **Do not skip steps.**

### Phase 0: Orient (Before Any Work)
1. Read `README.md` — understand the project from the user's perspective
2. Read `src/science_cli/core/README.md` — understand core modules
3. Read `src/science_cli/plot/README.md` — understand plot architecture
4. Read `src/science_cli/theme/README.md` — understand theme system
5. Read `documentation/plans/` — check if there's an active PLAN for this topic
   - If a PLAN exists: read it to know what's being worked on, what changed, what's next
   - If no PLAN exists: you'll create one in Phase 1

**Why**: This replaces re-reading the entire codebase. READMEs tell you the current state. PLANs tell you what's in progress.

### Phase 1: Plan (Before Any Code Changes)
When the user asks for a change, **always create or update a PLAN first**:

1. Create `documentation/plans/PLAN-<short-topic>.md` using the template below
2. Fill in: Objective, Context, Specification, Files to Modify, Dependencies, Test Strategy
3. Present the PLAN to the user for approval
4. Do NOT write code until the user approves

**PLAN Template:**
```markdown
# PLAN: <short-title>

## Status
- **Created**: YYYY-MM-DD
- **Status**: draft | in-progress | completed | superseded
- **Branch**: <branch-name>

## Objective
<1-2 sentences>

## Context
<What exists? What problem? Link related plans.>

## Specification
<Detailed spec>

## Files to Modify
| File | Action | Reason |
|------|--------|--------|

## Dependencies
<What must exist first?>

## Test Strategy
<How to verify>

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
```

### Phase 2: Implement
- Follow the PLAN exactly
- Use CodeGraph (`.codegraph/`) for exploration — prefer `codegraph search` over reading files
- Never break existing functionality
- Follow existing code style (PEP 8, type hints, f-strings, pathlib)

### Phase 3: Test
- Run existing tests
- Verify no regressions
- Add new tests if needed

### Phase 4: Update Documentation (ALWAYS — Never Skip)
**This is the last step before commit. Every time.**

1. Update `README.md` — reflect new features, changed behavior, new commands
2. Update `AGENTS.md` (this file) — update directory map, guardrails, patterns if structure changed
3. Update relevant module `README.md` — if new module created or module behavior changed
   - `src/science_cli/core/README.md`
   - `src/science_cli/plot/README.md`
   - `src/science_cli/theme/README.md`
4. Update the PLAN file — mark progress, note what changed, mark completed
5. Run `codegraph sync` — keep the index current

### Phase 5: Commit
- Commit with descriptive message
- Push branch if requested

---

## Documentation Structure

```
documentation/
├── plans/              ← One PLAN.md per topic/feature
│   └── (active plans live here, completed plans stay for reference)
└── instructions/       ← Reusable guides, workflows (future)
```

**Rules:**
- Each PLAN is self-contained — no need to read other files to understand it
- Multiple PLANs can exist simultaneously for different topics
- A PLAN is `superseded` when a newer plan replaces it
- Completed PLANs stay — they serve as history and context

---

## Directory Map

```
science-cli/
├── AGENTS.md                          ← This file (agent workflow + reference)
├── README.md                          ← User-facing documentation
├── documentation/                     ← Plans and instructions
│   ├── plans/                         ← PLAN.md files (one per topic)
│   └── instructions/                  ← Reusable guides
├── pyproject.toml                     ← Build config, dependencies, entry points
├── bin/sci                            ← Shell entry point
├── scripts/                           ← Dev/utility scripts
├── theme-previews/                    ← Generated theme preview PDFs
├── test_changes.py                    ← Smoke tests
├── test_guardrails.py                 ← Architecture guardrail tests
├── .codegraph/                        ← CodeGraph index
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
    │   │   ├── extensions_cmd.py      ← extensions list handler
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
    ├── tui/                           ← Textual TUI
    └── extensions.py                  ← ExtensionRegistry + entry-point discovery
```

---

## Where to Add New Features

### Adding a New CLI Command
1. Create `src/science_cli/cli/commands/<name>_cmd.py`
2. Define a `<name>_handler(args)` function
3. Import it in `src/science_cli/cli/commands/__init__.py`
4. Add it to `COMMAND_TREE` dict in `__init__.py`

### Adding a New Plot Type
1. Create `src/science_cli/plot/<technique>.py`
2. Define a `plot_<technique>(fig, ax, df, flags)` function
3. Import from `plot/base.py` (canonical), NOT from `plot/__init__.py`

### Adding a New Theme
1. Create `src/science_cli/theme/themes/<name>.yaml`
2. Follow schema: `figure`, `axes`, `font`, `colors`, `savefig` sections
3. Auto-discovered by `list_themes()` in `registry.py`

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
Devices live under their parent technique:
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
Same device name can appear under multiple techniques with different column mappings.

---

## What NOT to Do (Guardrails)

### Never:
- **Add hardcoded device-specific logic to data_loader.py** — use the config system
- **Add new hardcoded technique patterns directly to technique.py** — add via config or extensions
- **Create new top-level modules in science_cli/** — use core/, cli/, plot/, theme/
- **Modify config.py (legacy) for new features** — use core/config.py
- **Remove hardcoded defaults from technique.py or data_loader.py** — they are fallbacks
- **Add commands without registering in COMMAND_TREE** — they won't be accessible
- **Hardcode file paths** — use pathlib and config-based resolution
- **Import from cli/commands in core/ modules** — core must not depend on CLI
- **Commit theme-previews/** — generated files
- **Skip the documentation update step** — Phase 4 is mandatory

### Always:
- Follow PEP 8, type hints, f-strings, pathlib
- Read all READMEs before starting work (Phase 0)
- Create a PLAN before any code changes (Phase 1)
- Update README.md, AGENTS.md, and module READMEs as the LAST step (Phase 4)
- Run `codegraph sync` after structural changes

---

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
    )
```

Extensions are discovered via Python entry points (`science_cli.extensions` group)
and via the config file system. Config techniques have lower priority than Python extensions.

---

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
    get_device_config,       # → dict or None
    get_technique_patterns,  # → list[str]
    get_default_device,      # → str
    get_projects_root,       # → Path
    get_header_marker,       # → str
    get_merged_config,       # → dict (raw)
)
```

---

## CodeGraph Usage

```bash
codegraph sync                        # Update index after structural changes
codegraph search "detect_technique"   # Find symbols by name
codegraph context "how does plot work" # Build context for a task
codegraph stats                       # Index health and statistics
```

The `.codegraph/config.json` exclude list keeps generated/binary files out of the index.
**Always use CodeGraph before reading files** — it returns source code sections directly.
