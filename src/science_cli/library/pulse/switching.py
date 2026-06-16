"""Pulse switching time analysis."""
import numpy as np


def analyze_pulse_switching(switching_times, switching_voltages=None):
    """Analyze pulse switching time distributions."""
    t = np.asarray(switching_times, dtype=float).flatten()
    result = {
        "t_set_mean": float(np.mean(t)) if len(t) > 0 else None,
        "t_set_std": float(np.std(t)) if len(t) > 0 else None,
        "n_events": int(len(t)),
    }
    if switching_voltages is not None:
        v = np.asarray(switching_voltages, dtype=float).flatten()
        result["v_set_mean"] = float(np.mean(v)) if len(v) > 0 else None
        result["v_set_std"] = float(np.std(v)) if len(v) > 0 else None
    return result
