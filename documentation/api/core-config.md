# Core Config API

**Module:** `science_cli.core.config` — science-cli v3.11.0

Device-aware configuration system that merges hardcoded defaults, global config,
and per-project overrides into a unified configuration dict. Provides typed
accessors for device loading parameters, technique detection, file naming grammar,
and device/technique registry lookups.

---

## Config Resolution Order

Config layers are merged left-to-right, **last writer wins** for leaf keys,
while nested dicts are deep-merged:

```
1. Hardcoded defaults    core/config.py:_DEFAULT_*
2. Global config         ~/.config/science-cli/config.yaml
3. Technique configs     ~/.config/science-cli/techniques/<name>.yaml
4. Per-project config    <project_root>/sci-config.yaml
```

The `get_merged_config()` function produces a single merged dict. Typed
accessors call `get_merged_config()` internally and extract the relevant
subsection.

An additional 5-tier chain exists for **file naming grammar** resolution
(see `get_merged_grammar()`):

```
1. Hardcoded grammar (HARDCODED_GRAMMAR in technique.py)
2. Device-type-specific grammar
3. Global config grammar patterns
4. Project-level grammar overrides
5. Protocol-level grammar
```

---

## Cache Internals

```python
# Global config — loaded once, invalidated when file mtime changes
_global_config: dict | None = None
_global_config_mtime: float = 0.0

# Per-project config — keyed by resolved project root path
_project_config_cache: dict[str, dict] = {}

# Technique configs — keyed by technique name, invalidated on summed mtime
_technique_configs_cache: dict[str, dict] | None = None
_technique_configs_mtime: float = 0.0
```

All caches are cleared by `invalidate_cache()`.

---

## File Path Helpers

```python
def _global_config_path() -> Path
```

Returns `~/.config/science-cli/config.yaml`.

---

```python
def _project_config_path(project_root: Path) -> Path
```

Returns `<project_root>/sci-config.yaml`.

**Parameters:**
- `project_root` — Resolved project root directory.

---

```python
def _technique_configs_dir() -> Path
```

Returns `~/.config/science-cli/techniques/`.

---

## Config Loading

```python
def _load_yaml(path: Path) -> dict
```

Load a YAML file, returning `{}` if it doesn't exist or is unreadable.
Silently catches `YAMLError` and `OSError`.

---

```python
def load_global_config() -> dict
```

Load the global config from `~/.config/science-cli/config.yaml`. Cached until
the file's `st_mtime` changes. Returns `{}` if the file doesn't exist.

---

```python
def load_project_config(project_root: Path) -> dict
```

Load per-project `sci-config.yaml`, cached by resolved project root path.
Returns `{}` if the file doesn't exist.

**Parameters:**
- `project_root` — Path to the project root directory.

---

```python
def load_technique_configs() -> dict[str, dict]
```

Load all per-technique YAML config files from
`~/.config/science-cli/techniques/*.yaml`. Returns a dict keyed by technique
name (stem of the filename). Cached until the sum of file mtimes changes.

**Note:** Per-technique YAML files are a legacy approach. All technique
settings now live in the global `config.yaml` or per-project `sci-config.yaml`.

---

```python
def invalidate_cache() -> None
```

Clear all config caches. Call after writing config files so subsequent reads
pick up the new values.

---

## Merged Access

```python
def _merge_dicts(base: dict, *overrides: dict) -> dict
```

Deep-merge dicts: later values win for leaf keys, nested dicts are merged
recursively. Overrides are applied in order.

**Parameters:**
- `base` — Base dict (copied, not mutated).
- `*overrides` — One or more override dicts.

---

```python
def get_merged_config(project_root: Path | None = None) -> dict
```

Return the fully merged configuration across all layers:

```
hardcoded defaults ← global config ← technique configs ← project config
```

**Parameters:**
- `project_root` — Optional project root. When `None`, only global defaults
  and global config are merged.

**Returns:** Merged dict with top-level keys `projects_root`, `techniques`,
`defaults`, `devices`, `file_naming`, `plot`, etc.

**Cross-references:**
- `science_cli.core.technique` module separates technique detection logic
  from config storage.
- `science_cli.core.routing` uses merged config for protocol routing.

---

## Typed Accessors

```python
def get_technique_patterns(
    technique: str,
    project_root: Path | None = None,
) -> list[str]
```

Return filename regex patterns for a technique. Config patterns are prepended
before hardcoded defaults so user-defined patterns match first.

**Parameters:**
- `technique` — Technique slug (e.g. `'iv-sweep'`, `'raman'`).
- `project_root` — Optional project root for project-level overrides.

**Returns:** List of regex pattern strings.

---

```python
def get_device_config(
    technique: str,
    device_name: str,
    project_root: Path | None = None,
) -> dict | None
```

Return device loading config merged with all defaults. The returned dict
always contains every key from `_DEFAULT_DEVICE` (delimiter, decimal,
header_lines, encoding, columns) filled in.

Resolution order:
1. Technique-specific device config (from merged config)
2. Hardcoded built-in device configs (`_DEFAULT_TECHNIQUE_DEVICES`)
3. Global device registry overrides (`config.yaml → devices:`)
4. Per-project `devices.yaml` overrides
5. `_DEFAULT_DEVICE` fallback for any missing keys

**Parameters:**
- `technique` — Technique slug.
- `device_name` — Device slug (e.g. `'keithley-2400'`).
- `project_root` — Optional project root.

**Returns:** Dict with `delimiter`, `decimal`, `header_lines`, `encoding`,
`columns`, or `None` if the device is not found in any layer.

**Cross-references:** Called by `science_cli.core.data_loader` to resolve
device parameters during file loading.

---

```python
def get_default_device(
    technique: str,
    project_root: Path | None = None,
) -> str
```

Return the preferred default device name for a technique, or `''` if none
configured.

Resolution order:
1. `defaults` section of merged config (project → global → hardcoded)
2. `default_device` field in `_DEFAULT_GLOBAL_TECHNIQUES`

---

```python
def get_device_config_detail(
    technique: str,
    device_name: str,
    project_root: Path | None = None,
) -> dict | None
```

Return the raw device config dict as specified in YAML or hardcoded defaults,
**without** `_DEFAULT_DEVICE` fallback filling. Use this when displaying
config to users so they see only what's actually configured.

---

```python
def get_technique_config(
    technique: str,
    project_root: Path | None = None,
) -> dict | None
```

Return the full technique config dict from merged config. Includes patterns,
devices, header_marker, and any other technique-level keys. Returns `None`
if the technique is not found.

---

```python
def get_projects_root() -> Path
```

Return the configured projects root directory path. Defaults to
`~/workspace/projects/active_projects`. Configurable via `projects_root` in
global or project config.

---

```python
def get_data_path(project_root: Path) -> Path
```

Return the data directory path for a project. Reads `data_path` from merged
config (default `'data/raw'`). Returns `<project_root>/<data_path>`.

---

```python
def get_header_marker(
    technique: str,
    project_root: Path | None = None,
) -> str
```

Return the header marker string for a technique (e.g. `'Frequency'`,
`'Voltage'`). Used to detect the data header row in measurement files.

---

```python
def get_plot_labels(
    technique: str,
    project_root: Path | None = None,
) -> dict[str, str]
```

Return per-technique plot labels from the `plot.labels.<technique>` section
of merged config. Returns `{}` if not configured.

Example config:
```yaml
plot:
  labels:
    uv-vis:
      xlabel: "Wavelength (nm)"
      ylabel: "Transmission (%)"
```

Resolution chain at runtime: `CLI --xlabel/--ylabel > config > column detection > template default`

---

```python
def get_file_naming_patterns(project_root: Path | None = None) -> list[dict]
```

Return file naming pattern configs from merged config. Each pattern dict has
keys: `template`, `description`, `regex`, `fields`. Falls back to `[]` if
no naming grammar configured.

---

```python
def get_file_naming_grammar(project_root: Path | None = None) -> dict
```

Return the file naming grammar configuration. Returns a dict with keys:
- `separator`: Always `"_"` — hardcoded, never configurable.
- `patterns`: List of pattern dicts from merged config.

Falls back to `{"separator": "_", "patterns": []}`.

---

## Global Device / Technique Registry

```python
def get_global_device_config(device_name: str) -> dict | None
```

Look up a device config from the global `devices:` registry. Resolution:
1. Start with hardcoded default (`_DEFAULT_GLOBAL_DEVICES`)
2. Overlay with global config `config.yaml → devices:`

Returns dict with `delimiter`, `decimal`, `header_lines`, `encoding`,
`columns` or `None`.

**Cross-references:** Called by `science_cli.core.data_loader` as a
secondary lookup when no technique-specific device config is found.

---

```python
def list_global_devices() -> list[str]
```

List all device names in the global registry. Combines hardcoded defaults
and global config. Returns sorted list.

---

```python
def get_device_types() -> list[str]
```

Return list of known protocol-level device type categories (determine
analysis mode — volatile, bipolar, linear, etc.). These are different from
hardware instrument models.

Returns hardcoded grammar keys plus `"pvd"`, `"electrochem"`, `"general"`.

**Cross-references:** Delegates to `science_cli.library.instruments.types`
for instrument type registration.

---

```python
def get_global_technique_config(technique_name: str) -> dict | None
```

Look up a technique config from the global technique registry. Resolution:
1. Start with hardcoded default (`_DEFAULT_GLOBAL_TECHNIQUES`)
2. Overlay with global config `config.yaml → techniques:`

Returns dict with keys: `label`, `grammar_codes`, `default_device`, `types`
or `None`.

---

```python
def list_global_techniques() -> list[str]
```

List all technique names in the global registry. Combines hardcoded
technique configs (`_DEFAULT_GLOBAL_TECHNIQUES`), pattern-based techniques
(`_DEFAULT_TECHNIQUE_PATTERNS`), and global config techniques. Returns
sorted list.

---

```python
def resolve_technique_from_grammar(
    grammar_code: str, project_root: Path | None = None
) -> str | None
```

Map a grammar code (e.g. `'iv'`, `'iv-sweep'`, `'iv_dc'`) to a technique
config key. Checks:
1. Global technique registry for `grammar_codes` match
2. Direct technique name match as fallback

Returns the technique key (e.g. `'iv-sweep'`) or `None`.

---

```python
def list_technique_names() -> list[str]
```

List all known technique names from all sources:
1. Technique config files (`~/.config/science-cli/techniques/*.yaml`)
2. Global config techniques section
3. Hardcoded defaults (`_DEFAULT_TECHNIQUE_PATTERNS`)

Returns sorted list.

---

```python
def list_technique_devices(technique: str) -> list[str]
```

List device names configured for a given technique across all layers:
1. Technique config files
2. Global config techniques
3. Hardcoded defaults (`_DEFAULT_TECHNIQUE_DEVICES`)

Returns sorted list.

---

## Instrument Lookups

```python
def get_instrument(name: str) -> dict | None
```

Look up an instrument model by name. Delegates to
`science_cli.library.instruments.registry.get_instrument()`.

**Parameters:**
- `name` — Instrument model name (e.g. `'keithley-2400'`).

**Returns:** Instrument dict with `label`, `manufacturer`, `type`,
`techniques`, `config`, or `None` if not found.

---

```python
def get_instruments_by_technique(technique: str) -> list[dict]
```

List instrument models compatible with a given technique. Delegates to
`science_cli.library.instruments.registry.get_instruments_by_technique()`.

**Parameters:**
- `technique` — Technique slug (e.g. `'iv-sweep'`).

**Returns:** Sorted list of instrument dicts.

---

## Grammar Accessors

```python
def get_device_type_grammar(device_type: str) -> list[dict]
```

Return the default grammar patterns for a given device type. Checks
hardcoded `_DEFAULT_DEVICE_TYPE_GRAMMAR` first, then allows overrides from
global config `file_naming.device_types.<type>`.

**Parameters:**
- `device_type` — Device type string (e.g. `'memristor'`, `'junction'`).

**Returns:** List of grammar pattern dicts, or `[]` if unknown.

---

```python
def get_device_type_grammar_config() -> dict[str, list[dict]]
```

Return the full device-type grammar config. Merges hardcoded defaults with
global config overrides.

**Returns:** Dict keyed by device type, each value is a list of grammar
pattern dicts.

---

```python
def get_protocol_grammar(protocol_yaml_path: Path) -> list[dict]
```

Read the `grammar:` section from a protocol YAML file. Delegates to
`science_cli.core.protocol.read_protocol_grammar()`.

**Parameters:**
- `protocol_yaml_path` — Path to the protocol YAML file.

**Returns:** List of grammar pattern dicts, or `[]`.

---

```python
def get_merged_grammar(
    project_root: Path | None = None,
    protocol_name: str | None = None,
    device_type: str | None = None,
) -> dict
```

Resolve file naming grammar via 5-tier resolution chain:

1. Hardcoded grammar (`HARDCODED_GRAMMAR` in `technique.py`)
2. Device-type-specific grammar (from `get_device_type_grammar()`)
3. Global config grammar patterns
4. Project-level grammar overrides
5. Protocol-level grammar (highest priority)

**Parameters:**
- `project_root` — Optional project root for project-level overrides.
- `protocol_name` — Optional protocol name for protocol-level grammar.
- `device_type` — Optional device type for type-specific grammar.

**Returns:** Merged grammar dict with `patterns` key.

**Cross-references:** Uses `science_cli.core.technique._merge_grammar()`
for pattern deduplication and `science_cli.core.technique.HARDCODED_GRAMMAR`
as the fallback base.

---

## Config Generation

```python
def generate_default_config_yaml() -> str
```

Generate a YAML string with all sections documented and commented. Used by
`sci config init` to create a starter config file at
`~/.config/science-cli/config.yaml`.

Includes: `projects_root`, `theme`, `default_dpi`, `figure_format`,
`file_naming` (device_types + patterns), device registry (`devices:`),
technique registry (`techniques:`), and default device assignments
(`defaults:`).

---

```python
def write_technique_config(technique: str, data: dict) -> Path
```

Write a technique config YAML file to
`~/.config/science-cli/techniques/<technique>.yaml`. Creates the directory
if it doesn't exist. Calls `invalidate_cache()` after writing.

**Parameters:**
- `technique` — Technique slug (used as filename stem).
- `data` — Dict to serialize as YAML.

**Returns:** `Path` to the written file.

---

## Hardcoded Defaults

```python
_DEFAULT_DEVICE: dict = {
    "delimiter": None,       # None = auto-detect
    "decimal": ".",
    "header_lines": 0,
    "encoding": "utf-8",
    "columns": {},
}
```

Fallback device config used when no device-specific config is found. Every
key is guaranteed present in `get_device_config()` return values.

---

```python
_DEFAULT_TECHNIQUE_PATTERNS: dict[str, list[str]]
```

Built-in filename regex patterns keyed by technique slug. 24 techniques
defined: `ec-cv`, `ec-ca`, `ec-eis`, `ec-lsv`, `ec-swv`, `iv-sweep`,
`iv-breakdown`, `iv-leakage`, `mem-endurance`, `mem-retention`,
`mem-switching`, `pulse-endurance`, `pulse-retention`, `pulse-switching`,
`pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd`,
`pulse-stp`, `pulse-ppf`, `raman`, `uv-vis`.

---

```python
_DEFAULT_PULSE_HEADER_LINES: int = 147
```

Shared constant used by both `pulse-stp` and `pulse-ppf` default device
configs for Keysight B1500A.

---

```python
_DEFAULT_TECHNIQUE_DEVICES: dict[str, dict[str, dict]]
```

Built-in per-technique device configs for: `iv-sweep` (keithley-2400,
keysight-b1500a), `raman` (horiba-usth), `uv-vis` (iop-hanoi),
`pulse-stp` (keysight-b1500a), `pulse-ppf` (keysight-b1500a).

---

```python
_DEFAULT_PROJECTS_ROOT: str
```

Default projects root: `~/workspace/projects/active_projects`.

---

```python
_DEFAULT_GLOBAL_DEVICES: dict[str, dict]
```

Built-in global device registry with: `keithley-2400` (Keithley 2400
SourceMeter), `keysight-b1500` (Keysight B1500A Semiconductor Analyzer),
`horiba-usth` (Horiba LabRAM HR Evolution).

---

```python
_DEFAULT_GLOBAL_TECHNIQUES: dict[str, dict]
```

Built-in global technique registry with 10 techniques. Each entry has
`label`, `grammar_codes`, `default_device`, and optionally `types`.

Techniques: `iv-sweep`, `iv-breakdown`, `iv-leakage`, `raman`, `uv-vis`,
`pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-stp`,
`pulse-ppf`.

---

```python
_DEFAULT_DEVICE_TYPE_GRAMMAR: dict[str, list[dict]]
```

Built-in device-type-specific grammar patterns for:
- `memristor` — Crossbar rNcN naming convention
- `junction` — Basic junction naming (no matrix coordinates)
- `deposition` — Basic deposition naming

Each grammar pattern has fields: `id`, `template`, `regex`, `fields`.

---

## Cross-References

| Module | Relationship |
|--------|-------------|
| `science_cli.core.technique` | Uses config accessors for technique detection; provides `HARDCODED_GRAMMAR` and `_merge_grammar()` back to config |
| `science_cli.core.data_loader` | Calls `get_device_config()` and `get_global_device_config()` to resolve loading parameters |
| `science_cli.core.project` | Uses `get_projects_root()` for project path resolution |
| `science_cli.core.protocol` | `get_protocol_grammar()` delegates to `read_protocol_grammar()` |
| `science_cli.core.routing` | Uses merged config for protocol routing decisions |
| `science_cli.library.instruments.registry` | Backend for `get_instrument()` and `get_instruments_by_technique()` |
| `science_cli.library.instruments.types` | Backend for `get_device_types()` |
