"""Parquet storage for processed/extracted data.

Raw measurements are NEVER stored as parquet — only processed/extracted features.
This ensures raw data remains auditable and immutable.

Dependencies: pyarrow (already in pyproject.toml)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_features(
    df: pd.DataFrame,
    output_dir: str | Path,
    name: str = "features",
) -> Path:
    """Write a DataFrame of extracted features to a parquet file.

    Args:
        df: DataFrame with extracted features (one row per measurement).
        output_dir: Directory to write the parquet file to (e.g., step results dir).
        name: Base name for the file (default: 'features').

    Returns:
        Path to the written .parquet file.

    The output file will be: <output_dir>/<name>.parquet

    Raises:
        ValueError: If df is empty.
        OSError: If the directory cannot be created.
    """
    if df.empty:
        raise ValueError("Cannot write empty DataFrame to parquet")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    parquet_path = output_path / f"{name}.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")

    return parquet_path


def read_features(
    input_dir: str | Path,
    name: str = "features",
) -> pd.DataFrame | None:
    """Read extracted features from a parquet file.

    Args:
        input_dir: Directory containing the parquet file.
        name: Base name of the file (default: 'features').

    Returns:
        DataFrame with features, or None if the file doesn't exist.
    """
    parquet_path = Path(input_dir) / f"{name}.parquet"

    if not parquet_path.exists():
        return None

    return pd.read_parquet(parquet_path, engine="pyarrow")


def append_features(
    df: pd.DataFrame,
    output_dir: str | Path,
    name: str = "features",
) -> Path:
    """Append rows to an existing features parquet file, or create new one.

    Args:
        df: New feature rows to append.
        output_dir: Directory containing the parquet file.
        name: Base name of the file (default: 'features').

    Returns:
        Path to the parquet file.
    """
    existing = read_features(output_dir, name)

    if existing is not None:
        combined = pd.concat([existing, df], ignore_index=True)
        # Drop duplicate rows based on all columns
        combined = combined.drop_duplicates()
    else:
        combined = df

    return write_features(combined, output_dir, name)


def list_feature_files(input_dir: str | Path) -> list[Path]:
    """List all parquet feature files in a directory.

    Args:
        input_dir: Directory to scan.

    Returns:
        Sorted list of .parquet file paths.
    """
    return sorted(Path(input_dir).glob("*.parquet"))


def feature_metadata(parquet_path: str | Path) -> dict[str, Any] | None:
    """Get metadata about a features parquet file.

    Args:
        parquet_path: Path to the parquet file.

    Returns:
        Dict with: num_rows, num_columns, columns, dtypes, file_size_bytes
        or None if file doesn't exist.
    """
    path = Path(parquet_path)
    if not path.exists():
        return None

    df = pd.read_parquet(path, engine="pyarrow")

    return {
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "file_size_bytes": path.stat().st_size,
    }
