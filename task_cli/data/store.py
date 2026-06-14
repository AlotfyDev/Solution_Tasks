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
            "impl_notes": data["task"].get("implementation_notes") or "",
            "status": data["status"]["state"],
        }

        extra: dict[str, Any] = {}
        schema = self._registry.get(schema_id)
        for col_def in (schema.extra_columns or []):
            keys = col_def["json_path"].split(".")
            val: Any = data
            try:
                for k in keys:
                    val = val[k] if isinstance(val, dict) else None
            except (KeyError, TypeError):
                val = None
            extra[col_def["column"]] = str(val) if val is not None else col_def.get("default", "")

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

        # files (extra columns from schema.file_fields)
        if "files" in tnames:
            items = data.get("task", {}).get("files_to_modify", [])
            if items:
                file_fields = schema.file_fields or []
                columns = ["task_id", "path", "change_type"] + [f["column"] for f in file_fields]
                col_list = ", ".join(columns)
                ph_list = ", ".join(f":{c}" for c in columns)
                self._engine.execute_many(
                    f"INSERT INTO {tnames['files']} ({col_list}) VALUES ({ph_list})",
                    [
                        {
                            "task_id": task_id,
                            "path": f.get("path", ""),
                            "change_type": f.get("change_type", ""),
                            **{fd["column"]: f.get(fd["column"], fd.get("default", "")) for fd in file_fields}
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

    def update_task_field(self, schema_id: str, task_id: str, field: str, value: str) -> bool:
        main_table = self._main_table(schema_id)
        existing = self._engine.fetchone(
            f"SELECT id FROM {main_table} WHERE id = ?", (task_id,)
        )
        if existing is None:
            return False
        self._engine.execute(
            f"UPDATE {main_table} SET {field} = ?, updated_at = datetime('now') WHERE id = ?",
            (value, task_id),
        )
        self._commit()
        return True

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

        try:
            return self._engine.fetchall(
                f"SELECT * FROM {main_table}{where} ORDER BY sequence ASC", params
            )
        except Exception:
            return self._engine.fetchall(f"SELECT * FROM {main_table}{where}", params)

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

    # ── document CRUD ──────────────────────────────────────────────────────────

    def insert_document(self, data: dict) -> str:
        from datetime import datetime

        doc_id = data["doc_id"]
        phase = data.get("metadata", {}).get("phase", 0)
        now = datetime.now().isoformat()
        self._engine.execute(
            """INSERT OR REPLACE INTO tasks_document
               (id, file_path, title, content, phase, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM tasks_document WHERE id = ?), ?), ?)""",
            (doc_id, data["file_path"], data["title"], data["content"],
             phase, data.get("status", {}).get("state", "pending"), doc_id, now, now),
        )
        self._commit()
        return doc_id

    def get_document(self, doc_id: str) -> Optional[dict]:
        row = self._engine.fetchone("SELECT * FROM tasks_document WHERE id = ?", (doc_id,))
        if row is None:
            return None
        return dict(row)

    def list_documents(self) -> list[dict]:
        rows = self._engine.fetchall("SELECT * FROM tasks_document ORDER BY id")
        return [dict(r) for r in rows]

    def list_documents_filtered(
        self,
        status_filter: Optional[str] = None,
        phase_filter: Optional[int] = None,
    ) -> list[dict]:
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
        return self._engine.fetchall(f"SELECT * FROM tasks_document{where} ORDER BY id", params)

    def update_document_status(self, doc_id: str, new_state: str) -> bool:
        existing = self._engine.fetchone(
            "SELECT id FROM tasks_document WHERE id = ?", (doc_id,)
        )
        if existing is None:
            return False
        self._engine.execute(
            "UPDATE tasks_document SET status = :status, updated_at = datetime('now') WHERE id = :id",
            {"status": new_state, "id": doc_id},
        )
        self._commit()
        return True

    def delete_document(self, doc_id: str) -> bool:
        existing = self._engine.fetchone(
            "SELECT id FROM tasks_document WHERE id = ?", (doc_id,)
        )
        if existing is None:
            return False
        self._engine.execute(
            "DELETE FROM tasks_document WHERE id = ?", (doc_id,)
        )
        self._commit()
        return True

    def update_document(self, doc_id: str, data: dict) -> bool:
        existing = self._engine.fetchone(
            "SELECT id FROM tasks_document WHERE id = ?", (doc_id,)
        )
        if existing is None:
            return False
        phase = data.get("metadata", {}).get("phase", 0)
        self._engine.execute(
            """UPDATE tasks_document SET
               file_path = :file_path, title = :title, content = :content,
               phase = :phase, status = :status, updated_at = datetime('now')
               WHERE id = :id""",
            {
                "file_path": data.get("file_path", ""),
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "phase": phase,
                "status": data.get("status", {}).get("state", "pending"),
                "id": doc_id,
            },
        )
        self._commit()
        return True
