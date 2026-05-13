"""config command handler — plot, theme, init, show."""

import os
import subprocess
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

    elif sub == "set":
        if len(sub_args) >= 2 and sub_args[0] == "technique":
            _cmd_set_technique(sub_args[1:])
        else:
            console.print("[yellow]Usage: config set technique <name> <device>[/yellow]")

    elif sub == "edit":
        if sub_args:
            _cmd_edit_technique(sub_args[0])
        else:
            console.print("[yellow]Usage: config edit <technique>[/yellow]")

    elif sub == "list":
        if not sub_args:
            _cmd_list_techniques()
        elif sub_args[0] == "techniques":
            _cmd_list_techniques()
        elif sub_args[0] == "devices" and len(sub_args) > 1:
            _cmd_list_devices(sub_args[1])
        else:
            console.print("[yellow]Usage: config list techniques | config list devices <technique>[/yellow]")

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


def _cmd_set_technique(args: list) -> None:
    """Set the default device for a technique.

    Usage: sci config set technique <name> <device>
    Creates/updates ~/.config/science-cli/techniques/<name>.yaml
    """
    if len(args) < 2:
        console.print("[yellow]Usage: config set technique <technique> <device>[/yellow]")
        return

    technique = args[0]
    device = args[1]

    from science_cli.core.config import write_technique_config, load_technique_configs, list_technique_devices

    # Load existing technique config or create new one
    tech_configs = load_technique_configs()
    existing = tech_configs.get(technique, {})

    # Verify the device is valid (check if it exists in any config source)
    available_devices = list_technique_devices(technique)
    if available_devices and device not in available_devices:
        console.print(f"[yellow]Warning: '{device}' is not in the known devices for '{technique}'. Creating anyway.[/yellow]")

    # Update the defaults section
    existing["default_device"] = device

    write_technique_config(technique, existing)
    console.print(f"[green]✓[/green] Default device for '{technique}' set to '{device}'")


def _cmd_edit_technique(technique: str) -> None:
    """Open technique config in $EDITOR (or vim/nano as fallback).

    Creates the file first if it doesn't exist.
    """
    from science_cli.core.config import _technique_configs_dir

    tech_dir = _technique_configs_dir()
    tech_dir.mkdir(parents=True, exist_ok=True)
    path = tech_dir / f"{technique}.yaml"

    if not path.exists():
        # Create a minimal config template
        default_content = f"""# {technique} technique configuration
# Created by `sci config edit {technique}`
# See ~/.config/science-cli/config.yaml for full reference.

# Filename patterns for auto-detection
patterns:
  - "*{technique}*"

# Default device for this technique
# default_device: my-device

# Device-specific loading parameters
# devices:
#   my-device:
#     delimiter: "\\t"
#     decimal: "."
#     header_lines: 1
#     encoding: "utf-8"
#     columns:
#       voltage: "V"
#       current: "I"
"""
        with open(path, "w") as f:
            f.write(default_content)

    # Open in editor
    editor = os.environ.get("EDITOR", "vim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print(f"[green]✓[/green] Edited: {path}")

        # Invalidate caches so changes take effect
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found. Set $EDITOR or try: nano {path}[/red]")
    except subprocess.CalledProcessError:
        console.print(f"[yellow]Editor exited with error. File saved at: {path}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error editing file: {e}[/red]")


def _cmd_list_techniques() -> None:
    """List all configured techniques from all sources."""
    from science_cli.core.config import list_technique_names, load_technique_configs

    names = list_technique_names()

    if not names:
        console.print("[dim]No techniques configured.[/dim]")
        return

    # Check which have standalone config files
    tech_configs = load_technique_configs()

    table = Table(title="Configured Techniques")
    table.add_column("Technique", style="cyan")
    table.add_column("Config File", style="green")
    table.add_column("Devices", style="yellow")

    for name in names:
        has_config = "yes" if name in tech_configs else "—"
        from science_cli.core.config import list_technique_devices
        devices = list_technique_devices(name)
        devices_str = ", ".join(devices[:5])
        if len(devices) > 5:
            devices_str += f" … and {len(devices)-5} more"
        table.add_row(name, has_config, devices_str or "—")

    console.print(table)


def _cmd_list_devices(technique: str) -> None:
    """List devices configured for a specific technique."""
    from science_cli.core.config import list_technique_devices

    devices = list_technique_devices(technique)

    if not devices:
        console.print(f"[yellow]No devices configured for technique '{technique}'.[/yellow]")
        console.print("[dim]Use 'sci config set technique <name> <device>' to add one.[/dim]")
        return

    table = Table(title=f"Devices for {technique}")
    table.add_column("Device", style="cyan")

    for d in devices:
        table.add_row(d)

    console.print(table)
