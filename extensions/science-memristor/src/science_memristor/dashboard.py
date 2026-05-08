"""Self-contained HTML dashboard for memristor IV curve plots.

Reads devices.yaml and scans results/ for generated SVGs,
assembles a pure HTML+CSS page with per-cell click-to-show
``<details>`` elements and per-material matrix grids at the top.
Works with file:// protocol — no web server required.
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


# ── Number range formatting (Issue 3) ──────────────────────────


def _format_number_ranges(numbers: list[int]) -> str:
    """Collapse consecutive numbers into ranges.

    Args:
        numbers: Sorted (or unsorted) list of integers.

    Returns:
        String like ``"1-10"`` or ``"1-5, 11-15"``.
        Single numbers shown as just the number.

    Examples:
        >>> _format_number_ranges([1,2,3,4,5,6,7,8,9,10])
        '1-10'
        >>> _format_number_ranges([1,2,3,4,5,11,12,13,14,15])
        '1-5, 11-15'
        >>> _format_number_ranges([3])
        '3'
    """
    if not numbers:
        return ""
    numbers = sorted(set(numbers))
    ranges: list[tuple[int, int]] = []
    start = numbers[0]
    end = numbers[0]
    for n in numbers[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append((start, end))
            start = end = n
    ranges.append((start, end))

    parts: list[str] = []
    for s, e in ranges:
        if s == e:
            parts.append(str(s))
        else:
            parts.append(f"{s}-{e}")
    return ", ".join(parts)


# ── Dashboard generation ──────────────────────────────────────


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

    # Collect all plots
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

        # Build annotation text from sweep metadata
        annotations = _extract_sweep_annotations(fe.sweep)
        caption_parts = [f"#{order:02d}"]
        if annotations["sweep_rate"]:
            caption_parts.append(annotations["sweep_rate"])
        direction = annotations.get("direction")
        if direction:
            caption_parts.append(direction)
        else:
            caption_parts.append(fe.sweep_type or "uc")

        plots.append({
            "material_key": mat_key,
            "row": pt.row,
            "col": pt.col,
            "sweep_type": fe.sweep_type or "uc",
            "order": order,
            "plot_file": plot_file,
            "caption": "  |  ".join(caption_parts),
            "material_caption": f"r{pt.row}c{pt.col} | {mat_key} | {fe.sweep_type or 'uc'}",
        })

    if not plots:
        raise ValueError(
            "No plotted SVGs found. Run 'memristor plot --all' first."
        )

    # Group by material
    material_groups: dict[str, list[dict]] = {}
    for p in plots:
        material_groups.setdefault(p["material_key"], []).append(p)

    # Group by cell position (row, col) for cell-level <details>
    cell_groups: dict[tuple[int, int], list[dict]] = {}
    for p in plots:
        pos = (p["row"], p["col"])
        cell_groups.setdefault(pos, []).append(p)

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
        cell_groups=cell_groups,
        total_plots=len(plots),
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    return out


# ── HTML construction ─────────────────────────────────────────


def _build_html(
    config,
    material_groups: dict[str, list[dict]],
    cell_groups: dict[tuple[int, int], list[dict]],
    total_plots: int,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build the full HTML document."""
    device_label = config.device.label or config.device.id or "Memristor Device"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    matrices_html = _build_matrices_row(
        material_groups=material_groups,
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

    cell_details_html = _build_cell_details(
        cell_groups=cell_groups,
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

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
  <p>{total_plots} IV plots | {len(material_groups)} material(s) | {len(cell_groups)} cell(s) | Generated: {date_str}</p>
</header>

<main>
{matrices_html}
{cell_details_html}
</main>

<script>
{_js_click_to_open()}
</script>

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

    Each material gets one compact matrix table. Anchor links point
    to per-cell ``<details>`` elements below (``#cell-r0c0``).
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
    """Build an HTML table representing the crossbar matrix for one material.

    Cell links point to ``#cell-r{row}c{col}``.  Cell text uses
    ``_format_number_ranges`` for compact display (Issue 3).
    """
    # Build lookup: (row, col) -> list of plot orders
    cell_plots: dict[tuple[int, int], list[int]] = {}
    for p in plots:
        cell_plots.setdefault((p["row"], p["col"]), []).append(p["order"])

    rows_html = ""
    # Display rows from max (top) to min (bottom) — like T labels
    for r in range(max_row, min_row - 1, -1):
        cells = ""
        for c in range(min_col, max_col + 1):
            pos = (r, c)
            orders = cell_plots.get(pos, [])
            if orders:
                sorted_orders = sorted(set(orders))
                range_text = _format_number_ranges(sorted_orders)
                anchor = f"cell-r{r}c{c}"
                # Material info in the link for context
                n_files = len(sorted_orders)
                label = (
                    f"#{range_text}"
                    if n_files == 1
                    else f"#{range_text} ({n_files})"
                )
                cells += (
                    f'<td class="cell measured" style="background-color: {color};"'
                    f'><a href="#{anchor}" class="matrix-cell-link"'
                    f' title="T{r+1}-B{c+1}: {n_files} file(s)">{label}</a></td>'
                )
            else:
                cells += '<td class="cell empty"></td>'
        t_label = f"T{r + 1}" if r >= 0 else ""
        rows_html += f"<tr><th>{t_label}</th>{cells}</tr>\n"

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


def _build_cell_details(
    cell_groups: dict[tuple[int, int], list[dict]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build one ``<details>`` element per (row, col) cell position.

    Each ``<details>`` contains ALL plots at that position across all
    materials. The ``id`` matches the matrix-cell anchor so native
    link navigation + a small JS snippet opens it on click.

    ``<summary>`` shows: ``T1-B1 (3 materials, 20 files: #1-#20)``
    """
    if not cell_groups:
        return '<p class="no-data">No plotted cells found.</p>'

    sections = ""
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            pos = (row, col)
            cell_plots = cell_groups.get(pos)
            if not cell_plots:
                continue

            # Gather metadata for summary
            materials_in_cell = sorted(set(p["material_key"] for p in cell_plots))
            orders = sorted(set(p["order"] for p in cell_plots))
            n_files = len(orders)
            range_text = _format_number_ranges(orders)
            n_materials = len(materials_in_cell)

            t_label = row + 1
            b_label = col + 1
            mat_summary = ", ".join(materials_in_cell)

            # Build summary line
            if n_materials == 1:
                summary_line = (
                    f"T{t_label}-B{b_label}  |  {mat_summary}"
                    f"  ({n_files} files: #{range_text})"
                )
            else:
                summary_line = (
                    f"T{t_label}-B{b_label}  ({n_materials} materials, "
                    f"{n_files} files: #{range_text})"
                )

            # Build plot gallery — grouped by material within the cell
            gallery_parts = ""
            for mat_key in materials_in_cell:
                mat_plots = [
                    p for p in cell_plots if p["material_key"] == mat_key
                ]
                # Sub-heading for material
                gallery_parts += (
                    f'<h5 class="cell-material-heading">{mat_key}</h5>'
                )
                gallery_parts += _build_plot_gallery(mat_plots)

            sections += f"""
<details class="cell-details" id="cell-r{row}c{col}">
  <summary>
    <span class="cell-summary-text">{summary_line}</span>
  </summary>
  <div class="cell-body">
    {gallery_parts}
  </div>
</details>"""

    return sections


def _build_plot_gallery(plots: list[dict]) -> str:
    """Build a 2-column grid of plot figures."""
    items = ""
    for p in plots:
        items += f"""
  <figure class="plot-figure">
    <img src="{p['plot_file']}" alt="{p['material_caption']}" loading="lazy">
    <figcaption>{p['caption']}</figcaption>
  </figure>"""
    return f'<div class="plot-gallery">{items}</div>'


def _js_click_to_open() -> str:
    """Return inline JavaScript that opens ``<details>`` on matrix-cell click."""
    return r"""
/* ── Click-to-open: matrix cell links → <details> ── */
(function() {
  document.querySelectorAll('.matrix-cell-link').forEach(function(link) {
    link.addEventListener('click', function(e) {
      var id = this.getAttribute('href').substring(1);
      var details = document.getElementById(id);
      if (details) {
        details.open = true;
        setTimeout(function() {
          details.scrollIntoView({behavior: 'smooth', block: 'start'});
        }, 50);
      }
    });
  });
})();
"""


# ── CSS ───────────────────────────────────────────────────────


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

/* ── Per-cell <details> (Issue 2, 5) ────────── */
.cell-details {
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 16px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border-left: 4px solid #aaa;
}
.cell-details summary {
  cursor: pointer;
  font-size: 1.05rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  user-select: none;
  color: #333;
}
.cell-details summary::-webkit-details-marker { display: none; }
.cell-details summary::before {
  content: "▸";
  display: inline-block;
  width: 16px;
  transition: transform 0.2s;
  font-size: 0.8rem;
  color: #888;
}
.cell-details[open] summary::before {
  transform: rotate(90deg);
}
.cell-summary-text { flex: 1; }
.cell-body { margin-top: 16px; }

/* ── Material sub-headings inside cell details ── */
.cell-material-heading {
  font-size: 0.9rem;
  font-weight: 600;
  color: #555;
  margin: 12px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eee;
}
.cell-material-heading:first-child { margin-top: 0; }

/* ── Matrix table ──────────────────────────── */
.matrix-container { margin-bottom: 0; overflow-x: auto; }
.matrix-container h4 { font-size: 0.95rem; margin-bottom: 8px; color: #555; }
.matrix {
  border-collapse: collapse;
  font-size: 0.85rem;
  width: 100%;
}
.matrix th, .matrix td {
  border: 1px solid #ddd;
  padding: 5px 8px;
  text-align: center;
  min-width: 32px;
  height: 30px;
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
.matrix td.measured {
  font-weight: 600;
}
.matrix td.measured a {
  color: #222;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.78rem;
}
.matrix td.measured a:hover {
  text-decoration: underline;
}

/* ── Plot gallery ──────────────────────────── */
.plot-gallery {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 8px;
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
  font-size: 0.78rem;
  color: #555;
  font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
  word-break: break-all;
}

/* ── No data fallback ───────────────────────── */
.no-data {
  text-align: center;
  color: #999;
  font-size: 1rem;
  padding: 40px;
}
"""
