"""Switching analysis: V_set/V_reset statistics, Weibull fits, IV parameter extraction."""

import numpy as np
from science_cli.memristor.models import SwitchingData


def analyze_switching(
    v_set: np.ndarray,
    v_reset: np.ndarray,
    t_set: np.ndarray | None = None,
    t_reset: np.ndarray | None = None,
) -> dict:
    """Analyze switching voltage distributions.

    Returns V_set/V_reset statistics, Weibull fits, histograms, and time data.
    """
    v_set = np.asarray(v_set, dtype=float).flatten()
    v_reset = np.asarray(v_reset, dtype=float).flatten()

    result = {
        "v_set_mean": float(np.mean(v_set)),
        "v_reset_mean": float(np.mean(v_reset)),
        "v_set_std": float(np.std(v_set)),
        "v_reset_std": float(np.std(v_reset)),
        "v_set_cv": float(np.std(v_set) / np.abs(np.mean(v_set))) if np.mean(v_set) != 0 else float("inf"),
        "v_reset_cv": float(np.std(v_reset) / np.abs(np.mean(v_reset))) if np.mean(v_reset) != 0 else float("inf"),
        "n_switches": int(len(v_set)),
    }

    # Weibull fits
    result["weibull_set"] = _weibull_voltage_fit(v_set, "set")
    result["weibull_reset"] = _weibull_voltage_fit(v_reset, "reset")

    # Histogram data (10 bins, or fewer for small datasets)
    n_bins = min(10, max(3, len(v_set) // 5))
    hist_set, bin_edges_set = np.histogram(v_set, bins=n_bins)
    result["v_set_histogram"] = {
        "bins": bin_edges_set.tolist(),
        "counts": hist_set.tolist(),
    }

    hist_reset, bin_edges_reset = np.histogram(v_reset, bins=n_bins)
    result["v_reset_histogram"] = {
        "bins": bin_edges_reset.tolist(),
        "counts": hist_reset.tolist(),
    }

    # Switching times if available
    if t_set is not None:
        t_set = np.asarray(t_set, dtype=float).flatten()
        result["t_set_mean"] = float(np.mean(t_set))
        result["t_set_std"] = float(np.std(t_set))
    else:
        result["t_set_mean"] = None
        result["t_set_std"] = None

    if t_reset is not None:
        t_reset = np.asarray(t_reset, dtype=float).flatten()
        result["t_reset_mean"] = float(np.mean(t_reset))
        result["t_reset_std"] = float(np.std(t_reset))
    else:
        result["t_reset_mean"] = None
        result["t_reset_std"] = None

    # Kolmogorov-Smirnov test: set vs reset same distribution?
    from scipy import stats as sp_stats
    ks_stat, ks_p = sp_stats.ks_2samp(v_set, v_reset)
    result["ks_set_vs_reset"] = {
        "statistic": float(ks_stat),
        "p_value": float(ks_p),
        "different_distributions": bool(ks_p < 0.05),
    }

    return result


def _weibull_voltage_fit(voltages: np.ndarray, label: str) -> dict:
    """Fit Weibull minimum distribution to switching voltage magnitudes (|V|)."""
    from scipy import stats

    # Weibull requires positive data; fit on absolute magnitudes
    v_abs = np.abs(voltages)
    v_abs = v_abs[v_abs > 0]  # exclude exact zeros

    if len(v_abs) < 3:
        return {
            "V0": None,
            "beta": None,
            "error": f"Too few {label} events for Weibull fit",
        }

    try:
        params = stats.weibull_min.fit(v_abs, floc=0)
        return {
            "V0": float(params[2]),  # scale = characteristic voltage magnitude
            "beta": float(params[0]),  # shape = variability
            "location": float(params[1]),
            "polarity": "positive" if np.mean(voltages) >= 0 else "negative",
        }
    except Exception as e:
        return {
            "V0": None,
            "beta": None,
            "error": str(e),
        }


def extract_iv_parameters(
    voltage: np.ndarray,
    current: np.ndarray,
    read_voltage: float = 0.1,
) -> dict:
    """Cross-package call: delegates to science_iv.analyze for IV analysis.

    Extracts resistance and on/off ratio from the memristor's IV sweep.
    """
    try:
        from science_iv.analyze import extract_resistance, extract_on_off_ratio
    except ImportError:
        return {
            "error": "science-iv package not installed. Install with: pip install science-iv",
        }

    res = extract_resistance(voltage, current)
    ratio = extract_on_off_ratio(voltage, current, read_voltage=read_voltage)

    return {
        "resistance": res,
        "on_off_ratio": ratio,
    }


def switching_summary(data: SwitchingData) -> str:
    """Human-readable switching summary."""
    stats = analyze_switching(
        data.v_set, data.v_reset,
        t_set=data.t_set, t_reset=data.t_reset,
    )

    lines = [f"Switching: {stats['n_switches']} events"]
    lines.append(
        f"  V_set  = {stats['v_set_mean']:.3f} ± "
        f"{stats['v_set_std']:.3f} V (CV={stats['v_set_cv']:.3f})"
    )
    lines.append(
        f"  V_reset = {stats['v_reset_mean']:.3f} ± "
        f"{stats['v_reset_std']:.3f} V (CV={stats['v_reset_cv']:.3f})"
    )

    if stats["weibull_set"]["V0"] is not None:
        lines.append(
            f"  Weibull SET: V0={stats['weibull_set']['V0']:.3f}, "
            f"β={stats['weibull_set']['beta']:.1f}"
        )
    if stats["weibull_reset"]["V0"] is not None:
        lines.append(
            f"  Weibull RESET: V0={stats['weibull_reset']['V0']:.3f}, "
            f"β={stats['weibull_reset']['beta']:.1f}"
        )

    if stats["t_set_mean"] is not None:
        lines.append(f"  t_set  = {stats['t_set_mean']:.2e} ± {stats['t_set_std']:.2e} s")
    if stats["t_reset_mean"] is not None:
        lines.append(f"  t_reset = {stats['t_reset_mean']:.2e} ± {stats['t_reset_std']:.2e} s")

    ks = stats["ks_set_vs_reset"]
    lines.append(
        f"  KS test: D={ks['statistic']:.3f}, p={ks['p_value']:.3f} "
        f"({'DIFFERENT' if ks['different_distributions'] else 'same'} distribution)"
    )

    return "\n".join(lines)
