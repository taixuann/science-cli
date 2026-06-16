"""IV curve SVG generation — publication-style plotting for IV sweeps.

Reads CSV data files, generates publication-style IV curve SVGs
with sweep metadata annotations, and supports multi-trace overlay
and V_set/V_reset highlighting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from science_cli.library.iv.metrics import detect_vset, detect_vreset

logger = logging.getLogger(__name__)


def read_iv_csv(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Read voltage and current from an IV data CSV.

    Handles common column conventions:
      - Time,BI,BV (Keysight B1500A style)
      - Time,Current,Voltage
      - Voltage (V), Current (A), Potential (V)

    Robust against embedded instrument metadata by reading the file
    line-by-line and only collecting rows where every field in the
    data columns is a valid float.

    Args:
        filepath: Path to the CSV file.

    Returns:
        (voltage, current, info) where info contains metadata
        about which columns were detected.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If neither voltage nor current columns can be identified.
    """
    import csv

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, newline="") as f:
        first_line = f.readline()
    if "LabVIEW Measurement" in first_line:
        return read_iv_lvm(path)

    with open(path, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Empty file: {path}")

    expected_cols = len(header)
    header_lower = [h.strip().lower() for h in header]

    voltage_col: Optional[int] = None
    current_col: Optional[int] = None
    time_col: Optional[int] = None

    for i, cl in enumerate(header_lower):
        if any(k in cl for k in ("voltage", "potential", "e (v)", "v)", "bv", "bias voltage")):
            if voltage_col is None:
                voltage_col = i
        elif any(k in cl for k in ("current", "i (a)", "i/a", "i)", "we(1).current", "bi", "bias current")):
            if current_col is None:
                current_col = i
        elif any(k in cl for k in ("time", "corrected time", "t/s")):
            if time_col is None:
                time_col = i

    if voltage_col is None and current_col is None and expected_cols == 3:
        if any(k in header_lower[1] for k in ("bi", "current", "i")):
            current_col = 1
        if any(k in header_lower[2] for k in ("bv", "voltage", "v")):
            voltage_col = 2
        if "time" in header_lower[0]:
            time_col = 0
    if voltage_col is None and current_col is None and expected_cols >= 2:
        if "time" in header_lower[0]:
            current_col = 1
            voltage_col = 2
            time_col = 0

    if voltage_col is None:
        raise ValueError(f"Cannot identify voltage column in {path.name}. Columns: {header}")
    if current_col is None:
        raise ValueError(f"Cannot identify current column in {path.name}. Columns: {header}")

    numeric_rows: list[list[float]] = []
    metadata_rows: list[list[str]] = []
    skipped_lines: int = 0

    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            stripped = [c.strip() for c in row]
            if not any(stripped):
                continue
            if len(stripped) == 1 and stripped[0].startswith("="):
                continue
            if len(stripped) != expected_cols:
                continue
            try:
                numeric_rows.append([float(c) for c in stripped])
            except ValueError:
                metadata_rows.append(stripped)
                skipped_lines += 1
                continue

    if not numeric_rows:
        raise ValueError(f"No valid numeric data found in {path.name}")

    data = np.array(numeric_rows)
    voltage = data[:, voltage_col]
    current = data[:, current_col]
    time_arr = data[:, time_col] if time_col is not None else None

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]
    if time_arr is not None:
        time_arr = time_arr[mask]

    clarius_meta = _parse_clarius_metadata(metadata_rows)

    timestamp_first: Optional[float] = None
    timestamp_last: Optional[float] = None
    if time_arr is not None and len(time_arr) > 0:
        timestamp_first = float(time_arr[0])
        timestamp_last = float(time_arr[-1])

    info = {
        "voltage_col": header[voltage_col],
        "current_col": header[current_col],
        "time_col": header[time_col] if time_col is not None else None,
        "n_points": len(voltage),
        "skipped_lines": skipped_lines,
        "clarius_metadata": clarius_meta,
        "time": time_arr,
        "timestamp_first": timestamp_first,
        "timestamp_last": timestamp_last,
    }
    return voltage, current, info


def read_iv_lvm(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Read voltage and current from a tab-separated LabVIEW Measurement file.

    Parses the two-block header delimited by ***End_of_Header*** markers,
    extracts metadata (date, time, operator, channels, samples), and reads
    tab-separated numeric data with positional column mapping:

        col0: X_Value (row counter, skipped)
        col1: Untitled (Voltage)
        col2: Untitled 1 (Current)
        col3: Untitled 2 (Timestamp)
        col4: Comment (ignored)
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, newline="") as f:
        first_line = f.readline()
        if "LabVIEW Measurement" not in first_line:
            raise ValueError(f"Not a LabVIEW Measurement file: {path.name}")
        raw = f.read()
        lines = raw.splitlines()

    eoh_positions: list[int] = []
    for idx, line in enumerate(lines):
        if line.strip() == "***End_of_Header***":
            eoh_positions.append(idx)

    if len(eoh_positions) < 2:
        raise ValueError(f"LVM file {path.name} missing required ***End_of_Header*** delimiters (found {len(eoh_positions)})")

    first_eoh = eoh_positions[0]
    second_eoh = eoh_positions[1]

    block1_lines = lines[:first_eoh]
    metadata: dict = {"source": "LabVIEW Measurement"}
    for raw_line in block1_lines:
        row = raw_line.split("\t")
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            if key and val:
                metadata[key] = val

    block2_lines = lines[first_eoh + 1 : second_eoh]
    for raw_line in block2_lines:
        row = raw_line.split("\t")
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            if key and val:
                metadata[key] = val

    data_start = second_eoh + 1
    while data_start < len(lines) and not lines[data_start].strip():
        data_start += 1
    if data_start >= len(lines):
        raise ValueError(f"LVM file {path.name} has no column header after headers")

    col_header_line = lines[data_start]
    col_headers = [c.strip() for c in col_header_line.split("\t")]

    if len(col_headers) < 3:
        raise ValueError(f"LVM file {path.name} has fewer than 3 data columns (found {len(col_headers)})")

    numeric_rows: list[list[float]] = []
    ts_values: list[float] = []

    for raw_line in lines[data_start + 1 :]:
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        fields = [s.strip() for s in raw_line.split("\t")]
        if len(fields) < 3:
            continue
        try:
            _ = [float(fields[1]), float(fields[2])]
            numeric_rows.append([float(fields[1]), float(fields[2])])
            if len(fields) >= 4:
                try:
                    ts_values.append(float(fields[3]))
                except ValueError:
                    ts_values.append(0.0)
        except (ValueError, IndexError):
            continue

    if not numeric_rows:
        raise ValueError(f"No valid numeric data found in LVM file {path.name}")

    data = np.array(numeric_rows)
    voltage = data[:, 0]
    current = data[:, 1]

    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    time_arr: Optional[np.ndarray] = np.array(ts_values) if ts_values else None
    timestamp_first: Optional[float] = None
    timestamp_last: Optional[float] = None
    if time_arr is not None and len(time_arr) > 0:
        timestamp_first = float(time_arr[0])
        timestamp_last = float(time_arr[-1])

    lvm_info = {
        "source": "LabVIEW Measurement",
        "date": metadata.get("Date", ""),
        "time": time_arr,
        "operator": metadata.get("Operator", ""),
        "channels": metadata.get("Channels", ""),
        "samples": metadata.get("Samples", ""),
        "voltage_col": col_headers[1] if len(col_headers) > 1 else "col1",
        "current_col": col_headers[2] if len(col_headers) > 2 else "col2",
        "n_points": len(voltage),
        "skipped_lines": 0,
        "clarius_metadata": {},
        "time_col": None,
        "timestamp_first": timestamp_first,
        "timestamp_last": timestamp_last,
    }
    return voltage, current, lvm_info


def _parse_clarius_metadata(rows: list[list[str]]) -> dict:
    """Parse Keysight B1500A / Clarius+ sweep metadata from CSV metadata rows."""
    result: dict = {}
    for row in rows:
        if not row or len(row) < 2:
            continue
        key = row[0].strip()
        val = row[1].strip()
        parsed_val = None
        try:
            parsed_val = float(val)
        except (ValueError, TypeError):
            pass
        if key == "Start/Bias":
            if parsed_val is not None:
                result["start_v"] = parsed_val
        elif key == "Stop":
            if parsed_val is not None:
                result["stop_v"] = parsed_val
        elif key == "Step":
            if parsed_val is not None:
                result["step_v"] = parsed_val
        elif key == "Number of Points":
            if parsed_val is not None:
                result["n_points"] = int(parsed_val)
        elif key == "Compliance":
            if parsed_val is not None:
                result["compliance"] = parsed_val
        elif key == "Dual Sweep":
            result["dual_sweep_enabled"] = val.lower() in ("enabled", "true", "1", "yes")
        elif key == "Operation Mode":
            result["operation_mode"] = val
        elif key == "Sweep Delay":
            if parsed_val is not None:
                result["sweep_delay_s"] = parsed_val
        elif key == "Hold Time":
            if parsed_val is not None:
                result["hold_time_s"] = parsed_val
        elif key == "Speed":
            result["speed"] = val
    step_v = result.get("step_v")
    delay = result.get("sweep_delay_s")
    if step_v is not None and delay is not None and delay > 0:
        result["sweep_rate_approx"] = abs(step_v) / delay
    return result


def _should_use_log_scale(current: np.ndarray) -> bool:
    """Determine if current should use log scale based on dynamic range."""
    abs_i = np.abs(current)
    pos = abs_i[abs_i > 1e-30]
    if len(pos) < 2:
        return False
    ratio = pos.max() / pos.min()
    return ratio > 100.0


def _split_at_reversals(voltage: np.ndarray, hysteresis: float = 0.1) -> list[tuple[int, int]]:
    """Find voltage reversal points using hysteresis-based detection.

    Returns a list of (start, end) index pairs for each monotonic segment.
    """
    if len(voltage) < 3:
        return [(0, len(voltage))]

    dv = np.diff(voltage)
    nonzero = dv[np.abs(dv) > 1e-10]
    median_dv = float(np.median(nonzero)) if len(nonzero) > 0 else 0.0
    going_up = median_dv > 0

    current_min = float(voltage[0])
    current_max = float(voltage[0])
    segments: list[tuple[int, int]] = []
    start_idx = 0

    for i in range(1, len(voltage)):
        v = float(voltage[i])
        if v > current_max:
            current_max = v
        if v < current_min:
            current_min = v
        if going_up:
            if current_max - v >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = False
                current_min = v
                current_max = v
        else:
            if v - current_min >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = True
                current_min = v
                current_max = v

    if len(voltage) > start_idx:
        segments.append((start_idx, len(voltage)))
    return segments if segments else [(0, len(voltage))]


def _format_voltage(v: float) -> str:
    """Format a voltage value for display."""
    if v >= 0:
        return f"+{v:.1f}V"
    return f"{v:.1f}V"


def _extract_sweep_annotations(sweep: list[dict]) -> dict:
    """Extract annotation text from sweep segment metadata."""
    result: dict = {"sweep_rate": None, "direction": None, "voltage_range": None, "duration": None}
    if not sweep:
        return result

    rate = sweep[0].get("sweep_rate_v_s")
    if rate is not None:
        result["sweep_rate"] = f"{rate:.2f} V/s"

    has_start_voltages = all("start_voltage" in seg for seg in sweep) if sweep else False

    if has_start_voltages and len(sweep) >= 1:
        direction_parts: list[str] = []
        for seg in sweep:
            sv = seg["start_voltage"]
            direction_parts.append(_format_voltage(sv))
        last_ev = sweep[-1].get("end_voltage")
        if last_ev is not None:
            direction_parts.append(_format_voltage(last_ev))
        result["direction"] = " -> ".join(direction_parts)
    else:
        direction_parts = ["0"]
        for seg in sweep:
            d = seg.get("direction", "")
            vr = seg.get("voltage_range")
            if vr is not None and vr != 0:
                if d in ("forward", "fwd", "f"):
                    target = f"+{vr:.1f}V" if vr > 0 else f"{vr:.1f}V"
                elif d in ("reverse", "rev", "r"):
                    target = f"-{vr:.1f}V" if vr > 0 else f"{vr:.1f}V"
                else:
                    target = f"{vr:.1f}V"
                direction_parts.append(target)
                direction_parts.append("0")
            else:
                if d:
                    direction_parts.append(f"({d})")
        deduped: list[str] = []
        for part in direction_parts:
            if deduped and deduped[-1] == "0" and part == "0":
                continue
            deduped.append(part)
        result["direction"] = "->".join(deduped)

    vr_first = sweep[0].get("voltage_range")
    if vr_first is not None:
        result["voltage_range"] = f"{vr_first:.2f}V"
    dur = sweep[0].get("duration_s")
    if dur is not None:
        result["duration"] = f"{dur:.1f} s"
    return result


def build_plot_title(order: int, sweep: list[dict], sweep_type: str) -> str:
    """Build a plot title string: #N | X.XX V/s | direction_path."""
    st = sweep_type or "uc"
    annotations = _extract_sweep_annotations(sweep)
    parts = [f"#{order:02d}"]
    rate = annotations.get("sweep_rate")
    if rate:
        parts.append(rate)
    direction = annotations.get("direction")
    if direction:
        parts.append(direction)
    else:
        parts.append(st)
    return "  |  ".join(parts)


def _build_sweep_from_data(voltage: np.ndarray, time: np.ndarray | None = None) -> list[dict]:
    """Build sweep segment metadata from voltage/time data alone.

    Fallback for build_plot_title when no stored sweep metadata exists.
    """
    if len(voltage) < 2:
        return []

    dv = np.abs(np.diff(voltage))
    jump_threshold = 1.0
    big_jumps = np.where(dv > jump_threshold)[0]

    if len(big_jumps) > 0:
        first_jump = int(big_jumps[0])
        end_idx = first_jump + 1
        if end_idx < 10:
            end_idx = len(voltage)
    else:
        end_idx = len(voltage)

    voltage = voltage[:end_idx]
    if time is not None and len(time) >= end_idx:
        time = time[:end_idx]
    else:
        time = None

    segments = _split_at_reversals(voltage)
    if not segments:
        return []

    result: list[dict] = []
    for start, end in segments:
        v_seg = voltage[start:end]
        if len(v_seg) < 2:
            continue
        v0 = float(v_seg[0])
        v1 = float(v_seg[-1])
        characteristic_v = max(abs(v0), abs(v1))
        direction = "forward" if v1 >= v0 else "reverse"

        seg_dict: dict = {
            "direction": direction,
            "voltage_range": characteristic_v,
            "start_voltage": v0,
            "end_voltage": v1,
        }
        if time is not None and end <= len(time):
            t_seg = time[start:end]
            if len(t_seg) >= 2:
                dt = float(t_seg[-1] - t_seg[0])
                if dt > 0:
                    seg_dict["sweep_rate_v_s"] = characteristic_v / dt
                    seg_dict["duration_s"] = dt
        result.append(seg_dict)

    if len(result) > 2:
        result = result[:2]
    return result


_LINE_COLORS = ["#000000", "#444444", "#888888", "#BBBBBB"]
_LINE_STYLES = ["-", "--", ":", "-."]


def _get_line_style(file_index: int) -> tuple[str, str]:
    """Return (color, linestyle) for a file's position."""
    color = _LINE_COLORS[file_index % len(_LINE_COLORS)]
    style = _LINE_STYLES[file_index % len(_LINE_STYLES)]
    return color, style


def _plot_simple_sweep(ax, voltage: np.ndarray, current: np.ndarray, use_log: bool, order: int, file_index: int = 0, color: str | None = None, **kwargs) -> None:
    """Plot a single-direction IV sweep with cycled line style."""
    c, style = _get_line_style(file_index)
    color = color or c
    label = f"#{order:02d}"
    linewidth = float(kwargs.get("linewidth", 0.8))
    linestyle = kwargs.get("linestyle", style)
    marker = kwargs.get("marker", None)
    markersize = kwargs.get("markersize", None)
    if markersize is not None:
        try:
            markersize = float(markersize)
        except (ValueError, TypeError):
            markersize = None

    plot_kw = {"color": color, "linestyle": linestyle, "linewidth": linewidth, "label": label}
    if marker:
        plot_kw["marker"] = marker
    if markersize is not None:
        plot_kw["markersize"] = markersize

    if use_log:
        ax.semilogy(voltage, np.abs(current), **plot_kw)
        ax.set_ylabel("|Current| (A)", fontsize=10)
    else:
        ax.plot(voltage, current, **plot_kw)
        ax.set_ylabel("Current (A)", fontsize=10)


def _plot_bipolar_sweep(ax, voltage: np.ndarray, current: np.ndarray, use_log: bool, order: int, file_index: int = 0, color: str | None = None, **kwargs) -> None:
    """Plot a full bipolar sweep with forward/reverse distinction."""
    segments = _split_at_reversals(voltage)[:2]
    if len(segments) <= 1:
        _plot_simple_sweep(ax, voltage, current, use_log, order, file_index, color=color, **kwargs)
        return

    c, _ = _get_line_style(file_index)
    color = color or c
    rev_color = "#888888"
    plot_current = np.abs(current) if use_log else current

    linewidth = float(kwargs.get("linewidth", 0.8))
    linestyle = kwargs.get("linestyle", "-")
    rev_linestyle = kwargs.get("rev_linestyle", "--")
    marker = kwargs.get("marker", None)
    markersize = kwargs.get("markersize", None)
    if markersize is not None:
        try:
            markersize = float(markersize)
        except (ValueError, TypeError):
            markersize = None

    for seg_idx, (start, end) in enumerate(segments):
        v_seg = voltage[start:end]
        i_seg = plot_current[start:end]
        if len(v_seg) < 2:
            continue
        is_even = seg_idx % 2 == 0
        plot_kw = {"linewidth": linewidth}
        if marker:
            plot_kw["marker"] = marker
        if markersize is not None:
            plot_kw["markersize"] = markersize
        if is_even:
            plot_kw["color"] = color
            plot_kw["linestyle"] = linestyle
            plot_kw["label"] = f"#{order:02d} fwd" if seg_idx == 0 else None
            if use_log:
                ax.semilogy(v_seg, i_seg, **plot_kw)
            else:
                ax.plot(v_seg, i_seg, **plot_kw)
        else:
            plot_kw["color"] = rev_color
            plot_kw["linestyle"] = rev_linestyle
            plot_kw["label"] = f"#{order:02d} rev" if seg_idx == 1 else None
            if use_log:
                ax.semilogy(v_seg, i_seg, **plot_kw)
            else:
                ax.plot(v_seg, i_seg, **plot_kw)

    if use_log:
        ax.set_ylabel("|Current| (A)", fontsize=10)
    else:
        ax.set_ylabel("Current (A)", fontsize=10)


def _plot_time_colored_iv(ax, voltage: np.ndarray, current: np.ndarray, time: np.ndarray, use_log: bool, order: int) -> None:
    """Plot V-I curve colored by relative time with Nature styling."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    t_rel = time - time[0]
    y_vals = np.abs(current) if use_log else current

    points = np.array([voltage, y_vals]).T.reshape(-1, 1, 2)
    segs = np.concatenate([points[:-1], points[1:]], axis=1)

    norm = plt.Normalize(0, t_rel[-1])
    lc = LineCollection(segs, cmap="turbo", norm=norm, linewidth=1.2)
    lc.set_array(t_rel)
    ax.add_collection(lc)
    ax.autoscale()

    cbar_label = "|Current| (A)" if use_log else "Current (A)"
    ax.set_ylabel(cbar_label, fontsize=10)
    cbar = ax.figure.colorbar(lc, ax=ax, label="Time (s)", pad=0.02)
    cbar.ax.tick_params(labelsize=7)


def generate_iv_svg(voltage: np.ndarray, current: np.ndarray, metadata: dict, output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None):
    """Generate a publication-style IV curve SVG.

    ACS (American Chemical Society) style:
      - Sans-serif font (Arial/Helvetica/DejaVu Sans)
      - No grid lines
      - Inward tick marks on all four axes
      - All four spines visible
      - Black line(s), linewidth 0.8
      - Legend without box

    When time data is available, draws a time-colored V-I curve with
    Nature styling (open spines, turbo colormap).

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        metadata: Dict with keys: title, sweep, sweep_type, time, order, file_index.
        output_path: Path to save the SVG.
        dpi: Resolution for SVG rendering.
        raw_current: If True, plot raw linear current (no abs, no log).
        flags: Custom plot/figure flags.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    title = metadata.get("title", "IV Curve")
    sweep_type = metadata.get("sweep_type", "") or "uc"
    sweep = metadata.get("sweep", [])
    order = metadata.get("order", 0)
    file_index = metadata.get("file_index", 0)
    time_arr = metadata.get("time")

    segments = _split_at_reversals(voltage)[:2]
    auto_bipolar = len(segments) > 1
    if auto_bipolar:
        sweep_type = "f"

    need_auto = not sweep or (sweep and sweep[0].get("sweep_rate_v_s", 0) == 0)
    if need_auto:
        if time_arr is not None and len(time_arr) == len(voltage):
            derived_sweep = _build_sweep_from_data(voltage, time_arr)
        else:
            derived_sweep = _build_sweep_from_data(voltage, None)
        if derived_sweep:
            if sweep and derived_sweep:
                auto_rate = derived_sweep[0].get("sweep_rate_v_s", 0)
                stored_rate = sweep[0].get("sweep_rate_v_s", 0) if sweep else 0
                if stored_rate == 0 and auto_rate:
                    sweep[0]["sweep_rate_v_s"] = auto_rate
            else:
                sweep = derived_sweep
            title = build_plot_title(order=order, sweep=sweep, sweep_type=sweep_type)

    use_log = False if raw_current else _should_use_log_scale(current)
    has_time = time_arr is not None and len(time_arr) == len(voltage)

    acs_rc = {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.linewidth": 1.0,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.major.size": 4,
        "ytick.major.size": 4,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "legend.frameon": False,
    }

    plot_flags = dict(flags or {})
    color_val = plot_flags.pop("color", None)

    with plt.rc_context(acs_rc):
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=dpi)

        if has_time:
            _plot_time_colored_iv(ax, voltage, current, time_arr, use_log, order)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        elif sweep_type == "f":
            _plot_bipolar_sweep(ax, voltage, current, use_log, order, file_index, color=color_val, **plot_flags)
        else:
            _plot_simple_sweep(ax, voltage, current, use_log, order, file_index, color=color_val, **plot_flags)

        ax.set_xlabel("Voltage (V)", fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=8, direction="in", which="both")

        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.8)
        if raw_current:
            ax.spines["bottom"].set_position(("data", 0))

        if flags:
            _apply_figure_kw(ax, flags, title_default=title)

        handles, labels = ax.get_legend_handles_labels()
        if handles and (not flags or flags.get("legend", True) is not False):
            ax.legend(handles, labels, frameon=False, fontsize=8, loc="upper left")
            if ax.get_legend():
                for handle in ax.get_legend().legend_handles:
                    handle.set_linewidth(0.8)

        fig.tight_layout()
        ext = Path(output_path).suffix.lower()
        fmt = "pdf" if ext == ".pdf" else "svg"
        fig.savefig(str(output_path), format=fmt, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    logger.info(f"Generated plot: {output_path}")


def generate_iv_overlay_svg(traces: list[tuple[np.ndarray, np.ndarray, dict]], output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None):
    """Generate an overlay SVG with multiple IV traces on one plot.

    Args:
        traces: List of (voltage, current, metadata) tuples.
        output_path: Path to save the SVG.
        dpi: Resolution for SVG rendering.
        raw_current: If True, plot raw linear current.
        flags: Custom plot/figure flags.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    acs_rc = {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.linewidth": 1.0,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.major.size": 4,
        "ytick.major.size": 4,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "legend.frameon": False,
    }

    colors = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
    use_log = False if raw_current else any(_should_use_log_scale(t[1]) for t in traces)

    plot_flags = dict(flags or {})
    color_val = plot_flags.pop("color", None)

    with plt.rc_context(acs_rc):
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=dpi)

        for i, (voltage, current, meta) in enumerate(traces):
            color = color_val or colors[i % len(colors)]
            sweep_type = meta.get("sweep_type", "") or "uc"
            order = meta.get("order", i + 1)
            file_index = meta.get("file_index", i)

            if sweep_type == "f":
                _plot_bipolar_sweep(ax, voltage, current, use_log, order, file_index, color=color, **plot_flags)
            else:
                _plot_simple_sweep(ax, voltage, current, use_log, order, file_index, color=color, **plot_flags)

        ax.set_xlabel("Voltage (V)", fontsize=10)
        base_title = traces[0][2].get("title", "") if traces else ""
        title = base_title or f"IV Overlay ({len(traces)} sweeps)"
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=8, direction="in", which="both")
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.8)
        if raw_current:
            ax.spines["bottom"].set_position(("data", 0))

        if use_log:
            has_neg = any(np.any(t[1] < 0) for t in traces if t[1] is not None and len(t[1]) > 0)
            ax.set_ylabel("|Current| (A)" if has_neg else "Current (A)", fontsize=10)
            ax.set_yscale("log")
        else:
            ax.set_ylabel("Current (A)", fontsize=10)

        if flags:
            _apply_figure_kw(ax, flags, title_default=title)

        handles, labels = ax.get_legend_handles_labels()
        if handles and (not flags or flags.get("legend", True) is not False):
            ax.legend(handles, labels, frameon=False, fontsize=8, loc="upper left")

        fig.tight_layout()
        ext = Path(output_path).suffix.lower()
        fmt = "pdf" if ext == ".pdf" else "svg"
        fig.savefig(str(output_path), format=fmt, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    logger.info(f"Generated overlay plot: {output_path}")


def generate_iv_highlighted_svg(traces: list[tuple[np.ndarray, np.ndarray, dict]], highlight_cycles: list[int], output_path: str | Path, dpi: int = 150, raw_current: bool = False, flags: dict = None):
    """Generate a Nature-quality overlay SVG highlighting specific cycles in color.

    Non-highlighted cycles are plotted in light grey with low opacity so the
    coloured highlight cycles stand out. Each highlighted cycle gets a distinct
    color from the Nature Research discrete palette.

    Args:
        traces: List of (voltage, current, metadata) tuples.
        highlight_cycles: List of 1-based cycle numbers to highlight.
        output_path: Path to save the SVG.
        dpi: Resolution for SVG rendering.
        raw_current: If True, plot raw linear current.
        flags: Custom plot/figure flags.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nature_rc = {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.linewidth": 0.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "legend.frameon": False,
    }

    highlight_colors = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#56B4E9", "#CC79A7", "#F0E442", "#000000"]
    use_log = False if raw_current else any(_should_use_log_scale(t[1]) for t in traces)

    with plt.rc_context(nature_rc):
        fig, ax = plt.subplots(figsize=(3.46, 2.75), dpi=dpi)

        bg_traces: list[tuple[np.ndarray, np.ndarray, dict, int]] = []
        fg_traces: list[tuple[np.ndarray, np.ndarray, dict, int]] = []
        for i, (voltage, current, meta) in enumerate(traces):
            order = meta.get("order", i + 1)
            if order in highlight_cycles:
                fg_traces.append((voltage, current, meta, order))
            else:
                bg_traces.append((voltage, current, meta, order))

        for voltage, current, _meta, _order in bg_traces:
            plot_current = np.abs(current) if use_log else current
            kw = dict(color="#E0E0E0", alpha=0.08, linewidth=0.3, label=None)
            if use_log:
                ax.semilogy(voltage, plot_current, **kw)
            else:
                ax.plot(voltage, plot_current, **kw)

        color_idx = 0
        for voltage, current, _meta, order in fg_traces:
            color = highlight_colors[color_idx % len(highlight_colors)]
            color_idx += 1
            label = f"Cycle {order}"
            plot_current = np.abs(current) if use_log else current
            kw = dict(color=color, linewidth=0.75, label=label)
            if use_log:
                ax.semilogy(voltage, plot_current, **kw)
            else:
                ax.plot(voltage, plot_current, **kw)

        ax.set_xlabel("Voltage (V)", fontsize=7)
        if use_log:
            has_neg = any(np.any(t[1] < 0) for t in traces if t[1] is not None and len(t[1]) > 0)
            ax.set_ylabel("|Current| (A)" if has_neg else "Current (A)", fontsize=7)
            ax.set_yscale("log")
        else:
            ax.set_ylabel("Current (A)", fontsize=7)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_linewidth(0.5)

        ax.tick_params(labelsize=6, direction="in", which="both")
        ax.grid(False)

        if not use_log:
            ax.ticklabel_format(style="sci", axis="y", scilimits=(0, 0), useOffset=False)
            fg_only = [t for t in traces if t[2].get("order") in highlight_cycles]
            if not fg_only:
                fg_only = traces
            all_y = np.concatenate([t[1] for t in fg_only if t[1] is not None and len(t[1]) > 0])
            all_x = np.concatenate([t[0] for t in fg_only if t[0] is not None and len(t[0]) > 0])
            if len(all_y) > 0 and len(all_x) > 0:
                y_lo, y_hi = float(all_y.min()), float(all_y.max())
                x_lo, x_hi = float(all_x.min()), float(all_x.max())
                y_pad = 0.02 * (y_hi - y_lo) if y_hi > y_lo else max(abs(y_hi), 1e-12) * 0.02
                x_pad = 0.02 * (x_hi - x_lo) if x_hi > x_lo else max(abs(x_hi), 1e-12) * 0.02
                ax.set_xlim(x_lo - x_pad, x_hi + x_pad)

        if flags:
            _apply_figure_kw(ax, flags, title_default="")

        handles, labels = ax.get_legend_handles_labels()
        if handles and (not flags or flags.get("legend", True) is not False):
            ax.legend(handles, labels, frameon=False, fontsize=6, loc="upper left")

        fig.tight_layout()
        ext = Path(output_path).suffix.lower()
        fmt = "pdf" if ext == ".pdf" else "svg"
        fig.savefig(str(output_path), format=fmt, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    logger.info(f"Generated multi-cycle highlight plot: {output_path}")


def _apply_figure_kw(ax, flags: dict, title_default: str = "") -> None:
    """Apply figure keyword overrides to a matplotlib Axes.

    Applies settings from plot flags dict such as title, xlim, ylim,
    xlabel, ylabel, legend, xscale, yscale, grid, fontsize adjustments.

    This is a local helper to avoid tight coupling with CLI-level modules.
    """
    if not flags:
        return

    title = flags.get("title", title_default)
    if title:
        fontsize = flags.get("title_fontsize", 11)
        ax.set_title(title, fontsize=fontsize, fontweight="bold")

    xlim = flags.get("xlim")
    if xlim is not None and len(xlim) == 2:
        ax.set_xlim(xlim[0], xlim[1])

    ylim = flags.get("ylim")
    if ylim is not None and len(ylim) == 2:
        ax.set_ylim(ylim[0], ylim[1])

    xlabel = flags.get("xlabel")
    if xlabel:
        ax.set_xlabel(xlabel)

    ylabel = flags.get("ylabel")
    if ylabel:
        ax.set_ylabel(ylabel)

    fontsize = flags.get("fontsize")
    if fontsize is not None:
        for item in [ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels():
            item.set_fontsize(fontsize)

    if flags.get("grid", False):
        ax.grid(True, alpha=0.3)
    else:
        ax.grid(False)

    xscale = flags.get("xscale")
    if xscale:
        ax.set_xscale(xscale)

    yscale = flags.get("yscale")
    if yscale:
        ax.set_yscale(yscale)

    legend_val = flags.get("legend")
    if legend_val is not None and not legend_val:
        leg = ax.get_legend()
        if leg:
            leg.remove()
