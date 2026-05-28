"""CV analysis: peak detection, charge integration, scan rate analysis."""

import numpy as np
import scipy.signal as signal

from .models import CVData


def analyze_cv(data: CVData, options: dict | None = None) -> dict:
    """Run selected CV analyses. Options: peaks (bool), charge (bool)."""
    if options is None:
        options = {}
    results: dict = {}

    if options.get("peaks", True):
        results["peaks"] = peak_analysis(data, options)

    if options.get("charge", False):
        results["charge"] = calculate_charge(data)

    return results


def peak_analysis(data: CVData, options: dict | None = None) -> dict:
    """Detect anodic and cathodic peaks in CV data.

    Options:
        height: minimum peak height (passed to scipy.signal.find_peaks)
        distance: minimum distance between peaks
        prominence: minimum peak prominence
        peak_type: 'anodic', 'cathodic', or 'both' (default)

    Returns dict with: n_anodic, anodic_peaks, n_cathodic, cathodic_peaks,
    and optionally average_peak_separation.
    """
    if options is None:
        options = {}
    pot = data.potential
    cur = data.current

    height = options.get("height", None)
    distance = options.get("distance", None)
    prominence = options.get("prominence", None)

    anodic_peaks = []
    cathodic_peaks = []

    # Detect anodic peaks (positive current maxima)
    if options.get("peak_type", "both") in ("anodic", "both"):
        idx, props = _find_peaks(cur, height=height, distance=distance,
                                 prominence=prominence)
        if idx is not None and len(idx) > 0:
            for i, ix in enumerate(idx):
                anodic_peaks.append({
                    "index": int(ix),
                    "potential": float(pot[ix]),
                    "current": float(cur[ix]),
                    "height": float(props["peak_heights"][i]) if props else 0,
                })

    # Detect cathodic peaks (negative current minima → invert)
    if options.get("peak_type", "both") in ("cathodic", "both"):
        idx, props = _find_peaks(-cur, height=height, distance=distance,
                                 prominence=prominence)
        if idx is not None and len(idx) > 0:
            for i, ix in enumerate(idx):
                cathodic_peaks.append({
                    "index": int(ix),
                    "potential": float(pot[ix]),
                    "current": float(-cur[ix]),
                    "height": float(props["peak_heights"][i]) if props else 0,
                })

    result = {
        "n_anodic": len(anodic_peaks),
        "anodic_peaks": anodic_peaks,
        "n_cathodic": len(cathodic_peaks),
        "cathodic_peaks": cathodic_peaks,
    }

    # Compute average peak separation (ΔEp)
    if anodic_peaks and cathodic_peaks:
        separations = []
        for ap in anodic_peaks:
            for cp in cathodic_peaks:
                separations.append(abs(ap["potential"] - cp["potential"]))
        if separations:
            result["average_peak_separation"] = float(np.mean(separations))

    return result


def _find_peaks(curve, **kwargs):
    """Wrapper around scipy.signal.find_peaks with NaN safety."""
    sig = np.asarray(curve, dtype=float)
    if np.any(np.isnan(sig)):
        return [], {}
    try:
        return signal.find_peaks(sig, **kwargs)
    except Exception:
        return [], {}


def calculate_charge(data: CVData) -> dict:
    """Integrate CV curve to compute total, anodic, and cathodic charge.

    Charge is divided by scan rate to give capacitance-equivalent units (C).
    """
    pot = data.potential
    cur = data.current
    v = data.scan_rate if data.scan_rate else 1.0

    # Prefer numpy.trapezoid, fallback to scipy.integrate.trapezoid
    try:
        from numpy import trapezoid as _integrate
    except ImportError:
        from scipy.integrate import trapezoid as _integrate

    total = float(_integrate(cur, pot) / v)

    # Anodic charge (current > 0)
    if np.any(cur > 0):
        anodic_charge = float(_integrate(cur[cur > 0], pot[cur > 0]) / v)
    else:
        anodic_charge = 0

    # Cathodic charge (current < 0)
    if np.any(cur < 0):
        cathodic_charge = float(_integrate(cur[cur < 0], pot[cur < 0]) / v)
    else:
        cathodic_charge = 0

    return {
        "total_charge": total,
        "anodic_charge": anodic_charge,
        "cathodic_charge": abs(cathodic_charge),
        "unit": "C",
    }


def scan_rate_analysis(curves: list[CVData]) -> dict:
    """Analyze peak current vs scan rate across multiple CV curves.

    Fits both linear (i_p ∝ v) and square-root (i_p ∝ √v) models.
    Returns linear_fit_slope, linear_fit_intercept, sqrt_fit_slope,
    sqrt_fit_intercept.
    """
    results = {"scan_rates": [], "peak_currents": [], "peak_potentials": []}

    for cv in curves:
        peaks = peak_analysis(cv)

        # Prefer first anodic peak, fallback to first cathodic
        ip = 0
        if peaks.get("anodic_peaks"):
            ip = peaks["anodic_peaks"][0]["current"]
        elif peaks.get("cathodic_peaks"):
            ip = peaks["cathodic_peaks"][0]["current"]

        results["scan_rates"].append(cv.scan_rate)
        results["peak_currents"].append(ip)

    if len(results["scan_rates"]) > 1:
        sr = np.array(results["scan_rates"])
        ip = np.array(results["peak_currents"])
        mask = sr > 0

        if np.any(mask):
            # Linear fit: ip vs sr
            coeffs = np.polyfit(sr[mask], ip[mask], 1)
            results["linear_fit_slope"] = float(coeffs[0])
            results["linear_fit_intercept"] = float(coeffs[1])

            # Randles-Sevcik: ip vs sqrt(sr)
            coeffs_sqrt = np.polyfit(np.sqrt(sr[mask]), ip[mask], 1)
            results["sqrt_fit_slope"] = float(coeffs_sqrt[0])
            results["sqrt_fit_intercept"] = float(coeffs_sqrt[1])

    return results
