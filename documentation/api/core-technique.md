# `science_cli.core.technique` — Technique Detection & Filename Parsing

Merges hardcoded and config-driven pattern sources to detect measurement
techniques from filenames and parse structured naming conventions.

---

## Dataclasses

### `ColumnMap`

```python
@dataclass
class ColumnMap:
    x: str = ""
    y: str = ""
    x_label: str = ""
    y_label: str = ""
    extras: dict = field(default_factory=dict)
    x_aliases: list[str] = field(default_factory=list)
    y_aliases: list[str] = field(default_factory=list)
```

Maps standard column roles to file-specific column names. `resolve()` returns
`(xcol, ycol, xlabel, ylabel, resolved_extras)` by searching `columns` for the
preferred name first, then each alias in order. `x_label` / `y_label` serve as
display labels; if empty they fall back to the resolved column name or `"X"` /
`"Y"`. `extras` is a `dict[str, str]` mapping role names to column names, each
resolved via `_find_column()`.

### `TechniqueDef`

```python
@dataclass
class TechniqueDef:
    name: str
    label: str
    patterns: list[str]
    description: str = ""
```

Canonical definition of a measurement technique. Used to populate
`BUILTIN_TECHNIQUES` for `IV Sweep`, `EC-CV`, `AFM (Gwyddion)`, etc. `patterns`
holds the same regex list as in `PATTERNS`. `label` is the human-readable name
used by `technique_label()`.

---

## Pattern Dictionaries

### `PATTERNS: dict[str, list[str]]`

Hardcoded fallback regex patterns keyed by technique slug (~28 techniques).
Each value is a list of regex strings matched case-insensitively. Covers:

| Group | Techniques |
|-------|-----------|
| Electrochemistry | `ec-cv`, `ec-ca`, `ec-eis`, `ec-lsv`, `ec-swv` |
| IV measurements | `iv-sweep`, `iv-breakdown`, `iv-leakage` |
| Memory | `mem-endurance`, `mem-retention`, `mem-switching` |
| Pulse | `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd`, `pulse-stp`, `pulse-ppf` |
| Spectroscopy | `raman`, `uv-vis` |
| AFM | `afm-gwy`, `afm-spm`, `afm-ibw`, `afm-jpk`, `afm-stp`, `afm-top` |

### `HARDCODED_GRAMMAR: dict`

Single grammar pattern dict serving as the fallback file-naming rule:

```
regex: (?P<date_code>\d{6,8})[_-](?P<material>[A-Za-z0-9]+)[_-]
       (?P<technique>[A-Za-z0-9]+)[_-]?(?P<matrix>[A-Za-z0-9\-\+]+)?
       [_-]?(?P<suffix>\d+)?
```

The `matrix` field includes a sub-extractor: `r(?P<row>\d+)c(?P<col>\d+)`.

### `BUILTIN_TECHNIQUES: dict[str, TechniqueDef]`

Duplicate of `PATTERNS` expressed as `TechniqueDef` objects with descriptions.
Used as the authoritative registry for technique metadata. Keys match `PATTERNS`
exactly, minus `raman` and `uv-vis` (which exist in `PATTERNS` but are omitted
from `BUILTIN_TECHNIQUES` for reasons of scope).

---

## Pattern Resolution

### `_config_patterns() -> dict[str, list[str]]`

Tries `config.get_technique_config(tech, project_root)` for each known
technique key to extract a `"patterns"` list. Falls back to
`config.get_technique_patterns(tech, project_root)` if no full config exists.
Returns only entries that differ from the hardcoded `PATTERNS`. Returns empty
dict on `ImportError`.

### `_all_patterns() -> dict[str, list[str]]`

Merges config patterns (priority) onto hardcoded `PATTERNS` (fallback).
Config patterns are prepended to the existing list, with duplicates skipped
(first occurrence wins). This is the combined source used by `detect_technique()`.

---

## Technique Detection

### `detect_technique(filename: str) -> str`

Iterates `_all_patterns()` in insertion order. Returns the first technique slug
whose pattern matches `filename` via `re.search(..., re.IGNORECASE)`. Invalid
regex patterns (e.g. glob `*pattern*`) are silently skipped. Returns `""` on no
match.

---

## Labels

### `technique_label(tech: str) -> str`

Hardcoded label lookup. Returns a human-readable name (e.g. `"IV Sweep"`,
`"EIS"`, `"Pulse Endurance"`). Falls back to `tech.upper()` on unknown keys.

### `get_technique_label(technique: str, project_root=None) -> str`

Config-aware label lookup. Checks `config.get_technique_config()` for a
`"label"` field first, then falls back to `technique_label()`. Returns a
`str`.

---

## Grammar Parsing

### `_merge_grammar(base: dict, override: dict) -> dict`

Merges two grammar dicts with override taking priority. Override patterns are
prepended before base patterns; duplicate regexes are skipped via a tracked
set (first occurrence wins). Top-level non-pattern keys from override are
applied to the result after pattern merging.

### `_resolve_grammar_from_merged_config(project_root=None, protocol_name=None, device_type=None) -> dict`

5-tier resolution chain, lowest to highest priority:

1. **Hardcoded grammar** (`HARDCODED_GRAMMAR`) — fallback base
2. **Device-type grammar** — `config.get_device_type_grammar(device_type)` merged
3. **Global config** — `config.get_file_naming_grammar(None)` merged
4. **Project overrides** — `config.get_file_naming_grammar(project_root)` merged
   (only if it differs from global)
5. **Protocol grammar** — reads `<project_root>/protocol/<protocol_name>/<protocol_name>.yaml`
   via `config.get_protocol_grammar()`, merged last

Each layer calls `_merge_grammar()` to prepend, so the final list is in
protocol → project → global → device → hardcoded priority order.

---

## Filename Parsing

### `parse_filename_grammar(filename: str, project_root=None, protocol_name=None, device_type=None) -> dict`

Main entry point for extracting structured fields from a filename. Resolves the
grammar via `_resolve_grammar_from_merged_config()`, then tries each pattern's
regex in resolution order against `filename`. On match:

1. Collects `groupdict()` from the regex
2. Gathers sub-extractor specs from two sources:
   - Pattern-level `"extract"` dict (maps field name → sub-regex)
   - Per-field `"extract"` in the `"fields"` list
3. Applies each sub-extractor via `re.search()` on the extracted value,
   merging sub-groups into the result
4. Calls `standardize_grammar_fields()` for normalization

Returns the normalized dict, or `{"parse_error": "no matching pattern"}` on
failure. If `project_root` is `None`, auto-detects via `get_current_project_path()`.

---

## Field Normalization

### `standardize_grammar_fields(parsed: dict) -> dict`

Normalizes a parsed grammar result to exactly 5 universal fields:

| Field | Description |
|-------|-------------|
| `date_code` | Date in DDMMYY or YYYYMMDD format |
| `material` | Material or device name |
| `technique` | Measurement technique code |
| `matrix` | Crossbar addressing (e.g. `r0c0`, `b1-t1`) |
| `suffix` | Run/cycle number (converted to `int` if possible) |

Missing fields are set to `None`. Additionally extracts `row` / `col` integers
from `matrix` using two patterns:

- **rNcN**: `r(?P<row>\d+)-?c(?P<col>\d+)` — row/col as-is
- **bN-tN**: `b(?P<col>\d+)-t(?P<row>\d+)` — converted to 0-indexed
  (`tN - 1` → row, `bN - 1` → col)

`suffix` is converted to `int` if parseable.

---

## Helper

### `_find_column(preferred: str, aliases: list[str], columns: list[str]) -> str`

Returns the first string from `[preferred] + aliases` that exists in `columns`,
or `""` if none match. Used by `ColumnMap.resolve()` for column name matching.

---

## Cross-references

| Config function | Used by |
|----------------|---------|
| `config.get_technique_config()` | `_config_patterns()`, `get_technique_label()` |
| `config.get_technique_patterns()` | `_config_patterns()` |
| `config.get_file_naming_grammar()` | `_resolve_grammar_from_merged_config()` |
| `config.get_device_type_grammar()` | `_resolve_grammar_from_merged_config()` |
| `config.get_protocol_grammar()` | `_resolve_grammar_from_merged_config()` |
| `project.get_current_project_path()` | `_config_patterns()`, `parse_filename_grammar()` |

All config access is guarded by `try/except ImportError` to allow technique.py
to function even when the full config system is unavailable.
