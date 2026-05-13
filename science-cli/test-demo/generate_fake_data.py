import numpy as np
import os

STEP_DIR = os.path.join(os.path.dirname(__file__), "protocol", "demo-protocol", "1_iv-measurements")

def bipolar_sweep(v_max, v_min, n_points=200):
    half = n_points // 2
    t = np.linspace(0, 1, n_points)
    v = np.zeros(n_points)
    v[:half] = np.linspace(0, v_max, half)
    v[half:] = np.linspace(v_max, v_min, n_points - half)
    return t, v

def generate_set_iv(v_max=3.0, v_min=-3.0, v_set=0.9, v_reset=-1.2,
                     i_hrs=1e-8, i_lrs=1e-3, noise_level=0.05, n_points=400):
    t, v = bipolar_sweep(v_max, v_min, n_points)
    i = np.zeros_like(v)
    switched = False
    for j in range(n_points):
        raw = i_hrs if not switched else i_lrs
        switched = switched or (v[j] >= v_set and j < n_points // 2)
        switched = switched and not (v[j] <= v_reset and j >= n_points // 2)
        raw = i_hrs if not switched else i_lrs
        noise = raw * noise_level * np.random.randn()
        i[j] = abs(raw + noise)
    return t, v, i

def generate_reset_iv(v_max=1.5, v_min=-2.0, v_set=0.9, v_reset=-0.8,
                       i_hrs=1e-8, i_lrs=1e-3, noise_level=0.05, n_points=400):
    t, v = bipolar_sweep(v_max, v_min, n_points)
    i = np.zeros_like(v)
    switched = True
    for j in range(n_points):
        switched = switched and not (v[j] <= v_reset and j >= n_points // 2)
        raw = i_lrs if switched else i_hrs
        noise = raw * noise_level * np.random.randn()
        i[j] = abs(raw + noise)
    return t, v, i

def write_csv(filepath, t, v, i):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write("Time (s),Voltage (V),Current (A)\n")
        for ti, vi, ii in zip(t, v, i):
            f.write(f"{ti:.15e},{vi:.15e},{ii:.15e}\n")

np.random.seed(42)

materials = {
    "PDA": {"v_set": 0.9,  "v_reset": -0.8,  "i_lrs": 8e-4,  "i_hrs": 5e-9},
    "PDAc": {"v_set": 1.2, "v_reset": -1.0,  "i_lrs": 5e-4,  "i_hrs": 2e-8},
}

cells = [(0,0), (1,0), (0,1), (1,1)]
used_files = []
for row, col in cells:
    for mat_name, mat in materials.items():
        v_set = mat["v_set"] + 0.15 * np.random.randn()
        v_reset = mat["v_reset"] + 0.1 * np.random.randn()
        for cycle in range(3):
            fname = f"0101_{mat_name}_r{row}c{col}_iv_set_0{cycle+1}.csv"
            fpath = os.path.join(STEP_DIR, fname)
            t, v, i = generate_set_iv(v_set=v_set, v_reset=v_reset,
                                       i_lrs=mat["i_lrs"], i_hrs=mat["i_hrs"])
            write_csv(fpath, t, v, i)
            used_files.append(fname)

            fname = f"0101_{mat_name}_r{row}c{col}_iv_reset_0{cycle+1}.csv"
            fpath = os.path.join(STEP_DIR, fname)
            t, v, i = generate_reset_iv(v_set=v_set, v_reset=v_reset,
                                         i_lrs=mat["i_lrs"], i_hrs=mat["i_hrs"])
            write_csv(fpath, t, v, i)
            used_files.append(fname)

print(f"Generated {len(used_files)} IV CSV files in {STEP_DIR}")
for f in sorted(used_files):
    print(f"  {f}")
