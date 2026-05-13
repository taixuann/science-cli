"""Textual TUI — interactive terminal interface for science-cli.

Provides the `SCIApp` Textual application and supporting widgets for
the matcha-green themed TUI with SCI banner, two-column header,
scrollable output panel, and command input bar with slash commands.

Usage:
    Bare `sci` (no args) launches the TUI.
    `sci --repl` still uses the legacy prompt_toolkit REPL.
"""

from science_cli.tui.app import SCIApp

__all__ = ["SCIApp"]
