"""techniques command — list available techniques and usage guide."""

from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def techniques_handler(args: list) -> None:
    """Show available techniques and how to use them through the step system."""
    from science_cli.extensions import discover_extensions

    registry = discover_extensions()

    if not registry.techniques:
        console.print("[yellow]No techniques registered (no extensions loaded).[/yellow]")
        return

    # Summary header
    rprint("\n[bold]Available Techniques[/bold]")
    rprint("  Techniques are assigned to protocol steps. When you add data files\n"
           "  to a step, the technique is auto-detected from filename patterns.\n"
           "  The plot/analyze commands then use this information automatically.\n")

    # Table
    table = Table(border_style="cyan")
    table.add_column("ID", style="bold white")
    table.add_column("Label")
    table.add_column("Description")
    table.add_column("Filename Patterns", style="dim")

    for tid, tdef in sorted(registry.techniques.items()):
        patterns = ", ".join(tdef.patterns)
        table.add_row(tid, tdef.label, tdef.description, patterns)

    console.print(table)

    # Usage workflow
    rprint("\n[bold]How to use[/bold]")
    rprint("  1. [bold]create[/bold] a protocol:  [cyan]add -m protocol -n my-protocol --step 1_dep,2_dope --t ec-cv,ec-ca[/cyan]")
    rprint("  2. [bold]open[/bold] the protocol:   [cyan]open -m protocol -n my-protocol[/cyan]")
    rprint("  3. [bold]assign[/bold] data files:   [cyan]add -m data --fzf[/cyan]")
    rprint("     (technique is auto-detected from filenames)")
    rprint("  4. [bold]plot[/bold] the data:       [cyan]plot --fzf[/cyan]")
    rprint("     (uses the step's technique defaults)")
    rprint("")
