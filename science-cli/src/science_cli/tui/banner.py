"""ASCII SCI banner widget — displayed at the top of the TUI."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container

from science_cli import __version__
from science_cli.tui.theme import MATCHA_COLORS

#: ASCII art for the SCI banner — large block-letter "SCI" in the matcha accent color.
SCI_ART: str = """\
╔══════════════════════════════════════════╗
║   ███████╗███████╗███████╗              ║
║   ██╔════╝██╔════╝██╔════╝              ║
║   ███████╗█████╗  ███████╗              ║
║   ╚════██║██╔══╝  ╚════██║              ║
║   ███████║███████╗███████║              ║
║   ╚══════╝╚══════╝╚══════╝              ║
║   Scientific Data Analysis CLI v{version:<6} ║
╚══════════════════════════════════════════╝"""

class SCIBanner(Static):
    """A static widget displaying the ASCII SCI banner with version number.

    Renders the block-letter "SCI" art with a decorative border,
    using the matcha green accent color for the text and border.
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
        color: $accent;
    }
    """

    def compose(self) -> ComposeResult:
        """Render the banner with the current version string."""
        art = SCI_ART.format(version=__version__)
        yield Static(art)
