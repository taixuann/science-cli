"""CLI command handlers — each module maps to a top-level command group."""

from science_cli.cli.commands.project import project_handler
from science_cli.cli.commands.plot import plot_handler
from science_cli.cli.commands.analyze import analyze_handler
from science_cli.cli.commands.general import general_handler

from science_cli.cli.commands.add import add_handler
from science_cli.cli.commands.ls import ls_handler
from science_cli.cli.commands.open import open_handler
from science_cli.cli.commands.close import close_handler
from science_cli.cli.commands.delete import delete_handler
from science_cli.cli.commands.edit import edit_handler
from science_cli.cli.commands.config import config_handler
from science_cli.cli.commands.techniques import techniques_handler
from science_cli.cli.commands.results import results_handler
from science_cli.cli.commands.memristor import memristor_handler
from science_cli.cli.commands.extensions import extensions_handler

COMMAND_TREE = {
    "add":     {"handler": add_handler,  "desc": "Add protocol/metadata/data (group 1)"},
    "delete":  {"handler": delete_handler, "desc": "Delete protocol/metadata (group 1)"},
    "edit":    {"handler": edit_handler, "desc": "Edit protocol/metadata (group 1)"},
    "ls":      {"handler": ls_handler,   "desc": "List protocols/steps/files (group 1)"},
    "open":    {"handler": open_handler, "desc": "Open protocol sets session context (group 2)"},
    "close":   {"handler": close_handler, "desc": "Close protocol clears session context (group 2)"},
    "project": {"handler": project_handler, "desc": "Manage projects"},
    "plot":    {"handler": plot_handler, "desc": "Plot data — interactive or direct (group 3)"},
    "analyze": {"handler": analyze_handler, "desc": "Analyze data — peaks, fit, circuit (group 3)"},
    "config":      {"handler": config_handler, "desc": "Configure theme, settings (group 3)"},
    "techniques":  {"handler": techniques_handler, "desc": "List available techniques and usage guide"},
    "results":     {"handler": results_handler, "desc": "List saved results by protocol and step"},
    "extensions":  {"handler": extensions_handler, "desc": "List installed extension tools and their commands (Group 4)"},
    "memristor":  {"handler": memristor_handler, "desc": "Crossbar device management (init, add, ls, info, sync, validate, stats, rm, check)"},
}

GENERAL_COMMANDS = {
    "help":    {"handler": lambda a: None, "desc": "Show this help"},
    "version": {"handler": lambda a: None, "desc": "Show version"},
    "clear":   {"handler": lambda a: None, "desc": "Clear screen"},
    "history": {"handler": lambda a: None, "desc": "Show command history"},
}

ALL_COMMANDS = {**COMMAND_TREE, **GENERAL_COMMANDS}
