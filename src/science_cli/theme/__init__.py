"""Theme system — composite colors, presets for Rich and matplotlib."""

from science_cli.theme.registry import (
    apply_theme,
    get_theme,
    list_themes,
    template_to_flags,
    theme_to_rcparams,
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
