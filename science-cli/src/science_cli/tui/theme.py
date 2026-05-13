"""Matcha green color scheme for the TUI.

Colors inspired by matcha tea — muted greens on a dark earth-tone background.
Used by Textual CSS and widget styling throughout the TUI.
"""

#: Primary color palette for the matcha green theme.
MATCHA_COLORS: dict[str, str] = {
    "background": "#0d0d0d",       # Dark, not visible anyway (transparent)
    "surface": "#0d0d0d",
    "accent": "#55ee77",            # Bright vibrant green (was #8BAA89 muted sage)
    "accent_bright": "#77ff99",     # Even brighter (was #a3c2a1)
    "border": "#55AA55",            # Vibrant medium green (was #4A7A4A dark green)
    "border_dim": "#3a7a3a",        # (was #3a5a3a)
    "text": "#cccccc",
    "text_dim": "#888888",
    "dim": "#666666",
    "success": "#55ee77",
    "error": "#d47a7a",
    "warning": "#c4a86a",
    "info": "#5ea8b5",              # Soft cyan for protocol names
    "project": "#d4a853",           # Amber/gold for project names (NEW)
}

#: Textual CSS variable definitions using the matcha color palette.
CSS_VARIABLES: str = """
$background: #0d0d0d;
$surface: #0d0d0d;
$accent: #55ee77;
$accent-bright: #77ff99;
$border: #55AA55;
$border-dim: #3a7a3a;
$text: #cccccc;
$text-dim: #888888;
$dim: #666666;
$success: #55ee77;
$error: #d47a7a;
$warning: #c4a86a;
$info: #5ea8b5;
$project: #d4a853;
"""

#: Rich-compatible style mapping for use with Rich renderables.
RICH_STYLES: dict[str, str] = {
    "accent": "bold #55ee77",
    "dim": "#666666",
    "error": "#d47a7a",
    "warning": "#c4a86a",
    "info": "#5ea8b5",
    "success": "#55ee77",
    "border": "#55AA55",
    "text": "#cccccc",
    "project": "#d4a853",
}
