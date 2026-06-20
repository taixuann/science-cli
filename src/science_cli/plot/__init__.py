"""Plot engine — base class, utilities, and all technique-specific plotters."""

# ── AFM ──────────────────────────────────────────────────────────────────────
from science_cli.plot.afm import (  # noqa: F401
    plot_afm_height_distribution,
    plot_afm_image,
    plot_afm_line_profile,
    plot_afm_psd,
)

# ── Base ────────────────────────────────────────────────────────────────────
from science_cli.plot.base import (  # noqa: F401
    apply_figure_kw,
    create_figure,
    parse_figsize,
    plot_line,
    plot_scatter,
    save_figure,
    setup_backend,
)

# ── EC EIS ───────────────────────────────────────────────────────────────────
from science_cli.plot.eis import (  # noqa: F401
    plot_eis_bode,
    plot_eis_fit,
    plot_eis_nyquist,
)

from science_cli.theme import apply_theme  # noqa: F401
