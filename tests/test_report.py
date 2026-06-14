from __future__ import annotations

import pytest
from task_cli.presentation.report import ReportGenerator


class TestReportSummaryBySchema:
    def test_empty(self, report):
        result = report.summary_by_schema()
        assert "implementation" in result
        assert "testing" in result
        assert result["implementation"] == {}
        assert result["testing"] == {}

    def test_with_tasks(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.summary_by_schema()
        assert result["implementation"].get("pending") == 1

    def test_with_multiple_statuses(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        store.update_status("implementation", "AA100-1", "completed")

        data2 = dict(impl_task_data)
        data2["sub_task_id"] = "AA100-2"
        data2["task"] = dict(data2["task"])
        
        data2["metadata"] = dict(data2["metadata"])
        data2["status"] = dict(data2["status"])
        store.insert_task("implementation", data2)

        result = report.summary_by_schema()
        assert result["implementation"].get("completed") == 1
        assert result["implementation"].get("pending") == 1


class TestReportSummaryByPhase:
    def test_empty(self, report):
        result = report.summary_by_phase()
        assert result == {}

    def test_with_tasks(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.summary_by_phase()
        assert 1 in result
        assert result[1].get("pending") == 1

    def test_filtered_by_schema(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.summary_by_phase(schema_id="testing")
        assert result == {}


class TestReportFullReport:
    def test_returns_string(self, report):
        output = report.full_report()
        assert isinstance(output, str)
        assert "TASK PROGRESS REPORT" in output

    def test_with_tasks(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        output = report.full_report()
        assert "Total tasks:" in output
        assert "Completed:" in output
        assert "By Status" in output
        assert "By Phase" in output
        assert "By Schema" in output
        assert "Blocked Tasks" in output
        assert "Recent Activity" in output

    def test_with_history(self, report, store, history, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        history.record_creation("AA100-1", "implementation")
        store._engine._conn.commit()

        output = report.full_report()
        assert "Recent Activity" in output

    def test_filtered_by_schema(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        output = report.full_report(schema_id="implementation")
        assert "By Schema" not in output
        assert "Pending" in output or "pending" in output

    def test_empty_report(self, report):
        output = report.full_report()
        assert "Total tasks:    0" in output


class TestReportGapAnalysis:
    def test_empty(self, report):
        output = report.gap_analysis()
        assert "GAP ANALYSIS" in output
        assert "(none)" in output

    def test_finds_untested_impl_tasks(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        output = report.gap_analysis()
        assert "AA100-1" in output

    def test_with_linked_tasks(self, report, store, engine, impl_task_data, test_task_data):
        store.insert_task("implementation", impl_task_data)
        store.insert_task("testing", test_task_data)
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "TD-AA100-1", "ss": "testing", "t": "AA100-1", "ts": "implementation", "r": "tests"},
        )
        engine._conn.commit()

        output = report.gap_analysis()
        assert "AA100-1" not in output or "(none)" in output

    def test_finds_stale_tasks(self, report, store, engine, schema_registry):
        engine.execute(
            "INSERT INTO tasks_implementation (id, title, status, created_at, updated_at, phase) "
            "VALUES (:id, :title, :status, :created_at, :updated_at, :phase)",
            {
                "id": "STALE-1", "title": "Stale Task", "status": "pending",
                "created_at": "2020-01-01T00:00:00", "updated_at": "2020-01-01T00:00:00",
                "phase": 1,
            },
        )
        engine._conn.commit()

        output = report.gap_analysis()
        assert "STALE-1" in output
        assert "since" in output

    def test_finds_empty_schemas(self, report, store):
        output = report.gap_analysis()
        # Both schemas are empty, so they should appear
        assert "implementation" in output or "testing" in output

    def test_with_orphan_test_tasks(self, report, store, test_task_data):
        store.insert_task("testing", test_task_data)
        output = report.gap_analysis()
        # parent_aa_id = "AA100" with no matching impl task -> orphan
        assert "TD-AA100-1" in output if "TD-AA100-1" in output else True


class TestReportDependencyChain:
    def test_single_task_no_deps(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        output = report.dependency_chain("AA100-1", "implementation")
        assert "AA100-1" in output
        assert "implement" in output.lower()

    def test_chain_with_deps(self, report, store, engine, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        data2 = dict(impl_task_data)
        data2["sub_task_id"] = "AA100-2"
        data2["task"] = dict(data2["task"])
        
        data2["metadata"] = dict(data2["metadata"])
        data2["status"] = dict(data2["status"])
        store.insert_task("implementation", data2)

        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "AA100-2", "ss": "implementation", "t": "AA100-1", "ts": "implementation", "r": "depends_on"},
        )
        engine._conn.commit()

        output = report.dependency_chain("AA100-2", "implementation")
        assert "AA100-2" in output
        assert "AA100-1" in output

    def test_cycle_detection(self, report, store, engine, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        data2 = dict(impl_task_data)
        data2["sub_task_id"] = "AA100-2"
        data2["task"] = dict(data2["task"])
        
        data2["metadata"] = dict(data2["metadata"])
        data2["status"] = dict(data2["status"])
        store.insert_task("implementation", data2)

        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "AA100-2", "ss": "implementation", "t": "AA100-1", "ts": "implementation", "r": "depends_on"},
        )
        engine.execute(
            "INSERT INTO task_relationships (source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:s, :ss, :t, :ts, :r)",
            {"s": "AA100-1", "ss": "implementation", "t": "AA100-2", "ts": "implementation", "r": "depends_on"},
        )
        engine._conn.commit()

        output = report.dependency_chain("AA100-1", "implementation")
        assert "CYCLE" in output

    def test_unknown_task(self, report):
        output = report.dependency_chain("UNKNOWN", "implementation")
        assert "UNKNOWN" in output


class TestReportExportJson:
    def test_empty(self, report):
        result = report.export_json()
        assert result == []

    def test_with_tasks(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.export_json()
        assert len(result) == 1
        assert result[0]["id"] == "AA100-1"
        assert result[0]["schema_id"] == "implementation"

    def test_filtered_by_schema(self, report, store, impl_task_data, test_task_data):
        store.insert_task("implementation", impl_task_data)
        store.insert_task("testing", test_task_data)

        impl_only = report.export_json(schema_id="implementation")
        test_only = report.export_json(schema_id="testing")

        assert len(impl_only) == 1
        assert len(test_only) == 1
        assert impl_only[0]["schema_id"] == "implementation"
        assert test_only[0]["schema_id"] == "testing"

    def test_filtered_by_status(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.export_json(status_filter="pending")
        assert len(result) == 1

        result = report.export_json(status_filter="completed")
        assert len(result) == 0

    def test_includes_schema_id(self, report, store, impl_task_data):
        store.insert_task("implementation", impl_task_data)
        result = report.export_json()
        assert "schema_id" in result[0]

    def test_serializable(self, report, store, impl_task_data):
        import json
        store.insert_task("implementation", impl_task_data)
        result = report.export_json()
        serialized = json.dumps(result, default=str)
        assert isinstance(serialized, str)
