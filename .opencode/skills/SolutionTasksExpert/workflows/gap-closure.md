# Gap Closure Workflow

Use this workflow to close gaps between implementation and testing.

## Step 1: Identify Gaps

```
Call: gap_analysis()
```

Look for lines indicating implementation tasks without corresponding test coverage.

## Step 2: For each untested AA task

### 2a. Get the task details

```
Call: get_task(task_id=<aa_task_id>, schema_id="implementation")
```

Examine the acceptance criteria and files to understand what needs testing.

### 2b. Search for existing test designs

```
Call: search_tasks(query="TD-{AA_ID}")
```

The query uses the AA code (e.g., `M05`) to find any TD tasks already linked to it.

### 2c. If no test exists

1. Note that a TD sub-task needs to be created for this AA item.
2. Check the corresponding `Task_Driven_Test_Design/TD-*.md` file for test specifications.
3. Construct the testing task JSON conforming to `testing-schema.json`.
4. Insert via:

```
Call: validate_task(task_json=<td_task_json>)
Call: insert_task(task_json=<td_task_json>)
```

### 2d. Link test to implementation

```
Call: link_tasks(
  source_id=<new_test_task_id>,
  target_id=<aa_task_id>,
  rel_type="tests",
  source_schema="testing",
  target_schema="implementation"
)
```

If specific acceptance criteria are verified, also use `rel_type="verifies"`:

```
Call: link_tasks(
  source_id=<new_test_task_id>,
  target_id=<aa_task_id>,
  rel_type="verifies",
  source_schema="testing",
  target_schema="implementation"
)
```

## Step 3: Verify Coverage

```
Call: gap_analysis()
```

Confirm the gap no longer appears in the report.
