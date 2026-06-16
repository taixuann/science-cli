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


def _plot_cv_single(filepath: str, flags: dict) -> None:
    """CV single: potential vs current."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.device_resolver import resolve_device as _resolve_device
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    try:
        device = _resolve_device("ec-cv", filepath)
        load_kwargs = {"technique": "ec-cv"}
        if device:
            load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load CV data: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "ec-cv")
    if len(x) == 0 or len(y) == 0:
        console.print("[red]Could not determine x/y columns.[/red]")
        return
    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    from science_cli.plot.cv import plot_cv_curve
    plot_cv_curve(x, y, flags=flags, ax=ax)

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"ec-cv_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] CV saved: {save_path}")


def _overlay_cv(files: list, flags: dict) -> None:
    """Overlay CV curves."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.plot.cv import plot_cv_curve
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [entry["color"] for entry in cycle]
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for i, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="ec-cv")
            xi, yi, _, _ = _resolve_xy_columns(df, info, "ec-cv")
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            cf = dict(flags, color=colors[i % len(colors)])
            plot_cv_curve(xi, yi, flags=cf, label=label, ax=ax)
        except Exception:
            continue

    ax.legend()
    apply_figure_kw(ax, flags, "overlay")
    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "ec-cv_overlay.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] CV overlay saved: {save_path}")
