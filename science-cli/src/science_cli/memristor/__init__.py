"""science_cli.memristor: memristor characterization module."""

from science_cli.memristor.device import (
    SweepSegment,
    FileEntry,
    TechniqueGroup,
    MatrixPoint,
    DeviceGeometry,
    DeviceConfig,
    read_devices,
    write_devices,
    validate,
    sync_devices,
    generate_device_grid,
)

from science_cli.memristor.endurance import analyze_endurance
from science_cli.memristor.retention import analyze_retention
from science_cli.memristor.switching import analyze_switching, extract_iv_parameters

__all__ = [
    "SweepSegment", "FileEntry", "TechniqueGroup", "MatrixPoint",
    "DeviceGeometry", "DeviceConfig",
    "read_devices", "write_devices", "validate", "sync_devices",
    "generate_device_grid",
    "analyze_endurance", "analyze_retention", "analyze_switching",
    "extract_iv_parameters",
]

# Built-in analyzers keyed by technique name
ANALYZERS: dict[str, callable] = {
    "mem-endurance": analyze_endurance,
    "mem-retention": analyze_retention,
    "mem-switching": analyze_switching,
}

# Built-in plot presets keyed by technique name
PLOT_PRESETS: dict[str, dict] = {
    "mem-endurance": {"type": "line", "xlabel": "Cycle #", "ylabel": "Resistance (Ω)"},
    "mem-retention": {"type": "line", "xlabel": "Time (s)", "ylabel": "Resistance (Ω)"},
    "mem-switching": {"type": "scatter", "xlabel": "Cycle #", "ylabel": "Voltage (V)"},
}
