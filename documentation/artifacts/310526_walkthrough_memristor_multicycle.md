# WALKTHROUGH: Memristor Multi-Cycle Overlay & Direct Switching Statistics

We have successfully implemented and verified the two major features to help analyze and visualize very large memristor datasets (up to 2,000+ files per protocol) inside the `science-cli` codebase!

---

## 🌟 Visual Result: 667-Cycle Highlight Plot

Below is the generated Nature-style overlay plot for position `r1c4` under material `cu-c-pda(q)-ito` consisting of **667 sequential cycling sweeps**. 
- Highlighted cycles (`1`, `10`, `50`, `100`, `200`, `500`) are rendered in highly distinct, vibrant, solid lines with their specific parsed $V_{set}$ and $V_{reset}$ threshold parameters shown in the legend.
- All other 661 background cycles are plotted as a thin, semi-transparent grey envelope showing the full endurance envelope and variability bounds without clutter.

![667-Cycle Highlight Plot](/Users/tai/.gemini/antigravity/brain/cd0b0af3-f905-4a59-a12f-6fac0932bb18/iv_r1c4_cu-c-pda(q)-ito_multicycle.svg)

---

## 🛠️ Changes Implemented (All inside `dev` branch)

1. **Vibrant Highlight Plotting (`plotting.py`)**:
   - Implemented `generate_iv_highlighted_svg(traces, highlight_cycles, output_path, dpi=150)` that divides curves into foreground colored highlights (vibrant Nature colormap cycle) and background semi-transparent grey curves (`#E0E0E0`, `alpha=0.15`, `linewidth=0.5`).
   - Automatically populates the legend labels with cycle index and extracted database parameters, e.g. `Cycle 10 (Vset=0.35V, Vreset=-0.12V)`.
2. **Unified Path & Technique Fallbacks (`device.py`)**:
   - Added robust mapping fallbacks (`_resolve_tech_key` and inside `DeviceConfig.resolve_file_path`) so that shorthands like `"iv"` seamlessly resolve to `"iv-sweep"` when loading files or determining step folders.
3. **Interactive Cycle Selection & CLI integrations (`device_cli.py`)**:
   - Implemented the `--highlight` CSV/range parser helper `parse_cycles_list`.
   - Updated the `memristor plot` CLI command handler. If `--highlight` is passed but multiple cells are loaded, it launches an interactive `fzf` prompt to let the user select the target cell.
   - Updated the `memristor info` command to automatically connect to SQLite and output a comprehensive statistical summary block of $V_{set}$, $V_{reset}$, median ON/OFF ratios, and successful switching yields.

---

## 📊 Terminal Verification: Direct Switching Statistics

Running the enhanced `sci memristor info` command instantly processes 670 cycles of cell `r1c4` in the database and prints:

```text
  Switching Statistics (from SQLite):
    Total cycles: 670
    SET events detected:   662/670 (98.8% yield)
    RESET events detected: 670/670 (100.0% yield)
    V_set   = 0.392 ± 0.221 V (range: 0.00 to 0.93 V)
    V_reset = 0.122 ± 0.116 V (range: 0.00 to 0.72 V)
    Median ON/OFF Ratio:   2.25e+01
```

> [!NOTE]
> Volatile memristors relax automatically back to their high-resistance state (HRS) when voltage returns to zero, yielding extremely low $V_{reset}$ values ($0.122\text{ V}$) close to zero compared to their threshold $V_{set}$ ($0.392\text{ V}$). Separating the statistics and yields distinctly allows fast volatile vs. non-volatile classification on the command line!
