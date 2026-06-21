"""Endurance analysis: cycle statistics, Weibull failure, trend degradation."""
from pathlib import Path

import numpy as np


def analyze_endurance(r_on, r_off, cycles):
    """Analyze endurance cycling data.
    Returns dict with mean resistances, CV, failure detection, Weibull fit, trend.
    """
    r_on = np.asarray(r_on, dtype=float).flatten()
    r_off = np.asarray(r_off, dtype=float).flatten()
    cycles = np.asarray(cycles, dtype=float).flatten()

    ratio = r_off / r_on
    mean_r_on = float(np.mean(r_on))
    mean_r_off = float(np.mean(r_off))
    mean_ratio = float(np.mean(ratio))
    cv_r_on = float(np.std(r_on) / mean_r_on) if mean_r_on != 0 else float("inf")
    cv_r_off = float(np.std(r_off) / mean_r_off) if mean_r_off != 0 else float("inf")

    failed_mask = ratio < 10
    failure_cycle = int(cycles[failed_mask][0]) if np.any(failed_mask) else None

    weibull_fit = None
    if failure_cycle is not None:
        weibull_fit = _weibull_failure_fit(cycles, ratio)

    try:
        coeffs = np.polyfit(cycles, r_off, 1)
        trend_slope = float(coeffs[0])
        trend_r_squared = float(
            1 - np.sum((r_off - np.polyval(coeffs, cycles)) ** 2)
            / np.sum((r_off - np.mean(r_off)) ** 2)
        )
    except Exception:
        trend_slope = 0.0
        trend_r_squared = 0.0

    tail_n = max(int(len(cycles) * 0.1), 3)
    ratio_tail = ratio[-tail_n:]

    return {
        "mean_r_on": mean_r_on,
        "mean_r_off": mean_r_off,
        "mean_ratio": mean_ratio,
        "cv_r_on": cv_r_on,
        "cv_r_off": cv_r_off,
        "failure_cycle": failure_cycle,
        "n_cycles": int(len(cycles)),
        "weibull_fit": weibull_fit,
        "trend_slope": trend_slope,
        "trend_r_squared": trend_r_squared,
        "ratio_tail_mean": float(np.mean(ratio_tail)),
        "ratio_tail_std": float(np.std(ratio_tail)),
    }


def _weibull_failure_fit(cycles, ratio):
    """Fit Weibull minimum distribution to cycles-to-failure."""
    from scipy import stats
    failed_mask = ratio < 10
    if np.sum(failed_mask) < 3:
        return {"shape": None, "scale": None, "error": "Too few failure points for Weibull fit"}
    cycles_failed = cycles[failed_mask]
    params = stats.weibull_min.fit(cycles_failed, floc=0)
    return {
        "shape": float(params[0]),
        "location": float(params[1]),
        "scale": float(params[2]),
    }


def endurance_summary(data):
    """Human-readable endurance summary."""
    stats = analyze_endurance(data.r_on, data.r_off, data.cycles)
    lines = [f"Endurance: {stats['n_cycles']} cycles"]
    lines.append(f"  R_ON  = {stats['mean_r_on']:.1f} Ohm (CV={stats['cv_r_on']:.3f})")
    lines.append(f"  R_OFF = {stats['mean_r_off']:.1f} Ohm (CV={stats['cv_r_off']:.3f})")
    lines.append(f"  Ratio = {stats['mean_ratio']:.1f}")
    if stats["failure_cycle"] is not None:
        lines.append(f"  FAILURE at cycle {stats['failure_cycle']}")
    else:
        lines.append("  NO FAILURE (ratio > 10 throughout)")
    lines.append(f"  R_OFF trend: {stats['trend_slope']:.2e} Ohm/cycle (R-squared={stats['trend_r_squared']:.4f})")
    return "\n".join(lines)


def analyze_endurance_to_yaml(
    r_on,
    r_off,
    cycles,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
    metadata: dict | None = None,
    project_root: Path | None = None,
    step_name: str = "",
) -> Path:
    """Analyze endurance and write YAML analysis file.

    If *project_root* and *step_name* are provided, also writes the
    extracted pulse metadata back to ``protocol.yaml`` under that step.
    """
    from science_cli.core.analysis_output import write_analysis_yaml

    stats = analyze_endurance(r_on, r_off, cycles)
    output = {
        "analysis": {
            "mode": devices or "general",
            "parameters": {
                "cycles_to_failure": stats.get("failure_cycle"),
                "r_high_initial": stats.get("mean_r_off"),
                "r_low_initial": stats.get("mean_r_on"),
                "cycle_to_cycle_variability_pct": stats.get("cv_r_off", 0) * 100 if stats.get("cv_r_off") else None,
                "n_cycles": stats.get("n_cycles"),
                "ratio_tail_mean": stats.get("ratio_tail_mean"),
                "ratio_tail_std": stats.get("ratio_tail_std"),
            },
            "per_cycle_sampling": len(r_on) if hasattr(r_on, "__len__") else None,
        },
    }

    # Write metadata back to protocol.yaml if project context provided
    if project_root and step_name and metadata:
        from science_cli.core.analysis_output import merge_analysis_to_metadata
        from science_cli.core.protocol import update_step_metadata

        proto_meta = merge_analysis_to_metadata(
            metadata, output["analysis"], key_prefix=""
        )
        if proto_meta:
            update_step_metadata(project_root, step_name, proto_meta)

    return write_analysis_yaml(
        technique="pulse-endurance",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices,
    )
