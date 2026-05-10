"""Technique detection from filenames — merges hardcoded + extension patterns."""

import re

# Hardcoded fallback patterns — used when no extensions register patterns
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


def _all_patterns() -> dict[str, list[str]]:
    """Merge extension-registered patterns on top of hardcoded fallbacks."""
    patterns = dict(PATTERNS)
    try:
        from science_cli.extensions import get_registry
        registry = get_registry()
        for name, tdef in registry.techniques.items():
            if name not in patterns:
                patterns[name] = []
            # Extension patterns take priority: insert before hardcoded
            existing = patterns[name]
            new = [p for p in tdef.patterns if p not in existing]
            patterns[name] = new + existing
    except ImportError:
        pass
    return patterns


def detect_technique(filename: str) -> str:
    """Detect technique from filename using merged hardcoded + extension patterns."""
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
