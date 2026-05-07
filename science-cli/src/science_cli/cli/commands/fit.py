"""fit command handler."""

from rich.console import Console

from science_cli.cli.help import show_command_help

console = Console()


def fit_handler(args: list) -> None:
    """Handle `fit` command."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("fit")
        return

    filepath = args[0]
    rest = args[1:] if len(args) > 1 else []

    model = "linear"
    xcol, ycol = "", ""
    i = 0
    while i < len(rest):
        if rest[i] == "--model" and i + 1 < len(rest):
            model = rest[i + 1]
            i += 2
        elif rest[i] == "--xcol" and i + 1 < len(rest):
            xcol = rest[i + 1]
            i += 2
        elif rest[i] == "--ycol" and i + 1 < len(rest):
            ycol = rest[i + 1]
            i += 2
        else:
            i += 1

    from pathlib import Path
    path = Path(filepath)
    if not path.exists():
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if proj:
            candidate = proj / "data" / "raw" / filepath
            if candidate.exists():
                filepath = str(candidate)
            else:
                for f in (proj / "data" / "raw").iterdir():
                    if filepath.lower() in f.name.lower():
                        filepath = str(f)
                        break

    from science_cli.core.data_loader import fit_file
    fit_file(filepath, model, xcol=xcol, ycol=ycol)
