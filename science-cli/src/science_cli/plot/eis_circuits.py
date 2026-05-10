"""EIS equivalent circuit models and fitting using lmfit.

Provides a registry of thin-film relevant circuit models (Randles, Randles-CPE,
and Warburg-based diffusion models) with numpy-based simulation functions and
lmfit-based fitting.

Circuits:
    RRC    — Rs + (Rct || Cdl)                [3 params: Rs, Rct, Cdl]
    RQR    — Rs + (Rct || CPE)                [4 params: Rs, Rct, Q_mag, Q_n]
    RsRQW  — Rs + CPE || (Rct + Warburg)      [5 params: Rs, Rct, Q_mag, Q_n, sigma]
    RsRCW  — Rs + C || (Rct + Warburg)        [4 params: Rs, Rct, C, sigma]

Z_W = sigma / sqrt(j*omega)     Z_Q = 1 / (Q_mag * (j*omega)^n)
"""

import numpy as np
from lmfit import Minimizer, Parameters

# --- Circuit registry ---

CIRCUIT_REGISTRY = {
    "RRC": {"params": ["Rs", "Rct", "Cdl"], "desc": "Randles (simple)"},
    "RQR": {"params": ["Rs", "Rct", "Q_mag", "Q_n"], "desc": "Randles with CPE"},
    "RsRQW": {"params": ["Rs", "Rct", "Q_mag", "Q_n", "sigma"], "desc": "Rs + Q || (Rct + Warburg)"},
    "RsRCW": {"params": ["Rs", "Rct", "C", "sigma"], "desc": "Rs + C || (Rct + Warburg)"},
}

# --- Unit labels per circuit ---

_UNITS = {
    "RRC": {"Rs": "Ω", "Rct": "Ω", "Cdl": "F"},
    "RQR": {"Rs": "Ω", "Rct": "Ω", "Q_mag": "S·s^n", "Q_n": ""},
    "RsRQW": {"Rs": "Ω", "Rct": "Ω", "Q_mag": "S·s^n", "Q_n": "", "sigma": "Ω·s⁻⁰.⁵"},
    "RsRCW": {"Rs": "Ω", "Rct": "Ω", "C": "F", "sigma": "Ω·s⁻⁰.⁵"},
}

# --- Impedance primitives ---

def _z_warburg(omega: np.ndarray, sigma: float) -> np.ndarray:
    """Warburg impedance: Z_W = sigma / sqrt(j*omega) = sigma*(1-j)/sqrt(omega)."""
    return sigma / np.sqrt(1j * omega)


def _z_cpe(omega: np.ndarray, Q_mag: float, n: float) -> np.ndarray:
    """CPE impedance: Z_Q = 1 / (Q_mag * (j*omega)^n)."""
    return 1.0 / (Q_mag * (1j * omega) ** n)


# --- Circuit simulation functions ---

def _sim_rrc(omega, Rs, Rct, Cdl):
    """Simple Randles: Rs + (Rct || Cdl)."""
    return Rs + 1.0 / (1.0 / Rct + 1j * omega * Cdl)


def _sim_rqr(omega, Rs, Rct, Q_mag, Q_n):
    """Randles with CPE: Rs + (Rct || CPE)."""
    z_q = _z_cpe(omega, Q_mag, Q_n)
    return Rs + 1.0 / (1.0 / Rct + 1.0 / z_q)


def _sim_rsrqw(omega, Rs, Rct, Q_mag, Q_n, sigma):
    """Rs + Q || (Rct + Warburg).
    Z = Rs + 1 / (1/Z_Q + 1/(Rct + Z_W))
    """
    z_q = _z_cpe(omega, Q_mag, Q_n)
    z_w = _z_warburg(omega, sigma)
    return Rs + 1.0 / (1.0 / z_q + 1.0 / (Rct + z_w))


def _sim_rsrcw(omega, Rs, Rct, C, sigma):
    """Rs + C || (Rct + Warburg).
    Z = Rs + 1 / (1/Z_C + 1/(Rct + Z_W))      where Z_C = 1/(j*omega*C)
    """
    z_c = 1.0 / (1j * omega * C)
    z_w = _z_warburg(omega, sigma)
    return Rs + 1.0 / (1.0 / z_c + 1.0 / (Rct + z_w))


# Map model names to simulation callables
_SIM_FUNCS = {
    "RRC": _sim_rrc,
    "RQR": _sim_rqr,
    "RsRQW": _sim_rsrqw,
    "RsRCW": _sim_rsrcw,
}

# --- Parameter bounds and initial guesses ---

# Default initial guesses (overridden by data-driven estimates for Rs, Rct, C)
_PARAM_DEFAULTS = {
    "Rs": {"init_guess": None, "min": 0.0, "max": 1e9},
    "Rct": {"init_guess": None, "min": 0.0, "max": 1e12},
    "Cdl": {"init_guess": 1e-6, "min": 1e-15, "max": 1.0},
    "C": {"init_guess": 1e-6, "min": 1e-15, "max": 1.0},
    "Q_mag": {"init_guess": 1e-6, "min": 1e-12, "max": 1.0},
    "Q_n": {"init_guess": 0.9, "min": 0.5, "max": 1.0},
    "sigma": {"init_guess": 100.0, "min": 0.0, "max": 1e9},
}


def fit_eis_circuit(frequency, Z_data, model_name):
    """Fit EIS data to an equivalent circuit model using lmfit least-squares.

    Residuals are formed by concatenating real and imaginary impedance errors
    with equal weight.

    Args:
        frequency: 1-D array of frequencies (Hz).
        Z_data: 1-D array of complex impedances.
        model_name: Key in CIRCUIT_REGISTRY ("RRC", "RQR", "RsRQW", "RsRCW").

    Returns:
        dict on success:
            circuit        — model name used
            parameter_names — ordered list of parameter names
            fitted_params   — best-fit values (floats)
            param_stderr    — standard errors (floats; 0.0 if unavailable)
            param_error_pct — |stderr/value|*100 (None if value ≈ 0)
            r_squared       — coefficient of determination
            reduced_chi     — reduced chi-squared
            fit_Z_real      — fitted real impedance (list)
            fit_Z_imag      — fitted imaginary impedance (list)
            fit_frequency   — frequency array used (list)
            units           — unit labels per parameter
        dict with key "error" on failure.
    """
    if model_name not in CIRCUIT_REGISTRY:
        available = list(CIRCUIT_REGISTRY.keys())
        return {"error": f"Unknown circuit model: {model_name}. Available: {available}"}

    sim_func = _SIM_FUNCS[model_name]
    param_names = CIRCUIT_REGISTRY[model_name]["params"]

    f = np.asarray(frequency, dtype=float)
    Z = np.asarray(Z_data, dtype=complex)
    omega = 2.0 * np.pi * f

    if len(f) == 0 or len(Z) == 0:
        return {"error": "Empty frequency or impedance data"}

    Z_real = np.real(Z)
    Z_imag = np.imag(Z)

    # --- Data-driven initial guesses ---
    rs_guess = max(float(np.min(Z_real)), 0.1)
    rct_guess = max(float(np.max(Z_real) - np.min(Z_real)), 1.0)

    # Capacitance estimate from frequency at the -Z'' peak
    neg_z_imag = -Z_imag
    peak_idx = int(np.argmax(neg_z_imag))
    f_peak = f[min(peak_idx, len(f) - 1)]
    if f_peak > 0 and rct_guess > 0:
        c_guess = max(1.0 / (2.0 * np.pi * f_peak * rct_guess), 1e-12)
    else:
        c_guess = 1e-6

    data_guesses = {
        "Rs": rs_guess,
        "Rct": rct_guess,
        "Cdl": c_guess,
        "C": c_guess,
        "Q_mag": c_guess,
    }

    # --- Build lmfit Parameters ---
    params = Parameters()
    for name in param_names:
        bounds = _PARAM_DEFAULTS.get(name, {})
        init = bounds.get("init_guess")
        if init is None:
            init = data_guesses.get(name, 1.0)
        params.add(
            name,
            value=init,
            min=bounds.get("min", -np.inf),
            max=bounds.get("max", np.inf),
            vary=True,
        )

    # --- Residual: real + imaginary errors concatenated ---
    def residual(pars, omega_arr, Z_meas):
        vals = pars.valuesdict()
        Z_model = sim_func(omega_arr, **vals)
        res_real = np.real(Z_model) - np.real(Z_meas)
        res_imag = np.imag(Z_model) - np.imag(Z_meas)
        return np.concatenate([res_real, res_imag])

    # --- Run fit ---
    try:
        minimizer = Minimizer(residual, params, fcn_args=(omega, Z))
        result = minimizer.minimize(method="leastsq")
    except Exception as e:
        return {"error": f"Fit raised exception: {e}"}

    if not result.success:
        return {"error": f"Fit did not converge: {result.message}"}

    # --- Fit quality ---
    n_data = 2 * len(Z)
    n_params = len([p for p in result.params.values() if p.vary])
    dof = max(n_data - n_params, 1)
    if hasattr(result, "redchi") and result.redchi is not None:
        red_chi = result.redchi
    else:
        red_chi = float(np.sum(result.residual ** 2) / dof)

    Z_fit = sim_func(omega, **result.params.valuesdict())
    ss_res = float(np.sum((np.real(Z_fit - Z)) ** 2 + (np.imag(Z_fit - Z)) ** 2))
    ss_tot = float(np.sum((np.real(Z - np.mean(Z))) ** 2 + (np.imag(Z - np.mean(Z))) ** 2))
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else 0.0

    # --- Extract parameters ---
    fitted_params = []
    param_stderr = []
    param_error_pct = []

    for name in param_names:
        p = result.params.get(name)
        if p is not None:
            fitted_params.append(float(p.value))
            stderr = float(p.stderr) if p.stderr is not None else 0.0
            param_stderr.append(stderr)
            if abs(p.value) > 1e-15 and stderr > 0:
                param_error_pct.append(abs(stderr / p.value) * 100.0)
            else:
                param_error_pct.append(None)
        else:
            fitted_params.append(0.0)
            param_stderr.append(0.0)
            param_error_pct.append(None)

    return {
        "circuit": model_name,
        "parameter_names": list(param_names),
        "fitted_params": fitted_params,
        "param_stderr": param_stderr,
        "param_error_pct": param_error_pct,
        "r_squared": r_sq,
        "reduced_chi": red_chi,
        "fit_Z_real": np.real(Z_fit).tolist(),
        "fit_Z_imag": np.imag(Z_fit).tolist(),
        "fit_frequency": f.tolist(),
        "units": dict(_UNITS.get(model_name, {})),
    }
