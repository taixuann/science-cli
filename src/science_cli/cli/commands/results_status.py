"""Status tag system for result files.

Manages per-file status tags (keep, highlight, discard, star) stored in
project/results/.status.json. Migrates from legacy .stars.json on first access.
"""

from __future__ import annotations

import json
from pathlib import Path

# Allowed status tags for result files
STATUS_TAGS = ["keep", "highlight", "discard", "star"]

# Badge display strings for fzf (plain text, no Rich markup)
STATUS_BADGES: dict[str, str] = {
    "keep": "[KEEP]",
    "highlight": "[HIGHLIGHT]",
    "discard": "[DISCARD]",
    "star": "⭐",
}


def status_path(proj: Path) -> Path:
    """Return path to the status state file for a project."""
    return proj / "results" / ".status.json"


def stars_path(proj: Path) -> Path:
    """Return path to legacy star state file for a project."""
    return proj / "results" / ".stars.json"


def load_status(proj: Path) -> dict[str, str]:
    """Load the status dict (rel_key → tag) for a project.

    Migrates .stars.json → .status.json on first access if needed.
    """
    sp = status_path(proj)
    if sp.exists():
        try:
            data = json.loads(sp.read_text())
            # Normalize: ensure all values are strings (legacy bool migration)
            return {k: str(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError):
            return {}

    # Migrate from .stars.json if it exists
    legacy = stars_path(proj)
    if legacy.exists():
        try:
            legacy_data = json.loads(legacy.read_text())
            migrated: dict[str, str] = {}
            for k, v in legacy_data.items():
                if v is True:
                    migrated[k] = "star"
                # v is False → no status, skip
            if migrated:
                save_status(proj, migrated)
            return migrated
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_status(proj: Path, status: dict[str, str]) -> None:
    """Persist the status dict to project/results/.status.json."""
    sp = status_path(proj)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(status, indent=2))


def badge_for_file(tag: str, pf_name: str) -> str:
    """Build fzf display line with status badge prefix."""
    badge = STATUS_BADGES.get(tag, "")
    if badge:
        return f"{badge} {pf_name}"
    return pf_name
