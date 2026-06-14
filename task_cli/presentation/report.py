from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from task_cli.data.engine import DatabaseEngine
from task_cli.data.store import TaskStore
from task_cli.history.tracker import HistoryTracker
from task_cli.registry import SchemaRegistry


class ReportGenerator:
    """Generates progress reports from the task database."""

    VALID_STATES = ["pending", "in_progress", "completed", "blocked", "cancelled"]

    def __init__(self, engine: DatabaseEngine, store: TaskStore,
                 history: HistoryTracker, registry: SchemaRegistry):
        self._engine = engine
        self._store = store
        self._history = history
        self._registry = registry

    def _main_table(self, schema_id: str) -> str:
        return self._registry.get(schema_id).table_names["main"]

    def summary_by_schema(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for sid in self._registry.list_ids():
            rows = self._engine.fetchall(
                f"SELECT status, COUNT(*) as cnt FROM {self._main_table(sid)} GROUP BY status"
            )
            result[sid] = {r["status"]: r["cnt"] for r in rows}
        return result

    def summary_by_phase(self, schema_id: Optional[str] = None) -> dict[int, dict[str, int]]:
        schema_ids = [schema_id] if schema_id else self._registry.list_ids()
        result: dict[int, dict[str, int]] = {}
        for sid in schema_ids:
            try:
                rows = self._engine.fetchall(
                    f"SELECT phase, status, COUNT(*) as cnt FROM {self._main_table(sid)} "
                    f"GROUP BY phase, status ORDER BY phase"
                )
                for r in rows:
                    phase = r["phase"]
                    if phase not in result:
                        result[phase] = {}
                    result[phase][r["status"]] = result[phase].get(r["status"], 0) + r["cnt"]
            except Exception:
                continue
        return result

    def full_report(self, schema_id: Optional[str] = None) -> str:
        schema_ids = [schema_id] if schema_id else self._registry.list_ids()
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("TASK PROGRESS REPORT")
        lines.append("=" * 60)

        # 1. Overview
        lines.append("\n--- Overview ---")
        total = 0
        completed = 0
        for sid in schema_ids:
            rows = self._engine.fetchall(
                f"SELECT status, COUNT(*) as cnt FROM {self._main_table(sid)} GROUP BY status"
            )
            for r in rows:
                total += r["cnt"]
                if r["status"] == "completed":
                    completed += r["cnt"]
        pct = (completed / total * 100) if total else 0.0
        lines.append(f"  Total tasks:    {total}")
        lines.append(f"  Completed:      {completed}")
        lines.append(f"  Completion:     {pct:.1f}%")

        # 2. By Status
        lines.append("\n--- By Status ---")
        status_counts: dict[str, int] = {}
        for sid in schema_ids:
            rows = self._engine.fetchall(
                f"SELECT status, COUNT(*) as cnt FROM {self._main_table(sid)} GROUP BY status"
            )
            for r in rows:
                status_counts[r["status"]] = status_counts.get(r["status"], 0) + r["cnt"]
        lines.append(f"  {'Status':<15} {'Count':>5}")
        lines.append(f"  {'-' * 21}")
        for s in self.VALID_STATES:
            lines.append(f"  {s:<15} {status_counts.get(s, 0):>5}")
        lines.append(f"  {'-' * 21}")
        lines.append(f"  {'TOTAL':<15} {total:>5}")

        # 3. By Phase
        lines.append("\n--- By Phase ---")
        phase_summary = self.summary_by_phase(schema_id)
        if phase_summary:
            lines.append(f"  {'Phase':<7} {'Status':<15} {'Count':>5}")
            lines.append(f"  {'-' * 29}")
            for phase in sorted(phase_summary):
                for s in self.VALID_STATES:
                    cnt = phase_summary[phase].get(s, 0)
                    if cnt:
                        lines.append(f"  {phase:<7} {s:<15} {cnt:>5}")
        else:
            lines.append("  (no data)")

        # 4. By Schema
        if schema_id is None:
            lines.append("\n--- By Schema ---")
            by_schema = self.summary_by_schema()
            if by_schema:
                for sid, states in by_schema.items():
                    lines.append(f"  {sid}:")
                    for s in self.VALID_STATES:
                        cnt = states.get(s, 0)
                        if cnt:
                            lines.append(f"    {s:<15} {cnt}")
            else:
                lines.append("  (no schemas)")

        # 5. Blocked Tasks
        lines.append("\n--- Blocked Tasks ---")
        found_blocked = False
        for sid in schema_ids:
            try:
                blocked = self._engine.fetchall(
                    f"SELECT id, title, phase FROM {self._main_table(sid)} WHERE status = 'blocked'"
                )
                if blocked:
                    found_blocked = True
                    lines.append(f"  [{sid}]")
                    for b in blocked:
                        lines.append(f"    {b['id']}: {b.get('title', '')} (phase {b.get('phase', '')})")
            except Exception:
                continue
        if not found_blocked:
            lines.append("  (none)")

        # 6. Recent Activity
        lines.append("\n--- Recent Activity (last 10) ---")
        recent = self._history.get_recent_changes(limit=10, schema_id=schema_id)
        if recent:
            for r in recent:
                lines.append(
                    f"  [{r['changed_at']}] {r['task_id']}: "
                    f"{r['field_name']} '{r.get('old_value') or ''}' -> '{r.get('new_value') or ''}'"
                )
        else:
            lines.append("  (no activity)")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def gap_analysis(self) -> str:
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("GAP ANALYSIS")
        lines.append("=" * 60)

        # 1. Implementation tasks without linked test tasks
        lines.append("\n1. Implementation tasks without linked test tasks:")
        impl_table = self._registry.get("implementation").table_names["main"]
        impl_tasks = self._engine.fetchall(
            f"SELECT t.id, t.title, t.status "
            f"FROM {impl_table} t "
            f"WHERE t.id NOT IN ("
            f"  SELECT target_id FROM task_relationships "
            f"  WHERE rel_type = 'tests' AND target_schema = 'implementation'"
            f")"
        )
        if impl_tasks:
            for t in impl_tasks:
                lines.append(f"   {t['id']}: {t.get('title', '')} [{t['status']}]")
        else:
            lines.append("   (none)")

        # 2. Test tasks referencing missing implementation tasks
        lines.append("\n2. Test tasks referencing missing implementation tasks:")
        testing_table = self._registry.get("testing").table_names["main"]
        impl_table = self._registry.get("implementation").table_names["main"]
        orphan_tests = self._engine.fetchall(
            f"SELECT t.id, t.parent_aa_id, t.title "
            f"FROM {testing_table} t "
            f"LEFT JOIN {impl_table} i ON t.parent_aa_id = i.id "
            f"WHERE t.parent_aa_id IS NOT NULL AND t.parent_aa_id != '' AND i.id IS NULL"
        )
        if orphan_tests:
            for t in orphan_tests:
                lines.append(f"   {t['id']}: parent_aa_id={t['parent_aa_id']} ({t.get('title', '')})")
        else:
            lines.append("   (none)")

        # 3. Tasks pending/blocked for more than 7 days
        lines.append("\n3. Tasks pending/blocked for > 7 days:")
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        stale: list[tuple[str, dict]] = []
        for sid in self._registry.list_ids():
            rows = self._engine.fetchall(
                f"SELECT id, title, status, created_at FROM {self._main_table(sid)} "
                f"WHERE status IN ('pending', 'blocked') "
                f"AND created_at < :threshold",
                {"threshold": seven_days_ago}
            )
            for r in rows:
                stale.append((sid, r))
        if stale:
            for sid, r in stale:
                lines.append(f"   [{sid}] {r['id']}: {r.get('title', '')} "
                             f"[{r['status']}] since {r.get('created_at', '')}")
        else:
            lines.append("   (none)")

        # 4. Schemas with zero tasks
        lines.append("\n4. Schemas with zero tasks:")
        empty: list[str] = []
        for sid in self._registry.list_ids():
            cnt = self._engine.fetchone(
                f"SELECT COUNT(*) as cnt FROM {self._main_table(sid)}"
            )
            if cnt and cnt["cnt"] == 0:
                empty.append(sid)
        if empty:
            for sid in empty:
                lines.append(f"   {sid}")
        else:
            lines.append("   (none)")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def dependency_chain(self, task_id: str, schema_id: str) -> str:
        lines: list[str] = []
        lines.append(f"Dependency chain for {task_id} [{schema_id}]:")
        visited: set[str] = set()

        def resolve(current_id: str, current_schema: str, depth: int = 0) -> None:
            indent = "  " * depth
            key = f"{current_schema}:{current_id}"
            if key in visited:
                lines.append(f"{indent}-> {current_id} [{current_schema}] (CYCLE!)")
                return
            visited.add(key)

            task = self._engine.fetchone(
                f"SELECT id, title FROM {self._main_table(current_schema)} WHERE id = ?",
                (current_id,)
            )
            title = task["title"] if task else "(unknown)"
            if depth == 0:
                lines.append(f"{indent}{current_id} [{current_schema}] \u2014 {title}")
            else:
                lines.append(f"{indent}depends on {current_id} [{current_schema}] \u2014 {title}")

            deps = self._engine.fetchall(
                "SELECT target_id, target_schema FROM task_relationships "
                "WHERE source_id = :sid AND source_schema = :ss AND rel_type = 'depends_on'",
                {"sid": current_id, "ss": current_schema}
            )
            for dep in deps:
                resolve(dep["target_id"], dep["target_schema"], depth + 1)

        resolve(task_id, schema_id)
        return "\n".join(lines)

    def export_json(self, schema_id: Optional[str] = None,
                    status_filter: Optional[str] = None) -> list[dict]:
        schema_ids = [schema_id] if schema_id else self._registry.list_ids()
        result: list[dict] = []
        for sid in schema_ids:
            if status_filter:
                rows = self._engine.fetchall(
                    f"SELECT * FROM {self._main_table(sid)} WHERE status = :status",
                    {"status": status_filter}
                )
            else:
                rows = self._engine.fetchall(
                    f"SELECT * FROM {self._main_table(sid)}"
                )
            for r in rows:
                entry = dict(r)
                entry["schema_id"] = sid
                result.append(entry)
        return result
