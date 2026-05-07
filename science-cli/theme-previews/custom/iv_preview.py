"""Voltage vs Time and I-V preview — bipolar resistive switching.
V(t) shows sweep direction with numbered segments. I(V) is clean, no annotations.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).resolve().parent / "iv-directional-preview.png"
N = 120


def _bipolar(seed=42):
    rng = np.random.default_rng(seed)
    V = np.concatenate([np.linspace(0, 2, N), np.linspace(2, 0, N),
                        np.linspace(0, -2, N), np.linspace(-2, 0, N)])
    I = np.empty(4 * N)
    for i in range(4):
        s, e = i * N, (i + 1) * N
        sv = V[s:e]
        if i == 0:
            r = np.where(np.abs(sv) < 1.5, 5e4, 1e3)
            I[s:e] = sv / r
        elif i == 1:
            I[s:e] = sv / 1e3
        elif i == 2:
            r = np.where(np.abs(sv) < 1.5, 1e3, 5e4)
            I[s:e] = sv / r
        else:
            I[s:e] = sv / 5e4
        I[s:e] += rng.normal(0, 0.03 * max(abs(I[s:e])), e - s)
    t = np.arange(4 * N) * 0.01
    return t, V, I


def main():
    COLORS = ["#0072B2", "#009E73", "#D55E00", "#E69F00"]
    matplotlib.rcdefaults()
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 8,
        "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.linewidth": 0.8, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.direction": "in", "ytick.direction": "in",
    })

    t, V, I = _bipolar()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5, 5))

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for i in range(4):
        s, e = i * N, (i + 1) * N
        ax1.plot(t[s:e], V[s:e], color=COLORS[i], lw=1.5)
        mid = (s + e) // 2
        ax1.annotate(str(i + 1), (t[mid], V[mid]), fontsize=8, color=COLORS[i],
                     ha="center", va="center", fontweight="bold",
                     bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec=COLORS[i], lw=0.8))
    ax1.set_ylabel("Voltage (V)")

    ax2.plot(V, I, color="black", lw=1.2)
    ax2.set_xlabel("Voltage (V)")
    ax2.set_ylabel("Current (A)")

    fig.tight_layout(pad=0.3)
    fig.savefig(OUT, dpi=400, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
