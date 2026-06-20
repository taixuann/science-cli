"""IV data I/O — CSV/LVM file reading utilities.

Extracted from the deleted ``library/memristor/plotting.py`` to provide
pure data-loading functions (read_iv_csv, read_iv_lvm) without the SVG
generation that was also in that module.
"""

from __future__ import annotations

import csv
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

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # ── Auto-detect tab-separated measurement files ──
    with open(path, newline="") as f:
        first_line = f.readline()
    if "LabVIEW Measurement" in first_line:
        return read_iv_lvm(path)

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

    # ── Expose first and last timestamps ──
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
    """Read voltage and current from a tab-separated measurement file.

    Parses the two-block header delimited by ``***End_of_Header***`` markers,
    extracts metadata (date, time, operator, channels, samples), and reads
    tab-separated numeric data with positional column mapping:

        - col0: X_Value (row counter, skipped)
        - col1: Untitled (Voltage)
        - col2: Untitled 1 (Current)
        - col3: Untitled 2 (Timestamp)
        - col4: Comment (ignored)

    Args:
        filepath: Path to the data file.

    Returns:
        (voltage, current, metadata_dict) where ``metadata_dict`` includes
        ``source``, ``date``, ``time``, ``operator``, ``channels``,
        ``samples``, ``voltage_col``, ``current_col``, ``n_points``.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not in the expected format, has fewer than 3 data
            columns, or contains no valid numeric data.
    """

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, newline="") as f:
        # ── Header signature check ──
        first_line = f.readline()
        if "LabVIEW Measurement" not in first_line:
            raise ValueError(
                f"Not a LabVIEW Measurement file: {path.name}"
            )

        # ── Read entire file into lines for multi-pass parsing ──
        raw = f.read()
        lines = raw.splitlines()

    # ── Locate header-block delimiters ──
    eoh_positions: list[int] = []
    for idx, line in enumerate(lines):
        if line.strip() == "***End_of_Header***":
            eoh_positions.append(idx)

    if len(eoh_positions) < 2:
        raise ValueError(
            f"LVM file {path.name} missing required ***End_of_Header*** "
            f"delimiters (found {len(eoh_positions)})"
        )

    first_eoh = eoh_positions[0]
    second_eoh = eoh_positions[1]

    # ── Block 1: General metadata (before first End_of_Header) ──
    block1_lines = lines[:first_eoh]
    metadata: dict = {"source": "LabVIEW Measurement"}
    for raw_line in block1_lines:
        row = raw_line.split("\t")
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            if key and val:
                metadata[key] = val

    # ── Block 2: Channel info (between first and second End_of_Header) ──
    block2_lines = lines[first_eoh + 1 : second_eoh]
    for raw_line in block2_lines:
        row = raw_line.split("\t")
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            if key and val:
                metadata[key] = val

    # ── Column header line (first non-blank line after second End_of_Header) ──
    data_start = second_eoh + 1
    # Skip blank lines between End_of_Header marker and column headers
    while data_start < len(lines) and not lines[data_start].strip():
        data_start += 1
    if data_start >= len(lines):
        raise ValueError(f"LVM file {path.name} has no column header after headers")

    col_header_line = lines[data_start]
    col_headers = [c.strip() for c in col_header_line.split("\t")]

    if len(col_headers) < 3:
        raise ValueError(
            f"LVM file {path.name} has fewer than 3 data columns "
            f"(found {len(col_headers)})"
        )

    # ── Read tab-separated numeric data rows ──
    numeric_rows: list[list[float]] = []
    ts_values: list[float] = []

    for raw_line in lines[data_start + 1 :]:
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue

        fields = [s.strip() for s in raw_line.split("\t")]

        # Require at least voltage + current columns (col1, col2)
        if len(fields) < 3:
            continue

        try:
            # Only parse voltage (col1) and current (col2) as numeric;
            # col0 (X_Value / row counter) and col3 (timestamp) may be
            # non-numeric strings.
            _ = [float(fields[1]), float(fields[2])]  # validate parseable
            numeric_rows.append([float(fields[1]), float(fields[2])])

            # Attempt to parse timestamp from col3 if available
            if len(fields) >= 4:
                try:
                    ts_values.append(float(fields[3]))
                except ValueError:
                    ts_values.append(0.0)
        except (ValueError, IndexError):
            continue

    if not numeric_rows:
        raise ValueError(
            f"No valid numeric data found in LVM file {path.name}"
        )

    data = np.array(numeric_rows)
    voltage = data[:, 0]   # col1 → Untitled (Voltage)
    current = data[:, 1]   # col2 → Untitled 1 (Current)

    # Remove NaN
    mask = ~(np.isnan(voltage) | np.isnan(current))
    voltage = voltage[mask]
    current = current[mask]

    # ── Build result metadata map ──
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
