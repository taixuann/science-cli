"""Generic config-driven plot executor.

Reads layout, columns, axis, filter, series, and annotations from
config-studies.yaml via resolve_plot_config(). Handles 80% of studies
without study-specific Python code.

Layouts:
    - ``single`` -- single-axis X vs Y plot (iv, raman, uv-vis, ec-cv, ec-ca, afm, ...)
    - ``dual_axis`` -- twin Y-axis (pulse-stp-decay: current left, voltage right)
    - ``dual_panel`` / ``grid_2x2`` -- fall back to single with a warning
      (ec-eis Nyquist + Bode still handled by eis.py)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unflatten(flat: dict) -> dict:
    """Convert flat dot-separated keys (e.g. ``columns.x``) to nested dict."""
    result: dict = {}
    for key, value in flat.items():
        parts = key.split(".")
        target = result
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return result


def _normalise_col(name: str) -> str:
    """Strip whitespace, units in parens, and lowercase for matching."""
    import re
    return re.sub(r"\s*\(.*?\)", "", name).strip().lower()


def _get_column(df, col_name: str | None):
    """Get DataFrame column -- try direct, normalised, then variant."""
    if col_name is None or col_name in df.columns:
        return df[col_name] if col_name else None
    norm = _normalise_col(col_name)
    for c in df.columns:
        if _normalise_col(c) == norm:
            return df[c]
    for sep in ("_", " "):
        alt = col_name.replace(sep, " " if sep == "_" else "_")
        if alt in df.columns:
            return df[alt]
        alt_norm = _normalise_col(alt)
        for c in df.columns:
            if _normalise_col(c) == alt_norm:
                return df[c]
    return None


# ---------------------------------------------------------------------------
# Layout plotters
# ---------------------------------------------------------------------------


def _plot_single(x, y, cfg: dict, ax) -> None:
    """Single-axis X vs Y plot."""
    series_cfg = cfg.get("series", {})
    s = next(iter(series_cfg.values()), {}) if series_cfg else {}
    ax.plot(
        x, y,
        color=s.get("color", "#1f77b4"),
        linewidth=s.get("linewidth", 1.5),
        linestyle=s.get("linestyle", "-"),
        marker=s.get("marker", ""),
        markersize=s.get("markersize", 0),
        alpha=s.get("alpha", 1.0),
        label=s.get("label", ""),
    )


def _plot_dual_axis(x, y, df, y2_col: str | None, cfg: dict, ax1, ax2) -> None:
    """Dual Y-axis: y on left ax1, y2 on right ax2."""
    series_cfg = cfg.get("series", {})
    y1 = series_cfg.get("current", series_cfg.get("y", {}))
    ax1.plot(x, y, color=y1.get("color", "tab:red"),
             linewidth=y1.get("linewidth", 1.0), label=y1.get("label", ""))
    y2d = _get_column(df, y2_col)
    if y2d is not None:
        y2 = series_cfg.get("voltage", series_cfg.get("y2", {}))
        ax2.plot(x, y2d.values.astype(float),
                 color=y2.get("color", "tab:blue"),
                 linewidth=y2.get("linewidth", 1.0), label=y2.get("label", ""))
        ax2.spines["right"].set_visible(True)


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------


def _apply_axis_settings(ax, cfg: dict, ax2=None) -> None:
    """Apply axis labels, scale, grid, and limits from config."""
    axis_cfg = cfg.get("axis", {})
    if axis_cfg.get("xlabel"):
        ax.set_xlabel(axis_cfg["xlabel"])
    if axis_cfg.get("ylabel"):
        ax.set_ylabel(axis_cfg["ylabel"])
    if ax2 and axis_cfg.get("ylabel2"):
        ax2.set_ylabel(axis_cfg["ylabel2"], color=axis_cfg.get("y2color"))
    if axis_cfg.get("ycolor"):
        ax.tick_params(axis="y", colors=axis_cfg["ycolor"])
        ax.spines["left"].set_color(axis_cfg["ycolor"])
        ax.yaxis.label.set_color(axis_cfg["ycolor"])
    if ax2 and axis_cfg.get("y2color"):
        ax2.tick_params(axis="y", colors=axis_cfg["y2color"])
        ax2.spines["right"].set_color(axis_cfg["y2color"])
        ax2.yaxis.label.set_color(axis_cfg["y2color"])

    axes_cfg = cfg.get("axes", {})
    if axes_cfg.get("xscale"):
        ax.set_xscale(axes_cfg["xscale"])
    if axes_cfg.get("yscale"):
        ax.set_yscale(axes_cfg["yscale"])
    if axes_cfg.get("grid"):
        ax.grid(True, alpha=axes_cfg.get("grid_alpha", 0.3))
    if axes_cfg.get("xlim"):
        ax.set_xlim(axes_cfg["xlim"])
    if axes_cfg.get("ylim"):
        ax.set_ylim(axes_cfg["ylim"])


def _add_annotations(ax, cfg: dict, x=None, y=None) -> None:
    """Add text annotations from config near data points."""
    annotations = cfg.get("annotations", {})
    if not annotations or x is None or y is None or len(x) == 0:
        return
    for ann in annotations.values():
        if not isinstance(ann, dict):
            continue
        text = ann.get("text", "")
        if not text:
            continue
        xy = (x[-1], y[-1]) if ann.get("position", "last") == "last" else (x[0], y[0])
        ax.annotate(text, xy=xy, xytext=(10, 0),
                    textcoords="offset points", fontsize=8,
                    color=ann.get("color", "#333"),
                    fontweight=ann.get("fontweight", "normal"),
                    va="center")


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def _plot_generic(filepath: str, flags: dict, study_name: str | None = None) -> None:
    """Config-driven single-file plot executor.

    Args:
        filepath: Path to data file.
        flags: CLI flags dict (size, dpi, title, xlim, ylim, ...).
        study_name: Qualified study name, e.g. ``"iv:iv-bipolar-sweep"``.
            If ``None``, auto-detected from ``filepath`` via
            ``detect_study_from_filename()``.
    """
    if study_name is None:
        from science_cli.core.config import detect_study_from_filename
        study_name = detect_study_from_filename(Path(filepath).name) or "unknown"
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.plot_config import resolve_plot_config
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    plot_flat = resolve_plot_config(study_name)
    cfg = _unflatten(plot_flat)
    layout = cfg.get("layout", "single")

    try:
        df, _info = load_data_file(filepath, study_name=study_name)
    except Exception as e:
        console.print(f"[red]Failed to load data: {e}[/red]")
        return

    sign = float(cfg.get("current_sign", 1))

    columns = cfg.get("columns", {})
    x_col = columns.get("x")
    y_col = columns.get("y")
    y2_col = columns.get("y2")

    # Drop NaN/Inf rows (rendering fix — matplotlib cannot plot NaN)
    df = df.replace([np.inf, -np.inf], np.nan)
    if x_col and x_col in df.columns:
        df = df.dropna(subset=[x_col])
    if y_col and y_col in df.columns:
        df = df.dropna(subset=[y_col])

    # Sort by time to prevent backward-time rendering glitches
    if x_col and x_col in df.columns:
        df = df.sort_values(x_col).reset_index(drop=True)

    x_data = _get_column(df, x_col)
    y_data = _get_column(df, y_col)

    if x_data is None or y_data is None:
        console.print(
            f"[red]Missing columns: x={x_col}, y={y_col}. "
            f"Available: {list(df.columns)}[/red]"
        )
        return

    x_vals = x_data.values.astype(float)
    y_vals = y_data.values.astype(float) * sign

    apply_theme(get_active_theme())
    figsize = (
        parse_figsize(flags)
        or plot_flat.get("figure.figsize")
        or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    )

    if layout == "dual_axis":
        fig, ax1 = plt.subplots(figsize=figsize)
        ax2 = ax1.twinx()
        _plot_dual_axis(x_vals, y_vals, df, y2_col, cfg, ax1, ax2)
        _apply_axis_settings(ax1, cfg, ax2)
    elif layout == "single":
        fig, ax1 = plt.subplots(figsize=figsize)
        _plot_single(x_vals, y_vals, cfg, ax1)
        _apply_axis_settings(ax1, cfg)
    else:
        # dual_panel, grid_2x2 -- fall back to single with warning
        import logging

        logging.getLogger(__name__).warning(
            "Layout '%s' not yet implemented in generic executor, "
            "falling back to single. Use eis.py for ec-eis.",
            layout,
        )
        fig, ax1 = plt.subplots(figsize=figsize)
        _plot_single(x_vals, y_vals, cfg, ax1)
        _apply_axis_settings(ax1, cfg)

    _add_annotations(ax1, cfg, x_vals, y_vals)
    apply_figure_kw(ax1, flags, Path(filepath).stem)
    fig.tight_layout()

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    short = study_name.split(":")[-1]
    out_name = flags.get("n") or flags.get("name", f"{short}_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(
        flags.get("dpi", plot_flat.get(
            "savefig.dpi", mpl.rcParams.get("savefig.dpi", 600),
        ))
    )
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]\u2713[/bold green] Plot saved: {save_path}")


def _overlay_generic(files: list, flags: dict, study_name: str | None = None) -> None:
    """Config-driven overlay -- plot multiple files on same axes.

    Args:
        files: List of data file paths.
        flags: CLI flags dict (size, dpi, labels, ...).
        study_name: Qualified study name, e.g. ``"iv:iv-bipolar-sweep"``.
            If ``None``, auto-detected from the first file via
            ``detect_study_from_filename()``.
    """
    if study_name is None and files:
        from science_cli.core.config import detect_study_from_filename
        study_name = detect_study_from_filename(Path(files[0]).name) or "unknown"
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.plot_config import resolve_plot_config
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import parse_figsize
    from science_cli.theme import apply_theme

    console = Console()
    plot_flat = resolve_plot_config(study_name)
    cfg = _unflatten(plot_flat)
    apply_theme(get_active_theme())

    figsize = (
        parse_figsize(flags)
        or plot_flat.get("figure.figsize")
        or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    )
    fig, ax = plt.subplots(figsize=figsize)
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [c["color"] for c in cycle]

    label_str = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in label_str.split(",") if s.strip()] if label_str else []

    sign = float(cfg.get("current_sign", 1))
    columns = cfg.get("columns", {})
    x_col = columns.get("x")
    y_col = columns.get("y")
    series_cfg = cfg.get("series", {})
    s = next(iter(series_cfg.values()), {}) if series_cfg else {}

    for idx, fp in enumerate(files):
        try:
            df, _info = load_data_file(fp, study_name=study_name)
        except Exception:
            continue
        xd = _get_column(df, x_col)
        yd = _get_column(df, y_col)
        if xd is None or yd is None:
            continue
        label = label_list[idx] if idx < len(label_list) else Path(fp).stem
        ax.plot(
            xd.values.astype(float), yd.values.astype(float) * sign,
            color=colors[idx % len(colors)],
            linewidth=s.get("linewidth", 1.0),
            label=label,
        )

    _apply_axis_settings(ax, cfg)
    if label_list or len(files) > 1:
        ax.legend(fontsize=7)
    fig.tight_layout()

    out_dir = _get_results_dir(files[0])
    short = study_name.split(":")[-1]
    out_name = flags.get("n") or flags.get("name", f"{short}_overlay.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", plot_flat.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]\u2713[/bold green] Overlay saved: {save_path}")
