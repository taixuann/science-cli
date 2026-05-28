# AGENTS.md — science-cli Developer & Agent Index

Welcome! This file acts as the primary router and entry point for AI Coding Assistants (such as Antigravity and OpenCode) and human developers working in the `science-cli` repository.

To keep the workspace clean and modular, developer and agent instructions are split into three local, gitignored files at the root level:

1. **[RULES.md](file:///Users/tai/workspace/tools/science-cli/RULES.md)** — **Strict Developer Rules & Workflow Instructions**
   - Critical guardrails: Never delete user code, always commit changes immediately.
   - Step-by-step 6-phase developer session workflow (Orient → Plan → Implement → Test → Docs → Commit).
   - Core behavior guidelines and code architecture constraints.

2. **[SCHEMA.md](file:///Users/tai/workspace/tools/science-cli/SCHEMA.md)** — **Codebase Architecture & Developer Guides**
   - Current comprehensive codebase Directory Map.
   - Exact instructions on "Where to Add New Features" (CLI commands, plotting, themes, configurations, devices).
   - 4-Tier Config System Architecture details and typed config accessors.
   - Comprehensive CodeGraph Integration Guide and workflow query patterns.

3. **[README.md](file:///Users/tai/workspace/tools/science-cli/README.md)** — **User-Facing Documentation**
   - Reference for end-user installation, usage, commands, techniques, and options.

---

## 🚀 AI Agent Quick Start

Before doing *any* work in this codebase, you **must** follow these three steps:

1. **Check the Gaps & Pending Plans** at the bottom of this file to see what needs execution.
2. **Review the Rules in [RULES.md](file:///Users/tai/workspace/tools/science-cli/RULES.md)** very carefully. If you violate the *never delete code* or *always commit and update* rules, you have failed!
3. **Orient yourself using [SCHEMA.md](file:///Users/tai/workspace/tools/science-cli/SCHEMA.md)** and make full use of **CodeGraph** (`.codegraph/`) to locate modules, functions, and trace dependencies before writing a single line of code.

---

## 📋 The Workspace Plan Template

When the user asks for a change, **always create a Plan artifact first**.
- Workspace plans **must** be created under `documentation/artifacts/` as markdown files named **`DDMMYY_<short_topic>.md`** (e.g. `280526_repo_restructure.md`).
- Date format is DDMMYY (e.g., 28 May 2026 is `280526`).
- Always present the plan to the user for approval first. Do not make code edits or run modifying commands until the plan is approved.

### PLAN Template:
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

## ⚠️ Gaps and Missing Things

**Known gaps in the codebase and workflow. This section is updated after every session.**
**Do NOT execute gaps automatically — each gap needs a PLAN and user approval.**

### Completed (No Longer Gaps)

| Item | Completed In | Notes |
|------|-------------|-------|
| CodeGraph integration | cleanup/architecture-guardrails | `.codegraph/` initialized, SCHEMA.md has full integration guide |
| 3-tier config system | cleanup/architecture-guardrails | `core/config.py` — hardcoded ← global ← project |
| Device-aware data loading | cleanup/architecture-guardrails | `core/data_loader.py` accepts `device=` and `technique=` params |
| Dead code cleanup | cleanup/architecture-guardrails | Removed image.py, general.py, functions/ directory |
| Module READMEs | cleanup/architecture-guardrails | core/README.md, plot/README.md, theme/README.md |
| AGENTS.md workflow | cleanup/architecture-guardrails | 5-phase workflow, cross-PLAN tracking, CodeGraph integration |
| Sprint 2: Help menu restructure | Sprint 2 | 4-group commands, TechniquesBox TUI banner, --filter removed |
| Sprint 3: Cross-Protocol Dashboard | Sprint 3 | `dashboard --all`, stacked heatmaps, material filter, analysis_data.json cache |
| documentation/ structure | cleanup/architecture-guardrails | artifacts/ and library/ directories created |
| Architecture guardrail tests | cleanup/architecture-guardrails | test_guardrails.py — 16 tests passing |
| PLAN files created | cleanup/architecture-guardrails | 4 PLANs created with cross-PLAN relationships |
| Sprint 8: Global Config Registry | Sprint 8 | 4-tier config, global device/technique registry, sync/analyze split, SQLite v2 auto-construction |
| Config merge fix — `get_global_device_config()` / `get_device_config()` | 2026-05-16 | Properly overlay user config.yaml over hardcoded defaults instead of returning early |
| `-d`/`--device` flag for protocol steps | 2026-05-16 | First-class `device` property for each step; mirrors `-t`/`--technique` pattern |
| `memristor init --matrix` shorthand | 2026-05-16 | `--matrix r6-c6` as shorthand for `--rows 6 --cols 6`; `--label` auto-generates |
| fzf TUI subprocess dispatch | 2026-05-16 | `tui/app.py` uses subprocess.run with stop/start application mode; `fzf_utils.py` uses `/dev/tty` stderr |
| Consolidate devices.yaml into protocol YAML | version-2.1.1 | `core/protocol.py` created; SQLite schema v4; `read_devices()` reads protocol YAML first; `write_devices()` deprecated; `memristor init` writes to protocol YAML; sweep metadata sync pipeline |
| Repo restructuring (science-cli/* → repo root) | version-2.1.1 | `git mv science-cli/* .` — repo root IS science-cli; extensions/ removed; .gitignore simplified to standard blocklist |
| Clean up / Remove old scripts/ | 280526_repo_restructure | Completely removed `/scripts/` directory |
| Archive MIGRATION.md to documentation | 280526_repo_restructure | Moved and renamed `MIGRATION.md` to `documentation/README-1.0.0.md` |

### Active Gaps (Need Execution)

#### Command & Session Gaps
*All gaps closed* — 3-level state memory (project → protocol → step) fully implemented in `session.py`. Close/status/step tracking all work.

#### Config Gaps
*All gaps closed* (Sprint 8):
- **4-tier config**: Hardcoded defaults → Global config → Per-project config → Per-protocol
- **Global device registry**: Built-in keithley-2400 and keysight-b1500, extensible via `config edit devices`
- **Global technique registry**: Built-in iv-sweep, iv-breakdown, iv-leakage with grammar_codes
- **Universal grammar fields**: 5 standardized fields (date_code, material, technique, matrix, suffix), hardcoded `_` separator
- **Grammar-based filename parsing**: 4-tier resolution in `parse_filename_grammar()`
- **SQLite auto-construction**: `populate_from_grammar()` scans step dirs, parses filenames, populates SQLite without YAML
- **sync/analyze split**: `memristor sync` = pure filename parsing; `memristor analyze` = CSV-based computation
- **Dashboard SQLite fast path**: `generate_dashboard()` tries SQLite first, falls back to CSV reading

#### Extension Gaps
*All gaps closed* — extensions integrated as built-in modules in `refactor/2.1.0`.

#### Project Health Gaps
*All gaps now closed* (2026-05-14):
- **Test suite**: `tests/` directory with pytest structure, fixtures (`conftest.py`), core/memristor/session/CLI tests
- **CI/CD**: `.github/workflows/ci.yml` — GitHub Actions: lint → type-check → test (Python 3.9-3.11)
- **CHANGELOG**: Exists at `CHANGELOG.md` following Keep a Changelog format
- **LICENSE**: MIT License at `LICENSE`
- **Lock file**: `requirements.txt` generated from `pyproject.toml`
- **Type checking**: `[tool.mypy]` section in `pyproject.toml`
- **Linting**: `ruff.toml` with E/F/I/N/W/UP rules
- **CONTRIBUTING guide**: `CONTRIBUTING.md`
- **TUI README**: `src/science_cli/tui/README.md`
- **Migration guide**: Moved to `documentation/README-1.0.0.md` (1.x → 2.0.0)

#### AI Agent Integration Gaps
*All gaps closed* (2026-05-28):
- **`sci info --json`**: Full project manifest as machine-readable JSON — protocols, steps, files, themes, techniques, plot hints
- **`--json` on `sci ls` and `sci status`**: Machine-readable output for AI agents
- **`sci chat`**: Natural language to `sci plot` command router via LLM (configurable via `SCI_LLM_API_KEY` env var)
- **`plotting-guy` OpenCode agent**: New subagent in `~/.opencode/agents/plotting-guy.md` that drives science-cli for visualization tasks
- **`AGENTS_SCHEMA.md`**: Reference document at `documentation/AGENTS_SCHEMA.md` — schema and workflow for AI agents
- **Intent-router updated**: Routes plot/viz/data-discovery requests to plotting-guy
- **Template refactoring**: All 8 technique templates refactored with publication-quality presets (Helvetica, 600 DPI, standard figsize, per-technique colors, presets for IUPAC conventions, switching markers, conduction mechanisms, etc.)

#### Remaining Future Considerations (No PLANs Yet)

| Item | Type | Notes |
|------|------|-------|
| Per-device `data/plot/analyze` device shortcuts | Feature | `sci data -d keithley-2400` |
| Plugin system for 3rd-party device configs | Feature | Auto-discover from pip-installed packages |
| Cycle evolution analysis in dashboard | Feature | Placeholder panel exists, needs endurance data integration |
| Confidence scoring for parameter extraction | Feature | Placeholder panel exists, needs algorithm |

### Pending PLANs

- **Active Workspace Plans (`documentation/artifacts/`)**:
  - `280526_artifacts_and_reference_guides.md`: Coordinating plans restructuring and archiving (In-Progress).
  - [280526_ai_integration.md](file:///Users/tai/workspace/tools/science-cli/documentation/artifacts/280526_ai_integration.md): AI Agent Integration & Local Intent Routing (Draft/Approved).
  - [280526_dashboard.md](file:///Users/tai/workspace/tools/science-cli/documentation/artifacts/280526_dashboard.md): Project-Aware Dashboard Backend & Plot Engine (Draft/Approved).
  - [280526_refactor.md](file:///Users/tai/workspace/tools/science-cli/documentation/artifacts/280526_refactor.md): Code Reorganization & Technique-Library Consolidation (Draft/Approved).
  - `280526_repo_restructure.md`: Outlining root restructuring (Completed).
  - `280526_documentation_reorg.md`: Outlining documentation folder cleanup (Completed).

- **Historical Plans & Reports**:
  - All legacy non-date-prefixed plans (`PLAN-*.md` and `test-report-*.md`) have been safely archived under `documentation/artifacts/archive/` to keep the active planning workspace clean and focused.
