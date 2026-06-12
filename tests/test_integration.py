from __future__ import annotations

import json

import pytest
from task_cli.data.engine import DatabaseEngine
from task_cli.data.store import TaskStore
from task_cli.history.tracker import HistoryTracker
from task_cli.presentation.commands import register_default_relationships
from task_cli.presentation.report import ReportGenerator
from task_cli.registry import RelationshipRegistry, SchemaRegistry
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema
from task_cli.validation.validator import TaskValidator


class TestIntegration:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp_path = tmp_path

        self.schema_registry = SchemaRegistry()
        register_implementation_schema(self.schema_registry)
        register_testing_schema(self.schema_registry)

        self.rel_registry = RelationshipRegistry()
        register_default_relationships(self.rel_registry)

        self.engine = DatabaseEngine(tmp_path, self.schema_registry)
        self.engine.connect()

        self.store = TaskStore(self.engine, self.schema_registry)
        self.history = HistoryTracker(self.engine)
        self.validator = TaskValidator(self.schema_registry)
        self.report = ReportGenerator(self.engine, self.store, self.history, self.schema_registry)

        self.impl_data = {
            "sub_task_id": "AA999-1",
            "sequence": 1,
            "hierarchy_level": 1,
            "source": {
                "file": "spec.md", "relative_path": ".",
                "lines": [1, 10], "section_title": "Integration",
                "section_markdown": "# Integration\nContent",
            },
            "metadata": {
                "phase": 2, "effort": "L", "dependencies": [],
                "parent_aa": "AA999", "parent_title": "Parent",
                "tags": ["integration", "e2e"],
            },
            "task": {
                "title": "Integration Feature",
                "description": "End-to-end integration feature",
                "implementation_notes": "Notes",
                "acceptance_criteria": [
                    {"id": "AA999-C1", "description": "Feature works", "verified_by": "review"},
                ],
                "files_to_modify": [
                    {"path": "src/main.cpp", "change_type": "modify", "description": "Add feature"},
                ],
            },
            "traceability": {},
            "status": {"state": "pending"},
        }

        self.test_data = {
            "sub_task_id": "TD-AA999-1",
            "sequence": 1,
            "hierarchy_level": 1,
            "source": {
                "file": "test.md", "relative_path": ".",
                "lines": [1, 15], "section_title": "Test Integration",
                "section_markdown": "# Test\nContent",
            },
            "metadata": {
                "phase": 2, "test_level": "integration",
                "parent_aa": "AA999", "parent_td": "TD999",
                "aa_dependencies": [], "tags": ["integration_test"],
            },
            "task": {
                "title": "Integration Test",
                "description": "Integration tests for feature",
                "implementation_notes": "Use gtest",
                "scenarios": [
                    {"id": "S1", "name": "Full flow", "type": "positive"},
                ],
                "files_to_modify": [
                    {
                        "path": "tests/integration_test.cpp",
                        "change_type": "create",
                        "framework": "gtest",
                        "test_cases": [
                            {"name": "FullFlowWorks", "fixture": "IntegrationFixture", "status": "template"},
                        ],
                    }
                ],
                "acceptance_criteria": [
                    {"id": "TC-1", "description": "Tests pass", "verified_by": "ci"},
                ],
            },
            "traceability": {
                "aa_reference": "AA999",
                "td_reference": "TD999",
            },
            "status": {"state": "pending"},
        }

        yield

        self.engine.close()

    def test_01_register_schemas(self):
        ids = self.schema_registry.list_ids()
        assert "implementation" in ids
        assert "testing" in ids

    def test_02_database_created(self):
        assert self.engine.db_path.exists()
        assert self.engine.table_exists("task_relationships")
        assert self.engine.table_exists("task_history")
        assert self.engine.table_exists("tasks_implementation")
        assert self.engine.table_exists("tasks_testing")

    def test_03_validate_impl_data(self):
        errors = self.validator.validate(self.impl_data, "implementation")
        assert errors == []

    def test_04_validate_test_data(self):
        errors = self.validator.validate(self.test_data, "testing")
        assert errors == []

    def test_05_insert_impl_task(self):
        task_id = self.store.insert_task("implementation", self.impl_data)
        self.history.record_creation(task_id, "implementation")
        self.engine._conn.commit()
        assert task_id == "AA999-1"

    def test_06_insert_test_task(self):
        task_id = self.store.insert_task("testing", self.test_data)
        self.history.record_creation(task_id, "testing")
        self.engine._conn.commit()
        assert task_id == "TD-AA999-1"

    def test_07_link_tasks(self):
        self.store.insert_task("implementation", self.impl_data)
        self.store.insert_task("testing", self.test_data)

        self.engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "TD-AA999-1", "ss": "testing", "t": "AA999-1", "ts": "implementation", "r": "tests"},
        )
        self.engine._conn.commit()

        rows = self.engine.fetchall(
            "SELECT * FROM task_relationships WHERE rel_type = 'tests'"
        )
        assert len(rows) == 1
        assert rows[0]["source_id"] == "TD-AA999-1"
        assert rows[0]["target_id"] == "AA999-1"

    def test_08_query_tasks(self):
        self.store.insert_task("implementation", self.impl_data)
        tasks = self.store.list_tasks("implementation")
        assert len(tasks) == 1
        assert tasks[0]["id"] == "AA999-1"

        task = self.store.get_task("implementation", "AA999-1")
        assert task is not None
        assert len(task["acceptance_criteria"]) == 1
        assert len(task["files"]) == 1
        assert len(task["tags"]) == 2

    def test_09_update_status(self):
        self.store.insert_task("implementation", self.impl_data)
        self.store.update_status("implementation", "AA999-1", "in_progress")
        self.history.record_status_change("AA999-1", "implementation", "pending", "in_progress")

        task = self.store.get_task("implementation", "AA999-1")
        assert task["status"] == "in_progress"

        self.store.update_status("implementation", "AA999-1", "completed")
        self.history.record_status_change("AA999-1", "implementation", "in_progress", "completed")
        self.engine._conn.commit()

        task = self.store.get_task("implementation", "AA999-1")
        assert task["status"] == "completed"

    def test_10_track_history(self):
        self.store.insert_task("implementation", self.impl_data)
        self.history.record_creation("AA999-1", "implementation")
        self.history.record_status_change("AA999-1", "implementation", "pending", "in_progress")
        self.history.record_change("AA999-1", "implementation", "title", "Old", "New")
        self.engine._conn.commit()

        history = self.history.get_history("AA999-1")
        assert len(history) == 3

        status_history = self.history.get_history_for_field("AA999-1", "status")
        assert len(status_history) == 1

    def test_11_generate_report(self):
        self.store.insert_task("implementation", self.impl_data)
        self.history.record_creation("AA999-1", "implementation")
        self.engine._conn.commit()

        report_str = self.report.full_report()
        assert "AA999-1" in report_str or "TASK PROGRESS REPORT" in report_str

        summary = self.report.summary_by_schema()
        assert summary["implementation"].get("pending") == 1

        export = self.report.export_json()
        assert len(export) >= 1

    def test_12_gap_analysis(self):
        self.store.insert_task("implementation", self.impl_data)
        output = self.report.gap_analysis()
        assert "AA999-1" in output

    def test_13_delete_task_cascades(self):
        self.store.insert_task("implementation", self.impl_data)
        self.store.insert_task("testing", self.test_data)

        deleted = self.store.delete_task("implementation", "AA999-1")
        assert deleted is True
        assert self.store.get_task("implementation", "AA999-1") is None

        criteria = self.engine.fetchall(
            "SELECT * FROM acceptance_criteria_implementation WHERE task_id = ?",
            ("AA999-1",),
        )
        assert len(criteria) == 0

        files = self.engine.fetchall(
            "SELECT * FROM task_files_implementation WHERE task_id = ?",
            ("AA999-1",),
        )
        assert len(files) == 0

        tags = self.engine.fetchall(
            "SELECT * FROM tags_implementation WHERE task_id = ?",
            ("AA999-1",),
        )
        assert len(tags) == 0

        # Testing task should still exist
        assert self.store.get_task("testing", "TD-AA999-1") is not None

    def test_14_full_workflow(self):
        # Complete workflow: validate -> insert -> link -> update -> history -> report -> delete
        assert self.validator.validate(self.impl_data, "implementation") == []
        assert self.validator.validate(self.test_data, "testing") == []

        impl_id = self.store.insert_task("implementation", self.impl_data)
        test_id = self.store.insert_task("testing", self.test_data)
        self.history.record_creation(impl_id, "implementation")
        self.history.record_creation(test_id, "testing")

        self.engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": test_id, "ss": "testing", "t": impl_id, "ts": "implementation", "r": "tests"},
        )

        self.store.update_status("implementation", impl_id, "completed")
        self.history.record_status_change(impl_id, "implementation", "pending", "completed")
        self.engine._conn.commit()

        task = self.store.get_task("implementation", impl_id)
        assert task["status"] == "completed"

        history = self.history.get_history(impl_id)
        assert len(history) >= 2

        report = self.report.full_report()
        assert "completed" in report

        export = self.report.export_json()
        assert len(export) == 2

        deleted = self.store.delete_task("implementation", impl_id)
        assert deleted is True
