import os
import re


def extract_document(parsed: dict, filepath: str = "") -> dict:
    from .loader import load_file

    if filepath:
        f = load_file(filepath)
        doc_id = os.path.splitext(os.path.basename(filepath))[0]
        title = _extract_title(parsed, f["filename"])
        content = f["content"]
        file_path = f["path"]
    else:
        doc_id = _extract_title(parsed, "").replace(" ", "-")
        title = doc_id
        content = ""
        file_path = ""

    phase = _extract_phase(parsed)

    return {
        "doc_id": doc_id,
        "file_path": file_path,
        "title": title,
        "content": content,
        "status": {"state": "pending"},
        "metadata": {"phase": phase},
    }


def _extract_phase(parsed: dict) -> int:
    for section in parsed.get("sections", []):
        if section["level"] == 1:
            for p in section.get("paragraphs", []):
                m = re.search(r"Phase:\s*(\d+)", p, re.IGNORECASE)
                if m:
                    return int(m.group(1))
    return 0


def extract_sub_tasks(parsed: dict, doc_id: str, filepath: str = "", schema_id: str = "implementation") -> list[dict]:
    sub_tasks = []
    _phase = "0"
    _effort = ""
    _is_testing = schema_id == "testing"

    for section in parsed.get("sections", []):
        if section["level"] == 1:
            for p in section.get("paragraphs", []):
                m = re.search(r"Phase:\s*(\d+)", p, re.IGNORECASE)
                if m:
                    _phase = m.group(1)
                m = re.search(r"Effort:\s*([^\n]+)", p, re.IGNORECASE)
                if m:
                    _effort = m.group(1).strip()
            continue

        seq = len(sub_tasks) + 1
        tid = f"{doc_id}-{seq:02d}"

        if _is_testing:
            ac_list = [
                {"id": f"TC-{i+1}", "description": ac["text"]}
                for i, ac in enumerate(section.get("ac_items", []))
            ]
        else:
            ac_list = [
                {"id": f"{tid}-AC{i+1:02d}", "description": ac["text"]}
                for i, ac in enumerate(section.get("ac_items", []))
            ]

        tags = ["testing"] if _is_testing else []

        sub_task = {
            "sub_task_id": tid,
            "sequence": seq,
            "hierarchy_level": 1,
            "parent_doc_id": doc_id,
            "task": {
                "title": section["title"],
                "description": section["paragraphs"][0] if section["paragraphs"] else "",
                "implementation_notes": "",
                "acceptance_criteria": ac_list,
                "files_to_modify": [],
            },
            "metadata": {
                "phase": int(_phase) if _phase.isdigit() else 0,
                "effort": _effort,
                "dependencies": [],
                "parent_aa": doc_id,
                "parent_title": _extract_title(parsed, ""),
            },
            "traceability": {
                "aa_reference": doc_id,
            },
            "status": {"state": "pending"},
            "children": [],
            "notes": [],
            "file_refs": [],
            "tags": tags,
        }
        sub_tasks.append(sub_task)

    return sub_tasks


def _derive_doc_id(filename: str) -> str:
    name, _ = os.path.splitext(filename)
    m = re.match(r"^(AA|TD|DOC)-([A-Z0-9]+)", name)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return name


def _extract_title(parsed: dict, fallback: str) -> str:
    for section in parsed.get("sections", []):
        if section["level"] == 1:
            return section["title"]
    return os.path.splitext(fallback)[0]


def _build_section_markdown(section: dict) -> str:
    lines = []
    heading = "#" * section["level"] + " " + section["title"]
    lines.append(heading)
    for p in section.get("paragraphs", []):
        lines.append("")
        lines.append(p)
    for li in section.get("list_items", []):
        lines.append(f"- {li}")
    for ac in section.get("ac_items", []):
        mark = "x" if ac["checked"] else " "
        lines.append(f"- [{mark}] {ac['text']}")
    for cb in section.get("code_blocks", []):
        lang = cb.get("language", "")
        lines.append(f"```{lang}")
        lines.append(cb.get("code", ""))
        lines.append("```")
    return "\n".join(lines)
