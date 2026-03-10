"""Tests for hidden document context (docweave annotations)."""

from __future__ import annotations

import pytest

from docweave.backends.markdown_native import MarkdownBackend, _parse_docweave_comment
from docweave.plan.applier import apply_plan
from docweave.plan.planner import generate_plan
from docweave.plan.schema import PatchFile


@pytest.fixture()
def backend():
    return MarkdownBackend()


# --- Comment parsing ---


def test_parse_docweave_comment_simple():
    text = '<!-- docweave: {"summary": "hello"} -->'
    result = _parse_docweave_comment(text)
    assert result == {"summary": "hello"}


def test_parse_docweave_comment_with_whitespace():
    text = '<!--  docweave:  {"key": "val"}  -->'
    result = _parse_docweave_comment(text)
    assert result == {"key": "val"}


def test_parse_docweave_comment_not_docweave():
    assert _parse_docweave_comment("<!-- just a normal comment -->") is None


def test_parse_docweave_comment_invalid_json():
    assert _parse_docweave_comment("<!-- docweave: {invalid} -->") is None


def test_parse_docweave_comment_empty():
    assert _parse_docweave_comment("") is None


# --- Backend parsing ---


def test_annotation_attached_to_heading(backend, tmp_path):
    """A docweave comment before a heading populates its annotations."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "Overview section", "tags": ["intro"]} -->\n'
        "# Introduction\n"
        "\n"
        "Some text.\n"
    )
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert len(headings) == 1
    assert headings[0].annotations == {"summary": "Overview section", "tags": ["intro"]}


def test_annotation_not_emitted_as_block(backend, tmp_path):
    """Docweave comments should not appear as html_block blocks."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "test"} -->\n'
        "# Title\n"
        "\n"
        "Body.\n"
    )
    doc = backend.load_view(md)
    html_blocks = [b for b in doc.blocks if b.kind == "html_block"]
    assert len(html_blocks) == 0


def test_no_annotation_gives_empty_dict(backend, tmp_path):
    """Headings without docweave comments have empty annotations."""
    md = tmp_path / "doc.md"
    md.write_text("# Plain Heading\n\nSome text.\n")
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert len(headings) == 1
    assert headings[0].annotations == {}


def test_multiple_headings_with_annotations(backend, tmp_path):
    """Each heading gets its own annotations from the preceding comment."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "first"} -->\n'
        "# Section One\n"
        "\n"
        "Text.\n"
        "\n"
        '<!-- docweave: {"summary": "second"} -->\n'
        "## Section Two\n"
        "\n"
        "More text.\n"
    )
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert len(headings) == 2
    assert headings[0].annotations == {"summary": "first"}
    assert headings[1].annotations == {"summary": "second"}


def test_regular_html_comment_still_parsed(backend, tmp_path):
    """Non-docweave HTML comments are still emitted as html_block."""
    md = tmp_path / "doc.md"
    md.write_text(
        "# Title\n"
        "\n"
        "<!-- regular comment -->\n"
        "\n"
        "Body.\n"
    )
    doc = backend.load_view(md)
    html_blocks = [b for b in doc.blocks if b.kind == "html_block"]
    assert len(html_blocks) == 1


# --- Inspect output ---


def test_inspect_includes_annotations(backend, tmp_path):
    """Inspect result headings include annotation data."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "auth stuff", "tags": ["security"]} -->\n'
        "# Authentication\n"
        "\n"
        "Content.\n"
        "\n"
        "## Plain Sub\n"
        "\n"
        "More content.\n"
    )
    result = backend.inspect(md)
    assert len(result.headings) == 2

    h1 = result.headings[0]
    assert h1.text == "Authentication"
    assert h1.level == 1
    assert h1.block_id == "blk_001"
    assert h1.section_path == ["Authentication"]
    assert h1.annotations == {"summary": "auth stuff", "tags": ["security"]}

    h2 = result.headings[1]
    assert h2.text == "Plain Sub"
    assert h2.level == 2
    assert h2.block_id == "blk_003"
    assert h2.section_path == ["Authentication", "Plain Sub"]
    assert h2.annotations == {}


# --- set_context operation ---


def test_set_context_inserts_new_annotation(tmp_path):
    """set_context on a heading without annotations inserts a comment."""
    md = tmp_path / "doc.md"
    md.write_text("# Introduction\n\nSome text.\n")

    patch = PatchFile(
        version=1,
        target={"file": str(md), "backend": "auto"},
        operations=[{
            "id": "ctx_001",
            "op": "set_context",
            "anchor": {"by": "heading", "value": "Introduction"},
            "context": {"summary": "The intro section", "tags": ["overview"]},
        }],
    )

    plan = generate_plan(md, patch)
    assert plan.valid
    result = apply_plan(md, plan)
    assert result.operations_applied == 1

    content = md.read_text()
    assert "<!-- docweave:" in content
    assert '"summary"' in content
    assert '"The intro section"' in content

    # Verify it parses back correctly
    backend = MarkdownBackend()
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert headings[0].annotations["summary"] == "The intro section"
    assert headings[0].annotations["tags"] == ["overview"]


def test_set_context_merges_with_existing(tmp_path):
    """set_context merges new keys into existing annotations."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "original", "status": "draft"} -->\n'
        "# Introduction\n"
        "\n"
        "Some text.\n"
    )

    patch = PatchFile(
        version=1,
        target={"file": str(md), "backend": "auto"},
        operations=[{
            "id": "ctx_001",
            "op": "set_context",
            "anchor": {"by": "heading", "value": "Introduction"},
            "context": {"summary": "updated", "tags": ["new"]},
        }],
    )

    plan = generate_plan(md, patch)
    assert plan.valid
    apply_plan(md, plan)

    backend = MarkdownBackend()
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    ann = headings[0].annotations
    assert ann["summary"] == "updated"  # overwritten
    assert ann["status"] == "draft"  # preserved from original
    assert ann["tags"] == ["new"]  # new key added


def test_set_context_requires_context_field():
    """set_context without context field should be rejected."""
    with pytest.raises(ValueError, match="requires a 'context' field"):
        PatchFile(
            version=1,
            target={"file": "test.md", "backend": "auto"},
            operations=[{
                "id": "ctx_001",
                "op": "set_context",
                "anchor": {"by": "heading", "value": "Title"},
            }],
        )


# --- Roundtrip ---


def test_annotation_survives_content_edit(tmp_path):
    """Annotations survive when a different block is edited."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "keep me"} -->\n'
        "# Title\n"
        "\n"
        "Original paragraph.\n"
    )

    patch = PatchFile(
        version=1,
        target={"file": str(md), "backend": "auto"},
        operations=[{
            "id": "op_001",
            "op": "replace_text",
            "anchor": {"by": "quote", "value": "Original paragraph"},
            "replacement": "Updated paragraph",
        }],
    )

    plan = generate_plan(md, patch)
    assert plan.valid
    apply_plan(md, plan)

    content = md.read_text()
    assert "Updated paragraph" in content
    assert '<!-- docweave:' in content

    backend = MarkdownBackend()
    doc = backend.load_view(md)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert headings[0].annotations == {"summary": "keep me"}


# --- CLI integration ---


def test_inspect_cli_annotations(run_cli, tmp_path):
    """The inspect CLI command surfaces annotations in headings."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"summary": "cli test"} -->\n'
        "# My Section\n"
        "\n"
        "Content.\n"
    )
    result = run_cli("inspect", str(md))
    assert result.json["ok"] is True
    headings = result.json["result"]["headings"]
    assert len(headings) == 1
    assert headings[0]["text"] == "My Section"
    assert headings[0]["level"] == 1
    assert headings[0]["block_id"] == "blk_001"
    assert headings[0]["section_path"] == ["My Section"]
    assert headings[0]["annotations"]["summary"] == "cli test"


# --- Tag filtering ---


def test_inspect_tag_filter(run_cli, tmp_path):
    """inspect --tag filters headings to those with matching tag."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"tags": ["security", "api"]} -->\n'
        "# Authentication\n\nContent.\n\n"
        '<!-- docweave: {"tags": ["api", "performance"]} -->\n'
        "# Rate Limits\n\nContent.\n\n"
        "# Changelog\n\nUpdates.\n"
    )
    # Filter by "security" — should only get Authentication
    result = run_cli("inspect", str(md), "--tag", "security")
    assert result.json["ok"] is True
    headings = result.json["result"]["headings"]
    assert len(headings) == 1
    assert headings[0]["text"] == "Authentication"


def test_inspect_tag_filter_multiple_matches(run_cli, tmp_path):
    """inspect --tag returns all headings with the tag."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"tags": ["security", "api"]} -->\n'
        "# Authentication\n\nContent.\n\n"
        '<!-- docweave: {"tags": ["api", "performance"]} -->\n'
        "# Rate Limits\n\nContent.\n\n"
        "# Changelog\n\nUpdates.\n"
    )
    result = run_cli("inspect", str(md), "--tag", "api")
    headings = result.json["result"]["headings"]
    assert len(headings) == 2
    texts = [h["text"] for h in headings]
    assert "Authentication" in texts
    assert "Rate Limits" in texts


def test_inspect_tag_filter_case_insensitive(run_cli, tmp_path):
    """Tag matching is case-insensitive."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"tags": ["Security"]} -->\n'
        "# Auth\n\nContent.\n"
    )
    result = run_cli("inspect", str(md), "--tag", "security")
    assert len(result.json["result"]["headings"]) == 1


def test_inspect_tag_no_match(run_cli, tmp_path):
    """inspect --tag with no matches returns empty headings."""
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nContent.\n")
    result = run_cli("inspect", str(md), "--tag", "nonexistent")
    assert result.json["result"]["headings"] == []


def test_view_tag_filter(run_cli, tmp_path):
    """view --tag returns blocks from sections with matching tag."""
    md = tmp_path / "doc.md"
    md.write_text(
        '<!-- docweave: {"tags": ["security"]} -->\n'
        "# Authentication\n\nAuth content.\n\n"
        "# Changelog\n\nChangelog content.\n"
    )
    result = run_cli("view", str(md), "--tag", "security")
    assert result.json["ok"] is True
    blocks = result.json["result"]["blocks"]
    # Should include the heading and its content, not Changelog
    texts = [b["text"] for b in blocks]
    assert "Authentication" in texts
    assert "Auth content." in texts
    assert "Changelog" not in texts


def test_view_tag_no_match_warns(run_cli, tmp_path):
    """view --tag with no matches returns warning."""
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nContent.\n")
    result = run_cli("view", str(md), "--tag", "nonexistent")
    assert result.json["ok"] is True
    assert len(result.json["result"]["blocks"]) == 0
    assert any("WARN_TAG_NOT_FOUND" in w["code"] for w in result.json["warnings"])
