"""CA-specific plotting: chronoamperometry decay curves."""

import numpy as np

from science_cli.plot.base import (
    create_figure, save_figure, apply_figure_kw,
    parse_figsize, plot_line,
)


def plot_ca_decay(
    time: np.ndarray,
    current: np.ndarray,
    flags: dict | None = None,
    label: str = "",
    ax=None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    if ax is None:
        fig, ax = create_figure(flags.get("theme", "publication-acs"), figsize)
    else:
        fig = ax.figure

    plot_line(time, current, ax=ax, flags=flags, label=label)

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Time (s)")
    if not flags.get("ylabel"):
        ax.set_ylabel("Current (A)")
    if not flags.get("xscale"):
        ax.set_xscale("linear")

    return fig, ax


def plot_ca_cottrell(
    time: np.ndarray,
    current: np.ndarray,
    fit_x: np.ndarray | None = None,
    fit_y: np.ndarray | None = None,
    flags: dict | None = None,
    label: str = "",
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    fig, ax = create_figure(flags.get("theme", "default"), figsize)

    t_inv_sqrt = 1.0 / np.sqrt(time[time > 0])
    i_valid = current[time > 0]
    ax.scatter(t_inv_sqrt, i_valid, s=8, alpha=0.6, label="Data")

    if fit_x is not None and fit_y is not None:
        ax.plot(fit_x, fit_y, "r-", linewidth=1.5, label="Cottrell fit")

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("t^{-1/2} (s^{-1/2})")
    if not flags.get("ylabel"):
        ax.set_ylabel("Current (A)")
    ax.legend()

    return fig, ax
