"""STP decay: full current vs time, y-limited to V_set range."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RAW_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship/data/raw"
)
RESULTS_DIR = Path(
    "/Users/tai/workspace/projects/active_projects/res_internship"
    "/protocol/2.5_cu-c-pda(n3,q4,q5)_ito(2)/6_ppf/results"
)


def load(path):
    rows = []
    with path.open() as f:
        for row in csv.reader(f):
            if row and row[0] == "DataValue":
                try:
                    rows.append((float(row[1]), float(row[2]), float(row[3])))
                except: pass
    a = np.array(rows)
    return a[:, 0] * 1e6, -a[:, 2]


def main():
    files = [
        ("01", RAW_DIR / "190626_cu-c-pda(q5)-ito(2)_r3-c3_stp-decay_01.csv"),
        ("02", RAW_DIR / "190626_cu-c-pda(q5)-ito(2)_r3-c3_stp-decay_02.csv"),
    ]

    for name, fpath in files:
        print(f"Loading {fpath.name} ...")
        t_us, i_pos = load(fpath)

        fig, ax = plt.subplots(figsize=(6.0, 3.5))
        ax.plot(t_us, i_pos * 1e3, "-", color="#CC0000", lw=0.8)
        ax.set_xlabel("Time (µs)")
        ax.set_ylabel("Current (mA)")
        ax.set_title(f"STP Decay — R3-C3 ({name})")
        if name == "01":
            ax.set_ylim(1.0, 2.0)
        else:
            ax.set_ylim(2.8, 3.8)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()

        stem = RESULTS_DIR / f"stp_decay_R3-C3_{name}"
        stem.parent.mkdir(parents=True, exist_ok=True)
        for ext, dpi in [(".pdf", 300), (".png", 200)]:
            p = stem.with_suffix(ext)
            fig.savefig(p, dpi=dpi, bbox_inches="tight")
            print(f"  ✓ Saved: {p}")
        plt.close(fig)


if __name__ == "__main__":
    main()
