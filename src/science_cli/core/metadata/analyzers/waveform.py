"""Waveform pulse analysis — detect voltage plateaus, compute pulse parameters.

DataFrame-compute functions live here; header-parse functions live in
``parsers/waveform.py``. Moved from ``core/metadata/waveform.py`` as part of
parsers/ + analyzers/ split.
"""

from __future__ import annotations

import numpy as np


def _find_voltage_column(df):
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("voltage", "v", "v1", "measresult1_value"):
            return col
    return None


def _find_time_column(df):
    for col in df.columns:
        cl = col.lower().strip()
        if cl == "time" or (cl.startswith("time") and "measresult1_time" not in cl):
            return col
    for col in df.columns:
        cl = col.lower().strip()
        if "measresult1_time" in cl:
            return col
    return None


def _detect_voltage_levels(v, n_bins=100, n_levels=3):
    hist, edges = np.histogram(v, bins=n_bins)
    peaks = []
    for i in range(len(hist)):
        left = hist[i - 1] if i > 0 else 0
        right = hist[i + 1] if i + 1 < len(hist) else 0
        if hist[i] > left and hist[i] >= right and hist[i] > 1:
            peak_v = (edges[i] + edges[i + 1]) / 2
            peaks.append((peak_v, hist[i]))
    peaks.sort(key=lambda x: x[1], reverse=True)
    levels = sorted(peaks[:n_levels], key=lambda x: x[0])
    return [level[0] for level in levels]


def _find_crossing_time(t, v, level, direction="rising"):
    if direction == "rising":
        cross = np.where(v >= level)[0]
    else:
        cross = np.where(v <= level)[0]
    if len(cross) == 0:
        return None
    idx = cross[0]
    if idx > 0:
        v0, v1 = v[idx - 1], v[idx]
        t0, t1 = t[idx - 1], t[idx]
        if v1 != v0:
            frac = (level - v0) / (v1 - v0)
            return t0 + frac * (t1 - t0)
    return float(t[idx])


def analyze_waveform_params(
    df,
    raw_lines: list[str] | None = None,
    inputs: dict | None = None,
) -> dict:
    voltage_col = _find_voltage_column(df)
    time_col = _find_time_column(df)
    if voltage_col is None or time_col is None:
        return {}
    v_raw = df[voltage_col].values.astype(float)
    t_raw = df[time_col].values.astype(float)
    idx = np.argsort(t_raw)
    t = t_raw[idx]
    v = v_raw[idx]
    t_us = t * 1e6
    levels = _detect_voltage_levels(v)
    if len(levels) < 2:
        return {}
    v_set = levels[-1]
    v_read = levels[-2] if len(levels) >= 2 else levels[0]
    if v_set < v_read:
        v_set, v_read = v_read, v_set
    if v_set <= 0:
        return {}
    rise_10 = v_set * 0.1
    rise_50 = v_set * 0.5
    rise_90 = v_set * 0.9
    t_start = _find_crossing_time(t_us, v, rise_10, "rising")
    t_50 = _find_crossing_time(t_us, v, rise_50, "rising")
    t_90 = _find_crossing_time(t_us, v, rise_90, "rising")
    result = {"v_set_v": float(v_set), "v_read_v": float(v_read)}
    if t_start is None or t_50 is None:
        result["repeat_pattern"] = _detect_repeat_pattern(t_raw)
        return result
    v_set_med = np.median(v[v >= np.percentile(v, 75)])
    last_high = np.where(v >= v_set_med * 0.95)[0]
    if len(last_high) > 0:
        si = last_high[-1]
        ft = t_us[si:]
        fv = v[si:]
        v_transition_10 = v_read + (v_set - v_read) * 0.1
        t_fall_90 = _find_crossing_time(ft, fv, rise_90, "falling")
        t_fall_50 = _find_crossing_time(ft, fv, rise_50, "falling")
        t_fall_trans_10 = _find_crossing_time(ft, fv, v_transition_10, "falling")
    else:
        t_fall_90 = t_fall_50 = t_fall_trans_10 = None
    if t_50 is not None and t_fall_50 is not None:
        result["set_width_us"] = float(t_fall_50 - t_50)
    if t_start is not None and t_90 is not None:
        result["rise_us"] = float(t_90 - t_start)
    if t_fall_90 is not None and t_fall_trans_10 is not None:
        result["fall_us"] = float(t_fall_trans_10 - t_fall_90)
    if v_read > 0 and t_fall_50 is not None:
        after_fall = np.where(t_us >= t_fall_50)[0]
        if len(after_fall) > 0:
            rf = after_fall[0]
            read_stable = np.where(v[rf:] <= v_read * 1.1)[0]
            if len(read_stable) > 0:
                read_stable_t = t_us[rf + read_stable[0]]
                result["read_width_us"] = float(t_us[-1] - read_stable_t)
    result["repeat_pattern"] = _detect_repeat_pattern(t_raw)
    return result


def _detect_repeat_pattern(t: np.ndarray) -> str:
    wraps = int(np.sum(np.diff(t) < 0))
    return "repeated" if wraps > 0 else "single"


def _estimate_repeats(t: np.ndarray) -> int:
    wraps = int(np.sum(np.diff(t) < 0))
    if wraps > 0:
        return wraps + 1
    uq = np.unique(t)
    return max(1, int(round(len(t) / max(1, len(uq)))))


def detect_repeat_pattern(df) -> dict:
    time_col = _find_time_column(df)
    if time_col is None:
        return {"repeat_pattern": "single", "n_repeats": 1}
    t = df[time_col].values.astype(float)
    n = _estimate_repeats(t)
    return {
        "repeat_pattern": "repeated" if n > 1 else "single",
        "n_repeats": n,
    }


def detect_waveform_pattern_2d(df, max_points: int = 200) -> list[list[float]]:
    """Detect pulse waveform and return canonical 2D [[t, v], ...] array.

    Time in seconds, voltage in volts. Sorted by time.
    Subsampled to max_points evenly-spaced points to keep protocol.yaml small.
    Returns [] if no time/voltage column found.
    """
    voltage_col = _find_voltage_column(df)
    time_col = _find_time_column(df)
    if voltage_col is None or time_col is None:
        return []
    t = df[time_col].values.astype(float)
    v = df[voltage_col].values.astype(float)
    idx = np.argsort(t)
    t, v = t[idx], v[idx]
    if len(t) > max_points:
        step = len(t) // max_points
        t = t[::step][:max_points]
        v = v[::step][:max_points]
    return [[float(ti), float(vi)] for ti, vi in zip(t, v)]


def extract_waveform_metadata(
    df,
    study_name: str | None = None,
    device_type: str | None = None,
) -> dict:
    """Orchestrator: return waveform_pattern (2D) + derived scalars.

    Used when a study has data_shape.kind == "waveform_2d". Combines:
      - waveform_pattern: 2D [[t, v], ...] for plotting/illustration
      - derived scalars: v_set_v, v_read_v, set_width_us, read_width_us,
                         rise_us, fall_us, repeat_pattern, n_repeats

    The device_type parameter is reserved for future per-device specialization
    (e.g. volatile vs non-volatile memristor may emphasize different regions).
    """
    pattern = detect_waveform_pattern_2d(df)
    scalars = analyze_waveform_params(df, raw_lines=None, inputs={})
    repeats = detect_repeat_pattern(df)
    return {
        "waveform_pattern": pattern,
        **scalars,
        **repeats,
    }


def invert_current_sign(df):
    result = df.copy()
    for col in result.columns:
        cl = col.lower().strip()
        if cl in ("current", "measresult2_value", "i", "i1", "i2"):
            result[col] = result[col] * -1
    return result
