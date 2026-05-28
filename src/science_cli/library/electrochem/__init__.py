"""science-electrochem: electrochemistry analysis extension.

Provides electrochemical analysis for:
  - Cyclic Voltammetry (CV): peak detection, charge integration, scan rate analysis
  - Chronoamperometry (CA): Cottrell fitting, steady-state analysis
  - Electrochemical Impedance Spectroscopy (EIS): circuit fitting, KK test
"""

# ---------------------------------------------------------------------------
# Public API — importable as science_cli.library.electrochem
# ---------------------------------------------------------------------------
from .ca import analyze_ca, analyze_cottrell, analyze_steady_state
from .cv import (
    analyze_cv,
    calculate_charge,
    peak_analysis,
    scan_rate_analysis,
)
from .eis import analyze_eis, circuit_fit, kramers_kronig
from .models import CAData, CVData, EISData

__all__ = [
    # Models
    "CVData", "CAData", "EISData",
    # CV
    "analyze_cv", "peak_analysis", "calculate_charge", "scan_rate_analysis",
    # CA
    "analyze_ca", "analyze_cottrell", "analyze_steady_state",
    # EIS
    "analyze_eis", "circuit_fit", "kramers_kronig",
]


# ---------------------------------------------------------------------------
# Column alias lists — useful for data loader resolution
# ---------------------------------------------------------------------------
_cv_x_aliases = [
    "WE(1).Potential (V)", "Potential (V)", "potential",
    "Potential applied (V)", "E", "E/V", "V", "Voltage (V)",
]
_cv_y_aliases = [
    "WE(1).Current (A)", "Current (A)", "current", "I", "I/A", "<I>/A",
]
_ca_x_aliases = [
    "Corrected time (s)", "corrected time", "time", "Time", "Time (s)", "t/s",
]
_ca_y_aliases = [
    "WE(1).Current (A)", "Current (A)", "current", "I", "I/A", "<I>/A",
]
_eis_f_aliases = [
    "Frequency (Hz)", "Frequency", "f/Hz", "freq", "frequency", "f",
]
_eis_zr_aliases = [
    "Z' (Ω)", "Z'", "Re(Z)", "ReZ", "Zre", "Z_real", "z'", "z_re",
]
_eis_zi_aliases = [
    "-Z'' (Ω)", "-Z''", "Z''", '-Z"', "Im(Z)", "ImZ", "Zim", "Z_imag",
    "z''", "z_im",
]


# ---------------------------------------------------------------------------
# Built-in column maps keyed by technique name
# ---------------------------------------------------------------------------
from science_cli.core.technique import ColumnMap

COLUMN_MAPS: dict[str, ColumnMap] = {
    "ec-cv": ColumnMap(
        x="WE(1).Potential (V)", y="WE(1).Current (A)",
        x_label="Potential (V)", y_label="Current (A)",
        x_aliases=_cv_x_aliases, y_aliases=_cv_y_aliases,
    ),
    "ec-ca": ColumnMap(
        x="Corrected time (s)", y="WE(1).Current (A)",
        x_label="Time (s)", y_label="Current (A)",
        x_aliases=_ca_x_aliases, y_aliases=_ca_y_aliases,
    ),
    "ec-eis": ColumnMap(
        x="Z' (Ω)", y="-Z'' (Ω)",
        x_label="Z' (Ω)", y_label="-Z'' (Ω)",
        x_aliases=_eis_zr_aliases, y_aliases=_eis_zi_aliases,
        extras={
            "frequency": "Frequency (Hz)",
            "z_real": "Z' (Ω)", "z_imag": "-Z'' (Ω)",
            "magnitude": "|Z| (Ω)", "phase": "Phase (°)",
            "_f_aliases": _eis_f_aliases,
        },
    ),
}

# Built-in analyzers
ANALYZERS: dict[str, callable] = {
    "ec-cv": analyze_cv,
    "ec-ca": analyze_ca,
    "ec-eis": analyze_eis,
}

# Built-in plot presets
PLOT_PRESETS: dict[str, dict] = {
    "ec-cv": {"type": "line", "xlabel": "Potential (V)", "ylabel": "Current (A)"},
    "ec-ca": {"type": "line", "xlabel": "Time (s)", "ylabel": "Current (A)"},
    "ec-eis": {"type": "nyquist", "xlabel": "Z' (Ω)", "ylabel": "-Z'' (Ω)"},
}
