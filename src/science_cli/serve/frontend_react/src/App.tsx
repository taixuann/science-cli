import { useState, useMemo, useEffect, useCallback } from "react";
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

interface ProtocolInfo {
  name: string;
  technique: string;
  total_files: number;
  measured_cells: number;
  switching_yield: number;
}

interface ProjectInfo {
  project_name: string;
  protocols: ProtocolInfo[];
  stats: {
    total_protocols: number;
    total_files: number;
    total_cells_measured: number;
    overall_yield: number;
  };
}

interface CellMeta {
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
  device: { rows: number; cols: number; label: string };
  aggregate: {
    total_cells: number;
    measured_cells: number;
    switching_count: number;
    yield_pct: number;
    median_vset: number;
    median_vreset: number;
    median_ratio: number;
    total_iv_files: number;
  };
  materials: string[];
  device_types: Record<string, number>;
  heatmap: {
    rows: number;
    cols: number;
    metric: string;
    data: (number | null)[][];
    metadata: CellMeta[][];
  };
  histograms: {
    vset: { bins: string[]; counts: number[] };
    vreset: { bins: string[]; counts: number[] };
    ratio: { bins: string[]; counts: number[] };
  };
}

interface SweepData {
  label: string;
  voltage: number[];
  current: number[];
  v_set: number;
  v_reset: number;
}

interface IVData {
  cell_id: string;
  row: number;
  col: number;
  material: string;
  v_set: number;
  v_reset: number;
  ratio: number;
  switching: boolean;
  sweeps: SweepData[];
}

interface CellDisplay {
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

const DEVICE_TYPE_MAP: Record<string, { label: string; color: string; msg: string }> = {
  "non-volatile": {
    label: "Stable Bipolar RRAM",
    color: "emerald",
    msg: "Stable analog resistive storage cell with clear set/reset thresholds. Suitable for neuromorphic weight-update crossbar operations.",
  },
  "volatile": {
    label: "Volatile Memristor",
    color: "amber",
    msg: "Classification triggered by low Vreset and spontaneous relaxation profile. Exhibits threshold switching suitable for neural oscillators.",
  },
  "short": {
    label: "Stuck-ON (Ohmic)",
    color: "red",
    msg: "Forming-induced electrical breakdown. Filament is irreversibly metallic. Ohmic conduction model dominant (I ∝ V).",
  },
  "insulating": {
    label: "Stuck-OFF (Open)",
    color: "slate",
    msg: "No current response detected — severe delamination or local failure. Device is unusable for memory applications.",
  },
  "resistor": {
    label: "Ohmic Resistor",
    color: "purple",
    msg: "Linear I-V response with no switching. Classified as passive resistor element.",
  },
};

export default function App() {
  const [activeProtocolName, setActiveProtocolName] = useState<string>("");
  const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [ivData, setIVData] = useState<IVData | null>(null);
  const [loading, setLoading] = useState(true);

  const [activeTab, setActiveTab] = useState<string>("IV CURVES");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number }>({ row: 0, col: 0 });
  const [cycleFilter, setCycleFilter] = useState<string>("all");
  const [singleCycleVal, setSingleCycleVal] = useState<number>(1);
  const [currentScale, setCurrentScale] = useState<"log" | "linear_abs" | "linear_signed">("log");
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [customFilterText, setCustomFilterText] = useState<string>("1, 10, 50");
  const [probeLocked, setProbeLocked] = useState<boolean>(true);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [heatmapSnapshotType, setHeatmapSnapshotType] = useState<string>("V_reset");
  const [editedParams, setEditedParams] = useState<Record<string, { vSet?: number; vReset?: number }>>({});
  const [selectedSweepIdx, setSelectedSweepIdx] = useState<number>(0);
  const [histograms, setHistograms] = useState<{ vset: { bins: string[]; counts: number[] }; vreset: { bins: string[]; counts: number[] }; ratio: { bins: string[]; counts: number[] } } | null>(null);

  const protocolList = useMemo(() => projectInfo?.protocols ?? [], [projectInfo]);

  const sortedProtocolNames = useMemo(() =>
    [...protocolList].sort((a, b) => a.name.localeCompare(b.name)),
    [protocolList]
  );

  useEffect(() => {
    const ctrl = new AbortController();
    fetch("/api/project", { signal: ctrl.signal })
      .then(r => r.json())
      .then((data: ProjectInfo) => {
        setProjectInfo(data);
        if (data.protocols?.length > 0 && !activeProtocolName) {
          const first = data.protocols.sort((a, b) => a.name.localeCompare(b.name))[0];
          setActiveProtocolName(first.name);
        }
        setLoading(false);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!activeProtocolName) return;
    setLoading(true);
    const ctrl = new AbortController();
    Promise.all([
      fetch(`/api/protocol/${activeProtocolName}/dashboard`, { signal: ctrl.signal }).then(r => r.json()),
      fetch(`/api/protocol/${activeProtocolName}/histograms`, { signal: ctrl.signal }).then(r => r.json()),
    ])
      .then(([dash, hist]) => {
        setDashboardData(dash as DashboardData);
        setHistograms(hist as typeof histograms);
        const rows = (dash as DashboardData).device?.rows ?? 6;
        const cols = (dash as DashboardData).device?.cols ?? 6;
        setSelectedCell(prev => ({ row: Math.min(prev.row, rows - 1), col: Math.min(prev.col, cols - 1) }));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [activeProtocolName]);

  useEffect(() => {
    if (!activeProtocolName) return;
    const cellId = `R${selectedCell.row + 1}C${selectedCell.col + 1}`;
    const ctrl = new AbortController();
    fetch(`/api/protocol/${activeProtocolName}/device/${cellId}/iv`, { signal: ctrl.signal })
      .then(r => r.json())
      .then((data: IVData) => {
        setIVData(data);
        setSelectedSweepIdx(0);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [activeProtocolName, selectedCell.row, selectedCell.col]);

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

  const aggregate = dashboardData?.aggregate;
  const deviceTypes = dashboardData?.device_types ?? {};
  const heatmapMeta = dashboardData?.heatmap?.metadata ?? [];

  const deviceRows = dashboardData?.device?.rows ?? 6;
  const deviceCols = dashboardData?.device?.cols ?? 6;

  const currentProject = useMemo(() => ({
    id: projectInfo?.project_name ?? "unknown",
    name: activeProtocolName ? `${projectInfo?.project_name ?? ""} / ${activeProtocolName}` : projectInfo?.project_name ?? "No Project Open",
    materialStack: dashboardData?.materials?.join(", ") ?? "unknown",
    globalYield: aggregate?.yield_pct ?? 0,
    devicesAnalyzed: aggregate?.total_cells ?? 0,
    volatileDetected: deviceTypes["volatile"] ?? 0,
    baseVset: aggregate?.median_vset ?? 0,
    baseVreset: aggregate?.median_vreset ?? 0,
    baseOnOffRatio: aggregate?.median_ratio ?? 0,
    baseHScore: Math.min(100, Math.round((aggregate?.yield_pct ?? 0) * 0.85 + 10)),
  }), [projectInfo, activeProtocolName, dashboardData, aggregate, deviceTypes]);

  const getCellDisplay = useCallback((row: number, col: number): CellDisplay => {
    const meta = heatmapMeta[row]?.[col];
    const dt = meta?.device_type ?? "non-volatile";
    const mapping = DEVICE_TYPE_MAP[dt] ?? DEVICE_TYPE_MAP["non-volatile"];

    const cellKey = `${activeProtocolName}-${row}-${col}`;
    const edits = editedParams[cellKey];
    let vSet = meta?.v_set ?? 0;
    let vReset = meta?.v_reset ?? 0;
    let ratio = meta?.ratio ?? 0;
    let cellType = mapping.label;
    let color = mapping.color;
    let msg = mapping.msg;

    if (edits) {
      if (edits.vSet !== undefined) vSet = edits.vSet;
      if (edits.vReset !== undefined) vReset = edits.vReset;
      if (vSet < 0.1 || (vReset >= 0 && vReset < 0.05)) {
        cellType = "Stuck-ON (Ohmic)"; color = "red";
        msg = "Custom tune: short circuit state.";
      } else if (vSet > 3.0) {
        cellType = "Stuck-OFF (Open)"; color = "slate";
        msg = "Custom tune: SET beyond normal range.";
      } else if (vSet > 0 && vReset > 0 && vReset < 0.18) {
        cellType = "Volatile Memristor"; color = "amber";
        msg = "Dynamic: weak retention.";
      } else {
        cellType = "Stable Bipolar RRAM"; color = "emerald";
        msg = "Dynamic: healthy bipolar state.";
      }
    }

    const nCells = deviceRows * deviceCols;
    const hScore = meta
      ? Math.min(100, Math.round(
          (vSet > 0 && vSet < 3 ? 30 : 0) +
          (Math.abs(vReset) > 0.1 ? 25 : 0) +
          (ratio > 1 ? 20 : 0) +
          (meta.status === "Active Switching" ? 15 : 0) +
          10
        ))
      : 0;

    return {
      row, col,
      cellType,
      classificationColor: color,
      vSet: parseFloat(vSet.toFixed(3)),
      vReset: parseFloat(vReset.toFixed(3)),
      onOff: parseFloat(ratio.toFixed(1)),
      hScore,
      detailMessage: msg,
      seed: row * 7 + col * 13,
    };
  }, [heatmapMeta, editedParams, activeProtocolName, deviceRows, deviceCols]);

  const activeCellData = useMemo(() => {
    return getCellDisplay(selectedCell.row, selectedCell.col);
  }, [selectedCell, getCellDisplay]);

  const cellsList = useMemo(() => {
    const list: CellDisplay[] = [];
    for (let r = 0; r < deviceRows; r++) {
      for (let c = 0; c < deviceCols; c++) {
        list.push(getCellDisplay(r, c));
      }
    }
    return list;
  }, [deviceRows, deviceCols, getCellDisplay]);

  const dynamicGlobalYield = useMemo(() => {
    const total = cellsList.length;
    if (total === 0) return 0;
    const ok = cellsList.filter(c =>
      c.cellType.includes("Bipolar") || c.cellType.includes("Analog") || c.cellType.includes("RRAM")
    ).length;
    return parseFloat(((ok / total) * 100).toFixed(1));
  }, [cellsList]);

  const dynamicVolatiles = useMemo(() => {
    return cellsList.filter(c =>
      c.cellType.includes("Volatile") || c.cellType.includes("Threshold")
    ).length;
  }, [cellsList]);

  const activeSweeps = useMemo(() => {
    if (!ivData?.sweeps || ivData.sweeps.length === 0) return [];
    return ivData.sweeps;
  }, [ivData]);

  const generateHysteresisPoints = useCallback((sweep: SweepData, cycleNum: number, noise: boolean) => {
    if (sweep.voltage.length > 0 && sweep.current.length > 0) {
      const pts = sweep.voltage.map((v, i) => ({
        v,
        i: noise
          ? sweep.current[i] + (Math.random() - 0.5) * 0.002 * Math.max(...sweep.current.map(Math.abs))
          : sweep.current[i],
      }));
      return pts;
    }
    const pts: { v: number; i: number }[] = [];
    const pointsCount = 60;
    const vMax = Math.max(Math.abs(activeCellData.vSet) * 1.5, 2.0);
    for (let i = 0; i < pointsCount; i++) {
      const v = (i / pointsCount) * 2 * vMax - vMax;
      pts.push({ v, i: 0 });
    }
    return pts;
  }, [activeCellData]);

  const mapPointsToSvg = useCallback((points: { v: number; i: number }[]) => {
    if (points.length === 0) return "";
    const voltages = points.map(p => p.v);
    const currents = points.map(p => p.i);
    const vMin = Math.min(...voltages);
    const vMax = Math.max(...voltages);
    const vRange = Math.max(Math.abs(vMax), Math.abs(vMin), 0.1);

    const iAbs = currents.map(Math.abs);
    const iMax = Math.max(...iAbs, 1e-12);

    return points.map((p, idx) => {
      const x = 200 + (p.v / vRange) * 170;
      let y = 150;
      if (currentScale === "log") {
        const absI = Math.max(Math.abs(p.i), 1e-12);
        const logI = Math.log10(absI);
        const logMin = Math.log10(1e-12);
        const logMax = Math.log10(Math.max(iMax, 1e-6));
        const percent = Math.max(0, Math.min(1, (logI - logMin) / (logMax - logMin)));
        y = 280 - percent * 250;
      } else if (currentScale === "linear_abs") {
        const percent = Math.abs(p.i) / Math.max(iMax, 1e-12);
        y = 280 - Math.min(1, percent) * 250;
      } else {
        const percent = (p.i - (-iMax)) / (2 * iMax);
        y = 280 - Math.max(0, Math.min(1, percent)) * 250;
      }
      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(" ");
  }, [currentScale]);

  const plotCurves = useMemo(() => {
    const list: { key: string; path: string; color: string; width: number; opacity: number; dash?: string }[] = [];
    if (activeSweeps.length === 0) return list;

    if (cycleFilter === "all") {
      activeSweeps.forEach((sweep, i) => {
        const pts = generateHysteresisPoints(sweep, i + 1, false);
        const path = mapPointsToSvg(pts);
        list.push({
          key: `sweep-${i}`,
          path,
          color: theme === "light" ? "#94a3b8" : "#334155",
          width: 0.75,
          opacity: 0.35,
        });
      });
      if (activeSweeps.length >= 2) {
        const last = activeSweeps.length - 1;
        const pts1 = generateHysteresisPoints(activeSweeps[0], 1, true);
        list.push({
          key: 'cycle-first',
          path: mapPointsToSvg(pts1),
          color: theme === 'light' ? "#059669" : "#10b981",
          width: 2.0,
          opacity: 0.95,
        });
        const pts2 = generateHysteresisPoints(activeSweeps[last], last + 1, true);
        list.push({
          key: 'cycle-last',
          path: mapPointsToSvg(pts2),
          color: theme === 'light' ? "#4f46e5" : "#6366f1",
          width: 1.8,
          opacity: 0.95,
        });
      }
    } else if (cycleFilter === "single") {
      const idx = Math.min(singleCycleVal - 1, activeSweeps.length - 1);
      const sweep = activeSweeps[idx];
      if (sweep) {
        const pts = generateHysteresisPoints(sweep, singleCycleVal, true);
        list.push({
          key: `single-${singleCycleVal}`,
          path: mapPointsToSvg(pts),
          color: theme === 'light' ? "#059669" : "#10b981",
          width: 2.2,
          opacity: 1.0,
        });
      }
    } else if (cycleFilter === "custom") {
      const parts = customFilterText.split(",").map(p => parseInt(p.trim())).filter(num => !isNaN(num) && num >= 1);
      parts.forEach((cycle, i) => {
        const idx = Math.min(cycle - 1, activeSweeps.length - 1);
        const sweep = activeSweeps[idx] ?? activeSweeps[0];
        if (sweep) {
          const pts = generateHysteresisPoints(sweep, cycle, true);
          const colorPalette = theme === 'light'
            ? ["#059669", "#4f46e5", "#ea580c", "#d97706", "#c026d3"]
            : ["#10b981", "#6366f1", "#f97316", "#f59e0b", "#d946ef"];
          list.push({
            key: `custom-${cycle}-${i}`,
            path: mapPointsToSvg(pts),
            color: colorPalette[i % colorPalette.length],
            width: 2.0,
            opacity: 0.95,
          });
        }
      });
      if (parts.length === 0 && activeSweeps[0]) {
        const pts = generateHysteresisPoints(activeSweeps[0], 1, true);
        list.push({
          key: 'fallback-custom',
          path: mapPointsToSvg(pts),
          color: "#f59e0b",
          width: 2.0,
          opacity: 0.95,
          dash: "4,2",
        });
      }
    }
    return list;
  }, [activeSweeps, cycleFilter, singleCycleVal, customFilterText, theme, currentScale, generateHysteresisPoints, mapPointsToSvg]);

  const updateActiveCellParam = (field: "vSet" | "vReset", val: number) => {
    const key = `${activeProtocolName}-${selectedCell.row}-${selectedCell.col}`;
    setEditedParams(prev => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: val,
      },
    }));
  };

  const resetCellParams = () => {
    const key = `${activeProtocolName}-${selectedCell.row}-${selectedCell.col}`;
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
    link.download = `Memristor_Diagnostic_Matrix_${activeProtocolName}.tsv`;
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
                value={activeProtocolName}
                onChange={(e) => {
                  setActiveProtocolName(e.target.value);
                  setSelectedCell({ row: 0, col: 0 });
                }}
                className={`w-full p-2.5 text-xs font-semibold rounded-lg border shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all cursor-pointer appearance-none pr-8 ${
                  theme === 'light' ? 'bg-white border-slate-300 text-slate-800' : 'bg-white/5 border-white/10 text-white'
                }`}
              >
                {sortedProtocolNames.map((p) => (
                  <option key={p.name} value={p.name} className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>
                    {p.name}
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
                  ● {loading ? "Loading" : "Active"}
                </p>
              </div>
            </div>
          </section>

          <nav id="protocol-tree-nav" className="space-y-1">
            <label id="protocol-lbl" className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Protocol Tree</label>
            <div id="protocol-list" className="space-y-1.5 pl-1">
              {sortedProtocolNames.map((p) => {
                const technique = p.technique || "iv";
                const iconMap: Record<string, React.ReactNode> = {
                  "iv": <Activity className="w-3.5 h-3.5" />,
                  "ramp": <TrendingUp className="w-3.5 h-3.5" />,
                  "pulse": <Layers className="w-3.5 h-3.5" />,
                  "retention": <Layers className="w-3.5 h-3.5" />,
                  "stability": <Grid className="w-3.5 h-3.5" />,
                };
                return (
                  <button
                    key={p.name}
                    onClick={() => {
                      setActiveProtocolName(p.name);
                      setSelectedCell({ row: 0, col: 0 });
                    }}
                    className={`w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer ${
                      activeProtocolName === p.name
                        ? "text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold"
                        : (theme === "light" ? "text-slate-600 hover:text-slate-950 hover:bg-slate-205" : "text-slate-400 hover:text-slate-200 hover:bg-white/5")
                    }`}
                  >
                    <span className="flex items-center gap-2">{iconMap[technique] || <Activity className="w-3.5 h-3.5" />} {p.name}</span>
                    <span className="text-[8px] opacity-75 font-mono tracking-tighter font-semibold">{p.total_files}f</span>
                  </button>
                );
              })}
            </div>
          </nav>

          <div id="heatmap-snapshot-block" className="space-y-3 pt-4 border-t border-slate-200/80 dark:border-white/5 mt-auto">
            <span id="snapshot-lbl" className="text-[10px] font-bold text-slate-500 dark:text-slate-400 font-mono tracking-wider block uppercase">Heatmap Explorer ({deviceRows}x{deviceCols})</span>

            <div id="mini-grid" className={`grid grid-cols-${deviceCols} gap-1 p-1.5 rounded-xl border transition-colors ${
              theme === 'light' ? 'bg-[#f2f2f7] border-slate-205 shadow-3xs' : 'bg-black/30 border-zinc-800/85'
            }`} style={{ gridTemplateColumns: `repeat(${deviceCols}, minmax(0, 1fr))` }}>
              {cellsList.map((cell) => {
                const isSelected = selectedCell.row === cell.row && selectedCell.col === cell.col;
                let bg = "bg-emerald-500";
                if (cell.cellType.includes("Stuck-ON")) {
                  bg = "bg-red-500 shadow-[0_0_3.5px_#ef4444]";
                } else if (cell.cellType.includes("Stuck-OFF")) {
                  bg = "bg-slate-700 opacity-40";
                } else if (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold")) {
                  bg = "bg-amber-500 shadow-[0_0_3.5px_#f59e0b]";
                } else if (cell.cellType.includes("Ohmic")) {
                  bg = "bg-purple-500";
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
                CROSSBAR MATRIX <span className="bg-emerald-500/10 text-emerald-500 px-1 py-0.2 text-[8px] rounded font-bold font-mono">{deviceRows}x{deviceCols} Array</span>
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
                      max={activeSweeps.length}
                      value={singleCycleVal}
                      onChange={(e) => {
                        const parsed = parseInt(e.target.value);
                        if (!isNaN(parsed)) setSingleCycleVal(Math.max(1, Math.min(activeSweeps.length, parsed)));
                      }}
                      className={`w-10 bg-transparent text-center text-[10px] outline-none font-semibold font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${
                        theme === 'light' ? 'text-slate-800' : 'text-emerald-450'
                      }`}
                    />
                    <button
                      onClick={() => setSingleCycleVal(prev => Math.min(activeSweeps.length, prev + 1))}
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
                      max={Math.max(1, activeSweeps.length)}
                      value={singleCycleVal}
                      onChange={(e) => setSingleCycleVal(parseInt(e.target.value))}
                      className={`w-24 h-1 rounded-lg appearance-none cursor-pointer accent-emerald-500 ${
                        theme === 'light' ? 'bg-slate-200' : 'bg-zinc-800'
                      }`}
                    />
                    <span className="text-[8.5px] text-slate-400 font-mono tracking-tight">{activeSweeps.length}</span>
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
                    placeholder={`e.g. 1, 10, ${activeSweeps.length}`}
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

            {/* Left Dynamic Section */}
            <div id="plot-viewport" className="flex-1 border-r border-white/5 relative p-6 flex flex-col">

              {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm z-20">
                  <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
                    <p className="text-xs text-slate-400 font-mono">Loading protocol data...</p>
                  </div>
                </div>
              )}

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
                      {activeSweeps.length >= 1 && (
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded bg-[#059669]"></span> Sweep 1
                        </span>
                      )}
                      {activeSweeps.length >= 2 && (
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded bg-[#4f46e5]"></span> Sweep {activeSweeps.length}
                        </span>
                      )}
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

                      <text x="380" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="end">+Vmax</text>
                      <text x="20" y="165" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">-Vmax</text>
                      <text x="205" y="15" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "+Imax" : "Top"}</text>
                      <text x="205" y="295" fill="#64748b" className="text-[8px] font-mono" textAnchor="start">{currentScale === "linear_signed" ? "-Imax" : "Bottom"}</text>

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
                        <span className="text-slate-500">SWEEPS:</span>
                        <span className="text-slate-300">{activeSweeps.length}</span>
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

                  {activeSweeps.length > 0 && (
                    <div className="flex items-center gap-3 mt-2 px-1">
                      <span className="text-[9px] text-slate-500 font-mono">Sweep Explorer:</span>
                      <div className="flex gap-1 flex-wrap max-w-full overflow-x-auto">
                        {activeSweeps.map((_, i) => (
                          <button
                            key={i}
                            onClick={() => { setSelectedSweepIdx(i); setCycleFilter("single"); setSingleCycleVal(i + 1); }}
                            className={`px-2 py-0.5 text-[9px] font-mono rounded transition-colors cursor-pointer ${
                              selectedSweepIdx === i && cycleFilter === "single"
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : "bg-white/5 text-slate-400 hover:bg-white/10 border border-transparent"
                            }`}
                          >
                            #{i + 1}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === "CROSSBAR MATRIX" && (
                <div id="crossbar-expanded-view" className="flex-1 flex flex-col justify-between">
                  <div>
                    <h3 className={`text-xs font-bold uppercase tracking-wider mb-1 font-mono ${theme === 'light' ? 'text-slate-800' : 'text-white'}`}>Crossbar Array Architecture ({deviceRows}x{deviceCols} Sandbox)</h3>
                    <p className={`text-[10px] mb-4 uppercase ${theme === 'light' ? 'text-slate-500' : 'text-slate-500'}`}>Select cells in the grid to extract custom spectroscopic matrix configurations</p>
                  </div>

                  <div className={`grid gap-1.5 w-full max-w-[520px] mx-auto p-3 rounded-2xl border transition-all ${
                    theme === 'light' ? 'bg-[#f2f2f7] border-slate-200 shadow-3xs' : 'bg-[#1c1c1e] border-zinc-800'
                  }`} style={{ gridTemplateColumns: `repeat(${deviceCols}, minmax(0, 1fr))` }}>
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
                        } else if (cell.cellType.includes("Ohmic")) {
                          bgStyle = "bg-[#af52de] border-[#af52de] hover:bg-[#bf5af0] text-white shadow-3xs";
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
                        } else if (cell.cellType.includes("Ohmic")) {
                          bgStyle = "bg-[#bf5af0] border-[#bf5af0] hover:bg-[#c86bf2] text-black font-semibold shadow-sm";
                        } else {
                          bgStyle = "bg-[#30d158] border-[#30d158] hover:bg-[#34c759] text-black font-semibold shadow-sm";
                        }
                      }

                      let displayVal = "";
                      if (heatmapSnapshotType === "V_set") {
                        displayVal = `${cell.vSet}V`;
                      } else if (heatmapSnapshotType === "V_reset") {
                        displayVal = `${cell.vReset}V`;
                      } else {
                        displayVal = `${cell.onOff}`;
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
                            {displayVal}
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
                      <p className={`text-[10.5px] mt-1.5 leading-normal ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>
                        Currently highlighting cells based on <span className={`font-mono font-bold text-xs ${theme === 'light' ? 'text-indigo-900 border-b border-indigo-200/50' : 'text-white border-b border-white/10'}`}>{heatmapSnapshotType === "V_reset" ? "Median V_reset" : heatmapSnapshotType === "V_set" ? "Median V_set" : "ON/OFF Ratio"}</span>. Stable analog states show as emerald, volatile memory behaves as amber, stuck junctions display as red or dark gray.
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
                      <div id="vset-histogram" className="space-y-2">
                        <div className="flex justify-between text-[10px] font-mono select-none">
                          <span className="text-slate-400">V_set (Median: {aggregate?.median_vset ?? "?"} V)</span>
                          <span className="text-emerald-450 font-bold">SET Yield: {aggregate?.yield_pct ?? 0}%</span>
                        </div>
                        <div className="h-28 w-full relative border-l border-b border-white/10 p-1 bg-black/25 rounded-bl">
                          <svg className="w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="none">
                            <line x1="0" y1="25" x2="200" y2="25" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="75" x2="200" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            {(histograms?.vset?.counts ?? []).length > 0
                              ? (() => {
                                  const maxC = Math.max(...histograms!.vset.counts, 1);
                                  const w = 200 / histograms!.vset.counts.length;
                                  return histograms!.vset.counts.map((c, idx) => {
                                    const barH = Math.max(2, (c / maxC) * 90);
                                    return (
                                      <rect key={idx} x={idx * w + 2} y={100 - barH}
                                        width={Math.max(6, w - 4)} height={barH}
                                        fill="#10b981" fillOpacity={c === maxC ? "0.8" : "0.3"} rx="1" />
                                    );
                                  });
                                })()
                              : Array.from({ length: 8 }).map((_, idx) => {
                                  const barH = 20 + idx * 8;
                                  return (
                                    <rect key={idx} x={idx * 24 + 4} y={100 - barH}
                                      width="16" height={barH}
                                      fill="#10b981" fillOpacity="0.2" rx="1" />
                                  );
                                })}
                          </svg>
                          <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[8px] font-mono text-slate-500">
                            <span>{histograms?.vset?.bins?.[0] ?? "0V"}</span>
                            <span>{aggregate?.median_vset?.toFixed(2) ?? ""}V</span>
                            <span>{histograms?.vset?.bins?.[histograms.vset.bins.length - 1] ?? ""}</span>
                          </div>
                        </div>
                      </div>

                      <div id="vreset-histogram" className="space-y-2">
                        <div className="flex justify-between text-[10px] font-mono select-none">
                          <span className="text-slate-400">V_reset (Median: {aggregate?.median_vreset ?? "?"} V)</span>
                          <span className="text-indigo-400 font-bold">Cells: {aggregate?.switching_count ?? 0}x</span>
                        </div>
                        <div className="h-28 w-full relative border-l border-b border-white/10 p-1 bg-black/25 rounded-bl">
                          <svg className="w-full h-full" viewBox="0 0 200 100" preserveAspectRatio="none">
                            <line x1="0" y1="25" x2="200" y2="25" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            <line x1="0" y1="75" x2="200" y2="75" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5" />
                            {(histograms?.vreset?.counts ?? []).length > 0
                              ? (() => {
                                  const maxC = Math.max(...histograms!.vreset.counts, 1);
                                  const w = 200 / histograms!.vreset.counts.length;
                                  return histograms!.vreset.counts.map((c, idx) => {
                                    const barH = Math.max(2, (c / maxC) * 90);
                                    return (
                                      <rect key={idx} x={idx * w + 2} y={100 - barH}
                                        width={Math.max(6, w - 4)} height={barH}
                                        fill="#6366f1" fillOpacity={c === maxC ? "0.8" : "0.3"} rx="1" />
                                    );
                                  });
                                })()
                              : Array.from({ length: 8 }).map((_, idx) => {
                                  const barH = 15 + idx * 7;
                                  return (
                                    <rect key={idx} x={idx * 24 + 4} y={100 - barH}
                                      width="16" height={barH}
                                      fill="#6366f1" fillOpacity="0.2" rx="1" />
                                  );
                                })}
                          </svg>
                          <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[8px] font-mono text-slate-500">
                            <span>{histograms?.vreset?.bins?.[0] ?? "0V"}</span>
                            <span>{aggregate?.median_vreset?.toFixed(2) ?? ""}V</span>
                            <span>{histograms?.vreset?.bins?.[histograms.vreset.bins.length - 1] ?? ""}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div id="endurance-card" className="bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col space-y-3">
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Device Type Breakdown</span>
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono mt-0.5">Classification Distribution</h4>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                      {Object.entries(DEVICE_TYPE_MAP).map(([key, val]) => {
                        const count = deviceTypes[key] ?? 0;
                        const colorMap: Record<string, string> = {
                          "non-volatile": "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
                          "volatile": "border-amber-500/30 bg-amber-500/5 text-amber-400",
                          "short": "border-red-500/30 bg-red-500/5 text-red-400",
                          "insulating": "border-slate-500/30 bg-slate-500/5 text-slate-400",
                          "resistor": "border-purple-500/30 bg-purple-500/5 text-purple-400",
                        };
                        return (
                          <div key={key} className={`border rounded-lg p-3 text-center ${colorMap[key] ?? "border-white/10"}`}>
                            <p className="text-lg font-bold font-mono">{count}</p>
                            <p className="text-[8px] uppercase font-mono mt-1 opacity-75">{val.label}</p>
                          </div>
                        );
                      })}
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

              <section id="classification-section">
                <label id="classification-lbl" className={`text-[10px] font-bold uppercase tracking-widest block mb-3 font-mono ${theme === 'light' ? 'text-slate-400' : 'text-slate-500'}`}>Live Classification</label>

                <div id="classification-badge-container" className={`relative overflow-hidden group border p-4 rounded-xl transition-all ${
                  theme === 'light'
                    ? (activeCellData.classificationColor === 'emerald' ? 'bg-emerald-50/45 border-emerald-200 shadow-3xs' :
                       activeCellData.classificationColor === 'red' ? 'bg-red-50/45 border-red-200 shadow-3xs' :
                       activeCellData.classificationColor === 'slate' ? 'bg-slate-50 border-slate-200 shadow-3xs' :
                       activeCellData.classificationColor === 'purple' ? 'bg-purple-50/45 border-purple-200 shadow-3xs' :
                       'bg-amber-50/45 border-amber-200 shadow-3xs')
                    : (activeCellData.classificationColor === 'emerald' ? 'bg-emerald-500/5 border-emerald-500/20' :
                       activeCellData.classificationColor === 'red' ? 'bg-red-500/5 border-red-500/20' :
                       activeCellData.classificationColor === 'slate' ? 'bg-white/5 border-white/10' :
                       activeCellData.classificationColor === 'purple' ? 'bg-purple-500/5 border-purple-500/20' :
                       'bg-amber-500/5 border-amber-500/20')
                }`}>
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
                        activeCellData.classificationColor === 'purple'
                          ? (theme === 'light' ? "bg-purple-50 text-purple-700 border-purple-200" : "bg-purple-500/10 text-purple-400 border-purple-500/20") :
                        (theme === 'light' ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-amber-500/10 text-amber-400 border-amber-500/20")
                      }`}>
                        {activeCellData.cellType}
                      </span>
                      <h3 className={`text-lg font-semibold mt-2.5 leading-tight font-mono ${theme === 'light' ? 'text-slate-900' : 'text-white'}`}>Cell R({activeCellData.row}, C:{activeCellData.col})</h3>
                    </div>

                    <div className={`w-9 h-9 border rounded-full flex items-center justify-center animate-pulse ${
                      activeCellData.classificationColor === 'emerald' ? "border-emerald-500/50 text-emerald-600 dark:text-emerald-400" :
                      activeCellData.classificationColor === 'red' ? "border-red-500/50 text-red-600 dark:text-red-400" :
                      activeCellData.classificationColor === 'purple' ? "border-purple-500/50 text-purple-600 dark:text-purple-400" :
                      activeCellData.classificationColor === 'slate' ? "border-slate-400/50 text-slate-600 dark:text-slate-400" : "border-amber-500/50 text-amber-600 dark:text-amber-450"
                    }`}>
                      <span className="text-xs font-bold font-mono">!</span>
                    </div>
                  </div>

                  <p id="classification-message" className={`text-[11px] mt-3 leading-relaxed ${theme === 'light' ? 'text-slate-600 font-medium' : 'text-slate-400'}`}>
                    {activeCellData.detailMessage}
                  </p>
                </div>
              </section>

              <section id="extractions-section" className="flex-1 flex flex-col min-h-0">
                <label id="extractions-lbl" className={`text-[10px] font-bold uppercase tracking-widest block mb-3 font-mono ${theme === 'light' ? 'text-slate-400' : 'text-slate-500'}`}>Extraction Matrix</label>

                <div id="table-housing" className={`flex-1 border rounded-xl overflow-hidden flex flex-col transition-all duration-200 ${
                  theme === 'light' ? 'bg-white border-slate-250 hover:border-slate-300 shadow-3xs' : 'bg-[#1c1c1e]/40 border-zinc-800'
                }`}>
                  <table id="metrics-table" className="w-full text-left border-collapse">
                    <thead className={theme === 'light' ? 'bg-slate-50/80 border-b border-slate-200' : 'bg-[#121214]'}>
                      <tr className={`text-[9.5px] uppercase border-b font-mono tracking-wider ${theme === 'light' ? 'text-slate-500 border-slate-200' : 'text-zinc-500 border-zinc-800'}`}>
                        <th className="p-3 font-semibold">Spectroscopic Metric</th>
                        <th className="p-3 font-semibold text-right">Value</th>
                        <th className="p-3 font-semibold text-right">Dev Vol %</th>
                      </tr>
                    </thead>
                    <tbody className="text-xs font-mono">

                      <tr className={`border-b transition-colors ${theme === 'light' ? 'border-slate-100 hover:bg-slate-50/60' : 'border-zinc-850 hover:bg-white/5'}`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-medium' : 'p-3 text-zinc-400'}>V_set (Volt)</td>
                        <td className="p-3 text-right text-emerald-600 dark:text-emerald-400 font-bold">{activeCellData.vSet}</td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.04</td>
                      </tr>

                      <tr className={`border-b transition-colors ${theme === 'light' ? 'border-slate-100 hover:bg-slate-50/60' : 'border-zinc-850 hover:bg-white/5'}`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-medium' : 'p-3 text-zinc-400'}>V_reset (Volt)</td>
                        <td className={`p-3 text-right font-bold ${activeCellData.vReset > 0 ? (theme === 'light' ? 'text-amber-600' : 'text-amber-500') : (theme === 'light' ? 'text-indigo-600' : 'text-indigo-400')}`}>
                          {activeCellData.vReset}
                        </td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.31</td>
                      </tr>

                      <tr className={`transition-colors ${theme === 'light' ? 'hover:bg-slate-50/65' : 'hover:bg-white/5'}`}>
                        <td className={theme === 'light' ? 'p-3 text-slate-600 font-sans font-medium' : 'p-3 text-zinc-400 font-sans'}>R_on/R_off Ratio</td>
                        <td className={`p-3 text-right font-bold ${theme === 'light' ? 'text-indigo-600' : 'text-indigo-400'}`}>{activeCellData.onOff}</td>
                        <td className="p-3 text-right text-slate-400 dark:text-zinc-500">± 0.82</td>
                      </tr>

                    </tbody>
                  </table>

                  <div id="hpar-block" className={`mt-auto p-4 border-t transition-all ${theme === 'light' ? 'bg-slate-50/50 border-slate-200' : 'bg-indigo-600/10 border-white/10 rounded-b-lg'}`}>
                    <div className="flex justify-between items-center mb-1">
                      <span id="hpar-lbl" className="text-[10px] font-bold text-slate-400 tracking-wide font-mono">H-PARAMETER STATE</span>
                      <span id="hpar-val" className={`text-xs font-bold font-mono ${theme === 'light' ? 'text-slate-800' : 'text-indigo-450'}`}>{activeCellData.hScore} / 100</span>
                    </div>
                    <div id="progress-container" className={`w-full h-1.5 rounded-full overflow-hidden ${theme === 'light' ? 'bg-slate-200' : 'bg-white/10'}`}>
                      <div
                        id="progress-bar"
                        style={{ width: `${activeCellData.hScore}%` }}
                        className={`h-full rounded-full transition-all duration-700 ${theme === 'light' ? 'bg-indigo-600' : 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]'}`}
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

            <div className="flex justify-between items-start pb-4 border-b border-white/10">
              <div>
                <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-widest font-mono">AUTOMATED BENCH ANALYSIS REPORT</span>
                <h3 className="text-lg font-bold text-white uppercase leading-tight font-sans">
                  {currentProject.name} Characterization Sheet
                </h3>
              </div>
              <button
                onClick={() => setShowReport(false)}
                className="p-1 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-6 py-4 font-mono text-[11px] text-slate-300">

              <div className="bg-white/5 border border-white/5 rounded-lg p-3 grid grid-cols-2 gap-x-4 gap-y-2">
                <div>
                  <span className="text-slate-500 uppercase">Project:</span>{" "}
                  <span className="text-white font-bold">{projectInfo?.project_name ?? "N/A"}</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Protocol:</span>{" "}
                  <span className="text-white">{activeProtocolName}</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Operator:</span>{" "}
                  <span className="text-white">nguyenxuantai.9a1@gmail.com</span>
                </div>
                <div>
                  <span className="text-slate-500 uppercase">Yield:</span>{" "}
                  <span className="text-white">{aggregate?.yield_pct ?? 0}%</span>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-white uppercase border-b border-white/5 pb-1 mb-2 font-sans">Abstract Narrative Summary</h4>
                <p className="text-slate-400 leading-relaxed text-[11px]">
                  Bipolar resistive memories in {projectInfo?.project_name ?? "N/A"} / {activeProtocolName} exhibit {aggregate?.yield_pct ?? 0}% yield with {aggregate?.switching_count ?? 0} switching cells out of {aggregate?.total_cells ?? 0} total. There are {deviceTypes["volatile"] ?? 0} volatile cells and {(deviceTypes["short"] ?? 0) + (deviceTypes["insulating"] ?? 0)} short/open anomalies.
                </p>
              </div>

              <div>
                <h4 className="text-xs font-bold text-white uppercase border-b border-white/5 pb-1 mb-2 font-sans">Cell Extract Diagnostics Spec Sheet ({cellsList.length} Test Blocks)</h4>
                <div className="border border-white/10 rounded overflow-hidden">
                  <table className="w-full text-left font-mono text-[10px] border-collapse">
                    <thead className="bg-white/5 text-slate-400 border-b border-white/10">
                      <tr>
                        <th className="p-2">Coordinate</th>
                        <th className="p-2">Classification</th>
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
                          <td className="p-2 text-right">{cell.onOff}</td>
                          <td className="p-2 text-right text-white font-bold">{cell.hScore}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="p-2 bg-[#121214] text-[9px] text-slate-500 text-center">
                    Showing first 10 of {cellsList.length} parameters.
                  </div>
                </div>
              </div>

              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between">
                <div>
                  <h5 className="font-bold text-white font-sans text-xs">Neuromorphic Synaptic Fitness Validation</h5>
                  <p className="text-[10px] text-slate-400 mt-0.5">Validated on {activeProtocolName}.</p>
                </div>
                <span className="text-sm font-bold text-emerald-400 font-mono">{aggregate?.yield_pct && aggregate.yield_pct > 50 ? "PASS COMPLIANT" : "REVIEW REQUIRED"}</span>
              </div>
            </div>

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
                  alert("Export PDF payload initialized.");
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
