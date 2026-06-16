# Internal API — `src/science_cli/analysis/validators.py`

Per-technique YAML schema validators. Each validator receives the raw
`analysis_results` dict and returns it (possibly augmented with defaults),
or raises `ValueError` if required fields are missing.

---

## Registry

### `SCHEMA_VALIDATORS`

```python
SCHEMA_VALIDATORS: dict[str, Callable[[dict], dict]] = {}
```

Module-level dict mapping technique slug → validator function. Populated at
import time by the `@register` decorator. Looked up lazily by
`write_analysis_yaml()` at write time.

### `register(name: str)`

Decorator that inserts the decorated function into `SCHEMA_VALIDATORS` under
the given `name`. Multiple `@register` calls can be stacked on a single
function to register it under several slugs (see `validate_uv_vis_schema`).

---

## Validator Contract

Each validator accepts a single `results: dict` argument and must return a
`dict` (either the original, possibly mutated in-place, or a new dict). If
required fields are absent the validator **must raise `ValueError`** with a
descriptive message. Validators may also raise `AssertionError` for invariant
checks, though the current set uses `ValueError` exclusively.

---

## Per-Technique Validators

### `validate_afm_schema(results) → dict`

**Registered slug:** `afm-gwy`

Ensures `results["analysis"]` exists (creates an empty dict if missing). No
strict requirements — AFM analysis may be empty for interactive entry. Fields
like `roughness` or `Ra_nm` are encouraged but not required.

### `validate_pvd_schema(results) → dict`

**Registered slug:** `pvd-deposition`

Requires `"analysis"` key. Within `analysis`, requires at least one of
`thickness_nm` or `total_thickness_nm`. Raises `ValueError` if either level
of validation fails.

### `validate_uv_vis_schema(results) → dict`

**Registered slugs:** `uv-vis-transmission`, `uv-vis-absorbance` (stacked)

Requires `"analysis"` key. No further per-field constraints — any valid
UV-Vis analysis data is accepted.

### `validate_raman_schema(results) → dict`

**Registered slug:** `raman-spectrum`

Requires `"analysis"` key. Content is free-form.

### `validate_iv_sweep_schema(results) → dict`

**Registered slug:** `iv-sweep`

**Mode-aware validation.** Reads `analysis.parameters.mode` (defaults to
`"general"`). Depending on mode:

| Mode       | Requires                         |
|-----------|----------------------------------|
| `volatile` | `v_set` in `parameters`          |
| `bipolar`  | both `v_set` and `v_reset`       |
| (other)    | no parameter requirements         |

Raises `ValueError` if the required parameter(s) for the given mode are
missing. A `v_reset` appearing in `volatile` mode is silently accepted
(not an error).

### `validate_iv_breakdown_schema(results) → dict`

**Registered slug:** `iv-breakdown`

Requires `"analysis"` key. No further constraints.

### `validate_pulse_endurance_schema(results) → dict`

**Registered slug:** `pulse-endurance`

Requires `"analysis"` key. Content is free-form.

### `validate_pulse_retention_schema(results) → dict`

**Registered slug:** `pulse-retention`

Requires `"analysis"` key. Content is free-form.

### `validate_pulse_stp_schema(results) → dict`

**Registered slug:** `pulse-stp`

Requires `"analysis"` key. May contain `decay_fit` or `model` fields but
neither is mandatory (analysis may represent an error result).

### `validate_pulse_ppf_schema(results) → dict`

**Registered slug:** `pulse-ppf`

Requires `"analysis"` key. May contain `ppf_ratio_vs_interval` or
`tau_facilitation_ms` fields but neither is mandatory (analysis may
represent an error result).

---

## Integration — `core/analysis_output.py`

Validators are consumed by `write_analysis_yaml()` in
`src/science_cli/core/analysis_output.py`:

```python
def write_analysis_yaml(technique, step_dir, analysis_results, ...):
    validator = _get_validator(technique)    # lazy import → SCHEMA_VALIDATORS.get()
    if validator is not None:
        validated = validator(analysis_results)
    else:
        validated = analysis_results

    output = {"technique": technique, ..., **validated}
    yaml.dump(output, ...)
```

The lookup is performed lazily inside `_get_validator()` (line 15–21) via a
deferred `from science_cli.analysis.validators import SCHEMA_VALIDATORS`,
so the import only fires when YAML output is actually written. If the
import fails (e.g. optional dependencies missing), `_get_validator()`
returns `None` and validation is skipped.

If no validator is registered for the given technique slug, the results
dict is written verbatim without validation.
