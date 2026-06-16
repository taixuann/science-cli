"""Raman spectrum plotting."""
from pathlib import Path


def _plot_raman_single(filepath: str, flags: dict) -> None:
    """Single-axis Raman spectrum: intensity vs Raman shift."""
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from rich.console import Console

    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    p = Path(filepath)

    try:
        df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
    except Exception:
        df, info = load_data_file(str(p))

    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print(f"[red]Not enough columns in {p.name}.[/red]")
        return

    shift = pd.to_numeric(df[cols[0]], errors="coerce").values
    intensity = pd.to_numeric(df[cols[1]], errors="coerce").values
    mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))
    if not mask.any():
        console.print(f"[red]No valid data points in {p.name}.[/red]")
        return

    shift = shift[mask]
    intensity = intensity[mask]

    xlabel = flags.get("xlabel") or "Raman shift (cm⁻¹)"
    ylabel = flags.get("ylabel") or "Intensity (counts)"

    plt.figure()
    plot_kwargs = {}
    if flags.get("color"):
        plot_kwargs["color"] = flags["color"]
    if flags.get("linewidth"):
        plot_kwargs["linewidth"] = float(flags["linewidth"])
    if flags.get("linestyle"):
        plot_kwargs["linestyle"] = flags["linestyle"]
    plt.plot(shift, intensity, **plot_kwargs)

    meta = info.get("raman_metadata", {})
    laser = meta.get("laser", "")
    grating = meta.get("grating", "")
    subtitle = f"  [{laser} | {grating}]" if laser and grating else ""
    title = flags.get("title", "")
    if title:
        plt.title(f"{title}{subtitle}")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if flags.get("grid"):
        plt.grid(True, alpha=0.3)

    xlim = flags.get("xlim") or flags.get("zoom")
    if xlim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in xlim.split(",")]
            if len(parts) >= 2:
                plt.xlim(parts[0], parts[1])
        except ValueError:
            pass

    ylim = flags.get("ylim")
    if ylim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in ylim.split(",")]
            if len(parts) >= 2:
                plt.ylim(parts[0], parts[1])
        except ValueError:
            pass

    plt.tight_layout()

    out_name = flags.get("name") or flags.get("n")
    if not out_name:
        out_name = flags.get("auto_save") if isinstance(flags.get("auto_save"), str) else ""
    if not out_name:
        out_name = f"raman_{p.stem}.pdf"

    if out_name:
        from science_cli.cli.commands.raman import _get_results_dir as _raman_results_dir
        out_dir = _raman_results_dir(filepath)
        save_path = out_dir / out_name
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        plt.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()
    plt.close()


def _overlay_raman(files: list, flags: dict) -> None:
    """Overlay Raman spectra on single axis with color cycle."""
    from pathlib import Path

    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from rich.console import Console

    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    plt.figure()

    xlabel = flags.get("xlabel") or "Raman shift (cm⁻¹)"
    ylabel = flags.get("ylabel") or "Intensity (counts)"
    lw = float(flags.get("linewidth", 1.2))

    for f in files:
        p = Path(f)
        try:
            df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
        except Exception:
            continue
        cols = info.get("columns", [])
        if len(cols) < 2:
            continue
        shift = pd.to_numeric(df[cols[0]], errors="coerce").values
        intensity = pd.to_numeric(df[cols[1]], errors="coerce").values
        mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))
        if not mask.any():
            continue
        plt.plot(shift[mask], intensity[mask], label=p.stem, linewidth=lw)

    plt.title(flags.get("title") or "Raman Overlay Plot")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    if flags.get("grid"):
        plt.grid(True, alpha=0.3)

    xlim = flags.get("xlim") or flags.get("zoom")
    if xlim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in xlim.split(",")]
            if len(parts) >= 2:
                plt.xlim(parts[0], parts[1])
        except ValueError:
            pass

    ylim = flags.get("ylim")
    if ylim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in ylim.split(",")]
            if len(parts) >= 2:
                plt.ylim(parts[0], parts[1])
        except ValueError:
            pass

    plt.tight_layout()

    out_name = flags.get("name") or flags.get("n")
    if not out_name:
        out_name = "raman_overlay.pdf"

    if out_name:
        from science_cli.cli.commands.raman import _get_results_dir as _raman_results_dir
        out_dir = _raman_results_dir(files[0])
        save_path = out_dir / out_name
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        plt.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()
    plt.close()
