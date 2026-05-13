"""Help system — builds Rich-formatted hierarchical help text."""

from typing import Dict, List, Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from science_cli import __version__
from science_cli.theme import RICH_STYLES, RAW_COLORS

console = Console()

HELP_SECTIONS = {
    "GROUP 1: FILE MANAGEMENT": ["add", "delete", "edit", "ls"],
    "GROUP 2: CONTEXT NAVIGATION": ["open", "close"],
    "GROUP 3: DATA ANALYSIS": ["plot", "analyze", "config", "status", "results"],
    "GROUP 4: EXTENSIONS & TECHNIQUES": ["ext", "techniques"],
    "ADDITIONAL": ["help", "version", "clear", "history"],
}

COMMAND_DESCRIPTIONS = {
    "add":     "Add project/protocol/metadata/data",
    "delete":  "Delete protocol/metadata",
    "edit":    "Edit protocol/metadata",
    "ls":      "List projects/protocols/steps/files",
    "open":    "Open project/protocol/step",
    "close":   "Close context with auto-save",
    "plot":    "Plot data",
    "analyze": "Analyze data",
    "config":  "Configure settings",
    "status":  "Show current context status",
    "results": "List saved results by protocol and step",
    "ext":     "Unified extension interface — ext <name> <subcommand>",
    "techniques": "List available techniques and usage guide",
    "help":    "Show this help",
    "version": "Show version",
    "clear":   "Clear screen",
    "history": "Show command history",
}

SUBCOMMAND_HELP: Dict[str, Dict] = {}

COMMAND_HELP: Dict[str, dict] = {
    "add": {
        "usage": "add -m <mode> [flags]",
        "desc": "Add project/protocol/metadata/data (Group 1).",
        "subcommands": {
            "add -m project":     {"desc": "Create a new project (was 'project create')", "usage": "add -m project <name>"},
            "add -m protocol":    {"desc": "Create a protocol", "usage": "add -m protocol -n <name> [--desc <text>] [--step s1,s2] [-t ec-cv,ec-ca]"},
            "add -m metadata":    {"desc": "Update protocol metadata", "usage": "add -m metadata --step <steps> -pt <protocol> -t <techniques>"},
            "add -m data":        {"desc": "Interactive file assignment via fzf (shows assigned/unassigned status)", "usage": "add -m data --fzf [--all]"},
        },
        "flags": {
            "-n, --name":     {"desc": "Protocol name (required for protocol mode)"},
            "--desc":         {"desc": "Protocol description"},
            "--step":         {"desc": "Step ID(s), comma-separated"},
            "-t, --technique":{"desc": "Technique(s), comma-separated"},
            "-pt, --protocol":{"desc": "Protocol name (for metadata mode)"},
            "--fzf":          {"desc": "Interactive fzf file selection (shows assigned/unassigned)"},
            "--all":          {"desc": "Assign all selected files to one step (skip per-file prompt)"},
        },
        "examples": [
            "add -m project my-project",
            "add -m protocol -n doping --step 1_deposition,2_characterization -t ec-ca,ec-cv",
            "add -m metadata -step 1_deposition -pt doping -t ec-ca",
            "add -m data --fzf",
            "add -m data --fzf --all",
        ],
    },
    "edit": {
        "usage": "edit -m <mode> [flags]",
        "desc": "Edit protocol/metadata/data (Group 1).",
        "subcommands": {
            "edit -m protocol":    {"desc": "Edit protocol name/description/steps/techniques, remove or reorder steps", "usage": "edit -m protocol -n <name> [--nn <new-name>] [--desc <text>] [--step s1,s2] [-t ec-cv,ec-ca] [--rm-step <name>] [--reorder s1,s2,...]"},
            "edit -m metadata":    {"desc": "Edit file assignments and techniques", "usage": "edit -m metadata -n <name> [--step s1] [-t ec-cv] [--files f1.txt,f2.txt]"},
            "edit -m data":        {"desc": "Move/reassign files between steps (interactive fzf)", "usage": "edit -m data"},
        },
        "flags": {
            "-n, --name":     {"desc": "Protocol name (required)"},
            "--nn, --new-name":{"desc": "New protocol name (rename)"},
            "--desc":         {"desc": "New description"},
            "--step":         {"desc": "Step ID(s), comma-separated"},
            "-t, --technique":{"desc": "Technique(s), comma-separated"},
            "--rm-step":      {"desc": "Step name to remove from protocol"},
            "--reorder":      {"desc": "Comma-separated step order (e.g. 1_cv,2_ca,3_eis)"},
            "--files":        {"desc": "File(s), comma-separated"},
        },
        "examples": [
            "edit -m protocol -n doping --desc \"Updated description\"",
            "edit -m protocol -n doping --step 3_eis -t ec-eis",
            "edit -m protocol -n doping --nn doping-v2",
            "edit -m protocol -n doping --rm-step 2_ca-doping",
            "edit -m protocol -n doping --reorder 3_eis,1_cv-dep,2_ca-doping",
            "edit -m metadata -n doping --step 1_deposition -t ec-cv",
            "edit -m metadata -n doping --files 2105_CV.txt,2106_CV.txt",
            "edit -m data",
        ],
    },
    "delete": {
        "usage": "delete -m <mode> [flags]",
        "desc": "Delete protocol/metadata (Group 1).",
        "subcommands": {
            "delete -m protocol":    {"desc": "Delete a protocol and all its step folders", "usage": "delete -m protocol -n <name>"},
            "delete -m metadata":    {"desc": "Clear file assignments from protocol", "usage": "delete -m metadata -n <name> [--step s1] [--all]"},
        },
        "flags": {
            "-n, --name": {"desc": "Protocol name (required)"},
            "--step":     {"desc": "Step ID(s) to clear, comma-separated"},
            "--all":      {"desc": "Clear file assignments from all protocols"},
        },
        "examples": [
            "delete -m protocol -n doping",
            "delete -m metadata -n doping --step 1_deposition",
            "delete -m metadata --all",
        ],
    },
    "ls": {
        "usage": "ls [flags] [<step>]",
        "desc": "List projects/protocols/steps/files (Group 1). Global, not session-bound.",
        "subcommands": {
            "ls":                   {"desc": "List all protocols and steps", "usage": "ls"},
            "ls -m project":        {"desc": "List all projects (was 'project list')", "usage": "ls -m project"},
            "ls -m protocol":       {"desc": "List all protocols (summary)", "usage": "ls -m protocol"},
            "ls -m protocol --step":{"desc": "Show protocol steps only", "usage": "ls -m protocol --step"},
            "ls -m protocol --all": {"desc": "Show steps + files (full view)", "usage": "ls -m protocol --all"},
            "ls -m protocol --files":{"desc": "Show files only", "usage": "ls -m protocol --files"},
            "ls <step>":            {"desc": "List files in specific step", "usage": "ls 1_deposition"},
        },
        "examples": [
            "ls",
            "ls -m project",
            "ls -m protocol",
            "ls -m protocol --all",
            "ls 1_deposition",
        ],
    },
    "open": {
        "usage": "open -m <mode> [flags] [args]",
        "desc": "Open project/protocol/step — sets session context (Group 2).",
        "subcommands": {
            "open -m project <name>":   {"desc": "Open a project and set context (was 'project open <name>')", "usage": "open -m project my_project"},
            "open -m protocol -n <name>":{"desc": "Open protocol and set session", "usage": "open -m protocol -n doping"},
            "open -m step <step_id>":   {"desc": "Open specific step within current protocol", "usage": "open -m step 1_deposition"},
        },
        "examples": [
            "open -m project my_project",
            "open -m protocol -n doping",
            "open -m step 1_deposition",
            "# After: plot --fzf auto-uses protocol files",
            "# After: analyze -f file --peaks uses protocol context",
        ],
    },
    "close": {
        "usage": "close -m step|protocol|project",
        "desc": "Close context with auto-save (Group 2). Saves state before clearing context.",
        "subcommands": {
            "close -m step":      {"desc": "Close current step, auto-save step state", "usage": "close -m step"},
            "close -m protocol":  {"desc": "Close current protocol, auto-save protocol + step state", "usage": "close -m protocol"},
            "close -m project":   {"desc": "Close current project, auto-save all context state", "usage": "close -m project"},
        },
        "examples": [
            "close -m step",
            "close -m protocol",
            "close -m project",
        ],
    },
    "status": {
        "usage": "status [-m project|protocol]",
        "desc": "Show current context status (Group 3).",
        "subcommands": {
            "status":               {"desc": "Show full context tree", "usage": "status"},
            "status -m project":    {"desc": "Show project-level context", "usage": "status -m project"},
            "status -m protocol":   {"desc": "Show protocol context and steps", "usage": "status -m protocol"},
        },
        "examples": [
            "status",
            "status -m project",
            "status -m protocol",
        ],
    },
    "results": {
        "usage": "results [flags]",
        "desc": "List saved results by protocol and step (Group 3).",
        "subcommands": {},
        "examples": [
            "results",
        ],
    },
    "ext": {
        "usage": "ext <name> <subcommand> [args...]",
        "desc": "Unified extension interface (Group 4). Dispatch to registered extensions.",
        "subcommands": {
            "ext memristor init":     {"desc": "Scaffold a devices.yaml for memristor array", "usage": "ext memristor init --rows 4 --cols 4 --label 'My Device'"},
            "ext memristor ls":       {"desc": "List devices or matrix map", "usage": "ext memristor ls [--matrix]"},
            "ext memristor add":      {"desc": "Add file to a matrix point", "usage": "ext memristor add --row 0 --col 0 --file data.txt [--fzf]"},
            "ext memristor rm":       {"desc": "Remove file, technique, or point", "usage": "ext memristor rm --row 0 --col 0"},
            "ext memristor info":     {"desc": "Show detailed point info", "usage": "ext memristor info --row 0 --col 0"},
            "ext memristor sync":     {"desc": "Sync sweep metadata from data files", "usage": "ext memristor sync"},
            "ext memristor validate": {"desc": "Validate device configuration", "usage": "ext memristor validate"},
            "ext memristor stats":    {"desc": "Aggregate statistics across array", "usage": "ext memristor stats"},
            "ext memristor check":    {"desc": "List unassigned files in step dir", "usage": "ext memristor check"},
            "ext list":               {"desc": "List all available extensions", "usage": "ext list"},
            "ext help <name>":        {"desc": "Show extension help", "usage": "ext help memristor"},
        },
        "examples": [
            "ext memristor init --rows 4 --cols 4 --label 'ITO/PDA/Ta'",
            "ext memristor ls --matrix",
            "ext memristor add --row 0 --col 0 --file D1_r0c0_IV_set.txt",
            "ext memristor stats",
            "ext list",
            "ext help memristor",
        ],
    },
    "plot": {
        "usage": "plot [--fzf | -f file1,file2 [options]]",
        "desc": "Plot data — interactive or direct (Group 3). Accepts technique, analyze, style, and figure options.",
        "subcommands": {
            "plot --fzf":        {"desc": "Interactive: fzf file selection then prompts", "usage": "plot --fzf"},
            "plot -f <file>":    {"desc": "Single file direct plot", "usage": "plot -f 2105_CV.txt [options]"},
            "plot -f <f1>,<f2>": {"desc": "Multiple files overlay", "usage": "plot -f 2105_CV.txt,2106_CV.txt [options]"},
            "plot -theme":       {"desc": "Configure plot theme (placeholder)", "usage": "plot -theme"},
            "plot results":      {"desc": "List all saved figures in current project", "usage": "plot results"},
            "plot open <name>":  {"desc": "Open a saved figure with system viewer", "usage": "plot open ca_potential-variation.pdf"},
            "plot delete <name>":{"desc": "Delete a saved figure", "usage": "plot delete ca_potential-variation.pdf"},
        },
        "flags": {
            "-n, --name": {"desc": "Output filename (format from extension: .svg, .pdf, .png)"},
            "--type":     {"desc": "Plot type: line|scatter"},
            "--color":    {"desc": "Color: #1f77b4, red"},
            "--linewidth":{"desc": "Line width: 1.5, 2.0"},
            "--linestyle":{"desc": "Line style: solid, dashed, dotted"},
            "--marker":   {"desc": "Marker: o, s, ^, D"},
            "--markersize":{"desc": "Marker size: 8, 10"},
            "--cmap":     {"desc": "Colormap: viridis, plasma (scatter only)"},
            "--title":    {"desc": "Plot title"},
            "--xlabel":   {"desc": "X-axis label"},
            "--ylabel":   {"desc": "Y-axis label"},
            "--xlim":     {"desc": "X-axis limits: -0.5,0.5"},
            "--ylim":     {"desc": "Y-axis limits: -1e-3,1e-3"},
            "--zoom":     {"desc": "Axis limits: x1,x2,y1,y2 or x1,x2"},
            "--size":     {"desc": "Figure size: 8,6"},
            "--dpi":      {"desc": "Figure resolution: 150, 300"},
            "--grid":     {"desc": "Show grid"},
            "--legend":   {"desc": "Show legend"},
            "--label-name": {"desc": "Custom legend labels (comma-separated, overlay only)"},
        },
        "examples": [
            "plot --fzf",
            "plot -f 2105_CV.txt",
            "plot -f 2105_CV.txt --peaks --charge -n analysis.pdf --grid",
            "plot -f 2105_CV.txt,2106_CV.txt --label-name 0V,0.25V",
            "plot results",
            "plot open ca_potential-variation.pdf",
            "plot delete ca_potential-variation.pdf",
            "plot -theme",
        ],
    },
    "analyze": {
        "usage": "analyze -f <file> [options]",
        "desc": "Analyze data — peaks, fit, circuit (Group 3). No plotting, only analysis results.",
        "flags": {
            "--peaks":    {"desc": "Find CV peaks"},
            "--charge":   {"desc": "Integrate CV charge"},
            "--fit":      {"desc": "Fit CA decay"},
            "--circuit":  {"desc": "EIS circuit model: RRC, RQR, etc."},
            "--kk":       {"desc": "Kramers-Kronig validation (EIS)"},
        },
        "examples": [
            "analyze -f 2105_CV.txt --peaks --charge",
            "analyze -f 2104_CA.txt --fit",
            "analyze -f 2106_EIS.mpt --circuit RRC --kk",
        ],
    },
    "config": {
        "usage": "config <subcommand> [args]",
        "desc": "Configure themes, techniques, and devices (Group 3).",
        "subcommands": {
            "config theme list":                        {"desc": "List available themes", "usage": "config theme list"},
            "config theme set <name>":                  {"desc": "Set active theme", "usage": "config theme set <name>"},
            "config list techniques":                   {"desc": "List all configured techniques", "usage": "config list techniques"},
            "config list devices <technique>":           {"desc": "List devices for a technique", "usage": "config list devices iv-sweep"},
            "config set technique <name> <device>":      {"desc": "Set default device for a technique", "usage": "config set technique iv-sweep keithley-2400"},
            "config edit <technique>":                   {"desc": "Open technique config in $EDITOR", "usage": "config edit iv-sweep"},
        },
        "examples": [
            "config theme list",
            "config theme set tufte",
            "config theme set dark",
            "config list techniques",
            "config list devices iv-sweep",
            "config set technique iv-sweep keithley-2400",
            "config edit iv-sweep",
        ],
    },
    "techniques": {
        "usage": "techniques",
        "desc": "List available techniques and usage guide (Group 4).",
        "subcommands": {},
        "examples": [
            "techniques",
        ],
    },
}


def show_top_help() -> None:
    accent = RAW_COLORS.get("accent", "green")
    dim = RAW_COLORS.get("dim", "bright_black")
    accent_r = RICH_STYLES.get("accent", "green")

    console.print()
    console.print(Panel(
        f"[bold]sci[/bold] — Scientific Data Analysis CLI  [dim]v{__version__}[/dim]\n"
        "[dim]Work seamlessly with experimental data from the command line.[/dim]",
        border_style=accent_r,
    ))
    console.print()

    for section_name, cmd_names in HELP_SECTIONS.items():
        console.print(f"  [bold]{section_name}[/bold]")
        for name in cmd_names:
            desc = COMMAND_DESCRIPTIONS.get(name, "")
            console.print(f"    {name:<18} [dim]{desc}[/dim]")
        console.print()

    console.print(f"  [{dim}]Use `sci <command> --help` for more details on a command.[/{dim}]")
    console.print(f"  [{dim}]Use `sci` or `sci --repl` for the interactive REPL shell.[/{dim}]")
    console.print()


def show_command_help(cmd: str) -> None:
    accent = RICH_STYLES.get("accent", "green")
    dim = RAW_COLORS.get("dim", "bright_black")

    info = COMMAND_HELP.get(cmd)
    if not info:
        console.print(f"[yellow]No help available for '{cmd}'.[/yellow]")
        return

    console.print()
    console.print(f"  [bold]{info['usage']}[/bold]")
    console.print(f"  [dim]{info['desc']}[/dim]")
    console.print()

    subcmds = info.get("subcommands")
    if subcmds:
        console.print(f"  [bold]SUBCOMMANDS[/bold]")
        for name, sub in subcmds.items():
            console.print(f"    {name:<30} [dim]{sub['desc']}[/dim]")
            console.print(f"    {'':<30}  Usage: [{accent}]{sub['usage']}[/{accent}]")
        console.print()

    flags = info.get("flags")
    if flags:
        console.print(f"  [bold]FLAGS / OPTIONS[/bold]")
        for name, flag in flags.items():
            req = " [bold](required)[/bold]" if flag.get("required") else ""
            console.print(f"    {name:<25} [dim]{flag['desc']}[/dim]{req}")
        console.print()

    examples = info.get("examples")
    if examples:
        console.print(f"  [bold]EXAMPLES[/bold]")
        for ex in examples:
            console.print(f"    [{accent}]{ex}[/{accent}]")
        console.print()

    console.print(f"  [{dim}]Use `s-cli {cmd} --help` for more details.[/{dim}]")
    console.print()


def show_subcommand_help(cmd: str, sub: str) -> None:
    info = COMMAND_HELP.get(cmd)
    if not info:
        show_top_help()
        return
    subcmds = info.get("subcommands", {})
    sub_info = subcmds.get(sub)
    if not sub_info:
        show_command_help(cmd)
        return

    accent = RICH_STYLES.get("accent", "green")
    console.print()
    console.print(f"  [bold]{sub_info['usage']}[/bold]")
    console.print(f"  [dim]{sub_info['desc']}[/dim]")
    console.print()


def help_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_top_help()
    else:
        cmd = args[0]
        if cmd in COMMAND_HELP:
            if len(args) > 1:
                show_subcommand_help(cmd, args[1])
            else:
                show_command_help(cmd)
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            show_top_help()