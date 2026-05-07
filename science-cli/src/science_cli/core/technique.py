"""Technique detection from filenames."""

import re

PATTERNS = {
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


def detect_technique(filename: str) -> str:
    for tech, patterns in PATTERNS.items():
        for p in patterns:
            if re.search(p, filename, re.IGNORECASE):
                return tech
    return ""


def technique_label(tech: str) -> str:
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
