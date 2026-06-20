"""fzf subpackage — column registry, display builder, and selection helpers.

fzf_columns.py -> core/fzf/columns.py
fzf_utils.py   -> core/fzf/display.py

Public API re-exports (for backwards compat):
"""
from science_cli.core.fzf.columns import (
    STUDY_COLUMN_REGISTRY,
    GLOBAL_COLUMNS,
    status_badge_for_file,
    get_step_columns,
    get_global_columns,
)
from science_cli.core.fzf.display import (
    build_fzf_display,
    fzf_select,
)

__all__ = [
    "STUDY_COLUMN_REGISTRY",
    "GLOBAL_COLUMNS",
    "status_badge_for_file",
    "get_step_columns",
    "get_global_columns",
    "build_fzf_display",
    "fzf_select",
]
