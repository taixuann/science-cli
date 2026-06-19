"""Modular YAML config generation — produces 4 standalone config files.

Each function returns a YAML string for one config file:
    - generate_config_devices_yaml()  → config-devices.yaml (studies + device types)
    - generate_config_instruments_yaml() → config-instruments.yaml (instrument registry)
    - generate_config_grammar_yaml()  → config-grammar.yaml (filename naming grammar)
    - generate_config_template_yaml() → config-template.yaml (theme templates)

Data for studies/device_types/legacy_to_study now lives in config-devices.yaml.
Generation functions read from existing config files when available.
"""

from pathlib import Path

import yaml

_DEFAULT_PROJECTS_ROOT = str(Path.home() / "workspace" / "projects" / "active_projects")


# ── config-instruments.yaml data ─────────────────────────────────────


_INSTRUMENTS: dict[str, dict] = {
    "keysight-b1500a": {
        "label": "Keysight B1500A Semiconductor Parameter Analyzer",
        "location": "gtiit-china",
        "type": "semiconductor-device-analyzer",
        "techniques": ["iv-sweep", "iv-breakdown", "iv-leakage",
                       "pulse-endurance", "pulse-stp", "pulse-ppf"],
        "config": {"delimiter": ",", "decimal": ".", "header_lines": 246, "encoding": "utf-8"},
    },
    "keithley-2400": {
        "label": "Keithley 2400 SourceMeter",
        "location": "usth-hanoi",
        "type": "sourcemeter",
        "techniques": ["iv-sweep", "iv-breakdown", "iv-leakage", "pulse-endurance"],
        "config": {"delimiter": "\t", "decimal": ".", "header_lines": 23, "encoding": "utf-8"},
    },
    "autolab-usth": {
        "label": "Autolab USTH (CV deposition)",
        "location": "usth-hanoi",
        "type": "potentiostat",
        "techniques": ["ec-cv", "ec-ca", "ec-eis"],
        "config": {},
    },
    "horiba-usth": {
        "label": "Horiba LabRAM HR Evolution (USTH)",
        "location": "usth-hanoi",
        "type": "raman-spectrometer",
        "techniques": ["raman"],
        "config": {"delimiter": "\t", "decimal": ",", "header_lines": 45, "encoding": "latin1"},
    },
    "spectrometer-iop": {
        "label": "UV-Vis Spectrometer (IOP Hanoi) — vs-770st",
        "location": "iop-hanoi",
        "type": "uv-vis-spectrometer",
        "techniques": ["uv-vis"],
        "config": {"delimiter": ",", "decimal": ".", "header_lines": 1, "encoding": "latin1"},
    },
}


# ── config-grammar.yaml data ─────────────────────────────────────────


_GRAMMAR_PATTERNS: list[dict] = [
    {
        "id": "rNcN",
        "template": "{date_code}_{material}{batch?}_{matrix}_{study}_{type?}_{suffix?}",
        "description": "Standard rNcN convention (rectangular crossbar)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?"
                 r"_(?P<matrix>r\d+c\d+)_(?P<study>[^_]+)(?:_(?P<type>[^_]+))?"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
        "fields": ["date_code", "material", "batch", "matrix", "study", "type", "suffix"],
    },
    {
        "id": "bN-tN",
        "template": "{date_code}_{material}{batch?}_b{bot}-t{top}_{study}_{type?}_{suffix?}",
        "description": "Bottom/top crossbar convention",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?"
                 r"_b(?P<bot>\d+)-t(?P<top>\d+)_(?P<study>[^_]+)(?:_(?P<type>[^_]+))?"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
        "fields": ["date_code", "material", "batch", "bot", "top", "study", "type", "suffix"],
    },
    {
        "id": "basic",
        "template": "{date_code}_{material}_{study}_{suffix?}",
        "description": "Basic naming (no matrix coordinates)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<study>[^_]+)"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
        "fields": ["date_code", "material", "study", "suffix"],
    },
    {
        "id": "rN-cN-stp-decay",
        "template": "{date_code}_{material}_r{row}-c{col}_stp-decay_{suffix}{tag?}.{ext}",
        "description": "STP decay: 150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
                 r"_(?P<matrix>r\d+-c\d+)_(?P<study>stp-decay)"
                 r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$",
        "fields": ["date_code", "material", "matrix", "study", "suffix", "tag", "ext"],
    },
]

_GRAMMAR: dict = {
    "file_naming": {
        "separator": "_",
        "patterns": _GRAMMAR_PATTERNS,
    },
}


# ── config-template.yaml data ────────────────────────────────────────


_TEMPLATES: dict = {
    "templates": {
        "publication-nature": {
            "font": "Helvetica",
            "fontsize": 7,
            "dpi": 300,
            "figure_format": "pdf",
            "rcparams": {
                "font.family": "sans-serif",
                "font.sans-serif": ["Helvetica"],
                "axes.linewidth": 0.5,
                "axes.labelsize": 7,
                "xtick.labelsize": 6,
                "ytick.labelsize": 6,
                "legend.fontsize": 6,
                "lines.linewidth": 1.0,
            },
        },
        "publication-acs": {
            "font": "Helvetica",
            "fontsize": 8,
            "dpi": 600,
            "figure_format": "pdf",
            "rcparams": {
                "font.family": "sans-serif",
                "font.sans-serif": ["Helvetica"],
                "axes.linewidth": 0.5,
                "axes.labelsize": 8,
                "xtick.labelsize": 7,
                "ytick.labelsize": 7,
                "legend.fontsize": 7,
                "lines.linewidth": 1.0,
            },
        },
        "matcha": {
            "font": "sans-serif",
            "fontsize": 11,
            "dpi": 150,
            "figure_format": "png",
            "rcparams": {
                "axes.facecolor": "#f5f5f0",
                "axes.edgecolor": "#4a4a4a",
                "grid.color": "#d4d4d4",
                "grid.alpha": 0.6,
            },
        },
        "tufte": {
            "font": "serif",
            "fontsize": 10,
            "dpi": 200,
            "figure_format": "pdf",
            "rcparams": {
                "font.family": "serif",
                "axes.linewidth": 0.3,
                "axes.spines.top": False,
                "axes.spines.right": False,
            },
        },
        "dark": {
            "font": "sans-serif",
            "fontsize": 10,
            "dpi": 150,
            "figure_format": "png",
            "rcparams": {
                "axes.facecolor": "#1a1a1a",
                "axes.edgecolor": "#e0e0e0",
                "text.color": "#e0e0e0",
                "axes.labelcolor": "#e0e0e0",
                "xtick.color": "#e0e0e0",
                "ytick.color": "#e0e0e0",
                "figure.facecolor": "#121212",
                "grid.color": "#333333",
            },
        },
        "poster": {
            "font": "sans-serif",
            "fontsize": 14,
            "dpi": 300,
            "figure_format": "png",
            "rcparams": {
                "axes.linewidth": 1.5,
                "axes.labelsize": 14,
                "xtick.labelsize": 12,
                "ytick.labelsize": 12,
                "legend.fontsize": 12,
                "lines.linewidth": 2.0,
            },
        },
    },
}


# ── Generation functions ─────────────────────────────────────────────


def _yaml_dump(data: dict, sort_keys: bool = False) -> str:
    """Serialize dict to YAML string with consistent formatting."""
    return yaml.dump(data, default_flow_style=False, sort_keys=sort_keys,
                     allow_unicode=True, width=120)


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning {} if it doesn't exist or is unreadable."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def _config_dir() -> Path:
    """Return the global config directory."""
    return Path.home() / ".config" / "science-cli" / "config"


def generate_config_devices_yaml() -> str:
    """Generate config-devices.yaml — studies + device types + legacy mapping.

    Reads from existing config-devices.yaml if available, otherwise generates
    a template with empty sections.
    """
    path = _config_dir() / "config-devices.yaml"
    existing = _load_yaml(path)
    if existing:
        return _yaml_dump(existing)
    # Fallback: generate template with empty sections
    return _yaml_dump({
        "studies": {},
        "device_types": {},
        "legacy_to_study": {},
        "techniques": {},
    })


def generate_config_instruments_yaml() -> str:
    """Generate config-instruments.yaml — instrument model registry."""
    return _yaml_dump({
        "instruments": _INSTRUMENTS,
        "devices": {},
    })


def generate_config_grammar_yaml() -> str:
    """Generate config-grammar.yaml — filename naming grammar patterns."""
    return _yaml_dump(_GRAMMAR)


def generate_config_template_yaml() -> str:
    """Generate config-template.yaml — theme template definitions."""
    return _yaml_dump(_TEMPLATES)
