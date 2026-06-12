from __future__ import annotations

import json

import pytest


class TestTaskValidator:
    def test_validate_valid_impl(self, validator, impl_task_data):
        errors = validator.validate(impl_task_data, "implementation")
        assert errors == []

    def test_validate_valid_test(self, validator, test_task_data):
        errors = validator.validate(test_task_data, "testing")
        assert errors == []

    def test_validate_invalid_instance(self, validator, impl_task_data):
        invalid = dict(impl_task_data)
        invalid["sub_task_id"] = 123
        errors = validator.validate(invalid, "implementation")
        assert len(errors) > 0

    def test_validate_missing_required_field(self, validator, impl_task_data):
        invalid = dict(impl_task_data)
        invalid.pop("task")
        errors = validator.validate(invalid, "implementation")
        assert len(errors) > 0
        assert any("task" in err for err in errors)

    def test_validate_missing_schema(self, validator, impl_task_data):
        with pytest.raises(KeyError):
            validator.validate(impl_task_data, "nonexistent")

    def test_validate_invalid_enum(self, validator, impl_task_data):
        invalid = dict(impl_task_data)
        invalid["status"] = {"state": "invalid_state"}
        errors = validator.validate(invalid, "implementation")
        assert len(errors) > 0

    def test_validate_file_valid_impl(self, validator, impl_json_file):
        errors = validator.validate_file(impl_json_file)
        assert errors == []

    def test_validate_file_valid_test(self, validator, test_json_file):
        errors = validator.validate_file(test_json_file)
        assert errors == []

    def test_validate_file_with_explicit_schema(self, validator, impl_json_file):
        errors = validator.validate_file(impl_json_file, schema_id="implementation")
        assert errors == []

    def test_validate_file_auto_detect_testing(self, validator, tmp_path):
        data = {
            "sub_task_id": "TD-AA200-1",
            "sequence": 1,
            "hierarchy_level": 1,
            "source": {"file": "t.md", "relative_path": ".", "lines": [1, 5], "section_title": "T"},
            "metadata": {"phase": 1, "test_level": "unit", "parent_aa": "AA200", "parent_td": "TD2"},
            "task": {
                "title": "Test", "description": "Test",
                "scenarios": [{"id": "S1", "name": "S1", "type": "positive"}],
                "files_to_modify": [{"path": "t.cpp", "change_type": "create", "test_cases": [{"name": "TC1"}]}],
                "acceptance_criteria": [{"id": "TC-1", "description": "d"}],
            },
            "traceability": {"aa_reference": "AA200", "td_reference": "TD2"},
            "status": {"state": "pending"},
        }
        f = tmp_path / "td_task.json"
        f.write_text(json.dumps(data))
        errors = validator.validate_file(f)
        assert errors == []

    def test_validate_file_auto_detect_impl(self, validator, impl_json_file):
        errors = validator.validate_file(impl_json_file)
        assert errors == []

    def test_validate_file_not_found(self, validator, tmp_path):
        missing = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError):
            validator.validate_file(missing)

    def test_validate_file_invalid_json(self, validator, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        with pytest.raises(json.JSONDecodeError):
            validator.validate_file(bad_file)

    def test_validate_all_in_dir(self, validator, tmp_path, impl_task_data, test_task_data):
        (tmp_path / "valid_impl.json").write_text(json.dumps(impl_task_data))
        (tmp_path / "valid_test.json").write_text(json.dumps(test_task_data))

        invalid = dict(impl_task_data)
        invalid.pop("task")
        (tmp_path / "invalid.json").write_text(json.dumps(invalid))

        (tmp_path / "readme.txt").write_text("hello")

        results = validator.validate_all_in_dir(tmp_path)

        valid_impl_key = str(tmp_path / "valid_impl.json")
        valid_test_key = str(tmp_path / "valid_test.json")
        invalid_key = str(tmp_path / "invalid.json")
        txt_key = str(tmp_path / "readme.txt")

        assert valid_impl_key in results
        assert valid_test_key in results
        assert invalid_key in results
        assert txt_key not in results

        assert results[valid_impl_key] == []
        assert results[valid_test_key] == []
        assert len(results[invalid_key]) > 0

    def test_validate_all_in_dir_invalid_json(self, validator, tmp_path):
        (tmp_path / "bad.json").write_text("{{{")
        results = validator.validate_all_in_dir(tmp_path)
        key = str(tmp_path / "bad.json")
        assert key in results
        assert len(results[key]) > 0

    def test_validate_all_in_dir_empty(self, validator, tmp_path):
        results = validator.validate_all_in_dir(tmp_path)
        assert results == {}

    def test_validate_all_in_dir_mixed_extensions(self, validator, tmp_path):
        (tmp_path / "task.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("hello")
        (tmp_path / "data.csv").write_text("a,b,c")
        results = validator.validate_all_in_dir(tmp_path)
        assert str(tmp_path / "task.json") in results
        assert str(tmp_path / "notes.txt") not in results
        assert str(tmp_path / "data.csv") not in results
