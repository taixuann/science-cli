"""Volatile memristor analysis — V_set only, no V_reset expected."""
from pathlib import Path

import numpy as np


def analyze_volatile(v_set_values, on_off_ratios=None, compliance=None):
    """Analyze volatile memristor switching statistics.

    Volatile memristors show V_set but no V_reset — switching is one-directional.

    Args:
        v_set_values: Array of V_set voltages.
        on_off_ratios: Optional array of ON/OFF ratios.
        compliance: Optional compliance current.

    Returns:
        dict with statistics, yield, and distribution metrics.
    """
    v_set = np.asarray(v_set_values, dtype=float).flatten()
    n = len(v_set)

    if n == 0:
        return {"error": "No V_set events detected", "n_events": 0}

    result = {
        "n_events": n,
        "v_set_mean": float(np.mean(v_set)),
        "v_set_std": float(np.std(v_set)),
        "v_set_min": float(np.min(v_set)),
        "v_set_max": float(np.max(v_set)),
        "v_set_cv": float(np.std(v_set) / np.abs(np.mean(v_set))) if np.mean(v_set) != 0 else float("inf"),
        "mode": "volatile",
    }

    if on_off_ratios is not None and len(on_off_ratios) > 0:
        ratios = np.asarray(on_off_ratios, dtype=float).flatten()
        result["on_off_ratio_mean"] = float(np.mean(ratios))
        result["on_off_ratio_std"] = float(np.std(ratios))
        result["on_off_ratio_median"] = float(np.median(ratios))

    if compliance is not None:
        result["compliance"] = float(compliance)

    return result


def volatile_summary(analysis: dict) -> str:
    """Human-readable volatile analysis summary."""
    if "error" in analysis:
        return f"Volatile Analysis: {analysis['error']}"
    lines = [
        f"Volatile Memristor Analysis: {analysis['n_events']} switching events",
        f"  Mode: volatile (V_set only, no V_reset)",
        f"  V_set: {analysis['v_set_mean']:.3f} \u00b1 {analysis['v_set_std']:.3f} V",
        f"  V_set range: [{analysis['v_set_min']:.3f}, {analysis['v_set_max']:.3f}] V",
        f"  V_set CV: {analysis['v_set_cv']:.3f}",
    ]
    if "on_off_ratio_mean" in analysis:
        lines.append(f"  ON/OFF ratio: {analysis['on_off_ratio_mean']:.1f} \u00b1 {analysis['on_off_ratio_std']:.1f}")
    return "\n".join(lines)


def analyze_volatile_to_yaml(
    v_set_values,
    step_dir: Path,
    on_off_ratios=None,
    compliance=None,
    instrument: str = "",
    devices: str = "",
) -> Path:
    """Analyze volatile IV data and write YAML analysis file."""
    from science_cli.core.analysis_output import write_analysis_yaml

    stats = analyze_volatile(
        v_set_values=v_set_values,
        on_off_ratios=on_off_ratios,
        compliance=compliance,
    )

    if "error" in stats:
        output = {"analysis": {"error": stats["error"]}}
    else:
        output = {
            "analysis": {
                "mode": "volatile",
                "parameters": {
                    "v_set": stats.get("v_set_mean"),
                    "v_set_std": stats.get("v_set_std"),
                    "v_set_cv": stats.get("v_set_cv"),
                    "v_set_min": stats.get("v_set_min"),
                    "v_set_max": stats.get("v_set_max"),
                    "on_off_ratio": stats.get("on_off_ratio_mean"),
                    "compliance": stats.get("compliance"),
                    "set_yield": stats.get("n_events", 0) / max(len(v_set_values), 1) * 100,
                },
                "n_events": stats.get("n_events"),
            },
        }

    return write_analysis_yaml(
        technique="iv-sweep",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices or "memristor",
    )
