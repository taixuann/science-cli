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
# Subsampling
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge — override keys win."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


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
    series_type = s.get("type", "line")
    if series_type == "scatter":
        ax.scatter(
            x, y,
            s=float(s.get("markersize", 6)) ** 2,
            marker=s.get("marker", "o"),
            color=s.get("color", "#1f77b4"),
            alpha=s.get("alpha", 1.0),
            label=s.get("label", ""),
            linewidth=0,
        )
    else:
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


# ---------------------------------------------------------------------------
# Waveform panel
# ---------------------------------------------------------------------------


def _plot_waveform_panel(ax, waveform_pattern: list) -> None:
    """Draw a step plot of waveform segments on the given axes.

    Args:
        ax: Matplotlib axes to draw on.
        waveform_pattern: 2D array like ``[[t, v], ...]`` where each
            row is ``[time_s, voltage_V]``.
    """
    times = [row[0] for row in waveform_pattern]
    voltages = [row[1] for row in waveform_pattern]

    # Step plot with markers at segment boundaries
    ax.step(
        times, voltages,
        where="post",
        color="#1f77b4",
        linewidth=1.5,
        marker="o",
        markersize=3,
    )

    # Colored fill under the curve
    ax.fill_between(times, voltages, step="post", alpha=0.15, color="#1f77b4")

    # Horizontal dashed lines at each unique voltage level with text labels
    unique_voltages = sorted(set(voltages))
    for v in unique_voltages:
        ax.axhline(y=v, color="gray", linestyle="--", linewidth=0.5, alpha=0.4)
        ax.text(
            times[-1] if len(times) > 1 else 0,
            v,
            f"  {v:.3f} V",
            va="center",
            fontsize=7,
            color="gray",
        )

    ax.set_xlabel("Time (s)", fontsize=9)
    ax.set_ylabel("Voltage (V)", fontsize=9)
    ax.set_title("Waveform Segments", fontsize=10, fontweight="bold")

    # Y-limits: slightly above max voltage, slightly below min
    v_min = min(voltages)
    v_max = max(voltages)
    v_range = v_max - v_min if v_max != v_min else 0.1
    ax.set_ylim(v_min - 0.15 * v_range, v_max + 0.25 * v_range)

    ax.grid(True, alpha=0.2)


def _apply_ylim_padding(ax, y_vals_list: list[np.ndarray], cfg: dict) -> None:
    """Auto-compute y-limits from data with padding decades."""
    padding = cfg.get("axes", {}).get("ylim_padding", {})
    if not padding:
        return  # no padding config — don't override
    below = float(padding.get("below", 0.5))
    above = float(padding.get("above", 0.5))
    all_y = np.concatenate(y_vals_list) if y_vals_list else np.array([])
    if len(all_y) == 0:
        return
    y_min = np.nanmin(all_y)
    y_max = np.nanmax(all_y)
    lo = 10 ** (np.floor(np.log10(y_min)) - below)
    hi = 10 ** (np.ceil(np.log10(y_max)) + above)
    ax.set_ylim(lo, hi)


def _apply_yticks_show(ax, cfg: dict) -> None:
    """Show only y-ticks in a configurable range."""
    yticks_cfg = cfg.get("axes", {}).get("yticks_show", {})
    if not yticks_cfg:
        return
    lo = float(yticks_cfg["min"])
    hi = float(yticks_cfg["max"])
    import math
    lo_dec = int(math.ceil(math.log10(lo)))
    hi_dec = int(math.floor(math.log10(hi)))
    ticks = [10 ** d for d in range(lo_dec, hi_dec + 1)]
    ax.set_yticks(ticks)


def _plot_multi_series(x, series_data: dict[str, np.ndarray], cfg: dict, ax) -> None:
    """Multi-series scatter plot — each series with its own style and annotation.

    Reads ``columns.y_series`` for column-to-key mapping and ``series.<key>``
    for per-series styling.
    """
    series_cfg = cfg.get("series", {})
    for key, y_vals in series_data.items():
        s = series_cfg.get(key, {})
        series_type = s.get("type", "scatter")
        if series_type == "line":
            ax.plot(
                x, y_vals,
                color=s.get("color", "#1f77b4"),
                linewidth=s.get("linewidth", 1.5),
                linestyle=s.get("linestyle", "-"),
                marker=s.get("marker", ""),
                markersize=s.get("markersize", 0),
                alpha=s.get("alpha", 0.6),
                label=s.get("label", ""),
            )
        else:
            ax.scatter(
                x, y_vals,
                s=float(s.get("markersize", 12)) ** 2,
                marker=s.get("marker", "o"),
                color=s.get("color", "#1f77b4"),
                alpha=float(s.get("alpha", 0.6)),
                linewidth=0,
            )
        # Per-series annotation
        ann = s.get("annotation", {})
        text = ann.get("text", "")
        if text and len(x) > 0 and len(y_vals) > 0:
            ax.annotate(
                text,
                xy=(x[-1], y_vals[-1]),
                xytext=tuple(ann.get("xytext", [10, 0])),
                textcoords="offset points",
                fontsize=float(ann.get("fontsize", 6.5)),
                color=ann.get("color", s.get("color", "#333")),
                fontweight=ann.get("fontweight", "normal"),
                ha=ann.get("ha", "left"),
                va=ann.get("va", "center"),
            )


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


def _plot_generic(
    filepath: str,
    flags: dict,
    study_name: str | None = None,
    info: dict | None = None,
) -> None:
    """Config-driven single-file plot executor.

    Args:
        filepath: Path to data file.
        flags: CLI flags dict (size, dpi, title, xlim, ylim, ...).
        study_name: Qualified study name, e.g. ``"iv:iv-bipolar-sweep"``.
            If ``None``, auto-detected from ``filepath`` via
            ``detect_study_from_filename()``.
        info: Optional info dict from data loader (contains
            ``analysis.waveform_pattern``). If ``None`` and
            ``show_waveform`` is set, data is loaded internally.
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
    scale = flags.get("scale")
    plot_flat = resolve_plot_config(study_name, scale=scale)
    cfg = _unflatten(plot_flat)

    # Handle plot_variant (e.g. "current" for pulse-endurance)
    # Merges variant sub-block columns/axes over base config
    plot_variant = flags.get("plot_variant")
    if plot_variant and plot_variant in cfg:
        variant_cfg = cfg[plot_variant]
        if isinstance(variant_cfg, dict):
            for key in ("columns", "axes"):
                if key in variant_cfg:
                    cfg[key] = _deep_merge(cfg.get(key, {}), variant_cfg[key])

    # ── Protocol.yaml step-level overrides (highest priority) ────────
    # Allows steps to override xlim, ylim, yscale, etc. via
    # metadata.plot_overrides in protocol.yaml
    from science_cli.core.plot_config import resolve_step_plot_overrides
    step_overrides = resolve_step_plot_overrides(study_name, filepath=filepath)
    if step_overrides:
        # step_overrides are flat dot-separated — convert to nested and merge
        step_cfg = _unflatten(step_overrides)
        cfg = _deep_merge(cfg, step_cfg)

    layout = cfg.get("layout", "single")

    show_waveform = flags.get("show_waveform", False)

    try:
        df, info_internal = load_data_file(filepath, study_name=study_name)
    except Exception as e:
        console.print(f"[red]Failed to load data: {e}[/red]")
        return

    # Use provided info dict, fall back to internally loaded one
    _info = info if info is not None else info_internal

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
    # Also drop NaN in y_series columns
    y_series_cfg = columns.get("y_series", {})
    for key, col in y_series_cfg.items():
        if col in df.columns:
            df = df.dropna(subset=[col])

    # Sort by x to prevent backward-time rendering glitches
    if x_col and x_col in df.columns:
        df = df.sort_values(x_col).reset_index(drop=True)

    # Multi-series data extraction
    series_data: dict[str, np.ndarray] = {}
    if y_series_cfg:
        x_data = _get_column(df, x_col)
        if x_data is None:
            console.print(f"[red]Missing x column: {x_col}[/red]")
            return
        x_vals = x_data.values.astype(float)
        for key, col in y_series_cfg.items():
            yd = _get_column(df, col)
            if yd is not None:
                series_data[key] = yd.values.astype(float) * sign
            else:
                console.print(f"[yellow]Missing y_series column '{col}' for key '{key}'[/yellow]")

    x_data = _get_column(df, x_col)
    y_data = _get_column(df, y_col)

    if x_data is None and not series_data:
        console.print(
            f"[red]Missing columns: x={x_col}, y={y_col}. "
            f"Available: {list(df.columns)}[/red]"
        )
        return

    if x_data is not None:
        x_vals_maybe = x_data.values.astype(float)
    else:
        x_vals_maybe = None

    if y_data is not None and not series_data:
        y_vals = y_data.values.astype(float) * sign
    else:
        y_vals = None

    apply_theme(get_active_theme())
    figsize = (
        parse_figsize(flags)
        or plot_flat.get("figure.figsize")
        or mpl.rcParams.get("figure.figsize", (3.46, 2.75))
    )

    if show_waveform:
        # 1×2 layout: main plot (left) + waveform subfigure (right)
        fig, (ax1, axw) = plt.subplots(
            1, 2,
            figsize=(figsize[0] * 2, figsize[1]),
        )
        # Left axes: normal plot
        if layout == "multi_series":
            _plot_multi_series(x_vals_maybe, series_data, cfg, ax1)
            _apply_axis_settings(ax1, cfg)
            _apply_ylim_padding(ax1, list(series_data.values()), cfg)
            _apply_yticks_show(ax1, cfg)
        elif layout == "dual_axis":
            ax2 = ax1.twinx()
            _plot_dual_axis(x_vals_maybe, y_vals, df, y2_col, cfg, ax1, ax2)
            _apply_axis_settings(ax1, cfg, ax2)
        else:
            _plot_single(x_vals_maybe, y_vals, cfg, ax1)
            _apply_axis_settings(ax1, cfg)
        if layout != "multi_series":
            _add_annotations(ax1, cfg, x_vals_maybe, y_vals)
        apply_figure_kw(ax1, flags, Path(filepath).stem)

        # Right axes: describe panel — waveform or scalar metadata
        waveform_pattern = _info.get("analysis", {}).get("waveform_pattern")
        if waveform_pattern and isinstance(waveform_pattern, list) and len(waveform_pattern) >= 2:
            _plot_waveform_panel(axw, waveform_pattern)
        elif not _render_metadata_panel(axw, _info, filepath):
            axw.text(0.5, 0.5, "No describe data",
                     ha="center", va="center", transform=axw.transAxes,
                     fontsize=9, color="gray")
    elif layout == "multi_series":
        fig, ax1 = plt.subplots(figsize=figsize)
        # No subsampling — plot all data points
        _plot_multi_series(x_vals_maybe, series_data, cfg, ax1)
        _apply_axis_settings(ax1, cfg)
        _apply_ylim_padding(ax1, list(series_data.values()), cfg)
        _apply_yticks_show(ax1, cfg)
        apply_figure_kw(ax1, flags, Path(filepath).stem)
    elif layout == "dual_axis":
        fig, ax1 = plt.subplots(figsize=figsize)
        ax2 = ax1.twinx()
        _plot_dual_axis(x_vals_maybe, y_vals, df, y2_col, cfg, ax1, ax2)
        _apply_axis_settings(ax1, cfg, ax2)
        _add_annotations(ax1, cfg, x_vals_maybe, y_vals)
        apply_figure_kw(ax1, flags, Path(filepath).stem)
    elif layout == "single":
        fig, ax1 = plt.subplots(figsize=figsize)
        _plot_single(x_vals_maybe, y_vals, cfg, ax1)
        _apply_axis_settings(ax1, cfg)
        _add_annotations(ax1, cfg, x_vals_maybe, y_vals)
        apply_figure_kw(ax1, flags, Path(filepath).stem)
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


def _render_metadata_panel(ax, info: dict, filepath: str) -> bool:
    """Render scalar metadata on the describe panel axes.

    Collects scalar values from ``info.metadata`` and ``info.analysis``,
    preferring analysis (derived) values.  Falls back to reading the
    raw file header lines (V_LRS/V_HRS format for endurance files).

    Returns True if any content was rendered, False otherwise.
    """
    fields: dict[str, float] = {}

    # 1. Try derived metadata + analysis scalars
    for section in ("analysis", "metadata"):
        data = info.get(section, {}) or {}
        for k, v in data.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                # Pretty-name: v_set_v → "V_set", v_read_v → "V_read"
                pretty = k.replace("_v", "").replace("_", " ").title()
                fields[pretty] = float(v)

    # 2. Fallback: parse raw file header (V_LRS,V_HRS format)
    if not fields:
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                line1 = f.readline().strip()
                line2 = f.readline().strip()
            vals = {}
            if line1.startswith("V_LRS,"):
                vals["V_set"] = float(line1.split(",")[1])
            if line2.startswith("V_HRS,"):
                vals["V_read"] = float(line2.split(",")[1])
            fields.update(vals)
        except (OSError, ValueError, IndexError):
            pass

    # 3. Render
    if fields:
        ax.set_frame_on(False)
        ax.set_xticks([])
        ax.set_yticks([])
        n = len(fields)
        start_y = 0.55 if n <= 2 else 0.75
        step = 0.25 if n <= 2 else 0.18
        for i, (name, val) in enumerate(fields.items()):
            y = start_y - i * step
            ax.text(0.5, y, f"{name} = {val:.2f}",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=10, fontweight="bold")
        return True
    return False


# ---------------------------------------------------------------------------
# Endurance plot wrappers — config-driven via config-studies.yaml multi_series
# ---------------------------------------------------------------------------


def plot_endurance_resistance(file_path: str | Path = None, scale: str | None = None, **kwargs) -> None:
    """Plot R_HRS, R_LRS vs cycles — config-driven via ``_plot_generic``."""
    flags: dict = {"plot_variant": "resistance"}
    if scale:
        flags["scale"] = scale
    _plot_generic(str(file_path), flags, study_name="pulse:pulse-endurance")


def plot_endurance_current(file_path: str | Path = None, scale: str | None = None, **kwargs) -> None:
    """Plot I_LRS, I_HRS vs cycles — config-driven via ``_plot_generic``."""
    flags: dict = {"plot_variant": "current"}
    if scale:
        flags["scale"] = scale
    _plot_generic(str(file_path), flags, study_name="pulse:pulse-endurance")


def plot_endurance_both(file_path: str | Path = None, scale: str | None = None, **kwargs) -> None:
    """Plot both resistance and current as separate files."""
    plot_endurance_resistance(file_path=file_path, scale=scale, **kwargs)
    plot_endurance_current(file_path=file_path, scale=scale, **kwargs)
