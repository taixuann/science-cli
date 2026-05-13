"""Extension discovery via Python entry points.

Extensions register with group "science_cli.extensions" and provide:
    - register(registry: ExtensionRegistry) -> None

Also discovers techniques and devices from config files:
    - Global:  ~/.config/science-cli/config.yaml
    - Per-project: <project_root>/sci-config.yaml
"""

from importlib.metadata import entry_points
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnMap:
    """Maps standard column roles to file-specific column names.

    Each extension technique registers one ColumnMap that tells the core
    plot/analyze commands what columns to expect and how to label axes.

    The x/y fields hold the *preferred* column name; _resolve_xy_columns()
    in plot.py will try these first, then fall back to fuzzy-matching
    against common aliases for the technique.
    """

    x: str = ""  # Preferred column name for X-axis
    y: str = ""  # Preferred column name for Y-axis
    x_label: str = ""  # Default axis label for X
    y_label: str = ""  # Default axis label for Y
    # Additional columns keyed by role (e.g. "resistance", "frequency", "z_real", "z_imag")
    extras: dict = field(default_factory=dict)

    # Technique-specific alias lists that _resolve_xy_columns() falls back on
    # when the preferred columns are not found in the DataFrame.
    x_aliases: list[str] = field(default_factory=list)
    y_aliases: list[str] = field(default_factory=list)

    def resolve(
        self, columns: list[str]
    ) -> tuple[str, str, str, str, dict[str, str]]:
        """Resolve x, y, x_label, y_label and extras from available columns.

        Returns: (xcol, ycol, xlabel, ylabel, resolved_extras)
        """
        xcol = _find_column(self.x, self.x_aliases, columns)
        ycol = _find_column(self.y, self.y_aliases, columns)
        xlabel = self.x_label or xcol or "X"
        ylabel = self.y_label or ycol or "Y"
        resolved_extras: dict[str, str] = {}
        for role, preferred in self.extras.items():
            found = _find_column(preferred, [], columns)
            if found:
                resolved_extras[role] = found
        return xcol, ycol, xlabel, ylabel, resolved_extras


def _find_column(
    preferred: str, aliases: list[str], columns: list[str]
) -> str:
    """Find the first matching column name from preferred + aliases."""
    candidates = [preferred] + list(aliases) if preferred else list(aliases)
    for c in candidates:
        if c in columns:
            return c
    return ""


@dataclass
class TechniqueDef:
    name: str
    label: str
    patterns: list[str]
    description: str = ""


@dataclass
class ExtensionRegistry:
    techniques: dict[str, TechniqueDef] = field(default_factory=dict)
    analyzers: dict[str, callable] = field(default_factory=dict)
    plot_presets: dict[str, dict] = field(default_factory=dict)
    data_loaders: dict[str, callable] = field(default_factory=dict)
    column_maps: dict[str, ColumnMap] = field(default_factory=dict)
    name: str = ""


_loaded = False
_registry = ExtensionRegistry()


def _discover_config_techniques(registry: ExtensionRegistry) -> None:
    """Register techniques and device info from config files.

    Reads techniques section from merged config and registers any
    techniques that aren't already in the registry.
    """
    try:
        from science_cli.core.config import get_merged_config
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        project_root = proj if proj else None
        config = get_merged_config(project_root)
    except (ImportError, Exception):
        return

    techniques_config = config.get("techniques", {})
    for tech_name, tech_config in techniques_config.items():
        if tech_name in registry.techniques:
            continue  # Don't override extension-registered techniques

        label = tech_config.get("label", tech_name.replace("-", " ").title())
        patterns = tech_config.get("patterns", [])
        description = tech_config.get("description", "")

        registry.techniques[tech_name] = TechniqueDef(
            name=tech_name,
            label=label,
            patterns=patterns,
            description=description,
        )


def discover_extensions() -> ExtensionRegistry:
    global _loaded, _registry
    if _loaded:
        return _registry
    _loaded = True

    # 1. Load Python entry-point extensions
    eps = entry_points(group="science_cli.extensions")
    for ep in eps:
        try:
            ext = ep.load()
            if callable(ext):
                ext(_registry)
        except Exception:
            pass

    # 2. Load config-file techniques/devices
    _discover_config_techniques(_registry)

    return _registry


def get_registry() -> ExtensionRegistry:
    return _registry
