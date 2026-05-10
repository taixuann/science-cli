"""CA analysis: Cottrell fitting, steady-state analysis."""

import numpy as np
from lmfit import Model
from science_electrochem.models import CAData


def analyze_ca(data: CAData, options: dict | None = None) -> dict:
    options = options or {}
    results = {}

    if options.get("fit", True):
        results["cottrell"] = analyze_cottrell(data)

    if options.get("steady_state", True):
        results["steady_state"] = analyze_steady_state(data)

    return results


def analyze_cottrell(data: CAData) -> dict:
    t, i = data.time, data.current
    mask = t > 0
    t_pos, i_pos = t[mask], i[mask]

    t_inv = 1.0 / np.sqrt(t_pos)

    def cottrell(t_inv, slope, intercept):
        return slope * t_inv + intercept

    model = Model(cottrell)
    params = model.make_params(slope=1e-4, intercept=0)

    try:
        result = model.fit(i_pos, params, t_inv=t_inv)
        return {
            "slope": float(result.params["slope"].value),
            "slope_stderr": float(result.params["slope"].stderr or 0),
            "intercept": float(result.params["intercept"].value),
            "r_squared": float(result.rsquared),
            "reduced_chi": float(result.redchi),
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_steady_state(data: CAData, fraction: float = 0.2) -> dict:
    t, i = data.time, data.current
    n = len(t)
    tail_start = int(n * (1 - fraction))
    tail_i = i[tail_start:]

    return {
        "steady_state_current": float(np.mean(tail_i)),
        "steady_state_std": float(np.std(tail_i)),
        "steady_state_time": float(t[tail_start]),
        "steady_state_fraction": fraction,
    }
