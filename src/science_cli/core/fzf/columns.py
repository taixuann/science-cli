"""Per-study fzf column registry and helpers.

Defines which metadata columns to display in fzf for each study type,
and provides helpers for status badges and step column filtering.

The registry is keyed by ``(study_name, device_type)`` tuples.  Study-level
entries use ``device_type=None`` as the fall-through default.  Device-specific
overrides (e.g. ``("pulse:pulse-endurance", "volatile-memristor")``) take
priority when the caller supplies a matching device type.
"""

from __future__ import annotations

from pathlib import Path


# ── Global columns (always shown before per-study metadata) ──────

GLOBAL_COLUMNS: list[tuple[str, int]] = [
    ("Step",      16),   # step name from protocol.yaml
    ("DateTime",  14),   # DDMMYY-HHMMSS from filename
    ("Device-ID", 30),   # device-id from filename
    ("Study",     16),   # study name from filename
    ("Remarks",   12),   # remarks from filename
    ("Flags",      8),   # flags from filename
    ("Count",      6),   # count from filename
]


def get_global_columns(filepath: str, step_name: str | None = None) -> list[str]:
    """Return global column values for a file.

    Parses the filename using the universal convention
    (``DDMMYY-HHMMSS_device-id_study_remarks_flags_count.ext``)
    and returns one formatted column per ``GLOBAL_COLUMNS`` entry.

    Args:
        filepath: Full path to the data file.
        step_name: Optional step name from protocol.yaml (populates the
            ``Step`` column).

    Returns:
        List of formatted column strings, one per ``GLOBAL_COLUMNS`` entry,
        each padded to its configured width.
    """
    from science_cli.core.grammar import parse_filename

    fname = Path(filepath).name
    parsed = parse_filename(fname)

    columns: list[str] = []
    for col_name, width in GLOBAL_COLUMNS:
        if col_name == "Step" and step_name:
            val: str = step_name[:width]
        elif col_name == "DateTime" and parsed:
            dt = f"{parsed.get('date_code', '')}-{parsed.get('timestamp', '')}"
            val = dt[:width]
        elif col_name == "Device-ID" and parsed:
            val = (parsed.get("device_id", "") or "")[:width]
        elif col_name == "Study" and parsed:
            val = (parsed.get("study", "") or "")[:width]
        elif col_name == "Remarks" and parsed:
            val = (parsed.get("remarks", "") or "")[:width]
        elif col_name == "Flags" and parsed:
            val = (parsed.get("flags", "") or "")[:width]
        elif col_name == "Count" and parsed:
            cnt = parsed.get("count")
            val = str(cnt or "")[:width]
        else:
            val = ""
        columns.append(val.ljust(width))

    return columns


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


def flag_badge_for_file(filename: str) -> str:
    """Return a single-char flag badge parsed from the filename.
    
    Reads the ``flags`` field from the universal grammar pattern and maps
    to a symbol::
        important    → ★ (star)
        valid        → ✓ (check)
        invalid      → ✗ (cross)
        discard      → 🗑 (trash)
        questionable → ? (question)
    
    Returns:
        Single-char badge string, or empty string if no flags or unrecognized.
    """
    from science_cli.core.grammar import parse_filename
    parsed = parse_filename(filename)
    if not parsed:
        return ""
    flags = parsed.get("flags", "")
    if not flags:
        return ""
    _FLAG_BADGE_MAP = {
        "important": "★",
        "valid": "✓",
        "invalid": "✗",
        "discard": "🗑",
        "questionable": "?",
    }
    return _FLAG_BADGE_MAP.get(flags.lower(), "")


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
