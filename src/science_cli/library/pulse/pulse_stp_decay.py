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

    Returns (time_s, current_A, voltage_V, metadata_dict) or raises.
    """
    from science_cli.core.data_loader import load_data_file

    df, info = load_data_file(str(file_path), study_name="pulse:pulse-stp-decay")
    cols = info.get("columns", [])
    if "time" not in cols or "current" not in cols:
        raise ValueError(f"STP data must have 'time' and 'current' columns. Got: {cols}")

    time_array = df["time"].values.astype(float)
    current_array = df["current"].values.astype(float) * -1  # current_sign
    voltage_array = df.get("voltage", df.get("MeasResult1_value", np.full_like(time_array, np.nan))).values.astype(float)

    # Remove NaN
    mask = ~(np.isnan(time_array) | np.isnan(current_array))
    return time_array[mask], current_array[mask], voltage_array[mask], info.get("metadata", {})


# ── T1: Segment Detection ──


def detect_stp_segments(time_s: np.ndarray) -> list[dict]:
    """Split STP time data by large gaps (>10x median dt, AND >1 us absolute).

    Args:
        time_s: Time array in seconds.

    Returns:
        List of dicts with keys: segment_id (1-based), start (index), end (index),
        n_points, duration_s.
        Segments with <5 points are excluded.
        High-density files where >90% of gaps are <1 us are NOT split.
    """
    if len(time_s) < 5:
        return [{
            "segment_id": 1, "start": 0, "end": len(time_s),
            "n_points": len(time_s), "duration_s": float(time_s[-1] - time_s[0]),
        }]

    diffs = np.diff(time_s)
    median_dt = float(np.median(diffs)) if len(diffs) > 0 else 0.0
    max_dt = float(np.max(diffs)) if len(diffs) > 0 else 0.0

    # Continuous/high-density guard: if ALL gaps are <10 µs, don't split.
    # Real multi-cycle files have gaps of seconds (11s, 801s).
    # Random jitter or high-density sampling has gaps <10 µs.
    if max_dt < 10e-6:
        return [{
            "segment_id": 1, "start": 0, "end": len(time_s),
            "n_points": len(time_s), "duration_s": float(time_s[-1] - time_s[0]),
        }]

    # Find split points: gaps > 10x median dt AND > 50 µs absolute
    threshold = max(10.0 * median_dt, 50e-6)
    gap_indices = np.where(diffs > threshold)[0]

    if len(gap_indices) == 0:
        return [{
            "segment_id": 1, "start": 0, "end": len(time_s),
            "n_points": len(time_s), "duration_s": float(time_s[-1] - time_s[0]),
        }]

    segments: list[dict] = []
    start = 0
    for gi in gap_indices:
        end = gi + 1
        n_pts = end - start
        if n_pts >= 5:
            segments.append({
                "segment_id": len(segments) + 1,
                "start": start,
                "end": end,
                "n_points": n_pts,
                "duration_s": float(time_s[end - 1] - time_s[start]),
            })
        start = end

    # Last segment
    n_pts = len(time_s) - start
    if n_pts >= 5:
        segments.append({
            "segment_id": len(segments) + 1,
            "start": start,
            "end": len(time_s),
            "n_points": n_pts,
            "duration_s": float(time_s[-1] - time_s[start]),
        })

    return segments


def _has_extracted_decay(file_path: Path, project_root: Path) -> bool:
    """Check if a file already has extracted_decay tags in protocol.yaml (T4).

    Returns True if the file entry's metadata contains ``extracted_decay.segment_001``.
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
                if entry_name == fname:
                    meta = entry.get("metadata", {}) if isinstance(entry, dict) else {}
                    extracted = meta.get("extracted_decay", {})
                    if isinstance(extracted, dict) and extracted.get("segment_001"):
                        return True
                    if isinstance(extracted, bool) and extracted:
                        return True
    return False


def _tag_with_segment_metadata(
    file_path: Path, project_root: Path, segment_results: list[dict],
    step_name: str = "",
) -> None:
    """Tag a file with per-segment decay metadata in protocol.yaml (T3).

    Writes a structured ``extracted_decay`` dict:
    .. code-block:: yaml

        extracted_decay:
          segments: 3
          segment_001:
            model: monoexponential
            tau1_ms: 12.3
            ...
    """
    import yaml
    from science_cli.core.protocol import write_file_metadata
    from science_cli.core.paths import ProjectPaths

    fname = file_path.name
    paths = ProjectPaths(project_root)

    extracted: dict = {"segments": len(segment_results)}
    for i, seg in enumerate(segment_results, 1):
        key = f"segment_{i:03d}"
        entry: dict = {
            "model": seg.get("model", "unknown"),
        }
        if seg.get("tau1_ms") is not None:
            entry["tau1_ms"] = seg["tau1_ms"]
        if seg.get("tau2_ms") is not None:
            entry["tau2_ms"] = seg["tau2_ms"]
        if seg.get("initial_current_ua") is not None:
            entry["initial_current_ua"] = seg["initial_current_ua"]
        if seg.get("steady_state_current_ua") is not None:
            entry["steady_state_current_ua"] = seg["steady_state_current_ua"]
        if seg.get("decay_pct") is not None:
            entry["decay_pct"] = seg["decay_pct"]
        if seg.get("r_squared") is not None:
            entry["r_squared"] = seg["r_squared"]
        extracted[key] = entry

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
        write_file_metadata(resolved_py, resolved_step, fname, {"extracted_decay": extracted})
        from rich.console import Console
        Console().print(
            f"  [green]Tagged:[/green] {fname} -> protocol.yaml "
            f"(extracted_decay.segments={len(segment_results)})"
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


def _plot_full_waveform(ax, time_s, current_A, voltage_V, result) -> None:
    """Plot full STP decay waveform on given axes."""
    t_us = time_s * 1e6
    ax.plot(t_us, current_A * 1e6, ".", color="#CC0000", markersize=2, alpha=0.6, label="I(t) data")

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
        ax.plot(t_fit * 1e6, i_fit * 1e6, "-", color="#CC0000", linewidth=1.5, label=f"Fit: {result['model']}")

    # Voltage on right axis
    ax2 = ax.twinx()
    ax2.plot(t_us, voltage_V, "-", color="#0055CC", linewidth=0.8, alpha=0.7, label="V(t)")
    ax2.set_ylabel("Voltage (V)", color="#0055CC")
    ax2.tick_params(axis="y", colors="#0055CC")

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


def _plot_rise_zoom(ax, time_s, voltage_V, result) -> None:
    """Plot zoomed rise phase on given axes."""
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

    ax.set_xlabel("Time (µs)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Rise Phase (Zoom)", fontsize=10)


def _plot_decay_zoom(ax, time_s, current_A, result) -> None:
    """Plot zoomed decay phase with fit line."""
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
        ax.plot(t_fit * 1e6, i_fit_ua, "-", color="red", linewidth=1.5, label="Fit")

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


def _plot_segment_overview(
    fig, time_s, current_A, voltage_V, segments: list[dict], segment_results: list[dict],
) -> None:
    """Plot all segments overlaid with fit lines, tau markers, and annotation boxes (T2).

    Each segment gets a different color. Fit line is overlaid as a solid line.
    Green dot at tau1, orange dot at tau2 (if biexp).
    Annotation box per segment with model, tau, R².
    """
    import matplotlib.pyplot as plt

    t_us = time_s * 1e6
    i_ua = current_A * 1e6
    colors = plt.cm.tab10(np.linspace(0, 1, len(segments)))

    ax1 = fig.add_subplot(111)

    for seg_i, (seg, result) in enumerate(zip(segments, segment_results)):
        s, e = seg["start"], seg["end"]
        c = colors[seg_i]
        label = f"Seg {seg['segment_id']}"
        if "error" not in result:
            label += f" ({result['model']}, τ={result.get('tau1_ms', 0):.1f}ms)"

        # Scatter
        ax1.plot(t_us[s:e], i_ua[s:e], ".", color=c, markersize=2, alpha=0.5, label=label)

        if "error" not in result and result.get("tau1_ms") is not None:
            t_seg = time_s[s:e]
            t_fit = np.linspace(t_seg[0], t_seg[-1], 300)
            t_fit_norm = t_fit - t_seg[0]
            i_seg = np.abs(current_A[s:e])
            steady = result.get("steady_state_current_ua", i_seg[-1]) * 1e-6
            tau1 = result["tau1_ms"] * 1e-3  # ms -> s
            a1 = result.get("a1") or (i_seg[0] - steady)

            if result["model"] == "monoexponential":
                i_fit = a1 * np.exp(-t_fit_norm / tau1) + steady
            else:
                a2 = result.get("a2") or (i_seg[0] - steady) * 0.3
                tau2 = (result.get("tau2_ms") or tau1 * 1000) * 1e-3
                i_fit = (a1 * np.exp(-t_fit_norm / tau1) + a2 * np.exp(-t_fit_norm / tau2)) + steady

            ax1.plot(t_fit * 1e6, i_fit * 1e6, "-", color=c, linewidth=1.5, alpha=0.8)

            # Marker at tau1 (green dot)
            tau1_s = result["tau1_ms"] * 1e-3
            idx_tau1 = int(tau1_s / (t_seg[-1] - t_seg[0]) * len(t_fit)) if (t_seg[-1] - t_seg[0]) > 0 else 0
            if idx_tau1 < len(t_fit):
                ax1.plot(t_fit[idx_tau1] * 1e6, i_fit[idx_tau1] * 1e6, "o", color="green", markersize=6,
                         markeredgecolor="white", markeredgewidth=0.5)

            # Marker at tau2 (orange dot, if biexp)
            if result.get("tau2_ms"):
                tau2_s = result["tau2_ms"] * 1e-3
                idx_tau2 = int(tau2_s / (t_seg[-1] - t_seg[0]) * len(t_fit)) if (t_seg[-1] - t_seg[0]) > 0 else 0
                if idx_tau2 < len(t_fit):
                    ax1.plot(t_fit[idx_tau2] * 1e6, i_fit[idx_tau2] * 1e6, "o", color="orange", markersize=6,
                             markeredgecolor="white", markeredgewidth=0.5)

            # Annotation box
            r2 = result.get("r_squared", 0)
            tau1_str = f"τ₁={result['tau1_ms']:.1f}ms"
            tau2_str = f" τ₂={result['tau2_ms']:.1f}ms" if result.get("tau2_ms") else ""
            txt = (
                f"Seg {seg['segment_id']}: {result['model']}\n"
                f"{tau1_str}{tau2_str}\n"
                f"R²={r2:.4f}"
            )
            # Position box near the segment data
            seg_center = (s + e) // 2
            x_pos = t_us[min(seg_center + len(t_us) // 20, len(t_us) - 1)]
            y_pos = np.median(i_ua[s:e])
            ax1.text(x_pos, y_pos, txt, fontsize=7,
                     bbox=dict(boxstyle="round,pad=0.3", facecolor=c, alpha=0.15, edgecolor=c))

    ax1.set_xlabel("Time (µs)")
    ax1.set_ylabel("Current (µA)")
    ax1.legend(fontsize=7, loc="upper right", ncol=min(3, len(segments)))
    ax1.set_title(f"STP Decay — Segments Overview ({len(segments)} segments)", fontsize=10)


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
    from science_cli.library.pulse.stp import analyze_stp_decay
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())

    csv_path = Path(file_path)
    project_root = _get_project_root(csv_path)

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
        time_s, current_A, voltage_V, metadata = _load_stp_data(csv_path)
    except (ValueError, FileNotFoundError) as e:
        from rich.console import Console
        Console().print(f"[bold red]Error:[/bold red] {e}")
        return

    if len(time_s) < 5:
        from rich.console import Console
        Console().print(f"[yellow]Insufficient data: {csv_path.name}[/yellow]")
        return

    # T1: Detect segments
    segments = detect_stp_segments(time_s)

    # T2: Fit each segment
    segment_results: list[dict] = []
    for seg in segments:
        result = _fit_segment(time_s, current_A, seg)
        segment_results.append(result)

    # Print per-segment summary
    _print_segment_summary(csv_path.name, segments, segment_results)

    # T2: Overview plot — all segments overlaid
    fig = plt.figure(figsize=(8, 5))
    _plot_segment_overview(fig, time_s, current_A, voltage_V, segments, segment_results)

    fig.suptitle(f"STP Decay Overview: {csv_path.name}", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    _save_plot(fig, csv_path, "stp-decay-diagnostic_overview")

    # T3: Tag with per-segment metadata
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

        _tag_with_segment_metadata(
            csv_path, project_root, segment_results,
            step_name=resolved_step,
        )


def analyze_overlay(file_paths: list[Path] = None, **kwargs) -> None:
    """Overlay STP decay curves of [extracted-decay] tagged files.

    Reads all files tagged with ``[extracted-decay]`` and plots their
    decay fit curves on the same axes for cross-file comparison.
    """
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
            time_s, current_A, voltage_V, _ = _load_stp_data(fp)
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
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.5))
    colors = plt.cm.Set1(np.linspace(0, 1, len(overlay_data)))

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
        ax1.plot(t_fit * 1e6, i_fit_ua, "-", color=c, linewidth=1.2, label=label, alpha=0.8)

        # Decay zoom (right panel) — normalize time to start of decay
        skip = max(1, len(time_s) // 4)
        t_decay_norm = (time_s[skip:] - time_s[skip]) * 1e6
        i_decay_ua = current_A[skip:] * 1e6
        ax2.plot(t_decay_norm, i_decay_ua, ".", color=c, markersize=2, alpha=0.4)

    ax1.set_xlabel("Time (µs)")
    ax1.set_ylabel("Current (µA)")
    ax1.set_title("Full Decay Overlay", fontsize=10)
    ax1.legend(fontsize=6, loc="upper right", ncol=2)

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
