# Task: Document Schema

**Component:** New schema `document`
**Depends on:** `01-spec-parser-module.md` (extractor output format)
**Phase:** 2

## Description

Create a new `document` schema in the registry with its own table, JSON Schema, and CRUD operations. One document record per markdown spec file — stores the full file content.

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `default_schemas/document-schema.json` | CREATE | JSON Schema for document records |
| `task_cli/schemas/document.py` | CREATE | Register document schema with DDL |
| `task_cli/data/store.py` | MODIFY | Add `insert_document()`, `get_document()`, `list_documents()` |
| `task_cli/presentation/catalog.py` | MODIFY | Add `document` to auto-generated schema list (if needed — likely auto) |

## document-schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "document-schema.json",
  "title": "Document Schema",
  "description": "One row per markdown specification file, stores full content.",
  "type": "object",
  "required": ["doc_id", "file_path", "title", "content"],
  "properties": {
    "doc_id": {
      "type": "string",
      "pattern": "^[A-Z][A-Z0-9._-]+$",
      "description": "Derived from filename, e.g. AA-M06"
    },
    "file_path": { "type": "string" },
    "title": { "type": "string" },
    "content": { "type": "string" },
    "status": {
      "type": "object",
      "properties": {
        "state": { "type": "string", "enum": ["pending", "in_progress", "completed", "blocked", "cancelled"] }
      },
      "required": ["state"]
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "notes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": { "type": "string" },
          "text": { "type": "string" },
          "author": { "type": "string" }
        }
      }
    }
  }
}
```

## schemas/document.py

```python
from pathlib import Path
from ..registry.base import TaskSchema

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "default_schemas"

def register_document_schema(reg):
    reg.register(TaskSchema(
        schema_id="document",
        version="1.0",
        title="Document Schema",
        json_schema_path=SCHEMA_DIR / "document-schema.json",
        table_names={"main": "tasks_document"},
        ddl_statements=[_ddl()],
        extra_columns=[],
        id_prefix="",
        task_id_pattern=r"^[A-Z][A-Z0-9._-]+$",
    ))

def _ddl():
    return """CREATE TABLE IF NOT EXISTS tasks_document (
        id TEXT PRIMARY KEY,
        file_path TEXT,
        title TEXT,
        content TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT
    );"""
```

## store.py — Document CRUD

Add three methods:

```python
def insert_document(self, data: dict) -> str:
    """Insert one document record. Simpler than insert_task:
    no sub-tables (criteria, files, tags). Returns doc_id."""
    doc_id = data["doc_id"]
    now = datetime.now().isoformat()
    self._engine.execute(
        """INSERT OR REPLACE INTO tasks_document
           (id, file_path, title, content, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, COALESCE(?, ?), ?)""",
        (doc_id, data["file_path"], data["title"], data["content"],
         data.get("status", {}).get("state", "pending"), None, now, now)
    )
    return doc_id

def get_document(self, doc_id: str) -> dict | None:
    row = self._engine.fetchone("SELECT * FROM tasks_document WHERE id = ?", (doc_id,))
    if not row:
        return None
    return dict(row)

def list_documents(self) -> list[dict]:
    rows = self._engine.execute("SELECT * FROM tasks_document ORDER BY id").fetchall()
    return [dict(r) for r in rows]
```

## Acceptance Criteria

1. `TaskSchema` with `schema_id="document"` registers without errors
2. `register_document_schema(reg)` adds "document" to `reg.list()`
3. `tasks_document` table created on `DatabaseEngine.connect()`
4. `store.insert_document(data)` inserts a row and returns the doc_id
5. `store.get_document(doc_id)` returns the full row as dict
6. `store.list_documents()` returns all document rows
7. `store.insert_document` with existing doc_id does UPSERT (idempotent)
8. JSON Schema `document-schema.json` validates against `TaskValidator`
9. Document schema has NO sub-tables (no criteria, files, tags tables)
10. All tests pass
