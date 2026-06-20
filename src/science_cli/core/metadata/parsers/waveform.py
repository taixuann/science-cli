"""Waveform pulse header parser — extract setup pulse metadata from raw lines.

Parse functions live here; DataFrame-compute analyzers live in ``analyzers/waveform.py``.
Moved from ``core/metadata/waveform.py`` as part of parsers/ + analyzers/ split.
"""

from __future__ import annotations


def parse_setup_pulses(raw_lines: list[str]) -> dict | None:
    for line in raw_lines:
        if "SetupTitle" in line:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) > 1 and ("stp" in parts[1].lower() or "pulse" in parts[1].lower()):
                return {"setup_title": parts[1]}
    return None
