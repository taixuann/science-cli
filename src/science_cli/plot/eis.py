"""EIS-specific plotting: Nyquist, Bode."""

import numpy as np

from science_cli.plot.base import (
    apply_figure_kw,
    create_figure,
    parse_figsize,
    plot_line,
)


def _ensure_neg_imag(z_imag):
    """Ensure z_imag represents -Z'' (positive upward).
    
    Normalized column z_imag stores the raw column value. If the raw column
    was named "-Z'' (Ω)" (Autolab convention), values are already positive.
    If named "Z'' (Ω)" (other instruments), values are negative for capacitive.
    Detect by sign of min value and negate if needed so -Z'' sits on +y axis.
    """
    return -z_imag if np.min(z_imag) < 0 else z_imag


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

    y = _ensure_neg_imag(z_imag)
    plot_line(z_real, y, ax=ax, flags=flags, label=label)

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

    fig, ax1 = create_figure(flags.get("theme", ""), figsize=figsize)

    mag_flags = dict(flags)
    mag_flags.setdefault("color", "#2563eb")
    plot_line(frequency, magnitude, ax=ax1, flags=mag_flags)
    ax1.set_ylabel("|Z| (Ω)")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.grid(True, alpha=0.3)

    if phase is not None:
        ax2 = ax1.twinx()
        phase_flags = dict(flags)
        phase_flags["color"] = "#dc2626"
        plot_line(frequency, phase, ax=ax2, flags=phase_flags)
        ax2.set_ylabel("Phase (°)")
        ax2.set_xscale("log")
        ax2.set_xlabel("Frequency (Hz)")
        ax2.grid(True, alpha=0.3)

    return fig, ax1


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

    y_data = _ensure_neg_imag(z_imag)
    y_fit = _ensure_neg_imag(fit_imag)
    plot_line(z_real, y_data, ax=ax, flags=flags, label="Data")
    fit_flags = dict(flags)
    fit_flags["linestyle"] = "--"
    fit_flags["color"] = "red"
    fit_flags.pop("marker", None)
    plot_line(fit_real, y_fit, ax=ax, flags=fit_flags, label="Fit")

    ax.set_xlabel("Z' (Ω)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_aspect("equal")
    ax.legend()
    apply_figure_kw(ax, flags)

    return fig, ax
