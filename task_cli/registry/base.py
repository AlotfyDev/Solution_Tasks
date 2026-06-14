from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TaskSchema:
    """A registered task schema defining structure, validation rules, and DB mapping."""

    schema_id: str
    version: str
    title: str
    description: str

    # Path to the JSON Schema file used for validation
    json_schema_path: Optional[Path] = None
    _json_schema: Optional[dict] = None
    _json_schema_mtime: Optional[float] = None

    # Table configuration: maps logical groups to SQL table names (per-schema suffix)
    # e.g. {"main": "tasks_implementation", "criteria": "acceptance_criteria_implementation"}
    table_names: dict[str, str] = field(default_factory=dict)

    # DDL statements for creating this schema's tables
    ddl_statements: list[str] = field(default_factory=list)

    # Extra columns for the main table: [{"column": "effort", "json_path": "metadata.effort", "default": ""}]
    extra_columns: list[dict] = None

    # Extra columns for files table (beyond task_id, path, change_type)
    file_fields: list[dict] = None

    # Prefix used to detect schema from task IDs (e.g. "AA-" or "TD-")
    id_prefix: str = ""

    # Regex pattern for validating task IDs
    task_id_pattern: str = ""

    def json_schema(self) -> dict:
        if self.json_schema_path is not None:
            current_mtime = self.json_schema_path.stat().st_mtime
            if self._json_schema_mtime is None or current_mtime != self._json_schema_mtime:
                with open(self.json_schema_path, "r", encoding="utf-8") as f:
                    self._json_schema = json.load(f)
                self._json_schema_mtime = current_mtime
        return self._json_schema or {}

    def validate(self, instance: dict) -> list[str]:
        """Validate a data dict against this schema's JSON Schema. Returns list of errors."""
        import jsonschema
        schema = self.json_schema()
        if not schema:
            return ["No JSON Schema loaded"]

        errors: list[str] = []
        validator = jsonschema.Draft7Validator(schema)
        for err in validator.iter_errors(instance):
            path = " → ".join(str(p) for p in err.absolute_path) if err.absolute_path else "root"
            errors.append(f"{path}: {err.message}")
        return errors


@dataclass
class RelationshipType:
    """A registered relationship type between two schemas."""

    name: str
    source_schema_id: str
    target_schema_id: str
    description: str
    cardinality: str = "many_to_many"  # "one_to_one", "one_to_many", "many_to_many"
    bidirectional: bool = False

    # If True, also creates the inverse relationship automatically
    inverse_name: Optional[str] = None


class SchemaRegistry:
    """Registry of all known task schemas. Extensible at runtime."""

    def __init__(self):
        self._schemas: dict[str, TaskSchema] = {}

    def register(self, schema: TaskSchema) -> None:
        if schema.schema_id in self._schemas:
            raise ValueError(f"Schema '{schema.schema_id}' is already registered")
        self._schemas[schema.schema_id] = schema

    def get(self, schema_id: str) -> TaskSchema:
        if schema_id not in self._schemas:
            raise KeyError(f"Schema '{schema_id}' not found. Registered: {list(self._schemas)}")
        return self._schemas[schema_id]

    def list_ids(self) -> list[str]:
        return list(self._schemas)

    def list(self) -> list[TaskSchema]:
        return list(self._schemas.values())


class RelationshipRegistry:
    """Registry of relationship types between schemas."""

    def __init__(self):
        self._relationships: dict[str, RelationshipType] = {}

    def register(self, rel: RelationshipType) -> None:
        if rel.name in self._relationships:
            raise ValueError(f"Relationship '{rel.name}' is already registered")
        self._relationships[rel.name] = rel

    def get(self, name: str) -> RelationshipType:
        if name not in self._relationships:
            raise KeyError(f"Relationship '{name}' not found")
        return self._relationships[name]

    def list(self) -> list[RelationshipType]:
        return list(self._relationships.values())

    def for_schema(self, schema_id: str) -> list[RelationshipType]:
        return [r for r in self._relationships.values()
                if r.source_schema_id == schema_id or r.target_schema_id == schema_id]
