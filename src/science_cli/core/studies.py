"""Study domain model — detection, resolution, and rendering.

Pure domain model — no circular imports with core/config.py.
Uses lazy loaders to pull data from the global config at call time.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _studies_dict() -> dict:
    """Lazy load studies dict from global config (avoids circular import)."""
    from science_cli.core.config import load_global_config
    return load_global_config().get("studies", {})


def _device_types_dict() -> dict:
    """Lazy load device_types dict from global config (avoids circular import)."""
    from science_cli.core.config import load_global_config
    return load_global_config().get("device_types", {})


def _legacy_dict() -> dict:
    """Lazy load legacy_to_study dict from global config (avoids circular import)."""
    from science_cli.core.config import load_global_config
    return load_global_config().get("legacy_to_study", {})


@dataclass
class Study:
    """Represents a named study with detection patterns and instrument configs."""

    name: str
    technique: str
    label: str
    patterns: list[str] = field(default_factory=list)
    legacy_codes: list[str] = field(default_factory=list)
    instruments: dict[str, Any] = field(default_factory=dict)


def parse_study_name(study_name: str) -> tuple[str, str]:
    """Parse a qualified study name into (technique, name).

    Args:
        study_name: Study name in ``technique:study-name`` format.

    Returns:
        Tuple of (technique, study_name). If no colon, technique is empty string.
    """
    if ":" in study_name:
        parts = study_name.split(":", 1)
        return (parts[0], parts[1])
    return ("", study_name)


# ── Detection ──────────────────────────────────────────────────────────


def detect_study_from_filename(
    filename: str, studies_dict: dict | None = None
) -> str | None:
    """Detect study from filename using substring matching (case-insensitive).

    Checks patterns from all techniques, longest patterns first (most specific
    has highest priority).

    Args:
        filename: The filename to check (e.g. ``"150626_test_iv-sweep_001.csv"``).
        studies_dict: Optional studies dict override. Uses ``_STUDIES`` if None.

    Returns:
        Study name in ``"technique:study-name"`` format, or None if no match.
    """
    studies = studies_dict if studies_dict is not None else _studies_dict()

    entries: list[tuple[str, str, str]] = []
    for technique, technique_studies in studies.items():
        for study_name, study_cfg in technique_studies.items():
            for pattern in study_cfg.get("patterns", []):
                entries.append((technique, study_name, pattern))

    entries.sort(key=lambda x: len(x[2]), reverse=True)

    filename_lower = filename.lower()
    for technique, study_name, pattern in entries:
        if pattern.lower() in filename_lower:
            return f"{technique}:{study_name}"

    return None


# ── Resolution ─────────────────────────────────────────────────────────


def resolve_technique_from_study(study_name: str) -> str:
    """Extract the technique prefix from a qualified study name.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.

    Returns:
        Technique prefix (e.g. ``"iv"``, ``"pulse"``).
    """
    technique, _ = parse_study_name(study_name)
    return technique


def resolve_library_from_study(
    study_name: str, device_type: str | None = None
) -> str:
    """Get the analysis library for a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
        device_type: Optional device type for library override.

    Returns:
        Library name (e.g. ``"iv"``, ``"pulse"``, ``"ec"``).
    """
    if device_type is not None and device_type in _device_types_dict():
        lib = _device_types_dict()[device_type].get("library")
        if lib:
            return lib

    technique, _ = parse_study_name(study_name)
    if technique:
        return technique

    return "general"


def resolve_legacy_technique(technique_name: str) -> str | None:
    """Map an old technique name to its corresponding study name.

    Args:
        technique_name: Old technique name (e.g. ``"iv-sweep"``).

    Returns:
        Study name in ``"technique:study-name"`` format, or None.
    """
    return _legacy_dict().get(technique_name)


# ── Accessors ──────────────────────────────────────────────────────────


def get_study_config(
    study_name: str, studies_dict: dict | None = None
) -> dict | None:
    """Return the full config dict for a named study.

    Combines the study definition with the technique reference.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.
        studies_dict: Optional studies dict override.

    Returns:
        Study config dict with ``technique`` and ``name`` added, or None.
    """
    studies = studies_dict if studies_dict is not None else _studies_dict()
    technique, name = parse_study_name(study_name)

    if not technique or technique not in studies:
        return None

    study_cfg = studies[technique].get(name)
    if study_cfg is None:
        return None

    return {**study_cfg, "technique": technique, "name": name}


def get_studies_for_device_type(device_type: str) -> list[str]:
    """Return study names applicable to a device type.

    Args:
        device_type: Device type slug (e.g. ``"volatile-memristor"``).

    Returns:
        List of study names in ``"technique:study-name"`` format.
    """
    if device_type not in _device_types_dict():
        return []

    return list(_device_types_dict()[device_type].get("studies", []))


def get_studies_for_instrument(instrument: str) -> list[str]:
    """Return study names that have this instrument in their config.

    Args:
        instrument: Instrument name (e.g. ``"keysight-b1500a"``).

    Returns:
        List of study names in ``"technique:study-name"`` format.
    """
    result: list[str] = []
    for technique, technique_studies in _studies_dict().items():
        for study_name, study_cfg in technique_studies.items():
            instruments = study_cfg.get("instruments", {})
            if instrument in instruments:
                result.append(f"{technique}:{study_name}")
    return result


def get_instruments_for_study(study_name: str) -> list[str]:
    """Return instrument names configured for a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.

    Returns:
        List of instrument names.
    """
    technique, name = parse_study_name(study_name)
    if not technique or technique not in _studies_dict():
        return []

    study_cfg = _studies_dict()[technique].get(name, {})
    return list(study_cfg.get("instruments", {}).keys())


# ── Listing ────────────────────────────────────────────────────────────


def list_studies(technique_filter: str | None = None) -> list[str]:
    """List all study names, optionally filtered by technique prefix.

    Args:
        technique_filter: Optional technique prefix filter (e.g. ``"iv"``).

    Returns:
        Sorted list of study names in ``"technique:study-name"`` format.
    """
    result: list[str] = []
    for technique, technique_studies in _studies_dict().items():
        if technique_filter is not None and technique != technique_filter:
            continue
        for study_name in technique_studies:
            result.append(f"{technique}:{study_name}")
    return sorted(result)


def list_techniques_from_studies() -> list[str]:
    """List all technique prefixes that have studies defined.

    Returns:
        Sorted list of technique prefixes.
    """
    return sorted(_studies_dict().keys())


# ── Rendering ──────────────────────────────────────────────────────────


def render_study_table(
    studies: dict | None = None,
    technique_filter: str = "",
    console: Any = None,
) -> None:
    """Render studies as a Rich table.

    Args:
        studies: Optional studies dict (same nested format as ``_STUDIES``).
            Uses ``_STUDIES`` if None.
        technique_filter: Optional technique filter (empty = all).
        console: Optional Rich ``Console`` instance. Creates one if needed.
    """
    from rich.console import Console
    from rich.table import Table

    studies_dict = studies if studies is not None else _studies_dict()
    console = console if console is not None else Console()

    table = Table(title="Available Studies", border_style="cyan")
    table.add_column("Study", style="bold")
    table.add_column("Technique")
    table.add_column("Description")

    for technique, technique_studies in studies_dict.items():
        if technique_filter and technique != technique_filter:
            continue
        for study_name, study_cfg in technique_studies.items():
            table.add_row(
                study_name,
                technique,
                study_cfg.get("label", ""),
            )

    console.print(table)


def render_waveform(study_name: str) -> str:
    """Return descriptive text or ASCII waveform art for a study.

    Args:
        study_name: Study name in ``"technique:study-name"`` format.

    Returns:
        ASCII waveform text or descriptive placeholder.
    """
    technique, name = parse_study_name(study_name)

    waveforms: dict[str, str] = {
        "iv:iv-bipolar-sweep": (
            "     V\n"
            "     ^\n"
            "Vmax ----.\n"
            "    /   |   .\n"
            "   /    |    .\n"
            "0 ------+-------.--- t\n"
            "   .    |    /  |\n"
            "    .   |   /   |\n"
            "-Vmax ---'        |\n"
            "                 `-- 2 sweeps (fwd + rev)"
        ),
        "pulse:pulse-stp-decay": (
            "     V\n"
            "     ^\n"
            "Vset ----.\n"
            "    /   |   .\n"
            "   /    |    .\n"
            "0 --'----+----'-------- t\n"
            "        |\n"
            "        `-- read window (current decay)"
        ),
        "pulse:pulse-ppf": (
            "  V   /\\    /\\\n"
            "  ^  /  \\  /  \\\n"
            "     /    \\/    \\\n"
            "0 --------------- t\n"
            "       <- Dt ->"
        ),
    }

    if study_name in waveforms:
        return waveforms[study_name]

    if technique:
        return f"{technique}:{name} -- no waveform available"

    return "no waveform available"


# ── Config bridge (to Phase 2) ─────────────────────────────────────────


def load_studies_from_config(config_dir: Path | None = None) -> dict:
    """Load studies from ``config-devices.yaml``.

    Reads the ``studies`` section from the YAML file, falling back to
    ``_STUDIES`` if the file does not exist or is empty.

    Args:
        config_dir: Config directory path. Defaults to ``~/.config/science-cli/``.

    Returns:
        Studies dict in the same nested format as ``_STUDIES``.
    """
    if config_dir is None:
        config_dir = Path.home() / ".config" / "science-cli" / "config"

    devices_path = config_dir / "config-devices.yaml"
    if devices_path.exists():
        import yaml

        raw = devices_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if data and isinstance(data, dict) and "studies" in data:
            return data["studies"]

    return dict(_studies_dict())
