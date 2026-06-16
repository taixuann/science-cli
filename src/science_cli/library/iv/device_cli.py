"""IV sweep device CLI — logic for sci iv command."""
import argparse

from rich.console import Console

console = Console()


def build_iv_parser() -> argparse.ArgumentParser:
    """Build argument parser for iv subcommands."""
    parser = argparse.ArgumentParser(prog="iv", description="IV sweep analysis commands")
    parser.add_argument("--study", "-s", default="", help="Study name for technique resolution")
    subparsers = parser.add_subparsers(dest="subcommand")

    p_ls = subparsers.add_parser("ls", help="List IV sweep files")
    p_ls.add_argument("--step", help="Step name")

    p_info = subparsers.add_parser("info", help="Show IV file info")
    p_info.add_argument("file", nargs="?", help="File to inspect")

    p_plot = subparsers.add_parser("plot", help="Plot IV curves")
    p_plot.add_argument("--overlay", action="store_true", help="Overlay all traces")
    p_plot.add_argument("--all", action="store_true", help="Plot all files")
    p_plot.add_argument("--row", type=int, help="Row filter")
    p_plot.add_argument("--col", type=int, help="Col filter")

    p_analyze = subparsers.add_parser("analyze", help="Analyze IV data")
    p_analyze.add_argument("--vset-only", action="store_true", help="Volatile mode (V_set only)")
    p_analyze.add_argument("--row", type=int, help="Row filter")
    p_analyze.add_argument("--col", type=int, help="Col filter")

    subparsers.add_parser("sync", help="Sync IV data to SQLite cache")
    subparsers.add_parser("dashboard", help="Launch IV dashboard")

    return parser


def cmd_ls(args) -> None:
    console.print("[dim]IV sweep files:[/dim]")
    console.print("  (not yet implemented — use parent project context)")


def cmd_info(args) -> None:
    console.print("[yellow]info subcommand not yet implemented[/yellow]")


def cmd_plot(args) -> None:
    console.print("[yellow]plot subcommand not yet implemented[/yellow]")


def cmd_analyze(args) -> None:
    mode = "volatile" if getattr(args, "vset_only", False) else "bipolar"
    console.print(f"[dim]Analysis mode: {mode}[/dim]")
    console.print("[yellow]analyze subcommand not yet implemented[/yellow]")


def cmd_sync(args) -> None:
    console.print("[yellow]sync subcommand not yet implemented[/yellow]")


def cmd_dashboard(args) -> None:
    console.print("[yellow]dashboard subcommand not yet implemented[/yellow]")


def show_iv_help() -> None:
    parser = build_iv_parser()
    parser.print_help()


SVG_COLORS = [
    "#333333", "#666666", "#999999", "#BBBBBB",
    "#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
    "#9B59B6", "#1ABC9C",
]

ACCS_NATURE_STYLE = {
    "font_family": "Arial, Helvetica, sans-serif",
    "title_size": 10,
    "axis_label_size": 9,
    "tick_size": 8,
    "line_width": 1.2,
    "marker_size": 3,
}
