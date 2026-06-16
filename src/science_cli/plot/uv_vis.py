"""UV-Vis spectrum plotting."""
from pathlib import Path


def _plot_uv_vis_single(filepath: str, flags: dict) -> None:
    """Single-axis UV-Vis transmission vs wavelength."""
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
        df, info = load_data_file(filepath, technique="uv-vis")
    except Exception as e:
        console.print(f"[red]Failed to load UV-Vis data: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "uv-vis")
    if len(x) == 0 or len(y) == 0:
        console.print("[red]Could not determine x/y columns.[/red]")
        return
    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    ax.plot(x, y, linewidth=float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 1.0))))
    apply_figure_kw(ax, flags, Path(filepath).stem)

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"uv-vis_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] UV-Vis saved: {save_path}")


def _overlay_uv_vis(files: list, flags: dict) -> None:
    """Overlay UV-Vis spectra on single axis."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir, _resolve_xy_columns
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [entry["color"] for entry in cycle]
    lw = float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 0.75)))
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for i, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="uv-vis")
            xi, yi, _, _ = _resolve_xy_columns(df, info, "uv-vis")
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            ax.plot(xi, yi, label=label, color=colors[i % len(colors)], linewidth=lw)
        except Exception:
            continue

    ax.legend()
    apply_figure_kw(ax, flags, "overlay")
    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "uv-vis_overlay.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] UV-Vis overlay saved: {save_path}")
