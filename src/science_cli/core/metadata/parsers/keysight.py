"""Keysight B1500A header parsers — extract metadata from raw file header lines.

Parse functions extract metadata from raw file header lines (no computation).
Moved from ``core/metadata/keysight.py`` as part of parsers/ + analyzers/ split.
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
