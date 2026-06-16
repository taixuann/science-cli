"""PVD deposition CLI — logic for sci pvd command."""
import argparse

from rich.console import Console

console = Console()


def build_pvd_parser():
    """Build argument parser for pvd subcommands."""
    parser = argparse.ArgumentParser(prog="pvd", description="PVD deposition record commands")
    parser.add_argument("--study", "-s", default="", help="Study name for technique resolution")
    subparsers = parser.add_subparsers(dest="subcommand")

    subparsers.add_parser("ls", help="List PVD deposition steps")
    subparsers.add_parser("info", help="Show deposition details")
    subparsers.add_parser("add", help="Add deposition record")
    subparsers.add_parser("edit", help="Edit deposition record")
    subparsers.add_parser("analyze", help="Analyze deposition data")

    return parser


def cmd_ls(args):
    console.print("[dim]PVD deposition steps:[/dim]")


def cmd_info(args):
    console.print("[yellow]info not yet implemented[/yellow]")


def cmd_add(args):
    console.print("[yellow]add not yet implemented[/yellow]")


def cmd_edit(args):
    console.print("[yellow]edit not yet implemented[/yellow]")


def cmd_analyze(args):
    console.print("[yellow]analyze not yet implemented[/yellow]")


def show_pvd_help():
    parser = build_pvd_parser()
    parser.print_help()
