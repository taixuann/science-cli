"""Technique detection from filenames — merges hardcoded + config patterns.

Resolution order for patterns:
    1. Config patterns (global + per-project) — highest priority
    2. Hardcoded fallback patterns
"""

import re
from dataclasses import dataclass, field


def _find_column(preferred: str, aliases: list[str], columns: list[str]) -> str:
    """Find the first matching column name from preferred + aliases."""
    candidates = [preferred] + list(aliases) if preferred else list(aliases)
    for c in candidates:
        if c in columns:
            return c
    return ""


@dataclass
class ColumnMap:
    """Maps standard column roles to file-specific column names."""
    x: str = ""
    y: str = ""
    x_label: str = ""
    y_label: str = ""
    extras: dict = field(default_factory=dict)
    x_aliases: list[str] = field(default_factory=list)
    y_aliases: list[str] = field(default_factory=list)

    def resolve(self, columns: list[str]) -> tuple[str, str, str, str, dict[str, str]]:
        xcol = _find_column(self.x, self.x_aliases, columns)
        ycol = _find_column(self.y, self.y_aliases, columns)
        xlabel = self.x_label or xcol or "X"
        ylabel = self.y_label or ycol or "Y"
        resolved_extras: dict[str, str] = {}
        for role, preferred in self.extras.items():
            found = _find_column(preferred, [], columns)
            if found:
                resolved_extras[role] = found
        return xcol, ycol, xlabel, ylabel, resolved_extras


@dataclass
class TechniqueDef:
    name: str
    label: str
    patterns: list[str]
    description: str = ""


# Hardcoded fallback patterns — used when no config or extensions exist
PATTERNS: dict[str, list[str]] = {
    "ec-cv": [r"_CV\.", r"\.cv$", r"cv_", r"cv-"],
    "ec-ca": [r"_CA\.", r"\.ca$", r"ca_", r"ca-"],
    "ec-eis": [r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"],
    "ec-lsv": [r"_LSV\.", r"\.lsv$"],
    "ec-swv": [r"_SWV\.", r"\.swv$"],
    "iv-sweep": [r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"],
    "iv-breakdown": [r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"],
    "iv-leakage": [r"_leak", r"leakage_", r"leak_"],
    "mem-endurance": [r"_endurance", r"\.end", r"end_", r"endurance", r"-endurance"],
    "mem-retention": [r"_retention", r"\.ret", r"ret_", r"retention", r"-retention"],
    "mem-switching": [r"_switch", r"\.sw", r"sw_", r"switch_", r"-switch"],
}


# Built-in technique definitions — replaces extension registry
BUILTIN_TECHNIQUES: dict[str, TechniqueDef] = {
    "iv-sweep": TechniqueDef(name="iv-sweep", label="IV Sweep", patterns=[r"_IV\.", r"\.iv$", r"iv_", r"iv-", r"_sweep", r"sweep_"], description="Current-Voltage sweep"),
    "iv-breakdown": TechniqueDef(name="iv-breakdown", label="Breakdown", patterns=[r"_bd\.", r"breakdown_", r"_Vbd", r"bd_"], description="Ramped voltage to breakdown"),
    "iv-leakage": TechniqueDef(name="iv-leakage", label="Leakage", patterns=[r"_leak", r"leakage_", r"leak_"], description="Low-bias leakage current"),
    "ec-cv": TechniqueDef(name="ec-cv", label="CV", patterns=[r"_CV\.", r"\.cv$", r"cv_", r"cv-"], description="Cyclic Voltammetry"),
    "ec-ca": TechniqueDef(name="ec-ca", label="CA", patterns=[r"_CA\.", r"\.ca$", r"ca_", r"ca-"], description="Chronoamperometry"),
    "ec-eis": TechniqueDef(name="ec-eis", label="EIS", patterns=[r"\.mpt$", r"_EIS\.", r"\.eis$", r"_impedance", r"\.z"], description="Electrochemical Impedance Spectroscopy"),
    "ec-lsv": TechniqueDef(name="ec-lsv", label="LSV", patterns=[r"_LSV\.", r"\.lsv$"], description="Linear Sweep Voltammetry"),
    "ec-swv": TechniqueDef(name="ec-swv", label="SWV", patterns=[r"_SWV\.", r"\.swv$"], description="Square Wave Voltammetry"),
    "mem-endurance": TechniqueDef(name="mem-endurance", label="Endurance", patterns=[r"_endurance", r"\.end", r"end_", r"endurance", r"-endurance"], description="DC/pulsed endurance cycling"),
    "mem-retention": TechniqueDef(name="mem-retention", label="Retention", patterns=[r"_retention", r"\.ret", r"ret_", r"retention", r"-retention"], description="Retention time test"),
    "mem-switching": TechniqueDef(name="mem-switching", label="Switching", patterns=[r"_switch", r"\.sw", r"sw_", r"switch_", r"-switch"], description="Switching time / voltage characterization"),
}


def _config_patterns() -> dict[str, list[str]]:
    """Try loading technique patterns from the config system.

    Config patterns are prepended (take priority) before hardcoded ones.
    Returns a dict of technique → patterns, or empty dict on failure.
    """
    try:
        from science_cli.core.config import get_technique_patterns
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        project_root = proj if proj else None
        result: dict[str, list[str]] = {}
        # Get patterns for all known techniques (config may add new ones)
        all_techs = set(PATTERNS.keys())
        for tech in all_techs:
            patterns = get_technique_patterns(tech, project_root)
            if patterns != PATTERNS.get(tech, []):
                result[tech] = patterns
        return result
    except ImportError:
        return {}


def _all_patterns() -> dict[str, list[str]]:
    """Merge config and hardcoded patterns. Priority: config > hardcoded."""
    patterns: dict[str, list[str]] = {}
    for tech, pats in PATTERNS.items():
        patterns[tech] = list(pats)
    # Layer config on top (highest priority)
    for tech, pats in _config_patterns().items():
        if tech not in patterns:
            patterns[tech] = []
        existing = patterns[tech]
        new = [p for p in pats if p not in existing]
        patterns[tech] = new + existing
    return patterns


def detect_technique(filename: str) -> str:
    """Detect technique from filename using merged patterns.

    Checks: config patterns first, then hardcoded.
    Gracefully skips invalid regex patterns (e.g. glob-style ``*pattern*``).
    """
    for tech, patterns in _all_patterns().items():
        for p in patterns:
            try:
                if re.search(p, filename, re.IGNORECASE):
                    return tech
            except re.error:
                continue
    return ""


def technique_label(tech: str) -> str:
    """Return a human-readable label for a technique key."""
    labels = {
        "ec-cv": "CV",
        "ec-ca": "CA",
        "ec-eis": "EIS",
        "ec-lsv": "LSV",
        "ec-swv": "SWV",
        "iv-sweep": "IV Sweep",
        "iv-breakdown": "Breakdown",
        "iv-leakage": "Leakage",
        "mem-endurance": "Endurance",
        "mem-retention": "Retention",
        "mem-switching": "Switching",
    }
    return labels.get(tech, tech.upper())
