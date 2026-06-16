# `core/analysis_output.py` — Shared YAML Analysis Writer

**File:** `src/science_cli/core/analysis_output.py`

Provides a universal `write_analysis_yaml()` that any technique analyzer can call to persist analysis results as structured YAML files. Each result is validated against an optional per-technique schema validator before being written to disk.

---

## Constants

### `SCHEMA_VALIDATORS` (in `analysis/validators.py`)

Referenced lazily via `_get_validator()`. This is a `dict[str, Callable[[dict], dict]]` mapping technique slugs to validator functions. See [analysis/validators.py](#cross-references) for details.

---

## Functions

### `_get_validator(technique)`

Lazy-imports and looks up a schema validator for a given technique slug.

```python
def _get_validator(technique: str) -> Callable[[dict], dict] | None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `technique` | `str` | Technique slug (e.g. `"iv-sweep"`, `"pulse-endurance"`, `"afm-gwy"`). |

**Behavior:**

1. Attempts `from science_cli.analysis.validators import SCHEMA_VALIDATORS`.
2. Returns `SCHEMA_VALIDATORS.get(technique)` — the validator callable, or `None` if no validator is registered for that technique.
3. On `ImportError` (e.g., `analysis/validators.py` not installed or import path broken), returns `None` silently — writing proceeds without validation.

**Validator signature:** `Callable[[dict], dict]` — receives the `analysis_results` dict, validates it, and returns it (possibly augmented with defaults). Raises `ValueError` on invalid input.

**Registered validators (from `analysis/validators.py`):**

| Technique | Validator | Requirements |
|-----------|-----------|-------------|
| `afm-gwy` | `validate_afm_schema` | Ensures `analysis` key exists (may be empty for interactive entry). |
| `pvd-deposition` | `validate_pvd_schema` | `analysis` required; must contain `thickness_nm` or `total_thickness_nm`. |
| `uv-vis-transmission` | `validate_uv_vis_schema` | `analysis` key required. |
| `uv-vis-absorbance` | `validate_uv_vis_schema` | `analysis` key required. |
| `raman-spectrum` | `validate_raman_schema` | `analysis` key required. |
| `iv-sweep` | `validate_iv_sweep_schema` | `analysis` required; mode-dependent: `volatile` → `v_set` required, `bipolar` → both `v_set` and `v_reset` required. |
| `iv-breakdown` | `validate_iv_breakdown_schema` | `analysis` key required. |
| `pulse-endurance` | `validate_pulse_endurance_schema` | `analysis` key required. |
| `pulse-retention` | `validate_pulse_retention_schema` | `analysis` key required. |
| `pulse-stp` | `validate_pulse_stp_schema` | `analysis` required; `decay_fit` or `model` optional. |
| `pulse-ppf` | `validate_pulse_ppf_schema` | `analysis` required; `ppf_ratio_vs_interval` or `tau_facilitation_ms` optional. |

### `write_analysis_yaml(technique, step_dir, analysis_results, instrument, devices)`

Writes analysis results to `<step_dir>/results/<technique>_analysis.yaml`. This is the universal output function used by all analysis library modules.

```python
def write_analysis_yaml(
    technique: str,
    step_dir: Path,
    analysis_results: dict,
    instrument: str = "",
    devices: str = "",
) -> Path
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `technique` | `str` | Technique slug (e.g. `"iv-sweep"`, `"pulse-endurance"`, `"pvd-deposition"`). Used as the filename stem and included in the output envelope. |
| `step_dir` | `Path` | Path to the step directory. A `results/` subdirectory is created here if it does not exist. |
| `analysis_results` | `dict` | Technique-specific analysis results dict. Passed through the schema validator (if one is registered) before writing. |
| `instrument` | `str` | Optional instrument identifier string. Included in the output envelope metadata. |
| `devices` | `str` | Optional device-type string (from protocol YAML). Included in the output envelope metadata. |

**Returns:**

| Type | Description |
|------|-------------|
| `Path` | Absolute path to the written YAML file: `<step_dir>/results/<technique>_analysis.yaml`. |

**Output file structure:**

```
<step_dir>/
├── results/
│   └── <technique>_analysis.yaml    ← written by this function
```

**Envelope format:**

```yaml
technique: iv-sweep
instrument: Keysight B1500A
devices: memristor
timestamp: "2026-06-15T14:30:00.123456Z"
analysis:
  mode: volatile
  parameters:
    v_set: 1.23
    current_compliance_A: 1.0e-3
  metadata:
    sweep_rate_V_s: 0.5
    cycles: 100
```

The top-level keys `technique`, `instrument`, `devices`, and `timestamp` form the **envelope** — always present and populated from the function arguments. All remaining keys from `analysis_results` (after validation) are merged at the top level via `**validated`.

**Constants generated at write time:**

| Field | Source | Value |
|-------|--------|-------|
| `technique` | `technique` parameter | Verbatum slug string |
| `instrument` | `instrument` parameter | As provided (empty string if omitted) |
| `devices` | `devices` parameter | As provided (empty string if omitted) |
| `timestamp` | `datetime.utcnow()` | ISO 8601 with `Z` suffix, e.g. `"2026-06-15T14:30:00.123456Z"` |

**Write pipeline:**

```
write_analysis_yaml(technique, step_dir, analysis_results, instrument, devices)
    │
    ├─ 1. Create results/ directory               step_dir / "results"
    │      mkdir(parents=True, exist_ok=True)
    │
    ├─ 2. Build output path                        step_dir / "results" / f"{technique}_analysis.yaml"
    │
    ├─ 3. Look up validator                        _get_validator(technique)
    │      → SCHEMA_VALIDATORS.get(technique)
    │      → None on ImportError or missing key
    │
    ├─ 4. Validate analysis_results                validator(analysis_results)
    │      If validator is None, skip validation.
    │      Validator may raise ValueError — propagates to caller.
    │
    ├─ 5. Build envelope dict:
    │      {
    │          "technique":  technique,
    │          "instrument": instrument,
    │          "devices":    devices,
    │          "timestamp":  datetime.utcnow().isoformat() + "Z",
    │          **validated,          ← validated analysis_results merged in
    │      }
    │
    ├─ 6. Write YAML                              yaml.dump(output, f,
    │      sort_keys=False,                            default_flow_style=False,
    │      default_flow_style=False                    sort_keys=False)
    │
    └─ 7. Return Path to caller                    yaml_path (absolute)
```

**Callers (all library analysis modules):**

| Caller | File | Example Technique |
|--------|------|-------------------|
| `cli/commands/analyze.py` | `src/science_cli/cli/commands/analyze.py:436` | Central CLI dispatcher |
| `library/iv/volatile.py` | `src/science_cli/library/iv/volatile.py:101` | `iv-sweep` (volatile mode) |
| `library/iv/bipolar.py` | `src/science_cli/library/iv/bipolar.py:99` | `iv-sweep` (bipolar mode) |
| `library/pulse/endurance.py` | `src/science_cli/library/pulse/endurance.py:117` | `pulse-endurance` |
| `library/pulse/retention.py` | `src/science_cli/library/pulse/retention.py:104` | `pulse-retention` |
| `library/pulse/stp.py` | `src/science_cli/library/pulse/stp.py:176` | `pulse-stp` |
| `library/pulse/ppf.py` | `src/science_cli/library/pulse/ppf.py:110` | `pulse-ppf` |
| `library/pvd/yaml_io.py` | `src/science_cli/library/pvd/yaml_io.py:51` | `pvd-deposition` |

---

## Cross-References

| Module | File | Relationship |
|--------|------|-------------|
| `analysis/validators.py` | `src/science_cli/analysis/validators.py` | Defines `SCHEMA_VALIDATORS` registry and all per-technique validator functions. Lazy-imported by `_get_validator()`. Validators raise `ValueError` on invalid input. |
| `core/routing.py` | `src/science_cli/core/routing.py` | `resolve_library()` determines which library module to call; each library module then calls `write_analysis_yaml()` to persist results. |
| `library/iv/volatile.py` | `src/science_cli/library/iv/volatile.py` | Volatile I-V analysis — calls `write_analysis_yaml("iv-sweep", ...)`. |
| `library/iv/bipolar.py` | `src/science_cli/library/iv/bipolar.py` | Bipolar I-V analysis — calls `write_analysis_yaml("iv-sweep", ...)`. |
| `library/pulse/stp.py` | `src/science_cli/library/pulse/stp.py` | STP decay analysis — calls `write_analysis_yaml("pulse-stp", ...)`. |
| `library/pulse/ppf.py` | `src/science_cli/library/pulse/ppf.py` | PPF ratio analysis — calls `write_analysis_yaml("pulse-ppf", ...)`. |
| `library/pulse/endurance.py` | `src/science_cli/library/pulse/endurance.py` | Endurance cycling analysis — calls `write_analysis_yaml("pulse-endurance", ...)`. |
| `library/pulse/retention.py` | `src/science_cli/library/pulse/retention.py` | Retention time analysis — calls `write_analysis_yaml("pulse-retention", ...)`. |
| `library/pvd/yaml_io.py` | `src/science_cli/library/pvd/yaml_io.py` | PVD deposition analysis — calls `write_analysis_yaml("pvd-deposition", ...)`. |
| `cli/commands/analyze.py` | `src/science_cli/cli/commands/analyze.py` | CLI entry point that orchestrates routing → analysis → output via `write_analysis_yaml()`. |
