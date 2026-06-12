from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest
from task_cli.data.engine import DatabaseEngine, resolve_db_dir
from task_cli.registry import SchemaRegistry
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema


class TestDatabaseEngine:
    def test_creates_db_file(self, tmp_path):
        registry = SchemaRegistry()
        register_implementation_schema(registry)
        register_testing_schema(registry)

        engine = DatabaseEngine(tmp_path, registry)
        engine.connect()
        assert engine.db_path.exists()
        assert engine.db_path.name == "tasks.db"
        engine.close()

    def test_shared_tables_exist(self, engine):
        assert engine.table_exists("task_relationships")
        assert engine.table_exists("task_history")

    def test_schema_tables_exist(self, engine, schema_registry):
        for sid in schema_registry.list_ids():
            schema = schema_registry.get(sid)
            for table_key, table_name in schema.table_names.items():
                assert engine.table_exists(table_name), f"Table {table_name} not found for {table_key}"

    def test_execute_insert_and_select(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "A1", "ss": "impl", "t": "B1", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        row = engine.fetchone(
            "SELECT source_id, target_id, rel_type FROM task_relationships WHERE source_id = :s",
            {"s": "A1"},
        )
        assert row is not None
        assert row["source_id"] == "A1"
        assert row["target_id"] == "B1"
        assert row["rel_type"] == "depends_on"

    def test_fetchone_returns_none(self, engine):
        row = engine.fetchone(
            "SELECT * FROM task_relationships WHERE source_id = ?", ("NONEXISTENT",)
        )
        assert row is None

    def test_fetchall(self, engine):
        for i in range(3):
            engine.execute(
                "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
                "VALUES (:s, :ss, :t, :ts, :r)",
                {"s": f"S{i}", "ss": "impl", "t": f"T{i}", "ts": "impl", "r": "depends_on"},
            )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT source_id FROM task_relationships ORDER BY source_id"
        )
        assert len(rows) == 3
        assert rows[0]["source_id"] == "S0"

    def test_execute_many(self, engine):
        params = [
            {"s": "X1", "ss": "impl", "t": "Y1", "ts": "impl", "r": "depends_on"},
            {"s": "X2", "ss": "impl", "t": "Y2", "ts": "impl", "r": "depends_on"},
        ]
        engine.execute_many(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            params,
        )
        engine._conn.commit()

        rows = engine.fetchall("SELECT source_id FROM task_relationships ORDER BY source_id")
        assert len(rows) == 2

    def test_execute_without_connect_raises(self, tmp_path):
        registry = SchemaRegistry()
        engine = DatabaseEngine(tmp_path, registry)
        with pytest.raises(RuntimeError, match="not connected"):
            engine.execute("SELECT 1")

    def test_table_exists_false(self, engine):
        assert not engine.table_exists("nonexistent_table")

    def test_connection_idempotent(self, engine, tmp_path):
        conn1 = engine._conn  # already connected from fixture
        engine.connect()  # second connect closes and reopens
        conn2 = engine._conn
        assert conn2 is not None
        assert conn2 is not conn1  # new connection object
        # Verify tables still exist after reconnect
        assert engine.table_exists("task_relationships")
        assert engine.table_exists("task_history")

    def test_wal_mode(self, engine):
        cursor = engine.execute("PRAGMA journal_mode")
        row = cursor.fetchone()
        wal_value = row[0] if hasattr(row, "__iter__") else row
        assert str(wal_value).lower() == "wal"

    def test_foreign_keys_enabled(self, engine):
        cursor = engine.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result is not None
        value = result[0]
        assert value == 1

    def test_close_cleanup(self, engine, tmp_path):
        db_path = engine.db_path
        engine.close()
        assert engine._conn is None
        # Can't execute after close
        with pytest.raises(RuntimeError, match="not connected"):
            engine.execute("SELECT 1")
        # File should still exist on disk
        assert db_path.exists()

    def test_db_path_property(self, engine, tmp_path):
        expected = tmp_path / "tasks.db"
        assert engine.db_path == expected

    def test_resolve_db_dir_cli_arg_takes_priority(self, tmp_path):
        result = resolve_db_dir(tmp_path)
        assert result == tmp_path

    def test_resolve_db_dir_falls_back_to_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TASK_DB_DIR", str(tmp_path))
        result = resolve_db_dir(None)
        assert result == tmp_path

    def test_resolve_db_dir_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("TASK_DB_DIR", "C:\\custom\\db")
        result = resolve_db_dir(None)
        assert result == Path("C:\\custom\\db")

    def test_resolve_db_dir_default_project_data_dir(self):
        result = resolve_db_dir(None)
        expected = Path(__file__).resolve().parent.parent / ".data"
        assert result == expected

    def test_no_schema_tables_when_empty_registry(self, tmp_path):
        registry = SchemaRegistry()
        engine = DatabaseEngine(tmp_path, registry)
        engine.connect()
        assert engine.table_exists("task_relationships")
        assert engine.table_exists("task_history")
        engine.close()
