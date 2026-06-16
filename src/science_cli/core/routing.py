"""Device-type-aware library routing.

Determines which analysis library and analysis mode to use based on
technique name + device type (devices: field in protocol YAML).
Supports study-based resolution (study → technique → library).
"""


TECHNIQUE_LIBRARY_MAP: dict[str, str] = {
    "iv-sweep": "iv",
    "iv-breakdown": "iv",
    "iv-leakage": "iv",
    "pulse-endurance": "pulse",
    "pulse-retention": "pulse",
    "pulse-switching": "pulse",
    "pulse-forming": "pulse",
    "pulse-set": "pulse",
    "pulse-reset": "pulse",
    "pulse-read": "pulse",
    "pulse-ivd": "pulse",
    "pulse-stp": "pulse",
    "pulse-ppf": "pulse",
    "raman": "raman",
    "uv-vis": "uv-vis",
    "ec-cv": "ec",
    "ec-ca": "ec",
    "ec-eis": "ec",
    "ec-lsv": "ec",
    "ec-swv": "ec",
    "afm-gwy": "afm",
}


DEVICE_TYPE_MODE_MAP: dict[str, str] = {
    "memristor": "volatile",
    "junction": "bipolar",
    "deposition": "linear",
    "pvd": "linear",
    "electrochem": "general",
    "general": "general",
}


def resolve_study_library(study_name: str, device_type: str | None = None) -> str:
    """Determine library from study name (study → technique → library).

    Args:
        study_name: Study name (e.g. 'iv:iv-bipolar-sweep').
        device_type: Optional device type for library override.

    Returns:
        Library name: 'iv', 'pulse', 'raman', 'uv-vis', 'ec', 'afm'.
    """
    try:
        from science_cli.core.config import resolve_library_from_study
        return resolve_library_from_study(study_name, device_type)
    except ImportError:
        pass

    technique = study_name.split(":")[0] if ":" in study_name else ""
    return resolve_library(technique, device_type)


def resolve_library(
    technique: str,
    devices: str | None = None,
    study_name: str | None = None,
) -> str:
    """Determine which analysis library to use.

    If study_name is provided, resolves through study first.
    Otherwise uses technique + device type mapping.

    Args:
        technique: Technique slug (e.g. 'iv-sweep', 'pulse-endurance').
        devices: Device type from protocol YAML (e.g. 'memristor', 'junction').
        study_name: Optional study name for study-based resolution.

    Returns:
        Library name: 'iv', 'pulse', 'raman', 'uv-vis', 'ec', 'afm'.
        Falls back to technique prefix matching if not in map.
    """
    if study_name:
        return resolve_study_library(study_name, devices)

    result = TECHNIQUE_LIBRARY_MAP.get(technique)
    if result:
        return result
    for prefix, lib in [("iv-", "iv"), ("pulse-", "pulse"), ("ec-", "ec")]:
        if technique.startswith(prefix):
            return lib
    return "general"


def load_device_types_config() -> dict:
    """Load device types from config, falling back to hardcoded."""
    try:
        from science_cli.core.config import load_global_config
        cfg = load_global_config()
        return cfg.get("device_types", {})
    except ImportError:
        return {}


def resolve_analysis_mode(devices: str) -> str:
    """Determine analysis mode from device type, checking config first.

    The analysis mode affects how data is interpreted:
      - 'volatile': V_set only (no V_reset) — memristor volatile switching
      - 'bipolar': V_set + V_reset — junction bipolar switching
      - 'linear': Linear I-V — deposition/PVD
      - 'general': Default analysis

    Args:
        devices: Device type from protocol YAML devices: field.

    Returns:
        Analysis mode string: 'volatile', 'bipolar', 'linear', or 'general'.
    """
    try:
        device_types_cfg = load_device_types_config()
        if devices in device_types_cfg:
            return device_types_cfg[devices].get("analysis_mode", "general")
    except Exception:
        pass
    return DEVICE_TYPE_MODE_MAP.get(devices, "general")
