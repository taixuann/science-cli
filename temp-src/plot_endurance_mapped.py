"""Map Measurement Result sections to raw_cycles entries for R3-C3 endurance.

User ran 9000 silent cycles, then log-spaced read-backs to ~1M cycles.
Each read-back produces 1 Measurement Result section (V/I waveform).
raw_cycles is the summary table, but only 207/9205 entries have data.
Measurement Result sections have 410 with data — fill the gaps.

This script:
1. Extracts HRS/LRS from Measurement Result sections (V/I known)
2. Generates cycle indices: C[n] = 9000 × 10^(n/step_log), step_log=95
3. Cross-validates against raw_cycles where available
4. Plots everything together
"""
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
STEP_LOG = 95
BASE_CYCLE = 9000


def extract_meas_sections(path: Path):
    """Extract Measurement Result sections with non-zero data."""
    sections = []
    with path.open() as f:
        reader = csv.reader(f)
        in_section = False
        dv_rows = []
        y_bottom = None
        y_top = None
        for i, row in enumerate(reader):
            if not row:
                continue
            if 'Setup.Title' in str(row) and 'Measurement Result' in str(row):
                if in_section and dv_rows:
                    sections.append((lineno, y_bottom, y_top, dv_rows))
                in_section = True
                lineno = i + 1
                dv_rows = []
                y_bottom = None
                y_top = None
                continue
            if in_section:
                if 'YAxis.Bottom' in str(row):
                    y_bottom = [x.strip() for x in row[1:]]
                elif 'YAxis.Top' in str(row):
                    y_top = [x.strip() for x in row[1:]]
                elif row[0] == 'DataValue':
                    dv_rows.append(row)
        if in_section and dv_rows:
            sections.append((lineno, y_bottom, y_top, dv_rows))
    return sections


def extract_raw_cycles(path: Path):
    """Extract raw_cycles entries with non-zero data, grouped by cycle."""
    from collections import OrderedDict
    grouped = OrderedDict()
    with path.open() as f:
        for row in csv.reader(f):
            if row and row[0] == 'DataValue':
                cyc = row[1].strip()
                if not cyc:
                    continue
                try:
                    c = int(float(cyc))
                except ValueError:
                    continue
                if c < 1:
                    continue
                vals = [x.strip() for x in row]
                if c not in grouped:
                    grouped[c] = []
                grouped[c].append(vals)
    return grouped


def compute_r_from_section(y_bottom, y_top, dv_rows):
    """Extract HRS/LRS resistance from a Measurement Result section.

    Y-axis defines the range. Uses the ACTUAL DataValue V and I.
    Time=7.5µs → V~1.978V, I~-436µA → LRS (lower R)
    Time=145µs → V~0.300V, I~-1.147µA → HRS (higher R)
    """
    if len(dv_rows) < 2:
        return None, None, None, None
    t1 = float(dv_rows[0][1])
    v1 = float(dv_rows[0][2])
    i1 = float(dv_rows[0][3])
    t2 = float(dv_rows[1][1])
    v2 = float(dv_rows[1][2])
    i2 = float(dv_rows[1][3])

    if abs(v1) < 0.01 or abs(v2) < 0.01 or abs(i1) < 1e-12 or abs(i2) < 1e-12:
        return None, None, None, None

    r1 = abs(v1 / i1)
    r2 = abs(v2 / i2)

    if r1 < r2:
        return abs(v1 / i1), abs(v2 / i2), abs(i1), abs(i2)
    else:
        return abs(v2 / i2), abs(v1 / i1), abs(i2), abs(i1)


def compute_r_from_raw_cycle(rows, v_read_lrs=1.978, v_read_hrs=0.300):
    """Extract HRS/LRS resistance from raw_cycles entry.

    raw_ch2 (col 2) and target_meas (col 3) contain current values.
    Uses assumed V_read since no voltage column in R3-C3 format.
    """
    currents = []
    for r in rows:
        for idx in [2, 3]:
            v = r[idx].strip()
            if v and v != '0':
                try:
                    currents.append(float(v))
                except ValueError:
                    pass
    if len(currents) < 2:
        return None, None
    abs_i = sorted([abs(x) for x in currents if x != 0])
    if len(abs_i) < 2:
        return None, None
    lrs = v_read_lrs / abs_i[-1]  # largest |I| → LRS
    hrs = v_read_hrs / abs_i[0]   # smallest |I| → HRS
    return hrs, lrs


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
    device_label = "R3-C3"

    # 1. Extract measurement sections
    sections = extract_meas_sections(raw_path)
    good_sections = [s for s in sections if s[3] and len(s[3]) >= 2
                     and abs(float(s[3][0][2])) > 0.01
                     and abs(float(s[3][0][3])) > 1e-12]
    print(f"\nMeasurement Result sections: {len(sections)} total, {len(good_sections)} with data")

    # 2. Extract raw_cycles
    raw_groups = extract_raw_cycles(raw_path)
    raw_with_data = {}
    for c, rows in raw_groups.items():
        hrs, lrs = compute_r_from_raw_cycle(rows)
        if hrs and lrs:
            raw_with_data[c] = (hrs, lrs)
    print(f"raw_cycles entries: {len(raw_groups)} total, {len(raw_with_data)} with valid R data")

    # 3. Process measurement sections: compute R + generate cycle index
    section_cycles = []
    section_hrs = []
    section_lrs = []
    section_ilrs = []
    section_ihrs = []

    for idx, (lineno, yb, yt, dv) in enumerate(good_sections):
        lrs_r, hrs_r, i_lrs, i_hrs = compute_r_from_section(yb, yt, dv)
        if lrs_r is None:
            continue
        # Generate cycle index: C[n] = 9000 × 10^(n/95)
        cycle = BASE_CYCLE * (10 ** (idx / STEP_LOG))
        section_cycles.append(cycle)
        section_hrs.append(hrs_r)
        section_lrs.append(lrs_r)
        section_ilrs.append(i_lrs)
        section_ihrs.append(i_hrs)

    section_cycles = np.array(section_cycles)
    section_hrs = np.array(section_hrs)
    section_lrs = np.array(section_lrs)

    print(f"\nMeasurement Result data: {len(section_cycles)} cycles")
    print(f"  Cycle range: {section_cycles[0]:.0f} – {section_cycles[-1]:.0f}")
    print(f"  HRS: {np.min(section_hrs):.0f} – {np.max(section_hrs):.0f} Ω, mean={np.mean(section_hrs):.0f}")
    print(f"  LRS: {np.min(section_lrs):.0f} – {np.max(section_lrs):.0f} Ω, mean={np.mean(section_lrs):.0f}")

    # 4. Cross-validate with raw_cycles
    raw_cycles_arr = np.array(sorted(raw_with_data.keys()))
    raw_hrs_arr = np.array([raw_with_data[c][0] for c in raw_cycles_arr])
    raw_lrs_arr = np.array([raw_with_data[c][1] for c in raw_cycles_arr])

    # Match by finding nearest section to each raw_cycles entry
    matches = []
    for rc, rr_hrs, rr_lrs in zip(raw_cycles_arr, raw_hrs_arr, raw_lrs_arr):
        if rc < 100:  # skip cycles 1,2 (pre-conditioning)
            continue
        nearest = np.argmin(np.abs(section_cycles - rc))
        sc = section_cycles[nearest]
        sr_hrs = section_hrs[nearest]
        sr_lrs = section_lrs[nearest]
        ratio_hrs = rr_hrs / sr_hrs
        ratio_lrs = rr_lrs / sr_lrs
        matches.append((rc, sc, rr_hrs, sr_hrs, rr_lrs, sr_lrs, ratio_hrs, ratio_lrs))

    print(f"\nCross-validation (raw_cycles vs Measurement Result sections):")
    print(f"  {'raw_cyc':>8} {'sect_cyc':>8} {'raw_HRS':>10} {'sec_HRS':>10} {'raw_LRS':>10} {'sec_LRS':>10} {'ratio_H':>8} {'ratio_L':>8}")
    for m in matches[:5]:
        print(f"  {m[0]:8d} {m[1]:8.0f} {m[2]:10.0f} {m[3]:10.0f} {m[4]:10.0f} {m[5]:10.0f} {m[6]:8.2f} {m[7]:8.2f}")
    print("  ...")
    mean_hrs_ratio = np.mean([m[6] for m in matches])
    mean_lrs_ratio = np.mean([m[7] for m in matches])
    print(f"  Mean ratio: HRS={mean_hrs_ratio:.2f}, LRS={mean_lrs_ratio:.2f}")

    # 5. Plot
    fig, (ax_r, ax_ratio) = plt.subplots(2, 1, figsize=(7.0, 5.5), sharex=True)

    # Measurement Result sections
    ax_r.plot(section_cycles, section_hrs, "o", markersize=4, color="#CC0000",
              alpha=0.6, label="_nolegend_")
    ax_r.plot(section_cycles, section_lrs, "s", markersize=4, color="#0055CC",
              alpha=0.6, label="_nolegend_")

    # raw_cycles overlay
    ax_r.plot(raw_cycles_arr, raw_hrs_arr, "D", markersize=6, color="#FF9900",
              alpha=0.9, label="_nolegend_", markeredgecolor="black", markeredgewidth=0.5)
    ax_r.plot(raw_cycles_arr, raw_lrs_arr, "D", markersize=6, color="#00AA66",
              alpha=0.9, label="_nolegend_", markeredgecolor="black", markeredgewidth=0.5)

    ax_r.annotate("HRS (waveform)", xy=(section_cycles[-1], section_hrs[-1]),
                  xytext=(5, 0), textcoords="offset points", fontsize=10,
                  color="#CC0000", fontweight="bold", va="center")
    ax_r.annotate("LRS (waveform)", xy=(section_cycles[-1], section_lrs[-1]),
                  xytext=(5, 0), textcoords="offset points", fontsize=10,
                  color="#0055CC", fontweight="bold", va="center")

    ax_r.set_yscale("log")
    ax_r.set_ylabel("Resistance (Ω)")
    ax_r.set_title(f"Volatile Memristor — Endurance ({device_label})")
    ax_r.grid(True, alpha=0.25)
    ax_r.legend(["HRS (raw_cycles)", "LRS (raw_cycles)"], fontsize=8, loc="upper left")

    # Ratio panel
    section_ratio = section_hrs / section_lrs
    ax_ratio.plot(section_cycles, section_ratio, "^", markersize=4,
                  color="#994400", alpha=0.6, label="_nolegend_")
    raw_ratio = raw_hrs_arr[raw_hrs_arr > 0] / raw_lrs_arr[raw_lrs_arr > 0]
    ax_ratio.plot(raw_cycles_arr, raw_ratio, "D", markersize=6, color="#994400",
                  alpha=0.9, label="_nolegend_", markeredgecolor="black", markeredgewidth=0.5)
    ax_ratio.annotate("HRS/LRS", xy=(section_cycles[-1], section_ratio[-1]),
                      xytext=(5, 0), textcoords="offset points", fontsize=10,
                      color="#994400", fontweight="bold", va="center")
    ax_ratio.set_xlabel("Cycle")
    ax_ratio.set_ylabel("HRS / LRS")
    ax_ratio.grid(True, alpha=0.25)

    fig.tight_layout()
    safe_stem = "".join(c for c in raw_path.stem if c.isalnum() or c in "_-")[:30]
    stem = RESULTS_DIR / f"endurance_mapped_{safe_stem}"
    for ext, dpi_val in [(".pdf", 300), (".png", 200)]:
        p = stem.with_suffix(ext)
        fig.savefig(p, dpi=dpi_val, bbox_inches="tight")
        print(f"\n✓ Saved: {p}")
    plt.close(fig)

    print(f"\nMapping complete — {len(section_cycles)} cycles from waveform sections")
    print("Open the plot and check if raw_cycles (diamonds) overlay the sections (circles/squares)")


if __name__ == "__main__":
    main()
