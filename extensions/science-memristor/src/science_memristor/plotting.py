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

    # ── Detect voltage and current column indices ──
    voltage_col: Optional[int] = None
    current_col: Optional[int] = None

    for i, cl in enumerate(header_lower):
        if any(k in cl for k in ("voltage", "potential", "e (v)", "v)", "bv", "bias voltage")):
            if voltage_col is None:
                voltage_col = i
        elif any(k in cl for k in ("current", "i (a)", "i/a", "i)", "we(1).current", "bi", "bias current")):
            if current_col is None:
                current_col = i

    # Positional fallback for BI/BV convention (Time, BI, BV → cols 0,1,2)
    if voltage_col is None and current_col is None and expected_cols == 3:
        if any(k in header_lower[1] for k in ("bi", "current", "i")):
            current_col = 1
        if any(k in header_lower[2] for k in ("bv", "voltage", "v")):
            voltage_col = 2
    if voltage_col is None and current_col is None and expected_cols >= 2:
        if "time" in header_lower[0]:
            current_col = 1
            voltage_col = 2

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
    # Only collect rows where every field is a parseable float.
    # Stops at the first non-numeric row (metadata section marker).
    numeric_rows: list[list[float]] = []

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
                # Non-numeric row encountered — stop here
                # (this handles metadata lines like "Device Terminal,B,A")
                break

    if not numeric_rows:
        raise ValueError(f"No valid numeric data found in {path.name}")

    data = np.array(numeric_rows)
    voltage = data[:, voltage_col]
    current = data[:, current_col]

    # Remove NaN
    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    info = {
        "voltage_col": header[voltage_col],
        "current_col": header[current_col],
        "n_points": len(voltage),
    }
    return voltage, current, info


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
    direction_parts: list[str] = ["0"]
    for seg in sweep:
        d = seg.get("direction", "")
        vr = seg.get("voltage_range")
        if vr is not None and vr != 0:
            if d in ("forward", "fwd", "f"):
                target = f"+{vr:.0f}V" if vr > 0 else f"{vr:.0f}V"
            elif d in ("reverse", "rev", "r"):
                target = f"-{vr:.0f}V" if vr > 0 else f"{vr:.0f}V"
            else:
                target = f"{vr:.0f}V"
            direction_parts.append(target)
            direction_parts.append("0")
        else:
            # If no voltage range, just note the direction
            if d:
                direction_parts.append(f"({d})")

    # Deduplicate consecutive "0"s (happens when segments chain: 0→V→0→-V→0)
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


def _split_at_reversals(voltage: np.ndarray) -> list[tuple[int, int]]:
    """Find voltage reversal points in sweep data.

    Detects where the voltage derivative changes sign (i.e., the sweep
    changes direction). Returns a list of ``(start, end)`` index pairs
    (end exclusive) for each monotonic segment.

    If no clear reversals are found, returns a single segment covering
    the entire data.
    """
    if len(voltage) < 3:
        return [(0, len(voltage))]

    dv = np.diff(voltage)

    # Find sign-change indices in the derivative
    reversal_indices: list[int] = []
    for i in range(1, len(dv)):
        if dv[i - 1] * dv[i] < 0:
            reversal_indices.append(i)

    if not reversal_indices:
        return [(0, len(voltage))]

    # Build segments from reversal points
    segments: list[tuple[int, int]] = []
    start = 0
    for r in reversal_indices:
        if r > start + 1:  # at least 2 meaningful data points
            segments.append((start, r + 1))
        start = r

    if len(voltage) > start + 1:
        segments.append((start, len(voltage)))

    return segments if segments else [(0, len(voltage))]


def _plot_simple_sweep(
    ax,
    voltage: np.ndarray,
    current: np.ndarray,
    use_log: bool,
    order: int,
) -> None:
    """Plot a single-direction (uc/sp/sn) IV sweep as a black line."""
    label = f"#{order:02d}"
    if use_log:
        ax.semilogy(voltage, np.abs(current), "k-", linewidth=0.8, label=label)
        ax.set_ylabel("|Current| (A)", fontsize=10)
    else:
        ax.plot(voltage, current, "k-", linewidth=0.8, label=label)
        ax.set_ylabel("Current (A)", fontsize=10)


def _plot_bipolar_sweep(
    ax,
    voltage: np.ndarray,
    current: np.ndarray,
    use_log: bool,
    order: int,
) -> None:
    """Plot a full bipolar (``f``) sweep with forward/reverse distinction.

    Splits data at voltage reversal points. Forward segments are drawn
    in black; reverse segments in gray (``#888888``). Falls back to a
    simple black line if segmentation yields only one chunk.
    """
    segments = _split_at_reversals(voltage)

    if len(segments) <= 1:
        _plot_simple_sweep(ax, voltage, current, use_log, order)
        return

    plot_current = np.abs(current) if use_log else current

    for seg_idx, (start, end) in enumerate(segments):
        v_seg = voltage[start:end]
        i_seg = plot_current[start:end]
        if len(v_seg) < 2:
            continue

        is_even = seg_idx % 2 == 0  # forward on even segments

        if is_even:
            # Forward: solid black
            if use_log:
                ax.semilogy(
                    v_seg, i_seg, "k-", linewidth=0.8,
                    label=f"#{order:02d} fwd" if seg_idx == 0 else None,
                )
            else:
                ax.plot(
                    v_seg, i_seg, "k-", linewidth=0.8,
                    label=f"#{order:02d} fwd" if seg_idx == 0 else None,
                )
        else:
            # Reverse: solid gray
            if use_log:
                ax.semilogy(
                    v_seg, i_seg, "-", linewidth=0.8, color="#888888",
                    label=f"#{order:02d} rev" if seg_idx == 1 else None,
                )
            else:
                ax.plot(
                    v_seg, i_seg, "-", linewidth=0.8, color="#888888",
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

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        metadata: Dict with keys:
            - title (str): Plot title.
            - sweep (list[dict]): Sweep segment metadata.
            - sweep_type (str): Sweep type code (``f``, ``uc``, ``sp``, ``sn``).
            - order (int): File sequence number for legend.
            - row (int), col (int): Matrix position.
        output_path: Path to save the SVG.
        dpi: Resolution for SVG rendering.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    title = metadata.get("title", "IV Curve")
    sweep_type = metadata.get("sweep_type", "") or "uc"
    order = metadata.get("order", 0)

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
            _plot_bipolar_sweep(ax, voltage, current, use_log, order)
        else:
            _plot_simple_sweep(ax, voltage, current, use_log, order)

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
    from science_memristor.device import extract_material_batch

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
