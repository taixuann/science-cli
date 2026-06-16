"""science-iv: IV curve analysis extension.

Integrated into science-cli core as ``science_cli.library.iv``.
Provides IV sweep, breakdown, leakage, and memristor/junction analysis.
"""

import warnings

from science_cli.core.technique import ColumnMap
from .analyze import extract_breakdown_voltage, extract_resistance
from .metrics import detect_vset, detect_vreset, compute_on_off_ratio, extract_iv_parameters
from .volatile import analyze_volatile, analyze_volatile_to_yaml, volatile_summary
from .bipolar import analyze_bipolar, analyze_bipolar_to_yaml, bipolar_summary

__all__ = [
    "extract_breakdown_voltage", "extract_resistance",
    "detect_vset", "detect_vreset",
    "compute_on_off_ratio", "extract_iv_parameters",
    "analyze_volatile", "volatile_summary",
    "analyze_volatile_to_yaml",
    "analyze_bipolar", "bipolar_summary",
    "analyze_bipolar_to_yaml",
]

# Column alias lists
_iv_x_aliases = [
    "Voltage (V)", "voltage", "V", "Voltage",
    "WE(1).Potential (V)", "Potential (V)", "BV",
    "Bias Voltage (V)", "bias_voltage", "Bias", "bias",
]
_iv_y_aliases = [
    "Current (A)", "current", "I", "I/A",
    "WE(1).Current (A)", "Bi",
    "Bias Current (A)", "bias_current",
]

# Built-in column maps keyed by technique name
COLUMN_MAPS: dict[str, ColumnMap] = {
    "iv-sweep": ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
        x_aliases=_iv_x_aliases, y_aliases=_iv_y_aliases,
        extras={"resistance": "Resistance (Ω)"},
    ),
    "iv-breakdown": ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
        x_aliases=_iv_x_aliases, y_aliases=_iv_y_aliases,
    ),
    "iv-leakage": ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="|Current| (A)",
        x_aliases=_iv_x_aliases, y_aliases=_iv_y_aliases,
    ),
}

# Built-in analyzers
ANALYZERS: dict[str, callable] = {
    "iv-sweep": extract_resistance,
    "iv-breakdown": extract_breakdown_voltage,
    "iv-leakage": extract_resistance,
}

# Built-in plot presets
PLOT_PRESETS: dict[str, dict] = {
    "iv-sweep": {"type": "line", "xlabel": "Voltage (V)", "ylabel": "Current (A)"},
    "iv-breakdown": {"type": "line", "xlabel": "Voltage (V)", "ylabel": "Current (A)"},
    "iv-leakage": {"type": "line", "xlabel": "Voltage (V)", "ylabel": "|Current| (A)"},
}
