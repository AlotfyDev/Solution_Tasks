from __future__ import annotations

from typing import Any

from task_cli.registry import RelationshipRegistry, SchemaRegistry


class ToolCatalog:
    """
    Generates a self-documenting catalog of all CLI commands,
    MCP tools, resources, registered schemas, and connection guides.
    """

    CLI_COMMANDS: list[dict[str, str]] = [
        {"name": "validate", "description": "Validate a JSON task file against its schema", "usage": "task validate <file> [--schema <id>]"},
        {"name": "insert", "description": "Validate + insert a task JSON file into the database", "usage": "task insert <file> [--schema <id>]"},
        {"name": "import", "description": "Import all JSON files from a directory", "usage": "task import <dir>"},
        {"name": "export", "description": "Export tasks to JSON files in a directory", "usage": "task export --schema <id> [--status <s>] [--phase <n>] [--output-dir <dir>]"},
        {"name": "update", "description": "Update task status", "usage": "task update <task_id> --status <new_status>"},
        {"name": "get", "description": "Retrieve and display a task with all sub-entities", "usage": "task get <task_id> [--schema <id>] [--json]"},
        {"name": "list", "description": "List tasks with optional filters", "usage": "task list [--schema <id>] [--status <s>] [--phase <n>] [--json]"},
        {"name": "query", "description": "Execute raw SQL query (SELECT/PRAGMA only)", "usage": "task query <sql>"},
        {"name": "delete", "description": "Delete a task and its sub-entities", "usage": "task delete <task_id> [--schema <id>]"},
        {"name": "link", "description": "Create a relationship between two tasks", "usage": "task link <source_id> <target_id> --type <rel_type>"},
        {"name": "status", "description": "Show progress summary", "usage": "task status [--schema <id>] [--phase <n>]"},
        {"name": "schemas", "description": "List all registered schemas", "usage": "task schemas"},
        {"name": "history", "description": "Show change history for a task", "usage": "task history <task_id> [--schema <id>] [--limit <n>] [--json]"},
        {"name": "log", "description": "Show recent changes across all tasks", "usage": "task log [--schema <id>] [--limit <n>] [--json]"},
        {"name": "port", "description": "Find available TCP ports on 127.0.0.1", "usage": "task port [--list <n>] [--range <lo-hi>]"},
        {"name": "catalog", "description": "Display the complete tool catalog", "usage": "task catalog [--format json|markdown]"},
        {"name": "batch-import", "description": "Batch import JSON files from a directory", "usage": "task batch-import <dir> [--schema <id>] [--dry-run] [--skip-errors]"},
        {"name": "batch-link", "description": "Batch link tasks by naming convention or mapping file", "usage": "task batch-link --source-schema <s> --target-schema <t> --rel-type <r> --by-field <f>"},
        {"name": "batch-update", "description": "Batch update task status", "usage": "task batch-update --status <s> [--phase <n>] [--ids <csv>]"},
        {"name": "batch-delete", "description": "Batch delete tasks", "usage": "task batch-delete [--ids <csv>] [--phase <n>]"},
        {"name": "load-docs", "description": "Load markdown spec files and create tasks", "usage": "task load-docs --dir <path> [--pattern *.md]"},
        {"name": "import-documents", "description": "Batch-import markdown files from a directory as documents", "usage": "task import-documents <dir> [--pattern *.md] [--dry-run] [--project <p>]"},
        {"name": "list-documents", "description": "List all loaded documents", "usage": "task list-documents [--status <s>] [--phase <n>] [--json]"},
        {"name": "delete-document", "description": "Delete a document by ID", "usage": "task delete-document <doc_id>"},
        {"name": "update-document", "description": "Update a document's fields from JSON file", "usage": "task update-document <doc_id> <file.json>"},
        {"name": "normalize-doc-id", "description": "Generate a standard doc_id from a filename or parameters", "usage": "task normalize-doc-id <filename> [--schema <s>] [--serial <s>] [--topic <t>] [--project <p>]"},
    ]

    MCP_TOOLS: list[dict[str, str]] = [
        {"name": "list_tasks", "description": "List tasks with optional schema, status, and phase filters", "params": "schema_id, status, phase"},
        {"name": "get_task", "description": "Get a single task with all sub-entities", "params": "task_id, schema_id"},
        {"name": "insert_task", "description": "Validate and insert a task from JSON content", "params": "task_json, schema_id"},
        {"name": "insert_document", "description": "Insert a document record (one per markdown spec file)", "params": "doc_json"},
        {"name": "get_document", "description": "Get a document record by ID", "params": "doc_id"},
        {"name": "list_documents", "description": "List all document records", "params": "(none)"},
        {"name": "update_document", "description": "Update a document's fields", "params": "doc_json"},
        {"name": "delete_document", "description": "Delete a document by ID", "params": "doc_id"},
        {"name": "import_documents", "description": "Batch-import markdown files from a directory as documents", "params": "dir_path, pattern, dry_run, project"},
        {"name": "normalize_doc_id", "description": "Generate a standard doc_id from a filename or parameters", "params": "filename, schema, serial, topic, project"},
        {"name": "update_status", "description": "Update task status", "params": "task_id, new_status, schema_id"},
        {"name": "update_task", "description": "Update an arbitrary field of a task", "params": "task_id, field, value, schema_id"},
        {"name": "delete_task", "description": "Delete a task and all its sub-entities", "params": "task_id, schema_id"},
        {"name": "link_tasks", "description": "Create a relationship between two tasks", "params": "source_id, target_id, rel_type, source_schema, target_schema, properties"},
        {"name": "unlink_tasks", "description": "Delete a relationship between two tasks", "params": "source_id, target_id, rel_type, source_schema, target_schema"},
        {"name": "reload_schemas", "description": "Force reload all schemas from disk", "params": "(none)"},
        {"name": "status_report", "description": "Get a full status report", "params": "(none)"},
        {"name": "gap_analysis", "description": "Find gaps in test coverage, stale tasks, empty schemas", "params": "(none)"},
        {"name": "dependency_chain", "description": "Trace the dependency chain for a task", "params": "task_id, schema_id"},
        {"name": "search_tasks", "description": "Search tasks by title or description across all schemas", "params": "query"},
        {"name": "validate_task", "description": "Validate a task JSON without inserting", "params": "task_json"},
        {"name": "get_history", "description": "Get change history for a task", "params": "task_id, schema_id, limit"},
        {"name": "get_catalog", "description": "Get the complete tool catalog", "params": "format"},
        {"name": "import_tasks", "description": "Batch import all JSON task files from a directory", "params": "dir_path, schema, dry_run, skip_errors"},
        {"name": "export_tasks", "description": "Export tasks to JSON files in a directory", "params": "schema_id, output_dir, status, phase"},
        {"name": "batch_link_tasks", "description": "Batch link tasks by field matching or mapping file", "params": "source_schema, target_schema, rel_type, by_field, from_file"},
        {"name": "batch_update_status", "description": "Batch update status for multiple tasks", "params": "task_ids, new_status, schema_id, phase"},
        {"name": "batch_delete_tasks", "description": "Batch delete tasks by IDs or phase", "params": "task_ids, schema_id, phase"},
    ]

    MCP_RESOURCES: list[dict[str, str]] = [
        {"uri": "task://{schema_id}/{task_id}", "description": "Get a task as a structured resource (JSON)"},
        {"uri": "doc://{doc_id}", "description": "Get a document by ID (JSON)"},
        {"uri": "schema://{schema_id}", "description": "Get registered schema definition (JSON Schema)"},
        {"uri": "report://status", "description": "Get full status report (markdown)"},
        {"uri": "catalog://overview", "description": "Complete tool catalog (markdown)"},
    ]

    def __init__(self, schema_registry: SchemaRegistry, rel_registry: RelationshipRegistry):
        self._schema_registry = schema_registry
        self._rel_registry = rel_registry

    def _schema_section(self) -> str:
        lines: list[str] = []
        lines.append("## Registered Schemas")
        lines.append("")
        schema_ids = self._schema_registry.list_ids()
        if not schema_ids:
            lines.append("_(no schemas registered)_")
            return "\n".join(lines)
        for sid in schema_ids:
            s = self._schema_registry.get(sid)
            lines.append(f"### `{s.schema_id}` — {s.title}")
            lines.append("")
            lines.append(f"- **Version:** {s.version}")
            lines.append(f"- **Description:** {s.description}")
            lines.append("- **Tables:**")
            for role, table_name in s.table_names.items():
                lines.append(f"  - `{table_name}` ({role})")
            lines.append("")
        return "\n".join(lines)

    def _relationships_section(self) -> str:
        lines: list[str] = []
        lines.append("## Registered Relationships")
        lines.append("")
        rels = self._rel_registry.list()
        if not rels:
            lines.append("_(no relationship types registered)_")
            return "\n".join(lines)
        header = "| Name | Source Schema | Target Schema | Description |"
        sep = "|------|---------------|---------------|-------------|"
        lines.append(header)
        lines.append(sep)
        for r in rels:
            lines.append(f"| `{r.name}` | `{r.source_schema_id}` | `{r.target_schema_id}` | {r.description} |")
        lines.append("")
        return "\n".join(lines)

    def _cli_commands_section(self) -> str:
        lines: list[str] = []
        lines.append("## CLI Commands")
        lines.append("")
        lines.append("| Command | Description | Usage |")
        lines.append("|---------|-------------|-------|")
        for cmd in self.CLI_COMMANDS:
            lines.append(f"| `{cmd['name']}` | {cmd['description']} | `{cmd['usage']}` |")
        lines.append("")
        return "\n".join(lines)

    def _mcp_tools_section(self) -> str:
        lines: list[str] = []
        lines.append("## MCP Tools")
        lines.append("")
        lines.append("| Tool | Description | Parameters |")
        lines.append("|------|-------------|------------|")
        for t in self.MCP_TOOLS:
            lines.append(f"| `{t['name']}` | {t['description']} | `{t['params']}` |")
        lines.append("")
        return "\n".join(lines)

    def _mcp_resources_section(self) -> str:
        lines: list[str] = []
        lines.append("## MCP Resources")
        lines.append("")
        lines.append("| URI Pattern | Description |")
        lines.append("|-------------|-------------|")
        for r in self.MCP_RESOURCES:
            lines.append(f"| `{r['uri']}` | {r['description']} |")
        lines.append("")
        return "\n".join(lines)

    def _connection_guides_section(self) -> str:
        return """\
## Connection Guides

### Cline (stdio)
Add to `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Kilocode (stdio)
Add to Kilocode settings:
```json
{
  "mcp_servers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": []
    }
  }
}
```

### VS Code (stdio)
```json
{
  "mcpServers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": []
    }
  }
}
```

> For SSE mode and detailed configuration, see `MCP_CONFIG.md`.
"""

    def _configuration_section(self) -> str:
        return """\
## Database Configuration

The task database (`tasks.db`) location is resolved with this priority chain:

| Priority | Method | Example |
|----------|--------|---------|
| 1 (highest) | `--db-dir` CLI flag | `task --db-dir /path/to/data list` |
| 2 | `TASK_DB_DIR` env var | `$env:TASK_DB_DIR="/path/to/data"` |
| 3 (default) | Project `.data/` dir | `Solution_Tasks/.data/tasks.db` |

**CLI:** `task --db-dir <path> <subcommand>`
**MCP server:** `task-mcp --db-dir <path>` (stdio or SSE)

This ensures portability — the project carries its own default DB location,
but the user can override it at any time without modifying project files.
"""

    def _quick_start_section(self) -> str:
        return """\
## Quick Start

1. **Find a free port:**
   ```
   task port
   ```

2. **Start the SSE server:**
   ```
   task-mcp --sse --port 8000
   ```

3. **Connect your IDE:**
   Configure the MCP client to use `http://127.0.0.1:8000/sse` (see Connection Guides above).

4. **Insert tasks:**
   ```
   task insert tasks/AA100-1.json
   ```

5. **View progress:**
   ```
   task status
   task-mcp --sse
   ```
"""

    def get_catalog_markdown(self) -> str:
        sections: list[str] = []
        sections.append("# Task Toolkit \u2014 Tool Catalog")
        sections.append("")
        sections.append("Auto-generated catalog of all CLI commands, MCP tools, resources, registered schemas, and connection guides.")
        sections.append("")

        # Overview
        sections.append("## Overview")
        sections.append("")
        sections.append("The **Task Toolkit** manages implementation (AA) and testing (TD) tasks for the Cross-Language Trading System. It provides:")
        sections.append("")
        sections.append("- A pluggable **schema registry** for defining task types")
        sections.append("- **SQLite persistence** with automatic table creation per schema")
        sections.append("- **CLI** for task CRUD, validation, import/export, and status tracking")
        sections.append("- **MCP server** (stdio + SSE) for AI-assisted IDE workflows")
        sections.append("- **Relationship tracking** between tasks (dependencies, test coverage)")
        sections.append("- **Change history** with full audit trail")
        sections.append("")

        # Dynamic sections
        sections.append(self._schema_section())
        sections.append(self._relationships_section())

        # Static sections
        sections.append(self._configuration_section())
        sections.append(self._cli_commands_section())
        sections.append(self._mcp_tools_section())
        sections.append(self._mcp_resources_section())
        sections.append(self._connection_guides_section())
        sections.append(self._quick_start_section())

        return "\n".join(sections)

    def get_catalog_json(self) -> dict[str, Any]:
        schemas_list: list[dict[str, Any]] = []
        for sid in self._schema_registry.list_ids():
            s = self._schema_registry.get(sid)
            schemas_list.append({
                "id": s.schema_id,
                "title": s.title,
                "version": s.version,
                "description": s.description,
                "tables": [{"role": role, "name": name} for role, name in s.table_names.items()],
            })

        return {
            "system": "Task Toolkit",
            "description": "Modular task management CLI with pluggable schema registry and SQLite persistence",
            "configuration": {
                "database": {
                    "filename": "tasks.db",
                    "default_dir": "Solution_Tasks/.data/",
                    "priority_chain": [
                        {"level": 1, "method": "--db-dir CLI flag", "example": "task --db-dir /path list"},
                        {"level": 2, "method": "TASK_DB_DIR env var", "example": "$env:TASK_DB_DIR=\"/path\""},
                        {"level": 3, "method": "project default", "example": "Solution_Tasks/.data/"},
                    ],
                }
            },
            "schemas": schemas_list,
            "relationships": [
                {
                    "name": r.name,
                    "source_schema": r.source_schema_id,
                    "target_schema": r.target_schema_id,
                    "description": r.description,
                }
                for r in self._rel_registry.list()
            ],
            "cli_commands": self.CLI_COMMANDS,
            "mcp_tools": self.MCP_TOOLS,
            "mcp_resources": self.MCP_RESOURCES,
        }
