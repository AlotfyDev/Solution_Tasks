from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

from task_cli.registry import SchemaRegistry
from task_cli.registry.base import TaskSchema

# Default DB location: inside Solution_Tasks project, hidden directory
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / ".data"


def resolve_db_dir(cli_arg: Optional[Path]) -> Path:
    """Priority chain: --db-dir > TASK_DB_DIR env var > default project .data/"""
    if cli_arg is not None:
        return cli_arg
    env_dir = os.environ.get("TASK_DB_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_DB_DIR


class DatabaseEngine:
    """
    Manages SQLite connection and per-schema table lifecycle.

    Each registered schema gets its own set of tables (defined in schema.ddl_statements).
    Shared tables (relationships, history) are created unconditionally.
    """

    DB_FILENAME = "tasks.db"

    SHARED_DDL: list[str] = [
        (
            "CREATE TABLE IF NOT EXISTS task_relationships ("
            "  source_id       TEXT NOT NULL,"
            "  source_schema   TEXT NOT NULL,"
            "  target_id       TEXT NOT NULL,"
            "  target_schema   TEXT NOT NULL,"
            "  rel_type        TEXT NOT NULL,"
            "  properties_json TEXT DEFAULT '{}',"
            "  created_at      TEXT DEFAULT (datetime('now')),"
            "  PRIMARY KEY (source_id, target_id, rel_type)"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS task_history ("
            "  id          INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  task_id     TEXT NOT NULL,"
            "  schema_id   TEXT NOT NULL,"
            "  changed_at  TEXT DEFAULT (datetime('now')),"
            "  field_name  TEXT NOT NULL,"
            "  old_value   TEXT,"
            "  new_value   TEXT,"
            "  changed_by  TEXT DEFAULT 'cli'"
            ")"
        ),
    ]

    def __init__(self, db_dir: Path, registry: SchemaRegistry):
        self._db_dir = db_dir
        self._registry = registry
        self._db_path = db_dir / self.DB_FILENAME
        self._conn: Optional[sqlite3.Connection] = None
        self._db_dir.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            self.close()

        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")

        cursor = self._conn.cursor()
        self._create_shared_tables(cursor)
        self._ensure_all_schema_tables(cursor)
        self._conn.commit()

        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _create_shared_tables(self, cursor: sqlite3.Cursor) -> None:
        for ddl in self.SHARED_DDL:
            cursor.execute(ddl)

    def _create_schema_tables(self, cursor: sqlite3.Cursor, schema: TaskSchema) -> None:
        for ddl in schema.ddl_statements:
            cursor.execute(ddl)

    def _ensure_all_schema_tables(self, cursor: sqlite3.Cursor) -> None:
        for schema in self._registry.list():
            self._create_schema_tables(cursor, schema)

    def execute(self, sql: str, params: dict | tuple = ()) -> sqlite3.Cursor:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn.execute(sql, params)

    def execute_many(self, sql: str, params_list: list[dict | tuple]) -> sqlite3.Cursor:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: dict | tuple = ()) -> Optional[dict]:
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self, sql: str, params: dict | tuple = ()) -> list[dict]:
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def table_exists(self, table_name: str) -> bool:
        cursor = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None
