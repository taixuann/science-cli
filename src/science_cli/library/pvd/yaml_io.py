"""Read/write PVD deposition YAML analysis files."""
from pathlib import Path
from typing import Optional

import yaml

from science_cli.core.analysis_output import write_analysis_yaml
from science_cli.library.pvd.models import DepositionRun


def write_deposition_yaml(run: DepositionRun, output_path: Path) -> Path:
    """Write deposition run to YAML analysis file using shared writer.

    The *output_path* should be the full path to the desired YAML file
    (e.g. ``.../results/pvd-deposition_analysis.yaml``).  The parent of the
    ``results/`` directory will be used as the *step_dir*.
    """
    output_path = Path(output_path)

    analysis = {
        "analysis": {
            "total_thickness_nm": run.total_thickness_nm,
            "materials": list(dict.fromkeys([l.material for l in run.layers])),
            "deposition_parameters": {
                "temperature_c": run.layers[0].temperature_c if run.layers else None,
                "rate_nm_s": run.layers[0].rate_nm_s if run.layers else None,
            },
            "layer_stack": [
                {
                    "material": l.material,
                    "thickness_nm": l.thickness_nm,
                    "rate_nm_s": l.rate_nm_s,
                    "temperature_c": l.temperature_c,
                    "pressure_mtorr": l.pressure_mtorr,
                }
                for l in run.layers
            ],
        },
        "parameters": run.parameters,
        "status": "complete",
    }

    # Derive step_dir from output_path so the shared writer creates results/
    # e.g. output_path = .../protocol/step_name/results/pvd-deposition_analysis.yaml
    #       step_dir    = .../protocol/step_name
    if output_path.name.endswith("_analysis.yaml") and output_path.parent.name == "results":
        step_dir = output_path.parent.parent
    else:
        step_dir = output_path.parent

    return write_analysis_yaml(
        technique=run.technique,
        step_dir=step_dir,
        analysis_results=analysis,
        instrument=run.instrument,
        devices=getattr(run, "devices", ""),
    )


def read_deposition_yaml(path: Path) -> Optional[dict]:
    """Read deposition YAML analysis file."""
    path = Path(path)
    if not path.exists():
        return None

    with open(path) as f:
        data = yaml.safe_load(f)

    return data
