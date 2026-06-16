"""Pulse endurance plotting — cycles vs resistance."""
from pathlib import Path


def _plot_endurance(filepath: str, flags: dict) -> None:
    """Plot endurance cycling data: cycles vs resistance.

    Generic base implementation — used directly for unknown/unspecified
    device types, and called internally by device-type-specific variants.
    """
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    try:
        df, info = load_data_file(filepath, technique="pulse-endurance")
    except Exception as e:
        console.print(f"[red]Failed to load endurance data: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "mem-endurance")
    if len(x) == 0 or len(y) == 0:
        console.print("[red]Could not determine x/y columns.[/red]")
        return
    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    plot_type = flags.get("type", "line")
    if plot_type == "scatter":
        ax.scatter(x, y, s=float(flags.get("markersize", 4))**2, alpha=0.8)
    else:
        ax.plot(x, y, linewidth=float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 1.0))))

    apply_figure_kw(ax, flags, Path(filepath).stem)
    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"endurance_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Endurance saved: {save_path}")


# ── Device-type-specific endurance variants ──────────────────────────
#
# These are STUBS for now — they delegate to ``_plot_endurance()``.
# Future implementations will add device-type-specific analysis:
#
#   volatile-memristor:
#       ON/OFF ratio detection, STP-like decay behavior between
#       read pulses, lower threshold for read-disturb effects.
#
#   non-volatile-memristor:
#       R_high/R_low separation tracking, retention stability
#       between program/erase, window margin (R_high_min − R_low_max).


def _plot_endurance_volatile(filepath: str, flags: dict) -> None:
    """Plot endurance for volatile memristors.

    Currently delegates to the generic ``_plot_endurance()``.
    Future: add ON/OFF ratio, STP decay tracking, read-disturb analysis.
    """
    _plot_endurance(filepath, flags)


def _plot_endurance_nonvolatile(filepath: str, flags: dict) -> None:
    """Plot endurance for non-volatile memristors.

    Currently delegates to the generic ``_plot_endurance()``.
    Future: add HRS/LRS separation, window margin, retention tracking.
    """
    _plot_endurance(filepath, flags)


def _overlay_endurance(filepath: str, flags: dict) -> None:
    """Overlay endurance curves from multiple files."""
    _overlay_generic([filepath], flags, technique="mem-endurance")


def _overlay_generic(files: list, flags: dict, technique: str = "") -> None:
    """Generic overlay for endurance variant stubs."""
    from science_cli.cli.commands.plot import _generic_overlay
    _generic_overlay(files, flags, technique)


def _overlay_endurance_volatile(files: list, flags: dict) -> None:
    """Overlay endurance curves for volatile memristor context.

    Currently delegates to the generic overlay.
    """
    _overlay_generic(files, flags, technique="mem-endurance")


def _overlay_endurance_nonvolatile(files: list, flags: dict) -> None:
    """Overlay endurance curves for non-volatile memristor context.

    Currently delegates to the generic overlay.
    """
    _overlay_generic(files, flags, technique="mem-endurance")
