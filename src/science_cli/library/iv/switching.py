"""IV switching analysis — Weibull fits, statistics, histograms."""
import numpy as np
from science_cli.library.iv.metrics import detect_vset, detect_vreset, compute_on_off_ratio, extract_iv_parameters


def analyze_switching_statistics(v_set_values, v_reset_values):
    """Analyze switching voltage distributions with Weibull fits."""
    from scipy import stats

    v_set = np.asarray(v_set_values, dtype=float).flatten()
    v_reset = np.asarray(v_reset_values, dtype=float).flatten()

    result = {
        "v_set_mean": float(np.mean(v_set)) if len(v_set) > 0 else None,
        "v_reset_mean": float(np.mean(v_reset)) if len(v_reset) > 0 else None,
        "v_set_std": float(np.std(v_set)) if len(v_set) > 0 else None,
        "v_reset_std": float(np.std(v_reset)) if len(v_reset) > 0 else None,
        "n_set": int(len(v_set)),
        "n_reset": int(len(v_reset)),
    }

    if len(v_set) >= 3:
        try:
            v_abs = np.abs(v_set[v_set > 0])
            params = stats.weibull_min.fit(v_abs, floc=0)
            result["weibull_set"] = {"V0": float(params[2]), "beta": float(params[0])}
        except Exception:
            result["weibull_set"] = None

    if len(v_reset) >= 3:
        try:
            v_abs = np.abs(v_reset[v_reset > 0])
            params = stats.weibull_min.fit(v_abs, floc=0)
            result["weibull_reset"] = {"V0": float(params[2]), "beta": float(params[0])}
        except Exception:
            result["weibull_reset"] = None

    return result
