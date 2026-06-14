# Task: Legacy Data Migration (Future)

**Component:** Migration script  
**Depends on:** All prior phases (the pipeline must exist first)  
**Phase:** Future (not current sprint)

## Description

Migrate the existing 92 rows in `tasks_implementation` from the old schema (with `source_file`, `source_lines`, `section_title`, `section_markdown` columns) to the new schema (with `parent_doc_id`).

## Strategy

Use the same `spec_parser` pipeline that `load-docs` uses — read the actual .md files from disk, create documents, then match existing sub-tasks to documents via source file name.

## Migration Steps

1. **Backup**: `copy .data/tasks.db .data/tasks.db.bak`
2. **Create documents**: For each distinct `source_file`, load the .md file from disk → create document record (idempotent — uses `insert_document`)
3. **Match sub-tasks**: For each task in `tasks_implementation`, look up document by `source_file` → set `parent_doc_id`
4. **Clean up columns**: After migration, the DDL will no longer have source columns. If we keep them as nullable, old data still works but new code ignores them.
5. **Verify**: All sub-tasks have `parent_doc_id` set, all document references are valid

## Legacy Data Queries

```python
# Find all unique source files
SELECT DISTINCT source_file FROM tasks_implementation WHERE source_file IS NOT NULL;

# For each source file, load the .md from disk and create document
# Match: filename in source_file matches a .md file in the docs directory

# Set parent_doc_id from source_file
UPDATE tasks_implementation
SET parent_doc_id = ?
WHERE source_file = ?;

# Verify no orphans
SELECT id FROM tasks_implementation
WHERE (parent_doc_id IS NULL OR parent_doc_id = '')
  AND source_file IS NOT NULL AND source_file != '';
```

## When to Run This

Only after:
1. `spec_parser` is built and tested
2. `document` schema is in the registry
3. `load-docs` command works for new files
4. The legacy data is needed (e.g., when we want to link testing tasks to existing implementation tasks)

## Priority

**LOW** — The system works with the new pipeline for new spec files. Legacy data can remain in its current form until we need to query/update it with the new tools.
