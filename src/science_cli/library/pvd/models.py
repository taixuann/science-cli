"""Data models for PVD deposition records."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DepositionLayer:
    """Single layer in a deposition stack."""
    material: str
    thickness_nm: float
    rate_nm_s: float = 0.0
    temperature_c: float = 300.0
    pressure_mtorr: float = 5.0


@dataclass
class DepositionRun:
    """Complete deposition run record."""
    name: str = ""
    technique: str = "pvd-deposition"
    instrument: str = "custom-pvd-system"
    protocol: str = ""
    step: str = ""
    layers: list = field(default_factory=list)
    total_thickness_nm: float = 0.0
    parameters: dict = field(default_factory=dict)
    notes: str = ""
    devices: str = ""
