"""IV sweep command handler — replaces memristor IV functionality."""


def iv_handler(args):
    """Handle 'iv <subcommand>' from sci CLI."""
    if not args or args[0] in ("-h", "--help"):
        try:
            from science_cli.library.iv.device_cli import show_iv_help
            show_iv_help()
            return
        except Exception:
            pass

    try:
        from science_cli.library.iv.device_cli import build_iv_parser
        parser = build_iv_parser()
        parsed, extra = parser.parse_known_args(args)
        parsed.extra_args = extra

        study_name = getattr(parsed, "study", "") or ""
        if study_name:
            try:
                from science_cli.core.config import resolve_technique_from_study
                parsed.technique = resolve_technique_from_study(study_name)
            except ImportError:
                pass

        if parsed.subcommand == "ls":
            from science_cli.library.iv.device_cli import cmd_ls
            cmd_ls(parsed)
        elif parsed.subcommand == "info":
            from science_cli.library.iv.device_cli import cmd_info
            cmd_info(parsed)
        elif parsed.subcommand == "plot":
            from science_cli.library.iv.device_cli import cmd_plot
            cmd_plot(parsed)
        elif parsed.subcommand == "analyze":
            from science_cli.library.iv.device_cli import cmd_analyze
            cmd_analyze(parsed)
        elif parsed.subcommand == "sync":
            from science_cli.library.iv.device_cli import cmd_sync
            cmd_sync(parsed)
        elif parsed.subcommand == "dashboard":
            from science_cli.library.iv.device_cli import cmd_dashboard
            cmd_dashboard(parsed)
        else:
            parser.print_help()
    except SystemExit:
        pass
