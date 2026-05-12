"""Technique detection from filenames — merges hardcoded + config + extension patterns.

Resolution order for patterns:
    1. Config patterns (global + per-project) — highest priority
    2. Extension-registered patterns
    3. Hardcoded fallback patterns
"""

import re

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


def _extension_patterns() -> dict[str, list[str]]:
    """Try loading technique patterns from extensions."""
    try:
        from science_cli.extensions import get_registry
        registry = get_registry()
        result: dict[str, list[str]] = {}
        for name, tdef in registry.techniques.items():
            if tdef.patterns:
                result[name] = list(tdef.patterns)
        return result
    except ImportError:
        return {}


def _all_patterns() -> dict[str, list[str]]:
    """Merge config, extension, and hardcoded patterns.

    Priority: config > extensions > hardcoded
    """
    patterns: dict[str, list[str]] = {}

    # Start with hardcoded
    for tech, pats in PATTERNS.items():
        patterns[tech] = list(pats)

    # Layer extensions on top
    for tech, pats in _extension_patterns().items():
        if tech not in patterns:
            patterns[tech] = []
        existing = patterns[tech]
        new = [p for p in pats if p not in existing]
        # Extension patterns prepended for priority
        patterns[tech] = new + existing

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

    Checks: config patterns first, then extensions, then hardcoded.
    """
    for tech, patterns in _all_patterns().items():
        for p in patterns:
            if re.search(p, filename, re.IGNORECASE):
                return tech
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
    # Check extension registry for labels not in hardcoded set
    if tech not in labels:
        try:
            from science_cli.extensions import get_registry
            registry = get_registry()
            if tech in registry.techniques:
                return registry.techniques[tech].label
        except ImportError:
            pass
    return labels.get(tech, tech.upper())
