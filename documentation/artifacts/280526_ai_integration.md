# PLAN: AI Agent Integration & Local Intent Routing

## Classification
feature | docs | extension

## Related Plans
- [[280526_artifacts_and_reference_guides]] — related — parent plan coordinating workspace re-organization.
- [[280526_dashboard]] — related — AI agents use the backend plotting and overlay systems defined in the dashboard plan.

## Status
- **Created**: 2026-05-28
- **Status**: draft
- **Branch**: dev

## Objective
Establish a robust, self-contained AI-agent integration suite inside `science-cli` by moving the `plotting-guy` agent definition locally into the project root, documenting the exact `--json` schema discovery endpoints, and specifying the two primary workflows for AI-assisted chat and command execution.

## Context
AI agents (like Antigravity and OpenCode) are first-class developers and users of `science-cli`. Currently, the `plotting-guy` agent profile resides in the global user directory (`~/.opencode/`), making the repository dependent on external state. Moving this file locally to `/Users/tai/workspace/tools/science-cli/.opencode/agents/plotting-guy.md` ensures the AI workflows are fully self-contained. Furthermore, we need to explicitly outline the two workflows where the user can leverage the AI to run commands and plot files without having to write raw matplotlib scripts or complex CLI flags.

## Specification

### 1. Relocate the `plotting-guy` Subagent
- Create the local directory `.opencode/agents/` at the repository root.
- Create `/Users/tai/workspace/tools/science-cli/.opencode/agents/plotting-guy.md` to define the system prompts, capabilities, and tool layouts for the plotting subagent.
- The agent is equipped to read `.codegraph/` and run `sci info --json` to automatically discover protocols and steps.

### 2. Dual-Workflow AI Integration (The 2 Options)

#### Option 1: Direct Agent Execution (Workspace Sparring Mode)
- **Concept**: You chat with Antigravity or OpenCode directly in the IDE chat box.
- **Workflow**:
  1. You type a natural language instruction (e.g. "overlay R1C1 data from steps 1_set and 2_reset with ACS publication theme").
  2. The agent automatically executes `sci info --json` under the hood to locate the file paths.
  3. The agent constructs the correct CLI command: `sci plot --overlay protocol/1_iv-test/1_set/IV_data_R1C1.csv,protocol/1_iv-test/2_reset/IV_data_R1C1.csv --theme publication-acs --label-name "Set","Reset"`.
  4. The agent executes it directly in the terminal, presenting the resulting publication-ready plot PDF to you.

#### Option 2: CLI Helper Integration (The `sci chat` Router)
- **Concept**: You work directly in the terminal, calling the CLI but letting the LLM configure the complex parameters.
- **Workflow**:
  1. You run: `sci chat "overlay the IV sweep files for R2C3 in steps 1 and 2"`.
  2. The `sci chat` command sends the natural language query, the project structure (`sci info --json`), and the active session state to the LLM (using the key in `SCI_LLM_API_KEY`).
  3. The LLM translates the query to the exact backend command and either prints it out for confirmation or executes it directly on the active project.
  4. This allows you to organize your files manually in correct protocols and steps while letting the AI do the heavy lifting of configuring plots and extracting parameter fittings.

### 3. Machine-Readable Schema Specifications
- **`sci info --json`**: Emits a complete project manifest containing protocol names, steps, files, themes, techniques, and plot hints.
- **`sci ls --json`**: Emits hierarchical protocol step listings.
- **`sci status --json`**: Emits active session coordinates (project path, current protocol, current step, current theme).
- Standardize all CLI outputs under `--json` flags to return schema-valid JSON for direct machine consumption (e.g. avoiding text headers/footers when the JSON flag is present).

## Files to Modify
| File | Action | Reason |
|------|--------|--------|
| `.opencode/agents/plotting-guy.md` | [NEW] | Localized, self-contained definition of the visualization subagent |
| `src/science_cli/cli/commands/chat_cmd.py` | Modify | Update intent-routing prompt and session merging for Option 2 |
| `src/science_cli/cli/commands/info.py` | Modify | Ensure raw JSON formatting is completely clean and valid for parsing |
| `documentation/AGENTS_SCHEMA.md` | [DELETE] | Redundant guide deleted in favor of AGENTS.md, RULES.md, and SCHEMA.md |

## Dependencies
None

## Cross-PLAN Impact
Requires coordination with plot parameters and overlays defined in [[280526_dashboard]].

## Test Strategy
- Test schema output validity: `python -m json.tool` on outputs from `sci info --json`.
- Test local agent invocation structure in `.opencode/`.

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
