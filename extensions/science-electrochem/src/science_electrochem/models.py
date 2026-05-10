"""Data models for electrochemistry."""

from dataclasses import dataclass
import numpy as np


@dataclass
class CVData:
    potential: np.ndarray
    current: np.ndarray
    scan_rate: float = 0.0
    metadata: dict | None = None


@dataclass
class CAData:
    time: np.ndarray
    current: np.ndarray
    potential: float = 0.0
    metadata: dict | None = None


@dataclass
class EISData:
    frequency: np.ndarray
    impedance: np.ndarray
    temperature: float = 0.0
    metadata: dict | None = None

    @property
    def real(self) -> np.ndarray:
        return self.impedance.real

    @property
    def imag(self) -> np.ndarray:
        return self.impedance.imag

    @property
    def magnitude(self) -> np.ndarray:
        return np.abs(self.impedance)

    @property
    def phase(self) -> np.ndarray:
        return np.angle(self.impedance, deg=True)
