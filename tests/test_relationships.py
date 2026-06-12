from __future__ import annotations

import sqlite3

import pytest


class TestRelationships:
    def test_insert_and_query(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "AA100-1", "ss": "implementation", "t": "TD-AA100-1", "ts": "testing", "r": "tests"},
        )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT source_id, target_id, rel_type FROM task_relationships"
        )
        assert len(rows) == 1
        assert rows[0]["source_id"] == "AA100-1"
        assert rows[0]["target_id"] == "TD-AA100-1"
        assert rows[0]["rel_type"] == "tests"

    def test_query_by_source(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "A1", "ss": "impl", "t": "B1", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT * FROM task_relationships WHERE source_id = :sid",
            {"sid": "A1"},
        )
        assert len(rows) == 1
        assert rows[0]["target_id"] == "B1"

    def test_query_by_target(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "A2", "ss": "impl", "t": "B2", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT * FROM task_relationships WHERE target_id = :tid",
            {"tid": "B2"},
        )
        assert len(rows) == 1
        assert rows[0]["source_id"] == "A2"

    def test_with_properties_json(self, engine):
        props = '{"weight": 5, "description": "Critical path"}'
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type, properties_json) "
            "VALUES (:s, :ss, :t, :ts, :r, :p)",
            {"s": "A3", "ss": "impl", "t": "B3", "ts": "impl", "r": "depends_on", "p": props},
        )
        engine._conn.commit()

        row = engine.fetchone(
            "SELECT properties_json FROM task_relationships WHERE source_id = :sid",
            {"sid": "A3"},
        )
        assert row is not None
        assert row["properties_json"] == props

    def test_duplicate_pk_violation(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "DUP", "ss": "impl", "t": "DUP2", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            engine.execute(
                "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
                "VALUES (:s, :ss, :t, :ts, :r)",
                {"s": "DUP", "ss": "impl", "t": "DUP2", "ts": "impl", "r": "depends_on"},
            )

    def test_multiple_relationships_same_tasks(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "M", "ss": "impl", "t": "N", "ts": "impl", "r": "depends_on"},
        )
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "M", "ss": "impl", "t": "N", "ts": "impl", "r": "implements"},
        )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT rel_type FROM task_relationships WHERE source_id = :sid",
            {"sid": "M"},
        )
        assert len(rows) == 2

    def test_created_at_default(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "C", "ss": "impl", "t": "D", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        row = engine.fetchone(
            "SELECT created_at FROM task_relationships WHERE source_id = :sid",
            {"sid": "C"},
        )
        assert row is not None
        assert row["created_at"] is not None

    def test_delete_relationship(self, engine):
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "DEL", "ss": "impl", "t": "DEL2", "ts": "impl", "r": "depends_on"},
        )
        engine._conn.commit()

        engine.execute(
            "DELETE FROM task_relationships WHERE source_id = :sid",
            {"sid": "DEL"},
        )
        engine._conn.commit()

        rows = engine.fetchall(
            "SELECT * FROM task_relationships WHERE source_id = :sid",
            {"sid": "DEL"},
        )
        assert len(rows) == 0


class TestDefaultRelationships:
    def test_default_relationships_registered(self, rel_registry):
        names = {r.name for r in rel_registry.list()}
        assert "tests" in names
        assert "depends_on" in names
        assert "implements" in names
        assert "verifies" in names

    def test_tests_relationship(self, rel_registry):
        rel = rel_registry.get("tests")
        assert rel.source_schema_id == "testing"
        assert rel.target_schema_id == "implementation"

    def test_depends_on_relationship(self, rel_registry):
        rel = rel_registry.get("depends_on")
        assert rel.source_schema_id == "implementation"
        assert rel.target_schema_id == "implementation"

    def test_verifies_relationship(self, rel_registry):
        rel = rel_registry.get("verifies")
        assert rel.source_schema_id == "testing"
        assert rel.target_schema_id == "implementation"
