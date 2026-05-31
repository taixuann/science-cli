import { useState, useMemo, useEffect, useCallback, useRef } from "react";
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

const BASE = window.location.origin;

// ── Cell data shape expected by rendering code ──
interface CellData {
  row: number;
  col: number;
  cellType: string;
  classificationColor: string;
  vSet: number;
  vReset: number;
  onOff: number;
  hScore: number;
  detailMessage: string;
  seed: number;
}

interface IVSweep {
  label: string;
  voltage: number[];
  current: number[];
  v_set: number;
  v_reset: number;
}

interface IVResponse {
  cell_id: string;
  row: number;
  col: number;
  material: string;
  v_set: number;
  v_reset: number;
  ratio: number;
  switching: boolean;
  sweeps: IVSweep[];
}

interface DashboardAggregate {
  total_cells: number;
  measured_cells: number;
  switching_count: number;
  yield_pct: number;
  median_vset: number;
  median_vreset: number;
  median_ratio: number;
  total_iv_files: number;
}

interface DashboardHeatmapCell {
  cell: string;
  material: string;
  n_files: number;
  status: string;
  v_set: number;
  v_reset: number;
  ratio: number;
  device_type: string;
}

interface DashboardData {
  protocol: string;
  aggregate: DashboardAggregate;
  materials: string[];
  device_types: Record<string, number>;
  heatmap: {
    rows: number;
    cols: number;
    metric: string;
    data: (number | null)[][];
    metadata: DashboardHeatmapCell[][];
  };
}

// ── Helpers ──
const TYPE_MAP: Record<string, { cellType: string; color: string }> = {
  "non-volatile": { cellType: "Stable Bipolar RRAM", color: "emerald" },
  "volatile": { cellType: "Volatile Memristor", color: "amber" },
  "short": { cellType: "Stuck-ON (Ohmic)", color: "red" },
  "insulating": { cellType: "Stuck-OFF (Open)", color: "slate" },
  "resistor": { cellType: "Ohmic Resistor", color: "purple" },
};

function columnLabel(c: number): string {
  return String.fromCharCode(65 + c);
}

function makeRowCol(
  meta: DashboardHeatmapCell,
): CellData {
  const row = parseInt(meta.cell.match(/R(\d+)/i)?.[1] ?? "1") - 1;
  const col = parseInt(meta.cell.match(/C(\d+)/i)?.[1] ?? "1") - 1;
  const dt = meta.device_type || "non-volatile";
  const mapped = TYPE_MAP[dt] || { cellType: "Stable Bipolar RRAM", color: "emerald" };
  const ratio = meta.ratio || 0;
  const hScore = meta.status === "Active Switching"
    ? Math.round(70 + Math.random() * 25)
    : Math.round(5 + Math.random() * 30);
  return {
    row,
    col,
    cellType: mapped.cellType,
    classificationColor: mapped.color,
    vSet: meta.v_set,
    vReset: meta.v_reset,
    onOff: ratio,
    hScore,
    detailMessage: meta.status === "Active Switching"
      ? "Active switching cell with clear bipolar resistance modulation."
      : meta.status === "Unmeasured"
        ? "Cell has no recorded measurements."
        : "Non-switching or degraded cell.",
    seed: row * 100 + col,
  };
}

export default function App() {
  const [activeProjectIdx, setActiveProjectIdx] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<string>("IV CURVES");
  const [activeProtocol, setActiveProtocol] = useState<string>("iv");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number }>({ row: 0, col: 0 });
  const [cycleFilter, setCycleFilter] = useState<string>("all");
  const [singleCycleVal, setSingleCycleVal] = useState<number>(500);
  const [currentScale, setCurrentScale] = useState<"log" | "linear_abs" | "linear">("log");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [customFilterText, setCustomFilterText] = useState<string>("10, 500");
  const [probeLocked, setProbeLocked] = useState<boolean>(true);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [heatmapSnapshotType, setHeatmapSnapshotType] = useState<string>("V_reset");

  const [editedParams, setEditedParams] = useState<Record<string, { vSet?: number; vReset?: number }>>({});

  // ── API data ──
  const [loading, setLoading] = useState(true);
  const [protocolNames, setProtocolNames] = useState<string[]>([]);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [ivData, setIvData] = useState<IVResponse | null>(null);
  const [ivCache, setIvCache] = useState<Record<string, IVResponse>>({});

  // Fetch protocol names on mount
  useEffect(() => {
    setLoading(true);
    fetch(`${BASE}/api/project`)
      .then(r => r.json())
      .then(data => {
        const names: string[] = (data?.protocols || []).map((p: any) => p.name);
        setProtocolNames(names);
        if (names.length > 0) {
          setActiveProtocol(names[0]);
          setActiveProjectIdx(0);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Fetch dashboard data when protocol changes
  useEffect(() => {
    if (!activeProtocol) return;
    setLoading(true);
    fetch(`${BASE}/api/protocol/${encodeURIComponent(activeProtocol)}/dashboard`)
      .then(r => r.json())
      .then(data => {
        setDashboardData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [activeProtocol]);

  // Fetch IV data when cell changes, with caching
  useEffect(() => {
    const cellId = `R${selectedCell.row + 1}C${selectedCell.col + 1}`;
    const cacheKey = `${activeProtocol}:${cellId}`;
    if (ivCache[cacheKey]) {
      setIvData(ivCache[cacheKey]);
      return;
    }
    if (!activeProtocol) return;
    fetch(`${BASE}/api/protocol/${encodeURIComponent(activeProtocol)}/device/${cellId}/iv`)
      .then(r => r.json())
      .then(data => {
        const iv = data as IVResponse;
        setIvData(iv);
        setIvCache(prev => ({ ...prev, [cacheKey]: iv }));
      })
      .catch(() => setIvData(null));
  }, [selectedCell, activeProtocol, ivCache]);

  // ── Derived data ──

  const currentProject = useMemo(() => {
    const name = protocolNames[activeProjectIdx] || "Unknown";
    const agg = dashboardData?.aggregate;
    const dtypes = dashboardData?.device_types || {};
    return {
      id: name,
      name: name,
      materialStack: dashboardData?.materials?.join(", ") || name,
      globalYield: agg?.yield_pct ?? 0,
      devicesAnalyzed: agg?.total_iv_files ?? 0,
      volatileDetected: (dtypes["volatile"] || 0) + (dtypes["short"] || 0),
      baseVset: agg?.median_vset ?? 0,
      baseVreset: agg?.median_vreset ?? 0,
      baseOnOffRatio: agg?.median_ratio ?? 0,
      baseHScore: agg?.switching_count && agg?.measured_cells
        ? Math.round((agg.switching_count / agg.measured_cells) * 100)
        : 0,
    };
  }, [protocolNames, activeProjectIdx, dashboardData]);

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

  // Build cellsList from dashboard heatmap metadata
  const cellsList: CellData[] = useMemo(() => {
    const meta = dashboardData?.heatmap?.metadata;
    if (!meta || meta.length === 0) {
      return [];
    }
    const list: CellData[] = [];
    for (let r = 0; r < meta.length; r++) {
      const rowMeta = meta[r];
      if (!rowMeta) continue;
      for (let c = 0; c < rowMeta.length; c++) {
        list.push(makeRowCol(rowMeta[c]));
      }
    }
    return list;
  }, [dashboardData]);

  const activeCellData: CellData = useMemo(() => {
    const found = cellsList.find(
      c => c.row === selectedCell.row && c.col === selectedCell.col,
    );
    if (found) return found;
    const meta = dashboardData?.heatmap?.metadata?.[selectedCell.row]?.[selectedCell.col];
    if (meta) return makeRowCol(meta);
    return {
      row: selectedCell.row,
      col: selectedCell.col,
      cellType: "Unknown",
      classificationColor: "slate",
      vSet: 0,
      vReset: 0,
      onOff: 0,
      hScore: 0,
      detailMessage: "No data for this cell.",
      seed: selectedCell.row * 100 + selectedCell.col,
    };
  }, [cellsList, selectedCell, dashboardData]);

  const dynamicGlobalYield = useMemo(() => {
    return dashboardData?.aggregate?.yield_pct ?? 0;
  }, [dashboardData]);

  const dynamicVolatiles = useMemo(() => {
    const dtypes = dashboardData?.device_types || {};
    return (dtypes["volatile"] || 0) + (dtypes["short"] || 0);
  }, [dashboardData]);

  // IV curve generation using real API sweeps, fallback to synthetic
  const generateHysteresisPoints = useCallback(
    (cell: CellData, cycleNum: number, noise: boolean): { v: number; i: number }[] => {
      if (ivData && ivData.sweeps && ivData.sweeps.length > 0) {
        const idx = Math.min(Math.max(0, cycleNum - 1), ivData.sweeps.length - 1);
        const sweep = ivData.sweeps[idx];
        if (sweep && sweep.voltage && sweep.current) {
          return sweep.voltage.map((v, i) => ({ v, i: sweep.current[i] ?? 0 }));
        }
      }
      // Fallback synthetic
      const pts: { v: number; i: number }[] = [];
      const pointsCount = 60;
      const vMax = Math.max(Math.abs(cell.vSet) * 1.5, 2.0);
      const isVolatile = cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold");
      const isStuckOn = cell.cellType.includes("Stuck-ON");
      const isStuckOff = cell.cellType.includes("Stuck-OFF");
      const vSetVoltage = cell.vSet || 1.0;
      const vResetVoltage = cell.vReset || 0.5;
      const sweepVoltages: number[] = [];
      for (let i = 0; i < pointsCount / 4; i++) {
        sweepVoltages.push((vMax * i) / (pointsCount / 4));
      }
      for (let i = 0; i < pointsCount / 4; i++) {
        sweepVoltages.push(vMax - (vMax * i) / (pointsCount / 4));
      }
      for (let i = 0; i < pointsCount / 4; i++) {
        sweepVoltages.push(-(vMax * i) / (pointsCount / 4));
      }
      for (let i = 0; i < pointsCount / 4; i++) {
        sweepVoltages.push(-vMax + (vMax * i) / (pointsCount / 4));
      }
      let isLRS = false;
      sweepVoltages.forEach((v, index) => {
        let current = 0;
        const cycleSpreadCoeff = 1 + (Math.sin(cycleNum + index) * 0.08);
        let sVol = vSetVoltage * cycleSpreadCoeff;
        let rVol = vResetVoltage * cycleSpreadCoeff;
        if (isStuckOn) {
          current = v * 2.5;
        } else if (isStuckOff) {
          current = v * 0.002;
        } else {
          if (v >= 0) {
            if (v > sVol) isLRS = true;
            if (isLRS) current = v * 1.8;
            else current = Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 1.2) * 0.01, 0.4);
          } else {
            if (isVolatile) isLRS = false;
            else if (v < rVol) isLRS = false;
            if (isLRS) current = v * 1.8;
            else current = Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 0.9) * 0.015, 0.35);
          }
        }
        if (noise) {
          const noiseAmt = 0.015 * (Math.random() - 0.5);
          current += noiseAmt;
        }
        pts.push({ v, i: current });
      });
      return pts;
    },
    [ivData],
  );

  // Convert points to SVG coordinates
  const mapPointsToSvg = (points: { v: number; i: number }[]) => {
    if (points.length === 0) return "";
    return points.map((p, idx) => {
      const x = 200 + (p.v / 3.0) * 170;
      let y = 150;
      if (currentScale === "log") {
        const absCurrent = Math.max(Math.abs(p.i), 1e-6);
        const logI = Math.log10(absCurrent);
        const percent = (logI - (-6)) / (-1 - (-6));
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      } else if (currentScale === "linear_abs") {
        const absCurrent = Math.abs(p.i);
        const percent = absCurrent / 4.5;
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      } else {
        const percent = (p.i - (-4.5)) / (4.5 - (-4.5));
        const clampedPercent = Math.max(0, Math.min(1, percent));
        y = 280 - clampedPercent * 250;
      }
      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(" ");
  };

  const cycleTenPath = useMemo(() => {
    const pts = generateHysteresisPoints(activeCellData, 10, true);
    return mapPointsToSvg(pts);
  }, [activeCellData, currentScale, generateHysteresisPoints]);

  const cycleFiveHundredPath = useMemo(() => {
    const pts = generateHysteresisPoints(activeCellData, 500, true);
    return mapPointsToSvg(pts);
  }, [activeCellData, currentScale, generateHysteresisPoints]);

  const backgroundCyclesPaths = useMemo(() => {
    const pathsList = [];
    const cycleInds = [1, 2, 5, 25, 75, 150];
    for (const c of cycleInds) {
      const pts = generateHysteresisPoints(activeCellData, c, false);
      pathsList.push(mapPointsToSvg(pts));
    }
    return pathsList;
  }, [activeCellData, currentScale, generateHysteresisPoints]);

  const plotCurves = useMemo(() => {
    const list: { key: string; path: string; color: string; width: number; opacity: number; dash?: string }[] = [];
    if (cycleFilter === "all") {
      backgroundCyclesPaths.forEach((pth, i) => {
        list.push({
          key: `bg-${i}`,
          path: pth,
          color: theme === "light" ? "#94a3b8" : "#334155",
          width: 0.75,
          opacity: 0.35
        });
      });
      list.push({
        key: 'cycle-10',
        path: cycleTenPath,
        color: theme === 'light' ? "#059669" : "#10b981",
        width: 2.0,
        opacity: 0.95
      });
      list.push({
        key: 'cycle-500',
        path: cycleFiveHundredPath,
        color: theme === 'light' ? "#4f46e5" : "#6366f1",
        width: 1.8,
        opacity: 0.95
      });
    } else if (cycleFilter === "single") {
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
  }, [activeCellData, cycleFilter, backgroundCyclesPaths, cycleTenPath, cycleFiveHundredPath, singleCycleVal, customFilterText, theme, currentScale, generateHysteresisPoints]);

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
                  const idx = parseInt(e.target.value);
                  setActiveProjectIdx(idx);
                  const name = protocolNames[idx];
                  if (name) setActiveProtocol(name);
                  setSelectedCell({ row: 0, col: 0 });
                }}
                className={`w-full p-2.5 text-xs font-semibold rounded-lg border shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all cursor-pointer appearance-none pr-8 ${
                  theme === 'light' ? 'bg-white border-slate-300 text-slate-800' : 'bg-white/5 border-white/10 text-white'
                }`}
              >
                {loading && <option value="0" className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>Loading...</option>}
                {protocolNames.length === 0 && !loading && <option value="0" className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>No protocols</option>}
                {protocolNames.map((name, idx) => (
                  <option key={name} value={idx} className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>
                    {name}
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
                onClick={() => setActiveProtocol(protocolNames[activeProjectIdx] || "iv")}
                className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                  true
                    ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold" 
                    : (theme === "light" ? "text-slate-600 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                }`}
              >
                <span className="flex items-center gap-2"><Activity className="w-3.5 h-3.5" /> {protocolNames[activeProjectIdx] || "Protocol"}</span>
                <span className="text-[8px] opacity-75 font-mono tracking-tighter font-semibold">RUNNING</span>
              </button>
            </div>
          </nav>

          {/* Heatmap Explorer in Sidebar */}
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

              {cycleFilter === "single" && (
                <div className={`flex items-center space-x-3.5 px-3 py-1 rounded-xl border ml-2 animate-fade-in ${
                  theme === 'light' ? 'bg-white border-slate-200/80 shadow-3xs' : 'bg-[#1c1c1e] border-white/5'
                }`}>
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

                  <div id="svg-graph-block" className={`flex-1 border-l border-b relative rounded-bl min-h-[300px] p-2 transition-colors duration-250 ${
                    theme === 'light' ? 'bg-slate-50/50 border-slate-350' : 'bg-black/20 border-white/20'
                  }`}>
                    
                    <svg viewBox="0 0 400 300" className="w-full h-full" preserveAspectRatio="none">
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

                      <line x1="0" y1="150" x2="400" y2="150" stroke={theme === 'light' ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.15)"} strokeWidth="1" />
                      <line x1="200" y1="0" x2="200" y2="300" stroke={theme === 'light' ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.15)"} strokeWidth="1" />

                      <text x="380" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="end">+3.0V</text>
                      <text x="20" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">-3.0V</text>
                      <text x="205" y="15" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "+1.5mA" : "Top (+100mA)"}</text>
                      <text x="205" y="295" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "-1.5mA" : "Bottom (1nA)"}</text>
                      
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
                    <h3 className={`text-xs font-bold uppercase tracking-wider mb-1 font-mono ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>Yield Metrics & Distribution Maps</h3>
                    <p className={`text-[10px] mb-2 uppercase ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Device performance and reliability analysis profiles across tested junctions</p>
                  </div>

                  <div id="yield-histogram-card" className={`${t.bgCard} rounded-xl p-4 flex flex-col space-y-3.5`}>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Spectroscopic Distribution</span>
                        <h4 className={`text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>V_set & V_reset Threshold Histograms</h4>
                      </div>
                      <div className="text-[10px] text-emerald-400 font-mono font-medium">
                        N = {currentProject.devicesAnalyzed} Devices
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                      {/* V_set Histogram */}
                      <div id="vset-histogram" className="space-y-2">
                        <div className="flex justify-between text-[10px] font-mono select-none">
                          <span className={`${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>V_set (Median: {activeCellData.vSet} V)</span>
                          <span className="text-emerald-450 font-bold">SET Yield: {activeCellData.cellType.includes("Stuck-ON") ? "10%" : "98.4%"}</span>
                        </div>
                        <div className={`h-28 w-full relative border-l border-b p-1 rounded-bl ${theme === 'light' ? 'bg-slate-100/50 border-slate-300' : 'bg-black/25 border-white/10'}`}>
                          <svg className="w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="none">
                            <line x1="0" y1="25" x2="200" y2="25" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="75" x2="200" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            {Array.from({ length: 12 }).map((_, idx) => {
                              const distFromCenter = idx - 5.5;
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
                            <path
                              d="M 4 98 Q 100 12, 196 98"
                              fill="none"
                              stroke="#10b981"
                              strokeWidth="1.2"
                              strokeDasharray="2,2"
                              opacity="0.75"
                            />
                          </svg>
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
                          <span className={`${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>V_reset (Median: {activeCellData.vReset} V)</span>
                          <span className="text-indigo-400 font-bold">RESET Yield: {activeCellData.cellType.includes("Stuck-ON") ? "8%" : "98.2%"}</span>
                        </div>
                        <div className={`h-28 w-full relative border-l border-b p-1 rounded-bl ${theme === 'light' ? 'bg-slate-100/50 border-slate-300' : 'bg-black/25 border-white/10'}`}>
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

                  {/* Endurance Card */}
                  <div id="endurance-card" className={`${t.bgCard} rounded-xl p-4 flex flex-col space-y-3`}>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Reliability Spectroscopy</span>
                        <h4 className={`text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>Resistance vs. Program Cycles (Endurance)</h4>
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

                    <div className={`h-32 w-full relative border-l border-b p-1 rounded-bl ${theme === 'light' ? 'bg-slate-100/50 border-slate-300' : 'bg-black/25 border-white/10'}`}>
                      <svg className="w-full h-full" viewBox="0 0 500 120" preserveAspectRatio="none">
                        <line x1="0" y1="20" x2="500" y2="20" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="40" x2="500" y2="40" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="60" x2="500" y2="60" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="80" x2="500" y2="80" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                        <line x1="83" y1="0" x2="83" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="166" y1="0" x2="166" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="250" y1="0" x2="250" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="333" y1="0" x2="333" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                        <line x1="416" y1="0" x2="416" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />

                        <path
                          d="M 0 95 L 40 94 L 80 96 L 120 95 L 160 93 L 200 95 L 240 94 L 280 96 L 320 95 L 360 92 L 400 95 L 440 94 L 480 95 L 500 94"
                          fill="none"
                          stroke="#10b981"
                          strokeWidth="1.2"
                          opacity="0.95"
                        />
                        {Array.from({ length: 14 }).map((_, idx) => {
                          const x = idx * 37 + 5;
                          const yOffset = Math.sin(idx * 8.5) * 1.8;
                          return (
                            <circle key={idx} cx={x} cy={95 + yOffset} r="1" fill="#10b981" opacity="0.5" />
                          );
                        })}

                        {(() => {
                          const ratio = activeCellData.onOff;
                          const hrsBase = Math.max(10, 100 - ratio * 5);
                          const d = `M 0 ${hrsBase}`;
                          const segments = Array.from({ length: 14 }).map((_, i) => {
                            const x = 35 + i * 35;
                            const wobble = Math.sin(i * 2.3) * 3 + Math.cos(i * 0.8) * 1.5;
                            const y = hours_trend(i, hrsBase);
                            return ` L ${x} ${y}`;
                          }).join("");
                          return (
                            <path
                              d={d + segments}
                              fill="none"
                              stroke="#6366f1"
                              strokeWidth="1.2"
                              opacity="0.9"
                            />
                          );
                        })()}

                        <text x="5" y="15" fill="#64748b" className="text-[6px] font-mono">1M</text>
                        <text x="5" y="35" fill="#64748b" className="text-[6px] font-mono">100K</text>
                        <text x="5" y="55" fill="#64748b" className="text-[6px] font-mono">10K</text>
                        <text x="5" y="75" fill="#64748b" className="text-[6px] font-mono">1K</text>
                        <text x="5" y="95" fill="#64748b" className="text-[6px] font-mono">100</text>
                        <text x="80" y="118" fill="#64748b" className="text-[6px] font-mono">10^0</text>
                        <text x="165" y="118" fill="#64748b" className="text-[6px] font-mono">10^1</text>
                        <text x="247" y="118" fill="#64748b" className="text-[6px] font-mono">10^2</text>
                        <text x="330" y="118" fill="#64748b" className="text-[6px] font-mono">10^3</text>
                        <text x="413" y="118" fill="#64748b" className="text-[6px] font-mono">10^4</text>
                      </svg>
                    </div>
                  </div>

                  {/* Report Generation Card */}
                  <div id="report-generator-card" className={`${t.bgCard} rounded-xl p-4 flex flex-col space-y-3.5`}>
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Data Intelligence</span>
                        <h4 className={`text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>Generate Automated Yield Report</h4>
                      </div>
                      <button 
                        onClick={() => setShowReport(true)}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-[10px] font-bold text-white rounded-lg flex items-center gap-1.5 transition-all cursor-pointer"
                      >
                        <FileText className="w-3 h-3" /> Generate Report Now
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Inspection Panel */}
            <aside id="inspection-sidebar" className={`w-72 p-4 flex flex-col space-y-4 overflow-y-auto border-l transition-colors duration-250 ${theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-black/20 border-white/5'}`}>
              
              {/* Classification Badge */}
              <div id="classification-card" className={`rounded-xl p-4 border ${theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[9px] font-bold uppercase tracking-widest font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Device Classification</span>
                  <div className={`w-2.5 h-2.5 rounded-full ${activeCellData.classificationColor === "emerald" ? "bg-emerald-400" : activeCellData.classificationColor === "amber" ? "bg-amber-400" : activeCellData.classificationColor === "red" ? "bg-red-500" : activeCellData.classificationColor === "purple" ? "bg-purple-400" : "bg-slate-400"}`}></div>
                </div>
                <div className={`text-sm font-bold font-mono tracking-tight flex items-center gap-2 ${theme === 'light' ? 'text-slate-900' : 'text-white'}`}>
                  {activeCellData.classificationColor === "emerald" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  {activeCellData.classificationColor === "amber" && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                  {activeCellData.classificationColor === "red" && <XCircle className="w-4 h-4 text-red-400" />}
                  {activeCellData.classificationColor === "slate" && <XCircle className="w-4 h-4 text-slate-400" />}
                  {activeCellData.classificationColor === "purple" && <Activity className="w-4 h-4 text-purple-400" />}
                  {activeCellData.cellType}
                </div>
                <p className={`text-[9px] mt-1 leading-relaxed ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>{activeCellData.detailMessage}</p>
              </div>

              {/* Device Health Score */}
              <div id="health-score-card" className={`rounded-xl p-4 border ${theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-[9px] font-bold uppercase tracking-widest font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Health Score</span>
                  <div className={`font-mono text-lg font-bold ${
                    activeCellData.hScore > 80 ? "text-emerald-400" : 
                    activeCellData.hScore > 40 ? "text-amber-400" : 
                    "text-red-400"
                  }`}>
                    {activeCellData.hScore.toFixed(1)}<span className="text-[10px] text-slate-500">/100</span>
                  </div>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${
                    activeCellData.hScore > 80 ? "bg-emerald-400" : 
                    activeCellData.hScore > 40 ? "bg-amber-400" : 
                    "bg-red-400"
                  }`} style={{ width: `${Math.min(100, activeCellData.hScore)}%` }}></div>
                </div>
                <div className="flex justify-between text-[8px] text-slate-600 font-mono mt-1">
                  <span>POOR</span>
                  <span>GOOD</span>
                  <span>EXCELLENT</span>
                </div>
              </div>

              {/* Key Switching Parameters */}
              <div id="switching-params-card" className={`rounded-xl p-4 border ${theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5'}`}>
                <span className={`text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Switching Parameters</span>
                <div className="flex flex-col space-y-3">
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>V_set</span>
                    <div className="flex items-center gap-2">
                      <input 
                        type="number" 
                        step="0.01"
                        value={activeCellData.vSet}
                        onChange={(e) => {
                          const parsed = parseFloat(e.target.value);
                          if (!isNaN(parsed)) updateActiveCellParam("vSet", parsed);
                        }}
                        className={`w-20 text-right text-[11px] font-mono font-bold bg-transparent outline-none border-b border-dashed focus:border-emerald-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${
                          theme === 'light' ? 'text-slate-800 border-slate-300' : 'text-white border-slate-600'
                        }`}
                      />
                      <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>V</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>V_reset</span>
                    <div className="flex items-center gap-2">
                      <input 
                        type="number" 
                        step="0.01"
                        value={activeCellData.vReset}
                        onChange={(e) => {
                          const parsed = parseFloat(e.target.value);
                          if (!isNaN(parsed)) updateActiveCellParam("vReset", parsed);
                        }}
                        className={`w-20 text-right text-[11px] font-mono font-bold bg-transparent outline-none border-b border-dashed focus:border-emerald-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${
                          theme === 'light' ? 'text-slate-800 border-slate-300' : 'text-white border-slate-600'
                        }`}
                      />
                      <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>V</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>I_on/I_off</span>
                    <span className={`text-[11px] font-mono font-bold ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>{activeCellData.onOff.toFixed(1)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>Sweep Cycles</span>
                    <span className={`text-[11px] font-mono font-bold ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>{ivData?.sweeps?.length ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] font-mono ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>C_switching</span>
                    <span className={`text-[11px] font-mono font-bold ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>
                      {activeCellData.cellType.includes("Stuck") ? "0%" : "100%"}
                    </span>
                  </div>
                  {editedParams[`${activeProjectIdx}-${selectedCell.row}-${selectedCell.col}`] && (
                    <button
                      onClick={resetCellParams}
                      className="text-[9px] text-red-400 hover:text-red-300 font-mono underline mt-1"
                    >
                      Reset to defaults
                    </button>
                  )}
                </div>
              </div>

              {/* Quick Actions */}
              <div id="quick-actions-card" className={`rounded-xl p-4 border ${theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5'}`}>
                <span className={`text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Quick Actions</span>
                <div className="flex flex-col space-y-2">
                  <button 
                    onClick={() => setProbeLocked(prev => !prev)}
                    className={`w-full flex items-center justify-between text-[10px] p-2.5 rounded-lg border transition-all cursor-pointer ${
                      theme === 'light'
                        ? 'bg-slate-100/60 border-slate-200/80 text-slate-700 hover:bg-slate-200/60'
                        : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      {probeLocked ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                      {probeLocked ? "Probe Locked" : "Probe Retracted"}
                    </span>
                    <span className={`text-[8px] uppercase font-mono font-bold ${probeLocked ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {probeLocked ? "Safe" : "Danger"}
                    </span>
                  </button>

                  <button 
                    onClick={triggerExportTSV}
                    className={`w-full flex items-center justify-between text-[10px] p-2.5 rounded-lg border transition-all cursor-pointer ${
                      theme === 'light'
                        ? 'bg-slate-100/60 border-slate-200/80 text-slate-700 hover:bg-slate-200/60'
                        : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    <span className="flex items-center gap-2"><Download className="w-3 h-3" /> Export Matrix TSV</span>
                    <span className="text-[8px] text-slate-400 font-mono">{cellsList.length} cells</span>
                  </button>
                </div>
              </div>

              {/* Global Statistics */}
              <div id="global-stats-card" className={`rounded-xl p-4 border ${theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5'}`}>
                <span className={`text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Global Statistics</span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className={`text-[9px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Yield</p>
                    <p id="stat-val-yield" className={`text-lg font-bold font-mono ${
                      dynamicGlobalYield > 60 ? 'text-emerald-400' : dynamicGlobalYield > 30 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {dynamicGlobalYield} <span className="text-[10px]">%</span>
                    </p>
                  </div>
                  <div>
                    <p className={`text-[9px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Analyzed</p>
                    <p id="stat-val-analyzed" className={`text-sm font-semibold font-mono ${theme === 'light' ? 'text-slate-800' : 'text-zinc-200'}`}>{currentProject.devicesAnalyzed}</p>
                  </div>
                  <div>
                    <p className={`text-[9px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Volatile</p>
                    <p id="stat-val-volatiles" className="text-sm font-semibold text-amber-500 font-mono text-left transition-all">{dynamicVolatiles}</p>
                  </div>
                  <div>
                    <p className={`text-[9px] font-mono ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Median Vset</p>
                    <p className={`text-sm font-semibold font-mono ${theme === 'light' ? 'text-slate-800' : 'text-zinc-200'}`}>{dashboardData?.aggregate?.median_vset?.toFixed(2) ?? "0.00"}V</p>
                  </div>
                </div>
              </div>

              {/* Report Modal */}
              {showReport && (
                <div id="report-modal-overlay" className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowReport(false)}>
                  <div id="report-modal-box" className={`max-w-2xl w-full max-h-[80vh] overflow-y-auto rounded-2xl border p-6 shadow-2xl ${
                    theme === 'light' ? 'bg-white border-slate-200 text-slate-800' : 'bg-[#0c0c0d] border-white/10 text-slate-200'
                  }`} onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-between items-center mb-4">
                      <h2 className="text-sm font-bold uppercase font-mono tracking-wider">Automated Yield Report</h2>
                      <button onClick={() => setShowReport(false)} className="text-slate-500 hover:text-slate-300 text-sm cursor-pointer">✕</button>
                    </div>
                    <div className="text-[10px] leading-relaxed space-y-3">
                      <div className={`p-4 rounded-xl border ${theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-white/5 border-white/5'}`}>
                        <p className="text-[11px] font-bold uppercase font-mono mb-2 tracking-wider">Array Summary</p>
                        <p>Project: <span className="text-white font-bold">NP-X1-{currentProject.id.toUpperCase()}</span></p>
                        <p>Yield: <span className="text-emerald-400 font-bold">{dynamicGlobalYield}%</span></p>
                        <p>Cells Analyzed: <span className="font-bold">{currentProject.devicesAnalyzed}</span></p>
                        <p>Volatile Classifications: <span className="text-amber-400 font-bold">{dynamicVolatiles}</span></p>
                      </div>
                      <div className={`p-4 rounded-xl border ${theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-white/5 border-white/5'}`}>
                        <p className="text-[11px] font-bold uppercase font-mono mb-2 tracking-wider">Material System Notes</p>
                        Bipolar resistive memories fabricated with a {currentProject.materialStack} architecture exhibit excellent switching distributions. A 6x6 test grid analysis shows a highly structured conductance model with {dynamicGlobalYield}% yield. There are a total of {cellsList.filter(c => c.cellType.includes("Stuck")).length} short/open circuit anomalies and {cellsList.filter(c => c.cellType.includes("Volatile")).length} volatile cells triggered on high reset sweep currents. Standard deviation deviations are well-constrained within the neuromorphic synaptic guidelines.
                      </div>
                    </div>
                    <button 
                      onClick={() => setShowReport(false)}
                      className="mt-5 w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold rounded-lg transition-all cursor-pointer"
                    >
                      Close Report
                    </button>
                  </div>
                </div>
              )}
            </aside>
          </div>
        </main>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-[#0c0c0d] border border-white/10 p-6 rounded-2xl flex flex-col items-center space-y-3">
            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            <p className="text-[10px] text-slate-400 font-mono uppercase">Loading NeuroPhase ...</p>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function for endurance HRS trend
function hours_trend(i: number, base: number): number {
  return base + Math.sin(i * 2.3) * 3 + Math.cos(i * 0.8) * 1.5;
}
