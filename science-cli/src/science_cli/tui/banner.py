"""ASCII SCI banner widget — displayed at the top of the TUI."""

from textual.app import ComposeResult
from textual.widgets import Static

from science_cli import __version__

#: ASCII art for the SCI banner — large block-letter "SCI" in the matcha accent color.
SCI_ART: str = """\
███╗   ███╗ ██╗   ██╗ ███████╗  ██████╗ ██╗
████╗ ████║ ╚██╗ ██╔╝ ██╔════╝ ██╔════╝ ██║
██╔████╔██║  ╚████╔╝  ███████╗ ██║      ██║
██║╚██╔╝██║   ╚██╔╝   ╚════██║ ██║      ██║
██║ ╚═╝ ██║    ██║    ███████║ ╚██████╗ ██║
╚═╝     ╚═╝    ╚═╝    ╚══════╝  ╚═════╝ ╚═╝"""


class SCIBanner(Static):
    """A static widget displaying the ASCII SCI banner with version number.

    Renders the block-letter "SCI" art with no border,
    using the bright green accent color for the text.
    The version number is dynamically filled from `science_cli.__version__`.

    Usage:
        yield SCIBanner()
    """

    DEFAULT_CSS: str = """
    SCIBanner {
        height: auto;
        width: 100%;
        padding: 1 0;
        text-style: bold;
        color: #55dd77;
    }
    """

    def compose(self) -> ComposeResult:
        """Render the banner with the current version string."""
        art = SCI_ART.format(version=__version__)
        yield Static(art)
