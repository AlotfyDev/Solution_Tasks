from __future__ import annotations

from typing import Any, Optional

from task_cli.data.engine import DatabaseEngine
from task_cli.registry import SchemaRegistry


class TaskStore:
    """CRUD operations for tasks across all registered schemas."""

    VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "blocked", "cancelled"})
    _DELETE_ORDER = ["cases", "criteria", "files", "tags", "scenarios"]

    def __init__(self, engine: DatabaseEngine, registry: SchemaRegistry):
        self._engine = engine
        self._registry = registry

    # ── helpers ──────────────────────────────────────────────────────────────

    def _schema(self, schema_id: str):
        return self._registry.get(schema_id)

    def _main_table(self, schema_id: str) -> str:
        return self._schema(schema_id).table_names["main"]

    def _build_main_insert(self, schema_id: str, data: dict) -> tuple[str, dict]:
        common = {
            "id": data["sub_task_id"],
            "sequence": data.get("sequence", 1),
            "hierarchy_level": data.get("hierarchy_level", 1),
            "title": data["task"]["title"],
            "description": data["task"]["description"],
            "phase": data["metadata"]["phase"],
            "impl_notes": data["task"].get("implementation_notes", ""),
            "status": data["status"]["state"],
            "source_file": data["source"]["file"],
            "source_lines": str(data["source"]["lines"]),
            "section_title": data["source"].get("section_title", ""),
            "section_markdown": data["source"].get("section_markdown", ""),
        }

        extra: dict[str, Any] = {}
        if schema_id == "implementation":
            extra["effort"] = data["metadata"].get("effort", "")
        elif schema_id == "testing":
            extra["test_level"] = data["metadata"].get("test_level", "")

        columns = list(common) + list(extra)
        params = {**common, **extra}
        col_list = ", ".join(columns)
        ph_list = ", ".join(f":{c}" for c in columns)
        table = self._main_table(schema_id)

        sql = (
            f"INSERT INTO {table} ({col_list}, created_at, updated_at) "
            f"VALUES ({ph_list}, datetime('now'), datetime('now'))"
        )
        return sql, params

    def _commit(self) -> None:
        if self._engine._conn is not None:
            self._engine._conn.commit()

    # ── public API ───────────────────────────────────────────────────────────

    def insert_task(self, schema_id: str, data: dict) -> str:
        schema = self._schema(schema_id)
        task_id = data["sub_task_id"]

        sql, params = self._build_main_insert(schema_id, data)
        self._engine.execute(sql, params)

        tnames = schema.table_names

        # acceptance criteria (implementation)
        if "criteria" in tnames:
            items = data.get("task", {}).get("acceptance_criteria", [])
            if items:
                self._engine.execute_many(
                    f"INSERT INTO {tnames['criteria']} "
                    f"(id, task_id, description, verified_by) "
                    f"VALUES (:id, :task_id, :description, :verified_by)",
                    [
                        {
                            "id": c.get("id", ""),
                            "task_id": task_id,
                            "description": c.get("description", ""),
                            "verified_by": c.get("verified_by", ""),
                        }
                        for c in items
                    ],
                )

        # files (both schemas, different columns)
        if "files" in tnames:
            items = data.get("task", {}).get("files_to_modify", [])
            if items:
                if schema_id == "implementation":
                    self._engine.execute_many(
                        f"INSERT INTO {tnames['files']} "
                        f"(task_id, path, change_type, description) "
                        f"VALUES (:task_id, :path, :change_type, :description)",
                        [
                            {
                                "task_id": task_id,
                                "path": f.get("path", ""),
                                "change_type": f.get("change_type", ""),
                                "description": f.get("description", ""),
                            }
                            for f in items
                        ],
                    )
                else:
                    self._engine.execute_many(
                        f"INSERT INTO {tnames['files']} "
                        f"(task_id, path, change_type, framework) "
                        f"VALUES (:task_id, :path, :change_type, :framework)",
                        [
                            {
                                "task_id": task_id,
                                "path": f.get("path", ""),
                                "change_type": f.get("change_type", ""),
                                "framework": f.get("framework", "gtest"),
                            }
                            for f in items
                        ],
                    )

        # tags (implementation)
        if "tags" in tnames:
            items = data.get("metadata", {}).get("tags", [])
            if items:
                self._engine.execute_many(
                    f"INSERT INTO {tnames['tags']} (task_id, tag) "
                    f"VALUES (:task_id, :tag)",
                    [{"task_id": task_id, "tag": t} for t in items],
                )

        # scenarios (testing)
        if "scenarios" in tnames:
            items = data.get("task", {}).get("scenarios", [])
            if items:
                self._engine.execute_many(
                    f"INSERT INTO {tnames['scenarios']} "
                    f"(id, task_id, name, type) "
                    f"VALUES (:id, :task_id, :name, :type)",
                    [
                        {
                            "id": s.get("id", ""),
                            "task_id": task_id,
                            "name": s.get("name", ""),
                            "type": s.get("type", ""),
                        }
                        for s in items
                    ],
                )

        # test cases (testing, nested under files_to_modify)
        if "cases" in tnames:
            cases = []
            for f in data.get("task", {}).get("files_to_modify", []):
                fp = f.get("path", "")
                for tc in f.get("test_cases", []):
                    cases.append({
                        "name": tc.get("name", ""),
                        "file_path": fp,
                        "task_id": task_id,
                        "fixture": tc.get("fixture", ""),
                        "status": tc.get("status", "template"),
                    })
            if cases:
                self._engine.execute_many(
                    f"INSERT INTO {tnames['cases']} "
                    f"(name, file_path, task_id, fixture, status) "
                    f"VALUES (:name, :file_path, :task_id, :fixture, :status)",
                    cases,
                )

        self._commit()
        return task_id

    def update_status(self, schema_id: str, task_id: str, new_state: str) -> None:
        if new_state not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status {new_state!r}. "
                f"Must be one of: {', '.join(sorted(self.VALID_STATUSES))}"
            )
        main_table = self._main_table(schema_id)
        self._engine.execute(
            f"UPDATE {main_table} "
            f"SET status = :status, updated_at = datetime('now') "
            f"WHERE id = :id",
            {"status": new_state, "id": task_id},
        )
        self._commit()

    def get_task(self, schema_id: str, task_id: str) -> Optional[dict]:
        schema = self._schema(schema_id)
        main_table = schema.table_names["main"]

        row = self._engine.fetchone(
            f"SELECT * FROM {main_table} WHERE id = ?", (task_id,)
        )
        if row is None:
            return None

        result = dict(row)
        tnames = schema.table_names

        if "criteria" in tnames:
            result["acceptance_criteria"] = self._engine.fetchall(
                f"SELECT * FROM {tnames['criteria']} WHERE task_id = ?", (task_id,)
            )

        if "files" in tnames:
            result["files"] = self._engine.fetchall(
                f"SELECT * FROM {tnames['files']} WHERE task_id = ?", (task_id,)
            )

        if "tags" in tnames:
            rows = self._engine.fetchall(
                f"SELECT tag FROM {tnames['tags']} WHERE task_id = ?", (task_id,)
            )
            result["tags"] = [r["tag"] for r in rows]

        if "scenarios" in tnames:
            result["scenarios"] = self._engine.fetchall(
                f"SELECT * FROM {tnames['scenarios']} WHERE task_id = ?", (task_id,)
            )

        if "cases" in tnames:
            result["test_cases"] = self._engine.fetchall(
                f"SELECT * FROM {tnames['cases']} WHERE task_id = ?", (task_id,)
            )

        return result

    def list_tasks(
        self,
        schema_id: str,
        status_filter: Optional[str] = None,
        phase_filter: Optional[int] = None,
    ) -> list[dict]:
        main_table = self._main_table(schema_id)
        clauses: list[str] = []
        params: dict[str, Any] = {}

        if status_filter is not None:
            clauses.append("status = :status")
            params["status"] = status_filter
        if phase_filter is not None:
            clauses.append("phase = :phase")
            params["phase"] = phase_filter

        where = ""
        if clauses:
            where = " WHERE " + " AND ".join(clauses)

        return self._engine.fetchall(
            f"SELECT * FROM {main_table}{where} ORDER BY sequence ASC", params
        )

    def delete_task(self, schema_id: str, task_id: str) -> bool:
        schema = self._schema(schema_id)
        main_table = schema.table_names["main"]

        existing = self._engine.fetchone(
            f"SELECT id FROM {main_table} WHERE id = ?", (task_id,)
        )
        if existing is None:
            return False

        for key in self._DELETE_ORDER:
            if key in schema.table_names:
                self._engine.execute(
                    f"DELETE FROM {schema.table_names[key]} WHERE task_id = ?", (task_id,)
                )

        self._engine.execute(f"DELETE FROM {main_table} WHERE id = ?", (task_id,))
        self._commit()
        return True
