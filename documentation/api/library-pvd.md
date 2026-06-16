# API Reference — `science_cli.library.pvd`

Physical vapour deposition (PVD) run records, analysis, and YAML I/O.
Part of the `science-cli` electromechanical characterisation pipeline.

---

## Module layout

```
science_cli/library/pvd/
├── models.py       # DepositionLayer, DepositionRun dataclasses
├── analyze.py      # analyze_deposition(), deposition_summary()
├── yaml_io.py      # write_deposition_yaml(), read_deposition_yaml()
```

Analysis results are written via the shared `core/analysis_output.py`
writer (see [Cross-reference](#cross-reference)).

---

## `pvd/models.py` — Data models

### `DepositionLayer`

```python
@dataclass
class DepositionLayer:
    material: str
    thickness_nm: float
    rate_nm_s: float = 0.0
    temperature_c: float = 300.0
    pressure_mtorr: float = 5.0
```

A single layer in a PVD deposition stack.

| Field | Type | Default | Description |
|---|---|---|---|
| `material` | `str` | — | Material name (e.g. `"Ti"`, `"Pt"`, `"SiO2"`). |
| `thickness_nm` | `float` | — | Nominal thickness in nanometres. |
| `rate_nm_s` | `float` | `0.0` | Deposition rate (nm / s). |
| `temperature_c` | `float` | `300.0` | Substrate temperature (°C). |
| `pressure_mtorr` | `float` | `5.0` | Chamber pressure (mTorr). |

### `DepositionRun`

```python
@dataclass
class DepositionRun:
    name: str = ""
    technique: str = "pvd-deposition"
    instrument: str = "custom-pvd-system"
    protocol: str = ""
    step: str = ""
    layers: list = field(default_factory=list)
    total_thickness_nm: float = 0.0
    parameters: dict = field(default_factory=dict)
    notes: str = ""
    devices: str = ""
```

Complete record of one deposition run.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Human-readable run name. |
| `technique` | `str` | Technique slug (default `"pvd-deposition"`). Used as the filename stem by `write_deposition_yaml()`. |
| `instrument` | `str` | Instrument identifier. |
| `protocol` | `str` | Protocol name or path. |
| `step` | `str` | Step name within the protocol. |
| `layers` | `list[DepositionLayer]` | Ordered list of deposited layers. |
| `total_thickness_nm` | `float` | Pre-computed sum (nm). |
| `parameters` | `dict` | Arbitrary extra process parameters (temperature ramp, gas flow, …). |
| `notes` | `str` | Free-text notes. |
| `devices` | `str` | Device type string from the protocol YAML. |

---

## `pvd/analyze.py` — Analysis

### `analyze_deposition(layers)`

```python
def analyze_deposition(layers) -> dict
```

Compute summary statistics from a list of `DepositionLayer` objects.

| Key | Type | Description |
|---|---|---|
| `total_thickness_nm` | `float` | Sum of all layer thicknesses. |
| `n_layers` | `int` | Layer count. |
| `materials` | `list[str]` | Unique materials in order of first appearance. |
| `layer_stack` | `list[dict]` | Per-layer dicts: `material`, `thickness_nm`, `rate_nm_s`, `temperature_c`. |
| `mean_rate_nm_s` | `float` | Mean rate across layers with `rate_nm_s > 0`. |
| `rate_std_nm_s` | `float` | Standard deviation of those rates. |

Returns `{"error": …, "total_thickness_nm": 0.0}` if the layer list is empty.

### `deposition_summary(analysis)`

```python
def deposition_summary(analysis) -> str
```

Pretty-print the analysis dict as a human-readable block:

```
Deposition: 3 layers, 245.0 nm total
  Materials: Ti, Pt, Au
  Layer 1: Ti - 10.0 nm @ 0.05 nm/s
  Layer 2: Pt - 100.0 nm @ 0.12 nm/s
  Layer 3: Au - 135.0 nm @ 0.15 nm/s
```

Returns just the error message string if `analysis` contains `"error"`.

---

## `pvd/yaml_io.py` — YAML persistence

### `write_deposition_yaml(run, output_path)`

```python
def write_deposition_yaml(
    run: DepositionRun, output_path: Path
) -> Path
```

Serialises a `DepositionRun` to a YAML analysis file. Delegates to
`core/analysis_output.write_analysis_yaml()`.

The function builds a nested `analysis` dict with:

```yaml
analysis:
  total_thickness_nm: …
  materials: [Ti, Pt, Au]
  deposition_parameters:
    temperature_c: …
    rate_nm_s: …
  layer_stack:
    - material: Ti
      thickness_nm: 10.0
      rate_nm_s: 0.05
      temperature_c: 300.0
      pressure_mtorr: 5.0
parameters: {}
status: complete
```

**Path convention:** If `output_path` matches the pattern
`…/step_name/results/pvd-deposition_analysis.yaml`, then `step_dir` is
auto-detected as `<parent of results/>`, so `write_analysis_yaml` creates
the `results/` subdirectory and writes into it. Otherwise the parent of
`output_path` is used directly.

**Returns:** The absolute path of the written YAML file.

### `read_deposition_yaml(path)`

```python
def read_deposition_yaml(path: Path) -> dict | None
```

Simple deserialisation with `yaml.safe_load()`. Returns `None` if the file
does not exist.

---

## Cross-reference

### `science_cli.core.analysis_output`

Shared analysis YAML writer used by all technique modules
(PVD, IV-sweep, pulse-endurance, …).

```python
def write_analysis_yaml(
    technique: str,
    step_dir: Path,
    analysis_results: dict,
    instrument: str = "",
    devices: str = "",
) -> Path
```

Produces `<step_dir>/results/<technique>_analysis.yaml` with an envelope
containing `technique`, `instrument`, `devices`, and an ISO-8601 UTC
timestamp. Optionally validates `analysis_results` against a per-technique
schema registered in `science_cli.analysis.validators.SCHEMA_VALIDATORS`.

### Typical workflow

```
protocol/step_name/
├── results/
│   └── pvd-deposition_analysis.yaml   ← written by write_deposition_yaml()
└── pvd-deposition_data.yaml           ← optional raw data
```

---

## Usage example

```python
from pathlib import Path
from science_cli.library.pvd import (
    DepositionLayer,
    DepositionRun,
    analyze_deposition,
    deposition_summary,
    write_deposition_yaml,
)

# Build run record
run = DepositionRun(
    name="Ti-Pt-Au contacts",
    technique="pvd-deposition",
    instrument="AJA-ATC-2200",
    protocol="metal-contact",
    step="deposition-01",
    layers=[
        DepositionLayer("Ti", 10.0, rate_nm_s=0.05),
        DepositionLayer("Pt", 100.0, rate_nm_s=0.12),
        DepositionLayer("Au", 135.0, rate_nm_s=0.15),
    ],
)

run.total_thickness_nm = sum(l.thickness_nm for l in run.layers)

# Analyse
analysis = analyze_deposition(run.layers)
print(deposition_summary(analysis))

# Persist
write_deposition_yaml(run, Path("results/pvd-deposition_analysis.yaml"))
```
