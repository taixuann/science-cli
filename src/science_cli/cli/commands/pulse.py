"""Pulse measurement command handler."""


def pulse_handler(args):
    """Handle 'pulse <subcommand>' from sci CLI."""
    if not args or args[0] in ("-h", "--help"):
        try:
            from science_cli.library.pulse.device_cli import show_pulse_help
            show_pulse_help()
            return
        except Exception:
            pass

    try:
        from science_cli.library.pulse.device_cli import build_pulse_parser
        parser = build_pulse_parser()
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
            from science_cli.library.pulse.device_cli import cmd_ls
            cmd_ls(parsed)
        elif parsed.subcommand == "list":
            from science_cli.library.pulse.device_cli import cmd_list
            cmd_list(parsed)
        elif parsed.subcommand == "overlay":
            from science_cli.library.pulse.device_cli import cmd_overlay
            cmd_overlay(parsed)
        elif parsed.subcommand == "endurance":
            from science_cli.library.pulse.device_cli import cmd_endurance
            cmd_endurance(parsed)
        elif parsed.subcommand == "retention":
            from science_cli.library.pulse.device_cli import cmd_retention
            cmd_retention(parsed)
        elif parsed.subcommand == "stp":
            from science_cli.library.pulse.device_cli import cmd_stp
            cmd_stp(parsed)
        elif parsed.subcommand == "ppf":
            from science_cli.library.pulse.device_cli import cmd_ppf
            cmd_ppf(parsed)
        elif parsed.subcommand == "dashboard":
            from science_cli.library.pulse.device_cli import cmd_dashboard
            cmd_dashboard(parsed)
        else:
            parser.print_help()
    except SystemExit:
        pass
