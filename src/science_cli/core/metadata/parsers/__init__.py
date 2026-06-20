"""Parser registry — maps parser name to header-scanning function.

All parse functions extract metadata from raw file header lines (no computation).
They live in instrument-specific modules under this package.
"""

from __future__ import annotations

from typing import Callable

from science_cli.core.metadata.parsers.keysight import (
    parse_compliance,
    parse_repeat_count,
    parse_set_voltage,
    parse_sweep_range,
)
from science_cli.core.metadata.parsers.raman import extract_raman_metadata
from science_cli.core.metadata.parsers.waveform import parse_setup_pulses

_parser_registry: dict[str, Callable] = {
    "set_voltage": parse_set_voltage,
    "compliance": parse_compliance,
    "sweep_range": parse_sweep_range,
    "repeat_count": parse_repeat_count,
    "setup_pulses": parse_setup_pulses,
    "raman_metadata": extract_raman_metadata,
}
