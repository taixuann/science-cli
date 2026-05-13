"""memristor command handler — crossbar device management from the sci CLI."""


def memristor_handler(args: list) -> None:
    """Handle 'memristor <subcommand>' from the sci CLI."""
    try:
        from science_cli.memristor.device_cli import build_parser

        parser = build_parser()
        parsed = parser.parse_args(args)
        parsed.func(parsed)
    except SystemExit:
        pass
