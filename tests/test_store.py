from __future__ import annotations

import pytest
from task_cli.data.store import TaskStore


class TestTaskStoreInsert:
    def test_insert_impl_task(self, store, impl_task_data):
        task_id = store.insert_task("implementation", impl_task_data)
        assert task_id == "AA100-1"

    def test_insert_test_task(self, store, test_task_data):
        task_id = store.insert_task("testing", test_task_data)
        assert task_id == "TD-AA100-1"

    def test_insert_duplicate_pk_raises(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        with pytest.raises(Exception):
            store.insert_task("implementation", impl_task_data)

    def test_insert_impl_with_empty_criteria(self, store, impl_task_data):
        data = dict(impl_task_data)
        data["task"] = dict(data["task"])
        data["task"]["acceptance_criteria"] = []
        task_id = store.insert_task("implementation", data)
        assert task_id == "AA100-1"


class TestTaskStoreGet:
    def test_get_impl_task(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = store.get_task("implementation", "AA100-1")
        assert result is not None
        assert result["id"] == "AA100-1"
        assert result["title"] == "Implement feature X"
        assert result["status"] == "pending"
        assert result["phase"] == 1

    def test_get_impl_task_with_sub_entities(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = store.get_task("implementation", "AA100-1")
        assert len(result["acceptance_criteria"]) == 2
        assert len(result["files"]) == 2
        assert len(result["tags"]) == 2

    def test_get_impl_criteria_values(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = store.get_task("implementation", "AA100-1")
        criteria = result["acceptance_criteria"]
        assert criteria[0]["description"] == "Feature X works"
        assert criteria[0]["verified_by"] == "code_review"

    def test_get_impl_files_values(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = store.get_task("implementation", "AA100-1")
        files = result["files"]
        paths = {f["path"] for f in files}
        assert "src/core.cpp" in paths
        assert "include/core.h" in paths

    def test_get_impl_tags_values(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = store.get_task("implementation", "AA100-1")
        assert "backend" in result["tags"]
        assert "core" in result["tags"]

    def test_get_test_task(self, store, test_task_data):
        store.insert_task("testing", test_task_data)
        result = store.get_task("testing", "TD-AA100-1")
        assert result is not None
        assert result["id"] == "TD-AA100-1"
        assert result["test_level"] == "unit"

    def test_get_test_task_with_sub_entities(self, store, test_task_data):
        store.insert_task("testing", test_task_data)
        result = store.get_task("testing", "TD-AA100-1")
        assert len(result["scenarios"]) == 2
        assert len(result["files"]) == 1
        assert len(result["test_cases"]) == 2

    def test_get_test_scenarios_values(self, store, test_task_data):
        store.insert_task("testing", test_task_data)
        result = store.get_task("testing", "TD-AA100-1")
        names = {s["name"] for s in result["scenarios"]}
        assert "Happy path" in names
        assert "Null input" in names

    def test_get_test_cases_values(self, store, test_task_data):
        store.insert_task("testing", test_task_data)
        result = store.get_task("testing", "TD-AA100-1")
        names = {tc["name"] for tc in result["test_cases"]}
        assert "FeatureXWorks" in names
        assert "FeatureXNullInput" in names

    def test_get_nonexistent_task(self, store):
        result = store.get_task("implementation", "NONEXISTENT")
        assert result is None


class TestTaskStoreUpdate:
    def test_update_status(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.update_status("implementation", "AA100-1", "in_progress")
        result = store.get_task("implementation", "AA100-1")
        assert result["status"] == "in_progress"

    def test_update_status_multiple_times(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        for status in ["in_progress", "completed"]:
            store.update_status("implementation", "AA100-1", status)
        result = store.get_task("implementation", "AA100-1")
        assert result["status"] == "completed"

    def test_update_status_invalid_raises(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        with pytest.raises(ValueError, match="Invalid status"):
            store.update_status("implementation", "AA100-1", "invalid_state")

    def test_update_status_empty_string_raises(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        with pytest.raises(ValueError, match="Invalid status"):
            store.update_status("implementation", "AA100-1", "")

    def test_update_status_updates_timestamp(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.update_status("implementation", "AA100-1", "completed")
        result = store.get_task("implementation", "AA100-1")
        assert result["updated_at"] is not None
        assert result["updated_at"] != ""


class TestTaskStoreList:
    def test_list_no_filters(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        tasks = store.list_tasks("implementation")
        assert len(tasks) >= 1

    def test_list_multiple_tasks(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        data2 = dict(impl_task_data)
        data2["sub_task_id"] = "AA100-2"
        data2["task"] = dict(data2["task"])
        data2["source"] = dict(data2["source"])
        data2["metadata"] = dict(data2["metadata"])
        data2["status"] = dict(data2["status"])
        store.insert_task("implementation", data2)

        tasks = store.list_tasks("implementation")
        assert len(tasks) == 2

    def test_list_by_status(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.update_status("implementation", "AA100-1", "completed")

        pending = store.list_tasks("implementation", status_filter="pending")
        completed = store.list_tasks("implementation", status_filter="completed")
        assert len(pending) == 0
        assert len(completed) >= 1

    def test_list_by_phase(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        tasks = store.list_tasks("implementation", phase_filter=1)
        assert len(tasks) >= 1

    def test_list_by_phase_no_match(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        tasks = store.list_tasks("implementation", phase_filter=99)
        assert len(tasks) == 0

    def test_list_by_status_and_phase(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        tasks = store.list_tasks("implementation", status_filter="pending", phase_filter=1)
        assert len(tasks) >= 1
        for t in tasks:
            assert t["status"] == "pending"
            assert t["phase"] == 1

    def test_list_empty_schema(self, store):
        tasks = store.list_tasks("implementation")
        assert tasks == []


class TestTaskStoreDelete:
    def test_delete_task(self, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        deleted = store.delete_task("implementation", "AA100-1")
        assert deleted is True
        assert store.get_task("implementation", "AA100-1") is None

    def test_delete_nonexistent_task(self, store):
        deleted = store.delete_task("implementation", "NONEXISTENT")
        assert deleted is False

    def test_delete_cascades_criteria(self, store, engine, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.delete_task("implementation", "AA100-1")
        rows = engine.fetchall(
            "SELECT * FROM acceptance_criteria_implementation WHERE task_id = ?",
            ("AA100-1",),
        )
        assert len(rows) == 0

    def test_delete_cascades_files(self, store, engine, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.delete_task("implementation", "AA100-1")
        rows = engine.fetchall(
            "SELECT * FROM task_files_implementation WHERE task_id = ?",
            ("AA100-1",),
        )
        assert len(rows) == 0

    def test_delete_cascades_tags(self, store, engine, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.delete_task("implementation", "AA100-1")
        rows = engine.fetchall(
            "SELECT * FROM tags_implementation WHERE task_id = ?",
            ("AA100-1",),
        )
        assert len(rows) == 0

    def test_delete_cascades_all(self, store, engine, test_task_data):
        store.insert_task("testing", test_task_data)
        result_before = store.get_task("testing", "TD-AA100-1")
        assert len(result_before["scenarios"]) == 2
        assert len(result_before["test_cases"]) == 2

        store.delete_task("testing", "TD-AA100-1")
        assert store.get_task("testing", "TD-AA100-1") is None

        rows = engine.fetchall(
            "SELECT * FROM test_scenarios_testing WHERE task_id = ?",
            ("TD-AA100-1",),
        )
        assert len(rows) == 0
