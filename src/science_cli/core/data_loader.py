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
) -> tuple[pd.DataFrame, dict]:
    """Load a data file into a DataFrame.

    Args:
        filepath: Path to the data file.
        technique: Technique key (e.g. 'ec-eis', 'iv-sweep').
                   When provided with device, uses device config for loading.
        device: Device name (e.g. 'biologic-mpt', 'keithley-2400').
                When provided with technique, uses device config for loading.

    Returns:
        (DataFrame, metadata_dict) where metadata_dict includes at minimum
        'format', 'columns', 'path', and optionally 'device', 'technique'.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Try device-aware loading if technique + device provided
    device_cfg = _resolve_device_config(technique, device)
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


def _resolve_device_config(technique: str, device: str) -> dict | None:
    """Look up device loading config from the config system.

    Resolution order:
        1. Per-technique device config (technique → devices → device)
        2. Global device registry (devices → device)
        3. Hardcoded defaults
    """
    if not technique or not device:
        return None
    try:
        from science_cli.core.config import get_device_config, get_global_device_config
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        project_root = proj if proj else None

        # Try per-technique device config first
        cfg = get_device_config(technique, device, project_root)
        if cfg:
            return cfg

        # Fall back to global device registry
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
    and column name remapping.
    """
    delimiter = device_cfg.get("delimiter")
    decimal = device_cfg.get("decimal", ".")
    header_lines = device_cfg.get("header_lines", 0)
    encoding = device_cfg.get("encoding", "utf-8")
    columns = device_cfg.get("columns", {})

    # Auto-detect delimiter if not specified
    if delimiter is None:
        with open(path, encoding=encoding, errors="replace") as f:
            first_line = f.readline().strip()
        delimiter = (
            "\t" if "\t" in first_line
            else ";" if ";" in first_line
            else "," if "," in first_line
            else None
        )

    if delimiter:
        df = pd.read_csv(
            path,
            sep=delimiter,
            decimal=decimal,
            skiprows=header_lines,
            encoding=encoding,
            engine="python",
        )
    else:
        df = pd.read_csv(
            path,
            sep=r"\s+",
            decimal=decimal,
            skiprows=header_lines,
            encoding=encoding,
            engine="python",
        )

    df.columns = [c.strip().strip('"') for c in df.columns]

    # Remap columns if device config provides a column mapping
    if columns:
        # columns maps role→actual_column_name (e.g. voltage→"SourceV")
        # We create a reverse map to rename actual columns to role names
        rename_map: dict[str, str] = {}
        for role, actual_name in columns.items():
            if actual_name in df.columns:
                # Don't rename if it would overwrite another column
                if actual_name not in rename_map.values():
                    rename_map[actual_name] = role
        if rename_map:
            df = df.rename(columns=rename_map)

    # Ensure numeric coercion
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, {
        "format": path.suffix.lstrip("."),
        "columns": list(df.columns),
        "path": str(path),
        "device": device,
        "technique": technique,
    }


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
