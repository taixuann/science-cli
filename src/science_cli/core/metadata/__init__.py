"""Metadata extraction — parse (header scan) and analyze (DataFrame compute).

Public API (unchanged):
    - extract_metadata(raw_lines, metadata_config, df=None) -> (parsed, analysis)
    - run_analysis(name, df, raw_lines, inputs=None) -> dict
    - ANALYSIS_REGISTRY, _parser_registry
"""

from __future__ import annotations

from typing import Callable

from science_cli.core.metadata.analyzers import ANALYSIS_REGISTRY
from science_cli.core.metadata.parsers import _parser_registry


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
