"""Metadata extraction — parse (header scan) and analyze (computation) pipeline.

ANALYSIS_REGISTRY maps analysis function names to callables. It's registered
here and invoked by the metadata pipeline when an instrument config declares
``method: analyze``.

The pipeline is instrument-agnostic: it reads config, dispatches to
registered parse/analyze functions, and returns merged dicts.
"""

from __future__ import annotations

from typing import Callable


def run_analysis(
    analysis_name: str,
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    """Dispatch to registered analysis function and return output dict."""
    fn = ANALYSIS_REGISTRY.get(analysis_name)
    if fn is None:
        return {}
    return fn(df, raw_lines, inputs or {})


def extract_metadata(
    raw_lines: list[str],
    metadata_config: dict,
    df=None,
) -> tuple[dict, dict]:
    """Run the metadata extraction pipeline.

    Args:
        raw_lines: All raw lines from the file.
        metadata_config: The ``metadata`` section from instrument config.
        df: Loaded DataFrame (needed for analyze methods).

    Returns:
        (parsed_meta, analysis_meta) where parsed_meta is header-parsed
        values and analysis_meta is computed analysis values.
    """
    from science_cli.core.metadata.keysight import (
        parse_compliance,
        parse_repeat_count,
        parse_set_voltage,
        parse_sweep_range,
    )
    from science_cli.core.metadata.waveform import parse_setup_pulses

    _parser_registry: dict[str, Callable] = {
        "set_voltage": parse_set_voltage,
        "compliance": parse_compliance,
        "sweep_range": parse_sweep_range,
        "repeat_count": parse_repeat_count,
        "setup_pulses": parse_setup_pulses,
    }

    parsed: dict = {}
    analysis: dict = {}

    for field_name, field_cfg in metadata_config.items():
        method = field_cfg.get("method", "parse")

        if method == "parse":
            val = _run_parse(field_name, field_cfg, raw_lines, _parser_registry)
            parsed[field_name] = val

        elif method == "analyze":
            if df is not None:
                func_name = field_cfg.get("function", "")
                inputs = field_cfg.get("inputs", [])
                result = run_analysis(func_name, df, raw_lines, {"inputs": inputs})
                analysis[field_name] = result

    return parsed, analysis


def _run_parse(
    field_name: str,
    field_cfg: dict,
    raw_lines: list[str],
    parser_registry: dict[str, Callable],
):
    """Run a single parse step, trying parser functions first, then regex/csv_field."""
    import re

    extract_cfg = field_cfg.get("extract", {})
    header_key = field_cfg.get("header_key", "")
    parser_name = field_cfg.get("parser", "")

    if parser_name and parser_name in parser_registry:
        return parser_registry[parser_name](raw_lines)

    if extract_cfg.get("regex"):
        pattern = extract_cfg["regex"]
        group = int(extract_cfg.get("group", 0))
        for line in raw_lines:
            if header_key and header_key not in line:
                continue
            m = re.search(pattern, line)
            if m:
                try:
                    val = m.group(group)
                except IndexError:
                    val = m.group(0)
                return _try_numeric(val)

    if extract_cfg.get("csv_field") is not None and header_key:
        csv_idx = int(extract_cfg["csv_field"])
        for line in raw_lines:
            if line.strip().startswith(header_key) or header_key in line:
                parts = [p.strip() for p in line.split(",")]
                if csv_idx < len(parts):
                    return _try_numeric(parts[csv_idx])

    return None


def _try_numeric(val):
    """Convert to float/int if possible, otherwise return as-is."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        pass
    try:
        return float(val)
    except (ValueError, TypeError):
        pass
    return val


def _analyze_waveform_params(
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    from science_cli.core.metadata.waveform import analyze_waveform_params

    return analyze_waveform_params(df, raw_lines, inputs or {})


def _detect_repeat_pattern(
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    from science_cli.core.metadata.waveform import detect_repeat_pattern

    return detect_repeat_pattern(df)


def _analyze_iv_compliance(
    df,
    raw_lines: list[str],
    inputs: dict | None = None,
) -> dict:
    from science_cli.core.metadata.keysight import analyze_iv_compliance

    return analyze_iv_compliance(df, raw_lines, inputs or {})


ANALYSIS_REGISTRY: dict[str, Callable] = {
    "analyze_waveform_params": _analyze_waveform_params,
    "analyze_iv_compliance": _analyze_iv_compliance,
    "detect_repeat_pattern": _detect_repeat_pattern,
}
