"""Base plot utilities and generic plotting."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

from science_cli.theme import apply_theme


def setup_backend(interactive: bool = False):
    if not interactive:
        matplotlib.use("Agg")


def create_figure(theme: str = "publication-nature", figsize: tuple | None = None) -> tuple:
    apply_theme(theme)
    fig, ax = plt.subplots(figsize=figsize)
    return fig, ax


def apply_figure_kw(ax, flags: dict, title_default: str = ""):
    if flags.get("title"):
        ax.set_title(flags["title"])
    if flags.get("xlabel"):
        ax.set_xlabel(flags["xlabel"])
    if flags.get("ylabel"):
        ax.set_ylabel(flags["ylabel"])
    if flags.get("xlim"):
        try:
            parts = str(flags["xlim"]).split(",")
            ax.set_xlim(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            pass
    if flags.get("ylim"):
        try:
            parts = str(flags["ylim"]).split(",")
            ax.set_ylim(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            pass
    if flags.get("xscale"):
        ax.set_xscale(flags["xscale"])
    if flags.get("yscale"):
        ax.set_yscale(flags["yscale"])
    if flags.get("grid"):
        ax.grid(True, alpha=0.3)
    if flags.get("legend"):
        ax.legend()


def parse_figsize(flags: dict) -> tuple:
    size = flags.get("size", "")
    if size:
        try:
            parts = str(size).split(",")
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return None


def save_figure(fig, output_dir: Path, stem: str, flags: dict) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    name = flags.get("n") or flags.get("name") or f"{stem}.png"
    save_path = output_dir / name
    dpi = int(flags.get("dpi", 300))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    return save_path


def plot_line(
    x, y,
    ax=None,
    flags: dict | None = None,
    label: str = "",
) -> tuple:
    flags = flags or {}
    if ax is None:
        _, ax = create_figure(flags.get("theme", "publication-nature"))

    color = flags.get("color")
    lw = float(flags.get("linewidth", 1.5))
    ls = flags.get("linestyle", "-")
    marker = flags.get("marker")
    ms = float(flags.get("markersize", 6))

    kw = {"linewidth": lw, "linestyle": ls}
    if color:
        kw["color"] = color
    if marker:
        kw["marker"] = marker
        kw["markersize"] = ms
    if label:
        kw["label"] = label

    ax.plot(x, y, **kw)
    return ax


def plot_scatter(
    x, y,
    ax=None,
    flags: dict | None = None,
    label: str = "",
) -> tuple:
    flags = flags or {}
    if ax is None:
        _, ax = create_figure(flags.get("theme", "default"))

    color = flags.get("color")
    s = float(flags.get("markersize", 36))
    marker = flags.get("marker", "o")
    cmap = flags.get("cmap")

    kw = {"s": s, "marker": marker, "alpha": 0.8}
    if color:
        kw["c"] = color
    if cmap:
        kw["cmap"] = cmap
    if label:
        kw["label"] = label

    ax.scatter(x, y, **kw)
    return ax
