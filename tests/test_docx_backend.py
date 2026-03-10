"""Tests for the Word (.docx) backend."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from docweave.backends.docx_backend import WordBackend
from docweave.backends.registry import detect, init_backends

SAMPLE = Path(__file__).parent / "fixtures" / "sample.docx"


@pytest.fixture()
def backend():
    return WordBackend()


@pytest.fixture()
def sample_docx(tmp_path: Path) -> Path:
    """Copy sample.docx to tmp_path so tests don't mutate the fixture."""
    dst = tmp_path / "sample.docx"
    shutil.copy2(SAMPLE, dst)
    return dst


# --- Detection ---


def test_detect_docx(backend: WordBackend):
    assert backend.detect(Path("report.docx")) == 1.0


def test_detect_non_docx(backend: WordBackend):
    assert backend.detect(Path("report.md")) == 0.0
    assert backend.detect(Path("report.txt")) == 0.0


def test_detect_via_registry(sample_docx: Path):
    init_backends()
    b = detect(sample_docx)
    assert b.name == "word-docx"


# --- load_view ---


def test_load_view_block_count(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    # Sample has: title heading, intro para, section heading, formatted para,
    # 3 list items, section heading, para, table, section heading, para,
    # subsection heading, para = at least 13 blocks
    assert doc.block_count >= 10


def test_load_view_heading_detection(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert len(headings) >= 4  # title + 3 sections + 1 subsection
    heading_texts = [h.text for h in headings]
    assert "Sample Document" in heading_texts
    assert "Getting Started" in heading_texts
    assert "Data Overview" in heading_texts
    assert "Conclusion" in heading_texts


def test_load_view_heading_levels(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    # Title is Heading 1
    title = next(h for h in headings if h.text == "Sample Document")
    assert title.level == 1
    # Sections are Heading 2
    section = next(h for h in headings if h.text == "Getting Started")
    assert section.level == 2
    # Subsection is Heading 3
    sub = next(h for h in headings if h.text == "Next Steps")
    assert sub.level == 3


def test_load_view_section_path(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    # A paragraph under "Getting Started" should have section path
    # ["Sample Document", "Getting Started"]
    getting_started_blocks = [
        b for b in doc.blocks
        if b.section_path == ["Sample Document", "Getting Started"] and b.kind != "heading"
    ]
    assert len(getting_started_blocks) >= 1


def test_load_view_paragraph_text(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    paragraphs = [b for b in doc.blocks if b.kind == "paragraph"]
    texts = [p.text for p in paragraphs]
    assert any("introduction" in t.lower() for t in texts)


def test_load_view_table_detection(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    tables = [b for b in doc.blocks if b.kind == "table"]
    assert len(tables) >= 1
    # Table text should contain cell content
    assert "Performance" in tables[0].text
    assert "Uptime" in tables[0].text


def test_load_view_list_detection(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    lists = [b for b in doc.blocks if b.kind == "list_item"]
    assert len(lists) >= 3
    list_texts = [li.text for li in lists]
    assert "First item" in list_texts
    assert "Second item" in list_texts


def test_source_span_is_paragraph_index(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    for block in doc.blocks:
        assert block.source_span.start_line >= 1
        assert block.source_span.end_line == block.source_span.start_line


def test_stable_hash_deterministic(backend: WordBackend, sample_docx: Path):
    doc1 = backend.load_view(sample_docx)
    doc2 = backend.load_view(sample_docx)
    for b1, b2 in zip(doc1.blocks, doc2.blocks, strict=True):
        assert b1.stable_hash == b2.stable_hash


# --- inspect ---


def test_inspect_metadata(backend: WordBackend, sample_docx: Path):
    result = backend.inspect(sample_docx)
    assert result.backend == "word-docx"
    assert result.supports["tables"] is True
    assert result.supports["comments"] is True
    assert result.supports["styles"] is True
    assert result.supports["track_changes"] is False
    assert result.fidelity["roundtrip_risk"] == "medium"
    assert result.block_count >= 10


# --- resolve_anchor ---


def test_resolve_anchor_heading(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    anchor = {"by": "heading", "value": "Getting Started"}
    matches = backend.resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].block_kind == "heading"
    assert matches[0].confidence == 1.0


def test_resolve_anchor_block_id(backend: WordBackend, sample_docx: Path):
    doc = backend.load_view(sample_docx)
    first_id = doc.blocks[0].block_id
    anchor = {"by": "block_id", "value": first_id}
    matches = backend.resolve_anchor(doc, anchor)
    assert len(matches) == 1
    assert matches[0].block_id == first_id


# --- extract_text ---


def test_extract_text(backend: WordBackend, sample_docx: Path):
    text = backend.extract_text(sample_docx)
    assert "Sample Document" in text
    assert "Getting Started" in text
    assert "introduction" in text.lower()


# --- backend name and properties ---


def test_backend_properties(backend: WordBackend):
    assert backend.name == "word-docx"
    assert backend.tier == 1
    assert ".docx" in backend.extensions
