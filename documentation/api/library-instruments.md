# Instrument Library API

The instrument library provides a composable model/registry/type layer for
instrument metadata. It is consumed by both the TUI and the inference pipeline
(`science_cli/core/config.py` re-exports `get_instrument()` and
`get_instruments_by_technique()` as convenience wrappers).

---

## Models (`models.py`)

### `InstrumentConfig`

```python
@dataclass
class InstrumentConfig:
    delimiter: str = ","
    decimal: str = "."
    header_lines: int = 0
    encoding: str = "utf-8"
```

Describes how raw data files from an instrument are parsed.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `delimiter` | `str` | `","` | Column separator character |
| `decimal` | `str` | `"."` | Decimal point character |
| `header_lines` | `int` | `0` | Number of lines to skip before data |
| `encoding` | `str` | `"utf-8"` | File encoding (e.g. `"latin1"`) |

#### `InstrumentConfig.from_dict(d: dict) -> InstrumentConfig`
Classmethod. Constructs an `InstrumentConfig` from a dictionary, falling back
to defaults for missing keys via `dict.get()`.

#### `InstrumentConfig.to_dict() -> dict`
Serializes the instance to a plain `dict`.

---

### `Instrument`

```python
@dataclass
class Instrument:
    name: str
    label: str
    manufacturer: str
    type: str
    techniques: list[str] = field(default_factory=list)
    config: InstrumentConfig = field(default_factory=InstrumentConfig)
```

A logical instrument model — not a serial number, but a hardware *class*.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Canonical slug (e.g. `"keithley-2400"`) |
| `label` | `str` | Human-readable display name |
| `manufacturer` | `str` | Vendor string |
| `type` | `str` | Type slug (see `INSTRUMENT_TYPES` in `types.py`) |
| `techniques` | `list[str]` | Compatible technique slugs |
| `config` | `InstrumentConfig` | Per-instrument parse configuration |

#### `Instrument.from_dict(name: str, d: dict) -> Instrument`
Classmethod. Deserializes from a dict. `name` is supplied separately (it is
the dict key in the registry). Uses `dict.get()` with safe defaults.

#### `Instrument.to_dict() -> dict`
Serializes to a JSON/YAML-friendly dict. Techniques are sorted alphabetically.

---

## Registry (`registry.py`)

### `BUILTIN_INSTRUMENTS: dict[str, dict]`

Hardcoded catalog of known instrument models. Keys are canonical names,
values are raw dicts matching `Instrument.from_dict()` expectations.

| Key | Label | Type | Techniques |
|-----|-------|------|------------|
| `keithley-2400` | Keithley 2400 SourceMeter | `sourcemeter` | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance |
| `keysight-b1500a` | Keysight B1500A Semiconductor Parameter Analyzer | `parameter-analyzer` | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance, pulse-stp, pulse-ppf |
| `biologic` | Biologic SP-200 Potentiostat | `potentiostat` | ec-cv, ec-ca, ec-eis |
| `horiba-usth` | Horiba LabRAM HR Evolution (USTH) | `raman-spectrometer` | raman |
| `iop-hanoi` | UV-Vis Spectrometer (IOP Hanoi) | `uv-vis-spectrometer` | uv-vis |

### `_merged_instrument_registry() -> dict[str, dict]`

Merges `BUILTIN_INSTRUMENTS` with user overrides from the global config file
(`~/.config/science-cli/config.yaml` → `devices:` section, loaded via
`science_cli.core.config.load_global_config()`). User values are layered on
top of builtins via `dict.update()`. New instruments in global config that
don't exist in builtins are appended.

### `get_instrument(name: str) -> dict | None`

Look up a single instrument by canonical name. Returns a fully-formed
`Instrument.to_dict()` dict, or `None` if not found in merged registry.

### `get_all_instruments() -> list[dict]`

Returns all registered instruments (builtins + user overrides) as a list of
`Instrument.to_dict()` dicts, sorted by `label`.

### `get_instruments_by_technique(technique: str) -> list[dict]`

Filters the merged registry to instruments whose `techniques` list includes
the given `technique` slug. Returns sorted by `label`.

### `get_instrument_techniques(name: str) -> list[str]`

Returns the list of compatible technique slugs for a named instrument, or
empty list if the instrument is not found. Reads raw `techniques` from the
merged registry dict (no `Instrument` object construction).

### `register_instrument(name: str, data: dict) -> bool`

Creates a new instrument in the global config file. Writes the `data` dict
to `config.yaml` → `devices:` → `name`. Creates the config file/parent
directories if they don't exist. Calls `invalidate_cache()` after write.
Returns `True`.

Internally uses `science_cli.core.config._global_config_path()` and `yaml`.

### `remove_instrument(name: str) -> bool`

Removes an instrument from the global config file. Returns `False` if the
config file doesn't exist or the instrument name is not found in the
`devices:` section. Calls `invalidate_cache()` on success. Returns `True`.

### `edit_instrument(name: str, data: dict) -> bool`

Updates an existing instrument in the global config file via `dict.update()`.
Returns `False` if the config file doesn't exist or the instrument is not
found. Returns `True` on success. Calls `invalidate_cache()`.

---

## Types (`types.py`)

### `INSTRUMENT_TYPES: dict[str, str]`

Mapping of type slugs to human-readable descriptions:

| Slug | Description |
|------|-------------|
| `sourcemeter` | SourceMeter (SMU) |
| `parameter-analyzer` | Semiconductor Parameter Analyzer |
| `potentiostat` | Potentiostat / Galvanostat |
| `lcr-meter` | LCR Meter |
| `raman-spectrometer` | Raman Spectrometer |
| `uv-vis-spectrometer` | UV-Vis Spectrometer |
| `afm` | Atomic Force Microscope |
| `pvd-system` | PVD Deposition System |
| `probe-station` | Probe Station |
| `function-generator` | Function / Pulse Generator |
| `oscilloscope` | Oscilloscope |
| `unknown` | Unknown Instrument Type |

### `describe_type(t: str) -> str`

Returns the human-readable description for a type slug. Falls back to
`f"Custom: {t}"` if the slug is not in `INSTRUMENT_TYPES`.

### `list_types() -> list[str]`

Returns sorted list of all known type slugs (`INSTRUMENT_TYPES.keys()`).

### `MANUFACTURERS: set[str]`

Set of known manufacturer names used for autocomplete and validation:

```
Keithley/Tektronix, Keysight, BioLogic, Horiba, Bruker,
Oxford Instruments, Lake Shore, National Instruments,
Stanford Research, Rohde & Schwarz
```

---

## Cross-References

- `science_cli/core/config.py` re-exports `get_instrument()` and
  `get_instruments_by_technique()` at module level for convenience.
- `science_cli/core/config.py:load_global_config()` — loads the YAML file
  that `registry.py` reads for user overrides.
- `science_cli/core/config.py:invalidate_cache()` — called by the CRUD
  functions after every write to ensure subsequent reads pick up changes.
- `science_cli/library/instruments/types.py:list_types()` is also called by
  `science_cli/core/config.py:get_device_types()`.
