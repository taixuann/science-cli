"""fzf integration for interactive file selection with global styling."""

import os
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
    """Run fzf — stdout piped (captured), stderr wired to ``/dev/tty``.

    fzf writes its interactive UI to stderr (or directly to ``/dev/tty``)
    and the selected item(s) to stdout.  By piping stdout but routing
    stderr to ``/dev/tty``, the user sees the full fzf UI on the real
    terminal while we capture the selection result cleanly.

    Opening ``/dev/tty`` explicitly guarantees fzf gets the real
    controlling terminal, regardless of any Textual / asyncio / PTY
    wrappers around sys.stdout or sys.stderr.
    """
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

    item_set = set(items)
    filtered = [s for s in selected if s in item_set]

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
