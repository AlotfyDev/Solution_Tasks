import mistune


_markdown = mistune.create_markdown(renderer="ast", plugins=["task_lists"])


def parse(content: str) -> list[dict]:
    return _markdown(content)


def visit(tokens: list[dict]) -> dict:
    result = {
        "sections": [],
        "acceptance_criteria": [],
        "code_blocks": [],
    }
    current_section = None

    for token in tokens:
        t = token["type"]

        if t == "heading":
            level = token["attrs"]["level"]
            text = _collect_text(token)
            current_section = {
                "title": text,
                "level": level,
                "paragraphs": [],
                "list_items": [],
                "ac_items": [],
                "code_blocks": [],
            }
            result["sections"].append(current_section)

        elif t == "paragraph":
            text = _collect_text(token)
            if current_section is not None:
                current_section["paragraphs"].append(text)

        elif t == "list":
            for child in token.get("children", []):
                if child["type"] == "task_list_item":
                    checked = child["attrs"].get("checked", False)
                    text = _collect_text(child)
                    item = {"text": text, "checked": checked}
                    result["acceptance_criteria"].append(item)
                    if current_section is not None:
                        current_section["ac_items"].append(item)
                elif child["type"] == "list_item":
                    text = _collect_text(child)
                    if current_section is not None:
                        current_section["list_items"].append(text)

        elif t == "block_code":
            block = {
                "language": token.get("attrs", {}).get("info", ""),
                "code": token.get("raw", ""),
            }
            result["code_blocks"].append(block)
            if current_section is not None:
                current_section["code_blocks"].append(block)

    return result


def _collect_text(node: dict) -> str:
    parts = []
    for child in node.get("children", []):
        if "raw" in child:
            parts.append(child["raw"])
        elif "children" in child:
            parts.append(_collect_text(child))
    return "".join(parts)
