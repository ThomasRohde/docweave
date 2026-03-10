"""Tests for the Markdown backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from docweave.backends.markdown_native import MarkdownBackend

SAMPLE = Path(__file__).parent / "fixtures" / "sample.md"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def backend():
    return MarkdownBackend()


def test_detect_md(backend):
    assert backend.detect(Path("readme.md")) == 1.0


def test_detect_markdown_ext(backend):
    assert backend.detect(Path("readme.markdown")) == 1.0


def test_detect_txt(backend):
    assert backend.detect(Path("readme.txt")) == 0.0


def test_block_count(backend):
    doc = backend.load_view(SAMPLE)
    assert doc.block_count == 18


def test_heading_count(backend):
    doc = backend.load_view(SAMPLE)
    assert doc.heading_count == 7


def test_source_span_maps_to_raw_text(backend):
    """Each block's source_span should map back to its raw_text."""
    doc = backend.load_view(SAMPLE)
    lines = SAMPLE.read_text("utf-8").splitlines(keepends=True)
    for block in doc.blocks:
        span = block.source_span
        reconstructed = "".join(lines[span.start_line - 1 : span.end_line])
        assert reconstructed == block.raw_text, (
            f"Block {block.block_id} raw_text mismatch"
        )


def test_section_path_purpose(backend):
    doc = backend.load_view(SAMPLE)
    purpose_para = [
        b for b in doc.blocks if b.text == "The purpose is to demonstrate docweave."
    ]
    assert len(purpose_para) == 1
    assert purpose_para[0].section_path == ["Introduction", "Purpose"]


def test_section_path_non_functional(backend):
    doc = backend.load_view(SAMPLE)
    nf_para = [b for b in doc.blocks if b.text == "Performance must be acceptable."]
    assert len(nf_para) == 1
    assert nf_para[0].section_path == ["Requirements", "Non-Functional"]


def test_heading_levels(backend):
    doc = backend.load_view(SAMPLE)
    headings = {b.text: b.level for b in doc.blocks if b.kind == "heading"}
    assert headings["Introduction"] == 1
    assert headings["Purpose"] == 2


def test_stable_hash_deterministic(backend):
    doc1 = backend.load_view(SAMPLE)
    doc2 = backend.load_view(SAMPLE)
    for b1, b2 in zip(doc1.blocks, doc2.blocks):
        assert b1.stable_hash == b2.stable_hash


def test_inspect_result(backend):
    result = backend.inspect(SAMPLE)
    assert result.backend == "markdown-native"
    assert result.tier == "native-safe"
    assert result.editable is True


def test_block_kinds_present(backend):
    doc = backend.load_view(SAMPLE)
    kinds = {b.kind for b in doc.blocks}
    assert kinds == {
        "heading",
        "paragraph",
        "unordered_list",
        "ordered_list",
        "thematic_break",
        "code_block",
        "blockquote",
    }


def test_blockquote_parsed(backend):
    """Blockquotes should be parsed as blocks with kind='blockquote'."""
    doc = backend.load_view(SAMPLE)
    bq_blocks = [b for b in doc.blocks if b.kind == "blockquote"]
    assert len(bq_blocks) >= 1


def test_blockquote_content(backend):
    """Blockquote text content should be extracted."""
    doc = backend.load_view(SAMPLE)
    bq_blocks = [b for b in doc.blocks if b.kind == "blockquote"]
    assert any("blockquote for testing" in b.text for b in bq_blocks)


def test_bom_file_parses_correctly(backend, tmp_path):
    """A file with a UTF-8 BOM should parse correctly."""
    bom_file = tmp_path / "bom.md"
    bom_file.write_bytes(b"\xef\xbb\xbf# Title\n\nSome content.\n")
    doc = backend.load_view(bom_file)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert len(headings) == 1
    assert headings[0].text == "Title"


def test_inspect_tables_true(backend):
    """Inspect should report tables=True now that table parsing is implemented."""
    result = backend.inspect(SAMPLE)
    assert result.supports["tables"] is True


# --- Nested list tests (Bugs 1 & 2) ---


def test_nested_list_all_items_in_text(backend, tmp_path):
    """Text should include items after a nested group, not just before."""
    md = tmp_path / "nested.md"
    md.write_text(
        "- Item 1\n"
        "  - Nested A\n"
        "  - Nested B\n"
        "- Item 2\n"
        "- Item 3\n"
    )
    doc = backend.load_view(md)
    lists = [b for b in doc.blocks if b.kind == "unordered_list"]
    assert len(lists) == 1
    text = lists[0].text
    assert "Item 1" in text
    assert "Item 2" in text
    assert "Item 3" in text


def test_nested_list_single_block(backend, tmp_path):
    """A list with nested items should produce exactly one list block."""
    md = tmp_path / "nested.md"
    md.write_text(
        "- A\n"
        "  - B\n"
        "- C\n"
    )
    doc = backend.load_view(md)
    lists = [b for b in doc.blocks if b.kind in ("unordered_list", "ordered_list")]
    assert len(lists) == 1


def test_deeply_nested_list(backend, tmp_path):
    """3 levels of nesting should produce a single block."""
    md = tmp_path / "deep.md"
    md.write_text(
        "- Level 1\n"
        "  - Level 2\n"
        "    - Level 3\n"
        "  - Level 2b\n"
        "- Level 1b\n"
    )
    doc = backend.load_view(md)
    lists = [b for b in doc.blocks if b.kind in ("unordered_list", "ordered_list")]
    assert len(lists) == 1
    text = lists[0].text
    assert "Level 1" in text
    assert "Level 3" in text
    assert "Level 1b" in text


def test_mixed_list_types(backend, tmp_path):
    """Ordered list inside unordered should produce a single block."""
    md = tmp_path / "mixed.md"
    md.write_text(
        "- Unordered A\n"
        "  1. Ordered 1\n"
        "  2. Ordered 2\n"
        "- Unordered B\n"
    )
    doc = backend.load_view(md)
    # The top-level is unordered
    top_lists = [b for b in doc.blocks if b.kind in ("unordered_list", "ordered_list")]
    assert len(top_lists) == 1
    assert top_lists[0].kind == "unordered_list"
    text = top_lists[0].text
    assert "Unordered A" in text
    assert "Unordered B" in text


# --- UX 8: editable check ---


def test_inspect_read_only_file(backend, tmp_path):
    """Inspect should report editable=False for read-only files."""
    import stat

    ro_file = tmp_path / "readonly.md"
    ro_file.write_text("# Read Only\n")
    # Remove write permission
    ro_file.chmod(stat.S_IREAD)
    try:
        result = backend.inspect(ro_file)
        assert result.editable is False
    finally:
        # Restore permissions for cleanup
        ro_file.chmod(stat.S_IREAD | stat.S_IWRITE)
