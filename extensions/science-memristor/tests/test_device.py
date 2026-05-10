"""Tests for crossbar device data models, YAML I/O, validation, and CLI."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from science_memristor.device import (
    SweepSegment,
    FileEntry,
    TechniqueGroup,
    MatrixPoint,
    DeviceGeometry,
    DeviceConfig,
    read_devices,
    write_devices,
    validate,
    sync_devices,
    generate_device_grid,
    generate_rich_grid,
    find_orphaned_files,
    extract_material_batch,
    MATERIAL_TAG_PREFIX,
)
from science_memristor.device_cli import main, _add_material_tag, _format_material_display


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def step_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_config():
    device = DeviceGeometry(
        id="test-device",
        label="Test 2x2",
        rows=2,
        cols=2,
        cell_area_um2=10000,
    )
    points = [
        MatrixPoint(
            row=0,
            col=0,
            techniques={
                "iv": TechniqueGroup(
                    technique="iv",
                    files=[
                        FileEntry(
                            file="r0c0_iv_set.txt",
                            sweep_order=1,
                            sweep_type="SET",
                            sweep=[{"direction": "forward", "sweep_rate_v_s": 0.1}],
                        ),
                        FileEntry(
                            file="r0c0_iv_reset.txt",
                            sweep_order=2,
                            sweep_type="RESET",
                        ),
                    ],
                ),
                "endurance": TechniqueGroup(
                    technique="endurance",
                    files=[FileEntry(file="r0c0_endurance.txt")],
                ),
            },
            tags=["forming", "pristine"],
        ),
        MatrixPoint(
            row=0,
            col=1,
            techniques={
                "iv": TechniqueGroup(
                    technique="iv",
                    files=[FileEntry(file="r0c1_iv.txt")],
                ),
            },
        ),
    ]
    return DeviceConfig(device=device, points=points)


# ── Dataclass tests ─────────────────────────────────────────


class TestSweepSegment:
    def test_to_dict(self):
        s = SweepSegment("forward", 0.1, 2.0, 20.0)
        d = s.to_dict()
        assert d["direction"] == "forward"
        assert d["sweep_rate_v_s"] == 0.1
        assert d["voltage_range"] == 2.0
        assert d["duration_s"] == 20.0


class TestFileEntry:
    def test_is_sweep_detected(self):
        fe = FileEntry(file="test.txt", sweep=[])
        assert not fe.is_sweep_detected
        fe.sweep = [{"direction": "forward"}]
        assert fe.is_sweep_detected

    def test_to_dict_omits_none(self):
        fe = FileEntry(file="test.txt")
        d = fe.to_dict()
        assert d == {"file": "test.txt"}

    def test_to_dict_optional_fields(self):
        fe = FileEntry(
            file="test.txt",
            sweep_order=1,
            sweep_type="SET",
            temperature=300.0,
        )
        d = fe.to_dict()
        assert d["sweep_order"] == 1
        assert d["sweep_type"] == "SET"
        assert d["temperature"] == 300.0

    def test_to_dict_includes_extra(self):
        fe = FileEntry(file="test.txt", extra={"custom_key": "custom_val"})
        d = fe.to_dict()
        assert d["custom_key"] == "custom_val"
        assert d["file"] == "test.txt"


class TestTechniqueGroup:
    def test_primary_file(self):
        tg = TechniqueGroup(technique="iv")
        assert tg.primary_file is None
        fe = FileEntry(file="a.txt")
        tg.files.append(fe)
        assert tg.primary_file is fe

    def test_file_count(self):
        tg = TechniqueGroup(technique="iv")
        assert tg.file_count == 0
        tg.files.append(FileEntry(file="a.txt"))
        assert tg.file_count == 1

    def test_sorted_files(self):
        tg = TechniqueGroup(
            technique="iv",
            files=[
                FileEntry(file="b.txt", sweep_order=2),
                FileEntry(file="a.txt", sweep_order=1),
                FileEntry(file="c.txt", sweep_order=None),
            ],
        )
        sorted_f = tg.sorted_files()
        assert sorted_f[0].file == "a.txt"
        assert sorted_f[1].file == "b.txt"
        assert sorted_f[2].file == "c.txt"


class TestMatrixPoint:
    def test_position(self):
        pt = MatrixPoint(row=3, col=7)
        assert pt.position == (3, 7)

    def test_has_technique(self):
        pt = MatrixPoint(
            row=0, col=0,
            techniques={"iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")])},
        )
        assert pt.has_technique("iv")
        assert not pt.has_technique("endurance")

    def test_get_files(self):
        pt = MatrixPoint(
            row=0, col=0,
            techniques={"iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")])},
        )
        assert len(pt.get_files("iv")) == 1
        assert pt.get_files("endurance") == []

    def test_technique_names(self):
        pt = MatrixPoint(
            row=0, col=0,
            techniques={
                "iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")]),
                "endurance": TechniqueGroup(technique="endurance", files=[]),
            },
        )
        assert pt.technique_names == ["iv"]

    def test_total_files(self):
        tg1 = TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt"), FileEntry(file="b.txt")])
        tg2 = TechniqueGroup(technique="endurance", files=[FileEntry(file="c.txt")])
        pt = MatrixPoint(row=0, col=0, techniques={"iv": tg1, "endurance": tg2})
        assert pt.total_files == 3

    def test_is_measured(self):
        pt = MatrixPoint(row=0, col=0)
        assert not pt.is_measured
        pt.techniques["iv"] = TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")])
        assert pt.is_measured


class TestDeviceGeometry:
    def test_total_cells(self):
        dg = DeviceGeometry(id="t", label="t", rows=4, cols=8)
        assert dg.total_cells == 32

    def test_cell_label_default(self):
        dg = DeviceGeometry(id="t", label="t", rows=2, cols=2)
        assert dg.cell_label(0, 1) == "r0c1"

    def test_cell_label_custom(self):
        dg = DeviceGeometry(
            id="t", label="t", rows=2, cols=2,
            row_labels=["WL0", "WL1"],
            col_labels=["BL0", "BL1"],
        )
        assert dg.cell_label(0, 0) == "WL0/BL0"
        assert dg.cell_label(1, 1) == "WL1/BL1"


class TestDeviceConfig:
    def test_get_point(self, sample_config):
        pt = sample_config.get_point(0, 0)
        assert pt is not None
        assert pt.row == 0
        assert pt.col == 0

    def test_get_point_missing(self, sample_config):
        assert sample_config.get_point(1, 1) is None

    def test_get_row(self, sample_config):
        row = sample_config.get_row(0)
        assert len(row) == 2
        assert row[0].col == 0
        assert row[1].col == 1

    def test_get_col(self, sample_config):
        col = sample_config.get_col(0)
        assert len(col) == 1
        assert col[0].row == 0

    def test_get_points_with_technique(self, sample_config):
        pts = sample_config.get_points_with_technique("endurance")
        assert len(pts) == 1
        assert pts[0].position == (0, 0)

    def test_get_all_files(self, sample_config):
        files = sample_config.get_all_files("iv")
        assert len(files) == 3  # r0c0 has 2, r0c1 has 1

    def test_measured_cells(self, sample_config):
        assert sample_config.measured_cells == 2

    def test_missing_cells(self, sample_config):
        missing = sample_config.missing_cells
        assert (1, 0) in missing
        assert (1, 1) in missing
        assert (0, 0) not in missing
        assert (0, 1) not in missing

    def test_technique_coverage(self, sample_config):
        cov = sample_config.technique_coverage
        assert cov.get("iv", 0) == 2
        assert cov.get("endurance", 0) == 1
        assert "retention" not in cov

    def test_total_files(self, sample_config):
        assert sample_config.total_files == 4

    def test_file_map(self, sample_config):
        fm = sample_config.file_map
        assert "r0c0_iv_set.txt" in fm
        assert fm["r0c0_iv_set.txt"] == (0, 0, "iv")


# ── YAML round-trip tests ───────────────────────────────────


class TestYamlRoundTrip:
    def test_write_then_read(self, step_dir, sample_config):
        write_devices(step_dir, sample_config)
        assert (step_dir / "devices.yaml").exists()

        loaded = read_devices(step_dir)
        assert loaded is not None
        assert loaded.device.id == "test-device"
        assert loaded.device.rows == 2
        assert loaded.device.cols == 2
        assert loaded.measured_cells == 2
        assert loaded.total_files == 4

    def test_round_trip_preserves_data(self, step_dir, sample_config):
        write_devices(step_dir, sample_config)
        loaded = read_devices(step_dir)

        pt = loaded.get_point(0, 0)
        assert pt is not None
        assert len(pt.techniques["iv"].files) == 2
        assert pt.techniques["iv"].files[0].sweep_type == "SET"
        assert pt.techniques["iv"].files[0].sweep_order == 1
        assert pt.techniques["iv"].files[1].sweep_type == "RESET"
        assert pt.tags == ["forming", "pristine"]

        pt2 = loaded.get_point(0, 1)
        assert pt2 is not None
        assert len(pt2.techniques["iv"].files) == 1

    def test_round_trip_empty(self, step_dir):
        config = DeviceConfig(
            device=DeviceGeometry(id="e", label="Empty", rows=1, cols=1),
            points=[],
        )
        write_devices(step_dir, config)
        loaded = read_devices(step_dir)
        assert loaded is not None
        assert loaded.measured_cells == 0

    def test_missing_yaml(self, step_dir):
        loaded = read_devices(step_dir)
        assert loaded is None

    def test_meta_generated(self, step_dir, sample_config):
        write_devices(step_dir, sample_config)
        with open(step_dir / "devices.yaml") as f:
            data = yaml.safe_load(f)
        assert "_meta" in data
        assert data["_meta"]["total_cells"] == 4
        assert data["_meta"]["measured_cells"] == 2


# ── Validation tests ────────────────────────────────────────


class TestValidation:
    def test_valid_config(self, sample_config):
        issues = validate(sample_config)
        assert len(issues) == 0

    def test_empty_device_id(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="", label="", rows=1, cols=1),
            points=[],
        )
        issues = validate(config)
        assert any("device.id is empty" in i for i in issues)

    def test_empty_device_label(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="", rows=1, cols=1),
            points=[],
        )
        issues = validate(config)
        assert any("device.label is empty" in i for i in issues)

    def test_invalid_dimensions(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=0, cols=0),
            points=[],
        )
        issues = validate(config)
        assert any("rows" in i for i in issues)
        assert any("cols" in i for i in issues)

    def test_out_of_bounds_point(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[MatrixPoint(row=5, col=0)],
        )
        issues = validate(config)
        assert any("out of bounds" in i for i in issues)

    def test_duplicate_position(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0),
                MatrixPoint(row=0, col=0),
            ],
        )
        issues = validate(config)
        assert any("Duplicate position" in i for i in issues)

    def test_duplicate_sweep_order(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(
                    row=0, col=0,
                    techniques={
                        "iv": TechniqueGroup(
                            technique="iv",
                            files=[
                                FileEntry(file="a.txt", sweep_order=1),
                                FileEntry(file="b.txt", sweep_order=1),
                            ],
                        ),
                    },
                ),
            ],
        )
        issues = validate(config)
        assert any("duplicate sweep_order" in i for i in issues)

    def test_unknown_technique_warning(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(
                    row=0, col=0,
                    techniques={
                        "cv": TechniqueGroup(
                            technique="cv",
                            files=[FileEntry(file="a.txt")],
                        ),
                    },
                ),
            ],
        )
        issues = validate(config)
        assert any("unknown technique" in i for i in issues)

    def test_empty_filename(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(
                    row=0, col=0,
                    techniques={
                        "iv": TechniqueGroup(
                            technique="iv",
                            files=[FileEntry(file="")],
                        ),
                    },
                ),
            ],
        )
        issues = validate(config)
        assert any("empty filename" in i for i in issues)

    def test_technique_with_no_files(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(
                    row=0, col=0,
                    techniques={
                        "iv": TechniqueGroup(technique="iv", files=[]),
                    },
                ),
            ],
        )
        issues = validate(config)
        assert any("no files" in i for i in issues)


# ── Grid display tests ──────────────────────────────────────


class TestGrid:
    def test_empty_grid(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[],
        )
        grid = generate_device_grid(config)
        assert "T1" in grid
        assert "T2" in grid
        assert "B1" in grid
        assert "B2" in grid
        assert "----" in grid
        assert "Legend" in grid

    def test_grid_with_data(self, sample_config):
        grid = generate_device_grid(sample_config)
        assert "I" in grid
        assert "E" in grid
        assert "Legend" in grid


# ── CLI tests ───────────────────────────────────────────────


def _patch_protocol_dir(step_dir):
    """Context manager that patches _resolve_protocol_dir to return step_dir."""
    from science_memristor import device_cli as dc_mod
    return patch.object(dc_mod, "_resolve_protocol_dir", return_value=Path(step_dir))


class TestCLI:
    def test_init(self, step_dir):
        test_args = [
            "mem-device", "init",
            "--size", "2x2",
        ]
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", test_args):
            main()
        assert (step_dir / "devices.yaml").exists()

    def test_init_idempotent(self, step_dir):
        test_args = [
            "mem-device", "init",
            "--size", "2x2",
        ]
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", test_args):
            main()
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):
                main()

    def test_ls_no_file(self, step_dir):
        test_args = ["mem-device", "ls", "--step-dir", str(step_dir)]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):
                main()

    def test_init_then_ls(self, step_dir):
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", [
            "mem-device", "init",
            "--size", "2x2",
        ]):
            main()
        with patch.object(sys, "argv", [
            "mem-device", "ls", "--step-dir", str(step_dir),
        ]):
            main()

    def test_add_pattern(self, step_dir):
        """Batch regex assignment via --pattern."""
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", [
            "mem-device", "init",
            "--size", "2x2",
        ]):
            main()
        # Create a test file with r0c0 position in the name
        (step_dir / "0505_Test_r0c0_iv_set.txt").write_text("dummy")
        with patch.object(sys, "argv", [
            "mem-device", "add",
            "--pattern", r'r(\d+)c(\d+)',
            "--step-dir", str(step_dir),
        ]):
            main()
        # Verify the file was assigned to r0c0 with technique iv
        loaded = read_devices(step_dir)
        pt = loaded.get_point(0, 0)
        assert pt is not None
        assert pt.has_technique("iv")

    def test_validate_ok(self, step_dir):
        """Validation of a valid config produces no issues."""
        (step_dir / "a.txt").write_text("dummy")
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[MatrixPoint(row=0, col=0, techniques={
                "iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")]),
            })],
        )
        issues = validate(config, protocol_dir=step_dir)
        assert len(issues) == 0

    def test_validate_fail(self, step_dir):
        """Validation of an invalid config produces issues."""
        config = DeviceConfig(
            device=DeviceGeometry(id="", label="", rows=0, cols=0),
            points=[],
        )
        issues = validate(config, protocol_dir=step_dir)
        assert len(issues) > 0

    def test_stats_removed(self, step_dir):
        """stats subcommand was removed — verify it's no longer available."""
        from science_memristor.device_cli import build_parser
        p = build_parser()
        actions = [a for a in p._actions if hasattr(a, 'choices') and a.choices]
        for a in actions:
            assert "stats" not in a.choices

    def test_rm_point(self, step_dir):
        """Remove an entire matrix point with --matrix --confirm."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[MatrixPoint(row=0, col=0, techniques={
                "iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")]),
            })],
        )
        write_devices(step_dir, config)
        with patch.object(sys, "argv", [
            "mem-device", "rm",
            "--matrix", "r0c0",
            "--confirm",
            "--step-dir", str(step_dir),
        ]):
            main()
        loaded = read_devices(step_dir)
        pt = loaded.get_point(0, 0)
        assert pt is None

    def test_init_default_id(self, step_dir):
        with _patch_protocol_dir(step_dir), patch.object(sys, "argv", [
            "mem-device", "init",
            "--size", "4x4",
        ]):
            main()
        loaded = read_devices(step_dir)
        assert loaded.device.id == "crossbar-4x4"

    def test_ls_matrix(self, step_dir):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[MatrixPoint(row=0, col=0, techniques={
                "iv": TechniqueGroup(technique="iv", files=[FileEntry(file="a.txt")]),
                "endurance": TechniqueGroup(
                    technique="endurance", files=[FileEntry(file="b.txt")],
                ),
            })],
        )
        write_devices(step_dir, config)
        with patch.object(sys, "argv", [
            "mem-device", "ls", "--matrix", "--step-dir", str(step_dir),
        ]):
            main()  # Should not raise

    def test_ls_matrix_with_material_filter(self, step_dir):
        """--material flag filters matrix to single material group."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[MatrixPoint(row=0, col=0, techniques={
                "iv": TechniqueGroup(technique="iv", files=[
                    FileEntry(file="0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv"),
                ]),
            }, tags=["material:Ta-PDA-ITO(1)"])],
        )
        write_devices(step_dir, config)
        with patch.object(sys, "argv", [
            "mem-device", "ls", "--matrix",
            "--material", "Ta-PDA-ITO(1)",
            "--step-dir", str(step_dir),
        ]):
            main()  # Should not raise


# ── Material / batch extraction tests ────────────────────────


class TestMaterialBatch:
    def test_extract_with_batch(self):
        result = extract_material_batch(
            "0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv"
        )
        assert result == ("Ta-PDAc-ITO", "1")

    def test_extract_with_batch_2(self):
        result = extract_material_batch(
            "0605_Ta-PDAc-ITO(2)_b1-t1_IV-DC_f_01.csv"
        )
        assert result == ("Ta-PDAc-ITO", "2")

    def test_extract_q_variant(self):
        result = extract_material_batch(
            "0605_Ta-PDAq-ITO(1)_b1-t1_IV-DC_f_01.csv"
        )
        assert result == ("Ta-PDAq-ITO", "1")

    def test_extract_base_material(self):
        result = extract_material_batch(
            "0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv"
        )
        assert result == ("Ta-PDA-ITO", "1")

    def test_extract_non_canonical_returns_none(self):
        result = extract_material_batch("random_file.csv")
        assert result is None

    def test_extract_no_batch(self):
        """Material without (N) batch suffix."""
        result = extract_material_batch(
            "0505_Ta-PDA-ITO_b1-t1_IV-DC_uc_01.csv"
        )
        assert result == ("Ta-PDA-ITO", "")


class TestAddMaterialTag:
    def test_adds_single_tag(self):
        pt = MatrixPoint(row=0, col=0)
        _add_material_tag(pt, "0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv")
        assert pt.tags == ["material:Ta-PDAc-ITO(1)"]

    def test_deduplicates(self):
        pt = MatrixPoint(row=0, col=0)
        _add_material_tag(pt, "0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv")
        _add_material_tag(pt, "0605_Ta-PDAc-ITO(1)_b3-t1_IV-DC_f_01.csv")
        assert pt.tags == ["material:Ta-PDAc-ITO(1)"]

    def test_adds_multiple_materials(self):
        pt = MatrixPoint(row=0, col=0)
        _add_material_tag(pt, "0605_Ta-PDAc-ITO(1)_b1-t1_IV-DC_f_01.csv")
        _add_material_tag(pt, "0605_Ta-PDAq-ITO(1)_b1-t1_IV-DC_f_01.csv")
        assert set(pt.tags) == {
            "material:Ta-PDAc-ITO(1)",
            "material:Ta-PDAq-ITO(1)",
        }

    def test_skips_non_canonical(self):
        pt = MatrixPoint(row=0, col=0, tags=["existing"])
        _add_material_tag(pt, "not_matching.csv")
        assert pt.tags == ["existing"]


class TestFormatMaterialDisplay:
    def test_with_batch(self):
        assert _format_material_display("Ta-PDA-ITO(1)") == "Ta-PDA-ITO (batch 1)"

    def test_without_batch(self):
        assert _format_material_display("Ta-PDA-ITO") == "Ta-PDA-ITO"

    def test_multi_digit_batch(self):
        assert _format_material_display("Material(42)") == "Material (batch 42)"


class TestGetPointsByMaterial:
    def test_groups_by_tags(self):
        """Points with material tags are grouped correctly."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="a.txt"),
                    ]),
                }, tags=["material:Ta-PDA-ITO(1)"]),
                MatrixPoint(row=0, col=1, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="b.txt"),
                    ]),
                }, tags=["material:Ta-PDAc-ITO(1)"]),
            ],
        )
        groups = config.get_points_by_material()
        assert set(groups.keys()) == {"Ta-PDA-ITO(1)", "Ta-PDAc-ITO(1)"}
        assert len(groups["Ta-PDA-ITO(1)"]) == 1
        assert groups["Ta-PDA-ITO(1)"][0].position == (0, 0)
        assert len(groups["Ta-PDAc-ITO(1)"]) == 1

    def test_point_in_multiple_groups(self):
        """A point with multiple material tags appears in every group."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="a.txt"),
                    ]),
                }, tags=["material:Ta-PDA-ITO(1)", "material:Ta-PDAc-ITO(1)"]),
            ],
        )
        groups = config.get_points_by_material()
        assert len(groups["Ta-PDA-ITO(1)"]) == 1
        assert len(groups["Ta-PDAc-ITO(1)"]) == 1

    def test_fallback_to_filenames(self):
        """Points without material tags fall back to filename scanning."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="0505_Ta-PDA-ITO(1)_b1-t1_IV-DC_uc_01.csv"),
                    ]),
                }),
            ],
        )
        groups = config.get_points_by_material()
        assert "Ta-PDA-ITO(1)" in groups
        assert len(groups["Ta-PDA-ITO(1)"]) == 1

    def test_empty_when_no_data(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[],
        )
        groups = config.get_points_by_material()
        assert groups == {}


class TestGridWithMaterial:
    """Tests for grid generation with material filtering."""

    def test_grid_with_occupied_filter(self):
        """Only occupied positions show technique letters."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="a.txt"),
                    ]),
                }),
                MatrixPoint(row=1, col=1, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="b.txt"),
                    ]),
                }),
            ],
        )
        # Only show (0, 0) as occupied
        grid = generate_device_grid(config, occupied={(0, 0)})
        assert "I---" in grid  # r0c0 should show I (IV technique)
        # r1c1 should be "----" since it's not in the occupied set
        # Verify the grid shows "----" in the r1c1 position
        lines = grid.split("\n")
        # Row T1 (i=0, bottom row) should have r0c0=I---, r0c1=----
        t1_line = [l for l in lines if l.startswith("T1")][0]
        assert "I---" in t1_line  # occupied
        assert "----" in t1_line  # not occupied in the same row at col 1

    def test_grid_with_technique_filter(self):
        """When technique is specified, only that technique's letter appears."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=1, cols=1),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="a.txt"),
                    ]),
                    "endurance": TechniqueGroup(technique="endurance", files=[
                        FileEntry(file="b.txt"),
                    ]),
                }),
            ],
        )
        grid_all = generate_device_grid(config)
        assert "IE--" in grid_all  # shows both I and E

        grid_iv = generate_device_grid(config, technique="iv")
        assert "I" in grid_iv and "E" not in grid_iv.replace("Legend", "").replace("T1", "")

    def test_grid_with_title(self):
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=1, cols=1),
            points=[],
        )
        grid = generate_device_grid(config, title="Custom Title")
        assert "Custom Title" in grid

    def test_rich_grid_with_occupied(self):
        """Rich grid with occupied filter should not crash."""
        config = DeviceConfig(
            device=DeviceGeometry(id="x", label="x", rows=2, cols=2),
            points=[
                MatrixPoint(row=0, col=0, techniques={
                    "iv": TechniqueGroup(technique="iv", files=[
                        FileEntry(file="a.txt"),
                    ]),
                }),
            ],
        )
        table = generate_rich_grid(config, occupied={(0, 0)}, title="Filtered")
        assert table is not None
        assert table.title == "Filtered"


# ── Plotting tests ──────────────────────────────────────────


class TestReadIvCsv:
    """Tests for reading IV data from CSV files."""

    def test_basic_bi_bv(self, temp_csv):
        """Read a standard Time,BI,BV CSV."""
        header = "Time,BI,BV\n"
        rows = "0.0,1e-9,0.0\n0.1,2e-8,0.1\n0.2,3e-7,0.2\n"
        _write_csv(temp_csv, header + rows)

        voltage, current, info = plotting.read_iv_csv(str(temp_csv))
        assert len(voltage) == 3
        assert len(current) == 3
        assert info["voltage_col"] == "BV"
        assert info["current_col"] == "BI"

    def test_with_metadata_trailer(self, temp_csv):
        """CSV with metadata lines after numeric data."""
        lines = [
            "Time,BI,BV",
            "0.0,1e-9,0.0",
            "0.1,2e-8,0.1",
            "0.2,3e-7,0.2",
            "==================================",
            "IV_C_B1-T1_0n-11",
            "==================================",
            "",
            "Test Name,res2t#1@1",
            "Mode,Sweeping",
            "Device Terminal,B,A",
            "Name,BV,N/A",
            "Stop,-3,N/A",
        ]
        _write_csv(temp_csv, "\n".join(lines))

        voltage, current, info = plotting.read_iv_csv(str(temp_csv))
        assert len(voltage) == 3
        assert voltage[0] == 0.0
        assert current[0] == 1e-9

    def test_voltage_current_headers(self, temp_csv):
        """Read with 'Voltage (V)' and 'Current (A)' headers."""
        header = "Time,Voltage (V),Current (A)\n"
        rows = "0.0,0.0,1e-9\n0.1,0.5,2e-8\n"
        _write_csv(temp_csv, header + rows)

        voltage, current, info = plotting.read_iv_csv(str(temp_csv))
        assert info["voltage_col"] == "Voltage (V)"
        assert info["current_col"] == "Current (A)"

    def test_empty_file(self, temp_csv):
        temp_csv.write_text("")
        with pytest.raises(ValueError, match="Empty"):
            plotting.read_iv_csv(str(temp_csv))

    def test_no_data_rows(self, temp_csv):
        temp_csv.write_text("Time,BI,BV\n")
        with pytest.raises(ValueError, match="No valid"):
            plotting.read_iv_csv(str(temp_csv))


class TestBuildPlotFilename:
    """Tests for plot filename construction."""

    def test_standard(self):
        name = plotting.build_plot_filename(0, 0, "Ta-PDAc-ITO(1)", "f", 1)
        assert name == "iv_r0c0_Ta-PDAc-ITO(1)_f_01.svg"

    def test_uncategorized(self):
        name = plotting.build_plot_filename(1, 2, "Ta-PDA-ITO(1)", "uc", 5)
        assert name == "iv_r1c2_Ta-PDA-ITO(1)_uc_05.svg"

    def test_zero_padded(self):
        name = plotting.build_plot_filename(0, 0, "Mat", "f", 99)
        assert name == "iv_r0c0_Mat_f_99.svg"

    def test_sanitizes_material(self):
        name = plotting.build_plot_filename(0, 0, "a/b c", "f", 1)
        assert "/" not in name
        assert " " not in name


class TestBuildPlotTitle:
    """Tests for plot title construction."""

    def test_standard(self):
        sweep = [
            {"direction": "forward", "sweep_rate_v_s": 0.10, "voltage_range": 2.0},
        ]
        title = plotting.build_plot_title(1, sweep, "f")
        assert "#01" in title
        assert "0.10 V/s" in title
        assert "f" in title or "fwd" in title.lower() or "→" in title

    def test_none_sweep_type(self):
        sweep: list = []
        title = plotting.build_plot_title(2, sweep, "")
        assert "#02" in title
        assert "uc" in title

    def test_empty_sweep_falls_back_to_type(self):
        title = plotting.build_plot_title(5, [], "sp")
        assert "#05" in title
        assert "sp" in title


class TestShouldUseLogScale:
    """Tests for log-scale auto-detection."""

    def test_wide_range(self):
        import numpy as np
        current = np.array([1e-12, 1e-10, 1e-8, 1e-6])
        assert plotting._should_use_log_scale(current)

    def test_narrow_range(self):
        import numpy as np
        current = np.array([1e-6, 2e-6, 3e-6])
        assert not plotting._should_use_log_scale(current)

    def test_near_zero_excluded(self):
        import numpy as np
        current = np.array([0.0, 0.0, 1e-6, 2e-6])
        assert not plotting._should_use_log_scale(current)


class TestCollectIvFiles:
    """Tests for collecting IV file entries from DeviceConfig."""

    def test_collects_all(self, sample_config):
        targets = plotting.collect_iv_files(sample_config)
        assert len(targets) == 3  # r0c0 has 2 iv files, r0c1 has 1

    def test_material_filter(self, sample_config):
        """Material filter with tagged points."""
        # Add material tags to sample_config
        pt = sample_config.get_point(0, 0)
        pt.tags = ["material:TestMat(1)"]
        # Need a canonical filename for material extraction
        pt.techniques["iv"].files[0].file = "0505_TestMat(1)_b1-t1_IV-DC_f_01.csv"
        targets = plotting.collect_iv_files(sample_config, material="TestMat(1)")
        assert len(targets) >= 1

    def test_row_col_filter(self, sample_config):
        targets = plotting.collect_iv_files(sample_config, row=0, col=1)
        assert len(targets) == 1
        assert targets[0]["row"] == 0
        assert targets[0]["col"] == 1

    def test_orders_by_position(self, sample_config):
        targets = plotting.collect_iv_files(sample_config)
        # Should be sorted by (row, col, material, order)
        positions = [(t["row"], t["col"]) for t in targets]
        assert positions == sorted(positions)


class TestGenerateIvSvg:
    """Tests for SVG generation."""

    def test_generates_svg(self, temp_dir):
        import numpy as np
        v = np.linspace(-2, 2, 100)
        i = 1e-9 * np.sinh(v)  # diode-like

        metadata = {
            "title": "Test Plot",
            "sweep": [{"direction": "0.00V -> 2.00V", "sweep_rate_v_s": 0.1, "voltage_range": 2.0}],
            "sweep_type": "f",
            "row": 0,
            "col": 0,
        }
        out = temp_dir / "test.svg"
        plotting.generate_iv_svg(v, i, metadata, str(out), dpi=50)

        assert out.exists()
        content = out.read_text()
        assert "<svg" in content
        # Title is now built from sweep annotations: #00 | 0.10 V/s
        assert "#00" in content
        assert "0.10 V/s" in content

    def test_log_scale(self, temp_dir):
        import numpy as np
        v = np.linspace(-2, 2, 100)
        i = np.abs(v) * 1e-13 * np.exp(np.abs(v) * 5)  # spans many decades

        metadata = {"title": "Log Test", "sweep": [], "sweep_type": "f"}
        out = temp_dir / "log_test.svg"
        plotting.generate_iv_svg(v, i, metadata, str(out), dpi=50)

        assert out.exists()
        content = out.read_text()
        # Should have |Current| label
        assert "|Current|" in content or "current" in content.lower()


# ── Dashboard tests ─────────────────────────────────────────


class TestDashboard:
    """Tests for HTML dashboard generation."""

    def test_generates_html(self, temp_dir, sample_config):
        """Generate dashboard HTML with mock SVGs."""
        from science_memristor.dashboard import generate_dashboard

        # Create mock results dir with SVGs
        results_dir = temp_dir / "results"
        results_dir.mkdir()

        # Add plot entries to sample_config
        pt = sample_config.get_point(0, 0)
        fe = pt.techniques["iv"].files[0]
        fe.file = "0505_TestMat(1)_b1-t1_IV-DC_f_01.csv"  # canonical filename
        fe.extra["plot"] = "iv_r0c0_TestMat(1)_f_01.svg"
        fe.sweep_type = "f"
        fe.sweep = [{"direction": "0.00V -> 2.00V", "sweep_rate_v_s": 0.1, "voltage_range": 2.0}]

        # Create the mock SVG file
        (results_dir / "iv_r0c0_TestMat(1)_f_01.svg").write_text("<svg></svg>")

        out = generate_dashboard(sample_config, results_dir, temp_dir / "dashboard.html")
        assert out.exists()

        html = out.read_text()
        assert "<html" in html
        assert "TestMat(1)" in html
        assert "iv_r0c0_TestMat(1)_f_01.svg" in html
        assert "r0c0" in html

    def test_empty_raises(self, temp_dir, sample_config):
        """Dashboard with no plots raises ValueError."""
        from science_memristor.dashboard import generate_dashboard

        results_dir = temp_dir / "results"
        results_dir.mkdir()
        # No plot entries in sample_config
        with pytest.raises(ValueError, match="No plotted"):
            generate_dashboard(sample_config, results_dir, temp_dir / "dash.html")


# ── Helpers ─────────────────────────────────────────────────


@pytest.fixture
def temp_csv(tmp_path):
    """Create a temporary CSV file."""
    path = tmp_path / "test.csv"
    return path


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory."""
    return tmp_path


def _write_csv(path, content):
    """Write content to a CSV file."""
    path.write_text(content, encoding="utf-8")


# Import plotting module for tests
from science_memristor import plotting
