"""Per-technique YAML schema validators.

Each validator receives the raw ``analysis_results`` dict and returns it
(possibly augmented with defaults), or raises ``ValueError`` / ``AssertionError``
if required fields are missing or invalid.
"""

from typing import Any, Callable

# ---------------------------------------------------------------------------
# Public registry — maps technique slug → validator function
# ---------------------------------------------------------------------------

SCHEMA_VALIDATORS: dict[str, Callable[[dict], dict]] = {}


def register(name: str):
    """Decorator: register a validator for *name* in SCHEMA_VALIDATORS."""
    def wrapper(fn: Callable[[dict], dict]):
        SCHEMA_VALIDATORS[name] = fn
        return fn
    return wrapper


# ── AFM ─────────────────────────────────────────────────────────────────


@register("afm-gwy")
def validate_afm_schema(results: dict) -> dict:
    if "analysis" not in results:
        results["analysis"] = {}
    analysis = results["analysis"]
    if "roughness" not in analysis and "Ra_nm" not in analysis:
        pass  # AFM analysis may be empty (interactive entry)
    return results


# ── PVD / Deposition ────────────────────────────────────────────────────


@register("pvd-deposition")
def validate_pvd_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("PVD deposition results must contain 'analysis' key")
    analysis = results["analysis"]
    if "thickness_nm" not in analysis and "total_thickness_nm" not in analysis:
        raise ValueError("PVD analysis must include thickness_nm or total_thickness_nm")
    return results


# ── UV-Vis ──────────────────────────────────────────────────────────────


@register("uv-vis-transmission")
@register("uv-vis-absorbance")
def validate_uv_vis_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("UV-Vis results must contain 'analysis' key")
    return results


# ── Raman ───────────────────────────────────────────────────────────────


@register("raman-spectrum")
def validate_raman_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("Raman results must contain 'analysis' key")
    return results


# ── IV Sweep (mode-aware) ───────────────────────────────────────────────


@register("iv-sweep")
def validate_iv_sweep_schema(results: dict) -> dict:
    """Validate IV sweep results against schema.

    - If mode == ``volatile``: ``v_set`` is required, ``v_reset`` is NOT expected.
    - If mode == ``bipolar``: both ``v_set`` AND ``v_reset`` are required.
    """
    if "analysis" not in results:
        raise ValueError("IV sweep results must contain 'analysis' key")
    analysis = results["analysis"]
    mode = analysis.get("mode", "general")
    params = analysis.get("parameters", {})

    if mode == "volatile":
        if "v_set" not in params:
            raise ValueError("v_set required in analysis.parameters for volatile mode")
        if "v_reset" in params:
            pass  # allowed but unexpected — not an error
    elif mode == "bipolar":
        if "v_set" not in params:
            raise ValueError("v_set required in analysis.parameters for bipolar mode")
        if "v_reset" not in params:
            raise ValueError("v_reset required in analysis.parameters for bipolar mode")

    return results


# ── IV Breakdown ────────────────────────────────────────────────────────


@register("iv-breakdown")
def validate_iv_breakdown_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("IV breakdown results must contain 'analysis' key")
    return results


# ── Pulse Endurance ─────────────────────────────────────────────────────


@register("pulse-endurance")
def validate_pulse_endurance_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("Pulse endurance results must contain 'analysis' key")
    return results


# ── Pulse Retention ─────────────────────────────────────────────────────


@register("pulse-retention")
def validate_pulse_retention_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("Pulse retention results must contain 'analysis' key")
    return results


# ── Pulse STP ────────────────────────────────────────────────────────────


@register("pulse-stp")
def validate_pulse_stp_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("STP results must contain 'analysis' key")
    analysis = results["analysis"]
    if "decay_fit" not in analysis and "model" not in analysis:
        pass  # may be an error result
    return results


# ── Pulse PPF ────────────────────────────────────────────────────────────


@register("pulse-ppf")
def validate_pulse_ppf_schema(results: dict) -> dict:
    if "analysis" not in results:
        raise ValueError("PPF results must contain 'analysis' key")
    analysis = results["analysis"]
    if "ppf_ratio_vs_interval" not in analysis and "tau_facilitation_ms" not in analysis:
        pass  # may be an error result
    return results
