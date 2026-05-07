"""Theme system — composite colors, presets for Rich and matplotlib."""

from science_cli.theme.registry import (
    list_themes,
    get_theme,
    apply_theme,
    theme_to_rcparams,
    template_to_flags,
)

RICH_STYLES = {
    "accent": "green",
    "dim": "bright_black",
    "error": "red",
    "warning": "yellow",
    "info": "cyan",
}

RAW_COLORS = {
    "accent": "green",
    "dim": "bright_black",
    "error": "red",
    "warning": "yellow",
    "info": "cyan",
}
