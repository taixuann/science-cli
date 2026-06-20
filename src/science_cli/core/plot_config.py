"""Per-study plot configuration resolver.

Merges three layers of plot parameters (lowest → highest priority):
    1. Theme defaults from ``config-template.yaml`` (``rcparams`` block)
    2. Study-level plot config from ``config-studies.yaml``
    3. Device-level plot overrides from ``device_overrides.<device>.plot``

Returns a flat dict with dot-separated keys suitable for matplotlib rcParams
and per-series annotation styling::

    {
        "figure.figsize": [3.46, 2.75],
        "axes.xscale": "log",
        "series.hrs.color": "#CC0000",
        "annotations.lrs.text": "LRS",
    }
"""

from __future__ import annotations

import json
from typing import Any

from science_cli.core.config import load_global_config


# ── Helpers ─────────────────────────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge two dicts.

    Leaf values in *override* replace leaf values in *base*.
    List values in *override* fully replace (not append) list values in *base*.
    """
    result: dict = {}
    all_keys = set(base) | set(override)
    for key in all_keys:
        if key in override:
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(override[key], dict)
            ):
                result[key] = _deep_merge(base[key], override[key])
            else:
                result[key] = override[key]
        else:
            result[key] = base[key]
    return result


def _flatten_dict(d: dict, parent_key: str = "") -> dict:
    """Flatten a nested dict to dot-separated keys.

    Examples::

        {"series": {"hrs": {"color": "red"}}}
        → {"series.hrs.color": "red"}

        {"figure": {"figsize": [3.46, 2.75]}}
        → {"figure.figsize": [3.46, 2.75]}
    """
    items: list[tuple[str, Any]] = []
    for key, value in d.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(_flatten_dict(value, new_key).items())
        else:
            items.append((new_key, value))
    return dict(items)


# ── Core resolver ───────────────────────────────────────────────────────


def resolve_plot_config(
    study_name: str,
    device_type: str | None = None,
    active_theme: str = "publication-nature",
) -> dict:
    """Merge theme defaults + study plot config + device plot overrides.

    Priority (lowest → highest):
        1. Theme defaults from ``config-template.yaml`` (``rcparams`` block)
        2. Study-level plot config from ``config-studies.yaml``
        3. Device-level plot overrides from ``device_overrides.<device>.plot``

    Args:
        study_name: Qualified study name, e.g. ``"pulse:pulse-endurance"``.
        device_type: Optional device type slug for overrides
            (e.g. ``"volatile-memristor"``).
        active_theme: Theme name for theme defaults.  Defaults to
            ``"publication-nature"``.

    Returns:
        Flat dict with dot-separated keys.  Keys from higher-priority layers
        win.  List values fully replace (not append).  Empty dicts produce
        no keys.  If the study is not found, returns theme defaults only.
    """
    # ── Layer 1: theme defaults ──────────────────────────────────────
    cfg = load_global_config()
    templates = cfg.get("templates", {})
    theme_cfg = templates.get(active_theme, {})
    rcparams: dict = theme_cfg.get("rcparams", {})

    # ── Layer 2: study-level plot config ─────────────────────────────
    from science_cli.core.studies import parse_study_name

    technique, study_key = parse_study_name(study_name)
    studies_dict = cfg.get("studies", {})
    study_cfg: dict = {}
    if technique in studies_dict and study_key in studies_dict[technique]:
        study_cfg = studies_dict[technique][study_key]

    study_plot: dict = study_cfg.get("plot", {})

    # ── Layer 3: device-level plot overrides ─────────────────────────
    device_plot: dict = {}
    if device_type:
        device_overrides = study_cfg.get("device_overrides", {})
        device_block = device_overrides.get(device_type, {})
        device_plot = device_block.get("plot", {})

    # ── Deep merge (theme < study < device) ─────────────────────────
    merged = _deep_merge(rcparams, study_plot)
    merged = _deep_merge(merged, device_plot)

    # ── Flatten and return ──────────────────────────────────────────
    return _flatten_dict(merged)


# ── CLI test ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Quick smoke test — prints merged config for pulse-endurance with
    # volatile-memristor overrides (device series.hrs.color = "#2176AE"
    # should override study series.hrs.color = "#CC0000").
    cfg = resolve_plot_config(
        "pulse:pulse-endurance",
        device_type="volatile-memristor",
    )
    print(json.dumps(cfg, indent=2))
