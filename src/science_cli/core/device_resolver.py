"""Device resolution utility — determines which instrument a measurement file belongs to.

Extracted from ``cli/commands/plot.py`` and ``cli/commands/analyze.py`` to eliminate
code duplication. Both CLI modules imported this function with identical logic.
"""

from pathlib import Path


def resolve_device(
    technique: str,
    filepath: str,
    study_name: str | None = None,
) -> str:
    """Determine which device was used for this file based on step metadata.

    Resolution order:
        1. Look up file in the current protocol's steps → get ``instrument`` field
        2. Study instruments (if ``study_name`` provided and protocol lookup fails)
        3. Fall back to ``get_default_device(technique, study_name=study_name)``

    Args:
        technique: Technique name (e.g. ``"ec-cv"``, ``"iv-sweep"``).
        filepath: Path to the data file to look up in protocol steps.
        study_name: Optional study name for study-level instrument fallback.

    Returns:
        Device/instrument name string (e.g. ``"keysight-b1500a"``) or ``""``.
    """
    from science_cli.core.config import get_default_device, get_study_config
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    proj = get_current_project_path()
    session = load_session()
    pname = session.get("last_protocol", "")

    if pname and proj:
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(pname)
        if yaml_path.exists():
            import yaml
            with open(yaml_path) as f:
                proto = yaml.safe_load(f) or {}
            fname = Path(filepath).name
            for s in proto.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    instrument = s.get("instrument") or s.get("device", "")
                    if instrument:
                        return instrument

    # Study-level instrument fallback (if study_name provided)
    if not technique and study_name:
        study_cfg = get_study_config(study_name)
        if study_cfg:
            instrs = study_cfg.get("instruments", {})
            if instrs:
                return next(iter(instrs))

    return get_default_device(technique, study_name=study_name)
