#!/usr/bin/env python3
"""Parse R5-C3 endurance CSV, apply publication-nature theme, plot log-x.

Usage: python3 temp-src/plot_endurance_r5c3.py

Uses science-cli's theme system (publication-nature):
  - open axes (no top/right spines), Helvetica, small fonts
  - HRS/LRS annotations inside the plot area (HRS below line, LRS above line)
  - No legends — only inline annotations
"""

import csv
import sys
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Bootstrap science-cli theme ──────────────────────────────────────
# Add src to path so we can import the theme system
SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC.parent))  # science-cli root
os.environ["SCIENCE_CLI_ROOT"] = str(SRC.parent)

from science_cli.theme import apply_theme

apply_theme("publication-nature")

# ── Paths ────────────────────────────────────────────────────────────
DATA_RAW = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship/data/raw"
    "/180626_cu-c-pda(q5)-ito(2)_r5-c3_pulse-endurance_2.csv"
)
RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship/protocol"
    "/2.5_cu-c-pda(n3,q4,q5)_ito(2)/5_pulse-endurance/results"
)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LABEL = "R5-C3"
SAMPLES_PER_CYCLE = 30

# Theme-aware colors
C_LRS = "#0055CC"    # blue
C_HRS = "#CC0000"    # red
C_RATIO = "#CC7700"   # amber


def parse_display_full(path: Path):
    """Extract DataValue rows from Display Full section."""
    rows = []
    in_raw = False
    with path.open("r") as f:
        for row in csv.reader(f):
            if not row:
                continue
            r0 = row[0].strip()
            if r0 == "DataName" and "raw_cycles" in ",".join(row):
                in_raw = True
                continue
            if in_raw and r0 == "DataValue":
                rows.append(row)
            elif in_raw and r0 != "DataValue":
                break
    return rows


def group_by_cycle(rows):
    from collections import defaultdict
    groups = defaultdict(list)
    for row in rows:
        try:
            c = int(float(row[1].strip()))
            groups[c].append(row)
        except (ValueError, IndexError):
            continue
    return dict(groups)


def process_cycle(cycle_num, rows):
    if len(rows) != SAMPLES_PER_CYCLE:
        return None
    lrs_rows = rows[:15]
    hrs_rows = rows[15:30]

    V_lrs = np.array([abs(float(r[2])) for r in lrs_rows])
    I_lrs = np.array([abs(float(r[3])) for r in lrs_rows])
    V_hrs = np.array([abs(float(r[2])) for r in hrs_rows])
    I_hrs = np.array([abs(float(r[3])) for r in hrs_rows])

    V_lrs = V_lrs[V_lrs > 0.01]
    I_lrs = I_lrs[I_lrs > 1e-12]
    V_hrs = V_hrs[V_hrs > 0.001]
    I_hrs = I_hrs[I_hrs > 1e-12]

    if len(V_lrs) < 3 or len(I_lrs) < 3 or len(V_hrs) < 3 or len(I_hrs) < 3:
        return None

    return {
        "cycle": cycle_num,
        "R_lrs_ohm": float(np.mean(V_lrs) / np.mean(I_lrs)),
        "R_hrs_ohm": float(np.mean(V_hrs) / np.mean(I_hrs)),
    }


def _save_formats(fig, path_stem: str):
    """Save both PNG (200 DPI) and PDF (600 DPI via theme)."""
    for ext, dpi in [(".png", 200), (".pdf", None)]:
        p = RESULTS_DIR / f"{path_stem}{ext}"
        kw = dict(bbox_inches="tight")
        if dpi:
            kw["dpi"] = dpi
        fig.savefig(p, **kw)
        print(f"  Saved: {p}")


def main():
    print(f"Reading: {DATA_RAW.name}")
    raw_rows = parse_display_full(DATA_RAW)
    print(f"  Display Full rows: {len(raw_rows)}")

    cycle_groups = group_by_cycle(raw_rows)
    print(f"  Unique cycles: {len(cycle_groups)}")

    results = []
    for cnum in sorted(cycle_groups.keys()):
        r = process_cycle(cnum, cycle_groups[cnum])
        if r:
            results.append(r)

    if not results:
        print("ERROR: No valid cycles!")
        return

    n = len(results)
    cycles = np.array([r["cycle"] for r in results])
    R_lrs = np.array([r["R_lrs_ohm"] for r in results])
    R_hrs = np.array([r["R_hrs_ohm"] for r in results])
    ratio = R_hrs / R_lrs

    print(f"  Valid cycles: {n} (range {cycles[0]} – {cycles[-1]})")
    print(f"  R_LRS: mean={np.mean(R_lrs)/1e3:.2f} kΩ")
    print(f"  R_HRS: mean={np.mean(R_hrs)/1e6:.3f} MΩ")
    print(f"  Ratio: mean={np.mean(ratio):.1f}×")

    # ── Save CSV ──────────────────────────────────────────────────────
    csv_path = RESULTS_DIR / f"endurance_{LABEL}.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cycle", "R_lrs_ohm", "R_hrs_ohm", "R_lrs_kohm", "R_hrs_kohm", "ratio"])
        for r in results:
            w.writerow([
                r["cycle"], f"{r['R_lrs_ohm']:.1f}", f"{r['R_hrs_ohm']:.1f}",
                f"{r['R_lrs_ohm']/1e3:.3f}", f"{r['R_hrs_ohm']/1e3:.3f}",
                f"{r['R_hrs_ohm']/r['R_lrs_ohm']:.1f}"
            ])
    print(f"  CSV: {csv_path}")

    # ── PLOT 1: Resistance vs Cycles (log-log) ───────────────────────
    # publication-nature figsize: 3.46" x 2.75" (single column)
    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    ax.loglog(cycles, R_lrs, "s", ms=4, color=C_LRS, alpha=0.8,
              markerfacecolor=C_LRS, markeredgecolor="none")
    ax.loglog(cycles, R_hrs, "o", ms=4, color=C_HRS, alpha=0.8,
              markerfacecolor=C_HRS, markeredgecolor="none")

    # Annotations INSIDE the plot area
    # HRS annotation: below the HRS line (text_y < last HRS value)
    # LRS annotation: above the LRS line (text_y > last LRS value)
    last_hrs = R_hrs[-1]
    last_lrs = R_lrs[-1]
    last_cyc = cycles[-1]

    # Compute offset as % of y-range for robustness
    y_range = np.log10(R_hrs.max()) - np.log10(R_lrs.min())
    offset = 10 ** (0.03 * y_range)  # ~7% in log space

    ax.annotate("HRS", xy=(last_cyc, last_hrs),
                xytext=(last_cyc * 1.1, last_hrs / offset),
                fontsize=7, color=C_HRS, fontweight="bold",
                va="top", ha="left")
    ax.annotate("LRS", xy=(last_cyc, last_lrs),
                xytext=(last_cyc * 1.1, last_lrs * offset),
                fontsize=7, color=C_LRS, fontweight="bold",
                va="bottom", ha="left")

    ax.set_xlabel("Cycle")
    ax.set_ylabel("Resistance (Ω)")
    ax.set_xlim(left=0.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    # publication-nature: no grid, open axes (top/right spines off by theme)

    fig.tight_layout()
    print("Plot 1: Resistance vs Cycles")
    _save_formats(fig, f"endurance_{LABEL}")
    plt.close(fig)

    # ── PLOT 2: Ratio vs Cycles (log-x, linear-y) ────────────────────
    fig2, ax2 = plt.subplots(figsize=(3.46, 2.75))

    ax2.semilogx(cycles, ratio, "^", ms=4, color=C_RATIO, alpha=0.8,
                 markerfacecolor=C_RATIO, markeredgecolor="none")

    last_ratio = ratio[-1]
    offset_lin = 0.05 * (ratio.max() - ratio.min())
    ax2.annotate("HRS/LRS", xy=(last_cyc, last_ratio),
                 xytext=(last_cyc * 1.1, last_ratio - offset_lin),
                 fontsize=7, color=C_RATIO, fontweight="bold",
                 va="top", ha="left")

    ax2.set_xlabel("Cycle")
    ax2.set_ylabel("HRS / LRS")
    ax2.set_xlim(left=0.8)
    ax2.set_xscale("log")

    fig2.tight_layout()
    print("Plot 2: Ratio vs Cycles")
    _save_formats(fig2, f"endurance_{LABEL}_ratio")
    plt.close(fig2)

    # ── PLOT 3: Combined 2-panel (R top, ratio bottom) ───────────────
    fig3, (ax_r, ax_rr) = plt.subplots(2, 1, figsize=(3.46, 4.5),
                                        sharex=True)

    ax_r.loglog(cycles, R_lrs, "s", ms=3, color=C_LRS, alpha=0.8,
                markerfacecolor=C_LRS, markeredgecolor="none")
    ax_r.loglog(cycles, R_hrs, "o", ms=3, color=C_HRS, alpha=0.8,
                markerfacecolor=C_HRS, markeredgecolor="none")
    ax_r.annotate("LRS", xy=(last_cyc, last_lrs),
                  xytext=(last_cyc * 1.15, last_lrs * offset),
                  fontsize=6, color=C_LRS, fontweight="bold",
                  va="bottom", ha="left")
    ax_r.annotate("HRS", xy=(last_cyc, last_hrs),
                  xytext=(last_cyc * 1.15, last_hrs / offset),
                  fontsize=6, color=C_HRS, fontweight="bold",
                  va="top", ha="left")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_yscale("log")

    ax_rr.semilogx(cycles, ratio, "^", ms=3, color=C_RATIO, alpha=0.8,
                   markerfacecolor=C_RATIO, markeredgecolor="none")
    ax_rr.annotate("Ratio", xy=(last_cyc, last_ratio),
                   xytext=(last_cyc * 1.15, last_ratio - offset_lin),
                   fontsize=6, color=C_RATIO, fontweight="bold",
                   va="top", ha="left")
    ax_rr.set_xlabel("Cycle")
    ax_rr.set_ylabel("HRS / LRS")
    ax_rr.set_xlim(left=0.8)

    fig3.tight_layout()
    print("Plot 3: Combined 2-panel")
    _save_formats(fig3, f"endurance_{LABEL}_combined")
    plt.close(fig3)

    print("\nDone! All plots in:", RESULTS_DIR)


if __name__ == "__main__":
    main()
