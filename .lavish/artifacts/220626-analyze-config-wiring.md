---
layer: [1, 5, 6, 7]
type: plan
status: done
tags: [analyze, config, plot-defaults, protocol-override, pulse-endurance]
depends_on: [210626-endurance-plots]
assignee: plan
---

# Implementation Plan: Analyze Config Wiring + Per-File Protocol Override

**Date**: 22/06/2026
**Status**: 🟡 Planning
**Layer**: 1 (Config) + 5 (Plotting Dispatch) + 6 (Protocol) + 7 (Pulse Analyzers)

## Context Summary

The `interactive.analyze` menu for pulse-endurance works (Rich menu shows 4 options), and `plot_defaults` already exists in config-studies.yaml with carefully tuned defaults for bar colors, bins, fit styles, etc. **But the analyze functions in `pulse_endurance.py` hardcode everything** — `bins=50`, `color="#2EA043"`, `y_max = sorted_n[-2] * 1.5` etc. The config is dead.

**Three things need to happen:**

1. **Restructure `interactive.analyze`** — from array-based `options: [{name, handler, ...}]` + separate `plot_defaults:` block, to a **key-based** structure where each analyze function is its own key with `plot:` block inline.
2. **Create `resolve_analysis_plot_config()`** — reads from restructured config + per-file overrides from protocol.yaml → returns flat dot-separated dict.
3. **Refactor 4 analyze functions** to read from resolved config, with hardcoded fallbacks and `--show-config` dump.

### Resolution Order (lowest → highest priority)

1. **Hardcoded Python defaults** (fallback)
2. **Config layer** (`config-studies.yaml:...interactive.analyze.<function>.plot`)
3. **Protocol per-file analyz config** (`protocol.yaml:steps[].files[].analyze.<function>`)
4. **Device overrides** (future)

## Objectives

1. Restructure `interactive.analyze` config schema — key-based, each function self-contained with own `plot:` block
2. Create `resolve_analysis_plot_config()` in `core/plot_config.py`
3. Create `resolve_file_analyze_overrides()` in `core/protocol.py`
4. Refactor `ratio_histogram()` + `current_ratio_histogram()` to use config + `--show-config`
5. Refactor `ratio_vs_cycles()` + `i_ratio_vs_cycles()` to use config + `--show-config`
6. Update `interactive_menu.py dispatch()` for key-based schema
7. QA with real `res_internship` data
8. Docs — CHANGELOG, .lavish Layer 7 dashboard

## Files to Modify

| # | File | Change | Risk |
|---|------|--------|------|
| M1 | `config/config-studies.yaml` | Restructure `interactive.analyze` from array-based to key-based; move `plot_defaults` into per-function `plot:` | Low |
| M2 | `src/science_cli/core/plot_config.py` | Add `resolve_analysis_plot_config()` | Med |
| M3 | `src/science_cli/core/protocol.py` | Add `resolve_file_analyze_overrides()` | Low |
| M4 | `src/science_cli/core/interactive_menu.py` | Update `load_study_menu()` + `dispatch()` for key-based schema | Med |
| M5 | `src/science_cli/library/pulse/pulse_endurance.py` | Refactor 4 functions to use config + `--show-config` | Med |

## Architecture

```
config-studies.yaml                          protocol.yaml
  └─ pulse:                                      └─ step:
       pulse-endurance:                               files:
         interactive:                                     - file: ..._extracted-list.csv
           analyze:                                        analyze:
             ratio_histogram:                                ratio_histogram:
               menu_title: "Ratio Histogram"                   bins: 100
               handler: "..."                                  series:
               plot:                                             bar:
                 bins: 50                                         color: "#8B0000"
                 series:
                   bar: {color: "#2EA043"}
                                    │
                                    ▼
                    resolve_analysis_plot_config()
                    ("pulse:pulse-endurance", "ratio_histogram",
                     filepath="...")
                                    │
                                    ▼
                         Flat dict:
                         {"bins": 100,
                          "series.bar.color": "#8B0000",
                          ...}
                                    │
                                    ▼
                    pulse_endurance.py functions
                    cfg.get("bins", 50)
                    cfg.get("series.bar.color", "#2EA043")
```

## resolve_analysis_plot_config() API

```python
def resolve_analysis_plot_config(
    study_name: str,
    function_name: str,
    device_type: str | None = None,
    filepath: str | None = None,
) -> dict:
    """Resolve plot config for an analyze function.

    Resolution order (lowest → highest):
    1. config-studies.yaml: interactive.analyze.<function>.plot
    2. protocol.yaml: steps[].files[].analyze.<function>
    3. (future) device_overrides.<device>.analyze.<function>

    Returns flat dot-separated dict.
    """
    cfg = load_global_config()
    technique, study_key = parse_study_name(study_name)
    analyze_entry = (cfg["studies"][technique][study_key]
                     ["interactive"]["analyze"][function_name])
    study_cfg = analyze_entry.get("plot", {})

    # Protocol per-file analyze config
    proto_cfg = {}
    if filepath:
        from science_cli.core.protocol import resolve_file_analyze_config
        proto_cfg = resolve_file_analyze_config(filepath, function_name)

    merged = _deep_merge(study_cfg, proto_cfg)
    return _flatten_dict(merged)
```

## resolve_file_analyze_config() API

```python
def resolve_file_analyze_config(
    filepath: str | Path,
    function_name: str,
) -> dict:
    """Read per-file analyze config from protocol.yaml.

    Walks up from filepath to find protocol.yaml, locates the file
    entry in steps[].files[].analyze.<function>,
    returns the config dict or empty dict.
    """
    # Walk up to find protocol/<name>/<name>.yaml
    parts = Path(filepath).parts
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        proto_yaml = Path(*parts[:proto_idx + 2]) / f"{proto_name}.yaml"
    except (ValueError, IndexError):
        return {}

    if not proto_yaml.exists():
        return {}

    import yaml
    data = yaml.safe_load(proto_yaml.read_text()) or {}
    fname = Path(filepath).name
    for step in data.get("steps", []):
        for entry in step.get("files", []):
            entry_file = entry["file"] if isinstance(entry, dict) else entry
            if entry_file == fname:
                metadata = entry.get("metadata", {}) if isinstance(entry, dict) else {}
                return metadata.get("analyze_overrides", {}).get(function_name, {})
    return {}
```

## Detailed Config Schema

### New key-based structure

```yaml
    pulse-endurance:
      # ... existing patterns, data_shape, instruments ...
      interactive:
        plot:
          # ... plot menu (keep as-is) ...
        analyze:
          ratio_histogram:
            menu_title: "Ratio Histogram"
            handler: "science_cli.library.pulse.pulse_endurance.ratio_histogram"
            description: "Distribution of R_HRS / R_LRS ratio values"
            plot:
              bins: 50
              y_max_method: "2nd-bin*1.5"
              series:
                bar:
                  color: "#2EA043"
                  alpha: 0.7
                  edgecolor: "black"
                  linewidth: 0.5
                fit:
                  type: "log-normal"
                  color: "black"
                  style: "--"
                  linewidth: 1.2
                mean_line:
                  color: "red"
                  style: "--"
                median_line:
                  color: "blue"
                  style: ":"
              legend:
                loc: "upper right"
                fontsize: 8

          current_ratio_histogram:
            menu_title: "Current Ratio Histogram"
            handler: "science_cli.library.pulse.pulse_endurance.current_ratio_histogram"
            description: "Distribution of I_LRS / I_HRS ratio values"
            plot:
              bins: 50
              y_max_method: "2nd-bin*1.5"
              series:
                bar:
                  color: "#2EA043"
                  alpha: 0.7
                  edgecolor: "black"
                  linewidth: 0.5
                fit:
                  type: "log-normal"
                  color: "black"
                  style: "--"
                  linewidth: 1.2
                mean_line:
                  color: "red"
                  style: "--"
                median_line:
                  color: "blue"
                  style: ":"
              legend:
                loc: "upper right"
                fontsize: 8

          ratio_vs_cycles:
            menu_title: "Ratio vs Cycles"
            handler: "science_cli.library.pulse.pulse_endurance.ratio_vs_cycles"
            description: "R_HRS/R_LRS ratio trend over cycle number"
            plot:
              axes:
                xscale: log
                yscale: log
              series:
                scatter:
                  color: "#CC7700"
                  size: 6
                  alpha: 0.6
                  label: "Data"
                fit:
                  color: "red"
                  style: "--"
                  linewidth: 1.2
              legend:
                loc: "upper right"
                fontsize: 8

          i_ratio_vs_cycles:
            menu_title: "Current Ratio vs Cycles"
            handler: "science_cli.library.pulse.pulse_endurance.i_ratio_vs_cycles"
            description: "I_LRS/I_HRS ratio trend over cycle number"
            plot:
              axes:
                xscale: log
                yscale: log
              series:
                scatter:
                  color: "#2176AE"
                  size: 6
                  alpha: 0.6
                  label: "Data"
                fit:
                  color: "red"
                  style: "--"
                  linewidth: 1.2
              legend:
                loc: "upper right"
                fontsize: 8
```

### interactive_menu.py key-based dispatch

```python
def load_study_menu(study_key: str, menu_type: str) -> dict:
    """Returns dict of {function_key: {menu_title, handler, description, plot}}"""
    config_path = _get_config_path()
    with open(config_path) as f:
        config = yaml.safe_load(f)

    search_key = _normalize_study_key(study_key)
    for group in config.get("studies", {}).values():
        if search_key in group:
            study_cfg = group[search_key]
            interactive = study_cfg.get("interactive", {})
            menu = interactive.get(menu_type)
            if menu is None:
                raise KeyError(f"No interactive.{menu_type} for '{search_key}'")
            return menu

    raise KeyError(f"Study '{search_key}' not found")

def dispatch(study_key, menu_type, file_paths, **kwargs):
    if isinstance(file_paths, Path):
        file_paths = [file_paths]

    menu = load_study_menu(study_key, menu_type)
    # menu is now a dict: {function_key: {menu_title, handler, ...}}
    keys = list(menu.keys())
    choices = [menu[k] for k in keys]

    # Show menu using menu_title from first item (or find shared title)
    first = choices[0]
    title = first.get("menu_title", f"Select {menu_type}:")
    choice_idx = show_menu(title, choices) - 1
    selected_key = keys[choice_idx]
    selected = choices[choice_idx]

    # Dynamic import
    handler_path = selected["handler"]
    module_path, func_name = handler_path.rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)

    # Pass scale if present
    scale = selected.get("scale")
    if scale:
        kwargs["scale"] = scale

    if selected.get("overlay"):
        kwargs["file_paths"] = file_paths
        handler(**kwargs)
    else:
        for fp in file_paths:
            kwargs["file_path"] = fp
            handler(**kwargs)
```

### show_menu updated for dict-based options

```python
def show_menu(title: str, options: list[dict], default: int = 1) -> int:
    import questionary
    choices = []
    for i, opt in enumerate(options, 1):
        label = opt.get("name", opt.get("menu_title", f"Option {i}"))
        desc = opt.get("description", "")
        if desc:
            label += f" — {desc}"
        choices.append(questionary.Choice(title=label, value=i))

    result = questionary.select(
        title,
        choices=choices,
        default=choices[default - 1] if default - 1 < len(choices) else choices[0],
    ).ask()
    return result if result is not None else default
```

## Agent Delegation

| Task | Sub-agent | Files | Est. Time | Deps |
|------|-----------|-------|-----------|------|
| T1: Restructure config-studies.yaml | code-medium | config/config-studies.yaml | 20m | None |
| T2: resolve_analysis_plot_config() | code-medium | core/plot_config.py | 30m | T1 |
| T3: resolve_file_analyze_overrides() | code-medium | core/protocol.py | 25m | None |
| T4: Update interactive_menu.py | code-medium | core/interactive_menu.py | 20m | T1 |
| T5: Refactor histogram functions | code-medium | library/pulse/pulse_endurance.py | 45m | T2+T3 |
| T6: Refactor scatter functions | code-medium | library/pulse/pulse_endurance.py | 30m | T2+T3 |
| T7: QA with real data | review-light | Manual + pytest | 20m | T4+T5+T6 |
| T8: Docs + .lavish dashboards | docs-heavy | Docs + Layer 7 | 20m | T7 |

## Dependency Order

1. T1 (config schema) → T4 (menu) — parallel: T2 (config resolver), T3 (protocol override getter)
2. T1+T2+T3 → T5+T6 (function refactors)
3. T5+T6 → T7 (QA)
4. T7 → T8 (docs)

## Walkthrough

### Test scenario 1: Default behavior preserved
1. `sci analyze --all` → FZF → select endurance extracted-list CSV
2. Menu shows 4 options → pick "Ratio Histogram"
3. Plots with config-studies.yaml default values (bins=50, green bars, etc.)
4. Same as before — no breakage

### Test scenario 2: Per-file override
1. Edit protocol.yaml step entry:
   ```yaml
   - file: 200626-140448_...extracted-list.csv
     metadata:
       analyze_overrides:
         ratio_histogram:
           bins: 100
           series:
             bar:
               color: "#8B0000"
   ```
2. Re-run analyze → histogram uses bins=100, red bars
3. Config dump confirms: `{"bins": 100, "series.bar.color": "#8B0000", ...}`

### Test scenario 3: Config dump
1. `sci analyze --all` → FZF → select file → menu → pick "Current Ratio Histogram" with `--show-config`
2. Prints resolved config to terminal + normal plot saved

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Key-based schema breaks interactive_menu | High — menu doesn't render | Both `load_study_menu()` and `show_menu()` updated together in T4 |
| Protocol per-file lookup fails | Low — returns empty, uses defaults | `try/except` + empty dict fallback |
| pulse_endurance.py (530L) close to splitting threshold | Med | Keep refactors minimal; no extra abstraction |
| `--show-config` flag needs CLI plumbing | Low | `**kwargs` catches it, no CLI parser changes needed |

## Status

- [ ] T1: Config schema restructured
- [ ] T2: resolve_analysis_plot_config() written
- [ ] T3: resolve_file_analyze_overrides() written
- [ ] T4: interactive_menu.py updated
- [ ] T5: Histogram functions refactored
- [ ] T6: Scatter functions refactored
- [ ] T7: QA verified
- [ ] T8: Docs + .lavish dashboards updated
