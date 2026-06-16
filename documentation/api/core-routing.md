# `core/routing.py` — Library & Mode Resolution

**File:** `src/science_cli/core/routing.py`

Determines which analysis library module and analysis mode to use for a given technique. This is the central dispatch point that connects technique slugs (detected by `core/technique.py`) to their corresponding analysis implementations in `library/`.

---

## Constants

### `TECHNIQUE_LIBRARY_MAP`

Maps a technique slug to the name of the library subpackage that implements its analysis.

```python
TECHNIQUE_LIBRARY_MAP: dict[str, str] = {
    "iv-sweep":        "iv",
    "iv-breakdown":    "iv",
    "iv-leakage":      "iv",
    "pulse-endurance": "pulse",
    "pulse-retention": "pulse",
    "pulse-switching": "pulse",
    "pulse-forming":   "pulse",
    "pulse-set":       "pulse",
    "pulse-reset":     "pulse",
    "pulse-read":      "pulse",
    "pulse-ivd":       "pulse",
    "pulse-stp":       "pulse",
    "pulse-ppf":       "pulse",
    "raman":           "raman",
    "uv-vis":          "uv-vis",
    "ec-cv":           "ec",
    "ec-ca":           "ec",
    "ec-eis":          "ec",
    "ec-lsv":          "ec",
    "ec-swv":          "ec",
    "afm-gwy":         "afm",
}
```

| Key | Library | Analysis Module(s) |
|-----|---------|--------------------|
| `iv-sweep`, `iv-breakdown`, `iv-leakage` | `iv` | `library/iv/bipolar.py`, `library/iv/volatile.py` |
| `pulse-endurance`, `pulse-retention`, `pulse-switching`, `pulse-forming`, `pulse-set`, `pulse-reset`, `pulse-read`, `pulse-ivd`, `pulse-stp`, `pulse-ppf` | `pulse` | `library/pulse/endurance.py`, `library/pulse/retention.py`, `library/pulse/stp.py`, `library/pulse/ppf.py` |
| `raman` | `raman` | (external analysis) |
| `uv-vis` | `uv-vis` | (external analysis) |
| `ec-cv`, `ec-ca`, `ec-eis`, `ec-lsv`, `ec-swv` | `ec` | `library/electrochem/` |
| `afm-gwy` | `afm` | `library/afm/` |

### `DEVICE_TYPE_MODE_MAP`

Maps the protocol-level device type to an analysis mode that controls how results are interpreted.

```python
DEVICE_TYPE_MODE_MAP: dict[str, str] = {
    "memristor":    "volatile",
    "junction":     "bipolar",
    "deposition":   "linear",
    "pvd":          "linear",
    "electrochem":  "general",
    "general":      "general",
}
```

| Device Type | Mode | Interpretation |
|-------------|------|----------------|
| `memristor` | `volatile` | V_set only (no V_reset expected). Used by `iv/volatile.py`. |
| `junction` | `bipolar` | V_set + V_reset required. Used by `iv/bipolar.py`. |
| `deposition` | `linear` | Linear I-V characteristics (no switching). Used by `pvd/`. |
| `pvd` | `linear` | Same as `deposition`. |
| `electrochem` | `general` | Electrochemical analysis. Used by `electrochem/`. |
| `general` | `general` | Default fallback — no mode-specific constraints. |

---

## Functions

### `resolve_library(technique, devices)`

Determines which library subpackage to use for a given technique slug.

```python
def resolve_library(technique: str, devices: str | None = None) -> str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `technique` | `str` | Technique slug (e.g. `"iv-sweep"`, `"pulse-endurance"`, `"ec-cv"`). Typically produced by `core/technique.py:detect_technique()`. |
| `devices` | `str \| None` | Device type from the protocol YAML `devices:` field. Currently **unused** in the implementation but accepted for forward compatibility (allows device-specific library overrides). |

**Resolution order:**

1. **Exact map lookup** — Check `TECHNIQUE_LIBRARY_MAP.get(technique)`. Returns immediately if found.
2. **Prefix-based fallback** — If not in map, iterate known prefixes in order and return the first match:
   - `"iv-"` → `"iv"`
   - `"pulse-"` → `"pulse"`
   - `"ec-"` → `"ec"`
3. **General fallback** — Returns `"general"` if no prefix matches.

**Returns:** Library name string: `"iv"`, `"pulse"`, `"raman"`, `"uv-vis"`, `"ec"`, `"afm"`, or `"general"`.

**Examples:**

```python
resolve_library("iv-sweep")           # → "iv"
resolve_library("pulse-stp")          # → "pulse"
resolve_library("ec-cv")              # → "ec"
resolve_library("afm-gwy")            # → "afm"
resolve_library("iv-breakdown")       # → "iv" (exact match)
resolve_library("custom-iv-sweep")    # → "general" (no prefix match)
resolve_library("unknown-technique")  # → "general"
```

**Callers:**

- `cli/commands/analyze.py:433` — resolves library before dispatching analysis
- Library modules import this indirectly via the CLI command layer

### `resolve_analysis_mode(devices)`

Returns the analysis mode string for a given device type.

```python
def resolve_analysis_mode(devices: str) -> str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `devices` | `str` | Device type from protocol YAML (e.g. `"memristor"`, `"junction"`, `"deposition"`). |

**Resolution:**

- **Exact lookup** — Lookup in `DEVICE_TYPE_MODE_MAP.get(devices)`.
- **Fallback** — Returns `"general"` for any unrecognized device type.

**Returns:** One of `"volatile"`, `"bipolar"`, `"linear"`, or `"general"`.

**Mode semantics:**

| Mode | Behavior | Consumed By |
|------|----------|-------------|
| `volatile` | V_set required, V_reset optional | `library/iv/volatile.py` (validated in `analysis/validators.py:validate_iv_sweep_schema`) |
| `bipolar` | Both V_set and V_reset required | `library/iv/bipolar.py` (validated in `analysis/validators.py:validate_iv_sweep_schema`) |
| `linear` | Linear I-V characteristics | `library/pvd/` |
| `general` | No mode-specific constraints | `library/electrochem/`, fallback |

**Examples:**

```python
resolve_analysis_mode("memristor")  # → "volatile"
resolve_analysis_mode("junction")   # → "bipolar"
resolve_analysis_mode("deposition") # → "linear"
resolve_analysis_mode("pvd")        # → "linear"
resolve_analysis_mode("electrochem")# → "general"
resolve_analysis_mode("unknown")    # → "general"
```

---

## Prefix-Based Fallback Matching

When `resolve_library()` does not find an exact match in `TECHNIQUE_LIBRARY_MAP`, it falls back to prefix matching against three known prefixes in a fixed order:

```python
for prefix, lib in [("iv-", "iv"), ("pulse-", "pulse"), ("ec-", "ec")]:
    if technique.startswith(prefix):
        return lib
return "general"
```

**Known technique slugs that rely on prefix fallback (not in map but matched):**

None currently — all registered techniques in `core/technique.py:BUILTIN_TECHNIQUES` have explicit entries in `TECHNIQUE_LIBRARY_MAP`. The fallback exists for:

- Custom/config-defined technique slugs that use a standard prefix.
- Future technique additions where the library module is known by prefix convention.

**Prefixes not covered by fallback:** `"raman"`, `"uv-vis"`, `"afm-"` — these must be added explicitly to `TECHNIQUE_LIBRARY_MAP` to be resolved.

---

## Cross-References

| Module | File | Relationship |
|--------|------|-------------|
| `core/technique.py` | `src/science_cli/core/technique.py` | Produces technique slugs (`detect_technique`) that feed `resolve_library`. `BUILTIN_TECHNIQUES` defines every technique that `TECHNIQUE_LIBRARY_MAP` covers. |
| `library/iv/` | `src/science_cli/library/iv/` | `iv` library — bipolar and volatile IV analysis. Consumes `resolve_analysis_mode()` result for mode dispatch. |
| `library/iv/bipolar.py` | `src/science_cli/library/iv/bipolar.py` | Bipolar I-V analysis module (for `"bipolar"` mode). |
| `library/iv/volatile.py` | `src/science_cli/library/iv/volatile.py` | Volatile I-V analysis module (for `"volatile"` mode). |
| `library/pulse/` | `src/science_cli/library/pulse/` | `pulse` library — endurance, retention, STP, PPF analysis. |
| `library/pvd/` | `src/science_cli/library/pvd/` | `pvd` library — deposition/PVD analysis (uses `"linear"` mode). |
| `library/electrochem/` | `src/science_cli/library/electrochem/` | `ec` library — CV, CA, EIS, LSV, SWV analysis. |
| `library/afm/` | `src/science_cli/library/afm/` | `afm` library — AFM image analysis (Gwyddion files). |
| `analysis/validators.py` | `src/science_cli/analysis/validators.py` | Per-technique schema validators that check mode-specific requirements (e.g., `validate_iv_sweep_schema` checks `v_set`/`v_reset` based on mode). |
| `cli/commands/analyze.py` | `src/science_cli/cli/commands/analyze.py` | CLI entry point that calls `resolve_library()` then imports and invokes the resolved library's analysis function. |
| `core/config.py` | `src/science_cli/core/config.py` | Config system that can add custom technique patterns (used by `technique.py` but not by `routing.py` directly). |
