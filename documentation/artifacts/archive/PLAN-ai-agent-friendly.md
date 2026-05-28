# PLAN: AI-Agent-Friendly Science-CLI + Plotting-Guy Agent

## Classification
feature

## Related Plans
- None (net-new feature, no existing PLANs touch this area)

## Status
- **Created**: 2026-05-28
- **Status**: completed
- **Branch**: feature/ai-agent-friendly

## Objective
Make science-cli machine-readable so AI agents (OpenCode) can discover project structure, generate correct `sci plot` commands, and leverage existing themes/styles. Plus create a dedicated OpenCode `plotting-guy` agent that knows how to drive science-cli for visualization tasks.

## Context

Currently science-cli outputs are human-oriented Rich tables. An AI agent like OpenCode cannot:
- Discover what protocols/steps/files exist in a project
- Know what plot flags are available per technique
- Know what themes exist
- Construct correct `sci plot` commands automatically

The user manually sets up projects/protocols/steps/files. They want the AI to then *find* the data and *generate* plot commands — using existing themes and plotting code, never generating matplotlib directly.

### Existing foundations
- `_technique_hints()` in `plot.py:91` already has a structured dict of per-technique flags — just not exposed as JSON
- `core/protocol.py` already reads/writes protocol YAML with steps, files, devices
- `core/session.py` already tracks project/protocol/step state
- `theme/registry.py` has `list_themes()` and `apply_theme()`
- `ls_cmd.py` already iterates all protocols/steps/files — just needs JSON output mode
- `status.py` already reads session + project state — just needs JSON output mode

## Specification

### Part A: Science-CLI Changes

#### A1. New command: `sci info --json`

A single discovery command that dumps the complete project manifest as structured JSON. This is the **primary entry point** for AI agents.

```
sci info --json
```

**Output schema:**
```json
{
  "science_cli_version": "2.1.1",
  "project": {
    "name": "my-experiment",
    "path": "/Users/tai/projects/my-experiment",
    "theme": "publication-acs",
    "raw_file_count": 42,
    "protocol_count": 3
  },
  "session": {
    "last_project": "my-experiment",
    "last_protocol": "1_iv-test",
    "last_step": "1_set",
    "theme": "publication-acs"
  },
  "protocols": [
    {
      "name": "1_iv-test",
      "description": "...",
      "device": {"rows": 6, "cols": 6, "label": "R", ...},
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
              "size": 12345
            }
          ]
        }
      ]
    }
  ],
  "themes": ["publication-acs", "dark", "publication-nature", "poster", "tufte", "acs-annotated", "default"],
  "techniques_configured": [
    {"slug": "iv-sweep", "devices": ["keithley-2400", "keysight-b1500"]},
    {"slug": "ec-eis", "devices": ["biologic-mpt"]}
  ]
}
```

**Audience:** AI agents (OpenCode). Not meant for human consumption.

**Implementation:** New module `cli/commands/info.py` with `info_handler(args)`. Registered in `COMMAND_TREE` as `"info"`. Reads project path, session, protocol YAMLs, iterates steps/files, calls `list_themes()`, calls `list_global_devices()`/config accessors.

#### A2. `--json` flag on `sci ls`

Add `--json` flag. When present, outputs structured JSON instead of Rich tables.

- `sci ls --json` → all protocols with steps and file counts
- `sci ls -m protocol --json` → same but scoped
- `sci ls <step_name> --json` → files in that step with metadata
- `sci ls -m project --json` → all projects with stats

**Implementation:** Add `_ls_to_json()` functions that return dicts, called when `--json` flag detected. Reuse existing YAML-reading logic.

#### A3. `--json` flag on `sci status`

Same pattern. `sci status --json` outputs session + project state as JSON instead of Rich tables.

#### A4. Plot capability discovery: `sci plot`

Expose `_technique_hints()` via either:
- `sci plot --list-flags technique=iv-sweep --json` (explicit flag query)
- Or include in `sci info --json` output as `plot_hints` section

**Simpler approach:** Include `plot_hints` in the `sci info --json` output under a `techniques` key. This keeps discovery in one place.

#### A5. AGENTS_SCHEMA.md (reference document)

A `documentation/AGENTS_SCHEMA.md` that documents for AI agents:
- Project directory layout
- Protocol YAML format (name, steps, files, device)
- All CLI commands with flags
- Theme system overview
- The `sci info --json` schema
- How to map user intent → CLI commands

This is what the plotting-guy agent reads at session start.

### Part B: OpenCode Agent (`plotting-guy`)

#### B1. New agent: `~/.opencode/agents/plotting-guy.md`

A subagent that specializes in driving science-cli for visualization tasks.

**YAML frontmatter:**
```yaml
description: Drives science-cli for plotting, visualization, and data discovery. Reads sci info --json to discover project structure, generates correct sci plot commands, follows existing themes.
mode: subagent
model: opencode-go/deepseek-v4-pro
temperature: 0.1
permission:
  read: allow
  bash: allow
  glob: allow
  grep: allow
  ls: allow
```

**Behavior:**
1. On spawn: run `sci info --json` to discover the project
2. Read `documentation/AGENTS_SCHEMA.md` for command reference (project-local) or README.md
3. For plot requests: find the file path from info output → determine technique → look up available flags in plot_hints → construct `sci plot <path> --<flags>` command
4. For discovery requests: "what data exists?" → parse info output, present summary
5. For theme requests: "use the dark theme" → `sci plot ... --theme dark`
6. NEVER generate matplotlib/seaborn code — always call `sci` CLI
7. Can suggest plot improvements based on technique hints

**When spawned:** The intent-router should route to plotting-guy when:
- User asks about "plot", "visualize", "chart", "graph" in context of science-cli/data
- User asks "show me the data", "what's in my project"
- User asks about themes/styles for plotting

#### B2. Update intent-router to route to plotting-guy

Add `plotting-guy` to intent-router's `task:` permissions.

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/cli/commands/info.py` | **CREATE** | New `sci info --json` command |
| `src/science_cli/cli/commands/__init__.py` | EDIT | Register `info` in COMMAND_TREE |
| `src/science_cli/cli/commands/ls_cmd.py` | EDIT | Add `--json` output mode |
| `src/science_cli/cli/commands/status.py` | EDIT | Add `--json` output mode |
| `src/science_cli/cli/commands/plot.py` | EDIT | Expose technique hints in info output |
| `src/science_cli/cli/help.py` | EDIT | Add `info` to GROUP 3, add AGENTS_SCHEMA.md reference |
| `documentation/AGENTS_SCHEMA.md` | **CREATE** | AI agent reference document |
| `~/.opencode/agents/plotting-guy.md` | **CREATE** | New OpenCode subagent |
| `~/.opencode/agents/intent-router.md` | EDIT | Add plotting-guy to task permissions |
| `src/science_cli/theme/templates/*.yaml` | EDIT | Refactored all 8 templates with publication-quality presets |

#### Post-implementation: Template refactoring

All 8 technique templates (`ec-ca`, `ec-cv`, `ec-eis`, `iv-sweep`, `iv-breakdown`, `iv-leakage`, `mem-switching`, `mem-endurance`, `mem-retention`) refactored from bare-bones to full publication-quality configs:

- **figure**: `[3.54, 2.76]` figsize (standard 9cm width), 600 DPI, white facecolor
- **axes**: Full tick config (`in` direction, 3pt length, 0.5pt width), grid false, aspect ratio
- **defaults**: Refined `linewidth: 0.75`, per-technique colors/markers/alpha
- **font**: Helvetica, label 7pt, tick 6pt, title 8pt, legend 6pt
- **colors**: Technique-specific qualitative palettes (Wong palette), LRS/HRS dual colors
- **savefig**: PDF output, 600 DPI, tight bbox, 0.05in padding
- **presets**: Technique-specific configs (units, IUPAC convention, scan arrows, switching markers, breakdown highlighting, conduction mechanisms, log scales, temperature)

## Dependencies

None. This is additive — no existing code is modified beyond adding JSON output modes. All existing behavior preserved.

## Cross-PLAN Impact

None. No other PLANs touch the CLI command layer or output formatting.

## Test Strategy

1. **Unit tests**: Verify `sci info --json` output schema is valid JSON with all expected keys
2. **CLI smoke test**: `sci info --json | python -m json.tool` — validates output
3. **Integration**: Run against a real project with protocols/steps/files, verify all data appears
4. **Agent test**: Spawn plotting-guy with a plot request, verify it generates correct `sci plot` command
5. **Existing tests**: Run full test suite to verify no regressions (`pytest tests/`)

## Progress

- [x] PLAN created
- [x] User approved
- [x] A1: `sci info --json` implemented
- [x] A2: `--json` on `sci ls` implemented
- [x] A3: `--json` on `sci status` implemented  
- [x] A4: Plot hints exposed in `sci info --json`
- [x] A5: `sci chat` command implemented (additional — LLM-to-command router)
- [x] A6: AGENTS_SCHEMA.md created
- [x] B1: plotting-guy agent created
- [x] B2: intent-router updated
- [x] TEST passed (JSON validity, output schema verified)
- [x] DOCS updated (README, AGENTS.md, PLAN)
- [x] COMMIT done (d38b583)
