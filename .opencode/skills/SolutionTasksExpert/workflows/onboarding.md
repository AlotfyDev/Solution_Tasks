# Onboarding New Tasks

Use this workflow when adding new implementation or testing tasks.

## Step 1: Prepare JSON

The JSON must conform to the schema:
- AA tasks → `implementation-schema.json` (`sub_task_id` pattern: `^[A-Z][A-Z0-9._-]+$`, e.g., `AA-0.5-01` or `M05-01`)
- TD tasks → `testing-schema.json` (`sub_task_id` pattern: `^TD-[A-Z0-9._-]+$`, e.g., `TD-0.5-01` or `TD-M05-01`)

### Required fields — implementation schema
| Field | Details |
|-------|---------|
| `sub_task_id` | Pattern: `^[A-Z][A-Z0-9._-]+$` (e.g., `AA-0.5-01`) |
| `source` | `file`, `relative_path`, `lines`, `section_title` |
| `source.section_markdown` | **Required**: extract actual markdown text from source file for the specified lines |
| `metadata` | `phase` (0–9), `effort`, `dependencies`, `parent_aa`, `parent_title` |
| `task` | `title`, `description`, `acceptance_criteria` (min 1), `files_to_modify` |
| `traceability` | **Required**: `aa_reference`, `td_reference` — do NOT leave empty |
| `status` | `state` in `pending\|in_progress\|completed\|blocked\|cancelled` |

### Required fields — testing schema
| Field | Details |
|-------|---------|
| `sub_task_id` | Pattern: `^TD-[A-Z0-9._-]+$` (e.g., `TD-0.5-01`) |
| `source` | `file`, `relative_path`, `lines`, `section_title` |
| `metadata` | `phase` (0–9), `test_level`, `parent_aa`, `parent_td` |
| `task` | `title`, `description`, `scenarios` (min 1), `files_to_modify` (min 1, each containing test_cases), `acceptance_criteria` (min 1) |
| `traceability` | `aa_reference`, `td_reference` |
| `status` | `state` in `pending\|in_progress\|completed\|blocked\|cancelled` |

## Step 2: Validate

```
Call: validate_task(task_json=<json_string>)
```

If errors → fix JSON, repeat until response is `✓ valid`.

## Step 3: Insert

```
Call: insert_task(task_json=<json_string>)
```

Returns: `Inserted {task_id}`

If `schema_id` is omitted, the server auto-detects from the `sub_task_id` prefix.

## Step 4: Link Dependencies

For each entry in `metadata.dependencies`:

```
Call: link_tasks(
  source_id=<new_task_id>,
  target_id=<dependency_id>,
  rel_type="depends_on",
  source_schema="implementation",
  target_schema="implementation",
  properties='{"type": "hard"}'
)
```

For testing tasks, link to the implementation task:

```
Call: link_tasks(
  source_id=<test_task_id>,
  target_id=<impl_task_id>,
  rel_type="tests",
  source_schema="testing",
  target_schema="implementation"
)
```

## Step 5: Export JSON Files

After inserting and linking, export from DB to JSON:

```
Call: export_tasks(schema_id="implementation", output_dir=<target_directory>)
```

This writes all implementation tasks to JSON files in the output directory. Do NOT write JSON files manually.

For testing tasks:

```
Call: export_tasks(schema_id="testing", output_dir=<target_directory>)
```

## Step 6: [OPTIONAL] Batch Import

If multiple JSON task files exist in a directory:

```
Call: import_tasks(dir_path=<directory_path>, dry_run=true)
```

Use `dry_run=true` first to validate. When ready:

```
Call: import_tasks(dir_path=<directory_path>)
```

## Step 7: Verify

```
Call: get_task(task_id=<new_task_id>)
```

Check all fields, sub-entities (criteria, files, tags, scenarios, test cases), and relationships are correct.
