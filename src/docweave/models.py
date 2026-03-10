"""Pydantic models used by all backends."""

from __future__ import annotations

from pydantic import BaseModel, computed_field


class SourceSpan(BaseModel):
    start_line: int  # 1-based
    end_line: int  # 1-based inclusive


class Block(BaseModel):
    block_id: str  # e.g. "blk_001"
    kind: str
    section_path: list[str]
    text: str  # plain text content
    raw_text: str  # original source
    level: int | None = None
    source_span: SourceSpan
    stable_hash: str  # SHA-256[:16] of raw_text


class NormalizedDocument(BaseModel):
    file: str
    backend: str
    blocks: list[Block]
    metadata: dict = {}

    @property
    def headings(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "heading"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def heading_count(self) -> int:
        return len(self.headings)


class InspectResult(BaseModel):
    file: str
    backend: str
    tier: str
    editable: bool
    supports: dict
    fidelity: dict
    block_count: int
    headings: list[str]
