"""Data models for pulse analysis."""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class PulseData:
    """Container for pulse measurement data."""
    time: np.ndarray
    current: np.ndarray
    voltage: Optional[np.ndarray] = None
    filename: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class EnduranceData:
    """Container for endurance cycling data."""
    cycles: np.ndarray
    r_on: np.ndarray
    r_off: np.ndarray
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)


@dataclass
class RetentionData:
    """Container for retention decay data."""
    time: np.ndarray
    resistance: np.ndarray
    temperature: float = 298.0
    metadata: dict = field(default_factory=dict)


@dataclass
class STPData:
    """Container for short-term plasticity decay data."""
    time: np.ndarray
    current: np.ndarray
    metadata: dict = field(default_factory=dict)


@dataclass
class PPFData:
    """Container for paired-pulse facilitation data."""
    intervals_ms: np.ndarray
    ratios: np.ndarray
    metadata: dict = field(default_factory=dict)
