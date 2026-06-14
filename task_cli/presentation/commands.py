from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from task_cli.registry import SchemaRegistry, RelationshipRegistry, RelationshipType
from task_cli.validation.validator import TaskValidator
from task_cli.data.engine import DatabaseEngine, resolve_db_dir
from task_cli.data.store import TaskStore
from task_cli.history.tracker import HistoryTracker
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema
from task_cli.schemas.document import register_document_schema
from task_cli.presentation.catalog import ToolCatalog


class AppContext:
    """Holds all shared dependencies for CLI commands."""

    def __init__(self):
        self.schema_registry = SchemaRegistry()
        self.rel_registry = RelationshipRegistry()
        self.validator: Optional[TaskValidator] = None
        self.engine: Optional[DatabaseEngine] = None
        self.store: Optional[TaskStore] = None
        self.history: Optional[HistoryTracker] = None
        self.db_dir: Optional[Path] = None

    def initialize(self, db_dir: Optional[Path] = None) -> None:
        self.db_dir = resolve_db_dir(db_dir)

        register_implementation_schema(self.schema_registry)
        register_testing_schema(self.schema_registry)
        register_document_schema(self.schema_registry)

        register_default_relationships(self.rel_registry)

        self.engine = DatabaseEngine(self.db_dir, self.schema_registry)
        self.engine.connect()

        self.store = TaskStore(self.engine, self.schema_registry)
        self.history = HistoryTracker(self.engine)
        self.validator = TaskValidator(self.schema_registry, engine=self.engine)


def register_default_relationships(rel_registry: RelationshipRegistry) -> None:
    rel_registry.register(RelationshipType(
        name="tests",
        source_schema_id="testing",
        target_schema_id="implementation",
        description="TD tests verify AA implementation",
    ))
    rel_registry.register(RelationshipType(
        name="depends_on",
        source_schema_id="implementation",
        target_schema_id="implementation",
        description="Hard/soft dependencies between implementation tasks",
    ))
    rel_registry.register(RelationshipType(
        name="implements",
        source_schema_id="implementation",
        target_schema_id="implementation",
        description="Hierarchy/parent-child relationship",
    ))
    rel_registry.register(RelationshipType(
        name="verifies",
        source_schema_id="testing",
        target_schema_id="implementation",
        description="Test case verifies acceptance criterion",
    ))

def _auto_schema_id(sub_task_id: str, reg: SchemaRegistry) -> str:
    for schema in reg.list():
        prefix = getattr(schema, "id_prefix", "")
        if prefix and sub_task_id.startswith(prefix):
            return schema.schema_id
    return "implementation"


def _trunc(val: str, max_len: int = 40) -> str:
    if len(val) > max_len:
        return val[:max_len - 3] + "..."
    return val


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "-" * (sum(widths) + 2 * (len(widths) - 1))
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*row))


# ── parser builder ──────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Task Toolkit CLI — manage implementation and testing tasks",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=None,
        help="Directory for tasks.db (default: Solution_Tasks/.data/)",
    )

    sub = parser.add_subparsers(dest="command", required=True, title="subcommands")

    # validate
    p = sub.add_parser("validate", help="Validate a JSON task file against its schema")
    p.add_argument("file", type=str, help="Path to JSON task file")
    p.add_argument("--schema", default=None, help="Schema ID (auto-detected if omitted)")

    # insert
    p = sub.add_parser("insert", help="Validate + insert a task JSON file into the database")
    p.add_argument("file", type=str, help="Path to JSON task file")
    p.add_argument("--schema", default=None, help="Schema ID (auto-detected if omitted)")

    # update
    p = sub.add_parser("update", help="Update task fields (e.g., status)")
    p.add_argument("task_id", type=str, help="Task ID")
    p.add_argument("--schema", default=None, help="Schema ID (default: implementation)")
    p.add_argument(
        "--status",
        required=True,
        choices=["pending", "in_progress", "completed", "blocked", "cancelled"],
        help="New status",
    )

    # get
    p = sub.add_parser("get", help="Retrieve and display a task with all sub-entities")
    p.add_argument("task_id", type=str, help="Task ID")
    p.add_argument("--schema", default=None, help="Schema ID (default: implementation)")
    p.add_argument("--json", action="store_true", help="Output as JSON")

    # list
    p = sub.add_parser("list", help="List tasks with optional filters")
    p.add_argument("--schema", default=None, help="Schema ID (default: implementation)")
    p.add_argument(
        "--status",
        default=None,
        choices=["pending", "in_progress", "completed", "blocked", "cancelled"],
        help="Filter by status",
    )
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")
    p.add_argument("--json", action="store_true", help="Output as JSON")

    # query
    p = sub.add_parser("query", help="Execute raw SQL query (SELECT/PRAGMA only)")
    p.add_argument("sql", type=str, help="SQL query to execute")

    # delete
    p = sub.add_parser("delete", help="Delete a task and its sub-entities")
    p.add_argument("task_id", type=str, help="Task ID")
    p.add_argument("--schema", default=None, help="Schema ID (default: implementation)")

    # link
    p = sub.add_parser("link", help="Create a relationship between two tasks")
    p.add_argument("source_id", type=str, help="Source task ID")
    p.add_argument("target_id", type=str, help="Target task ID")
    p.add_argument("--type", dest="rel_type", required=True, help="Relationship type (registered in registry)")
    p.add_argument("--source-schema", default=None, help="Source schema ID (default: implementation)")
    p.add_argument("--target-schema", default=None, help="Target schema ID (default: implementation)")

    # status
    p = sub.add_parser("status", help="Show progress summary")
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")
    p.add_argument("--schema", default=None, help="Schema ID (all schemas if omitted)")

    # schemas
    sub.add_parser("schemas", help="List all registered schemas")

    # history
    p = sub.add_parser("history", help="Show change history for a task")
    p.add_argument("task_id", type=str, help="Task ID")
    p.add_argument("--schema", default=None, help="Schema ID (all schemas if omitted)")
    p.add_argument("--limit", type=int, default=50, help="Max entries (default: 50)")
    p.add_argument("--json", action="store_true", help="Output as JSON")

    # log
    p = sub.add_parser("log", help="Show recent changes across all tasks")
    p.add_argument("--schema", default=None, help="Schema ID (all schemas if omitted)")
    p.add_argument("--limit", type=int, default=20, help="Max entries (default: 20)")
    p.add_argument("--json", action="store_true", help="Output as JSON")

    # import
    p = sub.add_parser("import", help="Import all JSON files from a directory")
    p.add_argument("dir", type=str, help="Directory containing JSON task files")
    p.add_argument("--db-dir", type=Path, default=None, help="Directory for tasks.db (default: inherited from parent)")

    # export
    p = sub.add_parser("export", help="Export tasks to JSON files in a directory")
    p.add_argument("--schema", required=True, help="Schema ID to export")
    p.add_argument("--status", default=None, choices=["pending", "in_progress", "completed", "blocked", "cancelled"], help="Filter by status")
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")
    p.add_argument("--output-dir", type=Path, default=None, help="Output directory (default: ./export/, overridable via TASK_EXPORT_DIR env var)")

    # port
    p = sub.add_parser("port", help="Find available TCP ports on 127.0.0.1")
    p.add_argument("--range", type=str, default=None, help="Port range, e.g. '8000-9000'")
    p.add_argument("--list", dest="list_ports", type=int, default=1, help="Number of ports to find (default: 1)")

    # catalog
    p = sub.add_parser("catalog", help="Display the complete tool catalog with all commands, tools, resources, and schemas")
    p.add_argument("--format", default="markdown", choices=["markdown", "json"], help="Output format (default: markdown)")

    # batch-import
    p = sub.add_parser("batch-import", help="Batch import JSON files from a directory with enhanced flags")
    p.add_argument("dir", type=str, help="Directory containing JSON task files")
    p.add_argument("--schema", default=None, help="Schema ID (auto-detected if omitted)")
    p.add_argument("--dry-run", action="store_true", help="Validate only, no insert")
    p.add_argument("--skip-errors", action="store_true", help="Continue on individual file error")

    # batch-link
    p = sub.add_parser("batch-link", help="Batch link tasks by naming convention or mapping file")
    p.add_argument("--source-schema", default="testing", help="Source schema ID")
    p.add_argument("--target-schema", default="implementation", help="Target schema ID")
    p.add_argument("--rel-type", default="tests", help="Relationship type")
    p.add_argument("--by-field", default=None, help="Field name to match (e.g., parent_aa)")
    p.add_argument("--from-file", default=None, help="JSON mapping file path")

    # batch-update
    p = sub.add_parser("batch-update", help="Batch update task status")
    p.add_argument("--schema", default=None, help="Schema ID (auto-detected if omitted)")
    p.add_argument("--status", required=True, choices=["pending", "in_progress", "completed", "blocked", "cancelled"], help="New status")
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")
    p.add_argument("--ids", default=None, help="Comma-separated task IDs")

    # batch-delete
    p = sub.add_parser("batch-delete", help="Batch delete tasks")
    p.add_argument("--schema", default=None, help="Schema ID (auto-detected if omitted)")
    p.add_argument("--ids", default=None, help="Comma-separated task IDs")
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")

    # load-docs
    p = sub.add_parser("load-docs", help="Load markdown spec files and create tasks")
    p.add_argument("--dir", required=True, help="Directory containing .md spec files")
    p.add_argument("--pattern", default="AA-*.md", help="Glob pattern (default: AA-*.md)")
    p.add_argument("--dry-run", action="store_true", help="Parse only, no DB changes")

    # import-documents
    p = sub.add_parser("import-documents", help="Batch-import markdown files from a directory as documents")
    p.add_argument("dir", type=str, help="Directory containing .md files")
    p.add_argument("--pattern", default="*.md", help="Glob pattern (default: *.md)")
    p.add_argument("--dry-run", action="store_true", help="Parse only, no DB changes")
    p.add_argument("--project", default="", help="Project prefix (e.g. LAT for Logger_Adapter_Tests)")

    # list-documents
    p = sub.add_parser("list-documents", help="List all loaded documents")
    p.add_argument("--status", default=None, choices=["pending", "in_progress", "completed", "blocked", "cancelled"], help="Filter by status")
    p.add_argument("--phase", type=int, default=None, help="Filter by phase number")

    # delete-document
    p = sub.add_parser("delete-document", help="Delete a document by ID")
    p.add_argument("doc_id", type=str, help="Document ID to delete")

    # update-document
    p = sub.add_parser("update-document", help="Update a document's fields from JSON file")
    p.add_argument("doc_id", type=str, help="Document ID to update")
    p.add_argument("file", type=str, help="Path to JSON file with fields to update")

    # normalize-doc-id
    p = sub.add_parser("normalize-doc-id", help="Generate a standard doc_id from a filename or parameters")
    p.add_argument("filename", type=str, help="Filename or path to derive doc_id from")
    p.add_argument("--schema", default="", help="Schema: implementation/AA, testing/TD, impact/IMPACT, doc/DOC")
    p.add_argument("--serial", default="", help="Override serial number (e.g. 5.1)")
    p.add_argument("--topic", default="", help="Override topic description")
    p.add_argument("--project", default="", help="Project prefix (e.g. LAT for Logger_Adapter_Tests)")

    return parser


# ── command handlers ───────────────────────────────────────────────

def cmd_validate(args: argparse.Namespace, ctx: AppContext) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        return

    try:
        errors = ctx.validator.validate_file(file_path, args.schema)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        return
    except KeyError as e:
        print(f"Error: {e}")
        return

    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
    else:
        print("[OK] valid")


def cmd_insert(args: argparse.Namespace, ctx: AppContext) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        return

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        return

    schema_id = args.schema if args.schema is not None else _auto_schema_id(data.get("sub_task_id", ""), ctx.schema_registry)

    errors = ctx.validator.validate(data, schema_id)
    if errors:
        print(f"Validation failed for schema '{schema_id}':")
        for err in errors:
            print(f"  [FAIL] {err}")
        return

    task_id = ctx.store.insert_task(schema_id, data)
    ctx.history.record_creation(task_id, schema_id)
    ctx.engine._conn.commit()
    print(f"Inserted {task_id}")


def cmd_update(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_id = args.schema if args.schema is not None else "implementation"
    task_id = args.task_id
    new_status = args.status

    existing = ctx.store.get_task(schema_id, task_id)
    if existing is None:
        print(f"Error: task '{task_id}' not found in schema '{schema_id}'")
        return

    old_status = existing.get("status", "")

    ctx.store.update_status(schema_id, task_id, new_status)
    ctx.history.record_status_change(task_id, schema_id, old_status, new_status)
    ctx.engine._conn.commit()
    print(f"Updated {task_id}: status '{old_status}' -> '{new_status}'")


def cmd_get(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_id = args.schema if args.schema is not None else "implementation"
    task = ctx.store.get_task(schema_id, args.task_id)
    if task is None:
        print(f"Task '{args.task_id}' not found in schema '{schema_id}'")
        return

    if args.json:
        print(json.dumps(task, indent=2, default=str))
        return

    print(f"ID:          {task.get('id', '')}")
    print(f"Title:       {task.get('title', '')}")
    print(f"Description: {_trunc(task.get('description', ''), 60)}")
    print(f"Status:      {task.get('status', '')}")
    print(f"Phase:       {task.get('phase', '')}")
    print(f"Schema:      {schema_id}")

    if "acceptance_criteria" in task:
        for ac in task["acceptance_criteria"]:
            print(f"  Criterion: {_trunc(ac.get('description', ''), 60)}")
    if "files" in task:
        for f in task["files"]:
            print(f"  File: {f.get('path', '')} ({f.get('change_type', '')})")
    if "tags" in task:
        print(f"  Tags: {', '.join(task['tags'])}")
    if "scenarios" in task:
        for s in task["scenarios"]:
            print(f"  Scenario: {_trunc(s.get('name', ''), 50)} ({s.get('type', '')})")
    if "test_cases" in task:
        for tc in task["test_cases"]:
            print(f"  Test: {tc.get('name', '')} ({tc.get('status', '')})")


def cmd_list(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_id = args.schema if args.schema is not None else "implementation"
    rows = ctx.store.list_tasks(
        schema_id,
        status_filter=args.status,
        phase_filter=args.phase,
    )

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print(f"No tasks found for schema '{schema_id}'")
        return

    headers = ["ID", "Title", "Status", "Phase"]
    table_rows = [
        [r["id"], _trunc(r.get("title", ""), 37), r.get("status", ""), str(r.get("phase", ""))]
        for r in rows
    ]
    _print_table(headers, table_rows)


def cmd_query(args: argparse.Namespace, ctx: AppContext) -> None:
    sql = args.sql.strip()
    sql_upper = sql.upper()
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("PRAGMA")):
        print("Error: only SELECT and PRAGMA queries are allowed")
        return

    try:
        rows = ctx.engine.fetchall(sql)
    except Exception as e:
        print(f"Error: {e}")
        return

    if not rows:
        print("No results")
        return

    headers = list(rows[0].keys())
    table_rows = [[str(r.get(h, "")) for h in headers] for r in rows]
    _print_table(headers, table_rows)


def cmd_delete(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_id = args.schema if args.schema is not None else "implementation"
    task_id = args.task_id

    deleted = ctx.store.delete_task(schema_id, task_id)
    if not deleted:
        print(f"Task '{task_id}' not found in schema '{schema_id}'")
        return

    ctx.history.record_change(task_id, schema_id, "__deleted__", None, None)
    ctx.engine._conn.commit()
    print(f"Deleted {task_id}")


def cmd_link(args: argparse.Namespace, ctx: AppContext) -> None:
    source_schema = args.source_schema if args.source_schema is not None else "implementation"
    target_schema = args.target_schema if args.target_schema is not None else "implementation"
    rel_type_name = args.rel_type

    try:
        rel_type = ctx.rel_registry.get(rel_type_name)
    except KeyError:
        print(f"Error: relationship type '{rel_type_name}' not found. Registered: {[r.name for r in ctx.rel_registry.list()]}")
        return

    if rel_type.source_schema_id != source_schema:
        print(
            f"Error: relationship '{rel_type_name}' expects source schema "
            f"'{rel_type.source_schema_id}', got '{source_schema}'"
        )
        return
    if rel_type.target_schema_id != target_schema:
        print(
            f"Error: relationship '{rel_type_name}' expects target schema "
            f"'{rel_type.target_schema_id}', got '{target_schema}'"
        )
        return

    try:
        ctx.engine.execute(
            "INSERT INTO task_relationships "
            "(source_id, source_schema, target_id, target_schema, rel_type) "
            "VALUES (:source_id, :source_schema, :target_id, :target_schema, :rel_type)",
            {
                "source_id": args.source_id,
                "source_schema": source_schema,
                "target_id": args.target_id,
                "target_schema": target_schema,
                "rel_type": rel_type_name,
            },
        )
        ctx.engine._conn.commit()
        print(f"Linked {args.source_id} -> {args.target_id} ({rel_type_name})")
    except Exception as e:
        print(f"Error: {e}")


def cmd_status(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_ids: list[str]
    if args.schema is not None:
        schema_ids = [args.schema]
    else:
        schema_ids = ctx.schema_registry.list_ids()

    for sid in schema_ids:
        schema = ctx.schema_registry.get(sid)
        main_table = schema.table_names["main"]

        try:
            if args.phase is not None:
                rows = ctx.engine.fetchall(
                    f"SELECT status, COUNT(*) as cnt FROM {main_table} "
                    f"WHERE phase = :phase GROUP BY status",
                    {"phase": args.phase},
                )
            else:
                rows = ctx.engine.fetchall(
                    f"SELECT status, COUNT(*) as cnt FROM {main_table} GROUP BY status"
                )
        except Exception:
            continue

        total = sum(r["cnt"] for r in rows)

        print(f"\nSchema: {sid}" + (f" (phase {args.phase})" if args.phase is not None else ""))
        if rows:
            for r in rows:
                print(f"  {r['status']:<15} {r['cnt']}")
            print(f"  {'-' * 22}")
            print(f"  {'TOTAL':<15} {total}")
        else:
            print("  (no tasks)")


def cmd_schemas(args: argparse.Namespace, ctx: AppContext) -> None:
    schemas = ctx.schema_registry.list_ids()
    if not schemas:
        print("No schemas registered")
        return
    headers = ["Schema ID", "Title", "Version"]
    rows = []
    for sid in schemas:
        s = ctx.schema_registry.get(sid)
        rows.append([sid, s.title, s.version])
    _print_table(headers, rows)


def cmd_history(args: argparse.Namespace, ctx: AppContext) -> None:
    rows = ctx.history.get_history(
        args.task_id,
        schema_id=args.schema,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print(f"No history for task '{args.task_id}'")
        return

    headers = ["ID", "Task", "Changed At", "Field", "Old Value", "New Value"]
    table_rows = [
        [
            str(r["id"]),
            r["task_id"],
            _trunc(r.get("changed_at", ""), 20),
            r.get("field_name", ""),
            _trunc(r.get("old_value") or "", 20),
            _trunc(r.get("new_value") or "", 20),
        ]
        for r in rows
    ]
    _print_table(headers, table_rows)


def cmd_log(args: argparse.Namespace, ctx: AppContext) -> None:
    rows = ctx.history.get_recent_changes(
        limit=args.limit,
        schema_id=args.schema,
    )

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print("No recent changes")
        return

    headers = ["ID", "Task", "Changed At", "Field", "Old Value", "New Value"]
    table_rows = [
        [
            str(r["id"]),
            r["task_id"],
            _trunc(r.get("changed_at", ""), 20),
            r.get("field_name", ""),
            _trunc(r.get("old_value") or "", 20),
            _trunc(r.get("new_value") or "", 20),
        ]
        for r in rows
    ]
    _print_table(headers, table_rows)


def cmd_import(args: argparse.Namespace, ctx: AppContext) -> None:
    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        print(f"Error: not a directory: {src_dir}")
        return

    json_files = sorted(src_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found")
        return

    imported = 0
    errors = 0
    skipped = 0

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  SKIP {fp.name}: invalid JSON ({e})")
            skipped += 1
            continue

        schema_id = _auto_schema_id(data.get("sub_task_id", ""), ctx.schema_registry)
        errs = ctx.validator.validate(data, schema_id)
        if errs:
            print(f"  SKIP {fp.name}: validation failed for schema '{schema_id}'")
            for e in errs:
                print(f"    {e}")
            skipped += 1
            continue

        try:
            task_id = ctx.store.insert_task(schema_id, data)
            ctx.history.record_creation(task_id, schema_id)
            ctx.engine._conn.commit()
            imported += 1
            print(f"  OK   {fp.name} -> {task_id}")
        except Exception as e:
            print(f"  FAIL {fp.name}: {e}")
            errors += 1

    total = len(json_files)
    print(f"Imported {imported} files, {errors} errors, {skipped} skipped")


def cmd_export(args: argparse.Namespace, ctx: AppContext) -> None:
    schema_id = args.schema
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = Path(os.environ.get("TASK_EXPORT_DIR", "./export"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = ctx.store.list_tasks(
        schema_id,
        status_filter=args.status,
        phase_filter=args.phase,
    )

    if not tasks:
        print(f"No tasks found for schema '{schema_id}' with given filters")
        return

    count = 0
    for t in tasks:
        task_id = t["id"]
        full = ctx.store.get_task(schema_id, task_id)
        if full is None:
            continue
        fp = output_dir / f"{task_id}.json"
        fp.write_text(json.dumps(full, indent=2, default=str), encoding="utf-8")
        count += 1

    print(f"Exported {count} tasks to {output_dir}")


def cmd_catalog(args: argparse.Namespace, ctx: AppContext) -> None:
    catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
    if args.format == "json":
        import json as _json
        print(_json.dumps(catalog.get_catalog_json(), indent=2))
    else:
        print(catalog.get_catalog_markdown())


def cmd_port(args: argparse.Namespace, ctx: AppContext) -> None:
    """
    Find available TCP ports on 127.0.0.1.
    Usage: task port                    → find one free port
           task port --list 5           → find 5 free ports
           task port --range 9000-9999  → scan specific range
    """
    from task_cli.utils.port import find_free_port, scan_available_ports

    if args.list_ports and args.list_ports > 1:
        if args.range:
            parts = args.range.split("-")
            ports = scan_available_ports(int(parts[0]), int(parts[1]), limit=args.list_ports)
        else:
            ports = scan_available_ports(limit=args.list_ports)
        for p in ports:
            print(p)
    else:
        if args.range:
            parts = args.range.split("-")
            port = find_free_port(preferred_range=(int(parts[0]), int(parts[1])))
        else:
            port = find_free_port()
        print(port)


def _get_field_value(task_data: dict, field: str, task_id: str, reg: SchemaRegistry) -> str:
    parts = field.split(".", 1)
    if len(parts) == 2:
        nested = task_data.get(parts[0], {})
        if isinstance(nested, dict):
            val = nested.get(parts[1], "")
            if val:
                return val
    for variant in [field, f"{field}_id", f"{field}_name"]:
        val = task_data.get(variant, "")
        if val:
            return val
    import re
    stripped = task_id
    for schema in reg.list():
        prefix = getattr(schema, "id_prefix", "")
        if prefix and stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break
    m = re.match(r"^(.+)-\d+$", stripped)
    if m:
        return m.group(1)
    return stripped


def _validate_rel(ctx, rel_type_name, source_schema, target_schema):
    try:
        rel_def = ctx.rel_registry.get(rel_type_name)
    except KeyError:
        raise ValueError(f"Relationship type '{rel_type_name}' not found. Registered: {[r.name for r in ctx.rel_registry.list()]}")
    if rel_def.source_schema_id != source_schema:
        raise ValueError(
            f"Relationship '{rel_type_name}' expects source schema "
            f"'{rel_def.source_schema_id}', got '{source_schema}'"
        )
    if rel_def.target_schema_id != target_schema:
        raise ValueError(
            f"Relationship '{rel_type_name}' expects target schema "
            f"'{rel_def.target_schema_id}', got '{target_schema}'"
        )
    return rel_def


def _do_batch_link(ctx, source_id, target_id, rel_type_name, source_schema, target_schema):
    ctx.engine.execute(
        "INSERT INTO task_relationships "
        "(source_id, source_schema, target_id, target_schema, rel_type) "
        "VALUES (:s, :ss, :t, :ts, :r)",
        {"s": source_id, "ss": source_schema, "t": target_id, "ts": target_schema, "r": rel_type_name},
    )
    ctx.engine._conn.commit()


def cmd_batch_import(args: argparse.Namespace, ctx: AppContext) -> None:
    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        print(f"Error: not a directory: {src_dir}")
        return

    json_files = sorted(src_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found")
        return

    imported = 0
    errors = 0
    skipped = 0
    schema_override = args.schema
    dry_run = args.dry_run
    skip_errors = args.skip_errors

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            msg = f"invalid JSON ({e})"
            if skip_errors:
                print(f"  SKIP {fp.name}: {msg}")
                skipped += 1
                continue
            else:
                print(f"  FAIL {fp.name}: {msg}")
                errors += 1
                continue

        schema_id = schema_override if schema_override else _auto_schema_id(data.get("sub_task_id", ""), ctx.schema_registry)
        errs = ctx.validator.validate(data, schema_id)
        if errs:
            msg = f"validation failed for schema '{schema_id}'"
            if skip_errors:
                print(f"  SKIP {fp.name}: {msg}")
                for e in errs:
                    print(f"    {e}")
                skipped += 1
                continue
            else:
                print(f"  FAIL {fp.name}: {msg}")
                for e in errs:
                    print(f"    {e}")
                errors += 1
                continue

        if dry_run:
            print(f"  OK   {fp.name} -> {schema_id} (dry run)")
            imported += 1
            continue

        try:
            task_id = ctx.store.insert_task(schema_id, data)
            ctx.history.record_creation(task_id, schema_id)
            ctx.engine._conn.commit()
            imported += 1
            print(f"  OK   {fp.name} -> {task_id}")
        except Exception as e:
            print(f"  FAIL {fp.name}: {e}")
            errors += 1

    print(f"Imported {imported} files, {errors} errors, {skipped} skipped")


def cmd_batch_link(args: argparse.Namespace, ctx: AppContext) -> None:
    source_schema = args.source_schema
    target_schema = args.target_schema
    rel_type_name = args.rel_type
    by_field = args.by_field
    from_file = args.from_file

    if not by_field and not from_file:
        print("Error: either --by-field or --from-file is required")
        return
    if by_field and from_file:
        print("Error: --by-field and --from-file are mutually exclusive")
        return

    try:
        _validate_rel(ctx, rel_type_name, source_schema, target_schema)
    except ValueError as e:
        print(f"Error: {e}")
        return

    linked = 0
    errors = 0

    if from_file:
        fp = Path(from_file)
        if not fp.exists():
            print(f"Error: file not found: {fp}")
            return
        try:
            mapping = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"Error: invalid mapping file: {e}")
            return

        for item in mapping:
            source_id = item.get("source_id")
            target_id = item.get("target_id")
            if not source_id or not target_id:
                errors += 1
                print(f"  FAIL: invalid entry {item}")
                continue
            try:
                _do_batch_link(ctx, source_id, target_id, rel_type_name, source_schema, target_schema)
                print(f"  OK   {source_id} -> {target_id}")
                linked += 1
            except Exception as e:
                errors += 1
                print(f"  FAIL {source_id} -> {target_id}: {e}")

    elif by_field:
        source_tasks = ctx.store.list_tasks(source_schema)
        target_tasks = ctx.store.list_tasks(target_schema)

        for src in source_tasks:
            src_id = src["id"]
            field_value = _get_field_value(src, by_field, src_id, ctx.schema_registry)
            if not field_value:
                continue

            for tgt in target_tasks:
                tid = tgt["id"]
                if tid == field_value or (isinstance(field_value, str) and tid.startswith(f"{field_value}-")):
                    pass
                elif isinstance(field_value, str) and tid.startswith(f"{field_value}_"):
                    pass
                elif isinstance(field_value, str):
                    matched = False
                    for schema in ctx.schema_registry.list():
                        prefix = getattr(schema, "id_prefix", "")
                        if prefix and tid.startswith(f"{prefix}{field_value}-"):
                            matched = True
                            break
                    if not matched:
                        continue
                try:
                    _do_batch_link(ctx, src_id, tid, rel_type_name, source_schema, target_schema)
                    print(f"  OK   {src_id} -> {tid}")
                    linked += 1
                except Exception as e:
                    errors += 1
                    print(f"  FAIL {src_id} -> {tid}: {e}")

    print(f"Linked {linked} pairs, {errors} errors")


def cmd_batch_update(args: argparse.Namespace, ctx: AppContext) -> None:
    new_status = args.status
    phase = args.phase
    ids_str = args.ids
    schema_arg = args.schema

    if phase is None and not ids_str:
        print("Error: either --phase or --ids is required")
        return

    updated = 0

    if ids_str:
        ids = [tid.strip() for tid in ids_str.split(",") if tid.strip()]
        for tid in ids:
            sid = schema_arg if schema_arg else _auto_schema_id(tid, ctx.schema_registry)
            existing = ctx.store.get_task(sid, tid)
            if existing is None:
                print(f"  SKIP {tid}: not found in schema '{sid}'")
                continue
            old_status = existing.get("status", "")
            try:
                ctx.store.update_status(sid, tid, new_status)
                ctx.history.record_status_change(tid, sid, old_status, new_status)
                ctx.engine._conn.commit()
                updated += 1
                print(f"  OK   {tid}: {old_status} -> {new_status}")
            except ValueError as e:
                print(f"  FAIL {tid}: {e}")

    if phase is not None:
        schema_ids = [schema_arg] if schema_arg else ctx.schema_registry.list_ids()
        for sid in schema_ids:
            tasks = ctx.store.list_tasks(sid, phase_filter=phase)
            for task in tasks:
                tid = task["id"]
                old_status = task.get("status", "")
                try:
                    ctx.store.update_status(sid, tid, new_status)
                    ctx.history.record_status_change(tid, sid, old_status, new_status)
                    ctx.engine._conn.commit()
                    updated += 1
                    print(f"  OK   {tid}: {old_status} -> {new_status}")
                except ValueError as e:
                    print(f"  FAIL {tid}: {e}")

    print(f"Updated {updated} tasks")


def cmd_batch_delete(args: argparse.Namespace, ctx: AppContext) -> None:
    ids_str = args.ids
    phase = args.phase
    schema_arg = args.schema

    if phase is None and not ids_str:
        print("Error: either --phase or --ids is required")
        return

    deleted = 0

    if ids_str:
        ids = [tid.strip() for tid in ids_str.split(",") if tid.strip()]
        for tid in ids:
            sid = schema_arg if schema_arg else _auto_schema_id(tid, ctx.schema_registry)
            if ctx.store.delete_task(sid, tid):
                ctx.history.record_change(tid, sid, "__deleted__", None, None)
                ctx.engine._conn.commit()
                deleted += 1
                print(f"  OK   {tid}")
            else:
                print(f"  SKIP {tid}: not found in schema '{sid}'")

    if phase is not None:
        schema_ids = [schema_arg] if schema_arg else ctx.schema_registry.list_ids()
        for sid in schema_ids:
            tasks = ctx.store.list_tasks(sid, phase_filter=phase)
            for task in tasks:
                tid = task["id"]
                if ctx.store.delete_task(sid, tid):
                    ctx.history.record_change(tid, sid, "__deleted__", None, None)
                    ctx.engine._conn.commit()
                    deleted += 1
                    print(f"  OK   {tid}")
                else:
                    print(f"  FAIL {tid}: delete failed")

    print(f"Deleted {deleted} tasks")


def cmd_load_docs(args: argparse.Namespace, ctx: AppContext) -> None:
    from spec_parser.loader import load_directory
    from spec_parser.parser import parse, visit
    from spec_parser.extractor import extract_document, extract_sub_tasks

    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        print(f"Error: not a directory: {src_dir}")
        return

    files = load_directory(str(src_dir), args.pattern)
    if not files:
        print("No .md files found")
        return

    dry_run = args.dry_run
    doc_count = 0
    task_count = 0
    errors = 0

    for f in files:
        filepath = f["path"]
        content = f["content"]
        tokens = parse(content)
        parsed = visit(tokens)

        doc_data = extract_document(parsed, filepath)
        doc_id = doc_data["doc_id"]

        errors_list = ctx.validator.validate(doc_data, "document")
        if errors_list:
            print(f"  SKIP {filepath}: validation failed for document")
            for e in errors_list:
                print(f"    {e}")
            errors += 1
            continue

        if not dry_run:
            ctx.store.insert_document(doc_data)
            ctx.engine._conn.commit()
        doc_count += 1
        phase = doc_data.get("metadata", {}).get("phase", 0)
        print(f"  Document: {doc_id} (Phase {phase}, {len(content)} chars)")

        sub_schema = "testing" if doc_id.startswith("TD-") else "implementation"

        sub_tasks = extract_sub_tasks(parsed, doc_id, filepath)
        for sub_task in sub_tasks:
            sub_errors = ctx.validator.validate(sub_task, sub_schema)
            if sub_errors:
                print(f"    SKIP {sub_task['sub_task_id']}: validation failed against '{sub_schema}' schema")
                for e in sub_errors:
                    print(f"      {e}")
                errors += 1
                continue

            if not dry_run:
                ctx.store.insert_task(sub_schema, sub_task)
                ctx.engine._conn.commit()
            task_count += 1
            print(f"    Sub-task: {sub_task['sub_task_id']}")

    if dry_run:
        print("---")
        print(f"Dry run: {doc_count} documents, {task_count} sub-tasks would be created")
    else:
        print(f"Loaded {doc_count} documents, {task_count} sub-tasks, {errors} errors")

    return 1 if errors > 0 else None


def cmd_import_documents(args: argparse.Namespace, ctx: AppContext) -> None:
    import re
    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        print(f"Error: not a directory: {src_dir}")
        return

    md_files = sorted(src_dir.glob(args.pattern))
    if not md_files:
        print("No matching files found")
        return

    dry_run = args.dry_run
    inserted = 0
    errors = 0
    error_details = []

    for fp in md_files:
        try:
            content = fp.read_text(encoding="utf-8")
            content = fp.read_text(encoding="utf-8")
            doc_id = f"{args.project}-{fp.stem}" if args.project else fp.stem

            title = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            phase = 0
            m = re.search(r"TD-(\d+)", doc_id)
            if m:
                phase = int(m.group(1))

            data = {
                "doc_id": doc_id,
                "file_path": str(fp.resolve()),
                "title": title,
                "content": content,
                "metadata": {"phase": phase},
                "status": {"state": "pending"},
            }

            errs = ctx.validator.validate(data, "document")
            if errs:
                errors += 1
                msg = f"validation failed: {'; '.join(errs)}"
                error_details.append(f"{fp.name}: {msg}")
                print(f"  FAIL {fp.name}: {msg}")
                continue

            if not dry_run:
                ctx.store.insert_document(data)
                ctx.history.record_creation(doc_id, "document")
                ctx.engine._conn.commit()
            inserted += 1
            print(f"  OK   {fp.name} -> {doc_id}")
        except Exception as e:
            errors += 1
            error_details.append(f"{fp.name}: {e}")
            print(f"  FAIL {fp.name}: {e}")

    total = len(md_files)
    if dry_run:
        print(f"Dry run: {inserted} documents would be inserted, {errors} errors")
    else:
        print(f"Inserted {inserted} documents, {errors} errors out of {total}")


def cmd_delete_document(args: argparse.Namespace, ctx: AppContext) -> None:
    doc_id = args.doc_id
    deleted = ctx.store.delete_document(doc_id)
    if not deleted:
        print(f"Document '{doc_id}' not found")
        return
    ctx.history.record_change(doc_id, "document", "__deleted__", None, None)
    ctx.engine._conn.commit()
    print(f"Deleted document {doc_id}")


def cmd_update_document(args: argparse.Namespace, ctx: AppContext) -> None:
    doc_id = args.doc_id
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        return
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        return
    
    existing = ctx.store.get_document(doc_id)
    if existing is None:
        print(f"Document '{doc_id}' not found")
        return
    
    merged = dict(existing)
    merged.update(data)
    if "metadata" in data:
        merged["metadata"] = data["metadata"]
    if "status" in data:
        merged["status"] = data["status"]
    merged["doc_id"] = doc_id
    
    errors = ctx.validator.validate(merged, "document")
    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
        return
    
    ok = ctx.store.update_document(doc_id, merged)
    if not ok:
        print(f"Document '{doc_id}' not found")
        return
    ctx.history.record_change(doc_id, "document", "__updated__", None, None)
    ctx.engine._conn.commit()
    print(f"Updated document {doc_id}")


_DOC_ID_STANDARD_CLI = r"^([A-Z]+-)?(AA|TD|IMPACT|DOC)-\d+(\.\d+)*(-[A-Z][A-Za-z0-9-]*)?$"


def _check_doc_id_convention_cli(doc_id: str) -> list[str]:
    warnings = []
    if not re.match(_DOC_ID_STANDARD_CLI, doc_id):
        parts = doc_id.split("-")
        if len(parts) < 2:
            warnings.append(f"Naming convention: '{doc_id}' lacks CLASS-SERIAL-TOPIC")
        else:
            offset = 0
            if len(parts) >= 4:
                offset = 1
            cls = parts[offset]
            if cls not in ("AA", "TD", "IMPACT", "DOC"):
                warnings.append(f"CLASS '{cls}' not in AA|TD|IMPACT|DOC")
            serial_idx = offset + 1
            if len(parts) > serial_idx:
                ser = parts[serial_idx]
                if not ser.replace(".", "").isdigit():
                    warnings.append(f"SERIAL '{ser}' should be numeric-only")
            topic_idx = offset + 2
            if len(parts) <= topic_idx:
                warnings.append("missing TOPIC part")
            elif not parts[topic_idx][0].isupper():
                warnings.append(f"TOPIC '{parts[topic_idx]}' should start with uppercase")
    return warnings


def cmd_normalize_doc_id(args: argparse.Namespace, ctx: AppContext) -> None:
    from pathlib import Path as _Path
    stem = _Path(args.filename).stem
    parts = stem.split("-")
    cls = "DOC"
    ser = args.serial or (parts[1] if len(parts) > 1 else "")
    top = args.topic or ("-".join(parts[2:]) if len(parts) > 2 else parts[-1] if parts else stem)

    schema_to_cls = {"implementation": "AA", "testing": "TD", "impact": "IMPACT", "doc": "DOC"}
    cls_to_schema = {v: k for k, v in schema_to_cls.items()}

    if args.schema and args.schema in schema_to_cls:
        cls = schema_to_cls[args.schema]
    elif parts and parts[0] in cls_to_schema:
        cls = parts[0]

    if not args.serial:
        m = re.search(r"(\d[\d.]*)", stem)
        if m:
            ser = m.group(1)

    if not args.topic:
        tidx = stem.find("-") if cls else -1
        if tidx >= 0:
            rest = stem[tidx + 1:]
            m = re.search(r"\d[\d.]*-([A-Z].*)", rest)
            if m:
                top = m.group(1).replace("_", "-")

    if not ser:
        ser = "0"
    if not top:
        top = stem

    result = f"{cls}-{ser}-{top}" if not args.project else f"{args.project}-{cls}-{ser}-{top}"
    warnings = _check_doc_id_convention_cli(result)
    print(f"  doc_id: {result}")
    if warnings:
        for w in warnings:
            print(f"     ⚠ {w}")


def cmd_list_documents(args: argparse.Namespace, ctx: AppContext) -> None:
    rows = ctx.store.list_documents_filtered(
        status_filter=args.status,
        phase_filter=args.phase,
    )

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print("No documents found")
        return

    headers = ["ID", "Title", "Phase", "Status"]
    table_rows = [
        [r["id"], _trunc(r.get("title", ""), 37), str(r.get("phase", 0)), r.get("status", "")]
        for r in rows
    ]
    _print_table(headers, table_rows)
