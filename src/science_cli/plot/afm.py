"""AFM/SPM plotting: topography images, line profiles, height distributions, PSD."""

from pathlib import Path

import numpy as np
from matplotlib.axes import Axes


def plot_afm_image(
    image: np.ndarray,
    px_to_nm: float = 1.0,
    cmap: str = "viridis",
    title: str = "",
    ax: Axes | None = None,
) -> Axes:
    """Render an AFM topography image with a colorbar.

    Args:
        image: 2D height map.
        px_to_nm: Spatial calibration (nm per pixel).
        cmap: Matplotlib colormap name (default: 'viridis').
        title: Optional plot title.
        ax: Optional matplotlib Axes (creates one if None).

    Returns:
        The matplotlib Axes object.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 5))

    h, w = image.shape
    extent = [0, w * px_to_nm, h * px_to_nm, 0]

    im = ax.imshow(image, cmap=cmap, extent=extent, interpolation="nearest")
    plt.colorbar(im, ax=ax, label="Height (nm)")
    ax.set_xlabel("X (nm)")
    ax.set_ylabel("Y (nm)")
    if title:
        ax.set_title(title)

    return ax


def plot_afm_line_profile(
    distances: np.ndarray,
    heights: np.ndarray,
    ax: Axes | None = None,
) -> Axes:
    """Plot a line profile extracted from an AFM image.

    Args:
        distances: Distance along the profile (pixels or nm).
        heights: Height values along the profile.
        ax: Optional matplotlib Axes.

    Returns:
        The matplotlib Axes object.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 3))

    ax.plot(distances, heights, color="black", linewidth=1.0)
    ax.set_xlabel("Distance (pixels)")
    ax.set_ylabel("Height (nm)")
    ax.grid(True, alpha=0.3)

    return ax


def plot_afm_height_distribution(
    hist: np.ndarray,
    bin_edges: np.ndarray,
    ax: Axes | None = None,
) -> Axes:
    """Plot a histogram of pixel height values.

    Args:
        hist: Histogram counts.
        bin_edges: Bin edge positions.
        ax: Optional matplotlib Axes.

    Returns:
        The matplotlib Axes object.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 3))

    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    ax.bar(bin_centers, hist, width=bin_centers[1] - bin_centers[0] if len(bin_centers) > 1 else 1,
           color="steelblue", alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.set_xlabel("Height (nm)")
    ax.set_ylabel("Pixel count")
    ax.grid(True, alpha=0.3)

    return ax


def plot_afm_psd(
    freq: np.ndarray,
    power: np.ndarray,
    ax: Axes | None = None,
) -> Axes:
    """Plot the power spectral density of an AFM image.

    Args:
        freq: Spatial frequency array (nm⁻¹).
        power: Power density array.
        ax: Optional matplotlib Axes.

    Returns:
        The matplotlib Axes object.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 3))

    ax.loglog(freq, power, color="black", linewidth=1.0)
    ax.set_xlabel("Spatial frequency (nm⁻¹)")
    ax.set_ylabel("PSD (nm⁴)")
    ax.grid(True, alpha=0.3, which="both")

    return ax


def _plot_afm_single(filepath: str, flags: dict) -> None:
    """AFM single: topography + height distribution."""
    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    p = Path(filepath)
    cmap = flags.get("colormap", flags.get("cmap", "viridis"))

    try:
        from science_cli.library.afm import load_afm
        data = load_afm(str(p))
    except ImportError:
        console.print("[red]AFMReader is not installed. Run: pip install AFMReader>=0.0.7[/red]")
        return
    except Exception as e:
        console.print(f"[red]Failed to load {p.name}: {e}[/red]")
        return

    from science_cli.library.afm.analyze import height_distribution
    from science_cli.plot.afm import plot_afm_image

    title = flags.get("title", f"{p.stem}")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    plot_afm_image(data.image, data.pixel_to_nm, cmap=cmap, title=title, ax=ax1)
    ax1.set_aspect("equal")

    hist, bins = height_distribution(data.image, bins=100)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    ax2.bar(bin_centers, hist, width=bin_centers[1] - bin_centers[0] if len(bin_centers) > 1 else 1,
            color="steelblue", alpha=0.7, edgecolor="black", linewidth=0.5)
    ax2.set_xlabel("Height (nm)")
    ax2.set_ylabel("Pixel count")
    ax2.grid(True, alpha=0.3)
    ax2.set_title("Height Distribution")

    plt.tight_layout()
    out_name = flags.get("name") or flags.get("n")
    if out_name:
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if proj:
            out_dir = proj / "results"
        else:
            out_dir = p.parent / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = out_dir / out_name
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        fig.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)
