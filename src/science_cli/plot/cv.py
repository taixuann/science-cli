"""CV-specific plotting functions."""

import numpy as np

from science_cli.plot.base import (
    apply_figure_kw,
    create_figure,
    parse_figsize,
    plot_line,
)


def plot_cv_curve(
    potential: np.ndarray,
    current: np.ndarray,
    flags: dict | None = None,
    label: str = "",
    ax=None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    if ax is None:
        fig, ax = create_figure(flags.get("theme", "publication-nature"), figsize)
    else:
        fig = ax.figure

    plot_line(potential, current, ax=ax, flags=flags, label=label)

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Potential (V)")
    if not flags.get("ylabel"):
        ax.set_ylabel("Current (A)")

    return fig, ax


def plot_cv_overlay(
    curves: list[dict],
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    fig, ax = create_figure(flags.get("theme", "default"), figsize)

    for i, c in enumerate(curves):
        label = c.get("label", f"Curve {i+1}")
        plot_line(c["x"], c["y"], ax=ax, flags=flags, label=label)

    ax.legend()
    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Potential (V)")
    if not flags.get("ylabel"):
        ax.set_ylabel("Current (A)")

    return fig, ax


def plot_cv_with_peaks(
    potential: np.ndarray,
    current: np.ndarray,
    peaks: dict | None = None,
    flags: dict | None = None,
    label: str = "",
):
    flags = flags or {}
    fig, ax = plot_cv_curve(potential, current, flags, label)

    if peaks:
        anodic = peaks.get("anodic_peaks", [])
        cathodic = peaks.get("cathodic_peaks", [])
        for pk in anodic:
            ep = pk.get("potential", 0)
            ip = pk.get("current", 0)
            ax.plot(ep, ip, "v", color="red", markersize=8)
        for pk in cathodic:
            ep = pk.get("potential", 0)
            ip = pk.get("current", 0)
            ax.plot(ep, ip, "^", color="blue", markersize=8)

    return fig, ax
