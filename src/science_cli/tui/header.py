"""Two-column header widget — context and workflow display.

Shows the current session context on the left (project and protocol)
and the workflow steps on the right, styled in the matcha green theme.
Updates dynamically when the session context changes.
"""

from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from science_cli.core.session import load_session


class TuiHeader(Static):
    """A two-column header widget showing context and workflow.

    Left column: current context — ``(sci project/protocol) v2.0.0``
    Right column: workflow steps — ``1.project 2.protocol 3.data 4.plot``

    The header reads session state on mount and updates reactively
    when the parent app signals a context change via `context_project`
    and `context_protocol` reactive attributes.

    Attributes:
        context_project: The currently active project name (empty string if none).
        context_protocol: The currently active protocol name (empty string if none).
    """

    context_project: reactive[str] = reactive("")
    context_protocol: reactive[str] = reactive("")

    DEFAULT_CSS: str = """
    TuiHeader {
        height: 1;
        width: 100%;
        padding: 0 1;
    }
    TuiHeader Horizontal {
        height: 1;
    }
    TuiHeader .header-left {
        width: 1fr;
        content-align: left middle;
        color: #cccccc;
        text-style: bold;
    }
    TuiHeader .header-right {
        width: auto;
        content-align: right middle;
        color: #888888;
        text-style: italic;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the two-column header layout."""
        yield Horizontal(
            Static("", id="header-left", classes="header-left"),
            Static("", id="header-right", classes="header-right"),
        )

    def on_mount(self) -> None:
        """Load session state and populate the header on mount."""
        sess = load_session()
        self.context_project = sess.get("last_project", "")
        self.context_protocol = sess.get("last_protocol", "")
        self.refresh_header()

    def watch_context_project(self, value: str) -> None:
        """React to project context changes."""
        self.refresh_header()

    def watch_context_protocol(self, value: str) -> None:
        """React to protocol context changes."""
        self.refresh_header()

    def refresh_header(self) -> None:
        """Update the header display with current context and workflow."""
        proj = self.context_project
        proto = self.context_protocol

        if proj and proto:
            context = f"(sci {proj}/{proto})"
        elif proj:
            context = f"(sci {proj})"
        elif proto:
            context = f"(sci */{proto})"
        else:
            context = "(sci)"

        # Build multi-color Rich Text for left column
        # (sci project/protocol) with amber project and cyan protocol
        if proj and proto:
            left_text = RichText()
            left_text.append("(sci ", "bold")       # default text color
            left_text.append(proj, "bold #d4a853")  # amber project
            left_text.append("/", "dim")
            left_text.append(proto, "bold #5ea8b5")  # cyan protocol
            left_text.append(")", "dim")
        elif proj:
            left_text = RichText()
            left_text.append("(sci ", "bold")
            left_text.append(proj, "bold #d4a853")
            left_text.append(")", "dim")
        elif proto:
            left_text = RichText()
            left_text.append("(sci */", "bold")
            left_text.append(proto, "bold #5ea8b5")
            left_text.append(")", "dim")
        else:
            left_text = RichText("(sci)", "dim")

        left = self.query_one("#header-left", Static)
        right = self.query_one("#header-right", Static)

        if left and right:
            left.update(left_text)
            right.update("")

    def set_context(self, project: str = "", protocol: str = "") -> None:
        """Update the header context programmatically.

        Called by the parent app when a command changes the session state
        (e.g., `open -m project <name>` or `open <protocol>`).

        Args:
            project: The new project name, or empty string to keep current.
            protocol: The new protocol name, or empty string to keep current.
        """
        if project:
            self.context_project = project
        if protocol:
            self.context_protocol = protocol
