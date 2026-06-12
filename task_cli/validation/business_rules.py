from __future__ import annotations

from typing import Any, Optional

from task_cli.data.engine import DatabaseEngine
from task_cli.registry import SchemaRegistry


class BusinessRuleValidator:
    def __init__(self, engine: Optional[DatabaseEngine], registry: SchemaRegistry):
        self._engine = engine
        self._registry = registry

    def validate(self, data: dict, schema_id: str) -> list[str]:
        errors: list[str] = []
        errors.extend(self._check_phase_order(data, schema_id))
        errors.extend(self._check_dependency_exists(data, schema_id))
        errors.extend(self._check_id_uniqueness(data, schema_id))
        return errors

    def _check_phase_order(self, data: dict, schema_id: str) -> list[str]:
        errors = []
        if self._engine is None:
            return errors
        phase = data.get("metadata", {}).get("phase", 0)
        if phase <= 0:
            return errors
        main_table = self._registry.get(schema_id).table_names["main"]
        for prev in range(0, phase):
            pending = self._engine.fetchone(
                f"SELECT COUNT(*) as cnt FROM {main_table} "
                f"WHERE phase = :phase AND status = 'pending' "
                f"AND id != :new_id",
                {"phase": prev, "new_id": data.get("sub_task_id", "")},
            )
            if pending and pending["cnt"] > 0:
                errors.append(
                    f"phase {phase} task but phase {prev} tasks are still pending"
                )
                break
        return errors

    def _check_dependency_exists(self, data: dict, schema_id: str) -> list[str]:
        errors = []
        if self._engine is None:
            return errors
        metadata = data.get("metadata", {})
        deps = metadata.get("dependencies", [])
        if not deps:
            return errors
        main_table = self._registry.get(schema_id).table_names["main"]
        for dep in deps:
            dep_id = dep.get("id", "") if isinstance(dep, dict) else dep
            exists = self._engine.fetchone(
                f"SELECT id FROM {main_table} WHERE id = ?", (dep_id,)
            )
            if exists is None:
                errors.append(f"dependency '{dep_id}' not found in DB")
        return errors

    def _check_id_uniqueness(self, data: dict, schema_id: str) -> list[str]:
        errors = []
        if self._engine is None:
            return errors
        task_id = data.get("sub_task_id", "")
        if not task_id:
            return errors
        main_table = self._registry.get(schema_id).table_names["main"]
        exists = self._engine.fetchone(
            f"SELECT id FROM {main_table} WHERE id = ?", (task_id,)
        )
        if exists is not None:
            errors.append(f"task '{task_id}' already exists in schema '{schema_id}'")
        return errors
