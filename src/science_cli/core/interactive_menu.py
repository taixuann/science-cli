"""Config-driven interactive menu + routing.

Reads menu options from config-studies.yaml, renders a Rich menu,
and dynamically imports/calls the selected handler.
"""

from importlib import import_module
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.prompt import Prompt

console = Console()


def show_menu(title: str, options: list[dict], default: int = 1) -> int:
    """Show a numbered Rich menu and return the user's 1-based choice."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")
    console.print("─" * 50)
    for i, opt in enumerate(options, 1):
        marker = "▸" if i == default else " "
        console.print(f"  {marker} [bold]{i}[/bold]) {opt['name']}")
        desc = opt.get("description", "")
        if desc:
            console.print(f"      {desc}")
    console.print()
    choice = Prompt.ask(
        "Enter choice",
        choices=[str(i) for i in range(1, len(options) + 1)],
        default=str(default),
    )
    return int(choice)


def _get_config_path() -> Path:
    """Get path to config-studies.yaml.

    From core/interactive_menu.py, go up 4 levels to science-cli root.
    """
    return Path(__file__).parent.parent.parent.parent / "config" / "config-studies.yaml"


def load_study_menu(study_name: str, menu_type: str) -> dict:
    """Load interactive menu config for a study from config-studies.yaml.

    Args:
        study_name: e.g. "pulse-endurance"
        menu_type: "plot" or "analyze"

    Returns:
        Dict with menu_title and options list

    Raises:
        KeyError: if study or menu type not found
    """
    config_path = _get_config_path()
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Search all technique groups for the study
    for group in config.get("studies", {}).values():
        if study_name in group:
            study_cfg = group[study_name]
            interactive = study_cfg.get("interactive", {})
            menu = interactive.get(menu_type)
            if menu is None:
                raise KeyError(f"No interactive.{menu_type} menu for '{study_name}'")
            return menu

    raise KeyError(f"Study '{study_name}' not found in config-studies.yaml")


def dispatch(study_key: str, menu_type: str, file_path: Path, **kwargs: Any) -> None:
    """Show menu, dynamically import and call the selected handler.

    Args:
        study_key: e.g. "pulse-endurance"
        menu_type: "plot" or "analyze"
        file_path: Path to the selected data file
        **kwargs: Extra arguments passed to the handler
    """
    menu = load_study_menu(study_key, menu_type)
    choice = show_menu(menu["menu_title"], menu["options"])
    selected = menu["options"][choice - 1]

    # Dynamic import: "science_cli.plot.pulse_endurance.plot_resistance"
    handler_path = selected["handler"]
    module_path, func_name = handler_path.rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)

    # Call with file_path + any extra kwargs
    kwargs["file_path"] = file_path
    handler(**kwargs)
