"""Command input bar — accepts user commands with slash command support.

Provides a minimal Textual Input widget styled like Hermes:
- No border, height 1, transparent background
- Context shown in the header/status bar, not in the prompt
- Slash commands handled internally: /help, /clear, /history, /version
- Dispatches commands to the parent SciApp
"""

from textual.widgets import Input

#: Slash commands handled internally by the TUI (not dispatched to COMMAND_TREE).
SLASH_COMMANDS: dict[str, str] = {
    "/help": "Show available commands and slash command list",
    "/clear": "Clear the output panel",
    "/history": "Show recent command history",
    "/version": "Display sci version",
}


class CommandInput(Input):
    """A minimal Hermes-style input bar — just the typing line.

    No border, no context prefix in the prompt. Context is shown in the
    header and status bar above. The ``❯`` prefix is rendered as a
    separate Static widget in the parent app's compose.
    """

    DEFAULT_CSS: str = """
    CommandInput {
        height: 1;
        width: 100%;
        border: none;
        background: transparent;
        color: #cccccc;
        padding: 0;
        margin: 0;
    }
    CommandInput:focus {
        border: none;
    }
    CommandInput > .input--placeholder {
        color: #666666;
    }
    """

    def on_mount(self) -> None:
        """Set placeholder on mount."""
        self.placeholder = ""
        self.prompt = ""
