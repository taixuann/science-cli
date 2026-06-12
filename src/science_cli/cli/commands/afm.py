"""afm command handler — AFM/SPM image listing, info, plotting, analysis, and export."""

from pathlib import Path

import numpy as np
import yaml
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag

console = Console()

_AFM_EXTENSIONS = {".gwy", ".spm", ".ibw", ".jpk", ".stp", ".top"}


def _parse_flags(args: list) -> tuple:
    positional = []
    flags = {}
    i = 0
    while i < len(args):
        a = args[i]
        if is_flag(a):
            key = a.lstrip("-")
            if i + 1 < len(args) and not is_flag(args[i + 1]):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            positional.append(a)
            i += 1
    return positional, flags


def _resolve_file(name: str) -> str:
    path = Path(name)
    if path.exists():
        return str(path)
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        raw_dir = proj / "data" / "raw"
        full = raw_dir / name
        if full.exists():
            return str(full)
        for f in raw_dir.iterdir():
            if name.lower() in f.name.lower():
                return str(f)
    return ""


def _get_project_raw_dir() -> Path:
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        raw_dir = proj / "data" / "raw"
        if raw_dir.exists():
            return raw_dir
    return Path()


def _get_afm_files(raw_dir: Path) -> list[Path]:
    return sorted(
        f for f in raw_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _AFM_EXTENSIONS
    )


def _afm_fzf_pick_multi(prompt: str = "Select AFM file(s)") -> list[str]:
    raw_dir = _get_project_raw_dir()
    if not raw_dir:
        console.print("[yellow]No project open.[/yellow]")
        return []

    files = _get_afm_files(raw_dir)
    if not files:
        console.print("[yellow]No AFM files found.[/yellow]")
        return []

    from science_cli.core.fzf_utils import fzf_select
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    proj = get_current_project_path()
    paths = ProjectPaths(proj)
    file_step_map: dict[str, tuple[str, str, str]] = {}
    for py in paths.list_protocol_yamls():
        pname = py.stem
        with open(py) as f:
            proto_data = __import__("yaml").safe_load(f) or {}
        for s in proto_data.get("steps", []):
            tech = s.get("technique", "").lower()
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                file_step_map[fname] = (pname, s["name"], tech)

    sess = load_session()
    active_proto = sess.get("last_protocol", "")

    display_files = []
    show_proto = True
    if active_proto:
        active_protocol_files = [
            f for f in files
            if f.name in file_step_map
            and file_step_map[f.name][0] == active_proto
            and file_step_map[f.name][2].startswith("afm-")
        ]
        if active_protocol_files:
            display_files = active_protocol_files
            show_proto = False
        else:
            display_files = files
            show_proto = True
    else:
        display_files = files
        show_proto = True

    from science_cli.core.fzf_utils import build_fzf_display
    display_items = []
    for f in display_files:
        name = f.name
        size_kb = f.stat().st_size / 1024
        tag = f"[{size_kb:>7.1f} KB]"
        if name in file_step_map:
            proto, step, tech = file_step_map[name]
            base = build_fzf_display(proto, step, "", show_protocol=show_proto)
            display_items.append(f"{base} {tag} {name}")
        else:
            display_items.append(f"{tag} {name}")

    selected = fzf_select(
        items=display_items,
        prompt=prompt,
        multi=True,
        preview=f"head -n 5 {raw_dir}/$(echo {{}} | awk '{{print $NF}}')",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        return []

    selected = [s.split()[-1] for s in selected]
    return [str(raw_dir / s) for s in selected]


def afm_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("afm")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "ls":
        _afm_ls(sub_args)
    elif sub == "info":
        _afm_info(sub_args)
    elif sub == "plot":
        _afm_plot(sub_args)
    elif sub == "analyze":
        _afm_analyze(sub_args)
    elif sub == "export":
        _afm_export(sub_args)
    elif sub == "open":
        _afm_open(sub_args)
    else:
        console.print(f"[yellow]Unknown afm subcommand: {sub}[/yellow]")
        show_command_help("afm")


def _afm_ls(args: list) -> None:
    pos, flags = _parse_flags(args)
    raw_dir = _get_project_raw_dir()

    if not raw_dir:
        console.print("[yellow]No project open. Open a project first.[/yellow]")
        return

    files = _get_afm_files(raw_dir)
    if not files:
        console.print("[yellow]No AFM files found.[/yellow]")
        return

    from science_cli.core.technique import detect_technique, get_technique_label

    table = Table(title="AFM/SPM Files", border_style="cyan")
    table.add_column("File", style="bold white")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Format", style="yellow")
    table.add_column("Path", style="dim")

    for f in files:
        size = f.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        ext = f.suffix.lower().lstrip(".")
        tech = detect_technique(f.name)
        label = get_technique_label(tech) if tech else ext.upper()
        table.add_row(f.name, size_str, label, str(f.parent))

    console.print(table)


def _afm_info(args: list) -> None:
    pos, flags = _parse_flags(args)

    if not pos:
        files = _afm_fzf_pick_multi("Select AFM file(s) for info")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in files:
        _do_afm_info(filepath)


def _do_afm_info(filepath: str) -> None:
    from science_cli.library.afm.loader import list_channels, load_afm

    p = Path(filepath)

    try:
        channels = list_channels(str(p))
        data = load_afm(str(p))
    except ImportError:
        console.print("[red]AFMReader is not installed. Run: pip install AFMReader>=0.0.7[/red]")
        return
    except Exception as e:
        console.print(f"[red]Failed to load {p.name}: {e}[/red]")
        return

    from science_cli.core.technique import detect_technique, get_technique_label
    tech = detect_technique(p.name)
    label = get_technique_label(tech) if tech else "Unknown"

    table = Table(title=f"AFM File Info: {p.name}", border_style="cyan", show_lines=True)
    table.add_column("Property", style="bold white")
    table.add_column("Value", style="dim")

    table.add_row("File", str(p))
    table.add_row("Format", p.suffix.lower())
    table.add_row("Technique", label)
    table.add_row("Size", f"{p.stat().st_size / 1024:.1f} KB")
    table.add_row("Pixel calibration", f"{data.pixel_to_nm:.4f} nm/pixel")

    img_shape = data.image.shape
    table.add_row("Image dimensions", f"{img_shape[0]} × {img_shape[1]} px")
    if len(img_shape) == 2:
        size_nm_x = img_shape[1] * data.pixel_to_nm
        size_nm_y = img_shape[0] * data.pixel_to_nm
        table.add_row("Scan size", f"{size_nm_x:.1f} × {size_nm_y:.1f} nm")

    table.add_row("Channels", ", ".join(channels))
    table.add_row("Active channel", channels[0] if channels else "N/A")
    table.add_row("Metadata keys", str(len(data.metadata)))

    console.print(table)


def _afm_plot(args: list) -> None:
    pos, flags = _parse_flags(args)
    cmap = flags.get("cmap", "viridis")

    if not pos:
        selected_files = _afm_fzf_pick_multi("Select AFM file(s) to plot")
        if not selected_files:
            return
        resolved = selected_files
    else:
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in resolved:
        _do_afm_plot(filepath, cmap, flags)


def _do_afm_plot(filepath: str, cmap: str, flags: dict) -> None:
    import matplotlib.pyplot as plt

    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    p = Path(filepath)

    try:
        from science_cli.library.afm import load_afm
        data = load_afm(str(p))
    except ImportError:
        console.print("[red]AFMReader is not installed. Run: pip install AFMReader>=0.0.7[/red]")
        return
    except Exception as e:
        console.print(f"[red]Failed to load {p.name}: {e}[/red]")
        return

    from science_cli.plot.afm import plot_afm_image

    title = flags.get("title", f"{p.stem}")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    plot_afm_image(data.image, data.pixel_to_nm, cmap=cmap, title=title, ax=ax1)

    ax1.set_aspect("equal")

    # Height distribution on the right
    from science_cli.library.afm.analyze import height_distribution
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


def _afm_analyze(args: list) -> None:
    pos, flags = _parse_flags(args)

    if not pos:
        files = _afm_fzf_pick_multi("Select AFM file(s) for analysis")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in files:
        _do_afm_analyze(filepath, flags)


def _do_afm_analyze(filepath: str, flags: dict) -> None:
    from science_cli.library.afm import (
        compute_roughness,
        height_distribution,
        line_profile,
        load_afm,
    )

    p = Path(filepath)

    try:
        data = load_afm(str(p))
    except ImportError:
        console.print("[red]AFMReader is not installed. Run: pip install AFMReader>=0.0.7[/red]")
        return
    except Exception as e:
        console.print(f"[red]Failed to load {p.name}: {e}[/red]")
        return

    img = data.image
    px_to_nm = data.pixel_to_nm

    console.print(f"\n[bold]AFM Analysis: {p.name}[/bold]")
    console.print(f"  Image: {img.shape[0]}×{img.shape[1]} px, {px_to_nm:.4f} nm/px")
    console.print(f"  Scan size: {img.shape[1] * px_to_nm:.1f}×{img.shape[0] * px_to_nm:.1f} nm")
    console.print(f"  Channel: {data.channels[0] if data.channels else 'N/A'}")
    console.print()

    # Roughness
    console.print("[bold]Surface Roughness[/bold]")
    roughness = compute_roughness(img, px_to_nm)
    if "error" in roughness:
        console.print(f"  [red]{roughness['error']}[/red]")
    else:
        rtable = Table(border_style="cyan", show_header=False)
        rtable.add_column("Parameter", style="bold white")
        rtable.add_column("Value", style="dim")
        rtable.add_row("Ra (arithmetic)", f"{roughness['Ra_nm']:.4f} nm")
        rtable.add_row("Rq (RMS)", f"{roughness['Rq_nm']:.4f} nm")
        rtable.add_row("Rmax (peak-valley)", f"{roughness['Rmax_nm']:.4f} nm")
        rtable.add_row("Rsk (skewness)", f"{roughness['Rsk']:.4f}")
        rtable.add_row("Rku (kurtosis)", f"{roughness['Rku']:.4f}")
        rtable.add_row("Sdr (area ratio)", f"{roughness['Sdr']:.2f}%")
        rtable.add_row("Valid pixels", str(roughness["n_pixels"]))
        console.print(rtable)

    # Height distribution
    console.print()
    console.print("[bold]Height Distribution[/bold]")
    hist, bin_edges = height_distribution(img, bins=100)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    peak_idx = int(np.argmax(hist))
    console.print(f"  Modal height: {bin_centers[peak_idx]:.4f} nm")
    console.print(f"  Height range: {bin_edges[0]:.4f} to {bin_edges[-1]:.4f} nm")

    # Line profile (center cross)
    h, w = img.shape
    center_r, center_c = h // 2, w // 2
    console.print()
    console.print("[bold]Line Profile (center cross)[/bold]")
    console.print(f"  Horizontal: (row={center_r}, col=0) → (row={center_r}, col={w - 1})")
    console.print(f"  Vertical:   (row=0, col={center_c}) → (row={h - 1}, col={center_c})")

    dist_h, height_h = line_profile(img, (center_r, 0), (center_r, w - 1))
    dist_v, height_v = line_profile(img, (0, center_c), (h - 1, center_c))

    console.print(f"  Horizontal range: {float(np.nanmin(height_h)):.4f} to {float(np.nanmax(height_h)):.4f} nm")
    console.print(f"  Vertical range:   {float(np.nanmin(height_v)):.4f} to {float(np.nanmax(height_v)):.4f} nm")

    export = flags.get("export") or flags.get("output") or flags.get("name")
    if export:
        base = Path(export)
        if not base.suffix:
            base = base.with_suffix(".csv")

        import pandas as pd

        roughness_df = pd.DataFrame([roughness])
        roughness_csv = base.parent / f"{base.stem}_roughness.csv"
        roughness_df.to_csv(roughness_csv, index=False)
        console.print(f"[green]✓[/green] Roughness → {roughness_csv}")

        hist_df = pd.DataFrame({"bin_center": bin_centers, "count": hist})
        hist_csv = base.parent / f"{base.stem}_height_distribution.csv"
        hist_df.to_csv(hist_csv, index=False)
        console.print(f"[green]✓[/green] Height distribution → {hist_csv}")

        profile_df = pd.DataFrame({
            "horizontal_distance_px": dist_h,
            "horizontal_height_nm": height_h,
            "vertical_distance_px": dist_v,
            "vertical_height_nm": height_v,
        })
        profile_csv = base.parent / f"{base.stem}_line_profiles.csv"
        profile_df.to_csv(profile_csv, index=False)
        console.print(f"[green]✓[/green] Line profiles → {profile_csv}")

    # Additional analysis flags
    if flags.get("psd"):
        from science_cli.library.afm.analyze import compute_psd
        freq, power = compute_psd(img, px_to_nm)
        console.print("\n[bold]Power Spectral Density[/bold]")
        console.print(f"  Frequency range: {float(freq[1]):.6f} to {float(freq[-1]):.6f} nm⁻¹")


def _afm_export(args: list) -> None:
    pos, flags = _parse_flags(args)
    fmt = flags.get("format", flags.get("output", flags.get("o", ""))).lower()
    channel = flags.get("channel", flags.get("c", ""))

    if not pos:
        files = _afm_fzf_pick_multi("Select AFM file(s) to export")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in files:
        _do_afm_export(filepath, fmt, channel, flags)


def _do_afm_export(filepath: str, fmt: str, channel: str, flags: dict) -> None:
    from science_cli.library.afm import load_afm

    p = Path(filepath)

    try:
        data = load_afm(str(p), channel=channel or None)
    except ImportError:
        console.print("[red]AFMReader is not installed. Run: pip install AFMReader>=0.0.7[/red]")
        return
    except Exception as e:
        console.print(f"[red]Failed to load {p.name}: {e}[/red]")
        return

    # Determine output path
    out_dir = Path(flags.get("outdir", "")) if flags.get("outdir") else p.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = p.stem
    suffix = flags.get("suffix", "")
    if suffix:
        stem = f"{stem}{suffix}"

    channel_tag = f"_{channel}" if channel else ""

    if not fmt or fmt in ("png", "img", "image"):
        import matplotlib.pyplot as plt

        from science_cli.plot.afm import plot_afm_image
        fig, ax = plt.subplots(figsize=(6, 5))
        plot_afm_image(data.image, data.pixel_to_nm, cmap=flags.get("cmap", "viridis"), ax=ax)
        png_path = out_dir / f"{stem}{channel_tag}.png"
        fig.savefig(png_path, dpi=int(flags.get("dpi", 300)), bbox_inches="tight")
        plt.close(fig)
        console.print(f"[green]✓[/green] PNG → {png_path}")

    elif fmt in ("csv",):
        import pandas as pd
        img = data.image
        rows = []
        for r in range(img.shape[0]):
            for c in range(img.shape[1]):
                rows.append({"row": r, "col": c, "height_nm": float(img[r, c])})
        df = pd.DataFrame(rows)
        csv_path = out_dir / f"{stem}{channel_tag}.csv"
        df.to_csv(csv_path, index=False)
        console.print(f"[green]✓[/green] CSV → {csv_path}")

    elif fmt in ("npy", "npz"):
        npy_path = out_dir / f"{stem}{channel_tag}.npy"
        np.save(str(npy_path), data.image)
        console.print(f"[green]✓[/green] NPY → {npy_path}")

    else:
        console.print(f"[red]Unknown export format: '{fmt}'. Use: png, csv, or npy.[/red]")


def _build_file_step_map() -> dict[str, tuple[str, str]]:
    """Build a mapping of filename → (protocol_name, step_name)."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths

    proj = get_current_project_path()
    if not proj:
        return {}

    paths = ProjectPaths(proj)
    mapping: dict[str, tuple[str, str]] = {}

    for py in paths.list_protocol_yamls():
        pname = py.stem
        try:
            with open(py) as f:
                proto_data = yaml.safe_load(f) or {}
        except Exception:
            continue
        for s in proto_data.get("steps", []):
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                mapping[fname] = (pname, s["name"])

    return mapping


def _resolve_step_dir(raw_path: str, step_map: dict | None = None) -> Path | None:
    """Resolve the step directory for a raw AFM file.

    The step directory (protocol/<name>/<step>) holds symlinks pointing
    to the raw file in data/raw/.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths

    fname = Path(raw_path).name
    if step_map is None:
        step_map = _build_file_step_map()

    entry = step_map.get(fname)
    if not entry:
        return None

    pname, sname = entry
    proj = get_current_project_path()
    if not proj:
        return None

    return ProjectPaths(proj).step_dir(pname, sname)


def _read_afm_analysis(yaml_path: Path) -> dict:
    """Read existing afm_analysis.yaml, return data dict."""
    if not yaml_path.exists():
        return {"files": []}

    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            data = {"files": []}
        if "files" not in data:
            data["files"] = []
        return data
    except Exception:
        console.print(f"[yellow]Warning: Could not parse {yaml_path}, starting fresh.[/yellow]")
        return {"files": []}


def _write_afm_analysis(yaml_path: Path, data: dict) -> None:
    """Write afm_analysis.yaml with header comment."""
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w") as f:
        f.write("# afm_analysis.yaml — auto-generated by afm open\n")
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _afm_open(args: list) -> None:
    import shutil
    import subprocess

    gwyddion = shutil.which("gwyddion") or "/opt/homebrew/bin/gwyddion"
    if not Path(gwyddion).exists():
        console.print("[red]Gwyddion not found. Install it: brew install gwyddion[/red]")
        return

    files = _afm_fzf_pick_multi("Select AFM .ibw file to open in Gwyddion")
    if not files:
        return

    ibw_files = [f for f in files if Path(f).suffix.lower() == ".ibw"]
    if not ibw_files:
        console.print("[yellow]No .ibw file selected. Please select a .ibw file.[/yellow]")
        return

    raw_path = ibw_files[0]
    fname = Path(raw_path).name

    step_map = _build_file_step_map()
    step_dir = _resolve_step_dir(raw_path, step_map)

    if not step_dir:
        console.print("[red]Could not determine step directory. Is this file assigned to an AFM step?[/red]")
        console.print("[yellow]Tip: run 'add -m data' to assign files to a protocol step.[/yellow]")
        return

    console.print(f"  Opening [cyan]{fname}[/cyan] in Gwyddion...")
    subprocess.Popen([gwyddion, raw_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    console.print(f"\n[bold]── AFM Analysis: {fname} ──[/bold]")
    console.print("[dim](file opened in Gwyddion — inspect it, then enter values below)[/dim]\n")

    yaml_path = step_dir / "afm_analysis.yaml"
    existing_data = _read_afm_analysis(yaml_path)
    existing_files = existing_data.get("files", [])

    existing_entry = next((e for e in existing_files if e.get("name") == fname), None)

    def _prompt_float(label: str, key: str) -> float | None:
        val = existing_entry.get(key) if existing_entry else None
        if val is not None:
            raw = Prompt.ask(f"  {label}", default=f"{val}")
            return float(raw)
        raw = Prompt.ask(f"  {label}")
        return float(raw) if raw.strip() else None

    def _prompt_str(label: str, key: str, hint: str | None = None) -> str:
        val = existing_entry.get(key) if existing_entry else hint
        if val:
            return Prompt.ask(f"  {label}", default=val)
        return Prompt.ask(f"  {label}") or ""

    thick = _prompt_float("Thickness (nm)", "thick_nm")
    sa = _prompt_float("Sa — surface roughness (nm)", "sa_nm")
    sq = _prompt_float("Sq — root mean square (nm)", "sq_nm")
    material = _prompt_str("Material", "material", hint="ito")

    new_entry = {"name": fname}
    if thick is not None:
        new_entry["thick_nm"] = thick
    if sa is not None:
        new_entry["sa_nm"] = sa
    if sq is not None:
        new_entry["sq_nm"] = sq
    if material:
        new_entry["material"] = material

    if existing_entry:
        existing_entry.update(new_entry)
    else:
        existing_files.append(new_entry)

    existing_data["files"] = existing_files
    _write_afm_analysis(yaml_path, existing_data)
    console.print(f"\n[green]✓[/green] Saved to {yaml_path}")
