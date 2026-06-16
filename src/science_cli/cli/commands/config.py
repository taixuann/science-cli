"""config command handler — plot, theme, init, show, list techniques, set technique."""

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from science_cli.cli.help import show_command_help

console = Console()


def config_handler(args: list) -> None:
    """Handle `config` command and subcommands."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("config")
        return

    sub = args[0]
    sub_args = args[1:]

    # Deprecation warnings for redirected commands
    if sub in ("list", "edit", "show", "init", "devices", "grammar", "set"):
        console.print("[yellow]⚠️  'config' subcommands are deprecated.[/yellow]")
        console.print("[dim]Use 'ls -m' for listing, 'edit -m' for editing, 'init' standalone.[/dim]")

    if sub == "plot":
        console.print("[yellow]config plot: use plot_settings.json directly at ~/.config/science-cli/plot_settings.json[/yellow]")

    elif sub == "theme":
        from science_cli.core.session import get_active_theme, set_active_theme
        from science_cli.theme import apply_theme, list_themes
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
        if not sub_args:
            console.print("[yellow]Usage: config set technique <name> <device>[/yellow]")
            console.print("[yellow]       config set techniques <technique> <device>[/yellow]")
        elif sub_args[0] == "technique" and len(sub_args) >= 3:
            _cmd_set_technique(sub_args[1:])
        elif sub_args[0] == "techniques" and len(sub_args) >= 3:
            _cmd_set_techniques(sub_args[1:])
        else:
            console.print("[yellow]Usage: config set technique <name> <device>[/yellow]")
            console.print("[yellow]       config set techniques <technique> <device>[/yellow]")

    elif sub == "edit":
        _cmd_edit(sub_args)

    elif sub == "list":
        if not sub_args:
            _cmd_list_techniques()
        elif sub_args[0] == "techniques":
            _cmd_list_techniques()
        elif sub_args[0] == "devices" and len(sub_args) > 1:
            _cmd_list_devices(sub_args[1])
        elif sub_args[0] == "grammar":
            _cmd_list_grammar(sub_args[1:] if len(sub_args) > 1 else [])
        else:
            console.print("[yellow]Usage: config list techniques | config list devices <technique> | config list grammar [--device-type <type>][/yellow]")

    elif sub == "devices":
        if not sub_args or sub_args[0] == "list":
            _cmd_list_global_devices()
        else:
            console.print("[yellow]Usage: config devices [list][/yellow]")

    elif sub == "grammar":
        if not sub_args or sub_args[0] == "list":
            _cmd_list_grammar(sub_args[1:] if len(sub_args) > 1 else [])
        elif sub_args[0] == "edit":
            _cmd_edit_grammar(sub_args[1:] if len(sub_args) > 1 else [])
        else:
            console.print("[yellow]Usage: config grammar [list|edit][/yellow]")
            console.print("[yellow]       config grammar list --device-type <type>[/yellow]")
            console.print("[yellow]       config grammar edit --device-type <type>[/yellow]")
            console.print("[yellow]       config grammar edit --protocol <name>[/yellow]")

    else:
        console.print(f"[yellow]Unknown config subcommand: {sub}[/yellow]")
        show_command_help("config")


def _cmd_init(args: list) -> None:
    """Generate default config files.

    Default: creates 4 modular files (config-devices.yaml, config-instruments.yaml,
    config-grammar.yaml, config-template.yaml) under ~/.config/science-cli/.

    Usage: sci config init [--global|--project|--monolithic]
        --global         Write to ~/.config/science-cli/ (4 modular files, default)
        --project        Write to <project_root>/sci-config.yaml
        --monolithic     Create old-style single config.yaml (deprecated)
    """
    target = "global"
    monolithic = False
    for a in args:
        if a == "--project":
            target = "project"
        elif a == "--monolithic":
            monolithic = True
        elif a == "--global":
            target = "global"

    # Base config directory
    config_dir = Path.home() / ".config" / "science-cli"

    # Check for migration hint
    old_config = config_dir / "config.yaml"
    modular_existing = [config_dir / f for f in ("config-devices.yaml", "config-instruments.yaml",
                                                  "config-grammar.yaml", "config-template.yaml")]
    has_existing_modular = any(p.exists() for p in modular_existing)

    if target == "project":
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[red]No project open. Open a project first, or use --global.[/red]")
            return
        config_path = proj / "sci-config.yaml"
        if config_path.exists():
            console.print(f"[yellow]Project config already exists: {config_path}[/yellow]")
            return
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from science_cli.core.config import generate_default_config_yaml
            content = generate_default_config_yaml()
        except ImportError:
            content = "theme: publication-nature\nprojects_root: ~/workspace/projects/active_projects\n"
        with open(config_path, "w") as f:
            f.write(content)
        console.print(f"[green]\u2713[/green] Project config created: {config_path}")
        console.print("[dim]Edit this file to configure project-level overrides.[/dim]")
        return

    if monolithic:
        if old_config.exists():
            console.print(f"[yellow]Monolithic config already exists: {old_config}[/yellow]")
            return
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            from science_cli.core.config import generate_default_config_yaml
            content = generate_default_config_yaml()
        except ImportError:
            content = "theme: publication-nature\nprojects_root: ~/workspace/projects/active_projects\n"
        with open(old_config, "w") as f:
            f.write(content)
        console.print(f"[green]\u2713[/green] Monolithic config created: {old_config}")
        console.print("[yellow]Warning: --monolithic is deprecated. Use 'sci config init' (without flags) to create modular files instead.[/yellow]")
        return

    # Default: create 4 modular files
    if has_existing_modular:
        console.print(f"[yellow]Modular config already exists: {config_dir}[/yellow]")
        console.print("[dim]Use --monolithic for old-style config or remove modular files to re-init.[/dim]")
        return

    if old_config.exists():
        console.print("[yellow]Old monolithic config.yaml detected at {old_config}[/yellow]")
        console.print("[dim]Run 'python scripts/migrate-config-to-modular.py' to split into modular files.[/dim]")
        console.print("[dim]Or use 'sci config init --monolithic' to create old-style config.[/dim]")
        return

    config_dir.mkdir(parents=True, exist_ok=True)

    try:
        from science_cli.core.config_defaults import (
            generate_config_devices_yaml,
            generate_config_instruments_yaml,
            generate_config_grammar_yaml,
            generate_config_template_yaml,
        )
        files = {
            config_dir / "config-devices.yaml": generate_config_devices_yaml(),
            config_dir / "config-instruments.yaml": generate_config_instruments_yaml(),
            config_dir / "config-grammar.yaml": generate_config_grammar_yaml(),
            config_dir / "config-template.yaml": generate_config_template_yaml(),
        }
    except ImportError:
        console.print("[red]Config defaults module not available. Using basic fallback.[/red]")
        files = {
            config_dir / "config-devices.yaml": "# studies + device types\n",
            config_dir / "config-instruments.yaml": "# instrument registry\n",
            config_dir / "config-grammar.yaml": "# filename grammar\n",
            config_dir / "config-template.yaml": "# theme templates\n",
        }

    for path, content in files.items():
        if not path.exists():
            path.write_text(content)

    console.print(f"[green]\u2713[/green] Modular config created: {config_dir}")
    for path in files:
        console.print(f"  \u2514 {path.name}")
    console.print("[dim]Edit these files to configure studies, instruments, grammar, and templates.[/dim]")


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
            get_merged_config,
            invalidate_cache,
            load_global_config,
            load_project_config,
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

    from science_cli.core.config import (
        list_technique_devices,
        load_technique_configs,
        write_technique_config,
    )

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


def _cmd_set_techniques(args: list) -> None:
    """Set the default device for a technique (plural alias).

    Usage: sci config set techniques <name> <device>
    Alias for: config set technique <name> <device>
    """
    # Delegate to singular version
    _cmd_set_technique(args)


def _cmd_edit_technique(technique: str, force: bool = False) -> None:
    """Open technique config in $EDITOR (or nvim as fallback).

    Creates the file first if it doesn't exist.
    Use --force to overwrite an existing file with the template.
    """
    from science_cli.core.config import _technique_configs_dir

    tech_dir = _technique_configs_dir()
    tech_dir.mkdir(parents=True, exist_ok=True)
    path = tech_dir / f"{technique}.yaml"

    if not path.exists() or force:
        if force and path.exists():
            console.print(f"[dim]Regenerating {path}...[/dim]")
        # Create a minimal config template
        default_content = f"""# ============================================================
# TECHNIQUE CONFIG: {technique}
# ============================================================
# This file tells science-cli HOW to detect and LOAD data files
# for the '{technique}' technique.
#
# QUICK START:
#   1. Define filename patterns so science-cli can auto-detect
#      which technique a file belongs to
#   2. Define one or more devices with their column mappings,
#      delimiters, and encoding so data loads correctly
#   3. Optionally set a default_device for this technique
#
# LAYERED CONFIG: If you also have ~/.config/science-cli/config.yaml
# or a per-project sci-config.yaml, those values OVERRIDE these.
# Hardcoded defaults are the lowest priority fallback.
#
# ============================================================
# 1. FILENAME PATTERNS
# ============================================================
# science-cli matches filenames against these patterns (regex)
# to auto-detect the technique. List as many as needed.
#
# Examples:
#   - "*{technique}*"        matches any file containing the technique name
#   - "_IV_"                 matches files with _IV_ in the name
#   - r"_sweep"              matches files containing _sweep
#
patterns:
  - "*{technique}*"

# ============================================================
# 2. DEFAULT DEVICE (optional)
# ============================================================
# When loading a file for this technique, science-cli uses this
# device's column mapping by default. You can still override
# per-file via the CLI.
#
# Uncomment and set to one of the devices defined below:
# default_device: keithley-2400

# ============================================================
# 3. DEVICE DEFINITIONS
# ============================================================
# Each device has its own loading rules. This is where you tell
# science-cli about your measurement equipment.
#
# Fields:
#   delimiter     - Column separator: "\\t" (tab), "," (comma),
#                   ";" (semicolon), " " (space)
#   decimal       - Decimal separator: "." or ","
#   header_lines  - Number of lines to skip before column headers
#   encoding      - File encoding: "utf-8", "latin-1", "cp1252"
#   columns:
#     voltage     - Column name for voltage (or key matching pattern)
#     current     - Column name for current
#     time        - Column name for time (optional)
#     frequency   - Column name for frequency (EIS)
#     z_real      - Column name for real impedance (EIS)
#     z_imag      - Column name for imaginary impedance (EIS)
#     potential   - Column name for potential (CV/CA)
#
# Column names are matched case-insensitively against CSV headers.
# Use "Untitled" for Keithley 2400 tab-separated export column headers.
#
# --- Example: Keithley 2400 (tab-separated CSV) ---
# devices:
#   keithley-2400:
#     delimiter: "\\t"
#     decimal: "."
#     header_lines: 23
#     encoding: "utf-8"
#     columns:
#       voltage: "Untitled"
#       current: "Untitled 1"
#       time: "Untitled 2"
#
# --- Example: Keysight B1500A Clarius+ (CSV) ---
#   keithley-clarius:
#     delimiter: ","
#     decimal: "."
#     header_lines: 8
#     encoding: "utf-8"
#     columns:
#       voltage: "BV"
#       current: "BI"
#
# --- Example: Biologic .mpt (EIS) ---
#   biologic-mpt:
#     delimiter: "\\t"
#     decimal: ","
#     header_lines: 1
#     encoding: "latin-1"
#     columns:
#       frequency: "freq"
#       z_real: "Re(Z)"
#       z_imag: "-Im(Z)"
#
# ============================================================
# 4. UNCOMMENT AND CUSTOMIZE BELOW
# ============================================================
#
# devices:
#   my-device:
#     delimiter: "\\t"
#     decimal: "."
#     header_lines: 1
#     encoding: "utf-8"
#     columns:
#       voltage: "V"
#       current: "I"
#       time: "Time"
"""
        with open(path, "w") as f:
            f.write(default_content)

    # Open in editor
    editor = os.environ.get("EDITOR", "nvim")
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


def _cmd_edit(args: list) -> None:
    """Handle `config edit` subcommand with support for --global, devices, grammar.

    Usage:
        config edit <technique> [--force]          # Edit per-technique config (existing behavior)
        config edit --global                       # Edit global config
        config edit devices                        # Edit global device registry
        config edit grammar                        # Edit global file naming grammar
        config edit techniques --global            # Edit global technique registry (NEW)
    """
    is_global = "--global" in args
    is_force = "--force" in args
    clean_args = [a for a in args if a not in ("--global", "--force")]

    if clean_args:
        target = clean_args[0]
        if target == "devices":
            _cmd_edit_global_devices()
        elif target == "grammar":
            _cmd_edit_grammar(clean_args[1:] if len(clean_args) > 1 else [])
        elif target == "techniques" and is_global:
            _cmd_edit_global_techniques()
        else:
            _cmd_edit_technique(target, force=is_force)
    elif is_global:
        _cmd_edit_global_config()
    else:
        console.print("[yellow]Usage: config edit <technique> [--force][/yellow]")
        console.print("[yellow]       config edit --global[/yellow]")
        console.print("[yellow]       config edit devices[/yellow]")
        console.print("[yellow]       config edit grammar [--device-type <type>][/yellow]")
        console.print("[yellow]       config edit grammar --protocol <name>[/yellow]")
        console.print("[yellow]       config edit techniques --global[/yellow]")


def _cmd_edit_global_config() -> None:
    """Open the global config file in $EDITOR."""
    from science_cli.core.config import _global_config_path

    path = _global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
        with open(path, "w") as f:
            f.write(content)
        console.print(f"[dim]Created default config: {path}[/dim]")

    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print(f"[green]✓[/green] Edited global config: {path}")
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found. Set $EDITOR or try: nano {path}[/red]")
    except subprocess.CalledProcessError:
        console.print(f"[yellow]Editor exited with error. File saved at: {path}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error editing file: {e}[/red]")


def _cmd_edit_global_devices() -> None:
    """Open the devices section of the global config for editing."""
    from science_cli.core.config import _global_config_path

    path = _global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
        with open(path, "w") as f:
            f.write(content)
        console.print(f"[dim]Created default config: {path}[/dim]")

    console.print("[dim]Edit the 'devices:' section in the global config.[/dim]")
    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print("[green]✓[/green] Devices config updated")
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found.[/red]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _cmd_edit_global_grammar() -> None:
    """Open the grammar section of the global config for editing."""
    from science_cli.core.config import _global_config_path

    path = _global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
        with open(path, "w") as f:
            f.write(content)
        console.print(f"[dim]Created default config: {path}[/dim]")

    console.print("[dim]Edit the 'file_naming:' section in the global config.[/dim]")
    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print("[green]✓[/green] Grammar config updated")
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found.[/red]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _cmd_edit_grammar(args: list | None = None) -> None:
    """Edit grammar patterns with support for --device-type and --protocol flags.

    Usage:
        config edit grammar                            (global grammar)
        config edit grammar --device-type <type>       (device-type grammar)
        config edit grammar --protocol <name>          (protocol grammar)
        config grammar edit                            (same as above)
        config grammar edit --device-type <type>       (device-type grammar)
        config grammar edit --protocol <name>          (protocol grammar)
    """
    args = args or []

    # Check for --device-type flag
    device_type = None
    if "--device-type" in args:
        dt_idx = args.index("--device-type")
        if dt_idx + 1 < len(args):
            device_type = args[dt_idx + 1]

    # Check for --protocol flag
    protocol_name = None
    if "--protocol" in args:
        p_idx = args.index("--protocol")
        if p_idx + 1 < len(args):
            protocol_name = args[p_idx + 1]

    if device_type and protocol_name:
        console.print("[yellow]Specify either --device-type or --protocol, not both.[/yellow]")
        return

    if device_type:
        _cmd_edit_grammar_device_type(device_type)
    elif protocol_name:
        _cmd_edit_grammar_protocol(protocol_name)
    else:
        _cmd_edit_global_grammar()


def _cmd_edit_grammar_device_type(device_type: str) -> None:
    """Edit grammar patterns for a specific device type.

    Opens ~/.config/science-cli/config.yaml scrolled to the device_types
    section, or creates a template if the section doesn't exist.
    """
    from science_cli.core.config import _global_config_path, get_device_type_grammar

    path = _global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
        with open(path, "w") as f:
            f.write(content)
        console.print(f"[dim]Created default config: {path}[/dim]")

    # Ensure the device_type section exists
    import yaml
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    file_naming = cfg.setdefault("file_naming", {})
    device_types = file_naming.setdefault("device_types", {})

    if device_type not in device_types:
        # Create a template
        from science_cli.core.config import _DEFAULT_DEVICE_TYPE_GRAMMAR
        device_types[device_type] = list(_DEFAULT_DEVICE_TYPE_GRAMMAR.get(device_type, []))
        if not device_types[device_type]:
            device_types[device_type] = [{
                "id": f"{device_type}-custom",
                "template": "{date_code}_{material}_{technique}_{suffix?}",
                "description": f"Custom grammar for {device_type} devices",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<technique>[^_]+)(?:_(?P<suffix>\d+))?\.\w+$",
            }]
        cfg["file_naming"] = file_naming
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        console.print(f"[dim]Created grammar template for device type '{device_type}'.[/dim]")

    console.print(f"[dim]Edit the 'file_naming.device_types.{device_type}' section.[/dim]")
    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print(f"[green]✓[/green] Device-type grammar updated for '{device_type}'")
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found.[/red]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _cmd_edit_grammar_protocol(protocol_name: str) -> None:
    """Edit grammar patterns for a specific protocol.

    Opens the protocol YAML file in $EDITOR, creating a grammar section
    template if one doesn't exist.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.core.config import invalidate_cache

    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Open a project first.[/yellow]")
        return

    proto_dir = proj / "protocol" / protocol_name
    proto_yaml = proto_dir / f"{protocol_name}.yaml"

    if not proto_yaml.exists():
        console.print(f"[yellow]Protocol '{protocol_name}' not found at {proto_yaml}[/yellow]")
        return

    # Ensure grammar section exists
    import yaml
    with open(proto_yaml) as f:
        data = yaml.safe_load(f) or {}

    if "grammar" not in data:
        data["grammar"] = {
            "patterns": [
                {
                    "id": f"{protocol_name}-custom",
                    "template": "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}",
                    "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$",
                },
            ],
        }
        with open(proto_yaml, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        console.print(f"[dim]Created grammar section in protocol '{protocol_name}'.[/dim]")

    console.print(f"[dim]Edit the 'grammar:' section in the protocol YAML.[/dim]")
    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(proto_yaml)], check=True)
        console.print(f"[green]✓[/green] Protocol grammar updated for '{protocol_name}'")
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found.[/red]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _cmd_edit_global_techniques() -> None:
    """Open the techniques section of the global config for editing."""
    from science_cli.core.config import _global_config_path

    path = _global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        from science_cli.core.config import generate_default_config_yaml
        content = generate_default_config_yaml()
        with open(path, "w") as f:
            f.write(content)
        console.print(f"[dim]Created default config: {path}[/dim]")

    console.print("[dim]Edit the 'techniques:' section in the global config.[/dim]")
    editor = os.environ.get("EDITOR", "nvim")
    try:
        subprocess.run([editor, str(path)], check=True)
        console.print("[green]✓[/green] Techniques config updated")
        from science_cli.core.config import invalidate_cache
        invalidate_cache()
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found.[/red]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Editor exited with error.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _cmd_list_techniques() -> None:
    """List all configured techniques from all sources with per-device config display."""
    from science_cli.core.config import (
        get_default_device,
        get_device_config_detail,
        get_technique_patterns,
        list_technique_devices,
        list_technique_names,
    )

    names = list_technique_names()

    if not names:
        console.print("[dim]No techniques configured.[/dim]")
        console.print("[dim]Use 'sci config set technique <name> <device>' to add one.[/dim]")
        return

    # Build the enhanced 4-column table with per-device rows
    table = Table(
        title="Configured Techniques",
        show_lines=True,
        border_style="cyan",
        header_style="bold white",
    )
    table.add_column("Technique ID", style="bold cyan")
    table.add_column("Filename Patterns", style="dim")
    table.add_column("Device Config", style="white")
    table.add_column("Default Device", style="green")

    for tech_name in sorted(names):
        patterns = get_technique_patterns(tech_name)
        patterns_str = "\n".join(f"• {p}" for p in patterns) if patterns else "—"
        default_device = get_default_device(tech_name)
        default_str = default_device if default_device else "—"
        devices = list_technique_devices(tech_name)

        if not devices:
            # Technique has no devices configured — show one row with placeholder
            table.add_row(tech_name, patterns_str, "[dim]—[/dim]", default_str)
        else:
            for device_name in devices:
                device_cfg = get_device_config_detail(tech_name, device_name)
                # Build device config display cell
                config_parts = [f"[bold]{device_name}[/bold]"]
                if device_cfg:
                    delimiter = device_cfg.get("delimiter", "")
                    decimal = device_cfg.get("decimal", ".")
                    header_lines = device_cfg.get("header_lines", 0)
                    encoding = device_cfg.get("encoding", "utf-8")
                    columns = device_cfg.get("columns", {})

                    meta_parts = []
                    if delimiter:
                        display_delim = repr(delimiter)[1:-1]  # strip quotes
                        meta_parts.append(f"delimiter: [dim]{display_delim}[/dim]")
                    if decimal is not None:
                        meta_parts.append(f"decimal: [dim]{decimal}[/dim]")
                    if header_lines:
                        meta_parts.append(f"header_lines: [dim]{header_lines}[/dim]")
                    if encoding:
                        meta_parts.append(f"encoding: [dim]{encoding}[/dim]")

                    if meta_parts:
                        config_parts.append(" | ".join(meta_parts))

                    if columns:
                        col_strs = [f"[green]{k}[/green]→[dim]{v}[/dim]" for k, v in sorted(columns.items())]
                        config_parts.append("columns: " + ", ".join(col_strs))
                else:
                    config_parts.append("[dim]no config[/dim]")

                config_str = "\n".join(config_parts)
                # Show default only on first row for this technique
                row_default = default_str if device_name == devices[0] else ""
                table.add_row(tech_name, patterns_str, config_str, row_default)

    console.print(table)

    # Workflow guidance panel
    console.print()
    console.print(Panel(
        "[bold]How to use techniques[/bold]\n"
        "  1. [bold]create[/bold] a protocol:  add -m protocol -n my-protocol --step 1_dep,2_dope -t ec-cv,ec-ca\n"
        "  2. [bold]open[/bold] the protocol:   open -m protocol -n my-protocol\n"
        "  3. [bold]assign[/bold] data files:   add -m data\n"
        "     (technique is auto-detected from filenames)\n"
        "  4. [bold]plot[/bold] the data:       plot --fzf",
        title="Workflow Guide",
        border_style="cyan",
    ))
    console.print()


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


def _cmd_list_global_devices() -> None:
    """List all devices in the global registry."""
    from science_cli.core.config import get_global_device_config, list_global_devices

    devices = list_global_devices()

    if not devices:
        console.print("[yellow]No devices in global registry.[/yellow]")
        return

    table = Table(title="Global Device Registry")
    table.add_column("Device", style="cyan")
    table.add_column("Label", style="dim")
    table.add_column("Delimiter", style="white")
    table.add_column("Header Lines", style="white")
    table.add_column("Columns", style="green")

    for d in devices:
        cfg = get_global_device_config(d)
        label = cfg.get("label", "") if cfg else ""
        delim = repr(cfg.get("delimiter", ""))[1:-1] if cfg and cfg.get("delimiter") else "auto"
        header = str(cfg.get("header_lines", 0)) if cfg else "0"
        cols = ", ".join(sorted(cfg.get("columns", {}).keys())) if cfg else ""
        table.add_row(d, label, delim, header, cols)

    console.print(table)


def _cmd_list_grammar(args: list | None = None) -> None:
    """List configured file naming grammar patterns.

    Supports:
        config list grammar                              (global patterns)
        config list grammar --device-type <type>         (device-type patterns)
        config list grammar --protocol <name>            (protocol patterns)
    """
    args = args or []

    # Check for --device-type flag
    device_type = None
    if "--device-type" in args:
        dt_idx = args.index("--device-type")
        if dt_idx + 1 < len(args):
            device_type = args[dt_idx + 1]

    # Check for --protocol flag
    protocol_name = None
    if "--protocol" in args:
        p_idx = args.index("--protocol")
        if p_idx + 1 < len(args):
            protocol_name = args[p_idx + 1]

    from science_cli.core.config import (
        get_device_type_grammar,
        get_file_naming_patterns,
        get_protocol_grammar,
    )
    from science_cli.core.project import get_current_project_path

    if device_type and protocol_name:
        console.print("[yellow]Specify either --device-type or --protocol, not both.[/yellow]")
        return

    if device_type:
        patterns = get_device_type_grammar(device_type)
        if not patterns:
            console.print(f"[yellow]No grammar patterns for device type '{device_type}'.[/yellow]")
            return
        title = f"Grammar Patterns for Device Type: [bold]{device_type}[/bold]"
    elif protocol_name:
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open. Open a project first.[/yellow]")
            return
        proto_yaml = proj / "protocol" / protocol_name / f"{protocol_name}.yaml"
        patterns = get_protocol_grammar(proto_yaml)
        if not patterns:
            console.print(f"[yellow]No grammar patterns for protocol '{protocol_name}'.[/yellow]")
            return
        title = f"Grammar Patterns for Protocol: [bold]{protocol_name}[/bold]"
    else:
        patterns = get_file_naming_patterns()
        title = "File Naming Grammar Patterns"

    if not patterns:
        console.print("[yellow]No file naming patterns configured.[/yellow]")
        console.print("[dim]Use 'config edit grammar' to add patterns.[/dim]")
        return

    table = Table(title=title)
    table.add_column("ID", style="cyan")
    table.add_column("Template", style="dim")
    table.add_column("Fields", style="green")

    for p in patterns:
        pid = p.get("id", "?")
        template = p.get("template", "")
        fields_spec = p.get("fields", [])
        if isinstance(fields_spec, list):
            field_names = ", ".join(
                fd.get("name", "?") for fd in fields_spec
            )
        elif isinstance(fields_spec, dict):
            field_names = ", ".join(fields_spec.keys())
        else:
            field_names = ""
        table.add_row(pid, template, field_names)

    console.print(table)
    console.print()
    console.print("[dim]Separator is ALWAYS '_' (underscore) — hardcoded.[/dim]")
    if not device_type and not protocol_name:
        console.print("[dim]Use 'config edit grammar' to modify.[/dim]")
