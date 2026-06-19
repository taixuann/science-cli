"""Per-study fzf column registry and helpers.

Defines which metadata columns to display in fzf for each study type,
and provides helpers for status badges and step column filtering.
"""

from __future__ import annotations


# ── Study column registry ────────────────────────────────────────

# Registry: study_name -> list of metadata column keys to show in fzf
STUDY_COLUMN_REGISTRY: dict[str, list[str]] = {
    "pulse:pulse-stp-decay": [
        "v_set_v", "v_read_v", "set_width_us", "read_width_us",
        "rise_us", "fall_us", "repeat_pattern",
    ],
    "pulse:pulse-endurance": [
        "v_set_v", "v_reset_v", "set_width_us", "reset_width_us",
        "read_width_us", "n_cycles", "repeat_pattern",
    ],
    "pulse:pulse-ppf": [
        "v_set_v", "v_read_v", "set_width_us", "read_width_us",
        "interval_min_ms", "interval_max_ms",
    ],
    "iv:iv-bipolar-sweep": [
        "sweep_pattern", "v_set", "v_reset", "compliance_a",
        "step_v", "delay_s",
    ],
    "ec:ec-cv": ["v_min", "v_max", "scan_rate_mv_s", "n_cycles"],
    "ec:ec-ca": ["v_step", "duration_s", "sample_interval_s"],
    "ec:ec-eis": ["freq_min_hz", "freq_max_hz", "amplitude_v", "n_points"],
    "raman:raman-spectrum": [
        "laser_nm", "nd_filter", "accumulation", "acq_time_s",
    ],
    "uv-vis:uv-vis-spectrum": [
        "wavelength_min_nm", "wavelength_max_nm", "scan_rate_nm_min",
    ],
}


def status_badge_for_file(
    file_key: str, status_dict: dict | None
) -> str:
    """Return a single-char status badge for a file.

    Returns: '★' (highlight), '✓' (keep), '✗' (discard), '' (none/clear)
    """
    if not status_dict:
        return ""
    tag = status_dict.get(file_key)
    if tag == "highlight" or tag == "star":
        return "★"
    if tag == "keep":
        return "✓"
    if tag == "discard":
        return "✗"
    return ""


def get_step_columns(
    project_root, step_name: str, study_name: str | None = None
) -> dict:
    """Read step.metadata and return only the columns needed for fzf display.

    Parameters
    ----------
    project_root:
        Project root path (Path or str).
    step_name:
        Step name to look up.
    study_name:
        If provided, use STUDY_COLUMN_REGISTRY to filter/order columns.

    Returns
    -------
    dict
        column_name -> value (only the keys the study cares about).
    """
    from pathlib import Path
    from science_cli.core.protocol import read_step_metadata

    metadata = read_step_metadata(Path(project_root), step_name) or {}
    if study_name and study_name in STUDY_COLUMN_REGISTRY:
        cols = STUDY_COLUMN_REGISTRY[study_name]
        return {k: metadata.get(k) for k in cols if k in metadata}
    return metadata
