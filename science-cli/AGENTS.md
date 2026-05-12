# AGENTS.md — science-cli Developer Reference

## Session Workflow (Read This First)

Every session follows this loop. **Do not skip steps.**

### Phase 0: Orient (Before Any Work)
1. Run `codegraph stats` — verify index is current, note file/symbol counts
2. Read `README.md` — understand the project from the user's perspective
3. Read `src/science_cli/core/README.md` — understand core modules
4. Read `src/science_cli/plot/README.md` — understand plot architecture
5. Read `src/science_cli/theme/README.md` — understand theme system
6. Read `documentation/plans/` — check if there's an active PLAN for this topic
   - If a PLAN exists: read it to know what's being worked on, what changed, what's next
   - If no PLAN exists: you'll create one in Phase 1

**Why**: CodeGraph stats tell you the index health. READMEs tell you the current state. PLANs tell you what's in progress. This replaces re-reading the entire codebase.

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
- **Use CodeGraph for ALL exploration** — see "CodeGraph Integration" section below
  - `codegraph search "symbol"` to find definitions
  - `codegraph context "how does X work"` to understand features
  - `codegraph context "impact of changing X"` before editing
- Only read files when CodeGraph doesn't have the answer (YAML files, new files)
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
5. **Check for cross-PLAN impacts** — if this change affects another PLAN:
   - Update that PLAN with a `Cross-PLAN Update` section
   - Tell the user which PLANs were affected
6. Run `codegraph sync` — keep the index current

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

### Cross-PLAN Tracking (Critical)

**When one PLAN affects another, you MUST update both.**

1. **Declare relationships**: Every PLAN must list `Related Plans` and explain the relationship
   - `blocks` — this PLAN must complete before the other can start
   - `blocked-by` — this PLAN depends on another completing first
   - `affects` — this PLAN changes something the other PLAN also touches
   - `related` — shares context but no direct dependency

2. **Update impacted PLANs**: When implementing PLAN-A and you discover it changes something PLAN-B also touches:
   - Update PLAN-A: note the change in `Specification` and `Progress`
   - Update PLAN-B: add a `Cross-PLAN Update` section noting what changed and what needs adjustment
   - Tell the user: "PLAN-A affects PLAN-B — I've updated both. Review PLAN-B before proceeding."

3. **Split large changes**: If a single change touches multiple domains (commands + config + extensions), split into linked PLANs rather than one mega-PLAN. Each PLAN should be independently completable.

4. **Execution order**: Respect `blocks`/`blocked-by` relationships. Complete blocking PLANs first.

**Example PLAN relationships:**
```
PLAN-command-restructure
  └─ blocks → PLAN-extension-interface (commands must exist before extensions can use them)
  └─ affects → PLAN-config-expansion (both touch session state)

PLAN-config-expansion
  └─ blocked-by → PLAN-command-restructure
  └─ affects → PLAN-version-bump (config changes justify version bump)
```

### PLAN Template (with Cross-PLAN Support)
```markdown
# PLAN: <short-title>

## Classification
<command-restructure | config | extension | docs | refactor | cleanup | feature>

## Related Plans
- [[PLAN-other-topic]] — blocks/affects/blocked-by/related — <why>

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
<What must exist first? Link to blocking PLANs.>

## Cross-PLAN Impact
<What other PLANs does this affect? What needs updating?>

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
- Run `codegraph stats` in Phase 0 to verify index health
- Use CodeGraph for exploration BEFORE reading files
- Read all READMEs before starting work (Phase 0)
- Create a PLAN before any code changes (Phase 1)
- **Check for cross-PLAN impacts** — if your change affects another PLAN, update both
- **Declare relationships** — every PLAN must list Related Plans with blocks/affects/blocked-by
- Update README.md, AGENTS.md, and module READMEs as the LAST step (Phase 4)
- Run `codegraph sync` after structural changes (Phase 4)
- **Check Gaps section** — before creating a new PLAN, check if it's already listed as a gap

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

## Gaps and Missing Things

**Known gaps in the codebase and workflow. This section is updated after every session.**
**Do NOT execute gaps automatically — each gap needs a PLAN and user approval.**

### Completed (No Longer Gaps)

| Item | Completed In | Notes |
|------|-------------|-------|
| CodeGraph integration | cleanup/architecture-guardrails | `.codegraph/` initialized, AGENTS.md has full integration guide |
| 3-tier config system | cleanup/architecture-guardrails | `core/config.py` — hardcoded ← global ← project |
| Device-aware data loading | cleanup/architecture-guardrails | `core/data_loader.py` accepts `device=` and `technique=` params |
| Dead code cleanup | cleanup/architecture-guardrails | Removed image.py, general.py, functions/ directory |
| Module READMEs | cleanup/architecture-guardrails | core/README.md, plot/README.md, theme/README.md |
| AGENTS.md workflow | cleanup/architecture-guardrails | 5-phase workflow, cross-PLAN tracking, CodeGraph integration |
| documentation/ structure | cleanup/architecture-guardrails | plans/ and instructions/ directories created |
| Architecture guardrail tests | cleanup/architecture-guardrails | test_guardrails.py — 16 tests passing |
| PLAN files created | cleanup/architecture-guardrails | 4 PLANs created with cross-PLAN relationships |

### Active Gaps (Need Execution)

**PLANs are created but not yet executed. Each gap below has a corresponding PLAN.**

#### Command & Session Gaps

| Gap | Impact | Priority | PLAN | Status |
|-----|--------|----------|------|--------|
| **Command restructuring** | `project` command still exists, `close` missing, `open`/`ls`/`add` don't support `-m project` | HIGH | PLAN-1 | PLAN created, not executed |
| **3-level state memory** | Session only tracks project + protocol, not step. Close doesn't save state per level | HIGH | PLAN-1 | PLAN created, not executed |

#### Config Gaps

| Gap | Impact | Priority | PLAN | Status |
|-----|--------|----------|------|--------|
| **Technique-specific configs** | No per-technique YAML configs for patterns, devices, delimiters | HIGH | PLAN-2 | PLAN created, not executed |
| **Config command expansion** | `config` only handles themes, needs `set technique`, `edit` subcommands | MEDIUM | PLAN-2 | PLAN created, not executed |

#### Extension Gaps

| Gap | Impact | Priority | PLAN | Status |
|-----|--------|----------|------|--------|
| **`ext <name> <subcommand>` interface** | No unified extension command interface | MEDIUM | PLAN-3 | PLAN created, not executed |
| **Extension docs missing** | science-* extensions not documented in AGENTS.md or README | LOW | — | Needs separate PLAN |
| **Extensions not merged into core** | science-iv, science-memristor, science-electrochem still external | LOW | — | Future work |

#### Project Health Gaps

| Gap | Impact | Priority | Notes |
|-----|--------|----------|-------|
| **No test suite** | No automated regression testing beyond 16 guardrail tests | HIGH | Need pytest structure with `tests/` directory, fixtures, parametrized tests |
| **No CI/CD** | No automated testing on push | MEDIUM | Need GitHub Actions workflow: lint → test → build |
| **No CHANGELOG** | Users can't track changes between versions | MEDIUM | Need `CHANGELOG.md` following Keep a Changelog format |
| **No LICENSE** | Cannot be used as open-source | HIGH | Need to choose license (MIT? Apache 2.0?) |
| **No lock file** | Reproducible installs not guaranteed | MEDIUM | Need `requirements.txt` or `poetry.lock` |
| **No type checking** | Type hints exist but not enforced | LOW | Need `mypy` or `pyright` config + `py.typed` marker |
| **No linting config** | Inconsistent code style possible | LOW | Need `ruff.toml` or `.flake8` |
| **No CONTRIBUTING guide** | New contributors don't know how to help | LOW | Need `CONTRIBUTING.md` |
| **No TUI README** | `tui/` module undocumented | LOW | Need `src/science_cli/tui/README.md` |
| **No migration guide** | Users upgrading from v1 don't know what changed | MEDIUM | Need `MIGRATION.md` for version upgrades |

### Pending PLANs

| PLAN | Classification | Status | Blocks | Blocked By |
|------|----------------|--------|--------|------------|
| PLAN-1: Command Restructuring | command-restructure | **Created** | PLAN-2, PLAN-3 | — |
| PLAN-2: Config Expansion | config | **Created** | — | PLAN-1 |
| PLAN-3: Extension Interface | extension | **Created** | — | PLAN-1 |
| PLAN-4: Version Bump to 2.0.0 | cleanup | **Created** | — | PLAN-1, PLAN-2, PLAN-3 |

**Execution order**: PLAN-1 → PLAN-2 + PLAN-3 (parallel) → PLAN-4

**When creating a new PLAN, check if it relates to any of these pending items.**

---

## CodeGraph Integration (Use This First)

CodeGraph (`.codegraph/`) is a pre-indexed knowledge graph of this codebase.
**Always use CodeGraph before reading files** — it returns source code sections directly
and traces relationships across the entire project.

### When to Use CodeGraph vs Reading Files

| Task | Use | Why |
|------|-----|-----|
| "Where is function X defined?" | `codegraph search "X"` | Instant, no file scanning |
| "What calls function X?" | `codegraph context "what calls X"` | Traces full call chain |
| "How does feature Y work?" | `codegraph context "how does Y work"` | Returns entry points + related symbols + source |
| "What will break if I change X?" | `codegraph context "impact of changing X"` | Shows callers, callees, dependents |
| "What imports module Z?" | `codegraph search "import Z"` | Finds all import sites |
| Read a specific file I already know | `read <file>` | You know the path, just need content |
| Explore unknown area | CodeGraph FIRST, then read | Graph tells you which files matter |

### CodeGraph Commands by Workflow Phase

#### Phase 0: Orient
```bash
# Get the big picture
codegraph context "architecture of science-cli"

# Find all entry points
codegraph search "run_cli"
codegraph search "handler" --kind function

# See what modules exist
codegraph stats
```

#### Phase 1: Plan
```bash
# Understand what exists before proposing changes
codegraph search "detect_technique"          # Find current technique detection
codegraph context "how are commands registered"  # Understand COMMAND_TREE
codegraph search "ColumnMap"                 # See extension system

# Trace relationships before planning changes
codegraph context "what uses data_loader"    # See all consumers
codegraph context "what imports technique"   # See technique dependents
```

#### Phase 2: Implement
```bash
# Find where to add new code
codegraph search "COMMAND_TREE"              # See command registration pattern
codegraph context "how to add a new command" # Returns registration flow

# Before editing, check impact
codegraph context "impact of changing plot.py"  # See what depends on plot

# Verify your changes don't break imports
codegraph search "<new_function_name>"       # Confirm it's findable
```

#### Phase 3: Test
```bash
# Verify symbols are indexed
codegraph search "<new_function>"
codegraph search "<new_class>"

# Check file is indexed
codegraph stats  # Should show increased file count
```

#### Phase 4: Update Docs
```bash
# MUST run after any structural change
codegraph sync

# Verify index is current
codegraph stats
```

### CodeGraph Query Patterns

**Find all callers of a function:**
```bash
codegraph context "what calls detect_technique"
```

**Find all files that import a module:**
```bash
codegraph search "from science_cli.core.config"
codegraph search "import science_cli.plot"
```

**Understand a feature end-to-end:**
```bash
codegraph context "how does the plot command work from CLI to output"
codegraph context "how does technique detection work end to end"
codegraph context "how does the config system load and merge configs"
```

**Find where to add new code:**
```bash
codegraph search "COMMAND_TREE"              # Command registration
codegraph search "BUILTIN_THEMES"            # Theme registration
codegraph search "ExtensionRegistry"         # Extension registration
```

### CodeGraph Limitations

- **YAML files are NOT indexed** — themes, templates, configs require file reads
- **New files need `codegraph sync`** — run after creating new modules
- **Generated files excluded** — `theme-previews/`, `__pycache__/` not indexed
- **External packages not indexed** — only `src/science_cli/` is indexed

### CodeGraph Config

Located at `.codegraph/config.json`. Key settings:
- `include`: File patterns to index (`.py` included)
- `exclude`: Patterns to skip (`theme-previews/**`, `__pycache__/**`, etc.)
- `extractDocstrings: true` — docstrings are indexed for search
- `trackCallSites: true` — call relationships are tracked

**To add exclusions:** Edit `.codegraph/config.json` → `exclude` array → run `codegraph sync`

---

## CodeGraph Usage Quick Reference

```bash
codegraph sync                        # Update index after structural changes
codegraph search "detect_technique"   # Find symbols by name
codegraph context "how does plot work" # Build context for a task
codegraph stats                       # Index health and statistics
```

The `.codegraph/config.json` exclude list keeps generated/binary files out of the index.
**Always use CodeGraph before reading files** — it returns source code sections directly.
