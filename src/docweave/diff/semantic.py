"""Block-level structural diff between two NormalizedDocuments."""

from __future__ import annotations

from pydantic import BaseModel

from docweave.models import NormalizedDocument


class BlockChange(BaseModel):
    block_id: str
    kind: str
    section_path: list[str]
    detail: str


class HeadingChange(BaseModel):
    block_id: str
    before_text: str
    after_text: str
    before_level: int | None
    after_level: int | None


class SemanticDiffReport(BaseModel):
    sections_added: list[str]
    sections_removed: list[str]
    blocks_added: list[BlockChange]
    blocks_removed: list[BlockChange]
    blocks_modified: list[BlockChange]
    headings_changed: list[HeadingChange]
    summary: str


def semantic_diff(
    before: NormalizedDocument, after: NormalizedDocument,
) -> SemanticDiffReport:
    """Compute structural diff between two parsed documents."""
    # Build lookup dicts
    before_by_hash: dict[str, str] = {}  # hash -> block_id
    after_by_hash: dict[str, str] = {}
    before_by_id = {b.block_id: b for b in before.blocks}
    after_by_id = {b.block_id: b for b in after.blocks}

    for b in before.blocks:
        before_by_hash.setdefault(b.stable_hash, b.block_id)
    for b in after.blocks:
        after_by_hash.setdefault(b.stable_hash, b.block_id)

    # Match by stable_hash first (unchanged blocks)
    matched_before: set[str] = set()
    matched_after: set[str] = set()

    for h in before_by_hash:
        if h in after_by_hash:
            matched_before.add(before_by_hash[h])
            matched_after.add(after_by_hash[h])

    # Unmatched blocks: match by block_id
    blocks_modified: list[BlockChange] = []
    for bid, blk_before in before_by_id.items():
        if bid in matched_before:
            continue
        if bid in after_by_id and bid not in matched_after:
            blk_after = after_by_id[bid]
            blocks_modified.append(BlockChange(
                block_id=bid,
                kind=blk_after.kind,
                section_path=blk_after.section_path,
                detail=(
                    f"Content changed "
                    f"(hash {blk_before.stable_hash[:8]}→{blk_after.stable_hash[:8]})"
                ),
            ))
            matched_before.add(bid)
            matched_after.add(bid)

    # Remaining unmatched
    blocks_removed: list[BlockChange] = []
    for bid, blk in before_by_id.items():
        if bid not in matched_before:
            blocks_removed.append(BlockChange(
                block_id=bid,
                kind=blk.kind,
                section_path=blk.section_path,
                detail=f"Block removed ({blk.kind})",
            ))

    blocks_added: list[BlockChange] = []
    for bid, blk in after_by_id.items():
        if bid not in matched_after:
            blocks_added.append(BlockChange(
                block_id=bid,
                kind=blk.kind,
                section_path=blk.section_path,
                detail=f"Block added ({blk.kind})",
            ))

    # Heading changes: subset of modified where kind == "heading"
    headings_changed: list[HeadingChange] = []
    for mc in blocks_modified:
        if mc.kind == "heading":
            blk_b = before_by_id[mc.block_id]
            blk_a = after_by_id[mc.block_id]
            headings_changed.append(HeadingChange(
                block_id=mc.block_id,
                before_text=blk_b.text,
                after_text=blk_a.text,
                before_level=blk_b.level,
                after_level=blk_a.level,
            ))

    # Section changes: compare unique section paths from headings
    before_sections = {"/".join(b.section_path) for b in before.blocks if b.kind == "heading"}
    after_sections = {"/".join(b.section_path) for b in after.blocks if b.kind == "heading"}
    sections_added = sorted(after_sections - before_sections)
    sections_removed = sorted(before_sections - after_sections)

    # Build summary
    parts: list[str] = []
    if blocks_added:
        parts.append(f"{len(blocks_added)} blocks added")
    if blocks_removed:
        parts.append(f"{len(blocks_removed)} blocks removed")
    if blocks_modified:
        parts.append(f"{len(blocks_modified)} blocks modified")
    summary = ", ".join(parts) if parts else "No changes"

    return SemanticDiffReport(
        sections_added=sections_added,
        sections_removed=sections_removed,
        blocks_added=blocks_added,
        blocks_removed=blocks_removed,
        blocks_modified=blocks_modified,
        headings_changed=headings_changed,
        summary=summary,
    )
