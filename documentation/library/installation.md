# Installation

## Prerequisites

- **Python 3.9+** (3.11 recommended)
- **pip** (Python package manager)
- **Git** (for source install)

## Install from PyPI

```bash
pip install science-cli
```

## Install from Source

```bash
git clone https://github.com/taixuann/science-cli.git
cd science-cli
pip install -e .
```

Editable mode (`-e`) lets you pull updates with `git pull` — no reinstall needed.

## Verify Installation

```bash
sci --version
sci --help
```

## Dependencies

Installed automatically with pip:

`numpy`, `pandas`, `matplotlib`, `scipy`, `lmfit`, `plotly`, `textual`, `pyyaml`, `rich`, `prompt_toolkit`, `questionary`, `pyarrow`

## Post-Install: Initialize Config

Create your global config file so science-cli knows where your projects live:

```bash
sci config init
```

This creates `~/.config/science-cli/config.yaml` with default settings. You can then set your projects directory:

```bash
sci config show           # see current config
# Edit ~/.config/science-cli/config.yaml directly,
# or use config edit for the global config file:
sci config edit --global
```

Set `projects_root` to the directory where you keep experiment data. Example:

```yaml
projects_root: /home/user/experiments
```

## Platform Notes

| Platform | Notes |
|----------|-------|
| **macOS** | Works out of the box. `sci` (no args) launches the TUI. |
| **Linux** | Requires `x-terminal-emulator` or a compatible terminal for TUI mode. |
| **Windows** | Works under WSL or native Python. TUI mode may need Windows Terminal. |

## Upgrading

```bash
pip install --upgrade science-cli
```

If installed from source:

```bash
cd science-cli
git pull
pip install -e .
```
