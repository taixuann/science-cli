"""Pulse retention plotting — time vs resistance."""
from pathlib import Path


def _plot_retention(filepath: str, flags: dict) -> None:
    """Plot retention data: time vs resistance."""
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
        df, info = load_data_file(filepath, technique="pulse-retention")
    except Exception as e:
        console.print(f"[red]Failed to load retention data: {e}[/red]")
        return

    figsize = parse_figsize(flags) or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    fig, ax = plt.subplots(figsize=figsize)
    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, "mem-retention")
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
    out_name = flags.get("n") or flags.get("name", f"retention_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Retention saved: {save_path}")
