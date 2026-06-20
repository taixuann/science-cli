---
layer: [1, 2, 3, 4, 5, 7]
type: plan
status: planning
tags: [config, keysight, fzf, plot, pulse, cli]
assignee: plan
---

# Implementation Plan: Science-CLI Post-Refactor Tasks (Batch 2)

**Date**: 14/06/2026
**Status**: 🟡 Planning
## Context Summary

science-cli v3.10.0 post-Phases 0-6 refactor. 214 tests passing. Source at `src/science_cli/`. Four independent features requested:

1. Rename `-d/--device` → `--ins/--instrument` (per-step, NOT `--devices` plural)
2. Add `results --move` subcommand
3. Plot help layout improvements (third column for technique flags, columnar THEME flags)
4. Per-technique `analyze --technique` system

## Key Architectural Points

- **Instrument registry** (`library/instruments/registry.py`) has builtin instruments like `keithley-2400` each with a `techniques: [...]` field — this enables auto-assigning technique when `--ins` is specified
- **`--devices`** (plural) is the per-PROTOCOL device type field (memristor/junction/general) — must NOT change
- **`-d/--device`** (singular) is the per-STEP field currently writing `device:` into protocol YAML step entries
- **YAML field rename**: `device:` per-step → `instrument:` — this is a wire format change
- **Backward compat**: `-d/--device` flags should still be accepted for two versions with deprecation warning
- **Per-technique analyze** should mirror the plot pattern: `--technique <type>` flag + technique-specific flags + validated flags

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/science_cli/cli/commands/add.py` | Rename `-d/--device` flag → `--ins/--instrument` (lines 156, 169, 203, 244, 250). Backward compat shim. YAML field `device:` → `instrument:`. Auto-technique assignment from instrument registry. | Med |
| `src/science_cli/cli/commands/edit_cmd.py` | Same renaming (lines 109, 220, 258, 261, 280, 319, 324, 329). Backward compat shim. Auto-technique from instrument. | Med |
| `src/science_cli/cli/help.py` | Update `-d/--device` → `--ins/--instrument` in add/edit help (lines 69, 97). Update results help. Plot: third column for TECHNIQUE flags in subcommand listing. Plot THEME flags → columnar layout. Analyze: add technique-specific flag groups. | Med |
| `src/science_cli/cli/commands/ls_cmd.py` | Rename "Device" column header → "Instrument" in step table (line 219). Update `s.get("device")` → `s.get("instrument")` (line 229, 263, 434). | Low |
| `src/science_cli/cli/commands/results.py` | Add `--move` flag handler: fzf select results, confirm destination, copy/move with optional rename. Update results_handler to dispatch. | Low |
| `src/science_cli/cli/commands/analyze.py` | Add `--technique/-t` flag support. Add per-technique flag maps matching plot `TECHNIQUE_FLAGS`. Validate technique flags. Route to correct analyzer. Deprecation warnings for per-technique analyze subcommands. | Med |
| `src/science_cli/cli/commands/__init__.py` | No changes needed (handler names unchanged). | None |
| `tests/test_cli.py` | No changes needed (command list unchanged). | None |
| `tests/test_phase3_instruments.py` | Update device→instrument references in test assertions. | Low |
| `tests/test_core/` | Add tests for results --move, analyze --technique, --ins auto-technique. | Low |

## Task 1: `-d/--device` → `--ins/--instrument` (per-step only)

### What changes

| Location | Current | New |
|----------|---------|-----|
| `add.py:156` | `flags.get("d") or flags.get("device", "")` | `flags.get("ins") or flags.get("instrument", "")` |
| `add.py:169` | `entry["device"] = devs[i]` | `entry["instrument"] = devs[i]` |
| `add.py:203` | `flags.get("d") or flags.get("device")` | `flags.get("ins") or flags.get("instrument")` |
| `add.py:244,250` | `s["device"] = devs[i]` / `entry["device"] = devs[i]` | `s["instrument"]` / `entry["instrument"]` |
| `edit_cmd.py:109` | `flags.get("d") or flags.get("device")` | `flags.get("ins") or flags.get("instrument")` |
| `edit_cmd.py:214,220,258,261` | `s["device"] = devs[i]` | `s["instrument"] = devs[i]` |
| `edit_cmd.py:280,319,324` | `flags.get("d") or flags.get("device")` | `flags.get("ins") or flags.get("instrument")` |
| `ls_cmd.py:219,229,263,434` | `s.get("device", "")` | `s.get("instrument", "")` |
| `help.py:69,97` | `-d, --device` | `--ins, --instrument` |

### Sub-task 1a: Command-line flag rename + backward compat shim

In `_parse_flags` in both `add.py` and `edit_cmd.py`, after parsing:

```python
# Backward compat: accept -d/--device with deprecation warning
if not ins_raw:
    d_val = flags.get("d") or flags.get("device")
    if d_val:
        console.print("[yellow]Deprecation: -d/--device is deprecated, use --ins/--instrument. Will be removed in v4.0.0[/yellow]")
        ins_raw = d_val
```

The `warn_unknown("device", devs)` calls in edit_cmd.py should change to `warn_unknown("instrument", devs)` — but the check function needs a new mapping or the `list_global_devices()` function needs to be aliased for instruments.

### Sub-task 1b: YAML field rename `device:` → `instrument:`

All protocol YAML step entries currently write `device: keithley-2400`. This must change to `instrument: keithley-2400`.

This affects:
- `add.py` `_add_protocol` and `_add_metadata` — the `entry["device"] = devs[i]` lines
- `edit_cmd.py` `_edit_protocol` and `_edit_metadata` — the `s["device"] = devs[i]` lines
- `ls_cmd.py` — the `s.get("device", "")` reads

**Migration**: When reading protocol YAMLs, fall back to `device:` key if `instrument:` not found (backward compat reading old YAMLs). This can be done in a helper or inline:

```python
ins = s.get("instrument") or s.get("device", "")
```

### Sub-task 1c: Auto-technique assignment from instrument registry

When `--ins keithley-2400` is specified without `-t/--technique`, look up the instrument in the registry and auto-assign the first compatible technique:

```python
from science_cli.library.instruments.registry import get_instrument
if ins_raw and not techs_raw:
    ins_name = ins_split[0]  # first instrument only for auto-detection
    ins_data = get_instrument(ins_name)
    if ins_data and ins_data.get("techniques"):
        # Auto-assign first technique
        auto_tech = ins_data["techniques"][0]
        console.print(f"[dim]Auto-assigned technique '{auto_tech}' from instrument '{ins_name}'[/dim]")
        techs_raw = auto_tech
```

For multiple steps with one instrument, apply the same technique to all steps. For comma-separated instruments matching comma-separated steps, each step gets its own instrument's technique.

**Edge cases**:
- If `-t` is also given, explicit technique wins (no auto-assignment)
- If instrument not found in registry, print warning but continue
- If instrument has no techniques listed, skip auto-assignment

## Task 2: `results --move` subcommand

### Handler dispatch in `results_handler`

```python
def results_handler(args: list) -> None:
    _, flags = _parse_flags(args)
    
    if args and args[0] in ("--help", "-h"):
        show_command_help("results")
        return
    
    if flags.get("move"):
        _results_move()
        return
    
    # Existing logic...
```

### `_results_move()` implementation

```python
def _results_move() -> None:
    """Collect result files and move/copy to project results/."""
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    import shutil
    
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return
    
    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    
    # Collect all result files
    result_files = []  # [(protocol, step, path)]
    for py in proto_yamls:
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)
        if not proto_path.exists():
            continue
        for sd in sorted(proto_path.iterdir()):
            if not sd.is_dir():
                continue
            results_dir = sd / "results"
            if not results_dir.exists():
                continue
            for pf in sorted(results_dir.iterdir()):
                if pf.suffix in (".pdf", ".svg", ".png", ".csv", ".json", ".txt"):
                    result_files.append((pname, sd.name, pf))
    
    if not result_files:
        console.print("[yellow]No result files found.[/yellow]")
        return
    
    # fzf select
    from science_cli.core.fzf_utils import build_fzf_display, fzf_select
    display_lines = [
        build_fzf_display(pname, sd_name, pf.name)
        for pname, sd_name, pf in result_files
    ]
    selected_displays = fzf_select(display_lines, prompt="Select results to move (Tab to multi-select):", multi=True)
    if not selected_displays:
        console.print("[yellow]No results selected.[/yellow]")
        return
    
    # Resolve selected files
    selected_files = []
    for sel in selected_displays:
        name = sel.split()[-1]
        for pname, sd_name, pf in result_files:
            if pf.name == name:
                selected_files.append((pname, sd_name, pf))
                break
    
    # Confirm destination
    import questionary
    target_dir = proj / "results"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    action = flags.get("move")
    is_copy = action == "copy" or not action  # default: copy
    action_word = "Copy" if is_copy else "Move"
    
    if not questionary.confirm(
        f"{action_word} {len(selected_files)} file(s) to {target_dir}?",
        default=True
    ).ask():
        console.print("[yellow]Cancelled.[/yellow]")
        return
    
    # Perform copy/move
    copied = []
    for pname, sd_name, pf in selected_files:
        dest = target_dir / pf.name
        if dest.exists():
            # Optional rename
            stem = pf.stem
            new_name = f"{stem}_{pname}_{sd_name}{pf.suffix}"
            # Could also prompt for rename per file, but for batch just auto-prefix
            dest = target_dir / new_name
        
        if is_copy:
            shutil.copy2(str(pf), str(dest))
        else:
            shutil.move(str(pf), str(dest))
        copied.append((pf.name, dest.name))
    
    rprint(f"[bold green]✓[/bold green] {action_word}ed {len(copied)} file(s) to {target_dir}")
    for orig, dest_name in copied:
        rprint(f"  [dim]• {orig} → {dest_name}[/dim]")
```

### Help text update

In `help.py`, update `results` section:
```python
"results": {
    "usage": "results [--move]",
    "desc": "Browse saved figures by protocol and step via fzf (Group 2).",
    "subcommands": {
        "results":           {"desc": "Interactive browse via fzf", "usage": "results"},
        "results --move":    {"desc": "Collect results to project/results/", "usage": "results --move [--copy]"},
    },
    "flags": {
        "OPERATION": {
            "--move":    {"desc": "Move selected result files to project/results/"},
            "--copy":    {"desc": "Copy selected result files to project/results/ (default if --move alone)"},
        },
    },
    ...
},
```

## Task 3: Plot help layout improvements

### 3a: Third column for technique flags in subcommand listing

In `show_command_help("plot")`, the subcommand section currently shows two columns: name, desc, usage. Add a third column showing relevant technique flags when applicable.

Change rendering in `help.py:636-638`:
```python
if subcmds:
    console.print("  [bold]SUBCOMMANDS[/bold]")
    for name, sub in subcmds.items():
        console.print(f"    {name:<30} [dim]{sub['desc']}[/dim]")
        console.print(f"    {'':<30}  Usage: [{accent}]{sub['usage']}[/{accent}]")
```

To include a third column for technique flags when the subcommand references `--technique`:
```python
if subcmds:
    console.print("  [bold]SUBCOMMANDS[/bold]")
    console.print(f"    {'Name':<30} {'Description':<50} {'Available Flags'}")
    for name, sub in subcmds.items():
        flags_str = ""
        if name == "plot --technique <type> <file>":
            flags_str = "--laser, --accumulation, --scan-rate..."
        console.print(f"    {name:<30} [dim]{sub['desc'][:48]}[/dim] {flags_str}")
```

Better approach: use Rich `Table` with 3 columns:
```python
from rich.table import Table
table = Table(box=None, show_header=False)
table.add_column("Command", style="bold")
table.add_column("Description")
table.add_column("Flags", style="dim")
for name, sub in subcmds.items():
    flags_str = _get_technique_flags_for_subcommand(name)
    table.add_row(name, sub['desc'], flags_str)
console.print(table)
```

Where `_get_technique_flags_for_subcommand()` checks if the subcommand name references `--technique` and returns the appropriate flag names from `TECHNIQUE_FLAGS` (imported from plot.py).

### 3b: THEME flags in columns

Replace the current flat list for THEME flags (lines 646-651 in help.py) with Rich `Table` or `Columns` rendering.

When `category == "THEME"`, render flags in 2-3 columns instead of one per line:

```python
if category == "THEME":
    from rich.table import Table as RichTable
    theme_table = RichTable(box=None, show_header=False, pad_edge=False)
    theme_table.add_column("Flag", style="bold", width=25)
    theme_table.add_column("Description", style="dim", width=40)
    # Group into batches of ~7-8 per column
    items = list(cat_flags.items())
    for name, flag in items:
        theme_table.add_row(name, flag['desc'])
    console.print(f"  [bold]{category}[/bold]")
    console.print(theme_table)
    console.print()
else:
    # existing rendering...
```

But the user wants them in 2-3 columns (side by side). Use Rich `Columns`:

```python
if category == "THEME":
    from rich import columns as rich_columns
    from rich.text import Text
    items = []
    for name, flag in cat_flags.items():
        items.append(f"{name}: {flag['desc']}")
    from rich.columns import Columns
    console.print(f"  [bold]{category}[/bold]")
    console.print(Columns(items, equal=True, column_first=True))
    console.print()
```

## Task 4: Per-technique analyze system

### 4a: Add `--technique` flag to `analyze_handler`

In `analyze.py`, add `--technique` / `-t` flag detection similar to `plot.py`:

```python
TECHNIQUE_ANALYZERS = {
    "iv-sweep": _analyze_iv,
    "iv-breakdown": _analyze_iv,
    "iv-leakage": _analyze_iv,
    "ec-cv": _analyze_cv,
    "ec-ca": _analyze_ca,
    "ec-eis": _analyze_eis,
    "raman": _analyze_raman,
    "uv-vis": _analyze_uv_vis,
}

ANALYZE_TECHNIQUE_FLAGS = {
    "iv-sweep": [
        {"name": "--vset-only", "type": bool, "help": "Volatile mode — V_set only, no V_reset"},
        {"name": "--yaml", "type": bool, "help": "Output analysis as YAML"},
    ],
    "raman": [
        {"name": "--peaks", "type": bool, "help": "Detect Raman peaks"},
        {"name": "--baseline", "type": bool, "help": "Apply baseline correction"},
    ],
    "uv-vis": [
        {"name": "--bandgap", "type": bool, "help": "Calculate Tauc bandgap"},
        {"name": "--peaks", "type": bool, "help": "Detect absorbance peaks"},
    ],
    "ec-cv": [
        {"name": "--peaks", "type": bool, "help": "Find redox peaks"},
        {"name": "--charge", "type": bool, "help": "Integrate charge"},
    ],
    "ec-ca": [
        {"name": "--fit", "type": str, "help": "Fit CA decay (Cottrell)"},
    ],
    "ec-eis": [
        {"name": "--circuit", "type": str, "help": "EIS circuit model: RRC, RQR"},
        {"name": "--kk", "type": bool, "help": "Kramers-Kronig validation"},
    ],
}
```

### 4b: Route based on `--technique` flag

In `_analyze_direct`, if `--technique` is given, use it instead of auto-detection:

```python
def _analyze_direct(files: list, rest_args: list) -> None:
    _, flags = _parse_flags(rest_args)
    
    if not files:
        console.print("[yellow]No files specified.[/yellow]")
        return
    
    filepath = _resolve_file(files[0])
    if not filepath:
        console.print(f"[red]File not found: {files[0]}[/red]")
        return
    
    # Explicit --technique overrides auto-detection
    tech = flags.get("technique") or flags.get("t", "")
    if not tech:
        tech = _detect_technique(Path(filepath).name)
        if not tech:
            console.print(f"[yellow]Unknown technique. Use --technique <type> to specify.[/yellow]")
            return
    
    # Validate technique flags
    if tech:
        warnings = _validate_analyze_flags(flags, tech)
        for w in warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")
    
    analyzer = TECHNIQUE_ANALYZERS.get(tech)
    if analyzer:
        analyzer(filepath, flags)
    else:
        console.print(f"[yellow]No analyzer for technique '{tech}'.[/yellow]")
```

### 4c: Add technique-specific flag validation

```python
_ALL_ANALYZE_FLAGS = []
for flags in ANALYZE_TECHNIQUE_FLAGS.values():
    _ALL_ANALYZE_FLAGS.extend(flags)

def _validate_analyze_flags(flags: dict, technique: str = "") -> list[str]:
    warnings = []
    if not technique:
        for flag_info in _ALL_ANALYZE_FLAGS:
            key = flag_info["name"].lstrip("-")
            if flags.get(key) is not None:
                warnings.append(
                    f"Flag '{flag_info['name']}' requires --technique <type>."
                )
        return warnings
    allowed = [f["name"] for f in ANALYZE_TECHNIQUE_FLAGS.get(technique, [])]
    for flag_info in _ALL_ANALYZE_FLAGS:
        key = flag_info["name"].lstrip("-")
        if flags.get(key) is not None and flag_info["name"] not in allowed:
            warnings.append(
                f"Flag '{flag_info['name']}' is not valid for technique '{technique}'."
            )
    return warnings
```

### 4d: Help text for `analyze --technique`

Update `COMMAND_HELP["analyze"]` in `help.py`:

```python
"analyze": {
    "usage": "analyze [options] [<file>]",
    "desc": "Analyze data — fzf-based, technique-aware analysis (Group 3). Use --technique to unlock technique-specific flags.",
    "subcommands": {
        "analyze":          {"desc": "Interactive: fzf file selection then analyze", "usage": "analyze"},
        "analyze <file>":   {"desc": "Direct: analyze file with auto-detected technique", "usage": "analyze file.csv"},
        "analyze --technique <type> <file>": {"desc": "Direct: analyze with explicit technique", "usage": "analyze --technique raman file.txt --peaks --baseline"},
    },
    "flags": {
        "TECHNIQUE": {
            "-t, --technique": {"desc": "Technique: iv-sweep, iv-breakdown, ec-cv, ec-ca, ec-eis, raman, uv-vis"},
        },
        "IV-SWEEP (with --technique iv-sweep)": {
            "--vset-only": {"desc": "Volatile mode — detect V_set only"},
            "--yaml": {"desc": "Output analysis as YAML to stdout"},
        },
        "RAMAN (with --technique raman)": {
            "--peaks":    {"desc": "Detect and list Raman peaks"},
            "--baseline": {"desc": "Apply baseline correction before peak detection"},
        },
        "UV-VIS (with --technique uv-vis)": {
            "--bandgap":  {"desc": "Calculate Tauc bandgap"},
            "--peaks":    {"desc": "Detect absorbance peaks"},
        },
        "EC-CV (with --technique ec-cv)": {
            "--peaks":    {"desc": "Find CV redox peaks"},
            "--charge":   {"desc": "Integrate CV charge"},
        },
        "EC-CA (with --technique ec-ca)": {
            "--fit":      {"desc": "Fit CA decay curve to Cottrell equation"},
        },
        "EC-EIS (with --technique ec-eis)": {
            "--circuit":  {"desc": "EIS equivalent circuit model, e.g. RRC, RQR"},
            "--kk":       {"desc": "Validate EIS data with Kramers-Kronig"},
        },
    },
    "examples": [
        "analyze",
        "analyze file.csv",
        "analyze --technique iv-sweep file.csv --vset-only",
        "analyze --technique raman file.txt --peaks --baseline",
        "analyze --technique uv-vis file.txt --bandgap --peaks",
        "analyze --technique ec-cv file.csv --peaks --charge",
        "# Deprecated: use 'sci analyze --technique raman' instead of 'sci raman analyze'",
    ],
},
```

### 4e: Deprecation for per-technique analyze subcommands

In `raman.py`, `ec.py`, `uv-vis.py`, `afm.py`, `memristor.py`, `iv.py`, `pulse.py`, `pvd.py`: when their `analyze` subcommand is called, print a deprecation warning pointing users to `sci analyze --technique <name>`.

Example for raman.py:
```python
def _raman_analyze(...):
    console.print("[yellow]Deprecation: 'sci raman analyze' is deprecated. Use 'sci analyze --technique raman'. Will be removed in v4.0.0.[/yellow]")
    # Forward to analyze module
    from science_cli.cli.commands.analyze import _analyze_raman
    _analyze_raman(filepath, flags)
```

## Agent Delegation

| Task | Sub-agent | Notes |
|------|-----------|-------|
| 1a: Flag rename (add.py, edit_cmd.py) | tools-code-medium | Backward compat shim + deprecation warning |
| 1b: YAML field rename | tools-code-light | `device:` → `instrument:` with read fallback |
| 1c: Auto-technique from instrument | tools-code-medium | Lookup instrument registry, wire into add/edit |
| 2: results --move | tools-code-medium | New `_results_move()` function |
| 3a: Third column for technique flags | tools-code-light | Rich Table in show_command_help |
| 3b: THEME flags in columns | tools-code-light | Rich Columns rendering |
| 4a-d: analyze --technique system | tools-code-medium | TECHNIQUE_ANALYZERS, flag validation, routing |
| 4e: Deprecation in per-technique analyze | tools-code-light | Warning + forward wrapper |
| Test updates | tools-code-light | Update test assertions, add new tests |
| Help text updates | tools-docs-light | Analyze help, results help, add/edit help |
| Lint + typecheck | tools-review-light | Ruff + mypy pass |

## Dependency Order

1. **Task 1a + 1b** (flag + YAML rename) — foundational, other tasks don't depend on it
2. **Task 2** (results --move) — independent
3. **Task 3a + 3b** (plot help layout) — independent  
4. **Task 4a-4d** (analyze --technique core) — independent core
5. **Task 4e** (deprecation in per-technique analyzers) — depends on 4a-4d
6. **Test updates** — after tasks 1-4
7. **Help text + documentation** — after tasks 1-4

Tasks 1, 2, 3, 4 can be done in parallel.

## Risks

- **YAML backward compat**: Old protocol YAMLs with `device:` key won't be read as `instrument:`. Must add fallback: `s.get("instrument") or s.get("device", "")`
- **Test regressions**: `test_phase3_instruments.py` `test_devices_flag_in_add_protocol` checks `data.get("devices") == "memristor"` — this is `--devices` (plural, per-protocol), NOT per-step `device`. Must not break.
- **`test_devices_in_ls_output`**: Tests the `devices:` column in ls output (per-protocol, NOT per-step). Must not be affected.
- **`ins` is already an alias for `instrument` command**: The flag `--ins` won't conflict because `_parse_flags` extracts the flag key, and `ins` is not a command name at parse time.
- **Cross-import from plot.py**: `analyze.py` needs to import technique flag structures or define its own. Define in `analyze.py` to avoid coupling.

## Walkthrough

(To be filled during/after implementation)
