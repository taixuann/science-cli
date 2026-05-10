"""memristor command handler — crossbar device management from the sci REPL."""

import sys


def memristor_handler(args: list) -> None:
    """Handle 'memristor <subcommand>' from the sci REPL/CLI."""
    try:
        from science_memristor.device_cli import build_parser

        parser = build_parser()
        parsed = parser.parse_args(args)
        parsed.func(parsed)
    except SystemExit:
        pass
