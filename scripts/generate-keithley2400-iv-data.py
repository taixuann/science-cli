"""Generate realistic Keithley 2400 IV test data with metadata headers.

Usage:
    python scripts/generate-keithley2400-iv-data.py \\
        --output projects/active_projects/test-project/data/raw \\
        --cells 4 --cycles 3

Generates CSV files in Keithley 2400 format with:
  - 23-line metadata header (compliance, date, sweep params, etc.)
  - Tab-separated columns: Untitled (V), Untitled 1 (I), Untitled 2 (time)
  - Realistic bipolar IV curves with set/reset switching
  - Canonical filename convention: DDMM_Material_rNcN_iv_type.csv
"""

import argparse
import textwrap
from pathlib import Path
import numpy as np


# ── Default parameters ──
DEFAULT_DATE = "1405"
DEFAULT_MATERIAL = "TaOx-W"
DEFAULT_COMPLIANCE = 1e-3
V_READ = 0.1
V_MAX = 2.5
N_POINTS = 201


def generate_bipolar_iv(
    seed: int = 0,
    v_set: float = 1.2,
    v_reset: float = -0.8,
    r_hrs: float = 1e6,
    r_lrs: float = 1e4,
    noise_scale: float = 0.02,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a realistic bipolar IV sweep with set/reset.

    Returns:
        (voltage, current, time) arrays.
    """
    rng = np.random.default_rng(seed)

    # Voltage sweep: 0 → +Vmax → 0 → -Vmax → 0
    half = N_POINTS // 2
    v_fwd = np.linspace(0, V_MAX, half)
    v_rev = np.linspace(V_MAX, -V_MAX, half)
    v_bwd = np.linspace(-V_MAX, 0, N_POINTS - half * 2) if N_POINTS % 2 else np.array([])
    voltage = np.concatenate([v_fwd, v_rev, v_bwd])

    # Current using simple switching model
    current = np.zeros_like(voltage)
    switched_set = False
    switched_reset = False
    for i, v in enumerate(voltage):
        if not switched_set and v >= v_set:
            switched_set = True
        if switched_set and v <= v_reset:
            switched_reset = True

        if not switched_set:
            r = r_hrs
        elif switched_set and not switched_reset:
            r = r_lrs
        else:
            r = r_lrs if voltage[i] < 0 else r_hrs

        i_ideal = v / r if r > 0 else 0
        i_noise = i_ideal * noise_scale * rng.standard_normal()
        current[i] = abs(i_ideal) if v < V_READ and abs(v) < 0.15 else max(abs(i_ideal + i_noise), 1e-12)
        current[i] *= np.sign(v) if abs(v) > 0.01 else 1

    # Clamp at compliance
    current = np.clip(current, -DEFAULT_COMPLIANCE, DEFAULT_COMPLIANCE)

    # Time: 0.1 s per point
    time = np.arange(len(voltage)) * 0.1

    return voltage, current, time


def build_metadata_header(
    date_str: str = "05/14/2026",
    time_str: str = "14:30:00",
    compliance: float = DEFAULT_COMPLIANCE,
    v_max: float = V_MAX,
    n_points: int = N_POINTS,
) -> str:
    """Build a 23-line Keithley 2400 metadata block."""
    lines = [
        "Keithley 2400 SourceMeter",
        f"Date: {date_str}",
        f"Time: {time_str}",
        "Mode: Voltage Sweep",
        f"Compliance: {compliance:.1e} A",
        f"Start: 0 V",
        f"Stop: {v_max:.1f} V",
        "Step: 0.025 V",
        "Source: Voltage",
        "Sense: Remote",
        "NPLC: 1",
        "Range: Auto",
        "Filter: On",
        "Speed: Normal",
        "Terminals: Output",
        "Channel: CH1",
        "Output: ON",
        "Hold: 0 s",
        "Delay: 0.01 s",
        "Sweep: Bipolar",
        f"Points: {n_points}",
        "Measurement: Current",
        "--- Data ---",
    ]
    return "\n".join(lines)


def format_value(v: float) -> str:
    """Format a float for Keithley 2400 output."""
    return f"{v:.6e}"


def generate_file(
    output_dir: Path,
    material: str,
    row: int,
    col: int,
    sweep_type: str,
    cycle: int,
    seed: int,
    date_code: str = DEFAULT_DATE,
):
    """Generate one Keithley 2400 CSV file."""
    rng = np.random.default_rng(seed)

    # Vary v_set/v_reset slightly per cycle
    v_set = 1.2 + rng.uniform(-0.15, 0.15)
    v_reset = -0.8 + rng.uniform(-0.1, 0.1)
    r_hrs = 1e6 * (10 ** rng.uniform(-0.2, 0.2))
    r_lrs = 8e3 * (10 ** rng.uniform(-0.15, 0.15))

    voltage, current, time = generate_bipolar_iv(
        seed=seed, v_set=v_set, v_reset=v_reset,
        r_hrs=r_hrs, r_lrs=r_lrs,
    )

    # Filename convention
    if sweep_type == "forming":
        type_code = "forming"
    elif sweep_type == "set":
        type_code = "set"
    elif sweep_type == "reset":
        type_code = "reset"
    else:
        type_code = "iv"

    filename = f"{date_code}_{material}_r{row}c{col}_iv_{type_code}.csv"
    if cycle > 1:
        stem = filename.replace(".csv", "")
        filename = f"{stem}_{cycle:02d}.csv"

    filepath = output_dir / filename

    # Build content
    date_str = f"05/{date_code[2:]}/20{date_code[:2]}"
    hour = 10 + (row * 3 + col) % 8
    time_str = f"{hour:02d}:{(cycle * 7) % 60:02d}:00"

    header = build_metadata_header(
        date_str=date_str, time_str=time_str,
        compliance=DEFAULT_COMPLIANCE,
    )

    body_lines = [header]
    body_lines.append("Untitled\tUntitled 1\tUntitled 2")
    for v, c, t in zip(voltage, current, time):
        body_lines.append(
            f"{format_value(v)}\t{format_value(c)}\t{format_value(t)}"
        )

    filepath.write_text("\n".join(body_lines), encoding="utf-8")
    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Generate Keithley 2400 test IV data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Example:
              # Generate 4 cells × 3 cycles each = 12 files
              python scripts/generate-keithley2400-iv-data.py \\
                  --output projects/active_projects/test-project/data/raw \\
                  --cells 4 --cycles 3 --material TaOx-W

            Output files:
              1405_TaOx-W_r0c0_iv_forming.csv
              1405_TaOx-W_r0c0_iv_set.csv
              1405_TaOx-W_r0c0_iv_reset.csv
              1405_TaOx-W_r0c0_iv_set_02.csv
              ...

            Each file has:
              - 23-line Keithley 2400 metadata header
              - Tab-separated data: Untitled (V), Untitled 1 (I), Untitled 2 (s)
              - Bipolar sweep 0 → +2.5V → -2.5V → 0 with set/reset switching
        """),
    )
    parser.add_argument("--output", "-o", type=Path, default=Path("data/raw"),
                        help="Output directory")
    parser.add_argument("--cells", type=int, default=4,
                        help="Number of cells (row-major, up to 6)")
    parser.add_argument("--cycles", type=int, default=2,
                        help="Cycles per cell (each cycle gets set + reset)")
    parser.add_argument("--material", default=DEFAULT_MATERIAL,
                        help="Material name for filenames")
    parser.add_argument("--date", default=DEFAULT_DATE,
                        help="Date code (DDMM, default 1405)")
    parser.add_argument("--cols", type=int, default=0,
                        help="Grid columns (default = cells for 1D, 3 for grid)")
    parser.add_argument("--grid", action="store_true",
                        help="Generate grid layout (rows = cells/2, cols = 2)")
    args = parser.parse_args()

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.grid:
        n_cols = args.cols or 2
        n_rows = (args.cells + n_cols - 1) // n_cols
        positions = [(r, c) for r in range(n_rows) for c in range(n_cols)][:args.cells]
    else:
        positions = [(i, 0) for i in range(args.cells)]

    material = args.material
    files_created = []

    for row, col in positions:
        base_seed = row * 10 + col + 42

        for cycle in range(1, args.cycles + 1):
            for sweep_type in ("forming", "set", "reset"):
                seed = base_seed * 100 + cycle * 10 + {"forming": 1, "set": 2, "reset": 3}[sweep_type]
                fname = generate_file(
                    output_dir=output_dir,
                    material=material,
                    row=row, col=col,
                    sweep_type=sweep_type,
                    cycle=cycle,
                    seed=seed,
                    date_code=args.date,
                )
                files_created.append(fname)
                print(f"  Created: {fname}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Generated {len(files_created)} files in: {output_dir}")
    print(f"  Material:  {material}")
    print(f"  Cells:     {len(positions)} ({', '.join(f'r{r}c{c}' for r,c in positions)})")
    print(f"  Cycles:    {args.cycles}")
    print(f"  Sweeps/cell: forming, set, reset")
    print(f"\nNext step: run 'memristor sync' from the protocol directory")
    print(f"  then 'memristor plot --all' and 'memristor dashboard --open'")


if __name__ == "__main__":
    main()
