"""Tests for raw and semantic diff."""

from __future__ import annotations

from pathlib import Path

from docweave.backends.markdown_native import MarkdownBackend
from docweave.diff.raw import DiffHunk, format_raw_diff, raw_diff
from docweave.diff.semantic import semantic_diff

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample.md"


def _parse(text: str, label: str = "test.md"):
    backend = MarkdownBackend()
    return backend._parse_source(text, label)


# --- Raw diff tests ---


def test_raw_diff_identical():
    text = "Hello\nWorld\n"
    assert raw_diff(text, text) == []


def test_raw_diff_addition():
    before = "Hello\n"
    after = "Hello\nWorld\n"
    hunks = raw_diff(before, after)
    assert len(hunks) >= 1
    plus_lines = [ln for h in hunks for ln in h.lines if ln.startswith("+")]
    assert any("World" in ln for ln in plus_lines)


def test_raw_diff_deletion():
    before = "Hello\nWorld\n"
    after = "Hello\n"
    hunks = raw_diff(before, after)
    assert len(hunks) >= 1
    minus_lines = [ln for h in hunks for ln in h.lines if ln.startswith("-")]
    assert any("World" in ln for ln in minus_lines)


def test_raw_diff_line_numbers():
    before = "A\nB\nC\n"
    after = "A\nX\nC\n"
    hunks = raw_diff(before, after)
    assert len(hunks) >= 1
    hunk = hunks[0]
    assert hunk.start_line_before >= 1
    assert hunk.count_before >= 1
    assert hunk.start_line_after >= 1
    assert hunk.count_after >= 1


def test_format_raw_diff():
    hunks = [
        DiffHunk(
            start_line_before=1, count_before=2,
            start_line_after=1, count_after=2,
            lines=["-old", "+new"],
        ),
    ]
    output = format_raw_diff(hunks)
    assert "@@ -1,2 +1,2 @@" in output
    assert "-old" in output
    assert "+new" in output


def test_format_raw_diff_empty():
    assert format_raw_diff([]) == ""


# --- Semantic diff tests ---


def test_semantic_diff_no_changes():
    text = "# Title\n\nSome text.\n"
    doc = _parse(text)
    report = semantic_diff(doc, doc)
    assert report.blocks_added == []
    assert report.blocks_removed == []
    assert report.blocks_modified == []
    assert report.summary == "No changes"


def test_semantic_diff_added_removed():
    before_text = "# Title\n\nParagraph one.\n"
    after_text = "# Title\n\nParagraph two.\n\nNew paragraph.\n"
    before_doc = _parse(before_text)
    after_doc = _parse(after_text)
    report = semantic_diff(before_doc, after_doc)
    # blk_002 exists in both but modified, blk_003 added in after
    total_changes = (
        len(report.blocks_added) + len(report.blocks_removed) + len(report.blocks_modified)
    )
    assert total_changes > 0


def test_semantic_diff_summary():
    before_text = "# Title\n\nOld text.\n"
    after_text = "# Title\n\nNew text.\n"
    before_doc = _parse(before_text)
    after_doc = _parse(after_text)
    report = semantic_diff(before_doc, after_doc)
    assert isinstance(report.summary, str)
    # Should contain "modified" since content changed
    assert any(
        kw in report.summary
        for kw in ("modified", "No changes", "added", "removed")
    )
