# PLAN: REPL Natural Language + Per-Technique Figure Presets

## Classification
feature

## Related Plans
- PLAN-ai-agent-friendly.md — shares LLM integration concerns (info --json, structured output)
- None currently blocking or blocked by this plan.

## Status
- **Created**: 2026-05-29
- **Status**: draft
- **Branch**: dev

## Objective

1. Add **natural language input** to the `sci --repl` shell so users can type "plot step 3-raman with baseline correction" and get valid `sci` commands executed.
2. Create a **per-technique figure preset system** with publication-ready defaults (Nature/ACS standards) that auto-applies correct figsize, units, axis labels, and special layouts.

## Context

### What Exists Today

**REPL + LLM:**
- `chat_cmd.py` — basic `sci chat <message>` command: sends OpenAI request, returns raw command string, auto-executes. No JSON output, no multi-command, no explanation.
- `repl.py` — prompt_toolkit shell with context banner, dispatches only exact COMMAND_TREE commands. Unknown input shows "Unknown: <cmd>".
- `sci info --json` — provides project manifest for LLM context.
- No LLM library dependency (`pyproject.toml` has zero LLM deps; `chat_cmd.py` uses raw `urllib.request`).

**Figure Presets:**
- `theme/templates/*.yaml` — per-technique templates with basic defaults: `plot_type`, `linewidth`, `linestyle`, `labels` (xlabel, ylabel). Used by `template_to_flags()` in interactive plot mode.
- `plot.py:_figsize()` — hardcoded `(10, 7)` default.
- `raman.py` — hardcoded `(10, 5)` figsize.
- No concept of per-technique figsize, no `--preset` or `--smart-layout` flags.
- Theme system (`registry.py`) reads from YAML themes but no theme YAML files exist — everything is hardcoded RC params.

**Plot dispatch flow (relevant for presets):**
```
plot_handler → _plot_direct / _plot_interactive → _do_plot / _do_overlap
  → _figsize(flags) → hardcoded (10,7)
  → _resolve_xy_columns(df, info, technique) → xlabel, ylabel from data columns
  → _apply_figure_kw(ax, flags, ...)
  → fig.savefig(...)
```
`template_to_flags()` is only called in `_plot_interactive()` (fzf path), not in `_plot_direct()`.

### What the User Wants

**Feature 1: LLM Compiler REPL**
- System prompt contains full COMMAND_TREE + command help (extracted programmatically)
- LLM maps natural language → valid `sci` commands
- Structured JSON output: `{ "commands": [...], "explanation": "..." }`
- Display explanation before executing
- Fallback: if feature is missing, log to `issues.json` and suggest alternatives
- LLM backend: OpenAI-compatible API, same env vars as existing `chat_cmd`

**Feature 2: Per-Technique Figure Presets**
- YAML-based figure presets for each technique following publication standards
- Integrate with existing theme/templates pattern
- Support `--preset <journal>` and `--smart-layout` flags
- Auto-apply based on technique detection
- Presets override hardcoded defaults but can be overridden per-plot

## Specification

### Feature 1: REPL Natural Language

#### Phase 1a — NL Router in REPL

When the REPL receives input that is NOT in `COMMAND_TREE` (the "Unknown" fallback), instead of printing "Unknown: <cmd>", try NL routing:

```
user input → exact match in COMMAND_TREE? → dispatch normally
          → match known meta commands (help, history, etc)? → dispatch
          → NL COMPILER FALLBACK:
              1. Build system prompt (COMMAND_TREE + help text) programmatically
              2. Call LLM (same as chat_cmd's backend)
              3. Parse structured JSON response
              4. Display explanation
              5. Execute commands sequentially
              6. On error or missing feature: log to issues.json
```

#### Phase 1b — Structured JSON Output Schema

Instead of raw command string (current `chat_cmd`), the LLM returns:

```json
{
  "commands": ["sci plot protocol/1_iv-test/3-raman/raman_data.txt --baseline --norm --name raman_baseline.pdf"],
  "explanation": "Plotting the Raman spectrum for step 3-raman with baseline correction and normalization. Output: raman_baseline.pdf in protocol results directory.",
  "confidence": "high",
  "suggestions": []
}
```

Error/fallback schema:
```json
{
  "commands": [],
  "explanation": "Cannot find a step named '3-raman' in the current project. Available steps: 1_set, 2_reset.",
  "confidence": "low",
  "suggestions": ["Try 'sci ls' to see available steps"]
}
```

#### Phase 1c — System Prompt Construction

Build the system prompt dynamically from `COMMAND_TREE` and `COMMAND_HELP`:

```python
def build_compiler_prompt() -> str:
    prompt = """You are a science-cli compiler. Convert natural language to sci CLI commands.
    
Respond ONLY with JSON: { "commands": [...], "explanation": "...", "confidence": "high|medium|low", "suggestions": [...] }

Available commands:"""
    for cmd, info in COMMAND_HELP.items():
        prompt += f"\n\n{cmd}: {info['desc']}\n"
        for sub, sub_info in info.get("subcommands", {}).items():
            prompt += f"  {sub}: {sub_info['desc']}\n"
        for flag_name, flag_info in info.get("flags", {}).items():
            prompt += f"  Flag {flag_name}: {flag_info['desc']}\n"
        for ex in info.get("examples", []):
            prompt += f"  Example: {ex}\n"
    prompt += _build_session_context()
    return prompt
```

#### Phase 1d — Issues.json Fallback

When the LLM responds with `"confidence": "low"` or no valid commands, append to `~/.config/science-cli/repl_issues.json`:

```json
{
  "timestamp": "2026-05-29T14:30:00",
  "input": "plot step 3-raman with baseline correction",
  "llm_response": "...",
  "reason": "Step '3-raman' not found in current project"
}
```

#### Phase 1e — LLM Backend

Reuse `chat_cmd.py`'s approach but refactor into shared utility:
- API key: `SCI_LLM_API_KEY` env var or `~/.config/science-cli/config.yaml` → `chat.api_key`
- Model: `SCI_LLM_MODEL` env var (default `gpt-4o`)
- Base URL: `SCI_LLM_BASE_URL` env var (default `https://api.openai.com/v1`)
- **No new dependency** — keep using `urllib.request` (matching existing pattern)

#### Phase 1f — REPL Integration

Modify the "Unknown: {cmd}" fallback in `repl.py`:
1. Try NL compiler
2. If commands returned, print explanation, then execute each command
3. If no commands, print suggestions
4. Add `--no-nl` flag to REPL to disable LLM routing

### Feature 2: Figure Preset System

#### Phase 2a — Preset Data Model

Create `src/science_cli/theme/presets/` directory with per-technique YAML:

```yaml
# presets/raman.yaml
technique: raman
figure:
  figsize: [3.33, 2.75]       # Nature single-column
  dpi: 600
labels:
  xlabel: "Raman shift (cm⁻¹)"
  ylabel: "Intensity (a.u.)"
layout:
  fingerprint_range: [200, 1800]    # auto xlim for raman
  tick_label_size: 8
```

```yaml
# presets/ec-eis.yaml
technique: ec-eis
figure:
  figsize_nyquist: [3.33, 3.33]    # 1:1 aspect ratio
  figsize_bode: [3.33, 2.75]
  dpi: 600
labels:
  xlabel_nyquist: "Z′ (Ω)"
  ylabel_nyquist: "−Z″ (Ω)"
  xlabel_bode: "Frequency (Hz)"
```

```yaml
# presets/ec-cv.yaml
technique: ec-cv
figure:
  figsize: [3.33, 2.75]
  dpi: 600
labels:
  xlabel: "E vs Ref (V)"
  ylabel: "I (mA)"
layout:
  show_arrow: true           # IUPAC anodic direction arrow
  iupac_convention: true     # anodic current upward
```

#### Phase 2b — Journal Variants

Each technique preset supports journal-specific overrides:

```yaml
# presets/raman.yaml (extended)
technique: raman
presets:
  nature:
    figure:
      figsize: [3.33, 2.75]   # single column
      dpi: 600
    font:
      family: "Helvetica"
      size: 8
  acs:
    figure:
      figsize: [3.25, 2.5]    # ACS single column
      dpi: 600
    font:
      family: "Helvetica"
      size: 8
  default:
    figure:
      figsize: [3.33, 2.75]
      dpi: 300
    font:
      family: "sans-serif"
      size: 10
```

`--preset nature` loads the `nature` variant for the detected technique.

#### Phase 2c — Flag Integration

New plot command flags:
- `--preset <journal>` — "nature", "acs", "default" (applies journal-specific preset)
- `--smart-layout` — auto-applies preset based on technique detection (same as `--preset default`)
- Without flags: preserve current behavior (backward compatible), but use preset figsize instead of hardcoded `(10, 7)`

#### Phase 2d — Preset Loading + Override Resolution

```
1. Detect technique (from filename or -t flag)
2. Load preset YAML: theme/presets/{technique}.yaml
3. If --preset <journal>, select that variant
4. Merge with user's explicit flags (explicit flags override preset)
5. Apply to figure
```

#### Phase 2e — Preset Registry

New module `src/science_cli/theme/presets.py`:

```python
def load_preset(technique: str, journal: str = "default") -> dict:
    """Load figure preset for technique + journal variant."""

def apply_preset(fig, ax, preset: dict, flags: dict = None) -> None:
    """Apply preset to figure, with flag overrides."""

def list_techniques_with_presets() -> list[str]:
    """List techniques that have preset YAML files."""

def preset_to_rcparams(preset: dict) -> dict:
    """Convert preset dict to matplotlib rcParams overrides."""
```

#### Phase 2f — Per-Technique Preset Table

| Technique | Figsize (in) | X Label (units) | Y Label (units) | DPI | Special |
|-----------|-------------|-----------------|-----------------|-----|---------|
| **raman** | 3.33×2.75 | Raman shift (cm⁻¹) | Intensity (a.u.) | 600 | Fingerprint 200-1800, tick labels 8pt |
| **uv-vis** | 3.33×2.75 | Wavelength (nm) | Absorbance (a.u.) | 600 | Range 300-800 nm auto-xlim |
| **ec-cv** | 3.33×2.75 | E vs Ref (V) | I (mA) | 600 | Scan arrow, IUPAC (anodic up) |
| **ec-ca** | 3.33×2.75 | Time (s) | I (mA) | 600 | Step potential annotation |
| **ec-eis (Nyquist)** | 3.33×3.33 | Z′ (Ω) | −Z″ (Ω) | 600 | **1:1 aspect** (mandatory) |
| **ec-eis (Bode)** | 3.33×2.75 | Frequency (Hz) | Dual y: \|Z\|, phase | 600 | Log x-axis auto |
| **iv-sweep** | 3.33×2.75 | Voltage (V) | Current (A) | 600 | Semi-log toggle |
| **iv-breakdown** | 3.33×2.75 | Voltage (V) | Current (A) | 600 | — |
| **iv-leakage** | 3.33×2.75 | Voltage (V) | \|Current\| (A) | 600 | — |
| **mem-endurance** | 3.33×2.75 | Cycle # | Resistance (Ω) | 600 | Log y-axis auto |
| **mem-retention** | 3.33×2.75 | Time (s) | Resistance (Ω) | 600 | Log y-axis auto |
| **mem-switching** | 3.33×2.75 | Cycle # | Voltage (V) | 600 | — |

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/repl.py` | Modify | Add NL fallback path before "Unknown" dispatch |
| `src/science_cli/cli/commands/chat_cmd.py` | Modify | Refactor LLM call into shared utility; add JSON parsing |
| `src/science_cli/core/llm_utils.py` | **NEW** | Shared LLM backend (API call, prompt builder, JSON parser) |
| `src/science_cli/cli/commands/__init__.py` | Modify | Expose dynamic COMMAND_TREE export for prompt building |
| `src/science_cli/theme/presets.py` | **NEW** | Preset loader, apply, registry |
| `src/science_cli/theme/presets/*.yaml` | **NEW** | 12 per-technique preset YAML files |
| `src/science_cli/theme/__init__.py` | Modify | Export preset functions |
| `src/science_cli/cli/commands/plot.py` | Modify | Add `--preset`, `--smart-layout` flags; use presets for figsize/DPI/labels |
| `src/science_cli/theme/registry.py` | Modify | Integrate preset loading into `template_to_flags` |
| `src/science_cli/cli/help.py` | Modify | Add help text for new plot flags |
| `pyproject.toml` | No change | No new dependencies (use urllib.request) |

## Dependencies

**Feature 1:**
- Existing `chat_cmd.py` LLM backend (API key, env vars, urllib.request)
- Existing `COMMAND_TREE` and `COMMAND_HELP` from `__init__.py` and `help.py`
- Existing `sci info --json` for session context
- **No new Python dependencies**

**Feature 2:**
- Existing `theme/templates/` YAML pattern (extend with presets)
- Existing `registry.py` theme loading infrastructure
- Existing `plot.py` flag parsing and figure creation pipeline
- **No new Python dependencies**

## Cross-PLAN Impact

- PLAN-ai-agent-friendly.md — this plan's LLM Compiler shares the JSON output format philosophy; the refactored `llm_utils.py` should be compatible with that plan's vision
- PLAN-dashboard-themes-fzf-columns.md — presets could feed into dashboard figure sizing later
- No blocking relationships

## Test Strategy

**Unit tests:**
1. `test_llm_utils.py` — prompt builder extracts correct COMMAND_TREE, JSON parser handles valid/invalid responses
2. `test_presets.py` — load each preset YAML (12 techniques), verify key fields (figsize, xlabel, ylabel, dpi), verify journal variants
3. `test_preset_apply.py` — preset overrides hardcoded values, user flags override preset values

**Integration tests:**
4. `test_repl_nl_fallback.py` — REPL input "plot step 1 with loglog" triggers NL path (mock LLM), explanation displayed, command executed
5. `test_plot_preset.py` — `sci plot -f data.csv --preset nature` applies correct figsize + DPI
6. `test_smart_layout.py` — `sci plot -f data.csv --smart-layout` auto-detects technique and applies preset

**Manual smoke tests:**
7. `sci --repl` → type "show me all raman files" → LLM maps to `sci raman ls`
8. `sci --repl` → type "plot cv data with peaks" → LLM maps to correct plot + analyze commands
9. `sci plot -f data.csv --preset nature` → verify figure dimensions (3.33×2.75, 600 DPI, Helvetica)

## Progress

- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
