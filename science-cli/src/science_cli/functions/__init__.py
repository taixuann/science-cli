"""Compatibility shims — redirect old imports to new core locations."""

from science_cli.core.session import *  # noqa: F401, F403
from science_cli.core.technique import *  # noqa: F401, F403
from science_cli.core.fzf_utils import *  # noqa: F401, F403
from science_cli.core.manifest import *  # noqa: F401, F403
from science_cli.core.file_utils import *  # noqa: F401, F403


def create_protocol_from_setids(proj):
    """Placeholder: creates protocol from set IDs. Implement as needed."""
    return {"name": "unnamed", "steps": []}


def parse_filename(name):
    return {"filename": name, "base": Path(name).stem, "ext": Path(name).suffix}


def filename_parser_wizard():
    return {}


def lookup_metadata(key):
    return {}


def undo_metadata(filepath):
    pass


def batch_assign_wizard():
    pass


from pathlib import Path
