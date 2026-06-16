---
name: sci-config
description: "Configuration management knowledge for science-cli v3.11.0 — 4-tier config inheritance, 5-tier grammar resolution, instrument registry, device config format, theme system, and all `sci config` subcommands across GLOBAL, THEME, TECHNIQUE, INSTRUMENT, and GRAMMAR categories. Load when configuring science-cli, adding devices, customizing grammar, or managing themes."
version: 3.11.0
author: science-cli team
ontology: [skill, science-cli, config, grammar, instruments, devices, themes, yaml]
workspace: tools/science-cli
load: on_request
---

# sci-config — science-cli Configuration Management Skill

## 1. Config File Locations — 4-Tier Inheritance

Settings are resolved by merging four layers. Higher-numbered tiers override lower-numbered ones. The merge is **deep** (nested dicts merge recursively).

```
Tier 1: Hardcoded Defaults (core/config.py, core/technique.py)
  ─ Always present, never removed
  ─ Built-in devices, technique patterns, grammar fallbacks, delimiters
    │ fallback
    ▼
Tier 2: Global Config (~/.config/science-cli/config.yaml, techniques/*.yaml)
  ─ Shared across ALL projects
  ─ Created by `sci config init --global`
  ─ Themes, project root, device registry, technique registry, file naming
    │ per-project override
    ▼
Tier 3: Per-Project Config (<project>/sci-config.yaml)
  ─ Overrides for one project only
  ─ Created by `sci config init --project`
  ─ Project-level technique/device overrides
    │ per-protocol override
    ▼
Tier 4: Per-Protocol YAML (<project>/protocol/<name>/<name>.yaml)
  ─ Highest priority
  ─ Step configs, instruments, sweep metadata, grammar: section
  ─ Created by `sci add -m protocol`
```

### File Location Reference Table

| File | Purpose | Created By |
|------|---------|------------|
| `~/.config/science-cli/config.yaml` | Global config (devices, techniques, grammar, defaults) | `sci config init --global` |
| `~/.config/science-cli/session.json` | Session state (active theme, last project/protocol/step) | Auto-created on first `sci` |
| `~/.config/science-cli/techniques/<name>.yaml` | Per-technique overrides | `sci config edit <technique>` |
| `<project>/sci-config.yaml` | Per-project overrides | `sci config init --project` |
| `<project>/protocol/<name>/<name>.yaml` | Protocol YAML (steps, instruments, grammar) | `sci add -m protocol` |

### Cache Invalidation

`config show` calls `invalidate_cache()` before display. Manual `config edit` also invalidates after editor exit.

---

## 2. `sci config` Command Tree — All Subcommands by Category

### Quick Reference Card

```
CATEGORY      SUBCOMMANDS
─────────────────────────────────────────────────────────────
GLOBAL         config init, config show
THEME          config theme list, config theme set <name>
TECHNIQUE      config list techniques
               config list devices <technique>
               config set technique <name> <device>
               config edit <technique> [--force]
               config edit techniques --global
INSTRUMENT     config devices list
               config edit devices
GRAMMAR        config list grammar [--device-type <type>]
               config grammar list [--device-type <type>|--protocol <name>]
               config edit grammar [--device-type <type>|--protocol <name>]
               config grammar edit [--device-type <type>|--protocol <name>]
               config grammar test <filename>
```

---

## 3. GLOBAL Subcommands

### `sci config init [--global|--project]`

Generate a default configuration file with all sections documented and commented.

| Flag | Description |
|------|-------------|
| `--global` | Write to `~/.config/science-cli/config.yaml` (default) |
| `--project` | Write to `<current_project>/sci-config.yaml` |

**Behavior:** Creates parent directory if needed. Refuses to overwrite existing files.

**Generated template includes:**
- `projects_root` — root directory for all projects
- `theme` — default matplotlib theme (`publication-nature`)
- `default_dpi` / `default_figure_format` — output defaults
- `file_naming:` — global grammar patterns (rNcN, bN-tN, device_type grammars)
- `devices:` — built-in device registry
- `techniques:` — technique registry
- `defaults:` — per-technique default device assignment

### `sci config show [--global|--project|--merged]`

Display the merged (or scoped) configuration as a Rich tree view.

| Flag | Description |
|------|-------------|
| `--global` | Show only global config (`~/.config/science-cli/config.yaml`) |
| `--project` | Show only per-project config (`<project>/sci-config.yaml`) |
| `--merged` | Show fully merged config (default) |

**Behavior:** Calls `invalidate_cache()` before display. `--project`/`--merged` require an open project.

---

## 4. THEME Subcommands

### `sci config theme list`

List all available themes. Active theme marked with `●`.

**7 Built-in Themes:**

| Theme | Use Case | Key Features |
|-------|----------|-------------|
| `default` | Quick previews | Standard matplotlib rcParams |
| `dark` | Screens / dark mode | Dark backgrounds, light text |
| `tufte` | Minimal ink, max data | Tufte-inspired, minimal grid |
| `publication-acs` | ACS journal style | Helvetica, boxed axes, 600 DPI |
| `publication-nature` | Nature journal style | Helvetica, spines off, minimal |
| `poster` | Conference posters | Large fonts, high DPI |
| `acs-annotated` | ACS with annotations | ACS base + annotation-friendly |

### `sci config theme set <name>`

Set the active matplotlib theme and apply it immediately.

**Flow:**
```
config theme set publication-nature
  → set_active_theme("publication-nature")  → writes to session.json
  → apply_theme("publication-nature")       → reads theme YAML
  → theme_to_rcparams()                    → converts to rcParams dict
  → matplotlib.rcParams.update(rc)          → applied globally
```

---

## 5. TECHNIQUE Subcommands

### `sci config list techniques`

List all configured techniques with device configuration details. Renders a 4-column Rich Table: Technique ID, Filename Patterns, Device Config, Default Device.

**Built-in Techniques (28+ slugs):**

| Technique | Default Device | Delimiter | Header Lines | Encoding |
|-----------|---------------|-----------|-------------|----------|
| `iv-sweep` | keithley-2400 | `\t` | 23 | utf-8 |
| `iv-breakdown` | keithley-2400 | `\t` | 23 | utf-8 |
| `iv-leakage` | keithley-2400 | `\t` | 23 | utf-8 |
| `pulse-endurance` | keithley-2400 | — | — | — |
| `pulse-retention` | keithley-2400 | — | — | — |
| `pulse-stp` | keysight-b1500a | `,` | 147 | utf-8 |
| `pulse-ppf` | keysight-b1500a | `,` | 147 | utf-8 |
| `raman` | horiba-usth | `\t` | 45 | latin1 |
| `uv-vis` | iop-hanoi | `,` | 1 | latin1 |
| `ec-cv` | — | — | — | — |
| `ec-ca` | — | — | — | — |
| `ec-eis` | — | — | — | — |
| `afm-gwy` | — | — | — | — |

### `sci config list devices <technique>`

List all device names configured for a specific technique.

### `sci config set technique <name> <device>`

Set the default device for a technique. Creates `~/.config/science-cli/techniques/<name>.yaml`.

**Alias:** `sci config set techniques <name> <device>`

**Validates device name** against known devices (warning if unknown, but still writes).

### `sci config edit <technique> [--force]`

Open per-technique config in `$EDITOR`. With `--force`, overwrite existing file with template.

**Generated template includes:**
1. Filename pattern regexes
2. Default device (commented)
3. Device definitions with delimiter, decimal, header_lines, encoding, columns
4. Customization stub

### `sci config edit techniques --global`

Edit the global technique registry section (`techniques:`) in `~/.config/science-cli/config.yaml`.

---

## 6. INSTRUMENT Subcommands

### `sci config devices list`

List all devices in the global device registry. Combines hardcoded + user-defined.

**Built-in Devices:**

| Device | Label | Delimiter | Header Lines | Column Roles |
|--------|-------|-----------|-------------|--------------|
| `keithley-2400` | Keithley 2400 SourceMeter | `\t` | 23 | current, time, voltage |
| `keysight-b1500` | Keysight B1500A | `,` | 48 | current, time, voltage |
| `keysight-b1500a` | Keysight B1500A Clarius | `,` | 245 | current, time, voltage |
| `horiba-usth` | Horiba LabRAM HR Evolution | `\t` | 45 | shift, intensity |
| `iop-hanoi` | UV-Vis Spectrometer (IOP Hanoi) | `,` | 1 | transmittance, wavelength |
| `biologic` | Biologic Potentiostat | (mpt format) | (auto) | potential, current, time |

### `sci config edit devices`

Open the devices section of the global config for editing.

### Built-in Instrument Registry (via `sci instrument`)

| Instrument | Type | Techniques |
|------------|------|------------|
| `keithley-2400` | sourcemeter | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance |
| `keysight-b1500a` | parameter-analyzer | iv-sweep, iv-breakdown, iv-leakage, pulse-endurance, pulse-stp, pulse-ppf |
| `biologic` | potentiostat | ec-cv, ec-ca, ec-eis |
| `horiba-usth` | raman-spectrometer | raman |
| `iop-hanoi` | uv-vis-spectrometer | uv-vis |

---

## 7. GRAMMAR Subcommands — 5-Tier Grammar System

### Grammar Resolution Tiers

```
Tier 1: Hardcoded Grammar Fallback (core/technique.py HARDCODED_GRAMMAR)
  ─ Catch-all regex: date_code, material, technique, matrix, suffix
    │ overridden by
    ▼
Tier 2: Device-Type Grammar (config.yaml → file_naming.device_types)
  ─ memristor (crossbar-rNcN), junction (junction-basic), deposition (deposition-basic)
    │ overridden by
    ▼
Tier 3: Global Config Grammar (config.yaml → file_naming.patterns)
  ─ Standard conventions: rNcN, bN-tN
    │ overridden by
    ▼
Tier 4: Project-Level Grammar (sci-config.yaml → file_naming.patterns)
  ─ Per-project naming convention overrides
    │ overridden by
    ▼
Tier 5: Protocol-Level Grammar (protocol/<name>.yaml → grammar:)
  ─ Highest priority. Per-protocol custom patterns.
```

### `sci config list grammar [--device-type <type>|--protocol <name>]`

List configured grammar patterns in a 3-column table (ID, Template, Fields).

**Flags:**
- `--device-type <type>`: Show device-type grammar (memristor, junction, deposition)
- `--protocol <name>`: Show protocol-level grammar section

### `sci config edit grammar [--device-type <type>|--protocol <name>]`

Edit grammar patterns in `$EDITOR`.

| Scope | Target File |
|-------|-------------|
| None | Global config `file_naming:` section |
| `--device-type <type>` | Global config `file_naming.device_types.<type>` |
| `--protocol <name>` | Protocol YAML `grammar:` section |

### `sci config grammar test <filename>`

Test a filename against the merged grammar and print parsed fields. Use for debugging custom patterns.

```
sci config grammar test "140526_Ta-PDA-ITO_r0c0_iv_01.csv"
# ┌────────────┬──────────────────┐
# │ Field      │ Value            │
# ├────────────┼──────────────────┤
# │ date_code  │ 140526           │
# │ material   │ Ta-PDA-ITO       │
# │ technique  │ iv               │
# │ matrix     │ r0c0             │
# │ suffix     │ 1                │
# └────────────┴──────────────────┘
```

### Universal Grammar Fields

| Field | Description | Example |
|-------|-------------|---------|
| `date_code` | DDMMYY or YYYYMMDD | `140526`, `20240526` |
| `material` | Device/material name | `Ta-PDA-ITO` |
| `technique` | Measurement technique code | `iv`, `raman` |
| `matrix` | Crossbar position | `r0c0`, `b1-t1` |
| `suffix` | Order/cycle number | `01`, `001` |
| `batch` | Batch number (optional) | `2` |
| `type` | Measurement type | `uc` (unipolar), `dc` |
| `bot`, `top` | bN-tN electrode indices | `1`, `3` |
| `row`, `col` | Derived numeric indices | `0`, `0` |

**Separator:** ALWAYS `_` (underscore) — hardcoded, not configurable.

### Device-Type Grammar Patterns

**memristor (crossbar-rNcN):**
```yaml
template: "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}"
```
Matches: `140526_Ta-PDA-ITO_2_r0c0_iv_uc_01.csv`

**junction (junction-basic):**
```yaml
template: "{date_code}_{material}_{technique}_{suffix?}"
```
Matches: `140526_Ta-PDA-ITO_iv_01.csv` (no matrix coords)

**deposition (deposition-basic):**
```yaml
template: "{date_code}_{material}_{technique}_{suffix?}"
```
Same as junction, for deposition/process records.

---

## 8. Device Config Format

Each device configuration in the YAML follows this structure:

```yaml
<device-slug>:
  label: "Human-readable name"
  delimiter: "\t"            # Column separator
  decimal: "."               # Decimal separator
  header_lines: 23           # Lines to skip before data
  encoding: "utf-8"          # File encoding
  columns:                   # Column role → name mapping
    voltage: "Untitled"
    current: "Untitled 1"
    time: "Untitled 2"
  names: [shift, intensity]  # Alternative: column names for headerless files
```

### Column Role Mappings

| Role | Used By | Description |
|------|---------|-------------|
| `voltage` | iv-sweep, pulse-* | Voltage/BIAS column |
| `current` | iv-sweep, pulse-* | Current/MEAS column |
| `time` | iv-sweep, pulse-* | Time column |
| `frequency` | ec-eis | Frequency column |
| `z_real` | ec-eis | Real impedance |
| `z_imag` | ec-eis | Imaginary impedance |
| `potential` | ec-cv, ec-ca | Electrode potential |
| `wavelength` | uv-vis | Wavelength |
| `transmittance` | uv-vis | Transmission |

### Device Config Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `delimiter` | string | auto-detect | Column separator (`\t`, `,`, `;`) |
| `decimal` | string | `.` | Decimal separator (`.` or `,`) |
| `header_lines` | int | `0` | Lines to skip before data |
| `encoding` | string | `utf-8` | File encoding (utf-8, latin1, cp1252) |
| `columns` | dict | `{}` | Column role → name mapping |
| `names` | list | — | Column names for headerless files |
| `label` | string | — | Human-readable device label |

---

## 9. Common Config Patterns for AI Agents

### Adding a New Device

```bash
# 1. Open device registry in editor
sci config edit devices

# 2. Set as default for a technique
sci config set technique iv-sweep my-new-device

# 3. Verify
sci config list devices iv-sweep
```

### Creating a Custom Grammar Pattern

```bash
# 1. Edit per-protocol grammar (requires open project + protocol)
sci config edit grammar --protocol 1_iv-test

# 2. Test against actual filenames
sci config grammar test "240526_MyProject_iv_01.csv"

# 3. Verify in listing
sci config list grammar --protocol 1_iv-test
```

### Switching Themes for a Session

```bash
# List available
sci config theme list

# Set for session
sci config theme set poster     # Conference
sci config theme set tufte      # Minimal
sci config theme set publication-nature  # Default journal
```

### Per-Technique Device Override

```bash
# Set Keithley as default for IV sweep
sci config set technique iv-sweep keithley-2400

# Edit full technique config (patterns, devices, defaults)
sci config edit iv-sweep
```

### Viewing the Full Effective Config

```bash
sci config show                # Merged config
sci config show --global       # Global only
sci config show --project      # Project only
```
