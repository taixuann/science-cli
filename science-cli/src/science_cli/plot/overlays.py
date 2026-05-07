"""Overlay plotting for multi-file comparisons."""

import numpy as np

from science_cli.plot.base import (
    create_figure, save_figure, apply_figure_kw,
    parse_figsize, plot_line,
)
from science_cli.theme import get_theme


def plot_overlay(
    curves: list[dict],
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    fig, ax = create_figure(flags.get("theme", "publication-acs"), figsize)

    theme = get_theme(flags.get("theme", "publication-acs"))
    colors = theme.get("colors", {}).get("prop_cycle", [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    ])

    for i, c in enumerate(curves):
        color = colors[i % len(colors)]
        cf = dict(flags)
        cf.setdefault("color", color)
        label = c.get("label", f"Curve {i+1}")
        plot_line(c["x"], c["y"], ax=ax, flags=cf, label=label)

    ax.legend()
    apply_figure_kw(ax, flags)
    return fig, ax
