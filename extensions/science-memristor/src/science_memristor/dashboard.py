"""Self-contained HTML dashboard for memristor IV curve plots.

Reads devices.yaml and scans results/ for generated SVGs,
assembles a pure HTML+CSS page with per-material matrix grids
and inline plot galleries. Works with file:// protocol — no
web server required.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

# Material color palette — distinct enough for side-by-side grids
_MATERIAL_COLORS = [
    "#a8d8ea",  # light blue
    "#f4bfbf",  # light red
    "#c3e6cb",  # light green
    "#ffeaa7",  # light yellow
    "#d4b8d9",  # light purple
    "#ffd8a8",  # light orange
    "#b8d4e3",  # steel blue
    "#e8d4b8",  # tan
]
_COLOR_INDEX: dict[str, str] = {}


def _get_material_color(material_key: str) -> str:
    """Assign a consistent color to each material key."""
    if material_key not in _COLOR_INDEX:
        idx = len(_COLOR_INDEX) % len(_MATERIAL_COLORS)
        _COLOR_INDEX[material_key] = _MATERIAL_COLORS[idx]
    return _COLOR_INDEX[material_key]


def generate_dashboard(
    config,
    results_dir: Path,
    output_path: str | Path,
) -> Path:
    """Generate a self-contained HTML dashboard for IV curve plots.

    Args:
        config: DeviceConfig instance loaded from devices.yaml.
        results_dir: Directory containing the generated SVG files.
        output_path: Where to write the HTML file.

    Returns:
        Path to the generated HTML file.
    """
    from science_memristor.plotting import _extract_sweep_annotations

    # Collect all plots: (material_key, row, col, sweep_type, order, plot_filename, fe)
    plots: list[dict] = []
    for pt, fe in config.get_all_files("iv"):
        plot_file = fe.extra.get("plot", "")
        if not plot_file:
            continue
        svg_path = results_dir / plot_file
        if not svg_path.exists():
            continue

        from science_memristor.device import extract_material_batch
        mb = extract_material_batch(fe.file)
        if mb:
            mat_name, batch = mb
            mat_key = f"{mat_name}({batch})" if batch else mat_name
        else:
            mat_key = "unknown"

        order = fe.sweep_order or 0
        if order == 0:
            tg = pt.techniques.get("iv")
            if tg:
                for idx, f in enumerate(tg.sorted_files(), 1):
                    if f.file == fe.file:
                        order = idx
                        break

        # Build caption annotations from sweep metadata
        annotations = _extract_sweep_annotations(fe.sweep)
        caption_parts = [f"r{pt.row}c{pt.col}", mat_key, fe.sweep_type or "uc"]
        if annotations["sweep_rate"]:
            caption_parts.append(annotations["sweep_rate"])
        if annotations["voltage_range"]:
            caption_parts.append(annotations["voltage_range"])

        anchor = f"r{pt.row}c{pt.col}-{mat_key.replace('/', '-').replace(' ', '_')}-{order:02d}"

        plots.append({
            "material_key": mat_key,
            "row": pt.row,
            "col": pt.col,
            "sweep_type": fe.sweep_type or "uc",
            "order": order,
            "plot_file": plot_file,
            "caption": " | ".join(caption_parts),
            "anchor": anchor,
        })

    if not plots:
        raise ValueError(
            "No plotted SVGs found. Run 'memristor plot --all' first."
        )

    # Group by material
    material_groups: dict[str, list[dict]] = {}
    for p in plots:
        material_groups.setdefault(p["material_key"], []).append(p)

    # Group by position → material → sweep_type for plot galleries
    position_groups: dict[tuple, list[dict]] = {}
    for p in plots:
        key = (p["row"], p["col"], p["material_key"], p["sweep_type"])
        position_groups.setdefault(key, []).append(p)

    # Determine global row/col bounds
    all_rows = {p["row"] for p in plots}
    all_cols = {p["col"] for p in plots}
    if all_rows and all_cols:
        min_row, max_row = min(all_rows), max(all_rows)
        min_col, max_col = min(all_cols), max(all_cols)
    else:
        min_row = max_row = min_col = max_col = 0

    html = _build_html(
        config=config,
        material_groups=material_groups,
        position_groups=position_groups,
        total_plots=len(plots),
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    return out


def _build_html(
    config,
    material_groups: dict[str, list[dict]],
    position_groups: dict[tuple, list[dict]],
    total_plots: int,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build the full HTML document string."""
    device_label = config.device.label or config.device.id or "Memristor Device"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    matrices_html = _build_matrices_row(
        material_groups=material_groups,
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

    galleries_html = _build_position_galleries(position_groups)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{device_label} — IV Dashboard</title>
<style>
{css()}
</style>
</head>
<body>

<header>
  <h1>{device_label}</h1>
  <p>{total_plots} IV plots | {len(material_groups)} material(s) | Generated: {date_str}</p>
</header>

<main>
{matrices_html}
{galleries_html}
</main>

</body>
</html>"""


def _build_matrices_row(
    material_groups: dict[str, list[dict]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build a horizontal flex row containing ALL material matrix grids.

    Each material gets one compact matrix table in the row.
    Anchor links in cells point down to the plot galleries below.
    """
    matrices = ""
    for mat_key in sorted(material_groups.keys()):
        plots = material_groups[mat_key]
        color = _get_material_color(mat_key)

        positions = set()
        for p in plots:
            positions.add((p["row"], p["col"]))

        matrix_html = _build_matrix_table(
            plots=plots,
            mat_key=mat_key,
            positions=positions,
            min_row=min_row,
            max_row=max_row,
            min_col=min_col,
            max_col=max_col,
            color=color,
        )
        matrices += matrix_html

    if not matrices:
        return ""

    return f'<div class="matrix-row">{matrices}</div>'


def _build_position_galleries(
    position_groups: dict[tuple, list[dict]],
) -> str:
    """Build plot galleries grouped by cell position → material → sweep_type.

    Each group gets a heading: ``T{row+1}-B{col+1}  |  {material}  |  {sweep_type}``
    and a grid of plot figures.
    """
    sections = ""
    for key in sorted(position_groups.keys()):
        row, col, mat_key, sweep_type = key
        plots = position_groups[key]

        heading = f"T{row + 1}-B{col + 1}  |  {mat_key}  |  {sweep_type}"
        gallery_html = _build_plot_gallery(plots)

        sections += f"""
<section class="plot-group" id="group-{row}-{col}-{mat_key.replace('/', '-').replace(' ', '_')}-{sweep_type}">
  <h3>{heading}</h3>
  <div class="plot-gallery">
    {gallery_html}
  </div>
</section>"""

    return sections


def _build_material_section(
    mat_key: str,
    plots: list[dict],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build a collapsible section for one material."""
    color = _get_material_color(mat_key)
    n_plots = len(plots)

    # Gather unique positions for this material
    positions = set()
    for p in plots:
        positions.add((p["row"], p["col"]))

    # Build matrix table
    matrix_html = _build_matrix_table(
        plots=plots,
        mat_key=mat_key,
        positions=positions,
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
        color=color,
    )

    # Build plot gallery
    gallery_html = _build_plot_gallery(plots)

    return f"""
<section class="material-section" style="border-left: 4px solid {color};">
<details open>
<summary>
  <span class="material-name">{mat_key}</span>
  <span class="material-count">{n_plots} plot(s) in {len(positions)} cell(s)</span>
</summary>

<div class="material-body">
  {matrix_html}
  <h3>IV Curves</h3>
  <div class="plot-gallery">
    {gallery_html}
  </div>
</div>
</details>
</section>"""


def _build_matrix_table(
    plots: list[dict],
    mat_key: str,
    positions: set[tuple[int, int]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    color: str,
) -> str:
    """Build an HTML table representing the crossbar matrix for one material."""
    # Build lookup: (row, col) -> list of plot orders
    cell_plots: dict[tuple[int, int], list[int]] = {}
    for p in plots:
        cell_plots.setdefault((p["row"], p["col"]), []).append(p["order"])

    n_rows = max_row - min_row + 1
    n_cols = max_col - min_col + 1

    rows_html = ""
    # Display rows from max (top) to min (bottom) — like T labels
    for r in range(max_row, min_row - 1, -1):
        cells = ""
        for c in range(min_col, max_col + 1):
            pos = (r, c)
            orders = cell_plots.get(pos, [])
            if orders:
                # Build anchor link
                # Find the first plot with this position
                first_order = sorted(orders)[0]
                anchor = f"r{r}c{c}-{mat_key.replace('/', '-').replace(' ', '_')}-{first_order:02d}"
                order_text = ",".join(str(o) for o in sorted(orders))
                cells += (
                    f'<td class="cell measured" style="background-color: {color};"'
                    f'><a href="#{anchor}">{order_text}</a></td>'
                )
            else:
                cells += '<td class="cell empty"></td>'
        t_label = f"T{r + 1}" if r >= 0 else ""
        rows_html += f"<tr><th>{t_label}</th>{cells}</tr>\n"

    # Bottom electrode labels
    b_labels = "".join(f"<th>B{c + 1}</th>" for c in range(min_col, max_col + 1))

    return f"""
<div class="matrix-container">
<h4>{mat_key}</h4>
<table class="matrix">
  <thead>
    <tr><th></th>{b_labels}</tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</div>"""


def _build_plot_gallery(plots: list[dict]) -> str:
    """Build the plot gallery for a material section."""
    items = ""
    for p in plots:
        items += f"""
  <figure class="plot-figure" id="{p['anchor']}">
    <img src="{p['plot_file']}" alt="{p['caption']}" loading="lazy">
    <figcaption>{p['caption']}</figcaption>
  </figure>"""
    return items


def css() -> str:
    """Return the CSS stylesheet for the dashboard."""
    return """
/* ── Reset & Base ─────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #f5f5f5;
  color: #222;
  line-height: 1.5;
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

/* ── Header ───────────────────────────────── */
header {
  background: #fff;
  border-radius: 8px;
  padding: 24px 32px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
header h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
header p  { color: #666; font-size: 0.9rem; }

/* ── Matrix row (all materials, top of page) ── */
.matrix-row {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 12px;
  margin-bottom: 24px;
}
.matrix-row .matrix-container {
  flex: 0 0 auto;
  min-width: 200px;
  max-width: 320px;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ── Material sections ─────────────────────── */
.material-section {
  background: #fff;
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.material-section details summary {
  cursor: pointer;
  font-size: 1.15rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 12px;
  user-select: none;
}
.material-section details summary::-webkit-details-marker { display: none; }
.material-section details summary::before {
  content: "▸";
  display: inline-block;
  width: 16px;
  transition: transform 0.2s;
  font-size: 0.8rem;
}
.material-section details[open] summary::before {
  transform: rotate(90deg);
}
.material-name  { color: #222; }
.material-count { color: #888; font-weight: 400; font-size: 0.9rem; }
.material-body  { margin-top: 16px; }

/* ── Plot groups (per cell → material → sweep_type) ── */
.plot-group {
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.plot-group h3 {
  font-size: 1.0rem;
  font-weight: 600;
  margin-bottom: 14px;
  color: #333;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0e0e0;
}

/* ── Matrix table ──────────────────────────── */
.matrix-container { margin-bottom: 24px; overflow-x: auto; }
.matrix-container h4 { font-size: 0.95rem; margin-bottom: 8px; color: #555; }
.matrix {
  border-collapse: collapse;
  font-size: 0.85rem;
}
.matrix th, .matrix td {
  border: 1px solid #ddd;
  padding: 6px 10px;
  text-align: center;
  min-width: 36px;
  height: 32px;
}
.matrix th {
  background: #eee;
  font-weight: 600;
  color: #444;
}
.matrix td.empty {
  background: #fafafa;
  color: #ccc;
}
.matrix td.measured a {
  color: #222;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.8rem;
}
.matrix td.measured a:hover {
  text-decoration: underline;
}

/* ── Plot gallery ──────────────────────────── */
.material-body h3 {
  font-size: 0.95rem;
  margin-bottom: 12px;
  color: #555;
}
.plot-gallery {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}
@media (max-width: 900px) {
  .plot-gallery { grid-template-columns: 1fr; }
}
.plot-figure {
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}
.plot-figure img {
  max-width: 100%;
  height: auto;
  background: #fff;
}
.plot-figure figcaption {
  margin-top: 8px;
  font-size: 0.8rem;
  color: #555;
  font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
  word-break: break-all;
}
"""
