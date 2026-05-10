"""EIS-specific plotting: Nyquist, Bode."""

import numpy as np
import matplotlib.pyplot as plt

from science_cli.theme import apply_theme
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
    """Plot Nyquist diagram: Z' vs -Z''. z_imag should be the raw Z'' values."""
    flags = flags or {}
    figsize = parse_figsize(flags)
    if ax is None:
        fig, ax = create_figure(flags.get("theme", "publication-acs"), figsize)
    else:
        fig = ax.figure

    # Plot -Z'' (negate z_imag for correct Nyquist orientation)
    y_vals = -z_imag
    plot_line(z_real, y_vals, ax=ax, flags=flags, label=label)

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Z' (Ω)")
    if not flags.get("ylabel"):
        ax.set_ylabel("-Z'' (Ω)")

    # Auto-scale with 5% padding (instead of set_aspect("equal") which can hide data)
    x_min, x_max = np.nanmin(z_real), np.nanmax(z_real)
    y_min, y_max = np.nanmin(y_vals), np.nanmax(y_vals)
    x_pad = max((x_max - x_min) * 0.05, abs(x_max) * 0.01)
    y_pad = max((y_max - y_min) * 0.05, abs(y_max) * 0.01)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    return fig, ax


def plot_eis_bode(
    frequency: np.ndarray,
    magnitude: np.ndarray,
    phase: np.ndarray | None = None,
    flags: dict | None = None,
):
    """Plot Bode diagram with dual y-axis: |Z| (left log) and Phase (right linear), shared log x-axis."""
    flags = flags or {}
    figsize = parse_figsize(flags)

    fig, ax_mag = create_figure(flags.get("theme", "default"), figsize)

    # Left axis: |Z| (log-log, red)
    mag_flags = dict(flags)
    mag_flags["color"] = flags.get("color", None) or "#D55E00"
    plot_line(frequency, magnitude, ax=ax_mag, flags=mag_flags)
    ax_mag.set_xlabel("Frequency (Hz)")
    ax_mag.set_ylabel("|Z| (Ω)")
    ax_mag.set_xscale("log")
    ax_mag.set_yscale("log")
    ax_mag.grid(True, alpha=0.3)

    if phase is not None:
        # Right axis: Phase (linear, blue)
        ax_phase = ax_mag.twinx()
        phase_flags = dict(flags)
        phase_flags["color"] = flags.get("color", None) or "#0072B2"
        phase_flags["linestyle"] = "--"
        plot_line(frequency, phase, ax=ax_phase, flags=phase_flags)
        ax_phase.set_ylabel("Phase (°)")
        ax_phase.set_yscale("linear")

        return fig, (ax_mag, ax_phase)
    else:
        return fig, ax_mag


def plot_eis_fit(
    z_real: np.ndarray,
    z_imag: np.ndarray,
    fit_real: np.ndarray,
    fit_imag: np.ndarray,
    flags: dict | None = None,
):
    """Plot Nyquist with data and fit overlay. z_imag/fit_imag are raw Z'' values."""
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

    # Auto-scale with 5% padding (replaces set_aspect("equal") which can hide data)
    all_x = np.concatenate([np.asarray(z_real).ravel(), np.asarray(fit_real).ravel()])
    all_y = np.concatenate([np.asarray(-z_imag).ravel(), np.asarray(-fit_imag).ravel()])
    x_min, x_max = np.nanmin(all_x), np.nanmax(all_x)
    y_min, y_max = np.nanmin(all_y), np.nanmax(all_y)
    x_pad = max((x_max - x_min) * 0.05, abs(x_max) * 0.01)
    y_pad = max((y_max - y_min) * 0.05, abs(y_max) * 0.01)
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    ax.legend()
    apply_figure_kw(ax, flags)

    return fig, ax
