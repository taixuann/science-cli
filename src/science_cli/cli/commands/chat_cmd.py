"""chat command — natural language to sci CLI commands via LLM."""

import json
import os
import subprocess
import sys
import urllib.request

from science_cli.cli.help import show_command_help

CHAT_SYSTEM_PROMPT = """You are a science-cli assistant. Your job is to convert natural language requests
into sci CLI commands. You MUST respond with ONLY the command to execute, nothing else.

Available commands and their flags:
  sci plot <file> [--loglog] [--type line|scatter] [--color <color>] [--linewidth <n>]
      [--xlabel <label>] [--ylabel <label>] [--title <title>] [--zoom x1,x2,y1,y2]
      [--grid] [--legend] [--theme <theme>] [--dpi <n>] [-n <output_name>.pdf]
      [--overlay <file1,file2,...>] [--label-name <label1,label2,...>]
  sci memristor dashboard [--open]
  sci memristor plot <device_id> [--type switching|endurance|retention]
  sci raman plot <file> [--type line] [--color] [--grid]
  sci analyze <file> [--type line|scatter] [--loglog]
  sci eis <file> [--nyquist] [--bode] [--circuit]
  sci ls [--json] [-m project|protocol] [-n <name>]
  sci status [--json]
  sci info [--json]
  sci results [--fzf]
Theme names: publication-nature, publication-acs, poster, dark, default, tufte, acs-annotated

Default theme is publication-nature. Use --theme to override.

Example mappings:
  "plot the IV data" → sci plot protocol/<protocol>/<step>/<file>.csv
  "plot with loglog" → sci plot <file> --loglog
  "show me the dashboard" → sci memristor dashboard --open
  "compare these files" → sci plot --overlay file1,file2,file3 --label-name label1,label2,label3
  "use nature style" → sci plot <file> --theme publication-nature
  "add grid and legend" → sci plot <file> --grid --legend
  "zoom in on x from 0 to 1" → sci plot <file> --zoom 0,1
  "show project info" → sci info --json

RULES:
1. Return ONLY the command, nothing else. No markdown, no backticks, no explanation.
2. Use file paths from the project context if provided.
3. Never make up file paths — use what's in the context.
4. If you don't have enough context, suggest the user runs 'sci info --json' first.
5. All plot output goes to PDF. Include -n <name>.pdf if a name is implied."""


def chat_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("chat")
        return

    message = " ".join(args).strip()
    if not message:
        from rich.console import Console
        Console().print("[yellow]Usage: chat <natural language request>[/yellow]")
        Console().print("[dim]Example: chat plot the IV data with loglog axes[/dim]")
        return

    _chat_execute(message, auto_confirm=True)


def _chat_execute(message: str, auto_confirm: bool = False) -> None:
    from rich.console import Console

    console = Console()

    ctx = _get_project_context()
    prompt = _build_prompt(message, ctx)

    console.print("[dim]Thinking...[/dim]")
    command = _call_llm(prompt)

    if not command:
        console.print("[red]Failed to get a response. Check API key and network.[/red]")
        return

    console.print(f"[bold cyan]→[/bold cyan] [white]{command}[/white]")

    if not auto_confirm:
        console.print("[dim]Execute? [[bold green]Enter[/bold green]] / [[bold red]Ctrl+C[/bold red] to cancel[/dim] ", end="")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return

    _run_command(command)


def _get_project_context() -> dict | None:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "science_cli", "info", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _build_prompt(message: str, ctx: dict | None) -> str:
    prompt = CHAT_SYSTEM_PROMPT

    if ctx:
        session = ctx.get("session", {})
        project = ctx.get("project", {})
        protocols = ctx.get("protocols", [])
        themes = ctx.get("themes", [])
        plot_hints = ctx.get("plot_hints", {})

        prompt += f"\n\n## Current Session\n"
        prompt += f"Project: {session.get('last_project', 'none')}\n"
        prompt += f"Protocol: {session.get('last_protocol', 'none')}\n"
        prompt += f"Step: {session.get('last_step', 'none')}\n"
        prompt += f"Theme: {session.get('theme', 'publication-nature')}\n"

        if project:
            prompt += f"\nProject path: {project.get('path', '')}\n"

        if themes:
            prompt += f"\nAvailable themes: {', '.join(themes)}\n"

        if protocols:
            prompt += "\n## Project Structure\n"
            for proto in protocols[:5]:
                prompt += f"\nProtocol: {proto['name']}\n"
                prompt += f"  Description: {proto.get('description', '')}\n"
                for step in proto.get("steps", [])[:10]:
                    files = [f["name"] for f in step.get("files", [])[:5]]
                    prompt += f"  Step: {step['name']} (technique: {step.get('technique', '')}, files: {', '.join(files)}{'...' if len(step.get('files', [])) > 5 else ''})\n"

        if plot_hints:
            prompt += "\n## Technique Plot Flags\n"
            for tech, hints in plot_hints.items():
                prompt += f"  {tech}: {hints.get('plot_style', '')}\n"

    prompt += f"\n\n## User Request\n{message}\n\n## Command\n"
    return prompt


def _call_llm(prompt: str) -> str:
    api_key = _get_api_key()
    if not api_key:
        return ""

    model = os.environ.get("SCI_LLM_MODEL", "gpt-4o")
    base_url = os.environ.get("SCI_LLM_BASE_URL", "https://api.openai.com/v1")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip()
    except Exception:
        return ""


def _get_api_key() -> str:
    key = os.environ.get("SCI_LLM_API_KEY", "")
    if key:
        return key

    try:
        config_path = os.path.expanduser("~/.config/science-cli/config.yaml")
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        chat_cfg = cfg.get("chat", {})
        key = chat_cfg.get("api_key", "")
        if key:
            return os.path.expandvars(key)
    except Exception:
        pass

    return ""


def _run_command(command: str) -> None:
    args = command.strip().split()
    if not args:
        return

    if args[0] != "sci":
        args = ["sci"] + args

    import subprocess
    subprocess.run([sys.executable, "-m", "science_cli"] + args[1:])
