# PLAN: Plot Label Optimization — Config-Driven Labels & No-Quotes

## Classification
config / refactor

## Related Plans
- [[280526_refactor]] — related (templates refactored)
- [[280526_themes]] — related (theme/template system)

## Status
- **Created**: 2026-05-28
- **Status**: completed
- **Branch**: dev

## Objective
Fix label resolution so xlabel/ylabel are config-driven from `~/.config/science-cli/config.yaml` with a clean resolution chain, and eliminate the need for shell quoting on multi-word labels.

## Context
### Problem 1: Labels not user-configurable
Currently, technique labels come only from hardcoded plot templates (`theme/plot-templates/*.yaml`) or column auto-detection. Users cannot define their preferred labels centrally. We'll add a `plot.labels.<technique>` section to the global config YAML so users control per-technique labels.

### Problem 2: Template labels silently ignored
`template_to_flags()` in `theme/registry.py:156` reads `data.get("labels", {})` but all 11 plot templates store labels under the key `axes:` — technique-specific default labels are **never loaded**.

### Problem 3: No-quotes parsing
`_parse_flags()` in `plot.py:24` only grabs the **next single token** as a flag value. So `--xlabel Wavelength (nm)` sets xlabel=`"Wavelength"` and treats `(nm)` as a positional arg.

### Problem 4: Direct path skips template/config defaults
`_plot_direct()` detects technique but never calls `template_to_flags()` or reads config labels.

### Problem 5: UV-Vis ylabel mismatch
Template has `ylabel: "Absorbance (a.u.)"` but user expects `T%`.

## Specification

### Resolution Chain (last wins)
```
1. CLI --xlabel / --ylabel             (highest — per-plot override)
2. Config plot.labels.<technique>      (user preference — global)
3. Column auto-detection               (data-file headers)
4. Plot template YAML axes:            (hardcoded fallback)
```

### 1. Add `plot.labels` config section
New top-level section in `~/.config/science-cli/config.yaml`:
```yaml
plot:
  labels:
    uv-vis:
      xlabel: "Wavelength (nm)"
      ylabel: "T%"
    iv-sweep:
      xlabel: "Voltage (V)"
      ylabel: "Current (A)"
    ec-cv:
      xlabel: "E vs Ref (V)"
      ylabel: "I (mA)"
```

### 2. Add `get_plot_labels()` accessor in `core/config.py`
- Reads `plot.labels.<technique>` from merged config
- Returns dict with `xlabel`/`ylabel` or empty dict

### 3. Fix `template_to_flags()` — axes key
In `theme/registry.py:156`: `data.get("labels", {})` → `data.get("axes", {})`

### 4. Fix `_parse_flags()` — multi-token values
In `plot.py:22-28`: consume all subsequent non-flag tokens, join with spaces.

### 5. Add template+config label resolution to plot paths
- In `_do_plot()`: apply config labels between column auto-detect and CLI flags
- In `_plot_direct()`: load template flags + config labels + CLI flags
- In `_plot_interactive()`: config labels already layered via `_do_plot()`

### 6. Fix uv-vis.yaml ylabel
- Change from `"Absorbance (a.u.)"` → `"Transmission (%)"`

## Files Modified
| File | Action | Reason |
|------|--------|--------|
| `src/science_cli/core/config.py` | Edit | Add `get_plot_labels()` accessor |
| `src/science_cli/theme/registry.py:156` | Edit | Fix label key `labels:`→`axes:` |
| `src/science_cli/cli/commands/plot.py:22-28` | Edit | Multi-token flag values (no quotes) |
| `src/science_cli/cli/commands/plot.py:489-494` | Edit | Add template+config labels to direct path |
| `src/science_cli/cli/commands/plot.py:653-663` | Edit | Add config labels layer between column/CLI |
| `src/science_cli/theme/plot-templates/uv-vis.yaml:9` | Edit | Fix ylabel to `Transmission (%)` |
| `~/.config/science-cli/config.yaml` | Edit | Add `plot.labels` section with defaults for all 11 techniques |

## Dependencies
None — all changes are self-contained.

## Test Strategy
1. **Config accessor**: `get_plot_labels("uv-vis")` returns correct labels from config
2. **No-quotes**: `_parse_flags(["--xlabel", "Voltage", "(V)"])` returns `{"xlabel": "Voltage (V)"}`
3. **Resolution chain**: CLI flag > config > column > template
4. **Template fix**: `template_to_flags("uv-vis")` returns xlabel/ylabel

## Progress
- [x] PLAN created
- [x] User approved
- [x] IMPLEMENT — config accessor (`get_plot_labels()`)
- [x] IMPLEMENT — template_to_flags fix (`labels:` → `axes:`)
- [x] IMPLEMENT — multi-token parser (no quotes needed)
- [x] IMPLEMENT — config labels in plot paths (interactive + direct)
- [x] IMPLEMENT — uv-vis ylabel fix (`Transmission (%)`)
- [x] IMPLEMENT — user config update (`plot.labels` section)
- [x] TEST passed (97 tests, all green)
- [x] COMMIT done (`a71eff6` on `dev`)

## Summary
All items complete. Resolution chain: `CLI --xlabel` > `Config plot.labels.<technique>` > `Column auto-detection` > `Template YAML axes:`.
Labels like `--xlabel Voltage (V)` no longer require shell quoting.
