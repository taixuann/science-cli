"""Pulse endurance analysis handlers — ratio vs cycles + histograms.

Menu-driven analysis functions for extracted-list endurance CSV files
(2 header lines: V_set, V_read; then data rows).  Provides log-log
scatter plots with linear fits and histograms for both R-ratio and
I-ratio columns.
"""

from pathlib import Path

import numpy as np


# ── Helpers ──


def _get_results_dir_relative(csv_path: Path) -> Path:
    """Determine a suitable output directory relative to the CSV file path.

    Resolution order:
      1. protocol/<name>/<step>/results/ — if path contains protocol/
      2. Scan protocol YAMLs from project root — if file is in data/raw/
      3. project/results/
      4. results/ next to the CSV
    """
    parts = csv_path.parts
    # 1. Direct protocol path
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        step_name = parts[proto_idx + 2]
        results_dir = Path(*parts[: proto_idx + 3]) / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        return results_dir
    except (ValueError, IndexError):
        pass

    # 2. File in data/raw/ — scan protocol YAMLs to find owning step
    try:
        raw_idx = parts.index("data")
        if raw_idx + 1 < len(parts) and parts[raw_idx + 1] == "raw":
            project_root = Path(*parts[:raw_idx])
            fname = parts[-1]
            import yaml
            for py in sorted(project_root.glob("protocol/*/*.yaml")):
                with open(py) as f:
                    proto_data = yaml.safe_load(f) or {}
                for s in proto_data.get("steps", []):
                    for entry in s.get("files", []):
                        entry_file = entry["file"] if isinstance(entry, dict) else entry
                        if entry_file == fname:
                            step_name_clean = s["name"].replace(" ", "_")
                            results_dir = py.parent / step_name_clean / "results"
                            results_dir.mkdir(parents=True, exist_ok=True)
                            return results_dir
    except (ValueError, IndexError):
        pass

    # 3. Fallback: results/ next to project root
    for parent in csv_path.parents:
        if (parent / "results").exists() or parent.name == "protocol":
            out = parent / "results"
            out.mkdir(parents=True, exist_ok=True)
            return out
    # 4. Last resort
    out = csv_path.parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save_analysis_plot(fig, csv_path: Path, kind: str) -> None:
    """Save analysis figure with format: {kind}_{full-stem}.pdf

    Uses the complete original CSV filename stem so files are
    easily correlated back to their source measurement.
    """
    out_dir = _get_results_dir_relative(csv_path)
    stem = csv_path.stem
    save_path = out_dir / f"{kind}_{stem}.pdf"
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    from rich.console import Console

    Console().print(f"[bold green]\u2713[/bold green] Saved: {save_path}")


def _to_native(obj):
    """Recursively convert numpy scalars/arrays to native Python types.

    PyYAML dumps numpy types as ``!!python/object/apply`` tags which
    break ``yaml.safe_load()`` on re-read.  Always convert before
    writing to protocol.yaml.
    """
    import numpy as np

    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_native(v) for v in obj]
    return obj


def _update_protocol_metadata(csv_path: Path, metadata: dict) -> None:
    """Update the protocol.yaml step metadata with analysis results.

    Locates the protocol YAML file from csv_path, finds the step
    containing this file, and updates step.metadata.  All values
    are converted to native Python types to avoid numpy-YAML tags.
    """
    import yaml

    # Navigate: csv_path is in <project>/protocol/<name>/<step>/
    # protocol.yaml is at <project>/protocol/<name>/<name>.yaml
    parts = csv_path.parts
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        proto_yaml = Path(*parts[: proto_idx + 2]) / f"{proto_name}.yaml"
    except (ValueError, IndexError):
        return  # Can't determine protocol path

    if not proto_yaml.exists():
        return

    # Convert numpy values *before* writing — this is the single fix
    # that prevents !!python/object/apply tags from appearing in YAML.
    metadata = _to_native(metadata)

    with open(proto_yaml) as f:
        config = yaml.safe_load(f)

    # Find step containing this file
    step_folder = csv_path.parent.name
    for step in config.get("steps", []):
        if step.get("name", "").replace(" ", "_") == step_folder:
            if "metadata" not in step:
                step["metadata"] = {}
            step["metadata"].update(metadata)
            break

    with open(proto_yaml, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


# ── Ratio vs cycles ──


def ratio_vs_cycles(file_path: Path = None, **kwargs) -> None:
    """Log-log scatter of R_HRS / R_LRS ratio vs cycle number with linear fit.

    Reads from extracted-list CSV (2 header lines: V_set, V_read; then
    data rows with columns including ``cycle`` and ``ratio``).  Saves
    the plot to results/ and writes fit metrics to protocol.yaml.

    Config-driven via resolve_analysis_plot_config().
    """
    import json as _json
    import pandas as pd
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    from science_cli.core.plot_config import resolve_analysis_plot_config

    apply_theme(get_active_theme())

    function_name = kwargs.get("function_name", "ratio_vs_cycles")
    csv_path = Path(file_path)
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-endurance",
        function_name,
        filepath=str(csv_path),
    )

    if kwargs.get("show_config") or kwargs.get("show-config"):
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    if df.empty:
        from rich.console import Console

        Console().print("[bold red]Error:[/bold red] Empty CSV data — nothing to plot.")
        return

    cycles = df["cycle"].dropna().values.astype(float)
    ratio = df["ratio"].dropna().values.astype(float)

    # Log-log fit: keep only positive values for log10
    valid = (cycles > 0) & (ratio > 0)
    log_c = np.log10(cycles[valid])
    log_r = np.log10(ratio[valid])

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    scatter_color = plot_cfg.get("series.scatter.color", "#CC7700")
    scatter_size = int(plot_cfg.get("series.scatter.size", 6))
    scatter_alpha = float(plot_cfg.get("series.scatter.alpha", 0.6))
    scatter_label = plot_cfg.get("series.scatter.label", "Data")

    ax.scatter(cycles, ratio,
               s=scatter_size, color=scatter_color,
               alpha=scatter_alpha, label=scatter_label)

    if len(log_c) >= 3:
        coeffs = np.polyfit(log_c, log_r, 1)
        fit_slope = float(coeffs[0])
        fit_intercept = float(coeffs[1])

        # R² on log-transformed data
        pred = np.polyval(coeffs, log_c)
        residuals = log_r - pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((log_r - np.mean(log_r)) ** 2)
        r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Plot fit line over full cycle range
        fit_x = np.logspace(
            np.log10(cycles[valid].min()), np.log10(cycles[valid].max()), 200
        )
        fit_y = 10 ** (np.log10(fit_x) * fit_slope + fit_intercept)

        fit_color = plot_cfg.get("series.fit.color", "red")
        fit_style = plot_cfg.get("series.fit.style", "--")
        fit_lw = float(plot_cfg.get("series.fit.linewidth", 1.2))

        ax.plot(
            fit_x,
            fit_y,
            color=fit_color,
            linestyle=fit_style,
            linewidth=fit_lw,
            label=f"Fit: slope={fit_slope:.3f}\n$R^2$={r_squared:.4f}",
        )
    else:
        fit_slope = None
        r_squared = None

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Cycle")
    ax.set_ylabel("R$_{\\mathrm{HRS}}$ / R$_{\\mathrm{LRS}}$ Ratio")
    ax.set_xlim(cycles[valid].min() * 0.9, cycles[valid].max() * 1.1)

    legend_loc = plot_cfg.get("legend.loc", "upper right")
    legend_fs = int(plot_cfg.get("legend.fontsize", 8))
    ax.legend(fontsize=legend_fs, loc=legend_loc)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_analysis_plot(fig, csv_path, "ratio-vs-cycles")

    if fit_slope is not None:
        _update_protocol_metadata(
            csv_path,
            {
                "ratio_fit_slope": fit_slope,
                "ratio_fit_r_squared": r_squared,
            },
        )
    else:
        _update_protocol_metadata(
            csv_path,
            {"ratio_fit_slope": None, "ratio_fit_r_squared": None},
        )


def i_ratio_vs_cycles(file_path: Path = None, **kwargs) -> None:
    """Log-log scatter of I_LRS / I_HRS ratio vs cycle number with linear fit.

    Reads from extracted-list CSV (2 header lines: V_set, V_read; then
    data rows with columns including ``cycle`` and ``i_ratio``).  Saves
    the plot to results/ and writes fit metrics to protocol.yaml.

    Config-driven — see :func:`ratio_vs_cycles` for the pattern.
    """
    import json as _json
    import pandas as pd
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    from science_cli.core.plot_config import resolve_analysis_plot_config

    apply_theme(get_active_theme())

    function_name = kwargs.get("function_name", "i_ratio_vs_cycles")
    csv_path = Path(file_path)
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-endurance",
        function_name,
        filepath=str(csv_path),
    )

    if kwargs.get("show_config") or kwargs.get("show-config"):
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    if df.empty:
        from rich.console import Console

        Console().print("[bold red]Error:[/bold red] Empty CSV data — nothing to plot.")
        return

    cycles = df["cycle"].dropna().values.astype(float)
    i_ratio = df["i_ratio"].dropna().values.astype(float)

    # Log-log fit: keep only positive values for log10
    valid = (cycles > 0) & (i_ratio > 0)
    log_c = np.log10(cycles[valid])
    log_ir = np.log10(i_ratio[valid])

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    scatter_color = plot_cfg.get("series.scatter.color", "#2176AE")
    scatter_size = int(plot_cfg.get("series.scatter.size", 6))
    scatter_alpha = float(plot_cfg.get("series.scatter.alpha", 0.6))
    scatter_label = plot_cfg.get("series.scatter.label", "Data")

    ax.scatter(cycles, i_ratio,
               s=scatter_size, color=scatter_color,
               alpha=scatter_alpha, label=scatter_label)

    if len(log_c) >= 3:
        coeffs = np.polyfit(log_c, log_ir, 1)
        fit_slope = float(coeffs[0])
        fit_intercept = float(coeffs[1])

        # R² on log-transformed data
        pred = np.polyval(coeffs, log_c)
        residuals = log_ir - pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((log_ir - np.mean(log_ir)) ** 2)
        r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Plot fit line over full cycle range
        fit_x = np.logspace(
            np.log10(cycles[valid].min()), np.log10(cycles[valid].max()), 200
        )
        fit_y = 10 ** (np.log10(fit_x) * fit_slope + fit_intercept)

        fit_color = plot_cfg.get("series.fit.color", "red")
        fit_style = plot_cfg.get("series.fit.style", "--")
        fit_lw = float(plot_cfg.get("series.fit.linewidth", 1.2))

        ax.plot(
            fit_x,
            fit_y,
            color=fit_color,
            linestyle=fit_style,
            linewidth=fit_lw,
            label=f"Fit: slope={fit_slope:.3f}\n$R^2$={r_squared:.4f}",
        )
    else:
        fit_slope = None
        r_squared = None

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Cycle")
    ax.set_ylabel("I$_{\\mathrm{LRS}}$ / I$_{\\mathrm{HRS}}$ Ratio")
    ax.set_xlim(cycles[valid].min() * 0.9, cycles[valid].max() * 1.1)

    legend_loc = plot_cfg.get("legend.loc", "upper right")
    legend_fs = int(plot_cfg.get("legend.fontsize", 8))
    ax.legend(fontsize=legend_fs, loc=legend_loc)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_analysis_plot(fig, csv_path, "i-ratio-vs-cycles")

    if fit_slope is not None:
        _update_protocol_metadata(
            csv_path,
            {
                "i_ratio_fit_slope": fit_slope,
                "i_ratio_fit_r_squared": r_squared,
            },
        )
    else:
        _update_protocol_metadata(
            csv_path,
            {"i_ratio_fit_slope": None, "i_ratio_fit_r_squared": None},
        )


# ── Histograms ──


def ratio_histogram(file_path: Path = None, **kwargs) -> None:
    """Generate histogram of R_HRS / R_LRS ratio distribution.

    Reads from extracted-list CSV, saves plot to results/ directory.
    Updates protocol.yaml with ratio statistics.

    Config-driven via resolve_analysis_plot_config() — hardcoded values
    serve as fallback defaults when config is absent.
    """
    import json as _json
    import pandas as pd
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import lognorm
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    from science_cli.core.plot_config import resolve_analysis_plot_config

    apply_theme(get_active_theme())

    # Resolve config
    function_name = kwargs.get("function_name", "ratio_histogram")
    csv_path = Path(file_path)
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-endurance",
        function_name,
        filepath=str(csv_path),
    )

    # --show-config support
    if kwargs.get("show_config") or kwargs.get("show-config"):
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    ratios = df["ratio"].dropna().values.astype(float)

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    # X-axis scale (log for skewed distributions, linear otherwise)
    xscale = plot_cfg.get("xscale", "linear")

    # Config-driven histogram bar styling
    n_bins = int(plot_cfg.get("bins", 50))
    bar_color = plot_cfg.get("series.bar.color", "#2EA043")
    bar_alpha = float(plot_cfg.get("series.bar.alpha", 0.7))
    bar_edgecolor = plot_cfg.get("series.bar.edgecolor", "black")
    bar_linewidth = float(plot_cfg.get("series.bar.linewidth", 0.5))

    # Use log-spaced bins when xscale is log for even bin distribution
    if xscale == "log":
        bins_arr = np.logspace(
            np.log10(max(ratios.min(), 1)),
            np.log10(ratios.max()),
            n_bins + 1,
        )
    else:
        bins_arr = n_bins

    n, bins_edges, _ = ax.hist(
        ratios,
        bins=bins_arr,
        color=bar_color,
        alpha=bar_alpha,
        edgecolor=bar_edgecolor,
        linewidth=bar_linewidth,
    )

    # Y-axis max method: supports "2nd-bin*1.5" (default) and
    # "percentile_N*M" (e.g. "percentile_99*1.2").
    sorted_n = np.sort(n)
    y_max_method = plot_cfg.get("y_max_method", "2nd-bin*1.5")
    if y_max_method.startswith("percentile_") and "*" in y_max_method:
        parts = y_max_method.replace("percentile_", "").split("*")
        try:
            pct = float(parts[0])
            mult = float(parts[1])
            y_max = np.percentile(n, pct) * mult
        except (ValueError, IndexError):
            y_max = sorted_n[-2] * 1.5
    else:
        y_max = sorted_n[-2] * 1.5
    ax.set_ylim(0, y_max)

    # Apply log-scale with padding and clean tick formatting
    if xscale == "log":
        ax.set_xscale("log")
        from matplotlib import ticker
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.xaxis.set_minor_formatter(ticker.NullFormatter())
        # Push x-axis lower bound to the left so data centers visually
        x_pad_factor = float(plot_cfg.get("x_pad_factor", 0.3))
        ax.set_xlim(ratios.min() * x_pad_factor, ratios.max() * 1.1)

    # Log-normal PDF fit
    fit_color = plot_cfg.get("series.fit.color", "black")
    fit_style = plot_cfg.get("series.fit.style", "--")
    fit_lw = float(plot_cfg.get("series.fit.linewidth", 1.2))

    if len(ratios) > 1 and ratios.min() > 0:
        params = lognorm.fit(ratios)
        if xscale == "log":
            x_pdf = np.logspace(np.log10(ratios.min()), np.log10(ratios.max()), 300)
        else:
            x_pdf = np.linspace(ratios.min(), ratios.max(), 300)
        pdf = lognorm.pdf(x_pdf, *params)
        bin_width = bins_edges[1] - bins_edges[0]
        pdf_scaled = pdf * len(ratios) * bin_width
        ax.plot(
            x_pdf, pdf_scaled,
            color=fit_color, linestyle=fit_style, linewidth=fit_lw,
            label="Log-normal fit",
        )

    ax.set_xlabel("R$_{\\mathrm{HRS}}$ / R$_{\\mathrm{LRS}}$ Ratio")
    ax.set_ylabel("Count")

    mean_color = plot_cfg.get("series.mean_line.color", "red")
    mean_style = plot_cfg.get("series.mean_line.style", "--")
    median_color = plot_cfg.get("series.median_line.color", "blue")
    median_style = plot_cfg.get("series.median_line.style", ":")

    ax.axvline(
        np.mean(ratios),
        color=mean_color,
        linestyle=mean_style,
        linewidth=1.0,
        label=f"Mean: {np.mean(ratios):.0f}",
    )
    ax.axvline(
        np.median(ratios),
        color=median_color,
        linestyle=median_style,
        linewidth=1.0,
        label=f"Median: {np.median(ratios):.0f}",
    )

    legend_loc = plot_cfg.get("legend.loc", "upper right")
    legend_fs = int(plot_cfg.get("legend.fontsize", 8))
    ax.legend(fontsize=legend_fs, loc=legend_loc)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_analysis_plot(fig, csv_path, "ratio-histogram")

    # Update protocol.yaml metadata
    _update_protocol_metadata(
        csv_path,
        {
            "ratio_mean": float(np.mean(ratios)),
            "ratio_median": float(np.median(ratios)),
            "ratio_std": float(np.std(ratios)),
        },
    )


def current_ratio_histogram(file_path: Path = None, **kwargs) -> None:
    """Generate histogram of I_LRS / I_HRS ratio distribution.

    Config-driven — see :func:`ratio_histogram` for the pattern.
    """
    import json as _json
    import pandas as pd
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import lognorm
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    from science_cli.core.plot_config import resolve_analysis_plot_config

    apply_theme(get_active_theme())

    function_name = kwargs.get("function_name", "current_ratio_histogram")
    csv_path = Path(file_path)
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-endurance",
        function_name,
        filepath=str(csv_path),
    )

    if kwargs.get("show_config") or kwargs.get("show-config"):
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    i_ratios = df["i_ratio"].dropna().values.astype(float)

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    # X-axis scale (log for skewed distributions)
    xscale = plot_cfg.get("xscale", "linear")

    n_bins = int(plot_cfg.get("bins", 50))
    bar_color = plot_cfg.get("series.bar.color", "#2EA043")
    bar_alpha = float(plot_cfg.get("series.bar.alpha", 0.7))
    bar_edgecolor = plot_cfg.get("series.bar.edgecolor", "black")
    bar_linewidth = float(plot_cfg.get("series.bar.linewidth", 0.5))

    # Use log-spaced bins when xscale is log
    if xscale == "log":
        bins_arr = np.logspace(
            np.log10(max(i_ratios.min(), 1)),
            np.log10(i_ratios.max()),
            n_bins + 1,
        )
    else:
        bins_arr = n_bins

    n, bins_edges, _ = ax.hist(
        i_ratios,
        bins=bins_arr,
        color=bar_color,
        alpha=bar_alpha,
        edgecolor=bar_edgecolor,
        linewidth=bar_linewidth,
    )

    # Y-axis max method
    sorted_n = np.sort(n)
    y_max_method = plot_cfg.get("y_max_method", "2nd-bin*1.5")
    if y_max_method.startswith("percentile_") and "*" in y_max_method:
        parts = y_max_method.replace("percentile_", "").split("*")
        try:
            pct = float(parts[0])
            mult = float(parts[1])
            y_max = np.percentile(n, pct) * mult
        except (ValueError, IndexError):
            y_max = sorted_n[-2] * 1.5
    else:
        y_max = sorted_n[-2] * 1.5
    ax.set_ylim(0, y_max)

    # Apply log-scale with padding and clean tick formatting
    if xscale == "log":
        ax.set_xscale("log")
        from matplotlib import ticker
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.xaxis.set_minor_formatter(ticker.NullFormatter())
        x_pad_factor = float(plot_cfg.get("x_pad_factor", 0.3))
        ax.set_xlim(i_ratios.min() * x_pad_factor, i_ratios.max() * 1.1)

    fit_color = plot_cfg.get("series.fit.color", "black")
    fit_style = plot_cfg.get("series.fit.style", "--")
    fit_lw = float(plot_cfg.get("series.fit.linewidth", 1.2))

    # Log-normal PDF fit
    if len(i_ratios) > 1 and i_ratios.min() > 0:
        params = lognorm.fit(i_ratios)
        if xscale == "log":
            x_pdf = np.logspace(np.log10(i_ratios.min()), np.log10(i_ratios.max()), 300)
        else:
            x_pdf = np.linspace(i_ratios.min(), i_ratios.max(), 300)
        pdf = lognorm.pdf(x_pdf, *params)
        bin_width = bins_edges[1] - bins_edges[0]
        pdf_scaled = pdf * len(i_ratios) * bin_width
        ax.plot(
            x_pdf, pdf_scaled,
            color=fit_color, linestyle=fit_style, linewidth=fit_lw,
            label="Log-normal fit",
        )

    ax.set_xlabel("I$_{\\mathrm{LRS}}$ / I$_{\\mathrm{HRS}}$ Ratio")
    ax.set_ylabel("Count")

    mean_color = plot_cfg.get("series.mean_line.color", "red")
    mean_style = plot_cfg.get("series.mean_line.style", "--")
    median_color = plot_cfg.get("series.median_line.color", "blue")
    median_style = plot_cfg.get("series.median_line.style", ":")

    ax.axvline(
        np.mean(i_ratios),
        color=mean_color,
        linestyle=mean_style,
        linewidth=1.0,
        label=f"Mean: {np.mean(i_ratios):.0f}",
    )
    ax.axvline(
        np.median(i_ratios),
        color=median_color,
        linestyle=median_style,
        linewidth=1.0,
        label=f"Median: {np.median(i_ratios):.0f}",
    )

    legend_loc = plot_cfg.get("legend.loc", "upper right")
    legend_fs = int(plot_cfg.get("legend.fontsize", 8))
    ax.legend(fontsize=legend_fs, loc=legend_loc)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_analysis_plot(fig, csv_path, "current-ratio-histogram")

    _update_protocol_metadata(
        csv_path,
        {
            "i_ratio_mean": float(np.mean(i_ratios)),
            "i_ratio_median": float(np.median(i_ratios)),
            "i_ratio_std": float(np.std(i_ratios)),
        },
    )
