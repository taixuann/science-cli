"""Tests for per-study fzf column registry and helpers.

Covers ``STUDY_COLUMN_REGISTRY``, ``status_badge_for_file``,
``get_step_columns``, ``get_columns_for``, and ``build_fzf_display``
study-aware behavior (including device-type overrides).
"""

from pathlib import Path

from science_cli.core.fzf.columns import (
    STUDY_COLUMN_REGISTRY,
    _STUDY_BY_NAME,
    get_columns_for,
    get_step_columns,
    status_badge_for_file,
)
from science_cli.core.fzf.display import build_fzf_display


# ── Registry shape ───────────────────────────────────────────


def test_registry_keys_are_tuples():
    """Registry keys are (study, device_type) tuples."""
    for key in STUDY_COLUMN_REGISTRY:
        assert isinstance(key, tuple) and len(key) == 2, f"Key {key!r} is not a 2-tuple"


def test_registry_has_study_defaults():
    """Registry covers all current studies with device_type=None defaults."""
    expected_studies = {
        "pulse:pulse-stp-decay",
        "pulse:pulse-endurance",
        "pulse:pulse-ppf",
        "iv:iv-bipolar-sweep",
        "ec:ec-cv",
        "ec:ec-ca",
        "ec:ec-eis",
        "raman:raman-spectrum",
        "uv-vis:uv-vis-spectrum",
    }
    study_defaults = {study for study, device in STUDY_COLUMN_REGISTRY if device is None}
    assert study_defaults == expected_studies


def test_registry_has_device_overrides():
    """Registry has device-specific overrides for pulse-endurance."""
    assert ("pulse:pulse-endurance", "volatile-memristor") in STUDY_COLUMN_REGISTRY
    assert ("pulse:pulse-endurance", "non-volatile-memristor") in STUDY_COLUMN_REGISTRY


def test_backwards_compat_alias():
    """_STUDY_BY_NAME maps study name -> default columns."""
    assert "pulse:pulse-stp-decay" in _STUDY_BY_NAME
    assert "v_set_v" in _STUDY_BY_NAME["pulse:pulse-stp-decay"]


def test_registry_pulse_stp_has_waveform_keys():
    """STP-decay registry includes all pattern-waveform keys."""
    cols = STUDY_COLUMN_REGISTRY[("pulse:pulse-stp-decay", None)]
    for key in ("v_set_v", "v_read_v", "set_width_us", "read_width_us",
                "rise_us", "fall_us", "repeat_pattern"):
        assert key in cols, f"STP-decay missing {key}"


def test_registry_pulse_endurance_has_reset_keys():
    """Endurance default registry includes V_reset + reset_width + n_cycles."""
    cols = STUDY_COLUMN_REGISTRY[("pulse:pulse-endurance", None)]
    for key in ("v_set_v", "v_reset_v", "set_width_us", "reset_width_us",
                "read_width_us", "n_cycles", "repeat_pattern"):
        assert key in cols, f"endurance missing {key}"


def test_registry_iv_bipolar_has_sweep_keys():
    """IV bipolar registry includes sweep_pattern + compliance + step + delay."""
    cols = STUDY_COLUMN_REGISTRY[("iv:iv-bipolar-sweep", None)]
    for key in ("sweep_pattern", "v_set", "v_reset", "compliance_a",
                "step_v", "delay_s"):
        assert key in cols, f"iv-bipolar-sweep missing {key}"


def test_registry_ec_studies_have_electrochem_keys():
    """EC studies have appropriate metadata keys."""
    assert "v_min" in STUDY_COLUMN_REGISTRY[("ec:ec-cv", None)]
    assert "v_max" in STUDY_COLUMN_REGISTRY[("ec:ec-cv", None)]
    assert "scan_rate_mv_s" in STUDY_COLUMN_REGISTRY[("ec:ec-cv", None)]
    assert "v_step" in STUDY_COLUMN_REGISTRY[("ec:ec-ca", None)]
    assert "duration_s" in STUDY_COLUMN_REGISTRY[("ec:ec-ca", None)]
    assert "freq_min_hz" in STUDY_COLUMN_REGISTRY[("ec:ec-eis", None)]
    assert "freq_max_hz" in STUDY_COLUMN_REGISTRY[("ec:ec-eis", None)]


# ── get_columns_for ──────────────────────────────────────────


def test_get_columns_for_study_only():
    """get_columns_for returns study-level columns when no device override."""
    cols = get_columns_for("pulse:pulse-stp-decay")
    assert "v_set_v" in cols
    assert "v_read_v" in cols


def test_get_columns_for_study_device():
    """get_columns_for returns device-specific columns over study-level."""
    volatile_cols = get_columns_for("pulse:pulse-endurance", "volatile-memristor")
    nonvol_cols = get_columns_for("pulse:pulse-endurance", "non-volatile-memristor")
    # volatile shows v_read_v, non-volatile shows v_reset_v
    assert "v_read_v" in volatile_cols
    assert "v_reset_v" in nonvol_cols
    assert "v_reset_v" not in volatile_cols
    assert "v_read_v" not in nonvol_cols


def test_get_columns_for_fallback_to_study_default():
    """get_columns_for falls back to study default for unregistered device."""
    cols = get_columns_for("pulse:pulse-endurance", "some-unknown-device")
    # Should fall back to study-level default which has v_reset_v
    assert "v_reset_v" in cols
    assert "v_read_v" not in cols


def test_get_columns_for_fallback_to_empty():
    """get_columns_for returns [] for unknown study."""
    cols = get_columns_for("nonexistent:study")
    assert cols == []


def test_get_columns_for_explicit_none_device():
    """get_columns_for with device_type=None returns study default."""
    cols = get_columns_for("pulse:pulse-endurance", None)
    assert "v_reset_v" in cols


# ── status_badge_for_file ────────────────────────────────────


def test_status_badge_returns_empty_for_missing_file():
    assert status_badge_for_file("nope", None) == ""
    assert status_badge_for_file("nope", {}) == ""


def test_status_badge_returns_highlight_for_highlight_tag():
    assert status_badge_for_file("a/b/c.pdf", {"a/b/c.pdf": "highlight"}) == "★"


def test_status_badge_returns_star_for_star_tag():
    assert status_badge_for_file("a/b/c.pdf", {"a/b/c.pdf": "star"}) == "★"


def test_status_badge_returns_check_for_keep_tag():
    assert status_badge_for_file("a/b/c.pdf", {"a/b/c.pdf": "keep"}) == "✓"


def test_status_badge_returns_x_for_discard_tag():
    assert status_badge_for_file("a/b/c.pdf", {"a/b/c.pdf": "discard"}) == "✗"


def test_status_badge_returns_empty_for_clear_tag():
    assert status_badge_for_file("a/b/c.pdf", {"a/b/c.pdf": "clear"}) == ""


# ── get_step_columns ──────────────────────────────────────────


def test_get_step_columns_returns_empty_when_no_protocol(tmp_project):
    """No protocol.yaml → empty dict, not error."""
    result = get_step_columns(tmp_project, "missing_step")
    assert result == {}


def test_get_step_columns_returns_all_metadata_without_study(tmp_project):
    """Without study_name, returns full metadata dict (filtered to subset
    of keys actually present in metadata)."""
    proj = Path(tmp_project)
    (proj / "protocol.yaml").write_text(
        "steps:\n"
        "  - name: my_step\n"
        "    metadata:\n"
        "      v_set_v: 2.5\n"
        "      v_read_v: 0.5\n"
        "      other_field: noise\n"
    )
    result = get_step_columns(proj, "my_step")
    # No study_name filter → returns all metadata
    assert result.get("v_set_v") == 2.5
    assert result.get("v_read_v") == 0.5
    assert result.get("other_field") == "noise"


def test_get_step_columns_filters_to_registry_columns(tmp_project):
    """With study_name, filters to STUDY_COLUMN_REGISTRY columns."""
    proj = Path(tmp_project)
    (proj / "protocol.yaml").write_text(
        "steps:\n"
        "  - name: my_step\n"
        "    metadata:\n"
        "      v_set_v: 2.5\n"
        "      v_read_v: 0.5\n"
        "      set_width_us: 100\n"
        "      read_width_us: 50\n"
        "      irrelevant_field: should_be_filtered\n"
    )
    result = get_step_columns(
        proj, "my_step", "pulse:pulse-stp-decay"
    )
    assert "v_set_v" in result
    assert "v_read_v" in result
    assert "set_width_us" in result
    assert "read_width_us" in result
    assert "irrelevant_field" not in result


def test_get_step_columns_with_device_type(tmp_project):
    """get_step_columns accepts device_type and returns appropriate columns."""
    proj = Path(tmp_project)
    (proj / "protocol.yaml").write_text(
        "steps:\n"
        "  - name: my_step\n"
        "    metadata:\n"
        "      v_set_v: 2.5\n"
        "      v_read_v: 0.5\n"
        "      v_reset_v: 1.2\n"
        "      set_width_us: 100\n"
        "      read_width_us: 50\n"
        "      reset_width_us: 80\n"
        "      n_cycles: 1000\n"
        "      repeat_pattern: toggle\n"
    )
    # Volatile device → should show v_read_v, not v_reset_v
    result_volatile = get_step_columns(
        proj, "my_step", "pulse:pulse-endurance", "volatile-memristor"
    )
    assert "v_read_v" in result_volatile
    assert "v_reset_v" not in result_volatile

    # Non-volatile device → should show v_reset_v, not v_read_v
    result_nonvol = get_step_columns(
        proj, "my_step", "pulse:pulse-endurance", "non-volatile-memristor"
    )
    assert "v_reset_v" in result_nonvol
    assert "v_read_v" not in result_nonvol


def test_get_step_columns_returns_empty_for_unknown_step(tmp_project):
    """Step not found → empty dict."""
    proj = Path(tmp_project)
    (proj / "protocol.yaml").write_text("steps:\n  - name: other\n")
    result = get_step_columns(proj, "missing")
    assert result == {}


# ── build_fzf_display study-aware ─────────────────────────────


def test_build_fzf_display_legacy_signature_unchanged():
    """Backward compat — no metadata, no study_name, no badge."""
    line = build_fzf_display("proto1", "step1", "file.csv")
    assert "proto1" in line
    assert "step1" in line
    assert "file.csv" in line


def test_build_fzf_display_status_badge_prepends():
    """status_badge='★' prepends '★' to the line."""
    line = build_fzf_display(
        "p1", "s1", "f.csv", status_badge="★"
    )
    assert line.startswith("★")


def test_build_fzf_display_filters_metadata_to_study_columns():
    """When study_name is registered, only those columns appear."""
    metadata = {
        "v_set_v": 2.5, "v_read_v": 0.5, "set_width_us": 100,
        "read_width_us": 50, "irrelevant": "drop_me",
    }
    line = build_fzf_display(
        "p1", "s1", "f.csv",
        metadata=metadata, study_name="pulse:pulse-stp-decay",
    )
    assert "2.5" in line
    assert "0.5" in line
    assert "drop_me" not in line


def test_build_fzf_display_unregistered_study_shows_all_metadata():
    """When study_name is not in registry, all metadata is shown."""
    metadata = {"a": 1, "b": 2, "c": 3}
    line = build_fzf_display(
        "p1", "s1", "f.csv",
        metadata=metadata, study_name="unknown:study",
    )
    assert "1" in line
    assert "2" in line
    assert "3" in line


def test_build_fzf_display_no_protocol_column_when_show_protocol_false():
    """show_protocol=False omits protocol column."""
    line = build_fzf_display(
        "p1", "s1", "f.csv", show_protocol=False,
    )
    assert "p1" not in line
    assert "s1" in line
    assert "f.csv" in line


def test_build_fzf_display_combines_badge_and_study_metadata():
    """Badge + study columns + protocol/step/filename all in one line."""
    metadata = {
        "v_set_v": 2.5, "v_read_v": 0.5, "set_width_us": 100,
        "read_width_us": 50, "rise_us": 2.4, "fall_us": 2.3,
        "repeat_pattern": "single",
    }
    line = build_fzf_display(
        "p1", "s1", "f.csv",
        metadata=metadata, study_name="pulse:pulse-stp-decay",
        status_badge="✓",
    )
    assert line.startswith("✓")
    assert "p1" in line
    assert "s1" in line
    assert "f.csv" in line
    assert "2.5" in line
    assert "single" in line


def test_build_fzf_display_device_type_override():
    """device_type param selects device-specific columns in display."""
    metadata = {
        "v_set_v": 2.5, "v_read_v": 0.5, "v_reset_v": 1.2,
        "set_width_us": 100, "read_width_us": 50, "reset_width_us": 80,
        "n_cycles": 1000, "repeat_pattern": "toggle",
    }
    # Volatile: should show v_read_v, not v_reset_v
    line_volatile = build_fzf_display(
        "p1", "s1", "f.csv",
        metadata=metadata,
        study_name="pulse:pulse-endurance",
        device_type="volatile-memristor",
    )
    assert "0.5" in line_volatile  # v_read_v
    assert "1.2" not in line_volatile  # v_reset_v should not appear

    # Non-volatile: should show v_reset_v, not v_read_v
    line_nonvol = build_fzf_display(
        "p1", "s1", "f.csv",
        metadata=metadata,
        study_name="pulse:pulse-endurance",
        device_type="non-volatile-memristor",
    )
    assert "1.2" in line_nonvol  # v_reset_v
    assert "0.5" not in line_nonvol  # v_read_v should not appear
