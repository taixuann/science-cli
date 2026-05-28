#!/usr/bin/env python3
"""Generate Nature-themed preview plots for all techniques.

Usage:
    python scripts/generate_nature_previews.py
    python scripts/generate_nature_previews.py --output /path/to/output

Each technique gets its own figure with the publication-nature theme applied.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from science_cli.theme import apply_theme


def _setup_ax(ax, xlabel, ylabel, title=""):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)


def generate_iv_sweep(output_dir):
    """IV sweep: voltage vs current with set/reset switching."""
    fig, ax = plt.subplots()
    v = np.linspace(0, 5, 200)
    # Forward: low resistance state
    i_fwd = v * 1e-3 * (1 + 0.1 * np.sin(v * 10))
    # Reset at ~3V
    reset_idx = np.argmin(np.abs(v - 3))
    i_fwd[reset_idx:] = i_fwd[reset_idx:] * 0.1
    # Reverse: high resistance state
    i_rev = v * 0.1e-3 * (1 + 0.05 * np.sin(v * 8))
    ax.plot(v, i_fwd * 1e6, label="Forward", linewidth=0.75)
    ax.plot(v, i_rev * 1e6, label="Reverse", linewidth=0.75)
    _setup_ax(ax, "Voltage (V)", "Current (µA)", "")
    ax.legend()
    fig.savefig(output_dir / "nature_iv-sweep.png", dpi=150)
    fig.savefig(output_dir / "nature_iv-sweep.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ iv-sweep")


def generate_iv_breakdown(output_dir):
    """IV breakdown: voltage vs log|current| showing breakdown."""
    fig, ax = plt.subplots()
    v = np.linspace(0, 12, 300)
    i = 1e-12 * np.exp(v / 2) + 1e-6 * (v > 8) * (v - 8) ** 2
    ax.semilogy(v, i * 1e6, linewidth=0.75)
    _setup_ax(ax, "Voltage (V)", "Current (µA)", "")
    fig.savefig(output_dir / "nature_iv-breakdown.png", dpi=150)
    fig.savefig(output_dir / "nature_iv-breakdown.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ iv-breakdown")


def generate_iv_leakage(output_dir):
    """IV leakage: low-bias leakage current."""
    fig, ax = plt.subplots()
    v = np.linspace(-2, 2, 200)
    i = 1e-9 * v + 5e-11 * np.sign(v) * (np.abs(v) ** 1.5)
    ax.plot(v, i * 1e12, linewidth=0.75)
    _setup_ax(ax, "Voltage (V)", "Leakage (pA)", "")
    fig.savefig(output_dir / "nature_iv-leakage.png", dpi=150)
    fig.savefig(output_dir / "nature_iv-leakage.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ iv-leakage")


def generate_ec_cv(output_dir):
    """CV: cyclic voltammogram with redox peaks."""
    fig, ax = plt.subplots()
    v = np.linspace(-0.5, 0.8, 400)
    rev = v[::-1]
    i_fwd = (-1e-3 * np.sin(4 * v) - 0.5e-3) * (1 + 0.1 * np.random.randn(len(v)))
    i_rev = (-1e-3 * np.sin(4 * rev) + 0.3e-3) * (1 + 0.1 * np.random.randn(len(v)))
    ax.plot(v, i_fwd * 1e3, label="Forward", linewidth=0.75)
    ax.plot(v, i_rev * 1e3, label="Reverse", linewidth=0.75)
    _setup_ax(ax, "E vs Ref (V)", "I (mA)", "")
    ax.legend()
    fig.savefig(output_dir / "nature_ec-cv.png", dpi=150)
    fig.savefig(output_dir / "nature_ec-cv.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ ec-cv")


def generate_ec_ca(output_dir):
    """CA: chronoamperometry decay."""
    fig, ax = plt.subplots()
    t = np.linspace(0.01, 5, 200)
    i = 1e-3 / np.sqrt(t) + 5e-6
    ax.plot(t, i * 1e3, linewidth=0.75)
    _setup_ax(ax, "Time (s)", "Current (mA)", "")
    fig.savefig(output_dir / "nature_ec-ca.png", dpi=150)
    fig.savefig(output_dir / "nature_ec-ca.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ ec-ca")


def generate_ec_eis(output_dir):
    """EIS: Nyquist plot."""
    fig, ax = plt.subplots()
    # RC circuit: semicircle
    omega = np.logspace(-1, 4, 100)
    r = 500
    c = 1e-6
    z_re = r / (1 + (omega * r * c) ** 2)
    z_im = omega * r ** 2 * c / (1 + (omega * r * c) ** 2)
    ax.plot(z_re, -z_im, "o-", markersize=2, linewidth=0.75)
    ax.set_aspect("equal")
    _setup_ax(ax, "Z' (Ω)", "-Z'' (Ω)", "")
    fig.savefig(output_dir / "nature_ec-eis.png", dpi=150)
    fig.savefig(output_dir / "nature_ec-eis.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ ec-eis")


def generate_raman(output_dir):
    """Raman spectrum."""
    fig, ax = plt.subplots()
    x = np.linspace(200, 3200, 500)
    y = 100 * np.exp(-((x - 1350) ** 2) / 40000) + \
        80 * np.exp(-((x - 1580) ** 2) / 25000) + \
        30 * np.exp(-((x - 2800) ** 2) / 90000) + \
        20 * np.exp(-((x - 2950) ** 2) / 40000) + \
        5 + 2 * np.random.randn(len(x))
    ax.plot(x, y, linewidth=0.75)
    _setup_ax(ax, "Raman shift (cm⁻¹)", "Intensity (a.u.)", "")
    fig.savefig(output_dir / "nature_raman.png", dpi=150)
    fig.savefig(output_dir / "nature_raman.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ raman")


def generate_uv_vis(output_dir):
    """UV-Vis absorbance spectrum."""
    fig, ax = plt.subplots()
    x = np.linspace(300, 800, 300)
    y = 0.8 * np.exp(-((x - 450) ** 2) / 4000) + \
        0.3 * np.exp(-((x - 550) ** 2) / 3000) + \
        0.05 + 0.02 * np.random.randn(len(x))
    ax.plot(x, y, linewidth=0.75)
    _setup_ax(ax, "Wavelength (nm)", "Absorbance (a.u.)", "")
    fig.savefig(output_dir / "nature_uv-vis.png", dpi=150)
    fig.savefig(output_dir / "nature_uv-vis.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ uv-vis")


def generate_mem_switching(output_dir):
    """Memristor I-V switching curves."""
    fig, ax = plt.subplots()
    v = np.linspace(0, 3, 200)
    # LRS
    i_lrs = v * 2e-3 * (1 + 0.05 * np.sin(v * 5))
    # HRS
    i_hrs = v * 0.1e-3 * (1 + 0.08 * np.sin(v * 5))
    ax.semilogy(v, i_lrs * 1e3, label="LRS", linewidth=0.75)
    ax.semilogy(v, i_hrs * 1e3, label="HRS", linewidth=0.75)
    _setup_ax(ax, "Voltage (V)", "Current (mA)", "")
    ax.legend()
    fig.savefig(output_dir / "nature_mem-switching.png", dpi=150)
    fig.savefig(output_dir / "nature_mem-switching.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ mem-switching")


def generate_mem_endurance(output_dir):
    """Memristor endurance cycling."""
    fig, ax = plt.subplots()
    cycles = np.arange(1, 101)
    i_lrs = 2e-3 * (1 + 0.2 * np.random.randn(100))
    i_hrs = 0.05e-3 * (1 + 0.4 * np.random.randn(100))
    i_hrs[70:] *= 1.5  # degradation
    ax.plot(cycles, i_lrs * 1e3, "o", markersize=2, label="LRS", linewidth=0.5)
    ax.plot(cycles, i_hrs * 1e3, "s", markersize=2, label="HRS", linewidth=0.5)
    ax.set_yscale("log")
    _setup_ax(ax, "Cycle (#)", "Current (mA)", "")
    ax.legend()
    fig.savefig(output_dir / "nature_mem-endurance.png", dpi=150)
    fig.savefig(output_dir / "nature_mem-endurance.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ mem-endurance")


def generate_mem_retention(output_dir):
    """Memristor retention over time."""
    fig, ax = plt.subplots()
    t = np.logspace(0, 5, 50)
    i_lrs = 1e-3 * np.exp(-t / 1e6) * (1 + 0.05 * np.random.randn(50))
    i_hrs = 5e-5 * np.exp(t / 1e7) * (1 + 0.1 * np.random.randn(50))
    ax.plot(t, i_lrs * 1e3, "o-", markersize=3, label="LRS", linewidth=0.75)
    ax.plot(t, i_hrs * 1e3, "s-", markersize=3, label="HRS", linewidth=0.75)
    _setup_ax(ax, "Time (s)", "Current (mA)", "")
    ax.legend()
    fig.savefig(output_dir / "nature_mem-retention.png", dpi=150)
    fig.savefig(output_dir / "nature_mem-retention.pdf", dpi=600)
    plt.close(fig)
    print("  ✓ mem-retention")


GENERATORS = {
    "iv-sweep": generate_iv_sweep,
    "iv-breakdown": generate_iv_breakdown,
    "iv-leakage": generate_iv_leakage,
    "ec-cv": generate_ec_cv,
    "ec-ca": generate_ec_ca,
    "ec-eis": generate_ec_eis,
    "raman": generate_raman,
    "uv-vis": generate_uv_vis,
    "mem-switching": generate_mem_switching,
    "mem-endurance": generate_mem_endurance,
    "mem-retention": generate_mem_retention,
}


def main():
    parser = argparse.ArgumentParser(description="Generate Nature-themed preview plots")
    parser.add_argument(
        "--output", "-o",
        default="/Users/tai/workspace/projects/active_projects/test-project/plots",
        help="Output directory for plots",
    )
    parser.add_argument(
        "--techniques", "-t",
        default="",
        help="Comma-separated list of techniques (default: all)",
    )
    parser.add_argument(
        "--force-pdf", "-p",
        action="store_true",
        help="Also generate PDF versions",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Apply Nature theme globally
    apply_theme("publication-nature")

    # Select techniques
    if args.techniques:
        names = [s.strip() for s in args.techniques.split(",")]
    else:
        names = list(GENERATORS.keys())

    for name in names:
        fn = GENERATORS.get(name)
        if fn:
            fn(output_dir)
        else:
            print(f"  ? Unknown technique: {name}")

    print(f"\nAll plots saved to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
