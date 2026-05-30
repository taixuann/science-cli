# PLAN: Protocol & Manifest Aware Dynamic Serve Layouts

## Classification
refactor | feature

## Related Plans
- [[290526_integrate_premium_frontend]] — completed (integrated the premium React layout base)

## Status
- **Created**: 2026-05-29
- **Status**: draft
- **Branch**: dev

## Objective
Enhance the visualization server (`sci serve`) backend and the premium React frontend dashboard to dynamically load the protocol's YAML configuration (`<protocol_name>.yaml`) and the step's results metadata (`manifest.json` / `metadata.json`). Based on the active step's configured technique (e.g. Cyclic Voltammetry `ec-cv`, Impedance `ec-eis`, or Memristor Switching `iv-sweep`), the server and dashboard will adapt in real-time to display custom layouts, metrics, overlays, and charts.

In addition, ensure that all visual documents (especially PDF, SVG, and high-DPI PNGs) fully scale to take up 100% of the display canvas's width and height to maximize readability at any viewport size.

## Context & Vision
Currently, the premium dashboard always displays a 6x6 Memristor Crossbar Grid and I-V Sweep Plotly charts. While perfect for memristive switching characterization (`iv-sweep`), this interface is completely irrelevant when a researcher is viewing an electrochemistry step (like Cyclic Voltammetry `ec-cv` for polymer deposition, or Chronoamperometry `ec-ca` for counter-ion doping) or an optical step (like Raman spectroscopy).

Tai's vision is a **technique-aware visual dashboard**. When the researcher selects a step in the sidebar:
1. The server reads the step's `technique` and `device` from the protocol's YAML file.
2. The server reads the step's results manifest (`manifest.json` or any technique-specific results JSON like EIS Nyquist fits).
3. The server merges this metadata and passes it to the frontend via the `/api/project` or `/api/protocol/...` endpoints.
4. The React client dynamically updates its tabs, panels, and parameters—rendering interactive Plotly charts and metrics tailored specifically to that technique (e.g., overlaying CV curves, showing EIS circuit fit elements, or plotting CA current decay).

## Specification

### 1. Backend Metadata Ingestion (`src/science_cli/serve/api.py`)
- **YAML Mapping**: In `_scan_protocol_dirs`, load `<protocol_name>.yaml`. Match step folder names and enrich each step object with its configured `technique` and `device`.
- **Manifest Ingestion**: For each step, scan its `results/` folder for `manifest.json` (or any `metadata.json`). If found, read and embed the manifest fields (`parameters`, `command`, `created` timestamp, `results` metrics) into the step data under a `manifest` attribute.

### 2. Sizing, Scaling, and Rendering (`documentation/science-cli-plot-gallery/src/App.tsx`)
- **Full Viewport Stretching**:
  - Render both `"svg"` and `"pdf"` files using custom `<iframe />` tags instead of `<img>` tags, allowing browsers to render vector graphics and multi-page reports natively.
  - Set the canvas viewframes to take up `w-full h-full min-h-[440px]...` for `iframe` elements, and `w-full h-full object-contain` for raster images to stretch and fit the preview pane beautifully.
  - In the fullscreen Lightbox modal, set the pan wrapper size to `w-[90%] h-[90%]` and scale the embedded `iframe`/`img` to `w-full h-full` to leverage maximum resolution.

### 3. Frontend Adaptation Lifecycle
- **Dynamic Tab Rendering**:
  - If `activeStep.technique` is `iv-sweep` or `mem-switching`: Keep the **6x6 Crossbar Heatmap** tab active, displaying parameter distribution, yield, and I-V curves.
  - If `activeStep.technique` is `ec-cv` or `ec-ca` (Electrochemistry): Render an **Electrochemistry Analytics** tab. Instead of the 6x6 grid, display potential-current loops or chronoamperometric transients, and show deposition stats (charge passed, peak separation).
  - If `activeStep.technique` is `ec-eis` (Impedance): Render an **EIS Impedance Nyquist** tab. Extract equivalent circuit fitting elements (like $R_s$, $R_{ct}$, CPE constant) from the results JSON and plot Nyquist/Bode curves.
- **Visual Symmetrical Enhancements**:
  - Update the sidebar step buttons to show a small technique-specific colored badge (e.g. `CV` in green, `EIS` in blue, `IV` in purple) next to the step name.

---

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| [api.py](file:///Users/tai/workspace/tools/science-cli/src/science_cli/serve/api.py) | [MODIFY] | Enrich step list with `technique`, `device`, and parsed `manifest.json` metadata from the results directories. |
| [App.tsx](file:///Users/tai/workspace/tools/science-cli/documentation/science-cli-plot-gallery/src/App.tsx) | [MODIFY] | Refine the React viewports to scale previews to full width/height, handle PDF files as iframe components, and conditionally render tabs based on `activeStep.technique`. |

---

## Test & Build Strategy
1. **Frontend Compilation**: Run `npm run build` inside `documentation/science-cli-plot-gallery/` to compile the updated React application.
2. Overwrite the files in `src/science_cli/serve/frontend/assets/` with the updated compiled assets.
3. **Automated Verification**: Run `pytest` to make sure all 97 codebase tests continue to pass.
4. **Manual Validation**: Launch the dev server, select `3_ca-doping` (which features mixed `ec-cv`, `ec-ca`, and `ec-eis` steps), and verify the dashboard layout adapts dynamically for each step!
