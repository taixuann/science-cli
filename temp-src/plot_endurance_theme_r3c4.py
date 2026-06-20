#!/usr/bin/env python3
"""
Standalone endurance plot with publication-nature theme.
- Single axes: R_decay + LRS vs cycle (log-log). LRS spike at ~8377 masked out.
- Separate subfigure: ratio vs cycles (semilogy) to show degradation over time.

Output: data/results/endurance_R3-C4_volatile.pdf (.png)
        data/results/ratio_vs_cycles_R3-C4.pdf (.png)
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
INPUT_FILE = Path("/Users/tai/workspace/projects/active_projects/res_internship/data/results/endurance_Memristors endurance v2 [cu-c-.csv")
OUTPUT_DIR = Path("/Users/tai/workspace/projects/active_projects/res_internship/data/results")

# ── Theme ──────────────────────────────────────────────────────────────────
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
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.format": "pdf",
    "figure.figsize": [3.46, 2.75],
})

# ── Load ───────────────────────────────────────────────────────────────────
df = pd.read_csv(INPUT_FILE)
cycles = df["cycle"].values
r_hrs = df["r_hrs_ohm"].values
r_lrs = df["r_lrs_ohm"].values
ratio = df["ratio"].values

# ── Mask out LRS spike (~8377) for main endurance plot ─────────────────────
GAP_START = 8350
GAP_END = 8400
keep = ~((cycles > GAP_START) & (cycles < GAP_END))
c_plot = cycles[keep]
h_plot = r_hrs[keep]
l_plot = r_lrs[keep]
r_plot = ratio[keep]

# ====== FIGURE 1: Endurance (R_decay + LRS) ======
fig, ax = plt.subplots(figsize=(3.46, 2.75))

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Cycle")
ax.set_ylabel("Resistance (Ω)")
ax.set_xlim(0.9, c_plot.max() * 1.5)
y_min = min(l_plot.min(), h_plot.min()) * 0.8
y_max = max(l_plot.max(), h_plot.max()) * 1.3
ax.set_ylim(y_min, y_max)
ax.grid(True, which="both", alpha=0.25, linewidth=0.3)

ax.scatter(c_plot, h_plot, c="#2176AE", marker="o", s=16, alpha=0.7,
           linewidths=0.3, edgecolors="#2176AE", label="R_decay")
ax.scatter(c_plot, l_plot, c="#0055CC", marker="s", s=12, alpha=0.6,
           linewidths=0.3, edgecolors="#0055CC", label="LRS")

# Annotations at last data point
ax.annotate("R_decay", xy=(c_plot[-1], h_plot[-1]), xytext=(8, 8),
            textcoords="offset points", fontsize=6, fontweight="bold",
            color="#2176AE", ha="left", va="bottom",
            arrowprops=dict(arrowstyle="-", color="#2176AE", lw=0.3))
ax.annotate("LRS", xy=(c_plot[-1], l_plot[-1]), xytext=(8, -14),
            textcoords="offset points", fontsize=6, fontweight="bold",
            color="#0055CC", ha="left", va="bottom",
            arrowprops=dict(arrowstyle="-", color="#0055CC", lw=0.3))

ax.legend(loc="upper left", frameon=False)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
fig.savefig(OUTPUT_DIR / "endurance_R3-C4_volatile.pdf", bbox_inches="tight")
fig.savefig(OUTPUT_DIR / "endurance_R3-C4_volatile.png", bbox_inches="tight", dpi=300)
plt.close(fig)

# ====== FIGURE 2: Ratio vs Cycles ======
fig2, ax2 = plt.subplots(figsize=(3.46, 2.0))

ax2.set_xscale("log")
ax2.set_xlabel("Cycle")
ax2.set_ylabel("Ratio ($R_{\\mathrm{decay}} / R_{\\mathrm{LRS}}$)")
ax2.set_xlim(0.9, c_plot.max() * 1.5)
ax2.grid(True, which="both", alpha=0.25, linewidth=0.3)

# Plot ratio as scatter with connecting line
ax2.plot(c_plot, r_plot, c="#CC7700", linewidth=0.5, alpha=0.4)
ax2.scatter(c_plot, r_plot, c="#CC7700", marker="^", s=10, alpha=0.6,
            linewidths=0.3, edgecolors="#CC7700")

# Add a smoothed trend line (rolling median)
window_size = max(3, len(c_plot) // 100)
if window_size > 1:
    df_plot = pd.DataFrame({"cycle": c_plot, "ratio": r_plot}).sort_values("cycle")
    df_plot["ratio_smooth"] = df_plot["ratio"].rolling(window=window_size, center=True).median()
    ax2.plot(df_plot["cycle"], df_plot["ratio_smooth"], c="#CC7700", linewidth=0.8, alpha=0.9, label="Trend")

# Annotations at first and last
ax2.annotate(f"{r_plot[0]:.0f}", xy=(c_plot[0], r_plot[0]), xytext=(-30, 8),
             textcoords="offset points", fontsize=5.5, color="#CC7700", ha="right",
             arrowprops=dict(arrowstyle="-", color="#CC7700", lw=0.3))
ax2.annotate(f"{r_plot[-1]:.0f}", xy=(c_plot[-1], r_plot[-1]), xytext=(8, 8),
             textcoords="offset points", fontsize=5.5, color="#CC7700", ha="left",
             arrowprops=dict(arrowstyle="-", color="#CC7700", lw=0.3))

ax2.legend(frameon=False, fontsize=6, loc="upper left")

fig2.savefig(OUTPUT_DIR / "ratio_vs_cycles_R3-C4.pdf", bbox_inches="tight")
fig2.savefig(OUTPUT_DIR / "ratio_vs_cycles_R3-C4.png", bbox_inches="tight", dpi=300)
plt.close(fig2)

# ── Summary ──────────────────────────────────────────────────────────────
print(f"✅ Saved:")
print(f"   {OUTPUT_DIR / 'endurance_R3-C4_volatile.pdf'}")
print(f"   {OUTPUT_DIR / 'endurance_R3-C4_volatile.png'}")
print(f"   {OUTPUT_DIR / 'ratio_vs_cycles_R3-C4.pdf'}")
print(f"   {OUTPUT_DIR / 'ratio_vs_cycles_R3-C4.png'}")
print(f"   Data: {len(c_plot)} pts (removed {len(cycles) - len(c_plot)} spike)")
print(f"   Ratio: {r_plot[0]:.0f} → {r_plot[-1]:.0f} (start → end)")
