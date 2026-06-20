"""Instrument type categorizations."""

INSTRUMENT_TYPES: dict[str, str] = {
    "sourcemeter": "SourceMeter (SMU)",
    "semiconductor-device-analyzer": "Semiconductor Device Analyzer",
    "parameter-analyzer": "Semiconductor Parameter Analyzer",
    "potentiostat": "Potentiostat / Galvanostat",
    "lcr-meter": "LCR Meter",
    "raman-spectrometer": "Raman Spectrometer",
    "uv-vis-spectrometer": "UV-Vis Spectrometer",
    "afm": "Atomic Force Microscope",
    "pvd-system": "PVD Deposition System",
    "probe-station": "Probe Station",
    "function-generator": "Function / Pulse Generator",
    "oscilloscope": "Oscilloscope",
    "unknown": "Unknown Instrument Type",
}


def describe_type(t: str) -> str:
    return INSTRUMENT_TYPES.get(t, f"Custom: {t}")


def list_types() -> list[str]:
    return sorted(INSTRUMENT_TYPES.keys())
