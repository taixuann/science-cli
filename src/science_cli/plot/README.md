# Plot Engine (`src/science_cli/plot/`)

## Architecture

```
plot/
├── base.py          ← ** CANONICAL ** — all figure/save logic originates here
├── __init__.py      ← Re-exports base.py functions + additional utilities
├── ca.py            ← Chronoamperometry (I vs t)
├── cv.py            ← Cyclic voltammetry (I vs E)
├── eis.py           ← EIS (Nyquist: -Z'' vs Z'; Bode: |Z| + phase vs f)
├── eis_circuits.py  ← Circuit fitting models (RRC, RQR, RsRQW, RsRCW)
└── overlays.py      ← Multi-file overlay plotting
```

## Canonical Rule

**`base.py` is canonical.** All figure creation, theme application, and save logic
should be defined in `base.py`. The `__init__.py` module re-exports these for
convenience but should NOT contain independent implementations.

If you find duplicated logic between `__init__.py` and `base.py`, the truth is in
`base.py` — `__init__.py` should be a thin re-export layer.

## How to Add a New Plot Module

1. Create `plot/<technique>.py`
2. Define a function `plot_<technique>(fig, ax, df, flags, **extra)` that:
   - Takes a matplotlib Figure + Axes
   - Takes a pandas DataFrame + keyword flags dict
   - Draws on `ax`
   - Returns nothing (or a result dict)
3. Import from `base.py` for `create_figure`, `apply_figure_kw`, `save_figure`
4. Add dispatch logic in `cli/commands/plot.py` to call the new function

### Example Template

```python
"""<Technique> plot module."""

import numpy as np
from science_cli.plot.base import apply_figure_kw


def plot_my_technique(fig, ax, df, flags, xcol="", ycol=""):
    """Plot description."""
    x = df[xcol].values if xcol in df.columns else df.iloc[:, 0].values
    y = df[ycol].values if ycol in df.columns else df.iloc[:, 1].values

    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    ax.plot(x, y, linewidth=flags.get("linewidth", 1.5),
            marker=flags.get("marker", ""))

    apply_figure_kw(ax, flags)
    return {"x": x, "y": y}
```

## Key Functions (from base.py)

| Function | Purpose |
|----------|---------|
| `create_figure(theme, figsize)` | Create fig/ax with theme applied |
| `apply_figure_kw(ax, flags)` | Apply labels, limits, scales, grid, legend |
| `save_figure(fig, output_dir, stem, flags)` | Save to file (PDF/PNG) |
| `parse_figsize(flags)` | Parse size string → tuple |
| `setup_backend(interactive)` | Set matplotlib backend |

## Dependencies

- matplotlib, numpy — core plotting
- science_cli.theme — theme application via rcParams
