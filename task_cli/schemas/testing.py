from __future__ import annotations

from pathlib import Path

from ..registry import SchemaRegistry, TaskSchema


def register_testing_schema(registry: SchemaRegistry) -> TaskSchema:
    schema = TaskSchema(
        schema_id="testing",
        version="1.0.0",
        title="TD Testing Task Schema",
        description="Sub-tasks derived from After_Audit markdown specifications",
        json_schema_path=Path(__file__).resolve().parent.parent.parent
        / "default_schemas"
        / "testing-schema.json",
        table_names={
            "main": "tasks_testing",
            "scenarios": "test_scenarios_testing",
            "files": "test_files_testing",
            "cases": "test_cases_testing",
        },
        ddl_statements=[
            """
CREATE TABLE IF NOT EXISTS tasks_testing (
    id TEXT PRIMARY KEY,
    parent_td_id TEXT,
    parent_aa_id TEXT,
    sequence INT,
    hierarchy_level INT,
    title TEXT,
    description TEXT,
    phase INT,
    test_level TEXT,
    impl_notes TEXT,
    status TEXT DEFAULT 'pending',
    source_file TEXT,
    source_lines TEXT,
    section_title TEXT,
    section_markdown TEXT,
    created_at TEXT,
    updated_at TEXT
)
""",
            """
CREATE TABLE IF NOT EXISTS test_scenarios_testing (
    id TEXT,
    task_id TEXT REFERENCES tasks_testing(id),
    name TEXT,
    type TEXT,
    PRIMARY KEY (id, task_id)
)
""",
            """
CREATE TABLE IF NOT EXISTS test_files_testing (
    task_id TEXT REFERENCES tasks_testing(id),
    path TEXT,
    change_type TEXT,
    framework TEXT DEFAULT 'gtest',
    PRIMARY KEY (task_id, path)
)
""",
            """
CREATE TABLE IF NOT EXISTS test_cases_testing (
    name TEXT,
    file_path TEXT,
    task_id TEXT,
    fixture TEXT,
    status TEXT DEFAULT 'template',
    PRIMARY KEY (name, file_path, task_id),
    FOREIGN KEY (task_id, file_path) REFERENCES test_files_testing(task_id, path)
)
""",
        ],
    )
    registry.register(schema)
    return schema
