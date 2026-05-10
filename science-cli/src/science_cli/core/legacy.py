"""Legacy placeholder functions — migrated from functions/ directory.

These are placeholder/stub implementations for commands that reference
them. They should be replaced with real implementations as features mature.
"""

from pathlib import Path


def create_protocol_from_setids(proj):
    """Placeholder: creates protocol from set IDs. Implement as needed."""
    return {"name": "unnamed", "steps": []}


def parse_filename(name):
    """Placeholder: parse a filename into components."""
    return {"filename": name, "base": Path(name).stem, "ext": Path(name).suffix}


def filename_parser_wizard():
    """Placeholder: interactive filename parsing wizard."""
    return {}


def lookup_metadata(proj, key):
    """Placeholder: look up metadata for a file in a project."""
    return {}


def undo_metadata(filepath):
    """Placeholder: undo metadata assignment."""
    pass


def batch_assign_wizard(proj):
    """Placeholder: interactive batch file assignment wizard."""
    pass
