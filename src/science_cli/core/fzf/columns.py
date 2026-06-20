"""Per-study fzf column registry and helpers.

Defines which metadata columns to display in fzf for each study type,
and provides helpers for status badges and step column filtering.

The registry is keyed by ``(study_name, device_type)`` tuples.  Study-level
entries use ``device_type=None`` as the fall-through default.  Device-specific
overrides (e.g. ``("pulse:pulse-endurance", "volatile-memristor")``) take
priority when the caller supplies a matching device type.
"""

from __future__ import annotations


# ── Study column registry ────────────────────────────────────────

# Registry: (study_name, device_type) -> list of metadata column keys
# Entries with device_type=None are study-level defaults (fall-through).
STUDY_COLUMN_REGISTRY: dict[tuple[str, str | None], list[str]] = {
    # ── Device-specific overrides ──────────────────────────────
    # volatile endurance: read-decay columns
    ("pulse:pulse-endurance", "volatile-memristor"): [
        "v_set_v", "v_read_v", "set_width_us", "read_width_us",
        "n_cycles", "repeat_pattern",
    ],
    # non-volatile endurance: reset sweep columns
    ("pulse:pulse-endurance", "non-volatile-memristor"): [
        "v_set_v", "v_reset_v", "set_width_us", "reset_width_us",
        "read_width_us", "n_cycles", "repeat_pattern",
    ],
    # ── Study-level defaults (device_type=None) ────────────────
    ("pulse:pulse-stp-decay", None): [
        "v_set_v", "v_read_v", "set_width_us", "read_width_us",
        "rise_us", "fall_us", "repeat_pattern",
    ],
    ("pulse:pulse-endurance", None): [
        "v_set_v", "v_reset_v", "set_width_us", "reset_width_us",
        "read_width_us", "n_cycles", "repeat_pattern",
    ],
    ("pulse:pulse-ppf", None): [
        "v_set_v", "v_read_v", "set_width_us", "read_width_us",
        "interval_min_ms", "interval_max_ms",
    ],
    ("iv:iv-bipolar-sweep", None): [
        "sweep_pattern", "v_set", "v_reset", "compliance_a",
        "step_v", "delay_s",
    ],
    ("ec:ec-cv", None): ["v_min", "v_max", "scan_rate_mv_s", "n_cycles"],
    ("ec:ec-ca", None): ["v_step", "duration_s", "sample_interval_s"],
    ("ec:ec-eis", None): ["freq_min_hz", "freq_max_hz", "amplitude_v", "n_points"],
    ("raman:raman-spectrum", None): [
        "laser_nm", "nd_filter", "accumulation", "acq_time_s",
    ],
    ("uv-vis:uv-vis-spectrum", None): [
        "wavelength_min_nm", "wavelength_max_nm", "scan_rate_nm_min",
    ],
}


def get_columns_for(study_name: str, device_type: str | None = None) -> list[str]:
    """Return column list, device-specific if registered, else study default.

    Resolution order:
      1. ``(study_name, device_type)`` — device-specific override
      2. ``(study_name, None)`` — study-level default (fall-through)
      3. ``[]`` — unknown study
    """
    if device_type is not None and (study_name, device_type) in STUDY_COLUMN_REGISTRY:
        return STUDY_COLUMN_REGISTRY[(study_name, device_type)]
    return STUDY_COLUMN_REGISTRY.get((study_name, None), [])


# Backwards-compat alias (flat study->cols, for tests that index by name only)
_STUDY_BY_NAME: dict[str, list[str]] = {}
for (_study, _device), _cols in STUDY_COLUMN_REGISTRY.items():
    if _device is None:
        _STUDY_BY_NAME[_study] = _cols


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
    project_root,
    step_name: str,
    study_name: str | None = None,
    device_type: str | None = None,
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
    device_type:
        If provided, use device-specific column override when available.

    Returns
    -------
    dict
        column_name -> value (only the keys the study cares about).
    """
    from pathlib import Path
    from science_cli.core.protocol import read_step_metadata

    metadata = read_step_metadata(Path(project_root), step_name) or {}
    if study_name:
        cols = get_columns_for(study_name, device_type)
        if cols:
            return {k: metadata.get(k) for k in cols if k in metadata}
    return metadata
