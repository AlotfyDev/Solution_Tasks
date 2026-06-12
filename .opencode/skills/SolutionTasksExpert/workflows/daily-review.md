# Daily Progress Review

Use this workflow for regular status checks.

## Step 1: Full Status

```
Call: status_report()
```

Review: completion %, blocked count, recent activity, counts by schema and phase.

## Step 2: By Phase

For each phase 0–9:

```
Call: list_tasks(phase=<N>)
```

Check if any phase has many `pending` or `in_progress` items. Prioritize lower phases first.

## Step 3: Blockers

```
Call: list_tasks(status="blocked")
```

For each blocked task:

```
Call: dependency_chain(task_id=<blocked_id>)
```

Identify the root cause — which upstream dependency is itself blocked or incomplete.

## Step 4: Coverage Gaps

```
Call: gap_analysis()
```

Note which implementation tasks lack test coverage. These are candidates for the gap-closure workflow.

## Step 5: Recent Changes

For each active (in_progress / blocked) task:

```
Call: get_history(task_id=<active_id>, limit=10)
```

Review status transitions and notes to understand what changed since last session.

## Summary Format

Report to user:

- **Completion**: X% overall
- **Blocked**: N items (list IDs + reasons)
- **At Risk**: items pending > 3 days
- **Gaps**: M implementation tasks without tests
- **Next Actions**: recommended priorities
