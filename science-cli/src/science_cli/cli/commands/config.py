"""config command handler — plot, theme."""

from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


def config_handler(args: list) -> None:
    """Handle `config` command and subcommands."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("config")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "plot":
        console.print("[yellow]config plot: use plot_settings.json directly at ~/.config/science-cli/plot_settings.json[/yellow]")

    elif sub == "theme":
        from science_cli.theme import list_themes, apply_theme
        from science_cli.core.session import get_active_theme, set_active_theme
        if not sub_args or sub_args[0] == "list":
            themes = list_themes()
            active = get_active_theme()
            console.print("[bold]Available themes:[/bold]")
            for name in themes:
                indicator = " [green]●[/green]" if name == active else ""
                console.print(f"  • {name}{indicator}")
        elif sub_args[0] == "set" and len(sub_args) > 1:
            name = sub_args[1]
            all_themes = list_themes()
            if name in all_themes:
                set_active_theme(name)
                apply_theme(name)
                console.print(f"[green]✓[/green] Theme set: {name}")
            else:
                console.print(f"[red]Unknown theme: {name}. Use 'config theme list' to see available.[/red]")
        else:
            console.print("[yellow]Usage: config theme [list|set <name>][/yellow]")

    else:
        console.print(f"[yellow]Unknown config subcommand: {sub}[/yellow]")
        show_command_help("config")
