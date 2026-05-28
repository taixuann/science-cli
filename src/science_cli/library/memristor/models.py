"""Data models for memristor characterization."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class EnduranceData:
    cycles: np.ndarray
    r_on: np.ndarray
    r_off: np.ndarray
    ratio: np.ndarray
    filename: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def failure_cycle(self) -> int | None:
        """First cycle where ratio drops below 10 (standard read margin)."""
        failed = np.where(self.ratio < 10)[0]
        return int(self.cycles[failed[0]]) if len(failed) > 0 else None

    @property
    def cycle_variability(self) -> dict:
        """Cycle-to-cycle σ/μ for R_on and R_off."""
        return {
            "r_on_cv": float(np.std(self.r_on) / np.mean(self.r_on)),
            "r_off_cv": float(np.std(self.r_off) / np.mean(self.r_off)),
        }


@dataclass
class RetentionData:
    time: np.ndarray
    resistance: np.ndarray
    temperature: float = 298.0
    filename: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def decay_rate(self) -> float:
        """Slope in log-time space: dR/d(log t)."""
        log_t = np.log10(self.time[1:])
        return float(np.polyfit(log_t, self.resistance[1:], 1)[0])


@dataclass
class SwitchingData:
    v_set: np.ndarray
    v_reset: np.ndarray
    t_set: np.ndarray | None = None
    t_reset: np.ndarray | None = None
    r_on: np.ndarray | None = None
    r_off: np.ndarray | None = None
    filename: str = ""
    metadata: dict = field(default_factory=dict)
