"""science-iv: IV curve analysis extension."""

from science_cli.extensions import ColumnMap, ExtensionRegistry, TechniqueDef


def register(registry: ExtensionRegistry):
    registry.name = "science-iv"

    # --- Techniques ---
    registry.techniques["iv-sweep"] = TechniqueDef(
        name="iv-sweep",
        label="IV Sweep",
        patterns=["_IV.", ".iv", "iv_", "_sweep", "sweep_"],
        description="Current-Voltage sweep",
    )
    registry.techniques["iv-breakdown"] = TechniqueDef(
        name="iv-breakdown",
        label="Breakdown",
        patterns=["_bd.", "breakdown_", "_Vbd", "bd_"],
        description="Ramped voltage to breakdown",
    )
    registry.techniques["iv-leakage"] = TechniqueDef(
        name="iv-leakage",
        label="Leakage",
        patterns=["_leak", "leakage_", "leak_"],
        description="Low-bias leakage current",
    )

    # --- Analyzers ---
    from science_iv.analyze import (
        extract_resistance,
        extract_breakdown_voltage,
    )

    registry.analyzers["iv-sweep"] = extract_resistance
    registry.analyzers["iv-breakdown"] = extract_breakdown_voltage
    registry.analyzers["iv-leakage"] = extract_resistance

    # --- Plot presets ---
    registry.plot_presets["iv-sweep"] = {
        "type": "line",
        "xlabel": "Voltage (V)",
        "ylabel": "Current (A)",
    }
    registry.plot_presets["iv-breakdown"] = {
        "type": "line",
        "xlabel": "Voltage (V)",
        "ylabel": "Current (A)",
    }
    registry.plot_presets["iv-leakage"] = {
        "type": "line",
        "xlabel": "Voltage (V)",
        "ylabel": "|Current| (A)",
    }

    # --- Column maps ---
    # Common IV column names across different source formats
    _iv_x_aliases = [
        "Voltage (V)", "voltage", "V", "Voltage",
        "WE(1).Potential (V)", "Potential (V)",
        "BV", "Bias Voltage (V)", "bias_voltage",
        "Bias", "bias",
    ]
    _iv_y_aliases = [
        "Current (A)", "current", "I", "I/A",
        "WE(1).Current (A)",
        "Bi", "Bias Current (A)", "bias_current",
    ]

    registry.column_maps["iv-sweep"] = ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
        x_aliases=_iv_x_aliases,
        y_aliases=_iv_y_aliases,
        extras={"resistance": "Resistance (Ω)"},
    )
    registry.column_maps["iv-breakdown"] = ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="Current (A)",
        x_aliases=_iv_x_aliases,
        y_aliases=_iv_y_aliases,
    )
    registry.column_maps["iv-leakage"] = ColumnMap(
        x="Voltage (V)", y="Current (A)",
        x_label="Voltage (V)", y_label="|Current| (A)",
        x_aliases=_iv_x_aliases,
        y_aliases=_iv_y_aliases,
    )
