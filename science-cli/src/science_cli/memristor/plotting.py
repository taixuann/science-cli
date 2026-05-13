"""IV curve SVG generation for memristor crossbar devices.

Reads CSV data files, generates publication-style IV curve SVGs
with sweep metadata annotations, and manages plot filename tracking
in devices.yaml via FileEntry.extra["plot"].
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def read_iv_csv(filepath: str | Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Read voltage and current from an IV data CSV.

    Handles common column conventions:
      - ``Time,BI,BV`` (Keysight B1500A style)
      - ``Time,Current,Voltage``
      - ``Voltage (V)``, ``Current (A)``, ``Potential (V)``, etc.

    Robust against embedded instrument metadata (common in Autolab exports)
    by reading the file line-by-line and only collecting rows where every
    field in the data columns is a valid float.

    Args:
        filepath: Path to the CSV file.

    Returns:
        (voltage, current, info) where ``info`` contains metadata
        about which columns were detected.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If neither voltage nor current columns can be identified.
    """
    import csv
    import io

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # ── Read header and detect columns ──
    with open(path, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Empty file: {path}")

    expected_cols = len(header)
    header_lower = [h.strip().lower() for h in header]

    # ── Detect voltage, current, and time column indices ──
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

    # Positional fallback for BI/BV convention (Time, BI, BV → cols 0,1,2)
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
        raise ValueError(
            f"Cannot identify voltage column in {path.name}. "
            f"Columns: {header}"
        )
    if current_col is None:
        raise ValueError(
            f"Cannot identify current column in {path.name}. "
            f"Columns: {header}"
        )

    # ── Line-by-line numeric extraction ──
    # Collect ALL numeric rows from ALL data segments in the file.
    # Clarius+ (Keysight B1500A) files contain multiple data segments
    # separated by metadata blocks and re-appearing headers. We skip
    # non-numeric metadata rows and re-appearing "Time,BI,BV" headers,
    # collecting numeric rows from every segment.
    numeric_rows: list[list[float]] = []
    metadata_rows: list[list[str]] = []  # collected for Clarius+ parsing
    skipped_lines: int = 0

    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            # Skip empty lines and separators
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
                # Non-numeric row — metadata or re-appearing header between
                # data segments (e.g. "Device Terminal,B,A", "Time,BI,BV").
                # Collect for Clarius+ metadata parsing, but keep reading.
                metadata_rows.append(stripped)
                skipped_lines += 1
                continue

    if not numeric_rows:
        raise ValueError(f"No valid numeric data found in {path.name}")

    data = np.array(numeric_rows)
    voltage = data[:, voltage_col]
    current = data[:, current_col]
    time_arr = data[:, time_col] if time_col is not None else None

    # Remove NaN
    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]
    if time_arr is not None:
        time_arr = time_arr[mask]

    # Parse Clarius+ metadata from collected non-numeric rows
    clarius_meta = _parse_clarius_metadata(metadata_rows)

    info = {
        "voltage_col": header[voltage_col],
        "current_col": header[current_col],
        "time_col": header[time_col] if time_col is not None else None,
        "n_points": len(voltage),
        "skipped_lines": skipped_lines,
        "clarius_metadata": clarius_meta,
        "time": time_arr,
    }
    return voltage, current, info


def _parse_clarius_metadata(rows: list[list[str]]) -> dict:
    """Parse Keysight B1500A / Clarius+ sweep metadata from CSV metadata rows.

    Scans collected non-numeric rows for recognizable key-value pairs
    and extracts sweep parameters. Handles ``N/A`` values gracefully by
    skipping unparseable fields.

    Recognized keys:
        ``Start/Bias``, ``Stop``, ``Step``, ``Number of Points``,
        ``Compliance``, ``Dual Sweep``, ``Operation Mode``,
        ``Sweep Delay``, ``Hold Time``, ``Speed``.

    Args:
        rows: List of row lists (from csv.reader) that were identified
            as non-data lines during CSV parsing.

    Returns:
        Dict with keys: ``start_v``, ``stop_v``, ``step_v``,
        ``n_points``, ``compliance``, ``dual_sweep_enabled``,
        ``operation_mode``, ``sweep_delay_s``, ``hold_time_s``,
        ``speed``, ``sweep_rate_approx``. Values are ``None``
        for any key not found or unparseable.
    """
    result: dict = {}

    for row in rows:
        if not row or len(row) < 2:
            continue

        key = row[0].strip()
        val = row[1].strip()

        # Attempt numeric parse — may fail for "N/A", "Enabled", etc.
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
            result["dual_sweep_enabled"] = val.lower() in (
                "enabled", "true", "1", "yes",
            )
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

    # ── Calculate derived sweep rate ──
    step_v = result.get("step_v")
    delay = result.get("sweep_delay_s")
    if step_v is not None and delay is not None and delay > 0:
        result["sweep_rate_approx"] = abs(step_v) / delay

    return result


def _extract_from_array(
    data: np.ndarray,
    header: list[str],
    header_lower: list[str],
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Extract voltage/current from a raw numpy array."""
    voltage_col: Optional[int] = None
    current_col: Optional[int] = None

    for i, h in enumerate(header_lower):
        h = h.strip()
        if any(k in h for k in ("voltage", "potential", "bv")):
            if voltage_col is None:
                voltage_col = i
        elif any(k in h for k in ("current", "bi")):
            if current_col is None:
                current_col = i

    if voltage_col is None or current_col is None:
        if data.shape[1] >= 3:
            current_col = 1
            voltage_col = 2
        elif data.shape[1] == 2:
            voltage_col = 1
            current_col = 0

    if voltage_col is None or current_col is None:
        raise ValueError(f"Cannot detect columns in {header}")

    voltage = data[:, voltage_col]
    current = data[:, current_col]
    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    info = {
        "voltage_col": header[voltage_col] if voltage_col < len(header) else f"col{voltage_col}",
        "current_col": header[current_col] if current_col < len(header) else f"col{current_col}",
        "n_points": len(voltage),
    }
    return voltage, current, info


def build_plot_filename(
    row: int,
    col: int,
    material_key: str,
    sweep_type: str,
    order: int,
) -> str:
    """Build a plot filename following the naming convention.

    Format: ``iv_r{row}c{col}_{material}_{sweep_type}_{order:02d}.svg``

    Args:
        row: Matrix row index (0-based).
        col: Matrix column index (0-based).
        material_key: Material+batch key, e.g. ``"Ta-PDAc-ITO(1)"``.
        sweep_type: Sweep type code (``f``, ``sp``, ``sn``, ``uc``).
        order: Sequence number.

    Returns:
        Filename string, e.g. ``"iv_r0c0_Ta-PDAc-ITO(1)_f_01.svg"``.
    """
    # Sanitize material key for filename (already alphanumeric with hyphens/parens)
    material_safe = material_key.replace("/", "-").replace(" ", "_")
    st = sweep_type or "uc"
    return f"iv_r{row}c{col}_{material_safe}_{st}_{order:02d}.svg"


def build_plot_title(
    order: int,
    sweep: list[dict],
    sweep_type: str,
) -> str:
    """Build a plot title string.

    Format: ``#N  |  X.XX V/s  |  direction_path``
    """
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


def _should_use_log_scale(current: np.ndarray) -> bool:
    """Determine if current should use log scale.

    Uses log scale if the absolute current spans more than 2 decades
    (ratio of max to min > 100), excluding values near zero.
    """
    abs_i = np.abs(current)
    pos = abs_i[abs_i > 1e-30]
    if len(pos) < 2:
        return False
    ratio = pos.max() / pos.min()
    return ratio > 100.0


def _format_voltage(v: float) -> str:
    """Format a voltage value for display in direction paths.

    Examples: +3.5V, -2.0V, 0.0V
    """
    if v >= 0:
        return f"+{v:.1f}V"
    else:
        return f"{v:.1f}V"


def _extract_sweep_annotations(sweep: list[dict]) -> dict:
    """Extract annotation text from sweep segment metadata.

    Returns dict with keys: sweep_rate, direction, voltage_range, duration.
    For multi-segment sweeps, builds a human-readable direction path
    (e.g. ``0→+2V→0→-2V→0``) from all segments.
    """
    result: dict = {
        "sweep_rate": None,
        "direction": None,
        "voltage_range": None,
        "duration": None,
    }
    if not sweep:
        return result

    # ── Sweep rate (from first segment) ──
    rate = sweep[0].get("sweep_rate_v_s")
    if rate is not None:
        result["sweep_rate"] = f"{rate:.2f} V/s"

    # ── Build human-readable direction path from all segments ──
    # Check if segments carry explicit start/end voltages
    # (from auto-detected data via _build_sweep_from_data).
    has_start_voltages = all(
        "start_voltage" in seg for seg in sweep
    ) if sweep else False

    if has_start_voltages and len(sweep) >= 1:
        direction_parts: list[str] = []
        for seg in sweep:
            sv = seg["start_voltage"]
            direction_parts.append(_format_voltage(sv))
        # Append the end voltage of the last segment
        last_ev = sweep[-1].get("end_voltage")
        if last_ev is not None:
            direction_parts.append(_format_voltage(last_ev))
        result["direction"] = " → ".join(direction_parts)
    else:
        # Legacy format: build 0→+V→0→-V→0 style from direction/voltage_range
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

        # Deduplicate consecutive "0"s
        deduped: list[str] = []
        for part in direction_parts:
            if deduped and deduped[-1] == "0" and part == "0":
                continue
            deduped.append(part)

        result["direction"] = "→".join(deduped)

    # ── Voltage range and duration (from first segment) ──
    vr_first = sweep[0].get("voltage_range")
    if vr_first is not None:
        result["voltage_range"] = f"{vr_first:.2f}V"

    dur = sweep[0].get("duration_s")
    if dur is not None:
        result["duration"] = f"{dur:.1f} s"

    return result


def _split_at_reversals(
    voltage: np.ndarray, hysteresis: float = 0.1,
) -> list[tuple[int, int]]:
    """Find voltage reversal points using hysteresis-based detection.

    Tracks running max/min as voltage moves. A reversal is triggered
    only when voltage deviates from the current extremum by more than
    ``hysteresis`` (default 0.1 V). This eliminates false reversals
    from sub-mV measurement noise while correctly detecting real
    turn-around points in bipolar sweeps.

    Returns a list of ``(start, end)`` index pairs (end exclusive)
    for each monotonic segment. For a dual-sweep (+3.5V → -3.5V →
    +3.5V) this produces exactly 2 segments.
    """
    if len(voltage) < 3:
        return [(0, len(voltage))]

    # Determine initial direction from median non-zero derivative
    dv = np.diff(voltage)
    nonzero = dv[np.abs(dv) > 1e-10]
    median_dv = float(np.median(nonzero)) if len(nonzero) > 0 else 0.0
    going_up = median_dv > 0

    # Track running extrema
    current_min = float(voltage[0])
    current_max = float(voltage[0])
    segments: list[tuple[int, int]] = []
    start_idx = 0

    for i in range(1, len(voltage)):
        v = float(voltage[i])

        # Update extrema
        if v > current_max:
            current_max = v
        if v < current_min:
            current_min = v

        # Check if voltage has swung far enough to count as reversal
        if going_up:
            # Currently rising — reversal when it drops enough below max
            if current_max - v >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = False
                current_min = v
                current_max = v
        else:
            # Currently falling — reversal when it rises enough above min
            if v - current_min >= hysteresis:
                segments.append((start_idx, i))
                start_idx = i
                going_up = True
                current_min = v
                current_max = v

    # Last segment
    if len(voltage) > start_idx:
        segments.append((start_idx, len(voltage)))

    return segments if segments else [(0, len(voltage))]


def _build_sweep_from_data(
    voltage: np.ndarray,
    time: np.ndarray | None = None,
) -> list[dict]:
    """Build sweep segment metadata from voltage/time data alone.

    Fallback for ``build_plot_title`` when no stored sweep metadata
    exists (neither from ``memristor sync`` nor from parsed Clarius+
    headers). Detects reversal points, infers direction per segment,
    and computes sweep rate if time data is available.

    Uses only the **first continuous sweep** — detects large voltage
    jumps (>1V) that indicate a boundary between separate measurement
    sweeps in concatenated Clarius+ data, and stops before the first
    such boundary.

    Args:
        voltage: Voltage data array (V).
        time: Optional time data array (s) for sweep rate calculation.

    Returns:
        List of segment dicts with keys: ``direction``, ``voltage_range``,
        ``sweep_rate_v_s`` (if time available), ``duration_s`` (if time
        available). Returns one segment for simple sweeps, multiple for
        bipolar sweeps.
    """
    if len(voltage) < 2:
        return []

    # ── Find the first continuous sweep by detecting large jumps ──
    dv = np.abs(np.diff(voltage))
    # A jump > 1V indicates a boundary between separate measurements
    jump_threshold = 1.0  # V
    big_jumps = np.where(dv > jump_threshold)[0]

    if len(big_jumps) > 0:
        first_jump = int(big_jumps[0])
        # Use data up to (and including) the point before the jump
        end_idx = first_jump + 1  # +1 because diff reduces length by 1
        # Skip if the first segment is too short
        if end_idx < 10:
            end_idx = len(voltage)
    else:
        end_idx = len(voltage)

    voltage = voltage[:end_idx]
    if time is not None and len(time) >= end_idx:
        time = time[:end_idx]
    else:
        time = None

    # ── Detect reversals within this continuous sweep ──
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
        # Use the characteristic voltage magnitude (maximum |V| in segment)
        # for display — not the full start-to-end range. This way a segment
        # going +3.5V → -3.5V shows "−3.5V" rather than "−7V".
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

    # Limit to first sweep cycle for display (multi-sweep files
    # can produce dozens of segments — the title should show
    # the characteristic sweep, not every repetition).
    if len(result) > 2:
        result = result[:2]

    return result


# ── Line style cycling (Issue 4) ────────────────────────────
_LINE_COLORS = ["#000000", "#444444", "#888888", "#BBBBBB"]
_LINE_STYLES = ["-", "--", ":", "-."]


def _get_line_style(file_index: int) -> tuple[str, str]:
    """Return (color, linestyle) for a file's position within a cell.

    Cycles through N gray shades and line styles so that multiple
    files at the same (row, col) position are visually distinct.
    """
    color = _LINE_COLORS[file_index % len(_LINE_COLORS)]
    style = _LINE_STYLES[file_index % len(_LINE_STYLES)]
    return color, style


def _plot_simple_sweep(
    ax,
    voltage: np.ndarray,
    current: np.ndarray,
    use_log: bool,
    order: int,
    file_index: int = 0,
) -> None:
    """Plot a single-direction (uc/sp/sn) IV sweep with cycled line style."""
    color, style = _get_line_style(file_index)
    label = f"#{order:02d}"
    if use_log:
        ax.semilogy(voltage, np.abs(current), color=color, linestyle=style,
                     linewidth=0.8, label=label)
        ax.set_ylabel("|Current| (A)", fontsize=10)
    else:
        ax.plot(voltage, current, color=color, linestyle=style,
                linewidth=0.8, label=label)
        ax.set_ylabel("Current (A)", fontsize=10)


def _plot_bipolar_sweep(
    ax,
    voltage: np.ndarray,
    current: np.ndarray,
    use_log: bool,
    order: int,
    file_index: int = 0,
) -> None:
    """Plot a full bipolar (``f``) sweep with forward/reverse distinction.

    Splits data at voltage reversal points. Forward segments use the
    file's cycled color; reverse segments use a muted gray with
    dashed line. Falls back to simple sweep if segmentation yields
    only one chunk.
    """
    segments = _split_at_reversals(voltage)[:2]

    if len(segments) <= 1:
        _plot_simple_sweep(ax, voltage, current, use_log, order, file_index)
        return

    color, _ = _get_line_style(file_index)
    rev_color = "#888888"
    plot_current = np.abs(current) if use_log else current

    for seg_idx, (start, end) in enumerate(segments):
        v_seg = voltage[start:end]
        i_seg = plot_current[start:end]
        if len(v_seg) < 2:
            continue

        is_even = seg_idx % 2 == 0  # forward on even segments

        if is_even:
            # Forward: solid, file's cycled color
            if use_log:
                ax.semilogy(
                    v_seg, i_seg, color=color, linestyle="-", linewidth=0.8,
                    label=f"#{order:02d} fwd" if seg_idx == 0 else None,
                )
            else:
                ax.plot(
                    v_seg, i_seg, color=color, linestyle="-", linewidth=0.8,
                    label=f"#{order:02d} fwd" if seg_idx == 0 else None,
                )
        else:
            # Reverse: dashed gray
            if use_log:
                ax.semilogy(
                    v_seg, i_seg, color=rev_color, linestyle="--", linewidth=0.8,
                    label=f"#{order:02d} rev" if seg_idx == 1 else None,
                )
            else:
                ax.plot(
                    v_seg, i_seg, color=rev_color, linestyle="--", linewidth=0.8,
                    label=f"#{order:02d} rev" if seg_idx == 1 else None,
                )

    if use_log:
        ax.set_ylabel("|Current| (A)", fontsize=10)
    else:
        ax.set_ylabel("Current (A)", fontsize=10)


def generate_iv_svg(
    voltage: np.ndarray,
    current: np.ndarray,
    metadata: dict,
    output_path: str | Path,
    dpi: int = 150,
):
    """Generate an ACS publication-style IV curve SVG.

    ACS (American Chemical Society) style:
      - Sans-serif font (Arial/Helvetica/DejaVu Sans)
      - No grid lines
      - Inward tick marks on all four axes
      - All four spines visible
      - Black line(s), linewidth 0.8
      - Legend without box

    Auto-detects bipolar sweeps from voltage reversals and overrides
    ``sweep_type`` to ``"f"`` when multiple sweep segments are found.

    When no ``sweep`` metadata is available, derives sweep annotations
    directly from the voltage/time data (direction path, sweep rate).

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        metadata: Dict with keys:
            - title (str): Plot title.
            - sweep (list[dict]): Sweep segment metadata (may be empty).
            - sweep_type (str): Sweep type code (``f``, ``uc``, ``sp``, ``sn``).
            - time (Optional[np.ndarray]): Time data for auto-detection fallback.
            - order (int): File sequence number for legend.
            - file_index (int): 0-based index within the cell for line style cycling.
            - row (int), col (int): Matrix position.
        output_path: Path to save the SVG.
        dpi: Resolution for SVG rendering.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    title = metadata.get("title", "IV Curve")
    sweep_type = metadata.get("sweep_type", "") or "uc"
    sweep = metadata.get("sweep", [])
    order = metadata.get("order", 0)
    file_index = metadata.get("file_index", 0)

    # ── Bug 3: Auto-detect bipolar from voltage reversals ──
    segments = _split_at_reversals(voltage)[:2]
    auto_bipolar = len(segments) > 1
    if auto_bipolar:
        sweep_type = "f"

    # ── Bug 4: Auto-detect sweep annotations from data ──
    # When stored sweep metadata is missing or incomplete (no sweep rate),
    # derive annotations directly from the voltage/time data.
    need_auto = not sweep or (
        sweep and sweep[0].get("sweep_rate_v_s", 0) == 0
    )
    if need_auto:
        time_arr = metadata.get("time")
        if time_arr is not None and len(time_arr) == len(voltage):
            derived_sweep = _build_sweep_from_data(voltage, time_arr)
        else:
            derived_sweep = _build_sweep_from_data(voltage, None)
        if derived_sweep:
            # Merge: use auto-detected rate for first segment if stored rate is zero/missing
            if sweep and derived_sweep:
                auto_rate = derived_sweep[0].get("sweep_rate_v_s", 0)
                stored_rate = sweep[0].get("sweep_rate_v_s", 0) if sweep else 0
                if stored_rate == 0 and auto_rate:
                    sweep[0]["sweep_rate_v_s"] = auto_rate
            else:
                sweep = derived_sweep
            title = build_plot_title(order=order, sweep=sweep, sweep_type=sweep_type)

    use_log = _should_use_log_scale(current)

    # ── ACS rcParams (local scope — does not pollute global) ──
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

    with plt.rc_context(acs_rc):
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=dpi)

        # ── Plot based on sweep type ──
        if sweep_type == "f":
            _plot_bipolar_sweep(ax, voltage, current, use_log, order, file_index)
        else:
            _plot_simple_sweep(ax, voltage, current, use_log, order, file_index)

        ax.set_xlabel("Voltage (V)", fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=8, direction="in", which="both")

        # ── ACS: no grid, all four spines visible ──
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.8)

        # ── Legend: no box, small font ──
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(
                handles, labels,
                frameon=False,
                fontsize=8,
                loc="upper left",
            )
            for handle in ax.get_legend().legend_handles:
                handle.set_linewidth(0.8)

        fig.tight_layout()
        fig.savefig(str(output_path), format="svg", dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    logger.info(f"Generated plot: {output_path}")


# ── Batch plotting helpers ──────────────────────────────────


def collect_iv_files(
    config,
    material: str = "",
    row: int | None = None,
    col: int | None = None,
) -> list[dict]:
    """Collect IV file entries from a DeviceConfig for plotting.

    Each returned dict has: point (MatrixPoint), file_entry (FileEntry),
    material_key, order, sweep_type, row, col.

    Args:
        config: DeviceConfig instance.
        material: Optional material+batch filter.
        row: Optional row filter.
        col: Optional col filter.

    Returns:
        List of plot target dicts.
    """
    from science_cli.memristor.device import extract_material_batch

    results: list[dict] = []

    for pt, fe in config.get_all_files("iv"):
        # Apply position filter
        if row is not None and pt.row != row:
            continue
        if col is not None and pt.col != col:
            continue

        # Extract material
        mb_result = extract_material_batch(fe.file)
        if mb_result:
            mat_name, batch = mb_result
            mat_key = f"{mat_name}({batch})" if batch else mat_name
        else:
            mat_key = "unknown"

        # Apply material filter
        if material and mat_key != material:
            continue

        # Determine order
        order = fe.sweep_order
        if order is None:
            # Use 1-based position within this point's sorted files
            tg = pt.techniques.get("iv")
            if tg:
                sorted_files = tg.sorted_files()
                for idx, f in enumerate(sorted_files, 1):
                    if f.file == fe.file:
                        order = idx
                        break
            if order is None:
                order = 0

        results.append({
            "point": pt,
            "file_entry": fe,
            "material_key": mat_key,
            "order": order,
            "sweep_type": fe.sweep_type or "uc",
            "row": pt.row,
            "col": pt.col,
        })

    # Sort by row, col, material, order
    results.sort(key=lambda x: (x["row"], x["col"], x["material_key"], x["order"]))
    return results


def build_fzf_line(target: dict) -> str:
    """Build a preview line for fzf display.

    Format: ``r{row}c{col}  {material}  {sweep_type}  {file}``
    """
    return (
        f"r{target['row']}c{target['col']}  "
        f"{target['material_key']:<25s}  "
        f"{target['sweep_type']:<3s}  "
        f"{target['file_entry'].file}"
    )
