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

# ── EC CA ────────────────────────────────────────────────────────────────────
from science_cli.plot.ca import (  # noqa: F401
    plot_ca_cottrell,
    plot_ca_decay,
)

# ── EC CV ────────────────────────────────────────────────────────────────────
from science_cli.plot.cv import (  # noqa: F401
    plot_cv_curve,
    plot_cv_overlay,
    plot_cv_with_peaks,
)

# ── EC EIS ───────────────────────────────────────────────────────────────────
from science_cli.plot.eis import (  # noqa: F401
    plot_eis_bode,
    plot_eis_fit,
    plot_eis_nyquist,
)

# ── Overlays ─────────────────────────────────────────────────────────────────
from science_cli.plot.overlays import (  # noqa: F401
    plot_overlay,
)
from science_cli.theme import apply_theme  # noqa: F401
