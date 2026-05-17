"""science-iv: IV curve analysis extension.

Integrated into science-cli core as ``science_cli.iv``.
Provides IV sweep, breakdown, and leakage analysis.
"""

from science_cli.core.technique import ColumnMap
from science_cli.iv.analyze import extract_breakdown_voltage, extract_resistance

__all__ = [
    "extract_breakdown_voltage", "extract_resistance",
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
