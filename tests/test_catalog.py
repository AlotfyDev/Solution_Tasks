from __future__ import annotations

import json

import pytest
from task_cli.presentation.catalog import ToolCatalog
from task_cli.presentation.commands import (
    AppContext,
    build_parser,
    cmd_catalog,
    register_default_relationships,
)
from task_cli.registry import RelationshipRegistry, SchemaRegistry
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema


@pytest.fixture
def schema_registry():
    registry = SchemaRegistry()
    register_implementation_schema(registry)
    register_testing_schema(registry)
    return registry


@pytest.fixture
def rel_registry():
    registry = RelationshipRegistry()
    register_default_relationships(registry)
    return registry


@pytest.fixture
def catalog(schema_registry, rel_registry):
    return ToolCatalog(schema_registry, rel_registry)


class TestToolCatalog:
    def test_get_catalog_markdown_returns_string(self, catalog):
        result = catalog.get_catalog_markdown()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_markdown_has_overview_section(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## Overview" in result

    def test_markdown_has_cli_commands(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## CLI Commands" in result

    def test_markdown_has_mcp_tools(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## MCP Tools" in result

    def test_markdown_has_registered_schemas(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## Registered Schemas" in result

    def test_markdown_has_relationships(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## Registered Relationships" in result

    def test_markdown_has_mcp_resources(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## MCP Resources" in result

    def test_markdown_has_connection_guides(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## Connection Guides" in result

    def test_markdown_has_quick_start(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "## Quick Start" in result

    def test_markdown_lists_dynamic_schemas(self, catalog):
        result = catalog.get_catalog_markdown()
        assert "implementation" in result
        assert "testing" in result

    def test_markdown_lists_all_cli_commands(self, catalog):
        result = catalog.get_catalog_markdown()
        for cmd in ToolCatalog.CLI_COMMANDS:
            assert cmd["name"] in result

    def test_markdown_lists_all_mcp_tools(self, catalog):
        result = catalog.get_catalog_markdown()
        for t in ToolCatalog.MCP_TOOLS:
            assert t["name"] in result

    def test_get_catalog_json_returns_dict(self, catalog):
        result = catalog.get_catalog_json()
        assert isinstance(result, dict)

    def test_json_has_expected_keys(self, catalog):
        result = catalog.get_catalog_json()
        keys = {"system", "description", "schemas", "relationships", "cli_commands", "mcp_tools", "mcp_resources"}
        assert keys.issubset(result.keys())

    def test_json_lists_schemas(self, catalog):
        result = catalog.get_catalog_json()
        schema_ids = [s["id"] for s in result["schemas"]]
        assert "implementation" in schema_ids
        assert "testing" in schema_ids

    def test_json_lists_relationships(self, catalog):
        result = catalog.get_catalog_json()
        rel_names = [r["name"] for r in result["relationships"]]
        assert "tests" in rel_names
        assert "depends_on" in rel_names
        assert "implements" in rel_names
        assert "verifies" in rel_names

    def test_json_lists_cli_commands(self, catalog):
        result = catalog.get_catalog_json()
        cmd_names = [c["name"] for c in result["cli_commands"]]
        assert "catalog" in cmd_names
        assert "load-docs" in cmd_names
        assert "list-documents" in cmd_names
        assert len(cmd_names) == 22

    def test_json_lists_mcp_tools(self, catalog):
        result = catalog.get_catalog_json()
        tool_names = [t["name"] for t in result["mcp_tools"]]
        assert "get_catalog" in tool_names
        assert "insert_document" in tool_names
        assert "get_document" in tool_names
        assert "list_documents" in tool_names
        assert len(tool_names) == 24

    def test_json_lists_mcp_resources(self, catalog):
        result = catalog.get_catalog_json()
        uris = [r["uri"] for r in result["mcp_resources"]]
        assert "catalog://overview" in uris
        assert "doc://{doc_id}" in uris
        assert len(uris) == 5


class TestCmdCatalog:
    def test_catalog_markdown_default(self, capsys, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        args = build_parser().parse_args(["catalog"])
        cmd_catalog(args, ctx)
        captured = capsys.readouterr()
        assert "# Task Toolkit" in captured.out
        assert "## Overview" in captured.out
        assert "## CLI Commands" in captured.out
        assert "## MCP Tools" in captured.out

    def test_catalog_json_format(self, capsys, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        args = build_parser().parse_args(["catalog", "--format", "json"])
        cmd_catalog(args, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["system"] == "Task Toolkit"
        assert "schemas" in data
        assert "cli_commands" in data

    def test_catalog_cli_parser_accepts_format(self):
        parser = build_parser()
        args = parser.parse_args(["catalog", "--format", "json"])
        assert args.command == "catalog"
        assert args.format == "json"

    def test_catalog_cli_default_format(self):
        parser = build_parser()
        args = parser.parse_args(["catalog"])
        assert args.command == "catalog"
        assert args.format == "markdown"


class TestCatalogDbConfig:
    def test_markdown_includes_db_config(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
        md = catalog.get_catalog_markdown()
        assert "## Database Configuration" in md
        assert "`--db-dir`" in md
        assert "`TASK_DB_DIR`" in md
        assert "`.data/`" in md

    def test_json_includes_db_config(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
        js = catalog.get_catalog_json()
        assert "configuration" in js
        assert "database" in js["configuration"]
        assert js["configuration"]["database"]["filename"] == "tasks.db"

    def test_json_priority_chain(self, tmp_path):
        ctx = AppContext()
        ctx.initialize(db_dir=tmp_path)
        catalog = ToolCatalog(ctx.schema_registry, ctx.rel_registry)
        js = catalog.get_catalog_json()
        chain = js["configuration"]["database"]["priority_chain"]
        assert len(chain) == 3
        assert chain[0]["level"] == 1
        assert "--db-dir" in chain[0]["method"]
        assert chain[1]["level"] == 2
        assert "TASK_DB_DIR" in chain[1]["method"]
        assert chain[2]["level"] == 3
        assert "project default" in chain[2]["method"]
