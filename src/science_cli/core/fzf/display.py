"""fzf integration for interactive file selection with global styling."""

import os
import platform
import shutil
import subprocess

from science_cli.core.session import get_fzf_opts


def _build_fzf_args(
    prompt: str = "Select:",
    multi: bool = False,
    preview: str | None = None,
    preview_window: str | None = None,
    query: str = "",
    header: str = "",
) -> list[str]:
    """Build fzf CLI args merging global opts with per-call overrides."""
    opts = get_fzf_opts()
    args = ["fzf"]

    height = opts.get("height", "60%")
    border = opts.get("border", "rounded")
    layout = opts.get("layout", "reverse")
    pw = preview_window or opts.get("preview_window", "")

    args.extend(["--height", height])
    args.extend(["--border", border])
    args.extend(["--layout", layout])
    args.extend(["--prompt", prompt + " "])
    args.extend(["--info", "inline"])

    binds = ["ctrl-a:select-all", "ctrl-d:deselect-all"]
    if multi:
        binds.append("tab:toggle+down")
        args.append("--multi")
    args.extend(["--bind", ",".join(binds)])

    if header:
        args.extend(["--header", header])

    if preview:
        args.extend(["--preview", preview])
        if pw:
            args.extend(["--preview-window", pw])

    if query:
        args.extend(["--query", query])

    return args


def fzf_select(
    items: list[str],
    prompt: str = "Select:",
    multi: bool = False,
    preview: str | None = None,
    preview_window: str | None = None,
    query: str = "",
) -> list[str]:
    """Interactive fzf selection with global styling and optional preview.

    Parameters
    ----------
    items : list[str]
        Items to display.
    prompt : str
        Prompt string.
    multi : bool
        Enable multi-select (Tab to toggle).
    preview : str or None
        Preview command template (``{}`` is replaced with selected item).
    preview_window : str or None
        Preview window layout, e.g. ``right:50%:border-sharp``.
    query : str
        Pre-populate search query.

    Returns
    -------
    list[str]
        Selected items, or empty list if cancelled.
    """
    if not items:
        return []

    if not shutil.which("fzf"):
        return _fallback_select(items, prompt, multi)

    try:
        input_text = "\n".join(items)
        args = _build_fzf_args(prompt, multi, preview, preview_window, query)
        return _run_fzf(args, input_text, items, prompt, multi)
    except (FileNotFoundError, OSError):
        return _fallback_select(items, prompt, multi)


def _run_fzf(
    args: list[str],
    input_text: str,
    items: list[str],
    prompt: str,
    multi: bool,
) -> list[str]:
    """Run fzf — stdout piped (captured), stderr wired to the terminal.

    On Unix, stderr is routed to ``/dev/tty`` so fzf gets the real
    controlling terminal regardless of any Textual / asyncio / PTY
    wrappers around sys.stdout or sys.stderr.

    On Windows, the console is inherited directly (``stderr=None``)
    since ``/dev/tty`` does not exist.
    """
    if platform.system() == "Windows":
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            return _fallback_select(items, prompt, multi)
    else:
        try:
            tty_fd = os.open("/dev/tty", os.O_RDWR)
        except OSError:
            return _fallback_select(items, prompt, multi)

        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=tty_fd,
            )
        except FileNotFoundError:
            os.close(tty_fd)
            return _fallback_select(items, prompt, multi)

        os.close(tty_fd)

    stdout_data, _ = proc.communicate(input=input_text.encode())

    if not stdout_data:
        return []

    result = stdout_data.decode("utf-8", errors="replace").strip()
    if not result:
        return []

    selected = [line.strip() for line in result.split("\n") if line.strip()]

    # Strip both sides: fzf strips trailing whitespace from returned lines,
    # but items may have padding trailing spaces (e.g. build_fzf_display).
    stripped_items = {item.strip() for item in items}
    filtered = [s for s in selected if s in stripped_items]

    return filtered if filtered else selected[:1] if selected else []


def _fallback_select(
    items: list[str], prompt: str, multi: bool
) -> list[str]:
    print(f"\n{prompt}")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item}")
    try:
        choice = input("Enter number(s) (comma-separated): ").strip()
        indices = [
            int(x.strip())
            for x in choice.split(",")
            if x.strip().isdigit()
        ]
        return [items[i - 1] for i in indices if 1 <= i <= len(items)]
    except (ValueError, IndexError):
        return []


def build_fzf_display(protocol: str = "", step: str = "", filename: str = "",
                       show_protocol: bool = True, width_proto: int = 20,
                       width_step: int = 22,
                       metadata: dict | None = None,
                       width_meta: int = 20,
                       study_name: str | None = None,
                       device_type: str | None = None,
                       status: str | None = None,
                       status_badge: str = "") -> str:
    """Build a fixed-width fzf display line.

    When ``show_protocol=True``: ``<protocol:20> <step:22> <filename>``.
    When ``show_protocol=False``: ``<step:22> <filename>``.

    When ``metadata`` is provided, appends fixed-width columns for each
    key-value pair in the dict, e.g.::

        <step:22> <filename:30> <technique:20> <instrument:20>

    When ``study_name`` matches a key in ``STUDY_COLUMN_REGISTRY``,
    only the registered columns are shown (in registry order) with
    compact ``width_meta=12``.  Unknown studies fall back to showing
    all metadata keys in dict order.

    When ``device_type`` is provided, device-specific column overrides
    are used if registered (e.g. volatile vs non-volatile endurance).

    When ``status_badge`` is non-empty, it is prepended (with 1 space)
    before the protocol/step columns.

    Parameters
    ----------
    protocol : str
        Protocol name.
    step : str
        Step name, or ``""`` for unassigned.
    filename : str
        File basename.
    show_protocol : bool
        Whether to include the protocol column (default True).
    width_proto : int
        Fixed width for protocol column (default 20).
    width_step : int
        Fixed width for step column (default 22).
    metadata : dict or None
        Optional dict of metadata key-value pairs to display in
        subsequent columns (e.g. ``{"technique": "ec-cv", "instrument": "keithley-2400"}``).
    width_meta : int
        Fixed width for each metadata column (default 20).
    study_name : str or None
        Study name (e.g. ``"pulse:pulse-stp-decay"``). When provided
        and registered, filters metadata to the study's column set.
    device_type : str or None
        Device type (e.g. ``"volatile-memristor"``). When provided with
        ``study_name``, uses device-specific column override if registered.
    status : str or None
        Legacy status tag — ignored if ``status_badge`` is set.
    status_badge : str
        Prepend this badge string (e.g. ``"★"``) before the line.
    """
    protocol = protocol or ""
    step = step or ""
    filename = filename or ""

    # Resolve metadata columns for this study (with optional device override)
    effective_meta = metadata
    effective_width = width_meta
    if study_name and metadata:
        from science_cli.core.fzf.columns import get_columns_for
        cols = get_columns_for(study_name, device_type)
        if cols:
            effective_meta = {k: metadata[k] for k in cols if k in metadata}
            effective_width = 12  # compact for narrow pulse values

    if show_protocol and protocol:
        base = f"{protocol:<{width_proto}} {step:<{width_step}} {filename}"
    else:
        base = f"{step:<{width_step}} {filename}"

    if effective_meta:
        meta_parts = []
        for v in effective_meta.values():
            val = str(v or "")
            meta_parts.append(f"{val:<{effective_width}}")
        if meta_parts:
            base = base + " " + " ".join(meta_parts)

    if status_badge:
        base = f"{status_badge} {base}"

    return base


# ── Filter helpers ─────────────────────────────────────────


def parse_filter_string(s: str) -> dict:
    """Parse a filter string into field-specific filters.

    With commas: ``{ddmm},{technique},{purpose}`` — field-specific.
    Without commas: treated as a raw filename search across all fields.

    Returns dict with keys: raw, date, technique, purpose.
    """
    if not s:
        return {"raw": "", "date": "", "technique": "", "purpose": ""}
    if "," not in s:
        return {"raw": s.strip(), "date": "", "technique": "", "purpose": ""}
    parts = s.split(",")
    return {
        "raw": "",
        "date": parts[0].strip() if len(parts) > 0 else "",
        "technique": parts[1].strip() if len(parts) > 1 else "",
        "purpose": parts[2].strip() if len(parts) > 2 else "",
    }


def filter_files_by_metadata(
    filenames: list[str],
    filter_dict: dict,
    technique_map: dict[str, str] | None = None,
) -> list[str]:
    """Filter filenames by metadata constraints.

    Parameters
    ----------
    filenames : list[str]
        File basenames to filter.
    filter_dict : dict
        With optional keys: date, technique, purpose.
    technique_map : dict or None
        Mapping of filename -> technique string.
        If None, filenames are matched by pattern conventions.

    Returns
    -------
    list[str]
        Filtered filenames.
    """
    result = filenames

    raw_filter = (filter_dict.get("raw") or "").strip()
    if raw_filter:
        return [f for f in result if raw_filter.lower() in f.lower()]

    date_filter = (filter_dict.get("date") or "").strip()
    if date_filter:
        result = [f for f in result if date_filter in f]

    tech_filter = (filter_dict.get("technique") or "").strip().lower()
    if tech_filter:
        if technique_map:
            result = [
                f
                for f in result
                if technique_map.get(f, "").lower() == tech_filter
            ]
        else:
            result = [
                f
                for f in result
                if tech_filter in f.lower()
            ]

    purpose_filter = (filter_dict.get("purpose") or "").strip().lower()
    if purpose_filter:
        result = [
            f
            for f in result
            if purpose_filter in f.lower()
        ]

    return result
