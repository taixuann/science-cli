"""Modular YAML config generation — produces 4 standalone config files.

Each function returns a YAML string for one config file:
    - generate_config_devices_yaml()  → config-devices.yaml (device types + legacy)
    - generate_config_studies_yaml()  → config-studies.yaml (study definitions)
    - generate_config_instruments_yaml() → config-instruments.yaml (instrument registry)
    - generate_config_template_yaml() → config-template.yaml (theme templates)

Data for device_types/legacy_to_study now lives in config-devices.yaml.
Data for studies now lives in config-studies.yaml.
Grammar patterns now live in config-instruments.yaml (per-instrument filename_patterns).
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
        "parsing": {
            "delimiter": ",", "decimal": ".", "header_lines_default": 246,
            "encoding": "utf-8",
            "columns": {"voltage": "V1", "current": "I2"},
        },
        "filename_patterns": [
            {
                "id": "rNcN",
                "template": "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}",
                "description": "Standard rNcN convention (rectangular crossbar)",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$",
            },
            {
                "id": "bN-tN",
                "template": "{date_code}_{material}{batch?}_b{bot}-t{top}_{technique}_{type?}_{suffix?}",
                "description": "Bottom/top crossbar convention",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_b(?P<bot>\d+)-t(?P<top>\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$",
            },
            {
                "id": "rN-cN-iv",
                "template": "{date_code}_{material}_iv-sweep_{matrix}_{suffix}.{ext}",
                "description": "rN-cN convention (1-indexed, hyphen) for iv-sweep data",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)_(?P<technique>[A-Za-z0-9/-]+)_(?P<matrix>r\d+-c\d+)_(?P<suffix>\d+)\.(?P<ext>\w+)$",
            },
            {
                "id": "rN-cN-stp-decay",
                "template": "{date_code}_{material}_r{row}-c{col}_stp-decay_{suffix}{tag?}.{ext}",
                "description": "STP decay: 150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)_(?P<matrix>r\d+-c\d+)_(?P<technique>stp-decay)_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$",
            },
        ],
    },
    "keithley-2400": {
        "label": "Keithley 2400 SourceMeter",
        "location": "usth-hanoi",
        "type": "sourcemeter",
        "techniques": ["iv-sweep", "iv-breakdown", "iv-leakage", "pulse-endurance"],
        "parsing": {
            "delimiter": "\t", "decimal": ".", "header_lines_default": 23,
            "encoding": "utf-8",
            "columns": {"voltage": "Untitled", "current": "Untitled 1",
                        "time": "Untitled 2"},
        },
        "filename_patterns": [
            {
                "id": "rNcN",
                "template": "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}",
                "description": "Standard rNcN convention (rectangular crossbar)",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$",
            },
            {
                "id": "bN-tN",
                "template": "{date_code}_{material}{batch?}_b{bot}-t{top}_{technique}_{type?}_{suffix?}",
                "description": "Bottom/top crossbar convention",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?_b(?P<bot>\d+)-t(?P<top>\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?(?:_(?P<suffix>\d+))?\.\w+$",
            },
            {
                "id": "rN-cN-iv",
                "template": "{date_code}_{material}_iv-sweep_{matrix}_{suffix}.{ext}",
                "description": "rN-cN convention (1-indexed, hyphen) for iv-sweep data",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)_(?P<technique>[A-Za-z0-9/-]+)_(?P<matrix>r\d+-c\d+)_(?P<suffix>\d+)\.(?P<ext>\w+)$",
            },
        ],
    },
    "autolab-usth": {
        "label": "Autolab USTH (CV deposition)",
        "location": "usth-hanoi",
        "type": "potentiostat",
        "techniques": ["ec-cv", "ec-ca", "ec-eis"],
        "parsing": {},
        "filename_patterns": [
            {
                "id": "cv-deposition",
                "template": "{date_code}_{material}_cv-deposition{suffix?}.{ext}",
                "description": "CV deposition (Autolab): 110526_material_cv-deposition[_suffix].txt",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>cv-deposition)(?:_(?P<suffix>[^_]+))?\.\w+$",
            },
            {
                "id": "ca-doping",
                "template": "{date_code}_{material}_ca-doping{suffix?}.{ext}",
                "description": "CA doping (Autolab): 110526_material_ca-doping[_suffix].txt",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>ca-doping)(?:_(?P<suffix>[^_]+))?\.\w+$",
            },
        ],
    },
    "horiba-usth": {
        "label": "Horiba LabRAM HR Evolution (USTH)",
        "location": "usth-hanoi",
        "type": "raman-spectrometer",
        "techniques": ["raman"],
        "parsing": {
            "delimiter": "\t", "decimal": ",", "header_lines_default": 45,
            "encoding": "latin1",
            "names": ["shift", "intensity"],
        },
        "filename_patterns": [
            {
                "id": "raman-spectrum",
                "template": "{date_code}_{material}_raman[-sers]_{suffix}.{ext}",
                "description": "Raman/SERS spectrum (Horiba USTH): 260526_PDA(q)-ITO_raman-sers_01.txt",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>raman(?:-sers)?)(?:_(?P<suffix>\d+))?\.\w+$",
            },
        ],
    },
    "spectrometer-iop": {
        "label": "UV-Vis Spectrometer (IOP Hanoi) — vs-770st",
        "location": "iop-hanoi",
        "type": "uv-vis-spectrometer",
        "techniques": ["uv-vis"],
        "parsing": {
            "delimiter": ",", "decimal": ".", "header_lines_default": 1,
            "encoding": "latin1",
            "columns": {"wavelength": "Wavelength nm.", "transmittance": "T%"},
        },
        "filename_patterns": [
            {
                "id": "uv-vis",
                "template": "{date_code}_{material}_uv-vis.{ext}",
                "description": "UV-Vis transmittance (IOP Hanoi): 280526_PDA(q)-ITO_uv-vis.txt",
                "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>uv-vis)\.\w+$",
            },
        ],
    },
}


# ── config-studies.yaml data ────────────────────────────────────────

_STUDIES: dict[str, dict] = {
    "iv": {
        "iv-bipolar-sweep": {
            "label": "Bipolar IV Sweep 0\u2192+V\u2192-V\u21920",
            "patterns": ["iv-sweep", "_IV", "iv-bipolar", "sweep_"],
            "legacy_codes": ["iv", "iv-sweep", "iv_dc"],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "voltage_v", "current_a"]},
            "instruments": {},
        },
        "iv-breakdown": {
            "label": "Breakdown \u2014 ramped voltage to breakdown",
            "patterns": ["breakdown", "_bd", "_Vbd", "bd_"],
            "legacy_codes": ["bd", "breakdown"],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "voltage_v", "current_a"]},
            "instruments": {},
        },
        "iv-leakage": {
            "label": "Leakage \u2014 low-bias leakage current",
            "patterns": ["leakage", "_leak", "leak_"],
            "legacy_codes": ["leak", "leakage"],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "voltage_v", "current_a"]},
            "instruments": {},
        },
    },
    "pulse": {
        "pulse-stp-decay": {
            "label": "STP Decay \u2014 set pulse + current decay read",
            "patterns": ["stp", "_STP", "stp_decay", "short-term"],
            "legacy_codes": ["stp", "pulse-stp", "short-term-plasticity"],
            "data_shape": {"kind": "waveform_2d", "columns": ["time_s", "voltage_v"], "units": ["s", "V"]},
            "derived_metadata": ["v_set_v", "v_read_v", "set_width_us", "read_width_us", "rise_us", "fall_us", "repeat_pattern"],
            "device_overrides": {"volatile-memristor": {"add": ["decay_tau_ms", "r_read_ohm"]}},
            "instruments": {},
        },
        "pulse-ppf": {
            "label": "Paired-Pulse Facilitation \u2014 double set with \u0394t",
            "patterns": ["ppf", "_PPF", "paired-pulse"],
            "legacy_codes": ["ppf", "pulse-ppf", "paired-pulse"],
            "data_shape": {"kind": "waveform_2d", "columns": ["time_s", "voltage_v"], "units": ["s", "V"]},
            "derived_metadata": ["v_set_v", "v_read_v", "set_width_us", "read_width_us", "rise_us", "fall_us", "repeat_pattern"],
            "instruments": {},
        },
        "pulse-endurance": {
            "label": "Pulse Endurance Cycling",
            "patterns": ["endurance", "_endurance", "endurance_"],
            "legacy_codes": ["endurance", "pulse-endurance"],
            "data_shape": {"kind": "waveform_2d", "columns": ["time_s", "voltage_v"], "units": ["s", "V"]},
            "derived_metadata": ["v_set_v", "v_read_v", "set_width_us", "read_width_us", "rise_us", "fall_us", "repeat_pattern"],
            "device_overrides": {
                "volatile-memristor": {"add": ["r_decay_ohm"]},
                "non-volatile-memristor": {"add": ["r_high_ohm", "r_low_ohm"]},
            },
            "instruments": {},
        },
        "pulse-retention": {
            "label": "Pulse Retention Time",
            "patterns": ["retention", "_retention", "retention_"],
            "legacy_codes": ["retention", "pulse-retention"],
            "data_shape": {"kind": "waveform_2d", "columns": ["time_s", "voltage_v"], "units": ["s", "V"]},
            "derived_metadata": ["v_set_v", "v_read_v", "set_width_us", "read_width_us", "rise_us", "fall_us", "repeat_pattern"],
            "device_overrides": {"non-volatile-memristor": {"add": ["r_read_ohm"]}},
            "instruments": {},
        },
    },
    "raman": {
        "raman-spectrum": {
            "label": "Raman Spectroscopy",
            "patterns": ["_raman", "_sers", "raman-sers", "_SERS"],
            "legacy_codes": ["raman", "sers", "raman-sers"],
            "data_shape": {"kind": "spectrum_2d", "columns": ["wavelength_nm", "intensity"], "units": ["nm", "counts"]},
            "instruments": {},
        },
    },
    "uv-vis": {
        "uv-vis-spectrum": {
            "label": "UV-Vis Transmittance",
            "patterns": ["_uv-vis", "_uvvis", "uv-vis", "uvvis"],
            "legacy_codes": ["uv-vis", "uvvis", "uv_vis"],
            "data_shape": {"kind": "spectrum_2d", "columns": ["wavelength_nm", "absorbance"], "units": ["nm", "au"]},
            "instruments": {},
        },
    },
    "ec": {
        "ec-cv": {
            "label": "Cyclic Voltammetry",
            "patterns": ["_CV.", ".cv", "cv_", "cv-"],
            "legacy_codes": [],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "potential_v", "current_a"]},
            "instruments": {},
        },
        "ec-ca": {
            "label": "Chronoamperometry",
            "patterns": ["_CA.", ".ca", "ca_", "ca-"],
            "legacy_codes": [],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "potential_v", "current_a"]},
            "instruments": {},
        },
        "ec-eis": {
            "label": "Electrochemical Impedance Spectroscopy",
            "patterns": [".mpt", "_EIS.", ".eis", "_impedance", ".z"],
            "legacy_codes": [],
            "data_shape": {"kind": "trace_2d", "columns": ["time_s", "potential_v", "current_a"]},
            "instruments": {},
        },
    },
    "afm": {
        "afm-topography": {
            "label": "AFM/SPM Surface Topography",
            "patterns": [".gwy", ".spm", ".ibw", ".jpk", ".stp", ".top"],
            "legacy_codes": [],
            "data_shape": {"kind": "image_2d", "columns": ["x_um", "y_um", "height_nm"]},
            "instruments": {},
        },
    },
}


# ── Hardcoded grammar fallback patterns ──────────────────────────────
# Used when no config files exist. These mirror the per-instrument
# filename_patterns from config-instruments.yaml / _INSTRUMENTS.
# The real source of truth is now _INSTRUMENTS[inst]["filename_patterns"].

_GRAMMAR_PATTERNS: list[dict] = [
    {
        "id": "rNcN",
        "template": "{date_code}_{material}{batch?}_{matrix}_{technique}_{type?}_{suffix?}",
        "description": "Standard rNcN convention (rectangular crossbar)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?"
                 r"_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
    },
    {
        "id": "bN-tN",
        "template": "{date_code}_{material}{batch?}_b{bot}-t{top}_{technique}_{type?}_{suffix?}",
        "description": "Bottom/top crossbar convention",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+?)(?:_(?P<batch>\d+))?"
                 r"_b(?P<bot>\d+)-t(?P<top>\d+)_(?P<technique>[^_]+)(?:_(?P<type>[^_]+))?"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
    },
    {
        "id": "rN-cN-iv",
        "template": "{date_code}_{material}_iv-sweep_{matrix}_{suffix}.{ext}",
        "description": "rN-cN convention (1-indexed, hyphen) for iv-sweep data",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)_(?P<technique>[A-Za-z0-9/-]+)"
                 r"_(?P<matrix>r\d+-c\d+)_(?P<suffix>\d+)\.(?P<ext>\w+)$",
    },
    {
        "id": "cv-deposition",
        "template": "{date_code}_{material}_cv-deposition{suffix?}.{ext}",
        "description": "CV deposition (Autolab)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>cv-deposition)"
                 r"(?:_(?P<suffix>[^_]+))?\.\w+$",
    },
    {
        "id": "ca-doping",
        "template": "{date_code}_{material}_ca-doping{suffix?}.{ext}",
        "description": "CA doping (Autolab)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>ca-doping)"
                 r"(?:_(?P<suffix>[^_]+))?\.\w+$",
    },
    {
        "id": "raman-spectrum",
        "template": "{date_code}_{material}_raman[-sers]_{suffix}.{ext}",
        "description": "Raman/SERS spectrum (Horiba USTH)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>raman(?:-sers)?)"
                 r"(?:_(?P<suffix>\d+))?\.\w+$",
    },
    {
        "id": "uv-vis",
        "template": "{date_code}_{material}_uv-vis.{ext}",
        "description": "UV-Vis transmittance (IOP Hanoi)",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>.+?)_(?P<technique>uv-vis)\.\w+$",
    },
    {
        "id": "rN-cN-stp-decay",
        "template": "{date_code}_{material}_r{row}-c{col}_stp-decay_{suffix}{tag?}.{ext}",
        "description": "STP decay: 150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv",
        "regex": r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
                 r"_(?P<matrix>r\d+-c\d+)_(?P<technique>stp-decay)"
                 r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$",
    },
]


# ── config-template.yaml data ────────────────────────────────────────
#
# Single source of truth for both theme definitions and per-technique plot
# templates. Read by:
#   - science_cli.theme.registry.theme_to_rcparams() / apply_theme()
#   - science_cli.theme.registry.template_to_flags()
#   - science_cli.core.config.get_plot_labels()
#
# Format mirrors the on-disk config-template.yaml exactly (nested
# figure/axes/grid/ticks/font/legend/lines/colors/savefig sections for
# themes; nested figure/axes/defaults/font/colors/savefig/presets for
# plot_techniques). The legacy "rcparams:" flat-key block is no longer
# produced or read.


_TEMPLATES: dict = {
    "templates": {
        "plot_labels": {
            "iv-sweep": {"xlabel": "Voltage (V)", "ylabel": "Current (A)"},
            "iv-breakdown": {"xlabel": "Voltage (V)", "ylabel": "Current (A)"},
            "iv-leakage": {
                "xlabel": "Voltage (V)",
                "ylabel": "Current density (A/cm²)",
            },
            "ec-cv": {"xlabel": "Potential (V)", "ylabel": "Current (A)"},
            "ec-ca": {"xlabel": "Time (s)", "ylabel": "I (A)"},
            "ec-eis": {"xlabel": "Z' (Ω)", "ylabel": "-Z'' (Ω)"},
            "raman": {"xlabel": "Raman shift (cm⁻¹)", "ylabel": "Intensity (counts)"},
            "uv-vis": {"xlabel": "Wavelength (nm)", "ylabel": "Transmission (%)"},
        },
        "plot_techniques": {
            "iv-sweep": {
                "plot_type": "line",
                "axes": {"xlabel": "Voltage (V)", "ylabel": "Current (A)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "iv-breakdown": {
                "plot_type": "line",
                "axes": {"xlabel": "Voltage (V)", "ylabel": "Current (A)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "iv-leakage": {
                "plot_type": "line",
                "axes": {
                    "xlabel": "Voltage (V)",
                    "ylabel": "Current density (A/cm²)",
                },
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "ec-cv": {
                "plot_type": "line",
                "axes": {"xlabel": "E vs Ref (V)", "ylabel": "I (mA)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "ec-ca": {
                "plot_type": "line",
                "axes": {"xlabel": "Time (s)", "ylabel": "I (mA)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "ec-eis": {
                "plot_type": "line",
                "axes": {"xlabel": "Z' (Ω)", "ylabel": "-Z'' (Ω)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "raman": {
                "plot_type": "line",
                "axes": {"xlabel": "Raman shift (cm⁻¹)", "ylabel": "Intensity (a.u.)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
            "uv-vis": {
                "plot_type": "line",
                "axes": {"xlabel": "Wavelength (nm)", "ylabel": "Transmission (%)"},
                "defaults": {"linewidth": 0.75, "linestyle": "-"},
            },
        },
        "default": {
            "figure": {"figsize": [6.4, 4.8], "dpi": 100},
            "axes": {"linewidth": 1.0, "grid": False},
            "font": {"family": "sans-serif", "size": 10},
            "colors": {
                "prop_cycle": [
                    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
                    "#0072B2", "#D55E00", "#CC79A7", "#000000",
                ],
            },
            "savefig": {"dpi": 300, "format": "pdf"},
        },
        "publication-nature": {
            "figure": {"figsize": [3.46, 2.75], "dpi": 300},
            "axes": {
                "linewidth": 0.5,
                "grid": False,
                "spines_top": False,
                "spines_right": False,
            },
            "font": {"family": "Helvetica", "size": 7},
            "colors": {
                "prop_cycle": [
                    "#000000", "#0072B2", "#D55E00", "#009E73",
                    "#E69F00", "#56B4E9", "#CC79A7", "#F0E442",
                ],
            },
            "savefig": {"dpi": 600, "format": "pdf"},
            "pdf": {"fonttype": 42},
        },
        "publication-acs": {
            "figure": {"figsize": [3.35, 2.6], "dpi": 300},
            "axes": {"linewidth": 0.8, "grid": False},
            "font": {"family": "sans-serif", "size": 8},
            "colors": {
                "prop_cycle": [
                    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
                    "#0072B2", "#D55E00", "#CC79A7", "#000000",
                ],
            },
            "savefig": {"dpi": 600, "format": "pdf"},
        },
        "acs-annotated": {
            "figure": {"figsize": [4.0, 3.2], "dpi": 300},
            "axes": {"linewidth": 0.8, "grid": False},
            "font": {"family": "sans-serif", "size": 8},
            "colors": {
                "prop_cycle": [
                    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
                    "#0072B2", "#D55E00", "#CC79A7", "#000000",
                ],
            },
            "savefig": {"dpi": 600, "format": "pdf"},
        },
        "tufte": {
            "figure": {"figsize": [6.4, 4.8], "dpi": 100},
            "axes": {
                "linewidth": 0.8,
                "grid": False,
                "spines_top": False,
                "spines_right": False,
            },
            "font": {"family": "serif", "size": 9},
            "colors": {
                "prop_cycle": [
                    "#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00",
                ],
            },
            "savefig": {"dpi": 300, "format": "pdf"},
        },
        "dark": {
            "figure": {"figsize": [6.4, 4.8], "dpi": 100},
            "axes": {"linewidth": 1.0, "grid": False},
            "font": {"family": "sans-serif", "size": 10},
            "colors": {
                "prop_cycle": [
                    "#F5A623", "#73C7F0", "#00B884", "#F7EC60",
                    "#0088CC", "#E87100", "#D989B4", "#505050",
                ],
            },
            "savefig": {"dpi": 300, "format": "pdf"},
        },
        "poster": {
            "figure": {"figsize": [12.0, 8.0], "dpi": 100},
            "axes": {"linewidth": 2.0, "grid": False},
            "font": {"family": "sans-serif", "size": 18},
            "colors": {
                "prop_cycle": [
                    "#0072B2", "#E69F00", "#D55E00", "#009E73",
                    "#56B4E9", "#CC79A7", "#F0E442", "#000000",
                ],
            },
            "savefig": {"dpi": 150, "format": "pdf"},
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
    """Generate config-devices.yaml — device types + legacy mapping (no studies).

    Reads from existing config-devices.yaml if available, otherwise generates
    a template with empty sections.
    """
    path = _config_dir() / "config-devices.yaml"
    existing = _load_yaml(path)
    if existing:
        return _yaml_dump(existing)
    # Fallback: generate template with empty sections
    return _yaml_dump({
        "device_types": {},
        "legacy_to_study": {},
        "techniques": {},
    })


def generate_config_studies_yaml() -> str:
    """Generate config-studies.yaml — canonical study definitions (v6).

    Reads from existing config-studies.yaml if available, otherwise generates
    from the _STUDIES hardcoded defaults.
    """
    path = _config_dir() / "config-studies.yaml"
    existing = _load_yaml(path)
    if existing:
        return _yaml_dump(existing)
    # Fallback: generate from hardcoded _STUDIES
    return _yaml_dump({"studies": _STUDIES})


def generate_config_instruments_yaml() -> str:
    """Generate config-instruments.yaml — instrument model registry."""
    return _yaml_dump({
        "instruments": _INSTRUMENTS,
    })


def generate_config_template_yaml() -> str:
    """Generate config-template.yaml — theme template definitions."""
    return _yaml_dump(_TEMPLATES)
