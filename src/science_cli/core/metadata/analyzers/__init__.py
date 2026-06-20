"""Analyzer registry — maps function name to DataFrame-compute function.

All analyze functions run computations on loaded DataFrames. They live in
instrument/mechanism-specific modules under this package.
"""

from __future__ import annotations

from typing import Callable

from science_cli.core.metadata.analyzers.iv import analyze_iv_compliance
from science_cli.core.metadata.analyzers.waveform import (
    analyze_waveform_params,
    detect_repeat_pattern,
    extract_waveform_metadata,
)

ANALYSIS_REGISTRY: dict[str, Callable] = {
    "analyze_waveform_params": analyze_waveform_params,
    "analyze_iv_compliance": analyze_iv_compliance,
    "detect_repeat_pattern": detect_repeat_pattern,
    "extract_waveform_metadata": extract_waveform_metadata,
}
