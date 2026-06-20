"""Extract endurance data, map timestamps to log-spaced cycles, save CSV + plot."""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
    "/protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/5_pulse-endurance/results"
)
BASE_CYCLE = 9000
MAX_CYCLE = 1007114
STEP_LOG = 95


def parse_sections(path):
    sections = []
    with path.open() as f:
        reader = csv.reader(f)
        cur = {"ts": None, "dv": []}
        in_sec = False
        for i, row in enumerate(reader):
            if not row:
                continue
            if 'Setup.Title' in str(row) and 'Measurement Result' in str(row):
                if in_sec:
                    sections.append(cur)
                cur = {"lineno": i + 1, "ts": None, "dv": []}
                in_sec = True
                continue
            if in_sec:
                if 'RecordTime' in str(row):
                    cur["ts"] = row[-1].strip()
                elif row[0] == "DataValue":
                    cur["dv"].append(row)
        if in_sec:
            sections.append(cur)
    return sections


def compute_r(section):
    dv = section["dv"]
    if len(dv) < 2:
        return None, None
    try:
        v1, i1 = float(dv[0][2]), float(dv[0][3])
        v2, i2 = float(dv[1][2]), float(dv[1][3])
    except (ValueError, IndexError):
        return None, None
    if abs(v1) < 0.01 or abs(v2) < 0.01 or abs(i1) < 1e-12 or abs(i2) < 1e-12:
        return None, None
    r1 = abs(v1 / i1)
    r2 = abs(v2 / i2)
    if r1 < r2:
        return r1, r2  # lrs, hrs
    else:
        return r2, r1


def main():
    args = sys.argv[1:]
    path = Path(args[0]) if args else Path(
        "/Users/tai/workspace/projects/active_projects/res_internship"
        "/data/Memristors endurance [cu-c-pda(q5)-ito(2)_r3-c3(1) ; 2026-06-19 18_59_18].csv"
    )
    label = "R3-C3"

    print(f"File: {path.name}")
    sections = parse_sections(path)
    print(f"Sections: {len(sections)}")

    # Filter: valid timestamp + data
    good = []
    for sec in sections:
        if not sec["ts"]:
            continue
        try:
            t = datetime.strptime(sec["ts"], "%m/%d/%Y %H:%M:%S")
        except ValueError:
            continue
        lrs, hrs = compute_r(sec)
        if lrs is None:
            continue
        good.append((t, lrs, hrs))

    # Sort chronologically (earliest → latest)
    good.sort(key=lambda x: x[0])
    print(f"With data: {len(good)}")
    print(f"Time: {good[0][0]} → {good[-1][0]}")
    dur_s = (good[-1][0] - good[0][0]).total_seconds()
    print(f"Duration: {dur_s:.0f}s = {dur_s/60:.1f}min")

    # Map each timestamp → cycle using log formula
    # Total log-steps from C9000 to C1007114:
    # n_total = STEP_LOG × log10(MAX_CYCLE / BASE_CYCLE)
    n_total = STEP_LOG * np.log10(MAX_CYCLE / BASE_CYCLE)
    print(f"Total log-steps: {n_total:.1f} (expect ~{len(good)} sections)")

    # Group sections by timestamp proximity (within 5s = same cycle)
    groups = []
    current = [good[0]]
    for item in good[1:]:
        if (item[0] - current[-1][0]).total_seconds() < 5:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    groups.append(current)
    print(f"Grouped into {len(groups)} cycles ({sum(len(g) for g in groups)} sections)")

    # Map each group to a log-spaced cycle index
    # Each group = 1 endurance cycle, with n_groups total spread across n_total log-steps
    t0 = groups[0][0][0]
    total_s = (groups[-1][-1][0] - t0).total_seconds()

    extracted = []
    for i, group in enumerate(groups):
        # Average HRS/LRS within group
        lrs_avg = np.mean([g[1] for g in group])
        hrs_avg = np.mean([g[2] for g in group])
        t_mid = group[len(group)//2][0]

        # Cycle from position within the log-spaced sequence
        elapsed = (t_mid - t0).total_seconds()
        frac = elapsed / total_s if total_s > 0 else 0
        n = frac * n_total
        if i == 0:
            n = 0
        elif i == len(groups) - 1:
            n = n_total
        cycle = BASE_CYCLE * (10 ** (n / STEP_LOG))
        extracted.append((cycle, t_mid, hrs_avg, lrs_avg))

    cycles = np.array([e[0] for e in extracted])
    hrs_arr = np.array([e[2] for e in extracted])
    lrs_arr = np.array([e[3] for e in extracted])
    ratio = hrs_arr / lrs_arr

    # Save CSV
    csv_path = RESULTS_DIR / f"endurance_data_{label}.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cycle", "timestamp", "hrs_ohm", "lrs_ohm", "ratio"])
        for cyc, t, h, l in extracted:
            w.writerow([f"{cyc:.0f}", t.isoformat(), f"{h:.1f}", f"{l:.1f}", f"{h/l:.1f}"])
    print(f"\nSaved: {csv_path}")

    # Summary stats
    print(f"\nExtracted: {len(extracted)} cycles")
    print(f"  Cycle: {cycles[0]:.0f} → {cycles[-1]:.0f}")
    print(f"  HRS:   {np.min(hrs_arr):.0f} – {np.max(hrs_arr):.0f} Ω  (mean={np.mean(hrs_arr):.0f})")
    print(f"  LRS:   {np.min(lrs_arr):.0f} – {np.max(lrs_arr):.0f} Ω  (mean={np.mean(lrs_arr):.0f})")
    print(f"  Ratio: {np.min(ratio):.1f} – {np.max(ratio):.1f}")

    # Plot
    fig, (ax_r, ax_ratio) = plt.subplots(2, 1, figsize=(6.5, 5.5), sharex=True)

    ax_r.plot(cycles, hrs_arr, "o", markersize=5, color="#CC0000", alpha=0.7, label="_nolegend_")
    ax_r.plot(cycles, lrs_arr, "s", markersize=5, color="#0055CC", alpha=0.7, label="_nolegend_")
    ax_r.annotate("HRS", xy=(cycles[-1], hrs_arr[-1]), xytext=(5, 0),
                  textcoords="offset points", fontsize=11, color="#CC0000",
                  fontweight="bold", va="center")
    ax_r.annotate("LRS", xy=(cycles[-1], lrs_arr[-1]), xytext=(5, 0),
                  textcoords="offset points", fontsize=11, color="#0055CC",
                  fontweight="bold", va="center")
    ax_r.set_xscale("log")
    ax_r.set_xlim(8000, 2e6)
    ax_r.xaxis.set_major_locator(plt.LogLocator(base=10, numticks=4))
    ax_r.xaxis.set_minor_locator(plt.NullLocator())
    ax_r.set_yscale("log")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_title(f"Volatile Memristor — Endurance ({label})")
    ax_r.grid(True, alpha=0.25)

    ax_ratio.plot(cycles, ratio, "^", markersize=5, color="#994400", alpha=0.7, label="_nolegend_")
    ax_ratio.annotate("HRS/LRS", xy=(cycles[-1], ratio[-1]), xytext=(5, 0),
                      textcoords="offset points", fontsize=11, color="#994400",
                      fontweight="bold", va="center")
    ax_ratio.set_xscale("log")
    ax_ratio.set_xlim(8000, 2e6)
    ax_ratio.xaxis.set_major_locator(plt.LogLocator(base=10, numticks=4))
    ax_ratio.xaxis.set_minor_locator(plt.NullLocator())
    ax_ratio.set_xlabel("Cycle")
    ax_ratio.set_ylabel("HRS / LRS")
    ax_ratio.grid(True, alpha=0.25)

    fig.tight_layout()
    plot_path = RESULTS_DIR / f"endurance_timestamp_{label}"
    for ext, dpi_val in [(".pdf", 300), (".png", 200)]:
        p = plot_path.with_suffix(ext)
        fig.savefig(p, dpi=dpi_val, bbox_inches="tight")
        print(f"Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
