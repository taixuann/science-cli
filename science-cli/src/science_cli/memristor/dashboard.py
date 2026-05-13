"""Self-contained interactive Plotly HTML dashboard for memristor IV curves.

Reads raw CSV data files directly (no SVG intermediates) and generates
a self-contained ``dashboard.html`` with interactive Plotly plots.
Works with ``file://`` protocol — no web server required.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Material colour palette ─────────────────────────────────

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
    """Assign a consistent colour to each material key."""
    if material_key not in _COLOR_INDEX:
        idx = len(_COLOR_INDEX) % len(_MATERIAL_COLORS)
        _COLOR_INDEX[material_key] = _MATERIAL_COLORS[idx]
    return _COLOR_INDEX[material_key]


# ── Number range formatting ─────────────────────────────────


def _format_number_ranges(numbers: list[int]) -> str:
    """Collapse consecutive numbers into compact ranges.

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


# ── Plotly figure generation ─────────────────────────────────


def _should_use_log_scale(current: np.ndarray) -> bool:
    """Determine if current should use log scale.

    Uses log scale if the absolute current spans more than 2 decades
    (ratio of max to min > 100), excluding values near zero.
    """
    abs_i = np.abs(current)
    pos = abs_i[abs_i > 1e-30]
    if len(pos) < 2:
        return False
    ratio = pos.max() / pos.min()
    return ratio > 100.0


def _create_iv_figure(
    voltage: np.ndarray,
    current: np.ndarray,
    title: str,
    plot_id: str,
    use_log: bool = False,
) -> str:
    """Generate a Plotly IV curve figure as an HTML div.

    Args:
        voltage: Voltage data array (V).
        current: Current data array (A).
        title: Plot title (e.g. ``"#01  |  0.82 V/s  |  0→+3.5V→0"``).
        plot_id: Unique DOM id for the plot div.
        use_log: If True, plot |current| on log scale.

    Returns:
        HTML string: a ``<div>`` with inline Plotly.newPlot() call.
        Does NOT include ``<script src="plotly.js">`` — that goes in the
        page ``<head>`` once.
    """
    import plotly.graph_objects as go

    display_current = np.abs(current) if use_log else current

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=voltage,
            y=display_current,
            mode="lines",
            line={"color": "#1f77b4", "width": 1.2},
            name=title,
            hovertemplate=(
                "V = %{x:.4f} V<br>I = %{y:.4e} A<extra></extra>"
            ),
        )
    )

    y_title = "|Current| (A)" if use_log else "Current (A)"
    fig.update_layout(
        title={"text": title, "font": {"size": 12, "family": "Arial, sans-serif"}},
        xaxis_title="Voltage (V)",
        yaxis_title=y_title,
        template="plotly_white",
        margin={"l": 60, "r": 20, "t": 40, "b": 50},
        height=350,
        hovermode="closest",
        dragmode="pan",
        showlegend=False,
        font={"family": "Arial, sans-serif", "size": 10},
    )

    if use_log:
        fig.update_yaxes(type="log")

    fig.update_xaxes(
        showline=True,
        linewidth=1,
        linecolor="black",
        mirror=True,
        ticks="inside",
    )
    fig.update_yaxes(
        showline=True,
        linewidth=1,
        linecolor="black",
        mirror=True,
        ticks="inside",
    )

    # Generate div-only HTML (no <html>, no plotly.js include)
    div_html = fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        div_id=plot_id,
        config={
            "displayModeBar": True,
            "modeBarButtonsToRemove": [
                "lasso2d",
                "select2d",
                "sendDataToCloud",
            ],
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": plot_id,
                "height": 600,
                "width": 800,
                "scale": 2,
            },
        },
    )
    return div_html


# ── Dashboard generation ─────────────────────────────────────


def generate_dashboard(
    config,
    results_dir: Path,
    output_path: str | Path,
) -> Path:
    """Generate a self-contained interactive Plotly HTML dashboard.

    Reads raw CSV data files directly (no intermediate SVGs) and
    generates Plotly IV curves embedded in a filterable, clickable
    matrix layout.

    Args:
        config: DeviceConfig instance loaded from devices.yaml.
        results_dir: Directory containing (or sibling to) raw data files.
            Raw files are resolved as ``results_dir.parent / fe.file``
            for each FileEntry.
        output_path: Where to write the HTML file.

    Returns:
        Path to the generated ``dashboard.html`` file.

    Raises:
        ValueError: If no IV files are found in the config.
    """
    from science_cli.memristor.plotting import (
        _extract_sweep_annotations,
        read_iv_csv,
    )
    from science_cli.memristor.device import extract_material_batch

    # Raw data files live in the step directory (parent of results/)
    data_dir = results_dir.parent

    # Collect all IV files from config
    plots: list[dict] = []
    for pt, fe in config.get_all_files("iv"):
        # Resolve raw CSV path
        csv_path = data_dir / fe.file
        if not csv_path.exists():
            logger.warning(f"Raw data file not found, skipping: {csv_path}")
            continue

        # Extract material+batch key
        mb = extract_material_batch(fe.file)
        if mb:
            mat_name, batch = mb
            mat_key = f"{mat_name}({batch})" if batch else mat_name
        else:
            mat_key = "unknown"

        # Determine display order
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
        if annotations.get("sweep_rate"):
            caption_parts.append(annotations["sweep_rate"])
        direction = annotations.get("direction")
        if direction:
            caption_parts.append(direction)
        else:
            caption_parts.append(fe.sweep_type or "uc")

        sweep_type = fe.sweep_type or "uc"
        plot_id = f"plot_r{pt.row}c{pt.col}_{mat_key.replace('-', '_').replace('(', '_').replace(')', '')}_{sweep_type}_{order:02d}"

        plots.append({
            "material_key": mat_key,
            "row": pt.row,
            "col": pt.col,
            "sweep_type": sweep_type,
            "order": order,
            "caption": "  |  ".join(caption_parts),
            "material_caption": f"r{pt.row}c{pt.col} | {mat_key} | {sweep_type}",
            "csv_path": csv_path,
            "plot_id": plot_id,
            "file_entry": fe,
            "point": pt,
        })

    if not plots:
        raise ValueError(
            "No IV data files found. Check that devices.yaml has IV entries "
            "and raw data files exist in the step directory."
        )

    # Read data and generate Plotly divs
    for p in plots:
        try:
            voltage, current, info = read_iv_csv(str(p["csv_path"]))
        except Exception as exc:
            logger.error(f"Error reading {p['csv_path'].name}: {exc}")
            p["plot_html"] = (
                f'<div class="plot-error" id="{p["plot_id"]}">'
                f"Error: {exc}</div>"
            )
            continue

        use_log = _should_use_log_scale(current)

        try:
            plot_html = _create_iv_figure(
                voltage=voltage,
                current=current,
                title=p["caption"],
                plot_id=p["plot_id"],
                use_log=use_log,
            )
            p["plot_html"] = plot_html
        except Exception as exc:
            logger.error(f"Error generating Plotly figure for {p['csv_path'].name}: {exc}")
            p["plot_html"] = (
                f'<div class="plot-error" id="{p["plot_id"]}">'
                f"Plotly error: {exc}</div>"
            )

    # Build data structures for layout
    material_groups: dict[str, list[dict]] = {}
    for p in plots:
        material_groups.setdefault(p["material_key"], []).append(p)

    cell_groups: dict[tuple[int, int], list[dict]] = {}
    for p in plots:
        cell_groups.setdefault((p["row"], p["col"]), []).append(p)

    all_rows = {p["row"] for p in plots}
    all_cols = {p["col"] for p in plots}
    if all_rows and all_cols:
        min_row, max_row = min(all_rows), max(all_rows)
        min_col, max_col = min(all_cols), max(all_cols)
    else:
        min_row = max_row = min_col = max_col = 0

    # Build HTML
    html = _build_html(
        config=config,
        material_groups=material_groups,
        cell_groups=cell_groups,
        total_plots=len(plots),
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
        plots=plots,
    )

    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written to {out}")
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
    plots: list[dict],
) -> str:
    """Assemble the full HTML document."""
    device_label = config.device.label or config.device.id or "Memristor Device"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    matrices_html = _build_matrices_row(
        material_groups=material_groups,
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )

    # Collect unique materials and sweep types for filter bar
    all_materials = sorted(material_groups.keys())
    all_sweep_types = sorted(set(p["sweep_type"] for p in plots))
    all_orders = sorted(set(p["order"] for p in plots))
    cycle_range = _format_number_ranges(all_orders) if all_orders else "—"

    filter_bar_html = _build_filter_bar(
        materials=all_materials,
        sweep_types=all_sweep_types,
        cycle_range=cycle_range,
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
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
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
{filter_bar_html}
{cell_details_html}
</main>

<script>
{_js_click_to_open()}
</script>
<script>
{_js_filters()}
</script>

</body>
</html>"""


def _build_filter_bar(
    materials: list[str],
    sweep_types: list[str],
    cycle_range: str,
) -> str:
    """Build the filter bar with dropdowns for material, sweep type, cycle range."""
    material_options = '<option value="all">All Materials</option>' + "".join(
        f'<option value="{m}">{m}</option>' for m in materials
    )
    sweep_options = '<option value="all">All Sweeps</option>' + "".join(
        f'<option value="{st}">{st}</option>' for st in sweep_types
    )

    return f"""
<div class="filter-bar" id="filter-bar">
  <div class="filter-group">
    <label for="filter-material">Material:</label>
    <select id="filter-material" onchange="applyFilters()">
      {material_options}
    </select>
  </div>
  <div class="filter-group">
    <label for="filter-sweep">Sweep:</label>
    <select id="filter-sweep" onchange="applyFilters()">
      {sweep_options}
    </select>
  </div>
  <div class="filter-group">
    <span class="filter-label">Cycles: {cycle_range}</span>
  </div>
  <div class="filter-group">
    <button class="filter-btn" onclick="expandAllCells()" title="Expand all cell details">+ Expand All</button>
    <button class="filter-btn" onclick="collapseAllCells()" title="Collapse all cell details">− Collapse All</button>
    <button class="filter-btn" onclick="resetFilters()" title="Reset all filters">↺ Reset</button>
  </div>
</div>"""


# ── Matrix row ───────────────────────────────────────────────


def _build_matrices_row(
    material_groups: dict[str, list[dict]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build a horizontal flex row of per-material matrix grids."""
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
    """Build an HTML table for one material's crossbar matrix.

    Cell links point to ``#cell-r{row}c{col}``. Cell text uses
    ``_format_number_ranges`` for compact display.
    """
    cell_plots: dict[tuple[int, int], list[int]] = {}
    for p in plots:
        cell_plots.setdefault((p["row"], p["col"]), []).append(p["order"])

    rows_html = ""
    for r in range(max_row, min_row - 1, -1):
        cells = ""
        for c in range(min_col, max_col + 1):
            pos = (r, c)
            orders = cell_plots.get(pos, [])
            if orders:
                sorted_orders = sorted(set(orders))
                range_text = _format_number_ranges(sorted_orders)
                anchor = f"cell-r{r}c{c}"
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


# ── Cell details ──────────────────────────────────────────────


def _build_cell_details(
    cell_groups: dict[tuple[int, int], list[dict]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> str:
    """Build ``<details>`` elements per cell position with Plotly figures."""
    if not cell_groups:
        return '<p class="no-data">No data cells found.</p>'

    sections = ""
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            cell_plots = cell_groups.get((row, col))
            if not cell_plots:
                continue

            materials_in_cell = sorted(set(p["material_key"] for p in cell_plots))
            orders = sorted(set(p["order"] for p in cell_plots))
            n_files = len(orders)
            range_text = _format_number_ranges(orders)
            n_materials = len(materials_in_cell)

            t_label = row + 1
            b_label = col + 1
            mat_summary = ", ".join(materials_in_cell)

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

            gallery_parts = ""
            for mat_key in materials_in_cell:
                mat_plots = [
                    p for p in cell_plots if p["material_key"] == mat_key
                ]
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
    """Build a 2-column grid of Plotly figure containers."""
    items = ""
    for p in plots:
        plot_html = p.get("plot_html", "")
        if not plot_html:
            plot_html = (
                f'<div class="plot-error" id="{p["plot_id"]}">'
                f"No data available</div>"
            )

        # Wrap each plot div in a filterable container
        items += f"""
  <div class="plot-figure"
       data-material="{_escape_attr(p['material_key'])}"
       data-sweep="{p['sweep_type']}"
       data-cycle="{p['order']}"
       data-cell="r{p['row']}c{p['col']}">
    <div class="plotly-wrapper" id="wrapper-{p['plot_id']}">
      {plot_html}
    </div>
    <figcaption>{p['caption']}</figcaption>
  </div>"""

    return f'<div class="plot-gallery">{items}</div>'


def _escape_attr(value: str) -> str:
    """Escape a string for safe use in HTML attributes."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


# ── JavaScript ─────────────────────────────────────────────────


def _js_click_to_open() -> str:
    """Return inline JavaScript that opens ``<details>`` on matrix-cell click."""
    return r"""
/* ── Click-to-open: matrix cell links → <details> ── */
(function() {
  document.querySelectorAll('.matrix-cell-link').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      var id = this.getAttribute('href').substring(1);
      var details = document.getElementById(id);
      if (details) {
        details.open = true;
        setTimeout(function() {
          details.scrollIntoView({behavior: 'smooth', block: 'start'});
        }, 100);
      }
    });
  });
})();
"""


def _js_filters() -> str:
    """Return inline JavaScript for the filter bar."""
    return r"""
/* ── Filter bar ── */
function applyFilters() {
  var material = document.getElementById('filter-material').value;
  var sweep = document.getElementById('filter-sweep').value;

  document.querySelectorAll('.plot-figure').forEach(function(el) {
    var elMat = el.getAttribute('data-material');
    var elSweep = el.getAttribute('data-sweep');

    var show = true;
    if (material !== 'all' && elMat !== material) show = false;
    if (sweep !== 'all' && elSweep !== sweep) show = false;

    el.style.display = show ? '' : 'none';
  });

  // Hide empty material headings and cell details
  document.querySelectorAll('.cell-details').forEach(function(details) {
    var visible = details.querySelectorAll('.plot-figure[style*="display: none"]').length;
    var total = details.querySelectorAll('.plot-figure').length;
    if (visible === total && total > 0) {
      details.style.display = 'none';
    } else {
      details.style.display = '';
    }
  });

  document.querySelectorAll('.cell-material-heading').forEach(function(h5) {
    var parent = h5.parentElement;
    var nextEl = h5.nextElementSibling;
    var hasVisible = false;
    while (nextEl) {
      if (nextEl.classList.contains('cell-material-heading')) break;
      var figs = nextEl.querySelectorAll ? nextEl.querySelectorAll('.plot-figure') : [];
      for (var i = 0; i < figs.length; i++) {
        if (figs[i].style.display !== 'none') { hasVisible = true; break; }
      }
      if (hasVisible) break;
      nextEl = nextEl.nextElementSibling;
    }
    h5.style.display = hasVisible ? '' : 'none';
  });
}

function expandAllCells() {
  document.querySelectorAll('.cell-details').forEach(function(el) {
    el.open = true;
  });
}

function collapseAllCells() {
  document.querySelectorAll('.cell-details').forEach(function(el) {
    el.open = false;
  });
}

function resetFilters() {
  document.getElementById('filter-material').value = 'all';
  document.getElementById('filter-sweep').value = 'all';
  applyFilters();
}

/* ── Auto-resize Plotly plots on details open ── */
(function() {
  document.querySelectorAll('.cell-details').forEach(function(details) {
    details.addEventListener('toggle', function() {
      if (details.open) {
        setTimeout(function() {
          var wrappers = details.querySelectorAll('.plotly-wrapper');
          wrappers.forEach(function(w) {
            var gd = w.firstElementChild;
            if (gd && gd.id && typeof Plotly !== 'undefined') {
              try { Plotly.Plots.resize(gd); } catch(e) {}
            }
          });
        }, 150);
      }
    });
  });
})();
"""


# ── CSS ───────────────────────────────────────────────────────


def css() -> str:
    """Return the CSS stylesheet for the Plotly dashboard."""
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

/* ── Filter bar ────────────────────────────── */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  background: #fff;
  border-radius: 8px;
  padding: 12px 24px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #555;
}
.filter-group select {
  padding: 4px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.85rem;
  background: #fff;
  cursor: pointer;
}
.filter-label {
  font-size: 0.85rem;
  color: #888;
  font-weight: 500;
}
.filter-btn {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #f8f8f8;
  font-size: 0.78rem;
  color: #555;
  cursor: pointer;
  transition: background 0.15s;
}
.filter-btn:hover {
  background: #e8e8e8;
}

/* ── Matrix row (all materials, top of page) ── */
.matrix-row {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 12px;
  margin-bottom: 8px;
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

/* ── Per-cell <details> ─────────────────────── */
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
.plot-figure .plotly-wrapper {
  width: 100%;
  min-height: 300px;
}
.plot-figure .plotly-wrapper .js-plotly-plot,
.plot-figure .plotly-wrapper .plot-container {
  width: 100% !important;
}
.plot-figure figcaption {
  margin-top: 8px;
  font-size: 0.78rem;
  color: #555;
  font-family: "SF Mono", "Menlo", "Monaco", "Courier New", monospace;
  word-break: break-all;
}

/* ── Plot error fallback ────────────────────── */
.plot-error {
  padding: 20px;
  color: #c00;
  font-size: 0.85rem;
  background: #fff5f5;
  border: 1px solid #fcc;
  border-radius: 4px;
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── No data fallback ───────────────────────── */
.no-data {
  text-align: center;
  color: #999;
  font-size: 1rem;
  padding: 40px;
}
"""
