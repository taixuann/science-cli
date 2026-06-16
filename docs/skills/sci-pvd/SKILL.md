---
name: sci-pvd
description: "Physical vapor deposition record management — multi-layer stack modeling, deposition parameter tracking (temperature/pressure/rate/time), CRUD operations for deposition records, thickness analysis and statistics. Load when managing PVD deposition records, tracking thin-film fabrication parameters, or analyzing deposition layer stacks."
version: 3.11.0
author: science-cli team
knowledge_type: technique
techniques: [pvd-deposition]
---

# sci-pvd — PVD Deposition Skill

## Overview

`sci pvd` provides CRUD operations and analysis for physical vapor deposition (PVD) records. It models deposition as a multi-layer stack with per-layer parameters (material, thickness, deposition rate, temperature, pressure) and top-level run metadata (instrument, protocol, step, notes). Supports recording individual layers, computing total thickness, analyzing deposition statistics, and YAML serialization.

### Common PVD Methods

| Method | Typical Rate | Pressure | Best For |
|--------|-------------|----------|----------|
| DC Sputtering | 0.1–10 Å/s | 1–10 mTorr | Conductive targets (metals) |
| RF Sputtering | 0.1–5 Å/s | 1–10 mTorr | Insulators (HfO₂, Al₂O₃, SiO₂) |
| Thermal Evaporation | >10 Å/s | 10⁻⁶–10⁻⁵ Torr | Simple metals, organics |
| E-beam Evaporation | 0.1–10 Å/s | 10⁻⁶–10⁻⁵ Torr | Refractory metals, oxides |

## CLI Reference

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `sci pvd ls` | List PVD deposition steps in current project |
| `sci pvd info` | Show deposition details and metadata |
| `sci pvd add` | Add a deposition record (interactive) |
| `sci pvd edit` | Edit a deposition record (interactive) |
| `sci pvd analyze` | Analyze deposition data |

### Subcommand Details

**`ls`** — Lists deposition steps showing: step name, technique (sputtering/evaporation), layer count, total thickness, rate file count.

**`info`** — Displays: layer materials, target thickness, deposition rate, temperature, pressure, power, instrument, timestamps, operator.

**`add`** — Interactive wizard for: material name, target thickness (nm), deposition rate (Å/s), temperature (°C), pressure (Torr/mbar), RF/DC power (W), instrument name.

**`edit`** — Interactive editor showing current values as defaults; pressing Enter keeps existing value.

**`analyze`** — Computes: average deposition rate (linear fit), rate standard deviation, total thickness, thickness uniformity, deposition time, rate stability index (CV = σ/μ).

## Layer Stack Modeling

### Data Model

**DepositionLayer** fields: material (str), thickness_nm (float), rate_nm_s (float), temperature_c (float), pressure_mtorr (float).

**DepositionRun** fields: name, technique, instrument, protocol, step, layers (ordered bottom→top), total_thickness_nm, parameters (dict), notes.

### Layer Ordering Convention

Stacks are stored bottom-to-top (first deposited to last). Example Ti/Pt/HfO₂/Ti/Au memristor stack:

1. Ti (adhesion, 5 nm) — on substrate
2. Pt (bottom electrode, 50 nm)
3. HfO₂ (switching layer, 10 nm)
4. Ti (top electrode adhesion, 5 nm)
5. Au (top electrode, 50 nm)

### Deposition Parameters

| Parameter | Typical Range | Impact |
|-----------|---------------|--------|
| Substrate temp | RT–400 °C | Adatom mobility, film density, crystallinity |
| Process pressure | 1–10 mTorr (sputter), 10⁻⁶–10⁻⁵ Torr (evap) | Mean free path, film stress |
| Deposition rate | 0.1–10 Å/s | Microstructure, thickness precision |
| RF/DC power | 20–300 W | Sputter yield, deposition rate |

## File Structure

```
protocol/1_pvd-deposition/
  ├── 1_pvd-deposition.yaml      # Protocol step YAML
  ├── pvd-layer/                  # Layer CSV files
  │   └── 260526_Ta_PDA_ITO_dep_01.csv
  └── pvd-rate/                   # Rate measurement files
      └── 260526_Ta_rate_01.csv
```

## YAML Schema

```yaml
technique: pvd-deposition
instrument: AJA-ATC
devices: deposition
analysis:
  total_thickness_nm: 120.0
  materials: [Ti, Pt, HfO2, Au]
  deposition_parameters:
    temperature_c: 300.0
    rate_nm_s: 0.5
  layer_stack:
    - material: Ti; thickness_nm: 5.0; rate_nm_s: 0.3
    - material: Pt; thickness_nm: 50.0; rate_nm_s: 0.8
    - material: HfO2; thickness_nm: 10.0; rate_nm_s: 0.2
    - material: Ti; thickness_nm: 5.0; rate_nm_s: 0.3
    - material: Au; thickness_nm: 50.0; rate_nm_s: 1.0
parameters:
  substrate: Si / 300 nm SiO2
  base_pressure_torr: 5.0e-7
  pre_deposition_treatment: Ar plasma clean 3 min at 20 W
status: complete
```

## AI Agent Usage

### PVD workflow
1. Open project: `sci open -m project <name>`
2. List deposition steps: `sci pvd ls`
3. Add record after deposition: `sci pvd add` (interactive)
4. Inspect records: `sci pvd info`
5. Analyze: `sci pvd analyze` — computes rate, uniformity, total thickness
6. Edit if needed: `sci pvd edit`

### Tips for AI agents
- **Multi-layer stacks**: Always specify layers bottom-to-top (deposition order)
- **Target vs achieved thickness**: Post-deposition validate via profilometry or ellipsometry
- **Rate stability**: CV < 5% indicates stable process; higher values suggest target aging or gas flow issues
- **Temperature effects**: Room temperature deposition is standard for memristor stacks to minimize interdiffusion
- **Pre-deposition clean**: Ar plasma (reverse sputter) for 1-5 min at 10-50 W RF improves adhesion
