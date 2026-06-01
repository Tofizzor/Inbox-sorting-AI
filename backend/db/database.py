"""SQLite connection and schema initialization."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from config import BACKEND_ROOT, get_data_dir, get_database_path


def get_connection() -> sqlite3.Connection:
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Apply schema and seed guide_config if empty."""
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    try:
        schema_path = BACKEND_ROOT / "db" / "schema.sql"
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _seed_guide_if_empty(conn)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def _seed_guide_if_empty(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM guide_config WHERE id = 1").fetchone()
    if row is not None:
        return
    seed_path = get_data_dir() / "guide_config.json"
    config_text = seed_path.read_text(encoding="utf-8")
    json.loads(config_text)  # validate
    conn.execute(
        "INSERT INTO guide_config (id, config, updated_at, updated_by) VALUES (1, ?, datetime('now'), ?)",
        (config_text, "system"),
    )
