"""Help system — builds Rich-formatted hierarchical help text."""

from typing import Dict

from rich.console import Console
from rich.panel import Panel

from science_cli import __version__
from science_cli.theme import RAW_COLORS, RICH_STYLES

console = Console()

HELP_SECTIONS = {
    "GROUP 1: FILE MANAGEMENT": ["add", "delete", "edit", "ls"],
    "GROUP 2: CONTEXT & INFORMATION": ["open", "close", "config", "status", "results", "info", "chat"],
    "GROUP 3: LIBRARY PLOTTING": ["plot", "analyze", "---", "serve", "---", "memristor", "raman", "uv-vis", "iv", "ec", "afm"],
    "ADDITIONAL": ["help", "version", "clear", "history"],
}

COMMAND_DESCRIPTIONS = {
    "add":     "Add project/protocol/metadata/data",
    "delete":  "Delete protocol/metadata",
    "edit":    "Edit protocol/metadata",
    "ls":      "List projects/protocols/steps/files",
    "open":    "Open project/protocol/step",
    "close":   "Close context with auto-save",
    "config":  "Configure settings — themes, techniques, devices, grammar",
    "status":  "Show current context tree (project/protocol/step)",
    "results": "Browse saved figures by protocol and step (fzf)",
    "info":    "Project manifest — machine-readable JSON via --json flag",
    "chat":    "AI chat — natural language to plot commands via LLM",
    "plot":    "Generic plot — fzf-based, auto-detects technique",
    "analyze": "Generic analyze — fzf-based, technique-aware",
    "serve":   "Start interactive dashboard server at localhost:8000",
    "memristor": "Memristor IV/endurance/retention — plot, dashboard, sync",
    "raman":   "Raman spectroscopy — list, inspect, plot, analyze",
    "uv-vis":  "UV-Vis spectroscopy — list, inspect, plot, analyze",
    "iv":      "IV sweep analysis (coming)",
    "ec":      "Electrochemistry CV/CA/EIS — list, inspect, plot, analyze",
    "afm":     "AFM/SPM image — ls, info, plot, analyze, export",
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
            "add -m protocol":    {"desc": "Create a protocol", "usage": "add -m protocol -n <name> [--desc <text>] [--step s1,s2] [-t ec-cv,ec-ca] [-d keithley-2400,keysight-b1500]"},
            "add -m metadata":    {"desc": "Update protocol step metadata (technique + device)", "usage": "add -m metadata --step <steps> -pt <protocol> -t <techniques> [-d <devices>]"},
            "add -m data":        {"desc": "Interactive file assignment via fzf (shows assigned/unassigned status)", "usage": "add -m data [--all]"},
        },
        "flags": {
            "OPERATION": {
                "-n, --name":     {"desc": "Protocol name (required for protocol mode)"},
                "--desc":         {"desc": "Protocol description"},
                "--step":         {"desc": "Step ID(s), comma-separated"},
                "-t, --technique":{"desc": "Technique(s), comma-separated"},
                "-d, --device":   {"desc": "Device name(s) per step, comma-separated (e.g. keithley-2400)"},
                "-pt, --protocol":{"desc": "Protocol name (for metadata mode)"},
                "--all":          {"desc": "Assign all selected files to one step (skip per-file prompt)"},
            },
        },
        "examples": [
            "add -m project my-project",
            "add -m protocol -n doping --step 1_deposition,2_characterization -t ec-ca,ec-cv -d keithley-2400,keysight-b1500",
            "add -m metadata -step 1_deposition -pt doping -t ec-ca -d keithley-2400",
            "add -m data",
            "add -m data --all",
        ],
    },
    "edit": {
        "usage": "edit -m <mode> [flags]",
        "desc": "Edit protocol/metadata/data (Group 1).",
        "subcommands": {
            "edit -m protocol":    {"desc": "Edit protocol name/description/steps/techniques/devices, remove or reorder steps", "usage": "edit -m protocol -n <name> [--nn <new-name>] [--desc <text>] [--step s1,s2] [-t ec-cv,ec-ca] [-d keithley-2400] [--rm-step <name>] [--reorder s1,s2,...]"},
            "edit -m metadata":    {"desc": "Edit file assignments, techniques, and devices", "usage": "edit -m metadata -n <name> [--step s1] [-t ec-cv] [-d keithley-2400] [--files f1.txt,f2.txt]"},
            "edit -m data":        {"desc": "Move/reassign files between steps (interactive fzf)", "usage": "edit -m data"},
        },
        "flags": {
            "OPERATION": {
                "-n, --name":     {"desc": "Protocol name (required)"},
                "--nn, --new-name":{"desc": "New protocol name (rename)"},
                "--desc":         {"desc": "New description"},
                "--step":         {"desc": "Step ID(s), comma-separated"},
                "-t, --technique":{"desc": "Technique(s), comma-separated"},
                "-d, --device":   {"desc": "Device name(s) per step, comma-separated"},
                "--rm-step":      {"desc": "Step name to remove from protocol"},
                "--reorder":      {"desc": "Comma-separated step order (e.g. 1_cv,2_ca,3_eis)"},
                "--files":        {"desc": "File(s), comma-separated"},
            },
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
        "desc": "Delete protocol/metadata/data files (Group 1).",
        "subcommands": {
            "delete -m protocol":    {"desc": "Delete a protocol and all its step folders", "usage": "delete -m protocol -n <name>"},
            "delete -m metadata":    {"desc": "Clear file assignments from protocol", "usage": "delete -m metadata -n <name> [--step s1] [--all]"},
            "delete -m data":        {"desc": "Remove data files from protocol YAML (fzf)", "usage": "delete -m data [--step <name>]"},
        },
        "flags": {
            "OPERATION": {
                "-n, --name": {"desc": "Protocol name (required)"},
                "--step":     {"desc": "Step ID(s) to clear, comma-separated"},
                "--all":      {"desc": "Clear file assignments from all protocols"},
            },
        },
        "examples": [
            "delete -m protocol -n doping",
            "delete -m metadata -n doping --step 1_deposition",
            "delete -m metadata --all",
            "delete -m data",
            "delete -m data --step 4_iv-sweep",
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
            "ls -m protocol -n <name>":{"desc": "List specific protocol by name", "usage": "ls -m protocol -n 1_protocol-1"},
            "ls -n <step>":         {"desc": "List files in specific step", "usage": "ls -n step-4"},
        },
        "examples": [
            "ls",
            "ls -m project",
            "ls -m protocol",
            "ls -m protocol --all",
            "ls -m protocol -n 1_protocol-1",
            "ls -n step-4",
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
        "desc": "Show current context status (Group 2).",
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
        "usage": "results",
        "desc": "Browse saved figures by protocol and step via fzf (Group 2).",
        "subcommands": {},
        "examples": [
            "results",
        ],
    },
    "serve": {
        "usage": "serve [--port 8000] [--project /path] [--dev] [--open]",
        "desc": "Start interactive dashboard server (Group 3). Serves frontend on localhost with REST API.",
        "subcommands": {},
        "flags": {
            "--port":     {"desc": "Port to listen on (default: 8000 or $SCI_SERVE_PORT)"},
            "--project":  {"desc": "Override project path (otherwise uses session)"},
            "--dev":      {"desc": "Enable CORS and verbose logging"},
            "--open":     {"desc": "Auto-open browser on start"},
        },
        "examples": [
            "serve",
            "serve --port 8080",
            "serve --dev --open",
            "serve --project /path/to/project",
        ],
    },
    "memristor": {
        "usage": "memristor <subcommand> [args...]",
        "desc": "Crossbar device manager (Group 3). Manage memristor array devices.",
        "subcommands": {
            "memristor init":         {"desc": "Scaffold a devices.yaml for memristor array", "usage": "memristor init --matrix r6-c6 [--label 'My Device'] [--steps iv:4_iv]"},
            "memristor ls":           {"desc": "List devices or matrix map", "usage": "memristor ls [--matrix]"},
            "memristor add":          {"desc": "Add file to a matrix point (fzf if no --file)", "usage": "memristor add --row 0 --col 0 [--file data.txt]"},
            "memristor rm":           {"desc": "Remove file, technique, or point", "usage": "memristor rm --row 0 --col 0"},
            "memristor info":         {"desc": "Show detailed point info", "usage": "memristor info --row 0 --col 0"},
            "memristor sync":         {"desc": "Sync sweep metadata from data files", "usage": "memristor sync"},
            "memristor validate":     {"desc": "Validate device configuration", "usage": "memristor validate"},
            "memristor stats":        {"desc": "Aggregate statistics across array", "usage": "memristor stats"},
            "memristor check":        {"desc": "List unassigned files in step dir", "usage": "memristor check"},
            "memristor plot":         {"desc": "Generate IV curve SVGs — fzf or batch", "usage": "memristor plot [--overlay] [--all]"},
            "memristor dashboard":    {"desc": "Generate HTML viewer for plotted IV SVGs", "usage": "memristor dashboard [--output path] [--open]"},
        },
        "examples": [
            "memristor init --matrix r6-c6 --steps iv:4_iv",
            "memristor init --matrix r6-c6 --label 'ITO/PDA/Ta' --steps iv:4_iv,endurance:5_endurance",
            "memristor ls --matrix",
            "memristor add --row 0 --col 0 --file D1_r0c0_IV_set.txt",
            "memristor stats",
            "memristor plot",
            "memristor plot --overlay",
            "memristor dashboard --open",
        ],
    },
    "raman": {
        "usage": "raman <subcommand> [args...]",
        "desc": "Raman spectroscopy: list, inspect, plot, and analyze spectra (Group 3).",
        "subcommands": {
            "raman ls":               {"desc": "List Raman files in current project", "usage": "raman ls [--step <name>]"},
            "raman info":             {"desc": "Show full header metadata (laser, grating, etc.)", "usage": "raman info [file]"},
            "raman plot":             {"desc": "Plot Raman spectrum with metadata annotation", "usage": "raman plot [file] [--grid] [--name out.pdf]"},
            "raman analyze":          {"desc": "Preprocessing pipeline (denoise → baseline → norm → peak detect) via RamanSPy. Enhanced analysis plot (raw + baseline + corrected + annotated peaks). Automatic text report with metadata, pipeline, peaks table, and summary. --ai mode: uses sci-raman opencode agent for intelligent flag recommendations via file metadata analysis. --overlay: overlay all processed spectra on a single figure. --all: subplot grid with each spectrum in its own panel. Multi-file fzf picker with CSV/PDF export.", "usage": "raman analyze [file] [--ai] [--overlay] [--all] [--denoise savgol|whittaker] [--baseline asls|airpls|arpls|poly|modpoly] [--norm vector|minmax|maxintensity|auc] [--plot]"},
        },
        "flags": {
            "THEME": {
                "--grid":       {"desc": "Show grid (plot subcommand)"},
                "--title":      {"desc": "Plot title"},
                "--xlabel":     {"desc": "X-axis label (default: Raman shift (cm-1))"},
                "--ylabel":     {"desc": "Y-axis label (default: Intensity (counts))"},
                "--xlim":       {"desc": "X-axis limits: 800,1800"},
                "--ylim":       {"desc": "Y-axis limits: 0,10000"},
            },
            "ANALYSIS": {
                "--ai":         {"desc": "Interactive step-by-step wizard for pipeline choices (analyze)"},
                "--denoise":    {"desc": "Denoising method: savgol|whittaker (analyze)"},
                "--baseline":   {"desc": "Baseline method: asls|airpls|arpls|poly|modpoly (analyze)"},
                "--norm":       {"desc": "Normalization method: vector|minmax|maxintensity|auc (analyze)"},
                "--plot":       {"desc": "Generate analysis figure: raw data + baseline + corrected + labeled peaks (analyze)"},
                "--savgol-window": {"desc": "Savitzky-Golay window length, default 9 (analyze)"},
                "--savgol-order":  {"desc": "Savitzky-Golay polynomial order, default 3 (analyze)"},
                "--lam":        {"desc": "Baseline smoothness (asls/airpls/arpls), default 1e7 (analyze)"},
                "--p":          {"desc": "Baseline asymmetry (asls/airpls/arpls), default 0.01 (analyze)"},
                "--overlay":    {"desc": "Single figure with all corrected spectra overlaid (analyze, multi-file)"},
                "--all":        {"desc": "Subplot grid with each corrected spectrum in its own panel (analyze, multi-file)"},
                "--no-legend":  {"desc": "Hide legend (plot and analyze overlay)"},
                "--prominence": {"desc": "Peak prominence threshold, default 500 (analyze)"},
                "--distance":   {"desc": "Min peak separation in cm-1 (analyze)"},
                "--height":     {"desc": "Min peak height in counts (analyze)"},
                "--width":      {"desc": "Min peak width in cm-1 (analyze)"},
            },
            "OUTPUT": {
                "-n, --name":   {"desc": "Output filename/prefix (plot, analyze)"},
                "--step":       {"desc": "Step name (ls subcommand)"},
            },
        },
        "examples": [
            "raman ls",
            "raman ls --step 3-raman",
            "raman info",
            "raman info 260526_PDA-ITO_raman_01.txt",
            "raman plot",
            "raman plot 260526_PDA-ITO_raman_01.txt --name raman_spectrum.pdf",
            "raman analyze --ai",
            "raman analyze 260526_PDA-ITO_raman_01.txt --denoise whittaker --baseline airpls --norm vector --prominence 1000 --plot",
            "raman analyze --overlay",
            "raman analyze --overlay --no-legend",
            "raman analyze --all",
            "raman analyze --ai --overlay",
        ],
    },
    "uv-vis": {
        "usage": "uv-vis <subcommand> [args...]",
        "desc": "UV-Vis spectroscopy: list, inspect, plot, and analyze spectra (Group 3).",
        "subcommands": {
            "uv-vis ls":               {"desc": "List UV-Vis files in current project", "usage": "uv-vis ls"},
            "uv-vis info":             {"desc": "Show header and data range details", "usage": "uv-vis info [file]"},
            "uv-vis plot":             {"desc": "Plot UV-Vis spectrum with standard axis labels", "usage": "uv-vis plot [file] [--grid] [--name out.pdf]"},
            "uv-vis analyze":          {"desc": "Calculate range, min/max peaks, inflection onset slope, and CSV export", "usage": "uv-vis analyze [file] [--name prefix]"},
        },
        "flags": {
            "THEME": {
                "--grid":       {"desc": "Show grid (plot)"},
                "--title":      {"desc": "Plot title"},
                "--xlabel":     {"desc": "X-axis label (default: Wavelength (nm))"},
                "--ylabel":     {"desc": "Y-axis label (default: Transmission (%))"},
                "--xlim":       {"desc": "X-axis limits: 300,800"},
                "--ylim":       {"desc": "Y-axis limits"},
            },
            "OUTPUT": {
                "-n, --name":   {"desc": "Output filename/prefix (plot, analyze)"},
            },
        },
        "examples": [
            "uv-vis ls",
            "uv-vis info",
            "uv-vis plot",
            "uv-vis plot 260526_PDA-ITO_uvvis_01.txt --name uv_vis.pdf",
            "uv-vis analyze",
        ],
    },
    "ec": {
        "usage": "ec <subcommand> [args...]",
        "desc": "Electrochemistry CV/CA/EIS: list, inspect, plot, and analyze (Group 3).",
        "subcommands": {
            "ec ls":                  {"desc": "List Electrochemistry files in current project", "usage": "ec ls"},
            "ec info":                {"desc": "Show columns, shape, and value range", "usage": "ec info [file]"},
            "ec plot":                {"desc": "Plot Cyclic Voltammetry, Chronoamperometry, or EIS Nyquist/Bode", "usage": "ec plot [file] [--grid] [--name out.pdf]"},
            "ec analyze":             {"desc": "Run peak finding (CV), Cottrell fit (CA), or circuit fitting (EIS)", "usage": "ec analyze [file] [--peaks] [--charge] [--fit] [--circuit RRC] [--kk]"},
        },
        "flags": {
            "THEME": {
                "--grid":       {"desc": "Show grid"},
                "--title":      {"desc": "Plot title"},
            },
            "ANALYSIS": {
                "--peaks":      {"desc": "Find CV redox peaks"},
                "--charge":     {"desc": "Integrate CV charge"},
                "--fit":        {"desc": "Fit CA decay curve to Cottrell equation"},
                "--circuit":    {"desc": "EIS equivalent circuit model, e.g. RRC, RQR"},
                "--kk":         {"desc": "Validate EIS impedance data with Kramers-Kronig relation"},
            },
            "OUTPUT": {
                "-n, --name":   {"desc": "Output filename/prefix (plot, analyze)"},
            },
        },
        "examples": [
            "ec ls",
            "ec info",
            "ec plot",
            "ec analyze --peaks --charge",
            "ec analyze --circuit RRC --kk",
        ],
    },
    "plot": {
        "usage": "plot [options]",
        "desc": "Plot data — fzf-based, auto-detects technique (Group 3). Accepts technique, analyze, style, and figure options.",
        "subcommands": {
            "plot":                {"desc": "Interactive: fzf file selection then prompts", "usage": "plot"},
            "plot --overlay":      {"desc": "Interactive: overlay all chosen files in one plot", "usage": "plot --overlay"},
            "plot --all":          {"desc": "Interactive: export each file individually", "usage": "plot --all"},
            "plot results":        {"desc": "List all saved figures in current project", "usage": "plot results"},
            "plot open <name>":    {"desc": "Open a saved figure with system viewer", "usage": "plot open ca_potential-variation.pdf"},
            "plot delete <name>":  {"desc": "Delete a saved figure", "usage": "plot delete ca_potential-variation.pdf"},
        },
        "flags": {
            "THEME": {
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
            "OUTPUT": {
                "-n, --name": {"desc": "Output filename (format from extension: .svg, .pdf, .png)"},
            },
        },
        "examples": [
            "plot",
            "plot --overlay",
            "plot --overlay --grid --legend",
            "plot --all",
            "plot results",
            "plot open ca_potential-variation.pdf",
            "plot delete ca_potential-variation.pdf",
        ],
    },
    "analyze": {
        "usage": "analyze [options]",
        "desc": "Analyze data — fzf-based, technique-aware analysis (Group 3). No plotting, only analysis results.",
        "flags": {
            "ANALYSIS": {
                "--peaks":    {"desc": "Find CV peaks"},
                "--charge":   {"desc": "Integrate CV charge"},
                "--fit":      {"desc": "Fit CA decay"},
                "--circuit":  {"desc": "EIS circuit model: RRC, RQR, etc."},
                "--kk":       {"desc": "Kramers-Kronig validation (EIS)"},
            },
        },
        "examples": [
            "analyze --peaks --charge",
            "analyze --fit",
            "analyze --circuit RRC --kk",
        ],
    },
    "afm": {
        "usage": "afm <subcommand> [args...]",
        "desc": "AFM/SPM image analysis: list, inspect, plot, analyze, and export (Group 3).",
        "subcommands": {
            "afm ls":               {"desc": "List AFM files in current project", "usage": "afm ls"},
            "afm info":             {"desc": "Show file metadata and available channels", "usage": "afm info [file]"},
            "afm plot":             {"desc": "Plot AFM topography image with height distribution", "usage": "afm plot [file] [--cmap viridis|gray|terrain] [--name out.pdf]"},
            "afm analyze":          {"desc": "Compute surface roughness, line profiles, height distribution, and PSD", "usage": "afm analyze [file] [--psd] [--export prefix]"},
            "afm export":           {"desc": "Export AFM image to PNG/CSV/NPY", "usage": "afm export [file] --format png|csv|npy [--channel <name>]"},
            "afm open":             {"desc": "Open .ibw file in Gwyddion, interactively record thickness, roughness (Sa/Sq), and material to afm_analysis.yaml", "usage": "afm open"},
        },
        "flags": {
            "THEME": {
                "--cmap":       {"desc": "Colormap: viridis, gray, terrain, plasma, inferno (default: viridis)"},
                "--grid":       {"desc": "Show grid"},
                "--title":      {"desc": "Plot title"},
                "--dpi":        {"desc": "Figure resolution (default: 300)"},
            },
            "ANALYSIS": {
                "--channel":    {"desc": "Channel name or index (default: first)"},
                "--psd":        {"desc": "Include power spectral density in analysis output"},
            },
            "OUTPUT": {
                "-n, --name":   {"desc": "Output filename/prefix (plot, analyze, export)"},
                "--format":     {"desc": "Export format: png, csv, npy (export subcommand)"},
            },
        },
        "examples": [
            "afm ls",
            "afm info",
            "afm info 260526_PDA-ITO_topography.gwy",
            "afm plot",
            "afm plot sample.gwy --cmap terrain --name topography.pdf",
            "afm analyze",
            "afm analyze sample.gwy --psd --export results/sample",
            "afm export sample.gwy --format csv",
            "afm export sample.gwy --format png --channel Phase --cmap gray",
            "afm open",
        ],
    },
    "config": {
        "usage": "config <subcommand> [args]",
        "desc": "Configure themes, techniques, devices, and naming grammar (Group 2).",
        "subcommands": {
            "config theme list":                            {"desc": "List available themes", "usage": "config theme list"},
            "config theme set <name>":                      {"desc": "Set active theme", "usage": "config theme set <name>"},
            "config init":                                  {"desc": "Generate a default config file", "usage": "config init [--global|--project]"},
            "config show":                                  {"desc": "Show merged config (global + project)", "usage": "config show [--global|--project]"},
            "config list techniques":                       {"desc": "List all configured techniques", "usage": "config list techniques"},
            "config list devices <technique>":               {"desc": "List devices for a technique", "usage": "config list devices iv-sweep"},
            "config list grammar":                          {"desc": "List naming grammar patterns", "usage": "config list grammar"},
            "config set technique <name> <device>":          {"desc": "Set default device for a technique", "usage": "config set technique iv-sweep keithley-2400"},
            "config edit <technique>":                      {"desc": "Open technique config in $EDITOR", "usage": "config edit iv-sweep [--force]"},
            "config edit --global":                         {"desc": "Edit global config.yaml in $EDITOR", "usage": "config edit --global"},
            "config edit devices":                          {"desc": "Edit global device registry in $EDITOR", "usage": "config edit devices"},
            "config edit grammar":                          {"desc": "Edit naming grammar in $EDITOR", "usage": "config edit grammar"},
            "config edit techniques --global":               {"desc": "Edit global technique registry in $EDITOR", "usage": "config edit techniques --global"},
            "config devices list":                          {"desc": "List devices in global registry", "usage": "config devices list"},
            "config grammar list":                          {"desc": "List naming grammar patterns", "usage": "config grammar list"},
            "config grammar edit":                          {"desc": "Edit naming grammar in $EDITOR", "usage": "config grammar edit"},
        },
        "examples": [
            "config theme list",
            "config theme set tufte",
            "config theme set dark",
            "config init --global",
            "config show",
            "config list techniques",
            "config list devices iv-sweep",
            "config list grammar",
            "config set technique iv-sweep keithley-2400",
            "config edit iv-sweep",
            "config edit --global",
            "config edit devices",
            "config edit grammar",
            "config edit techniques --global",
            "config devices list",
            "config grammar edit",
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
            if name == "---":
                console.print(f"    [dim]── technique-specific[/dim]")
                continue
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
        console.print("  [bold]SUBCOMMANDS[/bold]")
        for name, sub in subcmds.items():
            console.print(f"    {name:<30} [dim]{sub['desc']}[/dim]")
            console.print(f"    {'':<30}  Usage: [{accent}]{sub['usage']}[/{accent}]")
        console.print()

    flags = info.get("flags")
    if flags:
        # Check if categorized (first value is a dict of flags) or flat
        first_val = next(iter(flags.values()))
        if isinstance(first_val, dict) and "desc" not in first_val:
            for category, cat_flags in flags.items():
                console.print(f"  [bold]{category}[/bold]")
                for name, flag in cat_flags.items():
                    req = " [bold](required)[/bold]" if flag.get("required") else ""
                    console.print(f"    {name:<25} [dim]{flag['desc']}[/dim]{req}")
                console.print()
        else:
            console.print("  [bold]FLAGS / OPTIONS[/bold]")
            for name, flag in flags.items():
                req = " [bold](required)[/bold]" if flag.get("required") else ""
                console.print(f"    {name:<25} [dim]{flag['desc']}[/dim]{req}")
        console.print()

    examples = info.get("examples")
    if examples:
        console.print("  [bold]EXAMPLES[/bold]")
        for ex in examples:
            console.print(f"    [{accent}]{ex}[/{accent}]")
        console.print()

    console.print(f"  [{dim}]Use `sci {cmd} --help` for more details.[/{dim}]")
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
