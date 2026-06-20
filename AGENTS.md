# science-cli Agent Reference

This file documents the AI agent ecosystem for developing `science-cli` v3.20.0 — a Python CLI for managing, plotting, and analyzing experimental data (IV curves, CV, CA, EIS, memristor switching, Raman spectroscopy, AFM, UV-Vis, PVD).

Development agents live in `~/.config/opencode/agents/` and skills in `~/.config/opencode/skills/`.

---

## Agent Inventory

All agents are defined globally at `~/.config/opencode/agents/` — no prefix needed.

| Role | Model | Purpose |
|------|-------|---------|
| **plan** | `commandcode/deepseek/deepseek-v4-pro` | Architecture planning, dependency design |
| **code** | `commandcode/deepseek/deepseek-v4-pro` | Implementation, refactoring, fixes |
| **review** | `commandcode/deepseek/deepseek-v4-pro` | QA, code review, style checks |
| **docs** | `commandcode/deepseek/deepseek-v4-pro` | Documentation, config, changelog |


## Pipeline

```
plan → code → review → docs
 (design)   (implement)   (validate)   (document)
```

---

## Guardrails & Rules

### File Selection
- **Always use `fzf`** for interactive file selection when working with data files. Never hardcode filenames in scripts, tests, or documentation examples. The tool's `--fzf` flag is available for `add`, `delete`, `results`, `analyze`, and `plot` commands.

### Data Verification
- **Always verify data loading** against actual test files before committing. Run `sci info --json` in a test project directory to confirm file discovery, and spot-check a `sci plot` output against a known-good measurement file.

### Testing
- **Always run `pytest tests/ -q` before committing.** This is non-negotiable. Check that the test count matches expectations (do not add failing tests without flagging them).

### Data Integrity
- **Never edit raw data files.** Raw measurement files in `data/raw/` are immutable. All mutation (metadata, analysis results) goes into YAML, SQLite, or Parquet stores.

### Branch Discipline
- **Don't commit to `main` without review approval.** Use feature branches or the `dev` branch for active development. Only merge to `main` after a review agent has signed off.

### Config Changes
- **Config changes must update both code AND config YAML files.** The 4-tier config system (hardcoded → global → project → protocol) means a code change to config resolution logic must be reflected in the corresponding YAML files. Update `documentation/reference/config-system.md` and `documentation/schemas/config-yaml.md` when the config structure changes.

### Never Add Without Approval
- **Never add anything new (files, features, dependencies, commands, directories, or structural changes) without first asking the user for explicit approval.**

---

## Self-Update Protocol

When agents, skills, or config definitions for science-cli need updating:

1. The **docs** agent detects the need (e.g., a new technique requires a new analysis skill)
2. The docs agent calls **`config-opencode`** via `session({ mode: "message", agent: "config-opencode", text: "..." })` to create/update agent definitions and skills
3. config-opencode handles the infrastructure changes
4. The docs agent updates this AGENTS.md to reflect the new agent/skill inventory
5. The docs agent updates `tools/AGENTS.md` if the change affects tooling cross-references

---

## Skills Inventory

Science-cli-specific skills loaded from `~/.config/opencode/skills/`:

| Skill | Location | When to Load |
|-------|----------|-------------|
| **doc-maintenance** | `~/.config/opencode/skills/doc-maintenance/SKILL.md` | Before any code change that requires doc updates. Maps code changes to specific docs: INDEX.md, command refs, technique guides, YAML schemas, theme refs, workflows, tutorials, API docs. |
| **update-readme** | `~/.config/opencode/skills/update-readme/SKILL.md` | After new features or behavior changes. Diff-aware README/CHANGELOG updates. |
| **review-documents** | `~/.config/opencode/skills/review-documents/SKILL.md` | Before creating implementation plans. Read README, CHANGELOG, .lavish/ dashboards, artifacts. |
| **artifact-init** | `~/.config/opencode/skills/artifact-init/SKILL.md` | Starting new implementation artifacts. Creates DDMMYY-named plans with agent delegation. |
| **artifact-review** | `~/.config/opencode/skills/artifact-review/SKILL.md` | After implementation. Reviews artifacts, updates status, records changes. |
| **verify** | `~/.config/opencode/skills/verify/SKILL.md` | After code changes. Build + smoke test to confirm changes work. |
| **code-review** | `~/.config/opencode/skills/code-review/SKILL.md` | After review starts. Systematic code review at different effort levels. |
| **tool-docs** | `~/.config/opencode/skills/tool-docs/SKILL.md` | Cross-tool documentation guidance. Load for any documentation work across tools workspace. Auto-loads doc-maintenance for science-cli context. |
| **clean-code** | `~/.config/opencode/skills/clean-code/SKILL.md` | Function decomposition, naming, type hints. |
| **code-splitting** | `~/.config/opencode/skills/code-splitting/SKILL.md` | When source files exceed 250 lines. |
| **tdd-quality-gate** | `~/.config/opencode/skills/tdd-quality-gate/SKILL.md` | Strict TDD red-green-refactor loop. |
| **review-report** | `~/.config/opencode/skills/review-report/SKILL.md` | Generate structured review reports with traffic lights. |
| **workspace-nested-git-guard** | `~/.config/opencode/skills/workspace-nested-git-guard/SKILL.md` | Governs nested git repos (science-cli moved out of tools/ to `~/.config/science-cli/`). |
| **git-commit** | `~/.config/opencode/skills/git-commit/SKILL.md` | Commit conventions, changelog sync. |
| **sci-config-guide** | `~/.config/opencode/skills/sci-config-guide/SKILL.md` | Modular config architecture: 5-file split, 6-layer resolution, device-study-instrument relationships, grammar patterns, how to add/edit studies/instruments. Load for any config change, config architecture question, or adding new studies/instruments/techniques. |
| **sci-fzf-guide** | `~/.config/opencode/skills/sci-fzf-guide/SKILL.md` | FZF display system: `build_fzf_display()`, `STUDY_COLUMN_REGISTRY` for per-study columns, status badges, metadata flow from protocol.yaml. Load when working on fzf display, per-study columns, status badges, or results/plot/analyze/pulse commands that use fzf. |
| **skill-maintenance** | `~/.config/opencode/skills/skill-maintenance/SKILL.md` | Meta-skill: propagate structural changes across the skill ecosystem. Load after any config architecture change, workflow change, API change, or file structure change to identify and update all affected skills and AGENTS.md files. |
| **sci-keysight-endurance** | `~/.config/opencode/skills/sci-keysight-endurance/SKILL.md` | Parse Keysight WGFMU/B1500A endurance CSV files (v1+v2 formats), extract per-cycle LRS/HRS from Measurement Result sections, detect V_set/V_read voltages, and compute R_LRS/R_HRS/ratio. |
| **sci-plan-workflow** | `~/.config/opencode/skills/sci-plan-workflow/SKILL.md` | **Auto-loaded by plan agents.** On-ramp for all science-cli planning: task→skill routing table, session start protocol, delegation pipeline, domain skill reference. Load this FIRST before any feature planning in the science-cli workspace. |
| **sci-plot-config** | `~/.config/opencode/skills/sci-plot-config/SKILL.md` | Config-based plot system: `config-studies.yaml` defines WHAT to plot and HOW, plot command reads config via `resolve_plot_config()` and EXECUTES. Covers config schema (figure, axes, series, annotations, column mapping), 3-layer merge (theme < study < device), CLI flag overrides, plotter registry dispatch, output filename convention, and how to add plot config for new studies. Load when working on plot styling, column mapping, device overrides, adding plot config for studies, or any plot config architecture work. |
| **lavish-artifact** | `~/.config/opencode/skills/lavish-artifact/SKILL.md` | **Auto-loaded by plan + docs agents.** Artifact registry system using Lavish HTML dashboards: layered registries with versioning, status tags (★/✓/✗), cross-layer deps, Lavish review cycles, per-layer plan dispatch, and self-evolution protocol. Load for artifact dashboard creation, per-layer planning, or after structural changes. |

General-purpose skills also available: `browser`, `memory`, `git`, `free-tools-management`. **Note:** `tools-tasks` (task.md) is deprecated — use `.lavish/` artifact dashboards instead (`lavish-artifact` skill).

---

## Path References

| Resource | Path |
|----------|------|
| Source repo | `~/.config/science-cli/` |
| Documentation | `~/.config/science-cli/documentation/INDEX.md` |
| Agent skill docs | `~/.config/science-cli/docs/skills/` |
| Tests | `~/.config/science-cli/tests/` |
| Global config | `~/.config/science-cli/config/` |
| tools workspace | `~/workspace/tools/` |
| tools AGENTS.md | `~/workspace/tools/AGENTS.md` |
| Task board | `.lavish/` artifact dashboards | Single source of truth for work tracking |
| Plan artifacts | `.lavish/artifacts/` | DDMMYY plan artifacts with YAML frontmatter tags |
| Artifact dashboards | `<project>/.lavish/` | Single source of truth for tracking work, versions, tags, assignees |
| Plan artifacts | `<project>/.lavish/artifacts/` | DDMMYY plan artifacts with YAML frontmatter (layer, type, status, tags, depends_on, assignee) |

---

## Pulse Command Group

`pulse` is a subcommand group for managing pulse-based measurements (STP, endurance, PPF).

| Subcommand | Purpose |
|------------|---------|
| `sci pulse list [--study-filter <study>]` | List pulse steps from `protocol.yaml` with metadata columns (v_set_v, v_read_v, set_width_us, read_width_us, repeat_pattern) |
| `sci pulse overlay [--group-by <key>] [--tolerance <val>] [--output <path>]` | Case-study overlay plot; groups steps by metadata variable |

### Source of truth
- `protocol.yaml` is the SOLE source of truth for pulse steps
- NO `.cases/` directory; NO separate case-study YAML files
- Metadata is auto-written to `protocol.yaml` after each analysis run (Seq 4)
- `pulse list` reads from `protocol.yaml`; `pulse overlay` plots directly from raw data files referenced in steps

### Device-type dispatch
- `pulse:pulse-stp-decay` → single plot (V_read decay)
- `pulse:pulse-endurance` → `volatile` variant (R_decay) or `non-volatile` variant (R_high + R_low) based on step's device_type
- `pulse:pulse-ppf` → single plot (PPF ratio vs interval)

## Status Tags

Tags for managing results files (`sci results --status <tag>`).

| Tag | Badge | Meaning |
|-----|-------|---------|
| `keep` | ✓ | Important, keep for further analysis |
| `highlight` | ★ | Featured in dashboards |
| `discard` | ✗ | Mark for removal |
| `star` | ⭐ | Legacy: same as highlight |
| `clear` | — | Remove any tag |

Storage: `<project>/results/.status.json` (auto-migrates from `.stars.json`).
Serve sync: dashboard polls `/api/status` every 2s; click badge to cycle through tags.

## Per-Study fzf Columns

Every fzf-based file picker (`sci results`, `sci plot`, `sci analyze`, `sci pulse list`) now shows **study-specific metadata columns** instead of one-size-fits-all rows.

- **Source of truth**: `src/science_cli/core/fzf/columns.py` — `STUDY_COLUMN_REGISTRY` dict maps `(study, device_type)` tuples → list of metadata keys
- **Status badge**: `★` (highlight/star), `✓` (keep), `✗` (discard), `` (none/clear) — prepended to every row
- **Column resolution**: `get_step_columns(project_root, step_name, study_name)` reads `step.metadata` from `protocol.yaml` and returns only the registry's keys in registry order
- **Compact display**: registered columns use `width_meta=12` (vs. default 20) to keep pulse waveforms narrow
- **Fallback**: unregistered studies show all metadata keys in dict insertion order
- **Backwards compat**: `build_fzf_display()` without `study_name` behaves identically to pre-v3.19 behavior
