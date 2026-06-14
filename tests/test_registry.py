from __future__ import annotations

import json

import pytest
from task_cli.registry import RelationshipRegistry, RelationshipType, SchemaRegistry, TaskSchema


class TestTaskSchema:
    def test_create_with_all_fields(self):
        schema = TaskSchema(
            schema_id="custom",
            version="2.0.0",
            title="Custom Schema",
            description="A custom schema",
            json_schema_path=None,
            table_names={"main": "tasks_custom"},
            ddl_statements=["CREATE TABLE tasks_custom (id TEXT PRIMARY KEY)"],
        )
        assert schema.schema_id == "custom"
        assert schema.version == "2.0.0"
        assert schema.title == "Custom Schema"
        assert schema.table_names == {"main": "tasks_custom"}
        assert schema.ddl_statements == ["CREATE TABLE tasks_custom (id TEXT PRIMARY KEY)"]

    def test_json_schema_loads_from_file(self, tmp_path):
        schema_content = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_content))

        schema = TaskSchema(
            schema_id="test",
            version="1.0.0",
            title="Test",
            description="Test",
            json_schema_path=schema_file,
        )
        loaded = schema.json_schema()
        assert loaded == schema_content

    def test_json_schema_caches(self, tmp_path):
        import os
        schema_content = {"type": "object"}
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_content))

        schema = TaskSchema(
            schema_id="test",
            version="1.0.0",
            title="Test",
            description="Test",
            json_schema_path=schema_file,
        )
        first = schema.json_schema()
        # Call again without modifying: should return the cached dict (same object reference)
        second = schema.json_schema()
        assert second is first

        # Modify file on disk and update mtime to verify reloading
        schema_file.write_text(json.dumps({"type": "array"}))
        mtime = schema_file.stat().st_mtime
        os.utime(schema_file, (mtime + 2, mtime + 2))

        third = schema.json_schema()
        assert third == {"type": "array"}
        assert third is not first

    def test_json_schema_returns_empty_when_no_path(self):
        schema = TaskSchema(
            schema_id="test", version="1.0.0", title="Test", description="Test"
        )
        assert schema.json_schema() == {}

    def test_validate_valid_instance(self, tmp_path):
        schema_content = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_content))

        schema = TaskSchema(
            schema_id="test",
            version="1.0.0",
            title="Test",
            description="Test",
            json_schema_path=schema_file,
        )
        errors = schema.validate({"name": "hello"})
        assert errors == []

    def test_validate_invalid_instance(self, tmp_path):
        schema_content = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_content))

        schema = TaskSchema(
            schema_id="test",
            version="1.0.0",
            title="Test",
            description="Test",
            json_schema_path=schema_file,
        )
        errors = schema.validate({})
        assert any("name" in err for err in errors)

    def test_validate_no_schema_loaded(self):
        schema = TaskSchema(
            schema_id="test", version="1.0.0", title="Test", description="Test"
        )
        errors = schema.validate({"name": "hello"})
        assert errors == ["No JSON Schema loaded"]

    def test_validate_enum_failure(self, tmp_path):
        schema_content = {
            "type": "object",
            "properties": {"color": {"type": "string", "enum": ["red", "blue"]}},
        }
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_content))

        schema = TaskSchema(
            schema_id="test",
            version="1.0.0",
            title="Test",
            description="Test",
            json_schema_path=schema_file,
        )
        errors = schema.validate({"color": "green"})
        assert any("green" in err for err in errors)


class TestSchemaRegistry:
    def test_register_and_get(self, schema_registry):
        schema = schema_registry.get("implementation")
        assert schema.schema_id == "implementation"
        assert schema.version == "1.0.0"

    def test_register_duplicate_raises(self, schema_registry):
        dup = TaskSchema(
            schema_id="implementation",
            version="1.0.0",
            title="Dup",
            description="Dup",
        )
        with pytest.raises(ValueError, match="already registered"):
            schema_registry.register(dup)

    def test_get_missing_raises(self, schema_registry):
        with pytest.raises(KeyError, match="not found"):
            schema_registry.get("nonexistent")

    def test_list_ids(self, schema_registry):
        ids = schema_registry.list_ids()
        assert "implementation" in ids
        assert "testing" in ids
        assert "document" in ids
        assert len(ids) == 3

    def test_list(self, schema_registry):
        schemas = schema_registry.list()
        assert len(schemas) == 3
        assert all(isinstance(s, TaskSchema) for s in schemas)

    def test_register_custom_schema(self):
        registry = SchemaRegistry()
        s = TaskSchema(
            schema_id="custom",
            version="1.0.0",
            title="Custom",
            description="Custom schema",
        )
        registry.register(s)
        assert registry.get("custom") is s


class TestRelationshipType:
    def test_create_with_defaults(self):
        rel = RelationshipType(
            name="tests",
            source_schema_id="testing",
            target_schema_id="implementation",
            description="TD tests verify AA",
        )
        assert rel.name == "tests"
        assert rel.source_schema_id == "testing"
        assert rel.target_schema_id == "implementation"
        assert rel.cardinality == "many_to_many"
        assert not rel.bidirectional
        assert rel.inverse_name is None

    def test_create_with_all_fields(self):
        rel = RelationshipType(
            name="custom",
            source_schema_id="a",
            target_schema_id="b",
            description="Custom",
            cardinality="one_to_one",
            bidirectional=True,
            inverse_name="inverse_custom",
        )
        assert rel.cardinality == "one_to_one"
        assert rel.bidirectional
        assert rel.inverse_name == "inverse_custom"


class TestRelationshipRegistry:
    def test_register_and_get(self, rel_registry):
        rel = rel_registry.get("tests")
        assert rel.name == "tests"
        assert rel.source_schema_id == "testing"

    def test_register_duplicate_raises(self, rel_registry):
        dup = RelationshipType(
            name="tests",
            source_schema_id="a",
            target_schema_id="b",
            description="dup",
        )
        with pytest.raises(ValueError, match="already registered"):
            rel_registry.register(dup)

    def test_get_missing_raises(self, rel_registry):
        with pytest.raises(KeyError, match="not found"):
            rel_registry.get("nonexistent")

    def test_list(self, rel_registry):
        rels = rel_registry.list()
        names = {r.name for r in rels}
        assert "tests" in names
        assert "depends_on" in names
        assert "implements" in names
        assert "verifies" in names

    def test_for_schema(self, rel_registry):
        testing_rels = rel_registry.for_schema("testing")
        assert any(r.name == "tests" for r in testing_rels)
        assert any(r.name == "verifies" for r in testing_rels)

        impl_rels = rel_registry.for_schema("implementation")
        assert any(r.name == "depends_on" for r in impl_rels)
        assert any(r.name == "implements" for r in impl_rels)

    def test_for_schema_no_matches(self):
        registry = RelationshipRegistry()
        assert registry.for_schema("unknown") == []
