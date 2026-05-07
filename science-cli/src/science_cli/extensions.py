"""Extension discovery via Python entry points.

Extensions register with group "science_cli.extensions" and provide:
    - register(registry: ExtensionRegistry) -> None
"""

from importlib.metadata import entry_points
from dataclasses import dataclass, field


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
