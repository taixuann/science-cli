"""Tests for waveform pulse analysis module."""

import numpy as np
import pandas as pd


def _make_stp_dataframe(n_repeats=1, n_points=500):
    """Create a synthetic STP decay-like DataFrame.

    Waveform: 0V -> 2.75V set pulse -> 0.5V read pulse
    Uses linspace for clean time arrays.
    """
    n_bl = 50
    n_ris = 16
    n_set = 300
    n_fal = 17
    n_read = n_points - n_bl - n_ris - n_set - n_fal

    t_bl = np.linspace(0, 14.7, n_bl)
    t_ris = np.linspace(15, 19.5, n_ris)
    t_set = np.linspace(20, 109.5, n_set)
    t_fal = np.linspace(110, 114, n_fal)
    t_rd = np.linspace(115, 149.85, n_read)
    t = np.concatenate([t_bl, t_ris, t_set, t_fal, t_rd]) * 1e-6

    v = np.concatenate([
        np.full(n_bl, 0.0),
        np.linspace(0, 2.75, n_ris),
        np.full(n_set, 2.75),
        np.linspace(2.75, 0.5, n_fal),
        np.full(n_read, 0.5),
    ])

    c = np.concatenate([
        np.full(n_bl, -1e-9),
        np.full(n_ris, -1e-9),
        np.full(n_set, -1e-3),
        np.full(n_fal, -1e-3),
        np.exp(-np.arange(n_read) * 0.1) * -1e-3,
    ])

    if n_repeats > 1:
        t = np.tile(t, n_repeats)
        v = np.tile(v, n_repeats)
        c = np.tile(c, n_repeats)

    return pd.DataFrame({
        "time": t,
        "voltage": v,
        "current": c,
    })


class TestGrammarPattern:
    def test_valid_filename(self):
        import re
        pattern = (
            r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
            r"_(?P<matrix>r\d+-c\d+)_(?P<study>stp-decay)"
            r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$"
        )
        fname = "150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_041_important.csv"
        m = re.match(pattern, fname)
        assert m is not None, f"Failed to match {fname}"
        assert m.group("date_code") == "150626"
        assert m.group("material") == "cu-c-pda(q5)-ito"
        assert m.group("matrix") == "r5-c2"
        assert m.group("study") == "stp-decay"
        assert m.group("suffix") == "041"
        assert m.group("tag") == "important"
        assert m.group("ext") == "csv"

    def test_valid_filename_no_tag(self):
        import re
        pattern = (
            r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
            r"_(?P<matrix>r\d+-c\d+)_(?P<study>stp-decay)"
            r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$"
        )
        fname = "150626_cu-c-pda(q5)-ito_r5-c2_stp-decay_001.csv"
        m = re.match(pattern, fname)
        assert m is not None
        assert m.group("suffix") == "001"
        assert m.group("tag") is None

    def test_invalid_filename_no_stp(self):
        import re
        pattern = (
            r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
            r"_(?P<matrix>r\d+-c\d+)_(?P<study>stp-decay)"
            r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$"
        )
        fname = "150626_cu-c-pda(q5)-ito_r5-c2_iv-sweep_001.csv"
        m = re.match(pattern, fname)
        assert m is None

    def test_invalid_filename_bad_matrix(self):
        import re
        pattern = (
            r"^(?P<date_code>\d{6})_(?P<material>[-A-Za-z0-9/()]+)"
            r"_(?P<matrix>r\d+-c\d+)_(?P<study>stp-decay)"
            r"_(?P<suffix>\d+)(?:_(?P<tag>[^_]+))?\.(?P<ext>\w+)$"
        )
        fname = "150626_cu-c-pda(q5)-ito_bot2-top3_stp-decay_001.csv"
        m = re.match(pattern, fname)
        assert m is None


class TestAnalyzeWaveformParams:
    def test_empty_dataframe(self):
        from science_cli.core.metadata.analyzers.waveform import analyze_waveform_params
        df = pd.DataFrame()
        result = analyze_waveform_params(df, [])
        assert result == {}

    def test_synthetic_single_trace(self):
        from science_cli.core.metadata.analyzers.waveform import analyze_waveform_params
        df = _make_stp_dataframe(n_repeats=1)
        result = analyze_waveform_params(df, [])
        assert "v_set_v" in result
        assert "v_read_v" in result
        assert abs(result["v_set_v"] - 2.75) < 0.1
        assert abs(result["v_read_v"] - 0.5) < 0.1
        assert result["set_width_us"] > 0
        assert result["rise_us"] > 0
        assert result["repeat_pattern"] == "single"

    def test_synthetic_repeated_trace(self):
        from science_cli.core.metadata.analyzers.waveform import analyze_waveform_params
        df = _make_stp_dataframe(n_repeats=2)
        result = analyze_waveform_params(df, [])
        assert "v_set_v" in result
        assert abs(result["v_set_v"] - 2.75) < 0.1
        assert result["repeat_pattern"] == "repeated"

    def test_no_voltage_column(self):
        from science_cli.core.metadata.analyzers.waveform import analyze_waveform_params
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = analyze_waveform_params(df, [])
        assert result == {}


class TestParseSetupPulses:
    def test_with_stp_header(self):
        from science_cli.core.metadata.parsers.waveform import parse_setup_pulses
        lines = [
            "SomeHeader, field1, field2",
            "SetupTitle, STP decay",
            "AnotherField, value",
        ]
        result = parse_setup_pulses(lines)
        assert result is not None
        assert result["setup_title"] == "STP decay"

    def test_no_match(self):
        from science_cli.core.metadata.parsers.waveform import parse_setup_pulses
        lines = ["SomeHeader, field1", "AnotherField, value"]
        result = parse_setup_pulses(lines)
        assert result is None

    def test_empty_lines(self):
        from science_cli.core.metadata.parsers.waveform import parse_setup_pulses
        result = parse_setup_pulses([])
        assert result is None


class TestDetectRepeatPattern:
    def test_single_trace(self):
        from science_cli.core.metadata.analyzers.waveform import detect_repeat_pattern
        t = np.linspace(0, 1, 100)
        df = pd.DataFrame({"time": t})
        result = detect_repeat_pattern(df)
        assert result["repeat_pattern"] == "single"
        assert result["n_repeats"] == 1

    def test_repeated_trace_duplicates(self):
        from science_cli.core.metadata.analyzers.waveform import detect_repeat_pattern
        t = np.tile(np.linspace(0, 1, 50), 2)
        df = pd.DataFrame({"time": t})
        result = detect_repeat_pattern(df)
        assert result["repeat_pattern"] == "repeated"
        assert result["n_repeats"] == 2

    def test_no_time_column(self):
        from science_cli.core.metadata.analyzers.waveform import detect_repeat_pattern
        df = pd.DataFrame({"voltage": [1, 2, 3]})
        result = detect_repeat_pattern(df)
        assert result["repeat_pattern"] == "single"
        assert result["n_repeats"] == 1


class TestInvertCurrentSign:
    def test_inverts_current(self):
        from science_cli.core.metadata.analyzers.waveform import invert_current_sign
        df = pd.DataFrame({
            "time": [0.0, 1.0],
            "current": [-1e-3, -2e-3],
            "voltage": [0.0, 2.75],
        })
        result = invert_current_sign(df)
        assert result["current"].iloc[0] == 1e-3
        assert result["current"].iloc[1] == 2e-3
        assert result["voltage"].iloc[0] == 0.0

    def test_inverts_measresult2(self):
        from science_cli.core.metadata.analyzers.waveform import invert_current_sign
        df = pd.DataFrame({
            "MeasResult2_value": [-5e-6, -1e-5],
        })
        result = invert_current_sign(df)
        assert result["MeasResult2_value"].iloc[0] == 5e-6

    def test_does_not_modify_original(self):
        from science_cli.core.metadata.analyzers.waveform import invert_current_sign
        df = pd.DataFrame({"current": [-1e-3]})
        result = invert_current_sign(df)
        assert df["current"].iloc[0] == -1e-3
        assert result["current"].iloc[0] == 1e-3

    def test_empty_dataframe(self):
        from science_cli.core.metadata.analyzers.waveform import invert_current_sign
        df = pd.DataFrame()
        result = invert_current_sign(df)
        assert result.empty


class TestStpYamlOutput:
    def test_metadata_included(self, tmp_path):
        from science_cli.library.pulse.stp import analyze_stp_decay_to_yaml
        t = np.linspace(0, 150e-6, 500)
        i = np.exp(-t * 1e4) * 1e-3
        metadata = {
            "v_set_v": 2.75,
            "v_read_v": 0.5,
            "set_width_us": 90.0,
            "read_width_us": 35.0,
            "repeat_pattern": "single",
        }
        path = analyze_stp_decay_to_yaml(
            time=t, current=i,
            step_dir=tmp_path,
            instrument="keysight-b1500a",
            devices="volatile-memristor",
            metadata=metadata,
        )
        assert path.exists()
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "analysis" in data
        assert "waveform" in data["analysis"]
        assert data["analysis"]["waveform"]["v_set_v"] == 2.75
        assert data["analysis"]["waveform"]["v_read_v"] == 0.5
        assert data["analysis"]["waveform"]["set_width_us"] == 90.0

    def test_no_metadata_no_waveform_section(self, tmp_path):
        from science_cli.library.pulse.stp import analyze_stp_decay_to_yaml
        t = np.linspace(0, 150e-6, 500)
        i = np.exp(-t * 1e4) * 1e-3
        path = analyze_stp_decay_to_yaml(
            time=t, current=i,
            step_dir=tmp_path,
            instrument="keysight-b1500a",
            devices="volatile-memristor",
        )
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "analysis" in data
        assert "waveform" not in data["analysis"]


class TestDetectWaveformPattern2d:
    def test_returns_2d_list(self):
        """detect_waveform_pattern_2d returns [[t, v], ...] for pulse data."""
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        df = _make_stp_dataframe()
        result = detect_waveform_pattern_2d(df)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(pt, list) and len(pt) == 2 for pt in result)
        assert all(isinstance(pt[0], float) and isinstance(pt[1], float) for pt in result)

    def test_sorted_by_time(self):
        """Output is sorted by time ascending."""
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        df = _make_stp_dataframe()
        result = detect_waveform_pattern_2d(df)
        times = [pt[0] for pt in result]
        assert times == sorted(times)

    def test_empty_no_time_column(self):
        """Returns [] when no time column."""
        import pandas as pd
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = detect_waveform_pattern_2d(df)
        assert result == []

    def test_empty_no_voltage_column(self):
        """Returns [] when no voltage column."""
        import pandas as pd
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        df = pd.DataFrame({"time": [0.0, 1.0, 2.0]})
        result = detect_waveform_pattern_2d(df)
        assert result == []

    def test_subsampling(self):
        """1000-point input is subsampled to max_points."""
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        df = _make_stp_dataframe(n_points=1000)
        result = detect_waveform_pattern_2d(df, max_points=200)
        assert len(result) <= 200

    def test_values_match_input(self):
        """Output values match the input DataFrame."""
        from science_cli.core.metadata.analyzers.waveform import detect_waveform_pattern_2d
        t = np.array([0.0, 1.0, 2.0, 3.0])
        v = np.array([0.0, 1.5, 2.75, 0.5])
        df = pd.DataFrame({"time": t, "voltage": v})
        result = detect_waveform_pattern_2d(df)
        assert len(result) == 4
        assert result[0] == [0.0, 0.0]
        assert result[2] == [2.0, 2.75]


class TestExtractWaveformMetadata:
    def test_contains_waveform_pattern(self):
        """extract_waveform_metadata returns waveform_pattern + scalars."""
        from science_cli.core.metadata.analyzers.waveform import extract_waveform_metadata
        df = _make_stp_dataframe()
        result = extract_waveform_metadata(df)
        assert "waveform_pattern" in result
        assert isinstance(result["waveform_pattern"], list)
        assert len(result["waveform_pattern"]) > 0

    def test_derived_scalars_present(self):
        """extract_waveform_metadata includes derived scalar keys."""
        from science_cli.core.metadata.analyzers.waveform import extract_waveform_metadata
        df = _make_stp_dataframe()
        result = extract_waveform_metadata(df)
        assert any(k.startswith("v_") for k in result)
        assert "repeat_pattern" in result
        assert "n_repeats" in result

    def test_empty_dataframe(self):
        """extract_waveform_metadata returns empty-ish dict for empty df."""
        from science_cli.core.metadata.analyzers.waveform import extract_waveform_metadata
        df = pd.DataFrame()
        result = extract_waveform_metadata(df)
        assert "waveform_pattern" in result
        assert result["waveform_pattern"] == []

    def test_repeated_trace(self):
        """extract_waveform_metadata handles repeated traces."""
        from science_cli.core.metadata.analyzers.waveform import extract_waveform_metadata
        df = _make_stp_dataframe(n_repeats=2)
        result = extract_waveform_metadata(df)
        assert result["repeat_pattern"] == "repeated"
        assert result["n_repeats"] == 2
        assert len(result["waveform_pattern"]) > 0
