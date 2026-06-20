"""STP (Short-Term Plasticity) decay plotting."""
from pathlib import Path


def _load_waveform_def(filepath: str) -> tuple | None:
    """Load Waveform1_time/voltage from Keysight STP file DataName block."""
    import numpy as np
    import pandas as pd

    from science_cli.core.config import _DEFAULT_PULSE_HEADER_LINES
    path = Path(filepath)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, skiprows=_DEFAULT_PULSE_HEADER_LINES, encoding="utf-8",
                         engine="python", on_bad_lines="skip", dtype=str)
        df.columns = [c.strip() for c in df.columns]
        if "DataName" in df.columns:
            df = df.drop(columns=["DataName"])
        df.columns = [c.strip() for c in df.columns]
        wf_time = df.get("Waveform1_time")
        wf_volt = df.get("Waveform1_voltage")
        if wf_time is None or wf_volt is None:
            return None
        def _to_float(s):
            try:
                return float(str(s).strip())
            except (ValueError, TypeError):
                return float("nan")
        t_list = []
        v_list = []
        for i in range(len(wf_time)):
            tv = _to_float(wf_time.iloc[i])
            vv = _to_float(wf_volt.iloc[i])
            if not np.isnan(tv) and not np.isnan(vv):
                if tv > 1.0 or abs(vv) > 10.0:
                    continue
                if not t_list or abs(tv - t_list[-1]) > 1e-12 or abs(vv - v_list[-1]) > 1e-12:
                    t_list.append(tv)
                    v_list.append(vv)
        t, v = np.array(t_list), np.array(v_list)
        if len(t) < 4:
            return None
        return t, v
    except Exception:
        return None


def _extract_waveform_params(t, v) -> dict:
    """Extract pulse parameters from Waveform1 definition."""
    import numpy as np
    v_set = float(np.max(v))
    v_mid = v[(v > v_set * 0.08) & (v < v_set * 0.6)]
    v_read = float(np.median(v_mid)) if len(v_mid) > 0 else 0.0
    t_us = t * 1e6

    read_band = (np.abs(v - v_read) < (v_set - v_read) * 0.3) | (v == v_read)
    set_band = v >= v_set * 0.85

    read_idx = np.where(read_band)[0]
    set_idx = np.where(set_band)[0]

    if len(set_idx) < 2:
        return {"v_set": v_set, "v_read": v_read}

    set_gaps = np.where(np.diff(set_idx) > 2)[0]
    set_blocks = np.split(set_idx, set_gaps + 1)
    set_blocks = [b for b in set_blocks if len(b) >= 2]

    if not set_blocks:
        return {"v_set": v_set, "v_read": v_read}

    cycle_params = []
    for sb in set_blocks:
        s_start_idx = sb[0]
        s_end_idx = sb[-1]
        reads_before = read_idx[read_idx < s_start_idx]
        if len(reads_before) == 0:
            continue
        r_before = reads_before[-1]
        reads_after = read_idx[read_idx > s_end_idx]
        rise = float(t_us[s_start_idx] - t_us[r_before])
        set_w = float(t_us[s_end_idx] - t_us[s_start_idx])
        if len(reads_after) > 0:
            r_after = reads_after[0]
            fall = float(t_us[r_after] - t_us[s_end_idx])
            seg_v = v[r_after:]
            seg_t = t_us[r_after:]
            to_init = np.where(seg_v < v_read * 0.3)[0]
            if len(to_init) > 0:
                read_w = float(seg_t[to_init[0]] - t_us[r_after])
            else:
                read_w = float(seg_t[-1] - t_us[r_after])
        else:
            fall = 0.0
            read_w = 0.0
        cycle_params.append({"rise_us": rise, "set_width_us": set_w,
                             "fall_us": fall, "read_width_us": read_w})

    if not cycle_params:
        return {"v_set": v_set, "v_read": v_read}

    use_cycles = cycle_params[min(1, len(cycle_params)-1):]
    rise_us = float(np.mean([c["rise_us"] for c in use_cycles]))
    set_w = float(np.mean([c["set_width_us"] for c in use_cycles]))
    fall_us = float(np.mean([c["fall_us"] for c in use_cycles]))
    read_w = float(np.mean([c["read_width_us"] for c in use_cycles]))

    if len(set_blocks) >= 2:
        starts = [t_us[sb[0]] for sb in set_blocks]
        gaps = np.diff(starts)
        gaps = gaps[(gaps > 1) & (gaps < 500)]
        cycle_w = float(np.mean(gaps)) if len(gaps) > 0 else float(t_us[-1] - t_us[0])
    else:
        cycle_w = float(t_us[-1] - t_us[0])

    n_repeats = max(1, len(set_blocks))
    return {"v_set": v_set, "v_read": v_read, "rise_us": rise_us, "fall_us": fall_us,
            "set_width_us": set_w, "read_width_us": read_w,
            "cycle_width_us": cycle_w, "n_repeats": n_repeats}


def _plot_stp_decay(filepath: str, flags: dict) -> None:
    """STP-decay plot: twin Y-axis — voltage (blue, left) and current×(-1) (red, right) vs Time."""
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
        df, info = load_data_file(filepath, technique="pulse-stp")
    except Exception as e:
        console.print(f"[red]Failed to load STP data: {e}[/red]")
        return

    apply_theme(get_active_theme())
    plot_cfg = resolve_plot_config("pulse:pulse-stp-decay")
    t = df.get("time", df.get("Time"))
    v = df.get("voltage", df.get("MeasResult1_value"))
    i = df.get("current", df.get("MeasResult2_value"))
    if t is None or v is None or i is None:
        console.print("[red]STP data missing Time/MeasResult columns.[/red]")
        return

    t = t.values.astype(float)
    v = v.values.astype(float)
    i = i.values.astype(float) * -1
    mask = ~(np.isnan(t) | np.isnan(v) | np.isnan(i))
    t, v, i = t[mask], v[mask], i[mask]
    
    # Filter out pre-pulse region (V < 0.05V) to avoid line at origin
    v_threshold = 0.05
    sig_mask = v > v_threshold
    if sig_mask.any():
        t, v, i = t[sig_mask], v[sig_mask], i[sig_mask]
    
    t_us = t * 1e6

    dt = np.diff(t_us)
    wrap_indices = list(np.where(dt < 0)[0] + 1)
    segments = []
    start = 0
    for w in wrap_indices:
        segments.append((start, w))
        start = w
    segments.append((start, len(t_us)))

    has_describe = flags.get("describe")
    base_size = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", mpl.rcParams.get("figure.figsize", (3.46, 2.75))))
    if has_describe:
        fig = plt.figure(figsize=(base_size[0] * 2.2, base_size[1] * 1.2))
        gs = fig.add_gridspec(1, 2, width_ratios=[0.65, 0.35], wspace=0.35)
        ax1 = fig.add_subplot(gs[0, 0])
    else:
        fig, ax1 = plt.subplots(figsize=base_size)

    color_v = flags.get("color_v", plot_cfg.get("series.voltage.color", "tab:blue"))
    ax1.set_xlabel("Time (µs)")
    ax1.set_ylabel("Voltage (V)", color=color_v)
    ax1.tick_params(axis="y", labelcolor=color_v)

    ax2 = ax1.twinx()
    color_i = flags.get("color_i", plot_cfg.get("series.current.color", "tab:red"))
    ax2.set_ylabel("Current (A)", color=color_i)
    ax2.tick_params(axis="y", labelcolor=color_i)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("black")

    lw = float(plot_cfg.get("lines.linewidth", 1.0))
    for s_start, s_end in segments:
        ax1.plot(t_us[s_start:s_end], v[s_start:s_end], color=color_v, linewidth=lw)
        ax2.plot(t_us[s_start:s_end], i[s_start:s_end], color=color_i, linewidth=lw)

    if has_describe:
        wf = _load_waveform_def(filepath)
        if wf is not None:
            wf_params = _extract_waveform_params(wf[0], wf[1])
            v_set = wf_params["v_set"]
            v_read = wf_params["v_read"]
            rise_us = wf_params["rise_us"]
            fall_us = wf_params["fall_us"]
            set_width = wf_params["set_width_us"]
            read_width = wf_params["read_width_us"]
            cycle_width = wf_params["cycle_width_us"]
            n_repeats = wf_params["n_repeats"]
            n_pts = len(t)
            i_max = float(np.max(np.abs(i)))
            i_steady = float(np.mean(i[-10:]))
        else:
            s_long, e_long = segments[0]
            v_seg = v[s_long:e_long]
            t_seg = t_us[s_long:e_long]
            v_set = float(np.max(v_seg))
            v_mid = v_seg[(v_seg > v_set * 0.1) & (v_seg < v_set * 0.7)]
            v_read = float(np.median(v_mid)) if len(v_mid) > 0 else 0.0
            read_band = np.abs(v_seg - v_read) < (v_set - v_read) * 0.3
            set_band = v_seg >= v_set * 0.85
            read_idx = np.where(read_band)[0]
            set_idx = np.where(set_band)[0]
            if len(set_idx) > 0:
                set_gaps = np.where(np.diff(set_idx) > 2)[0]
                set_blocks = np.split(set_idx, set_gaps + 1)
                longest_set = max(set_blocks, key=len)
                set_width = float(t_seg[longest_set[-1]] - t_seg[longest_set[0]])
            else:
                set_width = 0.0
            if len(read_idx) > 0:
                read_gaps = np.where(np.diff(read_idx) > 2)[0]
                read_blocks = np.split(read_idx, read_gaps + 1)
                longest_read = max(read_blocks, key=len)
                read_width = float(t_seg[longest_read[-1]] - t_seg[longest_read[0]])
            else:
                read_width = 0.0
            rise_us = 0.0
            fall_us = 0.0
            cycle_width = float(t_seg[-1] - t_seg[0])
            n_repeats = len(segments)
            n_pts = len(t)
            i_max = float(np.max(np.abs(i)))
            i_steady = float(np.mean(i[-10:])) if len(i) > 10 else 0.0

        console.print("\n[bold]STP Pulse Parameters[/bold]")
        console.print(f"  Repeats:       {n_repeats}")
        console.print(f"  Cycle width:   {cycle_width:.0f} µs")
        console.print(f"  V_set:         {v_set:.3f} V  (width: {set_width:.0f} µs)")
        console.print(f"  V_read:        {v_read:.3f} V  (width: {read_width:.0f} µs)")
        console.print(f"  Rise:          {rise_us:.1f} µs  (read->set)")
        console.print(f"  Fall:          {fall_us:.1f} µs  (set->read)")
        console.print(f"  Max current:   {i_max:.6f} A")
        console.print(f"  Data points:   {n_pts}")

        ax_text = fig.add_subplot(gs[0, 1])
        ax_text.axis("off")
        ax_text.set_xlim(0, 1)
        ax_text.set_ylim(0, 1)
        panel_lines = [
            ("STP Pulse Parameters", True), ("", False),
            ("Repeats", f"{n_repeats}"), ("Cycle", f"{cycle_width:.0f} µs"),
            ("", False),
            ("V_set", f"{v_set:.3f} V"), ("Set width", f"{set_width:.0f} µs"),
            ("V_read", f"{v_read:.3f} V"), ("Read width", f"{read_width:.0f} µs"),
            ("", False),
            ("Rise (read->set)", f"{rise_us:.1f} µs"),
            ("Fall (set->read)", f"{fall_us:.1f} µs"),
            ("", False),
            ("Max current", f"{i_max:.6f} A"),
            ("Steady ΔI", f"{i_steady:.6f} A"),
            ("", False),
            ("Data points", f"{n_pts}"),
        ]
        y_pos = 0.95
        step_size = 0.055 if len(panel_lines) < 24 else 0.045
        for label, value in panel_lines:
            if label == "STP Pulse Parameters":
                ax_text.text(0.08, y_pos, label, fontsize=10, fontweight="bold",
                           transform=ax_text.transAxes,
                           bbox=dict(boxstyle="round,pad=0.4", facecolor="lightsteelblue", edgecolor="gray"))
            elif not label:
                pass
            elif value:
                ax_text.text(0.08, y_pos, label, fontsize=8, color="gray",
                           transform=ax_text.transAxes)
                ax_text.text(0.55, y_pos, value, fontsize=8, fontweight="bold",
                           transform=ax_text.transAxes,
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="lightgray"))
            else:
                ax_text.text(0.08, y_pos, label, fontsize=8, color="gray",
                           transform=ax_text.transAxes)
            y_pos -= step_size

    from science_cli.plot.base import apply_figure_kw
    apply_figure_kw(ax1, flags, Path(filepath).stem)

    out_dir = _get_results_dir(filepath)
    out_name = flags.get("n") or flags.get("name", f"stp-decay_{Path(filepath).stem}.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", plot_cfg.get("savefig.dpi", mpl.rcParams.get("savefig.dpi", 600))))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] STP plot saved: {save_path}")


def _overlay_stp_decay(files: list, flags: dict) -> None:
    """Overlay STP decays — 1×2 grid: left voltage, right current."""
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
    plot_cfg = resolve_plot_config("pulse:pulse-stp-decay")
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [entry["color"] for entry in cycle]

    fig, (ax_v, ax_i) = plt.subplots(1, 2, figsize=tuple(plot_cfg.get("figure.figsize", (7, 3))))
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for idx, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="pulse-stp")
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
        ax_v.plot(t_us, v_arr, color=color, linewidth=float(plot_cfg.get("lines.linewidth", 1.0)), label=label)
        ax_i.plot(t_us, i_arr, color=color, linewidth=float(plot_cfg.get("lines.linewidth", 1.0)), label=label)

    ax_v.set_xlabel("Time (µs)")
    ax_v.set_ylabel("Voltage (V)")
    ax_i.set_xlabel("Time (µs)")
    ax_i.set_ylabel("Current (A)")
    ax_v.legend()
    ax_i.legend()
    fig.tight_layout()

    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "stp-decay_overlay.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", plot_cfg.get("savefig.dpi", mpl.rcParams.get("savefig.dpi", 600))))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] STP overlay saved: {save_path}")
