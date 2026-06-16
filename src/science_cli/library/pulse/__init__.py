"""science-pulse: Pulse measurement analysis module for memristor characterization.
Provides endurance cycling, retention decay, switching time, STP decay, and PPF analysis.
"""

from .endurance import (
    analyze_endurance,
    analyze_endurance_to_yaml,
    endurance_summary,
)
from .ppf import analyze_ppf, analyze_ppf_to_yaml, ppf_summary
from .retention import (
    analyze_retention,
    analyze_retention_to_yaml,
    retention_summary,
)
from .stp import analyze_stp_decay, analyze_stp_decay_to_yaml, stp_summary
from .switching import analyze_pulse_switching

__all__ = [
    "analyze_endurance", "endurance_summary",
    "analyze_endurance_to_yaml",
    "analyze_retention", "retention_summary",
    "analyze_retention_to_yaml",
    "analyze_stp_decay", "stp_summary",
    "analyze_stp_decay_to_yaml",
    "analyze_ppf", "ppf_summary",
    "analyze_ppf_to_yaml",
    "analyze_pulse_switching",
]

ANALYZERS = {
    "pulse-endurance": analyze_endurance,
    "pulse-retention": analyze_retention,
    "pulse-stp": analyze_stp_decay,
    "pulse-ppf": analyze_ppf,
    "pulse-switching": analyze_pulse_switching,
}
