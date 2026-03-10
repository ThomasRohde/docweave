"""Structural validation for NormalizedDocument."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from docweave.models import NormalizedDocument


class ValidationIssue(BaseModel):
    code: str
    message: str
    block_id: str | None = None
    severity: Literal["error", "warning"]


class ValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue]
    block_count: int


def validate_document(doc: NormalizedDocument) -> ValidationReport:
    """Validate structural integrity of a parsed document."""
    issues: list[ValidationIssue] = []

    # 1. Heading nesting: flag jumps > 1 level
    prev_level: int | None = None
    for blk in doc.blocks:
        if blk.kind == "heading" and blk.level is not None:
            if prev_level is not None and blk.level > prev_level + 1:
                issues.append(ValidationIssue(
                    code="HEADING_SKIP",
                    message=(
                        f"Heading level jumps from h{prev_level} to h{blk.level} "
                        f"at block {blk.block_id}"
                    ),
                    block_id=blk.block_id,
                    severity="warning",
                ))
            prev_level = blk.level

    # 2. Source span overlap: sort by start_line, check consecutive spans
    sorted_blocks = sorted(doc.blocks, key=lambda b: b.source_span.start_line)
    for i in range(len(sorted_blocks) - 1):
        cur = sorted_blocks[i]
        nxt = sorted_blocks[i + 1]
        if cur.source_span.end_line > nxt.source_span.start_line:
            issues.append(ValidationIssue(
                code="SPAN_OVERLAP",
                message=(
                    f"Block {cur.block_id} (ends line {cur.source_span.end_line}) "
                    f"overlaps with {nxt.block_id} (starts line {nxt.source_span.start_line})"
                ),
                block_id=cur.block_id,
                severity="error",
            ))

    # 3. Zero-length blocks: start_line > end_line
    for blk in doc.blocks:
        if blk.source_span.start_line > blk.source_span.end_line:
            issues.append(ValidationIssue(
                code="ZERO_LENGTH",
                message=f"Block {blk.block_id} has zero or negative length span",
                block_id=blk.block_id,
                severity="error",
            ))

    has_error = any(iss.severity == "error" for iss in issues)
    return ValidationReport(
        valid=not has_error,
        issues=issues,
        block_count=doc.block_count,
    )
