"""Retention analysis: decay modeling, extrapolation, lifetime estimation."""

import numpy as np
from science_cli.memristor.models import RetentionData


def analyze_retention(
    time: np.ndarray,
    resistance: np.ndarray,
) -> dict:
    """Analyze retention time series.

    Returns dict with decay rate, model type, extrapolated 10yr resistance,
    lifetime, and goodness of fit.
    """
    t = np.asarray(time, dtype=float).flatten()
    r = np.asarray(resistance, dtype=float).flatten()

    # Ensure positive time
    mask = t > 0
    t = t[mask]
    r = r[mask]

    if len(t) < 3:
        return {
            "decay_rate": None,
            "decay_model": None,
            "extrapolated_10yr": None,
            "lifetime_hours": None,
            "r_squared": None,
            "error": "Insufficient data points (need ≥3)",
        }

    # Fit log-time model: R = a * log10(t) + b
    log_t = np.log10(t)
    coeffs_log = np.polyfit(log_t, r, 1)
    r_pred_log = np.polyval(coeffs_log, log_t)
    ss_res_log = np.sum((r - r_pred_log) ** 2)
    ss_tot_log = np.sum((r - np.mean(r)) ** 2)
    r2_log = float(1 - ss_res_log / ss_tot_log) if ss_tot_log > 0 else 0.0
    decay_rate = float(coeffs_log[0])

    # Fit power-law model: R = a * t^b
    log_r = np.log(r)
    coeffs_power = np.polyfit(log_t, log_r, 1)
    log_r_pred = np.polyval(coeffs_power, log_t)
    r_pred_power = np.exp(log_r_pred)
    ss_res_power = np.sum((r - r_pred_power) ** 2)
    ss_tot_power = np.sum((r - np.mean(r)) ** 2)
    r2_power = float(1 - ss_res_power / ss_tot_power) if ss_tot_power > 0 else 0.0

    # Choose better model
    if r2_log >= r2_power:
        decay_model = "log"
        r_squared = r2_log
        a_log, b_log = coeffs_log[0], coeffs_log[1]
        # Extrapolate to 10 years (315360000 seconds)
        t_10yr = 10 * 365.25 * 24 * 3600  # seconds
        extrapolated_10yr = float(a_log * np.log10(t_10yr) + b_log)
    else:
        decay_model = "power"
        r_squared = r2_power
        a_power, b_power = np.exp(coeffs_power[1]), coeffs_power[0]
        extrapolated_10yr = float(a_power * (10 * 365.25 * 24 * 3600) ** b_power)

    # Lifetime: time to reach ratio threshold (R falls to 50% or rises to 200%)
    r_initial = r[0]
    threshold = min(r_initial * 0.5, r_initial * 2.0)
    if decay_model == "log":
        t_lifetime = 10 ** ((threshold - b_log) / a_log) if a_log != 0 else float("inf")
    else:
        t_lifetime = (threshold / a_power) ** (1 / b_power) if a_power != 0 and b_power != 0 else float("inf")

    lifetime_hours = float(t_lifetime / 3600.0) if np.isfinite(t_lifetime) else None

    return {
        "decay_rate": decay_rate,
        "decay_model": decay_model,
        "extrapolated_10yr": extrapolated_10yr,
        "lifetime_hours": lifetime_hours,
        "r_squared": r_squared,
        "test_duration_hours": float(t[-1] / 3600.0),
        "n_points": int(len(t)),
    }


def retention_summary(data: RetentionData) -> str:
    """Human-readable retention summary."""
    stats = analyze_retention(data.time, data.resistance)

    lines = [
        f"Retention @ {data.temperature} K: "
        f"{stats['test_duration_hours']:.1f} h test, {stats['n_points']} points"
    ]
    lines.append(
        f"  Model: {stats['decay_model']} "
        f"(R²={stats['r_squared']:.4f})"
    )
    lines.append(f"  Decay rate: {stats['decay_rate']:.3e} Ω/decade")

    if stats["extrapolated_10yr"] is not None:
        lines.append(f"  R(10yr): {stats['extrapolated_10yr']:.1f} Ω")

    if stats["lifetime_hours"] is not None:
        days = stats["lifetime_hours"] / 24
        years = days / 365.25
        lines.append(
            f"  Lifetime: {stats['lifetime_hours']:.0f} h "
            f"({days:.0f} days, {years:.2f} years)"
        )
    else:
        lines.append(f"  Lifetime: unable to estimate")

    return "\n".join(lines)
