import express from "express";
import path from "path";

const app = express();
const PORT = 3000;

app.use(express.json());

// -------------------------------------------------------------
// Scientific Data Simulator for Memristors & Cells
// -------------------------------------------------------------

interface CellStats {
  cell: string;
  row: number;
  col: number;
  material: string;
  v_set: number;
  v_reset: number;
  r_on: number;
  r_off: number;
  ratio: number;
  switching: boolean;
  n_files: number;
}

// Generate realistic 6x6 crossbar array of memristor devices
const ROWS = 6;
const COLS = 6;
const MATERIALS = ["Ta-PDA-ITO(1)", "Ta-PDA-ITO(2)", "Au-PDA-Pt(1)"];

const cellDatabase: Record<string, CellStats[][]> = {};

function initDefaultProtocolData(protocol: string) {
  const grid: CellStats[][] = [];
  const matSelector = protocol.includes("cv") ? 2 : 0; // use different material systems
  
  for (let r = 0; r < ROWS; r++) {
    const rowCells: CellStats[] = [];
    for (let c = 0; c < COLS; c++) {
      const cellId = `R${r+1}C${c+1}`;
      
      // Some cells are dirty or unmeasured to look realistic (85% yield)
      const measured = Math.random() > 0.15;
      const switching = measured && Math.random() > 0.2; // 80% of measured switch
      
      // Generate highly realistic device metrics
      const v_set = +(1.5 + Math.random() * 1.1).toFixed(2); // 1.5V to 2.6V
      const v_reset = +(-1.1 - Math.random() * 1.0).toFixed(2); // -1.1V to -2.1V
      
      const r_on = +(300 + Math.random() * 1200).toFixed(0); // 300 to 1500 ohms
      let r_off = +(50000 + Math.random() * 450000).toFixed(0);
      if (!switching && measured) {
        if (Math.random() > 0.5) {
          r_off = +(r_on * (1 + Math.random() * 2)).toFixed(0); // short/leaky
        } else {
          r_off = 10000000; // open circuit
        }
      }
      
      const ratio = +(r_off / r_on).toFixed(1);
      const material = MATERIALS[Math.floor(Math.random() * 2) + matSelector];
      
      rowCells.push({
        cell: cellId,
        row: r,
        col: c,
        material,
        v_set: switching ? v_set : 0,
        v_reset: switching ? v_reset : 0,
        r_on: measured ? r_on : 0,
        r_off: measured ? r_off : 0,
        ratio: measured ? ratio : 0,
        switching,
        n_files: measured ? Math.floor(1 + Math.random() * 3) : 0,
      });
    }
    grid.push(rowCells);
  }
  cellDatabase[protocol] = grid;
}

// Pre-initialize basic protocols
initDefaultProtocolData("1_iv-test");
initDefaultProtocolData("2_cv-scan");
initDefaultProtocolData("3_retention");

// -------------------------------------------------------------
// JSON API Endpoint Definitions
// -------------------------------------------------------------

// Page 1 API: `/api/project`
app.get("/api/project", (req, res) => {
  const p1 = cellDatabase["1_iv-test"].flat();
  const measured = p1.filter(c => c.r_on > 0);
  const switching = p1.filter(c => c.switching);
  const yieldPct = +((switching.length / (measured.length || 1)) * 100).toFixed(1);

  res.json({
    project_name: "my-experiment",
    project_path: "/Users/tai/workspace/projects/my-experiment",
    last_protocol: "1_iv-test",
    last_step: "1_set",
    protocols: [
      {
        name: "1_iv-test",
        steps: ["1_set", "2_reset"],
        total_files: 24,
        measured_cells: measured.length,
        switching_yield: yieldPct,
        last_updated: new Date(Date.now() - 3600000 * 2.5).toISOString() // 2.5 hrs ago
      },
      {
        name: "2_cv-scan",
        steps: ["1_scan_fast", "2_scan_slow"],
        total_files: 18,
        measured_cells: cellDatabase["2_cv-scan"].flat().filter(c => c.r_on > 0).length,
        switching_yield: 62.5,
        last_updated: new Date(Date.now() - 3600000 * 24).toISOString() // yesterday
      },
      {
        name: "3_retention",
        steps: ["1_read_volt", "2_long_term"],
        total_files: 30,
        measured_cells: cellDatabase["3_retention"].flat().filter(c => c.r_on > 0).length,
        switching_yield: 85.0,
        last_updated: new Date(Date.now() - 3600000 * 48).toISOString()
      }
    ],
    stats: {
      total_protocols: 3,
      total_files: 72,
      total_cells_measured: measured.length + 12 + 15,
      overall_yield: 75.4
    }
  });
});

// Page 2 API: `/api/gallery`
app.get("/api/gallery", (req, res) => {
  res.json({
    plots: [
      {
        id: "plot_001",
        plot_path: "protocol/1_iv-test/1_set/results/iv_overlay.pdf",
        thumbnail_path: "protocol/1_iv-test/1_set/results/iv_overlay.png",
        data_files: ["data/raw/0505_Ta-PDA-ITO_r0c0_iv_01.csv", "data/raw/0505_Ta-PDA-ITO_r0c1_iv_01.csv"],
        protocol: "1_iv-test",
        step: "1_set",
        technique: "iv-sweep",
        device: "Keithley 2400 SourceMeter",
        theme: "publication-nature",
        generated_at: new Date().toISOString(),
        title: "IV Overlays — Row 1 Active",
        flags: { xlabel: "Voltage (V)", ylabel: "Current (A)" }
      },
      {
        id: "plot_002",
        plot_path: "protocol/1_iv-test/2_reset/results/vreset_dist.pdf",
        thumbnail_path: "protocol/1_iv-test/2_reset/results/vreset_dist.png",
        data_files: ["data/processed/vreset_distribution.csv"],
        protocol: "1_iv-test",
        step: "2_reset",
        technique: "iv-sweep",
        device: "Keithley 2400 SourceMeter",
        theme: "ieee-style",
        generated_at: new Date(Date.now() - 500000).toISOString(),
        title: "Vreset Distribution Waveform",
        flags: { xlabel: "Vreset (V)", ylabel: "Probability Count" }
      },
      {
        id: "plot_003",
        plot_path: "protocol/2_cv-scan/results/cyclic_voltammetry_r2c3.pdf",
        thumbnail_path: "protocol/2_cv-scan/results/cyclic_voltammetry_r2c3.png",
        data_files: ["data/raw/0512_Au-PDA-Pt_r2c3_cv_03.csv"],
        protocol: "2_cv-scan",
        step: "1_scan_fast",
        technique: "cv",
        device: "Ivium Potentiostat",
        theme: "publication-nature",
        generated_at: new Date(Date.now() - 3600000 * 20).toISOString(),
        title: "Cyclic Voltammetry (50mV/s) — R2C3 Cell",
        flags: { xlabel: "Potential vs Ag/AgCl (V)", ylabel: "Current density (mA/cm²)" }
      },
      {
        id: "plot_004",
        plot_path: "protocol/1_iv-test/1_set/results/retention_statistics.pdf",
        thumbnail_path: "protocol/1_iv-test/1_set/results/retention_statistics.png",
        data_files: ["data/raw/0505_retention_all.csv"],
        protocol: "1_iv-test",
        step: "1_set",
        technique: "retention",
        device: "Keithley 4200-SCS",
        theme: "scientific-dark",
        generated_at: new Date(Date.now() - 3600000 * 40).toISOString(),
        title: "Retention Profile @ 10⁴ Seconds",
        flags: { xlabel: "Time (s)", ylabel: "Resistance (Ω)" }
      },
      {
        id: "plot_005",
        plot_path: "protocol/3_retention/1_read_volt/results/hrs_lrs_resistance_r0c2.pdf",
        thumbnail_path: "protocol/3_retention/1_read_volt/results/hrs_lrs_resistance_r0c2.png",
        data_files: ["data/raw/0515_HRS_LRS_r0c2.csv"],
        protocol: "3_retention",
        step: "1_read_volt",
        technique: "retention",
        device: "Keysight B1500A",
        theme: "ieee-style",
        generated_at: new Date(Date.now() - 3600000 * 21).toISOString(),
        title: "Ohmic Resistance Evolution r0c2",
        flags: { xlabel: "Cycles (#)", ylabel: "DC Resistance (Ω)" }
      },
      {
        id: "plot_006",
        plot_path: "protocol/2_cv-scan/results/charge_transfer_kinetics.pdf",
        thumbnail_path: "protocol/2_cv-scan/results/charge_transfer_kinetics.png",
        data_files: ["data/processed/cv_kinetics_summary.csv"],
        protocol: "2_cv-scan",
        step: "2_scan_slow",
        technique: "cv",
        device: "Gamry Reference 600",
        theme: "publication-science",
        generated_at: new Date(Date.now() - 3600000 * 12).toISOString(),
        title: "Randles-Sevcik Kinetic Plot",
        flags: { xlabel: "Scan Rate (V/s)^0.5", ylabel: "Peak Current (mA)" }
      }
    ],
    filters: {
      protocols: ["1_iv-test", "2_cv-scan", "3_retention"],
      steps: ["1_set", "2_reset", "1_scan_fast", "2_scan_slow", "1_read_volt"],
      techniques: ["iv-sweep", "cv", "retention"],
      materials: ["Ta-PDA-ITO(1)", "Ta-PDA-ITO(2)", "Au-PDA-Pt(1)"]
    }
  });
});

// Page 3 API: `/api/protocol/<name>/summary`
app.get("/api/protocol/:name/summary", (req, res) => {
  const protocol = req.params.name;
  
  if (!cellDatabase[protocol]) {
    initDefaultProtocolData(protocol);
  }
  
  const cells = cellDatabase[protocol].flat();
  const measured = cells.filter(c => c.r_on > 0);
  const switching = cells.filter(c => c.switching);
  const yieldPct = +((switching.length / (measured.length || 1)) * 100).toFixed(1);
  
  const vsetVals = switching.map(c => c.v_set).sort((a,b)=>a-b);
  const vresetVals = switching.map(c => c.v_reset).sort((a,b)=>a-b);
  const ratioVals = measured.map(c => c.ratio).sort((a,b)=>a-b);
  
  const median_vset = vsetVals.length ? +(vsetVals[Math.floor(vsetVals.length/2)]).toFixed(2) : 0;
  const median_vreset = vresetVals.length ? +(vresetVals[Math.floor(vresetVals.length/2)]).toFixed(2) : 0;
  const median_ratio = ratioVals.length ? +(ratioVals[Math.floor(ratioVals.length/2)]).toFixed(1) : 0;

  res.json({
    protocol,
    device: { rows: ROWS, cols: COLS, label: `${ROWS}x${COLS} Organic Crossbar Array` },
    aggregate: {
      total_cells: ROWS * COLS,
      measured_cells: measured.length,
      switching_count: switching.length,
      yield_pct: yieldPct,
      median_vset,
      median_vreset,
      median_ratio,
      total_iv_files: measured.reduce((sum, c) => sum + c.n_files, 0)
    },
    materials: Array.from(new Set(cells.map(c => c.material)))
  });
});

// Page 3 API: `/api/protocol/<name>/heatmap`
app.get("/api/protocol/:name/heatmap", (req, res) => {
  const protocol = req.params.name;
  const metric = req.query.metric || "ratio"; // ratio, vset, vreset, yield, files
  const materialFilter = req.query.material || "";
  
  if (!cellDatabase[protocol]) {
    initDefaultProtocolData(protocol);
  }
  
  const grid = cellDatabase[protocol];
  const heatmapData: (number | null)[][] = [];
  const metadata: any[][] = [];
  
  for (let r = 0; r < ROWS; r++) {
    const rowHeat: (number | null)[] = [];
    const rowMeta: any[] = [];
    
    for (let c = 0; c < COLS; c++) {
      const cell = grid[r][c];
      const matchMaterial = !materialFilter || cell.material === materialFilter;
      
      if (!matchMaterial || cell.r_on === 0) {
        rowHeat.push(null);
        rowMeta.push({ cell: cell.cell, material: cell.material, n_files: 0, status: "Unmeasured" });
        continue;
      }
      
      let val: number | null = null;
      if (metric === "ratio") {
        val = cell.ratio;
      } else if (metric === "vset") {
        val = cell.switching ? cell.v_set : null;
      } else if (metric === "vreset") {
        val = cell.switching ? cell.v_reset : null;
      } else if (metric === "files") {
        val = cell.n_files;
      } else if (metric === "yield") {
        val = cell.switching ? 100 : 0;
      }
      
      rowHeat.push(val);
      rowMeta.push({
        cell: cell.cell,
        material: cell.material,
        n_files: cell.n_files,
        status: cell.switching ? "Active Switching" : "Non-Switching",
        v_set: cell.v_set,
        v_reset: cell.v_reset,
        r_on: cell.r_on,
        r_off: cell.r_off,
        ratio: cell.ratio
      });
    }
    heatmapData.push(rowHeat);
    metadata.push(rowMeta);
  }
  
  res.json({
    rows: ROWS,
    cols: COLS,
    metric,
    data: heatmapData,
    metadata
  });
});

// Page 3 API: `/api/protocol/<name>/device/<cell_id>/iv`
app.get("/api/protocol/:name/device/:cell_id/iv", (req, res) => {
  const protocol = req.params.name;
  const cellId = req.params.cell_id;
  
  let targetCell: CellStats | null = null;
  const grid = cellDatabase[protocol] || cellDatabase["1_iv-test"];
  
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      if (grid[r][c].cell === cellId) {
        targetCell = grid[r][c];
        break;
      }
    }
  }
  
  if (!targetCell) {
    return res.status(404).json({ error: `Cell ${cellId} not found` });
  }

  const sweeps = [];
  const sweepCount = targetCell.switching ? targetCell.n_files : 1;
  const cellVset = targetCell.switching ? targetCell.v_set : 2.0;
  const cellVreset = targetCell.switching ? targetCell.v_reset : -1.5;
  const cell_r_on = targetCell.r_on || 1000;
  const cell_r_off = targetCell.r_off || 200000;

  for (let s = 0; s < sweepCount; s++) {
    const voltages: number[] = [];
    const currents: number[] = [];
    
    const maxV = 3.0;
    const minV = -3.0;
    const steps = 40;
    
    const hrs_conduction = (V: number) => {
      const base = Math.sinh(2.0 * V) / (cell_r_off * 0.1);
      const linear = V / cell_r_off;
      return (linear + base * 0.05) * (1 + (Math.random() - 0.5) * 0.06);
    };
    
    const lrs_conduction = (V: number) => {
      return (V / cell_r_on) * (1 + (Math.random() - 0.5) * 0.03);
    };

    let state: "HRS" | "LRS" = "HRS";

    for (let i = 0; i <= steps; i++) {
      const v = +((maxV * i) / steps).toFixed(2);
      voltages.push(v);
      
      if (v >= cellVset && state === "HRS") {
        state = "LRS";
      }
      
      const current = state === "LRS" ? lrs_conduction(v) : hrs_conduction(v);
      currents.push(Math.abs(current) < 1e-12 ? 1e-12 : Math.abs(current));
    }

    for (let i = steps - 1; i >= 0; i--) {
      const v = +((maxV * i) / steps).toFixed(2);
      voltages.push(v);
      const current = state === "LRS" ? lrs_conduction(v) : hrs_conduction(v);
      currents.push(Math.abs(current) < 1e-12 ? 1e-12 : Math.abs(current));
    }

    for (let i = 1; i <= steps; i++) {
      const v = +((minV * i) / steps).toFixed(2);
      voltages.push(v);
      
      if (v <= cellVreset && state === "LRS") {
        state = "HRS";
      }
      
      const current = state === "LRS" ? lrs_conduction(v) : hrs_conduction(v);
      currents.push(Math.abs(current) < 1e-12 ? 1e-12 : Math.abs(current));
    }

    for (let i = steps - 1; i >= 0; i--) {
      const v = +((minV * i) / steps).toFixed(2);
      voltages.push(v);
      const current = state === "LRS" ? lrs_conduction(v) : hrs_conduction(v);
      currents.push(Math.abs(current) < 1e-12 ? 1e-12 : Math.abs(current));
    }

    sweeps.push({
      label: `Sweep #${String(s + 1).padStart(2, "0")}`,
      voltage: voltages,
      current: currents,
      v_set: targetCell.switching ? +(cellVset * (1 + (Math.random() - 0.5) * 0.05)).toFixed(2) : 0,
      v_reset: targetCell.switching ? +(cellVreset * (1 + (Math.random() - 0.5) * 0.05)).toFixed(2) : 0
    });
  }

  res.json({
    cell_id: cellId,
    row: targetCell.row,
    col: targetCell.col,
    material: targetCell.material,
    v_set: targetCell.v_set,
    v_reset: targetCell.v_reset,
    ratio: targetCell.ratio,
    switching: targetCell.switching,
    sweeps
  });
});

// Page 3 API: `/api/protocol/<name>/histograms`
app.get("/api/protocol/:name/histograms", (req, res) => {
  const protocol = req.params.name;
  
  if (!cellDatabase[protocol]) {
    initDefaultProtocolData(protocol);
  }
  
  const cells = cellDatabase[protocol].flat().filter(c => c.switching);
  const measured = cellDatabase[protocol].flat().filter(c => c.r_on > 0);
  
  const vsetCounts = [0, 0, 0, 0, 0, 0, 0];
  const vsetLabels = ["1.0-1.2", "1.2-1.5", "1.5-1.8", "1.8-2.1", "2.1-2.4", "2.4-2.7", "2.7+"];
  cells.forEach(c => {
    const v = c.v_set;
    if (v < 1.2) vsetCounts[0]++;
    else if (v < 1.5) vsetCounts[1]++;
    else if (v < 1.8) vsetCounts[2]++;
    else if (v < 2.1) vsetCounts[3]++;
    else if (v < 2.4) vsetCounts[4]++;
    else if (v < 2.7) vsetCounts[5]++;
    else vsetCounts[6]++;
  });

  const vresetCounts = [0, 0, 0, 0, 0, 0, 0];
  const vresetLabels = ["-1.0 to -1.2", "-1.2 to -1.4", "-1.4 to -1.6", "-1.6 to -1.8", "-1.8 to -2.0", "-2.0 to -2.2", "-2.2+"];
  cells.forEach(c => {
    const v = c.v_reset;
    if (v > -1.2) vresetCounts[0]++;
    else if (v > -1.4) vresetCounts[1]++;
    else if (v > -1.6) vresetCounts[2]++;
    else if (v > -1.8) vresetCounts[3]++;
    else if (v > -2.0) vresetCounts[4]++;
    else if (v > -2.2) vresetCounts[5]++;
    else vresetCounts[6]++;
  });

  const ratioCounts = [0, 0, 0, 0, 0, 0, 0];
  const ratioLabels = ["<10", "10-50", "50-100", "100-250", "250-500", "500-1000", "1000+"];
  measured.forEach(c => {
    const r = c.ratio;
    if (r < 10) ratioCounts[0]++;
    else if (r < 50) ratioCounts[1]++;
    else if (r < 100) ratioCounts[2]++;
    else if (r < 250) ratioCounts[3]++;
    else if (r < 500) ratioCounts[4]++;
    else if (r < 1000) ratioCounts[5]++;
    else ratioCounts[6]++;
  });

  res.json({
    vset: { bins: vsetLabels, counts: vsetCounts },
    vreset: { bins: vresetLabels, counts: vresetCounts },
    ratio: { bins: ratioLabels, counts: ratioCounts }
  });
});

// Serve Static Assets Folder using process.cwd()
app.use("/assets", express.static(path.join(process.cwd(), "assets")));

// Main physical routes
app.get("/", (req, res) => {
  res.sendFile(path.join(process.cwd(), "index.html"));
});

app.get("/gallery", (req, res) => {
  res.sendFile(path.join(process.cwd(), "gallery.html"));
});

app.get("/dashboard", (req, res) => {
  res.sendFile(path.join(process.cwd(), "dashboard.html"));
});

app.get("/dashboard/:protocol", (req, res) => {
  res.sendFile(path.join(process.cwd(), "dashboard.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running on port ${PORT}`);
});
