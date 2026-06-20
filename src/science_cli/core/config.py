"""Device-aware configuration system — merges hardcoded defaults, global config,
and per-project overrides. Provides typed accessors for device loading parameters.

Config resolution order (lowest → highest priority):
    0. Hardcoded defaults (config_defaults.py data)
    1. Old config.yaml (if exists — backward compat)
    2. config-devices.yaml (studies + device types)
    3. config-instruments.yaml (instrument registry + filename_patterns)
    4. config-template.yaml (theme templates)
    5. Per-project config (sci-config.yaml)
    6. Per-protocol grammar (protocol-level)

All techniques sections (old model) remain backward-compat shims that fall
back to module-level _DEFAULT_* constants if no old config.yaml provides them.
New study-based accessors use the ``studies`` key from modular config files.

Grammar patterns now live in per-instrument ``filename_patterns`` blocks in
config-instruments.yaml (Phase 3). The standalone config-grammar.yaml is deleted.
"""

from __future__ import annotations

from pathlib import Path

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
    "iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"],
    "iv-breakdown": [r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"],
    "iv-leakage": [r"_leak", r"leakage_", r"leak_"],
    "pulse-stp": [r"_stp", r"_STP", r"_stp_decay", r"_short-term"],
    "pulse-ppf": [r"_ppf", r"_PPF", r"_paired-pulse"],
    "raman": [r"_raman", r"_sers", r"_raman-sers", r"_SERS"],
    "uv-vis": [r"_uv-vis", r"_uvvis", r"uv-vis", r"uvvis"],
}

_DEFAULT_PULSE_HEADER_LINES = 147

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
        "keysight-b1500a": {
            "delimiter": ",",
            "decimal": ".",
            "header_lines": 245,
            "encoding": "utf-8",
            "columns": {
                "voltage": "V1",
                "current": "I2",
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
        "spectrometer-iop": {
            "label": "UV-Vis Spectrometer (IOP Hanoi) — vs-770st",
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
    "pulse-stp": {
        "keysight-b1500a": {
            "delimiter": ",",
            "decimal": ".",
            "header_lines": _DEFAULT_PULSE_HEADER_LINES,
            "encoding": "utf-8",
            "columns": {
                "time": "Time",
                "voltage": "MeasResult1_value",
                "current": "MeasResult2_value",
            },
        },
    },
    "pulse-ppf": {
        "keysight-b1500a": {
            "delimiter": ",",
            "decimal": ".",
            "header_lines": _DEFAULT_PULSE_HEADER_LINES,
            "encoding": "utf-8",
            "columns": {
                "time": "Time",
                "voltage": "MeasResult1_value",
                "current": "MeasResult2_value",
            },
        },
    },
}

_DEFAULT_PROJECTS_ROOT = str(Path.home() / "workspace" / "projects" / "active_projects")


# ── Cache ──────────────────────────────────────────────────────────────

# Global config cache — loaded once, invalidated when files change
_global_config: dict | None = None
_global_config_mtime: float = 0.0

# Per-project config cache — keyed by project root path
_project_config_cache: dict[str, dict] = {}

# Technique config cache
_technique_configs_cache: dict[str, dict] | None = None
_technique_configs_mtime: float = 0.0

# ── File paths ─────────────────────────────────────────────────────────


def _global_config_dir() -> Path:
    """Return the global config directory."""
    return Path.home() / ".config" / "science-cli" / "config"


def _global_config_path() -> Path:
    """Return path to the global config file (old monolithic)."""
    return _global_config_dir() / "config.yaml"


def _modular_config_paths() -> dict[str, Path]:
    """Return paths to the modular config files.

    Returns:
        dict with keys: devices, studies, instruments, template
    """
    d = _global_config_dir()
    return {
        "studies": d / "config-studies.yaml",
        "devices": d / "config-devices.yaml",
        "instruments": d / "config-instruments.yaml",
        "template": d / "config-template.yaml",
    }


def _project_config_path(project_root: Path) -> Path:
    """Return path to the per-project config file."""
    return project_root / "sci-config.yaml"


def _technique_configs_dir() -> Path:
    """Return directory for per-technique YAML config files.

    .. deprecated::
        Use modular config files instead. This directory is kept for backward
        compat with scripts that write per-technique overrides.
    """
    return Path.home() / ".config" / "science-cli" / "config" / "techniques"


# ── Loading helpers ────────────────────────────────────────────────────


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


def _sum_mtimes(paths: list[Path]) -> float:
    """Sum mtimes of all paths (files checked, dirs skipped)."""
    total = 0.0
    for p in paths:
        if p.exists():
            try:
                total += p.stat().st_mtime
            except OSError:
                pass
    return total


# ── Defaults source (Layer 0) ──────────────────────────────────────────


def _get_hardcoded_defaults() -> dict:
    """Return dict with ALL hardcoded defaults from config_defaults.py.

    This is Layer 0 — always present, always the lowest priority.
    Studies, device_types, and legacy_to_study are now empty here;
    they come from config-devices.yaml (Layer 2).

    Grammar patterns are now aggregated from per-instrument filename_patterns
    in _INSTRUMENTS (Phase 3).
    """
    from science_cli.core.config_defaults import _INSTRUMENTS  # noqa: I001

    # Build file_naming patterns from per-instrument filename_patterns
    all_patterns: list[dict] = []
    for inst_cfg in _INSTRUMENTS.values():
        all_patterns.extend(inst_cfg.get("filename_patterns", []))

    return {
        "projects_root": _DEFAULT_PROJECTS_ROOT,
        "techniques": {},
        "studies": {},
        "device_types": {},
        "legacy_to_study": {},
        "instruments": dict(_INSTRUMENTS),
        "file_naming": {"separator": "_", "patterns": all_patterns},
        "defaults": {},
        "templates": {
            "publication-nature": {"font": "Helvetica", "fontsize": 7, "dpi": 300},
            "publication-acs": {"font": "Helvetica", "fontsize": 8, "dpi": 600},
        },
    }


# ── Loading ────────────────────────────────────────────────────────────


def load_global_config() -> dict:
    """Load and merge all modular config files.

    Resolution order (lowest → highest priority):
        0. Hardcoded defaults
        1. Old config.yaml (if exists — backward compat)
        2. config-devices.yaml (studies + device types)
        3. config-instruments.yaml (instrument registry + filename_patterns)
        4. config-template.yaml (theme templates)

    Grammar patterns are aggregated from per-instrument filename_patterns
    in the instruments section (Phase 3). The standalone config-grammar.yaml
    is no longer used.

    Cached until file mtimes change.
    """
    global _global_config, _global_config_mtime
    base_dir = _global_config_dir()

    # Collect all config files for cache invalidation
    config_files = [
        base_dir / "config.yaml",
        base_dir / "config-studies.yaml",
        base_dir / "config-devices.yaml",
        base_dir / "config-instruments.yaml",
        base_dir / "config-template.yaml",
    ]
    tech_dir = _technique_configs_dir()

    current_mtime = _sum_mtimes(config_files + [tech_dir])
    if _global_config is not None and current_mtime == _global_config_mtime:
        return _global_config

    _global_config_mtime = current_mtime

    # Layer 0: Start with hardcoded defaults
    merged: dict = _get_hardcoded_defaults()

    # Layer 1: Old config.yaml (backward compat)
    old_path = base_dir / "config.yaml"
    if old_path.exists():
        old_cfg = _load_yaml(old_path)
        if old_cfg:
            merged = _merge_dicts(merged, old_cfg)
            pass  # backward compat

    # Layer 2: config-devices.yaml (device types + legacy mapping + techniques)
    devices_path = base_dir / "config-devices.yaml"
    devices_cfg = _load_yaml(devices_path)
    if devices_cfg:
        merged["device_types"] = devices_cfg.get("device_types", {})
        merged["legacy_to_study"] = devices_cfg.get("legacy_to_study", {})
        if "techniques" in devices_cfg:
            merged["techniques"] = devices_cfg["techniques"]

    # Layer 2b: config-studies.yaml (canonical studies — overrides devices if present)
    studies_path = base_dir / "config-studies.yaml"
    if studies_path.exists():
        studies_cfg = _load_yaml(studies_path)
        if studies_cfg and "studies" in studies_cfg:
            merged["studies"] = studies_cfg["studies"]

    # Layer 3: config-instruments.yaml (includes filename_patterns)
    instruments_path = base_dir / "config-instruments.yaml"
    instr_cfg = _load_yaml(instruments_path)
    if instr_cfg:
        merged["instruments"] = instr_cfg.get("instruments", {})

    # Rebuild file_naming from instruments (grammar patterns live per-instrument)
    instruments = merged.get("instruments", {})
    all_patterns: list[dict] = []
    for inst_cfg in instruments.values():
        if isinstance(inst_cfg, dict):
            all_patterns.extend(inst_cfg.get("filename_patterns", []))
    if all_patterns:
        merged["file_naming"] = {"separator": "_", "patterns": all_patterns}

    # Layer 4: config-template.yaml
    template_path = base_dir / "config-template.yaml"
    template_cfg = _load_yaml(template_path)
    if template_cfg:
        merged["templates"] = template_cfg.get("templates", {})

    _global_config = merged
    return merged


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
    merged = load_global_config()

    # Layer: technique configs (deprecated, per-technique overrides)
    tech_configs = load_technique_configs()
    if tech_configs:
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

    # Also check studies for matching patterns (new model)
    if not config_patterns:
        legacy_to_study = config.get("legacy_to_study", {})
        study_name = legacy_to_study.get(technique)
        if study_name:
            studies_dict = config.get("studies", {})
            tech_prefix, study_key = _parse_study_qualifier(study_name)
            if tech_prefix in studies_dict and study_key in studies_dict[tech_prefix]:
                config_patterns = studies_dict[tech_prefix][study_key].get("patterns", [])

    hardcoded = _DEFAULT_TECHNIQUE_PATTERNS.get(technique, [])
    merged = [p for p in config_patterns if p not in hardcoded]
    merged.extend(hardcoded)
    return merged


def _parse_study_qualifier(study_name: str) -> tuple[str, str]:
    """Parse 'technique:study-name' into (technique, study_name)."""
    if ":" in study_name:
        parts = study_name.split(":", 1)
        return (parts[0], parts[1])
    return ("", study_name)


def get_device_config(
    technique: str,
    device_name: str,
    project_root: Path | None = None,
    study_name: str | None = None,
) -> dict | None:
    """Return device loading config, or None if not found.

    Resolution order:
        1. Study instruments (if study_name provided)
        2. Per-technique devices from merged config
        3. Hardcoded built-in device configs (_DEFAULT_TECHNIQUE_DEVICES)
        4. Global device registry overrides

    Returns a dict with: delimiter, decimal, header_lines, encoding, columns.
    Falls back gracefully: missing keys use _DEFAULT_DEVICE defaults.
    """
    config = get_merged_config(project_root)
    device_cfg = None

    # Attempt 1: Check study instruments (new model)
    if study_name:
        studies_dict = config.get("studies", {})
        tech_prefix, study_key = _parse_study_qualifier(study_name)
        if tech_prefix in studies_dict and study_key in studies_dict[tech_prefix]:
            study_instr = studies_dict[tech_prefix][study_key].get("instruments", {})
            dev = study_instr.get(device_name)
            if dev:
                device_cfg = dict(dev)

    # Attempt 2: Check per-technique devices section (old model)
    if device_cfg is None:
        tech_section = config.get("techniques", {}).get(technique, {})
        devices = tech_section.get("devices", {})
        device_cfg = devices.get(device_name, None)

    # Attempt 3: Fallback to hardcoded built-in device configs
    if device_cfg is None:
        builtin_devices = _DEFAULT_TECHNIQUE_DEVICES.get(technique, {})
        device_cfg = builtin_devices.get(device_name, None)
        if device_cfg is None:
            return None

    # Attempt: merge metadata from study instruments even without study_name.
    # This ensures metadata sections defined in _STUDIES are available when
    # loading via hardcoded defaults (no config files on disk).
    if device_cfg is not None:
        studies_dict = config.get("studies", {})
        meta_found = False
        for tech_prefix, technique_studies in studies_dict.items():
            if meta_found:
                break
            for _study_key, study_cfg in technique_studies.items():
                instruments = study_cfg.get("instruments", {})
                if device_name in instruments:
                    dev_cfg = instruments[device_name]
                    dev_meta = dev_cfg.get("metadata", {})
                    if dev_meta:
                        device_cfg = dict(device_cfg)
                        device_cfg["metadata"] = dev_meta
                        meta_found = True
                    break

    # Overlay with global device registry
    global_cfg = load_global_config()
    global_devices = global_cfg.get("devices", {})
    global_device_cfg = global_devices.get(device_name)
    if global_device_cfg:
        device_cfg = _merge_dicts(device_cfg, global_device_cfg)

    # Also overlay with instrument config from instruments section (new model)
    # Note: instrument-level config is a generic fallback; per-technique
    # config values (from studies, techniques, or hardcoded) take priority.
    # Only apply instrument config fields that are NOT already set.
    instruments_section = global_cfg.get("instruments", {})
    instr_cfg = instruments_section.get(device_name)
    if instr_cfg and isinstance(instr_cfg, dict):
        instr_device_cfg = instr_cfg.get("parsing", {})
        if instr_device_cfg:
            for k, v in instr_device_cfg.items():
                device_cfg.setdefault(k, v)

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
    study_name: str | None = None,
) -> str:
    """Return the preferred default device name for a technique, or ''.

    Resolution order:
        1. ``defaults`` section of merged config (project → global → hardcoded)
        2. ``default_device`` field in ``_DEFAULT_GLOBAL_TECHNIQUES``
        3. Study instruments (first instrument of the mapped study)
        4. Explicit ``study_name`` instruments (if provided)
    """
    config = get_merged_config(project_root)
    defaults = config.get("defaults", {})
    dev = defaults.get(technique, "")
    if not dev:
        tech_cfg = _DEFAULT_GLOBAL_TECHNIQUES.get(technique, {})
        dev = tech_cfg.get("default_device", "")
    if not dev:
        legacy_to_study = config.get("legacy_to_study", {})
        legacy_study = legacy_to_study.get(technique)
        if legacy_study:
            studies_dict = config.get("studies", {})
            tech_prefix, study_key = _parse_study_qualifier(legacy_study)
            if tech_prefix in studies_dict and study_key in studies_dict[tech_prefix]:
                instrs = studies_dict[tech_prefix][study_key].get("instruments", {})
                if instrs:
                    dev = next(iter(instrs))
    # Step 4: try explicit study_name if provided
    if not dev and study_name:
        study_cfg = get_study_config(study_name)
        if study_cfg:
            instrs = study_cfg.get("instruments", {})
            if instrs:
                dev = next(iter(instrs))
    return dev


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

    Reads from the ``templates.plot_labels.<technique>`` section of the merged config.
    """
    config = get_merged_config(project_root)
    return dict(config.get("templates", {}).get("plot_labels", {}).get(technique, {}))


def get_file_naming_patterns(project_root: Path | None = None) -> list[dict]:
    """Return file naming pattern configs from merged config.

    Returns list of pattern dicts with keys: template, description, regex, fields.
    Falls back to empty list if no naming grammar configured.
    """
    config = get_merged_config(project_root)
    naming = config.get("file_naming", {})
    patterns = naming.get("patterns", [])
    return patterns


def get_file_naming_grammar(project_root: Path | None = None) -> dict:
    """Return the file naming grammar configuration.

    Grammar patterns are now aggregated from per-instrument filename_patterns
    in the instruments section (Phase 3).

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


def get_instrument_grammar(instrument_name: str) -> list[dict]:
    """Return filename_patterns for a specific instrument.

    Reads from ``instruments.<instrument_name>.filename_patterns`` in the
    merged config. Returns an empty list if the instrument or patterns
    are not found.

    Args:
        instrument_name: Instrument key (e.g. ``"keysight-b1500a"``).
    """
    config = get_merged_config()
    instruments = config.get("instruments", {})
    inst_cfg = instruments.get(instrument_name, {})
    if isinstance(inst_cfg, dict):
        return inst_cfg.get("filename_patterns", [])
    return []


def get_all_instrument_grammars() -> dict[str, list[dict]]:
    """Return filename_patterns for all instruments.

    Returns a dict mapping instrument name → list of pattern dicts.
    """
    config = get_merged_config()
    instruments = config.get("instruments", {})
    result: dict[str, list[dict]] = {}
    for name, inst_cfg in instruments.items():
        if isinstance(inst_cfg, dict):
            patterns = inst_cfg.get("filename_patterns", [])
            if patterns:
                result[name] = patterns
    return result


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
        builtin_devices = _DEFAULT_TECHNIQUE_DEVICES.get(technique, {})
        device_cfg = builtin_devices.get(device_name, None)
        if device_cfg is None:
            return None

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
        3. Overlay with instruments section (new modular model)
        4. Return merged result or None if not found in either

    Returns dict with: delimiter, decimal, header_lines, encoding, columns
    or None if not found.
    """
    cfg = dict(_DEFAULT_GLOBAL_DEVICES.get(device_name, {}))

    global_cfg = load_global_config()
    devices_section = global_cfg.get("devices", {})
    user_cfg = devices_section.get(device_name)
    if user_cfg:
        cfg.update(user_cfg)

    instruments_section = global_cfg.get("instruments", {})
    instr_cfg = instruments_section.get(device_name)
    if instr_cfg and isinstance(instr_cfg, dict):
        instr_device_cfg = instr_cfg.get("parsing", {})
        if instr_device_cfg:
            cfg.update(instr_device_cfg)

    return cfg if cfg else None


def list_global_devices() -> list[str]:
    """List all device names in the global registry.

    Combines hardcoded defaults, global config, and modular instruments.
    """
    names: set[str] = set(_DEFAULT_GLOBAL_DEVICES.keys())
    global_cfg = load_global_config()
    devices_section = global_cfg.get("devices", {})
    names.update(devices_section.keys())
    instruments_section = global_cfg.get("instruments", {})
    names.update(instruments_section.keys())
    return sorted(names)


def get_device_types() -> list[str]:
    """Return list of known protocol-level device type categories.

    Device types determine analysis mode (volatile, bipolar, linear, etc.).
    These are different from hardware instrument models.
    """
    global_cfg = load_global_config()
    extra_types = list(global_cfg.get("device_types", {}).keys())
    return list(_DEFAULT_DEVICE_TYPE_GRAMMAR.keys()) + extra_types + ["pvd", "electrochem", "general"]


# ── Device-type-specific grammar ─────────────────────────────────────


_DEFAULT_DEVICE_TYPE_GRAMMAR: dict[str, list[dict]] = {
    "memristor": [
        {
            "id": "crossbar-rNcN",
            "template": "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}",
            "regex": r'^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$',
            "fields": ["date_code", "material", "matrix", "technique", "type", "suffix"],
        },
    ],
    "junction": [
        {
            "id": "junction-basic",
            "template": "{date_code}_{material}_{technique}_{suffix?}",
            "regex": r'^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<technique>[^_]+)(?:_(?P<suffix>\d+))?\.\w+$',
            "fields": ["date_code", "material", "technique", "suffix"],
        },
    ],
    "deposition": [
        {
            "id": "deposition-basic",
            "template": "{date_code}_{material}_{technique}_{suffix?}",
            "regex": r'^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<technique>[^_]+)(?:_(?P<suffix>\d+))?\.\w+$',
            "fields": ["date_code", "material", "technique", "suffix"],
        },
    ],
}


def get_device_type_grammar(device_type: str) -> list[dict]:
    """Return the default grammar patterns for a given device type.

    Checks the hardcoded device-type grammar first, then allows overrides
    from the global config ``file_naming.device_types.<type>`` section.
    """
    patterns = list(_DEFAULT_DEVICE_TYPE_GRAMMAR.get(device_type, []))

    global_cfg = load_global_config()
    file_naming = global_cfg.get("file_naming", {})
    dt_grammar = file_naming.get("device_types", {}).get(device_type, [])
    if dt_grammar:
        patterns.extend(dt_grammar)

    return patterns


def get_device_type_grammar_config() -> dict[str, list[dict]]:
    """Return the full device-type grammar config.

    Merges hardcoded defaults with global config overrides.
    """
    result: dict[str, list[dict]] = {}
    for dt in _DEFAULT_DEVICE_TYPE_GRAMMAR:
        result[dt] = get_device_type_grammar(dt)
    global_cfg = load_global_config()
    file_naming = global_cfg.get("file_naming", {})
    dt_grammar = file_naming.get("device_types", {})
    for dt, patterns in dt_grammar.items():
        if dt not in result:
            result[dt] = list(patterns)
    return result


def get_protocol_grammar(protocol_yaml_path: Path) -> list[dict]:
    """Read the ``grammar:`` section from a protocol YAML file."""
    from science_cli.core.protocol import read_protocol_grammar  # noqa: I001
    return read_protocol_grammar(protocol_yaml_path)


def get_merged_grammar(
    project_root: Path | None = None,
    protocol_name: str | None = None,
    device_type: str | None = None,
) -> dict:
    """Resolve file naming grammar via 5-tier resolution chain.

    Resolution order (highest priority last):
        1. Hardcoded grammar (fallback base) — lowest priority
        2. Device-type-specific grammar (from config)
        3. Global config grammar patterns
        4. Project-level grammar overrides
        5. Protocol-level grammar (highest priority)
    """
    from science_cli.core.technique import _merge_grammar, HARDCODED_GRAMMAR  # noqa: I001

    merged = dict(HARDCODED_GRAMMAR)

    if device_type:
        dt_patterns = get_device_type_grammar(device_type)
        if dt_patterns:
            merged = _merge_grammar(merged, {"patterns": dt_patterns})

    global_grammar = get_file_naming_grammar(None)
    if global_grammar and global_grammar.get("patterns"):
        merged = _merge_grammar(merged, global_grammar)

    if project_root is not None:
        proj_grammar = get_file_naming_grammar(project_root)
        if proj_grammar and proj_grammar.get("patterns") and proj_grammar != global_grammar:
            merged = _merge_grammar(merged, proj_grammar)

    if project_root is not None and protocol_name:
        protocol_yaml = project_root / "protocol" / protocol_name / f"{protocol_name}.yaml"
        proto_grammar_patterns = get_protocol_grammar(protocol_yaml)
        if proto_grammar_patterns:
            merged = _merge_grammar(merged, {"patterns": proto_grammar_patterns})

    return merged


def get_instrument(name: str) -> dict | None:
    """Look up an instrument model by name (delegates to instrument registry)."""
    from science_cli.library.instruments.registry import get_instrument as _get_ins
    return _get_ins(name)


def get_instruments_by_technique(technique: str) -> list[dict]:
    """List instrument models compatible with a given technique."""
    from science_cli.library.instruments.registry import get_instruments_by_technique as _get_by_tech  # noqa: I001
    return _get_by_tech(technique)


def get_global_technique_config(technique_name: str) -> dict | None:
    """Look up a technique config from the global registry.

    Resolution order:
        1. Start with hardcoded default technique configs
        2. Overlay with global config (~/.config/science-cli/config.yaml → techniques:)
        3. Fall back to study data (new model)

    Returns dict with: patterns, label, grammar_codes, types, default_device
    or None if not found.
    """
    cfg = dict(_DEFAULT_GLOBAL_TECHNIQUES.get(technique_name, {}))
    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {})
    user_cfg = tech_section.get(technique_name)
    if user_cfg:
        cfg.update(user_cfg)

    if not cfg:
        legacy_to_study = global_cfg.get("legacy_to_study", {})
        study_name = legacy_to_study.get(technique_name)
        if study_name:
            studies_dict = global_cfg.get("studies", {})
            tech_prefix, study_key = _parse_study_qualifier(study_name)
            if tech_prefix in studies_dict and study_key in studies_dict[tech_prefix]:
                study = studies_dict[tech_prefix][study_key]
                cfg["label"] = study.get("label", technique_name)
                cfg["patterns"] = study.get("patterns", [])
                cfg["grammar_codes"] = study.get("legacy_codes", [])

    return cfg if cfg else None


def resolve_technique_from_grammar(
    grammar_code: str, project_root: Path | None = None
) -> str | None:
    """Map a grammar code (e.g. 'iv', 'iv-sweep', 'iv_dc') to a technique config key.

    Checks:
        1. Global technique registry (hardcoded + config.yaml) for grammar_codes match
        2. Study legacy_codes (new model)
        3. Direct technique name match as fallback
    Returns the technique key (e.g. 'iv-sweep') or None.
    """
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

    studies_dict = global_cfg.get("studies", {})
    for tech_prefix, technique_studies in studies_dict.items():
        for study_name, study_cfg in technique_studies.items():
            legacy_codes = study_cfg.get("legacy_codes", [])
            if grammar_code in legacy_codes or grammar_code == study_name:
                legacy_name = f"{tech_prefix}:{study_name}"
                legacy_to_study = global_cfg.get("legacy_to_study", {})
                for old_name, mapped in legacy_to_study.items():
                    if mapped == legacy_name:
                        return old_name
                return study_name

    return None


def list_global_techniques() -> list[str]:
    """List all technique names in the global registry.

    Combines hardcoded defaults, global config, and study prefixes.
    """
    names: set[str] = set(_DEFAULT_GLOBAL_TECHNIQUES.keys())
    names.update(_DEFAULT_TECHNIQUE_PATTERNS.keys())
    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {})
    names.update(tech_section.keys())
    # Include study technique prefixes (new model)
    studies_section = global_cfg.get("studies", {})
    names.update(studies_section.keys())
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
    "ec-cv": {
        "label": "Cyclic Voltammetry",
        "grammar_codes": ["ec-cv", "cv", "CV"],
        "default_device": "autolab-usth",
    },
    "ec-ca": {
        "label": "Chronoamperometry",
        "grammar_codes": ["ec-ca", "ca", "CA"],
        "default_device": "autolab-usth",
    },
    "ec-eis": {
        "label": "EIS — Electrochemical Impedance Spectroscopy",
        "grammar_codes": ["ec-eis", "eis", "EIS", "impedance"],
        "default_device": "autolab-usth",
    },
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
        "default_device": "spectrometer-iop",
    },
    "pulse-stp": {
        "label": "STP Decay",
        "grammar_codes": ["stp", "pulse-stp", "short-term-plasticity"],
        "default_device": "keysight-b1500a",
    },
    "pulse-ppf": {
        "label": "Paired-Pulse Facilitation",
        "grammar_codes": ["ppf", "pulse-ppf", "paired-pulse"],
        "default_device": "keysight-b1500a",
    },
    "pulse-endurance": {
        "label": "Pulse Endurance Cycling",
        "grammar_codes": ["endurance", "pulse-endurance", "end"],
        "default_device": "keysight-b1500a",
    },
    "pulse-retention": {
        "label": "Pulse Retention Time",
        "grammar_codes": ["retention", "pulse-retention", "ret"],
        "default_device": "keysight-b1500a",
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
#
# Per-device-type grammar patterns override the global patterns for
# specific device types (memristor, junction, deposition).
#
# Resolution order (5-tier):
#   1. Hardcoded defaults (core/config.py)
#   2. Device-type-specific grammar (below)
#   3. Global config grammar patterns (this section)
#   4. Project-level grammar overrides (sci-config.yaml)
#   5. Protocol-level grammar (protocol/<name>.yaml)

file_naming:
  # Per-device-type grammar patterns -- higher priority than global patterns
  device_types:
    memristor:
      - id: crossbar-rNcN
        template: "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}"
        description: "Standard rNcN convention for memristor crossbar arrays"
        regex: '^(?P<date_code>\\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\\d+))?_(?P<matrix>r\\d+c\\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\\d+))?\\.\\w+$'
    junction:
      - id: junction-basic
        template: "{date_code}_{material}_{technique}_{suffix?}"
        description: "Basic junction naming (no matrix coordinates)"
        regex: '^(?P<date_code>\\d{6})_(?P<material>[^_]+)_(?P<technique>[^_]+)(?:_(?P<suffix>\\d+))?\\.\\w+$'

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
  spectrometer-iop:
    label: "UV-Vis Spectrometer (IOP Hanoi) — vs-770st"
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
    default_device: spectrometer-iop

# --- Default device per technique ---
# When no device is specified, use this device for the technique.
defaults:
  iv-sweep: keithley-2400
  raman: horiba-usth
  uv-vis: spectrometer-iop
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

    Combines: technique config files, global config techniques, hardcoded defaults,
    and study prefixes (new model).
    """
    names: set[str] = set()

    tech_configs = load_technique_configs()
    names.update(tech_configs.keys())

    global_cfg = load_global_config()
    names.update(global_cfg.get("techniques", {}).keys())

    names.update(_DEFAULT_TECHNIQUE_PATTERNS.keys())

    studies_section = global_cfg.get("studies", {})
    names.update(studies_section.keys())

    return sorted(names)


def list_technique_devices(technique: str) -> list[str]:
    """List device names configured for a given technique.

    Checks: technique config files, global config, hardcoded defaults,
    and study instruments (new model).
    """
    devices: set[str] = set()

    tech_configs = load_technique_configs()
    if technique in tech_configs:
        devices.update(tech_configs[technique].get("devices", {}).keys())

    global_cfg = load_global_config()
    tech_section = global_cfg.get("techniques", {}).get(technique, {})
    devices.update(tech_section.get("devices", {}).keys())

    devices.update(_DEFAULT_TECHNIQUE_DEVICES.get(technique, {}).keys())

    studies_section = global_cfg.get("studies", {})
    for tech_prefix, technique_studies in studies_section.items():
        if tech_prefix == technique or technique in _DEFAULT_TECHNIQUE_PATTERNS:
            for study_name, study_cfg in technique_studies.items():
                instruments = study_cfg.get("instruments", {})
                devices.update(instruments.keys())

    return sorted(devices)


# ── Study-aware accessors (new model) ──────────────────────────────────


def detect_study_from_filename(filename: str) -> str | None:
    """Detect study from filename using study patterns.

    Delegates to studies.detect_study_from_filename with config-loaded data.
    """
    from science_cli.core import studies as _studies
    cfg = load_global_config()
    return _studies.detect_study_from_filename(filename, cfg.get("studies", {}))


def _merge_instrument_parsing(
    study_name: str, study_instruments: dict
) -> dict:
    """Enrich each study instrument with canonical parsing from instruments registry.

    For each instrument in the study's instruments dict:
      - delimiter, decimal, encoding, columns/names come from
        ``instruments.<inst>.parsing`` (the canonical source)
      - header_lines comes from the study-level override if present,
        otherwise falls back to ``parsing.header_lines_default``
      - metadata comes from the study level (unchanged)

    Args:
        study_name: For logging/debug context (unused currently).
        study_instruments: The ``instruments`` dict from a study config.

    Returns:
        New dict with the same keys, each enriched with parsing fields.
    """
    cfg = load_global_config()
    instruments_registry = cfg.get("instruments", {})
    enriched: dict = {}

    for inst_name, inst_cfg in study_instruments.items():
        merged = dict(inst_cfg)  # start with study-level (metadata, header_lines)

        instr_model = instruments_registry.get(inst_name, {})
        parsing = instr_model.get("parsing", {})

        if parsing:
            # Apply canonical parsing fields (instrument-level is source of truth)
            for key in ("delimiter", "decimal", "encoding", "columns", "names"):
                if key in parsing:
                    merged[key] = parsing[key]

            # header_lines: study override wins, else fall back to default
            if "header_lines" not in merged:
                default_hl = parsing.get("header_lines_default")
                if default_hl is not None:
                    merged["header_lines"] = default_hl

        enriched[inst_name] = merged

    return enriched


def get_study_config(study_name: str) -> dict | None:
    """Return config for a named study, merging technique defaults.

    Instruments are enriched with canonical parsing data from the
    instruments registry (delimiter, decimal, encoding, columns/names)
    via ``_merge_instrument_parsing``.  Study-level ``header_lines``
    overrides the instrument default when present.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
    """
    from science_cli.core import studies as _studies
    cfg = load_global_config()
    study_cfg = _studies.get_study_config(study_name, cfg.get("studies", {}))
    if study_cfg is None:
        return None

    # Enrich instruments with canonical parsing data
    instruments = study_cfg.get("instruments", {})
    if instruments:
        study_cfg["instruments"] = _merge_instrument_parsing(
            study_name, instruments
        )

    return study_cfg


def get_studies_for_device_type(device_type: str) -> list[str]:
    """Return study names applicable to a device type.

    Args:
        device_type: Device type slug (e.g. ``"volatile-memristor"``).
    """
    from science_cli.core import studies as _studies
    return _studies.get_studies_for_device_type(device_type)


def get_instruments_for_study(study_name: str) -> list[str]:
    """Return instrument names configured for a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
    """
    from science_cli.core import studies as _studies
    return _studies.get_instruments_for_study(study_name)


def resolve_technique_from_study(study_name: str) -> str:
    """Get the parent technique of a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
    """
    from science_cli.core import studies as _studies
    return _studies.resolve_technique_from_study(study_name)


def resolve_library_from_study(study_name: str, device_type: str | None = None) -> str:
    """Get the analysis library for a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
        device_type: Optional device type for library override.
    """
    from science_cli.core import studies as _studies
    return _studies.resolve_library_from_study(study_name, device_type)


def resolve_legacy_technique(technique_name: str) -> str | None:
    """Map old technique names to new study names.

    Args:
        technique_name: Old technique name (e.g. ``"iv-sweep"``).
    Returns:
        Study name in ``"technique:study-name"`` format, or None.
    """
    from science_cli.core import studies as _studies
    return _studies.resolve_legacy_technique(technique_name)


def list_studies(technique_filter: str | None = None) -> list[str]:
    """List all study names, optionally filtered by technique.

    Args:
        technique_filter: Optional technique prefix filter (e.g. ``"iv"``).
    Returns:
        Sorted list of study names in ``"technique:study-name"`` format.
    """
    from science_cli.core import studies as _studies
    return _studies.list_studies(technique_filter)
