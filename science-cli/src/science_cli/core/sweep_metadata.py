"""Sweep metadata — detect IV sweep segments from data, update protocol YAML.

When files are assigned to IV technique steps in a protocol, the system
auto-calculates sweep direction and sweep rate from the actual data and
stores them per-file in the protocol YAML.

Protocol YAML format (per-file):

    files:
      - deviceA_IV.txt                     # plain string (no sweep data yet)
      - file: deviceB_IV.txt               # dict with sweep metadata
        sweep:
          - direction: forward
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
          - direction: reverse
            sweep_rate_v_s: 0.1
            voltage_range: 2.0
            duration_s: 20.0
"""

from pathlib import Path
import numpy as np
import yaml


def detect_iv_columns(df, info):
    """Find time, voltage, current columns in a loaded IV data file.

    Returns (time_col, voltage_col, current_col) — any may be None.
    """
    cols = info.get("columns", [])
    time_col = None
    voltage_col = None
    current_col = None

    for c in cols:
        c_lower = c.lower().strip()
        if any(k in c_lower for k in ("corrected time", "time", "t/s", "time/s")):
            time_col = c
        elif any(k in c_lower for k in ("voltage", "v (v)", "potential", "e (v)", "v)", "bv", "bias voltage")):
            voltage_col = c
        elif any(k in c_lower for k in ("current", "i (a)", "i/a", "i)", "we(1).current", "bi", "bias current")):
            current_col = c

    return time_col, voltage_col, current_col


def extract_sweep_from_file(filepath, min_segment_points=5, technique="", device=""):
    """Load a data file and detect IV sweep segments.

    Args:
        filepath: Path to the data file.
        min_segment_points: Minimum points per segment.
        technique: Technique key (e.g. 'iv-sweep') for device-aware loading.
        device: Device name (e.g. 'keithley-2400') for device-aware loading.

    Returns list of segment dicts, or empty list if not an IV file.
    """
    from science_cli.core.data_loader import load_data_file

    path = Path(filepath)
    if not path.exists():
        return []

    try:
        df, info = load_data_file(str(path), technique=technique, device=device)
    except Exception:
        return []

    time_col, voltage_col, current_col = detect_iv_columns(df, info)
    if not voltage_col:
        return []

    try:
        v = df[voltage_col].values.astype(float)
        mask = ~np.isnan(v)
        v = v[mask]
        if time_col:
            t = df[time_col].values.astype(float)[mask]
        else:
            t = np.arange(len(v), dtype=float)
    except (ValueError, TypeError):
        return []

    # Use science-iv's detect_sweep_segments if available
    try:
        from science_iv.analyze import detect_sweep_segments
        segments = detect_sweep_segments(v, t, min_segment_points=min_segment_points)
    except ImportError:
        segments = _detect_sweep_fallback(v, t, min_segment_points)

    return segments


def _detect_sweep_fallback(voltage, time, min_segment_points=5):
    """Fallback sweep detection (no science-iv installed)."""
    v = np.asarray(voltage, dtype=float).flatten()
    t = np.asarray(time, dtype=float).flatten()

    dv = np.diff(v)
    sign = np.sign(dv)
    reversals = np.where(np.diff(sign, prepend=sign[0]) != 0)[0]

    boundaries = [0] + reversals.tolist() + [len(v) - 1]
    segments = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        n_points = e - s + 1
        if n_points < min_segment_points:
            continue

        # Check for zero-crossing within the segment (bipolar sweeps)
        # This splits a long monotonic sweep (e.g., +V→0→-V) at V=0
        sub_segments = [(s, e)]
        if len(v[s:e + 1]) >= 2 * min_segment_points:
            zv = v[s:e + 1]
            zt = t[s:e + 1]
            sv = np.sign(np.where(np.abs(zv) < 1e-12, 1e-12, zv))
            zero_idx = np.where(np.diff(sv))[0]
            if len(zero_idx) == 1:
                z = zero_idx[0] + s
                if z - s >= min_segment_points and e - z >= min_segment_points:
                    sub_segments = [(s, z), (z, e)]

        for ss, ee in sub_segments:
            seg_v = v[ss:ee + 1]
            seg_t = t[ss:ee + 1]
            dt = seg_t[-1] - seg_t[0]
            dv_seg = seg_v[-1] - seg_v[0]
            v_start = seg_v[0]
            v_end = seg_v[-1]
            direction = f"{v_start:.2f}V -> {v_end:.2f}V"
            sweep_rate = abs(dv_seg / dt) if dt > 0 else 0.0
            segments.append({
                "start_idx": int(ss),
                "end_idx": int(ee),
                "direction": direction,
                "sweep_rate_v_s": float(round(sweep_rate, 6)),
                "voltage_range": float(round(abs(dv_seg), 4)),
                "duration_s": float(round(dt, 4)),
            })
    return segments


def _normalize_files(step_files):
    """Normalize files list: every entry is a dict with 'file' key."""
    normalized = []
    for entry in step_files:
        if isinstance(entry, str):
            normalized.append({"file": entry})
        elif isinstance(entry, dict) and "file" in entry:
            normalized.append(entry)
        else:
            normalized.append(entry)
    return normalized


def _denormalize_files(entries):
    """Write back files list: plain string if no sweep, dict if sweep exists."""
    result = []
    for entry in entries:
        if isinstance(entry, dict):
            if "sweep" in entry:
                result.append(entry)
            else:
                result.append(entry.get("file", entry))
        else:
            result.append(entry)
    return result


def update_protocol_with_sweep(yaml_path, step_name, filename, sweep_segments):
    """Update a protocol YAML with sweep metadata for a specific file.

    Parameters
    ----------
    yaml_path : Path or str
        Path to the protocol YAML file.
    step_name : str
        Name of the step containing the file.
    filename : str
        The filename (basename) to update.
    sweep_segments : list[dict]
        Sweep segments from extract_sweep_from_file().
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        return False

    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    if not sweep_segments:
        return False

    for step in protocol.get("steps", []):
        if step.get("name") != step_name:
            continue
        files = step.setdefault("files", [])
        entries = _normalize_files(files)
        found = False
        for entry in entries:
            if entry["file"] == filename:
                entry["sweep"] = sweep_segments
                found = True
                break
        if not found:
            entries.append({"file": filename, "sweep": sweep_segments})
        step["files"] = _denormalize_files(entries)
        break
    else:
        return False

    with open(yaml_path, "w") as f:
        yaml.dump(protocol, f, default_flow_style=False, sort_keys=False)
    return True


def get_sweep_for_file(step_files, filename):
    """Retrieve sweep metadata for a specific file from a step's files list.

    Returns list of segment dicts, or None if no sweep data.
    """
    entries = _normalize_files(step_files)
    for entry in entries:
        if entry.get("file") == filename:
            return entry.get("sweep")
    return None
