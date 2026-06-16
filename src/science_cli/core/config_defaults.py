"""Modular YAML config generation — produces 4 standalone config files.

Each function returns a YAML string for one config file:
    - generate_config_devices_yaml()  → config-devices.yaml (studies + device types)
    - generate_config_instruments_yaml() → config-instruments.yaml (instrument registry)
    - generate_config_grammar_yaml()  → config-grammar.yaml (filename naming grammar)
    - generate_config_template_yaml() → config-template.yaml (theme templates)

All data is extracted from existing hardcoded defaults to keep backward compat.
"""

from pathlib import Path

import yaml

_DEFAULT_PROJECTS_ROOT = str(Path.home() / "workspace" / "projects" / "active_projects")


# ── config-devices.yaml data ──────────────────────────────────────────


_STUDIES: dict = {
    "iv": {
        "iv-bipolar-sweep": {
            "label": "Bipolar IV Sweep 0\u2192+V\u2192-V\u21920",
            "patterns": ["iv-sweep", "_IV", "iv-bipolar", "sweep_"],
            "legacy_codes": ["iv", "iv-sweep", "iv_dc"],
            "instruments": {
                "keithley-2400": {
                    "delimiter": "\t",
                    "header_lines": 23,
                    "columns": {"voltage": "Untitled", "current": "Untitled 1", "time": "Untitled 2"},
                    "metadata": {
                        "compliance": {
                            "method": "parse",
                            "parser": "compliance",
                            "description": "Compliance current (A)",
                        },
                        "sweep_range": {
                            "method": "parse",
                            "parser": "sweep_range",
                            "description": "Sweep voltage range start/stop (V)",
                        },
                    },
                },
                "keysight-b1500a": {
                    "delimiter": ",",
                    "header_lines": 245,
                    "columns": {"voltage": "V1", "current": "I2"},
                    "metadata": {
                        "set_voltage": {
                            "method": "parse",
                            "parser": "set_voltage",
                            "description": "Sweep max voltage from SetupTitle (V)",
                        },
                        "compliance": {
                            "method": "parse",
                            "parser": "compliance",
                            "description": "Compliance current from Primary.Compliance (A)",
                        },
                        "sweep_range": {
                            "method": "parse",
                            "parser": "sweep_range",
                            "description": "Sweep voltage range start/stop (V)",
                        },
                        "repeat_count": {
                            "method": "parse",
                            "parser": "repeat_count",
                            "description": "Measurement repeat count",
                        },
                        "compliance_analysis": {
                            "method": "analyze",
                            "function": "analyze_iv_compliance",
                            "inputs": ["voltage", "current"],
                            "outputs": ["in_compliance", "compliance_current", "compliance_voltage"],
                            "description": "Compliance detection from IV data",
                        },
                    },
                },
            },
        },
        "iv-breakdown": {
            "label": "Breakdown \u2014 ramped voltage to breakdown",
            "patterns": ["breakdown", "_bd", "_Vbd", "bd_"],
            "legacy_codes": ["bd", "breakdown"],
            "instruments": {},
        },
        "iv-leakage": {
            "label": "Leakage \u2014 low-bias leakage current",
            "patterns": ["leakage", "_leak", "leak_"],
            "legacy_codes": ["leak", "leakage"],
            "instruments": {},
        },
    },
    "pulse": {
        "pulse-stp-decay": {
            "label": "STP Decay \u2014 set pulse + current decay read",
            "patterns": ["stp", "_STP", "stp_decay", "short-term"],
            "legacy_codes": ["stp", "pulse-stp", "short-term-plasticity"],
            "instruments": {
                "keysight-b1500a": {
                    "delimiter": ",",
                    "header_lines": 147,
                    "columns": {"time": "Time", "voltage": "MeasResult1_value",
                                "current": "MeasResult2_value"},
                    "metadata": {
                        "compliance": {
                            "method": "parse",
                            "parser": "compliance",
                            "description": "Compliance current from Primary.Compliance (A)",
                        },
                        "repeat_count": {
                            "method": "parse",
                            "parser": "repeat_count",
                            "description": "Measurement repeat count",
                        },
                        "waveform_params": {
                            "method": "analyze",
                            "function": "analyze_waveform_params",
                            "inputs": ["waveform_time", "waveform_voltage"],
                            "outputs": ["rise_us", "fall_us", "set_width_us", "read_width_us"],
                            "description": "Extracted pulse parameters from waveform definition",
                        },
                    },
                },
            },
        },
        "pulse-ppf": {
            "label": "Paired-Pulse Facilitation \u2014 double set with \u0394t",
            "patterns": ["ppf", "_PPF", "paired-pulse"],
            "legacy_codes": ["ppf", "pulse-ppf", "paired-pulse"],
            "instruments": {
                "keysight-b1500a": {
                    "delimiter": ",",
                    "header_lines": 147,
                    "columns": {"time": "Time", "voltage": "MeasResult1_value",
                                "current": "MeasResult2_value"},
                },
            },
        },
        "pulse-endurance": {
            "label": "Pulse Endurance Cycling",
            "patterns": ["endurance", "_endurance", "endurance_"],
            "legacy_codes": ["endurance", "pulse-endurance"],
            "instruments": {
                "keysight-b1500a": {
                    "delimiter": ",",
                    "header_lines": 147,
                    "columns": {"time": "Time", "voltage": "MeasResult1_value",
                                "current": "MeasResult2_value"},
                },
            },
        },
        "pulse-retention": {
            "label": "Pulse Retention Time",
            "patterns": ["retention", "_retention", "retention_"],
            "legacy_codes": ["retention", "pulse-retention"],
            "instruments": {},
        },
    },
    "raman": {
        "raman-spectrum": {
            "label": "Raman Spectroscopy",
            "patterns": ["_raman", "_sers", "raman-sers", "_SERS"],
            "legacy_codes": ["raman", "sers", "raman-sers"],
            "instruments": {
                "horiba-usth": {
                    "delimiter": "\t",
                    "decimal": ",",
                    "header_lines": 45,
                    "encoding": "latin1",
                    "names": ["shift", "intensity"],
                },
            },
        },
    },
    "uv-vis": {
        "uv-vis-spectrum": {
            "label": "UV-Vis Transmittance",
            "patterns": ["_uv-vis", "_uvvis", "uv-vis", "uvvis"],
            "legacy_codes": ["uv-vis", "uvvis", "uv_vis"],
            "instruments": {
                "spectrometer-iop": {
                    "delimiter": ",",
                    "header_lines": 1,
                    "encoding": "latin1",
                    "columns": {"wavelength": "Wavelength nm.", "transmittance": "T%"},
                },
            },
        },
    },
    "ec": {
        "ec-cv": {
            "label": "Cyclic Voltammetry",
            "patterns": ["_CV.", ".cv", "cv_", "cv-"],
            "legacy_codes": [],
            "instruments": {
                "autolab-usth": {
                    "delimiter": ";",
                    "decimal": ".",
                    "header_lines": 0,
                    "encoding": "utf-8",
                    "columns": {
                        "current": "WE(1).Current (A)",
                        "potential": "WE(1).Potential (V)",
                        "scan": "Scan",
                        "time": "Time (s)",
                        "index": "Index",
                        "corrected_time": "Corrected time (s)",
                        "frequency": "Frequency (Hz)",
                        "z_real": "Z' (\u03A9)",
                        "z_imag": "-Z'' (\u03A9)",
                        "magnitude": "Z (\u03A9)",
                        "phase": "-Phase (\u00B0)",
                    },
                },
            },
        },
        "ec-ca": {
            "label": "Chronoamperometry",
            "patterns": ["_CA.", ".ca", "ca_", "ca-"],
            "legacy_codes": [],
            "instruments": {
                "autolab-usth": {
                    "delimiter": ";",
                    "decimal": ".",
                    "header_lines": 0,
                    "encoding": "utf-8",
                    "columns": {
                        "current": "WE(1).Current (A)",
                        "potential": "WE(1).Potential (V)",
                        "scan": "Scan",
                        "time": "Time (s)",
                        "index": "Index",
                        "corrected_time": "Corrected time (s)",
                        "frequency": "Frequency (Hz)",
                        "z_real": "Z' (\u03A9)",
                        "z_imag": "-Z'' (\u03A9)",
                        "magnitude": "Z (\u03A9)",
                        "phase": "-Phase (\u00B0)",
                    },
                },
            },
        },
        "ec-eis": {
            "label": "Electrochemical Impedance Spectroscopy",
            "patterns": [".mpt", "_EIS.", ".eis", "_impedance", ".z"],
            "legacy_codes": [],
            "instruments": {
                "autolab-usth": {
                    "delimiter": ";",
                    "decimal": ".",
                    "header_lines": 0,
                    "encoding": "utf-8",
                    "columns": {
                        "current": "WE(1).Current (A)",
                        "potential": "WE(1).Potential (V)",
                        "scan": "Scan",
                        "time": "Time (s)",
                        "index": "Index",
                        "corrected_time": "Corrected time (s)",
                        "frequency": "Frequency (Hz)",
                        "z_real": "Z' (\u03A9)",
                        "z_imag": "-Z'' (\u03A9)",
                        "magnitude": "Z (\u03A9)",
                        "phase": "-Phase (\u00B0)",
                    },
                },
            },
        },
    },
    "afm": {
        "afm-topography": {
            "label": "AFM/SPM Surface Topography",
            "patterns": [".gwy", ".spm", ".ibw", ".jpk", ".stp", ".top"],
            "legacy_codes": [],
            "instruments": {},
        },
    },
}

_DEVICE_TYPES: dict = {
    "volatile-memristor": {
        "label": "Volatile Memristor",
        "description": "One-directional switching with volatile decay",
        "studies": ["iv:iv-bipolar-sweep", "pulse:pulse-endurance",
                    "pulse:pulse-stp-decay", "pulse:pulse-ppf"],
        "analysis_mode": "volatile",
        "library": "iv",
    },
    "non-volatile-memristor": {
        "label": "Non-Volatile Memristor",
        "description": "Bidirectional switching with retention",
        "studies": ["iv:iv-bipolar-sweep", "pulse:pulse-endurance",
                    "pulse:pulse-retention"],
        "analysis_mode": "bipolar",
        "library": "iv",
    },
}

_LEGACY_TO_STUDY: dict[str, str] = {
    "iv-sweep": "iv:iv-bipolar-sweep",
    "iv-breakdown": "iv:iv-breakdown",
    "iv-leakage": "iv:iv-leakage",
    "pulse-stp": "pulse:pulse-stp-decay",
    "pulse-ppf": "pulse:pulse-ppf",
    "pulse-endurance": "pulse:pulse-endurance",
    "pulse-retention": "pulse:pulse-retention",
    "raman": "raman:raman-spectrum",
    "uv-vis": "uv-vis:uv-vis-spectrum",
    "ec-cv": "ec:ec-cv",
    "ec-ca": "ec:ec-ca",
    "ec-eis": "ec:ec-eis",
    "afm-gwy": "afm:afm-topography",
    "afm-spm": "afm:afm-topography",
    "afm-ibw": "afm:afm-topography",
    "afm-jpk": "afm:afm-topography",
    "afm-stp": "afm:afm-topography",
    "afm-top": "afm:afm-topography",
}


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


def generate_config_devices_yaml() -> str:
    """Generate config-devices.yaml — studies + device types + legacy mapping."""
    return _yaml_dump({
        "studies": _STUDIES,
        "device_types": _DEVICE_TYPES,
        "legacy_to_study": _LEGACY_TO_STUDY,
    })


def generate_config_instruments_yaml() -> str:
    """Generate config-instruments.yaml — instrument model registry."""
    return _yaml_dump({
        "instruments": _INSTRUMENTS,
    })


def generate_config_grammar_yaml() -> str:
    """Generate config-grammar.yaml — filename naming grammar patterns."""
    return _yaml_dump(_GRAMMAR)


def generate_config_template_yaml() -> str:
    """Generate config-template.yaml — theme template definitions."""
    return _yaml_dump(_TEMPLATES)
