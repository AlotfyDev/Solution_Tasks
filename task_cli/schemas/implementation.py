from __future__ import annotations

from pathlib import Path

from ..registry import SchemaRegistry, TaskSchema


def register_implementation_schema(registry: SchemaRegistry) -> TaskSchema:
    schema = TaskSchema(
        schema_id="implementation",
        version="1.0.0",
        title="AA Implementation Task Schema",
        description="Sub-tasks derived from After_Audit markdown specifications",
        json_schema_path=Path(__file__).resolve().parent.parent.parent
        / "default_schemas"
        / "implementation-schema.json",
        table_names={
            "main": "tasks_implementation",
            "criteria": "acceptance_criteria_implementation",
            "files": "task_files_implementation",
            "tags": "tags_implementation",
        },
        id_prefix="AA-",
        task_id_pattern=r"^AA\d+-\d+$",
        ddl_statements=[
            """
CREATE TABLE IF NOT EXISTS tasks_implementation (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    parent_doc_id TEXT,
    sequence INT,
    hierarchy_level INT,
    title TEXT,
    description TEXT,
    phase INT,
    effort TEXT,
    impl_notes TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT
)
""",
            """
CREATE TABLE IF NOT EXISTS acceptance_criteria_implementation (
    id TEXT,
    task_id TEXT REFERENCES tasks_implementation(id),
    description TEXT,
    verified_by TEXT,
    PRIMARY KEY (id, task_id)
)
""",
            """
CREATE TABLE IF NOT EXISTS task_files_implementation (
    task_id TEXT REFERENCES tasks_implementation(id),
    path TEXT,
    change_type TEXT,
    description TEXT,
    PRIMARY KEY (task_id, path)
)
""",
            """
CREATE TABLE IF NOT EXISTS tags_implementation (
    task_id TEXT,
    tag TEXT,
    PRIMARY KEY (task_id, tag)
)
""",
        ],
extra_columns=[
             {"column": "effort", "json_path": "metadata.effort", "default": ""},
             {"column": "parent_doc_id", "json_path": "parent_doc_id", "default": ""},
         ],
        file_fields=[
            {"column": "description", "default": ""},
        ],
    )
    registry.register(schema)
    return schema
