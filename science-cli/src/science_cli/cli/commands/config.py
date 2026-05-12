"""config command handler — plot, theme, init, show."""

from pathlib import Path
from rich.console import Console
from rich import print as rprint
from rich.table import Table
import yaml

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

    elif sub == "init":
        _cmd_init(sub_args)

    elif sub == "show":
        _cmd_show(sub_args)

    else:
        console.print(f"[yellow]Unknown config subcommand: {sub}[/yellow]")
        show_command_help("config")


def _cmd_init(args: list) -> None:
    """Generate a default config.yaml with all sections documented.

    Usage: sci config init [--global|--project]
        --global         Write to ~/.config/science-cli/config.yaml (default)
        --project        Write to <project_root>/sci-config.yaml
    """
    target = "global"
    if args and args[0] == "--project":
        target = "project"
    elif args and args[0] == "--global":
        target = "global"

    if target == "global":
        config_path = Path.home() / ".config" / "science-cli" / "config.yaml"
    else:
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[red]No project open. Open a project first, or use --global.[/red]")
            return
        config_path = proj / "sci-config.yaml"

    if config_path.exists():
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        console.print("[dim]Use 'sci config show' to view it.[/dim]")
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
    except ImportError:
        # Fallback: basic config
        content = "theme: publication-acs\nprojects_root: ~/workspace/projects/active_projects\n"

    with open(config_path, "w") as f:
        f.write(content)

    console.print(f"[green]✓[/green] Config created: {config_path}")
    console.print("[dim]Edit this file to configure techniques, devices, and defaults.[/dim]")


def _cmd_show(args: list) -> None:
    """Display the merged configuration.

    Usage: sci config show [--global|--project|--merged]
        --global      Show global config only (~/.config/science-cli/config.yaml)
        --project     Show per-project config only (sci-config.yaml)
        --merged      Show fully merged config (default)
    """
    mode = "merged"
    if args and args[0] in ("--global", "--project", "--merged"):
        mode = args[0].lstrip("-")

    try:
        from science_cli.core.config import (
            load_global_config,
            load_project_config,
            get_merged_config,
            invalidate_cache,
        )
    except ImportError:
        console.print("[red]Config system not available.[/red]")
        return

    invalidate_cache()  # Refresh before display

    if mode == "global":
        cfg = load_global_config()
        title = "Global config (~/.config/science-cli/config.yaml)"
    elif mode == "project":
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        cfg = load_project_config(proj)
        title = f"Project config ({proj / 'sci-config.yaml'})"
    else:
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        cfg = get_merged_config(proj)
        title = "Merged config (hardcoded ← global ← project)"

    if not cfg:
        console.print(f"[dim]No config found for: {title}[/dim]")
        return

    console.print(f"\n[bold]{title}[/bold]\n")
    _print_config_tree(cfg, indent=0)


def _print_config_tree(data: dict, indent: int = 0) -> None:
    """Pretty-print a config dict with indentation and type-appropriate styling."""
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, dict):
            if not value:
                console.print(f"{prefix}[bold cyan]{key}:[/bold cyan] {{}}")
            else:
                console.print(f"{prefix}[bold cyan]{key}:[/bold cyan]")
                _print_config_tree(value, indent + 1)
        elif isinstance(value, list):
            if not value:
                console.print(f"{prefix}[bold cyan]{key}:[/bold cyan] []")
            else:
                console.print(f"{prefix}[bold cyan]{key}:[/bold cyan]")
                for item in value:
                    console.print(f"{prefix}  - [green]{item}[/green]")
        elif value is None:
            console.print(f"{prefix}[bold cyan]{key}:[/bold cyan] [dim]null[/dim]")
        else:
            console.print(f"{prefix}[bold cyan]{key}:[/bold cyan] [green]{value}[/green]")
