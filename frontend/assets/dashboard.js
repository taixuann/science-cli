window.SciApp = {
  activeTheme: "light",
  currentProject: null,

  init() {
    this.setupTheme();
    this.setupSidebarToggle();
    this.loadGlobalContext();
    this.bindGlobalEvents();
  },

  async apiFetch(url, options = {}) {
    this.showGlobalLoader(true);
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`API error [${url}]:`, error);
      this.showErrorBanner(`Server error: ${error.message}`);
      throw error;
    } finally {
      this.showGlobalLoader(false);
    }
  },

  setupTheme() {
    const saved = localStorage.getItem("sci-theme") || "light";
    this.setTheme(saved);
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.addEventListener("click", e => {
        const theme = e.target.getAttribute("data-theme");
        if (theme) {
          this.setTheme(theme);
          window.dispatchEvent(new CustomEvent("scithemechange", { detail: theme }));
        }
      });
    });
  },

  setTheme(theme) {
    this.activeTheme = theme;
    localStorage.setItem("sci-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-theme") === theme);
    });
    document.body.style.transition = "background-color 0.3s ease, color 0.3s ease";
  },

  setupSidebarToggle() {
    const toggleBtn = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar");
    if (toggleBtn && sidebar) {
      toggleBtn.addEventListener("click", e => {
        e.stopPropagation();
        sidebar.classList.toggle("active");
      });
      document.addEventListener("click", e => {
        if (sidebar.classList.contains("active") && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove("active");
        }
      });
    }
  },

  async loadGlobalContext() {
    try {
      const data = await this.apiFetch("/api/project");
      this.currentProject = data;
      const el = document.getElementById("ctx-project");
      if (el) el.textContent = data.project_name;
    } catch (e) {
      console.warn("Could not load project context:", e);
    }
  },

  bindGlobalEvents() {
    const banner = document.createElement("div");
    banner.id = "sci-error-banner";
    banner.style.cssText = "position:fixed;bottom:20px;right:20px;background:#ff5252;color:#fff;padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.5);font-size:13px;z-index:10000;display:none;align-items:center;gap:12px;transition:all 0.3s ease;font-weight:500;";
    banner.innerHTML = '<span class="banner-msg"></span><button style="border:none;background:none;color:white;cursor:pointer;font-weight:700;font-size:14px;" onclick="this.parentElement.style.display=\'none\'">\u2715</button>';
    document.body.appendChild(banner);
  },

  showErrorBanner(msg) {
    const banner = document.getElementById("sci-error-banner");
    if (banner) {
      banner.querySelector(".banner-msg").textContent = msg;
      banner.style.display = "flex";
      setTimeout(() => { banner.style.display = "none"; }, 7000);
    }
  },

  showGlobalLoader(show) {
    let bar = document.getElementById("sci-top-loading-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "sci-top-loading-bar";
      bar.style.cssText = "position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--accent-cyan),var(--accent-blue));z-index:10001;transition:width 0.2s ease;width:0%;";
      document.body.appendChild(bar);
    }
    if (show) {
      bar.style.width = "40%";
      setTimeout(() => { if (bar.style.width === "40%") bar.style.width = "80%"; }, 300);
    } else {
      bar.style.width = "100%";
      setTimeout(() => { bar.style.width = "0%"; }, 200);
    }
  },

  formatDate(dateString) {
    if (!dateString) return "-";
    const d = new Date(dateString);
    return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" })
      + " " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
};

document.addEventListener("DOMContentLoaded", () => { window.SciApp.init(); });
