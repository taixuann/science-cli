"""Results manifest — JSON + CSV output for tracking analysis."""

import csv
import json
from datetime import datetime
from pathlib import Path


def emit_manifest(
    output_dir: Path | str,
    command: str,
    source_files: list[str],
    output_files: list[str],
    technique: str = "",
    parameters: dict | None = None,
    results: dict | None = None,
    project: str = "",
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created": datetime.now().isoformat(),
        "project": project,
        "command": command,
        "technique": technique,
        "source_files": source_files,
        "output_files": output_files,
        "parameters": parameters or {},
        "results": results or {},
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    emit_csv = parameters and parameters.get("csv", False)
    if emit_csv and results:
        csv_path = output_dir / "results.csv"
        flat = _flatten_results(technique, results)
        if flat:
            with open(csv_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=flat[0].keys())
                w.writeheader()
                w.writerows(flat)

    return manifest_path


def emit_csv_results(output_dir: Path | str, technique: str, results: dict):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _flatten_results(technique, results)
    if not rows:
        return None
    csv_path = output_dir / f"{technique}_results.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return csv_path


def _flatten_results(technique: str, results: dict) -> list[dict]:
    if technique == "ec-cv" and "peaks" in results:
        return results["peaks"]
    if technique == "ec-eis" and "fit_params" in results:
        return results["fit_params"]
    if technique == "ec-ca" and "fit_params" in results:
        return results["fit_params"]
    return [results]
