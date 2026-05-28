/**
 * science-cli Shared Dashboard Utilities & Core JS Engine
 * Centralized API helpers, Theme Management, Visual Skeletons, and Interactive SVGs
 */

window.SciApp = {
  // Config Properties
  activeTheme: "light",
  currentProject: null,
  
  // Initialize Global Scripts
  init() {
    this.setupTheme();
    this.setupSidebarToggle();
    this.loadGlobalContext();
    this.bindGlobalEvents();
  },

  // 1. API Fetch Helper with Auto-Error Handling & Loader support
  async apiFetch(url, options = {}) {
    this.showGlobalLoader(true);
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
      const data = await response.json();
      return data;
    } catch (error) {
      console.error(`Api Fetch Failure details for [${url}]:`, error);
      this.showErrorBanner(`Failure communicating with CLI server: ${error.message}. Please verify science-cli is running.`);
      throw error;
    } finally {
      this.showGlobalLoader(false);
    }
  },

  // 2. Theme management systems (Dark, Light, OLED Black)
  setupTheme() {
    const savedTheme = localStorage.getItem("sci-theme") || "light";
    this.setTheme(savedTheme);
    
    // Sync UI selector elements
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const theme = e.target.getAttribute("data-theme");
        if (theme) {
          this.setTheme(theme);
          // Dispatch global custom event for charts to update colors
          window.dispatchEvent(new CustomEvent("scithemechange", { detail: theme }));
        }
      });
    });
  },

  setTheme(theme) {
    this.activeTheme = theme;
    localStorage.setItem("sci-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    
    // Update active button indicators across all matching elements
    document.querySelectorAll(".theme-btn").forEach(btn => {
      if (btn.getAttribute("data-theme") === theme) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // Update body background or related transitions
    document.body.style.transition = "background-color 0.3s ease, color 0.3s ease";
  },

  // Get active layout parameters for Plotly depending on theme
  getPlotlyThemeLayout() {
    const isDark = this.activeTheme === "dark" || this.activeTheme === "black";
    const bgCol = this.activeTheme === "black" ? "#000000" : (this.activeTheme === "dark" ? "#131b2e" : "#f8fafc");
    const gridCol = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
    const textCol = isDark ? "#e8f0fe" : "#0f172a";

    return {
      paper_bgcolor: "transparent",
      plot_bgcolor: bgCol,
      font: {
        family: "'DM Sans', sans-serif",
        color: textCol,
        size: 11
      },
      xaxis: {
        gridcolor: gridCol,
        linecolor: gridCol,
        tickcolor: gridCol,
        zerolinecolor: gridCol,
        font: { family: "'JetBrains Mono', monospace" }
      },
      yaxis: {
        gridcolor: gridCol,
        linecolor: gridCol,
        tickcolor: gridCol,
        zerolinecolor: gridCol,
        font: { family: "'JetBrains Mono', monospace" }
      }
    };
  },

  // 3. Responsive Menu Sidebar Collapsing Triggers
  setupSidebarToggle() {
    const toggleBtn = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar");
    
    if (toggleBtn && sidebar) {
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sidebar.classList.toggle("active");
      });
      
      // Close sidebar if user clicks outside of it on mobile
      document.addEventListener("click", (e) => {
        if (sidebar.classList.contains("active") && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove("active");
        }
      });
    }
  },

  // 4. Load Current Context to keep sidebar matching actual files
  async loadGlobalContext() {
    try {
      const data = await this.apiFetch("/api/project");
      this.currentProject = data;
      
      // Update sidebar visual details
      const projectSpan = document.getElementById("ctx-project");
      const protocolSpan = document.getElementById("ctx-protocol");
      const stepSpan = document.getElementById("ctx-step");
      
      if (projectSpan) projectSpan.textContent = data.project_name;
      if (protocolSpan) protocolSpan.textContent = data.last_protocol;
      if (stepSpan) stepSpan.textContent = data.last_step;

      // Update sidebar visual breadcrumbs if present
      const breadProject = document.getElementById("crumbs-project");
      if (breadProject) breadProject.textContent = data.project_name;
    } catch (e) {
      console.warn("Could not load current project context details:", e);
    }
  },

  bindGlobalEvents() {
    // Add simple banner framework to body for errors
    const errorBanner = document.createElement("div");
    errorBanner.id = "sci-error-banner";
    errorBanner.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background-color: #ff5252;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      font-size: 13px;
      z-index: 10000;
      display: none;
      align-items: center;
      gap: 12px;
      transition: all 0.3s ease;
      font-weight: 500;
    `;
    errorBanner.innerHTML = `
      <span class="banner-msg"></span>
      <button style="border:none;background:none;color:white;cursor:pointer;font-weight:700;font-size:14px;" onclick="document.getElementById('sci-error-banner').style.display='none'">✕</button>
    `;
    document.body.appendChild(errorBanner);
  },

  showErrorBanner(msg) {
    const banner = document.getElementById("sci-error-banner");
    if (banner) {
      banner.querySelector(".banner-msg").textContent = msg;
      banner.style.display = "flex";
      // Auto dismiss after 7 seconds
      setTimeout(() => {
        banner.style.display = "none";
      }, 7000);
    }
  },

  // 5. Global Load State handler
  showGlobalLoader(show) {
    // We can show top progress bar or search overlay loader
    let bar = document.getElementById("sci-top-loading-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "sci-top-loading-bar";
      bar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue));
        z-index: 10001;
        transition: width 0.2s ease;
        width: 0%;
      `;
      document.body.appendChild(bar);
    }
    
    if (show) {
      bar.style.width = "40%";
      setTimeout(() => {
        if (bar.style.width === "40%") bar.style.width = "80%";
      }, 300);
    } else {
      bar.style.width = "100%";
      setTimeout(() => {
        bar.style.width = "0%";
      }, 200);
    }
  },

  // 6. Vector Procedural SVG Generators - massive performance and offline design optimization!
  // This allows the cards/lightbox to render beautiful actual graphics even if mock .png/pdf does not exist!
  drawHysteresisLoopSVG(width = 300, height = 200, v_set = 2.0, v_reset = -1.5, activeTheme = "dark") {
    const isDark = activeTheme === "dark" || activeTheme === "black";
    const bg = "transparent";
    const axisCol = isDark ? "#2a4a73" : "#cbd5e1";
    const curveCol = isDark ? "#00ffff" : "#2563eb";
    const fontCol = isDark ? "#8ba3c7" : "#475569";
    const lrsCol = isDark ? "#00e676" : "#16a34a"; // green
    const hrsCol = isDark ? "#ff9100" : "#ea580c"; // orange

    // Center coordinates
    const cx = width / 2;
    const cy = height / 2;
    
    // Scale vectors
    const sx = (width - 40) / 6;  // Range -3V to 3V
    const sy = (height - 40) / 2; // logarithmic currents

    // Generate path points
    const pts = [];
    const steps = 40;
    
    // 1. Forward Positive: 0 to 3V. Switches at v_set.
    let state = "HRS";
    for(let i=0; i<=steps; i++) {
      const v = (3.0 * i) / steps;
      if (v >= v_set) state = "LRS";
      const logI = state === "LRS" ? (Math.log10(v/1000 + 1e-6) + 6)/6 : (Math.log10(v/300000 + 1e-8) + 8)/8;
      pts.push([cx + v * sx, cy - logI * sy]);
    }
    
    // 2. Return Positive: 3V to 0V. Stays in LRS.
    for(let i=steps; i>=0; i--) {
      const v = (3.0 * i) / steps;
      const logI = (Math.log10(v/1000 + 1e-6) + 6)/6;
      pts.push([cx + v * sx, cy - logI * sy]);
    }
    
    // 3. Forward Negative: 0 to -3V. Stays LRS until v_reset.
    state = "LRS";
    for(let i=0; i<=steps; i++) {
      const v = -(3.0 * i) / steps;
      if (v <= v_reset) state = "HRS";
      const logI = state === "LRS" ? (Math.log10(Math.abs(v)/1000 + 1e-6) + 6)/6 : (Math.log10(Math.abs(v)/300000 + 1e-8) + 8)/8;
      pts.push([cx + v * sx, cy + logI * sy]);
    }
    
    // 4. Return Negative: -3V to 0V. Stays in HRS.
    for(let i=steps; i>=0; i--) {
      const v = -(3.0 * i) / steps;
      const logI = (Math.log10(Math.abs(v)/300000 + 1e-8) + 8)/8;
      pts.push([cx + v * sx, cy + logI * sy]);
    }

    const dStr = pts.map((p, idx) => `${idx === 0 ? 'M':'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');

    return `
      <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="background:${bg}; border-radius:8px; font-family:var(--font-mono)">
        <!-- Grid and Axes -->
        <line x1="20" y1="${cy}" x2="${width - 20}" y2="${cy}" stroke="${axisCol}" stroke-width="1" stroke-dasharray="2,4" />
        <line x1="${cx}" y1="20" x2="${cx}" y2="${height - 20}" stroke="${axisCol}" stroke-width="1" stroke-dasharray="2,4" />
        
        <!-- Axes Labels -->
        <text x="${width - 15}" y="${cy + 12}" fill="${fontCol}" font-size="9" text-anchor="end">V</text>
        <text x="${cx + 6}" y="25" fill="${fontCol}" font-size="9">log |I|</text>
        
        <!-- Switching event dashlines -->
        <line x1="${cx + v_set * sx}" y1="20" x2="${cx + v_set * sx}" y2="${height - 20}" stroke="red" stroke-width="0.8" stroke-dasharray="3,3" />
        <line x1="${cx + v_reset * sx}" y1="20" x2="${cx + v_reset * sx}" y2="${height - 20}" stroke="orange" stroke-width="0.8" stroke-dasharray="3,3" />
        <text x="${cx + v_set * sx + 4}" y="35" fill="red" font-size="8">Vset (${v_set}V)</text>
        <text x="${cx + v_reset * sx - 4}" y="${height - 30}" fill="orange" font-size="8" text-anchor="end">Vreset (${v_reset}V)</text>
        
        <!-- Hysteresis Curve Path -->
        <path d="${dStr}" fill="none" stroke="${curveCol}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        
        <!-- Conduction state markers -->
        <text x="${cx + 0.8 * sx}" y="${cy - 0.7 * sy}" fill="${lrsCol}" font-size="8" font-weight="bold">LRS</text>
        <text x="${cx - 1.2 * sx}" y="${cy - 0.1 * sy}" fill="${hrsCol}" font-size="8" font-weight="bold">HRS</text>
      </svg>
    `;
  },

  drawVoltammetryLoopSVG(width = 300, height = 200, activeTheme = "dark") {
    const isDark = activeTheme === "dark" || activeTheme === "black";
    const bg = "transparent";
    const axisCol = isDark ? "#2a4a73" : "#cbd5e1";
    const fontCol = isDark ? "#8ba3c7" : "#475569";
    const curveCol = isDark ? "#b197fc" : "#7c3aed"; // CV purple
    
    const cx = width / 2;
    const cy = height / 2;
    
    // Draw electrochemical duck-shaped cyclic scan
    const pts = [];
    const steps = 60;
    
    // Cyclic voltammetry parametric oval-duck formula
    for (let i = 0; i < steps; i++) {
      const theta = (2 * Math.PI * i) / steps;
      const x_pot = Math.cos(theta);
      // CV current usually shows peak reaction peaks: duck shape
      const y_cur = Math.sin(theta) + 0.45 * Math.cos(theta) + (theta > Math.PI ? -0.2 * Math.exp(-Math.pow(theta - 5, 2)) : 0.6 * Math.exp(-Math.pow(theta - 1.5, 2)));
      
      pts.push([cx + x_pot * (width - 60) / 2, cy - y_cur * (height - 60) / 2]);
    }
    
    const dStr = pts.map((p, idx) => `${idx === 0 ? 'M':'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') + " Z";
    
    return `
      <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="background:${bg}; border-radius:8px; font-family:var(--font-mono)">
        <line x1="20" y1="${cy}" x2="${width - 20}" y2="${cy}" stroke="${axisCol}" stroke-width="1" />
        <line x1="${cx}" y1="20" x2="${cx}" y2="${height - 20}" stroke="${axisCol}" stroke-width="1" />
        <text x="${width - 15}" y="${cy + 12}" fill="${fontCol}" font-size="9" text-anchor="end">Potential E (V)</text>
        <text x="${cx + 6}" y="25" fill="${fontCol}" font-size="9">Current I (mA)</text>
        <path d="${dStr}" fill="none" stroke="${curveCol}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <circle cx="${cx + 0.5 * (width-60)/2}" cy="${cy - 0.9 * (height-60)/2}" r="3" fill="#ff5252" />
        <text x="${cx + 0.5 * (width-60)/2 + 6}" y="${cy - 0.9 * (height-60)/1.8}" fill="#ff5252" font-size="8">Anodic Oxidation</text>
      </svg>
    `;
  },

  drawHistogramLoopSVG(width = 300, height = 200, values = [3, 8, 15, 22, 11, 4], labels = [], activeTheme = "dark") {
    const isDark = activeTheme === "dark" || activeTheme === "black";
    const bg = "transparent";
    const barCol = isDark ? "rgba(0, 212, 255, 0.4)" : "rgba(37, 99, 235, 0.4)";
    const barBorderCol = isDark ? "#00ffff" : "#2563eb";
    const axisCol = isDark ? "#2a4a73" : "#cbd5e1";
    const fontCol = isDark ? "#8ba3c7" : "#475569";
    
    const maxVal = Math.max(...values, 1);
    const count = values.length;
    const paddingLeft = 30;
    const paddingRight = 10;
    const paddingTop = 20;
    const paddingBottom = 20;
    
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    const barWidth = chartWidth / count - 4;
    
    let barsSvg = "";
    values.forEach((v, index) => {
      const h = (v / maxVal) * chartHeight;
      const x = paddingLeft + index * (chartWidth / count) + 2;
      const y = height - paddingBottom - h;
      
      barsSvg += `
        <rect x="${x}" y="${y}" width="${barWidth}" height="${h}" fill="${barCol}" stroke="${barBorderCol}" stroke-width="1.5" rx="3" />
        <text x="${x + barWidth/2}" y="${y - 4}" fill="${fontCol}" font-size="8" text-anchor="middle">${v}</text>
        <text x="${x + barWidth/2}" y="${height - 8}" fill="${fontCol}" font-size="8" text-anchor="middle">${labels[index] || index}</text>
      `;
    });
    
    return `
      <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="background:${bg}; pointer-events:none;">
        <line x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}" stroke="${axisCol}" stroke-width="1" />
        <line x1="${paddingLeft}" y1="${paddingTop}" x2="${paddingLeft}" y2="${height - paddingBottom}" stroke="${axisCol}" stroke-width="1" />
        ${barsSvg}
      </svg>
    `;
  },
  
  // Format dates elegantly for science files
  formatDate(dateString) {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      day: "numeric",
      month: "short",
      year: "numeric"
    }) + " " + date.toLocaleTimeString("en-US", { hour: "2-digit", minute:"2-digit", hour12: false });
  }
};

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  window.SciApp.init();
});
