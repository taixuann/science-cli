"""Temp script: plot endurance R_high / R_low for volatile memristor.

Handles two Keysight B1500A export formats:
  Format A (7-col): raw_cycles, raw_ch2, target_meas, ... (R3-C3 style)
  Format B (4-col): raw_cycles, raw_ch1, raw_ch2 (R5-C3 style)
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RAW_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
)
RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
    "/protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/5_pulse-endurance/results"
)
V_THRESHOLD = 1.0
V_READ_HRS = 0.3
V_READ_LRS = 1.75


def parse_keysight_csv(path: Path):
    raw = []
    with path.open() as f:
        for row in csv.reader(f):
            if row and row[0] == "DataValue":
                raw.append(row)
    return raw


def try_float(s):
    s = s.strip()
    return float(s) if s else float("nan")


def compute_per_cycle_resistance(rows: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ncols = len(rows[0]) if rows else 0

    cycles_map: dict[int, dict[str, list[float]]] = {}

    for row in rows:
        cyc_s = row[1].strip()
        if not cyc_s:
            continue
        try:
            cyc = int(float(cyc_s))
        except ValueError:
            continue
        if cyc < 1:
            continue

        if ncols >= 7:
            col2 = try_float(row[2])  # raw_ch2 (current for later cycles)
            col3 = try_float(row[3])  # target_meas (current for early cycles)
            currents = []
            for v in [col2, col3]:
                if not np.isnan(v) and v != 0.0:
                    currents.append(v)
            if not currents:
                continue
            for cur in currents:
                if cur == 0.0 or np.isnan(cur):
                    continue
                if cyc not in cycles_map:
                    cycles_map[cyc] = {"hrs": [], "lrs": []}
                abs_i = abs(cur)
                r = (V_READ_LRS / abs_i) if abs_i > 1e-10 else float("nan")
                # Classify: large current = LRS (ON), small current = HRS (OFF)
                if abs_i > 1e-5:
                    cycles_map[cyc]["lrs"].append(r)
                else:
                    cycles_map[cyc]["hrs"].append(r)
        else:
            col2 = try_float(row[2])  # raw_ch1 (voltage)
            col3 = try_float(row[3])  # raw_ch2 (current)
            if np.isnan(col2) or np.isnan(col3):
                continue
            if col3 == 0.0:
                continue
            r = abs(col2 / col3) if abs(col3) > 1e-15 else float("nan")
            if np.isnan(r):
                continue
            if cyc not in cycles_map:
                cycles_map[cyc] = {"hrs": [], "lrs": []}
            key = "lrs" if col2 > V_THRESHOLD else "hrs"
            cycles_map[cyc][key].append(r)

    cycles = sorted(cycles_map.keys())
    hrs_arr = np.full(len(cycles), np.nan)
    lrs_arr = np.full(len(cycles), np.nan)
    for i, cyc in enumerate(cycles):
        d = cycles_map[cyc]
        if d["hrs"]:
            hrs_arr[i] = np.mean([v for v in d["hrs"] if not np.isnan(v)])
        if d["lrs"]:
            lrs_arr[i] = np.mean([v for v in d["lrs"] if not np.isnan(v)])
    return np.array(cycles, dtype=float), hrs_arr, lrs_arr


def plot_endurance(cycles, hrs, lrs, stem: Path, device_label: str = "R3-C3"):
    ratio = hrs / lrs

    fig, (ax_r, ax_ratio) = plt.subplots(2, 1, figsize=(6.0, 5.5), sharex=True)

    ax_r.plot(cycles, hrs, "o", markersize=5, color="#CC0000", alpha=0.85, label="_nolegend_")
    ax_r.plot(cycles, lrs, "s", markersize=5, color="#0055CC", alpha=0.85, label="_nolegend_")
    ax_r.annotate(
        "HRS", xy=(cycles[-1], hrs[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#CC0000", fontweight="bold",
        va="center",
    )
    ax_r.annotate(
        "LRS", xy=(cycles[-1], lrs[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#0055CC", fontweight="bold",
        va="center",
    )
    ax_r.set_yscale("log")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_title(f"Volatile Memristor — Endurance ({device_label})")
    ax_r.grid(True, alpha=0.25)

    ax_ratio.plot(cycles, ratio, "^", markersize=5, color="#994400", alpha=0.85, label="_nolegend_")
    ax_ratio.annotate(
        "HRS/LRS", xy=(cycles[-1], ratio[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#994400", fontweight="bold",
        va="center",
    )
    ax_ratio.set_xscale("log")
    ax_ratio.set_yscale("log")
    ax_ratio.set_xlabel("Cycle")
    ax_ratio.set_ylabel("HRS / LRS")
    ax_ratio.grid(True, alpha=0.25)

    fig.tight_layout()
    stem.parent.mkdir(parents=True, exist_ok=True)
    for ext, dpi_val in [(".pdf", 300), (".png", 200)]:
        p = stem.with_suffix(ext)
        fig.savefig(p, dpi=dpi_val, bbox_inches="tight")
        print(f"  ✓ Saved: {p}")
    plt.close(fig)


def main():
    args = sys.argv[1:]
    if args:
        raw_path = Path(args[0])
    else:
        raw_path = RAW_DIR / "data" / ("Memristors endurance [cu-c-pda(q5)-ito(2)"
                                       "_r3-c3(1) ; 2026-06-19 18_59_18].csv")

    print(f"File: {raw_path.name}")
    print("Parsing CSV ...")
    rows = parse_keysight_csv(raw_path)
    print(f"  Total DataValue rows: {len(rows)}")
    print(f"  Columns per row: {len(rows[0]) if rows else 0}")

    print("Computing per-cycle resistance (skipping 0/NaN) ...")
    cycles, hrs, lrs = compute_per_cycle_resistance(rows)
    valid = ~np.isnan(hrs) & ~np.isnan(lrs)
    print(f"  Valid cycles: {np.sum(valid)} / {len(cycles)}")
    if np.any(valid):
        print(f"  HRS range: {np.nanmin(hrs):.1f} – {np.nanmax(hrs):.1f} Ω")
        print(f"  LRS range: {np.nanmin(lrs):.1f} – {np.nanmax(lrs):.1f} Ω")

    print("Plotting ...")
    safe_stem = "".join(c for c in raw_path.stem if c.isalnum() or c in "_-")[:30]
    stem = RESULTS_DIR / f"endurance_hrs_lrs_{safe_stem}"
    device_label = "R3-C3" if "r3-c3" in raw_path.name.lower() else "R5-C3"
    plot_endurance(cycles, hrs, lrs, stem, device_label=device_label)


if __name__ == "__main__":
    main()
