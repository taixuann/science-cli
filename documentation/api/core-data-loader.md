# `data_loader` — Experimental Data File Loading

**Module:** `science_cli.core.data_loader`  
**Since:** science-cli v3.0+  
**Relevant config:** `science_cli.core.config` (device config, technique patterns, global/project YAML merging)

Device-aware loader that reads experimental data files into pandas DataFrames with structured metadata. Supports four levels of resolution for loading parameters (in descending priority):

1. **Per-technique device config** — `techniques.<technique>.devices.<device>` from YAML
2. **Global device registry** — `devices.<device>` from YAML
3. **Auto-detection** — extension-based fallback when no device config is available
4. **Hardcoded defaults** — comma-delimiter, UTF-8, no header skipping

---

## Main Entry Point

### `load_data_file()`

```python
def load_data_file(
    filepath: str,
    technique: str = "",
    device: str = "",
) -> tuple[pd.DataFrame, dict]:
```

The single entry point for all data loading. Two modes of operation:

**Device-aware mode** (`technique` + `device` both non-empty): resolves device config via `_resolve_device_config()` and delegates to `_load_with_device_config()`. This path applies column remapping, delimiter/decimal/encoding overrides, Keysight B1500A filtering, and Raman header extraction.

**Auto-detection mode** (no technique/device): falls back to extension-based dispatch — `.mpt` → `_load_mpt()`, `.csv` → `_load_csv()`, `.txt` → `_load_txt()`, `.xlsx` → `_load_excel()`.

**Returns:**

| Field | Description |
|---|---|
| `format` | File extension without leading dot (e.g. `"csv"`, `"mpt"`) |
| `columns` | List of column names after any remapping |
| `path` | Absolute string path to the source file |
| `device` | *(only in device-aware mode)* Device slug used |
| `technique` | *(only in device-aware mode)* Technique slug used |
| `raman_metadata` | *(Raman only)* Dict from header parsing, see `extract_raman_metadata()` |

**Raises:** `FileNotFoundError` if `filepath` does not exist.

```python
# Device-aware — applies Keithley 2400 config for IV sweep
df, meta = load_data_file("data/iv_sweep.csv", technique="iv-sweep", device="keithley-2400")
meta["device"]   # "keithley-2400"
meta["columns"]  # ["voltage", "current"] — remapped from device config

# Auto-detection — loads as CSV with pandas defaults
df, meta = load_data_file("data/raw.csv")
meta["format"]  # "csv"
```

---

## Config Resolution

### `_resolve_device_config()`

```python
def _resolve_device_config(technique: str, device: str) -> dict | None:
```

Private resolver that implements the 3-layer lookup. Called by `load_data_file()`.

**Resolution order:**

1. `get_device_config(technique, device, project_root)` — per-technique device config from `sci-config.yaml` or global `config.yaml`
2. `get_global_device_config(device)` — top-level `devices.<device>` registry
3. Returns `None` (caller falls through to extension-based auto-detection)

Both accessors are defined in [`science_cli.core.config`](core-config.md) and merge hardcoded defaults with YAML overrides.

```python
# Typical resolved config dict:
{
    "delimiter": "\t",
    "decimal": ",",
    "header_lines": 1,
    "encoding": "latin1",
    "columns": {"voltage": "V", "current": "I"},
    "names": None,
}
```

Returns `None` if no config is found for the given technique+device pair — the caller then falls through to extension-based auto-detection.

### `_load_with_device_config()`

```python
def _load_with_device_config(
    path: Path,
    device_cfg: dict,
    technique: str,
    device: str,
) -> tuple[pd.DataFrame, dict]:
```

Core device-aware loader. Applies every parameter from `device_cfg` to `pd.read_csv()`.

**Parameter resolution from `device_cfg`:**

| Key | Default | Effect |
|---|---|---|
| `delimiter` | Auto-detect | Tab → semicolon → comma → whitespace |
| `decimal` | `"."` | Passed as `decimal=` to `pd.read_csv()` |
| `header_lines` | `0` | `skiprows=` before the data header |
| `encoding` | `"utf-8"` | File encoding |
| `columns` | `{}` | Dict mapping canonical role names → actual column names in file (see remapping below) |
| `names` | `None` | If set, forces `header=None` and uses these as explicit column names (headerless files) |

**Delimiter auto-detection:** when `delimiter` is `None`, reads the first line of the file and picks `\t` → `;` → `,` in that order. Falls back to `r"\s+"` (any whitespace) as last resort.

**Column remapping:** the `columns` dict maps canonical names (e.g. `"voltage"`, `"current"`, `"frequency"`) to the actual column headers in the raw file. Columns that match are renamed in-place; unmatched columns are left as-is. A column that already maps to a different role is skipped to prevent duplicates.

```yaml
# sci-config.yaml example:
techniques:
  iv-sweep:
    devices:
      keithley-2400:
        delimiter: "\t"
        header_lines: 1
        columns:
          voltage: "V_sweep"
          current: "I_meas"
```

**Keysight B1500A filtering:** if the DataFrame contains a `"DataName"` column, only rows where `DataName == "DataValue"` are kept (stripping `"SetupTitle"`, `"SetupParam"`, etc. rows), and the column is dropped afterward.

**Raman metadata:** when `technique == "raman"`, `_extract_raman_header_metadata(path)` is called and the result stored under `meta["raman_metadata"]`.

---

## Extension-Based Loaders (Fallback)

### `_load_mpt()`

```python
def _load_mpt(path: Path) -> tuple[pd.DataFrame, dict]:
```

Legacy loader for BioLogic `.mpt` files. Scans for a header row starting with `"Frequency"` or `"f/Hz"`, skips all preceding lines, then reads tab-delimited data with `latin1` encoding.

```python
df, meta = _load_mpt(Path("eis_measurement.mpt"))
meta["format"]  # "mpt"
```

### `_load_csv()`

```python
def _load_csv(path: Path) -> tuple[pd.DataFrame, dict]:
```

Straight `pd.read_csv()` with no special handling. Numeric columns are coerced via `pd.to_numeric()`.

### `_load_txt()`

```python
def _load_txt(path: Path) -> tuple[pd.DataFrame, dict]:
```

Delimiter auto-detection (same logic as `_load_with_device_config()`: tab → semicolon → comma → whitespace). Lines starting with `#` are treated as comments and skipped. Column headers are stripped of surrounding quotes.

### `_load_excel()`

```python
def _load_excel(path: Path) -> tuple[pd.DataFrame, dict]:
```

Delegates to `pd.read_excel()` with default arguments. Returns minimal metadata.

---

## Curve Fitting

### `fit_file()`

```python
def fit_file(
    filepath: str,
    model: str = "linear",
    xcol: str = "",
    ycol: str = "",
) -> lmfit.model.ModelResult | None:
```

Loads a data file via `load_data_file()` and fits a curve using `lmfit.Model`. Prints the fit report to stdout and returns the `ModelResult` object.

**Supported models:**

| `model` | Function | Parameters |
|---|---|---|
| `"linear"` | `y = slope * x + intercept` | `slope`, `intercept` |
| `"exponential"` | `y = a * exp(-b * x) + c` | `a`, `b`, `c` |
| `"power"` | `y = a * x ** b` | `a`, `b` |
| *(anything else)* | `y = a * x + b` | `a`, `b` |

If `xcol` / `ycol` are empty, uses the first and second DataFrame columns respectively. NaN values are masked out before fitting.

```python
# Linear fit using columns "V" and "I"
result = fit_file("iv_data.csv", model="linear", xcol="V", ycol="I")
result.params["slope"].value  # 0.0023
```

---

## Raman Metadata Extraction

### `extract_raman_metadata()`

```python
def extract_raman_metadata(filepath: str | Path) -> dict:
```

Parses the `#`-prefixed header block from Horiba LabRAM `.txt` / `.asc` files. Each header line is expected as `# key = value`. Keys are normalized:

- Lowercased
- Spaces → underscores
- `.` → stripped
- `()` → stripped
- `/` → `_per_`

**Normalized key examples:**

| Raw header | Normalized key |
|---|---|
| `# Laser Wavelength (nm) = 532.0` | `laser_wavelength_nm` |
| `# Grating (gr/mm) = 1800` | `grating_gr_per_mm` |
| `# Acquisition Time (s) = 10.0` | `acquisition_time_s` |
| `# Accumulations = 3` | `accumulations` |

```python
meta = extract_raman_metadata("raman_spectrum.txt")
meta["laser_wavelength_nm"]  # "532.0"
meta["grating_gr_per_mm"]    # "1800"
```

### `_extract_raman_header_metadata()`

```python
_extract_raman_header_metadata = extract_raman_metadata
```

Re-exported alias for internal use. Both names refer to the same function.

---

## Metadata Dict Reference

Every loader returns a `dict` with the following structure:

```python
{
    "format": "csv",              # file extension without dot
    "columns": ["V", "I", "t"],   # final column names after any remapping
    "path": "/data/sweep.csv",    # absolute path to source file

    # Present only when technique + device were provided:
    "device": "keithley-2400",
    "technique": "iv-sweep",

    # Present only for Raman technique:
    "raman_metadata": {
        "laser_wavelength_nm": "532.0",
        "grating_gr_per_mm": "1800",
    },
}
```

---

## Cross-References

- **`science_cli.core.config`** — `get_device_config()`, `get_global_device_config()`, `_DEFAULT_DEVICE`, YAML merging logic
- **`science_cli.core.project`** — `get_current_project_path()` used to locate per-project `sci-config.yaml`
- **`science_cli.core.technique`** — technique detection patterns that pair with device config
