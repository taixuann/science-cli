"""ASCII SCI banner widget with techniques box — displayed at the top of the TUI."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Horizontal

from science_cli import __version__
from science_cli.core.config import get_merged_config

#: ASCII art for the SCI banner — block-letter "SCI" in the matcha accent color.
SCI_ART: str = """\
███████╗ ██████╗ ██╗
██╔════╝██╔════╝ ██║
███████╗██║      ██║
╚════██║██║      ██║
███████║╚██████╗ ██║
╚══════╝ ╚═════╝ ╚═╝"""


def _get_active_techniques() -> list[tuple[str, str]]:
    """Return sorted (technique, device) pairs from merged config defaults."""
    config = get_merged_config()
    defaults = config.get("defaults", {})
    items = [(t, d) for t, d in sorted(defaults.items()) if d]
    if not items:
        items.append(("iv-sweep", "keithley-2400"))
    return items


class SCIBanner(Static):
    """A two-column banner: ASCII SCI art on the left, active techniques box on the right."""

    DEFAULT_CSS: str = """
    SCIBanner {
        height: auto;
        width: 100%;
        padding: 1 0;
    }
    #banner-art {
        color: #55dd77;
        text-style: bold;
        width: auto;
    }
    #techniques-box {
        color: #aaaaaa;
        width: auto;
        padding: 0 0 0 3;
    }
    """

    def compose(self) -> ComposeResult:
        tech_lines = []
        for tech, device in _get_active_techniques():
            tech_lines.append(f"  [bold #5ea8b5]{tech:<18}[/] {device}")
        tech_str = "\n".join(tech_lines)
        yield Horizontal(
            Static(SCI_ART, id="banner-art"),
            Static(
                "[bold #55ee77]Active Techniques[/]\n"
                "[dim]\u2500" * 30 + "[/]\n"
                f"{tech_str}",
                id="techniques-box",
            ),
        )
