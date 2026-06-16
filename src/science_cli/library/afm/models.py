"""Data models for AFM/SPM image analysis."""

from dataclasses import dataclass

import numpy as np


@dataclass
class AfmData:
    """AFM/SPM image data container.

    Attributes:
        image: 2D numpy array (height map) or 3D for multi-frame formats.
        pixel_to_nm: Spatial calibration factor (nm per pixel).
        channels: Available channel names in the source file.
        filepath: Source file path.
        metadata: Raw metadata dict from AFMReader.
    """
    image: np.ndarray
    pixel_to_nm: float
    channels: list[str]
    filepath: str
    metadata: dict
