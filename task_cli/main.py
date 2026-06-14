from __future__ import annotations

import builtins
import sys

_orig_print = builtins.print
def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        safe = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
        _orig_print(safe, **kwargs)

from task_cli.presentation.commands import (
    AppContext,
    build_parser,
    cmd_batch_delete,
    cmd_batch_import,
    cmd_batch_link,
    cmd_batch_update,
    cmd_catalog,
    cmd_delete,
    cmd_export,
    cmd_get,
    cmd_history,
    cmd_import,
    cmd_import_documents,
    cmd_insert,
    cmd_link,
    cmd_list,
    cmd_delete_document,
    cmd_list_documents,
    cmd_load_docs,
    cmd_normalize_doc_id,
    cmd_update_document,
    cmd_log,
    cmd_port,
    cmd_query,
    cmd_schemas,
    cmd_status,
    cmd_update,
    cmd_validate,
)


def entry() -> None:
    """
    Console entry point (console_scripts in pyproject.toml).

    1. Build parser
    2. Parse args
    3. Create AppContext and initialize (if command needs DB)
    4. Dispatch to command handler
    5. Exit with appropriate code (0=success, 1=error)
    """
    builtins.print = _safe_print
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    _HANDLERS = {
        "validate": cmd_validate,
        "insert": cmd_insert,
        "update": cmd_update,
        "get": cmd_get,
        "list": cmd_list,
        "query": cmd_query,
        "delete": cmd_delete,
        "link": cmd_link,
        "status": cmd_status,
        "schemas": cmd_schemas,
        "history": cmd_history,
        "log": cmd_log,
        "import": cmd_import,
        "export": cmd_export,
        "port": cmd_port,
        "catalog": cmd_catalog,
        "batch-import": cmd_batch_import,
        "batch-link": cmd_batch_link,
        "batch-update": cmd_batch_update,
        "batch-delete": cmd_batch_delete,
        "load-docs": cmd_load_docs,
        "delete-document": cmd_delete_document,
        "list-documents": cmd_list_documents,
        "import-documents": cmd_import_documents,
        "update-document": cmd_update_document,
        "normalize-doc-id": cmd_normalize_doc_id,
    }
    _NEEDS_DB = {
        "insert",
        "update",
        "get",
        "list",
        "query",
        "delete",
        "link",
        "status",
        "history",
        "log",
        "import",
        "export",
        "batch-import",
        "batch-link",
        "batch-update",
        "batch-delete",
        "load-docs",
        "delete-document",
        "list-documents",
        "import-documents",
        "update-document",
    }

    ctx = AppContext()

    if args.command in _NEEDS_DB:
        ctx.initialize(getattr(args, "db_dir", None))
    else:
        from task_cli.registry import RelationshipRegistry, SchemaRegistry
        from task_cli.schemas.implementation import register_implementation_schema
        from task_cli.schemas.testing import register_testing_schema
        from task_cli.schemas.document import register_document_schema
        from task_cli.presentation.commands import register_default_relationships
        from task_cli.validation.validator import TaskValidator

        ctx.schema_registry = SchemaRegistry()
        register_implementation_schema(ctx.schema_registry)
        register_testing_schema(ctx.schema_registry)
        register_document_schema(ctx.schema_registry)
        ctx.rel_registry = RelationshipRegistry()
        register_default_relationships(ctx.rel_registry)
        ctx.validator = TaskValidator(ctx.schema_registry)

    try:
        _HANDLERS[args.command](args, ctx)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    entry()
