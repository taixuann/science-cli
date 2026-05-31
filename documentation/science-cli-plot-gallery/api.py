# -*- coding: utf-8 -*-
"""
Science-CLI Data Provider APIs (api.py)
Emulates memristor crossbars, multi-project workspace paths,
and high-fidelity experimental plotting curves.
"""

import os
import math
import random
import json
from datetime import datetime

TARGET_WORKSPACE_DIR = "/Users/tai/workspace/projects/active_projects"
LOCAL_WORKSPACE_DIR = os.path.join(os.getcwd(), "active_projects")

def get_workspace_dir():
    if os.path.exists(TARGET_WORKSPACE_DIR):
        return TARGET_WORKSPACE_DIR
    return LOCAL_WORKSPACE_DIR

PROJECTS = ["res_internship", "non-res_odon-vallet", "non-res_phd-application", "test-project"]

def ensure_workspace():
    root = get_workspace_dir()
    if not os.path.exists(root):
        try:
            os.makedirs(root)
        except Exception:
            pass
            
    for proj in PROJECTS:
        proj_path = os.path.join(root, proj)
        if not os.path.exists(proj_path):
            try:
                os.makedirs(proj_path)
            except Exception:
                pass
                
        # Submfolders (protocols)
        for proto in ["Forming_Sweep", "Endurance_Cycles", "Retention_Test", "IV_Characterization"]:
            proto_path = os.path.join(proj_path, proto)
            if not os.path.exists(proto_path):
                try:
                    os.makedirs(proto_path)
                except Exception:
                    pass
            for step in ["Step_1_Initial", "Step_2_Stress_Cycle", "Step_3_Final_Verification"]:
                step_path = os.path.join(proto_path, step)
                if not os.path.exists(step_path):
                    try:
                        os.makedirs(step_path)
                    except Exception:
                        pass
                
                # Mock SVG file
                for fn in ["shaping_loop.svg", "current_voltage_sweep.svg", "resistance_vs_cycle.svg"]:
                    file_path = os.path.join(step_path, fn)
                    if not os.path.exists(file_path):
                        svg = """<?xml version="1.0" encoding="utf-8"?>
<svg viewBox="0 0 400 300" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#0a0f1d" />
  <path d="M 50,255 L 150,150 L 220,130 L 280,70 L 350,50" fill="none" stroke="#6366f1" stroke-width="3" />
  <circle cx="150" cy="150" r="5" fill="#ef4444" />
  <circle cx="280" cy="70" r="5" fill="#f59e0b" />
  <text x="30" y="30" font-family="monospace" font-size="12" fill="#94a3b8">PROJECT: {proj}</text>
  <text x="30" y="50" font-family="monospace" font-size="10" fill="#64748b">Step: {step}</text>
  <text x="160" y="155" font-family="sans-serif" font-size="10" fill="#ef4444">Vset (1.5V)</text>
</svg>""".format(proj=proj.upper(), step=step)
                        try:
                            with open(file_path, "w") as f:
                                f.write(svg)
                        except Exception:
                            pass

# Initialize on import safely
ensure_workspace()

def generate_seeded_crossbar(seed_str):
    """
    Generate deterministic devices based on a string seed (e.g. projectname_protocolname)
    Returns a 6x6 matrix of dicts.
    """
    # Simple LCG / Hash in python
    val = 0
    for char in seed_str:
        val = ord(char) + ((val << 5) - val)
    
    random_generator = random.Random(val)
    matrix = []
    
    for r in range(1, 7):
        row = []
        for c in range(1, 7):
            material = "AlOx" if random_generator.random() > 0.45 else "HfOx"
            switching = random_generator.random() > 0.15
            v_set = round(1.2 + random_generator.random() * 1.5, 2)
            v_reset = round(-0.5 - random_generator.random() * 1.2, 2)
            ratio = int(10 + random_generator.random() * 9990) if switching else 1
            file_count = int(5 + random_generator.random() * 25)
            dev_yield = int(75 + random_generator.random() * 25) if switching else 0
            
            row.append({
                "cell": "R{0}C{1}".format(r, c),
                "material": material,
                "switching": switching,
                "v_set": v_set,
                "v_reset": v_reset,
                "ratio": ratio,
                "file_count": file_count,
                "yield": dev_yield
            })
        matrix.append(row)
    return matrix

def get_projects_list():
    return {
        "workspace": get_workspace_dir(),
        "projects": PROJECTS
    }

def get_project_summary(proj_name):
    root = get_workspace_dir()
    proj_path = os.path.join(root, proj_name)
    
    protocols_list = []
    total_files = 0
    
    if os.path.exists(proj_path):
        folders = [f for f in os.listdir(proj_path) if os.path.isdir(os.path.join(proj_path, f))]
        folders.sort()
        
        for proto in folders:
            proto_path = os.path.join(proj_path, proto)
            steps_list = []
            proto_file_count = 0
            
            steps = [sf for sf in os.listdir(proto_path) if os.path.isdir(os.path.join(proto_path, sf))]
            steps.sort()
            
            for step in steps:
                step_path = os.path.join(proto_path, step)
                step_files = [fl for fl in os.listdir(step_path) if os.path.isfile(os.path.join(step_path, fl))]
                step_files.sort()
                
                proto_file_count += len(step_files)
                
                steps_list.append({
                    "name": step,
                    "files": [{
                        "name": fn,
                        "path": "{0}/{1}/{2}/{3}".format(proj_name, proto, step, fn),
                        "type": "svg" if fn.endswith(".svg") else "pdf" if fn.endswith(".pdf") else "png"
                    } for fn in step_files]
                })
            
            total_files += proto_file_count
            
            # Crossbar summary
            matrix = generate_seeded_crossbar("{0}_{1}".format(proj_name, proto))
            active_cells = sum(1 for row in matrix for cell in row if cell["switching"])
            avg_yield = round(sum(cell["yield"] for row in matrix for cell in row) / 36)
            
            protocols_list.append({
                "name": proto,
                "steps": steps_list,
                "total_files": proto_file_count,
                "measured_cells": active_cells,
                "switching_yield": avg_yield
            })
            
    return {
        "project_name": proj_name,
        "protocols": protocols_list,
        "stats": {
            "total_protocols": len(protocols_list),
            "total_files": total_files
        }
    }

def get_protocol_files(proj_name, proto):
    root = get_workspace_dir()
    proto_path = os.path.join(root, proj_name, proto)
    
    if not os.path.exists(proto_path):
        return None
        
    steps_list = []
    steps = [sf for sf in os.listdir(proto_path) if os.path.isdir(os.path.join(proto_path, sf))]
    steps.sort()
    
    for step in steps:
        step_path = os.path.join(proto_path, step)
        step_files = [fl for fl in os.listdir(step_path) if os.path.isfile(os.path.join(step_path, fl))]
        step_files.sort()
        
        step_files_data = []
        for fn in step_files:
            file_path = os.path.join(step_path, fn)
            stat = os.stat(file_path)
            step_files_data.append({
                "name": fn,
                "path": "{0}/{1}/{2}/{3}".format(proj_name, proto, step, fn),
                "type": "svg" if fn.endswith(".svg") else "pdf" if fn.endswith(".pdf") else "png",
                "size": "{0} KB".format(round(stat.st_size / 1024, 1)),
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "dimensions": "1280x800 px"
            })
            
        steps_list.append({
            "name": step,
            "files": step_files_data
        })
        
    return {
        "protocol": proto,
        "steps": steps_list
    }

def get_protocol_summary(proj_name, proto):
    matrix = generate_seeded_crossbar("{0}_{1}".format(proj_name, proto))
    active_count = 0
    sum_vset = 0.0
    sum_vreset = 0.0
    sum_ratio = 0.0
    sum_yield = 0.0
    
    for row in matrix:
        for cell in row:
            sum_yield += cell["yield"]
            if cell["switching"]:
                active_count += 1
                sum_vset += cell["v_set"]
                sum_vreset += cell["v_reset"]
                sum_ratio += cell["ratio"]
                
    return {
        "protocol": proto,
        "aggregate": {
            "active_cells_ratio": "{0}/36".format(active_count),
            "yield": round(sum_yield / 36, 1),
            "mean_vset": round(sum_vset / active_count, 2) if active_count > 0 else 0,
            "mean_vreset": round(sum_vreset / active_count, 2) if active_count > 0 else 0,
            "mean_ratio": int(sum_ratio / active_count) if active_count > 0 else 0
        }
    }

def get_heatmap_data(proj_name, proto, metric="ratio", material_filter=""):
    matrix = generate_seeded_crossbar("{0}_{1}".format(proj_name, proto))
    
    values = []
    for row in matrix:
        val_row = []
        for cell in row:
            if material_filter and cell["material"].lower() != material_filter.lower():
                val_row.append(None)
                continue
                
            if metric == "vset":
                val_row.append(cell["v_set"] if cell["switching"] else None)
            elif metric == "vreset":
                val_row.append(abs(cell["v_reset"]) if cell["switching"] else None)
            elif metric == "file_count":
                val_row.append(cell["file_count"])
            elif metric == "yield":
                val_row.append(cell["yield"])
            else: # ratio
                val_row.append(cell["ratio"] if cell["switching"] else None)
        values.append(val_row)
        
    metadata = []
    for row in matrix:
        row_meta = []
        for cell in row:
            row_meta.append({
                "cell": cell["cell"],
                "material": cell["material"],
                "switching": cell["switching"],
                "ratio": cell["ratio"],
                "v_set": cell["v_set"],
                "v_reset": cell["v_reset"],
                "yield": cell["yield"],
                "file_count": cell["file_count"]
            })
        metadata.append(row_meta)
        
    return {
        "protocol": proto,
        "metric": metric,
        "material": material_filter if material_filter else "All",
        "data": values,
        "metadata": metadata
    }

def get_device_iv(proj_name, proto, cell_id):
    matrix = generate_seeded_crossbar("{0}_{1}".format(proj_name, proto))
    target = None
    for row in matrix:
        for cell in row:
            if cell["cell"].lower() == cell_id.lower():
                target = cell
                break
                
    if not target:
        return None
        
    material = target["material"]
    switching = target["switching"]
    v_set = target["v_set"]
    v_reset = target["v_reset"]
    ratio = target["ratio"]
    
    sweeps = []
    points_count = 60
    
    if switching:
        # Set Sweep Curve
        volt1 = []
        curr1 = []
        for i in range(points_count + 1):
            v = round((i / (points_count / 2.0)) * 1.5, 3)
            volt1.append(v)
            r_state = 100000 if v < v_set else 100
            current = (v / r_state) + (random.random() * 1e-6)
            curr1.append(abs(current))
            
        # Reset Sweep Curve
        volt2 = []
        curr2 = []
        for i in range(points_count + 1):
            v = -round((i / (points_count / 2.0)) * 1.0, 3)
            volt2.append(v)
            r_state = 100 if v > v_reset else 100000
            current = (v / r_state) + (random.random() * 1e-6)
            curr2.append(abs(current))
            
        sweeps.append({"label": "Set Sweep Cycle", "voltage": volt1, "current": curr1, "v_set": v_set})
        sweeps.append({"label": "Reset Sweep Cycle", "voltage": volt2, "current": curr2, "v_reset": v_reset})
    else:
        # Defective Curve
        volt = []
        curr = []
        for i in range(-int(points_count/2), int(points_count/2) + 1):
            v = round((i / (points_count / 2.0)) * 2.0, 3)
            volt.append(v)
            current = (v / 1e8) + (random.random() * 1e-9)
            curr.append(abs(current))
        sweeps.append({"label": "Defective Sweep", "voltage": volt, "current": curr})
        
    return {
        "cell_id": cell_id,
        "material": material,
        "switching": switching,
        "v_set": v_set if switching else None,
        "v_reset": v_reset if switching else None,
        "ratio": ratio,
        "sweeps": sweeps
    }

def get_protocol_histograms(proj_name, proto):
    matrix = generate_seeded_crossbar("{0}_{1}".format(proj_name, proto))
    vsets = []
    vresets = []
    ratios = []
    
    for row in matrix:
        for cell in row:
            if cell["switching"]:
                vsets.append(cell["v_set"])
                vresets.append(abs(cell["v_reset"]))
                ratios.append(cell["ratio"])
                
    def bin_data(arr, num_bins=5):
        if not arr:
            return {"bins": [], "counts": []}
        amin, amax = min(arr), max(arr)
        arange = amax - amin if amax > amin else 1.0
        bin_width = arange / num_bins
        
        counts = [0] * num_bins
        bins = []
        for i in range(num_bins):
            low = amin + i * bin_width
            high = low + bin_width
            bins.append("{0:.1f}-{1:.1f}".format(low, high))
            
        for val in arr:
            idx = int((val - amin) / bin_width)
            if idx >= num_bins:
                idx = num_bins - 1
            if idx < 0:
                idx = 0
            counts[idx] += 1
            
        return {"bins": bins, "counts": counts}
        
    return {
        "protocol": proto,
        "vset": bin_data(vsets),
        "vreset": bin_data(vresets),
        "ratio": bin_data([math.log10(ratio) for ratio in ratios])
    }
