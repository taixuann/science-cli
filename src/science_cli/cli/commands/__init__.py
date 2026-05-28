"""CLI command handlers — each module maps to a top-level command group."""

from science_cli.cli.commands.add import add_handler
from science_cli.cli.commands.analyze import analyze_handler
from science_cli.cli.commands.chat_cmd import chat_handler
from science_cli.cli.commands.close import close_handler
from science_cli.cli.commands.config import config_handler
from science_cli.cli.commands.delete_cmd import delete_handler
from science_cli.cli.commands.edit_cmd import edit_handler
from science_cli.cli.commands.ls_cmd import ls_handler
from science_cli.cli.commands.memristor import memristor_handler
from science_cli.cli.commands.open_cmd import open_handler
from science_cli.cli.commands.info import info_handler
from science_cli.cli.commands.plot import plot_handler
from science_cli.cli.commands.raman import raman_handler
from science_cli.cli.commands.results import results_handler
from science_cli.cli.commands.status import status_handler
from science_cli.cli.commands.techniques import techniques_handler

COMMAND_TREE = {
    "add":     {"handler": add_handler,  "desc": "Add project/protocol/metadata/data (group 1)"},
    "chat":    {"handler": chat_handler, "desc": "AI chat — natural language to plot commands (group 2)"},
    "info":    {"handler": info_handler, "desc": "Project info — machine-readable manifest (group 2)"},
    "delete":  {"handler": delete_handler, "desc": "Delete protocol/metadata (group 1)"},
    "edit":    {"handler": edit_handler, "desc": "Edit protocol/metadata (group 1)"},
    "ls":      {"handler": ls_handler,   "desc": "List projects/protocols/steps/files (group 1)"},
    "open":    {"handler": open_handler, "desc": "Open project/protocol/step (group 2)"},
    "close":   {"handler": close_handler, "desc": "Close context with auto-save (group 2)"},
    "config":  {"handler": config_handler, "desc": "Configure settings — themes, techniques, devices, grammar (group 2)"},
    "status":  {"handler": status_handler, "desc": "Show current context tree (group 2)"},
    "results": {"handler": results_handler, "desc": "Browse saved figures by protocol and step (group 2)"},
    "plot":    {"handler": plot_handler, "desc": "Plot data — fzf-based, auto-detects technique (group 3)"},
    "analyze": {"handler": analyze_handler, "desc": "Analyze data — fzf-based, technique-aware (group 3)"},
    "memristor": {"handler": memristor_handler, "desc": "Memristor IV/endurance/retention — plot, dashboard, sync (group 3)"},
    "raman": {"handler": raman_handler, "desc": "Raman spectroscopy — list, inspect, plot, analyze (group 3)"},
    "techniques": {"handler": techniques_handler, "desc": "List techniques (deprecated: use 'config list techniques')"},
}
