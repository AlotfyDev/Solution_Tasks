from __future__ import annotations

import json
from pathlib import Path

import pytest

from task_cli.data.engine import DatabaseEngine
from task_cli.data.store import TaskStore
from task_cli.history.tracker import HistoryTracker
from task_cli.presentation.commands import AppContext, register_default_relationships
from task_cli.registry import RelationshipRegistry, SchemaRegistry
from task_cli.schemas.implementation import register_implementation_schema
from task_cli.schemas.testing import register_testing_schema
from task_cli.validation.validator import TaskValidator


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
def engine(schema_registry, tmp_path):
    eng = DatabaseEngine(tmp_path, schema_registry)
    eng.connect()
    yield eng
    eng.close()


@pytest.fixture
def store(engine, schema_registry):
    return TaskStore(engine, schema_registry)


@pytest.fixture
def history(engine):
    return HistoryTracker(engine)


@pytest.fixture
def app_context(tmp_path):
    ctx = AppContext()
    ctx.initialize(db_dir=tmp_path)
    yield ctx


@pytest.fixture
def report(engine, store, history, schema_registry):
    from task_cli.presentation.report import ReportGenerator
    return ReportGenerator(engine, store, history, schema_registry)


@pytest.fixture
def validator(schema_registry):
    return TaskValidator(schema_registry)


@pytest.fixture
def impl_task_data():
    return {
        "sub_task_id": "AA100-1",
        "sequence": 1,
        "hierarchy_level": 1,
        "source": {
            "file": "spec.md",
            "relative_path": ".",
            "lines": [1, 10],
            "section_title": "Section 1",
            "section_markdown": "# Section 1\nContent",
        },
        "metadata": {
            "phase": 1,
            "effort": "M",
            "dependencies": [],
            "parent_aa": "AA100",
            "parent_title": "Parent",
            "tags": ["backend", "core"],
        },
        "task": {
            "title": "Implement feature X",
            "description": "Implement feature X in the core module",
            "implementation_notes": "Use existing patterns",
            "acceptance_criteria": [
                {"id": "AA100-C1", "description": "Feature X works", "verified_by": "code_review"},
                {"id": "AA100-C2", "description": "No regressions", "verified_by": "ci"},
            ],
            "files_to_modify": [
                {"path": "src/core.cpp", "change_type": "modify", "description": "Add feature X"},
                {"path": "include/core.h", "change_type": "modify", "description": "Update header"},
            ],
        },
        "traceability": {},
        "status": {"state": "pending"},
    }


@pytest.fixture
def test_task_data():
    return {
        "sub_task_id": "TD-AA100-1",
        "sequence": 1,
        "hierarchy_level": 1,
        "source": {
            "file": "test_spec.md",
            "relative_path": ".",
            "lines": [1, 15],
            "section_title": "Test Section",
            "section_markdown": "# Test Section\nContent",
        },
        "metadata": {
            "phase": 1,
            "test_level": "unit",
            "parent_aa": "AA100",
            "parent_td": "TD1",
            "aa_dependencies": [],
            "tags": ["unit_test"],
        },
        "task": {
            "title": "Test feature X",
            "description": "Write unit tests for feature X",
            "implementation_notes": "Use gtest",
            "scenarios": [
                {"id": "S1", "name": "Happy path", "type": "positive"},
                {"id": "S2", "name": "Null input", "type": "negative"},
            ],
            "files_to_modify": [
                {
                    "path": "tests/core_test.cpp",
                    "change_type": "create",
                    "framework": "gtest",
                    "test_cases": [
                        {"name": "FeatureXWorks", "fixture": "FeatureXTest", "status": "template"},
                        {"name": "FeatureXNullInput", "fixture": "FeatureXTest", "status": "template"},
                    ],
                }
            ],
            "acceptance_criteria": [
                {"id": "TC-1", "description": "Tests compile and pass", "verified_by": "ci"},
            ],
        },
        "traceability": {
            "aa_reference": "AA100",
            "td_reference": "TD1",
        },
        "status": {"state": "pending"},
    }


@pytest.fixture
def impl_json_file(tmp_path, impl_task_data):
    path = tmp_path / "impl_task.json"
    path.write_text(json.dumps(impl_task_data))
    return path


@pytest.fixture
def test_json_file(tmp_path, test_task_data):
    path = tmp_path / "test_task.json"
    path.write_text(json.dumps(test_task_data))
    return path
