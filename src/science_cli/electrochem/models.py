"""Data models for electrochemistry."""

from dataclasses import dataclass
import numpy as np


@dataclass
class CVData:
    """Cyclic voltammetry data container."""
    potential: np.ndarray
    current: np.ndarray
    scan_rate: float = 0.0
    metadata: dict | None = None


@dataclass
class CAData:
    """Chronoamperometry data container."""
    time: np.ndarray
    current: np.ndarray
    potential: float = 0.0
    metadata: dict | None = None


@dataclass
class EISData:
    """Electrochemical impedance spectroscopy data container.

    Provides computed properties for real, imaginary parts, magnitude,
    and phase angle of the complex impedance.
    """
    frequency: np.ndarray
    impedance: np.ndarray  # complex array
    temperature: float = 0.0
    metadata: dict | None = None

    @property
    def real(self) -> np.ndarray:
        """Real part of impedance (Z')."""
        return self.impedance.real

    @property
    def imag(self) -> np.ndarray:
        """Imaginary part of impedance (Z'')."""
        return self.impedance.imag

    @property
    def magnitude(self) -> np.ndarray:
        """Magnitude of impedance (|Z|)."""
        return np.abs(self.impedance)

    @property
    def phase(self) -> np.ndarray:
        """Phase angle of impedance in degrees."""
        return np.angle(self.impedance, deg=True)
