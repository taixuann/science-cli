"""STP decay analysis — segment-aware batch diagnostic and overlay comparison.

Functions
---------
detect_stp_segments(time_s)
    Split STP time data by large gaps (T1).
analyze_all(file_path, **kwargs)
    Segment-aware diagnostic: detect segments, fit each, overview plot, metadata (T2/T3).
analyze_overlay(file_paths, **kwargs)
    Cross-file comparison of all [extracted-decay] tagged files.
"""

from pathlib import Path

import numpy as np

from science_cli.core.plot_config import resolve_analysis_plot_config
from science_cli.core.protocol import write_file_analyze_metadata

# ── Helpers ──


def _get_results_dir(csv_path: Path) -> Path:
    """Determine output directory relative to the CSV file path."""
    parts = csv_path.parts
    try:
        proto_idx = parts.index("protocol")
        proto_name = parts[proto_idx + 1]
        step_name = parts[proto_idx + 2]
        results_dir = Path(*parts[: proto_idx + 3]) / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        return results_dir
    except (ValueError, IndexError):
        pass
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
                            step_name = s["name"].replace(" ", "_")
                            results_dir = py.parent / step_name / "results"
                            results_dir.mkdir(parents=True, exist_ok=True)
                            return results_dir
    except (ValueError, IndexError):
        pass
    for parent in csv_path.parents:
        if (parent / "results").exists() or parent.name == "protocol":
            out = parent / "results"
            out.mkdir(parents=True, exist_ok=True)
            return out
    out = csv_path.parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _get_project_root(csv_path: Path) -> Path | None:
    """Get project root from a file in data/raw/ or protocol/."""
    parts = csv_path.parts
    try:
        proto_idx = parts.index("protocol")
        return Path(*parts[:proto_idx])
    except (ValueError, IndexError):
        pass
    try:
        raw_idx = parts.index("data")
        if raw_idx + 1 < len(parts) and parts[raw_idx + 1] == "raw":
            return Path(*parts[:raw_idx])
    except (ValueError, IndexError):
        pass
    return None


def _load_stp_data(file_path: Path):
    """Load time/current from an STP decay CSV.

    Returns (time_s, current_A, voltage_V, metadata_dict, wf_voltage) or raises.
    ``wf_voltage`` is the programmed Waveform1_voltage (if available) or None.
    """
    import pandas as pd
    from science_cli.core.data_loader import load_data_file

    df, info = load_data_file(str(file_path), study_name="pulse:pulse-stp-decay")
    cols = info.get("columns", [])
    if "time" not in cols or "current" not in cols:
        raise ValueError(f"STP data must have 'time' and 'current' columns. Got: {cols}")

    time_array = df["time"].values.astype(float)
    current_array = df["current"].values.astype(float) * -1  # current_sign
    voltage_array = df.get("voltage", df.get("MeasResult1_value", np.full_like(time_array, np.nan))).values.astype(float)

    # Try to get programmed Waveform1_voltage from the raw DataFrame
    wf_voltage: np.ndarray | None = None
    for col in df.columns:
        cl = col.lower().strip()
        if "waveform1_voltage" in cl:
            wf_voltage = pd.to_numeric(df[col], errors="coerce").values.astype(float)
            break

    # Remove NaN
    mask = ~(np.isnan(time_array) | np.isnan(current_array))
    time_c = time_array[mask]
    current_c = current_array[mask]
    voltage_c = voltage_array[mask]
    wf_c = wf_voltage[mask] if wf_voltage is not None else None
    return time_c, current_c, voltage_c, info.get("metadata", {}), wf_c


# ── T1: Segment Detection ──


def detect_stp_segments(
    time_s: np.ndarray,
    voltage_array: np.ndarray | None = None,
    pre_jump_points: int = 5,
) -> list[dict]:
    """Split STP data into non-overlapping segments by voltage plateaus.

    Each voltage level transition (e.g. 0→0.5V, 0.5V→1.75V, 1.75V→0.5V)
    creates a new segment covering that plateau within a single time-cycle.
    Segments are non-overlapping. For multi-cycle files (time wraps), each
    cycle's plateaus are isolated.

    Args:
        time_s: Time array (seconds).
        voltage_array: Measured voltage (MeasResult1_value).
        pre_jump_points: Context hint saved in segment metadata (ignored
            for boundary computation — context is applied at plot time).

    Returns:
        List of dict: segment_id, start, end, n_points, duration_s, v_level.
    """
    if len(time_s) < 10:
        return [_single_seg_leaf(len(time_s), time_s)]

    v = voltage_array.copy() if voltage_array is not None else None
    if v is None or np.sum(~np.isnan(v)) < 5:
        return [_single_seg_leaf(len(time_s), time_s)]

    v[np.isnan(v)] = 0.0

    # ── Time-wrap boundaries ──
    diffs = np.diff(time_s)
    wraps = np.where(diffs < -1e-8)[0]
    bounds = sorted({0, len(time_s)} | {int(w + 1) for w in wraps if int(w + 1) < len(time_s)})

    segments: list[dict] = []
    for ci in range(len(bounds) - 1):
        cs, ce = bounds[ci], bounds[ci + 1]
        if ce - cs < 5:
            continue

        vc = v[cs:ce].copy()

        # 3-level classification
        lev = np.zeros(ce - cs, dtype=int)
        lev[(vc > 0.15) & (vc < 0.9)] = 1
        lev[vc >= 0.9] = 2
        for i in range(1, len(lev) - 1):
            if lev[i] != lev[i - 1] and lev[i] != lev[i + 1]:
                lev[i] = lev[i - 1]

        tr = np.where(np.diff(lev) != 0)[0]
        if len(tr) < 1:
            if ce - cs >= 3:
                _add_seg(segments, cs, ce, time_s, vc)
            continue

        # Non-overlapping regions: [0, tr[0]+1], [tr[0]+1, tr[1]+1], ..., [tr[-1]+1, len]
        r_starts = [0] + [int(t + 1) for t in tr]
        r_ends = [int(t + 1) for t in tr] + [ce - cs]

        for rs, re in zip(r_starts, r_ends):
            if re - rs < 3:
                continue
            v_lvl = float(np.median(vc[rs:min(rs + 5, re)])) if re > rs else 0.0
            segments.append({
                "segment_id": 0, "start": cs + rs, "end": cs + re,
                "n_points": re - rs,
                "duration_s": float(time_s[cs + re - 1] - time_s[cs + rs]),
                "v_level": v_lvl,
            })

    for i, s in enumerate(segments, 1):
        s["segment_id"] = i
    return segments if segments else [_single_seg_leaf(len(time_s), time_s)]


def _single_seg_leaf(n: int, t: np.ndarray) -> list[dict]:
    return [{"segment_id": 1, "start": 0, "end": n, "n_points": n,
             "duration_s": float(t[-1] - t[0]) if n >= 2 else 0.0, "v_level": 0.0}]


def _add_seg(segs: list, cs: int, ce: int, t: np.ndarray, vc: np.ndarray) -> None:
    v_lvl = float(np.median(vc[:min(5, ce - cs)])) if ce > cs else 0.0
    segs.append({"segment_id": 0, "start": cs, "end": ce,
                  "n_points": ce - cs,
                  "duration_s": float(t[ce - 1] - t[cs]),
                  "v_level": v_lvl})

def _has_extracted_decay(file_path: Path, project_root: Path) -> bool:
    """Check if a file already has extracted_decay tags in protocol.yaml (T4).

    Returns True if the file entry's metadata contains ``extracted_decay.segment_001``
    in either the old flat location (``metadata.extracted_decay``) or the new
    per-function location (``analyze.analyze_all.metadata.extracted_decay``).
    """
    import yaml
    from science_cli.core.paths import ProjectPaths

    fname = file_path.name
    paths = ProjectPaths(project_root)

    for py in paths.list_protocol_yamls():
        with open(py) as f:
            proto_data = yaml.safe_load(f) or {}
        for s in proto_data.get("steps", []):
            for entry in s.get("files", []):
                entry_name = entry["file"] if isinstance(entry, dict) else entry
                if entry_name == fname and isinstance(entry, dict):
                    # Check old location: metadata.extracted_decay
                    meta = entry.get("metadata", {})
                    extracted = meta.get("extracted_decay", {})
                    if isinstance(extracted, dict) and extracted.get("segment_001"):
                        return True
                    if isinstance(extracted, bool) and extracted:
                        return True
                    # Check new location: analyze.analyze_all.metadata.extracted_decay
                    analyze_all = entry.get("analyze", {}).get("analyze_all", {})
                    if isinstance(analyze_all, dict):
                        new_extracted = analyze_all.get("metadata", {}).get("extracted_decay", {})
                        if isinstance(new_extracted, dict) and new_extracted.get("seg_001"):
                            return True
    return False


def _to_native(val):
    """Convert numpy scalar to native Python type for safe YAML serialization."""
    import numpy as np
    if isinstance(val, np.generic):
        return val.item()
    if isinstance(val, float) and (val != val):
        return None
    return val


def _tag_with_segment_metadata(
    csv_path: Path, project_root: Path, metadata_dict: dict,
    function_name: str = "analyze_all", step_name: str = "",
) -> None:
    """Tag a file with extracted_decay metadata under ``analyze.<function_name>.metadata``.

    Writes via :func:`write_file_analyze_metadata` so metadata lands in the
    per-function namespace rather than the flat ``metadata`` key.

    *metadata_dict* should have the form ``{"extracted_decay": {...}}``.
    """
    import yaml
    from science_cli.core.paths import ProjectPaths

    fname = csv_path.name
    paths = ProjectPaths(project_root)

    # Find protocol YAML + step name from file
    resolved_step = step_name
    resolved_py: Path | None = None
    for py in paths.list_protocol_yamls():
        with open(py) as f:
            proto_data = yaml.safe_load(f) or {}
        for s in proto_data.get("steps", []):
            for entry in s.get("files", []):
                entry_name = entry["file"] if isinstance(entry, dict) else entry
                if entry_name == fname:
                    resolved_py = py
                    if not resolved_step:
                        resolved_step = s["name"]
                    break

    if resolved_py is not None and resolved_step:
        write_file_analyze_metadata(resolved_py, resolved_step, fname, function_name, metadata_dict)
        from rich.console import Console
        n_segs = len([k for k in metadata_dict.get("extracted_decay", {}) if k.startswith("seg_")])
        Console().print(
            f"  [green]Tagged:[/green] {fname} -> protocol.yaml "
            f"(analyze.{function_name}.metadata.extracted_decay, {n_segs} segments)"
        )


# ── Plotting ──


def _save_plot(fig, csv_path: Path, kind: str) -> None:
    """Save figure to results/ with {kind}_{stem}.pdf."""
    out_dir = _get_results_dir(csv_path)
    stem = csv_path.stem
    save_path = out_dir / f"{kind}_{stem}.pdf"
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    from rich.console import Console
    Console().print(f"[bold green]\u2713[/bold green] Saved: {save_path}")


def _plot_full_waveform(ax, time_s, current_A, voltage_V, result, plot_cfg=None) -> None:
    """Plot full STP decay waveform on given axes."""
    cfg = plot_cfg or {}
    current_color = cfg.get("waveform.current_color", "#CC0000")
    current_label = cfg.get("waveform.current_label", "I(t)")
    voltage_color = cfg.get("waveform.voltage_color", "#0055CC")
    voltage_label = cfg.get("waveform.voltage_label", "V(t)")
    linewidth = float(cfg.get("waveform.linewidth", 1.0))

    t_us = time_s * 1e6
    ax.plot(t_us, current_A * 1e6, ".", color=current_color, markersize=2, alpha=0.6, label=f"{current_label} data")

    # Fitted decay line
    if result and "error" not in result and result.get("tau1_ms") is not None:
        t_fit = np.linspace(time_s[0], time_s[-1], 500)
        t_fit_norm = t_fit - time_s[0]
        i_norm = np.abs(current_A)
        steady = result.get("steady_state_current_ua", i_norm[-1]) * 1e-6
        a1 = result.get("a1") or (i_norm[0] - steady)
        tau1 = result["tau1_ms"]
        if result["model"] == "monoexponential":
            i_fit = a1 * np.exp(-t_fit_norm / tau1) + steady
        else:
            a2 = result.get("a2") or (i_norm[0] - steady) * 0.3
            tau2 = result.get("tau2_ms") or tau1
            i_fit = (a1 * np.exp(-t_fit_norm / tau1) + a2 * np.exp(-t_fit_norm / tau2)) + steady
        ax.plot(t_fit * 1e6, i_fit * 1e6, "-", color=current_color, linewidth=linewidth, label=f"Fit: {result['model']}")

    # Voltage on right axis
    ax2 = ax.twinx()
    ax2.plot(t_us, voltage_V, "-", color=voltage_color, linewidth=0.8, alpha=0.7, label=voltage_label)
    ax2.set_ylabel("Voltage (V)", color=voltage_color)
    ax2.tick_params(axis="y", colors=voltage_color)

    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Current (µA)")
    ax.legend(fontsize=8, loc="upper right")

    # Full waveform annotation
    if result and "error" not in result and result.get("tau1_ms") is not None:
        tau1 = result["tau1_ms"]
        tau2 = result.get("tau2_ms")
        init_i = result.get("initial_current_ua", 0)
        final_i = result.get("steady_state_current_ua", 0)
        model = result.get("model", "")
        r2 = result.get("r_squared", 0)
        txt = f"$\\tau$ = {tau1:.1f} ms"
        if tau2:
            txt += f"\n$\\tau_2$ = {tau2:.1f} ms"
        txt += f"\nI$_0$ = {init_i:.1f} µA\nI$_\\infty$ = {final_i:.1f} µA\nR² = {r2:.4f}"
        ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=8,
                verticalalignment="top", bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))


def _plot_rise_zoom(ax, time_s, voltage_V, result, plot_cfg=None) -> None:
    """Plot zoomed rise phase on given axes."""
    cfg = plot_cfg or {}
    xpad = float(cfg.get("rise_zoom.xpad", 0.15))
    time_unit = cfg.get("rise_zoom.time_unit", "µs")

    t_us = time_s * 1e6
    # Find the rise + plateau region (first ~20% of duration)
    mid = max(10, len(t_us) // 5)
    ax.plot(t_us[:mid], voltage_V[:mid], "-", color="#0055CC", linewidth=1.5)

    v_set = np.max(voltage_V[:mid])
    v_read = np.min(voltage_V[:mid])

    ax.axhline(y=v_set, color="green", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.axhline(y=v_read, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.text(t_us[0], v_set, f" V_set = {v_set:.3f} V", fontsize=7, color="green", va="bottom")
    ax.text(t_us[0], v_read, f" V_read = {v_read:.3f} V", fontsize=7, color="gray", va="top")

    ax.set_xlabel(f"Time ({time_unit})")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Rise Phase (Zoom)", fontsize=10)


def _plot_decay_zoom(ax, time_s, current_A, result, plot_cfg=None) -> None:
    """Plot zoomed decay phase with fit line."""
    cfg = plot_cfg or {}
    fit_color = cfg.get("fit.color", "black")
    fit_style = cfg.get("fit.style", "--")
    fit_linewidth = float(cfg.get("fit.linewidth", 1.2))

    t_us = time_s * 1e6
    i_ua = current_A * 1e6

    # Decay region: after voltage settles (skip initial portion)
    skip = max(1, len(t_us) // 4)
    t_decay = t_us[skip:]
    i_decay = i_ua[skip:]

    ax.plot(t_decay, i_decay, ".", color="#CC0000", markersize=3, alpha=0.6, label="Data")

    # Fitted decay for zoom
    if result and "error" not in result and result.get("tau1_ms") is not None:
        t_fit = np.linspace(time_s[skip], time_s[-1], 300)
        t_fit_norm = t_fit - time_s[0]
        i_norm = np.abs(current_A)
        steady = result.get("steady_state_current_ua", i_norm[-1]) * 1e-6
        a1 = result.get("a1") or (i_norm[0] - steady)
        tau1 = result["tau1_ms"]
        if result["model"] == "monoexponential":
            i_fit = a1 * np.exp(-t_fit_norm / tau1) + steady
        else:
            a2 = result.get("a2") or (i_norm[0] - steady) * 0.3
            tau2 = result.get("tau2_ms") or tau1
            i_fit = (a1 * np.exp(-t_fit_norm / tau1) + a2 * np.exp(-t_fit_norm / tau2)) + steady
        i_fit_ua = i_fit * 1e6
        ax.plot(t_fit * 1e6, i_fit_ua, fit_style, color=fit_color, linewidth=fit_linewidth, label="Fit")

        tau1 = result.get("tau1_ms", 0)
        tau2 = result.get("tau2_ms")
        decay_pct = result.get("decay_pct", 0)
        txt = f"$\\tau$ = {tau1:.1f} ms"
        if tau2:
            txt += f"\n$\\tau_2$ = {tau2:.1f} ms"
        txt += f"\nDecay = {decay_pct:.1f}%"
        ax.text(0.95, 0.95, txt, transform=ax.transAxes, fontsize=8,
                verticalalignment="top", horizontalalignment="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Current (µA)")
    ax.legend(fontsize=8)
    ax.set_title("Decay Phase (Zoom)", fontsize=10)


def _plot_single_segment(ax, time_s, current_A, voltage_V, seg: dict, result: dict, color, plot_cfg=None) -> None:
    """Plot a single voltage-plateau segment with context before the jump.

    Shows:
    - Current (scatter) on left axis
    - Voltage (line) on right axis, with the jump clearly visible
    - The pre-jump context window marked
    - Tau markers and annotation box for the decay fit
    """
    cfg = plot_cfg or {}
    fit_color = cfg.get("fit.color", "black")
    fit_style = cfg.get("fit.style", "--")
    fit_linewidth = float(cfg.get("fit.linewidth", 1.2))

    s, e = seg["start"], seg["end"]
    t_seg_us = time_s[s:e] * 1e6
    i_seg_ua = np.abs(current_A[s:e]) * 1e6
    v_seg = voltage_V[s:e]

    # Voltage on right axis (with the jump context visible)
    ax2 = ax.twinx()
    ax2.plot(t_seg_us, v_seg, "-", color="#0055CC", linewidth=1, alpha=0.7, label="V(t)")
    ax2.set_ylabel("Voltage (V)", color="#0055CC", fontsize=8)
    ax2.tick_params(axis="y", colors="#0055CC", labelsize=7)
    # Add horizontal line at the plateau voltage level
    v_level = seg.get("v_level", 0)
    if v_level > 0.01:
        ax2.axhline(y=v_level, color="#0055CC", linestyle="--", linewidth=0.5, alpha=0.3)
        ax2.text(t_seg_us[-1], v_level, f" {v_level:.2f}V", fontsize=6, color="#0055CC", alpha=0.5, va="bottom")

    # Current data (scatter)
    ax.plot(t_seg_us, i_seg_ua, ".", color=color, markersize=2.5, alpha=0.6, label="I(t)")

    # Mark the pre-jump context region
    pre_jump = min(5, len(t_seg_us) // 4)
    if pre_jump > 1:
        ax.axvspan(t_seg_us[0], t_seg_us[pre_jump], alpha=0.06, color="gray")
        ax.text(t_seg_us[pre_jump // 2], ax.get_ylim()[1] * 0.95, "context",
                fontsize=5, color="gray", alpha=0.5, ha="center")

    # Decay fit on the plateau (skip the fast jump region)
    if "error" not in result and result.get("tau1_ms") is not None:
        # Find the plateau region: voltage is stable near v_level
        if v_level > 0.01:
            plateau_mask = np.abs(v_seg - v_level) < 0.3 * v_level
            plateau_idx = np.where(plateau_mask)[0]
        else:
            plateau_idx = np.arange(len(v_seg))

        if len(plateau_idx) > 5:
            p_start = plateau_idx[0] if plateau_idx[0] > pre_jump else pre_jump
            p_end = plateau_idx[-1] + 1
            p_slice = slice(p_start, min(p_end, len(t_seg_us)))

            t_plateau = time_s[s:e][p_slice]
            i_plateau = np.abs(current_A[s:e][p_slice])

            if len(t_plateau) >= 5:
                t_fit = np.linspace(t_plateau[0], t_plateau[-1], 300)
                t_fit_norm = t_fit - t_plateau[0]
                steady = result.get("steady_state_current_ua", i_plateau[-1]) * 1e-6
                tau1 = result["tau1_ms"] * 1e-3  # ms -> s
                a1_val = result.get("a1") or (i_plateau[0] - steady)

                if result["model"] == "monoexponential":
                    i_fit = a1_val * np.exp(-t_fit_norm / tau1) + steady
                else:
                    a2 = result.get("a2") or (i_plateau[0] - steady) * 0.3
                    tau2 = (result.get("tau2_ms") or tau1 * 1000) * 1e-3
                    i_fit = (a1_val * np.exp(-t_fit_norm / tau1) +
                             a2 * np.exp(-t_fit_norm / tau2)) + steady

                ax.plot(t_fit * 1e6, i_fit * 1e6, fit_style, color=fit_color, linewidth=fit_linewidth, alpha=0.9, label="Fit")

                # Green dot at tau₁
                tau1_s = result["tau1_ms"] * 1e-3
                tau1_idx = int(tau1_s / (t_plateau[-1] - t_plateau[0]) * len(t_fit)) if t_plateau[-1] > t_plateau[0] else 0
                if 0 <= tau1_idx < len(t_fit):
                    ax.plot(t_fit[tau1_idx] * 1e6, i_fit[tau1_idx] * 1e6, "o", color="green", markersize=7,
                            markeredgecolor="white", markeredgewidth=0.8, zorder=5,
                            label=f"τ₁={result['tau1_ms']:.1f}ms")

                # Orange dot at tau₂
                if result.get("tau2_ms"):
                    tau2_s = result["tau2_ms"] * 1e-3
                    tau2_idx = int(tau2_s / (t_plateau[-1] - t_plateau[0]) * len(t_fit)) if t_plateau[-1] > t_plateau[0] else 0
                    if 0 <= tau2_idx < len(t_fit):
                        ax.plot(t_fit[tau2_idx] * 1e6, i_fit[tau2_idx] * 1e6, "o", color="orange", markersize=7,
                                markeredgecolor="white", markeredgewidth=0.8, zorder=5,
                                label=f"τ₂={result['tau2_ms']:.1f}ms")

                # Annotation box
                r2 = result.get("r_squared", 0)
                tau1_val = result["tau1_ms"]
                tau2_val = result.get("tau2_ms")
                txt = f"Seg {seg['segment_id']}: {result['model']}\n"
                txt += f"τ₁={tau1_val:.1f}ms"
                if tau2_val:
                    txt += f"  τ₂={tau2_val:.1f}ms"
                txt += f"\nI₀={result.get('initial_current_ua', 0):.1f}µA  I∞={result.get('steady_state_current_ua', 0):.1f}µA"
                txt += f"\nDecay={result.get('decay_pct', 0):.1f}%  R²={r2:.4f}"

                ax.text(0.97, 0.97, txt, transform=ax.transAxes, fontsize=7,
                        verticalalignment="top", horizontalalignment="right",
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.12, edgecolor=color))

    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Current (µA)")
    ax.legend(fontsize=6, loc="lower left", ncol=2)
    v_lvl = seg.get("v_level", 0)
    title = f"V={v_lvl:.2f}V" if v_lvl > 0.01 else "Baseline"
    ax.set_title(f"Segment {seg['segment_id']}: {title} — {seg['n_points']} pts",
                 fontsize=9)


def _plot_segment_overview(
    fig, time_s, current_A, voltage_V, segments: list[dict], segment_results: list[dict],
    plot_cfg=None,
) -> None:
    """Plot each segment in its own subpanel for clear visual inspection (T2 redesign).

    Grid layout:
    - 1 segment: 1×1
    - 2 segments: 1×2
    - 3-4 segments: 2×2
    - 5-6 segments: 3×2
    - 7+ segments: N×2 (auto rows)

    Each subpanel shows one segment's data, fit, tau markers, and annotation.
    """
    cfg = plot_cfg or {}
    layout = cfg.get("segment_overview.layout", "grid")
    ncols = int(cfg.get("segment_overview.ncols", 3))
    import matplotlib.pyplot as plt

    n_seg = len(segments)
    if layout == "grid":
        n_cols = min(ncols, n_seg)
        n_rows = (n_seg + n_cols - 1) // n_cols
    else:
        n_cols = 1
        n_rows = n_seg

    # Recreate figure with proper grid
    fig.clf()
    axes = fig.subplots(n_rows, n_cols, squeeze=False)

    colors = plt.cm.tab10(np.linspace(0, 1, n_seg))

    for seg_i, (seg, result) in enumerate(zip(segments, segment_results)):
        row = seg_i // n_cols
        col = seg_i % n_cols
        ax = axes[row][col]
        c = colors[seg_i]
        _plot_single_segment(ax, time_s, current_A, voltage_V, seg, result, c, plot_cfg=plot_cfg)

    # Hide unused subplots
    total_cells = n_rows * n_cols
    for idx in range(n_seg, total_cells):
        row = idx // n_cols
        col = idx % n_cols
        axes[row][col].set_visible(False)

    fig.subplots_adjust(hspace=0.4, wspace=0.3)


def _print_segment_summary(file_name: str, segments: list[dict], segment_results: list[dict]) -> None:
    """Print per-segment summary with fit results (T2)."""
    from rich.console import Console
    from rich.table import Table

    c = Console()
    c.print(f"\n[bold]STP Decay Analysis:[/bold] {file_name}")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Seg", style="dim", width=4)
    table.add_column("Model", width=14)
    table.add_column("τ₁ (ms)", justify="right", width=10)
    table.add_column("τ₂ (ms)", justify="right", width=10)
    table.add_column("I₀ (µA)", justify="right", width=10)
    table.add_column("I∞ (µA)", justify="right", width=10)
    table.add_column("Decay%", justify="right", width=8)
    table.add_column("R²", justify="right", width=8)
    table.add_column("Points", justify="right", width=6)

    for seg, result in zip(segments, segment_results):
        if "error" in result:
            table.add_row(
                str(seg["segment_id"]), "[red]FAIL[/red]",
                "", "", "", "", "", "", str(seg["n_points"]),
            )
        else:
            tau1 = f"{result.get('tau1_ms', 0):.2f}" if result.get("tau1_ms") else "—"
            tau2 = f"{result.get('tau2_ms', 0):.2f}" if result.get("tau2_ms") else "—"
            init_i = f"{result.get('initial_current_ua', 0):.2f}"
            final_i = f"{result.get('steady_state_current_ua', 0):.2f}"
            decay = f"{result.get('decay_pct', 0):.1f}"
            r2 = f"{result.get('r_squared', 0):.4f}"
            model = result.get("model", "?")
            table.add_row(
                str(seg["segment_id"]), model,
                tau1, tau2, init_i, final_i, decay, r2, str(seg["n_points"]),
            )

    c.print(table)
    c.print(f"  [dim]Total segments: {len(segments)}[/dim]")


def _fit_segment(time_s: np.ndarray, current_A: np.ndarray, seg: dict) -> dict:
    """Fit decay for a single segment."""
    from science_cli.library.pulse.stp import analyze_stp_decay

    s, e = seg["start"], seg["end"]
    n_pts = e - s
    if n_pts < 5:
        return {"error": f"Insufficient data points ({n_pts} < 5)", "model": "skip",
                "n_points": n_pts}
    t_seg = time_s[s:e]
    i_seg = current_A[s:e]
    return analyze_stp_decay(t_seg, i_seg)


# ── Main Handlers ──


def analyze_all(file_path: Path = None, overwrite: bool = False, **kwargs) -> None:
    """Segment-aware STP decay diagnostic (T2).

    For each file:
    1. Detect segments via ``detect_stp_segments()``
    2. Fit each segment via ``analyze_stp_decay()``
    3. Generate overview plot: all segments overlaid with fit lines + tau markers
    4. Print per-segment summary table
    5. Save per-segment metadata to protocol.yaml
    6. Respect ``--overwrite`` flag (T4)
    """
    function_name = kwargs.get("function_name", "analyze_all")
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())

    csv_path = Path(file_path)
    project_root = _get_project_root(csv_path)

    # Resolve plot config from config-studies.yaml + per-file protocol.yaml overrides
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-stp-decay", function_name, filepath=str(csv_path),
    )
    # --show-config support
    if kwargs.get("show_config") or kwargs.get("show-config"):
        import json as _json
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    # T4: Check if already analyzed
    if project_root and not overwrite:
        if _has_extracted_decay(csv_path, project_root):
            from rich.console import Console
            Console().print(
                f"  [yellow]Skipping[/yellow] {csv_path.name} — "
                f"already has extracted_decay metadata. Use --overwrite to re-analyze."
            )
            return

    try:
        time_s, current_A, voltage_V, metadata, wf_voltage = _load_stp_data(csv_path)
    except (ValueError, FileNotFoundError) as e:
        from rich.console import Console
        Console().print(f"[bold red]Error:[/bold red] {e}")
        return

    if len(time_s) < 5:
        from rich.console import Console
        Console().print(f"[yellow]Insufficient data: {csv_path.name}[/yellow]")
        return

    # T1: Detect segments by voltage-plateau boundaries (MeasResult1_value)
    segments = detect_stp_segments(time_s, voltage_array=voltage_V)

    # T2: Fit each segment
    segment_results: list[dict] = []
    for seg in segments:
        result = _fit_segment(time_s, current_A, seg)
        segment_results.append(result)

    # Print per-segment summary
    _print_segment_summary(csv_path.name, segments, segment_results)

    # T2: Overview plot — one subpanel per segment
    n_seg = len(segments)
    figsize_cfg = plot_cfg.get("segment_overview.figsize", [12, 8])
    dpi_cfg = int(plot_cfg.get("segment_overview.dpi", 150))
    fig = plt.figure(figsize=figsize_cfg, dpi=dpi_cfg)
    _plot_segment_overview(fig, time_s, current_A, voltage_V, segments, segment_results, plot_cfg=plot_cfg)

    fig.suptitle(f"STP Decay Overview: {csv_path.name}", fontsize=11, y=0.98)

    _save_plot(fig, csv_path, "stp-decay-diagnostic_overview")

    # T3: Tag with per-segment metadata under analyze.<function_name>.metadata.extracted_decay
    if project_root:
        # Find the step name
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(project_root)
        resolved_step = ""
        for py in paths.list_protocol_yamls():
            import yaml
            with open(py) as f:
                proto_data = yaml.safe_load(f) or {}
            for s in proto_data.get("steps", []):
                step_dir = paths.step_dir(py.stem, s["name"])
                if (step_dir / csv_path.name).exists() or (step_dir / csv_path.name).is_symlink():
                    resolved_step = s["name"]
                    break

        # Build new-format extracted_decay metadata
        extracted_dict: dict = {}
        for i, (seg, seg_result) in enumerate(zip(segments, segment_results), 1):
            s, e = seg["start"], seg["end"]
            extracted_dict[f"seg_{i:03d}"] = {
                "t1_s": _to_native(time_s[s]),
                "v1_v": _to_native(voltage_V[s]),
                "i1_a": _to_native(np.abs(current_A[s])),
                "t2_s": _to_native(time_s[min(e - 1, len(time_s) - 1)]),
                "v2_v": _to_native(voltage_V[min(e - 1, len(time_s) - 1)]),
                "i2_a": _to_native(np.abs(current_A[min(e - 1, len(time_s) - 1)])),
            }
        # Decay params from first successful fit
        for seg_result in segment_results:
            if "error" not in seg_result and seg_result.get("tau1_ms") is not None:
                extracted_dict["decay"] = {
                    "tau_ms": _to_native(seg_result["tau1_ms"]),
                    "r_squared": _to_native(seg_result.get("r_squared", 0)),
                }
                break

        _tag_with_segment_metadata(
            csv_path, project_root, {"extracted_decay": extracted_dict},
            function_name=function_name, step_name=resolved_step,
        )


def analyze_overlay(file_paths: list[Path] = None, **kwargs) -> None:
    """Overlay STP decay curves of [extracted-decay] tagged files.

    Reads all files tagged with ``[extracted-decay]`` and plots their
    decay fit curves on the same axes for cross-file comparison.
    """
    function_name = kwargs.get("function_name", "analyze_overlay")
    from science_cli.library.pulse.stp import analyze_stp_decay
    from science_cli.core.grammar import parse_filename
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())

    if not file_paths:
        from rich.console import Console
        Console().print("[yellow]No files selected for overlay.[/yellow]")
        return

    # Resolve plot config for overlay mode
    plot_cfg = resolve_analysis_plot_config(
        "pulse:pulse-stp-decay", function_name,
    )
    # --show-config support
    if kwargs.get("show_config") or kwargs.get("show-config"):
        import json as _json
        print(f"--- Resolved config for {function_name} ---")
        print(_json.dumps(plot_cfg, indent=2, default=str))
        return

    # Config-driven parameters
    colors_list = plot_cfg.get("colors", ["#CC0000", "#0055CC", "#2EA043", "#CC7700"])
    figsize = plot_cfg.get("figure.figsize", [8, 3.5])
    dpi = int(plot_cfg.get("figure.dpi", 150))
    fit_style = plot_cfg.get("fit.style", "--")
    fit_linewidth = float(plot_cfg.get("fit.linewidth", 1.0))
    legend_loc = plot_cfg.get("legend.loc", "upper right")
    legend_fontsize = int(plot_cfg.get("legend.fontsize", 8))

    # Filter to files tagged with [extracted-decay]
    overlay_data: list[dict] = []
    for fp in file_paths:
        parsed = parse_filename(fp.name)
        if not parsed:
            continue
        remarks = parsed.get("remarks", "")
        if "extracted-decay" not in remarks:
            continue
        try:
            time_s, current_A, voltage_V, _, _ = _load_stp_data(fp)
            result = analyze_stp_decay(time_s, current_A)
            if "error" not in result:
                overlay_data.append({
                    "name": fp.stem,
                    "time_s": time_s,
                    "current_A": current_A,
                    "result": result,
                })
        except (ValueError, FileNotFoundError):
            continue

    if len(overlay_data) < 1:
        from rich.console import Console
        Console().print(
            "[yellow]No files with valid decay fits found for overlay. "
            "Run 'analyze --all' first to tag files with [extracted-decay].[/yellow]"
        )
        return
    if len(overlay_data) < 2:
        from rich.console import Console
        Console().print(
            "[yellow]Need at least 2 tagged files for overlay. "
            "Run 'analyze --all' first to tag files with [extracted-decay].[/yellow]"
        )
        return

    # Plot comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
    colors = plt.cm.Set1(np.linspace(0, 1, len(overlay_data)))
    # Replace colors with config-driven list if enough entries
    if len(colors_list) >= len(overlay_data):
        colors = colors_list[:len(overlay_data)]

    for i, entry in enumerate(overlay_data):
        time_s = entry["time_s"]
        current_A = entry["current_A"]
        result = entry["result"]
        t_us = time_s * 1e6
        i_ua = current_A * 1e6
        c = colors[i]

        # Full decay (left panel)
        ax1.plot(t_us, i_ua, ".", color=c, markersize=1.5, alpha=0.4)

        # Fit line
        t_fit = np.linspace(time_s[0], time_s[-1], 300)
        t_fit_norm = t_fit - time_s[0]
        i_norm = np.abs(current_A)
        steady = result.get("steady_state_current_ua", i_norm[-1]) * 1e-6
        a1 = result.get("a1") or (i_norm[0] - steady)
        tau1 = result.get("tau1_ms", 1)
        if result["model"] == "monoexponential":
            i_fit = a1 * np.exp(-t_fit_norm / tau1) + steady
        else:
            a2 = result.get("a2") or (i_norm[0] - steady) * 0.3
            tau2 = result.get("tau2_ms") or tau1
            i_fit = (a1 * np.exp(-t_fit_norm / tau1) + a2 * np.exp(-t_fit_norm / tau2)) + steady
        i_fit_ua = i_fit * 1e6
        tau = result["tau1_ms"]
        label = f"{entry['name'][:25]} ($\\tau$={tau:.1f})"
        ax1.plot(t_fit * 1e6, i_fit_ua, fit_style, color=c, linewidth=fit_linewidth, label=label, alpha=0.8)

        # Decay zoom (right panel) — normalize time to start of decay
        skip = max(1, len(time_s) // 4)
        t_decay_norm = (time_s[skip:] - time_s[skip]) * 1e6
        i_decay_ua = current_A[skip:] * 1e6
        ax2.plot(t_decay_norm, i_decay_ua, ".", color=c, markersize=2, alpha=0.4)

    ax1.set_xlabel("Time (µs)")
    ax1.set_ylabel("Current (µA)")
    ax1.set_title("Full Decay Overlay", fontsize=10)
    ax1.legend(fontsize=legend_fontsize, loc=legend_loc, ncol=2)

    ax2.set_xlabel("Time (µs) from decay start")
    ax2.set_ylabel("Current (µA)")
    ax2.set_title("Decay Zoom (Aligned)", fontsize=10)

    fig.suptitle("STP Decay Overlay Comparison", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    # Save to first file's results/
    first_path = file_paths[0]
    _save_plot(fig, first_path, "stp-decay-overlay")

    from rich.console import Console
    Console().print(f"[bold green]\u2713[/bold green] Overlay: {len(overlay_data)} curves plotted")
