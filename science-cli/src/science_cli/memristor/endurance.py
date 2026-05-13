"""Endurance analysis: cycle statistics, Weibull failure, trend degradation."""

import numpy as np
from science_cli.memristor.models import EnduranceData


def analyze_endurance(
    r_on: np.ndarray,
    r_off: np.ndarray,
    cycles: np.ndarray,
) -> dict:
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

    # Failure detection: first cycle where ratio < 10
    failed_mask = ratio < 10
    failure_cycle = (
        int(cycles[failed_mask][0]) if np.any(failed_mask) else None
    )

    # Weibull fit for cycles-to-failure if failure detected
    weibull_fit = None
    if failure_cycle is not None:
        weibull_fit = _weibull_failure_fit(cycles, ratio)

    # Linear trend of R_off over cycles (degradation rate)
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

    # R_off / R_on stability over last 10% of cycles
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
        "trend_slope_unit": "Ω/cycle",
        "trend_r_squared": trend_r_squared,
        "ratio_tail_mean": float(np.mean(ratio_tail)),
        "ratio_tail_std": float(np.std(ratio_tail)),
    }


def _weibull_failure_fit(cycles: np.ndarray, ratio: np.ndarray) -> dict:
    """Fit Weibull minimum distribution to cycles-to-failure.

    Uses all cycles with ratio < 10 as failure events.
    Fits the Weibull scale (eta) and shape (beta) parameters.
    """
    from scipy import stats

    failed_mask = ratio < 10
    if np.sum(failed_mask) < 3:
        return {
            "shape": None,
            "scale": None,
            "error": "Too few failure points for Weibull fit",
        }

    cycles_failed = cycles[failed_mask]
    params = stats.weibull_min.fit(cycles_failed, floc=0)

    return {
        "shape": float(params[0]),
        "location": float(params[1]),
        "scale": float(params[2]),
        "mean_cycles_to_failure": float(params[2]) if len(params) > 2 else None,
        "r_squared": float(stats.weibull_min.cdf(
            np.max(cycles_failed), params[0], params[1], params[2]
        )),
    }


def endurance_summary(data: EnduranceData) -> str:
    """Human-readable endurance summary."""
    stats = analyze_endurance(data.r_on, data.r_off, data.cycles)

    lines = [f"Endurance: {stats['n_cycles']} cycles"]
    lines.append(f"  R_ON  = {stats['mean_r_on']:.1f} Ω (CV={stats['cv_r_on']:.3f})")
    lines.append(f"  R_OFF = {stats['mean_r_off']:.1f} Ω (CV={stats['cv_r_off']:.3f})")
    lines.append(f"  Ratio = {stats['mean_ratio']:.1f}")

    if stats["failure_cycle"] is not None:
        lines.append(f"  FAILURE at cycle {stats['failure_cycle']}")
        if stats["weibull_fit"] and stats["weibull_fit"].get("scale"):
            lines.append(
                f"  Weibull: β={stats['weibull_fit']['shape']:.2f}, "
                f"η={stats['weibull_fit']['scale']:.0f}"
            )
    else:
        lines.append(f"  NO FAILURE (ratio > 10 throughout)")

    lines.append(f"  R_OFF trend: {stats['trend_slope']:.2e} Ω/cycle (R²={stats['trend_r_squared']:.4f})")
    lines.append(f"  Tail ratio ({len(data.ratio) - int(len(data.cycles) * 0.9)} cycles): "
                 f"{stats['ratio_tail_mean']:.1f} ± {stats['ratio_tail_std']:.1f}")

    return "\n".join(lines)
