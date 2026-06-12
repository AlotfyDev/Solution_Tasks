from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from task_cli.data.engine import DatabaseEngine, resolve_db_dir
from task_cli.history.tracker import HistoryTracker
from task_cli.presentation.catalog import ToolCatalog
from task_cli.presentation.commands import AppContext
from task_cli.presentation.report import ReportGenerator
from task_cli.registry import SchemaRegistry

mcp = FastMCP(
    "Task Toolkit",
    instructions="Manage implementation tasks and test tasks for the Cross-Language Trading System. Supports AA (implementation) and TD (testing) task schemas with SQLite persistence.",
)

_context: Optional[AppContext] = None
_db_dir_override: Optional[Path] = None


def get_context() -> AppContext:
    global _context
    if _context is None:
        _context = AppContext()
        _context.initialize(_db_dir_override)
    return _context


# ── helpers ──────────────────────────────────────────────────────────


def _auto_schema_id(data: dict) -> str:
    sub_task_id = data.get("sub_task_id", "")
    return "testing" if sub_task_id.startswith("TD-") else "implementation"


# ── tools ────────────────────────────────────────────────────────────


@mcp.tool(description="List tasks with optional schema, status, and phase filters")
def list_tasks(
    schema_id: str = "implementation",
    status: Optional[str] = None,
    phase: Optional[int] = None,
) -> list[dict]:
    ctx = get_context()
    return ctx.store.list_tasks(schema_id, status_filter=status, phase_filter=phase)


@mcp.tool(description="Get a single task with all sub-entities (criteria, files, tags, scenarios, test cases)")
def get_task(task_id: str, schema_id: str = "implementation") -> dict:
    ctx = get_context()
    task = ctx.store.get_task(schema_id, task_id)
    return task if task is not None else {}


@mcp.tool(description="Validate and insert a task from its JSON content. Returns the task_id or validation errors.")
def insert_task(task_json: str, schema_id: Optional[str] = None) -> str:
    ctx = get_context()
    try:
        data = json.loads(task_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if schema_id is None:
        schema_id = _auto_schema_id(data)

    errors = ctx.validator.validate(data, schema_id)
    if errors:
        return "Validation errors:\n" + "\n".join(f"  \u2717 {e}" for e in errors)

    task_id = ctx.store.insert_task(schema_id, data)
    ctx.history.record_creation(task_id, schema_id)
    ctx.engine._conn.commit()
    return f"Inserted {task_id}"


@mcp.tool(description="Update task status. Valid states: pending, in_progress, completed, blocked, cancelled")
def update_status(task_id: str, new_status: str, schema_id: str = "implementation") -> str:
    ctx = get_context()
    existing = ctx.store.get_task(schema_id, task_id)
    if existing is None:
        return f"Task '{task_id}' not found in schema '{schema_id}'"

    old_status = existing.get("status", "")
    try:
        ctx.store.update_status(schema_id, task_id, new_status)
    except ValueError as e:
        return str(e)

    ctx.history.record_status_change(task_id, schema_id, old_status, new_status)
    ctx.engine._conn.commit()
    return f"Updated {task_id}: status '{old_status}' -> '{new_status}'"


@mcp.tool(description="Delete a task and all its sub-entities")
def delete_task(task_id: str, schema_id: str = "implementation") -> str:
    ctx = get_context()
    deleted = ctx.store.delete_task(schema_id, task_id)
    if not deleted:
        return f"Task '{task_id}' not found in schema '{schema_id}'"

    ctx.history.record_change(task_id, schema_id, "__deleted__", None, None)
    ctx.engine._conn.commit()
    return f"Deleted {task_id}"


@mcp.tool(description="Delete a relationship between two tasks. rel_type options: tests, depends_on, implements, verifies")
def unlink_tasks(
    source_id: str,
    target_id: str,
    rel_type: str = "tests",
    source_schema: str = "testing",
    target_schema: str = "implementation",
) -> str:
    ctx = get_context()
    ctx.engine.execute(
        "DELETE FROM task_relationships "
        "WHERE source_id=:src AND source_schema=:ss AND target_id=:tgt AND target_schema=:ts AND rel_type=:rt",
        {"src": source_id, "ss": source_schema, "tgt": target_id, "ts": target_schema, "rt": rel_type},
    )
    ctx.engine._conn.commit()
    return f"Unlinked {source_id} -> {target_id} ({rel_type})"


@mcp.tool(description="Create a relationship between two tasks. rel_type options: tests, depends_on, implements, verifies")
def link_tasks(
    source_id: str,
    target_id: str,
    rel_type: str = "tests",
    source_schema: str = "testing",
    target_schema: str = "implementation",
    properties: Optional[str] = None,
) -> str:
    ctx = get_context()

    try:
        rel_type_def = ctx.rel_registry.get(rel_type)
    except KeyError:
        registered = [r.name for r in ctx.rel_registry.list()]
        return f"Relationship type '{rel_type}' not found. Registered: {registered}"

    if rel_type_def.source_schema_id != source_schema:
        return (
            f"Relationship '{rel_type}' expects source schema "
            f"'{rel_type_def.source_schema_id}', got '{source_schema}'"
        )
    if rel_type_def.target_schema_id != target_schema:
        return (
            f"Relationship '{rel_type}' expects target schema "
            f"'{rel_type_def.target_schema_id}', got '{target_schema}'"
        )

    props_json = properties or "{}"

    try:
        ctx.engine.execute(
            "INSERT INTO task_relationships "
            "(source_id, source_schema, target_id, target_schema, rel_type, properties_json) "
            "VALUES (:source_id, :source_schema, :target_id, :target_schema, :rel_type, :properties_json)",
            {
                "source_id": source_id,
                "source_schema": source_schema,
                "target_id": target_id,
                "target_schema": target_schema,
                "rel_type": rel_type,
                "properties_json": props_json,
            },
        )
        ctx.engine._conn.commit()
        return f"Linked {source_id} -> {target_id} ({rel_type})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(description="Get a full status report: counts by schema, phase, blocked tasks, recent activity")
def status_report() -> str:
    ctx = get_context()
    report = ReportGenerator(ctx.engine, ctx.store, ctx.history, ctx.schema_registry)
    return report.full_report()


@mcp.tool(description="Find gaps: implementation tasks without test coverage, stale tasks, empty schemas")
def gap_analysis() -> str:
    ctx = get_context()
    report = ReportGenerator(ctx.engine, ctx.store, ctx.history, ctx.schema_registry)
    return report.gap_analysis()


@mcp.tool(description="Trace the dependency chain for a task (recursive depends_on relationship)")
def dependency_chain(task_id: str, schema_id: str = "implementation") -> str:
    ctx = get_context()
    report = ReportGenerator(ctx.engine, ctx.store, ctx.history, ctx.schema_registry)
    return report.dependency_chain(task_id, schema_id)


@mcp.tool(description="Search tasks by title or description text across all schemas")
def search_tasks(query: str) -> list[dict]:
    ctx = get_context()
    pattern = f"%{query}%"
    results: list[dict] = []

    for sid in ctx.schema_registry.list_ids():
        table = ctx.schema_registry.get(sid).table_names["main"]
        rows = ctx.engine.fetchall(
            f"SELECT * FROM {table} "
            f"WHERE title LIKE :q OR description LIKE :q",
            {"q": pattern},
        )
        for r in rows:
            entry = dict(r)
            entry["schema_id"] = sid
            results.append(entry)

    return results


@mcp.tool(description="Validate a task JSON without inserting. Returns list of errors or 'valid'.")
def validate_task(task_json: str) -> str:
    ctx = get_context()
    try:
        data = json.loads(task_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    schema_id = _auto_schema_id(data)

    try:
        errors = ctx.validator.validate(data, schema_id)
    except KeyError as e:
        return f"Schema not found: {e}"

    if errors:
        return "Validation errors:\n" + "\n".join(f"  \u2717 {e}" for e in errors)
    return "\u2713 valid"


@mcp.tool(description="Get change history for a task")
def get_history(
    task_id: str,
    schema_id: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    ctx = get_context()
    return ctx.history.get_history(task_id, schema_id=schema_id, limit=limit)


# ── resources ────────────────────────────────────────────────────────


@mcp.resource(
    "task://{schema_id}/{task_id}",
    description="Get a task as a structured resource",
)
def task_resource(schema_id: str, task_id: str) -> str:
    ctx = get_context()
    task = ctx.store.get_task(schema_id, task_id)
    if task is None:
        return json.dumps({"error": f"Task '{task_id}' not found in schema '{schema_id}'"})
    return json.dumps(task, indent=2, default=str)


@mcp.resource(
    "schema://{schema_id}",
    description="Get registered schema definition",
)
def schema_resource(schema_id: str) -> str:
    ctx = get_context()
    try:
        schema = ctx.schema_registry.get(schema_id)
    except KeyError:
        return json.dumps({"error": f"Schema '{schema_id}' not found"})
    return json.dumps(schema.json_schema(), indent=2, default=str)


@mcp.resource(
    "report://status",
    description="Get full status report",
)
def status_resource() -> str:
    ctx = get_context()
    report = ReportGenerator(ctx.engine, ctx.store, ctx.history, ctx.schema_registry)
    return report.full_report()


@mcp.tool(description="Force reload all schemas from disk (picks up changes to JSON schema files)")
def reload_schemas() -> str:
    ctx = get_context()
    count = 0
    for sid in ctx.schema_registry.list_ids():
        schema = ctx.schema_registry.get(sid)
        if not schema.json_schema_path or not schema.json_schema_path.exists():
            continue
        # Force re-read from disk regardless of cache
        with open(schema.json_schema_path, "r", encoding="utf-8") as f:
            schema._json_schema = json.load(f)
        count += 1
    return f"Reloaded {count} schemas"


@mcp.tool(description="Get the complete tool catalog describing all commands, tools, resources, and schemas")
def get_catalog(format: str = "markdown") -> str:
    """Returns catalog in markdown (default) or JSON format."""
    ctx = get_context()
    catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
    if format == "json":
        return json.dumps(catalog.get_catalog_json(), indent=2)
    return catalog.get_catalog_markdown()


@mcp.tool(description="Batch import all JSON task files from a directory")
def import_tasks(
    dir_path: str,
    schema: Optional[str] = None,
    dry_run: bool = False,
    skip_errors: bool = False,
) -> str:
    ctx = get_context()
    src_dir = Path(dir_path)
    if not src_dir.is_dir():
        return f"Error: not a directory: {src_dir}"

    json_files = sorted(src_dir.glob("*.json"))
    if not json_files:
        return "No JSON files found"

    imported = 0
    errors = 0
    skipped = 0

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            msg = f"invalid JSON ({e})"
            if skip_errors:
                skipped += 1
                continue
            else:
                errors += 1
                continue

        schema_id = schema if schema else _auto_schema_id(data)
        errs = ctx.validator.validate(data, schema_id)
        if errs:
            if skip_errors:
                skipped += 1
                continue
            else:
                errors += 1
                continue

        if dry_run:
            imported += 1
            continue

        try:
            task_id = ctx.store.insert_task(schema_id, data)
            ctx.history.record_creation(task_id, schema_id)
            ctx.engine._conn.commit()
            imported += 1
        except Exception:
            errors += 1

    return f"Imported {imported} files, {errors} errors, {skipped} skipped"


@mcp.tool(description="Export tasks to JSON files in a directory")
def export_tasks(
    schema_id: str,
    output_dir: str,
    status: Optional[str] = None,
    phase: Optional[int] = None,
) -> str:
    ctx = get_context()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    tasks = ctx.store.list_tasks(schema_id, status_filter=status, phase_filter=phase)
    if not tasks:
        return f"No tasks found for schema '{schema_id}' with given filters"

    count = 0
    for t in tasks:
        tid = t["id"]
        full = ctx.store.get_task(schema_id, tid)
        if full is None:
            continue
        fp = out_path / f"{tid}.json"
        fp.write_text(json.dumps(full, indent=2, default=str), encoding="utf-8")
        count += 1

    return f"Exported {count} tasks to {out_path}"


@mcp.tool(description="Batch link tasks by field matching or mapping file")
def batch_link_tasks(
    source_schema: str = "testing",
    target_schema: str = "implementation",
    rel_type: str = "tests",
    by_field: Optional[str] = None,
    from_file: Optional[str] = None,
) -> str:
    ctx = get_context()

    if not by_field and not from_file:
        return "Error: either --by-field or --from-file is required"
    if by_field and from_file:
        return "Error: --by-field and --from-file are mutually exclusive"

    try:
        from task_cli.presentation.commands import _validate_rel, _do_batch_link, _get_field_value
        _validate_rel(ctx, rel_type, source_schema, target_schema)
    except ValueError as e:
        return f"Error: {e}"

    linked = 0
    errors = 0

    if from_file:
        fp = Path(from_file)
        if not fp.exists():
            return f"Error: file not found: {fp}"
        try:
            mapping = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return f"Error: invalid mapping file: {e}"

        for item in mapping:
            source_id = item.get("source_id")
            target_id = item.get("target_id")
            if not source_id or not target_id:
                errors += 1
                continue
            try:
                _do_batch_link(ctx, source_id, target_id, rel_type, source_schema, target_schema)
                linked += 1
            except Exception:
                errors += 1

    elif by_field:
        source_tasks = ctx.store.list_tasks(source_schema)
        target_tasks = ctx.store.list_tasks(target_schema)

        for src in source_tasks:
            src_id = src["id"]
            field_value = _get_field_value(src, by_field, src_id)
            if not field_value:
                continue

            for tgt in target_tasks:
                tid = tgt["id"]
                if tid == field_value or (isinstance(field_value, str) and tid.startswith(f"{field_value}-")):
                    try:
                        _do_batch_link(ctx, src_id, tid, rel_type, source_schema, target_schema)
                        linked += 1
                    except Exception:
                        errors += 1

    return f"Linked {linked} pairs, {errors} errors"


@mcp.tool(description="Batch update status for multiple tasks")
def batch_update_status(
    task_ids: Optional[str] = None,
    new_status: str = "in_progress",
    schema_id: Optional[str] = None,
    phase: Optional[int] = None,
) -> str:
    ctx = get_context()
    from task_cli.presentation.commands import cmd_batch_update
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    ns = argparse.Namespace(status=new_status, phase=phase, ids=task_ids, schema=schema_id)
    with redirect_stdout(buf):
        cmd_batch_update(ns, ctx)
    return buf.getvalue().strip()


@mcp.tool(description="Batch delete tasks by IDs or phase")
def batch_delete_tasks(
    task_ids: Optional[str] = None,
    schema_id: Optional[str] = None,
    phase: Optional[int] = None,
) -> str:
    ctx = get_context()
    from task_cli.presentation.commands import cmd_batch_delete
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    ns = argparse.Namespace(ids=task_ids, phase=phase, schema=schema_id)
    with redirect_stdout(buf):
        cmd_batch_delete(ns, ctx)
    return buf.getvalue().strip()


@mcp.resource("catalog://overview", description="Complete tool catalog in markdown")
def catalog_resource() -> str:
    """Returns the full catalog as markdown."""
    ctx = get_context()
    catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
    return catalog.get_catalog_markdown()


def entry() -> None:
    """Entry point for console_scripts 'task-mcp'.
    
    Usage:
        task-mcp                    → stdio transport, DB in default .data/
        task-mcp --db-dir D:\data   → stdio transport, custom DB location
        task-mcp --sse              → SSE transport on port 8000
        task-mcp --sse --port 8080 → SSE transport on port 8080
    """
    parser = argparse.ArgumentParser(description="Task Toolkit MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run with SSE transport (network) instead of stdio")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE transport (default: 127.0.0.1)")
    parser.add_argument("--db-dir", type=Path, default=None, help="Directory for tasks.db (default: Solution_Tasks/.data/)")
    args = parser.parse_args()
    
    global _db_dir_override
    _db_dir_override = args.db_dir

    if args.sse:
        print(f"[task-mcp] Starting MCP server on {args.host}:{args.port} (SSE)", file=sys.stderr)
        print(f"[task-mcp] Connect URL: http://{args.host}:{args.port}/sse", file=sys.stderr)
        try:
            import uvicorn  # noqa: F401
        except ImportError:
            print("Error: SSE mode requires uvicorn. Install: pip install 'task-toolkit[sse]'", file=sys.stderr)
            sys.exit(1)
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    entry()
