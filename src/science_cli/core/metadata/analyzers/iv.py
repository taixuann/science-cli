"""IV compliance detection — detect compliance plateau in IV sweep data.

Moved from ``core/metadata/keysight.py`` as part of parsers/ + analyzers/ split.
"""

from __future__ import annotations


def analyze_iv_compliance(
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    """Detect actual compliance events in IV sweep data.

    Examines the current column for compliance limiting (plateau).
    Requires a sustained plateau (3+ consecutive points with near-zero
    current slope) to avoid false positives from low-current regions.

    Returns dict with:
        - in_compliance: bool
        - compliance_current: float or None
        - compliance_voltage: float or None
    """
    import numpy as np

    result: dict = {
        "in_compliance": False,
        "compliance_current": None,
        "compliance_voltage": None,
    }

    current_col = None
    voltage_col = None
    for col in df.columns:
        cl = col.lower().strip()
        if "current" in cl or cl in ("i", "i1", "i2", "i3", "i4"):
            current_col = col
        elif "voltage" in cl or cl in ("v", "v1", "v2"):
            voltage_col = col

    if current_col is None or voltage_col is None:
        return result

    voltages = df[voltage_col].values
    currents = df[current_col].values

    valid = ~(np.isnan(voltages) | np.isnan(currents))
    if valid.sum() < 3:
        return result

    v = voltages[valid].astype(float)
    i = currents[valid].astype(float)

    i_range = float(np.max(i) - np.min(i))
    v_range = float(np.max(v) - np.min(v))

    if i_range <= 0 or v_range <= 0:
        return result

    # Normalise: skip points where current is below 1% of range
    # (low-current regime can't be compliance)
    i_norm = i / i_range
    above_noise = i_norm > 0.01

    if above_noise.sum() < 3:
        return result

    # Only look at points above noise floor
    valid_idx = np.where(above_noise)[0]
    i_active = i[valid_idx]
    v_active = v[valid_idx]

    i_diff = np.abs(np.diff(i_active))
    v_diff = np.abs(np.diff(v_active))

    # Detect sustained plateau: 3+ consecutive near-zero current slopes
    plateau_threshold = 0.02 * i_range
    v_change_threshold = 0.01 * v_range

    # Find runs of consecutive plateau points
    # A point is "flat" if current change is tiny and voltage is still changing
    flat_pt_mask = (i_diff < plateau_threshold) & (v_diff > v_change_threshold)

    # Require at least 2 consecutive flat segments (3 flat points)
    run_count = 0
    plateau_start_idx = None
    for j in range(len(flat_pt_mask)):
        if flat_pt_mask[j]:
            if run_count == 0:
                plateau_start_idx = j
            run_count += 1
            if run_count >= 2:  # 2+ consecutive flat diffs = sustained plateau
                # plateau_start_idx is the index into i_diff/v_diff arrays.
                # The first plateau data point is at plateau_start_idx
                # in the i_active/v_active arrays, which maps back to
                # valid_idx[plateau_start_idx] in the original array.
                first_plateau = valid_idx[plateau_start_idx]
                result["in_compliance"] = True
                result["compliance_current"] = float(i[first_plateau])
                result["compliance_voltage"] = float(v[first_plateau])
                return result
        else:
            run_count = 0
            plateau_start_idx = None

    return result
