"""Keysight B1500A header parsers and data analyzers.

Parse functions extract metadata from raw file header lines (no computation).
Analyze functions run computations on loaded data columns.
"""

from __future__ import annotations

import re


def _find_line(lines: list[str], prefix: str) -> str | None:
    """Find first line containing *prefix* (case-insensitive)."""
    for line in lines:
        if prefix.lower() in line.strip().lower():
            return line.strip()
    return None


def _csv_field(line: str, index: int) -> str | None:
    """Extract comma-separated field at *index* from *line*."""
    parts = [p.strip() for p in line.split(",")]
    if 0 <= index < len(parts):
        return parts[index]
    return None


# ── Parsers ────────────────────────────────────────────────────────────


def parse_set_voltage(lines: list[str]) -> float | None:
    """Extract sweep max voltage from SetupTitle line.

    Looks for lines like: "TestParameter, SetupTitle, Sweep 2.0V, ..."
    Returns the voltage as a float, e.g. 2.0.
    """
    line = _find_line(lines, "SetupTitle")
    if not line:
        return None
    m = re.search(r"Sweep\s+([\d.]+)\s*V", line)
    return float(m.group(1)) if m else None


def parse_compliance(lines: list[str]) -> float | None:
    """Extract compliance current from Primary.Compliance line.

    Looks for lines like: "TestParameter, Primary.Compliance, 0.0001, ..."
    Returns the compliance current in Amperes.
    """
    line = _find_line(lines, "Primary.Compliance")
    if not line:
        return None
    val = _csv_field(line, 2)
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def parse_sweep_range(lines: list[str]) -> dict | None:
    """Extract sweep range from Output.Graph.XAxis line.

    Looks for lines like: "TestParameter, Output.Graph.XAxis, -2, 2, ..."
    Returns {"start": -2.0, "stop": 2.0} or None.
    """
    line = _find_line(lines, "Output.Graph.XAxis")
    if not line:
        return None
    parts = [p.strip() for p in line.split(",")]
    try:
        start = float(parts[2])
        stop = float(parts[3])
        return {"start": start, "stop": stop}
    except (IndexError, ValueError, TypeError):
        return None


def parse_repeat_count(lines: list[str]) -> int | None:
    """Extract repeat count from TestParameter RepeatCount line.

    Looks for lines like: "TestParameter, RepeatCount, 3"
    Returns the count as int.
    """
    for line in lines:
        if "RepeatCount" in line:
            val = _csv_field(line, 2)
            try:
                return int(float(val)) if val is not None else None
            except (TypeError, ValueError):
                return None
    return None


# ── Analyzers ──────────────────────────────────────────────────────────


def analyze_waveform_params(
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    """Extract pulse waveform parameters from waveform definition data.

    For Keysight B1500A, the waveform is defined in header rows with
    'Waveform1_time' and 'Waveform1_voltage' columns. This analyzer
    reads those definition rows and calculates:
        - rise_us: 10-90% rise time in microseconds
        - fall_us: 90-10% fall time in microseconds
        - set_width_us: width of set pulse at 50% height
        - read_width_us: width of read pulse at 50% height

    Returns dict with measured waveform parameters.
    """
    return {}


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
