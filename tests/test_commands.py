from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from task_cli.presentation.commands import (
    AppContext,
    build_parser,
    cmd_delete,
    cmd_get,
    cmd_history,
    cmd_insert,
    cmd_link,
    cmd_list,
    cmd_log,
    cmd_query,
    cmd_schemas,
    cmd_status,
    cmd_update,
    cmd_validate,
    register_default_relationships,
)
from task_cli.registry import RelationshipRegistry


class TestBuildParser:
    def test_returns_parser(self):
        parser = build_parser()
        assert parser is not None
        assert parser.description is not None

    def test_has_subcommands(self):
        parser = build_parser()
        subactions = parser._subparsers._group_actions
        for action in subactions:
            for name, subparser in action.choices.items():
                assert subparser is not None

    def test_validate_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["validate", "file.json"])
        assert args.command == "validate"
        assert args.file == "file.json"
        assert args.schema is None

    def test_insert_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["insert", "task.json", "--schema", "testing"])
        assert args.command == "insert"
        assert args.file == "task.json"
        assert args.schema == "testing"

    def test_update_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["update", "T1", "--status", "completed"])
        assert args.command == "update"
        assert args.task_id == "T1"
        assert args.status == "completed"

    def test_list_subcommand_with_filters(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--schema", "implementation", "--status", "pending", "--phase", "2"])
        assert args.command == "list"
        assert args.schema == "implementation"
        assert args.status == "pending"
        assert args.phase == 2

    def test_link_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["link", "A", "B", "--type", "depends_on"])
        assert args.command == "link"
        assert args.source_id == "A"
        assert args.target_id == "B"
        assert args.rel_type == "depends_on"

    def test_query_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["query", "SELECT * FROM tasks_implementation"])
        assert args.command == "query"
        assert args.sql == "SELECT * FROM tasks_implementation"


class TestAppContext:
    def test_initialization_creates_components(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        assert ctx.schema_registry is not None
        assert ctx.rel_registry is not None
        assert ctx.validator is not None
        assert ctx.engine is not None
        assert ctx.store is not None
        assert ctx.history is not None
        assert ctx.db_dir == tmp_path

    def test_initialization_registers_schemas(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        ids = ctx.schema_registry.list_ids()
        assert "implementation" in ids
        assert "testing" in ids

    def test_initialization_creates_db(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        assert ctx.engine.db_path.exists()
        assert ctx.engine.table_exists("task_relationships")

    def test_initialize_without_db_dir(self):
        ctx = AppContext()
        ctx.initialize()
        expected = Path(__file__).resolve().parent.parent / ".data"
        assert ctx.db_dir == expected

    def test_app_context_accepts_explicit_db_dir(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        assert ctx.db_dir == tmp_path


class TestRegisterDefaultRelationships:
    def test_registers_four_relationships(self):
        registry = RelationshipRegistry()
        register_default_relationships(registry)
        assert len(registry.list()) == 4

    def test_relationships_have_correct_schemas(self):
        registry = RelationshipRegistry()
        register_default_relationships(registry)
        assert registry.get("tests").source_schema_id == "testing"
        assert registry.get("tests").target_schema_id == "implementation"
        assert registry.get("depends_on").source_schema_id == "implementation"
        assert registry.get("implements").source_schema_id == "implementation"
        assert registry.get("verifies").source_schema_id == "testing"


class TestCmdValidate:
    def test_valid_impl_file(self, app_context, impl_json_file, capsys):
        args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_validate(args, app_context)
        captured = capsys.readouterr()
        assert "valid" in captured.out

    def test_valid_test_file(self, app_context, test_json_file, capsys):
        args = argparse.Namespace(file=str(test_json_file), schema=None)
        cmd_validate(args, app_context)
        captured = capsys.readouterr()
        assert "valid" in captured.out

    def test_missing_file(self, app_context, capsys):
        missing = str(app_context.db_dir / "nonexistent.json")
        args = argparse.Namespace(file=missing, schema=None)
        cmd_validate(args, app_context)
        captured = capsys.readouterr()
        assert "file not found" in captured.out

    def test_invalid_json(self, app_context, capsys):
        bad_file = app_context.db_dir / "bad.json"
        bad_file.write_text("not json")
        args = argparse.Namespace(file=str(bad_file), schema=None)
        cmd_validate(args, app_context)
        captured = capsys.readouterr()
        assert "invalid JSON" in captured.out


class TestCmdInsert:
    def test_insert_valid_file(self, app_context, impl_json_file, capsys):
        args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_insert(args, app_context)
        captured = capsys.readouterr()
        assert "Inserted" in captured.out

    def test_insert_missing_file(self, app_context, capsys):
        missing = str(app_context.db_dir / "missing.json")
        args = argparse.Namespace(file=missing, schema=None)
        cmd_insert(args, app_context)
        captured = capsys.readouterr()
        assert "file not found" in captured.out

    def test_insert_and_retrieve(self, app_context, impl_json_file, capsys):
        args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_insert(args, app_context)
        capsys.readouterr()

        task = app_context.store.get_task("implementation", "AA100-1")
        assert task is not None
        assert task["title"] == "Implement feature X"

    def test_insert_tracks_history(self, app_context, impl_json_file, capsys):
        args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_insert(args, app_context)
        capsys.readouterr()

        history = app_context.history.get_history("AA100-1")
        assert len(history) == 1
        assert history[0]["field_name"] == "__created__"


class TestCmdGet:
    def test_get_existing_task(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(task_id="AA100-1", schema=None, json=False)
        cmd_get(args, app_context)
        captured = capsys.readouterr()
        assert "AA100-1" in captured.out
        assert "Implement feature X" in captured.out

    def test_get_json_output(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(task_id="AA100-1", schema=None, json=True)
        cmd_get(args, app_context)
        captured = capsys.readouterr()
        import json as _json
        data = _json.loads(captured.out)
        assert data["id"] == "AA100-1"

    def test_get_nonexistent_task(self, app_context, capsys):
        args = argparse.Namespace(task_id="UNKNOWN", schema=None, json=False)
        cmd_get(args, app_context)
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestCmdList:
    def test_list_with_tasks(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, status=None, phase=None, json=False)
        cmd_list(args, app_context)
        captured = capsys.readouterr()
        assert "AA100-1" in captured.out or "Implement" in captured.out

    def test_list_empty(self, app_context, capsys):
        args = argparse.Namespace(schema=None, status=None, phase=None, json=False)
        cmd_list(args, app_context)
        captured = capsys.readouterr()
        assert "No tasks" in captured.out

    def test_list_json(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, status=None, phase=None, json=True)
        cmd_list(args, app_context)
        captured = capsys.readouterr()
        assert "AA100-1" in captured.out


class TestCmdUpdate:
    def test_update_status(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(task_id="AA100-1", schema=None, status="in_progress")
        cmd_update(args, app_context)
        captured = capsys.readouterr()
        assert "Updated" in captured.out
        assert "in_progress" in captured.out

        task = app_context.store.get_task("implementation", "AA100-1")
        assert task["status"] == "in_progress"

    def test_update_nonexistent(self, app_context, capsys):
        args = argparse.Namespace(task_id="UNKNOWN", schema=None, status="completed")
        cmd_update(args, app_context)
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_update_records_history(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()
        capsys.readouterr()

        args = argparse.Namespace(task_id="AA100-1", schema=None, status="in_progress")
        cmd_update(args, app_context)
        capsys.readouterr()

        history = app_context.history.get_history_for_field("AA100-1", "status")
        assert len(history) >= 1


class TestCmdDelete:
    def test_delete_existing(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(task_id="AA100-1", schema=None)
        cmd_delete(args, app_context)
        captured = capsys.readouterr()
        assert "Deleted" in captured.out
        assert app_context.store.get_task("implementation", "AA100-1") is None

    def test_delete_nonexistent(self, app_context, capsys):
        args = argparse.Namespace(task_id="UNKNOWN", schema=None)
        cmd_delete(args, app_context)
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestCmdSchemas:
    def test_list_schemas(self, app_context, capsys):
        args = argparse.Namespace()
        cmd_schemas(args, app_context)
        captured = capsys.readouterr()
        assert "implementation" in captured.out
        assert "testing" in captured.out
        assert "Schema ID" in captured.out

    def test_table_headers(self, app_context, capsys):
        args = argparse.Namespace()
        cmd_schemas(args, app_context)
        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "Version" in captured.out


class TestCmdStatus:
    def test_status_with_tasks(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, phase=None)
        cmd_status(args, app_context)
        captured = capsys.readouterr()
        assert "implementation" in captured.out
        assert "1" in captured.out

    def test_status_with_phase_filter(self, app_context, store, impl_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, phase=1)
        cmd_status(args, app_context)
        captured = capsys.readouterr()
        assert "phase 1" in captured.out.lower() or "1" in captured.out


class TestCmdLink:
    def test_link_tasks(self, app_context, store, engine, impl_task_data, test_task_data, capsys):
        store.insert_task("implementation", impl_task_data)
        store.insert_task("testing", test_task_data)
        app_context.engine._conn.commit()

        args = argparse.Namespace(
            source_id="TD-AA100-1", target_id="AA100-1",
            rel_type="tests", source_schema="testing", target_schema="implementation",
        )
        cmd_link(args, app_context)
        captured = capsys.readouterr()
        assert "Linked" in captured.out

        rows = engine.fetchall("SELECT * FROM task_relationships")
        assert len(rows) == 1

    def test_link_invalid_rel_type(self, app_context, capsys):
        args = argparse.Namespace(
            source_id="A", target_id="B",
            rel_type="invalid_type", source_schema=None, target_schema=None,
        )
        cmd_link(args, app_context)
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_link_wrong_schema(self, app_context, capsys):
        args = argparse.Namespace(
            source_id="A", target_id="B",
            rel_type="tests", source_schema="implementation", target_schema="testing",
        )
        cmd_link(args, app_context)
        captured = capsys.readouterr()
        assert "Error" in captured.out


class TestCmdQuery:
    def test_select_query(self, app_context, capsys):
        args = argparse.Namespace(sql="SELECT 1 as val")
        cmd_query(args, app_context)
        captured = capsys.readouterr()
        assert "1" in captured.out or "val" in captured.out

    def test_disallowed_query(self, app_context, capsys):
        args = argparse.Namespace(sql="DROP TABLE task_relationships")
        cmd_query(args, app_context)
        captured = capsys.readouterr()
        assert "only SELECT and PRAGMA" in captured.out

    def test_pragma_query(self, app_context, capsys):
        args = argparse.Namespace(sql="PRAGMA table_info(task_relationships)")
        cmd_query(args, app_context)
        captured = capsys.readouterr()
        assert "source_id" in captured.out

    def test_no_results(self, app_context, capsys):
        args = argparse.Namespace(sql="SELECT * FROM task_relationships")
        cmd_query(args, app_context)
        captured = capsys.readouterr()
        assert "No results" in captured.out


class TestCmdHistory:
    def test_history_for_task(self, app_context, impl_json_file, capsys):
        # Insert via app_context so same engine connection
        ins_args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_insert(ins_args, app_context)
        capsys.readouterr()

        args = argparse.Namespace(task_id="AA100-1", schema=None, limit=50, json=False)
        cmd_history(args, app_context)
        captured = capsys.readouterr()
        assert "__created__" in captured.out

    def test_history_json(self, app_context, impl_json_file, capsys):
        ins_args = argparse.Namespace(file=str(impl_json_file), schema=None)
        cmd_insert(ins_args, app_context)
        capsys.readouterr()

        args = argparse.Namespace(task_id="AA100-1", schema=None, limit=50, json=True)
        cmd_history(args, app_context)
        captured = capsys.readouterr()
        assert "__created__" in captured.out

    def test_no_history(self, app_context, capsys):
        args = argparse.Namespace(task_id="UNKNOWN", schema=None, limit=50, json=False)
        cmd_history(args, app_context)
        captured = capsys.readouterr()
        assert "No history" in captured.out


class TestCmdLog:
    def test_log_recent_changes(self, app_context, capsys):
        app_context.history.record_change("T1", "implementation", "status", "a", "b")
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, limit=20, json=False)
        cmd_log(args, app_context)
        captured = capsys.readouterr()
        assert "T1" in captured.out

    def test_log_json(self, app_context, capsys):
        app_context.history.record_change("T1", "implementation", "status", "a", "b")
        app_context.engine._conn.commit()

        args = argparse.Namespace(schema=None, limit=20, json=True)
        cmd_log(args, app_context)
        captured = capsys.readouterr()
        assert "T1" in captured.out

    def test_log_empty(self, app_context, capsys):
        args = argparse.Namespace(schema=None, limit=20, json=False)
        cmd_log(args, app_context)
        captured = capsys.readouterr()
        assert "No recent changes" in captured.out
