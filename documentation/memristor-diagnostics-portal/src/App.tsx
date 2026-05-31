import { useState, useMemo } from "react";
import { 
  Activity, 
  Cpu, 
  Layers, 
  FileSpreadsheet, 
  Sliders, 
  Info, 
  Lock, 
  Unlock, 
  Download, 
  FileText, 
  RefreshCw, 
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Grid,
  Sparkles,
  XCircle
} from "lucide-react";

// Standard Interface for project configuration
interface MemristorProject {
  id: string;
  name: string;
  materialStack: string;
  globalYield: number;
  devicesAnalyzed: number;
  volatileDetected: number;
  baseVset: number;
  baseVreset: number;
  baseOnOffRatio: number;
  baseHScore: number;
}

const PROJECTS: MemristorProject[] = [
  {
    id: "taox-hfo2",
    name: "TaOx/HfO2 Stack v4.2",
    materialStack: "Tantalum Oxide / Hafnium Oxide Bilayer",
    globalYield: 92.4,
    devicesAnalyzed: 1442,
    volatileDetected: 18,
    baseVset: 0.842,
    baseVreset: 0.115,
    baseOnOffRatio: 4.2,
    baseHScore: 88.42
  },
  {
    id: "tin-pcmo",
    name: "TiN/PCMO RRAM Stack v1.8",
    materialStack: "Titanium Nitride / Pr0.7Ca0.3MnO3 Manganite",
    globalYield: 81.6,
    devicesAnalyzed: 860,
    volatileDetected: 4,
    baseVset: 1.450,
    baseVreset: -1.120,
    baseOnOffRatio: 2.8,
    baseHScore: 72.15
  },
  {
    id: "zno-ftj",
    name: "ZnO-basedFTJ Synapse v2.1",
    materialStack: "Zinc Oxide Ferroelectric Tunnel Junction",
    globalYield: 95.1,
    devicesAnalyzed: 1200,
    volatileDetected: 0,
    baseVset: 2.100,
    baseVreset: -1.850,
    baseOnOffRatio: 5.1,
    baseHScore: 94.30
  },
  {
    id: "graphene-oxide",
    name: "Graphene Synapse v1.0",
    materialStack: "Graphene Oxide 2D Organic Layer",
    globalYield: 68.3,
    devicesAnalyzed: 512,
    volatileDetected: 37,
    baseVset: 0.620,
    baseVreset: -0.450,
    baseOnOffRatio: 1.9,
    baseHScore: 59.85
  }
];

export default function App() {
  const [activeProjectIdx, setActiveProjectIdx] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<string>("IV CURVES");
  const [activeProtocol, setActiveProtocol] = useState<string>("iv");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number }>({ row: 4, col: 2 });
  const [cycleFilter, setCycleFilter] = useState<string>("all");
  const [singleCycleVal, setSingleCycleVal] = useState<number>(500);
  const [currentScale, setCurrentScale] = useState<"log" | "linear_abs" | "linear">("log");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [customFilterText, setCustomFilterText] = useState<string>("10, 500");
  const [probeLocked, setProbeLocked] = useState<boolean>(true);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [heatmapSnapshotType, setHeatmapSnapshotType] = useState<string>("V_reset");

  // Dynamic customization of cell's specific properties
  // Users can edit specific parameters to simulate how a chip tuning step impacts characteristics!
  const [editedParams, setEditedParams] = useState<Record<string, { vSet?: number; vReset?: number }>>({});

  const currentProject = PROJECTS[activeProjectIdx];

  const t = useMemo(() => {
    const isL = theme === "light";
    return {
      bgRoot: isL ? "bg-slate-50 text-slate-800" : "bg-[#0A0A0B] text-slate-200",
      bgMain: isL ? "bg-white" : "bg-[#070708]",
      bgSidebar: isL ? "bg-slate-100 border-slate-200 text-slate-800" : "bg-black/20 border-white/5",
      borderSide: isL ? "border-slate-200" : "border-white/5",
      borderCol: isL ? "border-slate-200/60" : "border-white/10",
      bgCard: isL ? "bg-slate-50 border border-slate-200 shadow-xs" : "bg-black/40 border border-white/5",
      bgSubCard: isL ? "bg-slate-100/60 border border-slate-250" : "bg-black/25",
      textTitle: isL ? "text-slate-900" : "text-white",
      textDesc: isL ? "text-slate-500" : "text-slate-500",
      textMuted: isL ? "text-slate-500" : "text-slate-450",
      textBody: isL ? "text-slate-650" : "text-slate-350",
      bgHeader: isL ? "bg-slate-100 border-slate-200" : "bg-[#0c0c0d] border-b border-white/10",
      bgFooter: isL ? "bg-slate-100 border-t border-slate-200" : "bg-black border-t border-white/10",
      bgControl: isL ? "bg-slate-200/60 hover:bg-slate-200 border border-slate-300" : "bg-white/5 hover:bg-white/10 border border-white/10",
      bgLighter: isL ? "bg-slate-50" : "bg-white/5",
      graphBg: isL ? "bg-slate-50 border border-slate-200" : "bg-black/20 border-white/20",
      graphGridLine: isL ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.03)",
      graphZeroAxis: isL ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.15)",
      graphText: isL ? "#475569" : "#64748b",
      legendBg: isL ? "bg-white border border-slate-200 shadow-md text-slate-800" : "bg-black/75 backdrop-blur border border-white/10",
      tableHeaderBg: isL ? "bg-slate-100/80 border-b border-slate-250" : "bg-[#121214]",
      tableRowBorder: isL ? "border-slate-200" : "border-white/5",
      cellText: isL ? "text-slate-700" : "text-slate-400",
      inputBg: isL ? "bg-white border text-slate-900" : "bg-black border border-white/10 text-emerald-400",
    };
  }, [theme]);

  // Helper to generate seed for cellular attributes
  const getCellSeedData = (row: number, col: number, projectIdx: number) => {
    const s = (row * 6 + col) + (projectIdx * 13);
    const proj = PROJECTS[projectIdx];

    // Determine type classification
    let cellType = "Stable Analog RRAM";
    let classificationColor = "emerald";
    let detailMessage = "";
    let vSet = proj.baseVset;
    let vReset = proj.baseVreset;
    let onOff = proj.baseOnOffRatio;
    let hScore = proj.baseHScore;

    // We hardcode row 4, col 2 of the TaOx project to represent the volatile cell highlighted in the design draft:
    if (projectIdx === 0 && row === 4 && col === 2) {
      cellType = "Volatile Memristor";
      classificationColor = "amber";
      vSet = 0.842;
      vReset = 0.115;
      onOff = 4.2;
      hScore = 42.5;
      detailMessage = "Classification triggered by high SET yield (98%) and anomalous RESET instability (V_reset < 0.12V). Exhibits relaxation profile behavior.";
    } else if (s % 7 === 0) {
      cellType = "Stuck-ON (Ohmic)";
      classificationColor = "red";
      vSet = 0.05;
      vReset = 0.01;
      onOff = 0.2;
      hScore = 12.0;
      detailMessage = "Forming-induced electrical breakdown. Filament is irreversibly metallic. Ohmic conduction model dominant (I ∝ V). Device is unusable for memory applications.";
    } else if (s % 9 === 0) {
      cellType = "Stuck-OFF (Open)";
      classificationColor = "slate";
      vSet = 3.5;
      vReset = -3.5;
      onOff = 0.0;
      hScore = 5.4;
      detailMessage = "Severe delamination of electrode surfaces or local failure. No current response detected up to maximum safety threshold sweeps of 3.5V.";
    } else if (s % 5 === 0) {
      cellType = "Unstable Threshold Switch";
      classificationColor = "amber";
      vSet = proj.baseVset * 0.82 + (s % 5) * 0.05;
      vReset = Math.abs(proj.baseVreset) * 0.5 + (s % 3) * 0.04;
      onOff = proj.baseOnOffRatio + 0.5;
      hScore = 51.2;
      detailMessage = "Threshold switching switching profile with extremely rapid spontaneous filament rupture. Fails standard retention limits but useful for neural oscillators.";
    } else {
      // Healthy RRAM cell
      const offsetMultiplier = ((s % 10) - 5) / 10; // -0.5 to +0.5
      vSet = proj.baseVset + offsetMultiplier * (proj.baseVset * 0.15);
      vReset = proj.baseVreset + offsetMultiplier * (Math.abs(proj.baseVreset) * 0.15);
      onOff = proj.baseOnOffRatio + offsetMultiplier * 0.4;
      hScore = proj.baseHScore + offsetMultiplier * 5;
      if (hScore > 100) hScore = 99.1;
      if (hScore < 0) hScore = 10.0;
      detailMessage = `Normal analog resistive storage cell exhibiting clear set and reset thresholds. Excellent endurance reliability for neuromorphic weight-update crossbar operations.`;
    }

    // Apply manual user edits if they exist
    const cellKey = `${projectIdx}-${row}-${col}`;
    if (editedParams[cellKey]) {
      if (editedParams[cellKey].vSet !== undefined) {
        vSet = editedParams[cellKey].vSet!;
      }
      if (editedParams[cellKey].vReset !== undefined) {
        vReset = editedParams[cellKey].vReset!;
      }
      
      // Re-evaluate classification based on customized parameters
      if (vSet < 0.1 || (vReset >= 0 && vReset < 0.05)) {
        cellType = "Stuck-ON (Ohmic)";
        classificationColor = "red";
        hScore = 15.2;
        detailMessage = "Custom tune step created a short circuit state. Heavily degraded resistance state.";
      } else if (vSet > 3.0) {
        cellType = "Stuck-OFF (Open)";
        classificationColor = "slate";
        hScore = 8.5;
        detailMessage = "Custom tune step shifted SET requirement beyond normal voltage supply barriers.";
      } else if (vSet > 0 && vReset > 0 && vReset < 0.18) {
        cellType = "Volatile Memristor";
        classificationColor = "amber";
        hScore = 44.2;
        detailMessage = "Dynamic classification updated: Weak retention. Device shows relaxation properties at low voltages.";
      } else {
        cellType = "Stable Bipolar RRAM";
        classificationColor = "emerald";
        hScore = 91.8;
        detailMessage = "Dynamic classification updated: Tuned healthy bipolar resistive memory state.";
      }
    }

    return {
      row,
      col,
      cellType,
      classificationColor,
      vSet: parseFloat(vSet.toFixed(3)),
      vReset: parseFloat(vReset.toFixed(3)),
      onOff: parseFloat(onOff.toFixed(1)),
      hScore: parseFloat(hScore.toFixed(2)),
      detailMessage,
      seed: s
    };
  };

  const activeCellData = useMemo(() => {
    return getCellSeedData(selectedCell.row, selectedCell.col, activeProjectIdx);
  }, [selectedCell, activeProjectIdx, editedParams]);

  // Generate matrix for heatmap
  const cellsList = useMemo(() => {
    const list = [];
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 6; c++) {
        list.push(getCellSeedData(r, c, activeProjectIdx));
      }
    }
    return list;
  }, [activeProjectIdx, editedParams]);

  // Calculate dynamic statistics based on edited cells
  const dynamicGlobalYield = useMemo(() => {
    const totalSuccessful = cellsList.filter(c => c.cellType === "Stable Analog RRAM" || c.cellType === "Stable Bipolar RRAM").length;
    return parseFloat(((totalSuccessful / 36) * 100).toFixed(1));
  }, [cellsList]);

  const dynamicVolatiles = useMemo(() => {
    return cellsList.filter(c => c.cellType === "Volatile Memristor" || c.cellType === "Unstable Threshold Switch").length + (currentProject.id === "taox-hfo2" ? 14 : 2);
  }, [cellsList, currentProject]);

  // Generate dynamic hysteresis points for SVG IV curves plotting
  // Math formulation for high fidelity hysteresis simulation
  const generateHysteresisPoints = (cell: typeof activeCellData, cycleNum: number, noise: boolean) => {
    const pts: { v: number; i: number }[] = [];
    const pointsCount = 60;
    const vMax = Math.max(Math.abs(cell.vSet) * 1.5, 2.0);
    
    // Switch parameters based on type
    const isVolatile = cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold");
    const isStuckOn = cell.cellType.includes("Stuck-ON");
    const isStuckOff = cell.cellType.includes("Stuck-OFF");

    const vSetVoltage = cell.vSet;
    const vResetVoltage = cell.vReset;

    // Sweeping sequence: 0 -> Vmax -> 0 -> -Vmax -> 0
    const sweepVoltages: number[] = [];
    
    // Segment 1: 0 to Vmax
    for (let i = 0; i < pointsCount / 4; i++) {
      sweepVoltages.push((vMax * i) / (pointsCount / 4));
    }
    // Segment 2: Vmax to 0
    for (let i = 0; i < pointsCount / 4; i++) {
      sweepVoltages.push(vMax - (vMax * i) / (pointsCount / 4));
    }
    // Segment 3: 0 to -Vmax
    for (let i = 0; i < pointsCount / 4; i++) {
      sweepVoltages.push(-(vMax * i) / (pointsCount / 4));
    }
    // Segment 4: -Vmax to 0
    for (let i = 0; i < pointsCount / 4; i++) {
      sweepVoltages.push(-vMax + (vMax * i) / (pointsCount / 4));
    }

    let isLRS = false; // Low Resistance State

    sweepVoltages.forEach((v, index) => {
      let current = 0;
      
      const cycleSpreadCoeff = 1 + (Math.sin(cycleNum + index) * 0.08); // Slight organic dispersion
      let sVol = vSetVoltage * cycleSpreadCoeff;
      let rVol = vResetVoltage * cycleSpreadCoeff;

      if (isStuckOn) {
        current = v * 2.5; // Steep diagonal Ohmic
      } else if (isStuckOff) {
        current = v * 0.002; // Tiny leakage
      } else {
        // Normal switching mechanics
        if (v >= 0) {
          if (v > sVol) {
            isLRS = true; // Switched to ON
          }
          if (isLRS) {
            // Ohmic in LRS
            current = v * 1.8;
          } else {
            // Exponential Schottky/Fowler-Nordheim conduction in HRS
            current = Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 1.2) * 0.01, 0.4);
          }
        } else {
          // Negative voltage
          if (isVolatile) {
            // Volatiles release switching in zero region immediately, so they are always in HRS at negative unless threshold polarity is different.
            isLRS = false;
          } else {
            // Stable RRAM
            if (v < rVol) { // Reached reset threshold negative voltage
              isLRS = false; // Switched to OFF
            }
          }

          if (isLRS) {
            current = v * 1.8;
          } else {
            current = Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 0.9) * 0.015, 0.35);
          }
        }
      }

      // Add small simulated micro-noise
      if (noise) {
        const noiseAmt = 0.015 * (Math.random() - 0.5);
        current += noiseAmt;
      }
      
      pts.push({ v, i: current });
    });

    return pts;
  };

  // Convert points to SVG coordinates
  // Plotting region: X: 0 to 400 (corresponds to -3.0V to +3.0V), Y: 0 to 300 (corresponds to Logc/Linear current mapped appropriately)
  const mapPointsToSvg = (points: { v: number; i: number }[]) => {
    if (points.length === 0) return "";
    
    return points.map((p, idx) => {
      // Map V (-3 to +3) to X (20 to 380)
      const x = 200 + (p.v / 3.0) * 170;
      let y = 150;
      
      if (currentScale === "log") {
        // Log10 |I| scale
        // Y axis goes from log10(1uA)=-6 (bottom: 280) to log10(100mA)=-1 (top: 20)
        const absCurrent = Math.max(Math.abs(p.i), 1e-6);
        const logI = Math.log10(absCurrent);
        const percent = (logI - (-6)) / (-1 - (-6)); // 0 to 1
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      } else if (currentScale === "linear_abs") {
        // Absolute linear current |I|: 0A (bottom: 280) to 4.5A (top: 20)
        const absCurrent = Math.abs(p.i);
        const percent = absCurrent / 4.5;
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      } else {
        // Raw linear signed current I: -4.5A (bottom: 280) to +4.5A (top: 20)
        const percent = (p.i - (-4.5)) / (4.5 - (-4.5)); // 0 to 1
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      }
      
      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(" ");
  };

  const cycleTenPath = useMemo(() => {
    const pts = generateHysteresisPoints(activeCellData, 10, true);
    return mapPointsToSvg(pts);
  }, [activeCellData, currentScale]);

  const cycleFiveHundredPath = useMemo(() => {
    const pts = generateHysteresisPoints(activeCellData, 500, true);
    return mapPointsToSvg(pts);
  }, [activeCellData, currentScale]);

  // Noise / Background lines data
  const backgroundCyclesPaths = useMemo(() => {
    const pathsList = [];
    const cycleInds = [1, 2, 5, 25, 75, 150];
    for (const c of cycleInds) {
      const pts = generateHysteresisPoints(activeCellData, c, false);
      pathsList.push(mapPointsToSvg(pts));
    }
    return pathsList;
  }, [activeCellData, currentScale]);

  // Computed dynamic curves depending on selected filter modes (All, Single, Custom)
  const plotCurves = useMemo(() => {
    const list: { key: string; path: string; color: string; width: number; opacity: number; dash?: string }[] = [];
    
    if (cycleFilter === "all") {
      // Add background/dispersal noise cycles
      backgroundCyclesPaths.forEach((pth, i) => {
        list.push({
          key: `bg-${i}`,
          path: pth,
          color: theme === "light" ? "#94a3b8" : "#334155",
          width: 0.75,
          opacity: 0.35
        });
      });
      // Add Highlight Cycle 10 (emerald)
      list.push({
        key: 'cycle-10',
        path: cycleTenPath,
        color: theme === 'light' ? "#059669" : "#10b981",
        width: 2.0,
        opacity: 0.95
      });
      // Add Highlight Cycle 500 (indigo)
      list.push({
        key: 'cycle-500',
        path: cycleFiveHundredPath,
        color: theme === 'light' ? "#4f46e5" : "#6366f1",
        width: 1.8,
        opacity: 0.95
      });
    } else if (cycleFilter === "single") {
      // Compute single custom cycle from state
      const pts = generateHysteresisPoints(activeCellData, singleCycleVal, true);
      const pth = mapPointsToSvg(pts);
      list.push({
        key: `single-${singleCycleVal}`,
        path: pth,
        color: theme === 'light' ? "#059669" : "#10b981",
        width: 2.2,
        opacity: 1.0
      });
    } else if (cycleFilter === "custom") {
      // Custom parsing list
      const parts = customFilterText.split(",").map(p => parseInt(p.trim())).filter(num => !isNaN(num) && num >= 1);
      parts.forEach((c, i) => {
        const pts = generateHysteresisPoints(activeCellData, c, true);
        const pth = mapPointsToSvg(pts);
        const colorPalette = theme === 'light' 
          ? ["#059669", "#4f46e5", "#ea580c", "#d97706", "#c026d3"]
          : ["#10b981", "#6366f1", "#f97316", "#f59e0b", "#d946ef"];
        list.push({
          key: `custom-${c}-${i}`,
          path: pth,
          color: colorPalette[i % colorPalette.length],
          width: 2.0,
          opacity: 0.95
        });
      });
      // If empty layout, show at least cycle 10
      if (parts.length === 0) {
        list.push({
          key: 'fallback-custom',
          path: cycleTenPath,
          color: "#f59e0b",
          width: 2.0,
          opacity: 0.95,
          dash: "4,2"
        });
      }
    }
    
    return list;
  }, [activeCellData, cycleFilter, backgroundCyclesPaths, cycleTenPath, cycleFiveHundredPath, singleCycleVal, customFilterText, theme, currentScale]);

  // Adjust parameters manually
  const updateActiveCellParam = (field: "vSet" | "vReset", val: number) => {
    const key = `${activeProjectIdx}-${selectedCell.row}-${selectedCell.col}`;
    setEditedParams(prev => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: val
      }
    }));
  };

  // Preset quick adjustments to standard specs
  const resetCellParams = () => {
    const key = `${activeProjectIdx}-${selectedCell.row}-${selectedCell.col}`;
    setEditedParams(prev => {
      const updated = { ...prev };
      delete updated[key];
      return updated;
    });
  };

  const triggerExportTSV = () => {
    let tsv = "Cell_ID\tRow\tCol\tProject\tClassification\tV_set_Volt\tV_reset_Volt\tON_OFF_Ratio\tH_Score\n";
    cellsList.forEach((cell) => {
      tsv += `Cell_R${cell.row}C${cell.col}\t${cell.row}\t${cell.col}\t${currentProject.name}\t${cell.cellType}\t${cell.vSet}\t${cell.vReset}\t10^${cell.onOff}\t${cell.hScore}\n`;
    });

    const blob = new Blob([tsv], { type: "text/tab-separated-values" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Memristor_Diagnostic_Matrix_${currentProject.id}.tsv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div id="neurophase-root" className={`flex flex-col h-screen w-screen overflow-hidden ${t.bgRoot} transition-colors duration-250 select-none`}>
      
      {/* Header Navigation Area */}
      <header id="header-nav" className={`h-16 border-b transition-colors duration-250 ${t.bgHeader} backdrop-blur-md flex items-center justify-between px-6 shrink-0 z-10`}>
        <div id="header-brand" className="flex items-center space-x-4">
          <div id="brand-badge-container" className={`w-8 h-8 rounded-lg flex items-center justify-center ${theme === 'light' ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-500/20 border border-emerald-500/50'}`}>
            <div id="brand-indicator" className="w-4 h-4 rounded-sm bg-emerald-400 shadow-[0_0_8px_#10b981]"></div>
          </div>
          <div id="brand-labels">
            <h1 id="brand-title" className={`text-sm font-bold tracking-tight uppercase flex items-center gap-2 ${t.textTitle}`}>
              NeuroPhase-X1 <span className={`text-[9px] font-normal px-2 py-0.5 rounded-full ${theme === 'light' ? 'bg-slate-200 text-slate-700' : 'bg-white/10 text-slate-300'}`}>v4.2.1-live</span>
            </h1>
            <p id="brand-sub" className="text-[10px] text-slate-500 uppercase tracking-widest font-mono">Memristor Diagnostics Portal</p>
          </div>
        </div>
        
        <div id="header-tools" className="flex items-center space-x-6">
          {/* Two-mode Theme Toggle */}
          <div id="mode-selector-ring" className={`flex space-x-1 p-0.5 rounded-full border ${theme === 'light' ? 'bg-slate-200 border-slate-300' : 'bg-white/5 border-white/10'}`}>
            <button 
              id="btn-mode-light" 
              onClick={() => setTheme("light")} 
              className={`px-4 py-1 text-[10px] font-semibold rounded-full transition-all duration-200 cursor-pointer ${
                theme === "light" 
                  ? "bg-emerald-500 text-white shadow-xs font-bold" 
                  : "text-slate-400 hover:text-white"
              }`}
            >
              LIGHT
            </button>
            <button 
              id="btn-mode-dark" 
              onClick={() => setTheme("dark")} 
              className={`px-4 py-1 text-[10px] font-semibold rounded-full transition-all duration-200 cursor-pointer ${
                theme === "dark" 
                  ? "bg-slate-800 text-white shadow-xs font-bold" 
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              DARK
            </button>
          </div>
          
          <div id="user-avatar-housing" className={`flex items-center space-x-3 border-l pl-6 h-8 ${theme === 'light' ? 'border-slate-300' : 'border-white/10'}`}>
            <div className="text-right hidden sm:block">
              <p className={`text-[11px] font-medium ${t.textTitle}`}>nguyenxuantai.9a1</p>
              <p className="text-[9px] text-emerald-500 font-mono text-right">● Operator 01</p>
            </div>
            <div id="user-avatar" className="w-8 h-8 rounded-full bg-slate-800 border border-white/20 flex items-center justify-center overflow-hidden bg-gradient-to-tr from-slate-600 to-indigo-900">
              <span className="text-xs font-bold text-white uppercase">NT</span>
            </div>
          </div>
        </div>
      </header>

      {/* Primary Workspace Layout */}
      <div id="workspace-layout" className="flex flex-1 min-h-0 overflow-hidden">
        
        {/* Left Side Navigation Panel */}
        <aside id="sidebar-controls" className={`w-64 border-r p-4 flex flex-col space-y-6 shrink-0 overflow-y-auto transition-colors duration-250 ${t.bgSidebar}`}>
          
          <section id="project-section">
            <label id="project-lbl" className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Current Project</label>
            <div id="project-dropdown-container" className="relative group">
              <select 
                id="project-selector"
                value={activeProjectIdx}
                onChange={(e) => {
                  setActiveProjectIdx(parseInt(e.target.value));
                  // Auto reset selection if switching projects
                  setSelectedCell({ row: 4, col: 2 });
                }}
                className={`w-full p-2.5 text-xs font-semibold rounded-lg border shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all cursor-pointer appearance-none pr-8 ${
                  theme === 'light' ? 'bg-white border-slate-300 text-slate-800' : 'bg-white/5 border-white/10 text-white'
                }`}
              >
                {PROJECTS.map((proj, idx) => (
                  <option key={proj.id} value={idx} className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>
                    {proj.name}
                  </option>
                ))}
              </select>
              <div className="absolute right-3 top-3 pointer-events-none text-slate-400 text-[10px]">▼</div>
            </div>
            <div className={`p-3 rounded-b-lg border-x border-b ${theme === 'light' ? 'bg-slate-200/40 border-slate-300' : 'bg-emerald-500/5 border-white/5'}`}>
              <p className="text-[10px] font-medium text-slate-500 italic truncate">{currentProject.materialStack}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[9px] font-semibold text-slate-400">SYSTEM STATE</span>
                <p className="text-[10px] text-emerald-500 font-mono flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                  ● Active Acquisition
                </p>
              </div>
            </div>
          </section>
          
          <nav id="protocol-tree-nav" className="space-y-1">
            <label id="protocol-lbl" className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Protocol Tree</label>
            <div id="protocol-list" className="space-y-1.5 pl-1">
              
              <button 
                id="proto-sweep" 
                onClick={() => setActiveProtocol("iv")}
                className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                  activeProtocol === "iv" 
                    ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold" 
                    : (theme === "light" ? "text-slate-600 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                }`}
              >
                <span className="flex items-center gap-2"><Activity className="w-3.5 h-3.5" /> IV Sweep: 667-Cycle</span>
                <span className="text-[8px] opacity-75 font-mono tracking-tighter font-semibold">RUNNING</span>
              </button>

              <button 
                id="proto-endurance" 
                onClick={() => setActiveProtocol("endurance")}
                className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                  activeProtocol === "endurance"
                    ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold" 
                    : (theme === "light" ? "text-slate-650 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                }`}
              >
                <span className="flex items-center gap-2"><TrendingUp className="w-3.5 h-3.5" /> Pulsed Endurance</span>
                <span className="text-[8px] bg-[#6366f1]/15 text-[#6366f1] px-1 rounded-sm font-semibold">READY</span>
              </button>

              <button 
                id="proto-retention" 
                onClick={() => setActiveProtocol("retention")}
                className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                  activeProtocol === "retention"
                    ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold" 
                    : (theme === "light" ? "text-slate-650 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                }`}
              >
                <span className="flex items-center gap-2"><Layers className="w-3.5 h-3.5" /> Retention (85°C)</span>
                <span className="text-[8px] bg-amber-500/20 text-amber-600 px-1 rounded-sm font-semibold">TEMPERATE</span>
              </button>

              <button 
                id="proto-stability" 
                onClick={() => setActiveProtocol("stability")}
                className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                  activeProtocol === "stability"
                    ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold" 
                    : (theme === "light" ? "text-slate-650 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                }`}
              >
                <span className="flex items-center gap-2"><Grid className="w-3.5 h-3.5" /> Multi-Level Stability</span>
                <span className="text-[8px] bg-slate-300 text-slate-500 px-1 rounded-sm font-semibold">IDLE</span>
              </button>

            </div>
          </nav>

          {/* Moved Heatmap Explorer to Sidebar as per User Request */}
          <div id="heatmap-snapshot-block" className="space-y-3 pt-4 border-t border-slate-200/80 dark:border-white/5 mt-auto">
            <span id="snapshot-lbl" className="text-[10px] font-bold text-slate-500 dark:text-slate-400 font-mono tracking-wider block uppercase">Heatmap Explorer (6x6)</span>
            
            <div id="mini-grid" className={`grid grid-cols-6 gap-1 p-1.5 rounded-xl border transition-colors ${
              theme === 'light' ? 'bg-[#f2f2f7] border-slate-205 shadow-3xs' : 'bg-black/30 border-zinc-800/85'
            }`}>
              {cellsList.map((cell) => {
                const isSelected = selectedCell.row === cell.row && selectedCell.col === cell.col;
                let bg = "bg-emerald-500";
                if (cell.cellType.includes("Stuck-ON")) {
                  bg = "bg-red-500 shadow-[0_0_3.5px_#ef4444]";
                } else if (cell.cellType.includes("Stuck-OFF")) {
                  bg = "bg-slate-700 opacity-40";
                } else if (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold")) {
                  bg = "bg-amber-500 shadow-[0_0_3.5px_#f59e0b]";
                }
                
                return (
                  <button 
                    key={`mini-${cell.row}-${cell.col}`}
                    onClick={() => setSelectedCell({ row: cell.row, col: cell.col })}
                    className={`aspect-square w-full ${bg} ${isSelected ? (theme === 'light' ? "ring-2 ring-indigo-500 scale-110 shadow-xs" : "ring-2 ring-indigo-400 scale-110 shadow-xs") : ""} transition-all duration-150 rounded-md cursor-pointer`}
                    title={`Cell R${cell.row} C${cell.col}: ${cell.cellType}`}
                  />
                );
              })}
            </div>
            
            <div className="flex flex-col space-y-1">
              <span className={`text-[9px] font-mono uppercase font-semibold ${theme === 'light' ? 'text-slate-400' : 'text-zinc-500'}`}>Snap metric:</span>
              <select 
                value={heatmapSnapshotType} 
                onChange={(e) => setHeatmapSnapshotType(e.target.value)}
                className={`text-[10px] w-full px-2 py-1.5 outline-none font-sans cursor-pointer rounded-lg border transition-all ${
                  theme === 'light' 
                    ? 'bg-white border-slate-200/85 hover:border-slate-300 text-slate-700 font-semibold shadow-3xs' 
                    : 'bg-[#2c2c2e] border-zinc-700/65 text-zinc-100 hover:bg-zinc-700/80 font-medium'
                }`}
              >
                <option value="V_reset" className={theme === 'light' ? 'bg-white text-slate-800' : 'bg-[#1c1c1e] text-zinc-300'}>Median V_reset</option>
                <option value="V_set" className={theme === 'light' ? 'bg-white text-slate-800' : 'bg-[#1c1c1e] text-zinc-300'}>Median V_set</option>
                <option value="onOff" className={theme === 'light' ? 'bg-white text-slate-800' : 'bg-[#1c1c1e] text-zinc-300'}>ON/OFF state ratio</option>
              </select>
            </div>
          </div>

        </aside>

        {/* Central Workspace */}
        <main id="main-workspace" className={`flex-1 flex flex-col min-w-0 transition-colors duration-250 ${t.bgMain} overflow-y-auto`}>
          
          {/* Action Tabs and Search Control */}
          <div id="workspace-controls" className={`h-12 border-b flex items-center px-4 justify-between shrink-0 transition-colors duration-250 ${t.bgHeader}`}>
            <div id="tab-toggle-block" className="flex space-x-6 h-full items-center">
              <button 
                id="tab-btn-iv" 
                onClick={() => setActiveTab("IV CURVES")}
                className={`text-[10px] font-bold h-full border-b-2 px-1 transition-all cursor-pointer ${
                  activeTab === "IV CURVES" 
                    ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") 
                    : "text-slate-500 border-transparent hover:text-slate-300"
                }`}
              >
                IV CURVES
              </button>
              <button 
                id="tab-btn-crossbar" 
                onClick={() => setActiveTab("CROSSBAR MATRIX")}
                className={`text-[10px] font-bold h-full border-b-2 px-1 transition-all flex items-center gap-1.5 cursor-pointer ${
                  activeTab === "CROSSBAR MATRIX" 
                    ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") 
                    : "text-slate-500 border-transparent hover:text-slate-300"
                }`}
              >
                CROSSBAR MATRIX <span className="bg-emerald-500/10 text-emerald-500 px-1 py-0.2 text-[8px] rounded font-bold font-mono">6x6 Array</span>
              </button>
              <button 
                id="tab-btn-yield" 
                onClick={() => setActiveTab("YIELD METRICS")}
                className={`text-[10px] font-bold h-full border-b-2 px-1 transition-all cursor-pointer ${
                  activeTab === "YIELD METRICS" 
                    ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") 
                    : "text-slate-500 border-transparent hover:text-slate-300"
                }`}
              >
                YIELD METRICS
              </button>
            </div>
            
            <div id="cycle-filters" className="flex items-center space-x-3.5 flex-wrap">
              <span id="cycle-lbl" className="text-[10px] text-slate-500 uppercase font-mono">Overlay filter:</span>
              <div id="filter-btn-set" className={`flex p-0.5 rounded-lg border text-[9px] font-medium transition-all ${
                theme === 'light' ? 'bg-slate-100/90 border-slate-200/80 shadow-3xs' : 'bg-black/35 border-white/5'
              }`}>
                <button 
                  onClick={() => setCycleFilter("all")}
                  className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                    cycleFilter === "all" 
                      ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                      : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                  }`}
                >
                  OVERLAY ALL
                </button>
                <button 
                  onClick={() => setCycleFilter("single")}
                  className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                    cycleFilter === "single" 
                      ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                      : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                  }`}
                >
                  SINGLE CYCLE
                </button>
                <button 
                  onClick={() => setCycleFilter("custom")}
                  className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                    cycleFilter === "custom" 
                      ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                      : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                  }`}
                >
                  CUSTOM
                </button>
              </div>

              {/* Conditionally render helper input controls depending on selection */}
              {cycleFilter === "single" && (
                <div className={`flex items-center space-x-3.5 px-3 py-1 rounded-xl border ml-2 animate-fade-in ${
                  theme === 'light' ? 'bg-white border-slate-200/80 shadow-3xs' : 'bg-[#1c1c1e] border-white/5'
                }`}>
                  
                  {/* Click-based Counter Control */}
                  <div className={`flex items-center space-x-1 border rounded-lg overflow-hidden p-0.5 ${theme === 'light' ? 'border-slate-200/80 bg-slate-50' : 'border-white/10 bg-black/20'}`}>
                    <button 
                      onClick={() => setSingleCycleVal(prev => Math.max(1, prev - 1))}
                      className={`w-5 h-5 flex items-center justify-center text-[10px] font-bold rounded-md transition-colors cursor-pointer ${
                        theme === 'light' ? 'hover:bg-slate-200 text-slate-600' : 'hover:bg-white/10 text-slate-300'
                      }`}
                    >
                      -
                    </button>
                    <input 
                      type="number" 
                      min="1"
                      max="1000"
                      value={singleCycleVal}
                      onChange={(e) => {
                        const parsed = parseInt(e.target.value);
                        if (!isNaN(parsed)) setSingleCycleVal(Math.max(1, Math.min(1000, parsed)));
                      }}
                      className={`w-10 bg-transparent text-center text-[10px] outline-none font-semibold font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${
                        theme === 'light' ? 'text-slate-800' : 'text-emerald-450'
                      }`}
                    />
                    <button 
                      onClick={() => setSingleCycleVal(prev => Math.min(1000, prev + 1))}
                      className={`w-5 h-5 flex items-center justify-center text-[10px] font-bold rounded-md transition-colors cursor-pointer ${
                        theme === 'light' ? 'hover:bg-slate-200 text-slate-600' : 'hover:bg-white/10 text-slate-300'
                      }`}
                    >
                      +
                    </button>
                  </div>

                  {/* Horizontal Scroll Bar / Range Slider Selector */}
                  <div className="flex items-center space-x-2.5">
                    <span className="text-[8.5px] text-slate-400 font-mono tracking-tight">1</span>
                    <input 
                      type="range" 
                      min="1" 
                      max="1000" 
                      value={singleCycleVal} 
                      onChange={(e) => setSingleCycleVal(parseInt(e.target.value))}
                      className={`w-24 h-1 rounded-lg appearance-none cursor-pointer accent-emerald-500 ${
                        theme === 'light' ? 'bg-slate-200' : 'bg-zinc-800'
                      }`}
                    />
                    <span className="text-[8.5px] text-slate-400 font-mono tracking-tight">1k</span>
                    <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-md border transition-all ${
                      theme === 'light' 
                        ? 'text-emerald-750 bg-emerald-50/50 border-emerald-100' 
                        : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                    }`}>
                      C.{singleCycleVal}
                    </span>
                  </div>
                </div>
              )}

              {/* Custom list of comma-separated inputs */}
              {cycleFilter === "custom" && (
                <div className="flex items-center space-x-2 animate-fade-in">
                  <input 
                    type="text" 
                    value={customFilterText}
                    onChange={(e) => setCustomFilterText(e.target.value)}
                    placeholder="e.g. 10, 50, 500" 
                    className={`border px-3 py-1 text-[10px] w-32 outline-none font-mono focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/15 transition-all rounded-lg shadow-3xs ${
                      theme === 'light' 
                        ? 'bg-white border-slate-200/80 text-slate-800 placeholder-slate-400' 
                        : 'bg-[#1c1c1e] border-white/10 text-emerald-405 placeholder-slate-600'
                    }`}
                  />
                  <span className="text-[8px] text-slate-500 font-mono italic">comma list</span>
                </div>
              )}
            </div>
          </div>

          <div id="workspace-dynamic-core" className="flex-1 flex flex-col md:flex-row min-h-0">
            
            {/* Left Dynamic Section: Display depending on selection tab */}
            <div id="plot-viewport" className="flex-1 border-r border-white/5 relative p-6 flex flex-col">
              
              {activeTab === "IV CURVES" && (
                <div id="iv-curves-subview" className="flex-1 flex flex-col justify-between">
                  {/* Sweep Graph metadata header */}
                  <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
                    <div className="flex flex-col">
                      <span id="graph-coordinate-lbl" className="text-[10px] text-slate-500 font-mono">
                        {currentScale === "log" 
                          ? "Log10 |I| (A) vs. Applied Voltage V_appl (V)" 
                          : currentScale === "linear_abs" 
                            ? "Absolute Current |I| (A) vs. Applied Voltage V_appl (V)" 
                            : "Signed Current I (A) vs. Applied Voltage V_appl (V)"
                        }
                      </span>
                      <span className="text-[9px] text-emerald-500 font-semibold font-mono uppercase mt-0.5">
                        Active Mode: {currentScale === "log" ? "Logarithmic Magnitude" : currentScale === "linear_abs" ? "Absolute Magnitude Linear" : "Signed Linear Actual"}
                      </span>
                    </div>

                    {/* Highly interactive Scale selectors requested by user */}
                    <div id="scale-selectors" className={`flex p-0.5 rounded-lg border text-[9px] font-medium transition-colors ${
                      theme === 'light' ? 'bg-slate-100 border-slate-200/80 shadow-3xs' : 'bg-black/40 border-white/10'
                    }`}>
                      <button 
                        onClick={() => setCurrentScale("log")}
                        className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                          currentScale === "log" 
                            ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                            : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                        }`}
                      >
                        LOG CURRENT
                      </button>
                      <button 
                        onClick={() => setCurrentScale("linear_abs")}
                        className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                          currentScale === "linear_abs" 
                            ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                            : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                        }`}
                      >
                        ABS LINEAR (|I|)
                      </button>
                      <button 
                        onClick={() => setCurrentScale("linear_signed")}
                        className={`px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ${
                          currentScale === "linear_signed" 
                            ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') 
                            : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent')
                        }`}
                      >
                        ACTUAL CURRENT (Signed I)
                      </button>
                    </div>

                    <div className="flex gap-3 text-[9px] font-mono text-slate-400">
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-[#059669]"></span> Cycle 10
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-[#4f46e5]"></span> Cycle 500
                      </span>
                    </div>
                  </div>

                  {/* Interactive Dynamic Plot rendering using optimized pure responsive SVG vector paths */}
                  <div id="svg-graph-block" className={`flex-1 border-l border-b relative rounded-bl min-h-[300px] p-2 transition-colors duration-250 ${
                    theme === 'light' ? 'bg-slate-50/50 border-slate-350' : 'bg-black/20 border-white/20'
                  }`}>
                    
                    {/* SVG Graphic vector graph */}
                    <svg viewBox="0 0 400 300" className="w-full h-full" preserveAspectRatio="none">
                      {/* Sub-grid system lines */}
                      <g stroke={theme === 'light' ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.03)"} strokeWidth="0.5">
                        <line x1="0" y1="50" x2="400" y2="50" />
                        <line x1="0" y1="100" x2="400" y2="100" />
                        <line x1="0" y1="150" x2="400" y2="150" />
                        <line x1="0" y1="200" x2="400" y2="200" />
                        <line x1="0" y1="250" x2="400" y2="250" />
                        <line x1="66" y1="0" x2="66" y2="300" />
                        <line x1="133" y1="0" x2="133" y2="300" />
                        <line x1="200" y1="0" x2="200" y2="300" />
                        <line x1="266" y1="0" x2="266" y2="300" />
                        <line x1="333" y1="0" x2="333" y2="300" />
                      </g>

                      {/* Main Zero Axes in high panel visibility */}
                      <line x1="0" y1="150" x2="400" y2="150" stroke={theme === 'light' ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.15)"} strokeWidth="1" />
                      <line x1="200" y1="0" x2="200" y2="300" stroke={theme === 'light' ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.15)"} strokeWidth="1" />

                      {/* Tick Labels inside the plot directly */}
                      <text x="380" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="end">+3.0V</text>
                      <text x="20" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">-3.0V</text>
                      <text x="205" y="15" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "+1.5mA" : "Top (+100mA)"}</text>
                      <text x="205" y="295" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "-1.5mA" : "Bottom (1nA)"}</text>
                      
                      {/* Dynamic Theme-Aware Plot Curves */}
                      {plotCurves.map((curve) => (
                        <path 
                          key={curve.key} 
                          d={curve.path} 
                          fill="none" 
                          stroke={curve.color} 
                          strokeWidth={curve.width} 
                          opacity={curve.opacity}
                          strokeDasharray={curve.dash}
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          className="transition-all duration-300"
                        />
                      ))}
                    </svg>

                    {/* Interactive trace data-info overlay */}
                    <div id="interactive-legend-overlay" className="absolute bottom-4 right-4 bg-black/75 backdrop-blur border border-white/10 p-3 rounded-lg flex flex-col space-y-2 z-10 max-w-[180px]">
                      <div className="text-[9px] font-mono text-slate-400 pb-1 border-b border-white/5 uppercase">
                        Active Cell Coordinates
                      </div>
                      <div className="flex justify-between items-center text-[10px] font-mono gap-4">
                        <span className="text-slate-500">CELL ID:</span>
                        <span className="text-white font-bold">R({activeCellData.row}, C:{activeCellData.col})</span>
                      </div>
                      <div className="flex justify-between items-center text-[10px] font-mono">
                        <span className="text-slate-500">TYPE:</span>
                        <span className={`text-${activeCellData.classificationColor}-400 font-bold uppercase text-[9px]`}>{activeCellData.cellType}</span>
                      </div>
                      <div className="flex justify-between items-center text-[10px] font-mono">
                        <span className="text-slate-500">V_SWEEP RANGE:</span>
                        <span className="text-slate-300">-3V to +3V</span>
                      </div>
                    </div>

                    {!probeLocked && (
                      <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center text-center p-4">
                        <div className="max-w-[280px] bg-[#121214] border border-white/10 p-4 rounded-lg">
                          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2 animate-bounce" />
                          <p className="text-xs font-semibold text-white">PROBE IS RETRACTED</p>
                          <p className="text-[10px] text-slate-400 mt-1">Please lock microprobe arm onto contact pads to acquire active IV curves.</p>
                          <button 
                            onClick={() => setProbeLocked(true)} 
                            className="mt-3 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-[10px] font-bold text-white rounded transition-colors"
                          >
                            Lock Probe Arm Now
                          </button>
                        </div>
                      </div>
                    )}
                  </div>


                </div>
              )}

              {activeTab === "CROSSBAR MATRIX" && (
                <div id="crossbar-expanded-view" className="flex-1 flex flex-col justify-between">
                  <div>
                    <h3 className={`text-xs font-bold uppercase tracking-wider mb-1 font-mono ${
                      theme === 'light' ? 'text-slate-800' : 'text-white'
                    }`}>Crossbar Array Architecture (6x6 Sandbox)</h3>
                    <p className={`text-[10px] mb-4 uppercase ${
                      theme === 'light' ? 'text-slate-500' : 'text-slate-500'
                    }`}>Select cells in the grid to extract custom spectroscopic matrix configurations</p>
                  </div>

                  <div className={`grid grid-cols-6 gap-1.5 w-full max-w-[520px] mx-auto p-3 rounded-2xl border transition-all ${
                    theme === 'light' ? 'bg-[#f2f2f7] border-slate-200 shadow-3xs' : 'bg-[#1c1c1e] border-zinc-800'
                  }`}>
                    {cellsList.map((cell) => {
                      const isSelected = selectedCell.row === cell.row && selectedCell.col === cell.col;
                      let bgStyle = "";
                      
                      if (theme === 'light') {
                        if (cell.cellType.includes("Stuck-ON")) {
                          bgStyle = "bg-[#ff3b30] border-[#ff3b30] hover:bg-[#ff453a] text-white shadow-3xs";
                        } else if (cell.cellType.includes("Stuck-OFF")) {
                          bgStyle = "bg-[#8e8e93] border-[#8e8e93] hover:bg-[#a2a2a7] text-white/90";
                        } else if (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold")) {
                          bgStyle = "bg-[#ff9500] border-[#ff9500] hover:bg-[#ff9f0a] text-white shadow-3xs";
                        } else {
                          bgStyle = "bg-[#34c759] border-[#34c759] hover:bg-[#30d158] text-white shadow-3xs";
                        }
                      } else {
                        if (cell.cellType.includes("Stuck-ON")) {
                          bgStyle = "bg-[#ff453a] border-[#ff453a] hover:bg-[#ff5b54] text-white shadow-sm";
                        } else if (cell.cellType.includes("Stuck-OFF")) {
                          bgStyle = "bg-[#3a3a3c] border-[#48484a] hover:bg-[#48484a] text-zinc-400";
                        } else if (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold")) {
                          bgStyle = "bg-[#ff9f0a] border-[#ff9f0a] hover:bg-[#ffa924] text-black font-semibold shadow-sm";
                        } else {
                          bgStyle = "bg-[#30d158] border-[#30d158] hover:bg-[#34c759] text-black font-semibold shadow-sm";
                        }
                      }

                      return (
                        <button 
                          key={`${cell.row}-${cell.col}`}
                          onClick={() => setSelectedCell({ row: cell.row, col: cell.col })}
                          className={`aspect-square p-2 rounded-xl border text-center transition-all flex flex-col items-center justify-between cursor-pointer relative group ${bgStyle} ${
                            isSelected 
                              ? (theme === 'light' ? "ring-3 ring-indigo-500 scale-[1.04] z-10" : "ring-3 ring-indigo-400 scale-[1.04] z-10") 
                              : "border-transparent"
                          }`}
                        >
                          <div className={`text-[6.5px] font-bold font-mono absolute top-1 left-1.5 ${
                            cell.cellType.includes("Stuck-OFF") 
                              ? "text-slate-500 dark:text-zinc-500" 
                              : (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold") ? (theme === 'light' ? 'text-orange-950/50' : 'text-slate-800/60') : 'text-white/60 dark:text-black/50')
                          }`}>R{cell.row}</div>
                          <div className={`text-[6.5px] font-bold font-mono absolute top-1 right-1.5 ${
                            cell.cellType.includes("Stuck-OFF") 
                              ? "text-slate-500 dark:text-zinc-500" 
                              : (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold") ? (theme === 'light' ? 'text-orange-950/50' : 'text-slate-800/60') : 'text-white/60 dark:text-black/50')
                          }`}>C{cell.col}</div>
                          
                          <div className={`text-[10px] font-mono font-bold mt-2.5 ${
                            cell.cellType.includes("Stuck-OFF") 
                              ? "text-slate-100 dark:text-zinc-400" 
                              : (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold") ? (theme === 'light' ? 'text-white' : 'text-black') : 'text-white dark:text-black')
                          }`}>
                            {heatmapSnapshotType === "V_set" ? `${cell.vSet}V` : heatmapSnapshotType === "V_reset" ? `${cell.vReset}V` : `${cell.onOff}`}
                          </div>
                          
                          <span className={`text-[6px] uppercase tracking-tighter max-w-full truncate block scale-90 font-mono font-bold ${
                            cell.cellType.includes("Stuck-OFF") 
                              ? "text-slate-400 dark:text-zinc-500" 
                              : (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold") ? (theme === 'light' ? 'text-white/70' : 'text-slate-700') : 'text-white/70 dark:text-black/60')
                          }`}>
                            {cell.cellType.split(" ")[0]}
                          </span>

                          {/* Hover Tooltip showing precise parameters */}
                          <div className="pointer-events-none absolute z-20 bottom-full mb-1 left-1/2 -translate-x-1/2 bg-black border border-white/20 p-2 rounded text-left hidden group-hover:block whitespace-nowrap shadow-2xl">
                            <p className="text-[9px] font-mono font-bold text-white">Cell R{cell.row} C{cell.col}</p>
                            <p className="text-[8px] text-slate-400 font-mono mt-0.5">Type: {cell.cellType}</p>
                            <p className="text-[8px] text-slate-400 font-mono">V_set: {cell.vSet} V</p>
                            <p className="text-[8px] text-slate-400 font-mono">V_reset: {cell.vReset} V</p>
                            <p className="text-[8px] text-slate-400 font-mono">H-Score: {cell.hScore}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className={`p-3.5 rounded-xl mt-3 flex items-center justify-between border ${
                    theme === 'light' 
                      ? 'bg-indigo-50/20 border-indigo-150 text-slate-750 shadow-3xs' 
                      : 'bg-indigo-500/5 border-indigo-500/15 text-slate-300'
                  }`}>
                    <div>
                      <span className={`text-[9px] font-bold px-2 py-0.5 rounded font-mono uppercase border ${
                        theme === 'light' 
                          ? 'bg-indigo-50/50 text-indigo-700 border-indigo-200' 
                          : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                      }`}>Grid visualization mode</span>
                      <p className={`text-[10.5px] mt-1.5 leading-normal ${
                        theme === 'light' ? 'text-slate-600' : 'text-slate-400'
                      }`}>
                        Currently highlighting cells based on <span className={`font-mono font-bold text-xs ${
                          theme === 'light' ? 'text-indigo-900 border-b border-indigo-200/50' : 'text-white border-b border-white/10'
                        }`}>{heatmapSnapshotType === "V_reset" ? "Median V_reset" : heatmapSnapshotType === "V_set" ? "Median V_set" : "ON/OFF Ratio"}</span>. Stable analog states show as emerald, volatile memory behaves as amber, stuck junctions display as red or dark gray.
                      </p>
                    </div>
                    <div className="flex flex-col gap-0.5 shrink-0 ml-4 font-mono">
                      <span className="text-[8px] text-slate-500 uppercase">Legend:</span>
                      <span className="text-[8px] text-emerald-400 flex items-center gap-1">● Healthy: Stable RRAM</span>
                      <span className="text-[8px] text-amber-500 flex items-center gap-1">● Volatile: Decay Switch</span>
                      <span className="text-[8px] text-red-500 flex items-center gap-1">● Broken: Ohmic Shorted</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "YIELD METRICS" && (
                <div id="yield-metrics-subview" className="flex-1 flex flex-col space-y-4">
                  <div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-1 font-mono">Yield Metrics & Distribution Maps</h3>
                    <p className="text-[10px] text-slate-500 mb-2 uppercase">Device performance and reliability analysis profiles across tested junctions</p>
                  </div>

                  {/* Row 1: Histograms split into V_set and V_reset */}
                  <div id="yield-histogram-card" className="bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col space-y-3.5">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Spectroscopic Distribution</span>
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono mt-0.5">V_set & V_reset Threshold Histograms</h4>
                      </div>
                      <div className="text-[10px] text-emerald-400 font-mono font-medium">
                        N = {currentProject.devicesAnalyzed} Devices
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                      {/* V_set Histogram */}
                      <div id="vset-histogram" className="space-y-2">
                        <div className="flex justify-between text-[10px] font-mono select-none">
                          <span className="text-slate-400">V_set (Median: {activeCellData.vSet} V)</span>
                          <span className="text-emerald-450 font-bold">SET Yield: {activeCellData.cellType.includes("Stuck-ON") ? "10%" : "98.4%"}</span>
                        </div>
                        <div className="h-28 w-full relative border-l border-b border-white/10 p-1 bg-black/25 rounded-bl">
                          {/* SVG Render for Histogram */}
                          <svg className="w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="none">
                            {/* Grid lines */}
                            <line x1="0" y1="25" x2="200" y2="25" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="75" x2="200" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            {/* Dynamic Bars */}
                            {Array.from({ length: 12 }).map((_, idx) => {
                              const distFromCenter = idx - 5.5;
                              // Bell-curve distribution
                              const barHeight = Math.max(3, Math.round(92 * Math.exp(-Math.pow(distFromCenter, 2) / 7.5)));
                              const barY = 100 - barHeight;
                              const barX = idx * 16 + 4;
                              return (
                                <rect
                                  key={idx}
                                  x={barX}
                                  y={barY}
                                  width="12"
                                  height={barHeight}
                                  fill="#10b981"
                                  fillOpacity={idx === 5 || idx === 6 ? "0.8" : "0.3"}
                                  className="transition-all duration-500 hover:fill-opacity-100"
                                  rx="1"
                                />
                              );
                            })}
                            {/* Overlaid normal distribution analytical line */}
                            <path
                              d="M 4 98 Q 100 12, 196 98"
                              fill="none"
                              stroke="#10b981"
                              strokeWidth="1.2"
                              strokeDasharray="2,2"
                              opacity="0.75"
                            />
                          </svg>
                          {/* Labels */}
                          <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[8px] font-mono text-slate-500">
                            <span>{(activeCellData.vSet * 0.72).toFixed(2)}V</span>
                            <span>{activeCellData.vSet}V</span>
                            <span>{(activeCellData.vSet * 1.28).toFixed(2)}V</span>
                          </div>
                        </div>
                      </div>

                      {/* V_reset Histogram */}
                      <div id="vreset-histogram" className="space-y-2">
                        <div className="flex justify-between text-[10px] font-mono select-none">
                          <span className="text-slate-400">V_reset (Median: {activeCellData.vReset} V)</span>
                          <span className="text-indigo-400 font-bold">RESET Yield: {activeCellData.cellType.includes("Stuck-ON") ? "8%" : "98.2%"}</span>
                        </div>
                        <div className="h-28 w-full relative border-l border-b border-white/10 p-1 bg-black/25 rounded-bl">
                          <svg className="w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="none">
                            <line x1="0" y1="25" x2="200" y2="25" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="75" x2="200" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            {Array.from({ length: 12 }).map((_, idx) => {
                              const distFromCenter = idx - 6;
                              const barHeight = Math.max(3, Math.round(88 * Math.exp(-Math.pow(distFromCenter, 2) / 6)));
                              const barY = 100 - barHeight;
                              const barX = idx * 16 + 4;
                              return (
                                <rect
                                  key={idx}
                                  x={barX}
                                  y={barY}
                                  width="12"
                                  height={barHeight}
                                  fill="#6366f1"
                                  fillOpacity={idx === 6 ? "0.8" : "0.3"}
                                  className="transition-all duration-500 hover:fill-opacity-100"
                                  rx="1"
                                />
                              );
                            })}
                            {/* Overlaid normal distribution analytical line */}
                            <path
                              d="M 4 98 Q 104 15, 196 98"
                              fill="none"
                              stroke="#6366f1"
                              strokeWidth="1.2"
                              strokeDasharray="2,2"
                              opacity="0.75"
                            />
                          </svg>
                          <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[8px] font-mono text-slate-500">
                            <span>{(activeCellData.vReset - 0.35).toFixed(2)}V</span>
                            <span>{activeCellData.vReset}V</span>
                            <span>{(activeCellData.vReset + 0.35).toFixed(2)}V</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Row 2: Endurance Resistance vs Cycles */}
                  <div id="endurance-card" className="bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col space-y-3">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Reliability Spectroscopy</span>
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono mt-0.5">Resistance vs. Program Cycles (Endurance)</h4>
                      </div>
                      <div className="flex gap-4 text-[9px] font-mono text-slate-400">
                        <span className="flex items-center gap-1.1">
                          <span className="w-2.5 h-1 bg-emerald-400 rounded-sm"></span> LRS (R_on)
                        </span>
                        <span className="flex items-center gap-1.1">
                          <span className="w-2.5 h-1 bg-indigo-500 rounded-sm"></span> HRS (R_off)
                        </span>
                      </div>
                    </div>

                    <div className="h-32 w-full relative border-l border-b border-white/10 p-1 bg-black/25 rounded-bl">
                      <svg className="w-full h-full" viewBox="0 0 500 120" preserveAspectRatio="none">
                        {/* Horizontal log lines */}
                        <line x1="0" y1="20" x2="500" y2="20" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="40" x2="500" y2="40" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="60" x2="500" y2="60" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="80" x2="500" y2="80" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />

                        {/* Vertical log decades */}
                        <line x1="83" y1="0" x2="83" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="166" y1="0" x2="166" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="250" y1="0" x2="250" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="333" y1="0" x2="333" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="416" y1="0" x2="416" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />

                        {/* LRS Resistive Plot Line (Ohmic state, around 1 kΩ with slight dispersion noise) */}
                        <path
                          d="M 0 95 L 40 94 L 80 96 L 120 95 L 160 93 L 200 95 L 240 94 L 280 96 L 320 95 L 360 92 L 400 95 L 440 94 L 480 95 L 500 94"
                          fill="none"
                          stroke="#10b981"
                          strokeWidth="1.2"
                          opacity="0.95"
                        />
                        {/* Noise scatter overlay on LRS */}
                        {Array.from({ length: 14 }).map((_, idx) => {
                          const x = idx * 37 + 5;
                          const yOffset = Math.sin(idx * 8.5) * 1.8;
                          return (
                            <circle key={idx} cx={x} cy={95 + yOffset} r="1" fill="#10b981" opacity="0.5" />
                          );
                        })}

                        {/* HRS Resistive Plot Line (Dynamic OFF-state based on the active cell's state ratio) */}
                        {(() => {
                          const ratio = activeCellData.onOff;
                          // Standardize scaling ratio: target Y scales between 20 (high OFF resistance) and 80 (low OFF resistance)
                          const targetY = Math.max(15, 95 - (ratio * 14.5));
                          
                          let pthStr = `M 0 ${targetY}`;
                          const ptsList = [];
                          for (let i = 1; i <= 14; i++) {
                            const x = i * 36;
                            // Add memory fatigue degradation toward higher cycle numbers
                            const degradation = i > 10 ? (i - 10) * 1.6 : 0;
                            const y = targetY + Math.cos(i * 12.5) * 2.5 + degradation;
                            pthStr += ` L ${x} ${y}`;
                            ptsList.push({ x, y });
                          }
                          return (
                            <>
                              <path d={pthStr} fill="none" stroke="#6366f1" strokeWidth="1.2" opacity="0.95" />
                              {ptsList.map((pt, idx) => (
                                <circle key={idx} cx={pt.x} cy={pt.y} r="1" fill="#6366f1" opacity="0.5" />
                              ))}
                            </>
                          );
                        })()}
                      </svg>
                      {/* Subtitle labels */}
                      <div className="absolute top-1 left-2 text-[8px] font-mono text-slate-500">
                        Resistance R (Ω)
                      </div>
                      <div className="absolute bottom-1.5 left-2 right-2 flex justify-between text-[8px] font-mono text-slate-500">
                        <span>10⁰ (Cycle 1)</span>
                        <span>10¹</span>
                        <span>10²</span>
                        <span>10³</span>
                        <span>10⁴</span>
                        <span>10⁵</span>
                        <span>10⁶ (Limit)</span>
                      </div>

                      {/* Vertical logarithmic graduation ticks */}
                      <div className="absolute left-1 top-4 bottom-5 flex flex-col justify-between text-[7px] font-mono text-slate-600">
                        <span>10⁷ Ω</span>
                        <span>10⁶ Ω</span>
                        <span>10⁵ Ω</span>
                        <span>10⁴ Ω</span>
                        <span>10³ Ω</span>
                        <span>10² Ω</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </div>

            {/* Right Side: Diagnostics and Parameter Matrix Tables */}
            <div id="diagnostics-panel" className={`w-full md:w-80 p-5 overflow-y-auto flex flex-col space-y-6 shrink-0 border-t md:border-t-0 md:border-l transition-all duration-250 ${
              theme === 'light' 
                ? 'bg-[#fbfbfd] border-slate-200/80 text-slate-800' 
                : 'bg-black/40 border-white/5 text-slate-200'
            }`}>
              
              {/* Live Classification Diagnostics Panel */}
              <section id="classification-section">
                <label id="classification-lbl" className={`text-[10px] font-bold uppercase tracking-widest block mb-3 font-mono ${
                  theme === 'light' ? 'text-slate-400' : 'text-slate-500'
                }`}>Live Classification</label>
                
                <div id="classification-badge-container" className={`relative overflow-hidden group border p-4 rounded-xl transition-all ${
                  theme === 'light' 
                    ? (activeCellData.classificationColor === 'emerald' ? 'bg-emerald-50/45 border-emerald-200 shadow-3xs' :
                       activeCellData.classificationColor === 'red' ? 'bg-red-50/45 border-red-200 shadow-3xs' :
                       activeCellData.classificationColor === 'slate' ? 'bg-slate-50 border-slate-200 shadow-3xs' : 'bg-amber-50/45 border-amber-200 shadow-3xs')
                    : (activeCellData.classificationColor === 'emerald' ? 'bg-emerald-500/5 border-emerald-500/20' :
                       activeCellData.classificationColor === 'red' ? 'bg-red-500/5 border-red-500/20' :
                       activeCellData.classificationColor === 'slate' ? 'bg-white/5 border-white/10' : 'bg-amber-500/5 border-amber-500/20')
                }`}>
                  {/* Absolute glow decorative elements */}
                  <div className={`absolute top-0 right-0 w-24 h-24 rounded-full blur-xl pointer-events-none group-hover:scale-110 transition-transform ${
                    theme === 'light' ? 'bg-slate-500/5' : 'bg-amber-500/5'
                  }`}></div>
                  
                  <div className="flex justify-between items-start">
                    <div>
                      <span className={`px-2.5 py-0.5 text-[9px] font-bold rounded-md uppercase inline-block border ${
                        activeCellData.classificationColor === 'emerald' 
                          ? (theme === 'light' ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20") :
                        activeCellData.classificationColor === 'red' 
                          ? (theme === 'light' ? "bg-red-50 text-red-700 border-red-200" : "bg-red-500/10 text-red-400 border-red-500/20") :
                        activeCellData.classificationColor === 'slate' 
                          ? (theme === 'light' ? "bg-slate-100 text-slate-700 border-slate-200" : "bg-white/5 text-slate-400 border-white/10") : 
                        (theme === 'light' ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-amber-500/10 text-amber-400 border-amber-500/20")
                      }`}>
                        {activeCellData.cellType}
                      </span>
                      <h3 className={`text-lg font-semibold mt-2.5 leading-tight font-mono ${
                        theme === 'light' ? 'text-slate-900' : 'text-white'
                      }`}>Cell R({activeCellData.row}, C:{activeCellData.col})</h3>
                    </div>
                    
                    <div className={`w-9 h-9 border rounded-full flex items-center justify-center animate-pulse ${
                      activeCellData.classificationColor === 'emerald' ? "border-emerald-500/50 text-emerald-600 dark:text-emerald-400" :
                      activeCellData.classificationColor === 'red' ? "border-red-500/50 text-red-600 dark:text-red-400" :
                      activeCellData.classificationColor === 'slate' ? "border-slate-400/50 text-slate-600 dark:text-slate-400" : "border-amber-500/50 text-amber-600 dark:text-amber-450"
                    }`}>
                      <span className="text-xs font-bold font-mono">!</span>
                    </div>
                  </div>
                  
                  <p id="classification-message" className={`text-[11px] mt-3 leading-relaxed ${
                    theme === 'light' ? 'text-slate-600 font-medium' : 'text-slate-400'
                  }`}>
                    {activeCellData.detailMessage}
                  </p>
                </div>
              </section>

              {/* Parameter Matrix Table */}
              <section id="extractions-section" className="flex-1 flex flex-col min-h-0">
                <label id="extractions-lbl" className={`text-[10px] font-bold uppercase tracking-widest block mb-3 font-mono ${
                  theme === 'light' ? 'text-slate-400' : 'text-slate-500'
                }`}>Extraction Matrix</label>
                
                <div id="table-housing" className={`flex-1 border rounded-xl overflow-hidden flex flex-col transition-all duration-200 ${
                  theme === 'light' ? 'bg-white border-slate-250 hover:border-slate-300 shadow-3xs' : 'bg-[#1c1c1e]/40 border-zinc-800'
                }`}>
                  <table id="metrics-table" className="w-full text-left border-collapse">
                    <thead className={theme === 'light' ? 'bg-slate-50/80 border-b border-slate-200' : 'bg-[#121214]'}>
                      <tr className={`text-[9.5px] uppercase border-b font-mono tracking-wider ${
                        theme === 'light' ? 'text-slate-500 border-slate-200' : 'text-zinc-500 border-zinc-800'
                      }`}>
                        <th className="p-3 font-semibold">Spectroscopic Metric</th>
                        <th className="p-3 font-semibold text-right">Value</th>
                        <th className="p-3 font-semibold text-right">Dev Vol %</th>
                      </tr>
                    </thead>
                    <tbody className="text-xs font-mono">
                      
                      <tr className={`border-b transition-colors ${
                        theme === 'light' 
                          ? 'border-slate-100 hover:bg-slate-50/60' 
                          : 'border-zinc-850 hover:bg-white/5'
                      }`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-medium' : 'p-3 text-zinc-400'}>V_set (Volt)</td>
                        <td className="p-3 text-right text-emerald-600 dark:text-emerald-400 font-bold">{activeCellData.vSet}</td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.04</td>
                      </tr>
                      
                      <tr className={`border-b transition-colors ${
                        theme === 'light' 
                          ? 'border-slate-100 hover:bg-slate-50/60' 
                          : 'border-zinc-850 hover:bg-white/5'
                      }`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-medium' : 'p-3 text-zinc-400'}>V_reset (Volt)</td>
                        <td className={`p-3 text-right font-bold ${
                          activeCellData.vReset > 0 
                            ? (theme === 'light' ? 'text-amber-600' : 'text-amber-500') 
                            : (theme === 'light' ? 'text-indigo-600' : 'text-indigo-400')
                        }`}>
                          {activeCellData.vReset}
                        </td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.31</td>
                      </tr>

                      <tr className={`transition-colors ${
                        theme === 'light' 
                          ? 'hover:bg-slate-50/65' 
                          : 'hover:bg-white/5'
                      }`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-sans font-medium' : 'p-3 text-zinc-400 font-sans'}>R_on/R_off Ratio</td>
                        <td className={`p-3 text-right font-bold ${
                          theme === 'light' ? 'text-indigo-600' : 'text-indigo-400'
                        }`}>10^{activeCellData.onOff}</td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.82</td>
                      </tr>

                    </tbody>
                  </table>
                  
                  {/* Parameter Tuning feedback score */}
                  <div id="hpar-block" className={`mt-auto p-4 border-t transition-all ${
                    theme === 'light' ? 'bg-slate-50/50 border-slate-200' : 'bg-indigo-600/10 border-white/10 rounded-b-lg'
                  }`}>
                    <div className="flex justify-between items-center mb-1">
                      <span id="hpar-lbl" className="text-[10px] font-bold text-slate-400 tracking-wide font-mono">H-PARAMETER STATE</span>
                      <span id="hpar-val" className={`text-xs font-bold font-mono ${
                        theme === 'light' ? 'text-slate-800' : 'text-indigo-450'
                      }`}>{activeCellData.hScore} / 100</span>
                    </div>
                    <div id="progress-container" className={`w-full h-1.5 rounded-full overflow-hidden ${
                      theme === 'light' ? 'bg-slate-200' : 'bg-white/10'
                    }`}>
                      <div 
                        id="progress-bar"
                        style={{ width: `${activeCellData.hScore}%` }}
                        className={`h-full rounded-full transition-all duration-700 ${
                          theme === 'light' 
                            ? 'bg-indigo-600' 
                            : 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]'
                        }`}
                      ></div>
                    </div>
                    <div className="flex items-center justify-between text-[8px] text-slate-500 mt-2 font-mono">
                      <span>FORMING STATE</span>
                      <span className={activeCellData.hScore > 70 ? "text-emerald-600 font-bold" : "text-amber-500 font-bold"}>
                        {activeCellData.hScore > 70 ? "OPTIMIZED COUPLING" : "LOW STABILIZATION"}
                      </span>
                    </div>
                  </div>
                </div>
              </section>

            </div>
          </div>
        </main>
      </div>

      {/* Footer Mini-Dashboard Section */}
      <footer id="footer-matrix" className={`h-14 border-t flex flex-col sm:flex-row items-center px-6 shrink-0 z-10 select-none transition-colors duration-250 ${
        theme === 'light' 
          ? 'bg-[#fbfbfd] border-slate-200/80 text-slate-800' 
          : 'bg-[#121214] border-zinc-800/80 text-zinc-100'
      }`}>
        
        {/* Central stats overview */}
        <div id="global-stats" className="flex space-x-8">
          <div id="stat-yield" className="flex flex-col">
            <p id="stat-lbl-yield" className="text-[9px] font-bold text-slate-400 font-mono">GLOBAL YIELD</p>
            <p id="stat-val-yield" className="text-sm font-semibold text-emerald-600 dark:text-emerald-450 font-mono transition-all">
              {dynamicGlobalYield} <span className="text-[10px]">%</span>
            </p>
          </div>
          <div id="stat-analyzed" className="flex flex-col">
            <p id="stat-lbl-analyzed" className="text-[9px] font-bold text-slate-400 font-mono">DEVICES ANALYZED</p>
            <p id="stat-val-analyzed" className={`text-sm font-semibold font-mono ${theme === 'light' ? 'text-slate-800' : 'text-zinc-200'}`}>{currentProject.devicesAnalyzed}</p>
          </div>
          <div id="stat-volatile" className="flex flex-col">
            <p id="stat-lbl-volatiles" className="text-[9px] font-bold text-slate-500 font-mono text-left">VOLATILE DETECTED</p>
            <p id="stat-val-volatiles" className="text-sm font-semibold text-amber-500 font-mono text-left transition-all">{dynamicVolatiles}</p>
          </div>
        </div>

        {/* Right action control set - sleek and clean status as requested */}
        <div id="footer-actions" className="sm:ml-auto flex items-center space-x-2.5">
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest font-bold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-xs animate-pulse"></span> SYSTEM STATUS: ACTIVE
          </span>
        </div>
      </footer>

      {/* PDF diagnostic report builder popup modal */}
      {showReport && (
        <div id="report-modal" className="fixed inset-0 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-2xl bg-[#0d0d0f] border border-white/15 rounded-xl shadow-2xl p-6 relative flex flex-col max-h-[85vh] overflow-hidden select-text text-sm">
            
            {/* Modal header */}
            <div className="flex justify-between items-start pb-4 border-b border-white/10">
              <div>
                <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-widest font-mono">AUTOMATED BENCH ANALYSIS REPORT</span>
                <h3 className="text-lg font-bold text-white uppercase leading-tight font-sans">
                  TaOx / HfO2 Neuromorphic Crossbar Physical Characterization Sheet
                </h3>
              </div>
              <button 
                onClick={() => setShowReport(false)}
                className="p-1 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Modal interior scroll context */}
            <div className="flex-1 overflow-y-auto space-y-6 py-4 font-mono text-[11px] text-slate-300">
              
              <div className="bg-white/5 border border-white/5 rounded-lg p-3 grid grid-cols-2 gap-x-4 gap-y-2">
                <div>
                  <span className="text-slate-500 uppercase">Device ID:</span>{" "}
                  <span className="text-white font-bold">NP-X1-{currentProject.id.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Acquisition Time:</span>{" "}
                  <span className="text-white">2026-05-31 03:08:38 UTC</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Operator Code:</span>{" "}
                  <span className="text-white">nguyenxuantai.9a1@gmail.com</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Tested Crossbar Site:</span>{" "}
                  <span className="text-white">Silicon Die Block #B042</span>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-white uppercase border-b border-white/5 pb-1 mb-2 font-sans">
                  Abstract Narrative summary
                </h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  Bipolar resistive memories fabricated with a {currentProject.materialStack} architecture exhibit excellent switching distributions. A 6x6 test grid analysis shows a highly structured conductance model with {dynamicGlobalYield}% yield. There are a total of {cellsList.filter(c => c.cellType.includes("Stuck")).length} short/open circuit anomalies and {cellsList.filter(c => c.cellType.includes("Volatile")).length} volatile cells triggered on high reset sweep currents. Standard deviation deviations are well-constrained within the neuromorphic synaptic guidelines.
                </p>
              </div>

              <div>
                <h4 className="text-xs font-bold text-white uppercase border-b border-white/5 pb-1 mb-2 font-sans">
                  Cell Extract Diagnostics Spec Sheet (36 Test Blocks)
                </h4>
                <div className="border border-white/10 rounded overflow-hidden">
                  <table className="w-full text-left font-mono text-[10px] border-collapse">
                    <thead className="bg-white/5 text-slate-400 border-b border-white/10">
                      <tr>
                        <th className="p-2">Coordinate</th>
                        <th className="p-2">Electrode Class</th>
                        <th className="p-2 text-right">V_set</th>
                        <th className="p-2 text-right">V_reset</th>
                        <th className="p-2 text-right">Ratio</th>
                        <th className="p-2 text-right">H-Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cellsList.slice(0, 10).map((cell, idx) => (
                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                          <td className="p-2 text-white">R{cell.row}, C{cell.col}</td>
                          <td className={`p-2 font-bold text-${cell.classificationColor}-400`}>{cell.cellType}</td>
                          <td className="p-2 text-right text-emerald-400">{cell.vSet}V</td>
                          <td className="p-2 text-right text-indigo-400">{cell.vReset}V</td>
                          <td className="p-2 text-right">10^{cell.onOff}</td>
                          <td className="p-2 text-right text-white font-bold">{cell.hScore}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="p-2 bg-[#121214] text-[9px] text-slate-500 text-center">
                    Showing first 10 of 36 parameters. Complete matrix was successfully serialized to memory buffer.
                  </div>
                </div>
              </div>

              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between">
                <div>
                  <h5 className="font-bold text-white font-sans text-xs">Neuromorphic Synaptic Fitness Validation</h5>
                  <p className="text-[10px] text-slate-400 mt-0.5">Validated on cryogenic gate compliance updates.</p>
                </div>
                <span className="text-sm font-bold text-emerald-400 font-mono">PASS COMPLIANT</span>
              </div>
            </div>

            {/* Modal actions footer */}
            <div className="pt-4 border-t border-white/10 flex justify-end space-x-2 shrink-0">
              <button 
                onClick={() => {
                  triggerExportTSV();
                  alert("TSV completed. Check local downloads directory.");
                }} 
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-[11px] font-bold text-white rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" /> Download TSV Matrix
              </button>
              <button 
                onClick={() => {
                  alert("Export PDF payload initialized: 29.8 KB print stream sent.");
                  setShowReport(false);
                }} 
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-[11px] font-bold text-white rounded-lg transition-all shadow-[0_0_8px_rgba(16,185,129,0.4)] flex items-center gap-1.5 cursor-pointer"
              >
                <CheckCircle2 className="w-3.5 h-3.5" /> Finalize & Print Report
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
