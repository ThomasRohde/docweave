"""Apply an execution plan to a Word (.docx) document."""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

from docweave.plan.applier import ApplyResult, FingerprintConflictError
from docweave.plan.planner import ExecutionPlan


def _file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_style_id(element: object) -> str:
    """Read the style ID directly from a w:p XML element."""
    from docx.oxml.ns import qn

    p_pr = element.find(qn("w:pPr"))  # type: ignore[attr-defined]
    if p_pr is not None:
        p_style = p_pr.find(qn("w:pStyle"))
        if p_style is not None:
            return p_style.get(qn("w:val"), "")
    return ""


def _set_style_id(element: object, style_id: str) -> None:
    """Set the style ID on a w:p XML element."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    p_pr = element.find(qn("w:pPr"))  # type: ignore[attr-defined]
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        element.insert(0, p_pr)  # type: ignore[attr-defined]
    p_style = p_pr.find(qn("w:pStyle"))
    if p_style is None:
        p_style = OxmlElement("w:pStyle")
        p_pr.insert(0, p_style)
    p_style.set(qn("w:val"), style_id)


def _style_for_kind(kind: str, level: int | None = None) -> str:
    """Map a docweave content kind to a Word style name."""
    if kind == "heading":
        lvl = level if level and level >= 1 else 2
        return f"Heading {lvl}"
    if kind in ("list_item", "unordered_list"):
        return "List Bullet"
    if kind == "ordered_list":
        return "List Number"
    if kind == "blockquote":
        return "Quote"
    return "Normal"


def _get_body_elements(document: object) -> list:
    """Return the list of body child elements (paragraphs and tables)."""
    return list(document.element.body)  # type: ignore[attr-defined]


def _element_to_paragraph(element: object, body: object) -> object:
    """Wrap an lxml element as a python-docx Paragraph."""
    from docx.text.paragraph import Paragraph

    return Paragraph(element, body)  # type: ignore[arg-type]


def _set_paragraph_text(para: object, text: str) -> None:
    """Replace paragraph text, preserving first run's formatting if possible."""
    runs = para.runs  # type: ignore[attr-defined]
    if not runs:
        para.text = text  # type: ignore[attr-defined]
        return

    # Preserve first run's formatting, clear others
    first_run = runs[0]
    first_run.text = text
    for run in runs[1:]:
        run._element.getparent().remove(run._element)


def _create_paragraph_element(text: str, style_name: str, document: object) -> object:
    """Create a new paragraph element with the given text and style."""
    # Add a temporary paragraph to the document, then detach it
    para = document.add_paragraph(text, style=style_name)  # type: ignore[attr-defined]
    elem = para._element
    elem.getparent().remove(elem)
    return elem


def apply_plan_docx(
    path: Path, plan: ExecutionPlan, *, backup: bool = False,
) -> ApplyResult:
    """Apply an execution plan to a .docx file."""
    from docx import Document

    fingerprint_before = _file_fingerprint(path)

    if fingerprint_before != plan.fingerprint:
        raise FingerprintConflictError(
            expected=plan.fingerprint, actual=fingerprint_before,
        )

    backup_path: str | None = None
    if backup:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        bak = path.with_suffix(f".{stamp}.bak")
        shutil.copy2(path, bak)
        backup_path = str(bak)

    document = Document(str(path))
    body = document.element.body
    warnings: list[str] = []

    # Build index: para_index (1-based) → element
    elements = _get_body_elements(document)
    index_map: dict[int, object] = {}
    para_idx = 0
    for elem in elements:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag in ("p", "tbl"):
            para_idx += 1
            index_map[para_idx] = elem

    # Sort operations by affected_lines.end_line descending (bottom-up)
    sorted_ops = sorted(
        plan.resolved_operations,
        key=lambda r: r.affected_lines.end_line,
        reverse=True,
    )

    for resolved in sorted_ops:
        op = resolved.operation
        start = resolved.affected_lines.start_line
        op_type = op["op"]

        target_elem = index_map.get(start)
        if target_elem is None:
            warnings.append(f"Could not find element at index {start} for op {op.get('id', '?')}")
            continue

        if op_type == "insert_after":
            content = op["content"]
            style = _style_for_kind(content.get("kind", "paragraph"), content.get("level"))
            new_elem = _create_paragraph_element(content["value"], style, document)
            target_elem.addnext(new_elem)
            # Update index for subsequent ops (not strictly needed for bottom-up)

        elif op_type == "insert_before":
            content = op["content"]
            style = _style_for_kind(content.get("kind", "paragraph"), content.get("level"))
            new_elem = _create_paragraph_element(content["value"], style, document)
            target_elem.addprevious(new_elem)

        elif op_type == "replace_block":
            content = op["content"]
            tag = target_elem.tag.split("}")[-1] if "}" in target_elem.tag else target_elem.tag
            if tag == "p":
                para = _element_to_paragraph(target_elem, body)
                _set_paragraph_text(para, content["value"])
                # Update style if kind specifies it
                kind = content.get("kind", "paragraph")
                if kind == "heading":
                    style_name = _style_for_kind(kind, content.get("level"))
                    try:
                        para.style = document.styles[style_name]  # type: ignore[attr-defined,index]
                    except KeyError:
                        pass
            else:
                warnings.append(
                    f"replace_block on non-paragraph element at index {start}"
                )

        elif op_type == "replace_text":
            tag = target_elem.tag.split("}")[-1] if "}" in target_elem.tag else target_elem.tag
            if tag == "p":
                para = _element_to_paragraph(target_elem, body)
                search = op["anchor"]["value"]
                replacement = op.get("replacement", "")
                _replace_text_in_paragraph(para, search, replacement)
            else:
                warnings.append(
                    f"replace_text on non-paragraph element at index {start}"
                )

        elif op_type == "delete_block":
            target_elem.getparent().remove(target_elem)

        elif op_type == "set_heading":
            content = op["content"]
            tag = target_elem.tag.split("}")[-1] if "}" in target_elem.tag else target_elem.tag
            if tag == "p":
                para = _element_to_paragraph(target_elem, body)
                _set_paragraph_text(para, content["value"].lstrip("# "))
                # Check style via XML to avoid part lookup issues
                style_id = _get_style_id(target_elem)
                if not style_id.startswith("Heading"):
                    _set_style_id(target_elem, "Heading1")

        elif op_type == "normalize_whitespace":
            tag = target_elem.tag.split("}")[-1] if "}" in target_elem.tag else target_elem.tag
            if tag == "p":
                para = _element_to_paragraph(target_elem, body)
                text = para.text or ""  # type: ignore[attr-defined]
                # Collapse multiple spaces/newlines
                normalized = " ".join(text.split())
                _set_paragraph_text(para, normalized)

        else:
            warnings.append(f"Unknown operation type: {op_type}")

    document.save(str(path))
    fingerprint_after = _file_fingerprint(path)

    return ApplyResult(
        file=str(path),
        operations_applied=len(sorted_ops),
        fingerprint_before=fingerprint_before,
        fingerprint_after=fingerprint_after,
        backup_path=backup_path,
        warnings=warnings,
    )


def _replace_text_in_paragraph(para: object, search: str, replacement: str) -> None:
    """Replace text within a paragraph, handling run boundaries."""
    runs = para.runs  # type: ignore[attr-defined]
    if not runs:
        text = para.text or ""  # type: ignore[attr-defined]
        para.text = text.replace(search, replacement)  # type: ignore[attr-defined]
        return

    # Concatenate all run texts to find the substring
    full_text = "".join(r.text for r in runs)
    if search not in full_text:
        return

    new_full = full_text.replace(search, replacement)

    # Simple strategy: put all text in first run, clear others
    if runs:
        runs[0].text = new_full
        for run in runs[1:]:
            run.text = ""
