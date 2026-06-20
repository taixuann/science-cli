"""Theme registry: load, apply, list themes.

Single source of truth: config-template.yaml in the global config directory.
Theme definitions live under ``templates.<theme_name>`` and per-technique
plot defaults live under ``templates.plot_techniques.<technique>``.

This file is the Theme tier loader; it converts YAML → matplotlib rcParams.
The legacy ``theme/plot-theme/*.yaml`` and ``theme/plot-templates/*.yaml``
directories have been removed (consolidation v3.20).
"""

from __future__ import annotations

import matplotlib as mpl


def _load_templates_config() -> dict:
    """Load templates section from the global config (cached)."""
    from science_cli.core.config import load_global_config
    return load_global_config().get("templates", {}) or {}


def _load_theme(theme_name: str) -> dict:
    """Return the theme dict for *theme_name* from config-template.yaml."""
    templates = _load_templates_config()
    theme = templates.get(theme_name)
    if not theme:
        # Fall back to default theme so apply_theme() never silently no-ops.
        theme = templates.get("default", {}) or {}
    return theme


def list_themes() -> list[str]:
    """List all built-in theme names from config-template.yaml.

    Excludes non-theme keys (plot_labels, plot_techniques) so callers only
    see actual theme entries.
    """
    templates = _load_templates_config()
    non_theme_keys = {"plot_labels", "plot_techniques"}
    return sorted(k for k in templates if k not in non_theme_keys)


def get_theme(name: str) -> dict:
    """Return raw theme dict (used by overlays.py for color cycling)."""
    return _load_theme(name)


def theme_to_rcparams(name: str) -> dict:
    """Convert a theme dict to matplotlib rcParams.

    Reads from config-template.yaml (single source of truth — formerly
    theme/plot-theme/*.yaml). Returns a flat dict of matplotlib rcParams keys.
    """
    theme = _load_theme(name)
    if not theme:
        return {}

    rc: dict = {}

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


def apply_theme(name: str) -> None:
    """Apply theme rcParams to matplotlib's global rcParams dict."""
    rc = theme_to_rcparams(name)
    mpl.rcParams.update(rc)


def template_to_flags(technique: str) -> dict:
    """Load a technique template from config-template.yaml and return flags.

    Templates now live under ``templates.plot_techniques.<technique>`` in
    config-template.yaml. The extracted flag shape is preserved 1:1 with
    the previous plot-templates/*.yaml readers (plot_type, defaults.*,
    axes.{xlabel,ylabel}).
    """
    templates = _load_templates_config()
    data = templates.get("plot_techniques", {}).get(technique)
    if not data:
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
    axes = data.get("axes", {})
    for key in ("xlabel", "ylabel"):
        val = axes.get(key)
        if val:
            flags[key] = str(val)
    return flags