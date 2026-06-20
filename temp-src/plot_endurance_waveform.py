"""Extract HRS/LRS from Measurement Result sections in Keysight CSV."""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
    "/protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/5_pulse-endurance/results"
)


def extract_hrs_lrs_from_sections(path: Path):
    """Read Measurement Result sections and extract V/I per cycle."""
    cycles = []
    v_lrs_arr = []
    i_lrs_arr = []
    v_hrs_arr = []
    i_hrs_arr = []

    with path.open() as f:
        reader = csv.reader(f)
        in_section = False
        dv_rows = []
        for i, row in enumerate(reader):
            if not row:
                continue
            if 'Setup.Title' in str(row) and 'Measurement Result' in str(row):
                if in_section and dv_rows:
                    cycles.append((i, dv_rows))
                in_section = True
                dv_rows = []
                continue
            if in_section and row[0] == 'DataValue':
                dv_rows.append(row)
        if in_section and dv_rows:
            cycles.append((i, dv_rows))

    lrs_vals = []
    hrs_vals = []
    for lineno, dv_rows in cycles:
        if len(dv_rows) < 2:
            continue
        t1 = dv_rows[0][1].strip()
        v1 = float(dv_rows[0][2].strip())
        i1 = float(dv_rows[0][3].strip())
        t2 = dv_rows[1][1].strip()
        v2 = float(dv_rows[1][2].strip())
        i2 = float(dv_rows[1][3].strip())

        if abs(v1) < 0.01 or abs(v2) < 0.01:
            continue
        if abs(i1) < 1e-12 or abs(i2) < 1e-12:
            continue

        r1 = abs(v1 / i1)
        r2 = abs(v2 / i2)

        # Row at 7.5µs is V~1.978V (LRS read), row at 145µs is V~0.300V (HRS read)
        # LRS has lower resistance (higher current), HRS has higher resistance (lower current)
        if r1 < r2:
            lrs_vals.append(r1)
            hrs_vals.append(r2)
        else:
            lrs_vals.append(r2)
            hrs_vals.append(r1)

    c = np.arange(1, len(lrs_vals) + 1, dtype=float)
    return c, np.array(hrs_vals), np.array(lrs_vals)


def plot_endurance(cycles, hrs, lrs, stem: Path, device_label: str = "R3-C3"):
    ratio = hrs / lrs

    fig, (ax_r, ax_ratio) = plt.subplots(2, 1, figsize=(6.0, 5.5), sharex=True)

    ax_r.plot(cycles, hrs, "o", markersize=5, color="#CC0000", alpha=0.85, label="_nolegend_")
    ax_r.plot(cycles, lrs, "s", markersize=5, color="#0055CC", alpha=0.85, label="_nolegend_")
    ax_r.annotate(
        "HRS", xy=(cycles[-1], hrs[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#CC0000", fontweight="bold", va="center",
    )
    ax_r.annotate(
        "LRS", xy=(cycles[-1], lrs[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#0055CC", fontweight="bold", va="center",
    )
    ax_r.set_yscale("log")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_title(f"Volatile Memristor — Endurance ({device_label})")
    ax_r.grid(True, alpha=0.25)

    ax_ratio.plot(cycles, ratio, "^", markersize=5, color="#994400", alpha=0.85, label="_nolegend_")
    ax_ratio.annotate(
        "HRS/LRS", xy=(cycles[-1], ratio[-1]),
        xytext=(5, 0), textcoords="offset points",
        fontsize=11, color="#994400", fontweight="bold", va="center",
    )
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
        raw_path = Path(
            "/Users/tai/workspace/projects/active_projects/res_internship"
            "/data/Memristors endurance [cu-c-pda(q5)-ito(2)_r3-c3(1) ; 2026-06-19 18_59_18].csv"
        )

    print(f"File: {raw_path.name}")
    print("Extracting HRS/LRS from Measurement Result sections ...")
    cycles, hrs, lrs = extract_hrs_lrs_from_sections(raw_path)

    print(f"  Valid cycles: {len(cycles)}")
    print(f"  HRS range: {np.min(hrs):.1f} – {np.max(hrs):.1f} Ω")
    print(f"  LRS range: {np.min(lrs):.1f} – {np.max(lrs):.1f} Ω")
    print(f"  Ratio range: {np.min(hrs/lrs):.1f} – {np.max(hrs/lrs):.1f}")

    safe_stem = "".join(c for c in raw_path.stem if c.isalnum() or c in "_-")[:30]
    stem = RESULTS_DIR / f"endurance_waveform_{safe_stem}"
    device_label = "R3-C3" if "r3-c3" in raw_path.name.lower() else "R5-C3"
    print("Plotting ...")
    plot_endurance(cycles, hrs, lrs, stem, device_label=device_label)


if __name__ == "__main__":
    main()
