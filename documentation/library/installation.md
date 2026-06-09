# Installation

## Prerequisites

- **Python 3.9+** (3.11 recommended)
- **pip** or **pipx** (Python package manager)
- **fzf** for interactive file selection (installed automatically by the install scripts)

## Quick Start

The install scripts handle everything: Python check, fzf installation, PATH setup, and `sci config init`.

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.sh | bash
```

### Windows (PowerShell)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
irm https://raw.githubusercontent.com/taixuann/science-cli/main/scripts/install.ps1 | iex
```

## Manual Installation

### pipx (recommended, all platforms)

```bash
pipx install science-cli
```

pipx creates an isolated environment so science-cli doesn't interfere with other Python packages.

### pip (all platforms)

```bash
pip install science-cli
```

### uv (fast, cross-platform)

```bash
uv tool install science-cli
```

### From Source (development)

```bash
git clone https://github.com/taixuann/science-cli.git
cd science-cli
pip install -e .
```

Editable mode (`-e`) lets you pull updates with `git pull` — no reinstall needed.

## fzf Installation

science-cli uses **fzf** for interactive file selection. The install scripts above will install fzf automatically. If you installed manually, install fzf separately:

### macOS

```bash
brew install fzf
```

### Linux

Download the static binary from the [fzf releases page](https://github.com/junegunn/fzf/releases) and place it in `~/.local/bin/fzf`:

```bash
# Example for linux_amd64 (adjust architecture as needed)
curl -fsSL https://github.com/junegunn/fzf/releases/download/v0.58.0/fzf-0.58.0-linux_amd64.tar.gz | tar xz -C ~/.local/bin
```

### Windows

Download `fzf.exe` from the [fzf releases page](https://github.com/junegunn/fzf/releases) and place it in a directory on your PATH, or use winget:

```powershell
winget install fzf
```

If fzf is not found at runtime, science-cli falls back to a built-in selection interface automatically.

## Post-Install

### Initialize Config

Create your global config file so science-cli knows where your projects live:

```bash
sci config init
```

This creates `~/.config/science-cli/config.yaml` with default settings. You can then set your projects directory:

```bash
sci config show           # see current config
sci config edit --global  # edit config file
```

Set `projects_root` to the directory where you keep experiment data. Example:

```yaml
projects_root: /home/user/experiments
```

### Verify Installation

```bash
sci --version
sci --help
```

## Platform Notes

| Platform | Notes |
|----------|-------|
| **macOS** | Works out of the box. Install script installs fzf via brew. |
| **Linux** | Requires Python 3.9+. Install script downloads fzf binary. TUI mode needs a compatible terminal. |
| **Windows** | Requires Python 3.9+. Install script handles Python (via winget), fzf, and PATH management. TUI mode works best with Windows Terminal. Use `sci --repl` or `sci <command>` as alternatives. |

## Troubleshooting

### Windows

| Issue | Solution |
|-------|----------|
| `python` not found | Install Python from [python.org](https://python.org) or `winget install Python.Python.3.11` |
| Execution policy blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| fzf not found | Run the install script, or download `fzf.exe` manually from [GitHub releases](https://github.com/junegunn/fzf/releases) |
| TUI won't launch | Use `sci --repl` or `sci <command>` instead of bare `sci`. TUI needs Windows Terminal or a compatible terminal. |
| `/dev/tty` errors | These are harmless — science-cli falls back to built-in selection. |
| `sci` command not recognized | Add `%USERPROFILE%\.local\bin` and `%LOCALAPPDATA%\science-cli\bin` to PATH. |
| Plot windows don't open | Set `MPLBACKEND=TkAgg` or use `sci plot --save`. |

## Upgrading

```bash
pip install --upgrade science-cli
```

If installed via pipx:

```bash
pipx upgrade science-cli
```

If installed via uv:

```bash
uv tool upgrade science-cli
```

If installed from source:

```bash
cd science-cli
git pull
pip install -e .
```
