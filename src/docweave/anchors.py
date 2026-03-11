"""Anchor resolution — address blocks by heading, quote, ID, hash, or ordinal."""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, field_validator

from docweave.models import Block, NormalizedDocument, SourceSpan

AnchorType = Literal["heading", "quote", "ordinal", "block_id", "hash"]

_VALID_TYPES: set[str] = {"heading", "quote", "ordinal", "block_id", "hash"}


class OccurrenceOutOfRangeError(Exception):
    """Raised when the requested occurrence exceeds available matches."""

    def __init__(self, requested: int, available: int) -> None:
        self.requested = requested
        self.available = available
        super().__init__(
            f"Occurrence {requested} requested (1-indexed) but only"
            f" {available} block(s) match the anchor"
        )


class Anchor(BaseModel):
    by: AnchorType
    value: str
    occurrence: int = 1
    context_before: str | None = None
    context_after: str | None = None
    section: str | None = None
    index: int | None = None  # for ordinal

    @field_validator("by")
    @classmethod
    def _validate_by(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            msg = f"Unknown anchor type: {v!r}. Must be one of {sorted(_VALID_TYPES)}"
            raise ValueError(msg)
        return v


class AnchorMatch(BaseModel):
    block_id: str
    block_kind: str
    source_span: SourceSpan
    confidence: float
    match_type: str
    context: str

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        return round(v, 4)


def parse_anchor_spec(spec: str) -> Anchor:
    """Parse a string like 'heading:Purpose' or 'ordinal:paragraph:3' into an Anchor."""
    if ":" not in spec:
        msg = f"Invalid anchor spec {spec!r}: expected 'type:value'"
        raise ValueError(msg)

    anchor_type, _, remainder = spec.partition(":")
    if not remainder:
        msg = f"Invalid anchor spec {spec!r}: missing value after colon"
        raise ValueError(msg)

    if anchor_type not in _VALID_TYPES:
        msg = f"Unknown anchor type: {anchor_type!r}. Must be one of {sorted(_VALID_TYPES)}"
        raise ValueError(msg)

    if anchor_type == "ordinal":
        # ordinal:kind:N — rsplit on last colon
        if ":" not in remainder:
            msg = f"Invalid ordinal spec {spec!r}: expected 'ordinal:kind:N'"
            raise ValueError(msg)
        kind, _, n_str = remainder.rpartition(":")
        try:
            index = int(n_str)
        except ValueError:
            msg = f"Invalid ordinal index {n_str!r} in {spec!r}: must be an integer"
            raise ValueError(msg) from None
        return Anchor(by="ordinal", value=kind, index=index)

    return Anchor(by=anchor_type, value=remainder)


def _truncate(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _filter_by_section(doc: NormalizedDocument, section: str | None) -> list[tuple[int, Block]]:
    """Return (index, block) pairs, filtered by section if given (case-insensitive)."""
    pairs = list(enumerate(doc.blocks))
    if section:
        section_lower = section.lower()
        pairs = [
            (i, b) for i, b in pairs
            if any(s.lower() == section_lower for s in b.section_path)
        ]
    return pairs


def _resolve_block_id(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    matches = []
    for _i, block in _filter_by_section(doc, anchor.section):
        if block.block_id == anchor.value:
            matches.append(AnchorMatch(
                block_id=block.block_id,
                block_kind=block.kind,
                source_span=block.source_span,
                confidence=1.0,
                match_type="direct",
                context=_truncate(block.text),
            ))
    return matches


def _resolve_hash(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    matches = []
    for _i, block in _filter_by_section(doc, anchor.section):
        if block.stable_hash.startswith(anchor.value):
            matches.append(AnchorMatch(
                block_id=block.block_id,
                block_kind=block.kind,
                source_span=block.source_span,
                confidence=1.0,
                match_type="direct",
                context=_truncate(block.text),
            ))
    return matches


def _resolve_heading(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    matches = []
    filtered = _filter_by_section(doc, anchor.section)
    all_blocks = doc.blocks

    for i, block in filtered:
        if block.kind != "heading":
            continue
        text_lower = block.text.lower()
        value_lower = anchor.value.lower()

        if text_lower == value_lower:
            base_confidence = 1.0
            base_match_type = "exact"
        elif value_lower in text_lower:
            base_confidence = 0.8
            base_match_type = "substring"
        else:
            ratio = difflib.SequenceMatcher(None, text_lower, value_lower).ratio()
            if ratio >= 0.5:
                base_confidence = ratio
                base_match_type = "fuzzy"
            else:
                continue

        # Context boosting (same pattern as _resolve_quote)
        context_hits = 0
        if anchor.context_before and i > 0:
            prev_text = all_blocks[i - 1].text.lower()
            if anchor.context_before.lower() in prev_text:
                context_hits += 1
        if anchor.context_after and i < len(all_blocks) - 1:
            next_text = all_blocks[i + 1].text.lower()
            if anchor.context_after.lower() in next_text:
                context_hits += 1

        has_before = anchor.context_before is not None
        has_after = anchor.context_after is not None
        total_contexts = int(has_before) + int(has_after)

        if total_contexts > 0:
            if context_hits == total_contexts:
                confidence = min(base_confidence + 0.2, 1.0)
                match_type = "context"
            elif context_hits == 1:
                confidence = min(base_confidence + 0.1, 1.0)
                match_type = "context"
            else:
                # Context specified but none matched — penalize
                confidence = max(base_confidence - 0.2, 0.1)
                match_type = base_match_type
        else:
            confidence = base_confidence
            match_type = base_match_type

        matches.append(AnchorMatch(
            block_id=block.block_id,
            block_kind=block.kind,
            source_span=block.source_span,
            confidence=confidence,
            match_type=match_type,
            context=_truncate(block.text),
        ))
    return matches


def _resolve_quote(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    matches = []
    filtered = _filter_by_section(doc, anchor.section)
    all_blocks = doc.blocks

    for i, block in filtered:
        value_lower = anchor.value.lower()
        if value_lower not in block.text.lower():
            continue

        # Check context to boost confidence
        context_hits = 0
        if anchor.context_before and i > 0:
            prev_text = all_blocks[i - 1].text.lower()
            if anchor.context_before.lower() in prev_text:
                context_hits += 1
        if anchor.context_after and i < len(all_blocks) - 1:
            next_text = all_blocks[i + 1].text.lower()
            if anchor.context_after.lower() in next_text:
                context_hits += 1

        has_before = anchor.context_before is not None
        has_after = anchor.context_after is not None
        total_contexts = int(has_before) + int(has_after)

        if total_contexts == 0:
            confidence = 0.7
            match_type = "substring"
        elif context_hits == total_contexts:
            confidence = 1.0
            match_type = "context"
        elif context_hits == 1:
            confidence = 0.85
            match_type = "context"
        else:
            confidence = 0.7
            match_type = "substring"

        matches.append(AnchorMatch(
            block_id=block.block_id,
            block_kind=block.kind,
            source_span=block.source_span,
            confidence=confidence,
            match_type=match_type,
            context=_truncate(block.text),
        ))
    return matches


def _resolve_ordinal(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    kind = anchor.value
    n = anchor.index if anchor.index is not None else anchor.occurrence
    filtered = _filter_by_section(doc, anchor.section)

    count = 0
    for _i, block in filtered:
        if block.kind == kind:
            count += 1
            if count == n:
                return [AnchorMatch(
                    block_id=block.block_id,
                    block_kind=block.kind,
                    source_span=block.source_span,
                    confidence=1.0,
                    match_type="ordinal",
                    context=_truncate(block.text),
                )]
    return []


_STRATEGIES = {
    "block_id": _resolve_block_id,
    "hash": _resolve_hash,
    "heading": _resolve_heading,
    "quote": _resolve_quote,
    "ordinal": _resolve_ordinal,
}


def resolve_anchor(doc: NormalizedDocument, anchor: Anchor) -> list[AnchorMatch]:
    """Resolve an anchor against a document, returning matches sorted by confidence desc."""
    strategy = _STRATEGIES[anchor.by]
    matches = strategy(doc, anchor)
    matches.sort(key=lambda m: m.confidence, reverse=True)

    # Apply occurrence selection: among top-confidence matches, pick the Nth
    if matches and anchor.occurrence >= 1:
        top = matches[0].confidence
        top_matches = [m for m in matches if m.confidence == top]
        idx = anchor.occurrence - 1  # 1-based to 0-based
        if idx < len(top_matches):
            selected = top_matches[idx]
            # Move selected to front, keep rest for reporting
            matches = [selected] + [m for m in matches if m is not selected]
        else:
            raise OccurrenceOutOfRangeError(
                requested=anchor.occurrence, available=len(top_matches),
            )

    return matches


def search_blocks(doc: NormalizedDocument, query: str) -> list[AnchorMatch]:
    """Simple text search across all blocks. Case-insensitive."""
    matches = []
    query_lower = query.lower()
    for block in doc.blocks:
        text_lower = block.text.lower()
        if query_lower in text_lower:
            confidence = 1.0 if text_lower == query_lower else 0.7
            matches.append(AnchorMatch(
                block_id=block.block_id,
                block_kind=block.kind,
                source_span=block.source_span,
                confidence=confidence,
                match_type="exact" if confidence == 1.0 else "substring",
                context=_truncate(block.text),
            ))
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches
