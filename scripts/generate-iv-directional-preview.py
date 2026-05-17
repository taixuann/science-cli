#!/usr/bin/env python3
"""Generate a publication-quality bipolar resistive switching IV preview.

Produces an 8-shaped pinched hysteresis loop with:
  - Four color-coded sweep segments with directional arrows
  - Circled number annotations (1–4) at each segment midpoint
  - ACS theme styling (Helvetica 8pt, tight layout)
  - High-resolution PNG output with bbox_inches='tight'

Output: theme-previews/custom/iv-directional-preview.png

Run:
  cd /Users/tai/workspace/tools/science-cli && \
    python scripts/generate-iv-directional-preview.py
"""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from matplotlib.font_manager import FontProperties

# ── Output path ──────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "theme-previews" / "custom" / "iv-directional-preview.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── ACS theme settings (mirrors publication-acs.yaml) ────────
# We apply these directly so the script is self-contained.
ACS_COLORS = [
    "#0072B2",   # dark blue   → Seg 1 (0 → +Vmax)
    "#009E73",   # green       → Seg 2 (+Vmax → 0)
    "#D55E00",   # red         → Seg 3 (0 → -Vmax)
    "#E69F00",   # orange      → Seg 4 (-Vmax → 0)
]

theme = {
    "figure.facecolor": "white",
    "figure.figsize": (3.35, 2.6),   # ACS single-column width
    "figure.dpi": 300,
    "axes.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.labelcolor": "black",
    "axes.titlecolor": "black",
    "axes.grid": False,
    "axes.linewidth": 0.8,
    "axes.spines.top": True,
    "axes.spines.right": True,
    "xtick.color": "black",
    "ytick.color": "black",
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "font.family": "sans-serif",
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "lines.linewidth": 1.0,
    "lines.markersize": 4,
    "legend.frameon": False,
    "legend.loc": "best",
    "legend.fontsize": 7,
    "legend.fancybox": False,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
}

for k, v in theme.items():
    matplotlib.rcParams[k] = v


# ── Synthetic data: pinched hysteresis (8-shaped memristor) ──

def _sigmoid(x, center=0.0, width=0.1):
    """Smooth step from 0 to 1."""
    return 1.0 / (1.0 + np.exp(-(x - center) / width))


def generate_memristor_iv(
    V_max: float = 2.0,
    n_pts: int = 200,
    R_hrs: float = 50e3,      # High-resistance state (Ω)
    R_lrs: float = 2e3,        # Low-resistance state (Ω)
    V_set: float = 0.85,       # SET threshold (positive)
    V_reset: float = -0.65,    # RESET threshold (negative)
    switch_width: float = 0.06,
    seed: int = 42,
) -> tuple:
    """Generate a realistic bipolar resistive switching IV curve.

    Returns four arrays: (V1,I1), (V2,I2), (V3,I3), (V4,I4)
    corresponding to the four sweep segments.

    Sweep sequence:
      Seg 1: 0 → +V_max  (forward,  HRS → SET → LRS)
      Seg 2: +V_max → 0  (backward, LRS)
      Seg 3: 0 → -V_max  (forward,  LRS → RESET → HRS)
      Seg 4: -V_max → 0  (backward, HRS)
    """
    rng = np.random.default_rng(seed)
    noise = 1e-7  # small current noise

    # ── Segment 1: 0 → +V_max ─────────────────────────────────
    V1 = np.linspace(0, V_max, n_pts)
    # Before SET: HRS with slight nonlinearity (Schottky-like turn-on)
    I_hrs = V1 / R_hrs + 2e-6 * (np.exp(V1 / 0.15) - 1)
    # After SET: LRS
    I_lrs = V1 / R_lrs
    # Smooth transition via sigmoid at V_set
    w_set = _sigmoid(V1, V_set, switch_width)
    I1 = (1 - w_set) * I_hrs + w_set * I_lrs
    I1 += rng.normal(0, noise, n_pts)

    # ── Segment 2: +V_max → 0 ────────────────────────────────
    V2 = np.linspace(V_max, 0, n_pts)
    # Stays in LRS on the way down
    I2 = V2 / R_lrs
    I2 += rng.normal(0, noise, n_pts)

    # ── Segment 3: 0 → -V_max ────────────────────────────────
    V3 = np.linspace(0, -V_max, n_pts)
    # Before RESET: LRS
    I_lrs_neg = V3 / R_lrs
    # After RESET: HRS
    I_hrs_neg = V3 / R_hrs - 1.5e-6 * (np.exp(abs(V3) / 0.15) - 1)
    # Smooth transition: RESET at V_reset (negative), so use abs for sigmoid
    w_reset = _sigmoid(abs(V3), abs(V_reset), switch_width)
    I3 = (1 - w_reset) * I_lrs_neg + w_reset * I_hrs_neg
    I3 += rng.normal(0, noise, n_pts)

    # ── Segment 4: -V_max → 0 ────────────────────────────────
    V4 = np.linspace(-V_max, 0, n_pts)
    # Stays in HRS on the way back up to origin
    I4 = V4 / R_hrs + 2e-6 * (np.exp(abs(V4) / 0.15) - 1) * np.sign(V4)
    I4 += rng.normal(0, noise, n_pts)

    return (V1, I1), (V2, I2), (V3, I3), (V4, I4)


# ── Arrow placement ──────────────────────────────────────────

def _arrow_at_midpoint(ax, V, I, color: str, seg_num: int):
    """Place a directional arrow + circled number at curve midpoint.

    The arrow is offset perpendicular to the curve path so it does not
    overlay the line. The circle-annotation sits at the midpoint of
    the shifted arrow.
    """
    n = len(V)
    if n < 8:
        return

    # Use points near the middle third of the segment for direction and placement
    i0 = int(n * 0.43)
    i1 = int(n * 0.57)
    if i1 - i0 < 4:
        i0 = max(0, n // 2 - 6)
        i1 = min(n - 1, n // 2 + 6)

    # Midpoint in data space
    mid_idx = int(0.5 * (i0 + i1))
    x_mid = V[mid_idx]
    y_mid = I[mid_idx]

    # Direction vector (tail → head) in data space, using nearby points
    tail_d = np.array([V[i0], I[i0]])
    head_d = np.array([V[i1], I[i1]])
    d_vec = head_d - tail_d
    d_len = np.hypot(d_vec[0], d_vec[1])
    if d_len < 1e-12:
        return
    d_unit = d_vec / d_len

    # Perpendicular unit vector (rotate 90° CCW for "above" the curve)
    perp = np.array([-d_unit[1], d_unit[0]])

    # Offset distance in data-space — scale inversely with data range
    x_range = max(abs(V.max() - V.min()), 0.1)
    y_range = max(abs(I.max() - I.min()), 1e-9)
    # Use a fraction of the total range for the offset
    offset_data = 0.06 * min(x_range, y_range)

    # Build an arrow 0.35× the segment length
    arrow_frac = 0.30
    arr_tail = np.array([V[i0], I[i0]]) + perp * offset_data
    arr_head = np.array([V[i1], I[i1]]) + perp * offset_data

    ax.annotate(
        "", xy=arr_head, xytext=arr_tail,
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=1.2,
            mutation_scale=12,
            shrinkA=0,
            shrinkB=0,
        ),
        zorder=5,
    )

    # Circled number at arrow midpoint
    arr_mid = 0.5 * (arr_tail + arr_head)
    ax.text(
        arr_mid[0], arr_mid[1], str(seg_num),
        fontsize=7, fontweight="bold", color=color,
        ha="center", va="center", zorder=6,
        bbox=dict(
            boxstyle="circle,pad=0.15",
            fc="white",
            ec=color,
            lw=1.0,
        ),
    )


# ── Main plot ────────────────────────────────────────────────

def main():
    # Generate data
    (V1, I1), (V2, I2), (V3, I3), (V4, I4) = generate_memristor_iv(
        V_max=2.0, n_pts=200, R_hrs=50e3, R_lrs=2e3,
        V_set=0.85, V_reset=-0.65, seed=123,
    )

    # Convert to µA for nicer display
    scale = 1e6
    I1, I2, I3, I4 = [arr * scale for arr in (I1, I2, I3, I4)]

    # Labels for segments
    seg_labels = ["① 0→+V", "② +V→0", "③ 0→−V", "④ −V→0"]

    fig, ax = plt.subplots()

    # Plot all four segments
    segments = [
        (V1, I1, ACS_COLORS[0], 1, "SET (HRS→LRS)"),
        (V2, I2, ACS_COLORS[1], 2, "LRS return"),
        (V3, I3, ACS_COLORS[2], 3, "RESET (LRS→HRS)"),
        (V4, I4, ACS_COLORS[3], 4, "HRS return"),
    ]

    for V, I, color, num, label in segments:
        ax.plot(V, I, color=color, linewidth=1.2, zorder=2, label=label)
        _arrow_at_midpoint(ax, V, I, color, num)

    # Axis labels
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (µA)")
    ax.set_title("Bipolar Resistive Switching")

    # Origin-crossing marker (small dot at origin to emphasize pinched point)
    ax.plot(0, 0, "ko", markersize=2, zorder=4)

    # Horizontal and vertical zero lines (subtle)
    ax.axhline(y=0, color="gray", linewidth=0.4, linestyle="-", alpha=0.5, zorder=1)
    ax.axvline(x=0, color="gray", linewidth=0.4, linestyle="-", alpha=0.5, zorder=1)

    # Legend — compact, bottom-right
    ax.legend(
        fontsize=6, loc="lower right", frameon=False,
        ncol=1, columnspacing=0.5, handlelength=1.2,
        borderaxespad=0.3, borderpad=0.2,
    )

    # Tight axis limits — add small padding
    ax.set_xlim(-2.2, 2.2)
    ylim_max = max(abs(I1).max(), abs(I2).max(), abs(I3).max(), abs(I4).max())
    ax.set_ylim(-ylim_max * 1.15, ylim_max * 1.15)

    # Remove top/right spines for cleaner look (override ACS default)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Save with tight bounding box
    fig.savefig(
        OUT,
        dpi=600,
        bbox_inches="tight",
        pad_inches=0.03,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    plt.close(fig)

    print(f"✓ Saved: {OUT}")
    print(f"  Size:  {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
