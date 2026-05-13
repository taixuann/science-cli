"""Data models for IV analysis."""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class IVData:
    """Container for a single IV sweep measurement.

    Attributes
    ----------
    voltage : np.ndarray
        Voltage trace (V).
    current : np.ndarray
        Current trace (A).
    filename : str
        Source filename.
    metadata : dict
        Arbitrary metadata (scan rate, temperature, etc.).
    """

    voltage: np.ndarray
    current: np.ndarray
    filename: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def resistance(self) -> Optional[float]:
        """Ohmic resistance from ±0.1 V linear fit (R = 1/slope).

        Returns None if fewer than 3 points in the ohmic window
        or if the fitted slope is zero.
        """
        mask = np.abs(self.voltage) < 0.1
        if mask.sum() < 3:
            return None

        p = np.polyfit(
            self.voltage[mask], self.current[mask], 1
        )
        slope = p[0]
        if slope != 0:
            return 1.0 / slope
        return None

    @property
    def compliance(self) -> float:
        """Maximum absolute current — approximate compliance limit."""
        return float(np.max(np.abs(self.current)))

    @property
    def on_off_ratio(self) -> Optional[float]:
        """On/off ratio = max(|I|) / min(|I|) for I != 0.

        Returns None if no nonzero currents exist.
        """
        abs_i = np.abs(self.current)
        # find the smallest absolute current that is > 0
        min_i = np.min(abs_i[abs_i > 0]) if (abs_i > 0).any() else None
        if min_i is not None and min_i > 0:
            return float(np.max(abs_i) / min_i)
        return None
