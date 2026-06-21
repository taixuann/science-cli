"""Study plotter registry — maps study names to their plot/overlay functions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from science_cli.plot.generic import _overlay_generic, _plot_generic


def _get_legacy_and_studies() -> tuple[dict, dict]:
    """Lazy load legacy_to_study and studies from global config (avoids circular import)."""
    from science_cli.core.config import load_global_config
    cfg = load_global_config()
    return cfg.get("legacy_to_study", {}), cfg.get("studies", {})


@dataclass
class DevicePlotterVariant:
    """Per-device-type plot/overlay override for a study.

    When a StudyPlotter has a matching device_variant for the active
    device_type, the variant's non-None fields override the base
    StudyPlotter fields during dispatch.

    Attributes:
        plot_fn: Override plot function for this device type (None = use base).
        overlay_fn: Override overlay function for this device type (None = use base).
        flags: Override flags list for this device type (None = use base).
        hints: Override hints dict for this device type (None = use base).
    """
    plot_fn: Callable | None = None
    overlay_fn: Callable | None = None
    flags: list[dict] | None = None
    hints: dict | None = None


@dataclass
class StudyPlotter:
    plot_fn: Callable
    overlay_fn: Callable
    flags: list[dict] = field(default_factory=list)
    hints: dict | None = None
    single_layout: str = "single_axis"
    overlay_layout: str = "single_axis"
    device_variants: dict[str, DevicePlotterVariant] = field(default_factory=dict)


STUDY_PLOTTERS: dict[str, StudyPlotter] = {}

def resolve_study_plotter(
    study_name: str,
    device_type: str | None = None,
) -> StudyPlotter | None:
    """Resolve a StudyPlotter for a given study name.

    Args:
        study_name: Study name in "technique:study-name" format or legacy name.
        device_type: Optional device-type slug. When provided and the plotter
            has a matching ``device_variants`` entry, returns a merged
            StudyPlotter with variant overrides applied to the base.

    Returns:
        A StudyPlotter (possibly merged) or None if no mapping exists.
    """
    base = None
    if study_name in STUDY_PLOTTERS:
        base = STUDY_PLOTTERS[study_name]
    else:
        legacy, _ = _get_legacy_and_studies()
        mapped = legacy.get(study_name)
        if mapped and mapped in STUDY_PLOTTERS:
            base = STUDY_PLOTTERS[mapped]
    if base is None:
        return None

    # Merge device-type variant overrides into the base plotter
    if device_type:
        variant = base.device_variants.get(device_type)
        if variant is not None:
            return StudyPlotter(
                plot_fn=variant.plot_fn if variant.plot_fn is not None else base.plot_fn,
                overlay_fn=variant.overlay_fn if variant.overlay_fn is not None else base.overlay_fn,
                flags=variant.flags if variant.flags is not None else base.flags,
                hints=variant.hints if variant.hints is not None else base.hints,
                single_layout=base.single_layout,
                overlay_layout=base.overlay_layout,
                device_variants=base.device_variants,
            )

    return base

def register_study_plotter(study_name: str, plotter: StudyPlotter) -> None:
    STUDY_PLOTTERS[study_name] = plotter

def list_study_plotters() -> list[str]:
    return list(STUDY_PLOTTERS.keys())


# ── Populate STUDY_PLOTTERS from studies dict ──────────────────────────

_IV_SWEEP_FLAGS = [
    {"name": "--gradient", "action": "store_true", "help": "Color sweep points by position along cycle"},
    {"name": "--cmap", "type": str, "help": "Colormap for gradient: viridis, plasma, rainbow (default: viridis)"},
    {"name": "--loglog", "action": "store_true", "help": "Log-log axes"},
    {"name": "--highlight", "type": str, "help": "Highlight specific cycle(s)"},
]

_STP_FLAGS = [
    {"name": "--describe", "action": "store_true", "help": "Show pulse parameters (width, max V/I, steady current)"},
]

_RAMAN_FLAGS: list[dict] = []

_UV_VIS_FLAGS: list[dict] = []

_CV_FLAGS: list[dict] = []

_EIS_FLAGS: list[dict] = []

_AFM_FLAGS: list[dict] = []

_PPF_FLAGS = [
    {"name": "--describe", "action": "store_true", "help": "Show pulse parameters"},
]

# Flag definitions for all studies
STUDY_FLAGS: dict[str, list[dict]] = {
    "iv:iv-bipolar-sweep": _IV_SWEEP_FLAGS,
    "iv:iv-breakdown": [],
    "iv:iv-leakage": [],
    "pulse:pulse-stp-decay": _STP_FLAGS,
    "pulse:pulse-ppf": _PPF_FLAGS,
    "raman:raman-spectrum": [],
    "uv-vis:uv-vis-spectrum": [],
    "ec:ec-cv": [],
    "ec:ec-ca": [],
    "ec:ec-eis": [],
    "afm:afm-topography": [],
}

# Per-study overlay layouts
_OVERLAY_LAYOUTS: dict[str, str] = {
    "pulse:pulse-stp-decay": "1x2_panels",
    "pulse:pulse-ppf": "1x2_panels",
    "ec:ec-eis": "nyquist_bode",
}

# Populate all studies with generic config-driven plotters
_, _studies_for_plotters = _get_legacy_and_studies()
for technique, technique_studies in _studies_for_plotters.items():
    for study_name, study_cfg in technique_studies.items():
        full_name = f"{technique}:{study_name}"
        if full_name not in STUDY_PLOTTERS:
            STUDY_PLOTTERS[full_name] = StudyPlotter(
                plot_fn=_plot_generic,
                overlay_fn=_overlay_generic,
                flags=STUDY_FLAGS.get(full_name, []),
                overlay_layout=_OVERLAY_LAYOUTS.get(full_name, "single_axis"),
            )

# Override with dedicated plotters below (imports are deferred — inside functions)
def _init_dedicated_plotters():
    """Install dedicated plot/overlay functions for studies that need custom plotters.
    Only complex studies that generic.py cannot handle get overrides here.
    Called lazily — imports happen inside this function to avoid circular deps."""
    from science_cli.plot.afm import _plot_afm_single
    from science_cli.plot.eis import _overlay_eis, _plot_eis_single
    # EIS — dual-panel Nyquist + Bode
    STUDY_PLOTTERS["ec:ec-eis"].plot_fn = _plot_eis_single
    STUDY_PLOTTERS["ec:ec-eis"].overlay_fn = _overlay_eis
    # AFM — image-type plot
    STUDY_PLOTTERS["afm:afm-topography"].plot_fn = _plot_afm_single


# ── Universal --describe support ────────────────────────────────────────


DESCRIBE_FLAG = {"name": "--describe", "nargs": "?", "const": True, "help": "Show file metadata and analysis parameters (universal). Optional comma-separated field filter."}


def _build_waveform_segments_table(points: list[list[float]]):
    """Build a Rich Table of waveform segments from a 2D [time, voltage] array.

    Iterates through consecutive points, detecting where voltage changes to
    define segment boundaries. Each segment shows start time, end time,
    width, and voltage (in microseconds, rounded to 3 decimals).
    """
    from rich.table import Table as RichTable

    if not points or len(points) < 2:
        return None

    segments: list[dict] = []
    seg_start_t = points[0][0]
    seg_start_v = points[0][1]

    for i in range(1, len(points)):
        t, v = points[i]
        if v != seg_start_v:
            # Voltage change — close current segment
            segments.append({
                "start": seg_start_t,
                "end": t,
                "voltage": seg_start_v,
            })
            seg_start_t = t
            seg_start_v = v

    # Close the last segment
    segments.append({
        "start": seg_start_t,
        "end": points[-1][0],
        "voltage": seg_start_v,
    })

    # Build the table
    table = RichTable(title="Waveform Segments", border_style="cyan")
    table.add_column("Start", style="bold white", justify="right")
    table.add_column("End", style="bold white", justify="right")
    table.add_column("Width", style="bold white", justify="right")
    table.add_column("Voltage", style="dim", justify="right")

    for seg in segments:
        start_us = seg["start"] * 1e6
        end_us = seg["end"] * 1e6
        width_us = (seg["end"] - seg["start"]) * 1e6
        voltage = round(seg["voltage"], 3)

        table.add_row(
            f"{start_us:.2f} µs",
            f"{end_us:.2f} µs",
            f"{width_us:.2f} µs",
            f"{voltage:.3f} V",
        )

    return table


def _show_describe(filepath: str, study_name: str, fields_str: str | None = None) -> dict:
    """Show file metadata/analysis for any study without plotting.

    Returns the info dict for callers that want to inspect it.
    """
    from rich.console import Console
    from rich.table import Table as RichTable

    from science_cli.core.data_loader import load_data_file
    from science_cli.core.technique import detect_technique

    console = Console()
    technique = None
    try:
        from science_cli.core.config import resolve_technique_from_study
        technique = resolve_technique_from_study(study_name)
    except Exception:
        pass
    if not technique:
        technique = detect_technique(filepath)

    try:
        load_kwargs = {"study_name": study_name}
        if technique:
            load_kwargs["technique"] = technique
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load file: {e}[/red]")
        return {}

    metadata = info.get("metadata", {})
    analysis = info.get("analysis", {})
    merged = {**metadata, **analysis}

    # ── Extract waveform_pattern for dedicated segment display ──
    waveform_segments_table = None
    waveform_pattern = analysis.get("waveform_pattern")
    if waveform_pattern and isinstance(waveform_pattern, list) and len(waveform_pattern) >= 2:
        merged.pop("waveform_pattern", None)
        waveform_segments_table = _build_waveform_segments_table(waveform_pattern)

    if fields_str:
        fields = [f.strip() for f in fields_str.split(",") if f.strip()]
        selected = {k: v for k, v in merged.items() if k in fields}
        show_waveform = "waveform_pattern" in fields
        if not selected and not show_waveform:
            console.print(f"[yellow]No matching fields found. Available: {', '.join(merged.keys())}[/yellow]")
            return merged
        if selected:
            table = RichTable(title=f"Describe: {Path(filepath).name}", border_style="cyan")
            table.add_column("Field", style="bold white")
            table.add_column("Value", style="dim")
            for k, v in selected.items():
                table.add_row(k, str(v))
            console.print(table)
        if show_waveform and waveform_segments_table:
            console.print()
            console.print(waveform_segments_table)
        return merged

    if merged:
        table = RichTable(title=f"Describe: {Path(filepath).name}", border_style="cyan")
        table.add_column("Field", style="bold white")
        table.add_column("Value", style="dim")
        for k, v in merged.items():
            table.add_row(k, str(v))
        console.print(table)
        if waveform_segments_table:
            console.print()
            console.print(waveform_segments_table)
    else:
        file_info = info.get("file_info", {})
        console.print("[yellow]No metadata available for this file/study combination.[/yellow]")
        if file_info:
            console.print(f"[dim]File info: {file_info}[/dim]")

    return merged
