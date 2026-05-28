"""serve command handler — start interactive dashboard server."""

from __future__ import annotations

import os
import subprocess

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag


def _parse_flags(args: list) -> tuple:
    positional = []
    flags: dict[str, str | bool] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if is_flag(a):
            key = a.lstrip("-")
            if i + 1 < len(args) and not is_flag(args[i + 1]):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            positional.append(a)
            i += 1
    return positional, flags


def serve_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("serve")
        return

    pos, flags = _parse_flags(args)
    port = int(flags.get("port") or os.environ.get("SCI_SERVE_PORT", 6000))
    project = flags.get("project") or flags.get("p")
    dev_mode = "dev" in flags or "d" in flags
    auto_open = "open" in flags or "o" in flags

    from science_cli.serve.server import SciServeServer

    server = SciServeServer(
        port=port,
        project_override=project,
        dev_mode=dev_mode,
    )

    if auto_open:
        import threading
        t = threading.Thread(
            target=lambda: (
                __import__("time").sleep(1.0),
                subprocess.run(["open", f"http://localhost:{port}"]),
            )
        )
        t.daemon = True
        t.start()

    server.serve_forever()
