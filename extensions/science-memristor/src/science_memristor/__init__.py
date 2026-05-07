"""science-memristor: memristor characterization extension."""

from science_cli.extensions import ExtensionRegistry, TechniqueDef

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

    from science_memristor.endurance import analyze_endurance
    from science_memristor.retention import analyze_retention
    from science_memristor.switching import analyze_switching, extract_iv_parameters

    registry.analyzers["mem-endurance"] = analyze_endurance
    registry.analyzers["mem-retention"] = analyze_retention
    registry.analyzers["mem-switching"] = analyze_switching

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
