"""PPF (Paired-Pulse Facilitation) ratio analysis."""
from pathlib import Path

import numpy as np


def analyze_ppf(intervals_ms, ratios):
    """Analyze PPF ratio vs inter-spike interval.
    
    Fits exponential decay to PPF ratio as function of interval.
    
    Args:
        intervals_ms: Array of inter-pulse intervals (ms).
        ratios: Array of PPF ratios (A2/A1).
    
    Returns:
        dict with facilitation time constant, ratio statistics.
    """
    intervals = np.asarray(intervals_ms, dtype=float).flatten()
    ratios = np.asarray(ratios, dtype=float).flatten()
    
    if len(intervals) < 2:
        return {"error": "Insufficient data points (need >=2)"}
    
    # Fit: PPF(t) = 1 + A * exp(-t/tau)
    def ppf_model(t, a, tau):
        return 1 + a * np.exp(-t / tau)
    
    from scipy import optimize
    
    try:
        p0 = [max(ratios) - 1, np.median(intervals)]
        bounds = ([0, 0], [np.inf, np.inf])
        popt, _ = optimize.curve_fit(ppf_model, intervals, ratios, p0=p0, bounds=bounds, maxfev=5000)
        a_fit, tau_fit = popt
        
        residuals = ratios - ppf_model(intervals, a_fit, tau_fit)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((ratios - np.mean(ratios)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        result = {
            "tau_facilitation_ms": float(tau_fit),
            "a_amplitude": float(a_fit),
            "ppf_ratio_max": float(np.max(ratios)),
            "ppf_ratio_min": float(np.min(ratios)),
            "r_squared": float(r_squared),
            "n_intervals": int(len(intervals)),
        }
    except Exception:
        result = {
            "tau_facilitation_ms": None,
            "a_amplitude": None,
            "ppf_ratio_max": float(np.max(ratios)),
            "ppf_ratio_min": float(np.min(ratios)),
            "r_squared": 0,
            "n_intervals": int(len(intervals)),
            "fit_error": "Could not fit exponential model",
        }
    
    return result


def ppf_summary(analysis):
    """Human-readable PPF analysis summary."""
    if "error" in analysis:
        return f"PPF Analysis: {analysis['error']}"
    lines = [
        f"PPF Analysis: {analysis['n_intervals']} intervals",
        f"  PPF ratio range: {analysis['ppf_ratio_min']:.2f} - {analysis['ppf_ratio_max']:.2f}",
    ]
    if analysis["tau_facilitation_ms"] is not None:
        lines.append(f"  Facilitation time constant: {analysis['tau_facilitation_ms']:.1f} ms")
    lines.append(f"  R-squared = {analysis['r_squared']:.4f}")
    return "\n".join(lines)


def analyze_ppf_to_yaml(
    intervals_ms,
    ratios,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
) -> Path:
    """Analyze PPF and write YAML analysis file."""
    from science_cli.core.analysis_output import write_analysis_yaml

    stats = analyze_ppf(intervals_ms, ratios)

    if "error" in stats:
        output = {"analysis": {"error": stats["error"]}}
    else:
        ppf_table = [
            {"interval_ms": float(intervals_ms[i]), "ppf_ratio": float(ratios[i])}
            for i in range(min(len(intervals_ms), len(ratios)))
        ]
        output = {
            "analysis": {
                "mode": devices or "general",
                "ppf_ratio_vs_interval": ppf_table,
                "facilitation_time_constant_ms": stats.get("tau_facilitation_ms"),
                "a_amplitude": stats.get("a_amplitude"),
                "ppf_ratio_max": stats.get("ppf_ratio_max"),
                "ppf_ratio_min": stats.get("ppf_ratio_min"),
                "r_squared": stats.get("r_squared"),
                "n_intervals": stats.get("n_intervals"),
            },
        }

    return write_analysis_yaml(
        technique="pulse-ppf",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices,
    )
