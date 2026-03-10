"""Tests for DOCX annotation support via custom XML parts."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from docweave.backends.docx_annotations import (
    annotation_key,
    read_annotations,
    write_annotations,
)
from docweave.backends.docx_backend import WordBackend

SAMPLE = Path(__file__).parent / "fixtures" / "sample.docx"


@pytest.fixture()
def backend():
    return WordBackend()


@pytest.fixture()
def sample_docx(tmp_path: Path) -> Path:
    dst = tmp_path / "sample.docx"
    shutil.copy2(SAMPLE, dst)
    return dst


def _open_doc(path: Path):
    from docx import Document

    return Document(str(path))


# --- annotation_key ---


def test_annotation_key_format():
    assert annotation_key("Introduction", 1) == "Introduction::1"
    assert annotation_key("Details", 2) == "Details::2"


# --- read/write round-trip ---


def test_write_then_read_annotations(sample_docx):
    doc = _open_doc(sample_docx)
    annotations = {
        annotation_key("Sample Document", 1): {"summary": "The main doc", "tags": ["test"]},
        annotation_key("Getting Started", 2): {"summary": "Setup steps"},
    }
    write_annotations(doc, annotations)
    doc.save(str(sample_docx))

    doc2 = _open_doc(sample_docx)
    result = read_annotations(doc2)
    assert result[annotation_key("Sample Document", 1)] == {
        "summary": "The main doc",
        "tags": ["test"],
    }
    assert result[annotation_key("Getting Started", 2)] == {"summary": "Setup steps"}


def test_write_replaces_existing(sample_docx):
    doc = _open_doc(sample_docx)

    # Write initial annotations
    write_annotations(doc, {annotation_key("Title", 1): {"summary": "old"}})
    doc.save(str(sample_docx))

    # Write new annotations (should replace)
    doc2 = _open_doc(sample_docx)
    write_annotations(doc2, {annotation_key("Title", 1): {"summary": "new"}})
    doc2.save(str(sample_docx))

    doc3 = _open_doc(sample_docx)
    result = read_annotations(doc3)
    assert result[annotation_key("Title", 1)]["summary"] == "new"


def test_read_empty_document_returns_empty(sample_docx):
    doc = _open_doc(sample_docx)
    result = read_annotations(doc)
    assert result == {}


# --- Backend integration ---


def test_load_view_picks_up_annotations(backend, sample_docx):
    """Annotations stored in custom XML show up on heading blocks."""
    doc = _open_doc(sample_docx)
    write_annotations(doc, {
        annotation_key("Getting Started", 2): {
            "summary": "How to begin",
            "tags": ["setup"],
        },
    })
    doc.save(str(sample_docx))

    ndoc = backend.load_view(sample_docx)
    heading = next(b for b in ndoc.blocks if b.text == "Getting Started")
    assert heading.annotations == {"summary": "How to begin", "tags": ["setup"]}


def test_load_view_no_annotations_gives_empty(backend, sample_docx):
    ndoc = backend.load_view(sample_docx)
    heading = next(b for b in ndoc.blocks if b.text == "Getting Started")
    assert heading.annotations == {}


def test_inspect_surfaces_annotations(backend, sample_docx):
    doc = _open_doc(sample_docx)
    write_annotations(doc, {
        annotation_key("Getting Started", 2): {"summary": "Setup guide"},
    })
    doc.save(str(sample_docx))

    result = backend.inspect(sample_docx)
    h = next(h for h in result.headings if h.text == "Getting Started")
    assert h.annotations == {"summary": "Setup guide"}
    assert h.level == 2


# --- set_context via applier ---


def test_set_context_docx_creates_annotation(sample_docx):
    from docweave.plan.applier_docx import apply_plan_docx
    from docweave.plan.planner import generate_plan
    from docweave.plan.schema import PatchFile

    patch = PatchFile(
        version=1,
        target={"file": str(sample_docx), "backend": "auto"},
        operations=[{
            "id": "ctx_001",
            "op": "set_context",
            "anchor": {"by": "heading", "value": "Getting Started"},
            "context": {"summary": "Setup instructions", "status": "complete"},
        }],
    )

    plan = generate_plan(sample_docx, patch)
    assert plan.valid
    result = apply_plan_docx(sample_docx, plan)
    assert result.operations_applied == 1

    # Verify annotation was written
    backend = WordBackend()
    ndoc = backend.load_view(sample_docx)
    heading = next(b for b in ndoc.blocks if b.text == "Getting Started")
    assert heading.annotations["summary"] == "Setup instructions"
    assert heading.annotations["status"] == "complete"


def test_set_context_docx_merges_existing(sample_docx):
    from docweave.plan.applier_docx import apply_plan_docx
    from docweave.plan.planner import generate_plan
    from docweave.plan.schema import PatchFile

    # Pre-populate with existing annotations
    doc = _open_doc(sample_docx)
    write_annotations(doc, {
        annotation_key("Getting Started", 2): {"summary": "old", "status": "draft"},
    })
    doc.save(str(sample_docx))

    patch = PatchFile(
        version=1,
        target={"file": str(sample_docx), "backend": "auto"},
        operations=[{
            "id": "ctx_001",
            "op": "set_context",
            "anchor": {"by": "heading", "value": "Getting Started"},
            "context": {"summary": "updated", "tags": ["new"]},
        }],
    )

    plan = generate_plan(sample_docx, patch)
    assert plan.valid
    apply_plan_docx(sample_docx, plan)

    backend = WordBackend()
    ndoc = backend.load_view(sample_docx)
    heading = next(b for b in ndoc.blocks if b.text == "Getting Started")
    assert heading.annotations["summary"] == "updated"  # overwritten
    assert heading.annotations["status"] == "draft"  # preserved
    assert heading.annotations["tags"] == ["new"]  # added
