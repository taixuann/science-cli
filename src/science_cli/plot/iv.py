"""IV study plotting: bipolar sweep with gradient, breakdown."""
from pathlib import Path


def _plot_iv_bipolar(filepath: str, flags: dict) -> None:
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from science_cli.cli.commands.plot import (
        _get_results_dir,
        _resolve_xy_columns,
    )
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())
    try:
        df, info = load_data_file(filepath, technique="iv-sweep")
    except Exception as e:
        from rich.console import Console
        console = Console()
        console.print(f"[red]Failed to load file: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)

    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "iv-sweep")
    if len(x) == 0 or len(y) == 0:
        from rich.console import Console
        Console().print("[red]Could not determine x/y columns.[/red]")
        return

    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    plot_type = flags.get("type", "line")
    lw = float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 1.0)))
    ls = flags.get("linestyle", mpl.rcParams.get("lines.linestyle", "solid"))

    if flags.get("gradient"):
        from matplotlib.collections import LineCollection
        cmap_name = flags.get("cmap", "viridis")
        _cmap = plt.get_cmap(cmap_name)
        pts = np.column_stack([x, y]).reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        lc = LineCollection(segs, cmap=_cmap, linewidth=lw, linestyle=ls)
        lc.set_array(np.linspace(0, 1, len(segs)))
        ax.add_collection(lc)
        ax.autoscale()
        sm = plt.cm.ScalarMappable(cmap=_cmap)
        sm.set_array([])
        plt.colorbar(sm, ax=ax).set_label("Sweep progression")
    elif plot_type == "scatter":
        ax.scatter(x, y, s=float(flags.get("markersize", 4))**2, alpha=0.8)
    else:
        ax.plot(x, y, linewidth=lw, linestyle=ls)

    apply_figure_kw(ax, flags, Path(filepath).stem)

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"iv-sweep_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    from rich.console import Console
    Console().print(f"[bold green]✓[/bold green] IV plot saved: {save_path}")


def _plot_iv_breakdown(filepath: str, flags: dict) -> None:
    """Breakdown plot — similar to bipolar but without gradient."""
    from science_cli.cli.commands.plot import _do_plot
    _do_plot(filepath, flags, technique="iv-breakdown")


def _overlay_iv_bipolar(files: list, flags: dict) -> None:
    """Overlay IV sweeps — single-axis with per-file color cycle."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())
    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    cycle = mpl.rcParams["axes.prop_cycle"]
    theme_colors = [entry["color"] for entry in cycle]
    colors = [theme_colors[i % len(theme_colors)] for i in range(len(files))]
    lw = float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 0.75)))

    from science_cli.core.plot_config import resolve_plot_config
    _iv_cfg = resolve_plot_config("iv:iv-bipolar-sweep")
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []
    _cfg_sweep_color = _iv_cfg.get("series.sweep.color")

    for i, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="iv-sweep")
            xi, yi, _, _ = _resolve_xy_columns(df, info, "iv-sweep")
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            _line_color = _cfg_sweep_color or colors[i]
            ax.plot(xi, yi, label=label, color=_line_color, linewidth=lw)
        except Exception:
            continue

    ax.legend()
    apply_figure_kw(ax, flags, "overlay")

    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "iv-bipolar_overlay.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    from rich.console import Console
    Console().print(f"[bold green]✓[/bold green] IV overlay saved: {save_path}")
