# Impact Analysis: Document Schema & Markdown Pipeline

## 1. Executive Summary

Currently, the Task Toolkit stores markdown content inline in `tasks_implementation.section_markdown` — a flat text field that holds snippets extracted from spec files. This approach has three problems: (1) the full document content is never stored, only the section-level snippets, (2) there is no first-class "document" entity that a human can open, edit, and re-import, and (3) the `source.file`, `source.lines`, `section_title`, and `section_markdown` fields clutter the implementation schema with document-level concerns that belong on a parent entity.

The proposed change introduces a **`document` schema** — one row per markdown file — that stores the full file content in a `content` TEXT column. The existing `implementation` schema is revised to remove `source.file` and `section_markdown` from required fields and add a `parent_doc_id` foreign key reference instead. A new `spec_parser/` module (using `mistune`) provides the pipeline: load markdown files from disk, parse them into AST, and extract sections, acceptance criteria, and steps that map to sub-tasks.

The total impact is moderate: ~6 new files, ~12 modified files, ~20 new/modified test files. The data migration is straightforward (read .md files from disk to populate the document table). No schema-agnostic components (registry, engine, business rules) are affected. The effort is estimated at 15–20 hours across 5 phases.

## 2. Proposed Architecture

### 2.1 New: `document` Schema
- **schema_id**: `"document"`
- **table**: `tasks_document`
- **Purpose**: One row per markdown file, stores FULL file content
- **Fields**: `id`, `file_path`, `title`, `content`, `status`, `created_at`, `updated_at`
- **No sub-tables**: No criteria, files, tags — those belong on sub-tasks

### 2.2 Revised: `implementation` Schema
- **Remove from required**: `source.file`, `source.section_markdown`
- **Add**: `parent_doc_id` (references `tasks_document.id`)
- **Keep optional**: `source.section_title`, `source.relative_path`, `source.lines`
- **DDL changes**: Drop `source_file`, `source_lines`, `section_title`, `section_markdown` from `tasks_implementation`, add `parent_doc_id`

### 2.3 New Module: `spec_parser/`
```
spec_parser/
├── __init__.py
├── loader.py        # ~20 lines — glob + read files
├── parser.py        # ~60 lines — mistune AST walker
└── extractor.py     # ~40 lines — section/AC/step extraction
```
- **Library**: `mistune` (zero dependencies, AST output, `task_lists` plugin)
- **Pipeline**: loader reads → parser tokenizes → extractor maps to JSON Schema

## 3. Component-by-Component Impact

### 3.1 New Files to Create
| File | Lines | Purpose |
|------|-------|---------|
| `default_schemas/document-schema.json` | ~30 | JSON Schema for document tasks |
| `task_cli/schemas/document.py` | ~30 | Register document schema with DDL |
| `spec_parser/__init__.py` | ~3 | Package init |
| `spec_parser/loader.py` | ~20 | Read markdown files from disk |
| `spec_parser/parser.py` | ~60 | `mistune` AST walker |
| `spec_parser/extractor.py` | ~40 | Map AST to JSON Schema |
| `task_cli/data/migration.py` | ~80 | Migration script for existing data |

### 3.2 Files to Modify
| File | Changes | Complexity |
|------|---------|------------|
| `default_schemas/implementation-schema.json` | Remove `source.file`, `section_markdown` from required; add `parent_doc_id` | Small |
| `task_cli/schemas/implementation.py` | Update DDL (drop 4 columns, add `parent_doc_id`); update `extra_columns` | Medium |
| `task_cli/data/store.py` | `_build_main_insert`: remove source lines, add `parent_doc_id`; add document CRUD methods | Medium |
| `task_cli/presentation/commands.py` | Fix `_auto_schema_id` for document IDs; `cmd_get`/`cmd_list` output changes | Small |
| `task_cli/validation/validator.py` | Remove `source.file` from required validation logic | Small |
| `task_cli/mcp_server.py` | `update_task` column list; `task://` resource output changes | Small |
| `task_cli/presentation/report.py` | Gap analysis queries unchanged (no `source.field` dependency) | None |
| `tests/conftest.py` | Test fixtures: remove `source.file`/`section_markdown`, add `parent_doc_id` | Medium |
| `tests/test_store.py` | Add document CRUD tests; update existing | Small |
| `tests/test_validator.py` | Inline test data: remove `source.file`, update expected | Small |
| `tests/test_mcp_server.py` | Inline test data changes | Small |
| `tests/test_integration.py` | Inline test data changes | Small |
| `tests/test_commands.py` | Inline test data changes | Small |
| `tests/test_parser.py` | NEW: tests for `spec_parser` module | Medium |
| `.opencode/skills/SolutionTasksExpert/SKILL.md` | Core Concepts: add document schema; update Required Fields | Small |
| `.opencode/skills/SolutionTasksExpert/workflows/onboarding.md` | Add document creation step before sub-task extraction | Small |

### 3.3 Files NOT Affected
| File | Reason |
|------|--------|
| `task_cli/registry/base.py` | Schema-agnostic |
| `task_cli/data/engine.py` | Generic SQL execution |
| `task_cli/history/tracker.py` | Generic field tracking |
| `task_cli/presentation/catalog.py` | Auto-reads from registry |
| `task_cli/utils/port.py` | Unrelated |
| `task_cli/validation/business_rules.py` | Unaffected |
| `default_schemas/testing-schema.json` | Out of scope (testing schema unchanged for now) |
| `default_schemas/example-testing-task.json` | Example data, not critical |
| `tests/test_engine.py` | No source-field references |
| `tests/test_history.py` | No source-field references |
| `tests/test_registry.py` | No source-field references |
| `tests/test_catalog.py` | No source-field references |
| `tests/test_business_rules.py` | No source-field references |
| `tests/test_report.py` | No source-field references |
| `tests/test_relationships.py` | No source-field references |

## 4. Data Migration Strategy

### 4.1 Current Data Snapshot

```
=== Current Data Snapshot ===
  tasks_implementation: 92
  tasks_testing: 77
  task_relationships: 269

=== Distinct source_file values ===
  Total distinct files: 23
  AA-M19-BenchmarkSuite.md: 8 sub-tasks
  AA-M02-DailyFileRotation.md: 7 sub-tasks
  AA-M09-ResultMonadic.md: 6 sub-tasks
  AA-P01-EventLogSink.md: 5 sub-tasks
  AA-M18-LogSanitization.md: 5 sub-tasks
  AA-M14-UTC_Timezone.md: 5 sub-tasks
  AA-M11-EmergencyReset.md: 5 sub-tasks
  AA-M10-ResultGuardedAccess.md: 5 sub-tasks
  AA-C02-CompileTimeLogLevel.md: 5 sub-tasks
  AA-0.5-StubReconciliation.md: 5 sub-tasks
  AA-M13-StderrSink.md: 4 sub-tasks
  AA-M08-QueueConfig.md: 4 sub-tasks
  AA-M06-CustomPatternPerSink.md: 4 sub-tasks
  AA-M05-RateLimiting.md: 4 sub-tasks
  AA-M04-LOGJ_StructuredLogging.md: 4 sub-tasks
  AA-M01-FileSinkAppendMode.md: 4 sub-tasks
  AA-C04-DynamicLogLevel.md: 4 sub-tasks
  AA-M03-LOGV_Macros.md: 3 sub-tasks
  After_Audit_Implementation_Tasks/AA-C05-ThreadModel.md: 1 sub-tasks
  AA-M12-DeadCodeCleanup.md: 1 sub-tasks
  AA-M07-ErrorNotifier.md: 1 sub-tasks
  AA-C03-BacktraceLogging.md: 1 sub-tasks
  AA-C01-MultiLogger.md: 1 sub-tasks

=== section_markdown size distribution ===
  >2000 chars (full doc): 8
  1-2000 chars (section): 57
  Empty: 27

=== Grand-tasks (hierarchy_level=0) ===
  (none — all 92 tasks are level 1)

=== Sub-tasks with hierarchy_level > 0 ===
  level 1: 92
```

**Key observations:**
- 23 distinct markdown source files feed 92 implementation sub-tasks
- 8 sub-tasks have section_markdown > 2000 chars (likely full doc content stored in error — these were probably imported before section-level extraction was implemented)
- 57 sub-tasks have section-level content (1–2000 chars)
- 27 sub-tasks have empty section_markdown (likely grand-tasks or stubs)
- One source file has a differing path prefix (`After_Audit_Implementation_Tasks/AA-C05-ThreadModel.md` vs bare filenames for all others) — the migration must normalize these

### 4.2 Migration Steps
1. `CREATE TABLE tasks_document (id TEXT PK, file_path TEXT, title TEXT, content TEXT, status TEXT, created_at TEXT, updated_at TEXT)`
2. For each distinct `source_file`, resolve to the actual `.md` file on disk and read full content
3. `INSERT INTO tasks_document` with title extracted from first `#` heading
4. `UPDATE tasks_implementation SET parent_doc_id = ? WHERE source_file = ?`
5. **Verify**: all implementation tasks have `parent_doc_id` set
6. `ALTER TABLE tasks_implementation ADD COLUMN parent_doc_id TEXT` (if not already there)
7. Create new table without source columns: `CREATE TABLE tasks_implementation_v2 (...)` (excluding `source_file`, `source_lines`, `section_title`, `section_markdown`; including `parent_doc_id`)
8. `INSERT INTO tasks_implementation_v2 SELECT ... FROM tasks_implementation` (projecting only kept columns)
9. `DROP tasks_implementation`, `ALTER TABLE tasks_implementation_v2 RENAME TO tasks_implementation`
10. Re-create `acceptance_criteria_implementation`, `task_files_implementation`, `tags_implementation` (or use `PRAGMA foreign_keys=OFF` and re-attach)

### 4.3 Rollback Strategy
- Before migration: `BACKUP .data/tasks.db`
- Rollback: restore backup

## 5. spec_parser Module Design

### 5.1 loader.py
```python
import glob, os, codecs

def load_file(filepath: str) -> dict:
    with codecs.open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    return {"path": filepath, "content": content, "filename": os.path.basename(filepath)}

def load_directory(dirpath: str, pattern: str = "*.md") -> list[dict]:
    files = glob.glob(os.path.join(dirpath, pattern))
    return [load_file(f) for f in sorted(files)]
```

### 5.2 parser.py
```python
import mistune

markdown = mistune.create_markdown(renderer='ast', plugins=['task_lists'])

def parse(content: str) -> list[dict]:
    return markdown(content)

def visit(tokens: list[dict]) -> dict:
    # Walk AST and extract: sections, acceptance_criteria, code_blocks
    ...
```

### 5.3 extractor.py
```python
def extract_document(parsed: dict, filepath: str) -> dict:
    # Map parsed AST → document JSON Schema
    # Return: {doc_id, file_path, title, content, status}

def extract_sub_tasks(parsed: dict, doc_id: str) -> list[dict]:
    # For each section heading → one sub-task
    # Return: [{sub_task_id, parent_doc_id, source.section_title, task.title, ...}]
```

## 6. Implementation Phases

### Phase 1: Create document schema + spec_parser module
- **Files**: `document-schema.json`, `schemas/document.py`, `spec_parser/*`
- **Dependencies**: `pip install mistune`
- **Test**: parser can read `AA-C05-ThreadModel.md` and extract sections + ACs

### Phase 2: Revise implementation schema
- **Files**: `implementation-schema.json`, `schemas/implementation.py`, `store.py`
- Add `parent_doc_id` to DDL
- Remove `source.file`/`section_markdown` from required
- Add document CRUD to store

### Phase 3: Migration
- **Files**: `data/migration.py`
- Ship CLI command: `task migrate`
- Migrate `.data/tasks.db`

### Phase 4: Surface updates
- **Files**: `commands.py`, `mcp_server.py`, `validator.py`
- Update all handlers for new field layout
- Add CLI command: `task load-docs --dir <path>`

### Phase 5: Tests + docs
- **Files**: All test files, `SKILL.md`, `onboarding.md`
- Add `spec_parser` tests
- Update skill workflows for document-first approach

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Content loss during migration | Medium | High | Read full .md files from disk, not DB `section_markdown` |
| Old JSON files fail validation | Certain | Medium | Export all tasks after migration |
| MCP resource clients break | Medium | Medium | Version the `task://` resource or add `doc://` resource |
| `mistune` behavior differences | Low | Low | `mistune` is CommonMark-compliant, tested on 50+ files |
| Foreign key constraint failures | Low | Low | `PRAGMA foreign_keys=OFF` (default) |

## 8. Effort Estimate
- Phase 1 (schema + parser): 4–6 hours
- Phase 2 (revised implementation): 2–3 hours
- Phase 3 (migration): 2–3 hours
- Phase 4 (surface): 2–3 hours
- Phase 5 (tests + docs): 3–4 hours
- **Total: ~15–20 hours (2–3 days)**

## 9. Recommendation
Proceed with Phase 1 first (document schema + `spec_parser`), validate independently, then proceed through remaining phases sequentially.
