"""Shared YAML analysis output writer.

Provides a universal ``write_analysis_yaml()`` that any technique analyzer
can call to produce ``<step_dir>/results/<technique>_analysis.yaml`` files.
Each technique's results dict is validated against an optional per-technique
schema validator before being written.
"""

from datetime import datetime
from pathlib import Path

import yaml


def _get_validator(technique: str):
    """Look up a validator function for *technique* (or *None*)."""
    try:
        from science_cli.analysis.validators import SCHEMA_VALIDATORS
        return SCHEMA_VALIDATORS.get(technique)
    except ImportError:
        return None


def write_analysis_yaml(
    technique: str,
    step_dir: Path,
    analysis_results: dict,
    instrument: str = "",
    devices: str = "",
) -> Path:
    """Write analysis results to ``<step_dir>/results/<technique>_analysis.yaml``.

    Parameters
    ----------
    technique:
        Technique slug (e.g. ``iv-sweep``, ``pulse-endurance``, ``pvd-deposition``).
    step_dir:
        Path to the step directory (the parent of the ``results/`` sub-directory).
    analysis_results:
        Technique-specific analysis results (will be validated if a schema
        validator is registered for *technique*).
    instrument:
        Instrument identifier string (optional — included in envelope metadata).
    devices:
        Device-type string from the protocol YAML (optional — included in
        envelope metadata).

    Returns
    -------
    Path
        The absolute path of the written YAML file.
    """
    results_dir = step_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = results_dir / f"{technique}_analysis.yaml"

    validator = _get_validator(technique)
    if validator is not None:
        validated = validator(analysis_results)
    else:
        validated = analysis_results

    output = {
        "technique": technique,
        "instrument": instrument,
        "devices": devices,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **validated,
    }

    with open(yaml_path, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False)

    return yaml_path
