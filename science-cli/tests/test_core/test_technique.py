"""Tests for core/technique.py."""

from science_cli.core.technique import (
    detect_technique,
    technique_label,
    BUILTIN_TECHNIQUES,
    parse_filename_grammar,
)


class TestTechniqueDetection:
    """detect_technique should correctly identify techniques from filenames."""

    def test_detect_cv(self):
        assert detect_technique("sample_CV.txt") == "ec-cv"

    def test_detect_eis(self):
        assert detect_technique("sample_EIS.csv") == "ec-eis"
        assert detect_technique("sample.mpt") == "ec-eis"

    def test_detect_iv_sweep(self):
        assert detect_technique("device_IV.txt") == "iv-sweep"

    def test_detect_ca(self):
        assert detect_technique("sample_CA.txt") == "ec-ca"

    def test_detect_breakdown(self):
        assert detect_technique("sample_bd_test.txt") == "iv-breakdown"

    def test_detect_leakage(self):
        assert detect_technique("leakage_data.txt") == "iv-leakage"

    def test_detect_endurance(self):
        assert detect_technique("endurance_test.csv") == "mem-endurance"

    def test_detect_unknown_returns_empty(self):
        assert detect_technique("unknown.xyz") == ""


class TestTechniqueLabel:
    """technique_label should return human-readable names."""

    def test_label_iv_sweep(self):
        assert "IV" in technique_label("iv-sweep")

    def test_label_cv(self):
        assert "CV" in technique_label("ec-cv")

    def test_label_unknown(self):
        assert technique_label("nonexistent") == "NONEXISTENT"


class TestBuiltinTechniques:
    """BUILTIN_TECHNIQUES dict should have all expected entries."""

    def test_has_expected_techniques(self):
        for key in ("iv-sweep", "ec-cv", "ec-eis", "ec-ca",
                     "mem-endurance", "mem-switching", "mem-retention"):
            assert key in BUILTIN_TECHNIQUES

    def test_count_at_least_10(self):
        assert len(BUILTIN_TECHNIQUES) >= 10

    def test_each_has_required_fields(self):
        for name, tech in BUILTIN_TECHNIQUES.items():
            assert hasattr(tech, "patterns"), f"{name} missing patterns"
            assert hasattr(tech, "label"), f"{name} missing label"


class TestParseFilenameGrammar:
    """parse_filename_grammar should extract fields from filenames."""

    def test_no_naming_grammar_returns_error(self):
        result = parse_filename_grammar("test.csv")
        assert "parse_error" in result

    def test_parse_with_project_config(self, tmp_project_with_config):
        result = parse_filename_grammar(
            "140526_PDA_r0c0_iv.csv", project_root=tmp_project_with_config,
        )
        assert result.get("date_code") == "140526"
        assert result.get("material") == "PDA"
        assert result.get("row") == "0"
        assert result.get("col") == "0"
        assert result.get("technique") == "iv"

    def test_no_match_returns_error(self, tmp_path):
        import yaml
        config = {
            "file_naming": {
                "separator": "_",
                "patterns": [{
                    "template": "{date_code}_{material}",
                    "regex": r"^(?P<date_code>\d{6})_(?P<material>[^_]+)\.\w+$",
                    "fields": {"date_code": {}, "material": {}},
                }],
            },
        }
        (tmp_path / "sci-config.yaml").write_text(yaml.dump(config))
        result = parse_filename_grammar("no_match.txt", project_root=tmp_path)
        assert "parse_error" in result
