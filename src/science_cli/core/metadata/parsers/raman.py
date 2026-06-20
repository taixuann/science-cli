"""Raman spectroscopy header parsing — Horiba LabRAM file metadata.

Renamed from ``core/metadata/raman_header.py`` as part of parsers/ + analyzers/
split. The function name ``extract_raman_metadata`` is preserved for backwards
compatibility.
"""

from __future__ import annotations

from pathlib import Path


def extract_raman_metadata(filepath: str | Path) -> dict:
    """Parse the #-prefixed header from a Horiba LabRAM file and return metadata dict.

    Keys are normalized snake_case versions of the header field names.
    """
    path = Path(filepath) if not isinstance(filepath, Path) else filepath
    meta: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.startswith("#"):
                    break
                content = line.lstrip("#").strip()
                if "=" in content:
                    key_raw, val = content.split("=", 1)
                    key = (
                        key_raw.strip()
                        .lower()
                        .replace(" ", "_")
                        .replace(".", "")
                        .replace("(", "")
                        .replace(")", "")
                        .replace("/", "_per_")
                    )
                    meta[key] = val.strip()
    except OSError:
        pass
    return meta
