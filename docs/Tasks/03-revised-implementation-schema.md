# Task: Revised Implementation Schema

**Component:** Update existing `implementation` schema
**Depends on:** `02-document-schema.md` (parent_doc_id references tasks_document)
**Phase:** 3

## Description

Revise the `implementation` schema to:
1. Remove `source.file`, `source.section_markdown` from `required`
2. Add optional `parent_doc_id` field
3. Update DDL: remove `source_file`, `source_lines`, `section_title`, `section_markdown` columns; add `parent_doc_id TEXT`
4. Update `store.py` `_build_main_insert`: drop source field handling, add `parent_doc_id`
5. Update `implementation-schema.json` accordingly

## Files to Modify

| File | Changes |
|------|---------|
| `default_schemas/implementation-schema.json` | Remove `source` from `required`; remove `file`, `section_markdown` from source block; add optional `parent_doc_id` at top level |
| `task_cli/schemas/implementation.py` | Update DDL (4 columns out, parent_doc_id in); update extra_columns |
| `task_cli/data/store.py` | `_build_main_insert`: remove `source_file`, `source_lines`, `section_title`, `section_markdown` from the column assignments; add `parent_doc_id` |

## implementation-schema.json Changes

```json
{
  "required": [
    "sub_task_id",
    "sequence",
    "hierarchy_level",
    "metadata",
    "task",
    "traceability",
    "status"
  ],
  "properties": {
    "sub_task_id": { "type": "string", "pattern": "^[A-Z][A-Z0-9._-]+$" },
    "sequence": { "type": "integer", "minimum": 1 },
    "hierarchy_level": { "type": "integer", "minimum": 1, "maximum": 10 },
    "parent_doc_id": {
      "type": "string",
      "description": "References tasks_document.id — the source spec document"
    },
    "source": {
      "type": "object",
      "description": "Section origin info within the parent document (optional)",
      "properties": {
        "relative_path": { "type": "string" },
        "lines": { "$ref": "#/definitions/line_range" },
        "section_title": { "type": "string" }
      }
    },
    "metadata": { ... },
    "task": { ... },
    "traceability": { ... },
    "status": { ... },
    "children": { ... },
    "notes": { ... }
  }
}
```

## implementation.py DDL Changes

Remove these columns from `tasks_implementation` DDL:
- `source_file TEXT`
- `source_lines TEXT`
- `section_title TEXT`
- `section_markdown TEXT`

Add:
- `parent_doc_id TEXT`

New DDL:
```sql
CREATE TABLE IF NOT EXISTS tasks_implementation (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    parent_doc_id TEXT,
    sequence INT,
    hierarchy_level INT,
    title TEXT,
    description TEXT,
    phase INT,
    effort TEXT,
    impl_notes TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT
);
```

## store.py _build_main_insert Changes

Remove these lines (currently ~lines 37-40):
```python
extra["source_file"] = data["source"].get("relative_path", "") or ""
extra["source_lines"] = str(data["source"].get("lines", ""))
extra["source"]["section_title"] = data["source"].get("section_title", "") or ""
extra["source"]["section_markdown"] = data["source"].get("section_markdown", "") or ""
```

Add:
```python
extra["parent_doc_id"] = data.get("parent_doc_id", "") or ""
```

## Acceptance Criteria

1. `implementation-schema.json` validates a sub-task JSON without `source.file` — passes
2. `implementation-schema.json` validates a sub-task JSON with `parent_doc_id` — passes
3. `implementation-schema.json` still validates old-format JSON (backward compat for `source` block as optional) — passes
4. DDL no longer has `source_file`, `source_lines`, `section_title`, `section_markdown` columns
5. DDL has `parent_doc_id TEXT` column
6. `store.insert_task("implementation", data)` works with new format (no source fields)
7. `store.get_task("implementation", task_id)` returns dict without source fields, with `parent_doc_id`
8. `extra_columns` in schema registration only includes `effort` and `parent_doc_id`
9. All existing tests pass (after test fixtures updated in Phase 5)
