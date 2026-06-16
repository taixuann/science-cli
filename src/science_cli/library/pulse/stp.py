"""STP (Short-Term Plasticity) decay analysis — mono/biexponential fitting."""
from pathlib import Path

import numpy as np
from scipy import optimize


def analyze_stp_decay(time, current):
    """Analyze STP decay trace with mono/biexponential fitting.
    
    Fits both monoexponential and biexponential decay models,
    selects the better model by AIC.
    
    Args:
        time: Time array (ms).
        current: Current array (A).
    
    Returns:
        dict with decay parameters, fit quality, and model selection.
    """
    t = np.asarray(time, dtype=float).flatten()
    i = np.asarray(current, dtype=float).flatten()
    
    if len(t) < 5:
        return {"error": "Insufficient data points (need >=5)"}
    
    t_norm = t - t[0]
    i_norm = np.abs(i)
    
    initial_current = float(i_norm[0])
    steady_state = float(np.median(i_norm[-max(3, len(i_norm)//5):]))
    
    # Monoexponential: I(t) = A * exp(-t/tau) + I0
    def monoexp(tau_a, tau, a0):
        return a0 + tau_a * np.exp(-t_norm / tau)
    
    def mono_residual(params):
        tau_a, tau, a0 = params
        return monoexp(tau_a, tau, a0) - i_norm
    
    try:
        p0 = [initial_current - steady_state, np.median(t_norm) / 2, steady_state]
        bounds = ([0, 0, 0], [np.inf, np.inf, np.inf])
        result_mono = optimize.least_squares(mono_residual, p0, bounds=bounds, max_nfev=1000)
        tau_a1, tau1, a0_1 = result_mono.x
        residuals1 = result_mono.fun
        ss_res1 = np.sum(residuals1 ** 2)
        n1 = len(t_norm)
        k1 = 3
        aic1 = n1 * np.log(ss_res1 / n1) + 2 * k1 if ss_res1 > 0 else float("inf")
    except Exception:
        tau1 = None
        aic1 = float("inf")
        tau_a1 = 0
        a0_1 = steady_state
        ss_res1 = float("inf")
    
    # Biexponential: I(t) = A1 * exp(-t/tau1) + A2 * exp(-t/tau2) + I0
    def biexp(tau_a1, tau1, tau_a2, tau2, a0):
        return a0 + tau_a1 * np.exp(-t_norm / tau1) + tau_a2 * np.exp(-t_norm / tau2)
    
    def bi_residual(params):
        tau_a1, tau1, tau_a2, tau2, a0 = params
        return biexp(tau_a1, tau1, tau_a2, tau2, a0) - i_norm
    
    try:
        p0_bi = [(initial_current - steady_state) * 0.7, np.median(t_norm) / 4,
                 (initial_current - steady_state) * 0.3, np.median(t_norm) * 2, steady_state]
        bounds = ([0, 0, 0, 0, 0], [np.inf, np.inf, np.inf, np.inf, np.inf])
        result_bi = optimize.least_squares(bi_residual, p0_bi, bounds=bounds, max_nfev=2000)
        tau_a1b, tau1b, tau_a2b, tau2b, a0_b = result_bi.x
        residuals2 = result_bi.fun
        ss_res2 = np.sum(residuals2 ** 2)
        n2 = len(t_norm)
        k2 = 5
        aic2 = n2 * np.log(ss_res2 / n2) + 2 * k2 if ss_res2 > 0 else float("inf")
    except Exception:
        tau1b = None
        tau2b = None
        aic2 = float("inf")
        ss_res2 = float("inf")
    
    # Model selection
    if aic1 < aic2:
        model = "monoexponential"
        r_squared = 1 - ss_res1 / np.sum((i_norm - np.mean(i_norm)) ** 2) if ss_res1 != float("inf") else 0
        result = {
            "model": model,
            "tau1_ms": float(tau1) if tau1 is not None else None,
            "a1": float(tau_a1) if tau1 is not None else None,
            "a2": None, "tau2_ms": None,
            "initial_current_ua": initial_current * 1e6,
            "steady_state_current_ua": a0_1 * 1e6,
            "r_squared": float(r_squared),
        }
    else:
        model = "biexponential"
        r_squared = 1 - ss_res2 / np.sum((i_norm - np.mean(i_norm)) ** 2) if ss_res2 != float("inf") else 0
        total_amp = tau_a1b + tau_a2b if (tau_a1b + tau_a2b) > 0 else 1
        result = {
            "model": model,
            "tau1_ms": float(tau1b) if tau1b is not None else None,
            "tau2_ms": float(tau2b) if tau2b is not None else None,
            "a1": float(tau_a1b / total_amp) if tau_a1b is not None else None,
            "a2": float(tau_a2b / total_amp) if tau_a2b is not None else None,
            "initial_current_ua": initial_current * 1e6,
            "steady_state_current_ua": a0_b * 1e6,
            "r_squared": float(r_squared),
        }
    
    result["decay_pct"] = float((1 - steady_state / initial_current) * 100) if initial_current > 0 else 0
    return result


def stp_summary(analysis):
    """Human-readable STP analysis summary."""
    if "error" in analysis:
        return f"STP Analysis: {analysis['error']}"
    lines = [
        f"STP Decay Analysis: {analysis['model']}",
        f"  Current: {analysis['initial_current_ua']:.2f} uA -> {analysis['steady_state_current_ua']:.2f} uA",
        f"  Decay: {analysis['decay_pct']:.1f}%",
    ]
    if analysis["tau1_ms"] is not None:
        lines.append(f"  tau1 = {analysis['tau1_ms']:.1f} ms")
    if analysis["tau2_ms"] is not None:
        lines.append(f"  tau2 = {analysis['tau2_ms']:.1f} ms (weight={analysis['a2']:.2f})")
    lines.append(f"  R-squared = {analysis['r_squared']:.4f}")
    return "\n".join(lines)


def _to_native(val):
    """Convert numpy scalars to native Python types for safe YAML serialization."""
    import numpy as np
    if isinstance(val, np.generic):
        return val.item()
    if isinstance(val, float) and (val != val):
        return None
    return val


def analyze_stp_decay_to_yaml(
    time,
    current,
    step_dir: Path,
    instrument: str = "",
    devices: str = "",
) -> Path:
    """Analyze STP decay and write YAML analysis file."""
    from science_cli.core.analysis_output import write_analysis_yaml

    stats = analyze_stp_decay(time, current)

    if "error" in stats:
        output = {"analysis": {"error": stats["error"]}}
    else:
        output = {
            "analysis": {
                "mode": devices or "general",
                "decay_fit": {
                    "model": stats.get("model"),
                    "tau1_ms": _to_native(stats.get("tau1_ms")),
                    "tau2_ms": _to_native(stats.get("tau2_ms")),
                    "a1": _to_native(stats.get("a1")),
                    "a2": _to_native(stats.get("a2")),
                    "r_squared": _to_native(stats.get("r_squared")),
                },
                "parameters": {
                    "initial_current_ua": _to_native(stats.get("initial_current_ua")),
                    "steady_state_current_ua": _to_native(stats.get("steady_state_current_ua")),
                    "decay_pct": _to_native(stats.get("decay_pct")),
                },
            },
        }

    return write_analysis_yaml(
        technique="pulse-stp",
        step_dir=step_dir,
        analysis_results=output,
        instrument=instrument,
        devices=devices,
    )
