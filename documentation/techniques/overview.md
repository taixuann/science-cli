# Technique Taxonomy Overview

**Master reference** — 28+ measurement techniques, detection, routing, dispatch, analysis, and plotting.

This document is the canonical guide to how science-cli classifies, detects, routes, analyzes, and plots experimental data across six measurement domains. It covers every technique registered in the system, explains the filename-based detection engine, maps techniques to their analysis libraries and device-type analysis modes, and lists every analyzer, plotter, and YAML output schema.

---

## Technique Categories

Techniques are grouped into six categories based on measurement modality. Each category contains one or more technique slugs (machine-readable identifiers used throughout the system).

### 1. IV Measurements

DC current-voltage measurements on two-terminal devices.

| Technique Slug | Label | Description |
|---|---|---|
| `iv-sweep` | IV Sweep | DC current-voltage sweep (V vs I) |
| `iv-breakdown` | Breakdown | Ramped voltage to breakdown |
| `iv-leakage` | Leakage | Low-bias leakage current |

All three route to the `iv` library for analysis and use the `iv.metrics` module for parameter extraction (V_set, V_reset, ON/OFF ratio).

### 2. Pulse Measurements

Pulsed voltage measurements for memristor and neuromorphic device characterization. These share overlapping patterns with the legacy `mem-*` prefix (see Technique Detection overlap note below).

| Technique Slug | Label | Description |
|---|---|---|
| `pulse-endurance` | Pulse Endurance | Pulsed endurance cycling (R_high / R_low vs cycle count) |
| `pulse-retention` | Pulse Retention | Pulse retention time test (resistance decay over time) |
| `pulse-switching` | Pulse Switching | Pulse switching characterization |
| `pulse-forming` | Pulse Forming | Electroforming step (initial soft breakdown) |
| `pulse-set` | Pulse Set | Set operation pulse |
| `pulse-reset` | Pulse Reset | Reset operation pulse |
| `pulse-read` | Pulse Read | Read pulse (non-destructive read) |
| `pulse-ivd` | Pulsed IV | Pulsed IV measurement (quasi-static IV with pulses) |
| `pulse-stp` | STP Decay | Short-term plasticity decay (biexponential/stretched) |
| `pulse-ppf` | PPF Ratio | Paired-pulse facilitation ratio vs inter-pulse interval |

All pulse techniques route to the `pulse` library.

**Legacy overlap:** The techniques `mem-endurance`, `mem-retention`, and `mem-switching` exist as aliases with identical filename patterns to their `pulse-*` counterparts. They are NOT in `TECHNIQUE_LIBRARY_MAP` and currently route to the `general` library via fallback prefix matching. They are retained for backward compatibility but new workflows should use the `pulse-*` slugs exclusively. The `mem-*` prefixes were inherited from an older naming convention predating the unified `pulse-` namespace. See the detection overlap note below for pattern collision behavior.

### 3. Electrochemistry

Wet-cell electrochemical measurements from potentiostat instruments (Biologic, CH Instruments, etc.).

| Technique Slug | Label | Description |
|---|---|---|
| `ec-cv` | CV | Cyclic Voltammetry (potential vs current) |
| `ec-ca` | CA | Chronoamperometry (current vs time at fixed potential) |
| `ec-eis` | EIS | Electrochemical Impedance Spectroscopy (Nyquist, Bode) |
| `ec-lsv` | LSV | Linear Sweep Voltammetry |
| `ec-swv` | SWV | Square Wave Voltammetry |

All electrochemistry techniques route to the `ec` library. EIS has special plot dispatch generating Nyquist, Bode, and optional circuit-fit overlay plots. CV and CA share the `electrochem.models` data structures (CVData, CAData, EISData).

### 4. Spectroscopy

Optical spectroscopy techniques for thin-film and materials characterization.

| Technique Slug | Label | Description |
|---|---|---|
| `raman` | Raman | Raman spectroscopy (wavenumber vs intensity) |
| `uv-vis` | UV-Vis | UV-Vis transmission/absorbance spectroscopy (wavelength vs transmission/absorbance) |

Raman routes to the `raman` library with special plot dispatch via `_wrap_raman_plot`. UV-Vis routes to the `uv-vis` library. Both have custom analyzers for peak detection (scipy.signal.find_peaks) and UV-Vis additionally supports Tauc bandgap computation.

### 5. Microscopy

AFM/SPM image data in various native instrument formats.

| Technique Slug | Label | Description |
|---|---|---|
| `afm-gwy` | AFM (Gwyddion) | Gwyddion native format (.gwy) |
| `afm-spm` | AFM (Bruker SPM) | Bruker Nanoscope SPM format (.spm) |
| `afm-ibw` | AFM (Igor) | Igor Pro binary wave (.ibw) |
| `afm-jpk` | AFM (JPK) | JPK Instruments format (.jpk, jpk-, jpk_) |
| `afm-stp` | AFM (STP) | STP format (.stp) |
| `afm-top` | AFM (TOP) | Topography format (.top) |

Only `afm-gwy` is registered in `TECHNIQUE_LIBRARY_MAP` (routes to `afm` library). An AFM analyzer stub exists at `_analyze_afm` (not yet implemented — delegates to `afm analyze` CLI). AFM plot dispatch uses `_wrap_afm_plot` from the `afm` command module. The `cross-section` and `colormap` plot flags are AFM-specific.

### 6. Deposition

Physical vapor deposition process monitoring.

| Technique Slug | Label | Description |
|---|---|---|
| `pvd` | PVD Deposition | Physical vapor deposition process log |

Identified by the `deposition` / `pvd` device type routing to `linear` analysis mode. Produces `pvd-deposition_analysis.yaml` with layer-by-layer deposition parameters (material, thickness, rate, temperature, pressure).

---

## Technique Detection

The detection engine in `core/technique.py` maps raw data filenames to technique slugs using a regex-based pattern matching system. It powers automatic technique identification across all CLI commands — plot, analyze, ls, and technique-specific subcommands.

### How `detect_technique()` Works

```python
def detect_technique(filename: str) -> str:
    """Detect technique from filename using merged patterns."""
    for tech, patterns in _all_patterns().items():
        for p in patterns:
            try:
                if re.search(p, filename, re.IGNORECASE):
                    return tech
            except re.error:
                continue
    return ""
```

The function iterates over all techniques in insertion order, checking each regex pattern with `re.search()` (case-insensitive). **First match wins** — the order of techniques in the PATTERNS dict determines priority (see the overlap note below).

### Pattern Resolution Order (4-Tier)

1. **Project-level overrides** — `<project_root>/sci-config.yaml` patterns for a specific technique (highest priority)
2. **Global config patterns** — `~/.config/science-cli/config.yaml` technique entries
3. **Hardcoded fallback** — the `PATTERNS` dict in `core/technique.py`
4. **Per-field extract specs** — matrix position extraction (e.g., `r0c0`, `b1-t1`)

Config patterns are prepended before hardcoded patterns in `_all_patterns()`:

```python
def _all_patterns():
    patterns = {}
    for tech, pats in PATTERNS.items():
        patterns[tech] = list(pats)
    for tech, pats in _config_patterns().items():
        if tech not in patterns:
            patterns[tech] = []
        new = [p for p in pats if p not in existing]
        patterns[tech] = new + existing  # config first
    return patterns
```

### Complete Pattern Table

| Technique | Regex Patterns |
|---|---|
| `ec-cv` | `_CV\.`, `\.cv$`, `cv_`, `cv-` |
| `ec-ca` | `_CA\.`, `\.ca$`, `ca_`, `ca-` |
| `ec-eis` | `\.mpt$`, `_EIS\.`, `\.eis$`, `_impedance`, `\.z` |
| `ec-lsv` | `_LSV\.`, `\.lsv$` |
| `ec-swv` | `_SWV\.`, `\.swv$` |
| `iv-sweep` | `_IV\.`, `\.iv$`, `iv_`, `iv-`, `_sweep`, `sweep_` |
| `iv-breakdown` | `_bd\.`, `breakdown_`, `_Vbd`, `bd_` |
| `iv-leakage` | `_leak`, `leakage_`, `leak_` |
| `mem-endurance` | `_endurance`, `\.end`, `end_`, `endurance`, `-endurance` |
| `mem-retention` | `_retention`, `\.ret`, `ret_`, `retention`, `-retention` |
| `mem-switching` | `_switch`, `\.sw`, `sw_`, `switch_`, `-switch` |
| `pulse-endurance` | `_endurance`, `\.end`, `end_`, `endurance`, `-endurance` |
| `pulse-retention` | `_retention`, `\.ret`, `ret_`, `retention`, `-retention` |
| `pulse-switching` | `_switch`, `\.sw`, `sw_`, `switch_`, `-switch` |
| `pulse-forming` | `_forming`, `form_`, `_form` |
| `pulse-set` | `_set`, `_SET` |
| `pulse-reset` | `_reset`, `_RESET` |
| `pulse-read` | `_read`, `_READ` |
| `pulse-ivd` | `_ivd`, `_IVD`, `_pulsed-iv` |
| `pulse-stp` | `_stp`, `_STP`, `_stp_decay`, `_short-term` |
| `pulse-ppf` | `_ppf`, `_PPF`, `_paired-pulse` |
| `raman` | `_raman`, `_sers`, `_raman-sers`, `_SERS` |
| `uv-vis` | `_uv-vis`, `_uvvis`, `uv-vis`, `uvvis` |
| `afm-gwy` | `\.gwy$` |
| `afm-spm` | `\.spm$` |
| `afm-ibw` | `\.ibw$` |
| `afm-jpk` | `\.jpk$`, `jpk-`, `jpk_` |
| `afm-stp` | `\.stp$` |
| `afm-top` | `\.top$` |

### Detection Examples

| Filename | Technique | Matched Pattern |
|---|---|---|
| `2105_HfOx_CV_001.txt` | `ec-cv` | `_CV\.` |
| `2105_HfOx_IV_r0c0.txt` | `iv-sweep` | `_IV\.` |
| `2105_Pt_endurance_01.txt` | `mem-endurance` | `_endurance` (matched before `pulse-endurance`) |
| `S01_breakdown_3V.txt` | `iv-breakdown` | `breakdown_` |
| `sample_raman_SERS.txt` | `raman` | `_sers` |
| `AFM_001.gwy` | `afm-gwy` | `\.gwy$` |
| `eis_data.mpt` | `ec-eis` | `\.mpt$` |
| `run_leak_test.csv` | `iv-leakage` | `_leak` (via `_leak`) |

### Important: `mem-` vs `pulse-` Overlap

The `mem-endurance`, `mem-retention`, and `mem-switching` techniques have **exactly the same patterns** as their `pulse-*` counterparts. Because `mem-endurance` appears first in the PATTERNS dict (insertion order), a file named `2105_HfOx_endurance_001.txt` will be detected as `mem-endurance`, not `pulse-endurance`. This is a legacy artifact. The `mem-*` techniques are not in `TECHNIQUE_LIBRARY_MAP`, so they fall through to the `general` library in routing. To force `pulse-*` detection, either:

- Use config overrides to remove `mem-*` patterns, or
- Use explicit `--technique pulse-endurance` CLI flags

### Grammar-Based Filename Parsing

Beyond simple technique detection, `parse_filename_grammar()` in `core/technique.py` extracts structured fields from filenames using a 5-tier resolution chain:

1. **Hardcoded grammar** (fallback): `(?P<date_code>...)_(?P<material>...)_(?P<technique>...)_(?P<matrix>...)_(?P<suffix>...)`
2. **Device-type-specific grammar** (from config)
3. **Global config grammar** (from `get_file_naming_grammar()`)
4. **Project-level overrides** (from per-project grammar config)
5. **Protocol-level grammar** (from `<protocol>.yaml` grammar section — highest priority)

The result is normalized via `standardize_grammar_fields()` to always include five universal fields:

| Field | Description | Example |
|---|---|---|
| `date_code` | Date code (YYYYMMDD or similar) | `210526` |
| `material` | Material name or abbreviation | `HfOx` |
| `technique` | Technique abbreviation | `IV` |
| `matrix` | Matrix position | `r0c0`, `b1-t1` |
| `suffix` | Run number suffix | `001` |

Matrix positions are further extracted into `row` and `col` integers for both `rN-cN` and `bN-tN` (bottom-top) formats.

---

## Library Routing

The `TECHNIQUE_LIBRARY_MAP` in `core/routing.py` determines which analysis library module handles each technique.

### TECHNIQUE_LIBRARY_MAP

| Technique | Library |
|---|---|
| `iv-sweep` | `iv` |
| `iv-breakdown` | `iv` |
| `iv-leakage` | `iv` |
| `pulse-endurance` | `pulse` |
| `pulse-retention` | `pulse` |
| `pulse-switching` | `pulse` |
| `pulse-forming` | `pulse` |
| `pulse-set` | `pulse` |
| `pulse-reset` | `pulse` |
| `pulse-read` | `pulse` |
| `pulse-ivd` | `pulse` |
| `pulse-stp` | `pulse` |
| `pulse-ppf` | `pulse` |
| `raman` | `raman` |
| `uv-vis` | `uv-vis` |
| `ec-cv` | `ec` |
| `ec-ca` | `ec` |
| `ec-eis` | `ec` |
| `ec-lsv` | `ec` |
| `ec-swv` | `ec` |
| `afm-gwy` | `afm` |
| `mem-endurance` | *(general — not in map)* |
| `mem-retention` | *(general — not in map)* |
| `mem-switching` | *(general — not in map)* |
| `afm-spm` | *(general — not in map)* |
| `afm-ibw` | *(general — not in map)* |
| `afm-jpk` | *(general — not in map)* |
| `afm-stp` | *(general — not in map)* |
| `afm-top` | *(general — not in map)* |

### `resolve_library()` Implementation

```python
def resolve_library(technique: str, devices: str | None = None) -> str:
    result = TECHNIQUE_LIBRARY_MAP.get(technique)
    if result:
        return result
    for prefix, lib in [("iv-", "iv"), ("pulse-", "pulse"), ("ec-", "ec")]:
        if technique.startswith(prefix):
            return lib
    return "general"
```

The function first checks the explicit map. If no match, it tries prefix-based fallback matching (`iv-`, `pulse-`, `ec-`). Finally it returns `"general"`. This means techniques like `ec-lsv` and `ec-swv` work via the map lookup, while any hypothetical `pulse-*` variant would work via prefix fallback even without a map entry.

---

## Device Type Mode Routing

The `DEVICE_TYPE_MODE_MAP` in `core/routing.py` determines the analysis mode based on the device type declared in the protocol YAML (`devices:` field). The mode affects how data is interpreted — especially for IV measurements where the switching regime differs between device types.

### DEVICE_TYPE_MODE_MAP

| Device Type | Analysis Mode | Description |
|---|---|---|
| `memristor` | `volatile` | V_set only (no V_reset) — volatile switching |
| `junction` | `bipolar` | V_set + V_reset — bipolar switching |
| `deposition` | `linear` | Linear I-V — deposition/PVD process monitoring |
| `pvd` | `linear` | Linear I-V — PVD process monitoring |
| `electrochem` | `general` | General analysis — electrochemistry |
| `general` | `general` | Default analysis mode |

### `resolve_analysis_mode()` Implementation

```python
def resolve_analysis_mode(devices: str) -> str:
    return DEVICE_TYPE_MODE_MAP.get(devices, "general")
```

The mode is consumed by IV analyzers to determine whether to look for both V_set and V_reset (bipolar mode) or V_set only (volatile mode). The `--vset-only` CLI flag on `sci analyze` overrides the automatic mode detection for ad-hoc analysis.

### Mode Effect on IV Analysis

```python
# In _analyze_iv() — analyze.py:479
mode = "volatile" if flags.get("vset_only") else "general"

analysis_results = {
    "analysis": {
        "mode": mode,
        "parameters": {
            "v_set": params.get("v_set"),
            "v_reset": params.get("v_reset"),
            "on_off_ratio": params.get("on_off_ratio"),
            "switching_detected": params.get("switching_detected", False),
        },
    },
}
```

When mode is `volatile`, the V_reset field may be absent from the output YAML. The IV sweep schema validator (`validate_iv_sweep_schema()`) enforces this: bipolar mode requires both V_set and V_reset, while volatile mode only requires V_set.

---

## Analyzer & Plotter Mapping

### Per-Technique Analyzers

Registered in `TECHNIQUE_ANALYZERS` in `cli/commands/analyze.py`. This maps technique slugs to handler function names within the same module.

```python
TECHNIQUE_ANALYZERS = {
    "iv-sweep": "_analyze_iv",
    "iv-breakdown": "_analyze_iv",
    "iv-leakage": "_analyze_iv",
    "pulse-endurance": "_analyze_pulse_endurance",
    "pulse-retention": "_analyze_pulse_retention",
    "pulse-stp": "_analyze_pulse_stp",
    "pulse-ppf": "_analyze_pulse_ppf",
    "ec-cv": "_analyze_cv",
    "ec-ca": "_analyze_ca",
    "ec-eis": "_analyze_eis",
    "raman": "_analyze_raman",
    "uv-vis": "_analyze_uv_vis",
    "afm-gwy": "_analyze_afm",
}
```

**Implementation status:**

| Technique | Analyzer | Status | Library Module Used |
|---|---|---|---|
| `iv-sweep` | `_analyze_iv` | ✅ Implemented | `library.iv.metrics` (detect_vset, detect_vreset, extract_iv_parameters) |
| `iv-breakdown` | `_analyze_iv` | ✅ Implemented | `library.iv.metrics` |
| `iv-leakage` | `_analyze_iv` | ✅ Implemented | `library.iv.metrics` |
| `pulse-endurance` | `_analyze_pulse_endurance` | ⏳ Stub | *(delegates to `pulse analyze`)* |
| `pulse-retention` | `_analyze_pulse_retention` | ⏳ Stub | *(delegates to `pulse analyze`)* |
| `pulse-stp` | `_analyze_pulse_stp` | ⏳ Stub | *(delegates to `pulse analyze`)* |
| `pulse-ppf` | `_analyze_pulse_ppf` | ⏳ Stub | *(delegates to `pulse analyze`)* |
| `ec-cv` | `_analyze_cv` | ✅ Implemented | `library.electrochem.cv` (peak_analysis, calculate_charge) |
| `ec-ca` | `_analyze_ca` | ✅ Implemented | `library.electrochem.ca` (analyze_ca: Cottrell fit, steady state) |
| `ec-eis` | `_analyze_eis` | ✅ Implemented | `library.electrochem.eis` (circuit_fit, kramers_kronig) |
| `raman` | `_analyze_raman` | ✅ Implemented | scipy.signal.find_peaks |
| `uv-vis` | `_analyze_uv_vis` | ✅ Implemented | scipy.signal.find_peaks |
| `afm-gwy` | `_analyze_afm` | ⏳ Stub | *(delegates to `afm analyze`)* |

### Per-Technique Analyzer Flags

| Technique | Flag | Type | Description |
|---|---|---|---|
| `iv-sweep` | `--yaml` | store_true | Output analysis YAML to results/ |
| `iv-sweep` | `--vset-only` | store_true | Volatile mode: V_set only, no V_reset |
| `iv-sweep` | `--compliance` | float | Compliance current (A) |
| `pulse-stp` | `--yaml` | store_true | Output analysis YAML |
| `pulse-stp` | `--fit-model` | str | Decay fit model: biexponential or stretched |
| `pulse-ppf` | `--yaml` | store_true | Output analysis YAML |
| `pulse-ppf` | `--intervals` | str | Comma-separated intervals (ms): 10,50,100 |
| `raman` | `--yaml` | store_true | Output analysis YAML |
| `raman` | `--peaks` | store_true | Find and report peaks |
| `raman` | `--baseline` | str | Baseline method: poly, asls, airpls |
| `uv-vis` | `--yaml` | store_true | Output analysis YAML |
| `uv-vis` | `--bandgap` | store_true | Compute Tauc bandgap |
| `afm` | `--yaml` | store_true | Output analysis YAML |
| `afm` | `--roughness` | store_true | Compute Sa/Sq roughness |

### Per-Technique Plotters

Registered in `TECHNIQUE_PLOTTERS` in `cli/commands/plot.py`. Techniques set to `None` use the generic `_do_plot` handler. Special dispatch occurs via `_dispatch_technique_plot()` for Raman, AFM, and EIS.

```python
TECHNIQUE_PLOTTERS = {
    "iv-sweep": None,
    "iv-breakdown": None,
    "iv-leakage": None,
    "pulse-endurance": None,
    "pulse-retention": None,
    "pulse-stp": None,
    "pulse-ppf": None,
    "ec-cv": None,
    "ec-ca": None,
    "ec-eis": None,
    "uv-vis": None,
    "raman": None,
    "afm-gwy": None,
}
```

**Dispatch routing:**

```python
def _dispatch_technique_plot(filepath, flags, technique):
    if technique == "raman":
        _wrap_raman_plot(filepath, flags)
    elif technique in ("afm-gwy", "afm"):
        _wrap_afm_plot(filepath, flags)
    elif technique == "ec-eis":
        _do_eis_plot(filepath, flags)
    else:
        _do_plot(filepath, flags, technique)
```

| Technique | Plotter | Implementation |
|---|---|---|
| `iv-sweep` | `_do_plot` (generic) | matplotlib line/scatter, auto column resolution |
| `iv-breakdown` | `_do_plot` (generic) | Same generic handler as iv-sweep |
| `iv-leakage` | `_do_plot` (generic) | Same generic handler as iv-sweep |
| `pulse-endurance` | `_do_plot` (generic) | Falls back to first two numeric columns |
| `pulse-retention` | `_do_plot` (generic) | Falls back to first two numeric columns |
| `pulse-stp` | `_do_plot` (generic) | Falls back to first two numeric columns |
| `pulse-ppf` | `_do_plot` (generic) | Falls back to first two numeric columns |
| `ec-cv` | `_do_plot` (generic) | Resolves Potential vs Current columns |
| `ec-ca` | `_do_plot` (generic) | Resolves Time vs Current columns |
| `ec-eis` | `_do_eis_plot` | Special: Nyquist + Bode + circuit fit + KK check |
| `raman` | `_wrap_raman_plot` | Delegates to `raman._do_single_raman_plot` |
| `uv-vis` | `_do_plot` (generic) | Resolves Wavelength vs Transmittance columns |
| `afm-gwy` | `_wrap_afm_plot` | Delegates to `afm._do_afm_plot` with colormap |

### Per-Technique Plotter Flags

| Technique | Flag | Type | Description |
|---|---|---|---|
| `raman` | `--laser` | int | Laser wavelength (nm) |
| `raman` | `--accumulation` | int | Accumulation count |
| `raman` | `--acq-time` | float | Acquisition time (s) |
| `raman` | `--nd-filter` | int | ND filter value |
| `ec-cv` | `--scan-rate` | float | Scan rate (mV/s) |
| `ec-cv` | `--cycles` | int | Number of cycles |
| `ec-eis` | `--freq-range` | str | Frequency range (e.g., 1Hz-1MHz) |
| `uv-vis` | `--wavelength-range` | str | Wavelength range (nm) |
| `afm` | `--cross-section` | store_true | Show cross-section |
| `afm` | `--colormap` | str | Colormap name |

### Plot Flag Validation

Plot flags are validated against the registered technique in `_validate_technique_flags()`:

- Without `--technique`, all technique-specific flags generate warnings telling the user to specify a technique
- With `--technique`, flags from other techniques generate warnings listing which allowed flags exist
- Unrecognized flags are silently passed through (no validation error, just non-functional)

---

## Dispatch System

### `sci plot --technique <type>` Flow

```
sci plot --technique <type> [flags] <files...>
    │
    ├─ plot_handler(args)
    │   └─ _plot_direct(files, rest_args)
    │       ├─ _parse_flags(rest_args)          # Extract --technique and all flags
    │       ├─ _resolve_file(filename)          # Search data/raw/ for each file
    │       ├─ detect_technique(Path(filename)) # Auto-detect if no --technique
    │       ├─ template_to_flags(technique)     # Theme defaults
    │       ├─ get_plot_labels(technique)       # Config labels
    │       └─ _dispatch_technique_plot(filepath, flags, technique)
    │           ├─ "raman"    → _wrap_raman_plot(filepath, flags)
    │           │               └─ raman._do_single_raman_plot(filepath, flags, auto_save=True)
    │           ├─ "afm-gwy"  → _wrap_afm_plot(filepath, flags)
    │           │               └─ afm._do_afm_plot(filepath, cmap, flags)
    │           ├─ "ec-eis"   → _do_eis_plot(filepath, flags)
    │           │               ├─ plot_eis_nyquist(z_real, z_imag)
    │           │               ├─ plot_eis_bode(freq, mag, phase)
    │           │               ├─ circuit_fit(eis_data, circuit_model)  (--circuit)
    │           │               └─ kramers_kronig(eis_data)               (--kk)
    │           └─ default    → _do_plot(filepath, flags, technique)
    │                           ├─ load_data_file(filepath, technique=tech, device=device)
    │                           ├─ _resolve_xy_columns(df, info, technique)
    │                           ├─ matplotlib plot (line/scatter)
    │                           └─ _get_results_dir(filepath) → save PDF
    │
    └─ Overlay mode (multiple files):
        └─ _do_overlap(resolved, flags, technique)
            ├─ Loads each file, resolves x/y columns
            └─ Overlays all traces on single axes with legend
```

### `sci analyze --technique <type>` Flow

```
sci analyze --technique <type> [flags]
    │
    ├─ analyze_handler(args)
    │   ├─ explicit --technique → _analyze_with_technique(technique, flags)
    │   │   ├─ fzf_select for file in data/raw/
    │   │   └─ TECHNIQUE_ANALYZERS[technique](filepath, flags)
    │   │
    │   ├─ file args → _analyze_direct(files, rest_args)
    │   │   ├─ _detect_technique(Path(filepath).name)
    │   │   ├─ Route to _analyze_iv / _analyze_cv / _analyze_ca / etc.
    │   │   └─ extract_sweep_from_file(filepath) → update protocol YAML
    │   │
    │   └─ no args → fzf_select file → _analyze_direct
    │
    └─ Shared analyzer pattern:
        ├─ load_data_file(filepath, technique=tech, device=device)
        ├─ Resolve columns from info["columns"]
        ├─ Run technique-specific analysis (peak detection, circuit fit, etc.)
        ├─ if --yaml: _output_yaml(technique, filepath, results, flags)
        │   └─ write_analysis_yaml(technique, step_dir, results)
        │       ├─ Validate against SCHEMA_VALIDATORS[technique]
        │       └─ yaml.dump → <step_dir>/results/<technique>_analysis.yaml
        └─ _save_analysis_manifest(filepath, technique, results)
            └─ emit_manifest → manifest.json
```

### Data Loading

Both plot and analyze commands share a common data loading pipeline:

1. **File resolution** — `_resolve_file()` searches `data/raw/` if the path isn't absolute, including fuzzy filename matching
2. **Device resolution** — `_resolve_device()` checks the current protocol's step metadata first, then falls back to `get_default_device(technique)` from config
3. **Data loading** — `load_data_file(filepath, technique=tech, device=device)` uses the device-config to determine delimiter, decimal separator, header lines, encoding, and column mapping
4. **Column resolution** — Technique-specific column aliases (e.g., `ec-cv` → `WE(1).Potential (V)` / `WE(1).Current (A)`)

---

## YAML Schema Overview

Every technique analyzer can produce a structured YAML analysis file via the `write_analysis_yaml()` function in `core/analysis_output.py`. Files are written to `<step_dir>/results/<technique>_analysis.yaml`.

### Common Envelope

```yaml
technique: <technique_slug>
instrument: <instrument_name>
devices: <device_type>
timestamp: "2026-06-15T12:00:00Z"
```

### Per-Technique Output Files

| YAML File | Analyzer | Validator | Key Sections |
|---|---|---|---|
| `iv-sweep_analysis.yaml` | `_analyze_iv` | `validate_iv_sweep_schema` | analysis.mode, parameters (v_set, v_reset, on_off_ratio) |
| `pulse-endurance_analysis.yaml` | `_analyze_pulse_endurance` | `validate_pulse_endurance_schema` | cycles_to_failure, r_high_drift, r_low_drift |
| `pulse-retention_analysis.yaml` | `_analyze_pulse_retention` | `validate_pulse_retention_schema` | retention_time_s, r_high_decay, r_low_decay |
| `pulse-stp_analysis.yaml` | `_analyze_pulse_stp` | `validate_pulse_stp_schema` | model, decay_fit (tau1, tau2, a1, a2) |
| `pulse-ppf_analysis.yaml` | `_analyze_pulse_ppf` | `validate_pulse_ppf_schema` | ppf_ratio_vs_interval, tau_facilitation |
| `ec-cv_analysis.yaml` | `_analyze_cv` | — | scan_rate, cycles, peaks (anodic/cathodic), charge |
| `ec-ca_analysis.yaml` | `_analyze_ca` | — | potential_step, cottrell (slope, r_squared), steady_state_current |
| `ec-eis_analysis.yaml` | `_analyze_eis` | — | circuit_fit (model, parameters, r_squared), kk_test |
| `raman_analysis.yaml` | `_analyze_raman` | `validate_raman_schema` | preprocessing, peaks[], metadata |
| `uv-vis-transmission_analysis.yaml` | `_analyze_uv_vis` | `validate_uv_vis_schema` | mode, peaks[], bandgap (tauc) |
| `uv-vis-absorbance_analysis.yaml` | `_analyze_uv_vis` | `validate_uv_vis_schema` | mode, peaks[], bandgap |
| `afm_analysis.yaml` | `_analyze_afm` | `validate_afm_schema` | scan_size, roughness (Sa, Sq, Sz), cross_section, psd |
| `pvd-deposition_analysis.yaml` | — | `validate_pvd_schema` | total_thickness, layers[], parameters |

See the [full Analysis YAML schema reference](../schemas/analysis-yaml.md) for complete YAML examples per technique.

### YAML Output Workflow

```python
# analysis_output.py — write_analysis_yaml()
results_dir = step_dir / "results"
results_dir.mkdir(parents=True, exist_ok=True)
yaml_path = results_dir / f"{technique}_analysis.yaml"

validator = _get_validator(technique)
validated = validator(analysis_results) if validator else analysis_results

output = {
    "technique": technique,
    "instrument": instrument,
    "devices": devices,
    "timestamp": datetime.utcnow().isoformat() + "Z",
    **validated,
}

with open(yaml_path, "w") as f:
    yaml.dump(output, f, default_flow_style=False, sort_keys=False)
```

The `--yaml` flag on `sci analyze` triggers YAML output. When present, results are written to disk AND optionally printed to stdout for piping.

---

## Interactive Mode

Both `sci plot` and `sci analyze` support fzf-based interactive file selection when called without arguments:

### `sci plot` (interactive)

```
sci plot
    ↓
FZF file selector (multi-select with Tab)
    ↓
Auto-detect technique from protocol step metadata
    ↓
Prompt for style/analysis options → Prompt for figure options
    ↓
Overlay all files or plot individually
    ↓
Save PDF to results/ → emit manifest
```

Features:
- Detects active protocol from session, filters files to that protocol's steps
- Shows step metadata in fzf display columns (protocol → step → filename)
- Auto-fills technique from protocol step metadata
- Applies theme defaults and config plot labels
- Prompts for style flags and figure flags per technique
- Offers overlay vs individual mode for multi-file selection

### `sci analyze` (interactive)

```
sci analyze
    ↓
FZF file selector (single-select)
    ↓
Auto-detect technique from filename
    ↓
Run analyzer, print results to console
    ↓
Optionally write YAML (if --yaml passed as extra flag)
    ↓
Extract sweep metadata → update protocol YAML
```

---

## See Also

### Per-Technique Guides
- [IV Sweep Analysis](../../src/science_cli/library/iv/) — V_set detection, V_reset detection, ON/OFF ratio
- [Pulse Analysis](../../src/science_cli/library/pulse/) — Endurance, retention, STP, PPF
- [Electrochemistry](../../src/science_cli/library/electrochem/) — CV peak analysis, CA Cottrell fit, EIS circuit fitting
- [Raman](../../src/science_cli/library/raman/) — Preprocessing, peak detection, spectroscopic analysis
- [AFM](../../src/science_cli/library/afm/) — Topography analysis, roughness, cross-section

### Reference Documentation
- [Config System](../reference/config-system.md) — 4-tier configuration inheritance, device definitions
- [Protocol YAML Schema](../schemas/protocol-yaml.md) — Protocol YAML structure, steps, files, devices
- [Analysis YAML Schema](../schemas/analysis-yaml.md) — Complete per-technique YAML output schemas with validators
- [Config YAML Format](../schemas/config-yaml.md) — Global and per-project config file format

### Source Files
- `src/science_cli/core/technique.py` — detect_technique(), PATTERNS, BUILTIN_TECHNIQUES, parse_filename_grammar()
- `src/science_cli/core/routing.py` — TECHNIQUE_LIBRARY_MAP, DEVICE_TYPE_MODE_MAP, resolve_library()
- `src/science_cli/core/analysis_output.py` — write_analysis_yaml(), validator dispatch
- `src/science_cli/cli/commands/plot.py` — TECHNIQUE_PLOTTERS, TECHNIQUE_FLAGS, _dispatch_technique_plot()
- `src/science_cli/cli/commands/analyze.py` — TECHNIQUE_ANALYZERS, ANALYZE_TECHNIQUE_FLAGS, per-technique analyzers
- `src/science_cli/analysis/validators.py` — SCHEMA_VALIDATORS, per-technique schema validation
- `src/science_cli/core/config.py` — technique config, device resolution, grammar loading
