"""Shared pytest fixtures for science-cli tests."""

import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

SRC_DIR = Path(__file__).parent / "src"


# ── Temporary directory fixtures ──────────────────────────────────────


@pytest.fixture
def tmp_project():
    """Create a temporary project directory with sci-config.yaml."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        (proj / "sci-config.yaml").write_text("")
        (proj / "data" / "raw").mkdir(parents=True, exist_ok=True)
        yield proj


@pytest.fixture
def tmp_project_with_config(tmp_project):
    """Create a temporary project with a realistic sci-config.yaml."""
    config = {
        "techniques": {
            "iv-sweep": {
                "patterns": ["*_iv_*.csv", "*_IV-DC_*"],
                "header_marker": "Voltage",
                "devices": {
                    "test-device": {
                        "delimiter": ",",
                        "decimal": ".",
                        "header_lines": 1,
                        "encoding": "utf-8",
                        "columns": {
                            "voltage": "Voltage (V)",
                            "current": "Current (A)",
                            "time": "Time (s)",
                        },
                    },
                },
            },
        },
        "defaults": {"iv-sweep": "test-device"},
        "file_naming": {
            "separator": "_",
            "patterns": [
                {
                    "template": "{date_code}_{material}_{matrix}_{technique}",
                    "description": "Minimal naming",
                    "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+)_(?P<matrix>r\d+c\d+)_(?P<technique>[^_]+)\.\w+$",
                    "fields": {
                        "date_code": {"sql_column": "date_code"},
                        "material": {"sql_column": "material"},
                        "matrix": {"sql_column": None},
                        "technique": {"sql_column": "technique"},
                    },
                    "extract": {
                        "matrix": r"r(?P<row>\d+)c(?P<col>\d+)",
                    },
                },
            ],
        },
    }
    import yaml
    (tmp_project / "sci-config.yaml").write_text(yaml.dump(config))
    return tmp_project


# ── Session state fixtures ────────────────────────────────────────────


@pytest.fixture
def mock_session():
    """Mock session.py to use a temp file instead of ~/.config/science-cli/session.json."""
    sess = {
        "last_project": "",
        "last_protocol": "",
        "last_step": "",
        "project_state": {},
        "protocol_state": {},
        "step_state": {},
        "history": [],
        "theme": "publication-acs",
        "fzf_opts": {"height": "60%"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sess, f)
        temp_path = f.name

    with patch("science_cli.core.session.SESSION_FILE", Path(temp_path)):
        yield sess

    Path(temp_path).unlink(missing_ok=True)


# ── Sample CSV data fixtures ──────────────────────────────────────────


@pytest.fixture
def sample_iv_csv(tmp_path):
    """Create a sample IV CSV file."""
    content = """Time (s),Voltage (V),Current (A)
0.0,0.0,0.0
0.1,0.5,1e-6
0.2,1.0,2e-5
0.3,1.5,5e-4
0.4,2.0,1e-3
0.5,1.5,8e-4
0.6,1.0,3e-5
0.7,0.5,2e-6
0.8,0.0,0.0
"""
    path = tmp_path / "test_iv.csv"
    path.write_text(content)
    return path


@pytest.fixture
def sample_lvm_file(tmp_path):
    """Create a sample Keithley 2400 LVM-style tab-separated file."""
    content = (
        "LabVIEW Measurement\\n"
        "***End_of_Header***\\n"
        "X_Value\\tUntitled\\tUntitled 1\\tUntitled 2\\tComment\\n"
        "0\\t0.0\\t0.0\\t0.0\\t\\n"
        "1\\t0.5\\t1e-6\\t0.1\\t\\n"
        "2\\t1.0\\t2e-5\\t0.2\\t\\n"
    )
    path = tmp_path / "test_keithley.lvm"
    path.write_text(content)
    return path
