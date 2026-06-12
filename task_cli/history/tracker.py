from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from task_cli.data.engine import DatabaseEngine


class HistoryTracker:
    """
    Records and queries task change history.
    Writes to the shared 'task_history' table.
    """

    def __init__(self, engine: DatabaseEngine):
        self._engine = engine

    def record_change(self, task_id: str, schema_id: str, field_name: str,
                      old_value: Optional[str], new_value: Optional[str],
                      changed_by: str = "cli") -> None:
        self._engine.execute(
            "INSERT INTO task_history (task_id, schema_id, changed_at, field_name, old_value, new_value, changed_by) "
            "VALUES (:task_id, :schema_id, :changed_at, :field_name, :old_value, :new_value, :changed_by)",
            {
                "task_id": task_id,
                "schema_id": schema_id,
                "changed_at": datetime.now().isoformat(),
                "field_name": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
            },
        )

    def record_status_change(self, task_id: str, schema_id: str,
                             old_status: str, new_status: str,
                             changed_by: str = "cli") -> None:
        self.record_change(
            task_id, schema_id,
            field_name="status",
            old_value=old_status,
            new_value=new_status,
            changed_by=changed_by,
        )

    def record_creation(self, task_id: str, schema_id: str,
                        changed_by: str = "cli") -> None:
        self.record_change(
            task_id, schema_id,
            field_name="__created__",
            old_value=None,
            new_value="created",
            changed_by=changed_by,
        )

    def get_history(self, task_id: str, schema_id: Optional[str] = None,
                    limit: int = 50) -> list[dict]:
        sql = (
            "SELECT id, task_id, schema_id, changed_at, field_name, old_value, new_value, changed_by "
            "FROM task_history "
            "WHERE task_id = :task_id"
        )
        params: dict[str, Any] = {"task_id": task_id}
        if schema_id is not None:
            sql += " AND schema_id = :schema_id"
            params["schema_id"] = schema_id
        sql += " ORDER BY id DESC LIMIT :limit"
        params["limit"] = limit
        return self._engine.fetchall(sql, params)

    def get_history_for_field(self, task_id: str, field_name: str,
                              schema_id: Optional[str] = None) -> list[dict]:
        sql = (
            "SELECT id, task_id, schema_id, changed_at, field_name, old_value, new_value, changed_by "
            "FROM task_history "
            "WHERE task_id = :task_id AND field_name = :field_name"
        )
        params: dict[str, Any] = {"task_id": task_id, "field_name": field_name}
        if schema_id is not None:
            sql += " AND schema_id = :schema_id"
            params["schema_id"] = schema_id
        sql += " ORDER BY id DESC"
        return self._engine.fetchall(sql, params)

    def get_recent_changes(self, limit: int = 20,
                           schema_id: Optional[str] = None) -> list[dict]:
        sql = (
            "SELECT id, task_id, schema_id, changed_at, field_name, old_value, new_value, changed_by "
            "FROM task_history"
        )
        params: dict[str, Any] = {}
        if schema_id is not None:
            sql += " WHERE schema_id = :schema_id"
            params["schema_id"] = schema_id
        sql += " ORDER BY id DESC LIMIT :limit"
        params["limit"] = limit
        return self._engine.fetchall(sql, params)
