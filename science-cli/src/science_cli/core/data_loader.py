"""Data loading — reads experimental data files into pandas DataFrames."""

from pathlib import Path
import numpy as np
import pandas as pd


def load_data_file(filepath: str) -> tuple[pd.DataFrame, dict]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

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


def _load_mpt(path: Path) -> tuple[pd.DataFrame, dict]:
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
    from science_cli.plot.base import create_figure, save_figure
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
