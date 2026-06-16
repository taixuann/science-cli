"""memristor command handler — now a deprecated device-type alias.

'sci memristor' prints a deprecation warning and attempts to auto-dispatch
based on subcommand context. Subcommands sync/analyze/dashboard/plot map
to iv. Subcommands endurance/retention map to pulse.

Deprecation period: 3 minor versions (remove in v4.0.0).
"""

import sys


def memristor_handler(args):
    """Handle 'memristor <subcommand>' — deprecated alias for 'iv' and 'pulse'."""
    if not args or args[0] in ("-h", "--help"):
        _print_warning()
        try:
            from science_cli.library.memristor.device_cli import show_memristor_help
            show_memristor_help()
            return
        except Exception:
            pass

    _print_warning()

    # Route to iv or pulse based on subcommand
    if args:
        iv_cmds = {"sync", "analyze", "dashboard", "plot", "ls", "info", "init", "rm", "validate", "stats", "check", "add"}
        pulse_cmds = {"endurance", "retention"}

        if args[0] in iv_cmds:
            from science_cli.cli.commands.iv import iv_handler
            iv_handler(args)
        elif args[0] in pulse_cmds:
            from science_cli.cli.commands.pulse import pulse_handler
            pulse_handler(args)
        else:
            try:
                from science_cli.library.memristor.device_cli import build_parser
                parser = build_parser()
                parsed, extra = parser.parse_known_args(args)
                parsed.extra_args = extra
                parsed.func(parsed)
            except SystemExit:
                pass
            except Exception:
                print(f"[yellow]'sci memristor' is deprecated. Use 'sci iv' or 'sci pulse' instead.[/yellow]")


def _print_warning():
    print("[yellow]'sci memristor' is deprecated. Use 'sci iv' or 'sci pulse' instead.[/yellow]")
