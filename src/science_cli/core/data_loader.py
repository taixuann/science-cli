"""Data loading — reads experimental data files into pandas DataFrames.

Supports device-aware loading via the config system (4-tier resolution):
    1. Per-technique device config (technique → devices → device)
    2. Global device registry (devices → device) — fallback
    3. Auto-detection from file extension (no device config available)
    4. Hardcoded defaults (delimiter, encoding, header_lines)
"""

from pathlib import Path

import numpy as np
import pandas as pd


def load_data_file(
    filepath: str,
    technique: str = "",
    device: str = "",
    study_name: str = "",
) -> tuple[pd.DataFrame, dict]:
    """Load a data file into a DataFrame.

    Args:
        filepath: Path to the data file.
        technique: Technique key (e.g. 'ec-eis', 'iv-sweep').
                   When provided with device, uses device config for loading.
        device: Device name (e.g. 'biologic-mpt', 'keithley-2400').
                When provided with technique, uses device config for loading.
        study_name: Study name (e.g. 'iv:iv-bipolar-sweep'). When provided,
                   resolves technique + device config through study.

    Returns:
        (DataFrame, metadata_dict) where metadata_dict includes at minimum
        'format', 'columns', 'path', and optionally 'device', 'technique'.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Resolve technique from study if provided
    if study_name and not technique:
        try:
            from science_cli.core.config import resolve_technique_from_study
            technique = resolve_technique_from_study(study_name)
        except ImportError:
            pass

    # Try device-aware loading if technique + device or study_name provided
    device_cfg = _resolve_device_config(technique, device, study_name)
    if device_cfg:
        return _load_with_device_config(path, device_cfg, technique, device)

    # Fall back to extension-based auto-detection
    ext = path.suffix.lower()

    if ext == ".mpt":
        return _load_mpt(path)
    elif ext == ".csv":
        return _load_csv(path)
    elif ext == ".txt":
        return _load_txt(path)
    elif ext == ".xlsx":
        return _load_excel(path)
    else:
        return _load_txt(path)


def _resolve_device_config(
    technique: str, device: str, study_name: str = ""
) -> dict | None:
    """Look up device loading config, resolving through study first.

    Resolution order:
        1. Study instruments (if study_name provided)
        2. Per-technique device config (technique → devices → device)
        3. Global device registry (devices → device)
        4. Hardcoded defaults
    """
    if not technique and not device and not study_name:
        return None
    try:
        from science_cli.core.config import (
            get_device_config,
            get_global_device_config,
            get_study_config,
        )
        from science_cli.core.project import get_current_project_path

        proj = get_current_project_path()
        project_root = proj if proj else None

        # Try study-based config first
        if study_name:
            study_cfg = get_study_config(study_name)
            if study_cfg:
                instruments = study_cfg.get("instruments", {})
                if device and device in instruments:
                    cfg = dict(instruments[device])
                elif instruments:
                    first_dev = next(iter(instruments))
                    cfg = dict(instruments[first_dev])
                    device = first_dev
                else:
                    cfg = None

                if cfg:
                    global_cfg = get_global_device_config(device)
                    if global_cfg:
                        from science_cli.core.config import _merge_dicts
                        cfg = _merge_dicts(cfg, global_cfg)

                    from science_cli.core.config import _DEFAULT_DEVICE
                    merged = dict(_DEFAULT_DEVICE)
                    merged.update(cfg)
                    return merged

        # Try per-technique device config (existing behavior)
        if technique and device:
            cfg = get_device_config(technique, device, project_root)
            if cfg:
                return cfg

        # Fall back to global device registry
        if device:
            cfg = get_global_device_config(device)
            if cfg:
                return cfg

        return None
    except ImportError:
        return None


def _load_with_device_config(
    path: Path,
    device_cfg: dict,
    technique: str,
    device: str,
) -> tuple[pd.DataFrame, dict]:
    """Load a file using explicit device configuration.

    Uses device_cfg for: delimiter, decimal sep, header_lines, encoding,
    column name remapping, and optional explicit column names for header-less files.

    Also runs the metadata extraction pipeline if device_cfg contains
    a ``metadata`` section (parse header fields + analyze loaded columns).
    The instrument_config is included in the returned info dict for downstream
    use (e.g. column resolution in plot functions).
    """
    delimiter = device_cfg.get("delimiter")
    decimal = device_cfg.get("decimal", ".")
    header_lines = device_cfg.get("header_lines", 0)
    encoding = device_cfg.get("encoding", "utf-8")
    columns = device_cfg.get("columns", {})
    names = device_cfg.get("names")

    # Read raw lines before CSV parsing for metadata extraction
    with open(path, encoding=encoding, errors="replace") as f:
        raw_lines = f.readlines()

    # Auto-detect delimiter if not specified
    if delimiter is None:
        first_line = raw_lines[0].strip() if raw_lines else ""
        delimiter = (
            "\t" if "\t" in first_line
            else ";" if ";" in first_line
            else "," if "," in first_line
            else None
        )

    read_kwargs = {
        "sep": delimiter or r"\s+",
        "decimal": decimal,
        "skiprows": header_lines,
        "encoding": encoding,
        "engine": "python",
        "on_bad_lines": "skip",
    }

    if names:
        read_kwargs["header"] = None
        read_kwargs["names"] = names

    df = pd.read_csv(path, **read_kwargs)

    df.columns = [c.strip().strip('"') for c in df.columns]

    # Filter Keysight B1500A format: keep only DataValue rows (drop SetupTitle, etc.)
    if "DataName" in df.columns:
        df = df[df["DataName"].str.strip() == "DataValue"].copy()
        df = df.drop(columns=["DataName"])

    # Remap columns if device config provides a column mapping
    if columns:
        rename_map: dict[str, str] = {}
        for role, actual_name in columns.items():
            if actual_name in df.columns:
                if actual_name not in rename_map.values():
                    rename_map[actual_name] = role
        if rename_map:
            df = df.rename(columns=rename_map)

    # Ensure numeric coercion — try all columns initially
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        except (ValueError, TypeError):
            pass

    # Extract Raman metadata if applicable
    raman_meta = {}
    if technique == "raman":
        raman_meta = extract_raman_metadata(path)

    # Metadata extraction pipeline
    metadata_config = device_cfg.get("metadata", {})
    parsed_meta = {}
    analysis_meta = {}
    if metadata_config:
        from science_cli.core.metadata import extract_metadata as _run_meta_extract

        parsed_meta, analysis_meta = _run_meta_extract(raw_lines, metadata_config, df=df)

    meta = {
        "format": path.suffix.lstrip("."),
        "columns": list(df.columns),
        "path": str(path),
        "device": device,
        "technique": technique,
        "instrument_config": device_cfg,
    }
    if raman_meta:
        meta["raman_metadata"] = raman_meta
    if parsed_meta:
        meta["metadata"] = parsed_meta
    if analysis_meta:
        meta["analysis"] = analysis_meta

    return df, meta


def _load_mpt(path: Path) -> tuple[pd.DataFrame, dict]:
    """Legacy MPT loader — biologics BioLogic .mpt files."""
    with open(path) as f:
        lines = f.readlines()
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("Frequency"):
            header_end = i
            break
    else:
        for i, line in enumerate(lines):
            if line.strip().startswith("f/Hz"):
                header_end = i
                break

    df = pd.read_csv(path, skiprows=header_end, sep="\t", encoding="latin1")
    df.columns = [c.strip() for c in df.columns]
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, {"format": "mpt", "columns": list(df.columns), "path": str(path)}


def _load_csv(path: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(path)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, {"format": "csv", "columns": list(df.columns), "path": str(path)}


def _load_txt(path: Path) -> tuple[pd.DataFrame, dict]:
    with open(path) as f:
        first_line = f.readline().strip()
    sep = "\t" if "\t" in first_line else ";" if ";" in first_line else "," if "," in first_line else None

    if sep:
        df = pd.read_csv(path, sep=sep, comment="#", engine="python")
    else:
        df = pd.read_csv(path, sep=r"\s+", comment="#", engine="python")

    df.columns = [c.strip().strip('"') for c in df.columns]
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, {"format": "txt", "columns": list(df.columns), "path": str(path)}


def _load_excel(path: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_excel(path)
    return df, {"format": "xlsx", "columns": list(df.columns), "path": str(path)}


def fit_file(filepath: str, model: str = "linear", xcol: str = "", ycol: str = ""):
    import numpy as np
    from lmfit import Model

    df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 2:
        print("Need at least 2 columns")
        return

    x = df[cols[0]].values if not xcol else df[xcol].values
    y = df[cols[1]].values if not ycol else df[ycol].values
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    if model == "linear":
        def func(x, slope, intercept):
            return slope * x + intercept
    elif model == "exponential":
        def func(x, a, b, c):
            return a * np.exp(-b * x) + c
    elif model == "power":
        def func(x, a, b):
            return a * x ** b
    else:
        def func(x, a, b):
            return a * x + b

    fit_model = Model(func)
    params = fit_model.make_params()
    try:
        result = fit_model.fit(y, params, x=x)
        print(result.fit_report())
        return result
    except Exception as e:
        print(f"Fit failed: {e}")
        return None


def extract_raman_metadata(filepath: str | Path) -> dict:
    """Re-exported from :mod:`science_cli.core.metadata.parsers.raman`."""
    from science_cli.core.metadata.parsers.raman import extract_raman_metadata as _fn
    return _fn(filepath)


_extract_raman_header_metadata = extract_raman_metadata
