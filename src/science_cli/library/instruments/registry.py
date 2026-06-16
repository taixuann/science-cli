"""Instrument model registry CRUD.

Wraps the global config device registry with instrument-specific semantics.
"""

from science_cli.core.config import (
    invalidate_cache,
    load_global_config,
)
from science_cli.library.instruments.models import Instrument

BUILTIN_INSTRUMENTS: dict[str, dict] = {
    "keysight-b1500a": {
        "label": "Keysight B1500A Semiconductor Parameter Analyzer",
        "location": "gtiit-china",
        "type": "semiconductor-device-analyzer",
        "techniques": ["iv-sweep", "iv-breakdown", "iv-leakage", "pulse-endurance", "pulse-stp", "pulse-ppf"],
        "config": {"delimiter": ",", "decimal": ".", "header_lines": 246, "encoding": "utf-8"},
    },
    "keithley-2400": {
        "label": "Keithley 2400 SourceMeter",
        "location": "usth-hanoi",
        "type": "sourcemeter",
        "techniques": ["iv-sweep", "iv-breakdown", "iv-leakage", "pulse-endurance"],
        "config": {"delimiter": ",", "decimal": ".", "header_lines": 0, "encoding": "utf-8"},
    },
    "autolab-usth": {
        "label": "Autolab USTH (CV deposition)",
        "location": "usth-hanoi",
        "type": "potentiostat",
        "techniques": ["ec-cv", "ec-ca", "ec-eis"],
        "config": {},
    },
    "horiba-usth": {
        "label": "Horiba LabRAM HR Evolution (USTH)",
        "location": "usth-hanoi",
        "type": "raman-spectrometer",
        "techniques": ["raman"],
        "config": {"delimiter": "\t", "decimal": ",", "header_lines": 45, "encoding": "latin1"},
    },
    "spectrometer-iop": {
        "label": "UV-Vis Spectrometer (IOP Hanoi) — vs-770st",
        "location": "iop-hanoi",
        "type": "uv-vis-spectrometer",
        "techniques": ["uv-vis"],
        "config": {"delimiter": ",", "decimal": ".", "header_lines": 1, "encoding": "latin1"},
    },
}


def _merged_instrument_registry() -> dict[str, dict]:
    """Merge builtin instruments with user overrides from modular config."""
    import yaml

    from science_cli.core.config import _global_config_dir

    registry = dict(BUILTIN_INSTRUMENTS)

    # Read from old monolithic config.yaml (devices section) for backward compat
    global_cfg = load_global_config()
    for name, cfg in global_cfg.get("devices", {}).items():
        if name in registry:
            registry[name].update(cfg)
        else:
            registry[name] = cfg

    # Read from new modular config-instruments.yaml (takes priority)
    mod_path = _global_config_dir() / "config-instruments.yaml"
    if mod_path.exists():
        with open(mod_path) as f:
            mod_cfg = yaml.safe_load(f) or {}
        for name, cfg in mod_cfg.get("instruments", {}).items():
            if name in registry:
                registry[name].update(cfg)
            else:
                registry[name] = cfg

    return registry


def get_instrument(name: str) -> dict | None:
    """Get a single instrument model by name, or None if not found."""
    registry = _merged_instrument_registry()
    raw = registry.get(name)
    if raw is None:
        return None
    return Instrument.from_dict(name, raw).to_dict()


def get_all_instruments() -> list[dict]:
    """Get all registered instrument models sorted by name."""
    registry = _merged_instrument_registry()
    return sorted(
        [Instrument.from_dict(name, raw).to_dict() for name, raw in registry.items()],
        key=lambda x: x["label"],
    )


def get_instruments_by_technique(technique: str) -> list[dict]:
    """Get all instrument models compatible with a given technique."""
    registry = _merged_instrument_registry()
    result = []
    for name, raw in registry.items():
        techniques = raw.get("techniques", [])
        if technique in techniques:
            result.append(Instrument.from_dict(name, raw).to_dict())
    return sorted(result, key=lambda x: x["label"])


def get_instrument_techniques(name: str) -> list[str]:
    """Get the list of compatible techniques for an instrument.

    Args:
        name: Instrument model name (e.g. 'keithley-2400').

    Returns:
        List of technique slugs, or empty list if not found.
    """
    registry = _merged_instrument_registry()
    raw = registry.get(name)
    if raw is None:
        return []
    return list(raw.get("techniques", []))


def register_instrument(name: str, data: dict) -> bool:
    """Register a new instrument model in modular config."""
    import yaml

    from science_cli.core.config import _global_config_dir

    path = _global_config_dir() / "config-instruments.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    instruments = cfg.setdefault("instruments", {})
    instruments[name] = data
    cfg["instruments"] = instruments

    with open(path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    invalidate_cache()
    return True


def remove_instrument(name: str) -> bool:
    """Remove an instrument model from modular config."""
    import yaml

    from science_cli.core.config import _global_config_dir

    path = _global_config_dir() / "config-instruments.yaml"
    if not path.exists():
        return False

    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    instruments = cfg.get("instruments", {})
    if name not in instruments:
        return False

    del instruments[name]
    cfg["instruments"] = instruments

    with open(path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    invalidate_cache()
    return True


def edit_instrument(name: str, data: dict) -> bool:
    """Edit an existing instrument model in modular config."""
    import yaml

    from science_cli.core.config import _global_config_dir

    path = _global_config_dir() / "config-instruments.yaml"
    if not path.exists():
        return False

    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    instruments = cfg.setdefault("instruments", {})
    if name not in instruments:
        return False

    instruments[name].update(data)
    cfg["instruments"] = instruments

    with open(path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    invalidate_cache()
    return True
