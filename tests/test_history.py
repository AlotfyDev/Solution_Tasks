from __future__ import annotations

import re


class TestHistoryTracker:
    def test_record_change(self, engine, history):
        history.record_change("T1", "implementation", "status", "pending", "in_progress")
        engine._conn.commit()

        rows = history.get_history("T1")
        assert len(rows) == 1
        assert rows[0]["task_id"] == "T1"
        assert rows[0]["field_name"] == "status"
        assert rows[0]["old_value"] == "pending"
        assert rows[0]["new_value"] == "in_progress"
        assert rows[0]["changed_by"] == "cli"

    def test_record_status_change(self, engine, history):
        history.record_status_change("T2", "implementation", "pending", "completed")
        engine._conn.commit()

        rows = history.get_history("T2")
        assert len(rows) == 1
        assert rows[0]["field_name"] == "status"
        assert rows[0]["old_value"] == "pending"
        assert rows[0]["new_value"] == "completed"

    def test_record_creation(self, engine, history):
        history.record_creation("T3", "implementation")
        engine._conn.commit()

        rows = history.get_history("T3")
        assert len(rows) == 1
        assert rows[0]["field_name"] == "__created__"
        assert rows[0]["old_value"] is None
        assert rows[0]["new_value"] == "created"

    def test_get_history_ordered_by_id_desc(self, engine, history):
        history.record_change("T4", "implementation", "field1", None, "val1")
        history.record_change("T4", "implementation", "field2", None, "val2")
        history.record_change("T4", "implementation", "field3", None, "val3")
        engine._conn.commit()

        rows = history.get_history("T4", limit=10)
        assert len(rows) == 3
        assert rows[0]["field_name"] == "field3"
        assert rows[1]["field_name"] == "field2"
        assert rows[2]["field_name"] == "field1"

    def test_get_history_with_schema_filter(self, engine, history):
        history.record_change("T5", "implementation", "field1", None, "v1")
        history.record_change("T5", "testing", "field2", None, "v2")
        engine._conn.commit()

        impl_rows = history.get_history("T5", schema_id="implementation")
        test_rows = history.get_history("T5", schema_id="testing")
        assert len(impl_rows) == 1
        assert len(test_rows) == 1
        assert impl_rows[0]["field_name"] == "field1"
        assert test_rows[0]["field_name"] == "field2"

    def test_get_history_default_limit(self, engine, history):
        for i in range(5):
            history.record_change("T6", "implementation", f"f{i}", None, f"v{i}")
        engine._conn.commit()

        rows = history.get_history("T6", limit=3)
        assert len(rows) == 3

    def test_get_history_for_field(self, engine, history):
        history.record_change("T7", "implementation", "status", "pending", "in_progress")
        history.record_change("T7", "implementation", "status", "in_progress", "completed")
        history.record_change("T7", "implementation", "effort", None, "L")
        engine._conn.commit()

        status_rows = history.get_history_for_field("T7", "status")
        effort_rows = history.get_history_for_field("T7", "effort")
        assert len(status_rows) == 2
        assert len(effort_rows) == 1

    def test_get_history_for_field_with_schema(self, engine, history):
        history.record_change("T8", "implementation", "status", "a", "b")
        history.record_change("T8", "testing", "status", "c", "d")
        engine._conn.commit()

        rows = history.get_history_for_field("T8", "status", schema_id="implementation")
        assert len(rows) == 1
        assert rows[0]["old_value"] == "a"

    def test_get_recent_changes(self, engine, history):
        history.record_change("T9", "implementation", "status", "x", "y")
        history.record_change("T10", "testing", "field", None, "z")
        engine._conn.commit()

        recent = history.get_recent_changes(limit=10)
        assert len(recent) == 2

    def test_get_recent_changes_with_schema_filter(self, engine, history):
        history.record_change("T11", "implementation", "s", "a", "b")
        history.record_change("T12", "testing", "s", "c", "d")
        engine._conn.commit()

        impl_recent = history.get_recent_changes(limit=10, schema_id="implementation")
        test_recent = history.get_recent_changes(limit=10, schema_id="testing")
        assert len(impl_recent) == 1
        assert len(test_recent) == 1

    def test_get_recent_changes_default_limit(self, engine, history):
        for i in range(5):
            history.record_change(f"T{i}", "implementation", "f", None, "v")
        engine._conn.commit()

        recent = history.get_recent_changes()
        assert len(recent) == 5

    def test_iso8601_timestamp(self, engine, history):
        history.record_change("T_ISO", "implementation", "status", "a", "b")
        engine._conn.commit()

        rows = history.get_history("T_ISO")
        ts = rows[0]["changed_at"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts), f"Not ISO 8601: {ts}"

    def test_no_history_for_unknown_task(self, engine, history):
        rows = history.get_history("UNKNOWN")
        assert rows == []

    def test_no_history_for_field(self, engine, history):
        rows = history.get_history_for_field("UNKNOWN", "status")
        assert rows == []

    def test_custom_changed_by(self, engine, history):
        history.record_change("T_CB", "implementation", "status", "a", "b", changed_by="test_user")
        engine._conn.commit()

        rows = history.get_history("T_CB")
        assert rows[0]["changed_by"] == "test_user"

    def test_record_change_null_values(self, engine, history):
        history.record_change("T_NULL", "implementation", "__deleted__", None, None)
        engine._conn.commit()

        rows = history.get_history("T_NULL")
        assert rows[0]["old_value"] is None
        assert rows[0]["new_value"] is None
