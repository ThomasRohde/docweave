"""Unit tests for the anchor resolution module."""

from __future__ import annotations

from pathlib import Path

import pytest

from docweave.anchors import (
    Anchor,
    OccurrenceOutOfRangeError,
    parse_anchor_spec,
    resolve_anchor,
    search_blocks,
)
from docweave.backends.markdown_native import MarkdownBackend

SAMPLE = Path(__file__).parent / "fixtures" / "sample.md"
DUPLICATE_HEADINGS = Path(__file__).parent / "fixtures" / "duplicate_headings.md"


@pytest.fixture()
def doc():
    backend = MarkdownBackend()
    return backend.load_view(SAMPLE)


@pytest.fixture()
def dup_doc():
    backend = MarkdownBackend()
    return backend.load_view(DUPLICATE_HEADINGS)


# --- parse_anchor_spec ---


def test_parse_anchor_spec_heading():
    a = parse_anchor_spec("heading:Purpose")
    assert a.by == "heading"
    assert a.value == "Purpose"


def test_parse_anchor_spec_ordinal():
    a = parse_anchor_spec("ordinal:paragraph:3")
    assert a.by == "ordinal"
    assert a.value == "paragraph"
    assert a.index == 3


def test_parse_anchor_spec_invalid():
    with pytest.raises(ValueError, match="Unknown anchor type"):
        parse_anchor_spec("badtype:foo")


# --- heading resolution ---


def test_heading_exact_match(doc):
    anchor = Anchor(by="heading", value="Purpose")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    top = matches[0]
    assert top.confidence == 1.0
    assert top.match_type == "exact"
    assert top.block_kind == "heading"


def test_heading_case_insensitive(doc):
    anchor = Anchor(by="heading", value="purpose")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence == 1.0
    assert matches[0].match_type == "exact"


def test_heading_substring_match(doc):
    anchor = Anchor(by="heading", value="Purp")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence == 0.8
    assert matches[0].match_type == "substring"


def test_heading_fuzzy_match(doc):
    anchor = Anchor(by="heading", value="Purposee")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence > 0.5
    assert matches[0].match_type == "fuzzy"


def test_heading_no_match(doc):
    anchor = Anchor(by="heading", value="Nonexistent")
    matches = resolve_anchor(doc, anchor)
    assert matches == []


# --- quote resolution ---


def test_quote_substring(doc):
    anchor = Anchor(by="quote", value="demonstrate docweave")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence == 0.7
    assert matches[0].match_type == "substring"


def test_quote_with_context_boost(doc):
    anchor = Anchor(by="quote", value="demonstrate docweave", context_before="Purpose")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence > 0.7


# --- block_id resolution ---


def test_block_id_direct(doc):
    anchor = Anchor(by="block_id", value="blk_001")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) == 1
    assert matches[0].confidence == 1.0
    assert matches[0].match_type == "direct"
    assert matches[0].block_id == "blk_001"


# --- hash resolution ---


def test_hash_prefix(doc):
    first_block = doc.blocks[0]
    prefix = first_block.stable_hash[:8]
    anchor = Anchor(by="hash", value=prefix)
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1
    assert matches[0].confidence == 1.0
    assert matches[0].match_type == "direct"


# --- ordinal resolution ---


def test_ordinal_paragraph(doc):
    anchor = Anchor(by="ordinal", value="paragraph", index=2)
    matches = resolve_anchor(doc, anchor)
    assert len(matches) == 1
    assert matches[0].confidence == 1.0
    assert matches[0].match_type == "ordinal"
    assert matches[0].block_kind == "paragraph"


# --- section filter ---


def test_section_filter(doc):
    # Quote found under Purpose section
    anchor = Anchor(by="quote", value="demonstrate", section="Purpose")
    matches = resolve_anchor(doc, anchor)
    assert len(matches) >= 1

    # Same text not found under Features section
    anchor2 = Anchor(by="quote", value="demonstrate", section="Features")
    matches2 = resolve_anchor(doc, anchor2)
    assert matches2 == []


# --- search_blocks ---


def test_search_blocks(doc):
    matches = search_blocks(doc, "demonstrate")
    assert len(matches) >= 1
    assert all(m.confidence > 0 for m in matches)


# --- occurrence selection ---


def test_occurrence_selects_nth_heading(dup_doc):
    """occurrence=2 should select the 2nd duplicate heading."""
    anchor = Anchor(by="heading", value="Section", occurrence=2)
    matches = resolve_anchor(dup_doc, anchor)
    assert len(matches) >= 3  # 3 headings all match
    selected = matches[0]
    # The 2nd Section heading should be the selected one
    assert selected.block_kind == "heading"
    # Verify it's different from occurrence=1
    anchor1 = Anchor(by="heading", value="Section", occurrence=1)
    matches1 = resolve_anchor(dup_doc, anchor1)
    assert matches1[0].block_id != selected.block_id


def test_occurrence_selects_third_heading(dup_doc):
    """occurrence=3 should select the 3rd duplicate heading."""
    anchor = Anchor(by="heading", value="Section", occurrence=3)
    matches = resolve_anchor(dup_doc, anchor)
    selected = matches[0]
    assert selected.block_kind == "heading"
    # Must be different from occ 1 and 2
    for occ in [1, 2]:
        other = Anchor(by="heading", value="Section", occurrence=occ)
        other_matches = resolve_anchor(dup_doc, other)
        assert other_matches[0].block_id != selected.block_id


# --- heading context disambiguation ---


def test_heading_context_before_disambiguates(dup_doc):
    """context_before should boost the matching heading."""
    # The first "Section" heading is preceded by "First intro paragraph."
    anchor = Anchor(by="heading", value="Section", context_before="First intro paragraph")
    matches = resolve_anchor(dup_doc, anchor)
    assert len(matches) >= 1
    # The match with the highest confidence should be the first Section heading
    top = matches[0]
    assert top.match_type == "context"
    assert top.confidence > 0.8


def test_heading_context_after_disambiguates(dup_doc):
    """context_after should boost the matching heading."""
    # The second "Section" heading is followed by "Content under the second Section heading."
    anchor = Anchor(by="heading", value="Section", context_after="second Section")
    matches = resolve_anchor(dup_doc, anchor)
    assert len(matches) >= 1
    top = matches[0]
    assert top.match_type == "context"


# --- occurrence out of range ---


def test_occurrence_out_of_range_raises_error(dup_doc):
    """occurrence=999 should raise OccurrenceOutOfRangeError."""
    anchor = Anchor(by="heading", value="Section", occurrence=999)
    with pytest.raises(OccurrenceOutOfRangeError) as exc_info:
        resolve_anchor(dup_doc, anchor)
    assert exc_info.value.requested == 999
    assert exc_info.value.available >= 1
