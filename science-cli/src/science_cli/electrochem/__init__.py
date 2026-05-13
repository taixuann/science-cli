"""science-electrochem: electrochemistry analysis extension.

Provides electrochemical analysis for:
  - Cyclic Voltammetry (CV): peak detection, charge integration, scan rate analysis
  - Chronoamperometry (CA): Cottrell fitting, steady-state analysis
  - Electrochemical Impedance Spectroscopy (EIS): circuit fitting, KK test
"""

# ---------------------------------------------------------------------------
# Public API — importable as science_cli.electrochem
# ---------------------------------------------------------------------------
from science_cli.electrochem.models import CVData, CAData, EISData
from science_cli.electrochem.cv import analyze_cv, peak_analysis, calculate_charge, scan_rate_analysis
from science_cli.electrochem.ca import analyze_ca, analyze_cottrell, analyze_steady_state
from science_cli.electrochem.eis import analyze_eis, circuit_fit, kramers_kronig

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
# Extension registration — compatible with ExtensionRegistry
# ---------------------------------------------------------------------------
def register(registry) -> None:
    """Register electrochemistry techniques with the ExtensionRegistry."""
    from science_cli.extensions import TechniqueDef, ColumnMap

    registry.name = "science-electrochem"

    # --- Technique definitions ---
    registry.techniques["ec-cv"] = TechniqueDef(
        name="ec-cv",
        label="CV",
        patterns=["_CV.", ".cv", "cv_"],
        description="Cyclic Voltammetry",
    )
    registry.techniques["ec-ca"] = TechniqueDef(
        name="ec-ca",
        label="CA",
        patterns=["_CA.", ".ca", "ca_"],
        description="Chronoamperometry",
    )
    registry.techniques["ec-eis"] = TechniqueDef(
        name="ec-eis",
        label="EIS",
        patterns=[".mpt", "_EIS.", ".eis", "_impedance", ".z"],
        description="Electrochemical Impedance Spectroscopy",
    )

    # --- Analyzer functions ---
    registry.analyzers["ec-cv"] = analyze_cv
    registry.analyzers["ec-ca"] = analyze_ca
    registry.analyzers["ec-eis"] = analyze_eis

    # --- Plot presets ---
    registry.plot_presets["ec-cv"] = {
        "type": "line",
        "xlabel": "Potential (V)",
        "ylabel": "Current (A)",
    }
    registry.plot_presets["ec-ca"] = {
        "type": "line",
        "xlabel": "Time (s)",
        "ylabel": "Current (A)",
    }
    registry.plot_presets["ec-eis"] = {
        "type": "nyquist",
        "xlabel": "Z' (Ω)",
        "ylabel": "-Z'' (Ω)",
    }

    # --- Column maps ---
    registry.column_maps["ec-cv"] = ColumnMap(
        x="WE(1).Potential (V)",
        y="WE(1).Current (A)",
        x_label="Potential (V)",
        y_label="Current (A)",
        x_aliases=_cv_x_aliases,
        y_aliases=_cv_y_aliases,
    )
    registry.column_maps["ec-ca"] = ColumnMap(
        x="Corrected time (s)",
        y="WE(1).Current (A)",
        x_label="Time (s)",
        y_label="Current (A)",
        x_aliases=_ca_x_aliases,
        y_aliases=_ca_y_aliases,
    )
    registry.column_maps["ec-eis"] = ColumnMap(
        x="Z' (Ω)",
        y="-Z'' (Ω)",
        x_label="Z' (Ω)",
        y_label="-Z'' (Ω)",
        x_aliases=_eis_zr_aliases,
        y_aliases=_eis_zi_aliases,
        extras={
            "frequency": "Frequency (Hz)",
            "z_real": "Z' (Ω)",
            "z_imag": "-Z'' (Ω)",
            "magnitude": "|Z| (Ω)",
            "phase": "Phase (°)",
        },
    )
    # Store frequency aliases for EIS data loading
    registry.column_maps["ec-eis"].extras["_f_aliases"] = _eis_f_aliases
