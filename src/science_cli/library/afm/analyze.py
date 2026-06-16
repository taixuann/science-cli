"""AFM/SPM image analysis: roughness, height distribution, line profiles, PSD."""

import numpy as np


def compute_roughness(image: np.ndarray, px_to_nm: float = 1.0) -> dict:
    """Compute standard surface roughness parameters.

    Calculates:
        - Ra: Arithmetic average roughness
        - Rq: Root mean square roughness
        - Rmax: Maximum height (peak-to-valley)
        - Rsk: Skewness of height distribution
        - Rku: Kurtosis of height distribution

    Args:
        image: 2D height map (nanometers or arbitrary units).
        px_to_nm: Spatial calibration (nm per pixel). Used for area reporting.

    Returns:
        Dict with roughness parameters as standard Python floats.
    """
    img = np.asarray(image, dtype=float)
    if img.ndim != 2:
        raise ValueError(f"Expected 2D image, got shape {img.shape}")

    z = img[~np.isnan(img)]
    if len(z) < 9:
        return {"error": "Not enough valid pixels (minimum 9)"}

    n = float(len(z))
    z_mean = float(np.nanmean(img))
    z_centered = z - z_mean

    ra = float(np.sum(np.abs(z_centered)) / n)
    rq = float(np.sqrt(np.sum(z_centered**2) / n))
    rmax = float(np.nanmax(img) - np.nanmin(img))

    # Skewness and kurtosis (Rsk, Rku)
    if rq > 0:
        m3 = float(np.sum(z_centered**3) / n)
        m4 = float(np.sum(z_centered**4) / n)
        rsk = m3 / (rq**3)
        rku = m4 / (rq**4)
    else:
        rsk = 0.0
        rku = 0.0

    # Surface area ratio (developed interfacial area ratio)
    try:
        sdr = _surface_area_ratio(img, px_to_nm)
    except Exception:
        sdr = 0.0

    return {
        "Ra_nm": float(f"{ra:.4f}"),
        "Rq_nm": float(f"{rq:.4f}"),
        "Rmax_nm": float(f"{rmax:.4f}"),
        "Rsk": float(f"{rsk:.4f}"),
        "Rku": float(f"{rku:.4f}"),
        "Sdr": float(f"{sdr:.4f}"),
        "n_pixels": int(len(z)),
    }


def height_distribution(
    image: np.ndarray, bins: int = 100
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the height distribution histogram.

    Args:
        image: 2D height map.
        bins: Number of histogram bins (default: 100).

    Returns:
        Tuple of (histogram, bin_edges) as numpy arrays.
    """
    img = np.asarray(image, dtype=float)
    z = img[~np.isnan(img)]
    hist, bin_edges = np.histogram(z, bins=bins)
    return hist, bin_edges


def line_profile(
    image: np.ndarray, start: tuple[int, int], end: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Extract a line profile between two pixel coordinates.

    Uses linear interpolation along the line connecting (y1, x1) and (y2, x2).

    Args:
        image: 2D height map.
        start: (row, col) of the starting pixel.
        end: (row, col) of the ending pixel.

    Returns:
        Tuple of (distances_px, heights) as numpy arrays.
    """
    img = np.asarray(image, dtype=float)
    r1, c1 = start
    r2, c2 = end

    length = int(np.hypot(r2 - r1, c2 - c1))
    if length < 1:
        length = 1

    rows = np.linspace(r1, r2, length)
    cols = np.linspace(c1, c2, length)

    # Clip to image bounds
    h, w = img.shape
    rows = np.clip(rows, 0, h - 1)
    cols = np.clip(cols, 0, w - 1)

    heights = _interpolate(img, rows, cols)
    distances = np.sqrt((rows - r1) ** 2 + (cols - c1) ** 2)

    return distances, heights


def compute_psd(
    image: np.ndarray, px_to_nm: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the power spectral density (PSD) via 2D FFT radial average.

    Args:
        image: 2D height map.
        px_to_nm: Spatial calibration (nm per pixel).

    Returns:
        Tuple of (spatial_frequency_nm, power_density) as numpy arrays.
    """
    img = np.asarray(image, dtype=float)

    # Handle NaN by replacing with mean
    nan_mask = np.isnan(img)
    if nan_mask.any():
        img = img.copy()
        img[nan_mask] = np.nanmean(img)

    # Detrend: subtract 2D plane
    h, w = img.shape
    x_grid, y_grid = np.meshgrid(np.arange(w), np.arange(h))
    design = np.column_stack([x_grid.ravel(), y_grid.ravel(), np.ones_like(x_grid.ravel())])
    coeffs, _, _, _ = np.linalg.lstsq(design, img.ravel(), rcond=None)
    plane = (coeffs[0] * x_grid + coeffs[1] * y_grid + coeffs[2])
    img_detrended = img - plane

    # Apply Hanning window
    window = np.outer(np.hanning(h), np.hanning(w))
    img_windowed = img_detrended * window

    # 2D FFT
    fft = np.fft.fftshift(np.fft.fft2(img_windowed))
    psd_2d = np.abs(fft) ** 2 / (h * w)

    # Radial average
    cx, cy = w // 2, h // 2
    max_radius = min(cx, cy)
    y, x = np.ogrid[:h, :w]
    r = np.hypot(x - cx, y - cy).astype(int)

    psd_radial = np.zeros(max_radius)
    count = np.zeros(max_radius)
    for ri in range(max_radius):
        mask = r == ri
        psd_radial[ri] = np.mean(psd_2d[mask])
        count[ri] = np.sum(mask)

    # Exclude empty bins
    valid = count > 0
    psd_radial = psd_radial[valid]

    # Spatial frequency (nm^-1)
    pixel_size = px_to_nm  # nm per pixel
    freq = np.fft.fftfreq(max_radius, d=pixel_size)[: len(psd_radial)]
    freq = np.abs(freq)

    # Remove zero-frequency
    freq = freq[1:]
    psd_radial = psd_radial[1:]

    return freq, psd_radial


def _interpolate(img: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Bilinear interpolation at given (row, col) coordinates."""
    r_floor = np.floor(rows).astype(int)
    c_floor = np.floor(cols).astype(int)
    r_ceil = np.minimum(r_floor + 1, img.shape[0] - 1)
    c_ceil = np.minimum(c_floor + 1, img.shape[1] - 1)
    dr = rows - r_floor
    dc = cols - c_floor

    top_left = img[r_floor, c_floor]
    top_right = img[r_floor, c_ceil]
    bottom_left = img[r_ceil, c_floor]
    bottom_right = img[r_ceil, c_ceil]

    top = top_left + (top_right - top_left) * dc
    bottom = bottom_left + (bottom_right - bottom_left) * dc
    return top + (bottom - top) * dr


def _surface_area_ratio(image: np.ndarray, px_to_nm: float) -> float:
    """Compute the developed interfacial area ratio (Sdr)."""
    img = np.asarray(image, dtype=float)
    h, w = img.shape
    if h < 2 or w < 2:
        return 0.0

    dx = px_to_nm
    dy = px_to_nm

    # Forward differences
    dz_dx = img[:, 1:] - img[:, :-1]
    dz_dy = img[1:, :] - img[:-1, :]

    area = np.sqrt(dx**2 + (dz_dx[:-1, :])**2) * np.sqrt(dy**2 + (dz_dy[:, :-1])**2)
    sdr = (np.sum(area) - (w - 1) * (h - 1) * dx * dy) / ((w - 1) * (h - 1) * dx * dy)
    return max(sdr * 100, 0.0)
