"""Tests for memristor/db.py — SQLite query cache."""

import sqlite3

from science_cli.memristor.db import (
    init_db,
    check_schema,
    open_db,
    get_db_path,
    insert_file,
    upsert_cells,
    upsert_protocol,
    query_files,
    query_cells,
    update_file_analysis,
    rebuild_cells,
    close_db,
    SCHEMA_VERSION,
)


class TestDbSchema:
    """SQLite schema creation and validation."""

    def test_init_db_creates_tables(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "files" in tables
        assert "cells" in tables
        assert "protocols" in tables
        assert "_meta" in tables
        conn.close()

    def test_init_db_creates_indexes(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_files_material" in indexes
        assert "idx_files_protocol" in indexes
        assert "idx_files_mtime" in indexes
        assert "idx_files_technique" in indexes
        assert "idx_cells_protocol_material" in indexes
        conn.close()

    def test_check_schema_sets_version(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        check_schema(conn)
        cursor = conn.execute(
            "SELECT value FROM _meta WHERE key='schema_version'"
        )
        row = cursor.fetchone()
        assert int(row[0]) == SCHEMA_VERSION
        conn.close()


class TestDbCrud:
    """SQLite CRUD operations."""

    @classmethod
    def setup_class(cls):
        cls.conn = sqlite3.connect(":memory:")
        init_db(cls.conn)
        check_schema(cls.conn)

    @classmethod
    def teardown_class(cls):
        cls.conn.close()

    def test_insert_file(self):
        insert_file(
            self.conn,
            protocol="test-protocol",
            step="step-1",
            filename="data_iv.csv",
            technique_id="iv",
            material="PDA",
            row=0, col=0,
            file_size=1024,
        )
        self.conn.commit()
        files = query_files(self.conn)
        assert len(files) >= 1
        assert files[0]["filename"] == "data_iv.csv"

    def test_query_files_filter_by_protocol(self):
        files = query_files(self.conn, protocol="test-protocol")
        assert len(files) >= 1
        assert files[0]["protocol"] == "test-protocol"

    def test_insert_file_unique_constraint(self):
        insert_file(
            self.conn,
            protocol="p", step="s", filename="f.csv",
            technique_id="iv", material="M",
        )
        insert_file(
            self.conn,
            protocol="p", step="s", filename="f.csv",
            technique_id="iv", material="M",
        )
        self.conn.commit()
        files = query_files(self.conn, protocol="p")
        matches = [f for f in files if f["filename"] == "f.csv"]
        assert len(matches) == 1

    def test_upsert_protocol(self):
        upsert_protocol(self.conn, name="proto-1", label="Test Protocol",
                        rows=6, cols=6, materials='["PDA"]')
        self.conn.commit()

    def test_upsert_cells(self):
        upsert_cells(self.conn, protocol="p", material="M",
                     row=0, col=0, n_files=3,
                     median_v_set=0.85, median_v_reset=-0.5,
                     median_on_off_ratio=1.5)
        self.conn.commit()
        cells = query_cells(self.conn, protocol="p")
        assert len(cells) >= 1
        assert cells[0]["median_v_set"] == 0.85

    def test_update_file_analysis(self):
        insert_file(
            self.conn,
            protocol="p", step="s", filename="update_test.csv",
            technique_id="iv", material="M",
        )
        update_file_analysis(
            self.conn,
            protocol="p", step="s", filename="update_test.csv",
            v_set=1.0, v_reset=-0.8, on_off_ratio=2.0,
        )
        self.conn.commit()
        files = query_files(self.conn, protocol="p")
        match = next(f for f in files if f["filename"] == "update_test.csv")
        assert match["v_set"] == 1.0
        assert match["on_off_ratio"] == 2.0


class TestDbRebuild:
    """rebuild_cells should recompute aggregated metrics."""

    def test_rebuild_cells(self):
        conn = sqlite3.connect(":memory:")
        init_db(conn)
        check_schema(conn)

        insert_file(conn, protocol="p", step="s", filename="a.csv",
                    technique_id="iv", material="M", row=0, col=0,
                    v_set=0.8, on_off_ratio=1.5)
        insert_file(conn, protocol="p", step="s", filename="b.csv",
                    technique_id="iv", material="M", row=0, col=0,
                    v_set=1.0, on_off_ratio=2.5)
        conn.commit()

        rebuild_cells(conn)
        cells = query_cells(conn, protocol="p")
        assert len(cells) >= 1
        assert cells[0]["n_files"] == 2
        # median of [0.8, 1.0] = 0.9
        assert cells[0]["median_v_set"] == 0.9
        # median of [1.5, 2.5] = 2.0
        assert cells[0]["median_on_off_ratio"] == 2.0
        conn.close()


class TestDbOpen:
    """open_db should create a persistent database file."""

    def test_open_db_creates_file(self, tmp_path):
        conn = open_db(tmp_path)
        assert conn is not None
        db_path = get_db_path(tmp_path)
        assert db_path.exists()
        close_db(conn)

    def test_get_db_path(self, tmp_path):
        db_path = get_db_path(tmp_path)
        assert str(db_path).endswith(".db")
        assert tmp_path.name in str(db_path)
