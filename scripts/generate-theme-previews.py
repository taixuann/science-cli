"""Generate theme previews — single + overlay, every theme.

Run:  python scripts/generate-theme-previews.py
Output:  theme-previews/{theme}/{plot}.pdf
"""

from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from science_cli.theme import list_themes, apply_theme
from science_cli.plot.base import plot_line

OUT = Path(__file__).resolve().parent.parent / "theme-previews"
FIGSIZE = (7, 5)
SAVE_DPI = 600


# ── Sample data ──────────────────────────────────────────────

def _sample_cv():
    E = np.linspace(-0.6, 0.8, 600)
    I = np.zeros_like(E)
    mid = len(E) // 2
    I[:mid] = 1e-5 * (1 - np.exp(-10 * (E[:mid] - 0.4)**2)) + 2e-6 * (E[:mid] + 0.6)
    I[mid:] = -1e-5 * (1 - np.exp(-10 * (E[mid:] + 0.2)**2)) + 2e-6 * (0.8 - E[mid:])
    I += np.random.default_rng(42).normal(0, 2e-7, size=len(E))
    return E, I


def _sample_cv_overlay(n=3):
    curves = []
    for j in range(n):
        scale = [1.0, 0.7, 1.3][j]
        shift = [0, 0.05, -0.08][j]
        _, I = _sample_cv()
        E = np.linspace(-0.6 + shift, 0.8 + shift, 600)
        I = I * scale
        I += np.random.default_rng(42 + j).normal(0, 1e-7, size=600)
        curves.append((E, I, f"CV {chr(65 + j)}"))
    return curves


def _sample_ca():
    t = np.linspace(0.05, 5, 300)
    I = 5e-5 / np.sqrt(t) + 2e-6
    I += np.random.default_rng(42).normal(0, 5e-7, size=len(t))
    return t, I


def _sample_ca_overlay(n=3):
    curves = []
    for j in range(n):
        amp = [1.0, 0.6, 1.4][j]
        t = np.linspace(0.05, 5, 300)
        I = amp * 5e-5 / np.sqrt(t) + 2e-6
        I += np.random.default_rng(42 + j).normal(0, 5e-7, size=len(t))
        curves.append((t, I, f"CA {chr(65 + j)}"))
    return curves


def _sample_eis():
    rng = np.random.default_rng(42)
    f = np.logspace(4, -1, 50)
    Z = 100 + 500 / (1 + 1j * 2 * np.pi * f * 500 * 1e-6)
    Zr, Zi = Z.real, Z.imag + rng.normal(0, 2, size=len(Z))
    mag = np.abs(Z)
    phase = -np.angle(Z, deg=True)
    return Zr, Zi, f, mag, phase


def _sample_eis_overlay(n=3):
    f = np.logspace(4, -1, 50)
    curves = []
    for j in range(n):
        Rct, Cdl = [(500, 1e-6), (800, 0.5e-6), (300, 2e-6)][j]
        Z = 100 + Rct / (1 + 1j * 2 * np.pi * f * Rct * Cdl)
        rng = np.random.default_rng(42 + j)
        Zr, Zi = Z.real, Z.imag + rng.normal(0, 2, size=len(Z))
        curves.append((Zr, Zi, f"EIS {chr(65 + j)}"))
    return curves


def _sample_iv():
    rng = np.random.default_rng(42)
    V = np.concatenate([
        np.linspace(0, 2, 200), np.linspace(2, 0, 200),
        np.linspace(0, -2, 200), np.linspace(-2, 0, 200),
    ])
    I = np.empty(800)
    for i in range(4):
        start, end = i * 200, (i + 1) * 200
        seg_V = V[start:end]
        if i in (0, 3):  # forward (LRS)
            R = 1e3
        else:  # reverse (HRS)
            R = 1e5
        I[start:end] = seg_V / R + rng.normal(0, 1e-6, 200)
    t = np.arange(800) * 0.01
    return t, V, I


def _sample_iv_overlay():
    curves = []
    for j, (R_on, R_off) in enumerate([(1e4, 3e4), (8e3, 4e4), (1.2e4, 3.5e4)]):
        V = np.concatenate([
            np.linspace(0, 2, 200), np.linspace(2, 0, 200),
            np.linspace(0, -2, 200), np.linspace(-2, 0, 200),
        ])
        I = np.empty(800)
        rng = np.random.default_rng(42 + j)
        for k in range(4):
            s, e = k * 200, (k + 1) * 200
            R = R_on if k in (0, 3) else R_off
            I[s:e] = V[s:e] / R + rng.normal(0, 1e-6, 200)
        curves.append((V, I, f"Device {chr(65 + j)}"))
    return curves


# ── Sweep helpers ────────────────────────────────────────────

def _extract_sweep_segments(V, t):
    dV = np.diff(V)
    segs, start = [], 0
    for i in range(1, len(dV)):
        if dV[i-1] * dV[i] < 0:
            dt = t[i] - t[start]
            if dt > 0:
                segs.append((start, i, (V[i] - V[start]) / dt))
            start = i
    dt = t[-1] - t[start]
    if dt > 0:
        segs.append((start, len(V)-1, (V[-1] - V[start]) / dt))
    return segs


def _seg_arrow(ax, x, y, color, seg_num, offset_pt=24):
    """Offset arrow parallel to curve using display-coordinate math. No blank-page bug."""
    mid = len(x) // 2
    if mid < 4 or mid >= len(x) - 4:
        return
    tr = ax.transData
    inv = tr.inverted()
    # Direction in display coordinates
    p_fwd = tr.transform((x[mid+4], y[mid+4]))
    p_bwd = tr.transform((x[mid-4], y[mid-4]))
    disp_dx = p_fwd[0] - p_bwd[0]
    disp_dy = p_fwd[1] - p_bwd[1]
    norm = np.hypot(disp_dx, disp_dy)
    if norm < 1:
        return
    # Perpendicular unit vector in display space
    perp = np.array([-disp_dy / norm, disp_dx / norm]) * offset_pt
    # Shift both endpoints in display space
    tail_d = tr.transform((x[mid-4], y[mid-4])) + perp
    head_d = tr.transform((x[mid+4], y[mid+4])) + perp
    tail_d_inv = inv.transform(tail_d)
    head_d_inv = inv.transform(head_d)
    ax.annotate("", xy=head_d_inv, xytext=tail_d_inv,
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2))
    # Circled number at midpoint of shifted arrow
    mid_d = (tail_d + head_d) / 2
    mid_d_inv = inv.transform(mid_d)
    ax.text(mid_d_inv[0], mid_d_inv[1], str(seg_num),
            fontsize=7, color=color, ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="circle,pad=0.1", fc="white", ec=color, lw=0.8))


# ── CV plots ─────────────────────────────────────────────────

def _plot_cv(ax, E, I, theme):
    apply_theme(theme)
    plot_line(E, I, ax=ax, flags={"color": "#1f77b4", "linewidth": 1.5})
    ax.set_xlabel("Potential (V)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"Cyclic Voltammetry — {theme}", fontsize=12)


def _plot_cv_overlay(ax, curves, theme):
    apply_theme(theme)
    cycle = plt.rcParams["axes.prop_cycle"]
    colors = [e["color"] for e in cycle]
    for i, (x, y, label) in enumerate(curves):
        ax.plot(x, y, color=colors[i % len(colors)], linewidth=1.5, label=label)
    ax.set_xlabel("Potential (V)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"CV Overlay — {theme}", fontsize=12)
    ax.legend(fontsize=9)


def _plot_cv_annotated(ax, E, I, theme):
    _plot_cv(ax, E, I, theme)
    mid = len(E) // 2
    fwd_i = np.argmax(I[:mid])
    rev_i = np.argmin(I[mid:]) + mid
    for name, idx, yoff in [("E_pa", fwd_i, 20), ("E_pc", rev_i, -20)]:
        ax.annotate(name, xy=(E[idx], I[idx]), xytext=(15, yoff),
                    textcoords="offset points", fontsize=8, color="red",
                    arrowprops=dict(arrowstyle="->", color="red", lw=1.2),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", lw=0.5))


# ── CA plots ─────────────────────────────────────────────────

def _plot_ca(ax, t, I, theme):
    apply_theme(theme)
    plot_line(t, I, ax=ax, flags={"color": "#ff7f0e", "linewidth": 1.5})
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"Chronoamperometry — {theme}", fontsize=12)


def _plot_ca_overlay(ax, curves, theme):
    apply_theme(theme)
    cycle = plt.rcParams["axes.prop_cycle"]
    colors = [e["color"] for e in cycle]
    for i, (x, y, label) in enumerate(curves):
        ax.plot(x, y, color=colors[i % len(colors)], linewidth=1.5, label=label)
    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"CA Overlay — {theme}", fontsize=12)
    ax.legend(fontsize=9)


def _plot_ca_annotated(ax, t, I, theme):
    _plot_ca(ax, t, I, theme)
    ax.annotate("I_ss", xy=(t[-1], I[-1]), xytext=(-40, -30),
                textcoords="offset points", fontsize=8, color="red",
                arrowprops=dict(arrowstyle="->", color="red", lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", lw=0.5))
    t_half = t[min(np.searchsorted(I, I[-1] + (I[0] - I[-1]) / 2), len(t) - 1)]
    ax.axvline(t_half, color="gray", ls="--", lw=0.8, alpha=0.6)
    ax.annotate("t_1/2", xy=(t_half, ax.get_ylim()[1] * 0.6),
                fontsize=8, color="gray", ha="center")


# ── IV plots ─────────────────────────────────────────────────

def _plot_iv(ax, t, V, I, theme):
    apply_theme(theme)
    segs = _extract_sweep_segments(V, t)
    colors_line = ["#0072B2", "#009E73", "#D55E00", "#E69F00"]
    for i, (s, e, rate) in enumerate(segs):
        ax.plot(V[s:e+1], I[s:e+1], color=colors_line[i], linewidth=1.5)
        _seg_arrow(ax, V[s:e+1], I[s:e+1], colors_line[i], i + 1)
    ax.set_xlabel("Voltage (V)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"IV Curve — {theme}", fontsize=12)


def _plot_iv_overlay(ax, curves, theme):
    apply_theme(theme)
    cycle = plt.rcParams["axes.prop_cycle"]
    colors = [e["color"] for e in cycle]
    for i, (x, y, label) in enumerate(curves):
        ax.plot(x, y, color=colors[i % len(colors)], linewidth=1.5, label=label)
    ax.set_xlabel("Voltage (V)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"IV Overlay — {theme}", fontsize=12)
    ax.legend(fontsize=9)


def _plot_iv_annotated(ax, t, V, I, theme):
    apply_theme(theme)
    segs = _extract_sweep_segments(V, t)
    colors_cycle = ["#0072B2", "#009E73", "#D55E00", "#E69F00"]
    for i, (s, e, rate) in enumerate(segs):
        c = colors_cycle[i]
        d = "fwd" if rate > 0 else "rev"
        ax.plot(V[s:e+1], I[s:e+1], color=c, linewidth=1.5, label=f"Seg {i+1} ({d})")
        _seg_arrow(ax, V[s:e+1], I[s:e+1], c, i + 1)
    ax.annotate("RESET", xy=(1.3, 2e-5), fontsize=8, color="#D55E00",
                arrowprops=dict(arrowstyle="->", color="#D55E00", lw=1.2))
    ax.annotate("SET", xy=(-1.0, -2e-5), fontsize=8, color="#E69F00",
                arrowprops=dict(arrowstyle="->", color="#E69F00", lw=1.2))
    ax.set_xlabel("Voltage (V)", fontsize=11)
    ax.set_ylabel("Current (A)", fontsize=11)
    ax.set_title(f"IV Curve — {theme} (annotated)", fontsize=12)
    ax.legend(fontsize=8)


# ── EIS plots ────────────────────────────────────────────────

def _plot_eis(ax, Zr, Zi, f, mag, phase, theme):
    apply_theme(theme)
    plot_line(Zr, -Zi, ax=ax, flags={"color": "#2ca02c", "linewidth": 1.5, "marker": "o", "markersize": 4})
    ax.set_xlabel("Z' (Ω)", fontsize=11)
    ax.set_ylabel("-Z'' (Ω)", fontsize=11)
    ax.set_title(f"Nyquist Plot — {theme}", fontsize=12)
    ax.set_aspect("equal")


def _plot_eis_overlay(ax, curves, theme):
    apply_theme(theme)
    cycle = plt.rcParams["axes.prop_cycle"]
    colors = [e["color"] for e in cycle]
    markers = ["o", "s", "^"]
    for i, (Zr, Zi, label) in enumerate(curves):
        ax.plot(Zr, -Zi, color=colors[i % len(colors)], linewidth=1.5,
                label=label, marker=markers[i], markersize=4)
    ax.set_xlabel("Z' (Ω)", fontsize=11)
    ax.set_ylabel("-Z'' (Ω)", fontsize=11)
    ax.set_title(f"Nyquist Overlay — {theme}", fontsize=12)
    ax.set_aspect("equal")
    ax.legend(fontsize=9)


def _plot_eis_bode(ax, Zr, Zi, f, mag, phase, theme):
    apply_theme(theme)
    idx = np.argsort(f)
    ax.loglog(f[idx], mag[idx], color="#1f77b4", linewidth=1.5, label="|Z|")
    ax.invert_xaxis()
    ax.set_xlabel("Frequency (Hz)", fontsize=11)
    ax.set_ylabel("|Z| (Ω)", fontsize=11, color="#1f77b4")
    ax.tick_params(axis="y", labelcolor="#1f77b4")
    ax.grid(True, alpha=0.3)
    ax2 = ax.twinx()
    ax2.semilogx(f[idx], phase[idx], color="#d62728", linewidth=1.2, linestyle="--", label="Phase")
    ax2.set_ylabel("Phase (°)", fontsize=11, color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    ax2.set_xscale("log")
    ax2.set_xlim(ax.get_xlim())
    ax2.legend(fontsize=9, loc="lower left")
    ax.set_title(f"Bode Plot — {theme}", fontsize=12)
    ax.legend(fontsize=9, loc="lower right")


def _plot_eis_annotated(ax, Zr, Zi, f, mag, phase, theme):
    _plot_eis(ax, Zr, Zi, f, mag, phase, theme)
    Rs, Rct = Zr.min(), Zr.max() - Zr.min()
    for val, label, xoff in [(Rs, "R_s", 20), (Rs + Rct, "R_s + R_ct", -80)]:
        ax.annotate(label, xy=(val, 0), xytext=(xoff, 20),
                    textcoords="offset points", fontsize=8, color="red",
                    arrowprops=dict(arrowstyle="->", color="red", lw=1.2),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", lw=0.5))


# ── Main ─────────────────────────────────────────────────────

def main():
    themes = list_themes()
    print(f"Generating for {len(themes)} themes: {themes}")

    cv_E, cv_I = _sample_cv()
    ca_t, ca_I = _sample_ca()
    eis_Zr, eis_Zi, eis_f, eis_mag, eis_phase = _sample_eis()
    iv_t, iv_V, iv_I = _sample_iv()
    cv_curves = _sample_cv_overlay()
    ca_curves = _sample_ca_overlay()
    eis_curves = _sample_eis_overlay()
    iv_curves = _sample_iv_overlay()

    for theme in themes:
        theme_dir = OUT / theme
        theme_dir.mkdir(parents=True, exist_ok=True)
        is_ann = "annotated" in theme
        plots = [
            ("cv.pdf", _plot_cv_annotated if is_ann else _plot_cv, (cv_E, cv_I)),
            ("cv-overlay.pdf", _plot_cv_overlay, (cv_curves,)),
            ("ca.pdf", _plot_ca_annotated if is_ann else _plot_ca, (ca_t, ca_I)),
            ("ca-overlay.pdf", _plot_ca_overlay, (ca_curves,)),
            ("iv.pdf", _plot_iv_annotated if is_ann else _plot_iv, (iv_t, iv_V, iv_I)),
            ("iv-overlay.pdf", _plot_iv_overlay, (iv_curves,)),
            ("eis-nyquist.pdf", _plot_eis_annotated if is_ann else _plot_eis, (eis_Zr, eis_Zi, eis_f, eis_mag, eis_phase)),
            ("eis-overlay.pdf", _plot_eis_overlay, (eis_curves,)),
            ("eis-bode.pdf", _plot_eis_bode, (eis_Zr, eis_Zi, eis_f, eis_mag, eis_phase)),
        ]
        for name, fn, data in plots:
            apply_theme(theme)
            fig, ax = plt.subplots(figsize=FIGSIZE)
            fn(ax, *data, theme)
            fig.savefig(theme_dir / name, dpi=SAVE_DPI, bbox_inches="tight", pad_inches=0.05)
            plt.close(fig)
            print(f"  {theme}/{name}")

    print(f"\nDone. Open {OUT} to browse.")


if __name__ == "__main__":
    main()
