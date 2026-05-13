"""Matcha green color scheme for the TUI.

Colors inspired by matcha tea — muted greens on a dark earth-tone background.
Used by Textual CSS and widget styling throughout the TUI.
"""

#: Primary color palette for the matcha green theme.
MATCHA_COLORS: dict[str, str] = {
    "background": "#1a1f1a",       # Very dark green-black — main screen background
    "surface": "#1e241e",           # Slightly lighter background — panels, inputs
    "accent": "#8BAA89",            # Muted sage green — highlights, active elements
    "accent_bright": "#a3c2a1",    # Brighter accent — hover states
    "border": "#4A7A4A",           # Medium green — borders, dividers
    "border_dim": "#3a5a3a",       # Dimmer border — inactive borders
    "text": "#e0e8e0",             # Off-white with green tint — primary text
    "text_dim": "#8a9a8a",         # Muted text — secondary info
    "dim": "#6a7a6a",              # Dim green-gray — tertiary text, placeholders
    "success": "#7aba7a",          # Soft green — success messages
    "error": "#d47a7a",            # Muted red — errors (green-adjacent, not jarring)
    "warning": "#c4a86a",          # Muted gold — warnings
    "info": "#6aaa9a",             # Teal-green — info messages
}

#: Textual CSS variable definitions using the matcha color palette.
CSS_VARIABLES: str = """
$background: #1a1f1a;
$surface: #1e241e;
$accent: #8BAA89;
$accent-bright: #a3c2a1;
$border: #4A7A4A;
$border-dim: #3a5a3a;
$text: #e0e8e0;
$text-dim: #8a9a8a;
$dim: #6a7a6a;
$success: #7aba7a;
$error: #d47a7a;
$warning: #c4a86a;
$info: #6aaa9a;
"""

#: Rich-compatible style mapping for use with Rich renderables.
RICH_STYLES: dict[str, str] = {
    "accent": "bold #8BAA89",
    "dim": "#6a7a6a",
    "error": "#d47a7a",
    "warning": "#c4a86a",
    "info": "#6aaa9a",
    "success": "#7aba7a",
    "border": "#4A7A4A",
    "text": "#e0e8e0",
}
