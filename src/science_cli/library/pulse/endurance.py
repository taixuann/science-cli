"""Endurance analysis: cycle statistics, Weibull failure, trend degradation."""
from pathlib import Path

import numpy as np


def analyze_endurance(r_on, r_off, cycles):
    """Analyze endurance cycling data.
    Returns dict with mean resistances, CV, failure detection, Weibull fit, trend.
    """
    r_on = np.asarray(r_on, dtype=float).flatten()
    r_off = np.asarray(r_off, dtype=float).flatten()
    cycles = np.asarray(cycles, dtype=float).flatten()

    ratio = r_off / r_on
    mean_r_on = float(np.mean(r_on))
    mean_r_off = float(np.mean(r_off))
    mean_ratio = float(np.mean(ratio))
    cv_r_on = float(np.std(r_on) / mean_r_on) if mean_r_on != 0 else float("inf")
    cv_r_off = float(np.std(r_off) / mean_r_off) if mean_r_off != 0 else float("inf")

    failed_mask = ratio < 10
    failure_cycle = int(cycles[failed_mask][0]) if np.any(failed_mask) else None

    weibull_fit = None
    if failure_cycle is not None:
        weibull_fit = _weibull_failure_fit(cycles, ratio)

    try:
        coeffs = np.polyfit(cycles, r_off, 1)
        trend_slope = float(coeffs[0])
        trend_r_squared = float(
            1 - np.sum((r_off - np.polyval(coeffs, cycles)) ** 2)
            / np.sum((r_off - np.mean(r_off)) ** 2)
        )
    except Exception:
        trend_slope = 0.0
        trend_r_squared = 0.0

    tail_n = max(int(len(cycles) * 0.1), 3)
    ratio_tail = ratio[-tail_n:]

    return {
        "mean_r_on": mean_r_on,
        "mean_r_off": mean_r_off,
        "mean_ratio": mean_ratio,
        "cv_r_on": cv_r_on,
        "cv_r_off": cv_r_off,
        "failure_cycle": failure_cycle,
        "n_cycles": int(len(cycles)),
        "weibull_fit": weibull_fit,
        "trend_slope": trend_slope,
        "trend_r_squared": trend_r_squared,
        "ratio_tail_mean": float(np.mean(ratio_tail)),
        "ratio_tail_std": float(np.std(ratio_tail)),
    }


def _weibull_failure_fit(cycles, ratio):
    """Fit Weibull minimum distribution to cycles-to-failure."""
    from scipy import stats
    failed_mask = ratio < 10
    if np.sum(failed_mask) < 3:
        return {"shape": None, "scale": None, "error": "Too few failure points for Weibull fit"}
    cycles_failed = cycles[failed_mask]
    params = stats.weibull_min.fit(cycles_failed, floc=0)
    return {
        "shape": float(params[0]),
        "location": float(params[1]),
        "scale": float(params[2]),
    }


def endurance_summary(data):
    """Human-readable endurance summary."""
    stats = analyze_endurance(data.r_on, data.r_off, data.cycles)
    lines = [f"Endurance: {stats['n_cycles']} cycles"]
    lines.append(f"  R_ON  = {stats['mean_r_on']:.1f} Ohm (CV={stats['cv_r_on']:.3f})")
    lines.append(f"  R_OFF = {stats['mean_r_off']:.1f} Ohm (CV={stats['cv_r_off']:.3f})")
    lines.append(f"  Ratio = {stats['mean_ratio']:.1f}")
    if stats["failure_cycle"] is not None:
        lines.append(f"  FAILURE at cycle {stats['failure_cycle']}")
    else:
        lines.append("  NO FAILURE (ratio > 10 throughout)")
    lines.append(f"  R_OFF trend: {stats['trend_slope']:.2e} Ohm/cycle (R-squared={stats['trend_r_squared']:.4f})")
    return "\n".join(lines)


def analyze_endurance_to_yaml(
    r_on,
    r_off,
    cycles,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
    metadata: dict | None = None,
    project_root: Path | None = None,
    step_name: str = "",
) -> Path:
    """Analyze endurance and write YAML analysis file.

    If *project_root* and *step_name* are provided, also writes the
    extracted pulse metadata back to ``protocol.yaml`` under that step.
    """
    from science_cli.core.analysis_output import write_analysis_yaml

    stats = analyze_endurance(r_on, r_off, cycles)
    output = {
        "analysis": {
            "mode": devices or "general",
            "parameters": {
                "cycles_to_failure": stats.get("failure_cycle"),
                "r_high_initial": stats.get("mean_r_off"),
                "r_low_initial": stats.get("mean_r_on"),
                "cycle_to_cycle_variability_pct": stats.get("cv_r_off", 0) * 100 if stats.get("cv_r_off") else None,
                "n_cycles": stats.get("n_cycles"),
                "ratio_tail_mean": stats.get("ratio_tail_mean"),
                "ratio_tail_std": stats.get("ratio_tail_std"),
            },
            "per_cycle_sampling": len(r_on) if hasattr(r_on, "__len__") else None,
        },
    }

    # Write metadata back to protocol.yaml if project context provided
    if project_root and step_name and metadata:
        from science_cli.core.analysis_output import merge_analysis_to_metadata
        from science_cli.core.protocol import update_step_metadata

        proto_meta = merge_analysis_to_metadata(
            metadata, output["analysis"], key_prefix=""
        )
        if proto_meta:
            update_step_metadata(project_root, step_name, proto_meta)

    return write_analysis_yaml(
        technique="pulse-endurance",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices,
    )


# ── Menu-driven analysis handlers (called by interactive_menu.dispatch) ──

def _get_results_dir_relative(csv_path: Path) -> Path:
    """Determine a suitable output directory relative to the CSV file path.

    Tries protocol/<proto>/<step>/results/, then falls back to
    project/results/ or a results/ folder next to the CSV.
    """
    parts = csv_path.parts
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        step_name = parts[proto_idx + 2]
        results_dir = Path(*parts[:proto_idx + 3]) / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        return results_dir
    except (ValueError, IndexError):
        pass
    # Fallback: results/ next to CSV's project root
    for parent in csv_path.parents:
        if (parent / "results").exists() or parent.name == "protocol":
            out = parent / "results"
            out.mkdir(parents=True, exist_ok=True)
            return out
    # Last resort
    out = csv_path.parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save_and_close(fig, csv_path: Path, suffix: str) -> None:
    """Save a figure and close it, replicating the _save_fig pattern."""
    out_dir = _get_results_dir_relative(csv_path)
    stem = csv_path.stem
    save_path = out_dir / f"{stem}{suffix}.pdf"
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    from rich.console import Console
    Console().print(f"[bold green]✓[/bold green] Saved: {save_path}")


def ratio_histogram(file_path: Path = None, **kwargs) -> None:
    """Generate histogram of R_HRS / R_LRS ratio distribution.

    Reads from extracted-list CSV, saves plot to results/ directory.
    Updates protocol.yaml with ratio statistics.
    """
    import pandas as pd
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    csv_path = Path(file_path)
    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    ratios = df["ratio"].dropna()

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    ax.hist(ratios, bins=50, log=True,
            color="#CC7700", alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.axvline(ratios.mean(), color="red", linestyle="--", linewidth=1.0,
               label=f"Mean: {ratios.mean():.0f}")
    ax.axvline(ratios.median(), color="blue", linestyle=":", linewidth=1.0,
               label=f"Median: {ratios.median():.0f}")

    ax.set_xlabel("R_HRS / R_LRS Ratio")
    ax.set_ylabel("Count")
    ax.set_yscale("log")
    ax.legend(fontsize=8)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_and_close(fig, csv_path, "_ratio_histogram")

    # Update protocol.yaml metadata
    _update_protocol_metadata(csv_path, {
        "ratio_mean": float(ratios.mean()),
        "ratio_median": float(ratios.median()),
        "ratio_std": float(ratios.std()),
    })


def current_ratio_histogram(file_path: Path = None, **kwargs) -> None:
    """Generate histogram of I_LRS / I_HRS ratio distribution."""
    import pandas as pd
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    csv_path = Path(file_path)
    with open(csv_path) as f:
        v_set = float(f.readline().split(",")[1])
        v_read = float(f.readline().split(",")[1])

    df = pd.read_csv(csv_path, skiprows=2)
    i_ratios = df["i_ratio"].dropna()

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    ax.hist(i_ratios, bins=50, log=True,
            color="#2176AE", alpha=0.7, edgecolor="black", linewidth=0.5)
    ax.axvline(i_ratios.mean(), color="red", linestyle="--", linewidth=1.0,
               label=f"Mean: {i_ratios.mean():.0f}")
    ax.axvline(i_ratios.median(), color="blue", linestyle=":", linewidth=1.0,
               label=f"Median: {i_ratios.median():.0f}")

    ax.set_xlabel("I_LRS / I_HRS Ratio")
    ax.set_ylabel("Count")
    ax.set_yscale("log")
    ax.legend(fontsize=8)
    ax.set_title(f"V_set={v_set:.2f}V, V_read={v_read:.2f}V", fontsize=9)

    _save_and_close(fig, csv_path, "_current_ratio_histogram")

    _update_protocol_metadata(csv_path, {
        "i_ratio_mean": float(i_ratios.mean()),
        "i_ratio_median": float(i_ratios.median()),
        "i_ratio_std": float(i_ratios.std()),
    })


def _update_protocol_metadata(csv_path: Path, metadata: dict) -> None:
    """Update the protocol.yaml step metadata with analysis results.

    Locates the protocol YAML file from csv_path, finds the step
    containing this file, and updates step.metadata.
    """
    import yaml

    # Navigate: csv_path is in <project>/protocol/<name>/<step>/
    # protocol.yaml is at <project>/protocol/<name>/<name>.yaml
    parts = csv_path.parts
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        proto_yaml = Path(*parts[:proto_idx + 2]) / f"{proto_name}.yaml"
    except (ValueError, IndexError):
        return  # Can't determine protocol path

    if not proto_yaml.exists():
        return

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
