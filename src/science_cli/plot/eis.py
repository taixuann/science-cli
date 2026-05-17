"""EIS-specific plotting: Nyquist, Bode."""

import numpy as np

from science_cli.plot.base import (
    create_figure, save_figure, apply_figure_kw,
    parse_figsize, plot_line,
)


def plot_eis_nyquist(
    z_real: np.ndarray,
    z_imag: np.ndarray,
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

    plot_line(z_real, -z_imag, ax=ax, flags=flags, label=label)

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Z' (Ω)")
    if not flags.get("ylabel"):
        ax.set_ylabel("-Z'' (Ω)")
    ax.set_aspect("equal")

    return fig, ax


def plot_eis_bode(
    frequency: np.ndarray,
    magnitude: np.ndarray,
    phase: np.ndarray | None = None,
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)

    if phase is not None:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    else:
        fig, ax1 = plt.subplots(figsize=figsize)

    apply_theme(flags.get("theme", "default"))
    plot_line(frequency, magnitude, ax=ax1, flags=flags, label="|Z|")
    ax1.set_ylabel("|Z| (Ω)")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.grid(True, alpha=0.3)

    if phase is not None:
        plot_line(frequency, phase, ax=ax2, flags=flags, label="Phase")
        ax2.set_xlabel("Frequency (Hz)")
        ax2.set_ylabel("Phase (°)")
        ax2.set_xscale("log")
        ax2.grid(True, alpha=0.3)

    return fig, (ax1, ax2) if phase is not None else ax1


def plot_eis_fit(
    z_real: np.ndarray,
    z_imag: np.ndarray,
    fit_real: np.ndarray,
    fit_imag: np.ndarray,
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    fig, ax = create_figure(flags.get("theme", "default"), figsize)

    plot_line(z_real, -z_imag, ax=ax, flags=flags, label="Data")
    fit_flags = dict(flags)
    fit_flags["linestyle"] = "--"
    fit_flags["color"] = "red"
    fit_flags.pop("marker", None)
    plot_line(fit_real, -fit_imag, ax=ax, flags=fit_flags, label="Fit")

    ax.set_xlabel("Z' (Ω)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_aspect("equal")
    ax.legend()
    apply_figure_kw(ax, flags)

    return fig, ax
