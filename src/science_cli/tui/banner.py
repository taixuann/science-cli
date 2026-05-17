"""ASCII SCI banner widget — displayed at the top of the TUI."""

from textual.app import ComposeResult
from textual.widgets import Static

from science_cli import __version__

#: ASCII art for the SCI banner — block-letter "SCI" in the matcha accent color.
SCI_ART: str = """\
███████╗ ██████╗ ██╗
██╔════╝██╔════╝ ██║
███████╗██║      ██║
╚════██║██║      ██║
███████║╚██████╗ ██║
╚══════╝ ╚═════╝ ╚═╝"""


class SCIBanner(Static):
    """Single-column banner showing SCI ASCII art."""

    DEFAULT_CSS: str = """
    SCIBanner {
        height: 8;
        width: 100%;
        padding: 1 0;
    }
    #banner-art {
        color: #55dd77;
        text-style: bold;
        width: auto;
    }
    #banner-version {
        color: #666666;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(SCI_ART, id="banner-art")
        yield Static(f"science-cli v{__version__}", id="banner-version")
