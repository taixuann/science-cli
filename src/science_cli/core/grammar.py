"""Universal filename parsing convention for science-cli.

All new data files follow a single canonical naming convention
instead of per-instrument regex patterns. This module defines
the convention and provides parsing utilities.

Universal pattern::

    DDMMYY-HHMMSS_device-id_study_{remarks}_[flags]_count.ext

Examples::

    200626-122036_cu-c-pda(q5)-ito(2)_r3-c4_pulse-endurance_initial-rerun_flagged_001.csv
    190626-185918_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_pulse-endurance_{extracted-list}_[discard]_001.csv
    190626-185918_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_pulse-endurance_{raw}.csv
    190626-185918_keysight-b1500a_cu-c-pda(q5)-ito(2)_r3-c3_pulse-endurance_[valid].csv
    050526_ta-pda(c1)-ito_iv-sweep_r3-c1_001.csv  (legacy, pre-v3.20)

Field reference (in order from left to right):

    ============ ====================================== ========== ============================
    Field        Example                                Mandatory  Type
    ============ ====================================== ========== ============================
    date_code    200626                                 Yes        str (6 digits)
    timestamp    122036                                 Yes        str (6 digits)
    device_id    cu-c-pda(q5)-ito(2)_r3-c4              Yes        str (any chars; may contain
                                                                     underscores)
    study        pulse-endurance                        Yes        str (alphanumeric, hyphens,
                                                                     slashes; no underscores)
    remarks      extracted-list                          No         str | None (alphanumeric +
                                                                     hyphens + underscores,
                                                                     delimited by ``{...}``)
    flags        discard                                No         str | None (letters +
                                                                     hyphens, delimited by
                                                                     ``[...]``)
    count        001                                    No         int | None (digits only)
    ext          csv                                    Yes        str (file extension)
    ============ ====================================== ========== ============================

Parsing strategy (right-to-left disambiguation):

    1. Strip directory components, leaving the bare filename.
    2. Extract ``date_code``, ``timestamp``, and ``ext`` via regex on
       the fixed-width prefix and trailing extension.
    3. Split the remaining body on ``_`` into segments.
    4. From the right:
       - If the last segment is all digits → ``count`` (unambiguous).
       - If the next segment looks like ``[flags]`` → strip brackets.
       - If the next segment looks like ``{remarks}`` → strip brackets.
       - If no bracket-delimited fields were found, fall back to the
         legacy heuristic (collect up to 2 text-only segments checked
         against ``_is_viable_study()``) for backward compatibility
         with pre-v3.20 filenames.
    5. The next segment to the left is the mandatory ``study``.
    6. Everything further left becomes ``device_id`` (joined with ``_``).

Notes:

    - ``device_id`` CAN contain underscores — the right-to-left
      disambiguation handles this correctly.
    - ``remarks`` is always wrapped in ``{...}`` when building.
    - ``flags`` is always wrapped in ``[...]`` when building.
    - Legacy files that don't match the universal pattern should use the
      ``detect_study_from_filename()`` fallback in ``studies.py``.
"""

from __future__ import annotations

import re
from typing import Any

# Regex used for filename_matches_convention() — strict check, no underscores
# in device_id. This is intentionally conservative.
_UNIVERSAL_PATTERN_STRICT = re.compile(
    r"^(?P<date_code>\d{6})-"
    r"(?P<timestamp>\d{6})_"
    r"(?P<device_id>[-A-Za-z0-9/()\[\]{}]+)_"
    r"(?P<study>[A-Za-z0-9/-]+)"
    r"(?:_\{(?P<remarks>[^}]+)\})?"
    r"(?:_\[(?P<flags>[^\]]+)\])?"
    r"(?:_(?P<count>\d+))?"
    r"\.(?P<ext>\w+)$"
)

# Basic structure regex — extracts date_code, timestamp, body, and extension.
# The body (everything between the second _ and the last .) is then split
# and parsed right-to-left by _parse_body_parts().
_BASIC_STRUCTURE = re.compile(r"^(\d{6})-(\d{6})_(.+)\.(\w+)$")

# Patterns for right-to-left optional field matching
_RE_COUNT = re.compile(r"^\d+$")
_RE_TEXT = re.compile(r"^[A-Za-z-]+$")
_RE_FLAGS = re.compile(r"^\[[^\]]+\]$")       # [flags]
_RE_REMARKS = re.compile(r"^\{[^}]+\}$")      # {remarks}


# ── Public Constants ────────────────────────────────────────────────────


PATTERN_TEMPLATE = (
    "{date_code}-{timestamp}_{device_id}_{study}"
    "_{remarks?}[{flags?}]{count?}.{ext}"
)

PATTERN_DESCRIPTION = (
    "Universal naming convention: "
    "DDMMYY-HHMMSS_device-id_study_{remarks}_[flags]_count.ext"
)


# ── Public Functions ────────────────────────────────────────────────────


def parse_filename(filename: str) -> dict[str, Any] | None:
    """Parse a filename following the universal naming convention.

    Uses a right-to-left disambiguation strategy to correctly handle
    underscores inside the ``device_id`` field.

    Args:
        filename: Filename (with or without path) to parse. Only the
            base name is checked — directory components are ignored.

    Returns:
        Dictionary with keys ``date_code``, ``timestamp``, ``device_id``,
        ``study``, ``remarks``, ``flags``, ``count``, and ``ext``.
        Returns ``None`` if the filename does not match the universal
        pattern.

    Parsing strategy (right-to-left):

        1. Strip directory components.
        2. Extract ``date_code``, ``timestamp``, ``ext`` via regex.
        3. Split the middle body on ``_``.
        4. From the right:
           - If the last segment is all digits → ``count``.
           - If the next segment is ``[flags]`` → strip brackets.
           - If the next segment is ``{remarks}`` → strip brackets.
           - If no bracket-delimited fields found, fall back to
             legacy text-only heuristic (viable study check).
        5. The next segment is always ``study``.
        6. Everything left is ``device_id`` (joined with ``_``).

    Notes:
        - ``count`` is converted to ``int`` when present.
        - ``flags`` and ``remarks`` have their bracket delimiters
          stripped.
        - Legacy files without brackets (pre-v3.20) are handled via
          a backward-compatible fallback path.
    """
    name = _basename(filename)

    m = _BASIC_STRUCTURE.match(name)
    if not m:
        return None

    date_code, timestamp, body, ext = m.groups()
    parts = body.split("_")

    if len(parts) < 2:
        return None

    count: int | None = None
    flags: str | None = None
    remarks: str | None = None
    idx = len(parts) - 1

    # 1. Count (all digits, unambiguous from the right)
    if idx >= 0 and _RE_COUNT.match(parts[idx]):
        count = int(parts[idx])
        idx -= 1

    # 2. Flags from the right — bracket delimited [flags]
    if idx >= 0 and _RE_FLAGS.match(parts[idx]):
        flags = parts[idx][1:-1]  # strip brackets
        idx -= 1

    # 3. Remarks from the right — bracket delimited {remarks}
    if idx >= 0 and _RE_REMARKS.match(parts[idx]):
        remarks = parts[idx][1:-1]  # strip brackets
        idx -= 1

    # 4. Legacy fallback: if NO bracket-delimited fields were found,
    #    use the old text-only heuristic for backward compatibility
    #    with pre-v3.20 filenames (e.g. ``_initial-rerun_flagged_001``).
    if flags is None and remarks is None:
        text_fields: list[str] = []
        while idx >= 2 and _RE_TEXT.match(parts[idx]) and len(text_fields) < 2:
            if not _is_viable_study(parts[idx - 1]):
                break
            text_fields.append(parts[idx])
            idx -= 1

        if len(text_fields) >= 2:
            flags = text_fields[0]
            remarks = text_fields[1]
        elif len(text_fields) == 1:
            # Single text field → remarks (the more common standalone
            # modifier: "rerun", "initial", "cold-start").
            remarks = text_fields[0]

    # 5. Study (mandatory, last segment before optional fields)
    if idx < 0:
        return None
    study = parts[idx]
    idx -= 1

    # 6. Device_id (everything before study, may contain underscores)
    if idx < 0:
        return None
    device_id = "_".join(parts[: idx + 1])

    return {
        "date_code": date_code,
        "timestamp": timestamp,
        "device_id": device_id,
        "study": study,
        "remarks": remarks,
        "flags": flags,
        "count": count,
        "ext": ext,
    }


def build_filename(parts: dict) -> str:
    """Reconstruct a filename from parsed parts.

    Args:
        parts: Dict with keys from :func:`parse_filename` output:

            - ``date_code`` (str, required) — 6-digit date.
            - ``timestamp`` (str, required) — 6-digit time.
            - ``device_id`` (str, required) — device identifier.
            - ``study`` (str, required) — study name.
            - ``remarks`` (str, optional) — text modifier (wrapped in
              ``{...}``).
            - ``flags`` (str, optional) — text flag (wrapped in
              ``[...]``).
            - ``count`` (int | str, optional) — sequence number.
            - ``ext`` (str, required) — file extension (with or without
              leading dot).

    Returns:
        Reconstructed filename string following the universal grammar
        pattern ``DDMMYY-HHMMSS_device-id_study_{remarks}_[flags]_count.ext``.

    Grammar rules applied:

        - ``date_code`` and ``timestamp`` are joined with ``-``.
        - Fields are separated by ``_``.
        - ``remarks`` is wrapped in ``{...}``.
        - ``flags`` is wrapped in ``[...]``.
        - If only one optional text field is present, it appears in the
          ``remarks`` position (with curly braces).
        - ``count`` is zero-padded to 3 digits when provided as ``int``.
        - Text fields (``remarks``, ``flags``) are sanitised to only
          letters and hyphens; invalid characters become ``-``.
    """
    date_code = str(parts.get("date_code", ""))
    timestamp = str(parts.get("timestamp", ""))
    prefix = f"{date_code}-{timestamp}" if date_code and timestamp else ""

    device_id = str(parts.get("device_id", ""))
    study = str(parts.get("study", ""))

    body_parts: list[str] = []
    if prefix:
        body_parts.append(prefix)
    if device_id:
        body_parts.append(device_id)
    if study:
        body_parts.append(study)

    # Remarks — sanitise to letters + hyphens only, wrap in { }
    remarks = parts.get("remarks")
    if remarks:
        remarks_str = re.sub(r"[^a-zA-Z-]", "-", str(remarks)).strip("-")
        if remarks_str:
            body_parts.append(f"{{{remarks_str}}}")

    # Flags — sanitise to letters + hyphens only, wrap in [ ]
    flags = parts.get("flags")
    if flags:
        flags_str = re.sub(r"[^a-zA-Z-]", "-", str(flags)).strip("-")
        if flags_str:
            body_parts.append(f"[{flags_str}]")

    # Count — zero-pad to 3 digits when provided as int
    count = parts.get("count")
    if count is not None:
        try:
            body_parts.append(f"{int(count):03d}")
        except (ValueError, TypeError):
            body_parts.append(str(count))

    ext = str(parts.get("ext", "")).lstrip(".") if parts.get("ext") else ""

    filename = "_".join(body_parts)
    if ext:
        filename += f".{ext}"

    return filename


def filename_matches_convention(filename: str) -> bool:
    """Check whether a filename matches the universal naming convention.

    Uses a strict regex (no underscores in ``device_id``). Files with
    underscores in the device ID may return ``False`` even though
    :func:`parse_filename` can handle them.

    Args:
        filename: Filename (with or without path) to check.

    Returns:
        ``True`` if the filename matches the strict pattern, ``False``
        otherwise.
    """
    return _UNIVERSAL_PATTERN_STRICT.match(_basename(filename)) is not None


# ── Internal Helpers ────────────────────────────────────────────────────


def _is_viable_study(segment: str) -> bool:
    """Check if *segment* looks like a viable study name.

    A segment is a viable study if it is longer than 3 characters.
    This prevents short tokens (e.g. ``c4``, ``r3``, ``t1``) that are
    likely part of a device_id from being mistaken for a study name
    during right-to-left parsing.

    Args:
        segment: A body segment to check.

    Returns:
        ``True`` if the segment is a viable study candidate.
    """
    return len(segment) > 3


def _basename(filename: str) -> str:
    """Return the file name component of a path string.

    Handles both forward and backward slashes so the parsing
    functions work cross-platform and with bare filenames.

    Only strips a path separator if the text that follows looks
    like a ``DDMMYY-HHMMSS_`` prefix.  This prevents slashes that
    are part of the study name (e.g. ``pulse/endurance/v2``) from
    being mistaken for directory separators.
    """
    sep_idx = max(filename.rfind("/"), filename.rfind("\\"))
    if sep_idx == -1:
        return filename

    candidate = filename[sep_idx + 1 :]
    if re.match(r"\d{6}-\d{6}_", candidate):
        return candidate
    return filename
