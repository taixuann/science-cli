import { useState, useMemo, useEffect, useCallback } from "react";
import {
  Activity, Cpu, Lock, Unlock, Download, FileText,
  RefreshCw, AlertTriangle, CheckCircle2, XCircle
} from "lucide-react";
import Plot from 'react-plotly.js';

const BASE = window.location.origin;

interface CellData {
  row: number; col: number;
  cellType: string; classificationColor: string;
  vSet: number; vReset: number; onOff: number;
  hScore: number; detailMessage: string; seed: number;
}
interface IVSweep {
  label: string;
  voltage: number[];
  current: number[];
  v_set: number; v_reset: number;
}
interface IVResponse {
  cell_id: string; row: number; col: number;
  material: string; v_set: number; v_reset: number;
  ratio: number; switching: boolean;
  sweeps: IVSweep[];
}
interface DashboardAggregate {
  total_cells: number; measured_cells: number;
  switching_count: number; yield_pct: number;
  median_vset: number; median_vreset: number;
  median_ratio: number; total_iv_files: number;
}
interface DashboardHeatmapCell {
  cell: string; material: string; n_files: number;
  status: string; v_set: number; v_reset: number;
  ratio: number; device_type: string;
}
interface DashboardData {
  protocol: string;
  aggregate: DashboardAggregate;
  materials: string[];
  device_types: Record<string, number>;
  heatmap: {
    rows: number; cols: number; metric: string;
    data: (number | null)[][];
    metadata: DashboardHeatmapCell[][];
  };
}

const TYPE_MAP: Record<string, { cellType: string; color: string }> = {
  "non-volatile": { cellType: "Stable Bipolar RRAM", color: "emerald" },
  "volatile": { cellType: "Volatile Memristor", color: "amber" },
  "short": { cellType: "Stuck-ON (Ohmic)", color: "red" },
  "insulating": { cellType: "Stuck-OFF (Open)", color: "slate" },
  "resistor": { cellType: "Ohmic Resistor", color: "purple" },
};

function makeRowCol(meta: DashboardHeatmapCell): CellData {
  const row = parseInt(meta.cell.match(/R(\d+)/i)?.[1] ?? "1") - 1;
  const col = parseInt(meta.cell.match(/C(\d+)/i)?.[1] ?? "1") - 1;
  const dt = meta.device_type || "non-volatile";
  const mapped = TYPE_MAP[dt] || { cellType: "Stable Bipolar RRAM", color: "emerald" };
  const hScore = meta.status === "Active Switching"
    ? Math.round(70 + Math.random() * 25)
    : Math.round(5 + Math.random() * 30);
  return {
    row, col,
    cellType: mapped.cellType,
    classificationColor: mapped.color,
    vSet: meta.v_set, vReset: meta.v_reset,
    onOff: meta.ratio || 0, hScore,
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
  const [activeProtocol, setActiveProtocol] = useState<string>("");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number }>({ row: 0, col: 0 });
  const [cycleFilter, setCycleFilter] = useState<string>("all");
  const [singleCycleVal, setSingleCycleVal] = useState<number>(500);
  const [currentScale, setCurrentScale] = useState<"log" | "linear_abs" | "linear_signed">("log");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [customFilterText, setCustomFilterText] = useState<string>("10, 500");
  const [probeLocked, setProbeLocked] = useState<boolean>(true);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [heatmapSnapshotType, setHeatmapSnapshotType] = useState<string>("V_reset");
  const [editedParams, setEditedParams] = useState<Record<string, { vSet?: number; vReset?: number }>>({});
  const [loaded, setLoaded] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState<string>("All");

  const [loading, setLoading] = useState(true);
  const [protocolNames, setProtocolNames] = useState<string[]>([]);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [ivData, setIvData] = useState<IVResponse | null>(null);
  const [ivCache, setIvCache] = useState<Record<string, IVResponse>>({});

  useEffect(() => {
    setLoading(true);
    fetch(`${BASE}/api/project`)
      .then(r => r.json())
      .then(data => {
        const names: string[] = (data?.protocols || [])
          .map((p: any) => p.name);
        setProtocolNames(names);
        if (names.length > 0) {
          setActiveProtocol(names[0]);
          setActiveProjectIdx(0);
        }
        setLoading(false);
        setLoaded(true);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeProtocol) return;
    setLoading(true);
    fetch(`${BASE}/api/protocol/${encodeURIComponent(activeProtocol)}/dashboard`)
      .then(r => r.json())
      .then(data => { setDashboardData(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [activeProtocol]);

  useEffect(() => {
    const cellId = `R${selectedCell.row + 1}C${selectedCell.col + 1}`;
    const cacheKey = `${activeProtocol}:${cellId}`;
    if (ivCache[cacheKey]) { setIvData(ivCache[cacheKey]); return; }
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

  const currentProject = useMemo(() => {
    const name = protocolNames[activeProjectIdx] || "Unknown";
    const agg = dashboardData?.aggregate;
    const dtypes = dashboardData?.device_types || {};
    return {
      id: name, name,
      materialStack: dashboardData?.materials?.join(", ") || name,
      globalYield: agg?.yield_pct ?? 0,
      devicesAnalyzed: agg?.total_iv_files ?? 0,
      volatileDetected: (dtypes["volatile"] || 0) + (dtypes["short"] || 0),
      baseVset: agg?.median_vset ?? 0,
      baseVreset: agg?.median_vreset ?? 0,
      baseOnOffRatio: agg?.median_ratio ?? 0,
      baseHScore: agg?.switching_count && agg?.measured_cells
        ? Math.round((agg.switching_count / agg.measured_cells) * 100) : 0,
    };
  }, [protocolNames, activeProjectIdx, dashboardData]);

  const t = useMemo(() => {
    const isL = theme === "light";
    return {
      bgRoot: isL ? "bg-slate-50 text-slate-800" : "bg-[#0A0A0B] text-slate-200",
      bgMain: isL ? "bg-white" : "bg-[#070708]",
      bgSidebar: isL ? "bg-slate-100 border-slate-200 text-slate-800" : "bg-black/20 border-white/5",
      bgCard: isL ? "bg-slate-50 border border-slate-200 shadow-xs" : "bg-black/40 border border-white/5",
      textTitle: isL ? "text-slate-900" : "text-white",
      bgHeader: isL ? "bg-slate-100 border-slate-200" : "bg-[#0c0c0d] border-b border-white/10",
      graphGridLine: isL ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.03)",
      graphZeroAxis: isL ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.15)",
      graphText: isL ? "#475569" : "#64748b",
      cellText: isL ? "text-slate-700" : "text-slate-400",
    };
  }, [theme]);

  const availableMaterials = useMemo(() => {
    const mats = dashboardData?.materials || [];
    return ["All", ...mats];
  }, [dashboardData]);

  const cellsList: CellData[] = useMemo(() => {
    const meta = dashboardData?.heatmap?.metadata;
    if (!meta || meta.length === 0) return [];
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

  const filteredCellsList = useMemo(() => {
    if (selectedMaterial === "All") return cellsList;
    return cellsList.filter(c => {
      const meta = dashboardData?.heatmap?.metadata?.[c.row]?.[c.col];
      return meta && meta.material === selectedMaterial;
    });
  }, [cellsList, selectedMaterial, dashboardData]);

  const activeCellData: CellData = useMemo(() => {
    const found = cellsList.find(c => c.row === selectedCell.row && c.col === selectedCell.col);
    if (found) return found;
    const meta = dashboardData?.heatmap?.metadata?.[selectedCell.row]?.[selectedCell.col];
    if (meta) return makeRowCol(meta);
    return {
      row: selectedCell.row, col: selectedCell.col,
      cellType: "Unknown", classificationColor: "slate",
      vSet: 0, vReset: 0, onOff: 0, hScore: 0,
      detailMessage: "No data for this cell.",
      seed: selectedCell.row * 100 + selectedCell.col,
    };
  }, [cellsList, selectedCell, dashboardData]);

  const dynamicGlobalYield = useMemo(() => dashboardData?.aggregate?.yield_pct ?? 0, [dashboardData]);
  const dynamicVolatiles = useMemo(() => {
    const dtypes = dashboardData?.device_types || {};
    return (dtypes["volatile"] || 0) + (dtypes["short"] || 0);
  }, [dashboardData]);

  const generateHysteresisPoints = useCallback(
    (cell: CellData, cycleNum: number, noise: boolean): { v: number; i: number }[] => {
      if (ivData?.sweeps?.length) {
        const idx = Math.min(Math.max(0, cycleNum - 1), ivData.sweeps.length - 1);
        const sweep = ivData.sweeps[idx];
        if (sweep?.voltage?.length) {
          return sweep.voltage.map((v, i) => ({ v, i: sweep.current[i] ?? 0 }));
        }
      }
      const pts: { v: number; i: number }[] = [];
      const pts4 = 60;
      const vMax = Math.max(Math.abs(cell.vSet) * 1.5, 2.0);
      const sv: number[] = [];
      for (let i = 0; i < pts4; i++) sv.push(-vMax + (2 * vMax * i) / pts4);
      const isStuckOn = cell.cellType.includes("Stuck-ON");
      const isStuckOff = cell.cellType.includes("Stuck-OFF");
      const isVol = cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold");
      let lrs = false;
      sv.forEach(v => {
        let cur = 0;
        if (isStuckOn) cur = v * 2.5;
        else if (isStuckOff) cur = v * 0.002;
        else {
          if (v >= 0) {
            if (v > (cell.vSet || 1)) lrs = true;
            cur = lrs ? v * 1.8 : Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 1.2) * 0.01, 0.4);
          } else {
            if (isVol) lrs = false;
            else if (v < (cell.vReset || 0.5)) lrs = false;
            cur = lrs ? v * 1.8 : Math.sign(v) * Math.min(Math.pow(10, Math.abs(v) * 0.9) * 0.015, 0.35);
          }
        }
        if (noise) cur += 0.015 * (Math.random() - 0.5);
        pts.push({ v, i: cur });
      });
      return pts;
    }, [ivData]);

  const plotlyTraces = useMemo(() => {
    const traces: any[] = [];
    const sweeps = ivData?.sweeps;
    if (!sweeps?.length) {
      const pts = generateHysteresisPoints(activeCellData, 10, true);
      const y = currentScale === 'linear_signed' ? pts.map(p => p.i) : pts.map(p => Math.abs(p.i));
      traces.push({
        x: pts.map(p => p.v), y,
        type: 'scatter', mode: 'lines',
        name: 'Synthetic',
        line: { color: '#10b981', width: 1.5 },
        hovertemplate: 'V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
      });
      return traces;
    }
    const mapY = (s: IVSweep) => currentScale === 'linear_signed' ? s.current : s.current.map(Math.abs);
    if (cycleFilter === 'all') {
      const n = Math.min(sweeps.length, 10);
      for (let i = 1; i < n - 1; i++) {
        traces.push({
          x: sweeps[i].voltage, y: mapY(sweeps[i]),
          type: 'scatter', mode: 'lines',
          name: 'Cycle ' + (i + 1),
          line: { color: '#94a3b8', width: 0.8 },
          hovertemplate: 'Cycle ' + (i + 1) + '<br>V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
        });
      }
      if (sweeps.length > 0) {
        traces.push({
          x: sweeps[0].voltage, y: mapY(sweeps[0]),
          type: 'scatter', mode: 'lines',
          name: 'Cycle 1',
          line: { color: '#10b981', width: 2 },
          hovertemplate: 'Cycle 1<br>V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
        });
      }
      if (sweeps.length > 1) {
        const last = sweeps.length - 1;
        traces.push({
          x: sweeps[last].voltage, y: mapY(sweeps[last]),
          type: 'scatter', mode: 'lines',
          name: 'Cycle ' + (last + 1),
          line: { color: '#6366f1', width: 2 },
          hovertemplate: 'Cycle ' + (last + 1) + '<br>V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
        });
      }
    } else if (cycleFilter === 'single') {
      const idx = Math.min(Math.max(0, singleCycleVal - 1), sweeps.length - 1);
      traces.push({
        x: sweeps[idx].voltage, y: mapY(sweeps[idx]),
        type: 'scatter', mode: 'lines+markers',
        name: 'Cycle ' + (idx + 1),
        line: { color: '#10b981', width: 2 },
        marker: { size: 3, color: '#10b981' },
        hovertemplate: 'Cycle ' + (idx + 1) + '<br>V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
      });
    } else if (cycleFilter === 'custom') {
      const parts = customFilterText.split(',').map(p => parseInt(p.trim())).filter(n => !isNaN(n) && n >= 1);
      const colors = ['#10b981', '#6366f1', '#f97316', '#f59e0b', '#d946ef'];
      parts.forEach((c, i) => {
        const idx = Math.min(Math.max(0, c - 1), sweeps.length - 1);
        traces.push({
          x: sweeps[idx].voltage, y: mapY(sweeps[idx]),
          type: 'scatter', mode: 'lines',
          name: 'Cycle ' + c,
          line: { color: colors[i % colors.length], width: 1.5 },
          hovertemplate: 'Cycle ' + c + '<br>V: %{x:.3f} V<br>I: %{y:.3e} A<extra></extra>',
        });
      });
    }
    return traces;
  }, [ivData, activeCellData, currentScale, cycleFilter, singleCycleVal, customFilterText, generateHysteresisPoints]);

  const plotlyLayout = useMemo(() => ({
    autosize: true,
    margin: { l: 55, r: 20, t: 10, b: 55 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: t.graphText, family: 'ui-monospace, monospace' },
    xaxis: {
      title: { text: 'Voltage (V)', font: { size: 11, color: t.graphText } },
      gridcolor: t.graphGridLine,
      zerolinecolor: t.graphZeroAxis, zerolinewidth: 1,
      showspikes: true, spikecolor: t.graphZeroAxis, spikedash: 'dot',
    },
    yaxis: {
      title: {
        text: currentScale === 'log' ? '|I| (A)' : currentScale === 'linear_abs' ? '|I| (A)' : 'I (A)',
        font: { size: 11, color: t.graphText },
      },
      type: currentScale === 'log' ? 'log' : 'linear',
      gridcolor: t.graphGridLine,
      zerolinecolor: t.graphZeroAxis, zerolinewidth: 1,
    },
    showlegend: cycleFilter !== 'single',
    legend: { font: { size: 9, color: t.graphText }, bgcolor: 'transparent' },
    hovermode: 'closest',
    dragmode: 'pan',
  }), [currentScale, t, cycleFilter]);

  const heatmapZ = useMemo(() => {
    const data = dashboardData?.heatmap?.data || [];
    const meta = dashboardData?.heatmap?.metadata || [];
    if (selectedMaterial === "All" || !meta.length) return data;
    return data.map((row, r) => row.map((val, c) => {
      const cell = meta[r]?.[c];
      if (!cell || cell.material !== selectedMaterial) return null;
      return val;
    }));
  }, [dashboardData, selectedMaterial]);

  const heatmapHover = useMemo(() => {
    const meta = dashboardData?.heatmap?.metadata || [];
    return meta.map(row => row.map(cell => {
      if (!cell || cell.status === 'Unmeasured') return 'No data';
      const dtColor = cell.device_type === 'non-volatile' ? '#10b981'
        : cell.device_type === 'volatile' ? '#f59e0b'
        : cell.device_type === 'short' ? '#ef4444'
        : cell.device_type === 'insulating' ? '#64748b' : '#a855f7';
      return [
        '<b>' + cell.cell + '</b>',
        'Material: ' + cell.material,
        'Type: <span style="color:' + dtColor + '">' + cell.device_type + '</span>',
        'V<sub>set</sub>: ' + (cell.v_set?.toFixed(2) ?? 'N/A') + ' V',
        'V<sub>reset</sub>: ' + (cell.v_reset?.toFixed(2) ?? 'N/A') + ' V',
        'Ratio: ' + (cell.ratio?.toFixed(1) ?? 'N/A'),
        'Files: ' + cell.n_files,
      ].join('<br>');
    }));
  }, [dashboardData]);

  const heatmapLayout = useMemo(() => ({
    autosize: true,
    margin: { l: 45, r: 25, t: 10, b: 55 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: t.graphText, family: 'ui-monospace, monospace' },
    xaxis: {
      title: { text: 'Column', font: { size: 11 } },
      tickmode: 'array' as const,
      tickvals: dashboardData?.heatmap ? Array.from({ length: dashboardData.heatmap.cols }, (_, i) => i) : [],
      ticktext: dashboardData?.heatmap ? Array.from({ length: dashboardData.heatmap.cols }, (_, i) => 'C' + (i + 1)) : [],
      gridcolor: t.graphGridLine,
    },
    yaxis: {
      title: { text: 'Row', font: { size: 11 } },
      tickmode: 'array' as const,
      tickvals: dashboardData?.heatmap ? Array.from({ length: dashboardData.heatmap.rows }, (_, i) => i) : [],
      ticktext: dashboardData?.heatmap ? Array.from({ length: dashboardData.heatmap.rows }, (_, i) => 'R' + (i + 1)) : [],
      gridcolor: t.graphGridLine,
    },
    dragmode: 'select',
  }), [t, dashboardData]);

  const vSetValues = useMemo(() => cellsList.map(c => c.vSet).filter(v => v > 0), [cellsList]);
  const vResetValues = useMemo(() => cellsList.map(c => c.vReset).filter(v => v > 0), [cellsList]);

  const updateActiveCellParam = (field: "vSet" | "vReset", val: number) => {
    const key = activeProjectIdx + '-' + selectedCell.row + '-' + selectedCell.col;
    setEditedParams(prev => ({ ...prev, [key]: { ...prev[key], [field]: val } }));
  };
  const resetCellParams = () => {
    const key = activeProjectIdx + '-' + selectedCell.row + '-' + selectedCell.col;
    setEditedParams(prev => { const u = { ...prev }; delete u[key]; return u; });
  };
  const triggerExportTSV = () => {
    let tsv = "Cell_ID\tRow\tCol\tProject\tClassification\tV_set_Volt\tV_reset_Volt\tON_OFF_Ratio\tH_Score\n";
    cellsList.forEach(cell => {
      tsv += 'Cell_R' + cell.row + 'C' + cell.col + '\t' + cell.row + '\t' + cell.col + '\t' + currentProject.name + '\t' + cell.cellType + '\t' + cell.vSet + '\t' + cell.vReset + '\t10^' + cell.onOff + '\t' + cell.hScore + '\n';
    });
    const blob = new Blob([tsv], { type: "text/tab-separated-values" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = 'Memristor_Diagnostic_Matrix_' + currentProject.id + '.tsv';
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
  };

  if (loaded && protocolNames.length === 0) {
    return (
      <div className={'flex flex-col h-screen w-screen items-center justify-center ' + t.bgRoot}>
        <Cpu className="w-12 h-12 text-slate-600 mb-4" />
        <h2 className="text-lg font-bold font-mono text-slate-400">No Memristor Protocols Found</h2>
        <p className="text-xs text-slate-600 mt-2">No protocols with device data (devices.yaml) detected.</p>
      </div>
    );
  }

  const nCols = dashboardData?.heatmap?.cols ?? 6;
  const nRows = dashboardData?.heatmap?.rows ?? 6;

  return (
    <div className={'flex flex-col h-screen w-screen overflow-hidden ' + t.bgRoot + ' transition-colors duration-250 select-none'}>
      <header className={'h-16 border-b transition-colors duration-250 ' + t.bgHeader + ' backdrop-blur-md flex items-center justify-between px-6 shrink-0 z-10'}>
        <div className="flex items-center space-x-4">
          <div className={'w-8 h-8 rounded-lg flex items-center justify-center ' + (theme === 'light' ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-500/20 border border-emerald-500/50')}>
            <div className="w-4 h-4 rounded-sm bg-emerald-400 shadow-[0_0_8px_#10b981]"></div>
          </div>
          <div>
            <h1 className={'text-sm font-bold tracking-tight uppercase flex items-center gap-2 ' + t.textTitle}>
              NeuroPhase-X1 <span className={'text-[9px] font-normal px-2 py-0.5 rounded-full ' + (theme === 'light' ? 'bg-slate-200 text-slate-700' : 'bg-white/10 text-slate-300')}>v4.2.1-live</span>
            </h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-mono">Memristor Diagnostics Portal</p>
          </div>
        </div>
        <div className="flex items-center space-x-6">
          <div className={'flex space-x-1 p-0.5 rounded-full border ' + (theme === 'light' ? 'bg-slate-200 border-slate-300' : 'bg-white/5 border-white/10')}>
            <button onClick={() => setTheme("light")}
              className={'px-4 py-1 text-[10px] font-semibold rounded-full transition-all duration-200 cursor-pointer ' + (theme === "light" ? "bg-emerald-500 text-white shadow-xs font-bold" : "text-slate-400 hover:text-white")}
            >LIGHT</button>
            <button onClick={() => setTheme("dark")}
              className={'px-4 py-1 text-[10px] font-semibold rounded-full transition-all duration-200 cursor-pointer ' + (theme === "dark" ? "bg-slate-800 text-white shadow-xs font-bold" : "text-slate-500 hover:text-slate-800")}
            >DARK</button>
          </div>
          <div className={'flex items-center space-x-3 border-l pl-6 h-8 ' + (theme === 'light' ? 'border-slate-300' : 'border-white/10')}>
            <div className="text-right hidden sm:block">
              <p className={'text-[11px] font-medium ' + t.textTitle}>nguyenxuantai.9a1</p>
              <p className="text-[9px] text-emerald-500 font-mono text-right">&#9679; Operator 01</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-white/20 flex items-center justify-center overflow-hidden bg-gradient-to-tr from-slate-600 to-indigo-900">
              <span className="text-xs font-bold text-white uppercase">NT</span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className={'w-64 border-r p-4 flex flex-col space-y-6 shrink-0 overflow-y-auto transition-colors duration-250 ' + t.bgSidebar}>
          <section>
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Current Project</label>
            <div className="relative group">
              <select
                value={activeProjectIdx}
                onChange={(e) => {
                  const idx = parseInt(e.target.value);
                  setActiveProjectIdx(idx);
                  const name = protocolNames[idx];
                  if (name) setActiveProtocol(name);
                  setSelectedCell({ row: 0, col: 0 });
                }}
                className={'w-full p-2.5 text-xs font-semibold rounded-lg border shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all cursor-pointer appearance-none pr-8 ' + (theme === 'light' ? 'bg-white border-slate-300 text-slate-800' : 'bg-white/5 border-white/10 text-white')}
              >
                {loading && <option className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>Loading...</option>}
                {protocolNames.length === 0 && !loading && <option className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>No protocols</option>}
                {protocolNames.map((name, idx) => (
                  <option key={name} value={idx} className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>{name}</option>
                ))}
              </select>
              <div className="absolute right-3 top-3 pointer-events-none text-slate-400 text-[10px]">&#9660;</div>
            </div>
            <div className={'p-3 rounded-b-lg border-x border-b ' + (theme === 'light' ? 'bg-slate-200/40 border-slate-300' : 'bg-emerald-500/5 border-white/5')}>
              <p className="text-[10px] font-medium text-slate-500 italic truncate">{currentProject.materialStack}</p>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[9px] font-semibold text-slate-400">SYSTEM STATE</span>
                <p className="text-[10px] text-emerald-500 font-mono flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                  &#9679; Active Acquisition
                </p>
              </div>
            </div>
          </section>

          <section>
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Material Filter</label>
            <div className="relative group">
              <select
                value={selectedMaterial}
                onChange={(e) => setSelectedMaterial(e.target.value)}
                className={'w-full p-2.5 text-xs font-semibold rounded-lg border shadow-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all cursor-pointer appearance-none pr-8 ' + (theme === 'light' ? 'bg-white border-slate-300 text-slate-800' : 'bg-white/5 border-white/10 text-white')}
              >
                {availableMaterials.map((mat) => (
                  <option key={mat} value={mat} className={theme === 'light' ? 'bg-slate-50 text-slate-800' : 'bg-[#0c0c0d] text-slate-300'}>{mat}</option>
                ))}
              </select>
              <div className="absolute right-3 top-3 pointer-events-none text-slate-400 text-[10px]">&#9660;</div>
            </div>
            <div className={'p-3 rounded-b-lg border-x border-b ' + (theme === 'light' ? 'bg-slate-200/40 border-slate-300' : 'bg-emerald-500/5 border-white/5')}>
              <p className="text-[9px] text-slate-400 font-mono">
                {selectedMaterial === "All"
                  ? "Showing all " + cellsList.length + " devices"
                  : "Showing " + filteredCellsList.length + " / " + cellsList.length + " devices"}
              </p>
            </div>
          </section>

          <nav className="space-y-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-3 font-mono">Protocol Tree</label>
            <div className="space-y-1.5 pl-1">
              <button onClick={() => setActiveProtocol(protocolNames[activeProjectIdx] || "iv")}
                className={'w-full flex items-center justify-between text-left text-xs p-2.5 rounded transition-all cursor-pointer text-emerald-600 bg-emerald-500/10 border-l-2 border-emerald-500 font-bold'}
              >
                <span className="flex items-center gap-2"><Activity className="w-3.5 h-3.5" /> {protocolNames[activeProjectIdx] || "Protocol"}</span>
                <span className="text-[8px] opacity-75 font-mono tracking-tighter font-semibold">RUNNING</span>
              </button>
            </div>
          </nav>

          <div className="space-y-3 pt-4 border-t border-slate-200/80 dark:border-white/5 mt-auto">
            <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 font-mono tracking-wider block uppercase">Heatmap Explorer ({nCols}x{nRows})</span>
            <div className={'grid gap-1 p-1.5 rounded-xl border transition-colors ' + (theme === 'light' ? 'bg-[#f2f2f7] border-slate-205 shadow-3xs' : 'bg-black/30 border-zinc-800/85')}
              style={{ gridTemplateColumns: 'repeat(' + nCols + ', minmax(0, 1fr))' }}>
              {filteredCellsList.map((cell) => {
                const isSelected = selectedCell.row === cell.row && selectedCell.col === cell.col;
                let bg = "bg-emerald-500";
                if (cell.cellType.includes("Stuck-ON")) bg = "bg-red-500 shadow-[0_0_3.5px_#ef4444]";
                else if (cell.cellType.includes("Stuck-OFF")) bg = "bg-slate-700 opacity-40";
                else if (cell.cellType.includes("Volatile") || cell.cellType.includes("Threshold")) bg = "bg-amber-500 shadow-[0_0_3.5px_#f59e0b]";
                return (
                  <button key={'mini-' + cell.row + '-' + cell.col}
                    onClick={() => setSelectedCell({ row: cell.row, col: cell.col })}
                    className={'aspect-square w-full ' + bg + ' ' + (isSelected ? (theme === 'light' ? "ring-2 ring-indigo-500 scale-110 shadow-xs" : "ring-2 ring-indigo-400 scale-110 shadow-xs") : "") + ' transition-all duration-150 rounded-md cursor-pointer'}
                    title={'Cell R' + cell.row + ' C' + cell.col + ': ' + cell.cellType}
                  />
                );
              })}
            </div>
            <div className="flex flex-col space-y-1">
              <span className={'text-[9px] font-mono uppercase font-semibold ' + (theme === 'light' ? 'text-slate-400' : 'text-zinc-500')}>Snap metric:</span>
              <select value={heatmapSnapshotType} onChange={(e) => setHeatmapSnapshotType(e.target.value)}
                className={'text-[10px] w-full px-2 py-1.5 outline-none font-sans cursor-pointer rounded-lg border transition-all ' + (theme === 'light' ? 'bg-white border-slate-200/85 hover:border-slate-300 text-slate-700 font-semibold shadow-3xs' : 'bg-[#2c2c2e] border-zinc-700/65 text-zinc-100 hover:bg-zinc-700/80 font-medium')}
              >
                <option value="V_reset">Median V_reset</option>
                <option value="V_set">Median V_set</option>
                <option value="onOff">ON/OFF state ratio</option>
              </select>
            </div>

            <div className="space-y-3 pt-4 border-t border-slate-200/80 dark:border-white/5 mt-auto">
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 font-mono tracking-wider block uppercase">Device Listing ({filteredCellsList.length})</span>
              <div className={'max-h-[180px] overflow-y-auto space-y-1 p-1 rounded-xl border transition-colors custom-scrollbar ' + (theme === 'light' ? 'bg-[#f2f2f7] border-slate-200' : 'bg-black/30 border-zinc-800/85')}>
                {filteredCellsList.map((cell) => {
                  const isActive = selectedCell.row === cell.row && selectedCell.col === cell.col;
                  const dotColor = cell.classificationColor === "emerald" ? "bg-emerald-400" : cell.classificationColor === "amber" ? "bg-amber-400" : cell.classificationColor === "red" ? "bg-red-500" : cell.classificationColor === "purple" ? "bg-purple-400" : "bg-slate-400";
                  return (
                    <button key={'dev-' + cell.row + '-' + cell.col}
                      onClick={() => setSelectedCell({ row: cell.row, col: cell.col })}
                      className={'w-full flex items-center justify-between text-left p-1.5 rounded-lg transition-all cursor-pointer text-[9px] font-mono ' + (isActive
                        ? (theme === 'light' ? 'bg-indigo-100/80 ring-1 ring-indigo-300 text-slate-800' : 'bg-indigo-500/15 ring-1 ring-indigo-500/30 text-white')
                        : (theme === 'light' ? 'hover:bg-slate-200/60 text-slate-600' : 'hover:bg-white/5 text-slate-400'))}
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className={'w-1.5 h-1.5 rounded-full shrink-0 ' + dotColor}></span>
                        <span className="font-semibold">R{cell.row + 1}C{cell.col + 1}</span>
                        <span className={'truncate max-w-[50px] ' + (theme === 'light' ? 'text-slate-400' : 'text-slate-500')}>{cell.cellType.includes("Stable") ? "NV" : cell.cellType.includes("Volatile") ? "V" : cell.cellType.includes("Ohmic") ? "R" : cell.cellType.includes("Stuck-ON") ? "S" : cell.cellType.includes("Stuck-OFF") ? "I" : "?"}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[8px]">{cell.vSet.toFixed(2)}V</span>
                        <span className={'text-[8px] ' + (cell.hScore > 60 ? 'text-emerald-400' : cell.hScore > 30 ? 'text-amber-400' : 'text-red-400')}>{cell.hScore.toFixed(0)}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </aside>

        <main className={'flex-1 flex flex-col min-w-0 transition-colors duration-250 ' + t.bgMain + ' overflow-y-auto'}>
          <div className={'h-12 border-b flex items-center px-4 justify-between shrink-0 transition-colors duration-250 ' + t.bgHeader}>
            <div className="flex space-x-6 h-full items-center">
              <button onClick={() => setActiveTab("IV CURVES")}
                className={'text-[10px] font-bold h-full border-b-2 px-1 transition-all cursor-pointer ' + (activeTab === "IV CURVES" ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") : "text-slate-500 border-transparent hover:text-slate-300")}
              >IV CURVES</button>
              <button onClick={() => setActiveTab("CROSSBAR MATRIX")}
                className={'text-[10px] font-bold h-full border-b-2 px-1 transition-all flex items-center gap-1.5 cursor-pointer ' + (activeTab === "CROSSBAR MATRIX" ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") : "text-slate-500 border-transparent hover:text-slate-300")}
              >CROSSBAR MATRIX <span className="bg-emerald-500/10 text-emerald-500 px-1 py-0.2 text-[8px] rounded font-bold font-mono">{nCols}x{nRows} Array</span></button>
              <button onClick={() => setActiveTab("YIELD METRICS")}
                className={'text-[10px] font-bold h-full border-b-2 px-1 transition-all cursor-pointer ' + (activeTab === "YIELD METRICS" ? (theme === 'light' ? "border-emerald-600 text-emerald-600" : "text-white border-emerald-500") : "text-slate-500 border-transparent hover:text-slate-300")}
              >YIELD METRICS</button>
            </div>
            <div className="flex items-center space-x-3.5 flex-wrap">
              <span className="text-[10px] text-slate-500 uppercase font-mono">Overlay filter:</span>
              <div className={'flex p-0.5 rounded-lg border text-[9px] font-medium transition-all ' + (theme === 'light' ? 'bg-slate-100/90 border-slate-200/80 shadow-3xs' : 'bg-black/35 border-white/5')}>
                {["all","single","custom"].map(mode => {
                  const labels: Record<string,string> = {all:"OVERLAY ALL",single:"SINGLE CYCLE",custom:"CUSTOM"};
                  return (
                    <button key={mode} onClick={() => setCycleFilter(mode)}
                      className={'px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ' + (cycleFilter === mode ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent'))}
                    >{labels[mode]}</button>
                  );
                })}
              </div>
              {cycleFilter === "single" && (
                <div className={'flex items-center space-x-3.5 px-3 py-1 rounded-xl border ml-2 ' + (theme === 'light' ? 'bg-white border-slate-200/80 shadow-3xs' : 'bg-[#1c1c1e] border-white/5')}>
                  <div className={'flex items-center space-x-1 border rounded-lg overflow-hidden p-0.5 ' + (theme === 'light' ? 'border-slate-200/80 bg-slate-50' : 'border-white/10 bg-black/20')}>
                    <button onClick={() => setSingleCycleVal(prev => Math.max(1, prev - 1))}
                      className={'w-5 h-5 flex items-center justify-center text-[10px] font-bold rounded-md transition-colors cursor-pointer ' + (theme === 'light' ? 'hover:bg-slate-200 text-slate-600' : 'hover:bg-white/10 text-slate-300')}
                    >-</button>
                    <input type="number" min="1" max="1000" value={singleCycleVal}
                      onChange={(e) => { const p = parseInt(e.target.value); if (!isNaN(p)) setSingleCycleVal(Math.max(1, Math.min(1000, p))); }}
                      className={'w-10 bg-transparent text-center text-[10px] outline-none font-semibold font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ' + (theme === 'light' ? 'text-slate-800' : 'text-emerald-450')}
                    />
                    <button onClick={() => setSingleCycleVal(prev => Math.min(1000, prev + 1))}
                      className={'w-5 h-5 flex items-center justify-center text-[10px] font-bold rounded-md transition-colors cursor-pointer ' + (theme === 'light' ? 'hover:bg-slate-200 text-slate-600' : 'hover:bg-white/10 text-slate-300')}
                    >+</button>
                  </div>
                  <div className="flex items-center space-x-2.5">
                    <span className="text-[8.5px] text-slate-400 font-mono tracking-tight">1</span>
                    <input type="range" min="1" max="1000" value={singleCycleVal}
                      onChange={(e) => setSingleCycleVal(parseInt(e.target.value))}
                      className={'w-24 h-1 rounded-lg appearance-none cursor-pointer accent-emerald-500 ' + (theme === 'light' ? 'bg-slate-200' : 'bg-zinc-800')}
                    />
                    <span className="text-[8.5px] text-slate-400 font-mono tracking-tight">1k</span>
                    <span className={'text-[10px] font-bold font-mono px-2 py-0.5 rounded-md border transition-all ' + (theme === 'light' ? 'text-emerald-750 bg-emerald-50/50 border-emerald-100' : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20')}>C.{singleCycleVal}</span>
                  </div>
                </div>
              )}
              {cycleFilter === "custom" && (
                <div className="flex items-center space-x-2">
                  <input type="text" value={customFilterText} onChange={(e) => setCustomFilterText(e.target.value)}
                    placeholder="e.g. 10, 50, 500"
                    className={'border px-3 py-1 text-[10px] w-32 outline-none font-mono focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/15 transition-all rounded-lg shadow-3xs ' + (theme === 'light' ? 'bg-white border-slate-200/80 text-slate-800 placeholder-slate-400' : 'bg-[#1c1c1e] border-white/10 text-emerald-405 placeholder-slate-600')}
                  />
                  <span className="text-[8px] text-slate-500 font-mono italic">comma list</span>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 flex flex-col md:flex-row min-h-0">
            <div className="flex-1 border-r border-white/5 relative p-6 flex flex-col">
              {activeTab === "IV CURVES" && (
                <div className="flex-1 flex flex-col">
                  <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
                    <div className="flex flex-col">
                      <span className="text-[10px] text-slate-500 font-mono">
                        {currentScale === "log" ? "Log10 |I| (A) vs. V_appl (V)" : currentScale === "linear_abs" ? "Absolute |I| (A) vs. V_appl (V)" : "Signed I (A) vs. V_appl (V)"}
                      </span>
                      <span className="text-[9px] text-emerald-500 font-semibold font-mono uppercase mt-0.5">
                        Mode: {currentScale === "log" ? "Log" : currentScale === "linear_abs" ? "Absolute Current" : "Raw"}
                      </span>
                    </div>
                    <div className={'flex p-0.5 rounded-lg border text-[9px] font-medium transition-colors ' + (theme === 'light' ? 'bg-slate-100 border-slate-200/80 shadow-3xs' : 'bg-black/40 border-white/10')}>
                      {["log","linear_abs","linear_signed"].map(scale => {
                          const labels: Record<string,string> = {log:"Log",linear_abs:"Absolute Current",linear_signed:"Raw"};
                        return (
                          <button key={scale} onClick={() => setCurrentScale(scale as any)}
                            className={'px-3 py-1 rounded-md text-[9px] font-medium cursor-pointer transition-all duration-200 ' + (currentScale === scale ? (theme === 'light' ? 'bg-white text-slate-800 border border-slate-200/60 shadow-2xs font-semibold' : 'bg-white/10 text-white border border-white/15 font-semibold') : (theme === 'light' ? 'text-slate-500 hover:text-slate-800 border border-transparent' : 'text-slate-400 hover:text-slate-250 border border-transparent'))}
                          >{labels[scale]}</button>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex-1 min-h-[300px]">
                    <Plot
                      data={plotlyTraces}
                      layout={{
                        ...plotlyLayout,
                        title: { text: 'Cell R' + (selectedCell.row + 1) + 'C' + (selectedCell.col + 1) + ' - ' + activeCellData.cellType, font: { size: 12, color: t.graphText } },
                      }}
                      config={{ responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }}
                      style={{ width: '100%', height: '100%' }}
                      useResizeHandler
                    />
                  </div>
                </div>
              )}

              {activeTab === "CROSSBAR MATRIX" && (
                <div className="flex-1 flex flex-col">
                  <div className="mb-3">
                    <h3 className={'text-xs font-bold uppercase tracking-wider mb-1 font-mono ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>
                      Crossbar Array Architecture ({nCols}x{nRows})
                    </h3>
                    <p className={'text-[10px] mb-2 uppercase ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>
                      Metric: {heatmapSnapshotType === "V_reset" ? "Median V_reset" : heatmapSnapshotType === "V_set" ? "Median V_set" : "ON/OFF Ratio"} - click a cell to inspect
                    </p>
                  </div>
                  <div className="flex-1 min-h-[300px]">
                    <Plot
                      data={[{
                        z: heatmapZ,
                        type: 'heatmap',
                        hovertext: heatmapHover,
                        hoverinfo: 'text',
                        hoverlabel: { bgcolor: '#1c1c1e', font: { size: 10, color: '#e2e8f0' }, bordercolor: '#334155' },
                        colorscale: [[0,'#1e1b4b'],[0.15,'#312e81'],[0.3,'#0369a1'],[0.45,'#0d9488'],[0.6,'#65a30d'],[0.75,'#ca8a04'],[0.9,'#ea580c'],[1,'#dc2626']],
                        zsmooth: 'best',
                        showscale: true,
                        colorbar: { title: { text: heatmapSnapshotType, font: { size: 9 } }, tickfont: { size: 8 } },
                      }]}
                      layout={heatmapLayout}
                      config={{ responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }}
                      style={{ width: '100%', height: '100%' }}
                      useResizeHandler
                      onClick={(data: any) => {
                        if (data.points && data.points.length > 0) {
                          const pt = data.points[0];
                          if (pt.y >= 0 && pt.x >= 0) setSelectedCell({ row: pt.y, col: pt.x });
                        }
                      }}
                    />
                  </div>
                  <div className={'p-3.5 rounded-xl mt-3 flex items-center justify-between border ' + (theme === 'light' ? 'bg-indigo-50/20 border-indigo-150 text-slate-750 shadow-3xs' : 'bg-indigo-500/5 border-indigo-500/15 text-slate-300')}>
                    <div>
                      <span className={'text-[9px] font-bold px-2 py-0.5 rounded font-mono uppercase border ' + (theme === 'light' ? 'bg-indigo-50/50 text-indigo-700 border-indigo-200' : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20')}>Heatmap mode</span>
                      <p className={'text-[10.5px] mt-1.5 leading-normal ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>
                        Color intensity represents {heatmapSnapshotType === "V_reset" ? "V_reset" : heatmapSnapshotType === "V_set" ? "V_set" : "ON/OFF Ratio"} values. Hover for cell details including device type.
                      </p>
                    </div>
                    <div className="flex flex-col gap-0.5 shrink-0 ml-4 font-mono">
                      <span className="text-[8px] text-slate-500 uppercase">Legend:</span>
                      <span className="text-[8px] text-emerald-400 flex items-center gap-1">&#9679; NV: Stable RRAM</span>
                      <span className="text-[8px] text-amber-500 flex items-center gap-1">&#9679; V: Volatile</span>
                      <span className="text-[8px] text-red-500 flex items-center gap-1">&#9679; S: Short</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "YIELD METRICS" && (
                <div className="flex-1 flex flex-col space-y-4">
                  <div>
                    <h3 className={'text-xs font-bold uppercase tracking-wider mb-1 font-mono ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>Yield Metrics & Distribution Maps</h3>
                    <p className={'text-[10px] mb-2 uppercase ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Device performance and reliability analysis profiles</p>
                  </div>
                  <div className={t.bgCard + ' rounded-xl p-4 flex flex-col space-y-3.5'}>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Distribution</span>
                        <h4 className={'text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>V_set & V_reset Thresholds</h4>
                      </div>
                      <div className="text-[10px] text-emerald-400 font-mono font-medium">N = {currentProject.devicesAnalyzed} Devices</div>
                    </div>
                    <div className="h-64">
                      <Plot
                        data={[
                          { x: vSetValues, type: 'histogram', name: 'V_set', marker: { color: '#10b981', opacity: 0.7 }, nbinsx: 15, hovertemplate: 'V_set: %{x:.2f} V<br>Count: %{y}<extra></extra>' },
                          { x: vResetValues, type: 'histogram', name: 'V_reset', marker: { color: '#6366f1', opacity: 0.7 }, nbinsx: 15, hovertemplate: 'V_reset: %{x:.2f} V<br>Count: %{y}<extra></extra>' },
                        ]}
                        layout={{
                          barmode: 'overlay', autosize: true, margin: { l: 50, r: 20, t: 10, b: 50 },
                          paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                          font: { color: t.graphText, family: 'ui-monospace, monospace' },
                          xaxis: { title: { text: 'Threshold Voltage (V)', font: { size: 11 } }, gridcolor: t.graphGridLine },
                          yaxis: { title: { text: 'Count', font: { size: 11 } }, gridcolor: t.graphGridLine },
                          legend: { font: { size: 9 }, bgcolor: 'transparent' },
                        }}
                        config={{ responsive: true, displayModeBar: false }}
                        style={{ width: '100%', height: '100%' }}
                        useResizeHandler
                      />
                    </div>
                  </div>
                  <div className={t.bgCard + ' rounded-xl p-4 flex flex-col space-y-3'}>
                    <div className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Reliability</span>
                        <h4 className={'text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>Resistance vs. Program Cycles (Endurance)</h4>
                      </div>
                      <div className="flex gap-4 text-[9px] font-mono text-slate-400">
                        <span className="flex items-center gap-1.1"><span className="w-2.5 h-1 bg-emerald-400 rounded-sm"></span> LRS (R_on)</span>
                        <span className="flex items-center gap-1.1"><span className="w-2.5 h-1 bg-indigo-500 rounded-sm"></span> HRS (R_off)</span>
                      </div>
                    </div>
                    <div className="h-32">
                      <Plot
                        data={[
                          { x: Array.from({ length: 100 }, (_, i) => i + 1), y: Array.from({ length: 100 }, (_, i) => 500 + Math.random() * 100 + Math.sin(i * 0.1) * 30), type: 'scatter', mode: 'lines', name: 'LRS (R_on)', line: { color: '#10b981', width: 1.5 }, hovertemplate: 'Cycle: %{x}<br>R_on: %{y:.0f} Ohm<extra></extra>' },
                          { x: Array.from({ length: 100 }, (_, i) => i + 1), y: Array.from({ length: 100 }, (_, i) => 50000 - i * 50 + Math.random() * 5000 + Math.cos(i * 0.05) * 2000), type: 'scatter', mode: 'lines', name: 'HRS (R_off)', line: { color: '#6366f1', width: 1.5 }, hovertemplate: 'Cycle: %{x}<br>R_off: %{y:.0f} Ohm<extra></extra>' },
                        ]}
                        layout={{
                          autosize: true, margin: { l: 50, r: 20, t: 10, b: 45 },
                          paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                          font: { color: t.graphText, family: 'ui-monospace, monospace', size: 9 },
                          xaxis: { title: { text: 'Cycle #', font: { size: 10 } }, gridcolor: t.graphGridLine, type: 'log' },
                          yaxis: { title: { text: 'Resistance (Ohm)', font: { size: 10 } }, gridcolor: t.graphGridLine, type: 'log' },
                          legend: { font: { size: 8 }, bgcolor: 'transparent' }, showlegend: true,
                        }}
                        config={{ responsive: true, displayModeBar: false }}
                        style={{ width: '100%', height: '100%' }}
                        useResizeHandler
                      />
                    </div>
                  </div>
                  <div className={t.bgCard + ' rounded-xl p-4 flex flex-col space-y-3.5'}>
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="text-[9px] text-slate-500 font-mono uppercase">Data Intelligence</span>
                        <h4 className={'text-xs font-bold uppercase tracking-wider font-mono mt-0.5 ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>Generate Automated Yield Report</h4>
                      </div>
                      <button onClick={() => setShowReport(true)}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-[10px] font-bold text-white rounded-lg flex items-center gap-1.5 transition-all cursor-pointer"
                      ><FileText className="w-3 h-3" /> Generate Report Now</button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <aside className={'w-72 p-4 flex flex-col space-y-4 overflow-y-auto border-l transition-colors duration-250 ' + (theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-black/20 border-white/5')}>
              <div className={'rounded-xl p-4 border ' + (theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5')}>
                <div className="flex items-center justify-between mb-2">
                  <span className={'text-[9px] font-bold uppercase tracking-widest font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Device Classification</span>
                  <div className={'w-2.5 h-2.5 rounded-full ' + (activeCellData.classificationColor === "emerald" ? "bg-emerald-400" : activeCellData.classificationColor === "amber" ? "bg-amber-400" : activeCellData.classificationColor === "red" ? "bg-red-500" : activeCellData.classificationColor === "purple" ? "bg-purple-400" : "bg-slate-400")}></div>
                </div>
                <div className={'text-sm font-bold font-mono tracking-tight flex items-center gap-2 ' + (theme === 'light' ? 'text-slate-900' : 'text-white')}>
                  {activeCellData.classificationColor === "emerald" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  {activeCellData.classificationColor === "amber" && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                  {activeCellData.classificationColor === "red" && <XCircle className="w-4 h-4 text-red-400" />}
                  {activeCellData.classificationColor === "slate" && <XCircle className="w-4 h-4 text-slate-400" />}
                  {activeCellData.classificationColor === "purple" && <Activity className="w-4 h-4 text-purple-400" />}
                  {activeCellData.cellType}
                </div>
                <p className={'text-[9px] mt-1 leading-relaxed ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>{activeCellData.detailMessage}</p>
              </div>

              <div className={'rounded-xl p-4 border ' + (theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5')}>
                <div className="flex items-center justify-between">
                  <span className={'text-[9px] font-bold uppercase tracking-widest font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Health Score</span>
                  <div className={'font-mono text-lg font-bold ' + (activeCellData.hScore > 80 ? "text-emerald-400" : activeCellData.hScore > 40 ? "text-amber-400" : "text-red-400")}>
                    {activeCellData.hScore.toFixed(1)}<span className="text-[10px] text-slate-500">/100</span>
                  </div>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
                  <div className={'h-full rounded-full transition-all duration-500 ' + (activeCellData.hScore > 80 ? "bg-emerald-400" : activeCellData.hScore > 40 ? "bg-amber-400" : "bg-red-400")} style={{ width: Math.min(100, activeCellData.hScore) + '%' }}></div>
                </div>
                <div className="flex justify-between text-[8px] text-slate-600 font-mono mt-1"><span>POOR</span><span>GOOD</span><span>EXCELLENT</span></div>
              </div>

              <div className={'rounded-xl p-4 border ' + (theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5')}>
                <span className={'text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Switching Parameters</span>
                <div className="flex flex-col space-y-3">
                  <div className="flex items-center justify-between">
                    <span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>V_set</span>
                    <div className="flex items-center gap-2">
                      <input type="number" step="0.01" value={activeCellData.vSet}
                        onChange={(e) => { const p = parseFloat(e.target.value); if (!isNaN(p)) updateActiveCellParam("vSet", p); }}
                        className={'w-20 text-right text-[11px] font-mono font-bold bg-transparent outline-none border-b border-dashed focus:border-emerald-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ' + (theme === 'light' ? 'text-slate-800 border-slate-300' : 'text-white border-slate-600')}
                      /><span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>V</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>V_reset</span>
                    <div className="flex items-center gap-2">
                      <input type="number" step="0.01" value={activeCellData.vReset}
                        onChange={(e) => { const p = parseFloat(e.target.value); if (!isNaN(p)) updateActiveCellParam("vReset", p); }}
                        className={'w-20 text-right text-[11px] font-mono font-bold bg-transparent outline-none border-b border-dashed focus:border-emerald-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ' + (theme === 'light' ? 'text-slate-800 border-slate-300' : 'text-white border-slate-600')}
                      /><span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>V</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>I_on/I_off</span>
                    <span className={'text-[11px] font-mono font-bold ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>{activeCellData.onOff.toFixed(1)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>Sweep Cycles</span>
                    <span className={'text-[11px] font-mono font-bold ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>{ivData?.sweeps?.length ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={'text-[10px] font-mono ' + (theme === 'light' ? 'text-slate-600' : 'text-slate-400')}>C_switching</span>
                    <span className={'text-[11px] font-mono font-bold ' + (theme === 'light' ? 'text-slate-800' : 'text-white')}>{activeCellData.cellType.includes("Stuck") ? "0%" : "100%"}</span>
                  </div>
                  {editedParams[activeProjectIdx + '-' + selectedCell.row + '-' + selectedCell.col] && (
                    <button onClick={resetCellParams} className="text-[9px] text-red-400 hover:text-red-300 font-mono underline mt-1">Reset to defaults</button>
                  )}
                </div>
              </div>

              <div className={'rounded-xl p-4 border ' + (theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5')}>
                <span className={'text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Quick Actions</span>
                <div className="flex flex-col space-y-2">
                  <button onClick={() => setProbeLocked(prev => !prev)}
                    className={'w-full flex items-center justify-between text-[10px] p-2.5 rounded-lg border transition-all cursor-pointer ' + (theme === 'light' ? 'bg-slate-100/60 border-slate-200/80 text-slate-700 hover:bg-slate-200/60' : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10')}
                  >
                    <span className="flex items-center gap-2">{probeLocked ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}{probeLocked ? "Probe Locked" : "Probe Retracted"}</span>
                    <span className={'text-[8px] uppercase font-mono font-bold ' + (probeLocked ? 'text-emerald-400' : 'text-amber-400')}>{probeLocked ? "Safe" : "Danger"}</span>
                  </button>
                  <button onClick={triggerExportTSV}
                    className={'w-full flex items-center justify-between text-[10px] p-2.5 rounded-lg border transition-all cursor-pointer ' + (theme === 'light' ? 'bg-slate-100/60 border-slate-200/80 text-slate-700 hover:bg-slate-200/60' : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10')}
                  >
                    <span className="flex items-center gap-2"><Download className="w-3 h-3" /> Export Matrix TSV</span>
                    <span className="text-[8px] text-slate-400 font-mono">{cellsList.length} cells</span>
                  </button>
                </div>
              </div>

              <div className={'rounded-xl p-4 border ' + (theme === 'light' ? 'bg-white border-slate-200 shadow-xs' : 'bg-[#0c0c0d] border-white/5')}>
                <span className={'text-[9px] font-bold uppercase tracking-widest font-mono block mb-3 ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Global Statistics</span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className={'text-[9px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Yield</p>
                    <p className={'text-lg font-bold font-mono ' + (dynamicGlobalYield > 60 ? 'text-emerald-400' : dynamicGlobalYield > 30 ? 'text-amber-400' : 'text-red-400')}>{dynamicGlobalYield} <span className="text-[10px]">%</span></p>
                  </div>
                  <div>
                    <p className={'text-[9px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Analyzed</p>
                    <p className={'text-sm font-semibold font-mono ' + (theme === 'light' ? 'text-slate-800' : 'text-zinc-200')}>{currentProject.devicesAnalyzed}</p>
                  </div>
                  <div>
                    <p className={'text-[9px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Volatile</p>
                    <p className="text-sm font-semibold text-amber-500 font-mono">{dynamicVolatiles}</p>
                  </div>
                  <div>
                    <p className={'text-[9px] font-mono ' + (theme === 'light' ? 'text-slate-500' : 'text-slate-500')}>Median Vset</p>
                    <p className={'text-sm font-semibold font-mono ' + (theme === 'light' ? 'text-slate-800' : 'text-zinc-200')}>{dashboardData?.aggregate?.median_vset?.toFixed(2) ?? "0.00"}V</p>
                  </div>
                </div>
              </div>

              {showReport && (
                <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-6" onClick={() => setShowReport(false)}>
                  <div className={'max-w-2xl w-full max-h-[80vh] overflow-y-auto rounded-2xl border p-6 shadow-2xl ' + (theme === 'light' ? 'bg-white border-slate-200 text-slate-800' : 'bg-[#0c0c0d] border-white/10 text-slate-200')} onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-between items-center mb-4">
                      <h2 className="text-sm font-bold uppercase font-mono tracking-wider">Automated Yield Report</h2>
                      <button onClick={() => setShowReport(false)} className="text-slate-500 hover:text-slate-300 text-sm cursor-pointer">&#10005;</button>
                    </div>
                    <div className="text-[10px] leading-relaxed space-y-3">
                      <div className={'p-4 rounded-xl border ' + (theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-white/5 border-white/5')}>
                        <p className="text-[11px] font-bold uppercase font-mono mb-2 tracking-wider">Array Summary</p>
                        <p>Project: <span className="text-white font-bold">NP-X1-{currentProject.id.toUpperCase()}</span></p>
                        <p>Yield: <span className="text-emerald-400 font-bold">{dynamicGlobalYield}%</span></p>
                        <p>Cells Analyzed: <span className="font-bold">{currentProject.devicesAnalyzed}</span></p>
                        <p>Volatile Classifications: <span className="text-amber-400 font-bold">{dynamicVolatiles}</span></p>
                      </div>
                      <div className={'p-4 rounded-xl border ' + (theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-white/5 border-white/5')}>
                        <p className="text-[11px] font-bold uppercase font-mono mb-2 tracking-wider">Material System Notes</p>
                        Bipolar resistive memories fabricated with a {currentProject.materialStack} architecture exhibit excellent switching distributions. A {nCols}x{nRows} test grid analysis shows a highly structured conductance model with {dynamicGlobalYield}% yield. There are a total of {cellsList.filter(c => c.cellType.includes("Stuck")).length} short/open circuit anomalies and {cellsList.filter(c => c.cellType.includes("Volatile")).length} volatile cells triggered on high reset sweep currents.
                      </div>
                    </div>
                    <button onClick={() => setShowReport(false)} className="mt-5 w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold rounded-lg transition-all cursor-pointer">Close Report</button>
                  </div>
                </div>
              )}
            </aside>
          </div>
        </main>
      </div>

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
