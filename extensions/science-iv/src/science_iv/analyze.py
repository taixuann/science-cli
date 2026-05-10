"""IV analysis: resistance extraction, breakdown, fitting, on/off ratio, sweep segments."""

import numpy as np
from lmfit import Model, Parameters


def extract_resistance(
    voltage: np.ndarray,
    current: np.ndarray,
    window: float = 0.1,
) -> dict:
    """Linear fit in ±window V for Ohmic resistance.

    Returns dict with R (Ω), R_std (Ω), r_squared.
    """
    mask = np.abs(voltage) < window
    if mask.sum() < 3:
        return {
            "resistance": None,
            "resistance_stderr": None,
            "r_squared": None,
            "error": f"Less than 3 points in ±{window} V window",
        }

    v_win = voltage[mask]
    i_win = current[mask]
    coeffs = np.polyfit(v_win, i_win, 1)
    slope = coeffs[0]
    intercept = coeffs[1]

    if slope == 0:
        return {
            "resistance": None,
            "resistance_stderr": None,
            "r_squared": None,
            "error": "Zero slope — cannot compute resistance",
        }

    i_pred = slope * v_win + intercept
    ss_res = np.sum((i_win - i_pred) ** 2)
    ss_tot = np.sum((i_win - np.mean(i_win)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Standard error via OLS formula
    n = len(v_win)
    mse = ss_res / (n - 2) if n > 2 else 0.0
    x_mean = np.mean(v_win)
    se_slope = np.sqrt(mse / np.sum((v_win - x_mean) ** 2)) if mse > 0 and n > 2 else 0.0
    R = 1.0 / slope
    R_stderr = se_slope / (slope ** 2)

    return {
        "resistance": float(R),
        "resistance_stderr": float(R_stderr),
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "n_points": int(n),
    }


def extract_scan_rate(
    voltage: np.ndarray,
    current: np.ndarray,
    time: np.ndarray | None = None,
) -> dict:
    """Estimate scan rate in V/s.

    If time is provided, uses time delta between first and last voltage extrema.
    Otherwise estimates from number of inflection points and voltage range.
    """
    if time is not None and len(time) > 1:
        dv = np.max(voltage) - np.min(voltage)
        dt = time[-1] - time[0]
        scan_rate = abs(dv / dt) if dt > 0 else 0.0
    else:
        # Estimate from voltage span assuming a typical sweep
        v_range = np.max(voltage) - np.min(voltage)
        # Detect number of sweeps by counting direction reversals
        dv = np.diff(voltage)
        sign_changes = np.sum(np.diff(np.sign(dv)) != 0)
        n_sweeps = max(sign_changes + 1, 1)
        # Rough estimate: 1 full sweep = 2 × v_range
        scan_rate = v_range / (n_sweeps + 1)  # V per half-sweep (unitless, no time info)

    return {
        "scan_rate_v_s": float(scan_rate),
        "voltage_range": float(np.max(voltage) - np.min(voltage)),
        "n_sweeps": n_sweeps if time is None else 1,
    }


def extract_breakdown_voltage(
    voltage: np.ndarray,
    current: np.ndarray,
    threshold_current: float = 1e-6,
) -> dict:
    """Find voltage where |I| exceeds threshold (breakdown/leakage detection)."""
    abs_i = np.abs(current)
    idx_exceed = np.where(abs_i > threshold_current)[0]
    if len(idx_exceed) == 0:
        return {
            "breakdown_voltage": None,
            "breakdown_current": None,
            "breakdown_index": None,
            "error": f"No |I| exceeds threshold {threshold_current:.1e} A",
        }
    # First point exceeding threshold
    k = int(idx_exceed[0])
    return {
        "breakdown_voltage": float(voltage[k]),
        "breakdown_current": float(current[k]),
        "breakdown_index": k,
        "threshold_a": float(threshold_current),
    }


def fit_iv_curve(
    voltage: np.ndarray,
    current: np.ndarray,
    model: str = "ohmic",
) -> dict:
    """Fit IV data with lmfit using the specified conduction model.

    Supported models:
        "ohmic"       — I = V/R  (linear)
        "schottky"    — ln(I) ∝ sqrt(V)  (high-bias region)
        "sclc"        — log(I) ∝ log(V)  (Space-Charge-Limited Current)
        "pool-frenkel" — ln(I/V) ∝ sqrt(V)

    Returns dict with model, params, metrics (r_squared, rmse, aic, bic), success.
    """
    result = {
        "model": model,
        "params": {},
        "metrics": {"r_squared": None, "rmse": None, "aic": None, "bic": None},
        "success": False,
    }

    if model == "ohmic":
        return _fit_ohmic(voltage, current, result)
    elif model == "schottky":
        return _fit_schottky(voltage, current, result)
    elif model == "sclc":
        return _fit_sclc(voltage, current, result)
    elif model == "pool-frenkel":
        return _fit_pool_frenkel(voltage, current, result)
    else:
        result["error"] = f"Unknown model: {model}"
        return result


def _fit_ohmic(voltage, current, result):
    """I = V/R — linear fit through origin for ohmic region."""
    v = np.asarray(voltage, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()
    n = len(v)

    # Use ±0.1 V window for ohmic region
    mask = np.abs(v) < 0.1
    if mask.sum() < 3:
        mask = np.ones_like(v, dtype=bool)

    v_fit, i_fit = v[mask], i[mask]
    n_fit = len(v_fit)

    p = np.polyfit(v_fit, i_fit, 1)
    slope, intercept = p[0], p[1]
    i_pred = slope * v_fit + intercept
    rmse = float(np.sqrt(np.mean((i_fit - i_pred) ** 2)))
    ss_res = np.sum((i_fit - i_pred) ** 2)
    ss_tot = np.sum((i_fit - np.mean(i_fit)) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    result["params"] = {
        "R_ohm": 1.0 / slope if slope != 0 else float("inf"),
        "slope": float(slope),
        "intercept": float(intercept),
    }
    result["metrics"]["r_squared"] = r_squared
    result["metrics"]["rmse"] = rmse
    result["metrics"]["aic"] = float(n_fit * np.log(ss_res / n_fit) + 4) if n_fit > 0 and ss_res > 0 else None
    result["metrics"]["bic"] = float(n_fit * np.log(ss_res / n_fit) + 4 * np.log(n_fit)) if n_fit > 0 and ss_res > 0 else None
    result["success"] = True
    return result


def _fit_schottky(voltage, current, result):
    """Schottky emission: ln(I) ∝ sqrt(V) for high-bias forward region.

    Fit: ln(I) = a * sqrt(V) + b  for V > 0.1 V (forward bias).
    """
    v = np.asarray(voltage, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()

    # Use forward bias (V > 0) and |I| > 0 for log-space
    mask = (v > 0.1) & (np.abs(i) > 0)
    if mask.sum() < 3:
        mask = (v > 0) & (np.abs(i) > 0)
    if mask.sum() < 3:
        result["error"] = "Insufficient points in forward bias for Schottky fit"
        return result

    v_fit = v[mask]
    i_fit = np.abs(i[mask])
    n_fit = len(v_fit)

    sqrt_v = np.sqrt(v_fit)
    ln_i = np.log(i_fit)

    p = np.polyfit(sqrt_v, ln_i, 1)
    a, b = p[0], p[1]
    ln_i_pred = a * sqrt_v + b
    i_pred = np.exp(ln_i_pred)

    rmse = float(np.sqrt(np.mean((i_fit - i_pred) ** 2)))
    ss_res = np.sum((ln_i - ln_i_pred) ** 2)
    ss_tot = np.sum((ln_i - np.mean(ln_i)) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    result["params"] = {
        "schottky_slope": float(a),
        "schottky_intercept": float(b),
        "phi_b_eV": "needs material constants (A*, T, ε_r)",
    }
    result["metrics"]["r_squared"] = r_squared
    result["metrics"]["rmse"] = rmse
    result["metrics"]["aic"] = float(n_fit * np.log(ss_res / n_fit) + 4) if n_fit > 0 and ss_res > 0 else None
    result["metrics"]["bic"] = float(n_fit * np.log(ss_res / n_fit) + 4 * np.log(n_fit)) if n_fit > 0 and ss_res > 0 else None
    result["success"] = True
    return result


def _fit_sclc(voltage, current, result):
    """Space-Charge-Limited Current: log(I) ∝ n * log(V).

    Fit: log(I) = n * log(V) + b. n≈2 for trap-filled limit.
    Uses positive V, positive I region.
    """
    v = np.asarray(voltage, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()

    mask = (v > 0) & (i > 0)
    if mask.sum() < 3:
        result["error"] = "Insufficient points in forward SCLC region (V>0, I>0)"
        return result

    v_fit = v[mask]
    i_fit = i[mask]
    n_fit = len(v_fit)

    log_v = np.log(v_fit)
    log_i = np.log(i_fit)

    p = np.polyfit(log_v, log_i, 1)
    n_exp, b = p[0], p[1]
    log_i_pred = n_exp * log_v + b
    i_pred = np.exp(log_i_pred)

    rmse = float(np.sqrt(np.mean((i_fit - i_pred) ** 2)))
    ss_res = np.sum((log_i - log_i_pred) ** 2)
    ss_tot = np.sum((log_i - np.mean(log_i)) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    result["params"] = {
        "n_exponent": float(n_exp),
        "log_intercept": float(b),
        "interpretation": "Ohmic" if n_exp < 1.3 else ("SCLC (trap-filled)" if n_exp > 1.7 else "Transition"),
    }
    result["metrics"]["r_squared"] = r_squared
    result["metrics"]["rmse"] = rmse
    result["metrics"]["aic"] = float(n_fit * np.log(ss_res / n_fit) + 4) if n_fit > 0 and ss_res > 0 else None
    result["metrics"]["bic"] = float(n_fit * np.log(ss_res / n_fit) + 4 * np.log(n_fit)) if n_fit > 0 and ss_res > 0 else None
    result["success"] = True
    return result


def _fit_pool_frenkel(voltage, current, result):
    """Poole-Frenkel emission: ln(I/V) ∝ sqrt(V).

    Fit: ln(I/V) = a * sqrt(V) + b for forward bias.
    """
    v = np.asarray(voltage, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()

    mask = (v > 0.1) & (np.abs(i) > 0)
    if mask.sum() < 3:
        mask = (v > 0) & (np.abs(i) > 0)
    if mask.sum() < 3:
        result["error"] = "Insufficient points for Poole-Frenkel fit"
        return result

    v_fit = v[mask]
    i_fit = np.abs(i[mask])
    n_fit = len(v_fit)

    sqrt_v = np.sqrt(v_fit)
    ln_iv = np.log(i_fit / v_fit)

    p = np.polyfit(sqrt_v, ln_iv, 1)
    a, b = p[0], p[1]
    ln_iv_pred = a * sqrt_v + b
    i_pred = v_fit * np.exp(ln_iv_pred)

    rmse = float(np.sqrt(np.mean((i_fit - i_pred) ** 2)))
    ss_res = np.sum((ln_iv - ln_iv_pred) ** 2)
    ss_tot = np.sum((ln_iv - np.mean(ln_iv)) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    result["params"] = {
        "pf_slope": float(a),
        "pf_intercept": float(b),
    }
    result["metrics"]["r_squared"] = r_squared
    result["metrics"]["rmse"] = rmse
    result["metrics"]["aic"] = float(n_fit * np.log(ss_res / n_fit) + 4) if n_fit > 0 and ss_res > 0 else None
    result["metrics"]["bic"] = float(n_fit * np.log(ss_res / n_fit) + 4 * np.log(n_fit)) if n_fit > 0 and ss_res > 0 else None
    result["success"] = True
    return result


def extract_on_off_ratio(
    voltage: np.ndarray,
    current: np.ndarray,
    read_voltage: float = 0.1,
) -> dict:
    """Memristor on/off ratio: I at +read_voltage / |I| at -read_voltage.

    Finds the closest voltage point to ±read_voltage and computes ratio.
    """
    v = np.asarray(voltage, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()

    idx_pos = int(np.argmin(np.abs(v - abs(read_voltage))))
    idx_neg = int(np.argmin(np.abs(v + abs(read_voltage))))

    i_on = i[idx_pos]
    i_off = abs(i[idx_neg])

    ratio = abs(i_on / i_off) if i_off != 0 else float("inf")

    return {
        "on_off_ratio": float(ratio),
        "I_on_A": float(i_on),
        "I_off_A": float(i_off),
        "V_read": float(abs(read_voltage)),
        "V_on_actual": float(v[idx_pos]),
        "V_off_actual": float(v[idx_neg]),
    }


def detect_sweep_segments(
    voltage: np.ndarray,
    time: np.ndarray | None = None,
    min_segment_points: int = 5,
) -> list[dict]:
    """Detect sweep segments by finding voltage direction reversals.

    For each segment returns:
        start_idx, end_idx, direction ("forward"/"reverse"),
        sweep_rate (V/s), voltage_range (V), duration (s).

    Parameters
    ----------
    voltage : np.ndarray
        Voltage trace from the sweep.
    time : np.ndarray or None
        Time vector. If None, uses index-based time.
    min_segment_points : int
        Minimum points per segment (filters noise).

    Returns
    -------
    list[dict]
        Ordered list of sweep segments.
    """
    v = np.asarray(voltage, dtype=float).flatten()
    if time is not None:
        t = np.asarray(time, dtype=float).flatten()
    else:
        t = np.arange(len(v), dtype=float)

    dv = np.diff(v)
    # Sign of voltage step: +1 forward, -1 reverse, 0 flat
    sign = np.sign(dv)
    # Find reversal points where sign changes
    reversals = np.where(np.diff(sign, prepend=sign[0]) != 0)[0]

    # Build segment boundaries
    boundaries = [0] + reversals.tolist() + [len(v) - 1]
    segments = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        n_points = e - s + 1
        if n_points < min_segment_points:
            continue

        # Split at zero-crossing for bipolar sweeps (e.g., +V→0→-V)
        sub_segments = [(s, e)]
        if n_points >= 2 * min_segment_points:
            zv = v[s:e + 1]
            sv = np.sign(np.where(np.abs(zv) < 1e-12, 1e-12, zv))
            zero_cross = np.where(np.diff(sv))[0]
            if len(zero_cross) == 1:
                z = zero_cross[0] + s
                if z - s >= min_segment_points and e - z >= min_segment_points:
                    sub_segments = [(s, z), (z, e)]

        for ss, ee in sub_segments:
            seg_v = v[ss:ee + 1]
            seg_t = t[ss:ee + 1]
            dt = seg_t[-1] - seg_t[0]
            dv_seg = seg_v[-1] - seg_v[0]
            direction = "forward" if dv_seg >= 0 else "reverse"
            sweep_rate = abs(dv_seg / dt) if dt > 0 else 0.0
            segments.append({
                "start_idx": int(ss),
                "end_idx": int(ee),
                "direction": direction,
                "sweep_rate_v_s": float(sweep_rate),
                "voltage_range": float(abs(dv_seg)),
                "duration_s": float(dt),
            })

    return segments
