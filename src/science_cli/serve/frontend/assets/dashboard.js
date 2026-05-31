/**
 * science-cli Plot Gallery (dashboard.js)
 * Standalone client-side event binders, API retrievers, 
 * and dynamic Plotly.js Cartesian coordinate configurations.
 */

(function() {
  // Global Application Context
  window.SciApp = {
    currentProject: null,
    activeProtocol: null,
    activeStep: null,
    columns: 4,
    searchQuery: "",
    theme: "dark",
    
    // Core custom fetch wrapper for X-Project-Override support
    async apiFetch(url) {
      const headers = {
        "Content-Type": "application/json"
      };
      if (this.currentProject) {
        headers["X-Project-Override"] = this.currentProject;
      }
      
      const response = await fetch(url + (url.includes("?") ? "&" : "?") + "project=" + encodeURIComponent(this.currentProject || ""), {
        headers
      });
      
      if (!response.ok) {
        throw new Error("HTTP error " + response.status);
      }
      return response.json();
    }
  };

  // Register Workspace selectors & UI events when window loads
  document.addEventListener("DOMContentLoaded", function() {
    initThemeChooser();
    initProjectWorkspaceLoader();
  });

  // 1. Theme Configuration
  function initThemeChooser() {
    const savedTheme = localStorage.getItem("sci-theme") || "dark";
    setTheme(savedTheme);

    const buttons = document.querySelectorAll(".theme-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", function() {
        const selected = btn.getAttribute("data-theme") || "dark";
        setTheme(selected);
      });
    });
  }

  function setTheme(themeName) {
    window.SciApp.theme = themeName;
    document.documentElement.setAttribute("data-theme", themeName);
    localStorage.setItem("sci-theme", themeName);

    // Update active button indicators
    const buttons = document.querySelectorAll(".theme-btn");
    buttons.forEach(btn => {
      const active = btn.getAttribute("data-theme") === themeName;
      btn.classList.toggle("active", active);
    });
  }

  // 2. Fetch projects and populate dynamic dropdown select controls
  async function initProjectWorkspaceLoader() {
    try {
      const selectWrapper = document.createElement("div");
      selectWrapper.className = "sidebar-form-group";
      selectWrapper.id = "project-chooser-group";
      selectWrapper.innerHTML = `
        <label class="sidebar-form-label">Active Project</label>
        <select class="sidebar-select" id="sel-project">
          <option value="">-- Scanning --</option>
        </select>
      `;

      // Insert dropdown select element on top of Protocol chooser filter in Sidebar
      const filters = document.querySelector(".sidebar-filters");
      if (filters) {
        filters.insertBefore(selectWrapper, filters.firstChild);
      }

      const data = await window.SciApp.apiFetch("/api/projects");
      const projSelect = document.getElementById("sel-project");
      
      if (data && data.projects && data.projects.length > 0) {
        projSelect.innerHTML = "";
        data.projects.forEach(p => {
          const opt = document.createElement("option");
          opt.value = p;
          opt.textContent = p;
          projSelect.appendChild(opt);
        });

        // Event listener to trigger workspace transitions
        projSelect.addEventListener("change", function(e) {
          switchProjectWorkspace(e.target.value);
        });

        // Primary starting workspace
        switchProjectWorkspace(data.projects[0]);
      }
    } catch (err) {
      console.log("Failed scanning projects workspace directories", err);
    }
  }

  async function switchProjectWorkspace(projName) {
    if (!projName) return;
    window.SciApp.currentProject = projName;
    
    // Refresh Sidebar session indicators
    const projIndicator = document.getElementById("ctx-project");
    if (projIndicator) projIndicator.textContent = projName;

    // Reset children models
    window.SciApp.activeProtocol = null;
    window.SciApp.activeStep = null;
    
    const protoCtx = document.getElementById("ctx-protocol");
    if (protoCtx) protoCtx.textContent = "-";
    const stepCtx = document.getElementById("ctx-step");
    if (stepCtx) stepCtx.textContent = "-";

    const stepNav = document.getElementById("step-nav");
    if (stepNav) stepNav.style.display = "none";

    // Refresh dynamic frontend
    if (typeof window.init === "function") {
      window.init();
    }
  }

  // Interactive controls zoom scale trackers
  let currentZoom = 1.0;
  let currentPan = { x: 0, y: 0 };
  let isPanningMode = false;
  let panOrigin = { x: 0, y: 0 };

  // Lightbox Zoom and Pan Events
  window.initLightboxInteraction = function(imgElement) {
    currentZoom = 1.0;
    currentPan = { x: 0, y: 0 };
    updateTransformations(imgElement);

    // Apply scroll scale zooms
    imgElement.parentElement.addEventListener("wheel", function(e) {
      e.preventDefault();
      const scaleAmt = e.deltaY < 0 ? 0.15 : -0.15;
      currentZoom = Math.min(Math.max(0.4, currentZoom + scaleAmt), 4.0);
      updateTransformations(imgElement);
    });

    // Panning controls drag events
    imgElement.addEventListener("mousedown", function(e) {
      e.preventDefault();
      isPanningMode = true;
      panOrigin.x = e.clientX - currentPan.x;
      panOrigin.y = e.clientY - currentPan.y;
    });

    window.addEventListener("mousemove", function(e) {
      if (!isPanningMode) return;
      currentPan.x = e.clientX - panOrigin.x;
      currentPan.y = e.clientY - panOrigin.y;
      updateTransformations(imgElement);
    });

    window.addEventListener("mouseup", function() {
      isPanningMode = false;
    });
  };

  function updateTransformations(el) {
    if (el) {
      el.style.transform = `translate(${currentPan.x}px, ${currentPan.y}px) scale(${currentZoom})`;
    }
  }

})();
