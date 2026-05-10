"""CV analysis: peak detection, charge integration, scan rate analysis."""

import numpy as np
from scipy import signal
from science_electrochem.models import CVData


def analyze_cv(data: CVData, options: dict | None = None) -> dict:
    options = options or {}
    results = {}

    if options.get("peaks", True):
        results["peaks"] = peak_analysis(data, options)

    if options.get("charge", False):
        results["charge"] = calculate_charge(data)

    return results


def peak_analysis(data: CVData, options: dict | None = None) -> dict:
    options = options or {}
    pot, cur = data.potential, data.current

    height = options.get("height", None)
    distance = options.get("distance", None)
    prominence = options.get("prominence", None)

    anodic_peaks = []
    cathodic_peaks = []

    if options.get("peak_type", "both") in ("anodic", "both"):
        idx, props = _find_peaks(cur, height=height, distance=distance, prominence=prominence)
        if idx is not None and len(idx) > 0:
            for i, ix in enumerate(idx):
                anodic_peaks.append({
                    "index": int(ix),
                    "potential": float(pot[ix]),
                    "current": float(cur[ix]),
                    "height": float(props["peak_heights"][i]) if props else 0,
                })

    if options.get("peak_type", "both") in ("cathodic", "both"):
        idx, props = _find_peaks(-cur, height=height, distance=distance, prominence=prominence)
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

    if anodic_peaks and cathodic_peaks:
        separations = []
        for ap in anodic_peaks:
            for cp in cathodic_peaks:
                separations.append(abs(ap["potential"] - cp["potential"]))
        if separations:
            result["average_peak_separation"] = float(np.mean(separations))

    return result


def _find_peaks(curve, **kwargs):
    sig = np.asarray(curve, dtype=float)
    if np.any(np.isnan(sig)):
        return [], {}
    try:
        return signal.find_peaks(sig, **kwargs)
    except Exception:
        return [], {}


def calculate_charge(data: CVData) -> dict:
    pot, cur = data.potential, data.current
    v = data.scan_rate or 1.0

    try:
        from numpy import trapezoid as _integrate
    except ImportError:
        from scipy.integrate import trapezoid as _integrate
    total = float(_integrate(cur, pot) / v)
    anodic_charge = float(_integrate(cur[cur > 0], pot[cur > 0]) / v) if np.any(cur > 0) else 0
    cathodic_charge = float(_integrate(cur[cur < 0], pot[cur < 0]) / v) if np.any(cur < 0) else 0

    return {
        "total_charge": total,
        "anodic_charge": anodic_charge,
        "cathodic_charge": abs(cathodic_charge),
        "unit": "C",
    }


def scan_rate_analysis(curves: list[CVData]) -> dict:
    results = {"scan_rates": [], "peak_currents": [], "peak_potentials": []}
    for cv in curves:
        peaks = peak_analysis(cv)
        ip = 0
        if peaks["anodic_peaks"]:
            ip = peaks["anodic_peaks"][0]["current"]
        elif peaks["cathodic_peaks"]:
            ip = peaks["cathodic_peaks"][0]["current"]
        results["scan_rates"].append(cv.scan_rate)
        results["peak_currents"].append(ip)

    if len(results["scan_rates"]) > 1:
        sr = np.array(results["scan_rates"])
        ip = np.array(results["peak_currents"])
        mask = sr > 0
        if np.any(mask):
            coeffs = np.polyfit(sr[mask], ip[mask], 1)
            results["linear_fit_slope"] = float(coeffs[0])
            results["linear_fit_intercept"] = float(coeffs[1])
            coeffs_sqrt = np.polyfit(np.sqrt(sr[mask]), ip[mask], 1)
            results["sqrt_fit_slope"] = float(coeffs_sqrt[0])
            results["sqrt_fit_intercept"] = float(coeffs_sqrt[1])

    return results
