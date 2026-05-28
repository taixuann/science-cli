"""Tests for CLI commands — COMMAND_TREE, imports, help."""

import importlib

from science_cli.cli.commands import COMMAND_TREE


class TestCommandTree:
    """COMMAND_TREE should have the correct registered commands."""

    def test_has_expected_commands(self):
        keys = sorted(COMMAND_TREE.keys())
        expected = [
            'add', 'analyze', 'chat', 'close', 'config', 'delete', 'edit', 'info', 'ls',
            'memristor', 'open', 'plot', 'raman', 'results', 'status', 'techniques'
        ]
        assert keys == expected

    def test_each_command_has_handler(self):
        for name, entry in COMMAND_TREE.items():
            assert "handler" in entry, f"{name} missing handler"
            assert callable(entry["handler"]), f"{name} handler not callable"
            assert "desc" in entry, f"{name} missing desc"

    def test_no_legacy_commands(self):
        for forbidden in ("ext", "extensions", "project", "general"):
            assert forbidden not in COMMAND_TREE, f"{forbidden} should not be in COMMAND_TREE"


class TestCLIImports:
    """All CLI command modules should import cleanly."""

    def test_import_add(self):
        importlib.import_module("science_cli.cli.commands.add")

    def test_import_analyze(self):
        importlib.import_module("science_cli.cli.commands.analyze")

    def test_import_config(self):
        importlib.import_module("science_cli.cli.commands.config")

    def test_import_ls_cmd(self):
        importlib.import_module("science_cli.cli.commands.ls_cmd")

    def test_import_memristor(self):
        importlib.import_module("science_cli.cli.commands.memristor")

    def test_import_open_cmd(self):
        importlib.import_module("science_cli.cli.commands.open_cmd")

    def test_import_close(self):
        importlib.import_module("science_cli.cli.commands.close")

    def test_import_status(self):
        importlib.import_module("science_cli.cli.commands.status")

    def test_import_results(self):
        importlib.import_module("science_cli.cli.commands.results")

    def test_import_techniques(self):
        importlib.import_module("science_cli.cli.commands.techniques")

    def test_import_help(self):
        importlib.import_module("science_cli.cli.help")
