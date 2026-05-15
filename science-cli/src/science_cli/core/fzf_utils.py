"""fzf integration for interactive file selection with global styling."""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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
        return _run_fzf_via_pty(args, input_text, items, prompt, multi)
    except (FileNotFoundError, OSError):
        return _fallback_select(items, prompt, multi)


def _run_fzf_via_pty(
    args: list[str],
    input_text: str,
    items: list[str],
    prompt: str,
    multi: bool,
) -> list[str]:
    """Run fzf in a PTY via ``pty.spawn()`` — no external ``script`` needed.

    ``pty.spawn()`` creates a PTY, forks, and relays I/O between the
    real terminal and the PTY. The child (fzf) gets a real TTY in the
    PTY slave; the parent relays PTY output to the terminal AND captures
    it for selection parsing.  All synchronous — no async ContextVar
    interaction, no subprocess module overhead.
    """
    import pty
    import tempfile

    # Write items to a temp file for fzf to read via < redirect
    item_fd, item_path = tempfile.mkstemp(prefix="sci-fzf-items-", suffix=".txt")
    with os.fdopen(item_fd, "w") as f:
        f.write(input_text)

    # Build the command: bash -c "fzf < items"
    fzf_args_str = " ".join(shlex.quote(a) for a in args)
    cmd = ["bash", "-c", f"{fzf_args_str} < {shlex.quote(item_path)}"]

    # pty.spawn relays terminal I/O through a PTY.
    # The child gets a real TTY; the parent reads PTY output and forwards
    # it to stdout.  We capture all PTY output to extract the selection.
    output_chunks: list[bytes] = []

    def master_read(fd: int) -> bytes:
        data = os.read(fd, 65536)
        if data:
            output_chunks.append(data)
        return data

    try:
        pty.spawn(cmd, master_read=master_read)
    except FileNotFoundError:
        return _fallback_select(items, prompt, multi)
    finally:
        try:
            os.unlink(item_path)
        except OSError:
            pass

    if not output_chunks:
        return []

    # Decode and parse the selection from captured PTY output
    content = b"".join(output_chunks).decode("utf-8", errors="replace")

    if not content.strip():
        return []

    # Strip ANSI escape sequences
    cleaned = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", content)
    cleaned = re.sub(r"\x1b\][^\x07]*\x07", "", cleaned)
    cleaned = re.sub(r"\x1b[][()#;]", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)

    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]

    # Scan from end for items that match the original list
    item_set = set(items)
    matches: list[str] = []
    seen: set[str] = set()
    for line in reversed(lines):
        if line in item_set and line not in seen:
            matches.append(line)
            seen.add(line)
            if not multi:
                break

    if matches:
        matches.reverse()
        return matches

    return [lines[-1]] if lines else []


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
