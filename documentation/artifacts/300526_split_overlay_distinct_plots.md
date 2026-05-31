# PLAN: Split and Categorize Step Figures into Overlays and Individual Sweeps

## Classification
feature / refactor

## Related Plans
- [[290526_dynamic_serve_metadata]] — related (dynamic technique & serving)
- [[290526_integrate_premium_frontend]] — related (integrated premium React dashboard)

## Status
- **Created**: 2026-05-30
- **Status**: draft
- **Branch**: dev

## Objective
Split and categorize the visual plots list in the sidebar gallery for each step into two distinct groups:
1. **Overlays & Summaries** (e.g. fit parameters, overlay curves, summary sheets).
2. **Individual Sweeps** (plots that correspond directly to raw data files, e.g. prepended with `ec-cv_filename` or similar).

Also, replace tiny PDF iframe thumbnails in the sidebar gallery with a premium static SVG PDF document icon to prevent annoying native browser magnifier/control overflows.

## Context
When displaying scientific plots in a protocol step, there are two distinct types of visualization files:
1. Custom-named plots representing fits, multiple overlays, and consolidated summaries (e.g. `fit_parameters.png`, `overlay_cv.svg`).
2. Plots representing individual sweeps of raw data (e.g. `ec-cv_cu-c-pda_01.pdf`).

Currently, the gallery lists all files in a single flat list, making it hard to scan. By splitting the visual files into **Overlays & Summaries** and **Individual Sweeps**, the sidebar list will be much more organized. Additionally, embedding iframe elements for PDF thumbnails inside the tiny `w-11 h-11` thumbnails triggers native browser PDF viewer magnifiers and toolbars that overlap the sidebar. Using a neat vector document icon instead solves this perfectly.

## Specification

### 1. Update Frontend Data Models (`App.tsx`)
Update the `FileItem` interface to support an optional `category` property sent by the backend:
```typescript
interface FileItem {
  name: string;
  path: string;
  type: string;
  size?: string;
  created?: string;
  dimensions?: string;
  category?: "distinct" | "overlay";
}
```

### 2. Update Gallery Sidebar Rendering (`App.tsx`)
In the figures list viewport of the React app:
1. Filter the files by the search query first.
2. Group the filtered files into two subsets:
   - `overlays = filtered.filter(f => f.category === "overlay" || !f.category)`
   - `distincts = filtered.filter(f => f.category === "distinct")`
3. Render two distinct sections in the sidebar viewport, each with a visual indicator, count, and clear section title:
   - **Overlays & Summaries** (accented with `✦` and a subtle warm gold text color)
   - **Individual Sweeps** (accented with `⚏` and a sleek indigo text color)
4. Show a visual message if a section is empty.
5. Set `selectedGalleryFile` automatically to the first available file in the step (preferring overlays, fallback to sweeps).

### 3. Replace PDF Thumbnails with a Premium SVG Vector Icon
Inside the gallery list item's thumbnail preview block (`w-11 h-11` element), if `file.type === "pdf"`, instead of loading the `/files/...` source in a tiny scale-50 `iframe`, render a clean custom vector document SVG icon.
This will prevent all modern browser layout engine bugs that trigger native hover overlays, zoom controls, and download buttons inside microscopic thumbnail frames.

### 4. Build and Package frontend assets
1. Run `npm run build` in `documentation/science-cli-plot-gallery/`.
2. Move/copy the compiled React assets (JS and CSS) from `documentation/science-cli-plot-gallery/dist/assets/` to `src/science_cli/serve/frontend/assets/`.
3. Update `src/science_cli/serve/frontend/index.html` to reference the newly generated JS/CSS asset hashes.

---

## Files to Modify

| File | Action | Reason |
|------|--------|--------|
| [App.tsx](file:///Users/tai/workspace/tools/science-cli/documentation/science-cli-plot-gallery/src/App.tsx) | [MODIFY] | Split figures into two categories (overlays & distinct sweeps) and replace iframe PDF thumbnails with a static vector document SVG icon. |
| [index.html](file:///Users/tai/workspace/tools/science-cli/src/science_cli/serve/frontend/index.html) | [MODIFY] | Update JS and CSS script tags to point to the newly built production assets. |

---

## Dependencies
- Backend modifications in `src/science_cli/serve/api.py` are already completed and ready, assigning `category: "distinct"` or `"overlay"` dynamically.

## Cross-PLAN Impact
- None. Fully localized to the frontend visualization server and client dashboard.

## Test Strategy

### Automated Tests
- Run `pytest` to ensure all 97 codebase tests remain green.

### Manual Verification
- Start the server (`bin/sci serve --port 8001`).
- Navigate to the browser dashboard (`http://localhost:8001`).
- Select a step that contains both overlays/summaries and individual measurement sweep plots.
- Verify that the sidebar gallery is cleanly split into two styled sections with headers.
- Verify that hovering or interacting with PDF previews in the sidebar no longer spawns native PDF magnifying glasses or floating toolbar buttons.
- Confirm full-screen lightbox previews and main viewports still render high-resolution PDFs beautifully.

---

## Progress
- [ ] PLAN created
- [ ] User approved
- [ ] IMPLEMENT: Update App.tsx logic and layout
- [ ] IMPLEMENT: PDF SVG thumbnail replacement
- [ ] IMPLEMENT: Build and package frontend assets
- [ ] TEST: Run pytest & verify manually
- [ ] COMMIT done
