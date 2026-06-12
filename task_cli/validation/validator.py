from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from task_cli.registry import SchemaRegistry


class TaskValidator:
    """Validates task JSON instances against registered schemas."""

    def __init__(self, registry: SchemaRegistry):
        self._registry = registry

    def validate(self, instance: dict, schema_id: str) -> list[str]:
        """
        Validate a dict instance against a registered schema.
        Returns empty list if valid, list of error messages if invalid.
        Uses the TaskSchema.validate() method internally.
        Raises KeyError if schema_id not registered.
        """
        schema = self._registry.get(schema_id)
        return schema.validate(instance)

    def validate_file(self, file_path: Path, schema_id: Optional[str] = None) -> list[str]:
        """
        Read a JSON file and validate it.
        If schema_id is None, try to auto-detect from the JSON content:
          - If "sub_task_id" starts with "TD-": use "testing" schema
          - Otherwise: use "implementation" schema
        Returns list of errors. Raises FileNotFoundError if file missing,
        json.JSONDecodeError if invalid JSON.
        """
        content = file_path.read_text(encoding="utf-8")
        instance = json.loads(content)

        if schema_id is None:
            sub_task_id = instance.get("sub_task_id", "")
            schema_id = "testing" if sub_task_id.startswith("TD-") else "implementation"

        return self.validate(instance, schema_id)

    def validate_all_in_dir(self, dir_path: Path, schema_id: Optional[str] = None) -> dict[str, list[str]]:
        """
        Validate all JSON files in a directory.
        Returns dict mapping file_path -> list_of_errors.
        Skips non-JSON files.
        """
        results: dict[str, list[str]] = {}
        for child in sorted(dir_path.iterdir()):
            if child.suffix.lower() != ".json":
                continue
            try:
                errors = self.validate_file(child, schema_id)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                errors = [str(exc)]
            except KeyError as exc:
                errors = [f"Schema not found: {exc}"]
            results[str(child)] = errors
        return results
