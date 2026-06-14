from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from task_cli.mcp_server import (
    catalog_resource,
    delete_task,
    dependency_chain,
    document_resource,
    entry,
    gap_analysis,
    get_catalog,
    get_context,
    get_document,
    get_history,
    get_task,
    insert_document,
    insert_task,
    link_tasks,
    list_documents,
    list_tasks,
    mcp,
    search_tasks,
    status_report,
    task_resource,
    schema_resource,
    status_resource,
    update_status,
    validate_task,
)
from task_cli.presentation.commands import AppContext


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_context(tmp_path):
    """Reset the lazy global context before each test and re-init with tmp dir."""
    import task_cli.mcp_server as svr

    ctx = AppContext()
    ctx.initialize(db_dir=tmp_path)
    svr._context = ctx
    yield ctx
    svr._context = None


@pytest.fixture
def ctx(_reset_context):
    return _reset_context


@pytest.fixture
def impl_task_data():
    return {
        "sub_task_id": "AA200-1",
        "sequence": 1,
        "hierarchy_level": 1,
        "parent_doc_id": "AA200",
        "task": {
            "title": "Implement feature Y",
            "description": "Implement feature Y in the core module",
            "implementation_notes": "Use existing patterns",
            "acceptance_criteria": [
                {"id": "AA200-C1", "description": "Feature Y works", "verified_by": "code_review"},
            ],
            "files_to_modify": [
                {"path": "src/core.cpp", "change_type": "modify", "description": "Add feature Y"},
            ],
        },
        "metadata": {
            "phase": 1,
            "effort": "M",
            "dependencies": [],
            "parent_aa": "AA200",
            "parent_title": "Parent",
            "tags": ["backend"],
        },
        "traceability": {},
        "status": {"state": "pending"},
    }


@pytest.fixture
def test_task_data():
    return {
        "sub_task_id": "TD-AA200-1",
        "sequence": 1,
        "hierarchy_level": 1,
        "parent_doc_id": "AA200",
        "task": {
            "title": "Test feature Y",
            "description": "Write unit tests for feature Y",
            "implementation_notes": "Use gtest",
            "scenarios": [
                {"id": "S1", "name": "Happy path", "type": "positive"},
            ],
            "files_to_modify": [
                {
                    "path": "tests/core_test.cpp",
                    "change_type": "create",
                    "framework": "gtest",
                    "test_cases": [
                        {"name": "FeatureYWorks", "fixture": "FeatureYTest", "status": "template"},
                    ],
                }
            ],
            "acceptance_criteria": [
                {"id": "TC-1", "description": "Tests compile and pass", "verified_by": "ci"},
            ],
        },
        "metadata": {
            "phase": 1,
            "test_level": "unit",
            "parent_aa": "AA200",
            "parent_td": "TD1",
            "aa_dependencies": [],
            "tags": ["unit_test"],
        },
        "traceability": {
            "aa_reference": "AA200",
            "td_reference": "TD1",
        },
        "status": {"state": "pending"},
    }


# ── Tool existence tests ─────────────────────────────────────────────


class TestToolExistence:
    def test_list_tools(self):
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "list_tasks" in tools
        assert "get_task" in tools
        assert "insert_task" in tools
        assert "update_status" in tools
        assert "delete_task" in tools
        assert "link_tasks" in tools
        assert "status_report" in tools
        assert "gap_analysis" in tools
        assert "dependency_chain" in tools
        assert "search_tasks" in tools
        assert "validate_task" in tools
        assert "get_history" in tools
        assert "get_catalog" in tools
        assert len(tools) >= 13


# ── Tool behavior tests ─────────────────────────────────────────────


class TestListTasks:
    def test_empty(self):
        result = list_tasks()
        assert result == []

    def test_with_tasks(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = list_tasks()
        assert len(result) == 1
        assert result[0]["id"] == "AA200-1"

    def test_filter_by_status(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = list_tasks(status="completed")
        assert result == []

    def test_filter_by_phase(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = list_tasks(phase=1)
        assert len(result) == 1
        result = list_tasks(phase=99)
        assert result == []


class TestGetTask:
    def test_existing(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = get_task("AA200-1")
        assert result["id"] == "AA200-1"
        assert result["title"] == "Implement feature Y"

    def test_missing(self):
        result = get_task("UNKNOWN")
        assert result == {}

    def test_with_sub_entities(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = get_task("AA200-1")
        assert "acceptance_criteria" in result
        assert len(result["acceptance_criteria"]) == 1


class TestInsertTask:
    def test_valid_impl(self, ctx):
        data = {
            "sub_task_id": "AA300-1",
            "sequence": 1,
            "hierarchy_level": 1,
            "source": {
                "file": "s.md", "relative_path": ".", "lines": [1, 2],
                "section_title": "S", "section_markdown": "# S",
            },
            "metadata": {"phase": 1, "effort": "S", "dependencies": [], "parent_aa": "AA300", "parent_title": "P"},
            "task": {
                "title": "T", "description": "D", "implementation_notes": "",
                "acceptance_criteria": [
                    {"id": "AA300-C1", "description": "Works", "verified_by": "review"},
                ],
                "files_to_modify": [],
            },
            "traceability": {},
            "status": {"state": "pending"},
        }
        result = insert_task(json.dumps(data))
        assert "Inserted" in result
        assert "AA300-1" in result

    def test_valid_test(self, ctx, test_task_data):
        result = insert_task(json.dumps(test_task_data))
        assert "Inserted" in result
        assert "TD-AA200-1" in result

    def test_invalid_json(self, ctx):
        result = insert_task("not json")
        assert "Invalid JSON" in result

    def test_validation_error(self, ctx):
        data = {"sub_task_id": "AA400-1", "bad": "data"}
        result = insert_task(json.dumps(data))
        assert "Validation errors" in result

    def test_auto_detect_schema(self, ctx, test_task_data):
        result = insert_task(json.dumps(test_task_data), schema_id=None)
        assert "Inserted" in result

    def test_creates_history(self, ctx, impl_task_data):
        insert_task(json.dumps(impl_task_data))
        history = get_history("AA200-1")
        assert any(h["field_name"] == "__created__" for h in history)


class TestUpdateStatus:
    def test_valid_update(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = update_status("AA200-1", "in_progress")
        assert "Updated" in result
        assert get_task("AA200-1")["status"] == "in_progress"

    def test_nonexistent(self):
        result = update_status("UNKNOWN", "completed")
        assert "not found" in result

    def test_invalid_status(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = update_status("AA200-1", "invalid_state")
        assert "Invalid status" in result


class TestDeleteTask:
    def test_existing(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = delete_task("AA200-1")
        assert "Deleted" in result
        assert get_task("AA200-1") == {}

    def test_nonexistent(self):
        result = delete_task("UNKNOWN")
        assert "not found" in result


class TestLinkTasks:
    def test_link_valid(self, ctx, impl_task_data, test_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.store.insert_task("testing", test_task_data)
        ctx.engine._conn.commit()
        result = link_tasks("TD-AA200-1", "AA200-1")
        assert "Linked" in result
        rows = ctx.engine.fetchall("SELECT * FROM task_relationships")
        assert len(rows) == 1

    def test_invalid_rel_type(self, ctx):
        result = link_tasks("A", "B", rel_type="invalid_type")
        assert "not found" in result

    def test_wrong_schema(self, ctx):
        result = link_tasks("A", "B", source_schema="implementation", target_schema="testing")
        assert "expects source schema" in result

    def test_with_properties(self, ctx, impl_task_data, test_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.store.insert_task("testing", test_task_data)
        ctx.engine._conn.commit()
        props = '{"weight": 5}'
        result = link_tasks("TD-AA200-1", "AA200-1", properties=props)
        assert "Linked" in result


class TestStatusReport:
    def test_returns_report(self, ctx):
        result = status_report()
        assert isinstance(result, str)
        assert "TASK PROGRESS REPORT" in result

    def test_with_tasks(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = status_report()
        assert "Total tasks:" in result


class TestGapAnalysis:
    def test_returns_analysis(self, ctx):
        result = gap_analysis()
        assert "GAP ANALYSIS" in result

    def test_with_untested(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = gap_analysis()
        assert "AA200-1" in result


class TestDependencyChain:
    def test_no_deps(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        result = dependency_chain("AA200-1", "implementation")
        assert "AA200-1" in result

    def test_unknown(self):
        result = dependency_chain("UNKNOWN", "implementation")
        assert "UNKNOWN" in result


class TestSearchTasks:
    def test_empty(self):
        assert search_tasks("nonexistent") == []

    def test_finds_title(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        results = search_tasks("Implement")
        assert len(results) >= 1
        assert any(r["id"] == "AA200-1" for r in results)

    def test_finds_description(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        results = search_tasks("core module")
        assert len(results) >= 1

    def test_includes_schema_id(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        results = search_tasks("Implement")
        assert results[0].get("schema_id") == "implementation"


class TestValidateTask:
    def test_valid_impl(self):
        data = {
            "sub_task_id": "AA500-1",
            "sequence": 1,
            "hierarchy_level": 1,
            "source": {
                "file": "s.md", "relative_path": ".", "lines": [1, 2],
                "section_title": "S", "section_markdown": "# S",
            },
            "metadata": {"phase": 1, "effort": "S", "dependencies": [], "parent_aa": "AA500", "parent_title": "P"},
            "task": {
                "title": "T", "description": "D", "implementation_notes": "",
                "acceptance_criteria": [
                    {"id": "AA500-C1", "description": "Works", "verified_by": "review"},
                ],
                "files_to_modify": [],
            },
            "traceability": {},
            "status": {"state": "pending"},
        }
        result = validate_task(json.dumps(data))
        assert "valid" in result

    def test_invalid_json(self):
        result = validate_task("not json")
        assert "Invalid JSON" in result

    def test_validation_failure(self):
        data = {"sub_task_id": "AA600-1", "bad": "data"}
        result = validate_task(json.dumps(data))
        assert "Validation errors" in result

    def test_valid_test(self, ctx, test_task_data):
        result = validate_task(json.dumps(test_task_data))
        assert "valid" in result


class TestGetHistory:
    def test_empty(self):
        assert get_history("UNKNOWN") == []

    def test_with_history(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.history.record_creation("AA200-1", "implementation")
        ctx.engine._conn.commit()
        history = get_history("AA200-1")
        assert len(history) >= 1

    def test_limit(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.history.record_creation("AA200-1", "implementation")
        ctx.history.record_status_change("AA200-1", "implementation", "pending", "in_progress")
        ctx.engine._conn.commit()
        history = get_history("AA200-1", limit=1)
        assert len(history) == 1

    def test_filter_schema(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.history.record_creation("AA200-1", "implementation")
        ctx.engine._conn.commit()
        history = get_history("AA200-1", schema_id="implementation")
        assert len(history) >= 1
        history = get_history("AA200-1", schema_id="testing")
        assert len(history) == 0


# ── Resource tests ───────────────────────────────────────────────────


class TestTaskResource:
    def test_existing(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        raw = task_resource("implementation", "AA200-1")
        data = json.loads(raw)
        assert data["id"] == "AA200-1"
        assert data["title"] == "Implement feature Y"

    def test_missing(self):
        raw = task_resource("implementation", "UNKNOWN")
        data = json.loads(raw)
        assert "error" in data


class TestSchemaResource:
    def test_impl_schema(self):
        raw = schema_resource("implementation")
        data = json.loads(raw)
        assert "$schema" in data or "type" in data or "properties" in data

    def test_testing_schema(self):
        raw = schema_resource("testing")
        data = json.loads(raw)
        assert "$schema" in data or "type" in data or "properties" in data

    def test_missing(self):
        raw = schema_resource("nonexistent")
        data = json.loads(raw)
        assert "error" in data


class TestStatusResource:
    def test_returns_report(self, ctx):
        raw = status_resource()
        assert isinstance(raw, str)
        assert "TASK PROGRESS REPORT" in raw

    def test_with_data(self, ctx, impl_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.engine._conn.commit()
        raw = status_resource()
        assert "AA200-1" not in raw  # status report doesn't list specific tasks by default
        assert "Total tasks:" in raw


class TestGetCatalog:
    def test_returns_markdown_default(self):
        result = get_catalog()
        assert isinstance(result, str)
        assert "# Task Toolkit" in result
        assert "## Overview" in result
        assert "## CLI Commands" in result
        assert "## MCP Tools" in result
        assert "## Registered Schemas" in result

    def test_returns_json(self):
        result = get_catalog(format="json")
        data = json.loads(result)
        assert data["system"] == "Task Toolkit"
        assert "schemas" in data
        assert "cli_commands" in data
        assert "mcp_tools" in data
        assert "mcp_resources" in data

    def test_contains_schemas(self):
        result = get_catalog()
        assert "implementation" in result
        assert "testing" in result

    def test_contains_relationships(self):
        result = get_catalog()
        assert "tests" in result
        assert "depends_on" in result
        assert "implements" in result
        assert "verifies" in result


class TestCatalogResource:
    def test_returns_markdown(self, ctx):
        raw = catalog_resource()
        assert isinstance(raw, str)
        assert "# Task Toolkit" in raw
        assert "## Overview" in raw

    def test_contains_all_sections(self, ctx):
        raw = catalog_resource()
        assert "## CLI Commands" in raw
        assert "## MCP Tools" in raw
        assert "## Registered Schemas" in raw
        assert "## Registered Relationships" in raw
        assert "## MCP Resources" in raw
        assert "## Connection Guides" in raw
        assert "## Quick Start" in raw

    def test_lists_schemas_dynamically(self, ctx):
        raw = catalog_resource()
        assert "implementation" in raw
        assert "testing" in raw


# ── Error handling tests ─────────────────────────────────────────────


class TestErrorHandling:
    def test_insert_task_invalid_json(self):
        result = insert_task("{bad json}")
        assert "Invalid JSON" in result

    def test_validate_task_invalid_json(self):
        result = validate_task("{bad json}")
        assert "Invalid JSON" in result

    def test_delete_nonexistent(self):
        result = delete_task("NONEXISTENT")
        assert "not found" in result

    def test_update_nonexistent(self):
        result = update_status("NONEXISTENT", "completed")
        assert "not found" in result

    def test_get_task_missing(self):
        assert get_task("NONEXISTENT") == {}

    def test_link_invalid_rel(self):
        result = link_tasks("A", "B", rel_type="unknown_rel")
        assert "not found" in result

    def test_link_duplicate(self, ctx, impl_task_data, test_task_data):
        ctx.store.insert_task("implementation", impl_task_data)
        ctx.store.insert_task("testing", test_task_data)
        ctx.engine._conn.commit()
        link_tasks("TD-AA200-1", "AA200-1")
        result = link_tasks("TD-AA200-1", "AA200-1")
        assert "Error" in result

    def test_resource_missing_task(self):
        raw = task_resource("implementation", "GHOST")
        data = json.loads(raw)
        assert "error" in data

    def test_resource_missing_schema(self):
        raw = schema_resource("bogus")
        data = json.loads(raw)
        assert "error" in data


# ── Entry-point / SSE tests ─────────────────────────────────────────


class TestEntryArgumentParsing:
    def _ns(self, **kw):
        defaults = dict(sse=False, port=8000, host="127.0.0.1", db_dir=None)
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_parser_defaults(self):
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=self._ns()):
            with patch.object(mcp, "run") as mock_run:
                entry()
        mock_run.assert_called_once_with(transport="stdio")

    def test_parser_sse_default_port(self):
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=self._ns(sse=True)):
            with patch("task_cli.mcp_server.print"):
                with patch.object(mcp, "run") as mock_run:
                    entry()
        mock_run.assert_called_once_with(transport="sse", host="127.0.0.1", port=8000)

    def test_parser_sse_with_port(self):
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=self._ns(sse=True, port=8999)):
            with patch("task_cli.mcp_server.print"):
                with patch.object(mcp, "run") as mock_run:
                    entry()
        mock_run.assert_called_once_with(transport="sse", host="127.0.0.1", port=8999)

    def test_parser_sse_custom_host(self):
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=self._ns(sse=True, host="0.0.0.0")):
            with patch("task_cli.mcp_server.print"):
                with patch.object(mcp, "run") as mock_run:
                    entry()
        mock_run.assert_called_once_with(transport="sse", host="0.0.0.0", port=8000)

    def test_parser_sse_no_uvicorn_exits(self):
        ns = self._ns(sse=True, port=9999)
        import builtins
        _real_import = builtins.__import__
        def _mock_import(name, *args, **kwargs):
            if name == "uvicorn":
                raise ImportError("no uvicorn")
            return _real_import(name, *args, **kwargs)
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=ns):
            with patch("task_cli.mcp_server.print"):
                with patch("builtins.__import__", side_effect=_mock_import):
                    with pytest.raises(SystemExit):
                        entry()

    def test_entry_stdio_invokes_run(self):
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=self._ns()):
            with patch.object(mcp, "run") as mock_run:
                entry()
        mock_run.assert_called_once_with(transport="stdio")


# ── Lazy initialization tests ───────────────────────────────────────


class TestLazyInit:
    def test_context_is_none_before_first_call(self):
        import task_cli.mcp_server as svr_m

        svr_m._context = None
        saved = svr_m.get_context()
        assert saved is not None
        # now that get_context was called, _context is set
        svr_m._context = None
        # The module-level _context should be None at initial import time
        assert svr_m._context is None

    def test_get_context_returns_app_context(self):
        ctx = get_context()
        assert ctx.schema_registry is not None
        assert ctx.rel_registry is not None
        assert ctx.validator is not None
        assert ctx.engine is not None
        assert ctx.store is not None
        assert ctx.history is not None

    def test_get_context_is_singleton(self):
        ctx1 = get_context()
        ctx2 = get_context()
        assert ctx1 is ctx2

    def test_get_context_initializes_schemas(self):
        ctx = get_context()
        ids = ctx.schema_registry.list_ids()
        assert "implementation" in ids
        assert "testing" in ids
        assert "document" in ids

    def test_get_context_creates_db(self):
        ctx = get_context()
        assert ctx.engine.db_path.exists()


# ── Document MCP tool tests ───────────────────────────────────────────


class TestInsertDocument:
    def test_valid_doc(self, ctx):
        data = {
            "doc_id": "AA-DOC",
            "file_path": "docs/spec.md",
            "title": "AA-DOC — Test",
            "content": "# AA-DOC\n\nTest content.",
            "status": {"state": "pending"},
        }
        result = insert_document(json.dumps(data))
        assert "Inserted document" in result
        assert "AA-DOC" in result

    def test_invalid_json(self, ctx):
        result = insert_document("not json")
        assert "Invalid JSON" in result

    def test_validation_error(self, ctx):
        data = {"bad": "data"}
        result = insert_document(json.dumps(data))
        assert "Validation errors" in result


class TestGetDocument:
    def test_existing(self, ctx):
        ctx.store.insert_document({
            "doc_id": "AA-DOC2",
            "file_path": "docs/spec2.md",
            "title": "AA-DOC2",
            "content": "# AA-DOC2",
        })
        ctx.engine._conn.commit()
        result = get_document("AA-DOC2")
        assert result["id"] == "AA-DOC2"
        assert result["title"] == "AA-DOC2"

    def test_missing(self):
        result = get_document("UNKNOWN-DOC")
        assert result == {}


class TestListDocuments:
    def test_empty(self):
        result = list_documents()
        assert result == []

    def test_with_documents(self, ctx):
        ctx.store.insert_document({
            "doc_id": "AA-DOC3",
            "file_path": "docs/spec3.md",
            "title": "AA-DOC3",
            "content": "# AA-DOC3",
        })
        ctx.engine._conn.commit()
        result = list_documents()
        assert len(result) == 1
        assert result[0]["id"] == "AA-DOC3"


# ── Document resource tests ───────────────────────────────────────────


class TestDocumentResource:
    def test_existing(self, ctx):
        ctx.store.insert_document({
            "doc_id": "AA-DOC4",
            "file_path": "docs/spec4.md",
            "title": "AA-DOC4",
            "content": "# AA-DOC4",
        })
        ctx.engine._conn.commit()
        raw = document_resource("AA-DOC4")
        data = json.loads(raw)
        assert data["id"] == "AA-DOC4"

    def test_missing(self):
        raw = document_resource("UNKNOWN-DOC")
        data = json.loads(raw)
        assert "error" in data


