"""AFM/SPM file loader — wraps AFMReader for auto-format detection."""

from pathlib import Path

import numpy as np

from .models import AfmData


def load_afm(filepath: str, channel: str | None = None) -> AfmData:
    """Load an AFM/SPM file using AFMReader.

    Auto-detects format from file extension (.gwy, .spm, .ibw, .jpk, .stp, .top).

    Args:
        filepath: Path to the AFM file.
        channel: Optional channel name/index to extract (default: first).

    Returns:
        AfmData dataclass with image, scale, channels, metadata.

    Raises:
        ImportError: If AFMReader is not installed.
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported or channel not found.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"AFM file not found: {filepath}")

    try:
        from AFMReader.general_loader import LoadFile
        img_data, metadata = LoadFile(str(path))
    except ImportError as e:
        if "AFMReader" in str(e):
            raise ImportError(
                "AFMReader is not installed. Install it with: pip install AFMReader>=0.0.7"
            ) from e
        raise
    except Exception as e:
        raise ValueError(f"Failed to load AFM file '{path.name}': {e}") from e

    pixel_to_nm = _extract_pixel_to_nm(metadata, img_data)
    available_channels = _extract_channels(metadata, img_data)
    image = _select_channel(img_data, metadata, channel)

    return AfmData(
        image=image,
        pixel_to_nm=pixel_to_nm,
        channels=available_channels,
        filepath=str(path),
        metadata=metadata,
    )


def list_channels(filepath: str) -> list[str]:
    """Discover available channels in an AFM/SPM file.

    Args:
        filepath: Path to the AFM file.

    Returns:
        List of channel names.
    """
    try:
        from AFMReader.general_loader import LoadFile
        img_data, metadata = LoadFile(filepath)
    except ImportError as e:
        if "AFMReader" in e:
            raise ImportError(
                "AFMReader is not installed. Install it with: pip install AFMReader>=0.0.7"
            ) from e
        raise
    except Exception as e:
        raise ValueError(f"Failed to read AFM file '{Path(filepath).name}': {e}") from e

    return _extract_channels(metadata, img_data)


def _extract_pixel_to_nm(metadata: dict, img_data: np.ndarray | list) -> float:
    """Extract spatial calibration (nm per pixel) from metadata.

    Tries common metadata keys used by different AFM formats.
    """
    candidates = [
        metadata.get("pixel_to_nm"),
        metadata.get("pixel_size_nm"),
        metadata.get("pixel_to_nm_x"),
        metadata.get("pixel_size_x_nm"),
        metadata.get("Pixel size"),
    ]
    for val in candidates:
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass

    # Derive from scan size and image dimensions
    scan_size = metadata.get("scan_size_nm") or metadata.get("Scan Size")
    img = img_data[0] if isinstance(img_data, list) else img_data
    if scan_size and hasattr(img, "shape") and len(img.shape) >= 2:
        try:
            return float(scan_size) / max(img.shape[-2:])
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    # Default fallback
    return 1.0


def _extract_channels(metadata: dict, img_data: np.ndarray | list) -> list[str]:
    """Extract channel names from metadata or infer from data shape."""
    channels = metadata.get("channels") or metadata.get("channel_names") or metadata.get("data_names")
    if channels and isinstance(channels, list):
        return [str(c) for c in channels]

    if isinstance(img_data, list):
        return [f"Channel {i}" for i in range(len(img_data))]

    if isinstance(img_data, np.ndarray) and img_data.ndim == 3:
        return [f"Frame {i}" for i in range(img_data.shape[0])]

    return ["Height"]


def _select_channel(
    img_data: np.ndarray | list,
    metadata: dict,
    channel: str | None,
) -> np.ndarray:
    """Select a specific channel from multi-channel data."""
    channels = _extract_channels(metadata, img_data)

    if isinstance(img_data, list):
        if channel is None:
            return np.asarray(img_data[0])
        if channel in channels:
            idx = channels.index(channel)
            return np.asarray(img_data[idx])
        try:
            idx = int(channel)
            return np.asarray(img_data[idx])
        except (ValueError, IndexError):
            raise ValueError(
                f"Channel '{channel}' not found. Available: {channels}"
            )

    if isinstance(img_data, np.ndarray) and img_data.ndim == 3:
        if channel is None:
            return img_data[0]
        if channel in channels:
            idx = channels.index(channel)
            return img_data[idx]
        try:
            idx = int(channel)
            return img_data[idx]
        except (ValueError, IndexError):
            raise ValueError(
                f"Channel '{channel}' not found. Available: {channels}"
            )

    return np.asarray(img_data)
