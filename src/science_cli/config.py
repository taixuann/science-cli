"""Configuration: paths, themes, defaults."""

from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".config" / "science-cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

_DEFAULT_CONFIG = {
    "theme": "publication-acs",
    "projects_root": str(Path.home() / "projects" / "active_projects"),
    "repl_history_size": 200,
    "default_figure_format": "png",
    "default_dpi": 300,
}


def ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(_DEFAULT_CONFIG, f, default_flow_style=False)
    return CONFIG_FILE


def load_config() -> dict:
    ensure_config()
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f) or {}
    merged = _DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged


def save_config(config: dict):
    ensure_config()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_config(key: str, default=None):
    return load_config().get(key, default)


def set_config(key: str, value):
    config = load_config()
    config[key] = value
    save_config(config)
