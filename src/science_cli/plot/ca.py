"""CA-specific plotting: chronoamperometry decay curves."""

import numpy as np

from science_cli.plot.base import (
    apply_figure_kw,
    create_figure,
    parse_figsize,
    plot_line,
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
        fig, ax = create_figure(flags.get("theme", "publication-nature"), figsize)
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


def _plot_ca_single(filepath: str, flags: dict) -> None:
    """CA single: time vs current."""
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
        device = _resolve_device("ec-ca", filepath)
        load_kwargs = {"technique": "ec-ca"}
        if device:
            load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load CA data: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "ec-ca")
    if len(x) == 0 or len(y) == 0:
        console.print("[red]Could not determine x/y columns.[/red]")
        return
    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    from science_cli.plot.ca import plot_ca_decay
    plot_ca_decay(x, y, flags=flags, ax=ax)

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"ec-ca_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] CA saved: {save_path}")


def _overlay_ca(files: list, flags: dict) -> None:
    """Overlay CA decay curves."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.plot.ca import plot_ca_decay
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
            df, info = load_data_file(fp, technique="ec-ca")
            xi, yi, _, _ = _resolve_xy_columns(df, info, "ec-ca")
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            cf = dict(flags, color=colors[i % len(colors)])
            plot_ca_decay(xi, yi, flags=cf, label=label, ax=ax)
        except Exception:
            continue

    ax.legend()
    apply_figure_kw(ax, flags, "overlay")
    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "ec-ca_overlay.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] CA overlay saved: {save_path}")
