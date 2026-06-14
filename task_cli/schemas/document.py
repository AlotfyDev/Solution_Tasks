from pathlib import Path
from ..registry.base import TaskSchema

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "default_schemas"


def register_document_schema(reg):
    reg.register(TaskSchema(
        schema_id="document",
        version="1.0",
        title="Document Schema",
        description="One row per markdown specification file, stores full content.",
        json_schema_path=SCHEMA_DIR / "document-schema.json",
        table_names={"main": "tasks_document"},
        ddl_statements=[_ddl()],
        extra_columns=[],
        id_prefix="",
        task_id_pattern=r"^[A-Z][A-Z0-9._-]+$",
    ))


def _ddl():
    return """CREATE TABLE IF NOT EXISTS tasks_document (
        id TEXT PRIMARY KEY,
        file_path TEXT,
        title TEXT,
        content TEXT,
        phase INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT
    );"""
