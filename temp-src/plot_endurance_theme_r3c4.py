#!/usr/bin/env python3
"""
Standalone endurance plot with publication-nature theme.
Reads pre-cleaned CSV → styled endurance plot for volatile memristor.

Input:  data/results/endurance_Memristors endurance v2 [cu-c-.csv
Output: data/results/endurance_R3-C4_volatile.pdf  (and .png)
"""

import matplotlib
matplotlib.use("Agg")  # no display needed

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
INPUT_FILE = Path("/Users/tai/workspace/projects/active_projects/res_internship/data/results/endurance_Memristors endurance v2 [cu-c-.csv")
OUTPUT_DIR = Path("/Users/tai/workspace/projects/active_projects/res_internship/data/results")

# ── Apply publication-nature theme ─────────────────────────────────────────
# (Nature journals: 88mm single-column, Helvetica 7pt, open axes, 300 DPI)
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica"],
    "font.size": 7,
    "axes.linewidth": 0.5,
    "axes.labelsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "legend.frameon": False,
    "lines.linewidth": 1.0,
    "lines.markersize": 4,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.format": "pdf",
    "figure.figsize": [3.46, 2.75],  # Nature single-column (88mm)
})

# ── Load data ──────────────────────────────────────────────────────────────
df = pd.read_csv(INPUT_FILE)
cycles = df["cycle"].values
r_hrs = df["r_hrs_ohm"].values
r_lrs = df["r_lrs_ohm"].values
ratio = df["ratio"].values

# ── Create figure ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(3.46, 2.75))

# Log-log axes
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Cycle")
ax.set_ylabel("Resistance (Ω)")
ax.set_xlim(0.9, cycles.max() * 1.5)
ax.set_ylim(1e3, 1e7)

# Grid (subtle)
ax.grid(True, which="both", alpha=0.25, linewidth=0.3)

# ── Plot series (volatile-memristor colors) ───────────────────────────────
# R_decay (HRS-like) in #2176AE (volatile blue)
ax.scatter(cycles, r_hrs, c="#2176AE", marker="o", s=16, alpha=0.7,
           linewidths=0.3, edgecolors="#2176AE", label="R_decay")

# LRS in #0055CC (dark blue, smaller)
ax.scatter(cycles, r_lrs, c="#0055CC", marker="s", s=12, alpha=0.6,
           linewidths=0.3, edgecolors="#0055CC", label="LRS")

# Ratio in #CC7700 (amber)
ax.scatter(cycles, ratio, c="#CC7700", marker="^", s=12, alpha=0.6,
           linewidths=0.3, edgecolors="#CC7700", label="Ratio")

# ── Annotations (inside plot area, positioned at last data point) ─────────
def annotate_last(ax, x, y, text, color, xytext_offset=(0, 15)):
    """Place annotation near the last data point."""
    ax.annotate(
        text,
        xy=(x[-1], y[-1]),
        xytext=xytext_offset,
        textcoords="offset points",
        fontsize=6,
        fontweight="bold",
        color=color,
        ha="left",
        va="bottom",
        arrowprops=dict(arrowstyle="-", color=color, lw=0.3),
    )

annotate_last(ax, cycles, r_hrs, "R_decay", "#2176AE", xytext_offset=(8, 8))
annotate_last(ax, cycles, r_lrs, "LRS", "#0055CC", xytext_offset=(8, -12))
annotate_last(ax, cycles, ratio, "Ratio", "#CC7700", xytext_offset=(8, 8))

# ── Legend ─────────────────────────────────────────────────────────────────
ax.legend(loc="upper left", frameon=False)

# ── Save ───────────────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

fig.savefig(OUTPUT_DIR / "endurance_R3-C4_volatile.pdf", bbox_inches="tight")
fig.savefig(OUTPUT_DIR / "endurance_R3-C4_volatile.png", bbox_inches="tight", dpi=300)
plt.close(fig)

print(f"✅ Saved: {OUTPUT_DIR}/endurance_R3-C4_volatile.pdf")
print(f"✅ Saved: {OUTPUT_DIR}/endurance_R3-C4_volatile.png")
print(f"   Data: {len(cycles)} cycles")
print(f"   HRS range: {r_hrs.min():.2e} – {r_hrs.max():.2e} Ω")
print(f"   LRS range: {r_lrs.min():.2e} – {r_lrs.max():.2e} Ω")
print(f"   Ratio range: {ratio.min():.1f} – {ratio.max():.1f}")
