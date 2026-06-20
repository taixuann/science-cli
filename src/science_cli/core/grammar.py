"""Universal filename parsing convention for science-cli.

All new data files follow a single canonical naming convention
instead of per-instrument regex patterns. This module defines
the convention and provides parsing utilities.

Universal pattern::

    DDMMYY-HHMMSS_device-id_study_remarks_flags_count.ext

Example::

    200626-122036_cu-c-pda(q5)-ito(2)_r3-c4_pulse-endurance_initial-rerun_flagged_001.csv

Field reference (in order from left to right):

    ============ ============================= ========== ============================
    Field        Example                       Mandatory  Type
    ============ ============================= ========== ============================
    date_code    200626                        Yes        str (6 digits)
    timestamp    122036                        Yes        str (6 digits)
    device_id    cu-c-pda(q5)-ito(2)_r3-c4     Yes        str (any chars; may contain
                                                           underscores)
    study        pulse-endurance               Yes        str (alphanumeric, hyphens,
                                                           slashes; no underscores)
    remarks      initial-rerun                 No         str | None (letters,
                                                           hyphens; no digits)
    flags        flagged                       No         str | None (letters,
                                                           hyphens; no digits)
    count        001                           No         int | None (digits only)
    ext          csv                           Yes        str (file extension)
    ============ ============================= ========== ============================

Parsing strategy (right-to-left disambiguation):

    1. Strip directory components, leaving the bare filename.
    2. Extract ``date_code``, ``timestamp``, and ``ext`` via regex on
       the fixed-width prefix and trailing extension.
    3. Split the remaining body on ``_`` into segments.
    4. From the right:
       - If the last segment is all digits → ``count`` (unambiguous).
       - Collect up to 2 text-only segments (letters + hyphens) as
         optional fields.  A text segment is only collected if the
         segment immediately to its left is a **viable study name**
         (longer than 3 characters).  This prevents short device-id
         tokens (e.g. ``c4``) from being mistaken for a study.
       - The rightmost collected text → ``flags``.
       - The leftmost collected text → ``remarks``.
       - A single collected text is always ``remarks``.
    5. The next segment to the left is the mandatory ``study``.
    6. Everything further left becomes ``device_id``
       (joined with ``_``).

Notes:

    - ``device_id`` CAN contain underscores — the right-to-left
      disambiguation handles this correctly.
    - A single optional text field is always assigned to ``remarks``
      (not ``flags``) because ``remarks`` is the more common standalone
      modifier (e.g. ``rerun``, ``initial``, ``cold-start``).
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
    r"(?:_(?P<remarks>[A-Za-z-]+))?"
    r"(?:_(?P<flags>[A-Za-z-]+))?"
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


# ── Public Constants ────────────────────────────────────────────────────


PATTERN_TEMPLATE = (
    "{date_code}-{timestamp}_{device_id}_{study}"
    "_{remarks?}{flags?}{count?}.{ext}"
)

PATTERN_DESCRIPTION = (
    "Universal naming convention: "
    "DDMMYY-HHMMSS_device-id_study_remarks_flags_count.ext"
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
           - Collect up to 2 text-only segments, but only if the
             candidate study to the left would be **viable** (longer
             than 3 characters).  The rightmost collected text →
             ``flags``, the leftmost → ``remarks``.
        5. The next segment is always ``study``.
        6. Everything left is ``device_id`` (joined with ``_``).

    Notes:
        - ``count`` is converted to ``int`` when present.
        - A single optional text field is assigned to ``remarks``,
          not ``flags``.
        - ``flags`` only receives a value when both ``remarks`` and
          ``flags`` text fields precede the count.
    """
    name = _basename(filename)

    m = _BASIC_STRUCTURE.match(name)
    if not m:
        return None

    date_code, timestamp, body, ext = m.groups()
    parts = body.split("_")

    if len(parts) < 2:
        return None

    count = None
    flags = None
    remarks = None
    idx = len(parts) - 1

    # 1. Count (all digits, unambiguous from the right)
    if idx >= 0 and _RE_COUNT.match(parts[idx]):
        count = int(parts[idx])
        idx -= 1

    # 2. Collect up to 2 text fields from the right.
    #    Guard: at least 2 items must remain (device_id + study).
    #    Additional guard: the resulting study candidate must be
    #    longer than 3 characters (to avoid mistaking short device-id
    #    tokens like "c4" for the study name).
    text_fields: list[str] = []
    while idx >= 2 and _RE_TEXT.match(parts[idx]) and len(text_fields) < 2:
        if not _is_viable_study(parts[idx - 1]):
            break
        text_fields.append(parts[idx])
        idx -= 1

    # text_fields[0] is rightmost (closest to count = flags)
    # text_fields[1] is leftmost  (farthest from count = remarks)
    if len(text_fields) >= 2:
        flags = text_fields[0]
        remarks = text_fields[1]
    elif len(text_fields) == 1:
        # A single text field is always remarks (the more common
        # standalone modifier: "rerun", "initial", "cold-start").
        remarks = text_fields[0]

    # 3. Study (mandatory, last segment before optional fields)
    if idx < 0:
        return None
    study = parts[idx]
    idx -= 1

    # 4. Device_id (everything before study, may contain underscores)
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
