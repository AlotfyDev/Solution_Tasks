from __future__ import annotations

import pytest

from task_cli.validation.business_rules import BusinessRuleValidator
from task_cli.validation.validator import TaskValidator


@pytest.fixture
def db_validator(schema_registry, engine):
    return TaskValidator(schema_registry, engine=engine)


class TestBusinessRules:
    def test_phase_order_allows_same_phase(self, db_validator, store, impl_task_data):
        data_a = dict(impl_task_data)
        data_a["sub_task_id"] = "AA100-0"
        data_a["metadata"] = {**data_a["metadata"], "phase": 0}
        store.insert_task("implementation", data_a)

        data_b = dict(impl_task_data)
        data_b["sub_task_id"] = "AA200-0"
        data_b["metadata"] = {**data_b["metadata"], "phase": 0}

        errors = db_validator.validate(data_b, "implementation")
        assert errors == []

    def test_phase_order_blocks_skip(self, db_validator, store, impl_task_data):
        data_phase0 = dict(impl_task_data)
        data_phase0["sub_task_id"] = "AA100-0"
        data_phase0["metadata"] = {**data_phase0["metadata"], "phase": 0}
        store.insert_task("implementation", data_phase0)

        data_phase2 = dict(impl_task_data)
        data_phase2["sub_task_id"] = "AA200-2"
        data_phase2["metadata"] = {**data_phase2["metadata"], "phase": 2}

        errors = db_validator.validate(data_phase2, "implementation")
        assert any("phase" in e.lower() for e in errors)

    def test_dependency_exists(self, db_validator, store, impl_task_data):
        dep_data = dict(impl_task_data)
        dep_data["sub_task_id"] = "AA100-1"
        store.insert_task("implementation", dep_data)

        task_data = dict(impl_task_data)
        task_data["sub_task_id"] = "AA200-1"
        task_data["metadata"] = {
            **task_data["metadata"],
            "dependencies": [{"id": "AA100-1", "type": "hard"}],
        }

        errors = db_validator.validate(task_data, "implementation")
        assert errors == []

    def test_dependency_missing(self, db_validator, store, impl_task_data):
        task_data = dict(impl_task_data)
        task_data["sub_task_id"] = "AA200-1"
        task_data["metadata"] = {
            **task_data["metadata"],
            "dependencies": [{"id": "NONEXISTENT", "type": "hard"}],
        }

        errors = db_validator.validate(task_data, "implementation")
        assert any("NONEXISTENT" in e for e in errors)

    def test_id_uniqueness_duplicate(self, db_validator, store, impl_task_data):
        task_id = "AA100-1"
        data_a = dict(impl_task_data)
        data_a["sub_task_id"] = task_id
        store.insert_task("implementation", data_a)

        data_b = dict(impl_task_data)
        data_b["sub_task_id"] = task_id

        errors = db_validator.validate(data_b, "implementation")
        assert any(task_id in e for e in errors)

    def test_id_uniqueness_no_duplicate(self, db_validator, store, impl_task_data):
        data_a = dict(impl_task_data)
        data_a["sub_task_id"] = "AA100-1"
        store.insert_task("implementation", data_a)

        data_b = dict(impl_task_data)
        data_b["sub_task_id"] = "AA200-1"

        errors = db_validator.validate(data_b, "implementation")
        assert errors == []

    def test_no_engine_graceful_degradation(self, schema_registry):
        bv = BusinessRuleValidator(None, schema_registry)
        errors = bv.validate({"sub_task_id": "test"}, "implementation")
        assert errors == []
