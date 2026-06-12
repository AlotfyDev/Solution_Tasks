from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from task_cli.registry import SchemaRegistry, RelationshipRegistry, RelationshipType
from task_cli.validation.validator import TaskValidator
from task_cli.data.engine import DatabaseEngine, resolve_db_dir
from task_cli.data.store import TaskStore
from task_cli.history.tracker import HistoryTracker
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema
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

        register_default_relationships(self.rel_registry)

        self.engine = DatabaseEngine(self.db_dir, self.schema_registry)
        self.engine.connect()

        self.store = TaskStore(self.engine, self.schema_registry)
        self.history = HistoryTracker(self.engine)
        self.validator = TaskValidator(self.schema_registry)


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


# ── helpers ──────────────────────────────────────────────────────────

def _auto_schema_id(data: dict) -> str:
    sub_task_id = data.get("sub_task_id", "")
    return "testing" if sub_task_id.startswith("TD-") else "implementation"


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
    sep = "─" * (sum(widths) + 2 * (len(widths) - 1))
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
    p.add_argument("--output-dir", type=Path, default=Path("./export"), help="Output directory (default: ./export/)")

    # port
    p = sub.add_parser("port", help="Find available TCP ports on 127.0.0.1")
    p.add_argument("--range", type=str, default=None, help="Port range, e.g. '8000-9000'")
    p.add_argument("--list", dest="list_ports", type=int, default=1, help="Number of ports to find (default: 1)")

    # catalog
    p = sub.add_parser("catalog", help="Display the complete tool catalog with all commands, tools, resources, and schemas")
    p.add_argument("--format", default="markdown", choices=["markdown", "json"], help="Output format (default: markdown)")

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
            print(f"  \u2717 {err}")
    else:
        print("\u2713 valid")


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

    schema_id = args.schema if args.schema is not None else _auto_schema_id(data)

    errors = ctx.validator.validate(data, schema_id)
    if errors:
        print(f"Validation failed for schema '{schema_id}':")
        for err in errors:
            print(f"  \u2717 {err}")
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
    print(f"Updated {task_id}: status '{old_status}' \u2192 '{new_status}'")


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
        print(f"Linked {args.source_id} \u2192 {args.target_id} ({rel_type_name})")
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

        total = sum(r["cnt"] for r in rows)

        print(f"\nSchema: {sid}" + (f" (phase {args.phase})" if args.phase is not None else ""))
        if rows:
            for r in rows:
                print(f"  {r['status']:<15} {r['cnt']}")
            print(f"  {'─' * 22}")
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

        schema_id = _auto_schema_id(data)
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
    output_dir = Path(args.output_dir)
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
