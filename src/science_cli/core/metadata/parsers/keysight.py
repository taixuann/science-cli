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


# ---------------------------------------------------------------------------
# WGFMU Waveform column parser (Tier 1 programmed-pattern detection)
# ---------------------------------------------------------------------------

def parse_wgfmu_waveform_segments(df: pd.DataFrame) -> dict | None:
    """Parse WGFMU Waveform columns into raw (time, voltage) pairs.

    Tier 1: Direct column parse when ``Waveform1_voltage`` exists.

    Extracts the **programmed** pulse pattern from the optional
    ``Waveform1_time`` / ``Waveform1_voltage`` columns embedded alongside
    measured data in Keysight WGFMU (B1500A) CSV files.

    Returns just the raw ``[[t, v], ...]`` array — no segment merging,
    no voltage rounding, no labeled fields or width calculations.
    Downstream analyzers handle any further interpretation.

    Args:
        df: DataFrame with columns ``Waveform1_time``, ``Waveform1_voltage``.

    Returns:
        dict with keys:
        - ``waveform_programmed``: True
        - ``waveform_2d``: list of ``[t, v]`` pairs sorted by time
          (with duplicates removed).
        Returns ``None`` if ``Waveform1_voltage`` column not found.
    """
    if "Waveform1_voltage" not in df.columns:
        return None

    wf_time = "Waveform1_time"
    wf_volt = "Waveform1_voltage"

    wf_df = df[[wf_time, wf_volt]].copy()

    # Handle empty/whitespace cells — some files have fewer waveform points
    wf_df[wf_volt] = pd.to_numeric(wf_df[wf_volt], errors='coerce')
    wf_df[wf_time] = pd.to_numeric(wf_df[wf_time], errors='coerce')
    wf_df = wf_df.dropna(subset=[wf_time, wf_volt])

    if wf_df.empty:
        return None

    wf_df = wf_df.sort_values(wf_time).drop_duplicates()

    array_2d = [
        [float(t), float(v)]
        for t, v in zip(wf_df[wf_time], wf_df[wf_volt])
    ]

    if not array_2d:
        return None

    return {
        "waveform_programmed": True,
        "waveform_2d": array_2d,
    }
