"""Tests for cleanup/architecture-guardrails changes.

Run: python test_guardrails.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


# ── Test 1: Dead code cleanup ─────────────────────────────────────────

def test_image_py_deleted():
    """Verify image.py is gone."""
    path = Path(__file__).parent / "src/science_cli/cli/commands/image.py"
    assert not path.exists(), f"image.py should be deleted but exists at {path}"
    print("  [PASS] image.py deleted")


def test_general_py_deleted():
    """Verify general.py is gone."""
    path = Path(__file__).parent / "src/science_cli/cli/commands/general.py"
    assert not path.exists(), f"general.py should be deleted but exists at {path}"
    print("  [PASS] general.py deleted")


def test_functions_dir_deleted():
    """Verify functions/ directory is gone."""
    path = Path(__file__).parent / "src/science_cli/functions"
    assert not path.exists(), f"functions/ should be deleted but exists at {path}"
    print("  [PASS] functions/ deleted")


def test_no_general_import_in_init():
    """Verify general_handler import is removed from __init__.py."""
    init_path = Path(__file__).parent / "src/science_cli/cli/commands/__init__.py"
    content = init_path.read_text()
    assert "general_handler" not in content, "general_handler import should be removed"
    assert "GENERAL_COMMANDS" not in content, "GENERAL_COMMANDS should be removed"
    assert "ALL_COMMANDS" not in content, "ALL_COMMANDS should be removed"
    print("  [PASS] __init__.py cleaned of dead imports")


def test_no_general_in_app_import():
    """Verify app.py no longer imports GENERAL_COMMANDS."""
    app_path = Path(__file__).parent / "src/science_cli/app.py"
    content = app_path.read_text()
    assert "GENERAL_COMMANDS" not in content, "GENERAL_COMMANDS import should be removed"
    print("  [PASS] app.py cleaned of GENERAL_COMMANDS import")


def test_commmand_tree_has_13():
    """Verify COMMAND_TREE has 13 registered commands."""
    from science_cli.cli.commands import COMMAND_TREE
    keys = sorted(COMMAND_TREE.keys())
    expected = ['add', 'analyze', 'close', 'config', 'delete', 'edit', 'ls',
                'memristor', 'open', 'plot', 'results', 'status', 'techniques']
    assert keys == expected, f"Expected {expected}, got {keys}"
    print(f"  [PASS] COMMAND_TREE has {len(keys)} commands")


# ── Test 2: Config system ─────────────────────────────────────────────

def test_config_imports():
    """Verify all config accessors import cleanly."""
    from science_cli.core.config import (
        load_global_config, get_device_config, get_technique_patterns,
        get_default_device, get_projects_root, get_merged_config,
        generate_default_config_yaml, get_header_marker, invalidate_cache,
    )
    print("  [PASS] All config accessors import")


def test_config_backward_compat_no_file():
    """Verify config works with no config file (all defaults)."""
    from science_cli.core.config import (
        get_device_config, get_technique_patterns, get_default_device,
        get_projects_root, get_header_marker, invalidate_cache,
    )
    invalidate_cache()

    tech = "iv-sweep"
    patterns = get_technique_patterns(tech)
    assert len(patterns) >= 6, f"iv-sweep should have >=6 patterns, got {len(patterns)}"

    device_cfg = get_device_config(tech, "nonexistent")
    assert device_cfg is None, "Nonexistent device should return None"

    default_dev = get_default_device(tech)
    assert default_dev == "", f"Default device should be '', got '{default_dev}'"

    root = get_projects_root()
    assert isinstance(root, Path), f"projects_root should be Path, got {type(root)}"

    marker = get_header_marker(tech)
    assert marker == "", f"header_marker should be '', got '{marker}'"
    print("  [PASS] Config backward compat without config file")


def test_config_generate_default_yaml():
    """Verify generate_default_config_yaml produces valid YAML."""
    import yaml
    from science_cli.core.config import generate_default_config_yaml

    yaml_str = generate_default_config_yaml()
    cfg = yaml.safe_load(yaml_str)
    assert isinstance(cfg, dict), f"Should be dict, got {type(cfg)}"
    for key in ("projects_root", "theme", "techniques", "defaults"):
        assert key in cfg, f"Missing key: {key}"
    print("  [PASS] generate_default_config_yaml() produces valid YAML")


def test_config_with_sample_file():
    """Verify config merging with a sample project config."""
    import tempfile, yaml
    from pathlib import Path
    from unittest.mock import patch

    from science_cli.core import config as config_mod
    from science_cli.core import project as project_mod
    import science_cli.core.project  # ensure module loaded

    tmpdir = Path(tempfile.mkdtemp())
    (tmpdir / "sci-config.yaml").write_text("""
techniques:
  iv-sweep:
    patterns: ["*myIV*"]
    header_marker: "Voltage"
    devices:
      test-dev:
        delimiter: "\\t"
        decimal: "."
        header_lines: 15
        encoding: "utf-8"
        columns:
          voltage: "SourceV"
defaults:
  iv-sweep: test-dev
""")

    config_mod.invalidate_cache()
    original_get_proj = project_mod.get_current_project_path
    project_mod.get_current_project_path = lambda: tmpdir

    try:
        patterns = config_mod.get_technique_patterns("iv-sweep", tmpdir)
        assert "*myIV*" in patterns[0], "Config patterns should be first"

        device_cfg = config_mod.get_device_config("iv-sweep", "test-dev", tmpdir)
        assert device_cfg is not None
        assert device_cfg["header_lines"] == 15
        assert device_cfg["columns"]["voltage"] == "SourceV"

        default_dev = config_mod.get_default_device("iv-sweep", tmpdir)
        assert default_dev == "test-dev"

        marker = config_mod.get_header_marker("iv-sweep", tmpdir)
        assert marker == "Voltage"
    finally:
        project_mod.get_current_project_path = original_get_proj

    print("  [PASS] Config with sample project file")


# ── Test 3: Technique detection ───────────────────────────────────────

def test_technique_detection():
    """Verify technique detection still works (backward compat)."""
    from science_cli.core.technique import detect_technique

    tests = [
        ("sample_CV.txt", "ec-cv"),
        ("sample_EIS.csv", "ec-eis"),
        ("device_IV.txt", "iv-sweep"),
        ("sample.mpt", "ec-eis"),
        ("sample_CA.txt", "ec-ca"),
        ("sample_bd_test.txt", "iv-breakdown"),
        ("leakage_data.txt", "iv-leakage"),
        ("endurance_test.csv", "mem-endurance"),
        ("unknown.xyz", ""),
    ]
    for filename, expected in tests:
        result = detect_technique(filename)
        assert result == expected, f"{filename}: expected {expected}, got {result}"
    print("  [PASS] Technique detection (8 test cases)")


# ── Test 4: Data loader ───────────────────────────────────────────────

def test_data_loader_signature():
    """Verify load_data_file accepts optional technique/device params."""
    import inspect
    from science_cli.core.data_loader import load_data_file
    sig = inspect.signature(load_data_file)
    params = list(sig.parameters.keys())
    assert "technique" in params, "load_data_file should accept technique param"
    assert "device" in params, "load_data_file should accept device param"
    print("  [PASS] load_data_file has technique and device params")


# ── Test 5: Project config integration ────────────────────────────────

def test_project_uses_config():
    """Verify _get_projects_root tries config first."""
    from science_cli.core.project import _get_projects_root
    root = _get_projects_root()
    assert isinstance(root, Path), f"Should return Path, got {type(root)}"
    print(f"  [PASS] _get_projects_root returns Path: {root}")


# ── Test 6: Built-in techniques ──────────────────────────────────────

def test_builtin_techniques():
    """Verify built-in techniques are available without extension system."""
    from science_cli.core.technique import BUILTIN_TECHNIQUES
    assert len(BUILTIN_TECHNIQUES) >= 10, f"Expected >=10 techniques, got {len(BUILTIN_TECHNIQUES)}"
    # Verify key techniques exist
    for key in ("iv-sweep", "ec-cv", "ec-eis", "mem-endurance", "mem-switching"):
        assert key in BUILTIN_TECHNIQUES, f"Missing technique: {key}"
    print(f"  [PASS] Built-in techniques: {len(BUILTIN_TECHNIQUES)} techniques")


# ── Test 7: AST validity ──────────────────────────────────────────────

def test_all_modified_files_compile():
    """Verify all modified/new files pass py_compile."""
    import py_compile
    root = Path(__file__).parent / "src"

    files = [
        root / "science_cli/cli/commands/__init__.py",
        root / "science_cli/cli/commands/config.py",
        root / "science_cli/cli/commands/memristor.py",
        root / "science_cli/cli/commands/parse.py",
        root / "science_cli/cli/commands/metadata.py",
        root / "science_cli/cli/commands/data_cmd.py",
        root / "science_cli/app.py",
        root / "science_cli/core/config.py",
        root / "science_cli/core/technique.py",
        root / "science_cli/core/data_loader.py",
        root / "science_cli/core/project.py",
        root / "science_cli/memristor/db.py",
    ]
    for f in files:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            assert False, f"Compile error in {f.name}: {e}"
    print(f"  [PASS] All {len(files)} modified files compile cleanly")


# ── Test 8: SQLite guardrails ─────────────────────────────────────────


def test_sqlite_module_exists():
    """SQLite db.py module must exist."""
    import importlib
    try:
        importlib.import_module("science_cli.memristor.db")
    except ImportError:
        raise AssertionError("science_cli.memristor.db module not found")
    print("  [PASS] SQLite db module exists")


def test_sqlite_schema_has_tables():
    """SQLite module must define CREATE statements for all tables."""
    from science_cli.memristor.db import CREATE_FILES, CREATE_CELLS, CREATE_PROTOCOLS, CREATE_META
    assert "CREATE TABLE" in CREATE_FILES
    assert "CREATE TABLE" in CREATE_CELLS
    assert "CREATE TABLE" in CREATE_PROTOCOLS
    assert "CREATE TABLE" in CREATE_META
    print("  [PASS] SQLite schema has CREATE TABLE statements")


def test_sqlite_db_creation():
    """SQLite database creation and schema init must work."""
    import sqlite3
    from science_cli.memristor.db import init_db, check_schema
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    check_schema(conn)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    assert "files" in tables
    assert "cells" in tables
    assert "protocols" in tables
    assert "_meta" in tables
    conn.close()
    print("  [PASS] SQLite schema init creates all tables")


# ── Test 9: Documentation files exist ─────────────────────────────────

def test_documentation_files_exist():
    """Verify all required documentation files exist."""
    root = Path(__file__).parent
    docs = [
        root / "AGENTS.md",
        root / "src/science_cli/plot/README.md",
        root / "src/science_cli/core/README.md",
        root / "src/science_cli/theme/README.md",
    ]
    for d in docs:
        assert d.exists(), f"Missing documentation: {d}"
        content = d.read_text()
        assert len(content) > 100, f"Documentation too short: {d} ({len(content)} chars)"
    print(f"  [PASS] All {len(docs)} documentation files exist and have content")


# ── Run all tests ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== science-cli: Architecture Guardrails Tests ===\n")

    tests = [
        ("Cleanup: image.py deleted", test_image_py_deleted),
        ("Cleanup: general.py deleted", test_general_py_deleted),
        ("Cleanup: functions/ deleted", test_functions_dir_deleted),
        ("Cleanup: __init__.py import cleanup", test_no_general_import_in_init),
        ("Cleanup: app.py import cleanup", test_no_general_in_app_import),
        ("Cleanup: COMMAND_TREE has 13 commands", test_commmand_tree_has_13),
        ("Config: imports work", test_config_imports),
        ("Config: backward compat (no config file)", test_config_backward_compat_no_file),
        ("Config: generate_default_config_yaml", test_config_generate_default_yaml),
        ("Config: sample project config file", test_config_with_sample_file),
        ("Technique: detection works", test_technique_detection),
        ("DataLoader: signature has technique/device", test_data_loader_signature),
        ("Project: _get_projects_root uses config", test_project_uses_config),
        ("Techniques: built-in techniques available", test_builtin_techniques),
        ("SQLite: db module exists", test_sqlite_module_exists),
        ("SQLite: schema has CREATE TABLE statements", test_sqlite_schema_has_tables),
        ("SQLite: db creation and schema init", test_sqlite_db_creation),
        ("Compile: all modified files", test_all_modified_files_compile),
        ("Docs: documentation files exist", test_documentation_files_exist),
    ]

    passed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
