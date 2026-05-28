"""Device-aware configuration system — merges hardcoded defaults, global config,
and per-project overrides. Provides typed accessors for device loading parameters.

Config resolution order (last wins):
    1. Hardcoded defaults (in this module)
    2. Global config:  ~/.config/science-cli/config.yaml
    3. Per-project:    <project_root>/sci-config.yaml

The techniques section is organized as:

    techniques:
      <technique-slug>:
        patterns:           # filename patterns for technique detection
        header_marker:      # string that signals the data header row
        devices:
          <device-slug>:
            delimiter:      # CSV delimiter
            decimal:        # decimal separator
            header_lines:   # lines to skip before data
            encoding:       # file encoding
            columns:        # column name mappings

    defaults:
      <technique-slug>: <device-slug>   # preferred device per technique

A device can appear under multiple techniques (e.g., biologic-mpt under both
ec-eis and ec-cv) with potentially different settings per technique.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ── Hardcoded defaults — never removed, always fall back ───────────────

_DEFAULT_DEVICE = {
    "delimiter": None,          # None = auto-detect
    "decimal": ".",
    "header_lines": 0,
    "encoding": "utf-8",
    "columns": {},
}

# Built-in technique patterns — used when no config exists
_DEFAULT_TECHNIQUE_PATTERNS: dict[str, list[str]] = {
    "ec-cv": [r"_CV\.", r"\.cv$", r"cv_", r"cv-"],
    "ec-ca": [r"_CA\.", r"\.ca$", r"ca_", r"ca-"],
    "ec-eis": [r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"],
    "ec-lsv": [r"_LSV\.", r"\.lsv$"],
    "ec-swv": [r"_SWV\.", r"\.swv$"],
    "iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"],
    "iv-breakdown": [r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"],
    "iv-leakage": [r"_leak", r"leakage_", r"leak_"],
    "mem-endurance": [r"_endurance", r"\.end", r"end_", r"endurance", r"-endurance"],
    "mem-retention": [r"_retention", r"\.ret", r"ret_", r"retention", r"-retention"],
    "mem-switching": [r"_switch", r"\.sw", r"sw_", r"switch_", r"-switch"],
    "raman": [r"_raman", r"_sers", r"_raman-sers", r"_SERS"],
    "uv-vis": [r"_uv-vis", r"_uvvis", r"uv-vis", r"uvvis"],
}

_DEFAULT_TECHNIQUE_DEVICES: dict[str, dict[str, dict]] = {
    "iv-sweep": {
        "keithley-2400": {
            "delimiter": "\t",
            "decimal": ".",
            "header_lines": 23,
            "encoding": "utf-8",
            "columns": {
                "voltage": "Untitled",
                "current": "Untitled 1",
                "time": "Untitled 2",
            },
        },
    },
    "raman": {
        "horiba-usth": {
            "label": "Horiba LabRAM HR Evolution (USTH)",
            "delimiter": "\t",
            "decimal": ",",
            "header_lines": 45,
            "encoding": "latin1",
            "names": ["shift", "intensity"],
        },
    },
    "uv-vis": {
        "iop-hanoi": {
            "label": "UV-Vis Spectrometer (IOP Hanoi)",
            "delimiter": ",",
            "decimal": ".",
            "header_lines": 1,
            "encoding": "latin1",
            "columns": {
                "wavelength": "Wavelength nm.",
                "transmittance": "T%",
            },
        },
    },
}

_DEFAULT_PROJECTS_ROOT = str(Path.home() / "workspace" / "projects" / "active_projects")


# ── Cache ──────────────────────────────────────────────────────────────

# Global config cache — loaded once, invalidated when file changes
_global_config: dict | None = None
_global_config_mtime: float = 0.0

# Per-project config cache — keyed by project root path
_project_config_cache: dict[str, dict] = {}

# Technique config cache
_technique_configs_cache: dict[str, dict] | None = None
_technique_configs_mtime: float = 0.0


# ── File paths ─────────────────────────────────────────────────────────

def _global_config_path() -> Path:
    """Return path to the global config file."""
    return Path.home() / ".config" / "science-cli" / "config.yaml"


def _project_config_path(project_root: Path) -> Path:
    """Return path to the per-project config file."""
    return project_root / "sci-config.yaml"


def _technique_configs_dir() -> Path:
    """Return directory for per-technique YAML config files."""
    return Path.home() / ".config" / "science-cli" / "techniques"


# ── Loading ────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning {} if it doesn't exist or is unreadable."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def load_global_config() -> dict:
    """Load the global config, caching it until the file changes."""
    global _global_config, _global_config_mtime
    path = _global_config_path()
    if path.exists():
        mtime = path.stat().st_mtime
        if _global_config is not None and mtime == _global_config_mtime:
            return _global_config
        _global_config_mtime = mtime
    _global_config = _load_yaml(path)
    return _global_config


def load_project_config(project_root: Path) -> dict:
    """Load per-project sci-config.yaml, cached by project root."""
    cache_key = str(project_root.resolve())
    if cache_key in _project_config_cache:
        return _project_config_cache[cache_key]
    cfg = _load_yaml(_project_config_path(project_root))
    _project_config_cache[cache_key] = cfg
    return cfg


def load_technique_configs() -> dict[str, dict]:
    """Load all per-technique YAML config files from ~/.config/science-cli/techniques/*.yaml.

    Returns a dict keyed by technique name. Each value is the parsed YAML content.
    Cached until file mtimes change.
    """
    global _technique_configs_cache, _technique_configs_mtime
    tech_dir = _technique_configs_dir()
    if not tech_dir.exists():
        return {}

    # Check cache validity using sum of file mtimes
    current_mtime = 0.0
    for f in tech_dir.glob("*.yaml"):
        current_mtime += f.stat().st_mtime

    if _technique_configs_cache is not None and current_mtime == _technique_configs_mtime:
        return _technique_configs_cache

    _technique_configs_mtime = current_mtime
    configs: dict[str, dict] = {}
    for yaml_file in sorted(tech_dir.glob("*.yaml")):
        tech_name = yaml_file.stem
        data = _load_yaml(yaml_file)
        if data:
            configs[tech_name] = data

    _technique_configs_cache = configs
    return configs


def invalidate_cache() -> None:
    """Clear all config caches (useful after config writes)."""
    global _global_config, _global_config_mtime
    global _technique_configs_cache, _technique_configs_mtime
    _global_config = None
    _global_config_mtime = 0.0
    _technique_configs_cache = None
    _technique_configs_mtime = 0.0
    _project_config_cache.clear()


# ── Merged access ──────────────────────────────────────────────────────

def _merge_dicts(base: dict, *overrides: dict) -> dict:
    """Deep-merge dicts: later values win for leaf keys, nested dicts merge."""
    result = base.copy()
    for override in overrides:
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _merge_dicts(result[key], value)
            else:
                result[key] = value
    return result


def get_merged_config(project_root: Path | None = None) -> dict:
    """Return the fully merged configuration.

    Resolution: hardcoded defaults ← global config ← technique configs ← project config
    """
    base: dict[str, Any] = {
        "projects_root": _DEFAULT_PROJECTS_ROOT,
        "techniques": {},
        "defaults": {},
    }
    global_cfg = load_global_config()
    merged = _merge_dicts(base, global_cfg)

    # Layer technique configs on top of global config
    tech_configs = load_technique_configs()
    if tech_configs:
        # Wrap into techniques section for merging
        merged = _merge_dicts(merged, {"techniques": tech_configs})

    if project_root is not None:
        project_cfg = load_project_config(project_root)
        merged = _merge_dicts(merged, project_cfg)
    return merged


# ── Typed accessors ────────────────────────────────────────────────────

def get_technique_patterns(
    technique: str,
    project_root: Path | None = None,
) -> list[str]:
    """Return filename patterns for a technique.

    Checks config first, falls back to hardcoded defaults.
    Config patterns are prepended (take priority) before hardcoded ones.
    """
    config = get_merged_config(project_root)
    tech_section = config.get("techniques", {}).get(technique, {})
    config_patterns = tech_section.get("patterns", [])

    hardcoded = _DEFAULT_TECHNIQUE_PATTERNS.get(technique, [])
    # Config patterns prepended so they take priority in regex matching
    merged = [p for p in config_patterns if p not in hardcoded]
    merged.extend(hardcoded)
    return merged


def get_device_config(
    technique: str,
    device_name: str,
    project_root: Path | None = None,
) -> dict:
    """Return device loading config, or None if not found.

    Returns a dict with: delimiter, decimal, header_lines, encoding, columns.
    Falls back gracefully: missing keys use _DEFAULT_DEVICE defaults.
    """
    config = get_merged_config(project_root)
    tech_section = config.get("techniques", {}).get(technique, {})
    devices = tech_section.get("devices", {})

    device_cfg = devices.get(device_name, None)
    if device_cfg is None:
        # Fallback to hardcoded built-in device configs
        builtin_devices = _DEFAULT_TECHNIQUE_DEVICES.get(technique, {})
        device_cfg = builtin_devices.get(device_name, None)
        if device_cfg is None:
            return None

    # Overlay with global device registry (config.yaml → devices:)
    # so user's global overrides (e.g. header_lines) take effect.
    global_cfg = load_global_config()
    global_devices = global_cfg.get("devices", {})
    global_device_cfg = global_devices.get(device_name)
    if global_device_cfg:
        device_cfg = _merge_dicts(device_cfg, global_device_cfg)

    # Check per-project devices.yaml for overrides
    if project_root is not None and device_cfg is not None:
        project_devices_path = project_root / "devices.yaml"
        if project_devices_path.exists():
            project_devices = _load_yaml(project_devices_path)
            if device_name in project_devices:
                device_cfg = _merge_dicts(device_cfg, project_devices[device_name])

    # Merge with defaults so callers don't need to check every key
    merged = _DEFAULT_DEVICE.copy()
    merged.update(device_cfg)
    return merged


def get_default_device(
    technique: str,
    project_root: Path | None = None,
) -> str:
    """Return the preferred default device name for a technique, or ''."""
    config = get_merged_config(project_root)
    defaults = config.get("defaults", {})
    return defaults.get(technique, "")


def get_projects_root() -> Path:
    """Return the configured projects root directory path."""
    cfg = get_merged_config()
    return Path(cfg["projects_root"]).expanduser().resolve()


def get_data_path(project_root: Path) -> Path:
    """Return the data directory path for a project (reads from config if set)."""
    cfg = get_merged_config(project_root)
    data_subdir = cfg.get("data_path", "data/raw")
    return project_root / data_subdir


def get_header_marker(
    technique: str,
    project_root: Path | None = None,
) -> str:
    """Return the header marker string for a technique (e.g. 'Frequency', 'Voltage')."""
    config = get_merged_config(project_root)
    tech_section = config.get("techniques", {}).get(technique, {})
    return tech_section.get("header_marker", "")


def get_technique_config(
    technique: str,
    project_root: Path | None = None,
) -> dict | None:
    """Return the full technique config dict from merged config, or None if not found.

    Includes patterns, devices, header_marker, etc. from all config layers.
    Does NOT include technique-specific defaults (use get_default_device for that).
    """
    config = get_merged_config(project_root)
    tech_section = config.get("techniques", {}).get(technique, {})
    if not tech_section:
        return None
    return dict(tech_section)


def get_plot_labels(
    technique: str,
    project_root: Path | None = None,
) -> dict[str, str]:
    """Return per-technique plot labels from config, or empty dict.

    Reads from the ``plot.labels.<technique>`` section of the merged config.

    Example config.yaml::

        plot:
          labels:
            uv-vis:
              xlabel: "Wavelength (nm)"
              ylabel: "Transmission (%)"

    Resolution chain at runtime::
        CLI --xlabel/--ylabel > config > column detection > template default
    """
    config = get_merged_config(project_root)
    return dict(config.get("plot", {}).get("labels", {}).get(technique, {}))


def get_file_naming_patterns(project_root: Path | None = None) -> list[dict]:
    """Return file naming pattern configs from merged config.

    Returns list of pattern dicts with keys: template, description, regex, fields.
    Falls back to empty list if no naming grammar configured.

    Universal grammar fields (standardized across all projects/techniques/devices):
        - ``date_code``: Date in DDMMYY or YYYYMMDD format
        - ``material``: Material/device name (primary field)
        - ``technique``: Measurement technique code
        - ``matrix``: Crossbar addressing (rNcN, bN-tN)
        - ``suffix``: Order/cycle number (zero-padded integer)
    """
    config = get_merged_config(project_root)
    naming = config.get("file_naming", {})
    patterns = naming.get("patterns", [])
    return patterns


def get_file_naming_grammar(project_root: Path | None = None) -> dict:
    """Return the file naming grammar configuration.

    Returns dict with keys: separator, patterns (list of pattern dicts).
    Each pattern dict has: template, description, regex, fields.
    Falls back to empty dict with no patterns if not configured.
    """
    config = get_merged_config(project_root)
    naming = config.get("file_naming", {})
    return {
        "separator": "_",  # HARDCODED — never configurable
        "patterns": naming.get("patterns", []),
    }


def get_device_config_detail(
    technique: str,
    device_name: str,
    project_root: Path | None = None,
) -> dict | None:
    """Return the RAW device config dict with ALL details, NOT merged with defaults.

    Unlike get_device_config(), this returns the config exactly as specified
    in YAML or hardcoded defaults — no _DEFAULT_DEVICE fallback fill-in.
    Use this when displaying config to users so they see only what's configured.
    """
    config = get_merged_config(project_root)
    tech_section = config.get("techniques", {}).get(technique, {})
    devices = tech_section.get("devices", {})

    device_cfg = devices.get(device_name, None)
    if device_cfg is None:
        # Fallback to hardcoded built-in device configs (raw, no defaults merged)
        builtin_devices = _DEFAULT_TECHNIQUE_DEVICES.get(technique, {})
        device_cfg = builtin_devices.get(device_name, None)
        if device_cfg is None:
            return None

    # Check per-project devices.yaml for overrides
    if project_root is not None and device_cfg is not None:
        project_devices_path = project_root / "devices.yaml"
        if project_devices_path.exists():
            project_devices = _load_yaml(project_devices_path)
            if device_name in project_devices:
                device_cfg = _merge_dicts(device_cfg, project_devices[device_name])

    return dict(device_cfg)


# ── Global device/technique registry accessors ──────────────────────────


def get_global_device_config(device_name: str) -> dict | None:
    """Look up a device config from the global config's ``devices:`` registry.

    Resolution order:
        1. Start with hardcoded default global devices
        2. Overlay with global config (~/.config/science-cli/config.yaml → devices:)
        3. Return merged result or None if not found in either

    Returns dict with: delimiter, decimal, header_lines, encoding, columns
    or None if not found.
    """
    # Start with hardcoded defaults as base
    cfg = dict(_DEFAULT_GLOBAL_DEVICES.get(device_name, {}))

    # Overlay with user's global config.yaml
    global_cfg = load_global_config()
    devices_section = global_cfg.get("devices", {})
    user_cfg = devices_section.get(device_name)
    if user_cfg:
        cfg.update(user_cfg)

    return cfg if cfg else None


def list_global_devices() -> list[str]:
    """List all device names in the global registry.

    Combines hardcoded defaults and global config.
    """
    names: set[str] = set(_DEFAULT_GLOBAL_DEVICES.keys())
    global_cfg = load_global_config()
    devices_section = global_cfg.get("devices", {})
    names.update(devices_section.keys())
    return sorted(names)


def get_global_technique_config(technique_name: str) -> dict | None:
    """Look up a technique config from the global registry.

    Resolution order:
        1. Start with hardcoded default technique configs
        2. Overlay with global config (~/.config/science-cli/config.yaml → techniques:)

    Returns dict with: patterns, label, grammar_codes, types, default_device
    or None if not found.
    """
    cfg = dict(_DEFAULT_GLOBAL_TECHNIQUES.get(technique_name, {}))
    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {})
    user_cfg = tech_section.get(technique_name)
    if user_cfg:
        cfg.update(user_cfg)
    return cfg if cfg else None


def resolve_technique_from_grammar(
    grammar_code: str, project_root: Path | None = None
) -> str | None:
    """Map a grammar code (e.g. 'iv', 'iv-sweep', 'iv_dc') to a technique config key.

    Checks:
        1. Global technique registry (hardcoded + config.yaml) for grammar_codes match
        2. Direct technique name match as fallback
    Returns the technique key (e.g. 'iv-sweep') or None.
    """
    # Collect all technique configs from hardcoded + global config
    techs: dict[str, dict] = dict(_DEFAULT_GLOBAL_TECHNIQUES)
    global_cfg = load_global_config()
    for key, val in global_cfg.get("techniques", {}).items():
        if key in techs:
            techs[key].update(val)
        else:
            techs[key] = val

    for tech_name, tech_cfg in techs.items():
        codes = tech_cfg.get("grammar_codes", [])
        if grammar_code in codes or grammar_code == tech_name:
            return tech_name
    return None


def list_global_techniques() -> list[str]:
    """List all technique names in the global registry.

    Combines hardcoded defaults and global config.
    """
    names: set[str] = set(_DEFAULT_GLOBAL_TECHNIQUES.keys())
    names.update(_DEFAULT_TECHNIQUE_PATTERNS.keys())
    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {})
    names.update(tech_section.keys())
    return sorted(names)


# Hardcoded default global devices (the "built-in library")
_DEFAULT_GLOBAL_DEVICES: dict[str, dict] = {
    "keithley-2400": {
        "label": "Keithley 2400 SourceMeter",
        "delimiter": "\t",
        "decimal": ".",
        "header_lines": 23,
        "encoding": "utf-8",
        "columns": {
            "voltage": "Untitled",
            "current": "Untitled 1",
            "time": "Untitled 2",
        },
    },
    "keysight-b1500": {
        "label": "Keysight B1500A Semiconductor Analyzer",
        "delimiter": ",",
        "header_lines": 48,
        "columns": {
            "voltage": "BV",
            "current": "BI",
            "time": "Time",
        },
    },
    "horiba-usth": {
        "label": "Horiba LabRAM HR Evolution (USTH)",
        "delimiter": "\t",
        "decimal": ",",
        "header_lines": 45,
        "encoding": "latin1",
        "names": ["shift", "intensity"],
    },
}

# Hardcoded default global technique configs
_DEFAULT_GLOBAL_TECHNIQUES: dict[str, dict] = {
    "iv-sweep": {
        "label": "IV Sweep",
        "grammar_codes": ["iv", "IV", "iv-sweep", "iv_dc"],
        "default_device": "keithley-2400",
        "types": {
            "forming": {"label": "Forming", "step_type": "forming"},
            "set": {"label": "Set", "step_type": "set"},
            "reset": {"label": "Reset", "step_type": "reset"},
        },
    },
    "iv-breakdown": {
        "label": "Breakdown",
        "grammar_codes": ["bd", "breakdown"],
        "default_device": "keithley-2400",
    },
    "iv-leakage": {
        "label": "Leakage",
        "grammar_codes": ["leak", "leakage"],
        "default_device": "keithley-2400",
    },
    "raman": {
        "label": "Raman Spectroscopy",
        "grammar_codes": ["raman", "sers", "raman-sers"],
        "default_device": "horiba-usth",
    },
    "uv-vis": {
        "label": "UV-Vis Transmittance",
        "grammar_codes": ["uv-vis", "uvvis", "uv_vis"],
        "default_device": "iop-hanoi",
    },
}


# ── Config generation (for config init) ────────────────────────────────

def generate_default_config_yaml() -> str:
    """Generate a YAML string with all sections documented and commented.

    Used by `sci config init` to create a starter config file.
    """
    return """\
# science-cli configuration
# ========================
# ~/.config/science-cli/config.yaml
#
# This file is merged with hardcoded defaults.  Per-project
# sci-config.yaml files override these settings.
#
# 4-tier resolution order:
#   1. Hardcoded defaults (core/config.py)
#   2. Global config (~/.config/science-cli/config.yaml)  <- THIS FILE
#   3. Per-project config (<project>/sci-config.yaml)
#   4. Per-protocol metadata (protocol/<name>/...)

# Root directory for all projects
projects_root: "{projects_root}"
# Preferred theme (publication-nature, publication-acs, matcha, tufte, dark, poster)
theme: publication-nature

# Default figure output settings
default_dpi: 300
default_figure_format: pdf

# --- File Naming Grammar ---
# Defines how filenames are parsed into universal fields.
# Separator is ALWAYS _ (underscore) -- not configurable.
#
# Universal grammar fields (standardized):
#   - date_code: Date in DDMMYY or YYYYMMDD format
#   - material: Material/device name (primary field)
#   - technique: Measurement technique code
#   - matrix: Crossbar addressing (rNcN, bN-tN)
#   - suffix: Order/cycle number (zero-padded integer)

file_naming:
  patterns:
    - id: rNcN
      template: "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}"
      description: "Standard rNcN convention (rectangular crossbar)"
      regex: '^(?P<date_code>\\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\\d+))?_(?P<matrix>r\\d+c\\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\\d+))?\\.\\w+$'
    - id: bN-tN
      template: "{date_code}_{material}{batch?}_b{bot}-t{top}_{technique}_{type?}_{suffix?}"
      description: "Bottom/top crossbar convention"
      regex: '^(?P<date_code>\\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\\d+))?_b(?P<bot>\\d+)-t(?P<top>\\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\\d+))?\\.\\w+$'

# --- Device Registry ---
# Global device configurations shared across all projects.
# Add a new instrument here once, use it everywhere.

devices:
  keithley-2400:
    label: "Keithley 2400 SourceMeter"
    delimiter: "\\t"
    decimal: "."
    header_lines: 23
    encoding: "utf-8"
    columns:
      voltage: "Untitled"
      current: "Untitled 1"
      time: "Untitled 2"
  keysight-b1500:
    label: "Keysight B1500A Semiconductor Analyzer"
    delimiter: ","
    header_lines: 48
    columns:
      voltage: "BV"
      current: "BI"
      time: "Time"
  horiba-usth:
    label: "Horiba LabRAM HR Evolution (USTH)"
    delimiter: "\\t"
    decimal: ","
    header_lines: 45
    encoding: "latin1"
    names: ["shift", "intensity"]
  iop-hanoi:
    label: "UV-Vis Spectrometer (IOP Hanoi)"
    delimiter: ","
    decimal: "."
    header_lines: 1
    encoding: "latin1"
    columns:
      wavelength: "Wavelength nm."
      transmittance: "T%"

# --- Technique Registry ---
# Global technique definitions shared across all projects.
# Each technique can reference a default device from the devices registry.

techniques:
  iv-sweep:
    label: "IV Sweep"
    grammar_codes: ["iv", "IV", "iv-sweep", "iv_dc"]
    default_device: keithley-2400
    types:
      forming: { label: "Forming", step_type: forming }
      set: { label: "Set", step_type: set }
      reset: { label: "Reset", step_type: reset }

  raman:
    label: "Raman Spectroscopy"
    grammar_codes: ["raman", "sers", "raman-sers"]
    default_device: horiba-usth
  uv-vis:
    label: "UV-Vis Transmittance"
    grammar_codes: ["uv-vis", "uvvis", "uv_vis"]
    default_device: iop-hanoi

# --- Default device per technique ---
# When no device is specified, use this device for the technique.
defaults:
  iv-sweep: keithley-2400
  raman: horiba-usth
  uv-vis: iop-hanoi
""".replace("{projects_root}", _DEFAULT_PROJECTS_ROOT)


def write_technique_config(technique: str, data: dict) -> Path:
    """Write a technique config YAML file to ~/.config/science-cli/techniques/<technique>.yaml.

    Creates the directory if it doesn't exist. Invalidates caches after write.
    Returns the path to the written file.
    """
    tech_dir = _technique_configs_dir()
    tech_dir.mkdir(parents=True, exist_ok=True)
    path = tech_dir / f"{technique}.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    invalidate_cache()
    return path


def list_technique_names() -> list[str]:
    """List all known technique names from all sources.

    Combines: technique config files, global config techniques, and hardcoded defaults.
    """
    names: set[str] = set()

    # From technique config files
    tech_configs = load_technique_configs()
    names.update(tech_configs.keys())

    # From global config
    global_cfg = load_global_config()
    names.update(global_cfg.get("techniques", {}).keys())

    # From hardcoded defaults
    names.update(_DEFAULT_TECHNIQUE_PATTERNS.keys())

    return sorted(names)


def list_technique_devices(technique: str) -> list[str]:
    """List device names configured for a given technique.

    Checks: technique config files, global config, and hardcoded defaults.
    """
    devices: set[str] = set()

    # From technique config files
    tech_configs = load_technique_configs()
    if technique in tech_configs:
        devices.update(tech_configs[technique].get("devices", {}).keys())

    # From global config
    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {}).get(technique, {})
    devices.update(tech_section.get("devices", {}).keys())

    # From hardcoded defaults
    devices.update(_DEFAULT_TECHNIQUE_DEVICES.get(technique, {}).keys())

    return sorted(devices)
