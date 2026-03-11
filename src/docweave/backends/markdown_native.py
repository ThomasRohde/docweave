"""Markdown backend using markdown-it-py."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from docweave.backends.base import BackendAdapter
from docweave.models import Block, HeadingInfo, InspectResult, NormalizedDocument, SourceSpan

_DOCWEAVE_COMMENT_RE = re.compile(
    r"^\s*<!--\s*docweave:\s*(\{.*\})\s*-->\s*$", re.DOTALL,
)


def _parse_docweave_comment(text: str) -> dict | None:
    """Extract JSON payload from a ``<!-- docweave: {...} -->`` comment."""
    m = _DOCWEAVE_COMMENT_RE.match(text.strip())
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


class MarkdownBackend(BackendAdapter):
    @property
    def name(self) -> str:
        return "markdown-native"

    @property
    def tier(self) -> int:
        return 0

    @property
    def extensions(self) -> set[str]:
        return {".md", ".markdown"}

    def detect(self, path: Path) -> float:
        return 1.0 if path.suffix.lower() in self.extensions else 0.0

    def _parse_source(self, source: str, file_label: str) -> NormalizedDocument:
        """Parse raw Markdown source into a NormalizedDocument."""
        lines = source.splitlines(keepends=True)
        md = MarkdownIt("commonmark")
        md.enable("table")
        tokens = md.parse(source)

        blocks: list[Block] = []
        heading_stack: list[str] = []
        pending_annotations: dict[str, Any] = {}
        seq = 0
        i = 0

        while i < len(tokens):
            tok = tokens[i]

            if tok.type == "heading_open":
                level = int(tok.tag[1:])
                text = tokens[i + 1].content
                token_map = tok.map

                # Update heading stack: pop to level-1, push current heading
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(text)

                seq += 1
                raw = _extract_raw(lines, token_map)
                annotations = pending_annotations
                pending_annotations = {}
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="heading",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=level,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                    annotations=annotations,
                ))
                i += 3

            elif tok.type == "paragraph_open" and tok.level == 0:
                text = tokens[i + 1].content
                token_map = tok.map

                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="paragraph",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i += 3

            elif tok.type in ("bullet_list_open", "ordered_list_open") and tok.level == 0:
                kind = "unordered_list" if tok.type == "bullet_list_open" else "ordered_list"
                close_type = tok.type.replace("_open", "_close")
                token_map = tok.map

                # Collect inline content from list items, tracking nesting depth
                item_texts: list[str] = []
                j = i + 1
                depth = 1
                while j < len(tokens) and depth > 0:
                    if tokens[j].type == tok.type:
                        depth += 1
                    elif tokens[j].type == close_type:
                        depth -= 1
                        if depth == 0:
                            break
                    if tokens[j].type == "inline":
                        item_texts.append(tokens[j].content)
                    j += 1

                text = "\n".join(item_texts)
                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind=kind,
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i = j + 1

            elif tok.type in ("fence", "code_block"):
                token_map = tok.map
                text = tok.content

                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="code_block",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i += 1

            elif tok.type == "hr":
                token_map = tok.map

                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="thematic_break",
                    section_path=list(heading_stack),
                    text="",
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i += 1

            elif tok.type == "blockquote_open":
                close_type = "blockquote_close"
                token_map = tok.map

                # Collect inline content within the blockquote
                bq_texts: list[str] = []
                j = i + 1
                while j < len(tokens) and tokens[j].type != close_type:
                    if tokens[j].type == "inline":
                        bq_texts.append(tokens[j].content)
                    j += 1

                text = "\n".join(bq_texts)
                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="blockquote",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i = j + 1

            elif tok.type == "table_open":
                token_map = tok.map

                # Collect inline content from table cells
                tbl_texts: list[str] = []
                j = i + 1
                while j < len(tokens) and tokens[j].type != "table_close":
                    if tokens[j].type == "inline":
                        tbl_texts.append(tokens[j].content)
                    j += 1

                text = "\n".join(tbl_texts)
                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="table",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i = j + 1

            elif tok.type == "html_block":
                token_map = tok.map
                text = tok.content

                # Check for docweave annotation comment
                parsed = _parse_docweave_comment(text)
                if parsed is not None:
                    pending_annotations = parsed
                    i += 1
                    continue

                seq += 1
                raw = _extract_raw(lines, token_map)
                blocks.append(Block(
                    block_id=f"blk_{seq:03d}",
                    kind="html_block",
                    section_path=list(heading_stack),
                    text=text,
                    raw_text=raw,
                    level=None,
                    source_span=SourceSpan(
                        start_line=token_map[0] + 1,
                        end_line=token_map[1],
                    ),
                    stable_hash=_hash(raw),
                ))
                i += 1

            else:
                i += 1

        return NormalizedDocument(
            file=file_label,
            backend=self.name,
            blocks=blocks,
        )

    def load_view(self, path: Path) -> NormalizedDocument:
        source = path.read_text("utf-8-sig")
        return self._parse_source(source, str(path))

    def inspect(self, path: Path) -> InspectResult:
        doc = self.load_view(path)
        return InspectResult(
            file=str(path),
            backend=self.name,
            tier="native-safe",
            editable=os.access(path, os.W_OK),
            supports={
                "comments": False,
                "tables": True,
                "styles": False,
                "track_changes": False,
            },
            fidelity={
                "write_mode": "native",
                "roundtrip_risk": "low",
            },
            block_count=doc.block_count,
            headings=[
                HeadingInfo(
                    text=b.text, level=b.level or 1,
                    block_id=b.block_id, section_path=b.section_path,
                    annotations=b.annotations,
                )
                for b in doc.blocks if b.kind == "heading"
            ],
        )

    def resolve_anchor(self, view: Any, anchor: dict[str, Any]) -> Any:
        from docweave.anchors import Anchor
        from docweave.anchors import resolve_anchor as _resolve

        parsed = Anchor(**anchor) if isinstance(anchor, dict) else anchor
        return _resolve(view, parsed)

    def plan(self, view: Any, patches: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("Use generate_plan() directly")

    def apply(self, view: Any, plan: dict[str, Any]) -> str:
        raise NotImplementedError("Use apply_plan() directly")

    def validate(self, original: str, modified: str) -> list[dict[str, Any]]:
        from docweave.validation import validate_document

        doc = self._parse_source(modified, "<validate>")
        report = validate_document(doc)
        return [iss.model_dump() for iss in report.issues]

    def diff(self, original: str, modified: str) -> dict[str, Any]:
        from docweave.diff.semantic import semantic_diff

        before_doc = self._parse_source(original, "<diff:before>")
        after_doc = self._parse_source(modified, "<diff:after>")
        report = semantic_diff(before_doc, after_doc)
        return report.model_dump(mode="json")


def _extract_raw(lines: list[str], token_map: list[int]) -> str:
    return "".join(lines[token_map[0]:token_map[1]])


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
