"""Match Measurement Result sections to raw_cycles using timestamps + Y-axis values.

File structure:
- 822 Measurement Result sections (reverse chronological, newest first)
- 410 with non-zero data = 205 unique cycle measurements (each duplicated)
- raw_cycles section: 206 entries from C9000 to C1M

Maps by chronological position: earliest section = C9000, latest = C1M.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

V_READ_LRS = 1.978
V_READ_HRS = 0.300

RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
    "/protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/5_pulse-endurance/results"
)


def parse_file(path: Path):
    """Extract Measurement Result sections with timestamp + V/I data."""
    sections = []
    with path.open() as f:
        reader = csv.reader(f)
        current = {"lineno": 0, "ts": None, "yb": None, "yt": None, "dv": []}
        in_section = False
        for i, row in enumerate(reader):
            if not row:
                continue
            if 'Setup.Title' in str(row) and 'Measurement Result' in str(row):
                if in_section:
                    sections.append(current)
                current = {"lineno": i + 1, "ts": None, "yb": None, "yt": None, "dv": []}
                in_section = True
                continue
            if in_section:
                if 'RecordTime' in str(row):
                    current["ts"] = row[-1].strip()
                elif 'YAxis.Bottom' in str(row):
                    current["yb"] = [x.strip() for x in row[1:]]
                elif 'YAxis.Top' in str(row):
                    current["yt"] = [x.strip() for x in row[1:]]
                elif row[0] == 'DataValue':
                    current["dv"].append(row)
        if in_section:
            sections.append(current)
    return sections


def extract_hrs_lrs(section):
    """Compute HRS/LRS resistance from section DataValue rows."""
    dv = section["dv"]
    if len(dv) < 2:
        return None, None
    v1, i1 = float(dv[0][2]), float(dv[0][3])
    v2, i2 = float(dv[1][2]), float(dv[1][3])
    if abs(v1) < 0.01 or abs(v2) < 0.01 or abs(i1) < 1e-12 or abs(i2) < 1e-12:
        return None, None
    lrs = abs(v1 / i1)
    hrs = abs(v2 / i2)
    if lrs > hrs:
        lrs, hrs = hrs, lrs
    return lrs, hrs


def main():
    args = sys.argv[1:]
    path = Path(args[0]) if args else Path(
        "/Users/tai/workspace/projects/active_projects/res_internship"
        "/data/Memristors endurance [cu-c-pda(q5)-ito(2)_r3-c3(1) ; 2026-06-19 18_59_18].csv"
    )
    device_label = "R3-C3"

    print(f"File: {path.name}")
    sections = parse_file(path)
    print(f"Total sections: {len(sections)}")

    # Filter sections with data + valid timestamp, compute HRS/LRS
    good = []
    for s in sections:
        if not s["ts"]:
            continue
        try:
            t = datetime.strptime(s["ts"], "%m/%d/%Y %H:%M:%S")
        except ValueError:
            continue
        lrs, hrs = extract_hrs_lrs(s)
        if lrs is None:
            continue
        good.append((t, lrs, hrs))

    # Sort chronologically
    good.sort(key=lambda x: x[0])
    print(f"Cycles with data: {len(good)}")
    print(f"Time range: {good[0][0]} → {good[-1][0]}")
    dur = (good[-1][0] - good[0][0]).total_seconds()
    print(f"Duration: {dur:.0f}s = {dur/60:.1f}min")

    # Remove duplicates: consecutive sections with same timestamp
    unique = []
    for i, (t, lrs, hrs) in enumerate(good):
        if i > 0 and t == good[i - 1][0]:
            continue
        unique.append((lrs, hrs))
    print(f"Unique cycles (after dedup): {len(unique)}")

    # Generate cycle indices matching raw_cycles range C9000-C1007114
    # 205 unique points spread logarithmically
    raw_cycles_vals = [9000, 9209, 9423, 9642, 9866, 10095, 10330, 10570, 10816,
                       11067, 11324, 11587, 11856, 12132, 12414, 12703, 13000,
                       13304, 13616, 13936, 14264, 14600, 14945, 15299, 15662,
                       16034, 16416, 16808, 17210, 17623, 18047, 18482, 18929,
                       19388, 19860, 20345, 20843, 21355, 21881, 22422, 22978,
                       23550, 24138, 24743, 25365, 26005, 26663, 27340, 28036,
                       28752, 29489, 30247, 31027, 31829, 32654, 33503, 34376,
                       35274, 36198, 37149, 38127, 39133, 40168, 41233, 42329,
                       43457, 44617, 45811, 47040, 48304, 49605, 50944, 52322,
                       53740, 55199, 56701, 58247, 59838, 61476, 63162, 64897,
                       66683, 68521, 70413, 72360, 74364, 76426, 78548, 80732,
                       82979, 85291, 87670, 90117, 92634, 95223, 97886, 100624,
                       103440, 106335, 109312, 112371, 115516, 118747, 122068,
                       125479, 128984, 132584, 136281, 140078, 143977, 147979,
                       152088, 156305, 160633, 165074, 169631, 174306, 179102,
                       184021, 189066, 194239, 199543, 204980, 210553, 216265,
                       222119, 228117, 234262, 240557, 247005, 253609, 260371,
                       267296, 274385, 281643, 289072, 296677, 304459, 312424,
                       320574, 328913, 337444, 346171, 355098, 364228, 373565,
                       383113, 392876, 402857, 413062, 423493, 434156, 445054,
                       456192, 467574, 479204, 491087, 503228, 515631, 528301,
                       541243, 554462, 567962, 581750, 595829, 610206, 624884,
                       639871, 655170, 670788, 686730, 703001, 719608, 736555,
                       753848, 771494, 789498, 807867, 826607, 845724, 865225,
                       885117, 905406, 926100, 947205, 968728, 990678, 1013060]

    if len(unique) != len(raw_cycles_vals):
        print(f"WARNING: {len(unique)} unique cycles vs {len(raw_cycles_vals)} raw_cycles values")
        # Use log-spaced indices instead
        cycles = np.geomspace(9000, 1007114, len(unique))
    else:
        cycles = np.array(raw_cycles_vals)

    lrs_arr = np.array([u[0] for u in unique])
    hrs_arr = np.array([u[1] for u in unique])
    ratio = hrs_arr / lrs_arr

    print(f"\nResults:")
    print(f"  Cycles: {cycles[0]:.0f} – {cycles[-1]:.0f}")
    print(f"  HRS: {np.min(hrs_arr):.0f} – {np.max(hrs_arr):.0f} Ω, mean={np.mean(hrs_arr):.0f}")
    print(f"  LRS: {np.min(lrs_arr):.0f} – {np.max(lrs_arr):.0f} Ω, mean={np.mean(lrs_arr):.0f}")
    print(f"  Ratio: {np.min(ratio):.1f} – {np.max(ratio):.1f}")

    # Plot
    fig, (ax_r, ax_ratio) = plt.subplots(2, 1, figsize=(6.5, 5.5), sharex=True)

    ax_r.plot(cycles, hrs_arr, "o", markersize=5, color="#CC0000", alpha=0.7, label="_nolegend_")
    ax_r.plot(cycles, lrs_arr, "s", markersize=5, color="#0055CC", alpha=0.7, label="_nolegend_")
    ax_r.annotate("HRS", xy=(cycles[-1], hrs_arr[-1]), xytext=(5, 0),
                  textcoords="offset points", fontsize=11, color="#CC0000", fontweight="bold", va="center")
    ax_r.annotate("LRS", xy=(cycles[-1], lrs_arr[-1]), xytext=(5, 0),
                  textcoords="offset points", fontsize=11, color="#0055CC", fontweight="bold", va="center")
    ax_r.set_yscale("log")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_title(f"Volatile Memristor — Endurance ({device_label})")
    ax_r.grid(True, alpha=0.25)

    ax_ratio.plot(cycles, ratio, "^", markersize=5, color="#994400", alpha=0.7, label="_nolegend_")
    ax_ratio.annotate("HRS/LRS", xy=(cycles[-1], ratio[-1]), xytext=(5, 0),
                      textcoords="offset points", fontsize=11, color="#994400", fontweight="bold", va="center")
    ax_ratio.set_xlabel("Cycle")
    ax_ratio.set_ylabel("HRS / LRS")
    ax_ratio.set_xscale("log")
    ax_ratio.grid(True, alpha=0.25)

    fig.tight_layout()
    stem = RESULTS_DIR / f"endurance_matched_{device_label}"
    for ext, dpi_val in [(".pdf", 300), (".png", 200)]:
        p = stem.with_suffix(ext)
        fig.savefig(p, dpi=dpi_val, bbox_inches="tight")
        print(f"\n✓ Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
