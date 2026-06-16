"""instrument command handler — hardware/instrument model management."""

import os
import subprocess
import tempfile

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag
from science_cli.library.instruments import (
    get_all_instruments,
    get_instrument,
    get_instruments_by_technique,
    register_instrument,
    remove_instrument,
    edit_instrument,
)
from science_cli.library.instruments.types import describe_type, list_types

console = Console()


def _parse_flags(args: list) -> tuple[list[str], dict]:
    positional = []
    flags: dict[str, str | bool] = {}
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


def _render_template() -> str:
    return """# New Instrument Registration
# Fill in the fields below. Lines starting with # are comments.
# Remove the # to uncomment and fill.

label: "My Instrument"
location: "lab-location"
type: "sourcemeter"  # One of: """ + ", ".join(list_types()) + """
techniques:
  - iv-sweep
config:
  delimiter: ","
  decimal: "."
  header_lines: 0
  encoding: "utf-8"
"""


def instrument_handler(args: list) -> None:
    """Handle 'instrument <subcommand>' from sci CLI."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("instrument")
        return

    console.print("[yellow]⚠️  'sci instrument' is deprecated.[/yellow]")
    console.print("[dim]Use 'sci ls -m instrument' to list, 'sci edit -m instrument' to edit.[/dim]")

    sub = args[0]
    sub_args = args[1:]

    if sub == "ls":
        _cmd_ls(sub_args)
    elif sub == "info":
        _cmd_info(sub_args)
    elif sub == "register":
        _cmd_register(sub_args)
    elif sub == "edit":
        _cmd_edit(sub_args)
    elif sub == "rm":
        _cmd_rm(sub_args)
    else:
        console.print(f"[yellow]Unknown instrument subcommand: {sub}[/yellow]")
        console.print("[dim]Use 'sci instrument --help' for usage.[/dim]")


def _cmd_ls(args: list) -> None:
    _, flags = _parse_flags(args)
    technique = flags.get("technique") or flags.get("t")

    if technique:
        instruments = get_instruments_by_technique(technique)
        title = f"Instruments compatible with: {technique}"
    else:
        instruments = get_all_instruments()
        title = "Registered Instruments"

    if not instruments:
        rprint(f"[yellow]No instruments found.[/yellow]")
        return

    table = Table(title=title, border_style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Label", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Location", style="dim")
    table.add_column("Techniques", style="bright_black")

    for ins in instruments:
        tech_str = ", ".join(ins["techniques"][:4])
        if len(ins["techniques"]) > 4:
            tech_str += f" +{len(ins['techniques']) - 4}"
        table.add_row(
            ins["name"],
            ins["label"],
            describe_type(ins["type"]),
            ins.get("location", ""),
            tech_str,
        )

    console.print(table)
    console.print(f"[dim]Total: {len(instruments)} instrument(s)[/dim]")


def _cmd_info(args: list) -> None:
    if not args:
        console.print("[yellow]Usage: sci instrument info <name>[/yellow]")
        return

    name = args[0]
    ins = get_instrument(name)
    if ins is None:
        console.print(f"[red]Instrument '{name}' not found.[/red]")
        return

    console.print(f"\n[bold]Instrument:[/bold] [bold white]{name}[/bold white]")
    console.print(f"  Label:       {ins['label']}")
    console.print(f"  Location:    {ins.get('location', '')}")
    console.print(f"  Type:        {describe_type(ins['type'])}")

    if ins["techniques"]:
        console.print(f"\n  [bold]Compatible Techniques:[/bold]")
        for t in ins["techniques"]:
            console.print(f"    • {t}")

    config = ins.get("config", {})
    if config:
        console.print(f"\n  [bold]Config:[/bold]")
        for k, v in config.items():
            if v is not None:
                console.print(f"    {k}: {v}")


def _cmd_register(args: list) -> None:
    if not args:
        console.print("[yellow]Usage: sci instrument register <name>[/yellow]")
        return

    name = args[0]
    existing = get_instrument(name)
    if existing:
        console.print(f"[yellow]Instrument '{name}' already exists. Use 'edit' to modify.[/yellow]")
        return

    template = _render_template()
    editor = os.environ.get("EDITOR", "vi")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(template)
        tmp_path = f.name

    try:
        subprocess.call([editor, tmp_path])
        import yaml
        with open(tmp_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[red]Error reading edited file: {e}[/red]")
        return
    finally:
        os.unlink(tmp_path)

    if not data or not data.get("label"):
        console.print("[yellow]Registration cancelled or invalid data.[/yellow]")
        return

    register_instrument(name, data)
    rprint(f"[bold green]✓[/bold green] Instrument '[bold white]{name}[/bold white]' registered.")


def _cmd_edit(args: list) -> None:
    if not args:
        console.print("[yellow]Usage: sci instrument edit <name>[/yellow]")
        return

    name = args[0]
    ins = get_instrument(name)
    if ins is None:
        console.print(f"[red]Instrument '{name}' not found.[/red]")
        return

    import yaml
    current_yaml = yaml.dump(ins, default_flow_style=False, sort_keys=False)
    editor = os.environ.get("EDITOR", "vi")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(f"# Edit instrument '{name}'\n")
        f.write(current_yaml)
        tmp_path = f.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[red]Error reading edited file: {e}[/red]")
        return
    finally:
        os.unlink(tmp_path)

    if not data:
        console.print("[yellow]Edit cancelled or empty data.[/yellow]")
        return

    edit_instrument(name, data)
    rprint(f"[bold green]✓[/bold green] Instrument '[bold white]{name}[/bold white]' updated.")


def _cmd_rm(args: list) -> None:
    _, flags = _parse_flags(args)
    if not args:
        console.print("[yellow]Usage: sci instrument rm <name> [--confirm][/yellow]")
        return

    name = args[0]
    ins = get_instrument(name)
    if ins is None:
        console.print(f"[red]Instrument '{name}' not found.[/red]")
        return

    if not flags.get("confirm"):
        console.print(f"[yellow]Use --confirm to remove instrument '{name}'.[/yellow]")
        return

    removed = remove_instrument(name)
    if removed:
        rprint(f"[bold green]✓[/bold green] Instrument '[bold white]{name}[/bold white]' removed.")
    else:
        console.print(f"[red]Could not remove '{name}'.[/red]")
