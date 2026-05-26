# AGENTS.md — science-cli Developer Reference

## CRITICAL: NEVER Delete User Code
- **NEVER delete any `.py`, `.js`, `.ts`, or source code files** — even if they appear unused, dead, or duplicated
- **NEVER delete directories** containing user code — even if they appear empty (may have `__pycache__` or hidden files)
- **NEVER remove imports, functions, or classes** without explicit user approval
- If code appears dead: flag it in the PLAN, do NOT delete it
- If user asks to clean up dead code: confirm exactly which files, get explicit approval before any deletion
- **TUI code is sacred** — the `tui/` directory and all Textual/App code must NEVER be touched without explicit instruction
- **Recovery is not guaranteed** — `.pyc` files cannot be fully decompiled. Once source is gone, it's gone forever

## CRITICAL: Always Commit and Update
- **After EVERY code change, commit immediately** — never leave uncommitted changes
- **After EVERY commit, update the relevant PLAN** — mark progress, note what changed
- **After EVERY session, update README.md** — reflect new features, changed behavior
- **After EVERY session, update AGENTS.md** — update directory map, guardrails if structure changed
- **Apply to ALL modes**: plan mode, build mode, default mode — no exceptions
- Commit message must be descriptive and reference the PLAN if one exists
- If no PLAN exists for the change, create one first (Phase 1 of workflow)

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
/ (repo root = science-cli content)
├── AGENTS.md                          ← This file (agent workflow + reference)
├── README.md                          ← User-facing documentation
├── documentation/                     ← Plans and instructions
│   ├── plans/                         ← PLAN.md files (one per topic)
│   └── instructions/                  ← Reusable guides
├── pyproject.toml                     ← Build config, dependencies, entry points
├── bin/sci                            ← Shell entry point
├── scripts/                           ← Dev/utility scripts
├── theme-previews/                    ← Generated theme preview PDFs (gitignored)
├── tests/                             ← 78 pytest tests (core, memristor, session, CLI)
├── .codegraph/                        ← CodeGraph index
├── .gitignore                         ← Standard blocklist (repo isolated, no allowlist needed)
├── src/science_cli/                   ← Canonical source root
│   ├── __init__.py                    ← __version__
│   ├── __main__.py                    ← `python -m science_cli` entry point
│   ├── app.py                         ← CLI entry point (run_cli + REPL)
│   ├── repl.py                        ← prompt_toolkit REPL session
│   ├── config.py                      ← Legacy config (theme, projects_root)
│   ├── cli/                           ← CLI dispatch layer
│   │   ├── commands/                  ← One module per command
│   │   │   ├── __init__.py            ← COMMAND_TREE (all registered commands)
│   │   │   ├── add.py / analyze.py / close.py / config.py
│   │   │   ├── data_cmd.py / delete_cmd.py / edit_cmd.py
│   │   │   ├── eis.py / fit.py / ls_cmd.py / memristor.py
│   │   │   ├── metadata.py / open_cmd.py / parse.py
│   │   │   ├── plot.py / protocol.py / results.py
│   │   │   ├── status.py / techniques.py
│   │   └── help.py                    ← Help text rendering
│   ├── core/                          ← Core library — no CLI coupling
│   │   ├── config.py                  ← 4-tier device-aware config
│   │   ├── data_loader.py / file_utils.py / fzf_utils.py
│   │   ├── manifest.py / paths.py / project.py
│   │   ├── protocol.py / session.py
│   │   ├── sweep_metadata.py / technique.py
│   │   └── parquet_store.py
│   ├── plot/                          ← Plot engine
│   │   ├── __init__.py / base.py / ca.py / cv.py
│   │   ├── eis.py / overlays.py
│   ├── theme/                         ← Theme & template system
│   │   ├── __init__.py / registry.py
│   │   ├── themes/                    ← 7 style themes (*.yaml)
│   │   └── templates/                 ← Per-technique defaults (*.yaml)
│   ├── tui/                           ← Textual TUI
│   ├── memristor/                     ← Memristor characterization
│   │   ├── __init__.py / db.py / device.py / device_cli.py
│   │   ├── dashboard.py / plotting.py / models.py
│   │   ├── switching.py / endurance.py / retention.py
│   ├── electrochem/                   ← CV, CA, EIS analysis
│   └── iv/                            ← IV analysis models
```

---

## Where to Add New Features

### Adding a New CLI Command
1. Create `src/science_cli/cli/commands/<name>_cmd.py`
2. Define a `<name>_handler(args)` function
3. Import it in `src/science_cli/cli/commands/__init__.py`
4. Add it to `COMMAND_TREE` dict in `__init__.py`

### Adding a New CLI Flag to Protocol/Metadata Commands
The `-d`/`--device` flag pattern mirrors `-t`/`--technique` for step metadata:
- In `add.py`/`edit_cmd.py`: parse comma-separated `-d`/`--device`, store as `device` key in each step entry alongside `name` and `technique`
- In `ls_cmd.py`: add a Device column to the Rich table when listing steps
- This creates a **step → technique → device** triplet as first-class properties

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
Devices live under their parent technique (legacy approach):
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

### Adding a Global Device (Sprint 8)
Devices can now be defined globally (shared across all techniques):
1. Add to `_DEFAULT_GLOBAL_DEVICES` in `core/config.py`, or
2. Add to `~/.config/science-cli/config.yaml` under the `devices:` section via `config edit devices`
3. Reference by name in technique configs via `default_device: keithley-2400`
4. Fallback resolution: `_resolve_device_config()` checks global registry if per-technique lookup fails

### Adding a Global Technique (Sprint 8)
1. Add to `_DEFAULT_GLOBAL_TECHNIQUES` in `core/config.py`, or
2. Add to `~/.config/science-cli/config.yaml` under the `techniques:` section via `config edit techniques --global`
3. Include `grammar_codes`, `default_device`, and optional `types` mapping

---

## What NOT to Do (Guardrails)

### Never:
- **Add hardcoded device-specific logic to data_loader.py** — use the config system
- **Add new hardcoded technique patterns directly to technique.py** — add via config or the BUILTIN_TECHNIQUES dict
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

## Config System Architecture (4-Tier)

```
Hardcoded defaults (core/config.py)         ← _DEFAULT_DEVICE, _DEFAULT_TECHNIQUE_PATTERNS
       ↓ overridden by
Global config (~/.config/science-cli/config.yaml)  ← device registry, technique templates, grammar
       ↓ overridden by
Per-project config (<project_root>/sci-config.yaml) ← type→step mapping, project overrides
       ↓ overridden by
Per-protocol metadata (protocol/<name>/...)
```

**Global Device Registry** (Sprint 8):
- `_DEFAULT_GLOBAL_DEVICES` in `core/config.py` — built-in instruments (keithley-2400, keysight-b1500)
- `get_global_device_config(name)` — lookup from hardcoded + global config
- `list_global_devices()` — list all registered devices
- Devices defined independently of techniques (shared across all techniques)

**Global Technique Registry** (Sprint 8):
- `_DEFAULT_GLOBAL_TECHNIQUES` in `core/config.py` — built-in technique definitions
- `get_global_technique_config(name)` — lookup from hardcoded + global config
- `list_global_techniques()` — list all registered techniques
- Includes grammar_codes, default_device, types per technique

**Key modules:**
- `core/config.py` — loading, merging, caching, typed accessors, global registry
- `core/technique.py` — grammar-based filename parsing (4-tier resolution: hardcoded → global → project → protocol)
- `core/data_loader.py` — device-aware loading with global fallback
- `core/project.py` — consults config for projects_root
- `cli/commands/config.py` — `config init`, `config show`, `config edit --global`, `config devices`, `config grammar`
- `memristor/db.py` — schema v4 with universal grammar columns + sweep metadata (`sweep_order`, `sweep_type`, `sweep_segments`, `temperature`), `populate_from_grammar()`, `update_file_analysis()`, `update_file_sweep_metadata()`
- `memristor/dashboard.py` — SQLite fast read path via `_collect_device_data_from_sqlite()`
- `memristor/device_cli.py` — `sync` (pure filename parsing) + `analyze` (CSV computation)

**Typed accessors:**
```python
from science_cli.core.config import (
    get_device_config,              # → dict or None
    get_technique_patterns,         # → list[str]
    get_default_device,             # → str
    get_projects_root,              # → Path
    get_header_marker,              # → str
    get_merged_config,              # → dict (raw)
    get_global_device_config,       # → dict or None (Sprint 8)
    list_global_devices,            # → list[str] (Sprint 8)
    get_global_technique_config,    # → dict or None (Sprint 8)
    list_global_techniques,         # → list[str] (Sprint 8)
    get_file_naming_grammar,        # → dict (Sprint 8, separator hardcoded to "_")
)

from science_cli.core.technique import (
    parse_filename_grammar,         # → dict with 5 universal fields (Sprint 8)
    standardize_grammar_fields,     # → normalize to date_code, material, technique, matrix, suffix
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
| Sprint 2: Help menu restructure | Sprint 2 | 4-group commands, TechniquesBox TUI banner, --filter removed |
| Sprint 3: Cross-Protocol Dashboard | Sprint 3 | `dashboard --all`, stacked heatmaps, material filter, analysis_data.json cache |
| documentation/ structure | cleanup/architecture-guardrails | plans/ and instructions/ directories created |
| Architecture guardrail tests | cleanup/architecture-guardrails | test_guardrails.py — 16 tests passing |
| PLAN files created | cleanup/architecture-guardrails | 4 PLANs created with cross-PLAN relationships |
| Sprint 8: Global Config Registry | Sprint 8 | 4-tier config, global device/technique registry, sync/analyze split, SQLite v2 auto-construction |
| Config merge fix — `get_global_device_config()` / `get_device_config()` | 2026-05-16 | Properly overlay user config.yaml over hardcoded defaults instead of returning early |
| `-d`/`--device` flag for protocol steps | 2026-05-16 | First-class `device` property for each step; mirrors `-t`/`--technique` pattern |
| `memristor init --matrix` shorthand | 2026-05-16 | `--matrix r6-c6` as shorthand for `--rows 6 --cols 6`; `--label` auto-generates |
| fzf TUI subprocess dispatch | 2026-05-16 | `tui/app.py` uses subprocess.run with stop/start application mode; `fzf_utils.py` uses `/dev/tty` stderr |
| Consolidate devices.yaml into protocol YAML | version-2.1.1 | `core/protocol.py` created; SQLite schema v4; `read_devices()` reads protocol YAML first; `write_devices()` deprecated; `memristor init` writes to protocol YAML; sweep metadata sync pipeline |
| Repo restructuring (science-cli/* → repo root) | version-2.1.1 | `git mv science-cli/* .` — repo root IS science-cli; extensions/ removed; .gitignore simplified to standard blocklist |
| Log-log IV plot toggle | refactor/2.1.0 | `dashboard.py` — `IV` | `ln-ln` mode toggle in Device Explorer; `ivScaleMode` tracking; `setIVScale()` JS |
| Dashboard redesign: material groups, single-cycle viewer, Vset/Vreset markers | refactor/2.1.0 | Per-material JS data chunks, `i_set`/`i_reset` columns in SQLite, single-cycle IV viewer with `<` `>` navigation, distribution collapse toggles |
| Dashboard themes (Dark, Full Black, Full White) + fzf column standardization | feature/dashboard-themes-fzf-columns | 3 dashboard themes, `build_fzf_display()` helper, standardized `protocol  step  filename` fzf columns across all pickers |

### Active Gaps (Need Execution)

#### Command & Session Gaps

✅ **All gaps closed** — 3-level state memory (project → protocol → step) fully implemented in `session.py`. Close/status/step tracking all work.

#### Config Gaps

✅ **All gaps closed** (Sprint 8):
- **4-tier config**: Hardcoded defaults → Global config → Per-project config → Per-protocol
- **Global device registry**: Built-in keithley-2400 and keysight-b1500, extensible via `config edit devices`
- **Global technique registry**: Built-in iv-sweep, iv-breakdown, iv-leakage with grammar_codes
- **Universal grammar fields**: 5 standardized fields (date_code, material, technique, matrix, suffix), hardcoded `_` separator
- **Grammar-based filename parsing**: 4-tier resolution in `parse_filename_grammar()`
- **SQLite auto-construction**: `populate_from_grammar()` scans step dirs, parses filenames, populates SQLite without YAML
- **sync/analyze split**: `memristor sync` = pure filename parsing; `memristor analyze` = CSV-based computation
- **Dashboard SQLite fast path**: `generate_dashboard()` tries SQLite first, falls back to CSV reading

#### Extension Gaps

✅ **All gaps closed** — extensions integrated as built-in modules in `refactor/2.1.0`.

#### Project Health Gaps

✅ **All gaps now closed** (2026-05-14):
- **Test suite**: `tests/` directory with pytest structure, fixtures (`conftest.py`), core/memristor/session/CLI tests
- **CI/CD**: `.github/workflows/ci.yml` — GitHub Actions: lint → type-check → test (Python 3.9-3.11)
- **CHANGELOG**: Exists at `CHANGELOG.md` following Keep a Changelog format
- **LICENSE**: MIT License at `LICENSE`
- **Lock file**: `requirements.txt` generated from `pyproject.toml`
- **Type checking**: `[tool.mypy]` section in `pyproject.toml`
- **Linting**: `ruff.toml` with E/F/I/N/W/UP rules
- **CONTRIBUTING guide**: `CONTRIBUTING.md`
- **TUI README**: `src/science_cli/tui/README.md`
- **Migration guide**: `MIGRATION.md` (1.x → 2.0.0)

#### Remaining Future Considerations (No PLANs Yet)

| Item | Type | Notes |
|------|------|-------|
| Per-device `data/plot/analyze` device shortcuts | Feature | `sci data -d keithley-2400` |
| Plugin system for 3rd-party device configs | Feature | Auto-discover from pip-installed packages |
| Cycle evolution analysis in dashboard | Feature | Placeholder panel exists, needs endurance data integration |
| Confidence scoring for parameter extraction | Feature | Placeholder panel exists, needs algorithm |

### Pending PLANs

All original PLANs (1-4) are now completed or superseded. All Sprint plans (1-8) in PLAN-enhanced-dashboard are completed. PLAN-tui-fzf-pty and PLAN-device-step-metadata are also completed. PLAN-consolidate-devices-yaml is completed on `version-2.1.1`. The `refactor/2.1.0` branch contains all original implementations.

**When creating a new PLAN, check if it relates to any future considerations above.**

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
