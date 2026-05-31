"""memristor command handler — crossbar device management from the sci CLI."""


def memristor_handler(args: list) -> None:
    """Handle 'memristor <subcommand>' from the sci CLI."""
    if not args or args[0] in ("-h", "--help"):
        try:
            from science_cli.library.memristor.device_cli import show_memristor_help
            show_memristor_help()
            return
        except Exception:
            pass

    try:
        from science_cli.library.memristor.device_cli import build_parser

        parser = build_parser()
        parsed = parser.parse_args(args)
        parsed.func(parsed)
    except SystemExit:
        pass
