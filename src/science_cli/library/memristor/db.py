"""SQLite query cache for memristor data — read-optimized cache layer.

Schema (v2):
    files — per-file metadata, universal grammar columns, analysis results
    cells — per-cell aggregated metrics
    protocols — protocol metadata
    _meta — schema version tracking

WAL mode enabled. Schema migration via _meta table (version tracking).
"""

import sqlite3
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 6

# Data file suffixes (same as device.py DATA_SUFFIXES)
DATA_SUFFIXES = {".txt", ".csv", ".dat", ".tsv", ".log"}

# Techniques that belong in the memristor SQLite cache.
# EC techniques (ec-cv, ec-ca, etc.) and fabrication steps (pvd, afm) are excluded.
MEMRISTOR_TECHNIQUES = {
    "iv-sweep", "iv-breakdown", "iv-leakage",
    "mem-endurance", "mem-retention", "mem-switching",
}

# Schema DDL
CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    step TEXT NOT NULL,
    filename TEXT NOT NULL,
    technique_id TEXT,
    device_id TEXT,
    -- Universal grammar fields (populated by sync)
    date_code TEXT,
    material TEXT NOT NULL,
    matrix TEXT,
    row INTEGER,
    col INTEGER,
    suffix INTEGER,
    -- Computed analysis values (populated by analyze)
    v_set REAL,
    v_reset REAL,
    i_set REAL,
    i_reset REAL,
    on_off_ratio REAL,
    current_compliance REAL,
    compliance_confidence TEXT,
    -- Sweep metadata (v4)
    sweep_order INTEGER,
    sweep_type TEXT,
    sweep_segments TEXT,
    temperature REAL DEFAULT 298.0,
    -- Metadata
    file_size INTEGER,
    mtime TEXT,
    parse_error TEXT,
    UNIQUE(protocol, step, filename, technique_id)
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
    has_memristors INTEGER DEFAULT 1,
    last_sync TEXT
)
"""

CREATE_MATERIALS = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY,
    protocol TEXT NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    material TEXT NOT NULL,
    device_type TEXT DEFAULT 'non-volatile', -- 'non-volatile', 'volatile', 'resistor', 'short', 'insulating'
    errors TEXT DEFAULT '',
    UNIQUE(protocol, row, col)
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
    "CREATE INDEX IF NOT EXISTS idx_files_technique ON files(technique_id)",
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
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_FILES)
    conn.execute(CREATE_CELLS)
    conn.execute(CREATE_PROTOCOLS)
    conn.execute(CREATE_MATERIALS)
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
    if from_version < 2 <= to_version:
        # v1 → v2: schema redesigned with universal grammar columns
        # Drop old files table and recreate with v2 schema
        conn.execute("DROP TABLE IF EXISTS files")
        conn.execute(CREATE_FILES)

    if from_version < 3 <= to_version:
        # v2 → v3: add i_set and i_reset columns for precise marker plotting
        for col in ("i_set", "i_reset"):
            try:
                conn.execute(f"ALTER TABLE files ADD COLUMN {col} REAL")
            except sqlite3.OperationalError:
                pass  # column already exists

    if from_version < 4 <= to_version:
        # v3 → v4: add sweep metadata columns (sweep_order, sweep_type,
        # sweep_segments, temperature)
        for col, col_type in [
            ("sweep_order", "INTEGER"),
            ("sweep_type", "TEXT"),
            ("sweep_segments", "TEXT"),
            ("temperature", "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE files ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

    if from_version < 5 <= to_version:
        # v4 → v5: add has_memristors to protocols and create materials table
        try:
            conn.execute("ALTER TABLE protocols ADD COLUMN has_memristors INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute(CREATE_MATERIALS)

    if from_version < 6 <= to_version:
        # v5 → v6: add v_set_idx and v_reset_idx columns for detection marker plotting
        for col, col_type in [
            ("v_set_idx", "INTEGER"),
            ("v_reset_idx", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE files ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass


# ── CRUD helpers ───────────────────────────────────────────────────────


def insert_file(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    filename: str,
    technique_id: Optional[str] = None,
    device_id: Optional[str] = None,
    material: str = "unknown",
    row: Optional[int] = None,
    col: Optional[int] = None,
    date_code: Optional[str] = None,
    matrix: Optional[str] = None,
    suffix: Optional[int] = None,
    sweep_order: Optional[int] = None,
    sweep_type: Optional[str] = None,
    sweep_segments: Optional[str] = None,
    temperature: Optional[float] = None,
    v_set: Optional[float] = None,
    v_reset: Optional[float] = None,
    i_set: Optional[float] = None,
    i_reset: Optional[float] = None,
    on_off_ratio: Optional[float] = None,
    current_compliance: Optional[float] = None,
    compliance_confidence: Optional[str] = None,
    parse_error: Optional[str] = None,
    file_size: int = 0,
    mtime: str = "",
) -> None:
    """Insert or replace a file row in the ``files`` table."""
    conn.execute(
        """INSERT OR REPLACE INTO files (
            protocol, step, filename, technique_id, device_id,
            date_code, material, matrix,
            row, col, suffix,
            sweep_order, sweep_type, sweep_segments, temperature,
            v_set, v_reset, i_set, i_reset, on_off_ratio,
            current_compliance, compliance_confidence,
            parse_error, file_size, mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            protocol, step, filename, technique_id, device_id,
            date_code, material, matrix,
            row, col, suffix,
            sweep_order, sweep_type, sweep_segments, temperature,
            v_set, v_reset, i_set, i_reset, on_off_ratio,
            current_compliance, compliance_confidence,
            parse_error, file_size, mtime,
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


def upsert_material(
    conn: sqlite3.Connection,
    protocol: str,
    row: int,
    col: int,
    material: str,
    device_type: str = "non-volatile",
    errors: str = "",
) -> None:
    """Upsert a row into the ``materials`` table."""
    conn.execute(
        """INSERT OR REPLACE INTO materials (protocol, row, col, material, device_type, errors)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (protocol, row, col, material, device_type, errors),
    )


def classify_and_populate_materials(conn: sqlite3.Connection, protocol_name: str) -> None:
    """Classify device types and populate the materials table based on material naming, overrides, and cycle volatility yields."""
    from science_cli.core.project import get_current_project_path
    
    # Load Tier A persistent configuration overrides from protocol YAML
    proj = get_current_project_path()
    device_overrides = {}
    if proj:
        yaml_path = proj / "protocol" / protocol_name / f"{protocol_name}.yaml"
        if yaml_path.exists():
            import yaml
            try:
                with open(yaml_path) as f:
                    proto_data = yaml.safe_load(f) or {}
                device_overrides = proto_data.get("device_overrides", {})
            except Exception:
                pass

    # 1. Fetch all unique rows, cols, and materials for the protocol
    cursor = conn.execute(
        """SELECT DISTINCT row, col, material 
           FROM files 
           WHERE protocol = ? AND row IS NOT NULL AND col IS NOT NULL""",
        (protocol_name,),
    )
    points = cursor.fetchall()
    
    for r, c, mat in points:
        # Check manual overrides first (exact match or wildcard prefix matching)
        mat_overrides = device_overrides.get("materials", {})
        cell_overrides = device_overrides.get("cells", {})
        
        matched_override_type = None
        
        # Check cell coordinate override first (handles both 'rRcC' and 'R,C')
        for key in [f"r{r}c{c}", f"{r},{c}"]:
            if key in cell_overrides:
                matched_override_type = cell_overrides[key]
                break
                
        # Check material name override
        if not matched_override_type:
            for pattern, dev_type in mat_overrides.items():
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if mat.startswith(prefix):
                        matched_override_type = dev_type
                        break
                elif pattern == mat:
                    matched_override_type = dev_type
                    break
                    
        if matched_override_type:
            upsert_material(
                conn,
                protocol=protocol_name,
                row=r,
                col=c,
                material=mat,
                device_type=matched_override_type,
                errors="manual override",
            )
            continue

        # Fetch all sweep measurements for this coordinate
        cursor_params = conn.execute(
            """SELECT v_set, v_reset, on_off_ratio, compliance_confidence
               FROM files
               WHERE protocol = ? AND row = ? AND col = ?""",
            (protocol_name, r, c),
        )
        sweeps = cursor_params.fetchall()
        
        n_sweeps = len(sweeps)
        if n_sweeps == 0:
            continue
            
        n_v_set = sum(1 for sw in sweeps if sw[0] is not None)
        n_v_reset = sum(1 for sw in sweeps if sw[1] is not None)
        
        # Calculate median ratios
        ratios = [sw[2] for sw in sweeps if sw[2] is not None]
        median_ratio = np.median(ratios) if ratios else 1.0
        
        # Dynamic cycle-level volatility calculation
        n_switching_sweeps = 0
        n_volatile_sweeps = 0
        
        for sw in sweeps:
            v_s, v_r = sw[0], sw[1]
            if v_s is not None:
                n_switching_sweeps += 1
                # Volatile sweep if no reset or negligible reset (< 0.15 V)
                if v_r is None or abs(v_r) < 0.15:
                    n_volatile_sweeps += 1
                    
        if n_switching_sweeps > 0:
            volatility_yield = (n_volatile_sweeps / n_switching_sweeps) * 100.0
        else:
            volatility_yield = 0.0

        mat_lower = mat.lower()
        device_type = "non-volatile"
        errors = ""
        
        # Shorted heuristic (extremely low ON/OFF ratio, high leakage, no SET detected)
        if median_ratio < 1.2 and n_v_set == 0:
            device_type = "short"
            errors = "device shorted / stuck ON (high leakage)"
        # Insulating heuristic (no switching events and near-unit ratio or extremely low currents)
        elif n_v_set == 0 and n_v_reset == 0:
            device_type = "insulating"
            errors = "no switching detected (stuck OFF/open)"
        else:
            # Check for volatile behavior indicators based on volatility yield and material name
            is_volatile = "cu-c-pda" in mat_lower
            
            if volatility_yield >= 80.0:
                is_volatile = True
                errors = f"relaxation profile ({int(n_volatile_sweeps)}/{int(n_switching_sweeps)} cycles volatile)"
            elif volatility_yield < 20.0:
                is_volatile = False
                errors = f"stable non-volatile switching ({int(n_volatile_sweeps)}/{int(n_switching_sweeps)} cycles volatile)"
            else:
                is_volatile = True
                errors = f"mixed volatility: {volatility_yield:.1f}% ({int(n_volatile_sweeps)}/{int(n_switching_sweeps)} cycles volatile)"
                
            if is_volatile:
                device_type = "volatile"
            else:
                device_type = "non-volatile"
                
        # Preserve user manual overrides if already present in the database!
        # Manual overrides have priority over automated heuristics
        check_cur = conn.execute(
            "SELECT device_type, errors FROM materials WHERE protocol = ? AND row = ? AND col = ?",
            (protocol_name, r, c)
        )
        existing = check_cur.fetchone()
        if existing:
            # If the cell already has a manual error remark or non-default type, keep it!
            db_type, db_errors = existing[0], existing[1]
            if db_type in ("resistor", "volatile", "non-volatile", "short", "insulating") and db_errors != "":
                device_type = db_type
                errors = db_errors
            
        upsert_material(
            conn,
            protocol=protocol_name,
            row=r,
            col=c,
            material=mat,
            device_type=device_type,
            errors=errors,
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
        sql += " AND technique_id = ?"
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
    i_set: Optional[float] = None,
    i_reset: Optional[float] = None,
    v_set_idx: Optional[int] = None,
    v_reset_idx: Optional[int] = None,
    on_off_ratio: Optional[float] = None,
    current_compliance: Optional[float] = None,
    compliance_confidence: Optional[str] = None,
) -> None:
    """Update analysis results for a file row.

    Updates Vset, Vreset, switching currents, detection indices,
    on/off ratio, current compliance, and compliance confidence.
    """
    conn.execute(
        """UPDATE files SET
            v_set = ?, v_reset = ?, i_set = ?, i_reset = ?,
            v_set_idx = ?, v_reset_idx = ?,
            on_off_ratio = ?,
            current_compliance = ?, compliance_confidence = ?
           WHERE protocol = ? AND step = ? AND filename = ?""",
        (
            v_set, v_reset, i_set, i_reset,
            v_set_idx, v_reset_idx,
            on_off_ratio,
            current_compliance, compliance_confidence,
            protocol, step, filename,
        ),
    )


def update_file_sweep_metadata(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    filename: str,
    sweep_order: Optional[int] = None,
    sweep_type: Optional[str] = None,
    sweep_segments: Optional[str] = None,
    temperature: Optional[float] = None,
) -> None:
    """Update sweep metadata for a specific file entry.

    Uses protocol+step+filename as the lookup key.
    Only updates columns where the value is not None.

    Args:
        conn: Open SQLite connection.
        protocol: Protocol name.
        step: Step name.
        filename: The filename to update.
        sweep_order: Sweep order index.
        sweep_type: Sweep type code (``f``, ``sp``, ``sn``, ``uc``).
        sweep_segments: JSON string of segment dicts.
        temperature: Temperature in Kelvin.
    """
    sets: list[str] = []
    params: list = []

    if sweep_order is not None:
        sets.append("sweep_order = ?")
        params.append(sweep_order)
    if sweep_type is not None:
        sets.append("sweep_type = ?")
        params.append(sweep_type)
    if sweep_segments is not None:
        sets.append("sweep_segments = ?")
        params.append(sweep_segments)
    if temperature is not None:
        sets.append("temperature = ?")
        params.append(temperature)

    if not sets:
        return

    params.extend([protocol, step, filename])
    conn.execute(
        f"UPDATE files SET {', '.join(sets)} "
        f"WHERE protocol = ? AND step = ? AND filename = ?",
        params,
    )


def query_materials(
    conn: sqlite3.Connection,
    protocol: Optional[str] = None,
) -> list[dict]:
    """Query the ``materials`` table with optional protocol filter.

    Returns a list of dicts with keys: protocol, row, col, material, device_type, errors.
    """
    sql = "SELECT * FROM materials WHERE 1=1"
    params: list = []
    if protocol:
        sql += " AND protocol = ?"
        params.append(protocol)
    sql += " ORDER BY protocol, row, col"
    cursor = conn.execute(sql, params)
    return [{key: row[key] for key in row.keys()} for row in cursor.fetchall()]


def query_sweep_metadata(
    conn: sqlite3.Connection,
    protocol: str,
    step: Optional[str] = None,
) -> list[dict]:
    """Query sweep metadata from the files table.

    Args:
        conn: Open SQLite connection.
        protocol: Protocol name.
        step: Optional step name filter.

    Returns:
        List of dicts with keys: ``filename``, ``sweep_order``,
        ``sweep_type``, ``sweep_segments``, ``temperature``.
    """
    sql = ("SELECT filename, sweep_order, sweep_type, "
           "sweep_segments, temperature "
           "FROM files WHERE protocol = ?")
    params: list = [protocol]

    if step:
        sql += " AND step = ?"
        params.append(step)

    sql += " ORDER BY step, sweep_order"
    cursor = conn.execute(sql, params)
    return [{key: row[key] for key in row.keys()} for row in cursor.fetchall()]


def prune_stale_files(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    valid_filenames: set[str],
) -> int:
    """Delete rows from ``files`` for files no longer present on disk.

    Args:
        conn: Open SQLite connection.
        protocol: Protocol name.
        step: Step directory name.
        valid_filenames: Set of filenames currently on disk.

    Returns:
        Number of rows deleted.
    """
    if valid_filenames:
        placeholders = ",".join("?" for _ in valid_filenames)
        cursor = conn.execute(
            f"DELETE FROM files "
            f"WHERE protocol = ? AND step = ? "
            f"AND filename NOT IN ({placeholders})",
            [protocol, step] + list(valid_filenames),
        )
    else:
        cursor = conn.execute(
            "DELETE FROM files WHERE protocol = ? AND step = ?",
            [protocol, step],
        )
    return cursor.rowcount


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


# ── Grammar-based population ───────────────────────────────────────────


def populate_from_grammar(
    conn: sqlite3.Connection,
    protocol: str,
    step: str,
    project_root: Optional[Path] = None,
) -> dict:
    """Scan step directory, parse filenames via grammar patterns, populate SQLite.

    Does NOT read CSV content — pure filename parsing only.

    Args:
        conn: Open SQLite connection.
        protocol: Protocol name.
        step: Step directory name (relative to protocol dir).
        project_root: Project root for config resolution.

    Returns:
        dict with keys: files_found, files_matched, files_inserted, errors
    """
    from science_cli.core.config import get_default_device, resolve_technique_from_grammar
    from science_cli.core.technique import parse_filename_grammar

    # Resolve project root
    if project_root is None:
        try:
            from science_cli.core.project import get_current_project_path
            project_root = get_current_project_path()
        except ImportError:
            pass

    if project_root is None:
        return {
            "files_found": 0,
            "files_matched": 0,
            "files_inserted": 0,
            "errors": ["cannot resolve project_root"],
        }

    step_dir = project_root / "protocol" / protocol / step
    if not step_dir.is_dir():
        return {
            "files_found": 0,
            "files_matched": 0,
            "files_inserted": 0,
            "errors": [f"step directory not found: {step_dir}"],
        }

    files_found = 0
    files_matched = 0
    files_inserted = 0
    errors: list[str] = []

    for entry in sorted(step_dir.iterdir()):
        if entry.name.startswith("."):
            continue

        # Resolve symlinks to their real targets in data/raw/
        if entry.is_symlink():
            try:
                target = entry.resolve(strict=True)
            except (OSError, RuntimeError):
                continue  # broken symlink — skip
            if not target.is_file():
                continue
            filename = target.name
            suffix = target.suffix
            stat_result = target.stat()
        elif entry.is_file():
            filename = entry.name
            suffix = entry.suffix
            stat_result = entry.stat()
        else:
            continue

        if suffix.lower() not in DATA_SUFFIXES:
            continue

        files_found += 1
        file_size = stat_result.st_size
        mtime = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat()

        # Parse filename via grammar
        parsed = parse_filename_grammar(filename, project_root=project_root)

        if "parse_error" in parsed:
            # No grammar pattern matched — store with parse error
            insert_file(
                conn,
                protocol=protocol,
                step=step,
                filename=filename,
                material="unknown",
                parse_error=parsed["parse_error"],
                file_size=file_size,
                mtime=mtime,
            )
            files_inserted += 1
            errors.append(f"{filename}: {parsed['parse_error']}")
            continue

        files_matched += 1

        # Extract universal grammar fields from parse result
        date_code = parsed.get("date_code")
        material = parsed.get("material", "unknown")
        matrix = parsed.get("matrix")
        row_str = parsed.get("row")
        col_str = parsed.get("col")
        suffix_str = parsed.get("suffix")
        grammar_code = parsed.get("technique", "")

        row = int(row_str) if row_str is not None else None
        col = int(col_str) if col_str is not None else None
        suffix = int(suffix_str) if suffix_str is not None else None

        # Resolve technique_id from grammar code
        technique_id = None
        if grammar_code:
            technique_id = resolve_technique_from_grammar(
                grammar_code, project_root=project_root
            )

        # Resolve device_id from technique config (default device)
        device_id = None
        if technique_id:
            device_id = get_default_device(technique_id, project_root=project_root)
            if not device_id:
                device_id = None

        insert_file(
            conn,
            protocol=protocol,
            step=step,
            filename=filename,
            technique_id=technique_id,
            device_id=device_id,
            date_code=date_code,
            material=material,
            matrix=matrix,
            row=row,
            col=col,
            suffix=suffix,
            file_size=file_size,
            mtime=mtime,
        )
        files_inserted += 1

        if row is not None and col is not None:
            # Deduce a material-name default: cu-c-pda is volatile, ta-pda is non-volatile
            mat_lower = material.lower()
            default_type = "volatile" if "cu-c-pda" in mat_lower else "non-volatile"
            
            # Check if this cell already exists to preserve manual overrides!
            cursor_check = conn.execute(
                "SELECT device_type, errors FROM materials WHERE protocol = ? AND row = ? AND col = ?",
                (protocol, row, col)
            )
            existing = cursor_check.fetchone()
            if existing:
                db_type, db_errors = existing[0], existing[1]
                if db_type in ("resistor", "volatile", "non-volatile", "short", "insulating") and db_errors != "":
                    default_type = db_type
            
            upsert_material(
                conn,
                protocol=protocol,
                row=row,
                col=col,
                material=material,
                device_type=default_type,
            )

    return {
        "files_found": files_found,
        "files_matched": files_matched,
        "files_inserted": files_inserted,
        "errors": errors,
    }


def populate_protocol_from_step_dirs(
    conn: sqlite3.Connection,
    protocol: str,
    project_root: Optional[Path] = None,
) -> dict:
    """Scan ALL step directories under ``protocol/<name>/`` and populate the database.

    Calls ``populate_from_grammar()`` for each step directory found.
    Upserts the protocols table with the protocol name.

    Args:
        conn: Open SQLite connection.
        protocol: Protocol name.
        project_root: Project root for config resolution.

    Returns:
        dict with keys: steps_found, total_files, total_matched, total_inserted, errors
    """
    # Resolve project root
    if project_root is None:
        try:
            from science_cli.core.project import get_current_project_path
            project_root = get_current_project_path()
        except ImportError:
            pass

    if project_root is None:
        return {
            "steps_found": 0,
            "total_files": 0,
            "total_matched": 0,
            "total_inserted": 0,
            "errors": ["cannot resolve project_root"],
        }

    proto_dir = project_root / "protocol" / protocol
    if not proto_dir.is_dir():
        return {
            "steps_found": 0,
            "total_files": 0,
            "total_matched": 0,
            "total_inserted": 0,
            "errors": [f"protocol directory not found: {proto_dir}"],
        }

    # Read protocol YAML to learn step → technique mapping
    step_techniques: dict[str, str] = {}
    yaml_path = proto_dir / f"{protocol}.yaml"
    try:
        import yaml as _yaml
        if yaml_path.is_file():
            with open(yaml_path) as _f:
                _data = _yaml.safe_load(_f)
            for _s in (_data.get("steps") or []):
                if isinstance(_s, dict):
                    step_techniques[_s.get("name", "")] = _s.get("technique", "")
    except Exception:
        pass  # If YAML is unreadable, process all steps (backward compat)

    steps_found = 0
    total_files = 0
    total_matched = 0
    total_inserted = 0
    all_errors: list[str] = []

    for entry in sorted(proto_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue

        step_name = entry.name
        steps_found += 1

        technique = step_techniques.get(step_name, "")
        if technique and technique not in MEMRISTOR_TECHNIQUES:
            continue  # Skip non-memristor techniques (ec-cv, ec-ca, pvd, afm, etc.)

        result = populate_from_grammar(
            conn,
            protocol=protocol,
            step=step_name,
            project_root=project_root,
        )
        total_files += result["files_found"]
        total_matched += result["files_matched"]
        total_inserted += result["files_inserted"]
        all_errors.extend(result["errors"])

    # Upsert protocol entry
    upsert_protocol(conn, name=protocol)

    return {
        "steps_found": steps_found,
        "total_files": total_files,
        "total_matched": total_matched,
        "total_inserted": total_inserted,
        "errors": all_errors,
    }
