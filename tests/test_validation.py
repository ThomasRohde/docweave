"""Tests for document validation."""

from __future__ import annotations

from pathlib import Path

from docweave.backends.markdown_native import MarkdownBackend
from docweave.validation import validate_document

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.md"


def _parse(text: str, label: str = "test.md"):
    backend = MarkdownBackend()
    return backend._parse_source(text, label)


def test_sample_validates_clean():
    backend = MarkdownBackend()
    doc = backend.load_view(SAMPLE)
    report = validate_document(doc)
    assert report.valid is True
    assert report.issues == []


def test_heading_skip_detected():
    # h1 → h3 skips h2
    text = "# Title\n\n### Skipped\n\nSome text.\n"
    doc = _parse(text)
    report = validate_document(doc)
    codes = [iss.code for iss in report.issues]
    assert "HEADING_SKIP" in codes


def test_validate_cli_envelope(run_cli):
    result = run_cli("validate", str(SAMPLE))
    assert result.exit_code == 0
    env = result.json
    assert env["ok"] is True
    assert env["command"] == "validate"
    assert "valid" in env["result"]
    assert "issues" in env["result"]


def test_validate_block_count():
    backend = MarkdownBackend()
    doc = backend.load_view(SAMPLE)
    report = validate_document(doc)
    assert report.block_count == doc.block_count
    assert report.block_count > 0
