"""SQLite query cache for memristor data — read-optimized cache layer.

Schema:
    files — per-file metadata, technique, results
    cells — per-cell aggregated metrics
    protocols — protocol metadata
    _meta — schema version tracking

WAL mode enabled. Schema migration via _meta table (version tracking).
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1

# Schema DDL
CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    step TEXT NOT NULL,
    filename TEXT NOT NULL,
    technique TEXT NOT NULL,
    date_code TEXT,
    material TEXT NOT NULL,
    row INTEGER,
    col INTEGER,
    cycle_index INTEGER,
    timestamp_first REAL,
    timestamp_last REAL,
    v_set REAL,
    v_reset REAL,
    on_off_ratio REAL,
    current_compliance_1sf TEXT,
    compliance_confidence TEXT,
    plot_figure_path TEXT,
    file_size INTEGER,
    mtime TEXT,
    UNIQUE(protocol, step, filename)
)
"""

CREATE_CELLS = """
CREATE TABLE IF NOT EXISTS cells (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    material TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    n_files INTEGER DEFAULT 0,
    median_v_set REAL,
    median_v_reset REAL,
    median_on_off_ratio REAL,
    UNIQUE(protocol, material, row, col)
)
"""

CREATE_PROTOCOLS = """
CREATE TABLE IF NOT EXISTS protocols (
    name TEXT PRIMARY KEY,
    label TEXT,
    rows INTEGER,
    cols INTEGER,
    materials TEXT,
    last_sync TEXT
)
"""

CREATE_META = """
CREATE TABLE IF NOT EXISTS _meta (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_files_material ON files(material)",
    "CREATE INDEX IF NOT EXISTS idx_files_protocol ON files(protocol)",
    "CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime)",
    "CREATE INDEX IF NOT EXISTS idx_files_technique ON files(technique)",
    "CREATE INDEX IF NOT EXISTS idx_cells_protocol_material ON cells(protocol, material)",
]


def get_db_path(project_root: Path) -> Path:
    """Return the SQLite database path: ``<project_name>.db`` at project root."""
    return project_root / f"{project_root.name}.db"


def open_db(project_root: Path) -> sqlite3.Connection:
    """Open (or create) the SQLite database with WAL mode and schema init.

    Sets ``PRAGMA journal_mode=WAL`` and ``PRAGMA foreign_keys=ON``,
    then calls ``init_db`` and ``check_schema``.

    Args:
        project_root: Path to project root directory.

    Returns:
        An open ``sqlite3.Connection``.  Caller must close it.
    """
    db_path = get_db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    check_schema(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not exist."""
    conn.execute(CREATE_FILES)
    conn.execute(CREATE_CELLS)
    conn.execute(CREATE_PROTOCOLS)
    conn.execute(CREATE_META)
    for idx_sql in CREATE_INDEXES:
        conn.execute(idx_sql)


def check_schema(conn: sqlite3.Connection) -> None:
    """Check _meta.schema_version and apply migrations if needed."""
    cursor = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'")
    row = cursor.fetchone()
    current_version = int(row[0]) if row else 0

    if current_version < SCHEMA_VERSION:
        # Run migrations from current_version up to SCHEMA_VERSION
        _run_migrations(conn, current_version, SCHEMA_VERSION)
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )


def _run_migrations(conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
    """Apply sequential schema migrations from *from_version* to *to_version*."""
    # Currently no migrations needed (v1 is the initial schema).
    # Future migrations can be added here as numbered steps.
    pass


# ── CRUD helpers ───────────────────────────────────────────────────────


def insert_file(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    filename: str,
    technique: str,
    material: str = "unknown",
    row: Optional[int] = None,
    col: Optional[int] = None,
    date_code: Optional[str] = None,
    cycle_index: Optional[int] = None,
    timestamp_first: Optional[float] = None,
    timestamp_last: Optional[float] = None,
    v_set: Optional[float] = None,
    v_reset: Optional[float] = None,
    on_off_ratio: Optional[float] = None,
    current_compliance_1sf: Optional[str] = None,
    compliance_confidence: Optional[str] = None,
    plot_figure_path: Optional[str] = None,
    file_size: int = 0,
    mtime: str = "",
) -> None:
    """Insert or replace a file row in the ``files`` table."""
    conn.execute(
        """INSERT OR REPLACE INTO files (
            protocol, step, filename, technique, date_code, material,
            row, col, cycle_index,
            timestamp_first, timestamp_last,
            v_set, v_reset, on_off_ratio,
            current_compliance_1sf, compliance_confidence,
            plot_figure_path, file_size, mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            protocol, step, filename, technique, date_code, material,
            row, col, cycle_index,
            timestamp_first, timestamp_last,
            v_set, v_reset, on_off_ratio,
            current_compliance_1sf, compliance_confidence,
            plot_figure_path, file_size, mtime,
        ),
    )


def upsert_cells(
    conn: sqlite3.Connection,
    protocol: str,
    material: str,
    row: int,
    col: int,
    n_files: int = 0,
    median_v_set: Optional[float] = None,
    median_v_reset: Optional[float] = None,
    median_on_off_ratio: Optional[float] = None,
) -> None:
    """Upsert a row into the ``cells`` table."""
    conn.execute(
        """INSERT OR REPLACE INTO cells (
            protocol, material, row, col, n_files,
            median_v_set, median_v_reset, median_on_off_ratio
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            protocol, material, row, col, n_files,
            median_v_set, median_v_reset, median_on_off_ratio,
        ),
    )


def upsert_protocol(
    conn: sqlite3.Connection,
    name: str,
    label: Optional[str] = None,
    rows: Optional[int] = None,
    cols: Optional[int] = None,
    materials: Optional[str] = None,
) -> None:
    """Upsert a row into the ``protocols`` table."""
    last_sync = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO protocols (name, label, rows, cols, materials, last_sync)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, label, rows, cols, materials, last_sync),
    )


def query_files(
    conn: sqlite3.Connection,
    protocol: Optional[str] = None,
    technique: Optional[str] = None,
    material: Optional[str] = None,
) -> list[dict]:
    """Query the ``files`` table with optional filters.

    Returns a list of dicts (keys match column names).
    """
    sql = "SELECT * FROM files WHERE 1=1"
    params: list = []
    if protocol:
        sql += " AND protocol = ?"
        params.append(protocol)
    if technique:
        sql += " AND technique = ?"
        params.append(technique)
    if material:
        sql += " AND material = ?"
        params.append(material)
    sql += " ORDER BY protocol, step, filename"
    cursor = conn.execute(sql, params)
    return [{key: row[key] for key in row.keys()} for row in cursor.fetchall()]


def query_cells(
    conn: sqlite3.Connection,
    protocol: Optional[str] = None,
    material: Optional[str] = None,
) -> list[dict]:
    """Query the ``cells`` table with optional filters.

    Returns a list of dicts (keys match column names).
    """
    sql = "SELECT * FROM cells WHERE 1=1"
    params: list = []
    if protocol:
        sql += " AND protocol = ?"
        params.append(protocol)
    if material:
        sql += " AND material = ?"
        params.append(material)
    sql += " ORDER BY protocol, material, row, col"
    cursor = conn.execute(sql, params)
    return [{key: row[key] for key in row.keys()} for row in cursor.fetchall()]


def update_file_analysis(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    filename: str,
    v_set: Optional[float] = None,
    v_reset: Optional[float] = None,
    on_off_ratio: Optional[float] = None,
) -> None:
    """Update analysis results (Vset/Vreset/ratio) for a file row."""
    conn.execute(
        """UPDATE files SET v_set = ?, v_reset = ?, on_off_ratio = ?
           WHERE protocol = ? AND step = ? AND filename = ?""",
        (v_set, v_reset, on_off_ratio, protocol, step, filename),
    )


def rebuild_cells(conn: sqlite3.Connection) -> None:
    """Recompute the ``cells`` table from the ``files`` table.

    Aggregates per (protocol, material, row, col):
      - n_files = COUNT(*)
      - median_v_set = median of non-NULL v_set values
      - median_v_reset = median of non-NULL v_reset values
      - median_on_off_ratio = median of non-NULL on_off_ratio values

    Operates entirely in Python for correct median computation
    (SQLite has no built-in MEDIAN aggregate).
    """
    conn.execute("DELETE FROM cells")

    # Get distinct groups from files
    cursor = conn.execute(
        """SELECT protocol, material, row, col, COUNT(*) AS n_files
           FROM files
           WHERE row IS NOT NULL AND col IS NOT NULL
           GROUP BY protocol, material, row, col"""
    )
    groups = cursor.fetchall()

    for group in groups:
        proto = group["protocol"]
        mat = group["material"]
        r = group["row"]
        c = group["col"]
        n_files = group["n_files"]

        # Median v_set
        vset_cursor = conn.execute(
            """SELECT v_set FROM files
               WHERE protocol=? AND material=? AND row=? AND col=?
                 AND v_set IS NOT NULL
               ORDER BY v_set""",
            (proto, mat, r, c),
        )
        vset_vals = [row["v_set"] for row in vset_cursor.fetchall()]
        med_vset = _median(vset_vals)

        # Median v_reset
        vreset_cursor = conn.execute(
            """SELECT v_reset FROM files
               WHERE protocol=? AND material=? AND row=? AND col=?
                 AND v_reset IS NOT NULL
               ORDER BY v_reset""",
            (proto, mat, r, c),
        )
        vreset_vals = [row["v_reset"] for row in vreset_cursor.fetchall()]
        med_vreset = _median(vreset_vals)

        # Median on_off_ratio
        ratio_cursor = conn.execute(
            """SELECT on_off_ratio FROM files
               WHERE protocol=? AND material=? AND row=? AND col=?
                 AND on_off_ratio IS NOT NULL
               ORDER BY on_off_ratio""",
            (proto, mat, r, c),
        )
        ratio_vals = [row["on_off_ratio"] for row in ratio_cursor.fetchall()]
        med_ratio = _median(ratio_vals)

        conn.execute(
            """INSERT OR REPLACE INTO cells (
                protocol, material, row, col, n_files,
                median_v_set, median_v_reset, median_on_off_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (proto, mat, r, c, n_files, med_vset, med_vreset, med_ratio),
        )


def _median(values: list) -> Optional[float]:
    """Return the median of a sorted list of floats, or None if empty."""
    if not values:
        return None
    n = len(values)
    if n % 2 == 1:
        return float(values[n // 2])
    return (float(values[n // 2 - 1]) + float(values[n // 2])) / 2.0


def close_db(conn: sqlite3.Connection) -> None:
    """Close the database connection."""
    try:
        conn.close()
    except Exception:
        pass
