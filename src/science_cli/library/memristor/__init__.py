"""science_cli.library.memristor: memristor characterization module.

.. deprecated::
    Use :mod:`science_cli.library.iv` or :mod:`science_cli.library.pulse` instead.
"""

import warnings

warnings.warn(
    "science_cli.library.memristor is deprecated, "
    "use science_cli.library.iv or science_cli.library.pulse instead",
    DeprecationWarning, stacklevel=2,
)

from science_cli.library.iv import (
    extract_breakdown_voltage,
    extract_resistance,
    detect_vset,
    detect_vreset,
    compute_on_off_ratio,
    extract_iv_parameters,
)
from science_cli.library.iv.volatile import analyze_volatile, volatile_summary
from science_cli.library.iv.bipolar import analyze_bipolar, bipolar_summary
from science_cli.library.pulse.endurance import analyze_endurance
from science_cli.library.pulse.retention import analyze_retention

from .device import (
    DeviceConfig, DeviceGeometry, FileEntry, MatrixPoint,
    SweepSegment, TechniqueGroup, _migrate_devices_yaml,
    generate_device_grid, read_devices, sync_devices,
    sync_sweep_to_protocol_yaml, validate, write_devices,
)
from .device_assignment import (
    MaterialSpec, MaterialType, MemristorModel, ModelConfig,
    assign_device, assign_device_from_key, list_known_materials,
    get_assignment_for_protocol,
)
from .endurance import analyze_endurance as _old_endurance
from .retention import analyze_retention as _old_retention
from .switching import analyze_switching, extract_iv_parameters as _old_extract_iv

__all__ = [
    "SweepSegment", "FileEntry", "TechniqueGroup", "MatrixPoint",
    "DeviceGeometry", "DeviceConfig",
    "read_devices", "write_devices", "validate", "sync_devices",
    "sync_sweep_to_protocol_yaml", "_migrate_devices_yaml",
    "generate_device_grid",
    "MaterialType", "MemristorModel", "MaterialSpec", "ModelConfig",
    "assign_device", "assign_device_from_key", "list_known_materials",
    "get_assignment_for_protocol",
    "analyze_endurance", "analyze_retention", "analyze_switching",
    "extract_iv_parameters",
    "analyze_volatile", "volatile_summary",
    "analyze_bipolar", "bipolar_summary",
]

ANALYZERS = {
    "mem-endurance": _old_endurance,
    "mem-retention": _old_retention,
    "mem-switching": analyze_switching,
}

PLOT_PRESETS = {
    "mem-endurance": {"type": "line", "xlabel": "Cycle #", "ylabel": "Resistance (Ohm)"},
    "mem-retention": {"type": "line", "xlabel": "Time (s)", "ylabel": "Resistance (Ohm)"},
    "mem-switching": {"type": "scatter", "xlabel": "Cycle #", "ylabel": "Voltage (V)"},
}
