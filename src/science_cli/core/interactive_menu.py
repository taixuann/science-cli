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


def _normalize_study_key(study_name: str) -> str:
    """Strip technique prefix (e.g. 'pulse:pulse-endurance' -> 'pulse-endurance').

    Config-studies.yaml stores studies by their short name (e.g. 'pulse-endurance'),
    but filename detection returns prefixed names (e.g. 'pulse:pulse-endurance').
    """
    return study_name.split(":", 1)[-1] if ":" in study_name else study_name


def load_study_menu(study_name: str, menu_type: str) -> dict:
    """Load interactive menu config for a study from config-studies.yaml.

    Args:
        study_name: e.g. "pulse-endurance" or "pulse:pulse-endurance"
        menu_type: "plot" or "analyze"

    Returns:
        Dict with menu_title and options list

    Raises:
        KeyError: if study or menu type not found
    """
    config_path = _get_config_path()
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Normalize: strip "pulse:" prefix from the study key
    search_key = _normalize_study_key(study_name)

    # Search all technique groups for the study
    for group in config.get("studies", {}).values():
        if search_key in group:
            study_cfg = group[search_key]
            interactive = study_cfg.get("interactive", {})
            menu = interactive.get(menu_type)
            if menu is None:
                raise KeyError(f"No interactive.{menu_type} menu for '{search_key}'")
            return menu

    raise KeyError(f"Study '{search_key}' not found in config-studies.yaml")


def dispatch(
    study_key: str,
    menu_type: str,
    file_paths: Path | list[Path],
    **kwargs: Any,
) -> None:
    """Show menu, dynamically import and call the selected handler on each file.

    The menu is shown once (not per file). The chosen handler is applied
    to every file in ``file_paths``.

    Args:
        study_key: e.g. "pulse-endurance" or "pulse:pulse-endurance"
        menu_type: "plot" or "analyze"
        file_paths: Path or list of Paths to the selected data file(s)
        **kwargs: Extra arguments passed to the handler
    """
    if isinstance(file_paths, Path):
        file_paths = [file_paths]

    menu = load_study_menu(study_key, menu_type)
    choice = show_menu(menu["menu_title"], menu["options"])
    selected = menu["options"][choice - 1]

    # Dynamic import: "science_cli.plot.pulse_endurance.plot_resistance"
    handler_path = selected["handler"]
    module_path, func_name = handler_path.rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)

    for fp in file_paths:
        kwargs["file_path"] = fp
        handler(**kwargs)
