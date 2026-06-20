"""Keithley 2400 header parsers — minimal header metadata.

Keithley files have less structured header metadata than Keysight B1500A.
These parsers extract what's available from the free-form text header.

Moved from ``core/metadata/keithley.py`` as part of parsers/ + analyzers/ split.
"""

from __future__ import annotations

import re


def parse_compliance(lines: list[str]) -> float | None:
    """Extract compliance from Keithley file header.

    Looks for lines like: "Compliance: 1e-3 A"
    """
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("compliance"):
            m = re.search(r"([\d.eE+\-]+)", stripped.split(":")[-1])
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    return None
    return None


def parse_sweep_range(lines: list[str]) -> dict | None:
    """Extract sweep start/stop from Keithley file header.

    Looks for lines like: "Start: 0 V" and "Stop: 5 V"
    """
    start: float | None = None
    stop: float | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("start"):
            m = re.search(r"([\d.\-]+)", stripped.split(":")[-1])
            if m:
                try:
                    start = float(m.group(1))
                except ValueError:
                    pass
        elif stripped.lower().startswith("stop"):
            m = re.search(r"([\d.\-]+)", stripped.split(":")[-1])
            if m:
                try:
                    stop = float(m.group(1))
                except ValueError:
                    pass
    if start is not None and stop is not None:
        return {"start": start, "stop": stop}
    return None
