"""PVD deposition command handler."""


def pvd_handler(args):
    """Handle 'pvd <subcommand>' from sci CLI."""
    if not args or args[0] in ("-h", "--help"):
        try:
            from science_cli.library.pvd.device_cli import show_pvd_help
            show_pvd_help()
            return
        except Exception:
            pass

    try:
        from science_cli.library.pvd.device_cli import build_pvd_parser
        parser = build_pvd_parser()
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
            from science_cli.library.pvd.device_cli import cmd_ls
            cmd_ls(parsed)
        elif parsed.subcommand == "info":
            from science_cli.library.pvd.device_cli import cmd_info
            cmd_info(parsed)
        elif parsed.subcommand == "add":
            from science_cli.library.pvd.device_cli import cmd_add
            cmd_add(parsed)
        elif parsed.subcommand == "edit":
            from science_cli.library.pvd.device_cli import cmd_edit
            cmd_edit(parsed)
        elif parsed.subcommand == "analyze":
            from science_cli.library.pvd.device_cli import cmd_analyze
            cmd_analyze(parsed)
        else:
            parser.print_help()
    except SystemExit:
        pass
