"""CA analysis: Cottrell fitting, steady-state analysis."""

import numpy as np
from lmfit import Model
from science_cli.electrochem.models import CAData


def analyze_ca(data: CAData, options: dict | None = None) -> dict:
    """Run selected CA analyses. Options: fit (bool), steady_state (bool)."""
    if options is None:
        options = {}
    results: dict = {}

    if options.get("fit", True):
        results["cottrell"] = analyze_cottrell(data)

    if options.get("steady_state", True):
        results["steady_state"] = analyze_steady_state(data)

    return results


def analyze_cottrell(data: CAData) -> dict:
    """Perform Cottrell analysis: fit i(t) = slope / sqrt(t) + intercept.

    Uses lmfit to handle the linear regression in t^{-1/2} space.
    Returns slope, slope_stderr, intercept, r_squared, reduced_chi.
    """
    t = data.time
    i = data.current

    # Use only t > 0 (avoid division by zero at t=0)
    mask = t > 0
    t_pos = t[mask]
    i_pos = i[mask]

    t_inv = 1.0 / np.sqrt(t_pos)

    # Define the Cottrell model: i = slope * t^{-1/2} + intercept
    def cottrell(t_inv, slope, intercept):
        return slope * t_inv + intercept

    model = Model(cottrell)
    params = model.make_params(slope=0.0001, intercept=0)

    try:
        result = model.fit(i_pos, params, t_inv=t_inv)

        return {
            "slope": float(result.params["slope"].value),
            "slope_stderr": float(result.params["slope"].stderr
                                  if result.params["slope"].stderr is not None else 0),
            "intercept": float(result.params["intercept"].value),
            "r_squared": float(result.rsquared),
            "reduced_chi": float(result.redchi),
        }
    except Exception as e:
        return {"error": str(e)}


def analyze_steady_state(data: CAData, fraction: float = 0.2) -> dict:
    """Compute steady-state current from the tail of a CA transient.

    fraction: fraction of the data at the end to use (default 0.2 = last 20%).
    Returns steady_state_current, steady_state_std, steady_state_time,
    steady_state_fraction.
    """
    t = data.time
    i = data.current

    n = len(t)
    tail_start = int(n * (1 - fraction))
    tail_i = i[tail_start:]

    return {
        "steady_state_current": float(np.mean(tail_i)),
        "steady_state_std": float(np.std(tail_i)),
        "steady_state_time": float(t[tail_start]),
        "steady_state_fraction": fraction,
    }
