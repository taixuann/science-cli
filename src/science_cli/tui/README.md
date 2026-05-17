# Textual TUI Module

The Textual-based terminal UI for science-cli. Launched when `sci` is run without arguments.

## Components

| Module | Widget | Purpose |
|--------|--------|---------|
| `app.py` | `SCIApp` | Main Textual application, command dispatch |
| `banner.py` | `SCIBanner` | ASCII "SCI" art widget |
| `header.py` | `TuiHeader` | Context + workflow header |
| `input_bar.py` | `InputBar` | Command input with history |
| `output_panel.py` | `OutputPanel` | Scrollable command output |
| `status_bar.py` | `StatusBar` | Bottom status bar |
| `theme.py` | — | Matcha green color scheme, CSS |

## Architecture

The TUI dispatches commands through the same `COMMAND_TREE` as the CLI.
Output is captured via `_TeeWriter` and displayed in the output panel.

## Slash Commands

- `/help` — Show help
- `/clear` — Clear output
- `/history` — Show command history
- `/version` — Show version

## Key Bindings

- `Ctrl+C` — Cancel/suspend
- `Ctrl+D` — Exit TUI
- `Up/Down` — History navigation
- `Tab` — Auto-complete (via prompt_toolkit)
