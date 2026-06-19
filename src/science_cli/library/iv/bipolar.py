"""Bipolar junction analysis — V_set + V_reset, hysteresis characterization."""
from pathlib import Path

import numpy as np


def analyze_bipolar(v_set_values, v_reset_values, on_off_ratios=None, hysteresis_areas=None):
    """Analyze bipolar junction switching statistics.

    Bipolar junctions show both V_set (forward) and V_reset (reverse) switching.

    Args:
        v_set_values: Array of V_set voltages.
        v_reset_values: Array of V_reset voltages.
        on_off_ratios: Optional array of ON/OFF ratios.
        hysteresis_areas: Optional array of hysteresis loop areas.

    Returns:
        dict with statistics for both set and reset.
    """
    v_set = np.asarray(v_set_values, dtype=float).flatten()
    v_reset = np.asarray(v_reset_values, dtype=float).flatten()

    result = {"mode": "bipolar", "n_events": max(len(v_set), len(v_reset))}

    if len(v_set) > 0:
        result["v_set_mean"] = float(np.mean(v_set))
        result["v_set_std"] = float(np.std(v_set))
        result["v_set_cv"] = float(np.std(v_set) / np.abs(np.mean(v_set))) if np.mean(v_set) != 0 else float("inf")

    if len(v_reset) > 0:
        result["v_reset_mean"] = float(np.mean(v_reset))
        result["v_reset_std"] = float(np.std(v_reset))
        result["v_reset_cv"] = float(np.std(v_reset) / np.abs(np.mean(v_reset))) if np.mean(v_reset) != 0 else float("inf")

    if on_off_ratios is not None and len(on_off_ratios) > 0:
        ratios = np.asarray(on_off_ratios, dtype=float).flatten()
        result["on_off_ratio_mean"] = float(np.mean(ratios))
        result["on_off_ratio_std"] = float(np.std(ratios))

    if hysteresis_areas is not None and len(hysteresis_areas) > 0:
        areas = np.asarray(hysteresis_areas, dtype=float).flatten()
        result["hysteresis_area_mean"] = float(np.mean(areas))
        result["hysteresis_area_std"] = float(np.std(areas))

    return result


def bipolar_summary(analysis: dict) -> str:
    """Human-readable bipolar analysis summary."""
    lines = [
        f"Bipolar Junction Analysis: {analysis.get('n_events', 0)} switching events",
        "  Mode: bipolar (V_set + V_reset)",
    ]
    if "v_set_mean" in analysis:
        lines.append(f"  V_set: {analysis['v_set_mean']:.3f} \u00b1 {analysis['v_set_std']:.3f} V")
    if "v_reset_mean" in analysis:
        lines.append(f"  V_reset: {analysis['v_reset_mean']:.3f} \u00b1 {analysis['v_reset_std']:.3f} V")
    if "on_off_ratio_mean" in analysis:
        lines.append(f"  ON/OFF ratio: {analysis['on_off_ratio_mean']:.1f} \u00b1 {analysis['on_off_ratio_std']:.1f}")
    if "hysteresis_area_mean" in analysis:
        lines.append(f"  Hysteresis area: {analysis['hysteresis_area_mean']:.3f} \u00b1 {analysis['hysteresis_area_std']:.3f}")
    return "\n".join(lines)


def analyze_bipolar_to_yaml(
    v_set_values,
    v_reset_values,
    step_dir: Path,
    on_off_ratios=None,
    hysteresis_areas=None,
    instrument: str = "",
    devices: str = "",
    metadata: dict | None = None,
    project_root: Path | None = None,
    step_name: str | None = None,
) -> Path:
    """Analyze bipolar IV data and write YAML analysis file.

    If *project_root* and *step_name* are provided, also writes the
    extracted metadata back to ``protocol.yaml`` under that step.
    """
    from science_cli.core.analysis_output import (
        merge_analysis_to_metadata,
        write_analysis_yaml,
    )

    stats = analyze_bipolar(
        v_set_values=v_set_values,
        v_reset_values=v_reset_values,
        on_off_ratios=on_off_ratios,
        hysteresis_areas=hysteresis_areas,
    )

    output = {
        "analysis": {
            "mode": "bipolar",
            "parameters": {
                "v_set": stats.get("v_set_mean"),
                "v_set_std": stats.get("v_set_std"),
                "v_reset": stats.get("v_reset_mean"),
                "v_reset_std": stats.get("v_reset_std"),
                "on_off_ratio": stats.get("on_off_ratio_mean"),
                "hysteresis_area": stats.get("hysteresis_area_mean"),
            },
            "n_events": stats.get("n_events"),
        },
    }

    # Write metadata back to protocol.yaml if project context provided
    if project_root and step_name:
        from science_cli.core.protocol import update_step_metadata

        proto_meta = merge_analysis_to_metadata(
            metadata, output["analysis"], key_prefix=""
        )
        if proto_meta:
            update_step_metadata(project_root, step_name, proto_meta)

    return write_analysis_yaml(
        technique="iv-sweep",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices or "junction",
    )
