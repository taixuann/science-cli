"""Extension discovery via Python entry points.

Extensions register with group "science_cli.extensions" and provide:
    - register(registry: ExtensionRegistry) -> None
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


def discover_extensions() -> ExtensionRegistry:
    global _loaded, _registry
    if _loaded:
        return _registry
    _loaded = True

    eps = entry_points(group="science_cli.extensions")
    for ep in eps:
        try:
            ext = ep.load()
            ext(_registry)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load extension '{ep.name}': {e}")

    return _registry


def get_registry() -> ExtensionRegistry:
    return _registry
