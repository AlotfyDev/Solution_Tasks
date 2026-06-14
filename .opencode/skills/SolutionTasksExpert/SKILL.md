---
name: solution-tasks-expert
description: Use when managing AA implementation tasks, TD testing tasks, task status, gap analysis, or running the Task Toolkit CLI/MCP. Covers task creation, validation, linking, dependency chains, phase tracking, import/export, and the tool catalog.
---

# SolutionTasksExpert

Expert at managing implementation tasks (AA) and testing tasks (TD) for the Cross-Language Trading System using the Task Toolkit.

## Triggers
Use this skill when the user asks about:
- Task status, progress, or blocking items
- Creating, updating, or linking tasks
- Test coverage or gap analysis
- Project velocity or phase completion
- Dependency chains between tasks
- Importing/exporting task data

## MCP Integration
The Task Toolkit MCP server is available at:
- **stdio**: `task-mcp` (via Cline/Kilocode subprocess). Configured in `.cline/mcp.json` and `.kilo/mcp_servers.json`.
- **SSE**: `task-mcp --sse --port PORT` (standalone network server)

### Tools Available (28)
(Read `catalog://overview` or call `get_catalog()` for full details)

#### Task CRUD
| Tool | Purpose |
|------|---------|
| `list_tasks` | Filter by schema/status/phase |
| `get_task` | Full task + sub-entities |
| `insert_task` | Validate + add new task |
| `update_status` | Change task state |
| `update_task` | Update arbitrary field |
| `delete_task` | Remove task + cascade |

#### Relationships
| Tool | Purpose |
|------|---------|
| `link_tasks` | Create relationships |
| `unlink_tasks` | Delete a relationship |
| `batch_link_tasks` | Batch link by field matching |

#### Document CRUD
| Tool | Purpose |
|------|---------|
| `insert_document` | Create document record |
| `get_document` | Get document by ID |
| `list_documents` | List all documents |
| `update_document` | Update document fields |
| `delete_document` | Delete document by ID |
| `import_documents` | Batch-import markdown files as documents |
| `normalize_doc_id` | Generate standard doc_id |

#### Batch Operations
| Tool | Purpose |
|------|---------|
| `import_tasks` | Batch import JSON files from directory |
| `export_tasks` | Export tasks to JSON files |
| `batch_update_status` | Batch update status for multiple tasks |
| `batch_delete_tasks` | Batch delete tasks by IDs or phase |

#### Reports & Utilities
| Tool | Purpose |
|------|---------|
| `reload_schemas` | Reload schema files from disk |
| `status_report` | Full progress |
| `gap_analysis` | Find coverage gaps |
| `dependency_chain` | Trace dependencies |
| `search_tasks` | Text search |
| `validate_task` | Check JSON validity |
| `get_history` | Change log |
| `get_catalog` | This catalog |

### Resources Available (4)
| Resource | Content |
|----------|---------|
| `task://{schema}/{id}` | Full task JSON |
| `schema://{schema_id}` | JSON Schema definition |
| `report://status` | Status report |
| `catalog://overview` | This catalog |

## Core Concepts

### Schemas
Two default schemas are registered:

**implementation** — for AA (After_Audit) implementation sub-tasks
- Tables: `tasks_implementation`, `acceptance_criteria_implementation`, `task_files_implementation`, `tags_implementation`
- `sub_task_id` pattern: `^[A-Z][A-Z0-9._-]+$` (project-agnostic, e.g., `AA-0.5-01`)

**testing** — for TD (Test Design) testing sub-tasks
- Tables: `tasks_testing`, `test_scenarios_testing`, `test_files_testing`, `test_cases_testing`
- `sub_task_id` pattern: `^TD-[A-Z0-9._-]+$` (e.g., `TD-0.5-01` or `TD-AA-0.5-01`)

### Relationships
| Name | Source → Target | Description |
|------|-----------------|-------------|
| `tests` | testing → implementation | TD tests verify AA implementation |
| `depends_on` | implementation → implementation | Hard/soft dependencies between impl tasks |
| `implements` | implementation → implementation | Hierarchy / parent-child relationship |
| `verifies` | testing → implementation | Test case verifies acceptance criterion |

### Status Values
All tasks use one of: `pending`, `in_progress`, `completed`, `blocked`, `cancelled`

### Phase Order
Phases 0–9 are executed sequentially. Always check `list_tasks(phase=N)` before advancing.

> **Important**: If JSON schema files (`implementation-schema.json` / `testing-schema.json`) were modified since the MCP server started, call `reload_schemas()` to pick up changes. The MCP server caches schemas at startup; without reload, validation uses stale patterns.

## Workflows

### 1. Session Start — Orientation
Always begin by understanding the current state:

```
1. Call status_report() — full overview
2. Call gap_analysis() — find issues
3. list_tasks(status="blocked") — identify blockers
4. get_history() — review recent changes across all tasks
```

### 2. Daily Progress Review
Full workflow in `workflows/daily-review.md`. Steps:
1. `status_report()` — completion %, blocked count, recent activity
2. `list_tasks(phase=N)` for each phase 0–9
3. `list_tasks(status="blocked")` → `dependency_chain(id)` for each
4. `gap_analysis()` — implementation tasks without test coverage
5. `get_history(task_id)` for active tasks
6. Use `batch_update_status(phase=N, new_status="in_progress")` to start a phase

### 3. Gap Closure
Full workflow in `workflows/gap-closure.md`. Steps:
1. `gap_analysis()` — identify untested AA tasks
2. For each gap: `get_task(id, schema_id="implementation")` → `search_tasks(query="TD-{AA_ID}")`
3. Create missing TD sub-tasks via `insert_task()` → `link_tasks(source, target, rel_type="tests")`
4. [OPTIONAL] Use `batch_link_tasks(by_field="parent_aa")` to auto-link instead of manual `link_tasks()`
5. `gap_analysis()` — confirm closure

### 4. Onboarding New Tasks
Full workflow in `workflows/onboarding.md`. Steps:
1. Read canonical example at `Solution_Tasks/default_schemas/example-testing-task.json`
2. Prepare JSON conforming to schema (match field types exactly)
3. `validate_task(json)` — fix errors until valid
4. `insert_task(json)` — returns task ID
5. `link_tasks()` — record dependencies
6. [OPTIONAL] Use `import_tasks(dir_path)` to bulk insert if multiple JSON files exist
7. `get_task(id)` — verify all fields correct
8. `export_tasks(schema_id="implementation", output_dir=<dir>)` or `export_tasks(schema_id="testing", output_dir=<dir>)` to write JSON files from DB (do NOT write JSON manually)
9. Extract `source.section_markdown` from the actual markdown source file (not a placeholder) and populate `traceability` with `aa_reference` and `td_reference`

> **Note**: Testing schema has strict formats — `aa_dependencies` requires array of `{"id": "..."}` objects (not strings), and **testing** acceptance criterion IDs must match `^TC-\d+$` (digits only, e.g., `TC-01`). **implementation** AC IDs are `type: string` (any format, e.g., `AC-01`). Read the canonical example before producing JSON.

## Document ID Naming Convention

doc_ids follow this standard format:

```
{CLASS}-{SERIAL}-{TOPIC}
```

| Part | Rules | Examples |
|------|-------|----------|
| **CLASS** | One of `AA`, `TD`, `IMPACT`, `DOC` | `AA`, `TD`, `IMPACT`, `DOC` |
| **SERIAL** | Numeric-only, dot-separated hierarchy | `5`, `5.1`, `4.13`, `0` |
| **TOPIC** | PascalCase or kebab-case description | `RateLimiting`, `StderrSink` |

Examples: `AA-5.1-RateLimiting`, `TD-4.13-StderrSink`, `IMPACT-5.18-LogSanitization`, `DOC-1-ProjectSetup`

### Tools

- **MCP**: `normalize_doc_id(filename, schema?, serial?, topic?)` — generates a compliant doc_id
- **CLI**: `task normalize-doc-id <path> [--schema <s>] [--serial <s>] [--topic <t>]`
- **Validation**: `insert_document` warns if doc_id deviates from the standard

### Legacy

Existing doc_ids (like `AA-M05-RateLimiting`, `TD-0-C05-ThreadModel`) remain valid in the DB. New entries should use the standard format above.

## Best Practices

1. **Validate before insert**: Always call `validate_task(json_str)` before `insert_task(json_str)`.
2. **Link explicitly**: After inserting a task, call `link_tasks()` to record relationships.
3. **Record status history**: Use `update_status()` for all state changes (don't skip).
4. **Search before create**: Check `search_tasks(query)` for duplicates before creating.
5. **Phase order**: Tasks should be implemented in phase order (0 → 9). Check `list_tasks(phase=N)`.
6. **Test coverage**: After implementing AA tasks, always create corresponding TD tasks and link via `link_tasks(rel_type="tests")`.
7. **Use catalog reference**: When unsure about tool parameters, call `get_catalog(format="json")`.

## Batch Operations

The toolkit now provides batch operations for efficient task management
(added in v0.2.0):

| Operation | CLI | MCP | Description |
|-----------|-----|-----|-------------|
| Batch Import | `task batch-import <dir> [--schema <id>] [--dry-run] [--skip-errors]` | `import_tasks()` | Import multiple JSON files at once from a directory. Auto-detects schema unless `--schema` provided. Use `--dry-run` to validate without inserting. |
| Batch Link | `task batch-link --source-schema <s> --target-schema <t> --rel-type <r> --by-field <f>` | `batch_link_tasks()` | Link tasks by field matching (e.g., `parent_aa` matches target tasks with matching ID prefix) or from a mapping JSON file. |
| Batch Update | `task batch-update --status <s> [--phase <n>] [--ids <csv>]` | `batch_update_status()` | Update status for all tasks in a phase or for specific IDs. |
| Batch Delete | `task batch-delete [--ids <csv>] [--phase <n>]` | `batch_delete_tasks()` | Delete multiple tasks by phase or by specific IDs. |
| Batch Export | `task export --schema <id> [--output-dir <dir>]` | `export_tasks()` | Export all tasks from a schema to individual JSON files (was existing, now also an MCP tool). |

## Database

- File: `tasks.db` (SQLite, WAL mode)
- Default location: `Solution_Tasks/.data/` (auto-created, hidden directory)
- **Priority chain**: `--db-dir` > `TASK_DB_DIR` env var > project default
- CLI: `task --db-dir <path> list`
- MCP: `task-mcp --db-dir <path>`

## Project Context

- C++17 cross-language trading system
- VS 2022, Windows x64 + Win32
- 4 projects: Logger_Adapter (static lib), Experimental_Console (exe), Cplspls_To_Cross_Lang_Connector (static lib), Logger_Adapter_Tests (gtest)
- Quill v10.0.1 logging library
- Spec source: `After_Audit_Implementation_Tasks/AA-*.md`
- Test source: `Task_Driven_Test_Design/TD-*.md`
