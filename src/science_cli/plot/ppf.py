"""PPF (Paired-Pulse Facilitation) plotting."""
from pathlib import Path


def _plot_ppf_single(filepath: str, flags: dict) -> None:
    """PPF plot — twin-axis (voltage + current) similar to STP."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.plot_config import resolve_plot_config
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    try:
        df, info = load_data_file(filepath, technique="pulse-ppf")
    except Exception as e:
        console.print(f"[red]Failed to load PPF data: {e}[/red]")
        return

    apply_theme(get_active_theme())
    plot_cfg = resolve_plot_config("pulse:pulse-ppf")
    t = df.get("time", df.get("Time"))
    v = df.get("voltage", df.get("MeasResult1_value"))
    i = df.get("current", df.get("MeasResult2_value"))
    if t is None or v is None or i is None:
        console.print("[red]PPF data missing columns.[/red]")
        return

    t = t.values.astype(float)
    v = v.values.astype(float)
    i = i.values.astype(float) * -1
    mask = ~(np.isnan(t) | np.isnan(v) | np.isnan(i))
    t, v, i = t[mask], v[mask], i[mask]
    t_us = t * 1e6

    base_size = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", mpl.rcParams.get("figure.figsize", (3.46, 2.75))))
    fig, (ax_v, ax_i) = plt.subplots(1, 2, figsize=(base_size[0] * 1.8, base_size[1]))

    color_v = flags.get("color_v", plot_cfg.get("series.voltage.color", "tab:blue"))
    ax_v.plot(t_us, v, color=color_v, linewidth=float(plot_cfg.get("lines.linewidth", 1.0)))
    ax_v.set_xlabel("Time (µs)")
    ax_v.set_ylabel("Voltage (V)")

    color_i = flags.get("color_i", plot_cfg.get("series.current.color", "tab:red"))
    ax_i.plot(t_us, i, color=color_i, linewidth=float(plot_cfg.get("lines.linewidth", 1.0)))
    ax_i.set_xlabel("Time (µs)")
    ax_i.set_ylabel("Current (A)")

    fig.tight_layout()

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"ppf_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", plot_cfg.get("savefig.dpi", mpl.rcParams.get("savefig.dpi", 600))))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] PPF plot saved: {save_path}")


def _overlay_ppf(files: list, flags: dict) -> None:
    """Overlay PPF — 1×2 panels."""
    import matplotlib as mpl
    mpl.use("Agg")
    from pathlib import Path

    import matplotlib.pyplot as plt
    import numpy as np
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.plot_config import resolve_plot_config
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    plot_cfg = resolve_plot_config("pulse:pulse-ppf")
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [entry["color"] for entry in cycle]

    fig, (ax_v, ax_i) = plt.subplots(1, 2, figsize=tuple(plot_cfg.get("figure.figsize", (7, 3))))
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for idx, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="pulse-ppf")
        except Exception:
            continue
        t_arr = df.get("time", df.get("Time"))
        v_arr = df.get("voltage", df.get("MeasResult1_value"))
        i_arr = df.get("current", df.get("MeasResult2_value"))
        if t_arr is None:
            continue
        t_arr = t_arr.values.astype(float)
        v_arr = v_arr.values.astype(float)
        i_arr = i_arr.values.astype(float) * -1
        mask = ~(np.isnan(t_arr) | np.isnan(v_arr) | np.isnan(i_arr))
        t_us = t_arr[mask] * 1e6
        v_arr = v_arr[mask]
        i_arr = i_arr[mask]
        color = colors[idx % len(colors)]
        label = label_list[idx] if idx < len(label_list) else Path(fp).stem
        ax_v.plot(t_us, v_arr, color=color, linewidth=1.0, label=label)
        ax_i.plot(t_us, i_arr, color=color, linewidth=1.0, label=label)

    ax_v.set_xlabel("Time (µs)")
    ax_v.set_ylabel("Voltage (V)")
    ax_i.set_xlabel("Time (µs)")
    ax_i.set_ylabel("Current (A)")
    ax_v.legend()
    ax_i.legend()
    fig.tight_layout()

    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "ppf_overlay.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] PPF overlay saved: {save_path}")
