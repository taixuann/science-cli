"""Per-study plot configuration resolver.

Merges four layers of plot parameters (lowest → highest priority):
    1. Theme defaults from ``config-template.yaml`` (``rcparams`` block)
    2. Common study plot config (``plot.common`` or legacy flat ``plot`` block)
    3. Scale-specific config (``plot.<scale>`` block, e.g. ``plot.linear``/``plot.log``)
    4. Device-level plot overrides from ``device_overrides.<device>.plot``

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
    scale: str | None = None,
) -> dict:
    """Merge theme defaults + study plot config + device plot overrides.

    Priority (lowest → highest):
        1. Theme defaults from ``config-template.yaml`` (``rcparams`` block)
        2. ``plot.common`` (or legacy flat ``plot`` block)
        3. ``plot.<scale>`` block (e.g. ``plot.linear`` or ``plot.log``)
        4. Device-level plot overrides from ``device_overrides.<device>.plot``

    When the study's ``plot`` block contains a ``common`` sub-key, the
    ``<scale>`` sub-block (if specified) is merged on top of ``common``.
    If ``common`` is not present, the entire ``plot`` block is treated as
    the common config (legacy fallback) and scale blocks are ignored.

    Args:
        study_name: Qualified study name, e.g. ``"pulse:pulse-endurance"``.
        device_type: Optional device type slug for overrides
            (e.g. ``"volatile-memristor"``).
        active_theme: Theme name for theme defaults.  Defaults to
            ``"publication-nature"``.
        scale: Optional scale block name (e.g. ``"linear"`` or ``"log"``).
            When present, ``plot.<scale>`` is merged after ``plot.common``.

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

    # ── Resolve common + scale blocks ────────────────────────────────
    if "common" in study_plot:
        common_cfg = study_plot.get("common", {})
        scale_cfg = study_plot.get(scale, {}) if scale else {}
    else:
        common_cfg = study_plot  # legacy fallback — entire plot block
        scale_cfg = {}

    # ── Deep merge (theme < common < scale < device) ─────────────────
    merged = _deep_merge(rcparams, common_cfg)
    merged = _deep_merge(merged, scale_cfg)
    merged = _deep_merge(merged, device_plot)

    # ── Flatten and return ──────────────────────────────────────────
    return _flatten_dict(merged)


def study_has_scale_blocks(study_name: str) -> tuple[bool, bool]:
    """Check if a study defines ``plot.linear`` and/or ``plot.log`` blocks.

    Returns
        ``(has_linear, has_log)``.  Returns ``(False, False)`` for legacy
        studies that use a flat ``plot`` block (no ``common`` sub-key).
    """
    cfg = load_global_config()
    from science_cli.core.studies import parse_study_name

    technique, study_key = parse_study_name(study_name)
    study_plot = (
        cfg.get("studies", {})
        .get(technique, {})
        .get(study_key, {})
        .get("plot", {})
    )
    if "common" not in study_plot:
        return False, False  # legacy flat block
    return ("linear" in study_plot, "log" in study_plot)


def resolve_step_plot_overrides(
    study_name: str,
    filepath: str | Path | None = None,
    step_name: str | None = None,
) -> dict:
    """Read **step-level** plot overrides from ``protocol.yaml``.

    Allows per-step configuration to override plot parameters like
    ``xlim``, ``ylim``, ``yscale``, etc. by adding a ``plot_overrides``
    key to the step's ``metadata`` in ``protocol.yaml``::

        steps:
          - name: endurance-run-1
            technique: mem-endurance
            metadata:
              v_set_v: 2.0
              plot_overrides:
                axes:
                  xlim: [1, 10000]
                  ylim: [100, 10000000]

    Resolution order:
        1. Walk up from *filepath* to find ``protocol.yaml``
        2. Match *step_name* or auto-detect from *filepath* parent dir
        3. Extract ``metadata.plot_overrides``
        4. Flatten to dot-separated keys

    Returns:
        Flat dict with dot-separated override keys.  Empty dict if no
        overrides are found.
    """
    from pathlib import Path

    fp = Path(filepath) if filepath else None

    # ── Walk up to find protocol.yaml ──────────────────────────────────
    protocol_yaml: Path | None = None
    search_dir = (fp.parent if fp else None) or Path.cwd()
    for parent in [search_dir] + list(search_dir.parents):
        candidate = parent / "protocol.yaml"
        if candidate.exists():
            protocol_yaml = candidate
            break

    if protocol_yaml is None:
        return {}

    # ── Resolve step name ──────────────────────────────────────────────
    if step_name is None and fp:
        step_name = fp.parent.name

    if not step_name:
        return {}

    # ── Read step metadata ─────────────────────────────────────────────
    from science_cli.core.protocol import read_step_metadata

    project_root = protocol_yaml.parent
    meta = read_step_metadata(project_root, step_name)
    overrides = meta.get("plot_overrides", {})
    if not overrides or not isinstance(overrides, dict):
        return {}

    return _flatten_dict(overrides)


# ── Analyze config resolver ────────────────────────────────────────────────


def resolve_analysis_plot_config(
    study_name: str,
    function_name: str,
    device_type: str | None = None,
    filepath: str | None = None,
) -> dict:
    """Resolve plot config for an **analyze** function.

    Resolution order (lowest → highest priority):
        1. ``config-studies.yaml`` → ``interactive.analyze.<function>.plot``
        2. ``protocol.yaml`` → per-file ``analyze:<function>:`` section
        3. (reserved) device-level overrides

    Args:
        study_name: Qualified study name, e.g. ``"pulse:pulse-endurance"``.
        function_name: Analyze function key, e.g. ``"ratio_histogram"``.
        device_type: Optional device type slug (reserved for future use).
        filepath: Optional file path for per-file protocol overrides.

    Returns:
        Flat dict with dot-separated keys. Returns empty dict if the
        function has no config — callers fall back to hardcoded defaults.
    """
    cfg = load_global_config()
    from science_cli.core.studies import parse_study_name

    technique, study_key = parse_study_name(study_name)
    studies_dict = cfg.get("studies", {})
    study_cfg: dict = {}
    if technique in studies_dict and study_key in studies_dict[technique]:
        study_cfg = studies_dict[technique][study_key]

    # Navigate to interactive.analyze.<function>.plot
    interactive = study_cfg.get("interactive", {})
    analyze_menu = interactive.get("analyze", {})
    func_entry = analyze_menu.get(function_name, {})
    func_plot = func_entry.get("plot", {}) if isinstance(func_entry, dict) else {}

    # Per-file overrides from protocol.yaml
    proto_cfg: dict = {}
    if filepath:
        try:
            from science_cli.core.protocol import resolve_file_analyze_config

            proto_cfg = resolve_file_analyze_config(filepath, function_name)
        except ImportError:
            pass  # safe fallback

    # Deep merge (study config ← protocol overrides)
    merged = _deep_merge(func_plot, proto_cfg)
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
