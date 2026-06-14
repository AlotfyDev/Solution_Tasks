# Task: `task load-docs` CLI Command

**Component:** New CLI subcommand  
**Depends on:** `01-spec-parser-module.md` + `02-document-schema.md` + `03-revised-implementation-schema.md`
**Phase:** 4

## Description

Add a `task load-docs` command that:
1. Reads all .md files from a directory using `spec_parser/loader.py`
2. Parses each file using `spec_parser/parser.py`
3. Creates document records in `tasks_document`
4. Extracts and inserts sub-tasks into `tasks_implementation`
5. Is idempotent — re-running updates existing records

## Files to Modify

| File | Changes |
|------|---------|
| `task_cli/presentation/commands.py` | Add `cmd_load_docs()` handler, register in `build_parser()` |
| `task_cli/main.py` | Auto-register document schema alongside implementation/testing (if needed) |

## Command Interface

```
task load-docs --dir <path> [--pattern "*.md"] [--dry-run]
```

- `--dir` (required): path to directory containing .md spec files
- `--pattern` (optional, default "*.md"): glob pattern
- `--dry-run` (optional): parse and print what would be inserted, don't touch DB

## cmd_load_docs Logic

```
For each file in load_directory(dir, pattern):
    1. file_data = load_file(filepath)
    2. tokens = parse(file_data["content"])
    3. parsed = visit(tokens)
    
    4. doc_data = extract_document(parsed, filepath)
    5. If not dry_run:
           store.insert_document(doc_data)
           print(f"  Document: {doc_data['doc_id']}")
    
    6. sub_tasks = extract_sub_tasks(parsed, doc_data["doc_id"])
    7. For each sub_task in sub_tasks:
           errors = validator.validate(sub_task, "implementation")
           If errors:
               print(f"  SKIP {sub_task['sub_task_id']}: {errors}")
           Else if not dry_run:
               store.insert_task("implementation", sub_task)
               print(f"  Sub-task: {sub_task['sub_task_id']}")
    
    8. Commit transaction
```

## Output Example

```
$ task load-docs --dir Logger_Adapter/.docs/After_Audit_Implementation_Tasks --dry-run

Loaded 23 files
Document: AA-C05 (Phase 0, 8682 chars)
  Sub-task: AA-C05-01 — Thread Ownership Model
  Sub-task: AA-C05-02 — Concurrency Contract
  ... (25 sub-tasks total from AA-C05)
Document: AA-M06 (Phase 4, 8811 chars)
  Sub-task: AA-M06-01 — Publish Pattern Grammar
  ...
---
Dry run: 23 documents, 84 sub-tasks would be created
```

## Acceptance Criteria

1. `task load-docs --help` shows the command with all arguments
2. `task load-docs --dir <non-existent-dir>` returns clear error
3. `task load-docs --dir <dir-with-no-md-files>` returns "No .md files found"
4. `task load-docs --dir <dir> --dry-run` prints what would happen, no DB changes
5. `task load-docs --dir <dir>` creates documents + sub-tasks, all validatable
6. Running `load-docs` twice on same dir: second run updates existing records (idempotent)
7. A file with invalid content produces an error for that file, doesn't abort the batch
8. Exit code 0 on success, 1 on any error
