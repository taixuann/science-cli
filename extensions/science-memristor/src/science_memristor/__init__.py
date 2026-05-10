"""science-memristor: memristor characterization extension."""

from science_cli.extensions import ColumnMap, ExtensionRegistry, TechniqueDef

from science_memristor.device import (
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


def register(registry: ExtensionRegistry):
    registry.name = "science-memristor"

    # --- Techniques ---
    registry.techniques["mem-endurance"] = TechniqueDef(
        name="mem-endurance",
        label="Endurance",
        patterns=["_endurance", ".end", "end_", "endurance"],
        description="DC/pulsed endurance cycling",
    )
    registry.techniques["mem-retention"] = TechniqueDef(
        name="mem-retention",
        label="Retention",
        patterns=["_retention", ".ret", "ret_", "retention"],
        description="Retention time test",
    )
    registry.techniques["mem-switching"] = TechniqueDef(
        name="mem-switching",
        label="Switching",
        patterns=["_switch", ".sw", "sw_", "switch_"],
        description="Switching time / voltage characterization",
    )

    # --- Analyzers ---
    from science_memristor.endurance import analyze_endurance
    from science_memristor.retention import analyze_retention
    from science_memristor.switching import analyze_switching, extract_iv_parameters

    registry.analyzers["mem-endurance"] = analyze_endurance
    registry.analyzers["mem-retention"] = analyze_retention
    registry.analyzers["mem-switching"] = analyze_switching

    # --- Plot presets ---
    registry.plot_presets["mem-endurance"] = {
        "type": "line",
        "xlabel": "Cycle #",
        "ylabel": "Resistance (Ω)",
    }
    registry.plot_presets["mem-retention"] = {
        "type": "line",
        "xlabel": "Time (s)",
        "ylabel": "Resistance (Ω)",
    }
    registry.plot_presets["mem-switching"] = {
        "type": "scatter",
        "xlabel": "Cycle #",
        "ylabel": "Voltage (V)",
    }

    # --- Column maps ---
    registry.column_maps["mem-endurance"] = ColumnMap(
        x="Cycle", y="Resistance (Ω)",
        x_label="Cycle #", y_label="Resistance (Ω)",
        x_aliases=["Cycle", "cycle", "Cycle #", "cycle_number", "#"],
        y_aliases=["Resistance (Ω)", "Resistance", "R", "R (Ω)", "HRS", "LRS"],
    )
    registry.column_maps["mem-retention"] = ColumnMap(
        x="Time (s)", y="Resistance (Ω)",
        x_label="Time (s)", y_label="Resistance (Ω)",
        x_aliases=["Time (s)", "Time", "time", "t", "t/s"],
        y_aliases=["Resistance (Ω)", "Resistance", "R", "R (Ω)", "HRS", "LRS"],
    )
    registry.column_maps["mem-switching"] = ColumnMap(
        x="Cycle", y="Voltage (V)",
        x_label="Cycle #", y_label="Voltage (V)",
        x_aliases=["Cycle", "cycle", "Cycle #", "cycle_number", "#"],
        y_aliases=[
            "Voltage (V)", "voltage", "V", "Voltage",
            "SET Voltage (V)", "RESET Voltage (V)",
            "V_set", "V_reset", "V_SET", "V_RESET",
        ],
    )
