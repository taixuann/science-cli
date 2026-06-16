"""science-afm: AFM/SPM image analysis module.

Provides loading, visualization, and analysis of atomic force microscopy data:
  - File loading: Gwyddion (.gwy), Bruker (.spm), Igor (.ibw), JPK (.jpk), STP (.stp), TOP (.top)
  - Analysis: Surface roughness (Ra, Rq, Rmax, Rsk, Rku), height histograms, line profiles, PSD
  - Plotting: Topography images, line profiles, height distributions, power spectra
"""

from .analyze import (
    compute_psd,
    compute_roughness,
    height_distribution,
    line_profile,
)
from .loader import list_channels, load_afm
from .models import AfmData

__all__ = [
    "AfmData",
    "load_afm",
    "list_channels",
    "compute_roughness",
    "height_distribution",
    "line_profile",
    "compute_psd",
]

from science_cli.core.technique import ColumnMap

COLUMN_MAPS: dict[str, ColumnMap] = {
    "afm-gwy": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
    "afm-spm": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
    "afm-ibw": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
    "afm-jpk": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
    "afm-stp": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
    "afm-top": ColumnMap(
        x="", y="",
        x_label="Position (nm)", y_label="Height (nm)",
        x_aliases=[], y_aliases=[],
    ),
}

ANALYZERS: dict[str, callable] = {}

PLOT_PRESETS: dict[str, dict] = {
    "afm-gwy": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-spm": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-ibw": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-jpk": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-stp": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
    "afm-top": {"type": "image", "cmap": "viridis", "xlabel": "Position (nm)", "ylabel": "Position (nm)"},
}
