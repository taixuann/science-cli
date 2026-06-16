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
| `fzf_utils.py` | fzf integration for file selection via `script -q` PTY; falls back to numbered-list if fzf unavailable | No |
| `legacy.py` | Backward-compatibility shims | No |
| `manifest.py` | Manifest management | No |
| `parquet_store.py` | Parquet storage for processed analysis data (write/read/append features) | No |

**Core modules must never import from `cli/` or `plot/`.** They are the
foundation layer — CLI and plot depend on core, not the reverse.

## fzf Integration

`fzf_utils.py` provides interactive file selection powered by [fzf](https://github.com/junegunn/fzf). fzf renders its UI on stderr (or directly to `/dev/tty`) and writes the selected item(s) to stdout. The implementation uses `subprocess.Popen`:

1. fzf is launched via `subprocess.Popen` with piped stdin/stdout
2. Items are written to stdin via `proc.communicate(input=input_text)`
3. Selected item(s) are read from stdout — clean, no ANSI stripping needed
4. If fzf is unavailable or fails, falls back to `_fallback_select()` (numbered list)

**Unix (`/dev/tty` approach)**: fzf's stderr is wired to `/dev/tty` via `os.open("/dev/tty", os.O_RDWR)`. This guarantees fzf gets the real controlling terminal regardless of any Textual / asyncio / PTY wrappers around `sys.stdout` or `sys.stderr`. Previous approaches used `script -q` (via PLAN-tui-fzf-pty) and `pty.spawn()` — both required ANSI escape sequence stripping and had platform-specific issues.

**Windows**: `fzf_utils.py` detects the platform and avoids `/dev/tty`. Instead, fzf inherits the parent console directly (`stderr=None`) with `CREATE_NO_WINDOW` flag. This allows fzf to work natively on Windows without WSL.

If fzf is unavailable, `_fallback_select()` presents a simple numbered list. The `SCI_TUI_ACTIVE` env var guard was removed in PLAN-tui-fzf-pty — fzf now works everywhere (CLI, TUI suspend mode via subprocess dispatch, and REPL).

### TUI Subprocess Dispatch

When fzf commands are run inside the Textual TUI, `tui/app.py` stops application mode, launches a separate Python process (`subprocess.run([sys.executable, "-m", "science_cli", ...])`) that has direct access to the real terminal, then re-enters application mode. This avoids all asyncio nesting issues with questionary and fzf.

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
Global config (~/.config/science-cli/config.yaml)     ← device registry, technique templates, grammar
       ↓ overwritten by
Per-project config (<project_root>/sci-config.yaml)    ← type→step mapping, project overrides
       ↓ overwritten by
Per-protocol metadata (protocol/<name>/...)
```

**Note:** The per-technique YAML config files (`~/.config/science-cli/techniques/<technique>.yaml`) were part of an earlier design and have been superseded by the global config approach. All technique settings now live in the global `config.yaml` or per-project `sci-config.yaml`.

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
    write_technique_config,  # → write technique YAML
    list_technique_names,    # → list configured techniques
    list_technique_devices,  # → list devices for a technique
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

**Config merge fix (2026-05-16):** The `get_global_device_config()` and
`get_device_config()` functions now properly merge user config values over
hardcoded defaults:
- `get_global_device_config(device_name)`: starts with hardcoded defaults
  (`_DEFAULT_GLOBAL_DEVICES`), then overlays the user's
  `~/.config/science-cli/config.yaml → devices:` section. Previously it
  returned early from whichever source matched first.
- `get_device_config(technique, device_name)`: after resolving the
  per-technique device config, it now overlays the global device registry
  (from `config.yaml → devices:`) before applying per-project `devices.yaml`
  overrides. Previously the global registry was skipped for per-technique
  lookups.
- **Effect**: a user setting `header_lines: 21` in config.yaml now correctly
  overrides the hardcoded `23` for `keithley-2400`.

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
