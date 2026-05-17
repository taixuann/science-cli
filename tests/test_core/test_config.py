"""Tests for the core/config.py module."""

from pathlib import Path

from science_cli.core.config import (
    get_device_config,
    get_technique_patterns,
    get_default_device,
    get_projects_root,
    get_header_marker,
    get_merged_config,
    get_technique_config,
    get_file_naming_patterns,
    get_file_naming_grammar,
    invalidate_cache,
    list_technique_names,
    list_technique_devices,
    generate_default_config_yaml,
)


class TestConfigDefaults:
    """Config system should work with no config files (pure hardcoded defaults)."""

    def setup_method(self):
        invalidate_cache()

    def test_get_technique_patterns_returns_list(self):
        patterns = get_technique_patterns("iv-sweep")
        assert isinstance(patterns, list)
        assert len(patterns) >= 4

    def test_get_device_config_nonexistent_returns_none(self):
        cfg = get_device_config("iv-sweep", "nonexistent-device")
        assert cfg is None

    def test_get_default_device_returns_hardcoded(self):
        dev = get_default_device("iv-sweep")
        assert dev == "keithley-2400", f"Hardcoded default device should be 'keithley-2400', got '{dev}'"

    def test_get_projects_root_returns_path(self):
        root = get_projects_root()
        assert isinstance(root, Path)

    def test_get_header_marker_returns_empty_string(self):
        marker = get_header_marker("iv-sweep")
        assert marker == ""

    def test_get_technique_config_nonexistent_returns_none(self):
        cfg = get_technique_config("nonexistent-technique")
        assert cfg is None

    def test_get_file_naming_patterns_includes_hardcoded(self):
        patterns = get_file_naming_patterns()
        assert len(patterns) >= 1, f"Should have >=1 hardcoded patterns, got {len(patterns)}"
        assert any(p.get("id") == "rNcN" for p in patterns), "Should include rNcN pattern"

    def test_get_file_naming_grammar_includes_hardcoded(self):
        grammar = get_file_naming_grammar()
        assert grammar.get("separator") == "_"
        assert len(grammar.get("patterns", [])) >= 1, f"Should have >=1 hardcoded patterns, got {len(grammar.get('patterns', []))}"

    def test_list_technique_names_includes_hardcoded(self):
        names = list_technique_names()
        assert "iv-sweep" in names
        assert "ec-cv" in names
        assert "ec-eis" in names
        assert len(names) >= 10

    def test_list_technique_devices_iv_sweep(self):
        devices = list_technique_devices("iv-sweep")
        assert "keithley-2400" in devices

    def test_generate_default_config_is_valid(self):
        import yaml
        yaml_str = generate_default_config_yaml()
        cfg = yaml.safe_load(yaml_str)
        assert isinstance(cfg, dict)
        for key in ("projects_root", "theme", "techniques", "defaults"):
            assert key in cfg


class TestConfigWithProject:
    """Config system should correctly merge per-project config."""

    def setup_method(self):
        invalidate_cache()

    def test_project_patterns_prepended(self, tmp_project_with_config):
        patterns = get_technique_patterns("iv-sweep", tmp_project_with_config)
        assert "*_iv_*.csv" in patterns[0]

    def test_project_device_config(self, tmp_project_with_config):
        cfg = get_device_config("iv-sweep", "test-device", tmp_project_with_config)
        assert cfg is not None
        assert cfg["header_lines"] == 1
        assert cfg["columns"]["voltage"] == "Voltage (V)"

    def test_project_default_device(self, tmp_project_with_config):
        dev = get_default_device("iv-sweep", tmp_project_with_config)
        assert dev == "test-device"

    def test_project_naming_patterns(self, tmp_project_with_config):
        patterns = get_file_naming_patterns(tmp_project_with_config)
        assert len(patterns) >= 1
        assert "template" in patterns[0]
        assert "regex" in patterns[0]
        assert "fields" in patterns[0]

    def test_project_naming_grammar(self, tmp_project_with_config):
        grammar = get_file_naming_grammar(tmp_project_with_config)
        assert grammar["separator"] == "_"
        assert len(grammar["patterns"]) >= 1

    def test_project_technique_config(self, tmp_project_with_config):
        cfg = get_technique_config("iv-sweep", tmp_project_with_config)
        assert cfg is not None
        assert "patterns" in cfg
        assert "devices" in cfg

    def test_merged_config_includes_project(self, tmp_project_with_config):
        merged = get_merged_config(tmp_project_with_config)
        assert "techniques" in merged
        assert "iv-sweep" in merged["techniques"]
