"""Data models for IV analysis."""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class IVData:
    voltage: np.ndarray
    current: np.ndarray
    filename: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def resistance(self) -> float | None:
        """Ohmic resistance from linear region near zero bias."""
        mask = np.abs(self.voltage) < 0.1  # ±100 mV linear region
        if mask.sum() < 3:
            return None
        p = np.polyfit(self.voltage[mask], self.current[mask], 1)
        return 1.0 / p[0] if p[0] != 0 else None

    @property
    def compliance(self) -> float:
        return float(np.max(np.abs(self.current)))

    @property
    def on_off_ratio(self) -> float | None:
        """Ratio of max to min |current| for memristive switching IVs."""
        abs_i = np.abs(self.current)
        min_i = np.min(abs_i[abs_i > 0])
        return float(np.max(abs_i) / min_i) if min_i > 0 else None
