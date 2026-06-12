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


@mcp.tool(description="Get the complete tool catalog describing all commands, tools, resources, and schemas")
def get_catalog(format: str = "markdown") -> str:
    """Returns catalog in markdown (default) or JSON format."""
    ctx = get_context()
    catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
    if format == "json":
        return json.dumps(catalog.get_catalog_json(), indent=2)
    return catalog.get_catalog_markdown()


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
