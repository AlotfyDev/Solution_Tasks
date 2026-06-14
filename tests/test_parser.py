from spec_parser.loader import load_file, load_directory
from spec_parser.parser import parse, visit
from spec_parser.extractor import extract_document, extract_sub_tasks
import os

SAMPLE_PATH = os.path.join("tests", "testdata", "sample-spec.md")


class TestLoader:
    def test_load_file(self):
        result = load_file(SAMPLE_PATH)
        assert "path" in result
        assert "filename" in result
        assert "content" in result
        assert result["filename"] == "sample-spec.md"
        assert len(result["content"]) > 0

    def test_load_file_not_found(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_file("nonexistent.md")

    def test_load_directory(self):
        files = load_directory(os.path.dirname(SAMPLE_PATH), "*.md")
        assert len(files) >= 1
        assert any(f["filename"] == "sample-spec.md" for f in files)

    def test_load_empty_directory(self, tmp_path):
        files = load_directory(str(tmp_path), "*.md")
        assert files == []


class TestParser:
    def test_parse_returns_list(self):
        content = "# Hello\n\nWorld."
        tokens = parse(content)
        assert isinstance(tokens, list)

    def test_parse_heading_detection(self):
        content = "# H1\n## H2\n### H3"
        tokens = parse(content)
        headings = [t for t in tokens if t["type"] == "heading"]
        assert len(headings) == 3
        assert headings[0]["attrs"]["level"] == 1
        assert headings[1]["attrs"]["level"] == 2
        assert headings[2]["attrs"]["level"] == 3

    def test_parse_task_list_items(self):
        content = "- [ ] unchecked\n- [x] checked"
        tokens = parse(content)
        lists = [t for t in tokens if t["type"] == "list"]
        assert len(lists) >= 1

    def test_parse_code_block(self):
        content = "```python\nprint('hello')\n```"
        tokens = parse(content)
        code = [t for t in tokens if t["type"] == "block_code"]
        assert len(code) >= 1
        assert "python" in code[0].get("attrs", {}).get("info", "")


class TestVisit:
    def test_visit_sections(self):
        content = "# Title\n\nPara.\n## Step 1\n\nDetail."
        tokens = parse(content)
        result = visit(tokens)
        assert len(result["sections"]) >= 2

    def test_visit_acceptance_criteria(self):
        with open(SAMPLE_PATH) as f:
            content = f.read()
        tokens = parse(content)
        result = visit(tokens)
        assert len(result["acceptance_criteria"]) == 3

    def test_visit_no_content(self):
        result = visit([])
        assert result["sections"] == []
        assert result["acceptance_criteria"] == []


class TestExtractor:
    def test_extract_document(self):
        import codecs
        with codecs.open(SAMPLE_PATH, "r", encoding="utf-8-sig") as f:
            content = f.read()
        tokens = parse(content)
        parsed = visit(tokens)
        doc = extract_document(parsed, SAMPLE_PATH)
        assert "doc_id" in doc
        assert "file_path" in doc
        assert "title" in doc
        assert "content" in doc
        assert doc["content"] == content

    def test_extract_sub_tasks_count(self):
        with open(SAMPLE_PATH) as f:
            content = f.read()
        tokens = parse(content)
        parsed = visit(tokens)
        doc = extract_document(parsed, SAMPLE_PATH)
        subs = extract_sub_tasks(parsed, doc["doc_id"])
        assert len(subs) == 2

    def test_extract_sub_tasks_structure(self):
        with open(SAMPLE_PATH) as f:
            content = f.read()
        tokens = parse(content)
        parsed = visit(tokens)
        doc = extract_document(parsed, SAMPLE_PATH)
        subs = extract_sub_tasks(parsed, doc["doc_id"])
        sub = subs[0]
        assert "sub_task_id" in sub
        assert "parent_doc_id" in sub
        assert sub["parent_doc_id"] == doc["doc_id"]
        assert "task" in sub
        assert "acceptance_criteria" in sub["task"]

    def test_extract_sub_tasks_returns_list(self):
        tokens = parse("# Header\n\n## Section One\n\nDesc")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-TEST", "/path/file.md")
        assert isinstance(result, list)

    def test_extract_sub_tasks_derived_task_ids(self):
        tokens = parse("# Doc\n\n## First Step\n\n## Second Step\n\n## Third Step")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-M06", "")
        assert len(result) == 3
        assert result[0]["sub_task_id"] == "AA-M06-01"
        assert result[1]["sub_task_id"] == "AA-M06-02"
        assert result[2]["sub_task_id"] == "AA-M06-03"

    def test_extract_sub_tasks_skips_h1_sections(self):
        tokens = parse("# Main Title\n\nParagraph under H1\n\n## Real Section\n\nDesc")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-TEST", "")
        assert len(result) == 1
        assert result[0]["sub_task_id"] == "AA-TEST-01"

    def test_extract_sub_tasks_source_has_required_fields(self):
        tokens = parse("# Doc\n\n## Section One\n\nDescription")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-M05", "/path/AA-M05-RateLimiting.md")
        assert result[0]["parent_doc_id"] == "AA-M05"
        assert result[0]["task"]["title"] == "Section One"
        assert result[0]["task"]["description"] == "Description"

    def test_extract_sub_tasks_task_has_files_to_modify(self):
        tokens = parse("# Doc\n\n## Section\n\nDesc")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-TEST", "")
        assert "files_to_modify" in result[0]["task"]

    def test_extract_sub_tasks_metadata_has_parent_aa(self):
        tokens = parse("# Doc\n\n## Section\n\nDesc")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-C05", "")
        assert result[0]["metadata"]["parent_aa"] == "AA-C05"
        assert result[0]["metadata"]["parent_title"] == "Doc"

    def test_extract_sub_tasks_traceability_structure(self):
        tokens = parse("# Doc\n\n## Section\n\nDesc")
        parsed = visit(tokens)
        result = extract_sub_tasks(parsed, "AA-TEST", "")
        assert "aa_reference" in result[0]["traceability"]


class TestIntegration:
    def test_full_pipeline(self):
        loaded = load_file(SAMPLE_PATH)
        tokens = parse(loaded["content"])
        parsed = visit(tokens)
        doc = extract_document(parsed, SAMPLE_PATH)
        tasks = extract_sub_tasks(parsed, doc["doc_id"], SAMPLE_PATH)

        assert doc["doc_id"] == "sample-spec"
        assert len(tasks) == 2
        assert all(t["metadata"]["parent_aa"] == "sample-spec" for t in tasks)
