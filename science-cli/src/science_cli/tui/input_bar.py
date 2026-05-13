"""Command input bar — accepts user commands with slash command support.

Provides a Textual Input widget that:
- Shows the current session context as the prompt
- Handles slash commands internally: /help, /clear, /history, /version
- Dispatches non-slash commands to COMMAND_TREE handlers
- Captures command output and sends it to the OutputPanel
- Persists session history to session.json
"""

from textual.app import ComposeResult
from textual.widgets import Input
from textual.reactive import reactive
from textual import events

from science_cli.core.session import load_session, add_history
from science_cli.tui.theme import MATCHA_COLORS


#: Slash commands handled internally by the TUI (not dispatched to COMMAND_TREE).
SLASH_COMMANDS: dict[str, str] = {
    "/help": "Show available commands and slash command list",
    "/clear": "Clear the output panel",
    "/history": "Show recent command history",
    "/version": "Display sci version",
}


class CommandInput(Input):
    """A command input widget with context-aware prompt and slash command support.

    The prompt displays the current project/protocol context, e.g.:
    ``(sci my-project/my-protocol) > ``

    Slash commands (starting with ``/``) are handled internally rather than
    dispatched to COMMAND_TREE. Regular commands are dispatched to the
    parent SciApp for execution.

    Attributes:
        context_project: Current project name (from session).
        context_protocol: Current protocol name (from session).
    """

    context_project: reactive[str] = reactive("")
    context_protocol: reactive[str] = reactive("")

    DEFAULT_CSS: str = """
    CommandInput {
        height: 3;
        width: 100%;
        border: solid $border;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    CommandInput:focus {
        border: solid $accent;
    }
    CommandInput > .input--placeholder {
        color: $dim;
    }
    """

    def on_mount(self) -> None:
        """Load session context and set the prompt on mount."""
        sess = load_session()
        self.context_project = sess.get("last_project", "")
        self.context_protocol = sess.get("last_protocol", "")
        self._update_prompt()
        self.placeholder = "Type a command or /help for slash commands..."

    def _update_prompt(self) -> None:
        """Rebuild the prompt string from current context."""
        proj = self.context_project
        proto = self.context_protocol

        if proj and proto:
            self.prompt = f"(sci {proj}/{proto}) > "
        elif proj:
            self.prompt = f"(sci {proj}) > "
        elif proto:
            self.prompt = f"(sci */{proto}) > "
        else:
            self.prompt = "(sci) > "

    def watch_context_project(self, value: str) -> None:
        """Update prompt when project context changes."""
        self._update_prompt()

    def watch_context_protocol(self, value: str) -> None:
        """Update prompt when protocol context changes."""
        self._update_prompt()

    def update_context(self, project: str = "", protocol: str = "") -> None:
        """Update the command prompt context.

        Args:
            project: New project name, or empty to leave unchanged.
            protocol: New protocol name, or empty to leave unchanged.
        """
        if project:
            self.context_project = project
        if protocol:
            self.context_protocol = protocol
