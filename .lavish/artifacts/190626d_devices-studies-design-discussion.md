---
layer: [1, 7]
type: design-discussion
status: discussion
tags: [architecture, devices, studies, grammar, waveform]
assignee: human
---

# Design Discussion: Devices, Studies, Instruments, Grammar

**Date**: 19/06/2026
**Status**: 🟡 Discussion draft v6 — waveform-as-derived-intermediate confirmed
**Audience**: Human (design conversation). No code changes implied.
**Companion**: `160626c_device-study-relationship.md` is the existing low-level architecture map. This doc is the higher-level design discussion.

**Changelog:**
- v1: Mental model intro, 4 points + 3 gaps
- v2: Added 4-vocabulary table, per-study schema, "config-studies.yaml" proposal, 9 open questions
- v3: Refined direction-of-ownership (study owns instrument list, not vice versa), per-instrument grammar confirmed, code-audit findings added, simplified open questions
- v4: **Hybrid layout** — instrument holds machine-level parsing once, study holds per-(study, inst) metadata extractors. Avoids duplication while keeping (study, inst) data co-located.
- v5: **Waveform-as-2D-array v1** — initially framed as a config declaration + analyzer/plot refactor.
- v6 (this): **Waveform-as-derived-intermediate** — corrected: the 2D array is **produced by the analyzer** from raw time/voltage data, NOT declared in config. The analyzer's output becomes the intermediate representation, from which scalars (v_set_v, set_width_us, etc.) are deterministically derived. The array + scalars are both stored in `protocol.yaml` under the file/step entry. The array is the **source of truth** for the pulse pattern; the scalars are **derived views** of the same data. ASCII art rendering and pattern-similarity grouping become possible because the array is now in a stable, comparable form.

---

## 0. The four vocabularies (and the ownership rules)

| Vocabulary | What it is | Active set | Owns the **list of** | Where it lives |
|-----------|------------|------------|----------------------|----------------|
| **Device** | Physical thing being measured. | `volatile-memristor`, `non-volatile-memristor`, `junction` (3 only) | which **studies** apply to me | `config-devices.yaml:device_types` |
| **Study** | Measurement kind. What you did. | 9 studies: pulse×3, iv×1, ec×3, spectroscopy×2 | which **instruments** support me, the **metadata schema**, the **Python analyzer** | `config-studies.yaml:studies` (new file) |
| **Instrument** | Physical machine. | `keysight-b1500a`, `keithley-2400`, `autolab-usth`, `horiba-usth`, `spectrometer-iop` | my own info (type, location), how to **parse my files**, my **filename grammar patterns** | `config-instruments.yaml:instruments` |
| **Grammar pattern** | Filename regex. Recognizes a file as (instrument, study). | `rN-cN-stp-decay`, `rN-cN-iv`, `cv-deposition`, `raman-spectrum`, etc. | nothing (purely recognition) | `config-instruments.yaml:instruments.<inst>.filename_patterns` (per-inst) |

**The ownership direction (the key insight from your 2nd message):**

```
STUDY ─owns→ list of instruments
INSTRUMENT ─owns→ its own info + parsing + grammar
DEVICE ─owns→ list of studies
GRAMMAR ─owns→ nothing (just recognition patterns)
```

This is **NOT** bidirectional. The instrument does **NOT** own "the list of studies I support" — that's derivable by walking studies. The current config has `instruments.<inst>.techniques: [list]` which is **redundant** (and unused — see audit below). We can remove it.

---

## 1. The grammar question, answered concretely

You asked: "does grammar help parse metadata or only filename?"

**Grammar = filename only.** Three concrete uses:

1. **Identify the instrument.** When you `sci info` a folder, you see a list of files. Grammar matches the filename shape (date code, matrix, technique, ext) to identify which machine produced it.
2. **Identify the study.** The `technique:` capture group in the regex tells you the study (e.g. `stp-decay` → `pulse:pulse-stp-decay`).
3. **Extract filename metadata.** Date, material, matrix (r5-c2), suffix, tag.

**Grammar does NOT do:**
- Parse file contents (delimiter/header_lines does that)
- Extract metadata (parse/analyze functions do that, defined per-(study, instrument))
- Tell you which column is voltage vs current (column map does that)

**Where grammar lives:** per-instrument, under `instruments.<inst>.filename_patterns: [...]`. Different machines have different filename formats. Keysight uses `rN-cN-stp-decay`, Horiba uses `raman-spectrum` (no matrix). The grammar should be a property of the instrument, not a global list.

---

## 1.5. The waveform insight (v6, the real one)

You asked two questions:
1. "If the studies have the metadata, how does the instrument know where and how to parse?"
2. "Can the waveform pattern be parsed/analyzed to give us v_set, v_read, rise/fall widths, ASCII art?"

The answer to both is the same: **the 2D array is the analyzer's output, not the analyzer's input.**

### 1.5a. How the bridge works (parsing question)

The instrument doesn't know about metadata. The study doesn't know about file format. They meet at the **per-(study, inst) bridge**:

```yaml
# instrument: I produce files with V1, I2 columns, comma-delimited, 246 header lines
instruments:
  keysight-b1500a:
    parsing: {delimiter: ',', header_lines: 246, columns: {voltage: V1, current: I2}}

# study: I want these metadata keys, and for each machine I use, here's how to get them
studies:
  pulse:pulse-stp-decay:
    metadata_extractors:
      keysight-b1500a:
        compliance: {method: parse, parser: compliance}        # run on header
        waveform: {method: analyze, function: extract_waveform_from_data}  # NEW
        derived: {method: derive, function: derive_waveform_metadata}      # NEW
        repeat_count: {method: parse, parser: repeat_count}    # run on header
```

When the file `150626_cu-pda_r5-c2_stp-decay_041.csv` arrives:
1. Grammar → instrument = keysight-b1500a, study = pulse:pulse-stp-decay
2. Use `instruments.keysight-b1500a.parsing` to load the file → DataFrame (time, voltage, current)
3. Use `studies.pulse:pulse-stp-decay.metadata_extractors.keysight-b1500a` to extract metadata
4. The waveform extractor analyzes the time/voltage data → produces the 2D array
5. The derived extractor reads the array → produces scalars (v_set, v_read, widths, etc.)
6. Both array and scalars get written to `protocol.yaml` under the file/step entry

**The instrument and study are decoupled.** Adding a new machine = add a `parsing` block. Adding a new study = add a `metadata_extractors.<inst>` block. The two only meet at the bridge.

### 1.5b. The waveform as a DERIVED intermediate (v6, the corrected insight)

The 2D array is **produced by the analyzer from the raw time/voltage data**, not declared in config. It's the **intermediate representation** of the pulse pattern.

**Why the analyzer produces the array (vs reading a pre-declared example):**

- **The data IS in the file.** A pulse measurement has time and voltage columns. The pulse pattern can be detected: find the high level (v_set), find the low level (v_read), find the transitions (rise, fall), measure the widths. This is **analysis**, not declaration.
- **The array is reproducible.** Two analyzers running on the same data should produce the same array. The array is the **canonical result** of running the analyzer.
- **The scalars are derived from the array, deterministically.** Given the same array, v_set_v is always 0.5, set_width_us is always 39. This makes the metadata **verifiable**.

**The analyzer pipeline becomes:**

```
raw CSV file
    ↓
[instrument.parsing] → DataFrame (time, voltage, current)
    ↓
[study.metadata_extractors.<inst>.waveform] extract_waveform_from_data(data)
    ↓
   2D array [[time, voltage], ...]      # the pulse pattern
    ↓
[study.metadata_extractors.<inst>.derived] derive_waveform_metadata(waveform)
    ↓
   scalars {v_set_v: 0.5, v_read_v: 0.1, set_width_us: 39, read_width_us: 4, rise_us: 1, fall_us: 1, repeat_pattern: null}
    ↓
[merge_analysis_to_metadata] write array + scalars to protocol.yaml under file/step
    ↓
fzf / plot / UI read from protocol.yaml
```

**What lives in `protocol.yaml`:**

```yaml
# protocol.yaml — under the file entry for 150626_cu-pda_r5-c2_stp-decay_041.csv
- filename: 150626_cu-pda_r5-c2_stp-decay_041.csv
  study: pulse:pulse-stp-decay
  instrument: keysight-b1500a
  device: volatile-memristor
  waveform:                              # NEW: 2D array from analyzer
    - [0,    0  ]
    - [1e-6, 0.1]
    - [5e-6, 0.1]
    - [6e-6, 0  ]
    - [10e-6, 0  ]
    - [11e-6, 0.5]
    - [50e-6, 0.5]
  metadata:                              # existing block, NOW DERIVED from waveform
    v_set_v: 0.5
    v_read_v: 0.1
    set_width_us: 39
    read_width_us: 4
    rise_us: 1
    fall_us: 1
    repeat_pattern: null
    compliance: 1e-3                     # from header parser
    repeat_count: 1                      # from header parser
```

(The exact `protocol.yaml` layout is a separate design discussion — you said "we will leave the protocol.yaml configuration later".)

### 1.5c. The "what lives where" rule, updated

| Concern | Lives in | Why |
|---------|----------|-----|
| How to load a raw file | `instruments.<inst>.parsing` | Machine-level. Same for all studies. |
| How to extract metadata from a (study, inst) pair | `studies.<study>.metadata_extractors.<inst>` | Per-pair. Each study says what to extract from each machine. |
| **The waveform array itself** | **`protocol.yaml` under the file entry** | **Produced by the analyzer, stored as the canonical pulse pattern. The scalars are derived views.** |
| The scalars (v_set_v, etc.) | `protocol.yaml` under the file entry (derived from waveform) | Deterministic derivation from the array. Also includes header-parsed values like compliance, repeat_count. |
| The data shape declaration | `studies.<study>.data_shape` (NEW) | Tells the system "this study produces a 2D array `[time, voltage]`". The analyzer uses this hint to know what to extract. |
| ASCII art rendering of the waveform | Feature in `core/waveform_render.py` (NEW) | Reads the array from `protocol.yaml`, renders as text. Pure display, no analysis. |
| Grouping files by pattern similarity | Feature in `core/pattern_grouping.py` (future) | Compares arrays from `protocol.yaml` across files. Pure display, no analysis. |

### 1.5d. What this means for the analyzer (concretely)

The current `analyze_waveform_params` (which produces scalars from the raw data) becomes **two functions**:

```python
# core/waveform.py (NEW)

def extract_waveform_from_data(data: pd.DataFrame) -> list[list[float]]:
    """Analyze time/voltage data → produce the canonical 2D waveform array.
    
    This is the analyzer's primary output. It detects the pulse pattern:
    - Find high level (v_set) and low level (v_read)
    - Find transitions (rise, fall edges)
    - Reduce to a canonical representation [time, voltage] of the pulse shape
    """
    ...

def derive_waveform_metadata(waveform: list[list[float]]) -> dict:
    """Given the 2D array, compute the scalar metadata.
    
    This is deterministic. Same array → same scalars. Always.
    """
    return {
        "v_set_v": max(v for _, v in waveform),
        "v_read_v": min(v for _, v in waveform),  # or second-highest for asymmetric
        "set_width_us": ...,
        "read_width_us": ...,
        "rise_us": ...,
        "fall_us": ...,
    }
```

Both functions are pure. Easy to test. Easy to verify.

**Plot does NOT need to change.** The plot can continue reading raw data from the file, or it can read the array from `protocol.yaml`. Either works. (You said "touch directly to plot and analyze things" — no, the plot doesn't need to use the array.)

**fzf does NOT need to change for the scalar display.** It can continue showing v_set_v, set_width_us, etc. The array is **also** available in `protocol.yaml`, so the fzf CAN show a small ASCII-art preview if you want, but that's an optional new feature.

### 1.5e. Side question: raman/uv-vis as 2D arrays

Raman and UV-Vis are also 2D arrays `[wavelength, intensity]`. When we wire them up, the same structure applies:
- Analyzer produces 2D spectrum from raw data
- Scalars (peak_wavelength, peak_intensity, FWHM) are derived from the spectrum
- Both stored in `protocol.yaml`
- ASCII art rendering of the spectrum is a future feature

The current `metadata_schema` for these is empty. So adopting this structure is **forward-looking**.

### 1.5f. Why the array matters (the real value)

The 2D array unlocks things that scalars can't:

1. **ASCII art rendering.** Print a small text waveform in the terminal:
   ```
   v_set 0.5V  ┐    ┌──────┐
   v_read 0.1V ─┘────┘      └──
   time:   0  1µs  5µs 11µs 50µs
   ```
2. **Pattern-similarity grouping.** Compare two arrays: "are these two files from the same protocol?" Useful for batch analysis.
3. **Verification.** The array is the canonical result; the scalars are derived. If the array looks wrong, the scalars will be wrong too. If the scalars look wrong, you can compare to the array to see why.
4. **Reproducibility.** Two analyzers producing the same array means the same measurement. Two analyzers producing the same scalars can mean different measurements (if shapes differ).

**You said "this kind of information for all, the output that we use the config will return directly to the protocol.yaml where the filename under the filename we can put multiple stuff there".** This is exactly what the v6 structure does: the analyzer's output (array + scalars) gets written to `protocol.yaml` under the file/step entry. The filename groups its associated data.

---

## 2. The config split (clean version, hybrid layout)

After your v3 clarification (parsing goes with the machine, extractors go with the study) + the code audit, the target is:

```
config/
├── config.yaml                    # ~10 lines: projects_root, theme, dpi, defaults
├── config-devices.yaml            # device_types + legacy_to_study ONLY (~60 lines)
├── config-instruments.yaml        # instruments: registry + machine-level parsing + filename_patterns
├── config-studies.yaml (NEW)      # studies: metadata_schema + python_module + device_overrides + metadata_extractors
└── config-template.yaml           # plot labels + themes (unchanged)
# config-grammar.yaml — DELETED (folded into instruments.<inst>.filename_patterns)
```

### The "what lives where" rule (the key principle)

> **Anything that's about the MACHINE → `instruments.<inst>`.**
> **Anything that's about what a STUDY wants from the machine → `studies.<study>.metadata_extractors.<inst>`.**

| Concern | Lives in | Why |
|---------|----------|-----|
| `delimiter`, `header_lines`, `encoding` | `instruments.<inst>.parsing` | Machine-level. Same for all studies using this machine. |
| `columns: {voltage: V1, current: I2}` | `instruments.<inst>.parsing.columns` | Machine-level. Keysight files always have V1 and I2 columns. |
| `filename_patterns: [rN-cN-stp-decay]` | `instruments.<inst>.filename_patterns` | Machine-level. Keysight files always have this filename shape. |
| `metadata_extractors: {compliance: {method: parse, parser: ...}, waveform_params: {method: analyze, function: ...}}` | `studies.<study>.metadata_extractors.<inst>` | Study-level. Different studies want different keys from the same machine. |
| `metadata_schema: [v_set_v, v_read_v, ...]` | `studies.<study>.metadata_schema` | Study-level. Each study has its own canonical key list. |
| `device_overrides: {volatile: {add: [...]}}` | `studies.<study>.device_overrides` | Study-level. Volatile behavior is per-(study, device). |
| `python_module: pulse.stp` | `studies.<study>.python_module` | Study-level. The analyzer function is per-study. |

### Per-file ownership (final)

| File | Owns | Does NOT own |
|------|------|--------------|
| `config.yaml` | Global routing: `projects_root`, `theme`, `dpi`, `defaults` (default-instrument-per-technique) | Anything study/instrument-specific |
| `config-devices.yaml` | `device_types:` (device → list of studies, plus `analysis_mode`, `library`), `legacy_to_study:` (short code → full study name) | Metadata schema, parsing config, Python modules, instrument info, metadata extractors |
| `config-instruments.yaml` | `instruments:` registry: `name`, `label`, `type`, `location`, **`parsing`** (delimiter, encoding, header_lines, columns), **`filename_patterns`** (grammar) | Metadata extractors (per-study, not per-inst), per-device logic, list of studies supported (derivable) |
| `config-studies.yaml` (NEW) | `studies:` registry: per-study **`metadata_schema`**, **`python_module`**, **`device_overrides`**, **`metadata_extractors.<inst>`** (per-(study, inst) parser/analyzer bindings) | Machine-level parsing (lives in instruments), per-device routing (lives in devices) |
| `config-template.yaml` | Plot labels, theme definitions | Anything else |

### Per-study entry shape (proposed, v6 — array is derived, not declared)

```yaml
# config-studies.yaml
studies:
  pulse:pulse-stp-decay:
    label: "STP Decay — set pulse + current decay read"
    python_module: pulse.stp         # the analyzer (per-study)
    data_shape:                      # NEW: declares the data shape (the kind of array)
      kind: waveform_2d              # the analyzer will produce a 2D [time, voltage] array
      columns: [time_s, voltage_v]
      units: [s, V]
    derived_metadata:                # scalars the analyzer will compute FROM the array
      - v_set_v
      - v_read_v
      - set_width_us
      - read_width_us
      - rise_us
      - fall_us
      - repeat_pattern
    device_overrides:                # per-device schema tweaks
      volatile-memristor:
        add: [decay_tau_ms, r_read_ohm]
      non-volatile-memristor:
        exclude: [decay_tau_ms]      # non-volatile doesn't decay
    metadata_extractors:             # per-(study, inst) — how to extract each key
      keysight-b1500a:
        compliance:                  # parse from header
          method: parse
          parser: compliance
        repeat_count:
          method: parse
          parser: repeat_count
        waveform:                    # NEW: the analyzer produces the 2D array
          method: analyze
          function: extract_waveform_from_data
          inputs: [time, voltage]
          outputs: [waveform]        # goes to protocol.yaml under the file
        derived:                     # NEW: scalars derived from the array
          method: derive
          function: derive_waveform_metadata
          inputs: [waveform]
          outputs: [v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern]
  pulse:pulse-endurance:
    label: "Pulse Endurance Cycling"
    data_shape: {kind: waveform_2d, columns: [time_s, voltage_v]}
    derived_metadata: [cycle, r_high, r_low, ...]
    device_overrides:
      volatile-memristor: {add: [r_decay_ohm]}
      non-volatile-memristor: {add: [r_high_ohm, r_low_ohm]}
    metadata_extractors:
      keysight-b1500a:
        compliance: {method: parse, parser: compliance}
        waveform: {method: analyze, function: extract_endurance_waveform}
        derived: {method: derive, function: derive_endurance_metadata}
  raman:raman-spectrum:
    label: "Raman Spectroscopy"
    data_shape: {kind: spectrum_2d, columns: [wavelength_nm, intensity]}
    derived_metadata: [peak_wavelength_nm, peak_intensity, fwhm_nm, snr]
    python_module: raman.spectrum    # future
    metadata_extractors: {}          # raman files have no header to parse
  ...
```

**Note:** `metadata_extractors` is keyed by the instrument that supports the study. If a study has no instrument-specific parsing (e.g. raman uses `names: [shift, intensity]` and no header parsing), the block is empty or omitted.

### Per-instrument entry shape (proposed, machine-level only)

```yaml
# config-instruments.yaml
instruments:
  keysight-b1500a:
    label: Keysight B1500A
    type: semiconductor-device-analyzer
    location: gtiit-china
    parsing:                          # MACHINE-LEVEL: how to load any file from this machine
      delimiter: ','
      decimal: .
      header_lines: 246
      encoding: utf-8
      columns:                        # what columns exist in the raw file
        voltage: V1
        current: I2
        time: Time
    filename_patterns:                # per-instrument grammar (recognize filenames)
      - rN-cN-iv
      - rN-cN-stp-decay
      - rNcN
    # NO techniques: list (derivable from studies)
    # NO metadata extractors — those are per-(study, inst) in config-studies.yaml
    # NO metadata_schema — that's per-study
```

**What `parsing` does:** given a raw file from this machine, turn it into a DataFrame. Shared by all studies using this machine.

**What's NOT in `parsing`:** the metadata extractors. Those depend on what the study wants, not on what the machine produces. So they live in `studies.<study>.metadata_extractors.<inst>`.

### Per-device entry shape (current is fine, just trim)

```yaml
# config-devices.yaml
device_types:
  volatile-memristor:
    label: Volatile Memristor
    description: One-directional switching with volatile decay
    studies:
      - iv:iv-bipolar-sweep
      - pulse:pulse-stp-decay
      - pulse:pulse-endurance
      - pulse:pulse-ppf
    analysis_mode: volatile
    library: iv                       # overrides default 'iv' library if needed
  non-volatile-memristor:
    label: Non-Volatile Memristor
    description: Bidirectional switching with retention
    studies:
      - iv:iv-bipolar-sweep
      - pulse:pulse-endurance
      - pulse:pulse-retention
    analysis_mode: bipolar
  junction:
    label: Junction
    studies:
      - iv:iv-bipolar-sweep
      - ec:ec-cv
      - ec:ec-ca
      - ec:ec-eis
legacy_to_study:
  iv-sweep: iv:iv-bipolar-sweep
  pulse-stp: pulse:pulse-stp-decay
  # ... etc
```

---

## 3. Data flow (filename → analysis)

Given `150626_cu-pda_r5-c2_stp-decay_041.csv` in `data/raw/`:

```
STEP 1: GRAMMAR MATCH
   Try each instrument's filename_patterns in order.
   keysight-b1500a.filename_patterns[0] = rN-cN-stp-decay
   → regex matches! captures: {date_code, matrix, technique=stp-decay, suffix}
   → instrument = keysight-b1500a
   → study = pulse:pulse-stp-decay (from technique → studies mapping)

STEP 2: RESOLVE DEVICE
   study = pulse:pulse-stp-decay
   → walk device_types, find which device has this study
   → if multiple match (volatile + non-volatile both have it), use the project's
     current device_type (from project context)
   → device = volatile-memristor

STEP 3: LOAD DATA (MACHINE-LEVEL)
   source: instruments.keysight-b1500a.parsing
   → {delimiter: ',', header_lines: 246, columns: {voltage: V1, current: I2}}
   → read CSV → DataFrame
   → column remap (voltage: V1, current: I2)

STEP 4: EXTRACT METADATA (STUDY-LEVEL, per-inst)
   source: studies.pulse:pulse-stp-decay.metadata_extractors.keysight-b1500a
   → {compliance: {parse}, waveform: {analyze}, derived: {derive}, repeat_count: {parse}}
   For each extractor:
     - parse: run on the raw header (e.g. compliance from "Primary.Compliance")
     - analyze: run on the DataFrame, produce the 2D waveform array (e.g. extract_waveform_from_data)
     - derive: run on the array, produce the scalars (e.g. derive_waveform_metadata)
   → array + metadata dict

STEP 5: APPLY SCHEMA (STUDY-LEVEL)
   source: studies.pulse:pulse-stp-decay.derived_metadata
   → [v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us, repeat_pattern]
   Apply device_overrides:
     - volatile-memristor: add [decay_tau_ms, r_read_ohm]
   Final schema = [v_set_v, v_read_v, set_width_us, read_width_us, rise_us, fall_us,
                   repeat_pattern, decay_tau_ms, r_read_ohm]
   → final metadata dict (filter to schema keys)

STEP 6: WRITE TO protocol.yaml (NEW in v6)
   merge_analysis_to_metadata() writes:
     - waveform: [[time, voltage], ...]   # the 2D array
     - metadata: {v_set_v: ..., v_read_v: ..., ...}   # the scalars
   Both under the file/step entry.

STEP 7: FZF DISPLAY
   For file picker:
   → use final schema (with device overrides) → columns to show
   → each row = file path + per-file metadata values
   → (future: also show ASCII art of waveform — not in v6 scope)

STEP 8: PLOT
   resolve_study_plotter("pulse:pulse-stp-decay", "volatile-memristor")
   → StudyPlotter with device variant applied
   → plot_fn(df, metadata) → matplotlib figure
   → (plot does NOT use the array — unchanged from v3)

STEP 9: ANALYZE
   resolve_study_analyzer("pulse:pulse-stp-decay", "volatile-memristor")
   → StudyAnalyzer with device variant applied
   → analyze_fn(flags) → YAML results
   → (analyzer in v6 produces the array; this is when that happens — during the analyze run)
```

---

## 4. Code audit findings (Q6, Q7, Q8 from v2 answered)

You said Q6/Q7/Q8 were confusing. The question was: "what code actually reads these config blocks?" Here are the answers from reading the source.

### `config-devices.yaml:techniques:` — partially dead

This block (ec-cv, ec-ca, ec-eis, iv-sweep, raman, uv-vis) has `grammar_codes:`, `default_device:`, `devices:`. What's it for?

**Read by:**
- `core/config.py:946` — `list_global_techniques()` returns top-level `techniques:` keys
- `core/config.py:420, 479, 601, 615, 672` — `tech_section = config.get("techniques", {}).get(technique, {})` in 5+ helpers
- `cli/commands/instrument.py:114-147` — `ins["techniques"]` for display

**Verdict:** the `techniques:` block is **still in use** for legacy helper functions. It's the old "technique-centric" model. The new "study-centric" model (in `studies:`) is what the rest of the code uses. Both coexist. **Phase 1 of the refactor should decide which is canonical** (recommend: study-centric; deprecate `techniques:`).

### `config-instruments.yaml:devices:` — duplicate of `instruments.<inst>.config`

This block (autolab-usth, keithley-clarius, keithley-2400, horiba-usth) has `delimiter`, `columns`, etc.

**Read by:**
- `core/config.py:303` — `merged["devices"] = instr_cfg["devices"]` (merges the whole block into top-level `cfg["devices"]`)
- `core/config.py:710-720` — `get_device_parsing_config()` reads BOTH `cfg["devices"][name]` AND `cfg["instruments"][name]["config"]`, **merges them** with `instruments` taking priority

**Verdict:** the `devices:` block is **legacy**, fully duplicated by `instruments.<inst>.config`. The newer one wins via merge. **Safe to remove** (with one big caveat: `keithley-clarius` is in `devices:` but NOT in `instruments:` — that's a hidden entry we should keep or migrate).

**Action:** migrate `keithley-clarius` from `devices:` to `instruments:`, then remove the `devices:` block. Update `get_device_parsing_config()` to read from `instruments.<inst>.config` only.

### `instruments.<inst>.techniques:` — dead-ish

This is `instruments.<inst>.techniques: [iv-sweep, iv-breakdown, ...]` in the config.

**Read by:**
- `library/instruments/registry.py:104-105` — `if technique in techniques:` (when resolving default instrument for a technique)
- `cli/commands/ls_cmd.py:601, 608` — `study_filter and study_filter not in ins.get("techniques", [])` (for filtering instruments by study)

**Verdict:** **used, but should be derivable** (walk studies to get the reverse). After we remove the field, we need to compute it on-demand. Two-line change in the registry, easy.

### `instruments.<inst>.techniques:` (the hardcoded version in `config_defaults.py`)

Lines 28-57 of `config_defaults.py` have hardcoded `techniques: [list]` for each instrument. **Same** as above. Used as fallback when config-instruments.yaml doesn't have a particular instrument.

**Verdict:** same. Derive on-demand. Drop the hardcoded list.

### `device_types.<device>.analysis_mode` and `.library` — used

- `analysis_mode` → `core/routing.py:resolve_analysis_mode()` returns the analysis mode for routing
- `library` → `core/studies.py:resolve_library_from_study()` returns the library (overrides technique default)

**Verdict:** **KEEP.** Real fields, real usage. Document them better in `config-devices.yaml` comments.

### `core/studies.py:get_studies_for_instrument` — **DEAD CODE**

Defined at line 190 but **no callers** (grep returns 1 match: the definition itself). Safe to remove or repurpose.

### `core/studies.py:get_instruments_for_study` — wrapper

Defined at line 208, wrapped at `core/config.py:1303`. **No callers outside the wrapper.** It's a public API of sorts. Keep it, but mark as "derived from study config".

---

## 5. The refactor plan (revised, in dependency order)

After audit, here's the actual order. Each phase is small enough to verify with tests before moving on.

### Phase 0: Confirm design with you ← we are here

Ask Q1-Q4 below. Get sign-off.

### Phase 1: Decouple parsing config (Gap C, smallest)

- Move `config-instruments.yaml:devices:` content into `instruments.<inst>.config` (including the orphan `keithley-clarius`).
- Remove `config-instruments.yaml:devices:` block.
- Update `get_device_parsing_config()` to read only from `instruments.<inst>.config`.
- Move per-study `instruments.<inst>.columns` from `config-devices.yaml` to `config-instruments.yaml:instruments.<inst>.config.columns`. Keep `metadata:` per-study (it's per-study, not per-inst).
- Run all 547 tests. Should pass with no functional change.

Effort: 0.5-1 session.

### Phase 2: Per-instrument grammar (Gap D)

- Move each entry in `config-grammar.yaml:file_naming.patterns` to `config-instruments.yaml:instruments.<inst>.filename_patterns` (or the equivalent `instruments.<inst>.config.filename_patterns`).
- Update `core/protocol.py:parse_filename` (or wherever grammar is resolved) to walk per-instrument patterns.
- Decide: remove `config-grammar.yaml` entirely OR keep as legacy fallback. (Recommend: remove after a deprecation cycle.)
- Run all tests.

Effort: 0.5 session.

### Phase 3: `config-studies.yaml` for metadata schema (Gap B)

- Create `config-studies.yaml` with metadata_schema + python_module + device_overrides for each of the 9 studies.
- Update `core/studies.py` to load from the new file.
- Move `studies:` block from `config-devices.yaml` to the new file.
- Update `STUDY_COLUMN_REGISTRY` (in `core/fzf_columns.py`) to derive from the new config, falling back to the hardcoded dict for back-compat.
- Run all tests.

Effort: 1-1.5 sessions.

### Phase 4: Remove `instruments.<inst>.techniques` (derive on-demand)

- Update `library/instruments/registry.py:get_instrument_techniques()` to compute by walking studies.
- Update `cli/commands/ls_cmd.py` filtering to use the computed value.
- Update `core/config_defaults.py` to drop the hardcoded `techniques:` lists.
- Run all tests.

Effort: 0.5 session.

### Phase 5: `STUDY_ANALYZERS` registry (Gap A)

- Create `StudyAnalyzer` dataclass + `DeviceAnalyzerVariant` in `core/study_analyzers.py`.
- Migrate `TECHNIQUE_ANALYZERS` calls to `STUDY_ANALYZERS`.
- Add per-device variants where they make sense (endurance already has the plot variant; do the same for analyze).
- Effort: 1-1.5 sessions.

### Phase 5b: Waveform-as-derived-intermediate (v6 insight)

- Add `data_shape` to each study in `config-studies.yaml` (declaration of the array kind, not the values).
- Refactor the analyzer to produce the 2D array as primary output, scalars as derived:
  - `extract_waveform_from_data(data)` → 2D array `[time, voltage]`
  - `derive_waveform_metadata(waveform)` → scalars `{v_set_v, v_read_v, ...}`
- Update `merge_analysis_to_metadata` to write the array + scalars to `protocol.yaml` under the file/step entry.
- Add a `protocol.yaml` schema for the array block (you said: "we will leave the protocol.yaml configuration later" — so this is a separate design task).
- fzf display: keep showing scalars as today. The array is available for future ASCII-art rendering, but we don't add that now.
- Plot: unchanged. Still reads raw data.
- Effort: 2-3 sessions (touches the analyzer, the metadata writer, and the test fixtures). Plot and fzf are NOT touched.

### Phase 6: Update `config-devices.yaml:techniques:` block (cleanup)

- Decide: keep as legacy or remove.
- Recommend: remove (it's redundant with `studies:` + the new analyzer dispatch).
- Effort: 0.5 session.

### Phase 7: Docs + CHANGELOG + AGENTS.md

- Update `documentation/INDEX.md` to reflect new config layout.
- Update `documentation/reference/config-system.md` (if it exists).
- Update `CHANGELOG.md` with the breaking change note.
- Update `AGENTS.md` directory map.
- Effort: 0.5 session.

### Phase 8: Tests for per-device routing and per-study schema

- Add tests for `resolve_study_analyzer(study, device_type)` returning the right variant.
- Add tests for `STUDY_COLUMN_REGISTRY` deriving from `config-studies.yaml`.
- Add tests for per-instrument grammar resolution.
- Effort: 1 session.

**Total: ~5-6 sessions of focused work after design is settled.**

---

## 6. The 5 questions I need answered (v3 + v5)

### Q1: Per-device analyzer behavior — base + variant (mirror plot)

Same as v1/v2. The plot side uses `device_variants` already. Mirror it on the analyze side.

**Recommended: yes.** My recommendation. (Still awaiting your confirm.)

### Q2: Add `config-studies.yaml`?

This is the new file that owns the metadata schema. Studies have canonical metadata_schema, devices can add/exclude keys.

**Recommended: yes.** (You said Q5 from v2 is yes — that's the same question.)

### Q3: Fold grammar into `config-instruments.yaml` (per-inst)?

Move `config-grammar.yaml:file_naming.patterns` to `config-instruments.yaml:instruments.<inst>.filename_patterns`. Grammar is per-instrument because filename formats are per-instrument.

**Recommended: yes.**

### Q4: Singular or plural for spectroscopy studies?

`raman:raman-spectrum` (current) vs `raman:raman-spectra` (your phrasing).

**Your answer: `raman-spectrum` (singular).** Decided.

### Q5: Adopt waveform-as-derived-intermediate for pulse/spectroscopy? (v6, current)

The 2D array `[time, voltage]` becomes the **analyzer's primary output**. The scalars (v_set_v, set_width_us, etc.) are **deterministically derived** from the array. Both are stored in `protocol.yaml` under the file/step entry.

**The array is NOT a config declaration — it's a runtime result.**

**Pros:**
- The array is the canonical representation of the pulse pattern; scalars are derived views.
- Two files with the same array = same measurement. Two files with the same scalars can be different measurements.
- Unlocks future features: ASCII art rendering, pattern-similarity grouping, reproducibility checks.
- Analyzer is cleanly split: extraction (data → array) vs derivation (array → scalars). Both are pure functions, easy to test.

**Cons:**
- The analyzer needs refactoring (split into two functions).
- `protocol.yaml` schema gains a new block (the array). Layout decisions deferred to a separate design discussion.
- Plot and fzf are NOT touched (this was the v5 over-scope — corrected in v6).

**Scope (v6, smaller than v5):**
- `core/waveform.py` (NEW): `extract_waveform_from_data`, `derive_waveform_metadata`
- `core/analysis_output.py` (UPDATE): `merge_analysis_to_metadata` writes the array to `protocol.yaml`
- `config-studies.yaml` (UPDATE): add `data_shape` to pulse + spectroscopy studies
- `core/analysis_output.py` tests (UPDATE): add tests for array extraction + scalar derivation
- Plot: **unchanged**
- fzf display: **unchanged** (still shows scalars)

**My recommendation: yes.** It's a more honest data model and the scope is contained — only the analyzer and the metadata writer are touched. Plot and fzf are off-limits for this phase.

**Your answer needed: yes/no.**

---

## 7. Once Q1-Q5 are decided

The next step is to:
1. **Decide** Q1 (confirmed) and Q5 (waveform-as-derived-intermediate).
2. **Do a deeper code audit** if you want me to find more dead code / duplicates. I have a partial picture from this conversation, but a full pass with codegraph would be safer before refactoring.
3. **Write the plan artifact** (`/Users/tai/.config/science-cli/.opencode/artifacts/190626e_config-split-implementation-plan.md` or similar) with the per-phase task list, file-by-file changes, and test impact.
4. **Get your approval** on the plan.
5. **Delegate to code-medium** for execution.

I'm ready to do (2) and (3) now if you confirm Q5. Or do you want to discuss anything else first?

---

## 8. TL;DR (skim version)

The cleanest mental model (hybrid v4):

- **Devices** = what you measure (3 active: volatile/non-volatile memristor, junction)
- **Studies** = what you do to it (9 active: pulse×3, iv×1, ec×3, spectroscopy×2)
- **Instruments** = what machine produced the data (5 active)
- **Grammar** = filename recognition, per-instrument

**Ownership rule (the key principle):**
> **About the MACHINE → `instruments.<inst>`.**
> **About what a STUDY wants → `studies.<study>`.**
> **About the (study, inst) pair → `studies.<study>.metadata_extractors.<inst>`.**

**Config split:**
| File | Owns |
|------|------|
| `config.yaml` | Global routing only |
| `config-devices.yaml` | device_types + legacy_to_study |
| `config-instruments.yaml` | instruments: identity + machine-level parsing (delimiter, columns) + filename_patterns |
| `config-studies.yaml` (NEW) | studies: metadata_schema + python_module + device_overrides + metadata_extractors (per-inst) |
| `config-template.yaml` | plot labels + themes |
| `config-grammar.yaml` | DELETED (folded into instruments) |

**What "machine parses once" means:** `delimiter`, `header_lines`, `columns` live in `instruments.<inst>.parsing`. Written once. Shared by all studies using that machine. If you change keysight's columns, you change them in one place.

**What "study adds extractors" means:** `studies.<study>.metadata_extractors.<inst>` has the per-(study, inst) `parse:` and `analyze:` and `derive:` functions. Different studies want different metadata from the same machine.

**What "waveform-as-derived-intermediate" means (v6):** The 2D `[time, voltage]` array is the **analyzer's output**, not a config declaration. The analyzer:
1. Reads raw time/voltage from the DataFrame
2. Detects the pulse pattern → produces the 2D array
3. Derives scalars (v_set_v, set_width_us, etc.) from the array (deterministic)
4. Writes both array + scalars to `protocol.yaml` under the file/step entry

The array unlocks future features (ASCII art rendering, pattern-similarity grouping) but doesn't require them now. **Plot and fzf are NOT touched in v6.**

**Work: 5-6 sessions** to fully match your mental model. 8 phases. Each phase has tests. Plus 2-3 more sessions for the waveform-as-derived-intermediate refactor (Phase 5b).

**Decisions so far (all locked):**
- Q1: base + variant analyzer dispatch — **✅ confirmed (option c)**
- Q2: yes, add `config-studies.yaml` — ✅ confirmed
- Q3: yes, fold grammar into `config-instruments.yaml` — ✅ confirmed
- Q4: `raman-spectrum` (singular) — ✅ confirmed
- Q5 (v2): `studies:` block moves to `config-studies.yaml` — ✅ confirmed
- v4: hybrid layout — machine parses once, study adds extractors — ✅ confirmed
- **v6: waveform-as-derived-intermediate** — analyzer produces the 2D array; scalars are derived; both written to `protocol.yaml`. Scope is contained (analyzer + metadata writer only — plot and fzf unchanged).

**Decision still needed: Q5** (v6 waveform). Confirm?

**New decision deferred (per your "we will leave the protocol.yaml configuration later"):**
- **protocol.yaml layout for the waveform array** — separate design discussion.
