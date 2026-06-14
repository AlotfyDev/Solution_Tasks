# Task: MCP Tools & Resources Update

**Component:** MCP server updates for document schema  
**Depends on:** `02-document-schema.md` (store document CRUD)  
**Phase:** 4

## Description

Update the MCP server to expose document-related tools and resources alongside existing task tools.

## Files to Modify

| File | Changes |
|------|---------|
| `task_cli/mcp_server.py` | Add `insert_document`, `get_document`, `list_documents` tools; add `doc://` resource; update `task://` resource to include `parent_doc_id` |
| `task_cli/presentation/catalog.py` | Add `insert_document`, `get_document`, `list_documents` to `_mcp_tools` list |

## New MCP Tools

### `insert_document`
```
@mcp.tool(description="Insert a document record (one per markdown spec file)")
def insert_document(doc_id: str, file_path: str, title: str, content: str, status: str = "pending") -> str:
```
- Creates document in `tasks_document`
- Validates against `document-schema.json` before insert
- Returns doc_id on success

### `get_document`
```
@mcp.tool(description="Get a document record by ID")
def get_document(doc_id: str) -> str:
```
- Returns document JSON or "not found"
- Used by sub-agents to fetch full spec content

### `list_documents`
```
@mcp.tool(description="List all document records")
def list_documents() -> str:
```
- Returns JSON array of all documents

## New MCP Resource

### `doc://{doc_id}`
```
@mcp.resource(uri="doc://{doc_id}", name="Document by ID")
def get_document_resource(doc_id: str) -> str:
    ...
```
- Returns full document JSON (same as `get_document` tool)
- Format: JSON with doc_id, file_path, title, content, status

## Updated MCP Tool

### `update_task` (existing, line ~108)

Update the column list in the tool description:
- Remove: `source_file`, `section_markdown`, `section_title`
- Add: `parent_doc_id`

## Updated MCP Resource

### `task://{schema_id}/{task_id}` (existing)

The JSON output will no longer contain `source_file`, `source_lines`, `section_title`, `section_markdown`. Will contain `parent_doc_id` instead. This is a backward-incompatible change — document in release notes.

## Tool Count

Total tools: 22 → **25** (+3 new document tools)
Total resources: 5 → **6** (+1 doc:// resource)

## Acceptance Criteria

1. `insert_document(doc_id, file_path, title, content)` creates a document record
2. `get_document(doc_id)` returns the document JSON
3. `list_documents()` returns all documents as JSON array
4. `doc://{doc_id}` resource returns the same content as `get_document`
5. `insert_document` validates against `document-schema.json`
6. `update_task` description lists `parent_doc_id` instead of source fields
7. All existing MCP tests pass
8. Server starts without errors with the new tools registered
