import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";

// Mock directories support
const TARGET_WORKSPACE_DIR = "/Users/tai/workspace/projects/active_projects";
const LOCAL_WORKSPACE_DIR = path.join(process.cwd(), "active_projects");

// Check if we can use the requested target path, otherwise default to local
let rootWorkspacesDir = LOCAL_WORKSPACE_DIR;
try {
  if (fs.existsSync(TARGET_WORKSPACE_DIR)) {
    rootWorkspacesDir = TARGET_WORKSPACE_DIR;
  } else {
    fs.mkdirSync(LOCAL_WORKSPACE_DIR, { recursive: true });
  }
} catch (e) {
  // sandbox safe fallback
  try {
    fs.mkdirSync(LOCAL_WORKSPACE_DIR, { recursive: true });
  } catch(err){}
}

// Generate highly detailed mock files for memristor projects if they don't exist
const PROJECTS = [
  "res_internship",
  "non-res_odon-vallet",
  "non-res_phd-application",
  "test-project"
];

function ensureMockData() {
  PROJECTS.forEach(proj => {
    const projPath = path.join(rootWorkspacesDir, proj);
    if (!fs.existsSync(projPath)) {
      fs.mkdirSync(projPath, { recursive: true });
    }

    // Creating protocols
    const protocols = ["Forming_Sweep", "Endurance_Cycles", "Retention_Test", "IV_Characterization"];
    protocols.forEach(proto => {
      const protoPath = path.join(projPath, proto);
      if (!fs.existsSync(protoPath)) {
        fs.mkdirSync(protoPath, { recursive: true });
      }

      // Steps
      const steps = ["Step_1_Initial", "Step_2_Stress_Cycle", "Step_3_Final_Verification"];
      steps.forEach(step => {
        const stepPath = path.join(protoPath, step);
        if (!fs.existsSync(stepPath)) {
          fs.mkdirSync(stepPath, { recursive: true });
        }

        // Generate mock SVG plot files
        const fileNames = ["shaping_loop.svg", "current_voltage_sweep.svg", "resistance_vs_cycle.svg"];
        fileNames.forEach(fn => {
          const filePath = path.join(stepPath, fn);
          if (!fs.existsSync(filePath)) {
            const svgContent = `<?xml version="1.0" encoding="utf-8"?>
<svg viewBox="0 0 400 300" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#0a0f1d" />
  <grid stroke="#1e293b" stroke-width="1" />
  <path d="M 50,250 L 150,150 L 220,130 L 280,70 L 350,50" fill="none" stroke="#6366f1" stroke-width="3" />
  <circle cx="150" cy="150" r="5" fill="#ef4444" />
  <circle cx="280" cy="70" r="5" fill="#f59e0b" />
  <text x="50" y="30" font-family="'JetBrains Mono', monospace" font-size="12" fill="#94a3b8">${proj.toUpperCase()} - ${proto} - ${step}</text>
  <text x="160" y="155" font-family="'Inter', sans-serif" font-size="10" fill="#ef4444">Vset (1.5V)</text>
  <text x="290" y="75" font-family="'Inter', sans-serif" font-size="10" fill="#f59e0b">Vreset (-1.2V)</text>
  <text x="50" y="280" font-family="'Inter', sans-serif" font-size="9" fill="#64748b">File: ${fn}</text>
</svg>`;
            try {
              fs.writeFileSync(filePath, svgContent, "utf-8");
            } catch (err) {}
          }
        });
      });
    });
  });
}

try {
  ensureMockData();
} catch (e) {
  console.log("Mock data creation partial failure:", e);
}

// Generate device crossbar details
interface DeviceCell {
  cell: string;
  material: "HfOx" | "AlOx";
  switching: boolean;
  v_set: number;
  v_reset: number;
  ratio: number;
  file_count: number;
  yield: number;
}

const generateCrossbarData = (seed: string): DeviceCell[][] => {
  // Deterministic-like random seeding based on project/seed name
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  const seededRandom = () => {
    const x = Math.sin(hash++) * 10000;
    return x - Math.floor(x);
  };

  const matrix: DeviceCell[][] = [];
  for (let r = 1; r <= 6; r++) {
    const row: DeviceCell[] = [];
    for (let c = 1; c <= 6; c++) {
      const isAlOx = seededRandom() > 0.45;
      const switching = seededRandom() > 0.15; // 85% yield typical experimental
      const v_set = +(1.2 + seededRandom() * 1.5).toFixed(2);
      const v_reset = +(-0.5 - seededRandom() * 1.2).toFixed(2);
      const ratio = switching ? Math.floor(10 + seededRandom() * 9990) : 1;
      const file_count = Math.floor(5 + seededRandom() * 25);
      const devYield = switching ? Math.floor(75 + seededRandom() * 25) : 0;

      row.push({
        cell: `R${r}C${c}`,
        material: isAlOx ? "AlOx" : "HfOx",
        switching,
        v_set,
        v_reset,
        ratio,
        file_count,
        yield: devYield
      });
    }
    matrix.push(row);
  }
  return matrix;
};

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // Helper to extract project name from Query or Custom Headers
  const getProjectName = (req: express.Request): string => {
    let proj = (req.query.project as string) || (req.headers["x-project-override"] as string);
    if (!proj || !PROJECTS.includes(proj)) {
      proj = "res_internship"; // default fallback
    }
    return proj;
  };

  // Endpoint 1: GET /api/projects
  app.get("/api/projects", (req, res) => {
    try {
      res.json({
        workspace: rootWorkspacesDir,
        projects: PROJECTS
      });
    } catch (e) {
      res.status(500).json({ error: "Failed to read projects workspace" });
    }
  });

  // Endpoint 2: GET /api/project
  app.get("/api/project", (req, res) => {
    const proj = getProjectName(req);
    const projPath = path.join(rootWorkspacesDir, proj);

    try {
      const protocolsList: any[] = [];
      let totalFiles = 0;

      if (fs.existsSync(projPath)) {
        const folders = fs.readdirSync(projPath).filter(f => {
          return fs.statSync(path.join(projPath, f)).isDirectory();
        });

        folders.forEach(proto => {
          const protoPath = path.join(projPath, proto);
          const stepsList: any[] = [];
          let protoFileCount = 0;

          const steps = fs.readdirSync(protoPath).filter(sf => {
            return fs.statSync(path.join(protoPath, sf)).isDirectory();
          });

          steps.forEach(step => {
            const stepPath = path.join(protoPath, step);
            const stepFiles = fs.readdirSync(stepPath).filter(fl => {
              return fs.statSync(path.join(stepPath, fl)).isFile();
            });
            protoFileCount += stepFiles.length;
            stepsList.push({
              name: step,
              files: stepFiles.map(fn => ({
                name: fn,
                path: `${proj}/${proto}/${step}/${fn}`,
                type: fn.endsWith(".svg") ? "svg" : fn.endsWith(".pdf") ? "pdf" : "png"
              }))
            });
          });

          totalFiles += protoFileCount;

          // Compute overall mock protocol aggregates
          const matrix = generateCrossbarData(proj + "_" + proto);
          let activeCells = 0;
          let sumYield = 0;
          matrix.forEach(row => {
            row.forEach(cell => {
              if (cell.switching) activeCells++;
              sumYield += cell.yield;
            });
          });
          const avgYield = Math.round(sumYield / 36);

          protocolsList.push({
            name: proto,
            steps: stepsList,
            total_files: protoFileCount,
            measured_cells: activeCells,
            switching_yield: avgYield
          });
        });
      }

      res.json({
        project_name: proj,
        protocols: protocolsList,
        stats: {
          total_protocols: protocolsList.length,
          total_files: totalFiles
        }
      });
    } catch (e) {
      res.status(500).json({ error: "Failed to read project summary" });
    }
  });

  // Endpoint 3: GET /api/protocol/:protocol/files
  app.get("/api/protocol/:protocol/files", (req, res) => {
    const proj = getProjectName(req);
    const proto = req.params.protocol;
    const protoPath = path.join(rootWorkspacesDir, proj, proto);

    try {
      if (!fs.existsSync(protoPath)) {
        return res.status(404).json({ error: `Protocol ${proto} not found in project ${proj}` });
      }

      const stepsList: any[] = [];
      const steps = fs.readdirSync(protoPath).filter(sf => {
        return fs.statSync(path.join(protoPath, sf)).isDirectory();
      });

      steps.forEach(step => {
        const stepPath = path.join(protoPath, step);
        const stepFiles = fs.readdirSync(stepPath).filter(fl => {
          return fs.statSync(path.join(stepPath, fl)).isFile();
        });

        stepsList.push({
          name: step,
          files: stepFiles.map(fn => {
            const filePath = path.join(stepPath, fn);
            const stats = fs.statSync(filePath);
            return {
              name: fn,
              path: `${proj}/${proto}/${step}/${fn}`,
              type: fn.endsWith(".svg") ? "svg" : fn.endsWith(".pdf") ? "pdf" : "png",
              size: `${Math.round(stats.size / 102.4) / 10} KB`,
              created: stats.mtime.toISOString().substring(0, 10),
              dimensions: "1280x800 px" // simulated scientific chart dims
            };
          })
        });
      });

      res.json({
        protocol: proto,
        steps: stepsList
      });
    } catch (e) {
      res.status(500).json({ error: "Failed to read protocol files" });
    }
  });

  // Endpoint 4: GET /api/protocol/:protocol/summary
  app.get("/api/protocol/:protocol/summary", (req, res) => {
    const proj = getProjectName(req);
    const proto = req.params.protocol;
    const matrix = generateCrossbarData(proj + "_" + proto);

    let activeCount = 0;
    let sumVset = 0;
    let sumVreset = 0;
    let sumRatio = 0;
    let sumYield = 0;

    matrix.forEach(row => {
      row.forEach(cell => {
        sumYield += cell.yield;
        if (cell.switching) {
          activeCount++;
          sumVset += cell.v_set;
          sumVreset += cell.v_reset;
          sumRatio += cell.ratio;
        }
      });
    });

    res.json({
      protocol: proto,
      aggregate: {
        active_cells_ratio: `${activeCount}/36`,
        yield: +(sumYield / 36).toFixed(1),
        mean_vset: activeCount > 0 ? +(sumVset / activeCount).toFixed(2) : 0,
        mean_vreset: activeCount > 0 ? +(sumVreset / activeCount).toFixed(2) : 0,
        mean_ratio: activeCount > 0 ? Math.round(sumRatio / activeCount) : 0
      }
    });
  });

  // Endpoint 5: GET /api/protocol/:protocol/heatmap
  app.get("/api/protocol/:protocol/heatmap", (req, res) => {
    const proj = getProjectName(req);
    const proto = req.params.protocol;
    const metric = (req.query.metric as string) || "ratio"; // ratio, vset, vreset, file_count, yield
    const materialFilter = (req.query.material as string) || ""; // HfOx, AlOx, or empty

    const matrix = generateCrossbarData(proj + "_" + proto);

    const values = matrix.map(row => {
      return row.map(cell => {
        // Apply material filter
        if (materialFilter && cell.material.toLowerCase() !== materialFilter.toLowerCase()) {
          return null;
        }

        switch (metric) {
          case "vset":
            return cell.switching ? cell.v_set : null;
          case "vreset":
            return cell.switching ? Math.abs(cell.v_reset) : null;
          case "file_count":
            return cell.file_count;
          case "yield":
            return cell.yield;
          case "ratio":
          default:
            return cell.switching ? cell.ratio : null;
        }
      });
    });

    const metadata = matrix.map(row => {
      return row.map(cell => ({
        cell: cell.cell,
        material: cell.material,
        switching: cell.switching,
        ratio: cell.ratio,
        v_set: cell.v_set,
        v_reset: cell.v_reset,
        yield: cell.yield,
        file_count: cell.file_count
      }));
    });

    res.json({
      protocol: proto,
      metric,
      material: materialFilter || "All",
      data: values,
      metadata
    });
  });

  // Endpoint 6: GET /api/protocol/:protocol/device/:cell/iv
  app.get("/api/protocol/:protocol/device/:cell/iv", (req, res) => {
    const proj = getProjectName(req);
    const proto = req.params.protocol;
    const cellId = req.params.cell;

    const matrix = generateCrossbarData(proj + "_" + proto);
    let targetCell: DeviceCell | null = null;
    
    matrix.forEach(row => {
      row.forEach(c => {
        if (c.cell.toLowerCase() === cellId.toLowerCase()) {
          targetCell = c;
        }
      });
    });

    if (!targetCell) {
      return res.status(404).json({ error: `Cell ${cellId} not found` });
    }

    const { material, switching, v_set, v_reset, ratio } = targetCell as DeviceCell;

    // Generate high fidelity dual-sweep plotting points
    // Simulate cyclic resistance switching loops (hysteresis)
    const sweeps: any[] = [];
    const pointsCount = 60;
    
    if (switching) {
      // Sweep 1: Focus on continuous cycle (Set process)
      const volt1: number[] = [];
      const curr1: number[] = [];
      // Sweep from 0 to 3.0V then back to 0
      for (let i = 0; i <= pointsCount; i++) {
        const v = +( (i / (pointsCount/2)) * 1.5 ).toFixed(3);
        volt1.push(v);
        // Hysteresis curve logic
        const r_state = v < v_set ? 100000 : 100; // HRS -> LRS
        const current = (v / r_state) + (Math.random() * 1e-6);
        curr1.push(Math.abs(current));
      }

      // Sweep 2: Focus on Reset process (0 to -2.0V then back to 0)
      const volt2: number[] = [];
      const curr2: number[] = [];
      for (let i = 0; i <= pointsCount; i++) {
        const v = -( (i / (pointsCount/2)) * 1.0 ).toFixed(3);
        volt2.push(v);
        const r_state = v > v_reset ? 100 : 100000; // LRS -> HRS
        const current = (v / r_state) + (Math.random() * 1e-6);
        curr2.push(Math.abs(current));
      }

      sweeps.push({ label: "Set Sweep Cycle", voltage: volt1, current: curr1, v_set });
      sweeps.push({ label: "Reset Sweep Cycle", voltage: volt2, current: curr2, v_reset });
    } else {
      // Non switching / high resistance defect curves
      const volt: number[] = [];
      const curr: number[] = [];
      for (let i = -pointsCount/2; i <= pointsCount/2; i++) {
        const v = +( (i / (pointsCount/2)) * 2.0 ).toFixed(3);
        volt.push(v);
        const current = (v / 1e8) + (Math.random() * 1e-9); // pure Giga-ohm insulation
        curr.push(Math.abs(current));
      }
      sweeps.push({ label: "Defective Sweep", voltage: volt, current: curr });
    }

    res.json({
      cell_id: cellId,
      material,
      switching,
      v_set: switching ? v_set : null,
      v_reset: switching ? v_reset : null,
      ratio,
      sweeps
    });
  });

  // Endpoint 7: GET /api/protocol/:protocol/histograms
  app.get("/api/protocol/:protocol/histograms", (req, res) => {
    const proj = getProjectName(req);
    const proto = req.params.protocol;
    const matrix = generateCrossbarData(proj + "_" + proto);

    const vsets: number[] = [];
    const vresets: number[] = [];
    const ratios: number[] = [];

    matrix.forEach(row => {
      row.forEach(cell => {
        if (cell.switching) {
          vsets.push(cell.v_set);
          vresets.push(Math.abs(cell.v_reset));
          ratios.push(cell.ratio);
        }
      });
    });

    // Helper to generate simple bin groupings
    const binData = (arr: number[], numBins = 5) => {
      if (arr.length === 0) return { bins: [], counts: [] };
      const min = Math.min(...arr);
      const max = Math.max(...arr);
      const range = max - min;
      const binWidth = range / numBins;
      
      const counts = new Array(numBins).fill(0);
      const bins: string[] = [];

      for (let i = 0; i < numBins; i++) {
        const low = min + i * binWidth;
        const high = low + binWidth;
        bins.push(`${low.toFixed(1)}-${high.toFixed(1)}`);
      }

      arr.forEach(val => {
        let bIdx = Math.floor((val - min) / binWidth);
        if (bIdx >= numBins) bIdx = numBins - 1;
        if (bIdx < 0) bIdx = 0;
        counts[bIdx]++;
      });

      return { bins, counts };
    };

    res.json({
      protocol: proto,
      vset: binData(vsets),
      vreset: binData(vresets),
      ratio: binData(ratios.map(r => Math.log10(r))) // log ratio bins
    });
  });

  // Serve plots and data static files from workspace
  app.all("/files/*", (req, res) => {
    const filePath = req.params[0];
    const fullPath = path.join(rootWorkspacesDir, filePath);
    if (fs.existsSync(fullPath)) {
      res.sendFile(fullPath);
    } else {
      res.status(404).send("Scientific plot file not found");
    }
  });

  // Express Vite dev middleware routing
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server listening on public port ${PORT}`);
  });
}

startServer();
