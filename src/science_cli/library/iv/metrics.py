"""V_set/V_reset detection metrics — extracted from memristor/switching.py."""
import warnings

import numpy as np


def detect_vset(voltage, current, v_read=0.1):
    """Detect V_set using SCLC Log-Log slope method with derivative + threshold fallbacks.
    Operates on forward branch (0 -> +Vmax). Returns (V_set, index) or (None, None).
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    if len(voltage) < 10:
        return None, None

    segments = _split_at_reversals(voltage)
    if not segments:
        return None, None

    forward_seg = None
    for start, end in segments:
        v_seg = voltage[start:end]
        if len(v_seg) < 5:
            continue
        if float(np.max(v_seg)) > 0.5:
            forward_seg = (start, end, v_seg, current[start:end])
            break

    if forward_seg is None:
        return None, None

    seg_start, _seg_end, v_seg, i_seg = forward_seg

    i_median_start = float(np.median(np.abs(i_seg[:max(5, len(i_seg)//10)])))
    i_max = float(np.max(np.abs(i_seg)))
    if i_median_start <= 0 or i_max / i_median_start < 10:
        return None, None

    sclc_vset = None
    sclc_idx = None
    pos_mask = np.abs(v_seg) >= 0.05
    if np.sum(pos_mask) >= 5:
        v_pos = np.abs(v_seg[pos_mask])
        i_pos = np.abs(i_seg[pos_mask])
        log_v = np.log10(v_pos)
        log_i = np.log10(i_pos + 1e-30)
        log_i_smoothed = np.convolve(log_i, np.ones(3)/3, mode='same')
        log_i_smoothed[0] = log_i[0]
        log_i_smoothed[-1] = log_i[-1]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            dlogi_dlogv = np.gradient(log_i_smoothed, log_v)

        switching_points = np.where((dlogi_dlogv >= 3.0) & (i_pos > 1e-8))[0]
        if len(switching_points) > 0:
            diffs = np.diff(switching_points)
            plateau_breaks = np.where(diffs > 1)[0]
            plateau_starts = np.concatenate([[0], plateau_breaks + 1])
            plateau_ends = np.concatenate([plateau_breaks + 1, [len(switching_points)]])

            best_score = -1.0
            n_first_baseline = max(3, len(i_pos) // 15)
            baseline_i = float(np.median(np.abs(i_pos[:n_first_baseline])))
            if baseline_i <= 0:
                baseline_i = 1e-15

            for ps, pe in zip(plateau_starts, plateau_ends):
                p_len = pe - ps
                if p_len < 1:
                    continue
                plateau_slopes = dlogi_dlogv[switching_points[ps:pe]]
                p_max_slope = float(np.max(plateau_slopes))
                p_first_idx = switching_points[ps]
                i_at_start = float(np.abs(i_pos[p_first_idx]))
                i_ratio = i_at_start / baseline_i
                if i_ratio < 1:
                    i_ratio = 1.0
                score = p_len * p_max_slope * np.log10(max(i_ratio, 2.0))
                if score > best_score:
                    best_score = score
                    sclc_vset = float(v_pos[p_first_idx])
                    pos_indices = np.where(pos_mask)[0]
                    sclc_idx = int(seg_start + pos_indices[p_first_idx])

    log_i = np.log10(np.abs(i_seg) + 1e-30)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        dlogi_dv = np.gradient(log_i, v_seg)
    valid = np.isfinite(dlogi_dv)
    deriv_vset = None
    deriv_idx = None
    if np.any(valid):
        max_idx = int(np.argmax(dlogi_dv[valid]))
        deriv_vset = float(np.abs(v_seg[valid][max_idx]))
        deriv_idx = int(seg_start + np.where(valid)[0][max_idx])

    n_first = max(5, len(i_seg) // 10)
    baseline = float(np.median(np.abs(i_seg[:n_first])))
    thresh_vset = None
    thresh_idx = None
    if baseline > 0:
        threshold = baseline * 10.0
        above = np.where(np.abs(i_seg) > threshold)[0]
        if len(above) > 0:
            thresh_vset = float(np.abs(v_seg[above[0]]))
            thresh_idx = int(seg_start + above[0])

    if sclc_vset is not None:
        return sclc_vset, sclc_idx

    candidates = []
    cand_indices = []
    if deriv_vset is not None:
        candidates.append(deriv_vset)
        cand_indices.append(deriv_idx)
    if thresh_vset is not None:
        candidates.append(thresh_vset)
        cand_indices.append(thresh_idx)

    if candidates:
        best = min(range(len(candidates)), key=lambda k: candidates[k])
        return candidates[best], cand_indices[best]
    return None, None


def detect_vreset(voltage, current, v_read=0.1):
    """Detect V_reset using derivative minimum + current-drop threshold.
    Operates on negative sweep segments. Returns (V_reset, index) or (None, None).
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    if len(voltage) < 10:
        return None, None

    segments = _split_at_reversals(voltage)
    if not segments:
        return None, None

    neg_seg = None
    for start, end in segments:
        v_seg = voltage[start:end]
        if len(v_seg) < 5:
            continue
        if float(np.min(v_seg)) < -0.5:
            neg_seg = (start, v_seg, current[start:end])
            break

    if neg_seg is None:
        return None, None

    seg_start, v_seg, i_seg = neg_seg

    log_i = np.log10(np.abs(i_seg) + 1e-30)
    dlogi_dv = np.gradient(log_i, v_seg)
    valid = np.isfinite(dlogi_dv)
    deriv_vreset = None
    deriv_idx = None
    if np.any(valid):
        min_idx = int(np.argmin(dlogi_dv[valid]))
        deriv_vreset = float(np.abs(v_seg[valid][min_idx]))
        deriv_idx = int(seg_start + np.where(valid)[0][min_idx])

    n_first = max(5, len(i_seg) // 10)
    baseline = float(np.median(np.abs(i_seg[:n_first])))
    thresh_vreset = None
    thresh_idx = None
    if baseline > 0:
        threshold = baseline * 0.3
        below = np.where(np.abs(i_seg) < threshold)[0]
        if len(below) > 0:
            thresh_vreset = float(np.abs(v_seg[below[0]]))
            thresh_idx = int(seg_start + below[0])

    candidates = []
    cand_indices = []
    if deriv_vreset is not None:
        candidates.append(deriv_vreset)
        cand_indices.append(deriv_idx)
    if thresh_vreset is not None:
        candidates.append(thresh_vreset)
        cand_indices.append(thresh_idx)

    if candidates:
        best = min(range(len(candidates)), key=lambda k: candidates[k])
        return candidates[best], cand_indices[best]
    return None, None


def compute_on_off_ratio(voltage, current, v_read=0.1):
    """Compute ON/OFF resistance ratio from a bipolar IV sweep."""
    empty = {"v_read": float(v_read), "i_on": None, "i_off": None, "r_on": None, "r_off": None, "ratio": None}
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]
    if len(voltage) < 10:
        return empty
    segments = _split_at_reversals(voltage)
    if len(segments) < 2:
        return empty
    forward_branch = None
    backward_branch = None
    for idx, (start, end) in enumerate(segments):
        v_seg = voltage[start:end]
        i_seg = current[start:end]
        if len(v_seg) < 3:
            continue
        v_min, v_max = float(np.min(v_seg)), float(np.max(v_seg))
        if v_read < v_min or v_read > v_max:
            continue
        if forward_branch is None and float(np.mean(np.diff(v_seg))) > 0:
            forward_branch = (v_seg, i_seg)
        elif backward_branch is None:
            backward_branch = (v_seg, i_seg)
    if forward_branch is None and len(segments) >= 1:
        start, end = segments[0]
        forward_branch = (voltage[start:end], current[start:end])
    if backward_branch is None and len(segments) >= 2:
        start, end = segments[1]
        backward_branch = (voltage[start:end], current[start:end])
    i_off = None
    i_on = None
    if forward_branch is not None:
        v_fwd, i_fwd = forward_branch
        if len(v_fwd) >= 2:
            try:
                sort_idx = np.argsort(v_fwd)
                i_off = float(np.interp(v_read, v_fwd[sort_idx], np.abs(i_fwd[sort_idx])))
            except (ValueError, TypeError):
                i_off = None
    if backward_branch is not None:
        v_bwd, i_bwd = backward_branch
        if len(v_bwd) >= 2:
            try:
                sort_idx = np.argsort(v_bwd)
                i_on = float(np.interp(v_read, v_bwd[sort_idx], np.abs(i_bwd[sort_idx])))
            except (ValueError, TypeError):
                i_on = None
    r_on = float(v_read / i_on) if i_on and i_on > 0 else None
    r_off = float(v_read / i_off) if i_off and i_off > 0 else None
    ratio = float(r_off / r_on) if r_on is not None and r_off is not None and r_on > 0 else None
    return {"v_read": float(v_read), "i_on": i_on, "i_off": i_off, "r_on": r_on, "r_off": r_off, "ratio": ratio}


def extract_iv_parameters(voltage, current, v_read=0.1):
    """Extract IV parameters: Vset, Vreset, ON/OFF ratio."""
    v_set, v_set_idx = detect_vset(voltage, current, v_read)
    v_reset, v_reset_idx = detect_vreset(voltage, current, v_read)
    ratio_data = compute_on_off_ratio(voltage, current, v_read)
    switching_detected = v_set is not None or v_reset is not None
    return {
        "v_set": v_set, "v_reset": v_reset,
        "v_set_idx": v_set_idx, "v_reset_idx": v_reset_idx,
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


def _current_at_voltage(v_target, voltage, current):
    if v_target is None:
        return None
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    idx = int(np.argmin(np.abs(voltage - v_target)))
    return float(current[idx])


def _split_at_reversals(voltage, hysteresis=0.1):
    """Split voltage array at reversal points (direction changes)."""
    v = np.asarray(voltage, dtype=float)
    if len(v) < 3:
        return [(0, len(v) - 1)]
    dv = np.diff(v)
    nonzero = dv[np.abs(dv) > 1e-10]
    median_dv = float(np.median(nonzero)) if len(nonzero) > 0 else 0.0
    going_up = median_dv > 0
    current_min = float(v[0])
    current_max = float(v[0])
    segments = []
    start_idx = 0
    for i in range(1, len(v)):
        val = float(v[i])
        if val > current_max:
            current_max = val
        if val < current_min:
            current_min = val
        if going_up:
            if current_max - val >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = False
                current_min = val
                current_max = val
        else:
            if val - current_min >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = True
                current_min = val
                current_max = val
    if len(v) > start_idx:
        segments.append((start_idx, len(v) - 1))
    return segments if segments else [(0, len(v) - 1)]
