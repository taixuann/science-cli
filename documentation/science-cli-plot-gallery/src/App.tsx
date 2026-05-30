import React, { useState, useEffect, useRef } from "react";
import { 
  FolderGit2, 
  Layers, 
  Binary, 
  Activity, 
  Sliders, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Download, 
  Copy, 
  Check, 
  Cpu, 
  RotateCcw, 
  Search, 
  Columns, 
  Sun, 
  Moon, 
  Eye, 
  Info,
  ChevronRight,
  TrendingUp,
  SlidersHorizontal,
  X,
  Sparkles
} from "lucide-react";

// HSL color mapper for metrics
const getHeatmapColor = (metric: string, val: number | null, maxVal: number) => {
  if (val === null) return "rgba(100, 116, 139, 0.1)"; // unmeasured blank
  
  const pct = maxVal > 0 ? val / maxVal : 0;
  // Use lightness scaling (L) from 90% (lowest value) down to 35% (highest value) for contrast and visibility
  const lightness = 85 - pct * 45; 
  
  switch (metric) {
    case "yield":
      return `hsl(142, 75%, ${lightness}%)`; // Green spectrum (Emerald)
    case "ratio":
      return `hsl(262, 75%, ${lightness}%)`; // Indigo/Purple
    case "vset":
      return `hsl(187, 80%, ${lightness}%)`; // Cyan
    case "vreset":
      return `hsl(24, 85%, ${lightness}%)`; // Red/Orange
    case "file_count":
      return `hsl(217, 80%, ${lightness}%)`; // Blue
    default:
      return `hsl(217, 80%, ${lightness}%)`;
  }
};

interface FileItem {
  name: string;
  path: string;
  type: string;
  size?: string;
  created?: string;
  dimensions?: string;
  category?: "distinct" | "overlay";
}

interface StepItem {
  name: string;
  files: FileItem[];
}

interface Protocol {
  name: string;
  steps: StepItem[];
  total_files: number;
  measured_cells: number;
  switching_yield: number;
}

interface ProjectData {
  project_name: string;
  protocols: Protocol[];
  stats: {
    total_protocols: number;
    total_files: number;
  };
}

export default function App() {
  // Theme state: light, dark, oled
  const [theme, setTheme] = useState<"light" | "dark" | "oled">("dark");
  
  // API and Workspace States
  const [projectsList, setProjectsList] = useState<string[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("res_internship");
  const [projectData, setProjectData] = useState<ProjectData | null>(null);
  const [activeProtocol, setActiveProtocol] = useState<Protocol | null>(null);
  const [activeStep, setActiveStep] = useState<StepItem | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [columnCount, setColumnCount] = useState<3 | 4 | 5>(4);
  const [activeTab, setActiveTab] = useState<"gallery" | "crossbar">("gallery");

  // Dashboard / Crossbar states
  const [metric, setMetric] = useState<string>("ratio");
  const [materialFilter, setMaterialFilter] = useState<string>(""); // HfOx, AlOx or ""
  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [cellIVData, setCellIVData] = useState<any>(null);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [histograms, setHistograms] = useState<any>(null);

  // Lightbox view state
  const [lightboxFile, setLightboxFile] = useState<FileItem | null>(null);
  const [zoomScale, setZoomScale] = useState<number>(1.0);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDraggingLogo, setIsDraggingLogo] = useState<boolean>(false);
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Selected Gallery File State
  const [selectedGalleryFile, setSelectedGalleryFile] = useState<FileItem | null>(null);

  // Sync selected gallery file with step change
  useEffect(() => {
    if (activeStep && activeStep.files && activeStep.files.length > 0) {
      // Prefer first overlay file, fallback to first distinct file, fallback to first file
      const overlays = activeStep.files.filter((f) => f.category === "overlay" || !f.category);
      const distincts = activeStep.files.filter((f) => f.category === "distinct");
      if (overlays.length > 0) {
        setSelectedGalleryFile(overlays[0]);
      } else if (distincts.length > 0) {
        setSelectedGalleryFile(distincts[0]);
      } else {
        setSelectedGalleryFile(activeStep.files[0]);
      }
    } else {
      setSelectedGalleryFile(null);
    }
  }, [activeStep]);

  // Init - Fetch Projects
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await fetch("/api/projects");
        const data = await res.json();
        if (data.projects && data.projects.length > 0) {
          setProjectsList(data.projects);
          // Auto select first
          if (!data.projects.includes(selectedProject)) {
            setSelectedProject(data.projects[0]);
          }
        }
      } catch (err) {
        console.error("Failed to load projects workspace. Using fallbacks.", err);
        setProjectsList(["res_internship", "non-res_odon-vallet", "non-res_phd-application", "test-project"]);
      }
    };
    fetchProjects();
  }, []);

  // Fetch Project details when active project switches
  useEffect(() => {
    const fetchProjectDetails = async () => {
      setIsLoading(true);
      try {
        const url = `/api/project?project=${selectedProject}`;
        const res = await fetch(url, {
          headers: {
            "X-Project-Override": selectedProject
          }
        });
        const data = await res.json();
        setProjectData(data);
        
        // Reset sub selections
        if (data.protocols && data.protocols.length > 0) {
          const firstProto = data.protocols[0];
          setActiveProtocol(firstProto);
          if (firstProto.steps && firstProto.steps.length > 0) {
            setActiveStep(firstProto.steps[0]);
          } else {
            setActiveStep(null);
          }
        } else {
          setActiveProtocol(null);
          setActiveStep(null);
        }
      } catch (err) {
        console.error("Error fetching project metadata.", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProjectDetails();
  }, [selectedProject]);

  // Fetch heatmap and histograms when protocol switches
  useEffect(() => {
    if (!activeProtocol) {
      setHeatmapData(null);
      setHistograms(null);
      return;
    }
    
    const fetchProtocolDashboard = async () => {
      try {
        // Fetch heatmap
        const heatUrl = `/api/protocol/${encodeURIComponent(activeProtocol.name)}/heatmap?metric=${metric}&material=${materialFilter}&project=${selectedProject}`;
        const heatRes = await fetch(heatUrl, { headers: { "X-Project-Override": selectedProject } });
        const heatJson = await heatRes.json();
        setHeatmapData(heatJson);

        // Fetch histograms
        const histUrl = `/api/protocol/${encodeURIComponent(activeProtocol.name)}/histograms?project=${selectedProject}`;
        const histRes = await fetch(histUrl, { headers: { "X-Project-Override": selectedProject } });
        const histJson = await histRes.json();
        setHistograms(histJson);
      } catch (err) {
        console.error("Failed fetching dashboard metrics", err);
      }
    };
    fetchProtocolDashboard();
  }, [activeProtocol, metric, materialFilter, selectedProject]);

  // Fetch Device IV curves when cell clicked
  const handleCellSelect = async (cellId: string) => {
    if (!activeProtocol) return;
    setSelectedCell(cellId);
    try {
      const ivUrl = `/api/protocol/${encodeURIComponent(activeProtocol.name)}/device/${cellId}/iv?project=${selectedProject}`;
      const res = await fetch(ivUrl, { headers: { "X-Project-Override": selectedProject } });
      const data = await res.json();
      setCellIVData(data);
    } catch (err) {
      console.error("Error retrieving device curves", err);
    }
  };

  const copyIVDataToClipboard = () => {
    if (!cellIVData || !cellIVData.sweeps || cellIVData.sweeps.length === 0) return;
    
    let text = "Voltage (V)\tCurrent (A)\tSweep Label\n";
    cellIVData.sweeps.forEach((swp: any) => {
      swp.voltage.forEach((v: number, i: number) => {
        text += `${v}\t${swp.current[i]}\t${swp.label}\n`;
      });
    });

    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => {
      setIsCopied(false);
    }, 2000);
  };

  // Lightbox Pan & Zoom handlers
  const handlePanStart = (e: React.MouseEvent) => {
    setIsDraggingLogo(true);
    panStartRef.current = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
  };

  const handlePanMove = (e: React.MouseEvent) => {
    if (!isDraggingLogo) return;
    setPanOffset({
      x: e.clientX - panStartRef.current.x,
      y: e.clientY - panStartRef.current.y
    });
  };

  const handlePanEnd = () => {
    setIsDraggingLogo(false);
  };

  const downloadPlotFile = (file: FileItem) => {
    const link = document.createElement("a");
    link.href = `/files/${file.path}`;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Find max value in heatmap for normalized HSL scaling
  const getHeatmapMax = () => {
    if (!heatmapData || !heatmapData.data) return 1;
    let max = 0.0001;
    heatmapData.data.forEach((row: (number | null)[]) => {
      row.forEach((v) => {
        if (v !== null && v > max) max = v;
      });
    });
    return max;
  };

  const maxVal = getHeatmapMax();

  // Helper values for display theme classes
  const themeClasses = {
    light: "theme-light bg-slate-50 text-slate-900",
    dark: "theme-dark bg-slate-950 text-slate-100",
    oled: "theme-oled bg-black text-white"
  };

  return (
    <div className={`flex w-screen min-height-screen font-sans antialiased transition-colors duration-300 ${themeClasses[theme]}`}>
      
      {/* SIDEBAR NAVIGATION PANEL */}
      <aside className={`w-[260px] shrink-0 min-h-screen p-5 flex flex-col border-r border-slate-200/20 ${theme === 'light' ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
        
        {/* Logo/Brand */}
        <div className="flex items-center gap-3 pb-5 mb-5 border-b border-slate-200/20">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-indigo-500 to-indigo-600 flex items-center justify-center text-white font-mono font-bold text-lg shadow-md">
            &mu;
          </div>
          <div>
            <span className="text-sm font-bold tracking-tight block">science-cli</span>
            <span className="text-[10px] text-indigo-500 font-mono tracking-wider uppercase block font-semibold">plot gallery</span>
          </div>
        </div>

        {/* Dynamic Project switching */}
        <div className="mb-6">
          <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block mb-2 font-bold">
            Project Workspace
          </label>
          <div className="relative">
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className={`w-full py-2 px-3 pr-8 rounded-lg text-xs font-mono font-semibold appearance-none border transition-colors outline-none cursor-pointer ${
                theme === 'light' 
                  ? 'bg-slate-50 border-slate-300 hover:bg-slate-100 text-slate-800' 
                  : 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-slate-200'
              }`}
            >
              {projectsList.map((proj) => (
                <option key={proj} value={proj}>
                  {proj}
                </option>
              ))}
            </select>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
              <ChevronRight className="w-3.5 h-3.5 rotate-90" />
            </div>
          </div>
        </div>

        {/* Current Lab context widget */}
        <div className={`rounded-lg p-3.5 mb-5 border border-slate-200/20 text-xs ${theme === 'light' ? 'bg-slate-50 text-slate-600' : 'bg-slate-950/50 text-slate-300'}`}>
          <div className="text-[9px] font-mono uppercase text-indigo-500 mb-2 tracking-wider font-bold">
            Live Lab Session
          </div>
          <div className="space-y-1.5 font-mono text-[11px]">
            <div className="flex items-center justify-between gap-1">
              <span className="text-slate-400">Project:</span>
              <span className="font-bold truncate max-w-[120px] text-indigo-400">{selectedProject}</span>
            </div>
            <div className="flex items-center justify-between gap-1">
              <span className="text-slate-400">Protocol:</span>
              <span className="font-bold truncate max-w-[120px] text-emerald-400">{activeProtocol ? activeProtocol.name : "-"}</span>
            </div>
            <div className="flex items-center justify-between gap-1">
              <span className="text-slate-400">Active Step:</span>
              <span className="font-bold truncate max-w-[120px] text-amber-500">{activeStep ? activeStep.name : "-"}</span>
            </div>
          </div>
        </div>

        {/* Nested Protocol Chooser Sub-menu */}
        <div className="flex-1 flex flex-col min-h-0">
          <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block mb-2 font-bold">
            Protocols & Steps
          </label>
          <div className="space-y-1.5 overflow-y-auto pr-1 flex-1">
            {projectData?.protocols.map((proto) => {
              const isSelected = activeProtocol?.name === proto.name;
              return (
                <div key={proto.name} className="space-y-1">
                  <button
                    onClick={() => {
                      setActiveProtocol(proto);
                      setActiveStep(proto.steps.length > 0 ? proto.steps[0] : null);
                    }}
                    className={`w-full flex flex-col text-left p-2.5 rounded-lg border transition-all relative group ${
                      isSelected 
                        ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400 font-semibold' 
                        : 'border-transparent text-slate-400 hover:bg-slate-200/10 hover:text-slate-200'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full mb-1">
                      <span className="text-[12px] font-mono font-medium truncate max-w-[150px]">{proto.name}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono font-medium ${
                        isSelected ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/20' : 'bg-slate-200/10 text-slate-400'
                      }`}>
                        {proto.steps.length}s
                      </span>
                    </div>
                    
                    {/* Micro aggregates metadata block on selected protocol */}
                    <div className="flex items-center gap-3.5 mt-1 text-[9px] font-mono text-slate-400 opacity-80">
                      <span title="Total Files">📂 {proto.total_files}f</span>
                      <span className="text-emerald-400" title="Switching yield percentile">⚡ {proto.switching_yield}%</span>
                      <span title="Last updated time scale">⏱️ Active</span>
                    </div>
                  </button>

                  {/* Steps dynamically slid opened beneath active Protocol */}
                  {isSelected && proto.steps.length > 0 && (
                    <div className="pl-3.5 border-l border-slate-200/10 mt-1 mb-2.5 space-y-1">
                      {proto.steps.map((st) => {
                        const isStepSelected = activeStep?.name === st.name;
                        return (
                          <button
                            key={st.name}
                            onClick={() => setActiveStep(st)}
                            className={`w-full flex items-center justify-between py-1.5 px-2.5 rounded-md text-[11px] font-mono text-left transition-all ${
                              isStepSelected
                                ? 'bg-amber-500/10 text-amber-500 font-semibold'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-200/5'
                            }`}
                          >
                            <span className="truncate max-w-[130px] pr-1">{st.name}</span>
                            <span className="opacity-60 text-[9px]">{st.files.length}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Connection status badge */}
        <div className="pt-4 border-t border-slate-200/10 flex items-center justify-between text-[11px] font-mono text-slate-400 mt-auto">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>cli online</span>
          </div>
          <span className="text-[10px] text-slate-500">v1.4.2</span>
        </div>

      </aside>

      {/* CORE VIEWPORT */}
      <main className="flex-1 p-4 md:p-5 flex flex-col min-w-0 h-full overflow-hidden">
        
        {/* Navigation Breadcrumbs & Top bar */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200/10 mb-3 md:mb-4">
          <nav className="flex items-center gap-1.5 font-mono text-[11px] truncate">
            <span className="text-indigo-400 cursor-pointer hover:underline" onClick={() => setSelectedProject(projectsList[0] || "res_internship")}>projects</span>
            <span className="text-slate-500">/</span>
            <span className="text-slate-300 font-semibold truncate max-w-[100px]" title={selectedProject}>{selectedProject}</span>
            {activeProtocol && (
              <>
                <span className="text-slate-400">/</span>
                <span className="text-emerald-400 truncate max-w-[100px]" title={activeProtocol.name}>{activeProtocol.name}</span>
              </>
            )}
            {activeStep && (
              <>
                <span className="text-slate-400">/</span>
                <span className="text-amber-500 truncate max-w-[125px]" title={activeStep.name}>{activeStep.name}</span>
              </>
            )}
          </nav>

          {/* Theme & Search actions aligned row */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-end flex-wrap sm:flex-nowrap">
            
            {/* Filter Search Input (Directly left of Light/Dark/Oled controls) */}
            {activeTab === "gallery" && activeStep && (
              <div className="relative w-full sm:w-48 md:w-56 shrink-0">
                <Search className="w-3 h-3 text-slate-400 absolute left-2 top-11/12 -translate-y-1/2 top-1/2" />
                <input
                  type="text"
                  placeholder="Filter filenames..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={`w-full font-mono text-[10px] pl-7 pr-2.5 py-1 rounded-lg border outline-none ${
                    theme === 'light'
                      ? 'bg-white border-slate-300 text-slate-900 focus:border-indigo-500'
                      : 'bg-slate-950/80 border-slate-800 text-slate-200 focus:border-indigo-500'
                  }`}
                />
              </div>
            )}

            {/* Theme controls */}
            <div className={`flex items-center p-0.5 rounded-full border border-slate-200/10 shrink-0 ${theme === 'light' ? 'bg-slate-100' : 'bg-slate-900'}`}>
              <button
                onClick={() => setTheme("light")}
                className={`flex items-center gap-1 py-1 px-3 rounded-full text-[9px] uppercase font-mono tracking-wider font-semibold transition-all ${
                  theme === "light"
                    ? "bg-slate-800 text-white shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Sun className="w-2.5 h-2.5" />
                <span>Light</span>
              </button>
              <button
                onClick={() => setTheme("dark")}
                className={`flex items-center gap-1 py-1 px-3 rounded-full text-[9px] uppercase font-mono tracking-wider font-semibold transition-all ${
                  theme === "dark"
                    ? "bg-slate-700 text-white shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Moon className="w-2.5 h-2.5" />
                <span>Dark</span>
              </button>
              <button
                onClick={() => setTheme("oled")}
                className={`flex items-center gap-1 py-1 px-3 rounded-full text-[9px] uppercase font-mono tracking-wider font-semibold transition-all ${
                  theme === "oled"
                    ? "bg-neutral-800 text-white border border-neutral-700 shadow"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Cpu className="w-2.5 h-2.5 text-amber-500" />
                <span>Oled</span>
              </button>
            </div>
          </div>
        </header>

        {/* MAIN BODY AREA */}
        {isLoading ? (
          <div className="flex-1 flex flex-col justify-center items-center py-20">
            <div className="relative w-12 h-12 mb-3">
              <div className="absolute inset-0 rounded-full border-4 border-indigo-500/10"></div>
              <div className="absolute inset-0 rounded-full border-4 border-indigo-500 border-t-transparent animate-spin"></div>
            </div>
            <div className="text-slate-400 font-mono text-xs">Scanning multi-project workspace database ...</div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden space-y-3">
            
            {/* Title Section */}
            <div className="flex items-center justify-between shrink-0">
              <div>
                <h1 className="text-base font-bold tracking-tight text-slate-100">
                  {activeProtocol ? activeProtocol.name : selectedProject}
                </h1>
                <p className="text-[10px] text-slate-400 mt-0.5 font-mono">
                  {activeProtocol 
                    ? `Interactive laboratory diagnostics dashboard & bullseye heatmap curves` 
                    : `Select a protocol in the left sidebar directory menu to display analytics.`
                  }
                </p>
              </div>
            </div>

            {/* TAB VIEW SELECTOR */}
            {activeProtocol && (
              <div className="flex items-center justify-between border-b border-slate-200/10 pb-0 flex-wrap gap-2 shrink-0">
                <div className="flex gap-1">
                  <button
                    onClick={() => setActiveTab("gallery")}
                    className={`py-1 px-3 text-[11px] font-mono font-semibold border-b transition-all ${
                      activeTab === "gallery"
                        ? "border-amber-500 text-amber-500 font-bold"
                        : "border-transparent text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Figures Gallery
                  </button>
                  <button
                    onClick={() => setActiveTab("crossbar")}
                    className={`py-1 px-3 text-[11px] font-mono font-semibold border-b transition-all ${
                      activeTab === "crossbar"
                        ? "border-indigo-500 text-indigo-500 font-bold"
                        : "border-transparent text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    6x6 Crossbar Heatmap & IV Curves
                  </button>
                </div>

                {/* Additional gallery controls shown in Gallery tab */}
                {activeTab === "gallery" && activeStep && (
                  <div className="hidden sm:flex items-center gap-3">
                    {/* Columns grid filter */}
                    <div className="flex items-center gap-1.5 border border-slate-200/10 p-1.5 rounded-lg bg-slate-900/40">
                      <Columns className="w-3 h-3 text-slate-400" />
                      <span className="text-[10px] font-mono text-slate-400 mr-1.5">Cols:</span>
                      {[3, 4, 5].map((col) => (
                        <button
                          key={col}
                          onClick={() => setColumnCount(col as any)}
                          className={`w-5 h-5 rounded flex items-center justify-center font-mono text-[10px] font-bold transition-all ${
                            columnCount === col
                              ? "bg-amber-500 text-slate-950"
                              : "text-slate-400 hover:bg-slate-250/10 hover:text-slate-200"
                          }`}
                        >
                          {col}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

                   {/* TAB CONTENT: GALLERY */}
            {activeTab === "gallery" && activeProtocol && (
              <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden space-y-3">
                
                {/* Split layout: Left: Big space of figures | Right: Panel of small figures list gallery */}
                {activeStep ? (
                  activeStep.files && activeStep.files.length > 0 ? (
                    <div className="flex-1 grid grid-cols-1 xl:grid-cols-5 gap-3.5 items-stretch min-h-0 min-w-0 h-full">
                      
                      {/* Left space: Big space of figures (takes 4 of 5 columns - 80% width) */}
                      <div className={`xl:col-span-4 flex flex-col justify-between p-3.5 rounded-2xl border border-slate-200/10 relative h-full min-h-0 ${
                        theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-slate-900/40 border-slate-800'
                      }`}>
                        
                        {/* Header of active figure */}
                        {selectedGalleryFile ? (
                          <div className="flex flex-col h-full justify-between space-y-2.5 min-h-0">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-200/5 shrink-0">
                              <div>
                                <span className="text-[9px] text-slate-400 font-mono block">
                                  Path: <span className="text-indigo-400 font-semibold">{selectedGalleryFile.path}</span>
                                </span>
                                <div className="flex items-center gap-1.5 mt-0.5">
                                  <span className={`text-xs font-bold font-mono tracking-tight ${theme === 'light' ? 'text-slate-950' : 'text-white'}`}>
                                    {selectedGalleryFile.name}
                                  </span>
                                  <span className="text-[8px] font-mono font-bold px-1 py-0.5 rounded uppercase bg-indigo-500/10 text-indigo-400">
                                    {selectedGalleryFile.type}
                                  </span>
                                </div>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={() => setLightboxFile(selectedGalleryFile)}
                                  className={`p-1 px-2.5 rounded-md border text-[9px] font-mono flex items-center gap-1 transition-all ${
                                    theme === 'light'
                                      ? 'bg-white border-slate-300 hover:bg-slate-100 text-slate-800'
                                      : 'border-slate-800 bg-slate-950/60 hover:bg-slate-950 text-slate-300'
                                  }`}
                                  title="Expand to Fullscreen Lightbox with Zoom & Pan"
                                >
                                  <Maximize2 className="w-3 h-3" />
                                  <span>Maximize</span>
                                </button>
                                <button
                                  onClick={() => downloadPlotFile(selectedGalleryFile)}
                                  className="p-1 px-2.5 rounded-md border border-indigo-500/15 bg-indigo-500/10 hover:bg-indigo-500/20 text-[9px] font-mono text-indigo-400 flex items-center gap-1 transition-all font-semibold"
                                  title="Download File"
                                >
                                  <Download className="w-3 h-3" />
                                  <span>Download</span>
                                </button>
                              </div>
                            </div>

                            {/* Center Canvas display for active figure */}
                            <div className="flex-1 min-h-[460px] md:min-h-[540px] xl:min-h-[620px] bg-slate-950 rounded-xl border border-slate-800/80 flex items-center justify-center overflow-hidden p-4 relative group">
                              {selectedGalleryFile.type === "svg" || selectedGalleryFile.type === "pdf" ? (
                                <iframe
                                  src={`/files/${selectedGalleryFile.path}${selectedGalleryFile.type === "pdf" ? "#toolbar=0" : ""}`}
                                  className="w-full h-full min-h-[440px] md:min-h-[520px] xl:min-h-[600px] border-none scale-[1.01]"
                                  title={selectedGalleryFile.name}
                                />
                              ) : (
                                <img
                                  src={`/files/${selectedGalleryFile.path}`}
                                  className="w-full h-full max-h-[540px] xl:max-h-[600px] object-contain rounded-lg shadow-lg group-hover:scale-[1.01] transition-transform duration-300"
                                  alt={selectedGalleryFile.name}
                                  referrerPolicy="no-referrer"
                                />
                              )}
                              
                              {/* Overlay indicator */}
                              <div className="absolute bottom-3 right-3 bg-slate-900/80 backdrop-blur border border-slate-800 rounded px-2 py-0.5 text-[8px] font-mono text-slate-450 pointer-events-none">
                                🔬 Active diagnostics visualizer &middot; Vector scaling
                              </div>
                            </div>
                            
                            {/* Metadata specs of figure */}
                            <div className="pt-2 border-t border-slate-200/5 grid grid-cols-2 sm:grid-cols-4 gap-3 text-center font-mono text-[9px]">
                              <div className={`p-1.5 rounded-lg border ${theme === 'light' ? 'bg-slate-100/50 border-slate-200' : 'bg-slate-950/30 border-slate-900'}`}>
                                <span className="text-slate-500 block text-[8px] mb-0.5">Created On</span>
                                <span className={`font-bold ${theme === 'light' ? 'text-slate-800' : 'text-slate-300'}`}>{selectedGalleryFile.created || "2026-05-29"}</span>
                              </div>
                              <div className={`p-1.5 rounded-lg border ${theme === 'light' ? 'bg-slate-100/50 border-slate-200' : 'bg-slate-950/30 border-slate-900'}`}>
                                <span className="text-slate-500 block text-[8px] mb-0.5">File Size</span>
                                <span className={`font-bold ${theme === 'light' ? 'text-slate-800' : 'text-slate-300'}`}>{selectedGalleryFile.size || "15.4 KB"}</span>
                              </div>
                              <div className={`p-1.5 rounded-lg border ${theme === 'light' ? 'bg-slate-100/50 border-slate-200' : 'bg-slate-950/30 border-slate-900'}`}>
                                <span className="text-slate-500 block text-[8px] mb-0.5">Dimensions</span>
                                <span className={`font-bold ${theme === 'light' ? 'text-slate-800' : 'text-slate-300'}`}>{selectedGalleryFile.dimensions || "1280x800 px"}</span>
                              </div>
                              <div className={`p-1.5 rounded-lg border ${theme === 'light' ? 'bg-slate-100/50 border-slate-200' : 'bg-slate-950/30 border-slate-900'}`}>
                                <span className="text-slate-500 block text-[8px] mb-0.5">Quality Scale</span>
                                <span className="text-indigo-450 font-bold">Vector High-Fid</span>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3">
                            <Eye className="w-10 h-10 text-slate-600 animate-pulse" />
                            <span className="text-xs font-mono text-slate-400 font-semibold">Select a figure from the list on the right side to display it here.</span>
                          </div>
                        )}
                        
                      </div>

                      {/* Right space: Small figures list gallery (takes 1 of 5 columns - 20% width) */}
                      <div className={`xl:col-span-1 flex flex-col p-3 rounded-2xl border max-h-[640px] xl:max-h-[740px] ${
                        theme === 'light' ? 'bg-slate-50 border-slate-200' : 'bg-slate-900/20 border-slate-850'
                      }`}>
                        <div className="pb-2 border-b border-slate-200/10 mb-2 flex items-center justify-between">
                          <span className="text-[9px] font-mono uppercase tracking-wider text-slate-450 font-bold">
                            Figures ({activeStep.files.filter((f) => f.name.toLowerCase().includes(searchQuery.toLowerCase())).length})
                          </span>
                          <span className="text-[8px] font-mono text-indigo-400 font-bold uppercase bg-indigo-500/10 px-1 py-0.5 rounded">
                            Select
                          </span>
                        </div>

                        {/* List viewport */}
                        <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5 font-mono text-[11px] scrollbar-thin">
                          {(() => {
                            const filtered = activeStep.files.filter((f) => f.name.toLowerCase().includes(searchQuery.toLowerCase()));
                            const overlays = filtered.filter((f) => f.category === "overlay" || !f.category);
                            const distincts = filtered.filter((f) => f.category === "distinct");
                            
                            const renderFileItem = (file: FileItem) => {
                              const isSelected = selectedGalleryFile?.name === file.name;
                              return (
                                <div
                                  key={file.name}
                                  onClick={() => setSelectedGalleryFile(file)}
                                  className={`p-1.5 rounded-lg transition-all border cursor-pointer hover:shadow-sm flex gap-2 relative group overflow-hidden ${
                                    isSelected
                                      ? "bg-amber-500/10 border-amber-500/30 text-white shadow shadow-amber-500/5 ring-[0.5px] ring-amber-500/20"
                                      : "border-slate-800/60 bg-slate-950/20 hover:bg-slate-800/40 opacity-85 hover:opacity-100"
                                  }`}
                                >
                                  {/* Small Mini-Preview of Figure */}
                                  <div className="w-11 h-11 shrink-0 rounded bg-slate-950 flex items-center justify-center overflow-hidden border border-slate-200/5 relative">
                                    {file.type === "pdf" ? (
                                      <div className="w-full h-full bg-rose-950/20 flex flex-col items-center justify-center text-rose-500 p-1 relative">
                                        <svg className="w-5 h-5 text-rose-500/80 group-hover:scale-110 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                        </svg>
                                        <span className="text-[7px] font-bold uppercase tracking-wider text-rose-400 mt-0.5 font-mono">PDF</span>
                                      </div>
                                    ) : file.type === "svg" ? (
                                      <iframe
                                        src={`/files/${file.path}`}
                                        className="w-full h-full border-none pointer-events-none scale-50"
                                        title={file.name}
                                      />
                                    ) : (
                                      <img
                                        src={`/files/${file.path}`}
                                        className="w-full h-full object-cover"
                                        alt={file.name}
                                      />
                                    )}
                                    {/* Active state indicator dot */}
                                    {isSelected && (
                                      <span className="absolute top-0.5 right-0.5 flex h-1.5 w-1.5">
                                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                                      </span>
                                    )}
                                  </div>

                                  {/* Small Meta details */}
                                  <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                                    <div>
                                      <p className={`text-[10px] font-bold truncate ${isSelected ? "text-amber-500 font-semibold" : "text-slate-350"}`} title={file.name}>
                                        {file.name}
                                      </p>
                                    </div>
                                    <div className="flex items-center justify-between text-[7px] text-slate-500 font-bold uppercase w-fit bg-slate-950/30 px-1 rounded border border-slate-200/5 mt-0.5">
                                      <span className="text-indigo-400">{file.type}</span>
                                    </div>
                                  </div>
                                </div>
                              );
                            };

                            return (
                              <>
                                {/* Overlays & Summaries Block */}
                                {overlays.length > 0 && (
                                  <div className="space-y-1">
                                    <div className="flex items-center gap-1 px-1 py-0.5 mt-0.5 mb-1 border-b border-amber-500/10">
                                      <span className="text-[9px] font-bold text-amber-500 uppercase tracking-wider">
                                        ✦ Overlays & Summaries
                                      </span>
                                      <span className="text-[7px] font-mono text-slate-400 bg-slate-950/50 px-1 rounded border border-slate-850">
                                        {overlays.length}
                                      </span>
                                    </div>
                                    <div className="space-y-1.5">
                                      {overlays.map(renderFileItem)}
                                    </div>
                                  </div>
                                )}

                                {/* Individual Sweeps Block */}
                                {distincts.length > 0 && (
                                  <div className="space-y-1">
                                    <div className="flex items-center gap-1 px-1 py-0.5 mt-3 mb-1 border-b border-indigo-500/10">
                                      <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-wider">
                                        ⚏ Individual Sweeps
                                      </span>
                                      <span className="text-[7px] font-mono text-slate-400 bg-slate-950/50 px-1 rounded border border-slate-850">
                                        {distincts.length}
                                      </span>
                                    </div>
                                    <div className="space-y-1.5">
                                      {distincts.map(renderFileItem)}
                                    </div>
                                  </div>
                                )}

                                {filtered.length === 0 && (
                                  <div className="py-12 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl text-xs font-mono">
                                    No matches for "{searchQuery}"
                                  </div>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      </div>

                    </div>
                  ) : (
                    <div className="col-span-full py-16 text-center font-mono text-xs text-slate-400 border border-dashed border-slate-700 rounded-xl bg-slate-900/10">
                      No scientific charts exist inside this step directory.
                    </div>
                  )
                ) : (
                  <div className="text-center py-16 border rounded-xl border-dashed border-slate-700 text-slate-400 font-mono text-xs">
                    Please select or mount a step folder in the protocol list to explore dynamic plots files.
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: 6x6 CROSSBAR HEATMAP */}
            {activeTab === "crossbar" && activeProtocol && (
              <div className="space-y-6">
                
                {/* Metrics controls filters banner */}
                <div className={`p-4 rounded-xl border border-slate-200/10 grid grid-cols-1 md:grid-cols-3 gap-4 items-center justify-between ${theme === 'light' ? 'bg-slate-100' : 'bg-slate-900/30'}`}>
                  
                  {/* Metric Select */}
                  <div>
                    <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1.5 font-bold">
                      Heatmap Metric Selector
                    </label>
                    <select
                      value={metric}
                      onChange={(e) => setMetric(e.target.value)}
                      className={`w-full py-2 px-3 rounded-lg text-xs font-mono font-semibold border-slate-200/25 border outline-none bg-slate-950 text-slate-200 cursor-pointer focus:border-indigo-500`}
                    >
                      <option value="ratio">ON/OFF Resistance Ratio (R_on/R_off)</option>
                      <option value="vset">Threshold Set Voltage (V_set)</option>
                      <option value="vreset">Threshold Reset Voltage (V_reset)</option>
                      <option value="file_count">Associated Sweep Curve Count</option>
                      <option value="yield">Cell Operational Cycling Yield (%)</option>
                    </select>
                  </div>

                  {/* Material Filtering */}
                  <div>
                    <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1.5 font-bold">
                      Material Phase Segmenter
                    </label>
                    <select
                      value={materialFilter}
                      onChange={(e) => setMaterialFilter(e.target.value)}
                      className="w-full py-2 px-3 rounded-lg text-xs font-mono font-semibold border-slate-200/25 border outline-none bg-slate-950 text-slate-200 cursor-pointer focus:border-indigo-500"
                    >
                      <option value="">Full crossbar matrix (All materials)</option>
                      <option value="HfOx">Hafnium Oxide (HfOx) only</option>
                      <option value="AlOx">Aluminum Oxide (AlOx) only</option>
                    </select>
                  </div>

                  {/* Context stats summaries */}
                  <div className="text-right">
                    <span className="text-[10px] font-mono uppercase text-slate-400 block mb-1.5 font-bold text-left md:text-right">
                      Workspace Aggregates
                    </span>
                    <div className="flex items-center gap-4 justify-start md:justify-end text-xs font-mono">
                      <div>
                        Yield: <span className="text-emerald-400 font-bold">{projectData?.protocols.find(p => p.name === activeProtocol.name)?.switching_yield || "-"}%</span>
                      </div>
                      <div>
                        Tested Cells: <span className="text-indigo-400 font-bold">{projectData?.protocols.find(p => p.name === activeProtocol.name)?.measured_cells || "-"} / 36</span>
                      </div>
                    </div>
                  </div>

                </div>

                {/* Matrix crossbar & Plotly plot column */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                  
                  {/* Left: 6x6 crossbar card */}
                  <div className={`p-5 rounded-2xl border border-slate-200/10 flex flex-col items-center justify-center ${theme === 'light' ? 'bg-white' : 'bg-slate-900/40'}`}>
                    <div className="w-full flex justify-between items-center mb-4">
                      <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-bold">
                        6x6 Memristive Matrix Overlay
                      </h3>
                      <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-500">
                        <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500"></span>
                        <span>Active</span>
                      </div>
                    </div>

                    {/* Matrix Grid map */}
                    <div className="grid grid-cols-7 gap-2 max-w-[460px] w-full aspect-square text-center">
                      
                      {/* Grid Header column cells */}
                      <div className="flex items-center justify-center text-[10px] font-mono font-bold text-indigo-400">R\C</div>
                      {Array.from({ length: 6 }).map((_, i) => (
                        <div key={`col-hdr-${i}`} className="flex items-center justify-center text-[10px] font-mono text-slate-400">C{i+1}</div>
                      ))}

                      {/* Main R1-6 and C1-6 elements */}
                      {Array.from({ length: 6 }).map((_, rIdx) => {
                        return (
                          <React.Fragment key={`row-frag-${rIdx}`}>
                            <div className="flex items-center justify-center text-[10px] font-mono text-slate-400">R{rIdx+1}</div>
                            {Array.from({ length: 6 }).map((_, cIdx) => {
                              const cellMeta = heatmapData?.metadata?.[rIdx]?.[cIdx];
                              const cellValue = heatmapData?.data?.[rIdx]?.[cIdx];
                              const cellId = cellMeta?.cell || `R${rIdx+1}C${cIdx+1}`;
                              
                              const isUnmeasured = cellValue === null;
                              const cellBg = getHeatmapColor(metric, cellValue, maxVal);
                              const isSelected = selectedCell === cellId;

                              // Evaluate styling based on material segmenter
                              const isMuted = materialFilter && cellMeta?.material.toLowerCase() !== materialFilter.toLowerCase();
                              
                              return (
                                <button
                                  key={cellId}
                                  onClick={() => handleCellSelect(cellId)}
                                  style={{ backgroundColor: isMuted ? "rgba(100,116,139,0.03)" : cellBg }}
                                  className={`aspect-square rounded-lg flex flex-col justify-center items-center transition-all p-1 relative group select-none border border-slate-200/5 ${
                                    isSelected 
                                      ? "ring-4 ring-indigo-500 ring-offset-2 ring-offset-slate-900 border-indigo-500/80 z-10 scale-105 shadow-lg" 
                                      : "hover:scale-[1.04] hover:shadow-md"
                                  } ${isMuted ? 'opacity-25' : ''}`}
                                >
                                  {/* Cell label */}
                                  <span className={`text-[8px] font-mono block ${theme === 'light' ? 'text-slate-800' : 'text-white'} font-bold`}>
                                    {cellId}
                                  </span>
                                  {/* Metric value rendered inside cells */}
                                  <span className="text-[10px] font-mono font-bold tracking-tighter truncate w-full text-center">
                                    {isUnmeasured ? (
                                      <span className="text-slate-500 font-light">-</span>
                                    ) : metric === "ratio" ? (
                                      `10^${Math.round(Math.log10(cellValue))}`
                                    ) : metric === "vset" || metric === "vreset" ? (
                                      `${cellValue}V`
                                    ) : (
                                      cellValue
                                    )}
                                  </span>

                                  {/* Tooltip dynamic Hover elements */}
                                  <div className="absolute bottom-[110%] left-1/2 -translate-x-1/2 bg-slate-950/95 text-white p-2.5 rounded-lg text-[9px] font-mono pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50 shadow-xl border border-slate-800 w-[150px] text-left">
                                    <div className="text-amber-500 font-bold border-b border-slate-800 pb-1 mb-1 flex justify-between">
                                      <span>Device {cellId}</span>
                                      <span>{cellMeta?.material}</span>
                                    </div>
                                    <div className="space-y-0.5">
                                      <div>Vset: {cellMeta?.v_set || "-"}V</div>
                                      <div>Vreset: {cellMeta?.v_reset || "-"}V</div>
                                      <div>Ratio: {cellMeta?.ratio || "-"}</div>
                                      <div>Yield: {cellMeta?.yield || "-"}%</div>
                                      <div>Sweeps: {cellMeta?.file_count || "-"}</div>
                                    </div>
                                  </div>
                                </button>
                              );
                            })}
                          </React.Fragment>
                        );
                      })}

                    </div>

                    {/* Gradient legend scale */}
                    <div className="w-full max-w-[340px] flex items-center justify-between mt-5 font-mono text-[9px] text-slate-400 gap-3 border-t border-slate-200/10 pt-4">
                      <span>Low Density</span>
                      <div 
                        className="flex-1 h-3 rounded border border-slate-200/10"
                        style={{
                          background: `linear-gradient(to right, ${getHeatmapColor(metric, maxVal * 0.1, maxVal)}, ${getHeatmapColor(metric, maxVal * 0.5, maxVal)}, ${getHeatmapColor(metric, maxVal, maxVal)})`
                        }}
                      />
                      <span>High Density</span>
                    </div>

                  </div>

                  {/* Right: I-V dynamic curves plotter */}
                  <div className={`p-5 rounded-2xl border border-slate-200/10 flex flex-col justify-between min-h-[420px] ${theme === 'light' ? 'bg-white' : 'bg-slate-900/40'}`}>
                    
                    {cellIVData ? (
                      <div className="flex-1 flex flex-col justify-between space-y-4">
                        
                        {/* Interactive cell technical specifications header */}
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold font-mono">{cellIVData.cell_id} Curve Sweep Diagram</span>
                              <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                                cellIVData.switching ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                              }`}>
                                {cellIVData.switching ? "Active memristor switching" : "Defective / Open-circuit"}
                              </span>
                            </div>
                            <div className="text-[10px] font-mono text-slate-400 mt-1">
                              Material Structure: <span className="text-indigo-400 font-bold">{cellIVData.material} Layer stack</span> &middot; ON/OFF: {cellIVData.ratio}
                            </div>
                          </div>

                          <div className="flex gap-2">
                            <button
                              onClick={copyIVDataToClipboard}
                              className="p-1 px-3 rounded-lg border border-slate-200/10 bg-slate-950/50 hover:bg-slate-950 text-[10px] font-mono text-slate-300 flex items-center gap-1 transition-all"
                            >
                              {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                              <span>{isCopied ? "Copied!" : "Copy Curves"}</span>
                            </button>
                          </div>
                        </div>

                        {/* HIGH FIDELITY REACT VECTOR CURVE ENGINE FOR MEMRISTIVE HYSTERESIS */}
                        <div className="relative w-full aspect-[4/3] bg-slate-950 rounded-xl p-4 border border-slate-800 flex items-center justify-center group overflow-hidden">
                          
                          {/* Grid SVG canvas chart */}
                          <svg className="w-full h-full select-none" viewBox="0 0 400 280">
                            
                            {/* Cartesian center guides & grids */}
                            <line x1="50" y1="140" x2="380" y2="140" stroke="#1e293b" strokeWidth="1" strokeDasharray="3" />
                            <line x1="215" y1="20" x2="215" y2="240" stroke="#1e293b" strokeWidth="1" strokeDasharray="3" />
                            
                            {/* Surrounding grid lines */}
                            <line x1="105" y1="20" x2="105" y2="240" stroke="#1e293b" strokeWidth="0.5" strokeDasharray="2" />
                            <line x1="325" y1="20" x2="325" y2="240" stroke="#1e293b" strokeWidth="0.5" strokeDasharray="2" />
                            
                            <line x1="50" y1="60" x2="380" y2="60" stroke="#1e293b" strokeWidth="0.5" strokeDasharray="2" />
                            <line x1="50" y1="200" x2="380" y2="200" stroke="#1e293b" strokeWidth="0.5" strokeDasharray="2" />

                            {/* Chart Outer borders */}
                            <rect x="50" y="20" width="330" height="220" fill="none" stroke="#334155" strokeWidth="1" />

                            {/* Axis Labels */}
                            {/* y-axis labels from 10^-8 to 10^-2 */}
                            <text x="42" y="33" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">10^-2</text>
                            <text x="42" y="88" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">10^-4</text>
                            <text x="42" y="143" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">10^-6</text>
                            <text x="42" y="198" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">10^-8</text>
                            <text x="42" y="243" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">0 A</text>

                            {/* x-axis labels */}
                            <text x="50" y="255" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">-2.0 V</text>
                            <text x="132.5" y="255" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">-1.0 V</text>
                            <text x="215" y="255" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">0 V</text>
                            <text x="297.5" y="255" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">1.0 V</text>
                            <text x="380" y="255" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">2.0 V</text>

                            {/* Render actual hysteretic curve sweeps */}
                            {cellIVData.sweeps.map((swp: any, swpIdx: number) => {
                              
                              // Transform physics points into canvas dimensions
                              // x range from -2.0V to 2.0V -> maps to x=[50, 380]
                              // y range (log absolute current) from 10^-9 to 10^-2 -> maps to y=[240, 20]
                              const pointsStr = swp.voltage.map((v: number, i: number) => {
                                const xv = 215 + (v / 2.0) * 165;
                                const absC = Math.max(Math.abs(swp.current[i]), 1e-9);
                                const logC = Math.log10(absC); // -9 to -2
                                const yv = 240 - ((logC - (-9)) / ( -2 - (-9) )) * 220;
                                return `${xv},${yv}`;
                              }).join(" ");

                              return (
                                <g key={swpIdx}>
                                  <polyline
                                    points={pointsStr}
                                    fill="none"
                                    stroke={swpIdx === 0 ? "#818cf8" : swpIdx === 1 ? "#ec4899" : "#10b981"}
                                    strokeWidth="2.5"
                                    className="transition-all hover:strokeWidth-[3.5]"
                                  />
                                </g>
                              );
                            })}

                            {/* Render explicit Set and Reset switching pins/markers */}
                            {cellIVData.switching && cellIVData.sweeps.map((swp: any, swpIdx: number) => {
                              // Find index corresponding to thresh vset or vreset
                              if (swp.v_set) {
                                const idx = swp.voltage.indexOf(swp.v_set) >= 0 ? swp.voltage.indexOf(swp.v_set) : Math.floor(swp.voltage.length / 2);
                                const xVal = 215 + (swp.v_set / 2.0) * 165;
                                const absC = Math.max(Math.abs(swp.current[idx]), 1e-9);
                                const yVal = 240 - ((Math.log10(absC) - (-9)) / 7) * 220;
                                return (
                                  <g key={`vset-marker`}>
                                    <circle cx={xVal} cy={yVal} r="5" fill="#ef4444" className="animate-pulse" />
                                    <line x1={xVal} y1={yVal} x2={xVal} y2="140" stroke="#ef4444" strokeWidth="0.75" strokeDasharray="2" />
                                    <text x={xVal} y={yVal - 10} fill="#f87171" fontSize="8" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
                                      V_set ({swp.v_set}V)
                                    </text>
                                  </g>
                                );
                              }

                              if (swp.v_reset) {
                                const idx = swp.voltage.indexOf(swp.v_reset) >= 0 ? swp.voltage.indexOf(swp.v_reset) : Math.floor(swp.voltage.length / 2);
                                const xVal = 215 + (swp.v_reset / 2.0) * 165;
                                const absC = Math.max(Math.abs(swp.current[idx]), 1e-9);
                                const yVal = 240 - ((Math.log10(absC) - (-9)) / 7) * 220;
                                return (
                                  <g key={`vreset-marker`}>
                                    <circle cx={xVal} cy={yVal} r="5" fill="#f59e0b" className="animate-pulse" />
                                    <line x1={xVal} y1={yVal} x2={xVal} y2="140" stroke="#f59e0b" strokeWidth="0.75" strokeDasharray="2" />
                                    <text x={xVal} y={yVal - 10} fill="#fbbf24" fontSize="8" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
                                      V_reset ({swp.v_reset}V)
                                    </text>
                                  </g>
                                );
                              }
                              return null;
                            })}

                          </svg>

                          {/* Dynamic legend labels */}
                          <div className="absolute top-4 left-4 flex flex-col gap-1 font-mono text-[9px] bg-slate-950/80 p-2 rounded-lg border border-slate-800">
                            {cellIVData.sweeps.map((swp: any, i: number) => (
                              <div key={i} className="flex items-center gap-2">
                                <span className="w-3 h-0.5" style={{ backgroundColor: i === 0 ? "#818cf8" : i === 1 ? "#ec4899" : "#10b981" }}></span>
                                <span className="text-slate-400">{swp.label}</span>
                              </div>
                            ))}
                          </div>

                        </div>

                        {/* Interactive dynamic coordinates listing */}
                        <div className="mt-2 text-[10px] font-mono text-slate-400 text-center flex items-center justify-between">
                          <span>Graph scale: Logarithmic Current Amplitude |Current| (A)</span>
                          <span className="text-[9px] text-slate-500 font-normal">Double-sweep cyclic loop hysteresis</span>
                        </div>

                      </div>
                    ) : (
                      <div className="flex-1 flex flex-col justify-center items-center text-slate-500 font-mono text-xs py-20 text-center space-y-3 p-4">
                        <Activity className="w-12 h-12 text-slate-700 animate-pulse" />
                        <div>
                          Click on any active cell inside the 6x6 crossbar matrix map on the left to render its dynamic logarithmic sweep curve.
                        </div>
                      </div>
                    )}

                  </div>

                </div>

                {/* HISTOGRAMS PLOT SECTION */}
                {histograms && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-4">
                    
                    {/* Vset Histogram Distribution */}
                    <div className={`p-4 rounded-xl border border-slate-200/10 ${theme === 'light' ? 'bg-white' : 'bg-slate-900/35'}`}>
                      <div className="flex items-center justify-between mb-3 border-b border-slate-200/5 pb-2">
                        <h4 className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                          Threshold Vset Distribution
                        </h4>
                        <span className="text-[9px] font-mono text-indigo-400">HfOx + AlOx</span>
                      </div>
                      
                      {histograms.vset && histograms.vset.bins.length > 0 ? (
                        <div className="h-28 flex items-end justify-between gap-1 w-full relative">
                          {histograms.vset.counts.map((cnt: number, i: number) => {
                            const maxCount = Math.max(...histograms.vset.counts, 1);
                            const heightPct = (cnt / maxCount) * 100;
                            return (
                              <div key={i} className="flex-1 flex flex-col justify-end items-center h-full group relative">
                                <div 
                                  style={{ height: `${heightPct}%` }}
                                  className="w-full bg-indigo-500/25 border border-indigo-500/60 rounded-t hover:bg-indigo-500/50 transition-all cursor-pointer relative"
                                >
                                  {/* Value popover */}
                                  <span className="absolute bottom-[110%] left-1/2 -translate-x-1/2 bg-slate-950 px-1.5 py-0.5 rounded text-[8px] font-mono text-white opacity-0 group-hover:opacity-100 transition-opacity z-10">
                                    {cnt} cells
                                  </span>
                                </div>
                                <span className="text-[8px] font-mono text-slate-500 block mt-2 text-center w-full truncate" title={histograms.vset.bins[i]}>
                                  {histograms.vset.bins[i].replace("-", "-\n")}V
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="text-center py-8 font-mono text-[10px] text-slate-500">No histogram coordinates available.</div>
                      )}
                    </div>

                    {/* Vreset Histogram Distribution */}
                    <div className={`p-4 rounded-xl border border-slate-200/10 ${theme === 'light' ? 'bg-white' : 'bg-slate-900/35'}`}>
                      <div className="flex items-center justify-between mb-3 border-b border-slate-200/5 pb-2">
                        <h4 className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                          Threshold Vreset Distribution
                        </h4>
                        <span className="text-[9px] font-mono text-amber-500">Reverse polarity</span>
                      </div>
                      
                      {histograms.vreset && histograms.vreset.bins.length > 0 ? (
                        <div className="h-28 flex items-end justify-between gap-1 w-full relative">
                          {histograms.vreset.counts.map((cnt: number, i: number) => {
                            const maxCount = Math.max(...histograms.vreset.counts, 1);
                            const heightPct = (cnt / maxCount) * 100;
                            return (
                              <div key={i} className="flex-1 flex flex-col justify-end items-center h-full group relative">
                                <div 
                                  style={{ height: `${heightPct}%` }}
                                  className="w-full bg-amber-500/25 border border-amber-500/60 rounded-t hover:bg-amber-500/50 transition-all cursor-pointer relative"
                                >
                                  <span className="absolute bottom-[110%] left-1/2 -translate-x-1/2 bg-slate-950 px-1.5 py-0.5 rounded text-[8px] font-mono text-white opacity-0 group-hover:opacity-100 transition-opacity z-10">
                                    {cnt} cells
                                  </span>
                                </div>
                                <span className="text-[8px] font-mono text-slate-500 block mt-2 text-center w-full truncate" title={histograms.vreset.bins[i]}>
                                  {histograms.vreset.bins[i]}V
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="text-center py-8 font-mono text-[10px] text-slate-500">No threshold structures.</div>
                      )}
                    </div>

                    {/* Ratio Histogram Distribution */}
                    <div className={`p-4 rounded-xl border border-slate-200/10 ${theme === 'light' ? 'bg-white' : 'bg-slate-900/35'}`}>
                      <div className="flex items-center justify-between mb-3 border-b border-slate-200/5 pb-2">
                        <h4 className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                          ON/OFF Hysteresis Log Ratio
                        </h4>
                        <span className="text-[9px] font-mono text-emerald-400">Decibel magnitude</span>
                      </div>
                      
                      {histograms.ratio && histograms.ratio.bins.length > 0 ? (
                        <div className="h-28 flex items-end justify-between gap-1 w-full relative">
                          {histograms.ratio.counts.map((cnt: number, i: number) => {
                            const maxCount = Math.max(...histograms.ratio.counts, 1);
                            const heightPct = (cnt / maxCount) * 100;
                            return (
                              <div key={i} className="flex-1 flex flex-col justify-end items-center h-full group relative">
                                <div 
                                  style={{ height: `${heightPct}%` }}
                                  className="w-full bg-emerald-500/25 border border-emerald-500/60 rounded-t hover:bg-emerald-500/50 transition-all cursor-pointer relative"
                                >
                                  <span className="absolute bottom-[110%] left-1/2 -translate-x-1/2 bg-slate-950 px-1.5 py-0.5 rounded text-[8px] font-mono text-white opacity-0 group-hover:opacity-100 transition-opacity z-10">
                                    {cnt} cells
                                  </span>
                                </div>
                                <span className="text-[8px] font-mono text-slate-500 block mt-2 text-center w-full truncate" title={histograms.ratio.bins[i]}>
                                  10^{Math.round(parseFloat(histograms.ratio.bins[i]))}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="text-center py-8 font-mono text-[10px] text-slate-500">No distribution sweeps.</div>
                      )}
                    </div>

                  </div>
                )}

              </div>
            )}

          </div>
        )}

      </main>

      {/* PORTATIVE LIGHTBOX FOR PREVIEWS WITH ZOOMS & PANS */}
      {lightboxFile && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-8 bg-black/95 backdrop-blur-md animate-fade-in"
          onClick={() => {
            setLightboxFile(null);
            setZoomScale(1.0);
            setPanOffset({ x: 0, y: 0 });
          }}
        >
          <div 
            className="w-full max-w-5xl rounded-2xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row overflow-hidden shadow-2xl h-[85vh] max-h-[800px] relative animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            
            {/* Left canvas: Image & Zoom actions wrapper */}
            <div className="flex-1 bg-black flex flex-col justify-between relative h-1/2 md:h-full group">
              
              {/* Header inside canvas */}
              <div className="p-4 flex items-center justify-between border-b border-slate-850 absolute top-0 left-0 right-0 z-10 bg-gradient-to-b from-slate-900/90 to-transparent">
                <div>
                  <div className="text-[10px] font-mono text-amber-500 uppercase tracking-widest font-black">
                    Interactive Lightbox viewer
                  </div>
                  <h2 className="text-sm font-mono text-white font-bold truncate max-w-xs sm:max-w-md">
                    {lightboxFile.name}
                  </h2>
                </div>
                
                {/* Actions button */}
                <div className="flex gap-2">
                  <button
                    onClick={() => downloadPlotFile(lightboxFile)}
                    className="p-1.5 px-3 rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 text-[10px] font-mono font-bold flex items-center gap-1.5 transition-all shadow-md cursor-pointer"
                  >
                    <Download className="w-3 h-3" />
                    <span>Download Vector</span>
                  </button>
                </div>
              </div>

              {/* Main SVG/Embed display supporting Pan & Zoom */}
              <div 
                className="flex-1 flex items-center justify-center overflow-hidden cursor-move relative pt-20"
                onMouseDown={handlePanStart}
                onMouseMove={handlePanMove}
                onMouseUp={handlePanEnd}
                onMouseLeave={handlePanEnd}
              >
                <div 
                  className="transition-transform duration-100 origin-center flex items-center justify-center w-4/5 h-4/5 select-none"
                  style={{
                    transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomScale})`
                  }}
                >
                  {lightboxFile.type === "svg" || lightboxFile.type === "pdf" ? (
                    <iframe
                      src={`/files/${lightboxFile.path}${lightboxFile.type === "pdf" ? "#toolbar=0" : ""}`}
                      className="w-full h-full border-none pointer-events-none"
                      title={lightboxFile.name}
                    />
                  ) : (
                    <img
                      src={`/files/${lightboxFile.path}`}
                      className="w-full h-full object-contain pointer-events-none"
                      alt={lightboxFile.name}
                    />
                  )}
                </div>
              </div>

              {/* Float Zoom Action keys overlays */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-slate-900/90 border border-slate-850 p-2.5 rounded-full flex items-center gap-3.5 shadow-lg shadow-black/80 z-20 backdrop-blur">
                <button 
                  onClick={() => setZoomScale(prev => Math.max(0.5, prev - 0.25))}
                  className="p-1 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <span className="text-[10px] font-mono text-slate-200 font-bold min-w-[32px] text-center select-none">
                  {Math.round(zoomScale * 100)}%
                </span>
                <button 
                  onClick={() => setZoomScale(prev => Math.min(4.0, prev + 0.25))}
                  className="p-1 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Zoom In"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <div className="w-px h-3.5 bg-slate-805"></div>
                <button 
                  onClick={() => {
                    setZoomScale(1.0);
                    setPanOffset({ x: 0, y: 0 });
                  }}
                  className="p-1 text-slate-300 hover:text-white transition-all cursor-pointer"
                  title="Reset viewport placement"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>

            </div>

            {/* Right side panel: Technical metadata information */}
            <div className="w-full md:w-[280px] shrink-0 border-l border-slate-800 p-5 flex flex-col justify-between bg-slate-950 text-xs font-mono h-1/2 md:h-full">
              
              <div className="space-y-5">
                <div className="flex justify-between items-start border-b border-slate-850 pb-3">
                  <div>
                    <h3 className="text-gray-200 font-bold text-xs uppercase tracking-wide">Technical Metadata</h3>
                    <p className="text-[9px] text-slate-500 mt-1">Acquisition telemetry scans</p>
                  </div>
                  <button 
                    onClick={() => {
                      setLightboxFile(null);
                      setZoomScale(1.0);
                      setPanOffset({ x: 0, y: 0 });
                    }}
                    className="p-1 hover:bg-slate-850 rounded text-slate-400 hover:text-white transition-all cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-3">
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">File Name</span>
                    <span className="text-amber-500 font-bold block select-all break-all">{lightboxFile.name}</span>
                  </div>
                  
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">File Path</span>
                    <span className="text-slate-300 block select-all text-[11px] break-all">{lightboxFile.path}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase">File Size</span>
                      <span className="text-slate-200 block font-bold">{lightboxFile.size || "142 KB"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase">Dimensions</span>
                      <span className="text-slate-200 block font-bold">{lightboxFile.dimensions || "1280x800"}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase">Type</span>
                      <span className="text-indigo-400 block font-bold uppercase">{lightboxFile.type}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[9px] uppercase">Acquisition</span>
                      <span className="text-slate-200 block font-bold">2026-05-29</span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Informative notice block */}
              <div className="p-3 bg-indigo-950/20 rounded-xl border border-indigo-900/30 text-[10px] text-indigo-400 text-left flex gap-2 pt-3">
                <Info className="w-4 h-4 shrink-0 text-indigo-400 mt-0.5" />
                <div>
                  Double-click or drag of cursor the viewport is enabled for tactile 2D panning and absolute scaling.
                </div>
              </div>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}
