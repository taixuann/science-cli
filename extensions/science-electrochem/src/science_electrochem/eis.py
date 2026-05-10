"""EIS analysis: circuit fitting, Kramers-Kronig validation."""

import numpy as np
from lmfit import Model, Parameters
from science_electrochem.models import EISData


def analyze_eis(data: EISData, options: dict | None = None) -> dict:
    options = options or {}
    results = {}

    if options.get("circuit", True):
        circuit = options.get("circuit_model", "RRC")
        results["circuit_fit"] = circuit_fit(data, circuit)

    if options.get("kk", False):
        results["kk"] = kramers_kronig(data)

    return results


_circuit_functions = {}


def _register_circuit(name, func):
    _circuit_functions[name] = func


def _rc_series(f, R, C):
    w = 2 * np.pi * f
    Z = R + 1.0 / (1j * w * C)
    return Z


def _rrc_randles(f, Rs, Rct, Cdl):
    w = 2 * np.pi * f
    Z = Rs + 1.0 / (1j * w * Cdl + 1.0 / Rct)
    return Z


def _rq_randles(f, Rs, Rct, Q_mag, Q_n):
    w = 2 * np.pi * f
    Zcpe = 1.0 / (Q_mag * (1j * w) ** Q_n)
    Z = Rs + 1.0 / (1.0 / Zcpe + 1.0 / Rct)
    return Z


_register_circuit("RC", _rc_series)
_register_circuit("RRC", _rrc_randles)
_register_circuit("RQR", _rq_randles)
_register_circuit("Randles", _rq_randles)


def circuit_fit(data: EISData, circuit: str = "RRC") -> dict:
    f = data.frequency
    Z = data.impedance

    if circuit not in _circuit_functions:
        return {"error": f"Unknown circuit: {circuit}"}

    func = _circuit_functions[circuit]

    def residuals(params, f, Z_real, Z_imag):
        Z_calc = func(f, **{k: params[k].value for k in params})
        return np.concatenate([Z_calc.real - Z_real, Z_calc.imag - Z_imag])

    params = Parameters()
    if circuit == "RC":
        params.add("R", value=1000, min=1, max=1e9)
        params.add("C", value=1e-6, min=1e-12, max=1)
    elif circuit == "RRC":
        params.add("Rs", value=100, min=1, max=1e6)
        params.add("Rct", value=1000, min=1, max=1e9)
        params.add("Cdl", value=1e-6, min=1e-12, max=1)
    elif circuit in ("RQR", "Randles"):
        params.add("Rs", value=100, min=1, max=1e6)
        params.add("Rct", value=1000, min=1, max=1e9)
        params.add("Q_mag", value=1e-6, min=1e-12, max=1)
        params.add("Q_n", value=0.8, min=0.5, max=1.0, vary=True)

    from lmfit import Minimizer
    Z_real, Z_imag = Z.real, Z.imag

    minner = Minimizer(residuals, params, fcn_args=(f, Z_real, Z_imag))
    try:
        result = minner.minimize(method="leastsq")
        param_names = list(params.keys())
        fitted = [float(result.params[p].value) for p in param_names]
        stderr = [float(result.params[p].stderr or 0) for p in param_names]

        Z_fit = func(f, **{p: result.params[p].value for p in param_names})
        residuals_abs = np.abs(Z_fit - Z)
        r_squared = 1 - np.sum(residuals_abs ** 2) / np.sum(np.abs(Z - np.mean(Z)) ** 2)

        return {
            "circuit": circuit,
            "parameter_names": param_names,
            "fitted_params": fitted,
            "param_stderr": stderr,
            "r_squared": float(r_squared),
            "reduced_chi": float(result.redchi),
            "nfev": result.nfev,
            "fit_Z_real": Z_fit.real.tolist(),
            "fit_Z_imag": Z_fit.imag.tolist(),
            "fit_frequency": f.tolist(),
        }
    except Exception as e:
        return {"error": str(e)}


def kramers_kronig(data: EISData) -> dict:
    f = data.frequency
    Z = data.impedance

    n_poles = min(10, len(f) // 2)
    f_min, f_max = f.min(), f.max()
    poles = np.logspace(np.log10(f_min), np.log10(f_max), n_poles)

    from lmfit import Parameters, Minimizer

    def model_Z(f, poles_params):
        tau = 1.0 / (2 * np.pi * poles)
        R_inf = poles_params.get("R_inf", 0)
        Z_mod = R_inf * np.ones_like(f, dtype=complex)
        for i in range(len(tau)):
            Rk = poles_params.get(f"R_{i}", 0)
            Z_mod += Rk / (1 + 1j * 2 * np.pi * f * tau[i])
        return Z_mod

    params = Parameters()
    params.add("R_inf", value=Z.real.min(), min=0)
    for i in range(len(poles)):
        params.add(f"R_{i}", value=Z.real.mean() / n_poles, min=0)

    def residuals(params, f, Z_real, Z_imag):
        Z_calc = model_Z(f, params)
        return np.concatenate([Z_calc.real - Z_real, Z_calc.imag - Z_imag])

    minner = Minimizer(residuals, params, fcn_args=(f, Z.real, Z.imag))
    try:
        result = minner.minimize(method="leastsq")
        Z_fit = model_Z(f, result.params)

        residuals_abs = np.abs(Z_fit - Z)
        rel_residuals = residuals_abs / np.abs(Z) * 100
        score = float(np.mean(rel_residuals))

        return {
            "passes": score < 5.0,
            "consistency_score": score,
            "n_poles": n_poles,
            "reduced_chi": float(result.redchi),
        }
    except Exception as e:
        return {"error": str(e), "passes": False, "consistency_score": 999}
