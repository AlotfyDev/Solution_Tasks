# Task: spec_parser Module

**Component:** New module `spec_parser/`
**Depends on:** `mistune` (PyPI)
**Phase:** 1

## Description

Build a markdown parsing pipeline using `mistune` that reads .md spec files from disk and produces structured data ready for JSON Schema validation.

## Files to Create

| File | Lines | Purpose |
|------|-------|---------|
| `spec_parser/__init__.py` | ~3 | Package init, exports `load_file`, `parse`, `extract_document`, `extract_sub_tasks` |
| `spec_parser/loader.py` | ~20 | Read single file or batch directory of .md files |
| `spec_parser/parser.py` | ~60 | mistune AST walker: tokenize → structured tree |
| `spec_parser/extractor.py` | ~40 | Map AST → document JSON + sub-task JSON list |

## spec_parser/__init__.py

```python
from .loader import load_file, load_directory
from .parser import parse, visit
from .extractor import extract_document, extract_sub_tasks

__all__ = ["load_file", "load_directory", "parse", "visit", "extract_document", "extract_sub_tasks"]
```

## spec_parser/loader.py

Read markdown files from disk with UTF-8 BOM handling.

```python
import glob, os, codecs

def load_file(filepath: str) -> dict:
    """Read a single .md file, return {path, filename, content}."""
    ...

def load_directory(dirpath: str, pattern: str = "*.md") -> list[dict]:
    """Glob all .md files in a directory, return sorted list of loaded files."""
    ...
```

## spec_parser/parser.py

Use mistune AST mode with task_lists plugin.

```python
import mistune

_markdown = mistune.create_markdown(renderer='ast', plugins=['task_lists'])

def parse(content: str) -> list[dict]:
    """Parse markdown string into mistune AST token list."""
    return _markdown(content)

def visit(tokens: list[dict]) -> dict:
    """Walk AST and extract:
    - sections: [{title, level, paragraphs, list_items, ac_items, code_blocks}]
    - file_refs: [{path, change_type}] from file references in text
    - acceptance_criteria: [{text, checked}] aggregated from all sections
    """
    ...
```

## spec_parser/extractor.py

Map the visited AST into JSON Schema structures.

```python
def extract_document(parsed: dict, filepath: str) -> dict:
    """Build a document schema record:
    - doc_id: from filename (e.g., 'AA-M06-CustomPatternPerSink' -> 'AA-M06')
    - file_path: relative path
    - title: first h1 heading
    - content: raw markdown
    - status: {state: 'pending'}
    """
    ...

def extract_sub_tasks(parsed: dict, doc_id: str) -> list[dict]:
    """For each major section heading, build an implementation task:
    - sub_task_id: f"{doc_id}-{seq:02d}"
    - parent_doc_id: doc_id
    - hierarchy_level: 1
    - source.section_title: heading text
    - source.section_markdown: section content
    - task.title: from heading
    - task.description: first paragraph of section
    - acceptance_criteria: from - [ ] items in section
    - metadata.phase, metadata.effort: extracted from parent doc metadata
    """
    ...
```

## Acceptance Criteria

1. `pip install mistune` — single dependency, zero transitive deps
2. `load_file("AA-C05-ThreadModel.md")` returns `{path, filename, content}`
3. `parse(content)` returns mistune AST (list of dicts with heading, paragraph, list, task_list_item, block_code types)
4. `visit(tokens)` returns structured dict with `sections`, `acceptance_criteria`, `code_blocks`
5. `visit` correctly extracts `- [ ]` and `- [x]` items via mistune's `task_lists` plugin
6. `visit` correctly groups paragraphs under their nearest preceding heading
7. `extract_document(parsed, filepath)` returns a dict matching `document-schema.json`
8. `extract_sub_tasks(parsed, doc_id)` returns a list of dicts, each matching `implementation-schema.json` (without `source.file`)
9. Both `load_file` and `load_directory` handle UTF-8 BOM (Windows) and plain UTF-8
10. All functions are pure (no side effects, no DB access)
