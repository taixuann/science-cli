"""Plot engine — base class and utilities."""

from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from science_cli.theme import apply_theme, theme_to_rcparams


def setup_backend(interactive: bool = False):
    if not interactive:
        matplotlib.use("Agg")


def create_figure(theme: str = "publication-acs", figsize: tuple | None = None) -> tuple:
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
    return (6.4, 4.8)


def save_figure(fig, output_dir: Path, stem: str, flags: dict) -> Path:
    ext = flags.get("n") or flags.get("name", f"{stem}.png")
    if not ext.startswith("."):
        ext = ext if ext.startswith(".") else "." + ext.split(".")[-1] if "." in ext else ".png"
    else:
        pass
    name = flags.get("n") or flags.get("name", f"{stem}{ext}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output_dir / name

    dpi = int(flags.get("dpi", 300))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    return save_path
