# Core Library (`src/science_cli/core/`)

## Module Roles

| Module | Purpose | CLI-dependent? |
|--------|---------|----------------|
| `config.py` | **Device-aware config system** — merges hardcoded/global/project configs | No |
| `data_loader.py` | File → DataFrame with device-aware loading | No |
| `technique.py` | Technique detection from filename patterns (config + extensions + hardcoded) | No |
| `project.py` | Project path resolution, listing, status | No |
| `session.py` | Session state (JSON) — theme, project, protocol, history | No |
| `paths.py` | ProjectPaths — canonical directory layout resolution | No |
| `protocol.py` | Protocol YAML management | No |
| `sweep_metadata.py` | IV sweep segment auto-detection (forward/reverse) | No |
| `file_utils.py` | File I/O helpers | No |
| `fzf_utils.py` | fzf integration for file selection | No |
| `legacy.py` | Backward-compatibility shims | No |
| `manifest.py` | Manifest management | No |

**Core modules must never import from `cli/` or `plot/`.** They are the
foundation layer — CLI and plot depend on core, not the reverse.

## Session Lifecycle

```
sci project open <name>
    → set_last_project(name)        # writes to session.json
    → clears last_protocol, last_step

sci open -m protocol -n <name>
    → set_last_protocol(name)       # writes to session.json

sci close -m protocol
    → clear_last_protocol()         # clears last_protocol, last_step

sci config theme set <name>
    → set_active_theme(name)        # writes to session.json
```

Session file: `~/.config/science-cli/session.json`

## Config System Architecture

```
Hardcoded defaults (core/config.py::_DEFAULT_*)
       ↓ overwritten by
Global config (~/.config/science-cli/config.yaml)
       ↓ overwritten by  
Per-project config (<project_root>/sci-config.yaml)
       ↓
Merged config (get_merged_config())
```

### Typed Accessors

Use these instead of reading raw YAML:

```python
from science_cli.core.config import (
    get_device_config,       # → dict with delimiter, decimal, encoding, columns
    get_technique_patterns,  # → list of regex patterns
    get_default_device,      # → device name string
    get_projects_root,       # → Path
    get_header_marker,       # → header marker string
    get_merged_config,       # → full merged dict (for debugging)
    invalidate_cache,        # → clear all caches
)
```

### Device Config Schema

Devices are scoped to techniques. A device can appear under multiple techniques:

```yaml
techniques:
  ec-eis:
    patterns: ["*EIS*", "*.mpt"]
    header_marker: "Frequency"
    devices:
      biologic-mpt:
        delimiter: "\t"
        decimal: ","
        header_lines: 1
        encoding: "latin-1"
        columns:
          frequency: "freq"
          z_real: "Re(Z)"
          z_imag: "-Im(Z)"
  ec-cv:
    patterns: ["*CV*"]
    devices:
      biologic-mpt:         # same device, different technique
        delimiter: "\t"
        decimal: ","
        header_lines: 1
        encoding: "latin-1"
        columns:
          potential: "Ewe/V"
          current: "I/mA"

defaults:
  ec-eis: biologic-mpt
  ec-cv: biologic-mpt
```

**Note:** Config is additive, never replacement. All hardcoded defaults remain as
fallbacks when no config file exists.

## Data Loading Flow

```
load_data_file(filepath, technique="", device="")
    │
    ├─ technique + device provided?
    │   └─ YES → _resolve_device_config() → _load_with_device_config()
    │       Uses device cfg for: delimiter, decimal, header_lines, encoding, columns
    │
    └─ NO → extension-based auto-detection
        .mpt → _load_mpt()   (Biologic EIS, tab-separated, latin-1)
        .csv → _load_csv()   (comma-separated, utf-8)
        .txt → _load_txt()   (auto-detect delimiter)
        .xlsx→ _load_excel()
```
