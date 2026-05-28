"""Switching analysis: V_set/V_reset statistics, Weibull fits, IV parameter extraction."""

import logging
from pathlib import Path

import numpy as np

from science_cli.library.memristor.models import SwitchingData
from science_cli.library.memristor.plotting import _split_at_reversals, read_iv_csv

logger = logging.getLogger(__name__)


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


def _current_at_voltage(v_target, voltage, current):
    """Return the current at the point closest to v_target."""
    if v_target is None:
        return None
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    idx = int(np.argmin(np.abs(voltage - v_target)))
    return float(current[idx])


def extract_iv_parameters(voltage, current, v_read=0.1) -> dict:
    """Extract IV parameters: Vset, Vreset, ON/OFF ratio.

    Convenience wrapper calling detect_vset, detect_vreset, compute_on_off_ratio.
    """
    v_set = detect_vset(voltage, current, v_read)
    v_reset = detect_vreset(voltage, current, v_read)
    ratio_data = compute_on_off_ratio(voltage, current, v_read)
    switching_detected = v_set is not None or v_reset is not None
    return {
        "v_set": v_set,
        "v_reset": v_reset,
        "i_set": _current_at_voltage(v_set, voltage, current),
        "i_reset": _current_at_voltage(v_reset, voltage, current),
        "on_off_ratio": ratio_data.get("ratio"),
        "v_read": v_read,
        "i_on": ratio_data.get("i_on"),
        "i_off": ratio_data.get("i_off"),
        "r_on": ratio_data.get("r_on"),
        "r_off": ratio_data.get("r_off"),
        "switching_detected": switching_detected,
    }


def detect_vset(voltage, current, v_read=0.1):
    """Detect V_set — the voltage at which the device switches from HRS to LRS.

    Operates on the forward branch (0→+Vmax) of a bipolar IV sweep.
    Uses a combined derivative + threshold method to capture both
    abrupt and gradual switching.

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        v_read: Read voltage (V), not used directly but kept for
            interface consistency.

    Returns:
        V_set voltage magnitude (positive float), or None if no
        clear switching is detected.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    if len(voltage) < 10:
        return None

    segments = _split_at_reversals(voltage)
    if not segments:
        return None

    # Find the forward branch: first segment where voltage goes
    # significantly positive (max > 0.5 V)
    forward_seg = None
    for start, end in segments:
        v_seg = voltage[start:end]
        if len(v_seg) < 5:
            continue
        if float(np.max(v_seg)) > 0.5:
            forward_seg = (v_seg, current[start:end])
            break

    if forward_seg is None:
        return None

    v_seg, i_seg = forward_seg

    # ── Derivative method: d(log10|I|)/dV maximum ──
    log_i = np.log10(np.abs(i_seg) + 1e-30)
    dlogi_dv = np.gradient(log_i, v_seg)
    valid = np.isfinite(dlogi_dv)
    if np.any(valid):
        max_idx = int(np.argmax(dlogi_dv[valid]))
        deriv_vset = float(np.abs(v_seg[valid][max_idx]))
    else:
        deriv_vset = None

    # ── Threshold method: current exceeds baseline × 10 ──
    n_first = max(5, len(i_seg) // 10)
    baseline = float(np.median(np.abs(i_seg[:n_first])))
    if baseline <= 0:
        thresh_vset = None
    else:
        threshold = baseline * 10.0
        above = np.where(np.abs(i_seg) > threshold)[0]
        if len(above) > 0:
            thresh_vset = float(np.abs(v_seg[above[0]]))
        else:
            thresh_vset = None

    # ── Pick earlier (lower-voltage) result ──
    candidates = []
    if deriv_vset is not None:
        candidates.append(deriv_vset)
    if thresh_vset is not None:
        candidates.append(thresh_vset)

    if candidates:
        return min(candidates)
    return None


def detect_vreset(voltage, current, v_read=0.1):
    """Detect V_reset — the voltage at which the device switches from LRS to HRS.

    Operates on negative sweep segments of a bipolar IV sweep.
    Uses combined derivative (minimum) + current-drop threshold detection.

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        v_read: Read voltage (V), not used directly but kept for
            interface consistency.

    Returns:
        V_reset voltage magnitude (positive float), or None if no
        clear reset is detected.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    if len(voltage) < 10:
        return None

    segments = _split_at_reversals(voltage)
    if not segments:
        return None

    # Find the negative-going segment: first segment where voltage
    # drops below -0.5 V
    neg_seg = None
    for start, end in segments:
        v_seg = voltage[start:end]
        if len(v_seg) < 5:
            continue
        if float(np.min(v_seg)) < -0.5:
            neg_seg = (v_seg, current[start:end])
            break

    if neg_seg is None:
        return None

    v_seg, i_seg = neg_seg

    # ── Derivative method: d(log10|I|)/dV minimum ──
    # The reset event corresponds to a rapid drop in current →
    # most negative derivative of log(|I|) vs V
    log_i = np.log10(np.abs(i_seg) + 1e-30)
    dlogi_dv = np.gradient(log_i, v_seg)
    valid = np.isfinite(dlogi_dv)
    if np.any(valid):
        min_idx = int(np.argmin(dlogi_dv[valid]))
        deriv_vreset = float(np.abs(v_seg[valid][min_idx]))
    else:
        deriv_vreset = None

    # ── Threshold method: current drops below baseline × factor ──
    # Use the median of the first 10% of points on the negative-going
    # segment as baseline (device is in LRS near 0 V on the negative sweep).
    n_first = max(5, len(i_seg) // 10)
    baseline = float(np.median(np.abs(i_seg[:n_first])))
    if baseline <= 0:
        thresh_vreset = None
    else:
        # Reset: current drops to 30% of baseline
        threshold = baseline * 0.3
        below = np.where(np.abs(i_seg) < threshold)[0]
        if len(below) > 0:
            thresh_vreset = float(np.abs(v_seg[below[0]]))
        else:
            thresh_vreset = None

    candidates = []
    if deriv_vreset is not None:
        candidates.append(deriv_vreset)
    if thresh_vreset is not None:
        candidates.append(thresh_vreset)

    if candidates:
        return min(candidates)
    return None


def compute_on_off_ratio(voltage, current, v_read=0.1):
    """Compute ON/OFF resistance ratio from a bipolar IV sweep.

    Splits the sweep into forward (0→+Vmax) and backward (+Vmax→0)
    branches using reversal detection, interpolates the current at
    ``v_read`` on each branch, and reports resistances + ratio.

    - Forward branch (device in HRS before switching) → I_off
    - Backward branch (device in LRS after switching) → I_on

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        v_read: Read voltage at which to assess the ON/OFF ratio (V).

    Returns:
        Dict with keys: ``v_read``, ``i_on``, ``i_off``, ``r_on``,
        ``r_off``, ``ratio``. Values are ``None`` when the sweep
        cannot be meaningfully split or ``v_read`` is outside the
        voltage range.
    """
    empty = {
        "v_read": float(v_read),
        "i_on": None,
        "i_off": None,
        "r_on": None,
        "r_off": None,
        "ratio": None,
    }

    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    if len(voltage) < 10:
        return empty

    segments = _split_at_reversals(voltage)
    if len(segments) < 2:
        # Single-direction sweep — cannot distinguish on/off branches
        return empty

    # Forward branch: first segment that goes significantly positive
    # and spans v_read.
    forward_branch = None
    backward_branch = None

    for idx, (start, end) in enumerate(segments):
        v_seg = voltage[start:end]
        i_seg = current[start:end]
        if len(v_seg) < 3:
            continue

        v_min, v_max = float(np.min(v_seg)), float(np.max(v_seg))

        # Check if this segment spans v_read
        if v_read < v_min or v_read > v_max:
            continue

        if forward_branch is None and float(np.mean(np.diff(v_seg))) > 0:
            # Positive-going segment → forward (charging from 0→+V)
            forward_branch = (v_seg, i_seg)
        elif backward_branch is None:
            # Next segment that spans v_read → backward (return from +V→0)
            backward_branch = (v_seg, i_seg)

    # Fallback: use first two segments unconditionally
    if forward_branch is None and len(segments) >= 1:
        start, end = segments[0]
        forward_branch = (voltage[start:end], current[start:end])
    if backward_branch is None and len(segments) >= 2:
        start, end = segments[1]
        backward_branch = (voltage[start:end], current[start:end])

    # Interpolate — sort by voltage since np.interp requires
    # monotonically increasing x-values.
    i_off = None
    i_on = None

    if forward_branch is not None:
        v_fwd, i_fwd = forward_branch
        if len(v_fwd) >= 2:
            try:
                sort_idx = np.argsort(v_fwd)
                i_off = float(np.interp(
                    v_read, v_fwd[sort_idx], np.abs(i_fwd[sort_idx]),
                ))
            except (ValueError, TypeError):
                i_off = None

    if backward_branch is not None:
        v_bwd, i_bwd = backward_branch
        if len(v_bwd) >= 2:
            try:
                sort_idx = np.argsort(v_bwd)
                i_on = float(np.interp(
                    v_read, v_bwd[sort_idx], np.abs(i_bwd[sort_idx]),
                ))
            except (ValueError, TypeError):
                i_on = None

    # Compute resistances and ratio
    r_on = float(v_read / i_on) if i_on and i_on > 0 else None
    r_off = float(v_read / i_off) if i_off and i_off > 0 else None
    if r_on is not None and r_off is not None and r_on > 0:
        ratio = float(r_off / r_on)
    else:
        ratio = None

    return {
        "v_read": float(v_read),
        "i_on": i_on,
        "i_off": i_off,
        "r_on": r_on,
        "r_off": r_off,
        "ratio": ratio,
    }


def analyze_all_devices(config, results_dir):
    """Run switching analysis across all IV files in a DeviceConfig.

    Reads each IV CSV file, extracts V_set, V_reset, and ON/OFF ratio,
    and aggregates statistics across the full device matrix.

    Args:
        config: DeviceConfig instance loaded from devices.yaml.
        results_dir: Directory containing (or sibling to) raw data
            files. Raw files are resolved as ``results_dir.parent /
            fe.file``.

    Returns:
        dict with:
          - per_device: {(row, col): {v_set, v_reset, ratio, ...}}
          - aggregate: {median_vset, median_vreset, median_ratio,
            yield_pct}
          - histograms: {vset_bins, vset_counts, vreset_bins,
            vreset_counts, ratio_bins, ratio_counts}
    """
    results_dir = Path(results_dir)
    per_device = {}
    all_vset = []
    all_vreset = []
    all_ratios = []
    switching_count = 0
    total_count = 0

    for pt, fe in config.get_all_files("iv"):
        try:
            filepath = results_dir.parent / fe.file
            voltage, current, _info = read_iv_csv(filepath)
            params = extract_iv_parameters(voltage, current)

            key = (pt.row, pt.col)
            per_device[key] = params

            if params.get("switching_detected"):
                switching_count += 1
            if params.get("v_set") is not None:
                all_vset.append(float(params["v_set"]))
            if params.get("v_reset") is not None:
                all_vreset.append(float(params["v_reset"]))
            if params.get("on_off_ratio") is not None:
                all_ratios.append(float(params["on_off_ratio"]))
            total_count += 1

        except Exception:
            logger.warning(f"Skipping unreadable file: {fe.file}", exc_info=True)

    # ── Aggregate statistics ──
    aggregate = {
        "median_vset": float(np.median(all_vset)) if all_vset else None,
        "median_vreset": float(np.median(all_vreset)) if all_vreset else None,
        "median_ratio": float(np.median(all_ratios)) if all_ratios else None,
        "yield_pct": (switching_count / total_count * 100.0)
        if total_count > 0
        else 0.0,
        "n_devices": total_count,
        "n_switching": switching_count,
    }

    # ── Histograms ──
    histograms = {}
    if all_vset:
        n_bins = min(10, max(3, len(all_vset) // 5))
        counts, bin_edges = np.histogram(all_vset, bins=n_bins)
        histograms["vset_bins"] = bin_edges.tolist()
        histograms["vset_counts"] = counts.tolist()

    if all_vreset:
        n_bins = min(10, max(3, len(all_vreset) // 5))
        counts, bin_edges = np.histogram(all_vreset, bins=n_bins)
        histograms["vreset_bins"] = bin_edges.tolist()
        histograms["vreset_counts"] = counts.tolist()

    if all_ratios:
        n_bins = min(10, max(3, len(all_ratios) // 5))
        counts, bin_edges = np.histogram(all_ratios, bins=n_bins)
        histograms["ratio_bins"] = bin_edges.tolist()
        histograms["ratio_counts"] = counts.tolist()

    return {
        "per_device": per_device,
        "aggregate": aggregate,
        "histograms": histograms,
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
