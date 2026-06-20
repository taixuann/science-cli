"""Tests for the core/config.py module."""

from pathlib import Path

from science_cli.core.config import (
    get_device_config,
    get_device_type_grammar,
    get_device_type_grammar_config,
    get_technique_patterns,
    get_default_device,
    get_projects_root,
    get_header_marker,
    get_merged_config,
    get_merged_grammar,
    get_technique_config,
    get_file_naming_patterns,
    get_file_naming_grammar,
    get_metadata_config_for,
    invalidate_cache,
    list_technique_names,
    list_technique_devices,
    generate_default_config_yaml,
)
from science_cli.core.config_defaults import (
    generate_config_devices_yaml,
    generate_config_studies_yaml,
    generate_config_instruments_yaml,
    generate_config_template_yaml,
)
from science_cli.core.config_schema import (
    validate_devices_config,
    validate_studies_config,
    validate_instruments_config,
    validate_template_config,
    validate_all,
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

    def test_generate_devices_yaml_is_valid(self):
        import yaml
        yaml_str = generate_config_devices_yaml()
        cfg = yaml.safe_load(yaml_str)
        assert isinstance(cfg, dict)
        assert "device_types" in cfg
        assert "legacy_to_study" in cfg
        assert "studies" not in cfg, "studies should be in config-studies.yaml now"
        errors = validate_devices_config(cfg)
        assert errors == [], f"Validation errors: {errors}"

    def test_generate_studies_yaml_is_valid(self):
        import yaml
        yaml_str = generate_config_studies_yaml()
        cfg = yaml.safe_load(yaml_str)
        assert isinstance(cfg, dict)
        assert "studies" in cfg
        assert "iv" in cfg["studies"]
        assert "pulse" in cfg["studies"]
        assert "ec" in cfg["studies"]
        assert "raman" in cfg["studies"]
        assert "uv-vis" in cfg["studies"]
        assert "afm" in cfg["studies"]
        errors = validate_studies_config(cfg)
        assert errors == [], f"Validation errors: {errors}"

    def test_studies_yaml_has_v6_fields(self):
        """Verify v6 enhancements are present in generated studies config."""
        import yaml
        yaml_str = generate_config_studies_yaml()
        cfg = yaml.safe_load(yaml_str)

        # Check pulse study has v6 fields
        stp = cfg["studies"]["pulse"]["pulse-stp-decay"]
        assert "data_shape" in stp
        assert stp["data_shape"]["kind"] == "waveform_2d"
        assert "derived_metadata" in stp
        assert "v_set_v" in stp["derived_metadata"]
        assert "device_overrides" in stp
        assert "volatile-memristor" in stp["device_overrides"]

        # Check IV study has data_shape
        iv = cfg["studies"]["iv"]["iv-bipolar-sweep"]
        assert "data_shape" in iv
        assert iv["data_shape"]["kind"] == "trace_2d"

        # Check raman has spectrum_2d
        raman = cfg["studies"]["raman"]["raman-spectrum"]
        assert raman["data_shape"]["kind"] == "spectrum_2d"
        assert raman["data_shape"]["columns"] == ["wavelength_nm", "intensity"]

        # Check afm has image_2d
        afm = cfg["studies"]["afm"]["afm-topography"]
        assert afm["data_shape"]["kind"] == "image_2d"

    def test_generate_instruments_yaml_is_valid(self):
        import yaml
        yaml_str = generate_config_instruments_yaml()
        cfg = yaml.safe_load(yaml_str)
        assert isinstance(cfg, dict)
        assert "instruments" in cfg
        assert "keithley-2400" in cfg["instruments"]
        assert "keysight-b1500a" in cfg["instruments"]
        errors = validate_instruments_config(cfg)
        assert errors == [], f"Validation errors: {errors}"

    def test_generate_template_yaml_is_valid(self):
        import yaml
        yaml_str = generate_config_template_yaml()
        cfg = yaml.safe_load(yaml_str)
        assert isinstance(cfg, dict)
        assert "templates" in cfg
        assert "publication-nature" in cfg["templates"]
        errors = validate_template_config(cfg)
        assert errors == [], f"Validation errors: {errors}"

    def test_init_creates_modular_files(self, tmp_path):
        """Simulate 'config init' creating modular files in a temp dir."""
        import yaml
        from science_cli.core.config_defaults import (
            generate_config_devices_yaml,
            generate_config_studies_yaml,
            generate_config_instruments_yaml,
            generate_config_template_yaml,
        )
        files = {
            tmp_path / "config-devices.yaml": generate_config_devices_yaml(),
            tmp_path / "config-studies.yaml": generate_config_studies_yaml(),
            tmp_path / "config-instruments.yaml": generate_config_instruments_yaml(),
            tmp_path / "config-template.yaml": generate_config_template_yaml(),
        }
        for path, content in files.items():
            path.write_text(content)
            assert path.exists(), f"File not created: {path}"
        # Validate each file
        for path in files:
            cfg = yaml.safe_load(path.read_text())
            assert isinstance(cfg, dict), f"{path.name} is not valid YAML"
        # Validate combined
        combined = {}
        for path in files:
            combined.update(yaml.safe_load(path.read_text()) or {})
        errors = validate_all(combined)
        assert errors == [], f"Combined validation errors: {errors}"

    def test_migration_script(self, tmp_path):
        """Test migration script flow with a mock old config.yaml."""
        import yaml
        from science_cli.core.config_defaults import generate_config_devices_yaml
        old_config = tmp_path / "config.yaml"
        old_data = {
            "techniques": {
                "iv-sweep": {
                    "label": "IV Sweep",
                    "patterns": ["iv-sweep", "_IV"],
                    "grammar_codes": ["iv", "iv-sweep"],
                },
                "raman": {
                    "label": "Raman",
                    "patterns": ["_raman"],
                    "grammar_codes": ["raman"],
                },
            },
            "devices": {
                "keithley-2400": {
                    "label": "Keithley 2400",
                    "manufacturer": "Keithley/Tektronix",
                    "type": "sourcemeter",
                    "techniques": ["iv-sweep"],
                    "config": {"delimiter": "\t", "decimal": ".", "header_lines": 23},
                },
            },
            "file_naming": {
                "separator": "_",
                "patterns": [{"id": "rNcN", "template": "{a}_{b}", "description": "Test pattern", "regex": r"^test", "fields": ["a", "b"]}],
            },
        }
        with open(old_config, "w") as f:
            yaml.dump(old_data, f)

        from scripts.migrate_config_to_modular import extract_devices, extract_instruments, extract_grammar, extract_templates

        devices_data = extract_devices(old_data)
        instruments_data = extract_instruments(old_data)
        grammar_data = extract_grammar(old_data)
        templates_data = extract_templates(old_data)

        assert "studies" in devices_data
        assert len(devices_data["studies"]) > 0
        assert "instruments" in instruments_data
        assert "keithley-2400" in instruments_data["instruments"]
        assert "file_naming" in grammar_data
        assert "templates" in templates_data

        # Write extracted data
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        for fname, data in [
            ("config-devices.yaml", devices_data),
            ("config-instruments.yaml", instruments_data),
            ("config-grammar.yaml", grammar_data),
            ("config-template.yaml", templates_data),
        ]:
            path = out_dir / fname
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            assert path.exists()

        # Validate all output
        errors = validate_instruments_config(instruments_data)
        assert errors == [], f"Instrument validation errors: {errors}"
        errors = validate_grammar_config(grammar_data)
        assert errors == [], f"Grammar validation errors: {errors}"


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


class TestGrammarAccessors:
    """Grammar accessor functions for device-type and protocol grammar."""

    def setup_method(self):
        invalidate_cache()

    def test_get_device_type_grammar_memristor(self):
        patterns = get_device_type_grammar("memristor")
        assert len(patterns) >= 1
        assert patterns[0]["id"] == "crossbar-rNcN"
        assert "matrix" in patterns[0]["fields"]

    def test_get_device_type_grammar_junction(self):
        patterns = get_device_type_grammar("junction")
        assert len(patterns) >= 1
        assert patterns[0]["id"] == "junction-basic"
        assert "matrix" not in patterns[0]["fields"]

    def test_get_device_type_grammar_unknown(self):
        patterns = get_device_type_grammar("nonexistent")
        assert patterns == []

    def test_device_type_grammar_differs(self):
        mem = get_device_type_grammar("memristor")
        jun = get_device_type_grammar("junction")
        mem_fields = mem[0].get("fields", [])
        jun_fields = jun[0].get("fields", [])
        assert "matrix" in mem_fields
        assert "matrix" not in jun_fields

    def test_get_device_type_grammar_config(self):
        config = get_device_type_grammar_config()
        assert "memristor" in config
        assert "junction" in config
        assert "deposition" in config

    def test_get_protocol_grammar_empty(self, tmp_path):
        """Protocol without grammar section returns empty list."""
        from science_cli.core.config import get_protocol_grammar
        proto_yaml = tmp_path / "protocol" / "test" / "test.yaml"
        proto_yaml.parent.mkdir(parents=True)
        proto_yaml.write_text("name: test\ndevices: memristor\n")
        patterns = get_protocol_grammar(proto_yaml)
        assert patterns == []

    def test_get_protocol_grammar_with_patterns(self, tmp_path):
        """Protocol with grammar section returns patterns."""
        from science_cli.core.config import get_protocol_grammar
        import yaml
        data = {
            "name": "test",
            "grammar": {
                "patterns": [
                    {"id": "custom", "template": "{a}_{b}", "regex": r"test", "fields": ["a", "b"]},
                ],
            },
        }
        proto_yaml = tmp_path / "protocol" / "test" / "test.yaml"
        proto_yaml.parent.mkdir(parents=True)
        with open(proto_yaml, "w") as f:
            yaml.dump(data, f)
        patterns = get_protocol_grammar(proto_yaml)
        assert len(patterns) == 1
        assert patterns[0]["id"] == "custom"

    def test_get_merged_grammar_basic(self):
        """Merged grammar without extra params returns hardcoded defaults."""
        merged = get_merged_grammar()
        assert "patterns" in merged
        assert len(merged["patterns"]) >= 1

    def test_get_merged_grammar_with_device_type(self):
        """Device-type grammar adds patterns to merged grammar."""
        merged = get_merged_grammar(device_type="memristor")
        assert len(merged["patterns"]) >= 1
        # Device-type patterns should be in the merged set
        regexes = [p.get("regex", "") for p in merged["patterns"]]
        assert any("r\\\\d+c\\\\d+" in r or r"r\d+c\d+" in r for r in regexes)

    def test_get_merged_grammar_with_project(self, tmp_project_with_config):
        """Project-level grammar is included in merged grammar."""
        merged = get_merged_grammar(project_root=tmp_project_with_config)
        assert len(merged["patterns"]) >= 1
        # Project config has a minimal pattern
        regexes = [p.get("regex", "") for p in merged["patterns"]]
        assert any("date_code" in r for r in regexes)

    def test_get_device_type_grammar_config_includes_all(self):
        config = get_device_type_grammar_config()
        for dt in ("memristor", "junction", "deposition"):
            assert dt in config, f"Missing device type: {dt}"
            assert len(config[dt]) >= 1, f"Empty patterns for: {dt}"

    def test_write_protocol_grammar(self, tmp_path):
        """Write then read back protocol grammar patterns."""
        from science_cli.core.protocol import write_protocol_grammar
        from science_cli.core.config import get_protocol_grammar
        import yaml

        proto_yaml = tmp_path / "protocol" / "wtest" / "wtest.yaml"
        proto_yaml.parent.mkdir(parents=True)
        proto_yaml.write_text("name: wtest\ndevices: memristor\n")

        patterns = [
            {"id": "wtest-pattern", "template": "{a}_{b}", "regex": r"^test", "fields": ["a", "b"]},
        ]
        write_protocol_grammar(proto_yaml, patterns)

        read_back = get_protocol_grammar(proto_yaml)
        assert len(read_back) == 1
        assert read_back[0]["id"] == "wtest-pattern"

        # Verify the YAML was updated correctly
        with open(proto_yaml) as f:
            data = yaml.safe_load(f)
        assert "grammar" in data
        assert data["grammar"]["patterns"][0]["id"] == "wtest-pattern"
        assert data["name"] == "wtest"  # Preserved other fields


class TestGetMetadataConfigFor:
    """get_metadata_config_for resolves metadata config for (study, instrument)."""

    def setup_method(self):
        invalidate_cache()

    def test_returns_dict_for_valid_pair(self):
        """Returns a dict (possibly empty) for a valid study + instrument."""
        cfg = get_metadata_config_for("pulse:pulse-stp-decay", "keysight-b1500a")
        assert isinstance(cfg, dict)

    def test_returns_empty_for_unknown_study(self):
        """Returns empty dict when study is not in config."""
        cfg = get_metadata_config_for("nonexistent:study", "keysight-b1500a")
        assert cfg == {}

    def test_returns_empty_for_unknown_instrument(self):
        """Returns empty dict when instrument is not in config."""
        cfg = get_metadata_config_for("pulse:pulse-stp-decay", "nonexistent-instrument")
        assert cfg == {}

    def test_accepts_device_type_param(self):
        """device_type parameter is accepted (currently unused in resolution)."""
        cfg = get_metadata_config_for(
            "pulse:pulse-stp-decay", "keysight-b1500a", "volatile-memristor"
        )
        assert isinstance(cfg, dict)
