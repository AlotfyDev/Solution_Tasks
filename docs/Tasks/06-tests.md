# Task: Tests for Document Schema & Pipeline

**Component:** Test suite updates  
**Depends on:** All prior phases  
**Phase:** 5

## Description

Add and update tests for the entire document pipeline: spec_parser, document CRUD, revised implementation schema, load-docs command, and MCP tools.

## Files to Create

| File | Purpose |
|------|---------|
| `tests/test_parser.py` | Unit tests for spec_parser module |
| `tests/testdata/sample-spec.md` | Sample markdown file for parser tests |

## Files to Modify

| File | Changes |
|------|---------|
| `tests/conftest.py` | Remove `source.file`, `source.section_markdown` from fixtures; add `parent_doc_id`; add `doc_data` fixture |
| `tests/test_store.py` | Add `test_insert_document`, `test_get_document`, `test_list_documents`; update existing impl task tests |
| `tests/test_validator.py` | Update inline data dicts to match new schema; add document schema validation tests |
| `tests/test_commands.py` | Update inline data dicts; add `test_cmd_load_docs` |
| `tests/test_mcp_server.py` | Add tests for `insert_document`, `get_document`, `list_documents`, `doc://` resource; update test data for revised schema |
| `tests/test_integration.py` | Update inline data dicts; add document-first integration path |

## testdata/sample-spec.md

Create a minimal markdown file for parser tests:

```markdown
# AA-TEST — Test Document

This is a test specification for parser unit tests.

## Step 1 — Do the Thing

First step description.

- [ ] Acceptance criterion one
- [x] Already done criterion

## Step 2 — Do Another Thing

Second step description.

```cpp
void Foo() {}
```

- [ ] Another criterion
```

## test_parser.py Tests

```python
class TestLoader:
    def test_load_file_exists(self):
        ...
    def test_load_file_not_found(self):
        ...
    def test_load_file_utf8_bom(self):
        ...  # file with BOM header
    def test_load_directory(self):
        ...

class TestParser:
    def test_parse_returns_list(self):
        ...
    def test_parse_heading_detection(self):
        ...  # h1, h2, h3
    def test_parse_task_list_items(self):
        ...  # - [ ] and - [x]
    def test_parse_code_block(self):
        ...  # ```lang ... ```
    def test_visit_sections(self):
        ...  # sections grouped correctly
    def test_visit_acceptance_criteria(self):
        ...  # all ACs extracted

class TestExtractor:
    def test_extract_document(self):
        ...  # correct doc_id, title, content
    def test_extract_sub_tasks_count(self):
        ...  # correct number of sub-tasks
    def test_extract_sub_tasks_structure(self):
        ...  # each sub-task has correct fields
```

## conftest.py Changes

Current fixture `impl_task_data` (~lines 70-105):
- Remove `source.file` and `source.section_markdown`
- Add `parent_doc_id: "AA-TEST"`

Add new fixture `doc_data`:
```python
@pytest.fixture
def doc_data() -> dict:
    return {
        "doc_id": "AA-TEST",
        "file_path": "docs/AA-TEST.md",
        "title": "AA-TEST — Test Document",
        "content": "# AA-TEST — Test Document\n\nTest content.",
        "status": {"state": "pending"},
    }
```

Add `register_document_schema(reg)` in registry fixture.

## Acceptance Criteria

1. All parser tests pass with sample-spec.md
2. All document CRUD tests pass
3. All existing tests pass with updated fixtures
4. load-docs test creates documents + sub-tasks, verifies via get
5. MCP document tool tests pass
6. Integration test covers: create document → parse → extract → insert sub-tasks → verify relationships
7. Coverage of spec_parser module > 80%
