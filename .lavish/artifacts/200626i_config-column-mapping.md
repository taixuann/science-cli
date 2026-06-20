---
layer: [1, 5]
type: plan
status: planning
tags: [config, column-mapping, plot]
assignee: plan
---

# Implementation Plan: Config-Based Column Mapping + Studies Rename

**Date**: 20/06/2026
**Status**: 🟡 Planning
## Context Summary

The `sci plot` command has hardcoded column mappings in `_resolve_xy_columns()` instead of reading from `config-studies.yaml`. This causes:
1. Wrong plot prefix (`ec-ca_` instead of `pulse-stp-decay_`)
2. No column mapping for Keysight pulse studies
3. Current sign issue (Keysight outputs negative current)

## Problems to Fix

### 1. Hardcoded Column Mappings
`_resolve_xy_columns()` (lines 680-800) has hardcoded mappings for each technique:
- `ec-ca` → `WE(1).Current (A)`
- `ec-cv` → `WE(1).Potential (V)`
- `iv-sweep` → `Voltage (V)`, `Current (A)`
- **No mapping for `pulse-stp-decay`**

### 2. Current Sign Issue
Keysight B1500A outputs negative current for bipolar switching. Need `-1` multiplier.

### 3. "Techniques" vs "Studies"
The codebase uses "technique" terminology but the config uses "studies". Need to rename throughout.

## Proposed Solution

### Phase 1: Add Column Mapping to Config

Add `column_mapping` and `current_sign` to `config-studies.yaml` under each study's instrument:

```yaml
studies:
  pulse:
    pulse-stp-decay:
      instruments:
        keysight-b1500a:
          header_lines: 147
          columns:
            time: Time
            voltage: MeasResult1_value
            current: MeasResult2_value
          column_mapping:
            x: time
            y: current
          current_sign: -1  # Keysight outputs negative current
```

### Phase 2: Update `_resolve_xy_columns()` to Read from Config

Replace hardcoded mappings with config-based resolution:

```python
def _resolve_xy_columns(df, info: dict, technique: str = "") -> tuple:
    """Resolve X/Y columns from config instead of hardcoding."""
    
    # Try to get column mapping from config
    from science_cli.core.config import get_study_config
    study_config = get_study_config(technique)
    
    if study_config and "instruments" in study_config:
        # Get instrument from info or default to first
        instrument = info.get("instrument", list(study_config["instruments"].keys())[0])
        
        if instrument in study_config["instruments"]:
            inst_config = study_config["instruments"][instrument]
            
            # Get column mapping
            if "column_mapping" in inst_config:
                mapping = inst_config["column_mapping"]
                x_key = mapping.get("x", "time")
                y_key = mapping.get("y", "current")
                
                # Get actual column names from config
                columns = inst_config.get("columns", {})
                xcol = columns.get(x_key, x_key)
                ycol = columns.get(y_key, y_key)
                
                # Apply current sign if specified
                if "current_sign" in inst_config and y_key == "current":
                    sign = inst_config["current_sign"]
                    df[ycol] = df[ycol] * sign
                
                return xcol, ycol, xlabel, ylabel
    
    # Fallback to existing hardcoded logic
    ...
```

### Phase 3: Rename "Techniques" to "Studies"

1. Rename `detect_technique()` → `detect_study()`
2. Rename `technique` parameter → `study` throughout
3. Update all callers

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `config/config-studies.yaml` | Add `column_mapping` and `current_sign` to pulse studies | Low |
| `src/science_cli/cli/commands/plot.py` | Update `_resolve_xy_columns()` to read from config | Med |
| `src/science_cli/core/studies.py` | Rename `detect_technique()` → `detect_study()` | Med |
| `src/science_cli/core/technique.py` | Update or deprecate | Low |

## Agent Delegation

| Phase | Sub-agent | Notes |
|-------|-----------|-------|
| 1: Config updates | code-light | Add column_mapping + current_sign to config-studies.yaml |
| 2: Plot command refactor | code-medium | Update _resolve_xy_columns() to read from config |
| 3: Studies rename | code-light | Rename detect_technique() → detect_study() |
| 4: Testing | review-light | Verify plot command works with new config |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing plot functionality | High | Keep hardcoded fallbacks as safety net |
| Config schema changes break old configs | Medium | Make new fields optional with defaults |
| Rename breaks imports | Medium | Update all callers, keep backward compat aliases |
