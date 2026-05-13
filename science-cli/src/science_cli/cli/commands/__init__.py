"""CLI command handlers — each module maps to a top-level command group."""

from science_cli.cli.commands.project import project_handler
from science_cli.cli.commands.plot import plot_handler
from science_cli.cli.commands.analyze import analyze_handler

from science_cli.cli.commands.add import add_handler
from science_cli.cli.commands.ls_cmd import ls_handler
from science_cli.cli.commands.open_cmd import open_handler
from science_cli.cli.commands.delete_cmd import delete_handler
from science_cli.cli.commands.edit_cmd import edit_handler
from science_cli.cli.commands.config import config_handler
from science_cli.cli.commands.techniques import techniques_handler
from science_cli.cli.commands.results import results_handler
from science_cli.cli.commands.memristor_cmd import memristor_handler
from science_cli.cli.commands.extensions import extensions_handler
from science_cli.cli.commands.close import close_handler
from science_cli.cli.commands.status import status_handler
from science_cli.cli.commands.ext import ext_handler

COMMAND_TREE = {
    "add":     {"handler": add_handler,  "desc": "Add protocol/metadata/data/project (group 1)"},
    "delete":  {"handler": delete_handler, "desc": "Delete protocol/metadata (group 1)"},
    "edit":    {"handler": edit_handler, "desc": "Edit protocol/metadata (group 1)"},
    "ls":      {"handler": ls_handler,   "desc": "List projects/protocols/steps/files (group 1)"},
    "open":    {"handler": open_handler, "desc": "Open project/protocol/step — sets session context (group 2)"},
    "project": {"handler": project_handler, "desc": "[DEPRECATED] Use 'ls/open/add/close/status -m project' instead"},
    "close":   {"handler": close_handler, "desc": "Close context with auto-save (step/protocol/project)"},
    "status":  {"handler": status_handler, "desc": "Show current context status"},
    "plot":    {"handler": plot_handler, "desc": "Plot data — interactive or direct (group 3)"},
    "analyze": {"handler": analyze_handler, "desc": "Analyze data — peaks, fit, circuit (group 3)"},
    "config":      {"handler": config_handler, "desc": "Configure theme, settings (group 3)"},
    "techniques":  {"handler": techniques_handler, "desc": "List available techniques and usage guide"},
    "results":     {"handler": results_handler, "desc": "List saved results by protocol and step"},
    "extensions":  {"handler": extensions_handler, "desc": "List installed extension tools and their commands (Group 4)"},
    "ext":         {"handler": ext_handler, "desc": "Unified extension interface — ext <name> <subcommand>"},
    "memristor":  {"handler": memristor_handler, "desc": "Crossbar device management — alias for 'ext memristor'"},
}
