"""Theme registry: load, apply, list themes.

Three-tier LabPlot-inspired system:
  Theme       → global colors, fonts, grid, axis style
  Template    → per-object curve/plot presets
  PlotTemplate → full figure blueprints

This file handles the Theme tier. Templates live in theme/plot-templates/.
"""

from pathlib import Path

import matplotlib as mpl

_THEME_DIR = Path(__file__).parent / "plot-theme"
_THEME_CACHE: dict[str, dict] = {}

BUILTIN_THEMES = [
    "default",
    "tufte",
    "dark",
    "publication-acs",
    "publication-nature",
    "poster",
]


def _load_yaml_theme(name: str) -> dict:
    path = _THEME_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    import yaml
    with open(path) as f:
        return yaml.safe_load(f) or {}


def list_themes() -> list[str]:
    themes = []
    for p in _THEME_DIR.glob("*.yaml"):
        themes.append(p.stem)
    return sorted(themes)


def get_theme(name: str) -> dict:
    if name in _THEME_CACHE:
        return _THEME_CACHE[name]
    theme = _load_yaml_theme(name)
    if not theme:
        theme = _load_yaml_theme("default") or {}
    _THEME_CACHE[name] = theme
    return theme


def theme_to_rcparams(name: str) -> dict:
    theme = get_theme(name)
    rc = {}

    figure = theme.get("figure", {})
    rc["figure.facecolor"] = figure.get("facecolor", "white")
    rc["figure.figsize"] = figure.get("figsize", [6.4, 4.8])
    rc["figure.dpi"] = figure.get("dpi", 300)

    axes = theme.get("axes", {})
    rc["axes.facecolor"] = axes.get("facecolor", "white")
    rc["axes.edgecolor"] = axes.get("edgecolor", "black")
    rc["axes.labelcolor"] = axes.get("labelcolor", "black")
    rc["axes.titlecolor"] = axes.get("titlecolor", "black")
    rc["axes.grid"] = axes.get("grid", False)
    rc["axes.linewidth"] = axes.get("linewidth", 1.0)
    rc["axes.spines.top"] = axes.get("spines_top", True)
    rc["axes.spines.right"] = axes.get("spines_right", True)

    grid = theme.get("grid", {})
    rc["grid.color"] = grid.get("color", "#e0e0e0")
    rc["grid.alpha"] = grid.get("alpha", 0.3)
    rc["grid.linestyle"] = grid.get("linestyle", "-")

    ticks = theme.get("ticks", {})
    rc["xtick.color"] = ticks.get("color", "black")
    rc["ytick.color"] = ticks.get("color", "black")
    rc["xtick.direction"] = ticks.get("direction", "in")
    rc["ytick.direction"] = ticks.get("direction", "in")
    rc["xtick.major.width"] = ticks.get("major_width", 0.8)
    rc["ytick.major.width"] = ticks.get("major_width", 0.8)

    font = theme.get("font", {})
    rc["font.family"] = font.get("family", "sans-serif")
    rc["font.size"] = font.get("size", 10)
    rc["axes.labelsize"] = font.get("axes_labelsize", 12)
    rc["axes.titlesize"] = font.get("axes_titlesize", 14)
    rc["xtick.labelsize"] = font.get("tick_labelsize", 10)
    rc["ytick.labelsize"] = font.get("tick_labelsize", 10)
    rc["legend.fontsize"] = font.get("legend_size", 10)

    legend = theme.get("legend", {})
    rc["legend.frameon"] = legend.get("frameon", True)
    rc["legend.fancybox"] = legend.get("fancybox", True)
    rc["legend.loc"] = legend.get("loc", "best")

    lines = theme.get("lines", {})
    rc["lines.linewidth"] = lines.get("linewidth", 1.5)
    rc["lines.markersize"] = lines.get("markersize", 6)
    rc["lines.linestyle"] = lines.get("linestyle", "-")

    colors = theme.get("colors", {})
    prop_cycle = colors.get("prop_cycle", [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    ])
    rc["axes.prop_cycle"] = mpl.cycler(color=prop_cycle)

    savefig = theme.get("savefig", {})
    rc["savefig.dpi"] = savefig.get("dpi", 300)
    rc["savefig.bbox"] = savefig.get("bbox", "tight")
    rc["savefig.pad_inches"] = savefig.get("pad_inches", 0.1)
    rc["savefig.format"] = savefig.get("format", "pdf")

    pdf = theme.get("pdf", {})
    ft = pdf.get("fonttype")
    if ft is not None:
        rc["pdf.fonttype"] = ft

    return rc


def apply_theme(name: str):
    rc = theme_to_rcparams(name)
    mpl.rcParams.update(rc)


def template_to_flags(technique: str) -> dict:
    """Load a technique template YAML and return a flag dict.

    Templates live in theme/plot-templates/ and define plot_type, defaults
    (linewidth, linestyle, marker, markersize), and labels (xlabel, ylabel).
    """
    templates_dir = Path(__file__).parent / "plot-templates"
    path = templates_dir / f"{technique}.yaml"
    if not path.exists():
        return {}
    import yaml
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}
    flags: dict[str, str] = {}
    plot_type = data.get("plot_type", "")
    if plot_type:
        flags["type"] = str(plot_type)
    defaults = data.get("defaults", {})
    for key in ("linewidth", "linestyle", "marker", "markersize"):
        val = defaults.get(key)
        if val is not None:
            flags[key] = str(val)
    labels = data.get("axes", {})
    for key in ("xlabel", "ylabel"):
        val = labels.get(key)
        if val:
            flags[key] = str(val)
    return flags
