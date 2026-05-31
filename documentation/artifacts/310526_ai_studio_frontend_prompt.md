# Google AI Studio Prompt: Premium React Gallery & Dashboard Configuration

This document contains the tailored prompt and the file checklist to upload to Google AI Studio to enhance the interactive `science-cli` React frontend gallery.

## 📦 Files to Upload to Google AI Studio
When starting your session in Google AI Studio, drag and drop the following files into the prompt area:
1. **`App.tsx`** (located at [App.tsx](file:///Users/tai/workspace/tools/science-cli/documentation/science-cli-plot-gallery/src/App.tsx)) — The main React application logic.
2. **`index.css`** (located at [index.css](file:///Users/tai/workspace/tools/science-cli/documentation/science-cli-plot-gallery/src/index.css)) — The TailwindCSS styles and design tokens.

---

## 💬 Copy-Pasteable Prompt for Google AI Studio

Copy and paste the exact prompt below into Google AI Studio after uploading the two files above:

```text
You are a senior React and TailwindCSS expert developer specializing in interactive scientific dashboards and data visualization portals.

I have uploaded my frontend React application files:
- App.tsx: The main gallery and 6x6 crossbar dashboard view.
- index.css: The stylesheet.

I need you to upgrade and configure the React frontend to add advanced diagnostics, volatile memristor classification, and dynamic cycle-highlight overlays. Please modify App.tsx to implement the following features:

### 1. Volatile vs. Non-Volatile Classification Panels
Volatile memristors exhibit a clean SET process but have a highly unstable, low-voltage, or non-existent RESET process. To help researchers identify volatile devices at a glance:
- Expand the 6x6 Crossbar Heatmap Tab to show separate metric choices in the selector:
  - Median V_set Voltage
  - Median V_reset Voltage (and mark cells with no reset or V_reset < 0.15V as "Volatile / Relaxation Profile")
  - ON/OFF Ratio (10^1 to 10^6+)
  - SET Yield vs. RESET Yield distinctly (instead of a single combined yield)
- Add a new "Diagnostics Panel" in the sidebar or right column that reads cell data and outputs a classification badge:
  - "Volatile Memristor" (high SET yield, but extremely low/unstable RESET yield or V_reset < 0.15V)
  - "Non-Volatile Memristor" (stable bi-stable switching with clean SET and RESET distributions)
  - "Stuck ON / Shorted" (ON/OFF ratio near 1, high current in both states)
  - "Stuck OFF / Insulating" (very low current across all sweep cycles)

### 2. Multi-Cycle Curve Highlight Overlay
When displaying multi-cycle IV sweep curves (such as 667-cycle sweeps) in the gallery:
- Add an interactive "Cycle Overlay Controller" overlay on the Plot Gallery view.
- Provide quick-toggle preset pills: "All Cycles", "First/Last", "Decades (1, 10, 100, 500)", and a custom text input where researchers can type comma-separated cycles (e.g. "1, 10, 50, 100, 200, 500").
- When a filter is set, dynamically adjust the SVG or custom plot view to highlight selected cycles in bold primary colors (Emerald/Indigo/Cyan/Orange) and fade all unselected background cycles into a thin, semi-transparent grey (#E0E0E0, alpha 0.15, width 0.5px).

### 3. Crisp Vector Inline SVGs
Currently, the figures gallery renders file previews using generic iframes or microscopic thumbnails.
- Replace any low-resolution preview elements in the right sidebar list and center display with crisp, inline SVG rendering.
- For SVGs, parse the underlying XML strings or fetch them dynamically to inject them as direct react inline SVG nodes. This allows custom CSS styling (such as adapting colors on the fly based on Light/Dark/OLED mode) and pixel-perfect high-DPI scaling.

### 4. Premium Visual Layout Upgrades
- Implement a true split-screen layout when a figure is maximized, letting the user compare the IV sweep curve side-by-side with its extracted metrics table ($V_{set}$, $V_{reset}$, ON/OFF ratio, median parameters).
- Add subtle glassmorphism effects (backdrop-blur, thin border rings, soft glowing gradients) on the cards and dashboards to fit a premium Nature-style aesthetic.
- Preserve the existing projects switcher, protocol tree selectors, active step context widgets, and full theme synchronization (Light, Dark, OLED).

Please output the complete, fully updated App.tsx code with clean TypeScript typings and premium Tailwind classes.
```
