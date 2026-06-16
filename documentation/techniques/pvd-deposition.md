# PVD Deposition — Physical Vapor Deposition Records

## Overview

Physical vapor deposition (PVD) is a family of vacuum-based thin-film coating
techniques where solid source material is physically vaporised and transported
through low-pressure gas or vacuum to condense on a substrate. PVD is the
primary deposition method for microelectronic and memristive thin-film devices
because it offers precise thickness control, high film purity, and broad
material compatibility.

science-cli models PVD deposition as a multi-layer stack with per-layer
parameters (material, thickness, deposition rate, temperature, pressure) and
top-level run metadata (instrument, protocol, step, notes). The system supports
recording individual layers, computing total thickness, analyzing deposition
statistics, and serialising the record to YAML for integration with the
science-cli analysis pipeline.

### Technique Registration

The `pvd-deposition` technique slug is registered in the science-cli taxonomy
and is identified by the `deposition` or `pvd` device type, which routes to
`linear` analysis mode. Deposition records are managed exclusively through the
`sci pvd` CLI command group.

### Common PVD Methods

**Sputtering** — The most widely used method. A plasma (typically Ar at
1–10 mTorr) bombards a target, ejecting atoms that condense on the substrate.
DC sputtering for conductive targets; RF sputtering (13.56 MHz) for insulators
(HfO₂, Al₂O₃, SiO₂). Reactive sputtering introduces O₂ or N₂ for oxide/nitride
deposition from elemental targets. Typical rates: 0.1–10 Å/s.

**Thermal evaporation** — Source material is resistively heated in a boat or
filament. Line-of-sight transport in high vacuum (10⁻⁶–10⁻⁵ Torr). Simple,
high rate (>10 Å/s), but poor step coverage and lower film density than
sputtered films.

**Electron-beam evaporation** — A focused electron beam (5–20 kV) heats the
source locally in a water-cooled crucible. Can evaporate refractory metals
(W, Mo, Ta) and oxides. Closed-loop QCM rate control at 0.1–10 Å/s.

---

## Layer Stack Modeling

Deposition is modelled as a sequence of `DepositionLayer` objects arranged
bottom-to-top (first deposited to last deposited), wrapped in a
`DepositionRun` dataclass.

### DepositionLayer

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `material` | str | Target material (e.g., `Ti`, `Pt`, `HfO₂`) | (required) |
| `thickness_nm` | float | Nominal or measured thickness (nm) | (required) |
| `rate_nm_s` | float | Deposition rate (nm/s) | 0.0 |
| `temperature_c` | float | Substrate temperature (°C) | 300.0 |
| `pressure_mtorr` | float | Chamber pressure (mTorr) | 5.0 |

### DepositionRun

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `name` | str | Human-readable run name | `""` |
| `technique` | str | Technique slug | `"pvd-deposition"` |
| `instrument` | str | Tool identifier | `"custom-pvd-system"` |
| `protocol` | str | Protocol YAML path | `""` |
| `step` | str | Step within protocol | `""` |
| `layers` | list[DepositionLayer] | Ordered layers (bottom first) | `[]` |
| `total_thickness_nm` | float | Sum of layer thicknesses | 0.0 |
| `parameters` | dict | Free-form key-value store | `{}` |
| `notes` | str | Free-text notes | `""` |
| `devices` | str | Device type | `""` |

### Layer Ordering Convention

Layer stacks are stored bottom-to-top, matching the physical deposition
sequence. A typical Ti/Pt/HfO₂/Ti/Au memristor stack:

1. Ti (adhesion, 5 nm) — deposited first, on the substrate
2. Pt (bottom electrode, 50 nm)
3. HfO₂ (switching layer, 10 nm)
4. Ti (top electrode adhesion, 5 nm)
5. Au (top electrode, 50 nm) — deposited last

The substrate itself is not a layer — it is recorded in
`parameters["substrate"]` or the protocol YAML.

### Analysis Functions

`analyze_deposition(layers)` computes:

```python
total_thickness = sum(l.thickness_nm for l in layers)
materials = list(dict.fromkeys([l.material for l in layers]))
rates = [l.rate_nm_s for l in layers if l.rate_nm_s > 0]
```

Returns `total_thickness_nm`, `n_layers`, `materials` (ordered unique), per-layer
`layer_stack` dicts, and optionally `mean_rate_nm_s` and `rate_std_nm_s` when
non-zero rates exist. Returns `{"error": ..., "total_thickness_nm": 0.0}` for
empty layer lists.

---

## Deposition Parameters

The following parameters are the most commonly tracked variables for PVD
process monitoring:

### Substrate Temperature

Determines adatom mobility, film density, and crystallinity.

- **Room temperature (20–30 °C)** — Standard for memristor stacks where
  interdiffusion and crystallisation must be minimised.
- **Moderate (100–400 °C)** — Used for crystallisation of switching layers
  (e.g., monoclinic HfO₂ at ~300 °C) or improved film density.
- **High (>500 °C)** — Epitaxial growth (PLD), rarely used in standard PVD
  memristor stacks.

### Chamber Pressure

Base pressure (10⁻⁷–10⁻⁶ Torr) determines background contamination. Process
pressure affects mean free path and film stress.

- **Sputtering (1–10 mTorr)** — Lower pressure (<3 mTorr) gives higher energy
  and density but lower rate. Higher pressure (>5 mTorr) thermalises flux,
  reducing stress but increasing gas incorporation.
- **Evaporation (10⁻⁶–10⁻⁵ Torr)** — High vacuum maintains line-of-sight
  transport. Scattering at higher pressures degrades uniformity.

### Deposition Rate

Controls film microstructure and thickness precision. Measured in-situ by QCM.

- **Low (<0.5 Å/s)** — Smooth, dense films for thin layers (<10 nm). Risk of
  oxygen scavenging in reactive processes.
- **Moderate (0.5–2 Å/s)** — Standard for most PVD processes, balancing
  throughput and quality.
- **High (>2 Å/s)** — Thick films (>100 nm). May introduce pinholes or
  increased roughness.

The rate is not computed from power/temperature — it is entered as the
measured or target QCM rate.

### Pre-Deposition Treatment

Substrate preparation is critical for adhesion and yield:

- **Ar plasma clean** — In-situ reverse-sputter etch, 1–5 min at 10–50 W RF.
- **Solvent clean** — Acetone/isopropanol/DI water (ex-situ).
- **O₂ plasma clean** — Organic residue removal (ex-situ or in-situ).
- **Thermal outgassing** — Vacuum bake at 100–200 °C.

---

## CLI Commands

The `sci pvd` command group provides five subcommands. Commands marked (stub)
print a placeholder — argument interfaces are defined but handlers are not yet
fully wired.

### sci pvd ls

List PVD deposition records in the current step directory.

```bash
sci pvd ls
```

Currently a stub.

### sci pvd info [name]

Show detailed deposition information for a named record.

```bash
sci pvd info
sci pvd info hfo2_memristor_stack
```

If no name is provided, uses the first deposition record found. Displays the
full layer stack, total thickness, and parameters. Currently a stub.

### sci pvd add

Add a new deposition record with interactive field entry.

```bash
sci pvd add
```

Prompts for run name, instrument, layers (material, thickness, rate,
temperature, pressure), substrate, target purity, pre-treatment, and notes.
Currently a stub.

### sci pvd edit <name>

Edit an existing deposition record.

```bash
sci pvd edit hfo2_memristor_stack
```

Opens `$EDITOR` or falls back to interactive prompts. Currently a stub.

### sci pvd analyze [name]

Analyze deposition data and produce YAML output.

```bash
sci pvd analyze
sci pvd analyze hfo2_memristor_stack
```

Runs `analyze_deposition()` on the layer stack. Results are written to
`<step_dir>/results/pvd-deposition_analysis.yaml`. Currently a stub.

---

## Analysis Pipeline

```
DepositionRun
    │
    ▼
1. Layer stack extraction from run.layers
    │
    ▼
2. Total thickness: sum(l.thickness_nm)
    │
    ▼
3. Material inventory: dict.fromkeys([l.material ...])
    │
    ▼
4. Rate statistics: numpy.mean/std of non-zero rates
    │
    ▼
5. Layer stack serialisation per-layer dict
    │
    ▼
6. YAML assembly (yaml_io.py → write_deposition_yaml)
   ├─ Envelope: technique, instrument, devices, timestamp
   ├─ Analysis: layer_stack, deposition_parameters
   ├─ Parameters: run-level free-form dict
   └─ Status: "complete"
    │
    ▼
7. Schema validation (validators.py → validate_pvd_schema)
   ├─ "analysis" key must exist
   └─ "thickness_nm" or "total_thickness_nm" must be present
    │
    ▼
8. Write: results/pvd-deposition_analysis.yaml
```

---

## YAML Schema

Output structure produced by `write_deposition_yaml()`:

```yaml
technique: pvd-deposition
instrument: AJA-ATC
devices: deposition
timestamp: "2026-06-15T12:00:00Z"

analysis:
  total_thickness_nm: 120.0
  materials:
    - Ti
    - Pt
    - HfO2
    - Au
  deposition_parameters:
    temperature_c: 300.0
    rate_nm_s: 0.5
  layer_stack:
    - material: Ti
      thickness_nm: 5.0
      rate_nm_s: 0.3
      temperature_c: 300.0
      pressure_mtorr: 5.0
    - material: Pt
      thickness_nm: 50.0
      rate_nm_s: 0.8
      temperature_c: 300.0
      pressure_mtorr: 5.0
    - material: HfO2
      thickness_nm: 10.0
      rate_nm_s: 0.2
      temperature_c: 300.0
      pressure_mtorr: 3.0
    - material: Ti
      thickness_nm: 5.0
      rate_nm_s: 0.3
      temperature_c: 300.0
      pressure_mtorr: 5.0
    - material: Au
      thickness_nm: 50.0
      rate_nm_s: 1.0
      temperature_c: 300.0
      pressure_mtorr: 5.0

parameters:
  substrate: Si / 300 nm SiO2
  target: Ti (99.995%), Pt (99.99%), HfO2 (99.9%), Au (99.99%)
  base_pressure_torr: 5.0e-7
  pre_deposition_treatment: Ar plasma clean 3 min at 20 W
  deposition_method: DC sputtering (Ti, Pt, Au) / RF sputtering (HfO2)
  ar_flow_sccm: 20.0
  o2_flow_sccm: 0.0
  notes: Standard memristor stack for forming-free switching study

status: complete
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `technique` | string | Always `pvd-deposition` |
| `instrument` | string | Deposition tool identifier |
| `devices` | string | Device type: `deposition` or `pvd` |
| `analysis.total_thickness_nm` | float | Sum of layer thicknesses (nm) |
| `analysis.materials` | [string] | Ordered unique materials |
| `analysis.deposition_parameters` | dict | First-layer temperature and rate |
| `analysis.layer_stack[]` | list | Ordered layers (bottom to top) |
| `parameters` | dict | Free-form run-level parameters |
| `status` | string | Always `complete` |

### Schema Validation

```python
@register("pvd-deposition")
def validate_pvd_schema(results):
    if "analysis" not in results:
        raise ValueError("PVD deposition results must contain 'analysis' key")
    analysis = results["analysis"]
    if "thickness_nm" not in analysis and "total_thickness_nm" not in analysis:
        raise ValueError("PVD analysis must include thickness_nm or total_thickness_nm")
    return results
```

Validation runs inside `write_analysis_yaml()`. The YAML file is not written if
validation fails — a `ValueError` is raised to the caller.

---

## Examples

### CLI workflow

```bash
sci pvd add
sci pvd ls
sci pvd info hfo2_memristor_stack
sci pvd analyze hfo2_memristor_stack
```

### Programmatic usage

```python
from pathlib import Path
from science_cli.library.pvd import DepositionLayer, DepositionRun, analyze_deposition, write_deposition_yaml

layers = [
    DepositionLayer("Ti", 5.0, rate_nm_s=0.3, temperature_c=300.0, pressure_mtorr=5.0),
    DepositionLayer("Pt", 50.0, rate_nm_s=0.8, temperature_c=300.0, pressure_mtorr=5.0),
    DepositionLayer("HfO2", 10.0, rate_nm_s=0.2, temperature_c=300.0, pressure_mtorr=3.0),
    DepositionLayer("Ti", 5.0, rate_nm_s=0.3, temperature_c=300.0, pressure_mtorr=5.0),
    DepositionLayer("Au", 50.0, rate_nm_s=1.0, temperature_c=300.0, pressure_mtorr=5.0),
]

run = DepositionRun(
    name="hfo2_memristor_stack_v2",
    instrument="AJA-ATC",
    layers=layers,
    total_thickness_nm=sum(l.thickness_nm for l in layers),
    parameters={
        "substrate": "Si / 300 nm SiO2",
        "base_pressure_torr": 5.0e-7,
        "pre_deposition_treatment": "Ar plasma clean 3 min at 20 W",
        "deposition_method": "DC sputtering (Ti, Pt, Au) / RF sputtering (HfO2)",
        "ar_flow_sccm": 20.0,
    },
    notes="Standard memristor stack for forming-free switching study",
)

analysis = analyze_deposition(layers)
print(f"Total thickness: {analysis['total_thickness_nm']:.1f} nm")
print(f"Mean rate: {analysis.get('mean_rate_nm_s', 0):.2f} nm/s")

path = Path("protocol/memristor_fabrication/results/pvd-deposition_analysis.yaml")
write_deposition_yaml(run, path)
```

### Reading YAML analysis

```python
from pathlib import Path
from science_cli.library.pvd import read_deposition_yaml

data = read_deposition_yaml(Path("results/pvd-deposition_analysis.yaml"))
for layer in data.get("analysis", {}).get("layer_stack", []):
    print(f"  {layer['material']}: {layer['thickness_nm']} nm @ {layer['rate_nm_s']} nm/s")
```

---

## Source Code Reference

| Module | Key Functions / Classes |
|--------|------------------------|
| `library/pvd/models.py` | `DepositionLayer`, `DepositionRun` |
| `library/pvd/analyze.py` | `analyze_deposition()`, `deposition_summary()` |
| `library/pvd/yaml_io.py` | `write_deposition_yaml()`, `read_deposition_yaml()` |
| `library/pvd/device_cli.py` | `build_pvd_parser()`, `cmd_ls`, `cmd_info`, `cmd_add`, `cmd_edit`, `cmd_analyze` |
| `library/pvd/__init__.py` | Public API exports |
| `cli/commands/pvd.py` | `pvd_handler()` — subcommand routing |
| `core/analysis_output.py` | `write_analysis_yaml()` — shared YAML writer |
| `analysis/validators.py` | `validate_pvd_schema()` — registered for `pvd-deposition` |

---

## See Also

- `overview.md` — technique taxonomy: deposition category, detection patterns, device type routing
- `schemas/analysis-yaml.md` — full schema specification for all analysis YAML files
- `reference/config-system.md` — 4-tier configuration inheritance for device definitions
